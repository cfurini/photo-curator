"""Tests for the Mover module."""

from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.models import Action, FileAction, FileCategory, FileRecord, PipelineResult
from photo_curator.mover import Mover, resolve_duplicate_name


def _config(dest: Path, discard: Path, mode="copy", dry_run=False) -> CuratorConfig:
    return CuratorConfig(
        source=dest,
        destination=dest,
        discard=discard,
        mode=mode,
        match_strategy="filename-size",
        dry_run=dry_run,
        exiftool_batch_size=500,
        verbose=False,
        log_file=None,
    )


def _record(path: Path) -> FileRecord:
    return FileRecord(
        path=path,
        category=FileCategory.PHOTO,
        size=path.stat().st_size,
        extension=path.suffix.lower(),
    )


class TestResolveDuplicateName:
    def test_no_conflict(self, tmp_path):
        target = tmp_path / "file.jpg"
        assert resolve_duplicate_name(target) == target

    def test_one_conflict(self, tmp_path):
        target = tmp_path / "file.jpg"
        target.write_bytes(b"\x00")
        result = resolve_duplicate_name(target)
        assert result == tmp_path / "file_001.jpg"

    def test_multiple_conflicts(self, tmp_path):
        (tmp_path / "file.jpg").write_bytes(b"\x00")
        (tmp_path / "file_001.jpg").write_bytes(b"\x00")
        (tmp_path / "file_002.jpg").write_bytes(b"\x00")
        result = resolve_duplicate_name(tmp_path / "file.jpg")
        assert result == tmp_path / "file_003.jpg"


class TestMover:
    def test_copy_stores_file(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        discard_dir = tmp_path / "discard"
        discard_dir.mkdir()

        src_file = src_dir / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        config = _config(dest_dir, discard_dir, mode="copy")
        mover = Mover(config)

        dest_path = dest_dir / "2024" / "01" / "photo.jpg"
        action = FileAction(
            source=_record(src_file),
            action=Action.STORE,
            destination_path=dest_path,
        )

        result = mover.execute([action], PipelineResult())
        assert result.files_stored == 1
        assert dest_path.exists()
        assert src_file.exists()  # copy mode: source untouched

    def test_move_removes_source(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        discard_dir = tmp_path / "discard"
        discard_dir.mkdir()

        src_file = src_dir / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        config = _config(dest_dir, discard_dir, mode="move")
        mover = Mover(config)

        dest_path = dest_dir / "2024" / "01" / "photo.jpg"
        action = FileAction(
            source=_record(src_file),
            action=Action.STORE,
            destination_path=dest_path,
        )

        result = mover.execute([action], PipelineResult())
        assert result.files_stored == 1
        assert dest_path.exists()
        assert not src_file.exists()  # move mode: source removed

    def test_dry_run_no_changes(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        discard_dir = tmp_path / "discard"
        discard_dir.mkdir()

        src_file = src_dir / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        config = _config(dest_dir, discard_dir, dry_run=True)
        mover = Mover(config)

        dest_path = dest_dir / "2024" / "01" / "photo.jpg"
        action = FileAction(
            source=_record(src_file),
            action=Action.STORE,
            destination_path=dest_path,
        )

        result = mover.execute([action], PipelineResult())
        assert result.files_stored == 1
        assert not dest_path.exists()  # dry run: nothing written
        assert src_file.exists()

    def test_discard_source(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        discard_dir = tmp_path / "discard"
        discard_dir.mkdir()

        src_file = src_dir / "dup.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        config = _config(dest_dir, discard_dir, mode="copy")
        mover = Mover(config)

        discard_path = discard_dir / "dup.jpg"
        action = FileAction(
            source=_record(src_file),
            action=Action.DISCARD_SOURCE,
            destination_path=discard_path,
        )

        result = mover.execute([action], PipelineResult())
        assert result.files_discarded == 1
        assert discard_path.exists()

    def test_skip_counts(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        discard_dir = tmp_path / "discard"
        discard_dir.mkdir()

        src_file = src_dir / "skip.jpg"
        src_file.write_bytes(b"\x00" * 10)

        config = _config(dest_dir, discard_dir)
        mover = Mover(config)

        action = FileAction(
            source=_record(src_file),
            action=Action.SKIP,
            destination_path=src_file,
        )

        result = mover.execute([action], PipelineResult())
        assert result.files_skipped == 1
