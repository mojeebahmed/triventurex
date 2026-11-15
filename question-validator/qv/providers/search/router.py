"""Search router: cache first, then free pools in order, never past a free quota."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from qv.db.models import SearchQuery
from qv.db.session import Database
from qv.providers.search.base import SearchError, SearchHit, SearchProvider, SearchQuotaError
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted


def normalise_query(query: str) -> str:
    """Cache key form of a query: lower-case, single spaces."""
    return re.sub(r"\s+", " ", query.strip().lower())


@dataclass
class Pool:
    """A search provider with its free limits and the cost of one search in quota units."""

    provider: SearchProvider
    limits: list[Limit]
    units_per_search: float
    rpm: int

    def __post_init__(self) -> None:
        """Last observed cost (Exa reports it per call)."""
        self.observed_units = self.units_per_search


@dataclass
class RoutedResult:
    """Hits and where they came from."""

    hits: list[SearchHit]
    provider: str
    cached: bool


class SearchRouter:
    """Answers a query from the cache or the first pool with free quota left."""

    def __init__(self, db: Database, pools: list[Pool], metering: Metering, *, cache_days: int = 60) -> None:
        """`pools` in the order they should be tried."""
        self.db = db
        self.pools = pools
        self.metering = metering
        self.cache_days = cache_days

    def _cached(self, query: str, max_results: int) -> RoutedResult | None:
        now = datetime.now(UTC)
        with self.db.session() as s:
            rows = s.scalars(select(SearchQuery).where(
                SearchQuery.query_norm == normalise_query(query),
                SearchQuery.params_hash == _params_hash(max_results),
                SearchQuery.provider.in_([p.provider.name for p in self.pools]),
            ).order_by(SearchQuery.fetched_at.desc()))
            for row in rows:
                expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
                if expires > now:
                    return RoutedResult([SearchHit.from_json(h) for h in row.results_json], row.provider, True)
        return None

    def _store(self, provider: str, query: str, max_results: int, hits: list[SearchHit]) -> None:
        with self.db.session() as s:
            key = (provider, normalise_query(query), _params_hash(max_results))
            row = s.scalar(select(SearchQuery).where(SearchQuery.provider == key[0],
                                                     SearchQuery.query_norm == key[1],
                                                     SearchQuery.params_hash == key[2]))
            now = datetime.now(UTC)
            if row is None:
                row = SearchQuery(provider=provider, query=query, query_norm=key[1], params_hash=key[2])
                s.add(row)
            row.results_json = [h.to_json() for h in hits]
            row.fetched_at = now
            row.expires_at = now + timedelta(days=self.cache_days)

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> RoutedResult:
        """Cached result, else the first pool with quota. Raises QuotaExhausted when none can search."""
        cached = self._cached(query, max_results)
        if cached is not None:
            return cached
        errors: list[str] = []
        all_quota = True
        for pool in self.pools:
            name = pool.provider.name
            if not self.metering.ledger.can_spend(name, "", pool.observed_units, pool.limits):
                errors.append(f"{name}: free quota used up")
                continue
            self.metering.limiter.wait(f"search:{name}", pool.rpm)
            try:
                hits = pool.provider.search(query, max_results=max_results, ctx=ctx, objective=objective)
            except SearchQuotaError as exc:
                self.metering.ledger.mark_exhausted(name, "", pool.limits)
                errors.append(str(exc))
                continue
            except SearchError as exc:
                all_quota = False
                errors.append(str(exc))
                continue
            units = getattr(pool.provider, "last_cost_usd", None) or pool.units_per_search
            pool.observed_units = max(units, pool.units_per_search)
            self.metering.ledger.record(name, "", units, pool.limits)
            self._store(name, query, max_results, hits)
            return RoutedResult(hits, name, False)
        if all_quota:
            raise QuotaExhausted("No search provider has free quota left: " + "; ".join(errors))
        raise SearchError("All search providers failed: " + "; ".join(errors))


def _params_hash(max_results: int) -> str:
    return hashlib.sha256(json.dumps({"max_results": max_results}).encode()).hexdigest()[:16]
