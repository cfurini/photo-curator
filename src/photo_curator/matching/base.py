"""Abstract base for file-matching strategies."""

from __future__ import annotations

import abc
from typing import Any

from photo_curator.models import FileRecord, MatchResult


class MatchStrategy(abc.ABC):
    """Base class for all matching strategies.

    Each strategy defines how to compare source files against a
    destination index to detect duplicates.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier used by --match-strategy CLI flag."""
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
