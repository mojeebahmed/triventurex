"""Metering: free-tier quota ledger, per-minute rate limiting and the API call log.

Nothing here spends money: a call is only allowed when the ledger says the
provider's free quota (minus a safety reserve) still has room. Usage is written
in its own short transaction, so it survives even when the caller's work fails.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from qv.db.models import ApiCall, QuotaUsage
from qv.db.session import Database


class QuotaExhausted(RuntimeError):
    """No free quota is left for any provider/model that could do the work."""


@dataclass(frozen=True)
class Limit:
    """A quota: at most `amount` units per `period` ('day' or 'month') in `timezone`."""

    period: str
    amount: float
    timezone: str = "UTC"


def period_key(period: str, timezone: str = "UTC", now: datetime | None = None) -> str:
    """Key of the current period, e.g. '2026-11-15' (day) or '2026-11' (month)."""
    now = (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone))
    if period == "day":
        return now.strftime("%Y-%m-%d")
    if period == "month":
        return now.strftime("%Y-%m")
    raise ValueError(f"unknown period {period!r}")


class QuotaLedger:
    """Tracks free-tier usage per (provider, model, period) in the database."""

    def __init__(self, db: Database, *, reserve_fraction: float = 0.05,
                 clock: Callable[[], datetime] | None = None) -> None:
        """`reserve_fraction` of every limit is never used (safety margin)."""
        self.db = db
        self.reserve_fraction = reserve_fraction
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()

    def _row(self, s, provider: str, model: str, limit: Limit) -> QuotaUsage:  # noqa: ANN001
        key = period_key(limit.period, limit.timezone, self._clock())
        row = s.scalar(select(QuotaUsage).where(
            QuotaUsage.provider == provider, QuotaUsage.model == model,
            QuotaUsage.period == limit.period, QuotaUsage.period_key == key))
        if row is None:
            row = QuotaUsage(provider=provider, model=model, period=limit.period, period_key=key, used=0.0)
            s.add(row)
            s.flush()
        return row

    def usable(self, limit: Limit) -> float:
        """The part of a limit we allow ourselves to use."""
        return limit.amount * (1 - self.reserve_fraction)

    def remaining(self, provider: str, model: str, limit: Limit) -> float:
        """Units left in the current period (0 when marked exhausted by the provider)."""
        with self.db.session() as s:
            row = self._row(s, provider, model, limit)
            return 0.0 if row.exhausted else max(0.0, self.usable(limit) - row.used)

    def can_spend(self, provider: str, model: str, amount: float, limits: list[Limit]) -> bool:
        """True when `amount` fits in every limit."""
        return all(self.remaining(provider, model, lim) >= amount for lim in limits)

    def record(self, provider: str, model: str, amount: float, limits: list[Limit]) -> None:
        """Add `amount` to the current period of every limit."""
        with self._lock, self.db.session() as s:
            for lim in limits:
                self._row(s, provider, model, lim).used += amount

    def mark_exhausted(self, provider: str, model: str, limits: list[Limit]) -> None:
        """The provider said the quota is used up: block it for the rest of the period."""
        with self._lock, self.db.session() as s:
            for lim in limits:
                self._row(s, provider, model, lim).exhausted = True

    def snapshot(self) -> list[QuotaUsage]:
        """All ledger rows, newest periods first (for `qv quota`)."""
        with self.db.session() as s:
            return list(s.scalars(select(QuotaUsage).order_by(
                QuotaUsage.period_key.desc(), QuotaUsage.provider, QuotaUsage.model)))


class RateLimiter:
    """Sliding-window limiter: at most `rpm` calls per 60 s per key. Blocks until a slot is free."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        """`clock`/`sleep` are injectable for tests."""
        self._clock = clock
        self._sleep = sleep
        self._calls: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def wait(self, key: str, rpm: int) -> float:
        """Wait until a call for `key` is allowed; returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                q = self._calls.setdefault(key, deque())
                while q and now - q[0] >= 60:
                    q.popleft()
                if len(q) < rpm:
                    q.append(now)
                    return waited
                delay = 60 - (now - q[0]) + 0.05
            self._sleep(delay)
            waited += delay

    def penalise(self, key: str, seconds: float) -> None:
        """Block `key` for `seconds` (after a provider's per-minute 429)."""
        self._sleep(seconds)


@dataclass
class CallContext:
    """Who a call is made for (written to the API call log)."""

    run_id: int | None = None
    question_id: int | None = None
    stage: str | None = None


class UsageRecorder:
    """Writes one ApiCall row per external call."""

    def __init__(self, db: Database) -> None:
        """Record into `db`."""
        self.db = db

    def record(self, *, provider: str, kind: str, status: str, ctx: CallContext | None = None,
               model: str = "", http_status: int | None = None, input_tokens: int = 0, output_tokens: int = 0,
               thinking_tokens: int = 0, credits: float = 0.0, cost_usd: float = 0.0, latency_ms: int = 0,
               response_id: str | None = None, error: str | None = None) -> int:
        """Store a call and return its id."""
        ctx = ctx or CallContext()
        with self.db.session() as s:
            row = ApiCall(run_id=ctx.run_id, question_id=ctx.question_id, stage=ctx.stage, provider=provider,
                          model=model, kind=kind, status=status, http_status=http_status,
                          input_tokens=input_tokens, output_tokens=output_tokens, thinking_tokens=thinking_tokens,
                          credits=credits, cost_usd=cost_usd, latency_ms=latency_ms, response_id=response_id,
                          error=(error or None) and error[:2000])
            s.add(row)
            s.flush()
            return row.id


@dataclass
class Metering:
    """Everything a provider needs to stay inside free limits and log its usage."""

    ledger: QuotaLedger
    limiter: RateLimiter
    recorder: UsageRecorder

    @classmethod
    def for_db(cls, db: Database, reserve_fraction: float = 0.05) -> Metering:
        """Default metering backed by `db`."""
        return cls(QuotaLedger(db, reserve_fraction=reserve_fraction), RateLimiter(), UsageRecorder(db))
