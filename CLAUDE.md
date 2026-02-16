# CLAUDE.md — photo-curator project conventions

## What this project is

CLI tool that curates photo/video archives: scans a source directory, organizes files into YYYY/MM structure by EXIF date, detects duplicates, and routes losers to a discard directory. Built to evolve with new matching strategies over time.

## Key reference

Read `MasterDoc.md` before making changes — it is the authoritative baseline for business rules, architecture, and implementation details.

## Project structure

- `src/photo_curator/` — all source code (src layout)
- `tests/` — pytest test suite
- `pyproject.toml` — build config, dependencies, entry point
- Python 3.10+, zero runtime dependencies, exiftool required as system package

## Architecture rules

- **Pipeline is 5 sequential phases**: scan → metadata → match → resolve → execute. All changes must respect this flow.
- **Strategy pattern for matching**: new matching strategies go in `src/photo_curator/matching/` as a new file implementing `MatchStrategy` ABC, then registered in `registry.py`. Never modify existing strategies to add new behavior.
- **Resolver is where conflict logic lives**: keep vs discard decisions belong in `resolver.py`, not in the mover or matching layers.
- **Mover is the only module that touches the filesystem** (copy/move). All other modules are read-only or produce data structures.
- **Models are frozen dataclasses** (`FileRecord`, `MatchResult`, `CuratorConfig`). Do not make them mutable. `FileAction` and `PipelineResult` are intentionally mutable.
- **No data is ever deleted.** Files go to destination or discard — never removed. The discard directory is a holding area for human review.

## Coding conventions

- Standard library only for runtime — no pip dependencies. Dev dependencies (pytest) go in `[project.optional-dependencies] dev`.
- Use `pathlib.Path` for all file paths, never raw strings.
- Use `logging.getLogger(__name__)` in each module — never print().
- Type hints on all function signatures.
- Constants (extension sets, skip lists, EXIF fields) live in `config.py` — do not scatter them across modules.
- File type constants are `FrozenSet[str]` — do not use mutable sets.

## CLI conventions

- All three directory arguments (`--source`, `--destination`, `--discard`) are required.
- `--dry-run` must be supported by every code path that writes to disk.
- Exit code 0 on success, 1 if any errors occurred.
- Validation happens in `cli.py:validate_args()` before the pipeline runs.

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

- Unit tests do NOT require exiftool — mock subprocess or test pure functions.
- Integration tests in `test_pipeline.py` require exiftool and are marked with `@requires_exiftool` (auto-skipped if missing).
- Use `tmp_path` fixture for all file I/O in tests — never write to real directories.
- The `make_config` fixture in `conftest.py` creates `CuratorConfig` with sane defaults — use it instead of building configs manually.

## Adding a new matching strategy

1. Create `src/photo_curator/matching/your_strategy.py`
2. Implement class inheriting from `MatchStrategy` (in `base.py`)
3. Add `_register(YourStrategy())` in `registry.py`
4. The strategy auto-appears in `--match-strategy` CLI choices
5. Add tests in `tests/test_matching.py`

## Git workflow

- Branch from `main` for features
- Commit messages: imperative mood, focus on "why" not "what"
- Run `pytest tests/ -v` before committing — all tests must pass
