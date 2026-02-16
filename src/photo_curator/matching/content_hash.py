"""Match files by SHA256 hash of file content. Catches renamed duplicates."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from photo_curator.matching.base import MatchStrategy
from photo_curator.models import FileRecord, MatchResult
from photo_curator.scanner import walk_destination

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536  # 64 KB

# Type alias for the index this strategy expects
ContentHashIndex = dict[str, list[Path]]


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file, reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


class ContentHashStrategy(MatchStrategy):
    """A file is a duplicate if a file with identical SHA256 content hash
    already exists in the destination archive, regardless of filename."""

    @property
    def name(self) -> str:
        return "content-hash"

    def build_index(self, destination: Path) -> ContentHashIndex:
        """Index destination by SHA256 hash of file content."""
        index: dict[str, list[Path]] = defaultdict(list)
        dest_files = walk_destination(destination)
        total = len(dest_files)

        for i, (file_path, _size) in enumerate(dest_files):
            if i % 1000 == 0 and i > 0:
                logger.info(f"  Hashing destination: {i}/{total}")
            try:
                digest = sha256_file(file_path)
                index[digest].append(file_path)
            except OSError as e:
                logger.warning(f"Cannot hash {file_path}: {e}")

        return dict(index)

    def match_all(
        self,
        source_files: list[FileRecord],
        dest_index: ContentHashIndex,
    ) -> list[MatchResult]:
        results: list[MatchResult] = []
        total = len(source_files)

        for i, record in enumerate(source_files):
            if i % 1000 == 0 and i > 0:
                logger.info(f"  Hashing source: {i}/{total}")
            try:
                digest = sha256_file(record.path)
            except OSError as e:
                logger.warning(f"Cannot hash {record.path}: {e}")
                results.append(MatchResult(
                    source=record,
                    matched_destination=None,
                    is_duplicate=False,
                ))
                continue

            matches = dest_index.get(digest, [])

            if matches:
                results.append(MatchResult(
                    source=record,
                    matched_destination=matches[0],
                    is_duplicate=True,
                ))
            else:
                results.append(MatchResult(
                    source=record,
                    matched_destination=None,
                    is_duplicate=False,
                ))

        return results
