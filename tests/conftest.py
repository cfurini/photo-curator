"""Shared test fixtures."""

import pytest
from pathlib import Path

from photo_curator.config import CuratorConfig


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    return src


@pytest.fixture
def dest_dir(tmp_path: Path) -> Path:
    dest = tmp_path / "destination"
    dest.mkdir()
    return dest


@pytest.fixture
def discard_dir(tmp_path: Path) -> Path:
    d = tmp_path / "discard"
    d.mkdir()
    return d


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def make_config(source_dir, dest_dir, discard_dir, log_dir):
    """Factory fixture for creating CuratorConfig with overrides."""

    def _make(**overrides):
        defaults = dict(
            source=source_dir,
            destination=dest_dir,
            discard=discard_dir,
            mode="copy",
            match_strategy="filename-size",
            dry_run=False,
            exiftool_batch_size=500,
            verbose=False,
            log_dir=log_dir,
        )
        defaults.update(overrides)
        return CuratorConfig(**defaults)

    return _make
