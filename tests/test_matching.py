"""Tests for the matching strategy pattern."""

from pathlib import Path

from photo_curator.matching.content_hash import ContentHashStrategy, sha256_file
from photo_curator.matching.filename_size import FilenameSizeStrategy
from photo_curator.matching.registry import available_strategies, get_strategy
from photo_curator.models import FileCategory, FileRecord

import pytest


def _record(name: str, size: int, path: Path | None = None) -> FileRecord:
    return FileRecord(
        path=path or Path(f"/source/{name}"),
        category=FileCategory.PHOTO,
        size=size,
        extension=Path(name).suffix.lower(),
    )


class TestFilenameSizeStrategy:
    def test_exact_match(self):
        strategy = FilenameSizeStrategy()
        source = [_record("IMG_001.jpg", 1000)]
        index = {("img_001.jpg", 1000): [Path("/dest/2024/01/IMG_001.jpg")]}

        results = strategy.match_all(source, index)

        assert len(results) == 1
        assert results[0].is_duplicate is True
        assert results[0].matched_destination == Path("/dest/2024/01/IMG_001.jpg")

    def test_no_match_different_size(self):
        strategy = FilenameSizeStrategy()
        source = [_record("IMG_001.jpg", 1000)]
        index = {("img_001.jpg", 2000): [Path("/dest/2024/01/IMG_001.jpg")]}

        results = strategy.match_all(source, index)

        assert len(results) == 1
        assert results[0].is_duplicate is False
        assert results[0].matched_destination is None

    def test_no_match_different_name(self):
        strategy = FilenameSizeStrategy()
        source = [_record("IMG_002.jpg", 1000)]
        index = {("img_001.jpg", 1000): [Path("/dest/2024/01/IMG_001.jpg")]}

        results = strategy.match_all(source, index)

        assert results[0].is_duplicate is False

    def test_case_insensitive_filename(self):
        strategy = FilenameSizeStrategy()
        source = [_record("IMG_001.JPG", 1000)]
        index = {("img_001.jpg", 1000): [Path("/dest/IMG_001.jpg")]}

        results = strategy.match_all(source, index)

        assert results[0].is_duplicate is True

    def test_empty_dest_index(self):
        strategy = FilenameSizeStrategy()
        source = [_record("a.jpg", 100), _record("b.png", 200)]
        index = {}

        results = strategy.match_all(source, index)

        assert all(not r.is_duplicate for r in results)

    def test_empty_source(self):
        strategy = FilenameSizeStrategy()
        results = strategy.match_all([], {("x.jpg", 1): [Path("/x")]})
        assert results == []

    def test_build_index(self, tmp_path):
        (tmp_path / "2024" / "01").mkdir(parents=True)
        content = b"\xff\xd8" + b"\x00" * 100
        (tmp_path / "2024" / "01" / "IMG_001.jpg").write_bytes(content)

        strategy = FilenameSizeStrategy()
        index = strategy.build_index(tmp_path)

        key = ("img_001.jpg", len(content))
        assert key in index
        assert len(index[key]) == 1


class TestContentHashStrategy:
    def test_sha256_file(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"hello world")
        digest = sha256_file(f)
        assert len(digest) == 64  # hex SHA256
        # Same content = same hash
        f2 = tmp_path / "test2.jpg"
        f2.write_bytes(b"hello world")
        assert sha256_file(f2) == digest

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.jpg"
        f1.write_bytes(b"aaa")
        f2 = tmp_path / "b.jpg"
        f2.write_bytes(b"bbb")
        assert sha256_file(f1) != sha256_file(f2)

    def test_exact_content_match(self, tmp_path):
        """Same content under different names is detected as duplicate."""
        strategy = ContentHashStrategy()
        content = b"\xff\xd8" + b"\x00" * 100

        src = tmp_path / "source"
        src.mkdir()
        src_file = src / "renamed_photo.jpg"
        src_file.write_bytes(content)

        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        (dest / "original.jpg").write_bytes(content)

        index = strategy.build_index(tmp_path / "dest")
        source_records = [_record("renamed_photo.jpg", len(content), path=src_file)]
        results = strategy.match_all(source_records, index)

        assert len(results) == 1
        assert results[0].is_duplicate is True

    def test_different_content_no_match(self, tmp_path):
        """Different content is not a duplicate even with same name."""
        strategy = ContentHashStrategy()

        src = tmp_path / "source"
        src.mkdir()
        src_file = src / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 100)

        dest = tmp_path / "dest" / "2024" / "01"
        dest.mkdir(parents=True)
        (dest / "photo.jpg").write_bytes(b"\xff\xd8" + b"\x01" * 100)

        index = strategy.build_index(tmp_path / "dest")
        source_records = [_record("photo.jpg", src_file.stat().st_size, path=src_file)]
        results = strategy.match_all(source_records, index)

        assert results[0].is_duplicate is False

    def test_empty_dest(self, tmp_path):
        strategy = ContentHashStrategy()

        src = tmp_path / "source"
        src.mkdir()
        src_file = src / "photo.jpg"
        src_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        dest = tmp_path / "dest"
        dest.mkdir()

        index = strategy.build_index(dest)
        source_records = [_record("photo.jpg", src_file.stat().st_size, path=src_file)]
        results = strategy.match_all(source_records, index)

        assert results[0].is_duplicate is False

    def test_build_index(self, tmp_path):
        (tmp_path / "2024" / "01").mkdir(parents=True)
        content = b"\xff\xd8" + b"\x00" * 100
        (tmp_path / "2024" / "01" / "IMG_001.jpg").write_bytes(content)

        strategy = ContentHashStrategy()
        index = strategy.build_index(tmp_path)

        assert len(index) == 1
        digest = sha256_file(tmp_path / "2024" / "01" / "IMG_001.jpg")
        assert digest in index


class TestRegistry:
    def test_get_known_strategy(self):
        s = get_strategy("filename-size")
        assert s.name == "filename-size"

    def test_get_content_hash_strategy(self):
        s = get_strategy("content-hash")
        assert s.name == "content-hash"

    def test_get_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown match strategy"):
            get_strategy("nonexistent")

    def test_available_strategies(self):
        names = available_strategies()
        assert "filename-size" in names
        assert "content-hash" in names
