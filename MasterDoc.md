# photo-curator — Master Document

> **Purpose**: Living baseline for the photo-curator product. AI-consumable, human-reviewed.
> **Version**: 0.3.1 | **Last updated**: 2026-02-17

---

## 1. Business Goals, Rules and Architecture

### Problem

Family photo archives accumulate duplicates and disorganization across devices, imports, and backups. Manual curation does not scale.

### Goal

A CLI tool that ingests photos/videos from a source, organizes them into a date-based archive, detects duplicates, and discards the losers — with evolving intelligence over time.

### Core Concepts

| Concept | Definition |
|---------|-----------|
| **Source** | Directory scanned recursively for new media files |
| **Destination** | Archive organized as `YYYY/MM/` folders based on EXIF date. Files without date go to `NoDate/` |
| **Discard** | Directory where duplicate/inferior copies are sent. Nothing is deleted — the human decides when to purge |
| **Sidecar** | Metadata files (.xmp, .thm, .aae) that travel with their parent media file |

### Business Rules

1. **Duplicate detection** supports pluggable strategies. `filename-size` matches by name + byte size. `content-hash` matches by SHA256 of file content (catches renamed duplicates).
2. **Conflict resolution** is conservative: when a duplicate is found, the archive copy always wins. The source copy goes to discard.
3. **No data is ever deleted.** Files are either stored, discarded (moved to a safe holding area), or skipped.
4. **Copy is the default mode.** Move mode (which empties the source) must be explicitly requested.
5. **Recursive mode** is supported: source and destination can be the same directory. This allows re-processing the archive when a new dedup strategy is added.
6. **Dry-run** previews every action without touching any file.

### Supported Media

- **Photos (16):** jpg, jpeg, cr2, cr3, heic, png, tiff, tif, gif, bmp, nef, arw, dng, orf, rw2
- **Videos (9):** mov, mp4, avi, mpeg, mpg, m4v, mkv, wmv, 3gp
- **Sidecars (3):** xmp, thm, aae
- **Ignored:** desktop.ini, thumbs.db, .ds_store, .picasa.ini, zbthumbnail.info, `.picasaoriginals/` dirs

---

## 2. Product Architecture

### System Context

```
User (CLI) ──▶ photo-curator ──▶ exiftool (subprocess, batch JSON)
                    │
                    ├──▶ Source directory      (read)
                    ├──▶ Destination directory  (read + write)
                    └──▶ Discard directory      (write)
```

- **Runtime:** Python 3.10+, Ubuntu Server
- **External dependency:** `exiftool` (system package `libimage-exiftool-perl`)
- **Python dependencies:** None (stdlib only)

### CLI Interface

```
photo-curator --source PATH --destination PATH --discard PATH [OPTIONS]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--mode {copy,move}` | `copy` | Move empties source after run |
| `--match-strategy` | `filename-size` | `filename-size` or `content-hash` (extensible) |
| `--dry-run` | off | Preview without changes |
| `--verbose` / `-v` | off | DEBUG-level console output |
| `--log-dir PATH` | `.` (cwd) | Directory for `.log` and `.json` manifest files |
| `--exiftool-batch-size N` | `500` | Files per exiftool invocation |

**Subcommands:**
- `photo-curator [run]` — Run the curation pipeline (default)
- `photo-curator undo <manifest.json>` — Reverse operations from a previous run

### Pipeline (5 sequential phases)

```
1. SCAN         Scanner.scan()              → media FileRecords + sidecar map
2. METADATA     MetadataExtractor.enrich()  → FileRecords with year/month from EXIF
3. MATCH        Strategy.match_all()        → MatchResults (duplicate or new)
4. RESOLVE      Resolver.resolve()          → FileActions (store/discard/skip)
5. EXECUTE      Mover.execute()             → copy or move files, progress bar, update counters
6. MANIFEST     ManifestWriter.finalize()   → write JSON manifest (skipped in dry-run)
```

### Matching Strategy Pattern

```
matching/
├── base.py              ABC: name + build_index() + match_all()
├── filename_size.py     Match by (filename.lower(), file_size)
├── content_hash.py      Match by SHA256 of file content
└── registry.py          Lookup by name; add strategy = 1 file + 1 registry line
```

Each strategy owns its index building via `build_index(destination)`. The pipeline calls `strategy.build_index()` then `strategy.match_all()`. A shared `walk_destination()` helper in `scanner.py` provides the file list that strategies index. Both strategies also detect **source-to-source duplicates**: as each new file is processed, it is added to the index so subsequent source files with the same key are caught.

| Strategy | Index key | Catches | Trade-off |
|----------|-----------|---------|-----------|
| `filename-size` | `(name.lower(), size)` | Exact copies with same name | Fast; misses renamed files |
| `content-hash` | SHA256 hex digest | Renamed duplicates, any identical content | Slower; must read every byte |

### Conflict Resolution Rules

| Condition | Action | Destination |
|-----------|--------|-------------|
| Duplicate found | `DISCARD_SOURCE` | `{discard}/{filename}` |
| New file, has EXIF date | `STORE` | `{destination}/{YYYY}/{MM}/{filename}` |
| New file, no EXIF date | `NO_DATE` | `{destination}/NoDate/{filename}` |
| Already in correct path (recursive mode) | `SKIP` | no-op |

Name collisions at destination are resolved by appending `_001`, `_002`, etc.

### EXIF Date Extraction

Fields checked in priority order via exiftool batch JSON:
1. `DateTimeOriginal`
2. `CreateDate`
3. `MediaCreateDate`

First non-empty, non-zero field wins. Date validated: year ∈ [1900, 2100], month ∈ [1, 12].

---

## 3. Implementation Plan

### Project Structure

```
photo-curator/
├── pyproject.toml
├── .gitignore
├── src/photo_curator/
│   ├── __init__.py          version string
│   ├── __main__.py          python -m entry
│   ├── cli.py               argparse + validation + main()
│   ├── config.py            CuratorConfig dataclass + extension constants
│   ├── logging_setup.py     console + timestamped file logging
│   ├── manifest.py          JSON operations manifest writer (ManifestWriter)
│   ├── models.py            FileRecord, MatchResult, FileAction, OperationRecord, PipelineResult, enums
│   ├── scanner.py           recursive walk, sidecar mapping, walk_destination() helper
│   ├── metadata.py          exiftool batch calls, date parsing
│   ├── resolver.py          conflict resolution logic
│   ├── mover.py             copy/move/dry-run + duplicate name resolution + manifest recording
│   ├── pipeline.py          orchestrator wiring phases 1–6
│   ├── undo.py              undo operations from a JSON manifest
│   └── matching/
│       ├── base.py          MatchStrategy ABC (name + build_index + match_all)
│       ├── filename_size.py FilenameSizeStrategy
│       ├── content_hash.py  ContentHashStrategy (SHA256)
│       └── registry.py      strategy registry
└── tests/
    ├── conftest.py          shared fixtures (tmp dirs, config factory)
    ├── test_scanner.py      13 tests (scan + walk_destination + count_media)
    ├── test_metadata.py     10 tests (parse_date edge cases)
    ├── test_matching.py     18 tests (filename-size, content-hash, source-to-source dups, build_index, registry)
    ├── test_resolver.py      4 tests (each resolution rule)
    ├── test_mover.py        10 tests (copy, move, dry-run, discard, skip, name collision, manifest)
    ├── test_manifest.py      7 tests (ManifestWriter: write, record, config, summary, sidecars)
    ├── test_undo.py         11 tests (copy/move undo, dry-run, edge cases, manifest validation)
    └── test_pipeline.py      7 integration tests (requires exiftool)
```

### Data Models

**FileRecord** (frozen): `path`, `category`, `size`, `extension`, `year`, `month`, `parent_media`
**MatchResult** (frozen): `source`, `matched_destination`, `is_duplicate`
**FileAction** (mutable): `source`, `action`, `destination_path`, `sidecars`, `reason`
**OperationRecord** (mutable): `action`, `source`, `destination`, `source_size`, `matched_existing`, `sidecars`
**PipelineResult** (mutable): `files_scanned`, `files_stored`, `files_discarded`, `files_skipped`, `files_no_date`, `errors`, `dry_run`, `manifest_path`, `source_photos`, `source_videos`, `dest_before_total`, `dest_before_photos`, `dest_before_videos`, `dest_after_total`, `dest_after_photos`, `dest_after_videos`
**CuratorConfig** (frozen): `source`, `destination`, `discard`, `mode`, `match_strategy`, `dry_run`, `exiftool_batch_size`, `verbose`, `log_dir`

### Build & Test

```bash
cd photo-curator
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v            # 83 tests, all passing
photo-curator --help        # verify CLI
```

### Implementation Status (v0.3.1) — Complete

All 16 modules implemented. 83 tests passing. CLI operational with dry-run, copy, move modes, two matching strategies (filename-size, content-hash), structured JSON manifest output (skipped in dry-run), undo capability, source-to-source duplicate detection, single-line progress bar, and before/after destination inventory in summary.

---

## 4. Recommended Next Steps

### Completed

- ~~Hash-based matching strategy~~ — `content-hash` (SHA256). Done in v0.2.
- ~~Git init + CLAUDE.md~~ — Repo at `github.com/cfurini/photo-curator`. Done in v0.2.
- ~~Structured logging + undo~~ — Timestamped `.log` + `.json` manifest per run. `undo` subcommand reverses operations. `--log-dir` CLI option. Done in v0.3.
- ~~Source-to-source duplicate detection~~ — Both strategies now detect duplicates within the source batch, not only against the destination. Done in v0.3.1.
- ~~Console output improvements~~ — Single-line progress bar during Phase 5 (overwrites in place). Before/after destination inventory in summary. Per-file actions moved to DEBUG. JSON manifest skipped in dry-run. Done in v0.3.1.

### Near-term (v0.4)

1. **Progress tracking** — JSON checkpoint file for resumability on large archives. Enables safe interruption and restart of multi-hour runs.
2. **Quality-based conflict resolution** — When a duplicate is found, compare resolution, file format hierarchy (RAW > JPEG), or file size to pick the better copy. Keep the winner in archive, send the loser to discard.

### Mid-term (v0.5–v0.6)

3. **EXIF-based matching** — Match by camera model + timestamp + dimensions. Catches duplicates across different export names.
4. **Perceptual hashing** — pHash/dHash via `imagehash` library. Detects near-duplicates (crops, re-encodes, slight edits).

### Long-term

5. **Parallel exiftool** — `concurrent.futures` to run multiple batches simultaneously for faster metadata extraction on large archives.
6. **Integration with Immich/Photoprism** — Notify or sync with a photo management frontend after curation.
