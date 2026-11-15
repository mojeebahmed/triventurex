"""Gemini provider (recorded responses via respx) and model pools with free-quota fallback."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel
from sqlalchemy import select

from qv.db.models import ApiCall
from qv.db.session import Database
from qv.domain.stages import Decomposition, Extraction
from qv.providers.llm.base import (
    DailyQuotaError, LLMRefusal, LLMSchemaError, Message, ModelPool, RateLimitError, RawResponse, TransientError,
    json_schema_for,
)
from qv.providers.llm.gemini import API_BASE, GeminiProvider, classify_429
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted, QuotaLedger, RateLimiter, UsageRecorder

URL = f"{API_BASE}/models/m1:generateContent"


class Small(BaseModel):
    """Test schema."""

    city: str
    note: str | None


def ok_body(text: str, finish: str = "STOP", thought: bool = False) -> dict:
    parts = ([{"text": "thinking…", "thought": True}] if thought else []) + [{"text": text}]
    return {"candidates": [{"content": {"parts": parts}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7, "thoughtsTokenCount": 3},
            "modelVersion": "m1-001", "responseId": "r1"}


def quota_body(quota_id: str, delay: str = "13s") -> dict:
    return {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]}}


@pytest.fixture
def gemini(db: Database) -> GeminiProvider:
    return GeminiProvider("test-key", UsageRecorder(db), client=httpx.Client())


def call(p: GeminiProvider) -> RawResponse:
    return p.generate_json(model="m1", system="sys", messages=[Message("user", "hi")],
                           schema=json_schema_for(Small), ctx=CallContext(stage="s1a"))


def test_schema_for_structured_output_is_self_contained() -> None:
    schema = json_schema_for(Extraction)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and '"title"' not in text
    assert schema["additionalProperties"] is False
    assert schema["properties"]["passages"]["items"]["additionalProperties"] is False
    assert set(schema["required"]) == {"page", "passages", "no_relevant_content_reason"}


@respx.mock
def test_success_skips_thoughts_and_logs_usage(gemini: GeminiProvider, db: Database) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body('{"city":"Oslo","note":null}',
                                                                                thought=True)))
    raw = call(gemini)
    assert raw.text == '{"city":"Oslo","note":null}'
    assert (raw.input_tokens, raw.output_tokens, raw.thinking_tokens) == (11, 7, 3)
    req = route.calls.last.request
    assert req.headers["x-goog-api-key"] == "test-key" and "key=" not in str(req.url)
    body = json.loads(req.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["systemInstruction"]["parts"][0]["text"] == "sys"
    with db.session() as s:
        row = s.scalar(select(ApiCall))
        assert (row.status, row.stage, row.input_tokens, row.response_id) == ("ok", "s1a", 11, "r1")


@respx.mock
def test_daily_quota_429(gemini: GeminiProvider) -> None:
    respx.post(URL).mock(return_value=httpx.Response(
        429, json=quota_body("GenerateRequestsPerDayPerProjectPerModel-FreeTier")))
    with pytest.raises(DailyQuotaError):
        call(gemini)


@respx.mock
def test_per_minute_429(gemini: GeminiProvider) -> None:
    respx.post(URL).mock(return_value=httpx.Response(
        429, json=quota_body("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "13s")))
    with pytest.raises(RateLimitError) as exc:
        call(gemini)
    assert exc.value.retry_after == 14


def test_classify_429_defaults() -> None:
    assert classify_429({}) == (False, 20.0)


@respx.mock
@pytest.mark.parametrize("response,error", [
    (httpx.Response(503, json={"error": {"message": "overloaded"}}), TransientError),
    (httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), LLMRefusal),
    (httpx.Response(200, json=ok_body("{}", finish="SAFETY")), LLMRefusal),
    (httpx.Response(200, json=ok_body('{"city": "Os', finish="MAX_TOKENS")), LLMSchemaError),
])
def test_error_mapping(gemini: GeminiProvider, response: httpx.Response, error: type[Exception]) -> None:
    respx.post(URL).mock(return_value=response)
    with pytest.raises(error):
        call(gemini)


def test_missing_key_is_refused(db: Database) -> None:
    with pytest.raises(Exception, match="GEMINI_API_KEY"):
        GeminiProvider("", UsageRecorder(db))


# --- model pool -----------------------------------------------------------------

class ScriptedProvider:
    """Returns scripted responses or raises scripted errors, per model."""

    name = "fake"

    def __init__(self, script: dict[str, list[Any]]) -> None:
        self.script = script
        self.calls: list[tuple[str, list[Message]]] = []

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        self.calls.append((model, list(messages)))
        item = self.script[model].pop(0)
        if isinstance(item, Exception):
            raise item
        return RawResponse(text=item, model=model, finish_reason="STOP")


def make_pool(db: Database, script: dict[str, list[Any]], rpd: int = 100) -> tuple[ModelPool, ScriptedProvider]:
    prov = ScriptedProvider(script)
    metering = Metering(QuotaLedger(db, reserve_fraction=0), RateLimiter(sleep=lambda s: None), UsageRecorder(db))
    models = list(script)
    pool = ModelPool(prov, models, {m: [Limit("day", rpd)] for m in models}, {m: 1000 for m in models}, metering)
    return pool, prov


def test_pool_falls_back_when_daily_quota_is_used_up(db: Database) -> None:
    pool, prov = make_pool(db, {"a": [DailyQuotaError("a used up")], "b": ['{"city":"X","note":null}']})
    res = pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())
    assert res.model == "b" and res.output.city == "X"
    assert pool.available_models() == ["b"]  # 'a' marked exhausted for today


def test_pool_skips_models_without_ledger_quota(db: Database) -> None:
    pool, prov = make_pool(db, {"a": [], "b": ['{"city":"X","note":null}']}, rpd=1)
    pool.metering.ledger.record("fake", "a", 1, [Limit("day", 1)])
    pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())
    assert [m for m, _ in prov.calls] == ["b"]


def test_pool_raises_quota_exhausted_when_nothing_is_left(db: Database) -> None:
    pool, _ = make_pool(db, {"a": [DailyQuotaError("x")], "b": [DailyQuotaError("y")]})
    with pytest.raises(QuotaExhausted):
        pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())


def test_pool_retries_rate_limits_on_the_same_model(db: Database) -> None:
    pool, prov = make_pool(db, {"a": [RateLimitError("slow down", 1), '{"city":"X","note":null}'], "b": []})
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext()).model == "a"
    assert len(prov.calls) == 2


def test_pool_retries_schema_errors_once_with_feedback(db: Database) -> None:
    pool, prov = make_pool(db, {"a": ['{"city": 5}', '{"city":"X","note":null}']})
    res = pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())
    assert res.attempts == 2
    retry_messages = prov.calls[1][1]
    assert retry_messages[-1].role == "user" and "rejected" in retry_messages[-1].text


def test_pool_gives_up_after_second_schema_error(db: Database) -> None:
    pool, _ = make_pool(db, {"a": ["not json", '{"city": 5}']})
    with pytest.raises(LLMSchemaError):
        pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())


def test_pool_counts_every_request_in_the_ledger(db: Database) -> None:
    pool, _ = make_pool(db, {"a": ['{"city": 5}', '{"city":"X","note":null}']})
    pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())
    assert pool.metering.ledger.remaining("fake", "a", Limit("day", 100)) == 98


def test_decomposition_schema_validates_design_example() -> None:
    """The S1a example in prompts/ (Football Quest #70) is a valid Decomposition."""
    from pathlib import Path
    import re
    text = (Path(__file__).parents[1] / "prompts/s1a-question-decomposition.md").read_text()
    example = re.findall(r"```json\n(.*?)\n```", text, re.S)[-1]
    Decomposition.model_validate_json(example)
