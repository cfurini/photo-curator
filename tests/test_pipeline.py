"""Integration tests for the full pipeline."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from photo_curator.config import CuratorConfig
from photo_curator.pipeline import Pipeline


def _has_exiftool() -> bool:
    try:
        subprocess.run(["exiftool", "-ver"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


requires_exiftool = pytest.mark.skipif(
    not _has_exiftool(), reason="exiftool not installed"
)


def _config(source, dest, discard, mode="copy", dry_run=False) -> CuratorConfig:
    return CuratorConfig(
        source=source,
        destination=dest,
        discard=discard,
        mode=mode,
        match_strategy="filename-size",
        dry_run=dry_run,
        exiftool_batch_size=500,
        verbose=False,
        log_file=None,
    )


@requires_exiftool
def test_pipeline_new_files_no_exif(tmp_path):
    """Files without EXIF go to NoDate/."""
    src = tmp_path / "source"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    # Create a minimal JPEG (no real EXIF)
    (src / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    config = _config(src, dest, discard)
    result = Pipeline(config).run()

    assert result.files_scanned == 1
    assert result.files_no_date == 1
    assert (dest / "NoDate" / "photo.jpg").exists()


@requires_exiftool
def test_pipeline_dry_run_no_writes(tmp_path):
    """Dry run should not create any files."""
    src = tmp_path / "source"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    (src / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    config = _config(src, dest, discard, dry_run=True)
    result = Pipeline(config).run()

    assert result.files_scanned == 1
    assert not (dest / "NoDate" / "photo.jpg").exists()


@requires_exiftool
def test_pipeline_duplicate_goes_to_discard(tmp_path):
    """A file matching name+size in dest should be discarded."""
    src = tmp_path / "source"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    content = b"\xff\xd8\xff\xe0" + b"\x00" * 100

    # Put the same file in source and destination
    (src / "photo.jpg").write_bytes(content)
    (dest / "2024" / "01").mkdir(parents=True)
    (dest / "2024" / "01" / "photo.jpg").write_bytes(content)

    config = _config(src, dest, discard)
    result = Pipeline(config).run()

    assert result.files_discarded == 1
    assert (discard / "photo.jpg").exists()


@requires_exiftool
def test_pipeline_move_mode_removes_source(tmp_path):
    """In move mode, source file should be gone after processing."""
    src = tmp_path / "source"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    src_file = src / "unique.jpg"
    src_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    config = _config(src, dest, discard, mode="move")
    result = Pipeline(config).run()

    assert result.files_scanned == 1
    assert not src_file.exists()


def test_pipeline_empty_source(tmp_path):
    """An empty source directory should produce zero results."""
    src = tmp_path / "source"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    config = _config(src, dest, discard)
    result = Pipeline(config).run()

    assert result.files_scanned == 0
    assert result.errors == 0
