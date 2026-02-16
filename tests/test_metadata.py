"""Tests for the metadata module."""

from photo_curator.metadata import parse_date


def test_parse_date_valid():
    assert parse_date("2024:01:15 10:30:00") == ("2024", "01")


def test_parse_date_single_digit_month():
    assert parse_date("2020:3:05 00:00:00") == ("2020", "03")


def test_parse_date_none():
    assert parse_date(None) is None


def test_parse_date_empty_string():
    assert parse_date("") is None


def test_parse_date_zero_date():
    assert parse_date("0000:00:00 00:00:00") is None


def test_parse_date_invalid_month():
    assert parse_date("2024:13:01 00:00:00") is None


def test_parse_date_invalid_year_too_low():
    assert parse_date("1800:01:01 00:00:00") is None


def test_parse_date_invalid_year_too_high():
    assert parse_date("2200:01:01 00:00:00") is None


def test_parse_date_garbage():
    assert parse_date("not-a-date") is None


def test_parse_date_boundary_valid():
    assert parse_date("1900:01:01 00:00:00") == ("1900", "01")
    assert parse_date("2100:12:31 23:59:59") == ("2100", "12")
