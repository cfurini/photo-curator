"""Match files by identical filename (case-insensitive) and file size."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from photo_curator.matching.base import MatchStrategy
from photo_curator.models import FileRecord, MatchResult
from photo_curator.scanner import walk_destination

# Type alias for the index this strategy expects
FilenameSizeIndex = dict[tuple[str, int], list[Path]]


class FilenameSizeStrategy(MatchStrategy):
    """A file is a duplicate if an identical filename (case-insensitive)
    with the same byte size already exists in the destination archive."""

    @property
    def name(self) -> str:
        return "filename-size"

    def build_index(self, destination: Path) -> FilenameSizeIndex:
        """Index destination by (filename_lower, size)."""
        index: dict[tuple[str, int], list[Path]] = defaultdict(list)
        for file_path, size in walk_destination(destination):
            key = (file_path.name.lower(), size)
            index[key].append(file_path)
        return dict(index)

    def match_all(
        self,
        source_files: list[FileRecord],
        dest_index: FilenameSizeIndex,
    ) -> list[MatchResult]:
        results: list[MatchResult] = []

        for record in source_files:
            key = (record.path.name.lower(), record.size)
            matches = dest_index.get(key, [])

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
                # Track this source file so later source duplicates are caught
                if key not in dest_index:
                    dest_index[key] = []
                dest_index[key].append(record.path)

        return results
