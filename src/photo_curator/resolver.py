"""Conflict resolution: decide what happens to each file based on match results."""

from __future__ import annotations

import logging
from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.models import Action, FileAction, FileRecord, MatchResult

logger = logging.getLogger(__name__)


class Resolver:
    """Decides what to do with each file based on match results.

    v0.1 rules:
      - No match (new file):  STORE in destination YYYY/MM (or NO_DATE)
      - Match found (dup):    DISCARD_SOURCE (keep the archive copy)
      - Same resolved path:   SKIP (recursive mode, already in place)
    """

    def __init__(self, config: CuratorConfig) -> None:
        self.config = config

    def resolve(self, match_results: list[MatchResult]) -> list[FileAction]:
        actions: list[FileAction] = []

        for mr in match_results:
            source = mr.source

            if mr.is_duplicate:
                dest_path = self.config.discard / source.path.name
                actions.append(FileAction(
                    source=source,
                    action=Action.DISCARD_SOURCE,
                    destination_path=dest_path,
                    reason=f"Duplicate of {mr.matched_destination}",
                ))
            else:
                target_dir = self._target_dir(source)
                target_path = target_dir / source.path.name

                # Recursive mode: skip if already in correct location
                if target_path.resolve() == source.path.resolve():
                    actions.append(FileAction(
                        source=source,
                        action=Action.SKIP,
                        destination_path=target_path,
                        reason="Already in correct location",
                    ))
                else:
                    action = Action.NO_DATE if source.year is None else Action.STORE
                    reason = "No EXIF date" if source.year is None else "New file"
                    actions.append(FileAction(
                        source=source,
                        action=action,
                        destination_path=target_path,
                        reason=reason,
                    ))

        return actions

    def _target_dir(self, record: FileRecord) -> Path:
        if record.year and record.month:
            return self.config.destination / record.year / record.month
        return self.config.destination / "NoDate"
