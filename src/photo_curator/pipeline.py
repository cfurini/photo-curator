"""Pipeline orchestrator: scan -> metadata -> match -> resolve -> execute."""

from __future__ import annotations

import logging
from pathlib import Path

from photo_curator.config import CuratorConfig
from photo_curator.manifest import ManifestWriter
from photo_curator.matching.registry import get_strategy
from photo_curator.metadata import MetadataExtractor
from photo_curator.models import PipelineResult
from photo_curator.mover import Mover
from photo_curator.resolver import Resolver
from photo_curator.scanner import Scanner

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the full photo curation run."""

    def __init__(self, config: CuratorConfig, run_id: str) -> None:
        self.config = config
        self.run_id = run_id
        self.scanner = Scanner(config)
        self.metadata = MetadataExtractor(batch_size=config.exiftool_batch_size)
        self.strategy = get_strategy(config.match_strategy)
        self.resolver = Resolver(config)
        self.manifest = ManifestWriter(run_id, config, config.log_dir)
        self.mover = Mover(config, manifest=self.manifest)

    def run(self) -> PipelineResult:
        result = PipelineResult(dry_run=self.config.dry_run)

        # Phase 1: Scan source directory
        logger.info("Phase 1/5: Scanning source directory...")
        media_files, sidecar_map = self.scanner.scan()
        result.files_scanned = len(media_files)
        logger.info(
            f"  Found {len(media_files)} media files, "
            f"{sum(len(v) for v in sidecar_map.values())} sidecars"
        )

        if not media_files:
            logger.info("No files to process.")
            result.manifest_path = self.manifest.finalize(result)
            return result

        # Phase 2: Extract EXIF metadata (dates)
        logger.info("Phase 2/5: Extracting metadata via exiftool...")
        file_records = self.metadata.enrich(media_files, sidecar_map)

        # Phase 3: Match against destination archive
        logger.info("Phase 3/5: Matching against destination archive...")
        dest_index = self.strategy.build_index(self.config.destination)
        match_results = self.strategy.match_all(file_records, dest_index)

        # Phase 4: Resolve conflicts (keep vs discard)
        logger.info("Phase 4/5: Resolving conflicts...")
        actions = self.resolver.resolve(match_results)

        # Attach sidecars to their parent actions
        for action in actions:
            sidecars = sidecar_map.get(action.source.path, [])
            action.sidecars = sidecars

        # Phase 5: Execute file operations
        logger.info("Phase 5/5: Executing file operations...")
        result = self.mover.execute(actions, result)

        # Write JSON manifest
        result.manifest_path = self.manifest.finalize(result)

        return result
