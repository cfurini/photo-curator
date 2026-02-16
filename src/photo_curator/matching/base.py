"""Abstract base for file-matching strategies."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from photo_curator.models import FileRecord, MatchResult


class MatchStrategy(abc.ABC):
    """Base class for all matching strategies.

    Each strategy defines:
      - How to build a destination index from file paths
      - How to compare source files against that index
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier used by --match-strategy CLI flag."""
        ...

    @abc.abstractmethod
    def build_index(self, destination: Path) -> Any:
        """Scan the destination directory and build a strategy-specific index."""
        ...

    @abc.abstractmethod
    def match_all(
        self,
        source_files: list[FileRecord],
        dest_index: Any,
    ) -> list[MatchResult]:
        """Compare every source file against the destination index.

        Returns one MatchResult per source file.
        """
        ...
