"""Free-quota ledger, rate limiter and call log."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from qv.db.models import ApiCall
from qv.db.session import Database
from qv.providers.usage import CallContext, Limit, QuotaLedger, RateLimiter, UsageRecorder, period_key


def test_period_keys_use_the_quota_timezone() -> None:
    # 07:30 UTC on the 16th is still the 15th in California (Gemini's reset time zone)
    now = datetime(2026, 11, 16, 7, 30, tzinfo=UTC)
    assert period_key("day", "America/Los_Angeles", now) == "2026-11-15"
    assert period_key("day", "UTC", now) == "2026-11-16"
    assert period_key("month", "UTC", now) == "2026-11"


def test_ledger_reserve_and_spending(db: Database) -> None:
    ledger = QuotaLedger(db, reserve_fraction=0.1)
    lim = [Limit("day", 10)]
    assert ledger.remaining("gemini", "m", lim[0]) == 9  # 10 % reserve
    for _ in range(8):
        ledger.record("gemini", "m", 1, lim)
    assert ledger.can_spend("gemini", "m", 1, lim)
    ledger.record("gemini", "m", 1, lim)
    assert not ledger.can_spend("gemini", "m", 1, lim)
    assert ledger.can_spend("gemini", "other", 1, lim)  # per model


def test_ledger_new_period_starts_fresh(db: Database) -> None:
    clock = {"now": datetime(2026, 11, 15, 12, tzinfo=UTC)}
    ledger = QuotaLedger(db, reserve_fraction=0, clock=lambda: clock["now"])
    lim = [Limit("day", 2, "UTC")]
    ledger.record("p", "", 2, lim)
    assert not ledger.can_spend("p", "", 1, lim)
    clock["now"] = datetime(2026, 11, 16, 0, 1, tzinfo=UTC)
    assert ledger.can_spend("p", "", 1, lim)


def test_mark_exhausted_blocks_until_next_period(db: Database) -> None:
    ledger = QuotaLedger(db, reserve_fraction=0)
    lim = [Limit("month", 1000)]
    ledger.mark_exhausted("tavily", "", lim)
    assert ledger.remaining("tavily", "", lim[0]) == 0


def test_rate_limiter_waits_for_a_free_slot() -> None:
    t = {"now": 0.0}
    slept: list[float] = []

    def sleep(d: float) -> None:
        slept.append(d)
        t["now"] += d

    rl = RateLimiter(clock=lambda: t["now"], sleep=sleep)
    for _ in range(3):
        assert rl.wait("k", 3) == 0
    waited = rl.wait("k", 3)
    assert waited > 59 and slept
    assert rl.wait("other", 3) == 0


def test_usage_recorder(db: Database) -> None:
    rec = UsageRecorder(db)
    rec.record(provider="gemini", kind="llm", status="ok", ctx=CallContext(stage="s1a"), model="m",
               input_tokens=10, output_tokens=5, credits=1, error="x" * 5000)
    with db.session() as s:
        row = s.scalar(select(ApiCall))
        assert (row.provider, row.stage, row.input_tokens, row.credits, row.cost_usd) == ("gemini", "s1a", 10, 1, 0)
        assert len(row.error) == 2000
