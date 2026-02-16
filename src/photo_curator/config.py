"""Configuration constants and runtime config dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet

PHOTO_EXTENSIONS: FrozenSet[str] = frozenset({
    ".jpg", ".jpeg", ".cr2", ".cr3", ".heic", ".png",
    ".tiff", ".tif", ".gif", ".bmp", ".nef", ".arw",
    ".dng", ".orf", ".rw2",
})

VIDEO_EXTENSIONS: FrozenSet[str] = frozenset({
    ".mov", ".mp4", ".avi", ".mpeg", ".mpg",
    ".m4v", ".mkv", ".wmv", ".3gp",
})

SIDECAR_EXTENSIONS: FrozenSet[str] = frozenset({
    ".xmp", ".thm", ".aae",
})

MEDIA_EXTENSIONS: FrozenSet[str] = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
ALL_EXTENSIONS: FrozenSet[str] = MEDIA_EXTENSIONS | SIDECAR_EXTENSIONS

SKIP_FILENAMES: FrozenSet[str] = frozenset({
    "desktop.ini", "thumbs.db", ".ds_store",
    ".picasa.ini", "zbthumbnail.info",
})

SKIP_DIRNAMES: FrozenSet[str] = frozenset({
    ".picasaoriginals",
})

EXIF_DATE_FIELDS: list[str] = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
]

EXIFTOOL_TIMEOUT: int = 300  # seconds
DEFAULT_BATCH_SIZE: int = 500


@dataclass(frozen=True)
class CuratorConfig:
    """Immutable runtime configuration assembled from CLI args."""

    source: Path
    destination: Path
    discard: Path
    mode: str  # "copy" or "move"
    match_strategy: str  # "filename-size"
    dry_run: bool
    exiftool_batch_size: int
    verbose: bool
    log_dir: Path
