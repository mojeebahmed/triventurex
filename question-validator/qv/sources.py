"""Source registry: tier per domain and page kind (config/sources.yaml, METHODOLOGY.md §5)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from qv.config import CONFIG_DIR, Profile
from qv.providers.search.base import domain_of

TIER_ORDER = ("P", "S", "T", "X")  # best first

#: Page kinds (S3) that cap a page's tier; others leave the registry tier unchanged.
PAGE_KIND_CAP: dict[str, str] = {
    "quiz_or_trivia": "X",
    "listicle_or_content_farm": "X",
    "forum_or_social": "X",
    "machine_generated_suspected": "X",
    "encyclopedia_wiki": "T",
    "educational": "T",
    "news": "S",
}


def worse(a: str, b: str) -> str:
    """The lower of two tiers (P > S > T > X)."""
    return max(a, b, key=TIER_ORDER.index)


class Registry(BaseModel):
    """Domain → default tier."""

    model_config = ConfigDict(extra="forbid")

    version: int
    default_tier: str = Field("T", pattern="^[PSTX]$")
    suffix_tiers: dict[str, str] = Field(default_factory=dict)
    domains: dict[str, str] = Field(default_factory=dict)
    #: Domains not fetched for now (the person marked them "needs special access"); subdomains included.
    skip_domains: list[str] = Field(default_factory=list)

    def tier(self, url_or_domain: str) -> str:
        """Registry tier for a URL or domain (parent domains and suffixes are inherited)."""
        host = _host(url_or_domain)
        parts = host.split(".")
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            if candidate in self.domains:
                return self.domains[candidate]
        for suffix, tier in sorted(self.suffix_tiers.items(), key=lambda kv: -len(kv[0])):
            if host.endswith(suffix):
                return tier
        return self.default_tier

    def is_skipped(self, url_or_domain: str) -> bool:
        """True when the domain (or a parent) is in `skip_domains`."""
        host = _host(url_or_domain)
        return any(host == d or host.endswith("." + d) for d in self.skip_domains)

    def is_excluded(self, url: str) -> bool:
        """True for tier-X and skipped domains (dropped before fetching)."""
        return self.tier(url) == "X" or self.is_skipped(url)


def _host(url_or_domain: str) -> str:
    """Host of a URL, or a bare domain, lower case without www."""
    return domain_of(url_or_domain) if "/" in url_or_domain else url_or_domain.lower().removeprefix("www.")


def effective_tier(registry_tier: str, page_kind: str | None) -> str:
    """Registry tier lowered by what the page turned out to be (never raised)."""
    cap = PAGE_KIND_CAP.get(page_kind or "")
    return worse(registry_tier, cap) if cap else registry_tier


def is_frame_authority(url: str, profile: Profile) -> bool:
    """True when the URL's domain is one of the profile frame's authority domains."""
    if profile.frame is None:
        return False
    host = domain_of(url)
    for auth in profile.frame.authorities:
        auth = auth.lower().removeprefix("www.")
        if "." in auth and " " not in auth and (host == auth or host.endswith("." + auth)):
            return True
    return False


def load_registry(path: Path = CONFIG_DIR / "sources.yaml") -> Registry:
    """Load and validate the registry."""
    reg = Registry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    bad = {d: t for d, t in {**reg.domains, **reg.suffix_tiers}.items() if t not in TIER_ORDER}
    if bad:
        raise ValueError(f"Unknown tiers in sources.yaml: {bad}")
    return reg
