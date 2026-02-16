"""Tests for the matching strategy pattern."""

from pathlib import Path

from photo_curator.matching.filename_size import FilenameSizeStrategy
from photo_curator.matching.registry import available_strategies, get_strategy
from photo_curator.models import FileCategory, FileRecord

import pytest


def _record(name: str, size: int) -> FileRecord:
    return FileRecord(
        path=Path(f"/source/{name}"),
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


class TestRegistry:
    def test_get_known_strategy(self):
        s = get_strategy("filename-size")
        assert s.name == "filename-size"

    def test_get_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown match strategy"):
            get_strategy("nonexistent")

    def test_available_strategies(self):
        names = available_strategies()
        assert "filename-size" in names
