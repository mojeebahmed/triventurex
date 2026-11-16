"""Provider-neutral LLM interface, structured-output validation and model pools."""

from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """A model call failed in a way the caller should know about."""


class LLMRefusal(LLMError):
    """The model or its safety filter declined to answer (routed to review later)."""


class LLMSchemaError(LLMError):
    """The response was not valid JSON for the schema, even after one retry."""

    def __init__(self, message: str, raw_text: str = "") -> None:
        """Keep the raw text for diagnosis."""
        super().__init__(message)
        self.raw_text = raw_text


class DailyQuotaError(LLMError):
    """The provider reports that this model's daily (or longer) quota is used up."""


class RateLimitError(LLMError):
    """The provider reports a per-minute limit; retry after `retry_after` seconds."""

    def __init__(self, message: str, retry_after: float = 20.0) -> None:
        """`retry_after` comes from the provider's RetryInfo when given."""
        super().__init__(message)
        self.retry_after = retry_after


class TransientError(LLMError):
    """Server error or timeout; worth retrying with backoff."""


class ProviderUnavailable(LLMError):
    """The provider cannot serve this model right now (local server down, model not installed).

    A pool moves on to its next model without marking any quota as used up.
    """


@dataclass(frozen=True)
class Message:
    """One chat turn."""

    role: str  # "user" | "model"
    text: str


@dataclass
class RawResponse:
    """What a provider returns for one request (before schema validation)."""

    text: str
    model: str
    finish_reason: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    response_id: str | None = None
    api_call_id: int | None = None


@dataclass
class StructuredResult:
    """A validated structured output and how it was produced."""

    output: BaseModel
    provider: str
    model: str
    raw_text: str
    attempts: int
    api_call_ids: list[int] = field(default_factory=list)


class LLMProvider(Protocol):
    """One LLM provider. Implementations meter and log every request themselves."""

    name: str

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        """Send one request that must return JSON for `schema`. Raises the errors above."""
        ...


def json_schema_for(model_cls: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for structured output: refs inlined, titles and defaults removed."""
    schema = model_cls.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items() if k not in ("title", "default")}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


def parse_structured(text: str, model_cls: type[T]) -> T:
    """Parse and validate a JSON response; raises LLMSchemaError with a readable reason."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMSchemaError(f"Response is not valid JSON: {exc}", text) from exc
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:10])
        raise LLMSchemaError(f"Response does not match the schema: {errors}", text) from exc


@dataclass(frozen=True)
class PoolEntry:
    """One model of one provider inside a pool, with the limits we allow ourselves."""

    provider: LLMProvider
    model: str
    limits: list[Limit]
    rpm: int

    @property
    def label(self) -> str:
        """`provider/model`, as written in config/providers.yaml."""
        return f"{self.provider.name}/{self.model}"


class ModelPool:
    """Runs a structured request on the first model in a pool that can serve it.

    Entries may come from different providers (e.g. a local Ollama model first, Gemini after it).

    - Daily quota used up (ledger or provider 429) → the next entry takes over.
    - Provider unavailable (local server down, model not pulled) → the next entry, nothing marked.
    - Per-minute limit → wait and retry the same model.
    - Server errors → retry with backoff (bounded), then the next entry takes over (overloaded models
      are common on the free tier); only when every entry failed is the error raised.
    - Invalid JSON / schema → one retry on the same model with the error, then LLMSchemaError.
    """

    MAX_RATE_RETRIES = 4
    MAX_TRANSIENT_RETRIES = 3

    def __init__(self, entries: list[PoolEntry], metering: Metering) -> None:
        """`entries` in fallback order."""
        if not entries:
            raise ValueError("A model pool needs at least one model")
        self.entries = entries
        self.metering = metering
        self.last_provider = entries[0].provider.name

    @classmethod
    def single(cls, provider: LLMProvider, models: list[str], limits: dict[str, list[Limit]],
               rpm: dict[str, int], metering: Metering) -> ModelPool:
        """A pool whose models all come from one provider."""
        return cls([PoolEntry(provider, m, limits[m], rpm[m]) for m in models], metering)

    def _can_spend(self, e: PoolEntry) -> bool:
        return self.metering.ledger.can_spend(e.provider.name, e.model, 1, e.limits)

    def available_models(self) -> list[str]:
        """Labels (`provider/model`) of the entries that still have free quota now."""
        return [e.label for e in self.entries if self._can_spend(e)]

    def complete(self, *, system: str, user: str, schema_cls: type[T], ctx: CallContext) -> StructuredResult:
        """Return a validated output, falling back across entries; raises QuotaExhausted when none is left."""
        schema = json_schema_for(schema_cls)
        last_error: Exception | None = None
        transient: TransientError | None = None
        for e in self.entries:
            if not self._can_spend(e):
                continue
            self.last_provider = e.provider.name
            try:
                return self._complete_on(e, system, user, schema, schema_cls, ctx)
            except DailyQuotaError as exc:
                self.metering.ledger.mark_exhausted(e.provider.name, e.model, e.limits)
                last_error = exc
            except ProviderUnavailable as exc:
                last_error = exc
            except TransientError as exc:
                last_error = transient = exc
        if transient is not None:
            raise transient
        raise QuotaExhausted(
            f"No model available now in pool {[e.label for e in self.entries]}"
            + (f" (last error: {last_error})" if last_error else "")
        )

    def _complete_on(self, e: PoolEntry, system: str, user: str, schema: dict[str, Any],
                     schema_cls: type[T], ctx: CallContext) -> StructuredResult:
        messages = [Message("user", user)]
        call_ids: list[int] = []
        attempts = 0
        schema_retry_used = False
        while True:
            raw = self._send(e, system, messages, schema, ctx, call_ids)
            attempts += 1
            try:
                out = parse_structured(raw.text, schema_cls)
                return StructuredResult(out, e.provider.name, raw.model or e.model, raw.text, attempts, call_ids)
            except LLMSchemaError as exc:
                if schema_retry_used:
                    raise
                schema_retry_used = True
                messages = [*messages, Message("model", raw.text), Message(
                    "user", f"Your previous answer was rejected: {exc}. Reply again with JSON that matches "
                            "the schema exactly.")]

    def _send(self, e: PoolEntry, system: str, messages: list[Message], schema: dict[str, Any],
              ctx: CallContext, call_ids: list[int]) -> RawResponse:
        ledger, model = self.metering.ledger, e.model
        rate_retries = transient_retries = 0
        while True:
            if not self._can_spend(e):
                raise DailyQuotaError(f"{model}: free daily quota used up (ledger)")
            self.metering.limiter.wait(e.label, e.rpm)
            try:
                raw = e.provider.generate_json(model=model, system=system, messages=messages,
                                               schema=schema, ctx=ctx)
                ledger.record(e.provider.name, model, 1, e.limits)
                if raw.api_call_id:
                    call_ids.append(raw.api_call_id)
                return raw
            except RateLimitError as exc:
                rate_retries += 1
                if rate_retries > self.MAX_RATE_RETRIES:
                    raise DailyQuotaError(f"{model}: still rate-limited after {rate_retries} waits") from exc
                self.metering.limiter.penalise(e.label, exc.retry_after)
            except TransientError:
                transient_retries += 1
                ledger.record(e.provider.name, model, 1, e.limits)
                if transient_retries > self.MAX_TRANSIENT_RETRIES:
                    raise
                self.metering.limiter.penalise(e.label, 2 ** transient_retries)
            except (LLMRefusal, LLMSchemaError):
                ledger.record(e.provider.name, model, 1, e.limits)
                raise
