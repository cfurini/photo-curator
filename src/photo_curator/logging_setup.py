"""Logging configuration for photo-curator."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(verbose: bool = False, log_dir: Path = Path(".")) -> str:
    """Configure the photo_curator logger with console + timestamped file handler.

    Returns the run_id string (e.g. 'photo-curator_20260216_143022') so the
    manifest writer can use the same timestamp.
    """
    run_id = f"photo-curator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    root = logging.getLogger("photo_curator")
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_id}.log"
    fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    ))
    root.addHandler(fh)

    return run_id
