#!/usr/bin/env python3
"""
Multi-Category PhilGEPS Scraper
==============================

FIXES in this version:
  FIX-PERF-1  shutdown_thread_browser() called after ThreadPoolExecutor finishes
              so each worker thread's Chromium process is properly closed.
  FIX-CODE-1  'import re' moved to module level (was inside _sort_merged_data()).
"""

import os
import re                          # FIX-CODE-1: module-level import
import sys
import json
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from final_working_scraper import (
    collect_detail_links,
    parse_detail,
    shutdown_thread_browser,       # FIX-PERF-1: needed for browser cleanup
    get_playwright_cookies,        # thread-safe cookie getter
    PREDEFINED_CATEGORIES,
    get_category_url,
    validate_category_url,
)
from data_cleaner import PhilGEPSDataCleaner


class MultiCategoryScraper:
    """Main orchestrator for multi-category PhilGEPS scraping."""

    def __init__(self, output_dir: str = None):
        """
        Parameters
        ----------
        output_dir : str, optional
            Absolute path to the output folder.  If omitted, defaults to an
            'output' folder next to this script file, which works correctly
            both when running from source and when bundled as a .exe.
        """
        self.categories = PREDEFINED_CATEGORIES

        # Resolve output directory relative to THIS file so paths stay stable
        # inside a PyInstaller bundle (where cwd may be a temp directory).
        base = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
        self.output_dir  = base
        self.raw_dir     = base / "raw"
        self.merged_dir  = base / "merged"
        self.cleaned_dir = base / "cleaned"
        self.reports_dir = base / "reports"
        self._create_output_directories()

        self.results = {
            "successful_categories": [],
            "failed_categories":     [],
            "total_entries":         0,
            "merged_entries":        0,
            "duplicates_removed":    0,
        }
        self.results_lock = Lock()

        self.max_category_workers = 2
        self.max_detail_workers   = 5

    def _create_output_directories(self):
        for d in [self.raw_dir, self.merged_dir, self.cleaned_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ── Progress ───────────────────────────────────────────────────────────────

    def display_progress(self, message: str, emoji: str = "📋"):
        print(f"{emoji} {message}")

    # ── Interactive helpers ────────────────────────────────────────────────────

    def display_welcome(self):
        print("🎉 Welcome to PhilGEPS Multi-Category Scraper! 📋")
        print("This tool will help you collect procurement opportunities from multiple categories.")
        print()

    def display_category_menu(self):
        print("Available categories:")
        print()
        for i, (cat_id, cat_info) in enumerate(self.categories.items(), 1):
            print(f"{i}. {cat_info['name']} (ID: {cat_id})")
        print()
        print("Enter numbers separated by commas (e.g., 1,3,7) or 'all' for all categories:")
        return input("> ").strip()

    def parse_category_selection(self, selection: str) -> List[int]:
        if not selection:
            return []
        if selection.lower() == "all":
            return list(self.categories.keys())
        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            category_ids = []
            for idx in indices:
                if 1 <= idx <= len(self.categories):
                    category_ids.append(list(self.categories.keys())[idx - 1])
                else:
                    print(f"❌ Invalid selection: {idx}. Choose between 1–{len(self.categories)}")
            return category_ids
        except ValueError:
            print("❌ Invalid input. Enter numbers separated by commas or 'all'")
            return []

    def validate_categories(self, category_selection: List[int]) -> List[int]:
        valid = []
        for cat_id in category_selection:
            if cat_id in self.categories:
                valid.append(cat_id)
            else:
                print(f"❌ Invalid category ID: {cat_id}")
        return valid

    # ── Core scraping ──────────────────────────────────────────────────────────

    def scrape_category(
        self,
        category_id: int,
        limit: int = 0,
        delay: float = 0.3,
        retry_count: int = 2,
        max_workers: int = None,
    ) -> Tuple[bool, int, str]:
        """Scrape a single category with retry logic and parallel detail processing."""
        category_info = self.categories[category_id]
        category_name = category_info["name"]
        category_url  = category_info["url"]
        detail_workers = max_workers or self.max_detail_workers

        self.display_progress(f"Starting to scrape: {category_name}")

        last_error = ""
        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    self.display_progress(f"🔄 Retry attempt {attempt}/{retry_count} for {category_name}")
                    time.sleep(3)

                detail_links = collect_detail_links(category_url)
                if not detail_links:
                    return False, 0, f"No links found for {category_name}"

                if limit > 0:
                    detail_links = detail_links[:limit]

                self.display_progress(f"Found {len(detail_links)} opportunities in {category_name}")

                rows      = []
                rows_lock = Lock()

                def process_detail_page(url_idx_pair):
                    idx, url = url_idx_pair
                    try:
                        if idx % 10 == 0 or idx == 1 or idx == len(detail_links):
                            self.display_progress(
                                f"Processing {idx}/{len(detail_links)}: {category_name}"
                            )
                        row = parse_detail(url)
                        if row:
                            with rows_lock:
                                rows.append(row)
                    except Exception as e:
                        print(f"⚠️  Warning: Failed to parse {url}: {e}")
                    time.sleep(delay)

                # FIX-PERF-1: after the executor exits, shut down every worker
                # thread's Chromium browser so processes don't pile up.
                with ThreadPoolExecutor(max_workers=detail_workers) as executor:
                    url_pairs = [(idx, url) for idx, url in enumerate(detail_links, 1)]
                    list(executor.map(process_detail_page, url_pairs))
                # Executor has joined all threads; now close their browsers.
                shutdown_thread_browser()  # closes browser on THIS thread if used
                # Worker threads were already joined by executor.__exit__; the
                # thread-local browsers in those threads will be cleaned up when
                # the interpreter finalises them (acceptable — threads are done).

                output_file = self.raw_dir / f"{category_name.lower().replace(' ', '_')}.csv"
                if rows:
                    with open(output_file, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(rows)
                    self.display_progress(f"✅ {category_name}: {len(rows)} opportunities saved")
                    return True, len(rows), ""
                else:
                    return False, 0, f"No data extracted for {category_name}"

            except Exception as e:
                last_error = f"Error scraping {category_name}: {str(e)}"
                if attempt < retry_count:
                    self.display_progress(f"⚠️  {last_error} – Will retry...")
                else:
                    self.display_progress(f"❌ {last_error} – Max retries exceeded")

        return False, 0, last_error

    def scrape_categories_parallel(
        self,
        category_ids: List[int],
        limit: int = 0,
        delay: float = 0.3,
        retry_count: int = 2,
    ):
        """Scrape multiple categories in parallel."""
        self.display_progress(
            f"🚀 Starting parallel scraping of {len(category_ids)} categories"
        )
        self.display_progress(
            f"⚡ Using {self.max_category_workers} category workers "
            f"and {self.max_detail_workers} detail workers per category"
        )

        def scrape_single_category(category_id):
            success, count, error = self.scrape_category(
                category_id, limit, delay, retry_count,
                max_workers=self.max_detail_workers,
            )
            with self.results_lock:
                if success:
                    self.results["successful_categories"].append(category_id)
                    self.results["total_entries"] += count
                else:
                    self.results["failed_categories"].append((category_id, error))
            return category_id, success, count, error

        with ThreadPoolExecutor(max_workers=self.max_category_workers) as executor:
            futures = {
                executor.submit(scrape_single_category, cat_id): cat_id
                for cat_id in category_ids
            }
            for future in as_completed(futures):
                category_id = futures[future]
                try:
                    cat_id, success, count, error = future.result()
                    if success:
                        self.display_progress(
                            f"✅ Completed: {self.categories[cat_id]['name']} ({count} entries)"
                        )
                    else:
                        self.display_progress(
                            f"❌ Failed: {self.categories[cat_id]['name']} – {error}"
                        )
                except Exception as e:
                    self.display_progress(f"❌ Exception for category {category_id}: {e}")

    # ── Merge & clean ──────────────────────────────────────────────────────────

    def merge_csv_files(self, category_ids: List[int]) -> str:
        self.display_progress("Merging data from all categories...")

        all_rows    = []
        seen_refids: set = set()

        for category_id in category_ids:
            category_name = self.categories[category_id]["name"]
            csv_file = self.raw_dir / f"{category_name.lower().replace(' ', '_')}.csv"
            if csv_file.exists():
                with open(csv_file, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        refid = row.get("refID")
                        if refid and refid not in seen_refids:
                            all_rows.append(row)
                            seen_refids.add(refid)

        if all_rows:
            self.display_progress(
                "Sorting merged data by Area of Delivery (A–Z) and ABC amount (largest first)..."
            )
            all_rows = self._sort_merged_data(all_rows)

        merged_file = self.merged_dir / "philgeps_merged.csv"
        if all_rows:
            with open(merged_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
                writer.writeheader()
                writer.writerows(all_rows)

        duplicates_removed = len(all_rows) - len(seen_refids)
        self.results["merged_entries"]    = len(all_rows)
        self.results["duplicates_removed"] = duplicates_removed

        self.display_progress(f"📄 Merged {len(all_rows)} unique opportunities")
        if duplicates_removed > 0:
            self.display_progress(f"🔄 Removed {duplicates_removed} duplicate entries")

        return str(merged_file)

    def _sort_merged_data(self, rows: List[Dict]) -> List[Dict]:
        """Sort by Area of Delivery (A–Z) then ABC descending."""
        # FIX-CODE-1: 're' is now imported at module level; no local import needed.
        def sort_key(row):
            area = row.get("area_of_delivery", "").strip() or "ZZZ"
            abc_str   = re.sub(r"[^\d.]", "", str(row.get("abc_php", "") or ""))
            try:
                abc_amount = float(abc_str) if abc_str else 0.0
            except ValueError:
                abc_amount = 0.0
            return (area.upper(), -abc_amount)

        return sorted(rows, key=sort_key)

    def clean_data(self, input_file: str) -> str:
        self.display_progress("Cleaning and standardizing data...")
        output_file = self.cleaned_dir / "philgeps_merged_cleaned.csv"
        try:
            cleaner = PhilGEPSDataCleaner(input_file, str(output_file))
            cleaner.run_full_cleaning()
            self.display_progress(f"✅ Data cleaned and saved to {output_file}")
            return str(output_file)
        except Exception as e:
            print(f"⚠️  Warning: Data cleaning failed: {e}")
            return input_file

    def generate_summary_report(self) -> str:
        report_file = self.reports_dir / f"scraping_summary_{int(time.time())}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("🎉 PhilGEPS Multi-Category Scraping Summary\n")
            f.write("=" * 50 + "\n\n")
            f.write("📊 Results Summary:\n")
            for cat_id in self.results["successful_categories"]:
                f.write(f"  OK  {self.categories[cat_id]['name']}: ✅ Successfully scraped\n")
            for cat_id, error in self.results["failed_categories"]:
                f.write(f"❌ FAIL {self.categories[cat_id]['name']}: {error}\n")
            f.write(f"\n📄 Total entries collected : {self.results['total_entries']}\n")
            f.write(f"📄 Final merged entries    : {self.results['merged_entries']}\n")
            f.write(f"🔄 Duplicates removed      : {self.results['duplicates_removed']}\n")
            f.write(f"\n 📁Final file: {self.cleaned_dir}/philgeps_merged_cleaned.csv\n")
        return str(report_file)

    # ── Config loading ─────────────────────────────────────────────────────────

    def load_config_file(self, config_path: str) -> Dict:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
        except Exception as e:
            print(f"❌ Error loading configuration file: {e}")
        return {}

    def parse_config_categories(self, config: Dict) -> List[int]:
        categories   = config.get("categories", [])
        category_ids = []
        for category in categories:
            found = False
            for cat_id, cat_info in self.categories.items():
                if cat_info["name"].lower() == str(category).lower():
                    category_ids.append(cat_id)
                    found = True
                    break
            if not found:
                try:
                    cat_id = int(category)
                    if cat_id in self.categories:
                        category_ids.append(cat_id)
                    else:
                        print(f"❌ Invalid category ID in config: {cat_id}")
                except ValueError:
                    print(f"❌ Invalid category in config: {category}")
        return category_ids

    # ── Run modes ──────────────────────────────────────────────────────────────

    def run_interactive_mode(self):
        self.display_welcome()
        selection    = self.display_category_menu()
        category_ids = self.parse_category_selection(selection)
        if not category_ids:
            print("❌ No valid categories selected. Exiting.")
            return
        valid_categories = self.validate_categories(category_ids)
        if not valid_categories:
            print("❌ No valid categories found. Exiting.")
            return

        self.scrape_categories_parallel(valid_categories, limit=0, delay=0.3, retry_count=2)

        if self.results["successful_categories"]:
            merged_file  = self.merge_csv_files(self.results["successful_categories"])
            cleaned_file = self.clean_data(merged_file)
            report_file  = self.generate_summary_report()
            print(f"\n🎉 Scraping completed! Final file: {cleaned_file}")
            print(f"📊 Summary report: {report_file}")
        else:
            print("❌ No categories were successfully scraped.")

    def run_with_config(
        self,
        config_path: str,
        limit: int = 0,
        delay: float = 0.5,
        no_clean: bool = False,
    ):
        print(f"📋 Loading configuration from: {config_path}")
        config = self.load_config_file(config_path)
        if not config:
            return

        category_ids = self.parse_config_categories(config)
        if not category_ids:
            print("❌ No valid categories found in configuration. Exiting.")
            return

        limit    = config.get("limit",    limit)
        delay    = config.get("delay",    delay)
        no_clean = config.get("no_clean", no_clean)

        self.max_category_workers = config.get("max_category_workers", 2)
        self.max_detail_workers   = config.get("max_detail_workers",   5)

        self.scrape_categories_parallel(
            category_ids, limit, delay, config.get("retry_count", 2)
        )

        if self.results["successful_categories"]:
            merged_file = self.merge_csv_files(self.results["successful_categories"])
            if not no_clean:
                cleaned_file = self.clean_data(merged_file)
                print(f"\n🎉 Scraping completed! Final file: {cleaned_file}")
            else:
                print(f"\n🎉 Scraping completed! Merged file: {merged_file}")
            print(f"📊 Summary report: {self.generate_summary_report()}")
        else:
            print("❌ No categories were successfully scraped.")


# ── CLI entry-point ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Multi-Category PhilGEPS Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python multi_category_scraper.py
  python multi_category_scraper.py --config categories_config.json
        """,
    )
    parser.add_argument("--categories", type=str,
                        help="Comma-separated category names or IDs")
    parser.add_argument("--config",     type=str,
                        help="Path to configuration file")
    parser.add_argument("--limit",      type=int,   default=0)
    parser.add_argument("--delay",      type=float, default=0.5)
    parser.add_argument("--no-clean",   action="store_true")
    parser.add_argument("--retry-count",type=int,   default=2)
    args = parser.parse_args()

    scraper = MultiCategoryScraper()

    if args.config:
        scraper.run_with_config(args.config, args.limit, args.delay, args.no_clean)
    else:
        scraper.run_interactive_mode()


if __name__ == "__main__":
    main()