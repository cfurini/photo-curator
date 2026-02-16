"""JSON operations manifest writer for undo support and AI consumption."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.models import OperationRecord, PipelineResult

logger = logging.getLogger(__name__)


class ManifestWriter:
    """Collects file operations during a run and writes a JSON manifest."""

    def __init__(self, run_id: str, config: CuratorConfig, log_dir: Path) -> None:
        self.run_id = run_id
        self.config = config
        self.log_dir = log_dir
        self.operations: list[OperationRecord] = []

    def record(self, operation: OperationRecord) -> None:
        """Append a completed file operation."""
        self.operations.append(operation)

    def finalize(self, result: PipelineResult) -> Path:
        """Write the JSON manifest file and return its path."""
        manifest = {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "source": str(self.config.source),
                "destination": str(self.config.destination),
                "discard": str(self.config.discard),
                "mode": self.config.mode,
                "match_strategy": self.config.match_strategy,
                "dry_run": self.config.dry_run,
            },
            "operations": [
                _operation_to_dict(op) for op in self.operations
            ],
            "summary": {
                "files_scanned": result.files_scanned,
                "files_stored": result.files_stored,
                "files_discarded": result.files_discarded,
                "files_skipped": result.files_skipped,
                "files_no_date": result.files_no_date,
                "errors": result.errors,
            },
        }

        self.log_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.log_dir / f"{self.run_id}.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        logger.info(f"Manifest: {manifest_path}")
        return manifest_path


def _operation_to_dict(op: OperationRecord) -> dict:
    """Convert an OperationRecord to a JSON-serializable dict."""
    d: dict = {
        "action": op.action,
        "source": op.source,
        "destination": op.destination,
        "source_size": op.source_size,
    }
    if op.matched_existing is not None:
        d["matched_existing"] = op.matched_existing
    d["sidecars"] = op.sidecars
    return d
