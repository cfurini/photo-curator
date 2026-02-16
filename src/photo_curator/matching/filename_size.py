"""Match files by identical filename (case-insensitive) and file size."""

from __future__ import annotations

from pathlib import Path

from photo_curator.matching.base import MatchStrategy
from photo_curator.models import FileRecord, MatchResult

# Type alias for the index this strategy expects
FilenameSizeIndex = dict[tuple[str, int], list[Path]]


class FilenameSizeStrategy(MatchStrategy):
    """v0.1 strategy: a file is a duplicate if an identical filename (case-insensitive)
    with the same byte size already exists in the destination archive."""

    @property
    def name(self) -> str:
        return "filename-size"

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

        return results
