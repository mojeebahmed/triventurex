"""Settings (environment / .env) and edition profiles (config/profiles/*.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROFILES_DIR = CONFIG_DIR / "profiles"
DEFAULT_PROFILE = "general"


class Settings(BaseSettings):
    """Process-wide settings. Read from environment variables prefixed `QV_` and `.env`."""

    model_config = SettingsConfigDict(env_prefix="QV_", env_file=PROJECT_ROOT / ".env", extra="ignore")

    data_dir: Path = PROJECT_ROOT / "data"
    db_url: str | None = None
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY", repr=False)
    tavily_api_key: str = Field("", validation_alias="TAVILY_API_KEY", repr=False)
    exa_api_key: str = Field("", validation_alias="EXA_API_KEY", repr=False)
    contact: str = Field("", description="URL or email sent only to Wikimedia, whose API requires contact details")

    @field_validator("data_dir")
    @classmethod
    def _absolute_data_dir(cls, value: Path) -> Path:
        """A relative data directory is relative to the project folder, not the current directory."""
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL; defaults to `<data_dir>/validation.db`."""
        return self.db_url or f"sqlite:///{self.data_dir / 'validation.db'}"

    @property
    def exports_dir(self) -> Path:
        """Where exported files are written."""
        return self.data_dir / "exports"


class StructuralRules(BaseModel):
    """Profile-controlled settings for the structural checks."""

    model_config = ConfigDict(extra="forbid")

    allowed_types: list[str] = Field(default_factory=lambda: ["multi", "open"])
    allowed_difficulties: list[str] = Field(
        default_factory=lambda: ["easy", "hard"],
        description="The game accepts easy|hard; the original spec also mentions medium.",
    )
    min_multi_options: int = 2
    near_duplicate_threshold: float = Field(90.0, ge=0, le=100, description="Question wording similarity")
    near_duplicate_answer_threshold: float = Field(
        95.0, ge=0, le=100, description="Key similarity needed as well (filters template questions)"
    )
    warn_fewer_than_four_options: bool = True


class Frame(BaseModel):
    """A declared frame of reference (METHODOLOGY.md §1.7, §10)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    applies_to: list[str] = Field(default_factory=list)
    authorities: list[str] = Field(default_factory=list)
    confirmed: bool = Field(False, description="True once the edition's reviewer has confirmed the frame")


class Profile(BaseModel):
    """An edition profile: audience, frame, conventions and rule settings."""

    model_config = ConfigDict(extra="forbid")

    edition: str
    audience: str = "general"
    frame: Frame | None = None
    conventions: dict[str, str] = Field(default_factory=dict)
    direct_sources: list[str] = Field(default_factory=list)
    specialist_for: list[str] = Field(default_factory=list)
    structural: StructuralRules = Field(default_factory=StructuralRules)


def available_profiles(directory: Path = PROFILES_DIR) -> list[str]:
    """Names of all profiles in `directory`."""
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_profile(name: str = DEFAULT_PROFILE, directory: Path = PROFILES_DIR) -> Profile:
    """Load and validate one profile by name; raises FileNotFoundError / ValidationError."""
    path = directory / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"No profile '{name}' in {directory} (available: {', '.join(available_profiles(directory))})"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "frame" in data and data["frame"] in (None, "none"):
        data["frame"] = None
    return Profile.model_validate(data)


# ---------------------------------------------------------------------------
# Providers and research depth (config/providers.yaml, config/research.yaml)
# ---------------------------------------------------------------------------

class ModelLimits(BaseModel):
    """Free-tier limits we allow ourselves for one model."""

    model_config = ConfigDict(extra="forbid")

    rpm: int = Field(gt=0)
    rpd: int = Field(gt=0)


class GeminiConfig(BaseModel):
    """Gemini models, limits and pools."""

    model_config = ConfigDict(extra="forbid")

    daily_reset_timezone: str = "America/Los_Angeles"
    models: dict[str, ModelLimits]
    pools: dict[str, list[str]]


class LLMConfig(BaseModel):
    """All LLM providers."""

    model_config = ConfigDict(extra="forbid")

    gemini: GeminiConfig


class TavilyConfig(BaseModel):
    """Tavily free tier."""

    model_config = ConfigDict(extra="forbid")

    credits_per_month: float
    credits_per_search: float = 1
    rpm: int = 60


class ExaConfig(BaseModel):
    """Exa free credit."""

    model_config = ConfigDict(extra="forbid")

    usd_credit_per_month: float
    est_usd_per_search: float = 0.005
    rpm: int = 30


class ParallelConfig(BaseModel):
    """Parallel free MCP search (no published limits, so we cap ourselves)."""

    model_config = ConfigDict(extra="forbid")

    daily_soft_cap: int = Field(300, gt=0)
    rpm: int = 20


class PoliteConfig(BaseModel):
    """A free source without quota, limited only by politeness."""

    model_config = ConfigDict(extra="forbid")

    rpm: int = 30


class SearchConfig(BaseModel):
    """Search providers."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    tavily: TavilyConfig
    exa: ExaConfig
    wikipedia: PoliteConfig = Field(default_factory=PoliteConfig)
    alislam: PoliteConfig = Field(default_factory=lambda: PoliteConfig(rpm=10))


class FetchConfig(BaseModel):
    """Page fetching."""

    model_config = ConfigDict(extra="forbid")

    rpm_per_domain: int = 10
    timeout_s: float = 20
    max_bytes: int = 3_000_000


class ProvidersConfig(BaseModel):
    """config/providers.yaml"""

    model_config = ConfigDict(extra="forbid")

    reserve_fraction: float = Field(0.05, ge=0, lt=1)
    llm: LLMConfig
    stage_pools: dict[str, str]
    search: SearchConfig
    fetch: FetchConfig = Field(default_factory=FetchConfig)

    def pool_for(self, stage: str) -> list[str]:
        """Model ids for a stage, in fallback order."""
        return self.llm.gemini.pools[self.stage_pools[stage]]


class ResearchConfig(BaseModel):
    """config/research.yaml"""

    model_config = ConfigDict(extra="forbid")

    max_web_queries_per_question: int = Field(4, ge=0)
    results_per_query: int = Field(5, ge=1)
    max_documents_per_question: int = Field(5, ge=0)
    max_note_documents_per_question: int = Field(2, ge=0)
    wikipedia_results: int = Field(1, ge=0)
    alislam_search_results: int = Field(2, ge=0)
    search_cache_days: int = Field(60, ge=0)
    s3_window_chars: int = Field(40000, ge=2000)
    s3_window_overlap_chars: int = Field(1000, ge=0)
    s3_max_windows: int = Field(2, ge=1)


def load_providers_config(path: Path = CONFIG_DIR / "providers.yaml") -> ProvidersConfig:
    """Load and validate config/providers.yaml."""
    cfg = ProvidersConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    for pool, models in cfg.llm.gemini.pools.items():
        unknown = [m for m in models if m not in cfg.llm.gemini.models]
        if unknown:
            raise ValueError(f"Pool '{pool}' uses models without limits: {unknown}")
    for stage, pool in cfg.stage_pools.items():
        if pool not in cfg.llm.gemini.pools:
            raise ValueError(f"Stage '{stage}' uses unknown pool '{pool}'")
    return cfg


def load_research_config(path: Path = CONFIG_DIR / "research.yaml") -> ResearchConfig:
    """Load and validate config/research.yaml."""
    return ResearchConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
