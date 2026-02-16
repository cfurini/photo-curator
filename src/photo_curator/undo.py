"""Undo operations from a previous photo-curator run using its JSON manifest."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def undo(
    manifest_path: Path,
    dry_run: bool,
    verbose: bool,
    log_dir: Path,
) -> None:
    """Reverse all file operations recorded in a JSON manifest.

    - Copy-mode runs: delete the copied files (originals still in source).
    - Move-mode runs: move files back from destination/discard to source.
    """
    logger.info("=" * 60)
    logger.info(f"photo-curator UNDO")
    logger.info(f"  Manifest: {manifest_path}")
    logger.info(f"  Dry-run:  {dry_run}")
    logger.info("=" * 60)

    manifest = _load_manifest(manifest_path)
    mode = manifest["config"]["mode"]
    operations = manifest["operations"]

    if manifest["config"].get("dry_run", False):
        logger.info("Original run was dry-run — nothing to undo.")
        return

    if not operations:
        logger.info("No operations to undo.")
        return

    undo_records: list[dict] = []
    errors = 0

    # Process operations in reverse order
    for op in reversed(operations):
        # Undo sidecars first (reverse of how they were applied)
        for sc in reversed(op.get("sidecars", [])):
            ok = _undo_one(
                source=sc["source"],
                destination=sc["destination"],
                source_size=None,
                mode=mode,
                dry_run=dry_run,
            )
            if ok:
                undo_records.append({
                    "undone_source": sc["source"],
                    "undone_destination": sc["destination"],
                })
            else:
                errors += 1

        # Undo the main file
        ok = _undo_one(
            source=op["source"],
            destination=op["destination"],
            source_size=op.get("source_size"),
            mode=mode,
            dry_run=dry_run,
        )
        if ok:
            undo_records.append({
                "undone_source": op["source"],
                "undone_destination": op["destination"],
            })
        else:
            errors += 1

    # Write undo manifest
    if not dry_run:
        _write_undo_manifest(manifest_path, manifest, undo_records, errors, log_dir)

    logger.info("=" * 60)
    logger.info("Undo summary:")
    logger.info(f"  Operations undone: {len(undo_records)}")
    logger.info(f"  Errors:            {errors}")
    if dry_run:
        logger.info("  (DRY-RUN -- no files were changed)")
    logger.info("=" * 60)

    if errors > 0:
        raise SystemExit(1)


def _undo_one(
    source: str,
    destination: str,
    source_size: int | None,
    mode: str,
    dry_run: bool,
) -> bool:
    """Undo a single file operation. Returns True on success."""
    dest_path = Path(destination)
    src_path = Path(source)
    prefix = "[DRY-RUN] " if dry_run else ""

    if not dest_path.exists():
        logger.warning(f"SKIP (already gone): {dest_path}")
        return True  # Idempotent — not an error

    # Validate size if available
    if source_size is not None and dest_path.stat().st_size != source_size:
        logger.warning(
            f"SKIP (size mismatch): {dest_path} "
            f"(expected {source_size}, got {dest_path.stat().st_size})"
        )
        return False

    if mode == "copy":
        # Copy mode: originals are still in source, delete the copy
        logger.info(f"{prefix}DELETE: {dest_path}")
        if not dry_run:
            dest_path.unlink()
            _remove_empty_parents(dest_path.parent)
    else:
        # Move mode: move the file back to its original source location
        logger.info(f"{prefix}MOVE BACK: {dest_path} -> {src_path}")
        if not dry_run:
            src_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest_path), str(src_path))
            _remove_empty_parents(dest_path.parent)

    return True


def _remove_empty_parents(directory: Path) -> None:
    """Remove empty directories up the tree (stops at first non-empty)."""
    try:
        while directory != directory.parent:
            if not any(directory.iterdir()):
                directory.rmdir()
                directory = directory.parent
            else:
                break
    except OSError:
        pass  # Permission error or race condition — safe to ignore


def _load_manifest(path: Path) -> dict:
    """Load and validate a JSON manifest file."""
    if not path.exists():
        raise SystemExit(f"Error: manifest not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit(f"Error: cannot read manifest: {e}")

    if "schema_version" not in data:
        raise SystemExit("Error: manifest missing schema_version field")
    if "operations" not in data:
        raise SystemExit("Error: manifest missing operations field")
    if "config" not in data or "mode" not in data["config"]:
        raise SystemExit("Error: manifest missing config.mode field")

    return data


def _write_undo_manifest(
    original_manifest: Path,
    manifest_data: dict,
    undo_records: list[dict],
    errors: int,
    log_dir: Path,
) -> Path:
    """Write a JSON manifest recording what the undo operation did."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    undo_manifest = {
        "schema_version": "1.0",
        "type": "undo",
        "run_id": f"photo-curator_{timestamp}_undo",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "original_manifest": str(original_manifest),
        "original_run_id": manifest_data.get("run_id", "unknown"),
        "mode": manifest_data["config"]["mode"],
        "operations_undone": undo_records,
        "errors": errors,
    }

    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"photo-curator_{timestamp}_undo.json"
    path.write_text(
        json.dumps(undo_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info(f"Undo manifest: {path}")
    return path
