"""Settings (environment / .env) and edition profiles (config/profiles/*.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
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
