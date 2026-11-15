"""Local models through Ollama (`/api/chat` with a JSON-schema `format`), $0 and no quota.

The model runs on Mojeeb's Mac, so there is no daily limit — only speed. Two things
matter for correctness:

- `num_ctx` must hold the whole prompt. Ollama silently drops the start of a prompt
  that is longer than the context window, so a prompt that fills the window is
  treated as an error instead of a result.
- When Ollama is not running, or the model is not pulled, the provider raises
  `ProviderUnavailable` so a pool moves on to the next model (e.g. Gemini).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx

from qv.providers.llm.base import (
    LLMError, LLMSchemaError, Message, ProviderUnavailable, RawResponse, TransientError,
)
from qv.providers.usage import CallContext, UsageRecorder

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider:
    """Ollama REST client implementing LLMProvider."""

    name = "ollama"

    def __init__(self, recorder: UsageRecorder, *, base_url: str = DEFAULT_BASE_URL,
                 model_options: dict[str, dict[str, Any]] | None = None, client: httpx.Client | None = None,
                 timeout_s: float = 900.0, keep_alive: str = "10m") -> None:
        """`model_options` per model id: `num_ctx`, `temperature`, `think`, `num_predict`."""
        self._recorder = recorder
        self._base = base_url.rstrip("/")
        self._opts = model_options or {}
        self._client = client or httpx.Client(timeout=timeout_s)
        self._keep_alive = keep_alive

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        """One non-streaming chat request whose output must follow `schema`."""
        opts = dict(self._opts.get(model, {}))
        think = opts.pop("think", False)
        num_ctx = int(opts.get("num_ctx", 16384))
        opts["num_ctx"] = num_ctx
        opts.setdefault("temperature", 0)
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}]
                        + [{"role": "assistant" if m.role == "model" else "user", "content": m.text}
                           for m in messages],
            "format": schema,
            "stream": False,
            "think": think,
            "keep_alive": self._keep_alive,
            "options": opts,
        }
        start = time.monotonic()
        try:
            resp = self._client.post(f"{self._base}/api/chat", json=body)
        except httpx.ConnectError as exc:
            self._log(model, ctx, "error", None, start, error=f"not running: {exc}")
            raise ProviderUnavailable(f"ollama: not reachable at {self._base} (is Ollama running?)") from exc
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
            message = (data.get("error") if isinstance(data, dict) else None) or f"HTTP {resp.status_code}"
            self._log(model, ctx, "error", resp.status_code, start, error=message)
            if resp.status_code == 404:
                raise ProviderUnavailable(f"ollama: {message} (run `ollama pull {model}`)")
            if resp.status_code >= 500:
                raise TransientError(f"{model}: HTTP {resp.status_code} {message}")
            raise LLMError(f"{model}: HTTP {resp.status_code} {message}")

        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        tokens = dict(input_tokens=prompt_tokens, output_tokens=int(data.get("eval_count") or 0))
        text = (data.get("message") or {}).get("content", "")
        finish = data.get("done_reason")
        if prompt_tokens >= num_ctx:
            self._log(model, ctx, "error", 200, start, error=f"prompt filled num_ctx={num_ctx}", **tokens)
            raise LLMError(f"{model}: prompt ({prompt_tokens} tokens) does not fit num_ctx={num_ctx}; "
                           "raise num_ctx in config/providers.yaml")
        call_id = self._log(model, ctx, "ok", 200, start, **tokens)
        if finish == "length":
            raise LLMSchemaError(f"{model}: output cut off at the token limit", text)
        return RawResponse(text=text, model=data.get("model") or model, finish_reason=finish,
                           api_call_id=call_id, **tokens)

    def _log(self, model: str, ctx: CallContext, status: str, http_status: int | None, start: float,
             **kw: Any) -> int:
        return self._recorder.record(provider=self.name, kind="llm", status=status, ctx=ctx, model=model,
                                     http_status=http_status, credits=0,
                                     latency_ms=int((time.monotonic() - start) * 1000), **kw)
