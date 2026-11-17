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
    """Gemini models and their free-tier limits."""

    model_config = ConfigDict(extra="forbid")

    daily_reset_timezone: str = "America/Los_Angeles"
    models: dict[str, ModelLimits]


class OllamaModel(BaseModel):
    """One local model: no quota, only speed and context size."""

    model_config = ConfigDict(extra="forbid")

    rpm: int = Field(60, gt=0)
    num_ctx: int = Field(24576, ge=2048, description="Must hold the whole prompt (Ollama cuts longer ones)")
    think: bool = Field(False, description="Reasoning mode for models that have one (e.g. qwen3)")
    temperature: float = 0.0

    def options(self) -> dict:
        """Request options for OllamaProvider."""
        return {"num_ctx": self.num_ctx, "think": self.think, "temperature": self.temperature}


class OllamaConfig(BaseModel):
    """Local models served by Ollama on this machine ($0, no daily limit)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:11434"
    timeout_s: float = Field(900, gt=0)
    models: dict[str, OllamaModel] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """All LLM providers and the pools built from them."""

    model_config = ConfigDict(extra="forbid")

    gemini: GeminiConfig
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    pools: dict[str, list[str]] = Field(description="Pool name → `provider/model` entries in fallback order")


def split_entry(entry: str) -> tuple[str, str]:
    """`ollama/qwen3:14b` → ('ollama', 'qwen3:14b'). Split on the first slash only."""
    provider, sep, model = entry.partition("/")
    if not sep or not model:
        raise ValueError(f"Pool entry '{entry}' must be written as provider/model")
    return provider, model


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


class SitemapSiteConfig(BaseModel):
    """A site searched through the words in its article URLs (its own search page needs a browser)."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(description="used when an edition's frame lists this domain as an authority")
    sitemap: str
    include: str = Field("post-sitemap", description="only sub-sitemaps whose URL contains this")
    refresh_days: float = Field(7, gt=0)
    rpm: int = 10


class SearchConfig(BaseModel):
    """Search providers."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    tavily: TavilyConfig
    exa: ExaConfig
    wikipedia: PoliteConfig = Field(default_factory=PoliteConfig)
    alislam: PoliteConfig = Field(default_factory=lambda: PoliteConfig(rpm=10))
    sitemaps: dict[str, SitemapSiteConfig] = Field(default_factory=dict)


class FetchConfig(BaseModel):
    """Page fetching."""

    model_config = ConfigDict(extra="forbid")

    rpm_per_domain: int = 10
    timeout_s: float = 20
    max_bytes: int = 3_000_000
    max_pdf_bytes: int = Field(20_000_000, ge=0, description="web PDFs larger than this are not read")
    max_pdf_pages: int = Field(400, ge=1, description="pages read from one web PDF")
    pdf_min_quality: float = Field(0.85, ge=0, le=1, description="page text quality below this → needs OCR")


class ProvidersConfig(BaseModel):
    """config/providers.yaml"""

    model_config = ConfigDict(extra="forbid")

    reserve_fraction: float = Field(0.05, ge=0, lt=1)
    llm: LLMConfig
    stage_pools: dict[str, str]
    search: SearchConfig
    fetch: FetchConfig = Field(default_factory=FetchConfig)

    def pool_for(self, stage: str) -> list[str]:
        """`provider/model` entries for a stage, in fallback order."""
        return self.llm.pools[self.stage_pools[stage]]


class ResearchConfig(BaseModel):
    """config/research.yaml"""

    model_config = ConfigDict(extra="forbid")

    max_web_queries_per_question: int = Field(4, ge=0)
    results_per_query: int = Field(5, ge=1)
    max_documents_per_question: int = Field(5, ge=0)
    max_note_documents_per_question: int = Field(2, ge=0)
    wikipedia_results: int = Field(1, ge=0)
    alislam_search_results: int = Field(2, ge=0)
    site_search_results: int = Field(2, ge=0, description="per sitemap-searched frame site (e.g. alhakam.org)")
    library_pages_per_question: int = Field(2, ge=0, description="book pages (config/library.yaml) read per question")
    search_cache_days: int = Field(60, ge=0)
    s3_window_chars: int = Field(40000, ge=2000)
    s3_window_overlap_chars: int = Field(1000, ge=0)
    s3_max_windows: int = Field(2, ge=1)
    audit_sample_percent: float = Field(3.0, ge=0, le=100, description="auto_ok questions sent to review anyway")
    batch_size: int = Field(25, ge=1, description="most questions in one `qv next` batch")
    # KB phase 3 — stored pages first
    stored_pages_per_question: int = Field(2, ge=0, description="stored pages (knowledge index) read per question")
    stored_results_per_query: int = Field(10, ge=1, description="index results looked at per blind query")
    stored_max_age_days: int = Field(365, ge=0, description="time-sensitive questions skip stored pages older than this")
    stored_first_skip_web: bool = Field(False, description="skip the web searches when enough stored pages qualify")
    stored_skip_web_min: int = Field(2, ge=1, description="stored pages needed before web searches are skipped")
    pdf_pages_per_document: int = Field(1, ge=1, description="best pages of a web PDF read per question")


def load_providers_config(path: Path = CONFIG_DIR / "providers.yaml") -> ProvidersConfig:
    """Load and validate config/providers.yaml."""
    cfg = ProvidersConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    known = {"gemini": cfg.llm.gemini.models, "ollama": cfg.llm.ollama.models}
    for pool, entries in cfg.llm.pools.items():
        if not entries:
            raise ValueError(f"Pool '{pool}' is empty")
        for entry in entries:
            provider, model = split_entry(entry)
            if provider not in known:
                raise ValueError(f"Pool '{pool}': unknown provider '{provider}' in '{entry}'")
            if model not in known[provider]:
                raise ValueError(f"Pool '{pool}': '{entry}' has no entry under llm.{provider}.models")
    for stage, pool in cfg.stage_pools.items():
        if pool not in cfg.llm.pools:
            raise ValueError(f"Stage '{stage}' uses unknown pool '{pool}'")
    return cfg


def load_research_config(path: Path = CONFIG_DIR / "research.yaml") -> ResearchConfig:
    """Load and validate config/research.yaml."""
    return ResearchConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
