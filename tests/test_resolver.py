"""Tests for the Resolver module."""

from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.models import Action, FileCategory, FileRecord, MatchResult
from photo_curator.resolver import Resolver


def _config(dest: Path, discard: Path) -> CuratorConfig:
    return CuratorConfig(
        source=dest,  # doesn't matter for resolver tests
        destination=dest,
        discard=discard,
        mode="copy",
        match_strategy="filename-size",
        dry_run=False,
        exiftool_batch_size=500,
        verbose=False,
        log_dir=dest,
    )


def _record(name: str, year=None, month=None, path=None) -> FileRecord:
    p = path or Path(f"/source/{name}")
    return FileRecord(
        path=p,
        category=FileCategory.PHOTO,
        size=100,
        extension=Path(name).suffix.lower(),
        year=year,
        month=month,
    )


def test_new_file_stored(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    config = _config(dest, discard)
    resolver = Resolver(config)

    mr = MatchResult(
        source=_record("IMG.jpg", year="2024", month="03"),
        matched_destination=None,
        is_duplicate=False,
    )

    actions = resolver.resolve([mr])
    assert len(actions) == 1
    assert actions[0].action == Action.STORE
    assert "2024" in str(actions[0].destination_path)
    assert "03" in str(actions[0].destination_path)


def test_duplicate_discarded(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    config = _config(dest, discard)
    resolver = Resolver(config)

    mr = MatchResult(
        source=_record("IMG.jpg", year="2024", month="03"),
        matched_destination=Path("/dest/2024/03/IMG.jpg"),
        is_duplicate=True,
    )

    actions = resolver.resolve([mr])
    assert len(actions) == 1
    assert actions[0].action == Action.DISCARD_SOURCE
    assert "discard" in str(actions[0].destination_path)


def test_no_date_goes_to_nodate(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    discard = tmp_path / "discard"
    discard.mkdir()

    config = _config(dest, discard)
    resolver = Resolver(config)

    mr = MatchResult(
        source=_record("IMG.jpg"),
        matched_destination=None,
        is_duplicate=False,
    )

    actions = resolver.resolve([mr])
    assert actions[0].action == Action.NO_DATE
    assert "NoDate" in str(actions[0].destination_path)


def test_recursive_skip(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "2024" / "03").mkdir(parents=True)
    discard = tmp_path / "discard"
    discard.mkdir()

    config = _config(dest, discard)
    resolver = Resolver(config)

    file_path = dest / "2024" / "03" / "IMG.jpg"
    mr = MatchResult(
        source=_record("IMG.jpg", year="2024", month="03", path=file_path),
        matched_destination=None,
        is_duplicate=False,
    )

    actions = resolver.resolve([mr])
    assert actions[0].action == Action.SKIP
