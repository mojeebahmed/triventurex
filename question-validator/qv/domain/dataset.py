"""Models describing imports and differences between dataset versions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from qv.domain.structural import StructuralReport


class ChangedQuestion(BaseModel):
    """A question whose content differs between two versions."""

    model_config = ConfigDict(frozen=True)

    ext_id: str
    fields: tuple[str, ...] = Field(description="Columns whose (trimmed) value changed")


class DatasetDiff(BaseModel):
    """Differences between two versions, keyed by the CSV id (ids are permanent)."""

    model_config = ConfigDict(frozen=True)

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[ChangedQuestion, ...] = ()
    unchanged_count: int = 0
    duplicate_ids: tuple[str, ...] = Field(
        (), description="Ids that occur more than once in either version; compared by first occurrence"
    )

    @property
    def is_empty(self) -> bool:
        """True when nothing was added, removed or changed."""
        return not (self.added or self.removed or self.changed)


class ImportResult(BaseModel):
    """What `import_dataset` did."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str
    dataset_id: int
    version_id: int
    version_no: int
    created: bool = Field(description="False when the file is identical to the latest version")
    file_sha256: str
    report: StructuralReport
    diff: DatasetDiff | None = Field(None, description="Diff against the previous version, if any")
