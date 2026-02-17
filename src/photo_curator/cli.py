"""CLI argument parsing, validation, and main entry point."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from photo_curator import __version__
from photo_curator.config import CuratorConfig, DEFAULT_BATCH_SIZE
from photo_curator.logging_setup import setup_logging
from photo_curator.matching.registry import available_strategies

logger = logging.getLogger("photo_curator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-curator",
        description="Curate photo and video archives: organize, deduplicate, and discard.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- run subcommand (also the default when no subcommand given) ---
    run_parser = subparsers.add_parser(
        "run", help="Run the photo curation pipeline.",
    )
    _add_run_args(run_parser)
    # Also add run args to the top-level parser for backward compat
    _add_run_args(parser)

    # --- undo subcommand ---
    undo_parser = subparsers.add_parser(
        "undo", help="Reverse operations from a previous run using its JSON manifest.",
    )
    undo_parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the JSON manifest from a previous run.",
    )
    undo_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview undo actions without making changes.",
    )
    undo_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG-level) console output.",
    )
    undo_parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for log files (default: same directory as manifest).",
    )

    return parser


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """Add the run-mode arguments to a parser."""
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source directory to recursively scan for photos/videos.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=None,
        help="Destination archive directory (files organized into YYYY/MM).",
    )
    parser.add_argument(
        "--discard",
        type=Path,
        default=None,
        help="Directory for discarded duplicates.",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="copy",
        help="Copy or move files from source (default: copy).",
    )
    parser.add_argument(
        "--match-strategy",
        choices=available_strategies(),
        default="filename-size",
        help="Strategy for detecting duplicate files (default: filename-size).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview all actions without making changes.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG-level) console output.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for log and manifest files (default: current directory).",
    )
    parser.add_argument(
        "--exiftool-batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of files per exiftool batch call (default: {DEFAULT_BATCH_SIZE}).",
    )


def _check_exiftool() -> None:
    """Verify exiftool is installed and on PATH."""
    try:
        subprocess.run(
            ["exiftool", "-ver"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: exiftool is not installed or not in PATH.", file=sys.stderr)
        print("Install it with: sudo apt install libimage-exiftool-perl", file=sys.stderr)
        raise SystemExit(1)


def _validate_run_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments for the run command."""
    if not args.source:
        raise SystemExit("Error: --source is required")
    if not args.destination:
        raise SystemExit("Error: --destination is required")
    if not args.discard:
        raise SystemExit("Error: --discard is required")

    if not args.source.is_dir():
        raise SystemExit(f"Error: --source is not a directory: {args.source}")

    if not args.dry_run:
        args.destination.mkdir(parents=True, exist_ok=True)
        args.discard.mkdir(parents=True, exist_ok=True)

    if args.source.resolve() == args.destination.resolve():
        logger.info("Recursive mode: source and destination are the same directory.")

    _check_exiftool()


def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the run command."""
    log_dir = (args.log_dir or Path(".")).resolve()
    run_id = setup_logging(verbose=args.verbose, log_dir=log_dir)

    _validate_run_args(args)

    config = CuratorConfig(
        source=args.source.resolve(),
        destination=args.destination.resolve(),
        discard=args.discard.resolve(),
        mode=args.mode,
        match_strategy=args.match_strategy,
        dry_run=args.dry_run,
        exiftool_batch_size=args.exiftool_batch_size,
        verbose=args.verbose,
        log_dir=log_dir,
    )

    logger.info("=" * 60)
    logger.info(f"photo-curator v{__version__}")
    logger.info(f"  Source:      {config.source}")
    logger.info(f"  Destination: {config.destination}")
    logger.info(f"  Discard:     {config.discard}")
    logger.info(f"  Mode:        {config.mode}")
    logger.info(f"  Strategy:    {config.match_strategy}")
    logger.info(f"  Dry-run:     {config.dry_run}")
    logger.info(f"  Log dir:     {config.log_dir}")
    logger.info("=" * 60)

    from photo_curator.pipeline import Pipeline

    pipeline = Pipeline(config, run_id)
    result = pipeline.run()

    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(
        f"  Source:      {result.files_scanned} files "
        f"({result.source_photos} photos, {result.source_videos} videos)"
    )
    logger.info(
        f"  Destination: {result.dest_before_total} files before "
        f"-> {result.dest_after_total} files after "
        f"({result.dest_after_photos} photos, {result.dest_after_videos} videos)"
    )
    logger.info(f"  Stored:      {result.files_stored}")
    logger.info(f"  Discarded:   {result.files_discarded}")
    logger.info(f"  Skipped:     {result.files_skipped}")
    logger.info(f"  No date:     {result.files_no_date}")
    logger.info(f"  Errors:      {result.errors}")
    if result.dry_run:
        logger.info("  (DRY-RUN -- no files were changed)")
    if result.manifest_path:
        logger.info(f"  Manifest:    {result.manifest_path}")
    logger.info("=" * 60)

    raise SystemExit(1 if result.errors > 0 else 0)


def _cmd_undo(args: argparse.Namespace) -> None:
    """Execute the undo command."""
    log_dir = (args.log_dir or args.manifest.parent).resolve()
    setup_logging(verbose=args.verbose, log_dir=log_dir)

    from photo_curator.undo import undo

    undo(
        manifest_path=args.manifest.resolve(),
        dry_run=args.dry_run,
        verbose=args.verbose,
        log_dir=log_dir,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "undo":
        _cmd_undo(args)
    else:
        # Default to run (handles both explicit "run" and no subcommand)
        _cmd_run(args)
