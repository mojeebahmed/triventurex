"""Google Gemini API (generateContent with structured JSON output), free tier.

Only the REST endpoint is used (httpx), so tests can replay recorded responses
with respx. The API key goes in a header, never in the URL.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import Any

import httpx

from qv.providers.llm.base import (
    DailyQuotaError, LLMError, LLMRefusal, LLMSchemaError, Message, RateLimitError, RawResponse, TransientError,
)
from qv.providers.usage import CallContext, UsageRecorder

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_BLOCK_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY", "OTHER"}


class GeminiProvider:
    """Gemini REST client implementing LLMProvider."""

    name = "gemini"

    def __init__(self, api_key: str, recorder: UsageRecorder, *, client: httpx.Client | None = None,
                 timeout_s: float = 120.0, max_output_tokens: int = 16384) -> None:
        """`client` is injectable for tests."""
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set (put it in .env)")
        self._key = api_key
        self._recorder = recorder
        self._client = client or httpx.Client(timeout=timeout_s)
        self._max_output_tokens = max_output_tokens

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        """One generateContent request with responseJsonSchema."""
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": m.role, "parts": [{"text": m.text}]} for m in messages],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "maxOutputTokens": self._max_output_tokens,
            },
        }
        start = time.monotonic()
        try:
            resp = self._client.post(f"{API_BASE}/models/{model}:generateContent",
                                     headers={"x-goog-api-key": self._key}, json=body)
        except httpx.TimeoutException as exc:
            self._log(model, ctx, "error", None, start, error=f"timeout: {exc}")
            raise TransientError(f"{model}: timeout") from exc
        except httpx.HTTPError as exc:
            self._log(model, ctx, "error", None, start, error=str(exc))
            raise TransientError(f"{model}: {exc}") from exc

        data: dict[str, Any] = {}
        try:
            data = resp.json()
        except ValueError:
            pass
        if resp.status_code != 200:
            self._raise_for_status(model, ctx, resp.status_code, data, start)

        usage = data.get("usageMetadata", {})
        tokens = dict(input_tokens=int(usage.get("promptTokenCount", 0)),
                      output_tokens=int(usage.get("candidatesTokenCount", 0)),
                      thinking_tokens=int(usage.get("thoughtsTokenCount", 0)))
        response_id = data.get("responseId")
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            self._log(model, ctx, "refused", 200, start, response_id=response_id, error=f"blocked: {block}", **tokens)
            raise LLMRefusal(f"{model}: prompt blocked ({block})")
        candidates = data.get("candidates") or []
        if not candidates:
            self._log(model, ctx, "error", 200, start, response_id=response_id, error="no candidates", **tokens)
            raise TransientError(f"{model}: response without candidates")
        cand = candidates[0]
        finish = cand.get("finishReason")
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", [])
                       if not p.get("thought"))
        if finish in _BLOCK_REASONS:
            self._log(model, ctx, "refused", 200, start, response_id=response_id, error=f"finish: {finish}",
                      **tokens)
            raise LLMRefusal(f"{model}: response stopped ({finish})")
        call_id = self._log(model, ctx, "ok", 200, start, response_id=response_id, **tokens)
        if finish == "MAX_TOKENS":
            raise LLMSchemaError(f"{model}: output cut off at the token limit", text)
        return RawResponse(text=text, model=data.get("modelVersion") or model, finish_reason=finish,
                           response_id=response_id, api_call_id=call_id, **tokens)

    def _raise_for_status(self, model: str, ctx: CallContext, status: int, data: dict[str, Any],
                          start: float) -> None:
        err = data.get("error", {}) if isinstance(data, dict) else {}
        message = err.get("message", "") or f"HTTP {status}"
        if status == 429:
            daily, retry_after = classify_429(err)
            self._log(model, ctx, "quota", status, start, error=message)
            if daily:
                raise DailyQuotaError(f"{model}: {message}")
            raise RateLimitError(f"{model}: {message}", retry_after)
        self._log(model, ctx, "error", status, start, error=message)
        if status >= 500:
            raise TransientError(f"{model}: HTTP {status} {message}")
        raise LLMError(f"{model}: HTTP {status} {message}")

    def _log(self, model: str, ctx: CallContext, status: str, http_status: int | None, start: float,
             **kw: Any) -> int:
        return self._recorder.record(provider=self.name, kind="llm", status=status, ctx=ctx, model=model,
                                     http_status=http_status, credits=1,
                                     latency_ms=int((time.monotonic() - start) * 1000), **kw)


def classify_429(error: dict[str, Any]) -> tuple[bool, float]:
    """(is_daily_quota, retry_after_seconds) from a Gemini 429 error body.

    Daily/free-tier-per-day violations name a quota id containing 'PerDay'; per-minute
    ones contain 'PerMinute'. RetryInfo gives the suggested delay.
    """
    daily = False
    retry_after = 20.0
    for detail in error.get("details", []) or []:
        kind = detail.get("@type", "")
        if kind.endswith("QuotaFailure"):
            for v in detail.get("violations", []) or []:
                qid = f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}"
                if "PerDay" in qid or "per_day" in qid.lower():
                    daily = True
        elif kind.endswith("RetryInfo"):
            m = re.match(r"([\d.]+)s", str(detail.get("retryDelay", "")))
            if m:
                retry_after = float(m.group(1)) + 1
    return daily, retry_after
