"""CLI argument parsing, validation, and main entry point."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from photo_curator.config import CuratorConfig, DEFAULT_BATCH_SIZE
from photo_curator.logging_setup import setup_logging
from photo_curator.matching.registry import available_strategies

logger = logging.getLogger("photo_curator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-curator",
        description="Curate photo and video archives: organize, deduplicate, and discard.",
    )

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Source directory to recursively scan for photos/videos.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="Destination archive directory (files organized into YYYY/MM).",
    )
    parser.add_argument(
        "--discard",
        type=Path,
        required=True,
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
        "--log-file",
        type=Path,
        default=None,
        help="Path to log file (default: photo-curator.log in current directory).",
    )
    parser.add_argument(
        "--exiftool-batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of files per exiftool batch call (default: {DEFAULT_BATCH_SIZE}).",
    )

    return parser


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


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments."""
    if not args.source.is_dir():
        raise SystemExit(f"Error: --source is not a directory: {args.source}")

    if not args.dry_run:
        args.destination.mkdir(parents=True, exist_ok=True)
        args.discard.mkdir(parents=True, exist_ok=True)

    if args.source.resolve() == args.destination.resolve():
        logger.info("Recursive mode: source and destination are the same directory.")

    _check_exiftool()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    log_file = args.log_file or Path("photo-curator.log")
    setup_logging(verbose=args.verbose, log_file=log_file)

    validate_args(args)

    config = CuratorConfig(
        source=args.source.resolve(),
        destination=args.destination.resolve(),
        discard=args.discard.resolve(),
        mode=args.mode,
        match_strategy=args.match_strategy,
        dry_run=args.dry_run,
        exiftool_batch_size=args.exiftool_batch_size,
        verbose=args.verbose,
        log_file=log_file,
    )

    logger.info("=" * 60)
    logger.info("photo-curator v0.1")
    logger.info(f"  Source:      {config.source}")
    logger.info(f"  Destination: {config.destination}")
    logger.info(f"  Discard:     {config.discard}")
    logger.info(f"  Mode:        {config.mode}")
    logger.info(f"  Strategy:    {config.match_strategy}")
    logger.info(f"  Dry-run:     {config.dry_run}")
    logger.info("=" * 60)

    from photo_curator.pipeline import Pipeline

    pipeline = Pipeline(config)
    result = pipeline.run()

    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Scanned:   {result.files_scanned}")
    logger.info(f"  Stored:    {result.files_stored}")
    logger.info(f"  Discarded: {result.files_discarded}")
    logger.info(f"  Skipped:   {result.files_skipped}")
    logger.info(f"  No date:   {result.files_no_date}")
    logger.info(f"  Errors:    {result.errors}")
    if result.dry_run:
        logger.info("  (DRY-RUN -- no files were changed)")
    logger.info("=" * 60)

    raise SystemExit(1 if result.errors > 0 else 0)
