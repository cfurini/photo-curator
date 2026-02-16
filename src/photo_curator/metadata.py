"""EXIF date extraction via exiftool subprocess (batch mode)."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from photo_curator.config import EXIF_DATE_FIELDS, EXIFTOOL_TIMEOUT
from photo_curator.models import FileRecord

logger = logging.getLogger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[tuple[str, str]]:
    """Parse 'YYYY:MM:DD HH:MM:SS' into (YYYY, MM) or None."""
    if not date_str:
        return None
    try:
        parts = date_str.split()[0].split(":")
        if len(parts) >= 2:
            year = parts[0]
            month = parts[1].zfill(2)
            if 1900 <= int(year) <= 2100 and 1 <= int(month) <= 12:
                return (year, month)
    except (ValueError, IndexError):
        pass
    return None


class MetadataExtractor:
    def __init__(self, batch_size: int = 500) -> None:
        self.batch_size = batch_size

    def enrich(
        self,
        media_files: list[FileRecord],
        sidecar_map: dict[Path, list[FileRecord]],
    ) -> list[FileRecord]:
        """Extract EXIF dates and return new FileRecords with year/month populated."""
        if not media_files:
            return []

        paths = [f.path for f in media_files]
        date_map = self._batch_extract_dates(paths)

        enriched: list[FileRecord] = []
        for record in media_files:
            date_str = date_map.get(str(record.path))
            date_tuple = parse_date(date_str)
            enriched.append(FileRecord(
                path=record.path,
                category=record.category,
                size=record.size,
                extension=record.extension,
                year=date_tuple[0] if date_tuple else None,
                month=date_tuple[1] if date_tuple else None,
            ))

        return enriched

    def _batch_extract_dates(
        self, file_paths: list[Path],
    ) -> dict[str, Optional[str]]:
        """Call exiftool in batches, return {path_str: date_str_or_None}."""
        result: dict[str, Optional[str]] = {}

        for i in range(0, len(file_paths), self.batch_size):
            batch = file_paths[i : i + self.batch_size]
            try:
                cmd = [
                    "exiftool",
                    "-json",
                    *[f"-{field}" for field in EXIF_DATE_FIELDS],
                    "-d", "%Y:%m:%d %H:%M:%S",
                    *[str(p) for p in batch],
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=EXIFTOOL_TIMEOUT,
                )
                if proc.returncode != 0 and not proc.stdout:
                    logger.warning(
                        f"exiftool batch {i // self.batch_size} failed: "
                        f"{proc.stderr[:200]}"
                    )
                    continue

                data = json.loads(proc.stdout)
                for item in data:
                    file_path = item.get("SourceFile", "")
                    date_str = None
                    for field in EXIF_DATE_FIELDS:
                        val = item.get(field)
                        if val and val != "0000:00:00 00:00:00":
                            date_str = val
                            break
                    result[file_path] = date_str

            except subprocess.TimeoutExpired:
                logger.warning(f"exiftool batch {i // self.batch_size} timed out")
            except json.JSONDecodeError as e:
                logger.warning(f"exiftool JSON parse error: {e}")
            except Exception as e:
                logger.warning(f"exiftool batch error: {e}")

        return result
