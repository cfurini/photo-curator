"""Recursive file discovery, sidecar mapping, and destination indexing."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from pathlib import Path

from photo_curator.config import (
    MEDIA_EXTENSIONS,
    PHOTO_EXTENSIONS,
    SIDECAR_EXTENSIONS,
    SKIP_DIRNAMES,
    SKIP_FILENAMES,
    VIDEO_EXTENSIONS,
    CuratorConfig,
)
from photo_curator.models import FileCategory, FileRecord

logger = logging.getLogger(__name__)


def _categorize(ext: str) -> FileCategory:
    if ext in PHOTO_EXTENSIONS:
        return FileCategory.PHOTO
    if ext in VIDEO_EXTENSIONS:
        return FileCategory.VIDEO
    if ext in SIDECAR_EXTENSIONS:
        return FileCategory.SIDECAR
    return FileCategory.UNKNOWN


class Scanner:
    def __init__(self, config: CuratorConfig) -> None:
        self.config = config

    def scan(self) -> tuple[list[FileRecord], dict[Path, list[FileRecord]]]:
        """Walk source directory.

        Returns:
            media_files: list of FileRecord for photos/videos
            sidecar_map: dict mapping media file Path -> list of sidecar FileRecords
        """
        media_files: list[FileRecord] = []
        all_sidecars: list[FileRecord] = []

        for root, dirs, files in os.walk(self.config.source):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRNAMES]

            root_path = Path(root)
            for filename in files:
                if filename.lower() in SKIP_FILENAMES:
                    continue

                file_path = root_path / filename
                ext = file_path.suffix.lower()

                if ext not in MEDIA_EXTENSIONS and ext not in SIDECAR_EXTENSIONS:
                    continue

                try:
                    stat = file_path.stat()
                except OSError as e:
                    logger.warning(f"Cannot stat {file_path}: {e}")
                    continue

                record = FileRecord(
                    path=file_path,
                    category=_categorize(ext),
                    size=stat.st_size,
                    extension=ext,
                )

                if ext in MEDIA_EXTENSIONS:
                    media_files.append(record)
                else:
                    all_sidecars.append(record)

        sidecar_map = self._map_sidecars(media_files, all_sidecars)
        return media_files, sidecar_map

    def _map_sidecars(
        self,
        media_files: list[FileRecord],
        sidecars: list[FileRecord],
    ) -> dict[Path, list[FileRecord]]:
        """Map sidecar files to their parent media file by stem + directory."""
        media_lookup: dict[tuple[Path, str], Path] = {}
        for mf in media_files:
            key = (mf.path.parent, mf.path.stem.lower())
            media_lookup[key] = mf.path

        result: dict[Path, list[FileRecord]] = defaultdict(list)
        for sc in sidecars:
            key = (sc.path.parent, sc.path.stem.lower())
            media_path = media_lookup.get(key)
            if media_path:
                enriched = FileRecord(
                    path=sc.path,
                    category=sc.category,
                    size=sc.size,
                    extension=sc.extension,
                    parent_media=media_path,
                )
                result[media_path].append(enriched)
            else:
                logger.debug(f"Orphan sidecar (no matching media): {sc.path}")

        return dict(result)

    def index_destination(self) -> dict[tuple[str, int], list[Path]]:
        """Build an index of the destination archive for matching.

        Returns:
            dict of (filename_lower, size) -> list[Path]
        """
        index: dict[tuple[str, int], list[Path]] = defaultdict(list)

        if not self.config.destination.exists():
            return dict(index)

        for root, dirs, files in os.walk(self.config.destination):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRNAMES]

            root_path = Path(root)
            for filename in files:
                file_path = root_path / filename
                ext = file_path.suffix.lower()
                if ext not in MEDIA_EXTENSIONS and ext not in SIDECAR_EXTENSIONS:
                    continue

                try:
                    stat = file_path.stat()
                    key = (filename.lower(), stat.st_size)
                    index[key].append(file_path)
                except OSError:
                    pass

        return dict(index)
