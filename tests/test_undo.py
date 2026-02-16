"""Tests for the undo module."""

import json
from pathlib import Path

import pytest

from photo_curator.undo import undo, _load_manifest


def _write_manifest(path: Path, mode: str, operations: list, dry_run=False) -> Path:
    """Helper to create a test manifest file."""
    manifest = {
        "schema_version": "1.0",
        "run_id": "test-run",
        "timestamp": "2026-01-01T00:00:00",
        "config": {
            "source": "/tmp/source",
            "destination": "/tmp/dest",
            "discard": "/tmp/discard",
            "mode": mode,
            "match_strategy": "filename-size",
            "dry_run": dry_run,
        },
        "operations": operations,
        "summary": {"files_scanned": len(operations)},
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


class TestUndoCopyMode:
    def test_deletes_copied_files(self, tmp_path):
        """Copy-mode undo should delete the copies from destination."""
        src = tmp_path / "source"
        src.mkdir()
        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Source still has the original
        src_file = src / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        # Copy exists in destination
        dest_file = dest / "photo.jpg"
        dest_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": str(src_file),
            "destination": str(dest_file),
            "source_size": 52,
            "sidecars": [],
        }])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

        assert not dest_file.exists()  # copy deleted
        assert src_file.exists()  # original untouched

    def test_deletes_discarded_copies(self, tmp_path):
        """Copy-mode undo should delete files from discard dir too."""
        src = tmp_path / "source"
        src.mkdir()
        discard = tmp_path / "discard"
        discard.mkdir()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        src_file = src / "dup.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)
        discard_file = discard / "dup.jpg"
        discard_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "discard_source",
            "source": str(src_file),
            "destination": str(discard_file),
            "source_size": 52,
            "sidecars": [],
        }])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

        assert not discard_file.exists()
        assert src_file.exists()


class TestUndoMoveMode:
    def test_moves_files_back(self, tmp_path):
        """Move-mode undo should move files back to source."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        src_path = src_dir / "photo.jpg"
        dest_file = dest / "photo.jpg"
        dest_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "move", [{
            "action": "store",
            "source": str(src_path),
            "destination": str(dest_file),
            "source_size": 52,
            "sidecars": [],
        }])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

        assert not dest_file.exists()
        assert src_path.exists()
        assert src_path.stat().st_size == 52


class TestUndoDryRun:
    def test_dry_run_no_changes(self, tmp_path):
        """Dry-run undo should not modify any files."""
        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        dest_file = dest / "photo.jpg"
        dest_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": "/tmp/source/photo.jpg",
            "destination": str(dest_file),
            "source_size": 52,
            "sidecars": [],
        }])

        undo(manifest_path, dry_run=True, verbose=False, log_dir=log_dir)

        assert dest_file.exists()  # no changes in dry-run


class TestUndoEdgeCases:
    def test_already_gone_is_idempotent(self, tmp_path):
        """If the file is already deleted, undo should not error."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": "/tmp/source/gone.jpg",
            "destination": str(tmp_path / "nonexistent.jpg"),
            "source_size": 100,
            "sidecars": [],
        }])

        # Should not raise
        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

    def test_empty_operations(self, tmp_path):
        """Undo with no operations should succeed."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

    def test_dry_run_original_skipped(self, tmp_path):
        """If the original run was dry-run, undo should do nothing."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": "/tmp/source/photo.jpg",
            "destination": "/tmp/dest/photo.jpg",
            "source_size": 100,
            "sidecars": [],
        }], dry_run=True)

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

    def test_undo_with_sidecars(self, tmp_path):
        """Undo should also remove sidecar files."""
        src = tmp_path / "source"
        src.mkdir()
        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        src_file = src / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)
        src_xmp = src / "photo.xmp"
        src_xmp.write_text("<xmp/>")

        dest_file = dest / "photo.jpg"
        dest_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)
        dest_xmp = dest / "photo.xmp"
        dest_xmp.write_text("<xmp/>")

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": str(src_file),
            "destination": str(dest_file),
            "source_size": 52,
            "sidecars": [{
                "source": str(src_xmp),
                "destination": str(dest_xmp),
            }],
        }])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

        assert not dest_file.exists()
        assert not dest_xmp.exists()

    def test_writes_undo_manifest(self, tmp_path):
        """Undo should write its own JSON manifest."""
        src = tmp_path / "source"
        src.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Need at least one operation so undo doesn't short-circuit
        src_file = src / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)
        dest_file = dest / "photo.jpg"
        dest_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(manifest_path, "copy", [{
            "action": "store",
            "source": str(src_file),
            "destination": str(dest_file),
            "source_size": 52,
            "sidecars": [],
        }])

        undo(manifest_path, dry_run=False, verbose=False, log_dir=log_dir)

        undo_manifests = list(log_dir.glob("*_undo.json"))
        assert len(undo_manifests) == 1

        data = json.loads(undo_manifests[0].read_text())
        assert data["type"] == "undo"
        assert data["original_run_id"] == "test-run"


class TestLoadManifest:
    def test_missing_file(self, tmp_path):
        with pytest.raises(SystemExit, match="manifest not found"):
            _load_manifest(tmp_path / "nope.json")

    def test_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        with pytest.raises(SystemExit, match="cannot read manifest"):
            _load_manifest(bad)

    def test_missing_schema_version(self, tmp_path):
        f = tmp_path / "no_schema.json"
        f.write_text(json.dumps({"operations": [], "config": {"mode": "copy"}}))
        with pytest.raises(SystemExit, match="schema_version"):
            _load_manifest(f)

    def test_missing_operations(self, tmp_path):
        f = tmp_path / "no_ops.json"
        f.write_text(json.dumps({"schema_version": "1.0", "config": {"mode": "copy"}}))
        with pytest.raises(SystemExit, match="operations"):
            _load_manifest(f)
