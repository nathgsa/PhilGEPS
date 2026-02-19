#!/usr/bin/env python3
"""
PhilGEPS Scraper Pipeline Runner

BUGS FIXED:
  BUG-PP-1  subprocess(['python','final_working_scraper.py']) fails inside a
            frozen .exe because no .py files exist.  Replaced with direct
            function calls: collect_detail_links() / parse_detail().
  BUG-PP-2  Path(__file__).parent resolves to PyInstaller's temp extraction dir,
            not the folder where the .exe lives.  Fixed with _get_base_path().
  BUG-PP-3  validate_environment() tried __import__('beautifulsoup4') — always
            ImportError because the package's importable name is 'bs4'.
  BUG-PP-4  venv_python hardcoded to 'venv/bin/python' — wrong on Windows
            where it is 'venv\\Scripts\\python.exe'.  Removed: subprocess
            approach is gone entirely so venv detection is no longer needed.
"""

import os
import sys
import logging
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
import json


# ── BUG-PP-2 FIX: stable base path ────────────────────────────────────────────
def _get_base_path() -> Path:
    """
    Return the directory that should be treated as the project root.

    • Running as a PyInstaller .exe  → directory of the .exe file
    • Running as a .py script        → directory of this file
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_PATH = _get_base_path()


# ── Logging ────────────────────────────────────────────────────────────────────
def setup_logging(log_level=logging.INFO, log_file=None):
    if log_file is None:
        log_dir = BASE_PATH / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"scraper_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(str(log_file)),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


# ── Pipeline ───────────────────────────────────────────────────────────────────
class ScraperPipeline:
    """Main pipeline orchestrator for PhilGEPS scraping and data cleaning."""

    def __init__(self, config=None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # BUG-PP-2 FIX: all paths anchored to BASE_PATH
        self.default_config = {
            'scraper_output':  str(BASE_PATH / 'output' / 'raw'     / 'philgeps_final_working.csv'),
            'cleaned_output':  str(BASE_PATH / 'output' / 'cleaned' / 'philgeps_final_working_cleaned.csv'),
            'scraper_limit':   0,
            'scraper_delay':   0.5,
            'run_scraper':     True,
            'run_cleaner':     True,
            'backup_original': True,
        }

        self._ensure_output_directories()
        self.config = {**self.default_config, **self.config}

    def _ensure_output_directories(self):
        for sub in ('raw', 'cleaned', 'merged', 'reports'):
            (BASE_PATH / 'output' / sub).mkdir(parents=True, exist_ok=True)
        (BASE_PATH / 'logs').mkdir(parents=True, exist_ok=True)

    # ── BUG-PP-3 FIX: correct import names ────────────────────────────────────
    def validate_environment(self) -> bool:
        self.logger.info("Validating environment...")

        # BUG-PP-3 FIX: map package display names to their actual import names
        pkg_map = {
            'playwright':    'playwright',
            'pandas':        'pandas',
            'beautifulsoup4':'bs4',       # ← correct import name
            'requests':      'requests',
            'customtkinter': 'customtkinter',
        }
        missing = []
        for display, import_name in pkg_map.items():
            try:
                __import__(import_name)
            except ImportError:
                missing.append(display)

        if missing:
            self.logger.warning(f"Missing packages: {missing}")
            self.logger.warning("Install with: pip install " + " ".join(missing))

        self.logger.info("Environment validation completed")
        return True

    # ── BUG-PP-1 FIX: direct function calls instead of subprocess ─────────────
    def run_scraper(self) -> bool:
        if not self.config['run_scraper']:
            self.logger.info("Skipping scraper (disabled in config)")
            return True

        self.logger.info("=" * 60)
        self.logger.info("STARTING PHILGEPS SCRAPER")
        self.logger.info("=" * 60)

        try:
            # BUG-PP-1 FIX: import functions directly — works in both .py and .exe
            from final_working_scraper import collect_detail_links, parse_detail, get_playwright_cookies

            output_path = Path(self.config['scraper_output'])
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self.logger.info("Collecting detail links…")
            detail_urls = collect_detail_links()

            limit = self.config.get('scraper_limit', 0)
            if limit and limit > 0:
                detail_urls = detail_urls[:limit]

            self.logger.info(f"Scraping {len(detail_urls)} detail pages…")
            rows  = []
            delay = float(self.config.get('scraper_delay', 0.5))

            for idx, url in enumerate(detail_urls, 1):
                try:
                    self.logger.info(f"  {idx}/{len(detail_urls)}: {url}")
                    row = parse_detail(url)
                    if row:
                        rows.append(row)
                except Exception as e:
                    self.logger.warning(f"  Failed to parse {url}: {e}")
                time.sleep(max(0.0, delay))

            if not rows:
                self.logger.error("No rows scraped.")
                return False

            # Deduplicate
            seen, deduped = set(), []
            for row in rows:
                rid = row.get('refID')
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                deduped.append(row)

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=deduped[0].keys())
                w.writeheader()
                w.writerows(deduped)

            self.logger.info(f"Scraper complete. {len(deduped)} rows → {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error running scraper: {e}")
            return False

    def run_cleaner(self) -> bool:
        if not self.config['run_cleaner']:
            self.logger.info("Skipping data cleaner (disabled in config)")
            return True

        self.logger.info("=" * 60)
        self.logger.info("STARTING DATA CLEANER")
        self.logger.info("=" * 60)

        try:
            input_path  = Path(self.config['scraper_output'])
            output_path = Path(self.config['cleaned_output'])

            if not input_path.exists():
                self.logger.error(f"Input file not found: {input_path}")
                return False

            if self.config['backup_original']:
                import shutil
                backup = input_path.parent / f"{input_path.stem}.backup.csv"
                shutil.copy2(input_path, backup)
                self.logger.info(f"Backup created: {backup}")

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Direct import (BUG-PP-1 FIX — no subprocess)
            from data_cleaner import PhilGEPSDataCleaner
            cleaner = PhilGEPSDataCleaner(str(input_path), str(output_path))
            cleaner.run_full_cleaning()

            self.logger.info(f"Cleaner complete. Output: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error running data cleaner: {e}")
            return False

    def generate_summary_report(self):
        self.logger.info("=" * 60)
        self.logger.info("PIPELINE EXECUTION SUMMARY")
        self.logger.info("=" * 60)

        for label, key in [("Scraper output", 'scraper_output'),
                            ("Cleaned output", 'cleaned_output')]:
            p = Path(self.config[key])
            if p.exists():
                self.logger.info(f"✓ {label}: {p} ({p.stat().st_size:,} bytes)")
            else:
                self.logger.warning(f"✗ {label} not found: {p}")

        try:
            import pandas as pd
            for label, key in [("Scraper", 'scraper_output'),
                                ("Cleaned", 'cleaned_output')]:
                p = Path(self.config[key])
                if p.exists():
                    self.logger.info(f"✓ {label} rows: {len(pd.read_csv(p))}")
        except Exception as e:
            self.logger.warning(f"Could not analyse CSV files: {e}")

        self.logger.info("=" * 60)

    def run_pipeline(self) -> bool:
        start = datetime.now()
        self.logger.info(f"Starting PhilGEPS Scraper Pipeline at {start}")
        try:
            self.validate_environment()
            if not self.run_scraper():
                self.logger.error("Pipeline failed at scraper stage")
                return False
            if not self.run_cleaner():
                self.logger.error("Pipeline failed at cleaner stage")
                return False
            self.generate_summary_report()
            self.logger.info(f"Pipeline completed in {datetime.now() - start}")
            return True
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            return False


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Run PhilGEPS Scraper Pipeline")
    parser.add_argument('--scraper-limit',   type=int,   default=0)
    parser.add_argument('--scraper-delay',   type=float, default=0.5)
    parser.add_argument('--scraper-output',  type=str,
                        default=str(BASE_PATH / 'output' / 'raw' / 'philgeps_final_working.csv'))
    parser.add_argument('--cleaned-output',  type=str,
                        default=str(BASE_PATH / 'output' / 'cleaned' / 'philgeps_final_working_cleaned.csv'))
    parser.add_argument('--skip-scraper',    action='store_true')
    parser.add_argument('--skip-cleaner',    action='store_true')
    parser.add_argument('--no-backup',       action='store_true')
    parser.add_argument('--log-level',       default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--log-file',        type=str, default=None)
    args = parser.parse_args()

    logger = setup_logging(getattr(logging, args.log_level.upper()), args.log_file)

    config = {
        'scraper_output':  args.scraper_output,
        'cleaned_output':  args.cleaned_output,
        'scraper_limit':   args.scraper_limit,
        'scraper_delay':   args.scraper_delay,
        'run_scraper':     not args.skip_scraper,
        'run_cleaner':     not args.skip_cleaner,
        'backup_original': not args.no_backup,
    }

    pipeline = ScraperPipeline(config)
    sys.exit(0 if pipeline.run_pipeline() else 1)


if __name__ == "__main__":
    main()
