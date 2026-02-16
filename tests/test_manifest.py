"""Tests for the ManifestWriter module."""

import json
from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.manifest import ManifestWriter
from photo_curator.models import OperationRecord, PipelineResult


def _config(tmp_path: Path) -> CuratorConfig:
    return CuratorConfig(
        source=tmp_path / "source",
        destination=tmp_path / "dest",
        discard=tmp_path / "discard",
        mode="copy",
        match_strategy="filename-size",
        dry_run=False,
        exiftool_batch_size=500,
        verbose=False,
        log_dir=tmp_path / "logs",
    )


class TestManifestWriter:
    def test_finalize_writes_json(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-001", config, log_dir)

        result = PipelineResult(files_scanned=1, files_stored=1)
        path = writer.finalize(result)

        assert path.exists()
        assert path.suffix == ".json"
        data = json.loads(path.read_text())
        assert data["schema_version"] == "1.0"
        assert data["run_id"] == "test-run-001"

    def test_records_operations(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-002", config, log_dir)

        writer.record(OperationRecord(
            action="store",
            source="/src/photo.jpg",
            destination="/dest/2024/01/photo.jpg",
            source_size=1234,
        ))
        writer.record(OperationRecord(
            action="discard_source",
            source="/src/dup.jpg",
            destination="/discard/dup.jpg",
            source_size=5678,
        ))

        result = PipelineResult(files_scanned=2, files_stored=1, files_discarded=1)
        path = writer.finalize(result)

        data = json.loads(path.read_text())
        assert len(data["operations"]) == 2
        assert data["operations"][0]["action"] == "store"
        assert data["operations"][1]["action"] == "discard_source"

    def test_config_in_manifest(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-003", config, log_dir)

        path = writer.finalize(PipelineResult())
        data = json.loads(path.read_text())

        assert data["config"]["mode"] == "copy"
        assert data["config"]["match_strategy"] == "filename-size"
        assert data["config"]["dry_run"] is False

    def test_summary_in_manifest(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-004", config, log_dir)

        result = PipelineResult(
            files_scanned=10,
            files_stored=5,
            files_discarded=3,
            files_skipped=1,
            files_no_date=1,
            errors=0,
        )
        path = writer.finalize(result)
        data = json.loads(path.read_text())

        assert data["summary"]["files_scanned"] == 10
        assert data["summary"]["files_stored"] == 5
        assert data["summary"]["files_discarded"] == 3

    def test_sidecars_in_operation(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-005", config, log_dir)

        writer.record(OperationRecord(
            action="store",
            source="/src/photo.jpg",
            destination="/dest/2024/01/photo.jpg",
            source_size=1234,
            sidecars=[
                {"source": "/src/photo.xmp", "destination": "/dest/2024/01/photo.xmp"},
            ],
        ))

        path = writer.finalize(PipelineResult(files_stored=1))
        data = json.loads(path.read_text())

        assert len(data["operations"][0]["sidecars"]) == 1
        assert data["operations"][0]["sidecars"][0]["source"] == "/src/photo.xmp"

    def test_creates_log_dir_if_missing(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "new_logs"
        writer = ManifestWriter("test-run-006", config, log_dir)

        path = writer.finalize(PipelineResult())
        assert path.exists()
        assert log_dir.exists()

    def test_empty_operations(self, tmp_path):
        config = _config(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        writer = ManifestWriter("test-run-007", config, log_dir)

        path = writer.finalize(PipelineResult())
        data = json.loads(path.read_text())

        assert data["operations"] == []
