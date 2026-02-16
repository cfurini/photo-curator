"""Core data types used throughout the photo-curator pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class FileCategory(enum.Enum):
    PHOTO = "photo"
    VIDEO = "video"
    SIDECAR = "sidecar"
    UNKNOWN = "unknown"


class Action(enum.Enum):
    """What the pipeline will do with a file."""

    STORE = "store"  # Place in destination YYYY/MM
    DISCARD_SOURCE = "discard_source"  # Source is the loser, send to discard
    DISCARD_EXISTING = "discard_existing"  # Existing archive copy is the loser
    SKIP = "skip"  # Already in correct location (recursive mode)
    NO_DATE = "no_date"  # Store in destination/NoDate/


@dataclass(frozen=True)
class FileRecord:
    """A discovered file with its metadata."""

    path: Path
    category: FileCategory
    size: int  # bytes
    extension: str  # lowercased, includes dot
    year: Optional[str] = None  # YYYY from EXIF
    month: Optional[str] = None  # MM from EXIF
    parent_media: Optional[Path] = None  # For sidecars: their media file


@dataclass(frozen=True)
class MatchResult:
    """Result of comparing a source file against the destination archive."""

    source: FileRecord
    matched_destination: Optional[Path]  # None = new file
    is_duplicate: bool


@dataclass
class FileAction:
    """A planned action for one file (and its sidecars)."""

    source: FileRecord
    action: Action
    destination_path: Path
    sidecars: list[FileRecord] = field(default_factory=list)
    reason: str = ""


@dataclass
class OperationRecord:
    """One file operation recorded for the JSON manifest."""

    action: str  # "store", "discard", "no_date"
    source: str  # absolute path as string
    destination: str  # absolute path as string
    source_size: int
    matched_existing: Optional[str] = None
    sidecars: list[dict[str, str]] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Summary counters for a completed pipeline run."""

    files_scanned: int = 0
    files_stored: int = 0
    files_discarded: int = 0
    files_skipped: int = 0
    files_no_date: int = 0
    errors: int = 0
    dry_run: bool = False
    manifest_path: Optional[Path] = None
