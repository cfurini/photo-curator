"""File copy/move operations with dry-run support and duplicate name resolution."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from photo_curator.config import CuratorConfig
from photo_curator.manifest import ManifestWriter
from photo_curator.models import Action, FileAction, OperationRecord, PipelineResult

logger = logging.getLogger(__name__)


def resolve_duplicate_name(target: Path) -> Path:
    """If target exists, append _001, _002, etc. until a free name is found."""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    for counter in range(1, 10000):
        candidate = parent / f"{stem}_{counter:03d}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many duplicates for {target}")


class Mover:
    def __init__(
        self,
        config: CuratorConfig,
        manifest: Optional[ManifestWriter] = None,
    ) -> None:
        self.config = config
        self.manifest = manifest

    def execute(
        self, actions: list[FileAction], result: PipelineResult,
    ) -> PipelineResult:
        for action in actions:
            try:
                self._execute_one(action, result)
            except Exception as e:
                logger.error(f"Error processing {action.source.path}: {e}")
                result.errors += 1
        return result

    def _execute_one(self, fa: FileAction, result: PipelineResult) -> None:
        if fa.action == Action.SKIP:
            logger.debug(f"SKIP: {fa.source.path} ({fa.reason})")
            result.files_skipped += 1
            return

        dest = resolve_duplicate_name(fa.destination_path)
        prefix = "[DRY-RUN] " if self.config.dry_run else ""

        if fa.action in (Action.STORE, Action.NO_DATE):
            self._transfer(fa.source.path, dest, prefix)
            sidecar_records: list[dict[str, str]] = []
            for sc in fa.sidecars:
                sc_dest = dest.parent / sc.path.name
                sc_dest = resolve_duplicate_name(sc_dest)
                self._transfer(sc.path, sc_dest, prefix)
                sidecar_records.append({
                    "source": str(sc.path),
                    "destination": str(sc_dest),
                })
            self._record_operation(fa, dest, sidecar_records)
            if fa.action == Action.NO_DATE:
                result.files_no_date += 1
            else:
                result.files_stored += 1

        elif fa.action == Action.DISCARD_SOURCE:
            self._transfer(fa.source.path, dest, prefix)
            sidecar_records = []
            for sc in fa.sidecars:
                sc_dest = self.config.discard / sc.path.name
                sc_dest = resolve_duplicate_name(sc_dest)
                self._transfer(sc.path, sc_dest, prefix)
                sidecar_records.append({
                    "source": str(sc.path),
                    "destination": str(sc_dest),
                })
            self._record_operation(fa, dest, sidecar_records)
            result.files_discarded += 1

    def _transfer(self, src: Path, dest: Path, prefix: str) -> None:
        """Copy or move a single file."""
        logger.info(f"{prefix}{self.config.mode.upper()}: {src} -> {dest}")

        if self.config.dry_run:
            return

        dest.parent.mkdir(parents=True, exist_ok=True)

        if self.config.mode == "move":
            shutil.move(str(src), str(dest))
        else:
            shutil.copy2(str(src), str(dest))

    def _record_operation(
        self,
        fa: FileAction,
        dest: Path,
        sidecar_records: list[dict[str, str]],
    ) -> None:
        """Record a completed operation in the manifest."""
        if self.manifest is None:
            return

        self.manifest.record(OperationRecord(
            action=fa.action.value,
            source=str(fa.source.path),
            destination=str(dest),
            source_size=fa.source.size,
            sidecars=sidecar_records,
        ))
