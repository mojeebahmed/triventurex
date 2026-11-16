"""Local Ollama provider (recorded responses via respx), cross-provider pools and pool config."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from pydantic import BaseModel
from sqlalchemy import select

from qv.config import CONFIG_DIR, Settings, load_providers_config, split_entry
from qv.db.models import ApiCall
from qv.db.session import Database
from qv.providers.llm.base import (
    LLMError, LLMSchemaError, Message, ModelPool, PoolEntry, ProviderUnavailable, RawResponse, TransientError,
    json_schema_for,
)
from qv.providers.llm.ollama import OllamaProvider
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted, QuotaLedger, RateLimiter, UsageRecorder
from qv.services.research import build_llm_providers, build_pools, pool_entries

URL = "http://localhost:11434/api/chat"


class Small(BaseModel):
    """Test schema."""

    city: str


def ok_body(text: str, prompt_tokens: int = 50, done_reason: str = "stop") -> dict:
    return {"model": "qwen3:14b", "message": {"role": "assistant", "content": text}, "done": True,
            "done_reason": done_reason, "prompt_eval_count": prompt_tokens, "eval_count": 9}


@pytest.fixture
def ollama(db: Database) -> OllamaProvider:
    return OllamaProvider(UsageRecorder(db), model_options={"qwen3:14b": {"num_ctx": 4096, "think": False}},
                          client=httpx.Client())


def call(p: OllamaProvider, messages: list[Message] | None = None) -> RawResponse:
    return p.generate_json(model="qwen3:14b", system="sys", messages=messages or [Message("user", "hi")],
                           schema=json_schema_for(Small), ctx=CallContext(stage="s3"))


@respx.mock
def test_request_shape_and_result(ollama: OllamaProvider, db: Database) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body('{"city":"Oslo"}')))
    raw = call(ollama, [Message("user", "a"), Message("model", "b"), Message("user", "c")])
    assert raw.text == '{"city":"Oslo"}' and raw.input_tokens == 50 and raw.output_tokens == 9
    body = json.loads(route.calls[0].request.content)
    assert body["format"]["properties"]["city"]["type"] == "string"
    assert body["stream"] is False and body["think"] is False
    assert body["options"] == {"num_ctx": 4096, "temperature": 0}
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    with db.session() as s:
        row = s.scalar(select(ApiCall))
        assert (row.provider, row.model, row.status, row.credits) == ("ollama", "qwen3:14b", "ok", 0)


@respx.mock
def test_prompt_that_fills_the_context_is_an_error(ollama: OllamaProvider) -> None:
    """Ollama silently drops the start of a too-long prompt; we never accept that output."""
    respx.post(URL).mock(return_value=httpx.Response(200, json=ok_body('{"city":"X"}', prompt_tokens=4096)))
    with pytest.raises(LLMError, match="num_ctx"):
        call(ollama)


@respx.mock
@pytest.mark.parametrize("response,error", [
    (httpx.ConnectError("refused"), ProviderUnavailable),
    (httpx.Response(404, json={"error": "model 'qwen3:14b' not found"}), ProviderUnavailable),
    (httpx.Response(500, json={"error": "boom"}), TransientError),
    (httpx.Response(200, json=ok_body('{"city": "Os', done_reason="length")), LLMSchemaError),
])
def test_error_mapping(ollama: OllamaProvider, response: object, error: type[Exception]) -> None:
    route = respx.post(URL)
    if isinstance(response, Exception):
        route.mock(side_effect=response)
    else:
        route.mock(return_value=response)
    with pytest.raises(error):
        call(ollama)


# --- cross-provider pools -----------------------------------------------------------

class Fake:
    """A provider that answers or raises one scripted item per call."""

    def __init__(self, name: str, items: list[object]) -> None:
        self.name = name
        self.items = items
        self.calls = 0

    def generate_json(self, *, model, system, messages, schema, ctx):  # noqa: ANN001, ANN201
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return RawResponse(text=item, model=model, finish_reason="stop")


def metering(db: Database) -> Metering:
    return Metering(QuotaLedger(db, reserve_fraction=0), RateLimiter(sleep=lambda s: None), UsageRecorder(db))


def test_pool_moves_on_when_local_model_is_unavailable(db: Database) -> None:
    local = Fake("ollama", [ProviderUnavailable("down")])
    cloud = Fake("gemini", ['{"city":"X"}'])
    m = metering(db)
    pool = ModelPool([PoolEntry(local, "q", [], 60), PoolEntry(cloud, "g", [Limit("day", 10)], 60)], m)
    res = pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())
    assert (res.provider, res.model) == ("gemini", "g")
    assert pool.available_models() == ["ollama/q", "gemini/g"]  # nothing marked used up
    assert m.ledger.remaining("gemini", "g", Limit("day", 10)) == 9


def test_local_model_first_spends_no_quota(db: Database) -> None:
    local = Fake("ollama", ['{"city":"X"}'])
    cloud = Fake("gemini", [])
    pool = ModelPool([PoolEntry(local, "q", [], 60), PoolEntry(cloud, "g", [Limit("day", 10)], 60)], metering(db))
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext()).provider == "ollama"
    assert cloud.calls == 0


def test_pool_with_nothing_available_raises_quota_exhausted(db: Database) -> None:
    pool = ModelPool([PoolEntry(Fake("ollama", [ProviderUnavailable("down")]), "q", [], 60)], metering(db))
    with pytest.raises(QuotaExhausted, match="down"):
        pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())


# --- config ------------------------------------------------------------------------

def test_split_entry_keeps_colons_in_model_names() -> None:
    assert split_entry("ollama/qwen3:14b") == ("ollama", "qwen3:14b")
    with pytest.raises(ValueError):
        split_entry("qwen3:14b")


def write_cfg(tmp_path: Path, **changes: object) -> Path:
    data = yaml.safe_load((CONFIG_DIR / "providers.yaml").read_text())
    data["llm"]["pools"].update(changes)
    p = tmp_path / "providers.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


@pytest.mark.parametrize("entries,message", [
    (["gemini-3.5-flash-lite"], "provider/model"),
    (["openai/gpt"], "unknown provider"),
    (["ollama/llama9"], "no entry under llm.ollama.models"),
])
def test_bad_pool_entries_are_rejected(tmp_path: Path, entries: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_providers_config(write_cfg(tmp_path, cheap=entries))


def test_pools_leave_out_providers_that_are_not_set_up(db: Database) -> None:
    pcfg = load_providers_config()
    m = metering(db)
    providers = build_llm_providers(Settings(gemini_api_key=""), pcfg, m)  # no Gemini key
    assert set(providers) == {"ollama"}
    entries = pool_entries(pcfg.llm.pools["local_first"], providers, pcfg)
    assert [e.label for e in entries] == ["ollama/gemma3:12b"]
    with pytest.raises(LLMError, match="No usable model"):
        build_pools(providers, pcfg, m, stages=("s1a",))  # s1a uses the Gemini-only 'cheap' pool


def test_pool_moves_on_when_a_model_keeps_failing(db: Database) -> None:
    """An overloaded model (503s / timeouts after the retries) hands over to the next entry."""
    busy = Fake("gemini", [TransientError("503")] * (ModelPool.MAX_TRANSIENT_RETRIES + 1))
    other = Fake("gemini2", ['{"city":"X"}'])
    pool = ModelPool([PoolEntry(busy, "a", [Limit("day", 10)], 60), PoolEntry(other, "b", [Limit("day", 10)], 60)],
                     metering(db))
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=CallContext()).provider == "gemini2"
    lone = ModelPool([PoolEntry(Fake("g", [TransientError("503")] * 9), "a", [], 60)], metering(db))
    with pytest.raises(TransientError):
        lone.complete(system="s", user="u", schema_cls=Small, ctx=CallContext())


def test_a_failing_model_rests_so_later_requests_start_on_one_that_works(db: Database) -> None:
    """Each attempt at an overloaded free model may cost quota: after it fails, skip it for a while."""
    busy = Fake("gemini", [TransientError("503")] * 2 + ['{"city":"B"}'])
    other = Fake("gemini2", ['{"city":"X"}', '{"city":"Y"}'])
    pool = ModelPool([PoolEntry(busy, "a", [Limit("day", 10)], 60), PoolEntry(other, "b", [Limit("day", 10)], 60)],
                     metering(db))
    now = [0.0]
    pool.clock = lambda: now[0]
    pool.metering.limiter.penalise = lambda *a: None  # no real waiting in the test
    ctx = CallContext()
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=ctx).output.city == "X"
    assert busy.calls == ModelPool.MAX_TRANSIENT_RETRIES + 1
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=ctx).output.city == "Y"
    assert busy.calls == 2  # resting: not tried
    now[0] = ModelPool.COOLDOWN_S + 1  # rested: 'a' is first again
    assert pool.complete(system="s", user="u", schema_cls=Small, ctx=ctx).output.city == "B"
