"""Tests for the Scanner module."""

from pathlib import Path

from photo_curator.models import FileCategory
from photo_curator.scanner import Scanner


def test_scan_finds_media_files(make_config, source_dir):
    (source_dir / "photo.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (source_dir / "video.mp4").write_bytes(b"\x00" * 200)

    config = make_config()
    scanner = Scanner(config)
    media, sidecars = scanner.scan()

    assert len(media) == 2
    names = {r.path.name for r in media}
    assert names == {"photo.jpg", "video.mp4"}


def test_scan_categorizes_correctly(make_config, source_dir):
    (source_dir / "pic.cr2").write_bytes(b"\x00" * 50)
    (source_dir / "clip.mov").write_bytes(b"\x00" * 50)

    config = make_config()
    media, _ = Scanner(config).scan()

    by_name = {r.path.name: r for r in media}
    assert by_name["pic.cr2"].category == FileCategory.PHOTO
    assert by_name["clip.mov"].category == FileCategory.VIDEO


def test_scan_recursive(make_config, source_dir):
    sub = source_dir / "sub" / "deep"
    sub.mkdir(parents=True)
    (sub / "nested.jpg").write_bytes(b"\x00" * 10)

    config = make_config()
    media, _ = Scanner(config).scan()

    assert len(media) == 1
    assert media[0].path.name == "nested.jpg"


def test_scan_skips_junk_files(make_config, source_dir):
    (source_dir / "Thumbs.db").write_bytes(b"\x00" * 10)
    (source_dir / ".DS_Store").write_bytes(b"\x00" * 10)
    (source_dir / "real.jpg").write_bytes(b"\x00" * 10)

    config = make_config()
    media, _ = Scanner(config).scan()

    assert len(media) == 1
    assert media[0].path.name == "real.jpg"


def test_scan_skips_junk_dirs(make_config, source_dir):
    junk = source_dir / ".picasaoriginals"
    junk.mkdir()
    (junk / "hidden.jpg").write_bytes(b"\x00" * 10)
    (source_dir / "visible.jpg").write_bytes(b"\x00" * 10)

    config = make_config()
    media, _ = Scanner(config).scan()

    assert len(media) == 1
    assert media[0].path.name == "visible.jpg"


def test_sidecar_mapping(make_config, source_dir):
    (source_dir / "IMG_001.jpg").write_bytes(b"\x00" * 100)
    (source_dir / "IMG_001.xmp").write_text("<xmp/>")

    config = make_config()
    media, sidecar_map = Scanner(config).scan()

    assert len(media) == 1
    media_path = media[0].path
    assert media_path in sidecar_map
    assert len(sidecar_map[media_path]) == 1
    assert sidecar_map[media_path][0].extension == ".xmp"


def test_orphan_sidecar_not_in_map(make_config, source_dir):
    (source_dir / "orphan.xmp").write_text("<xmp/>")

    config = make_config()
    media, sidecar_map = Scanner(config).scan()

    assert len(media) == 0
    assert len(sidecar_map) == 0


def test_index_destination(make_config, dest_dir):
    (dest_dir / "2024" / "01").mkdir(parents=True)
    content = b"\xff\xd8" + b"\x00" * 100
    (dest_dir / "2024" / "01" / "IMG_001.jpg").write_bytes(content)

    config = make_config()
    index = Scanner(config).index_destination()

    key = ("img_001.jpg", len(content))
    assert key in index
    assert len(index[key]) == 1


def test_index_destination_empty(make_config, dest_dir):
    config = make_config()
    index = Scanner(config).index_destination()
    assert index == {}


def test_scan_ignores_unknown_extensions(make_config, source_dir):
    (source_dir / "readme.txt").write_text("hello")
    (source_dir / "data.csv").write_text("a,b")
    (source_dir / "real.png").write_bytes(b"\x00" * 10)

    config = make_config()
    media, _ = Scanner(config).scan()

    assert len(media) == 1
    assert media[0].path.name == "real.png"
