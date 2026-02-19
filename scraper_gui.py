#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhilGEPS Scraper — Professional GUI Application
================================================
Version 2.1.0

FEATURES & FIXES:
  1. Data Review: Now groups data by 'Category' first, ensuring scraped data
     from different categories stays organized together.
  2. MacOS Paths: Saves outputs to ~/Documents so users can find them.
  3. Windows Paths: Portable mode (saves next to .exe).
  4. Bundled Browser: Automatically detects Chromium bundled via PyInstaller.
"""

import sys
import os
import io as _io

# ─── 0. BUNDLED BROWSER CONFIGURATION (CRITICAL) ──────────────────────────────
# This block ensures Playwright finds the browser bundled inside the App/Exe.
if getattr(sys, 'frozen', False):
    # We are running as a compiled executable (PyInstaller)
    base_dir = sys._MEIPASS
    
    # This path matches where the .spec file puts the browser:
    # playwright/driver/package/.local-browsers
    bundled_browser_path = os.path.join(base_dir, "playwright", "driver", "package", ".local-browsers")
    
    # Force Playwright to use this internal path
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browser_path

# ─── WINDOWS CONSOLE FIX ──────────────────────────────────────────────────────
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                           errors='replace', line_buffering=True)
            sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8',
                                           errors='replace', line_buffering=True)
    except Exception:
        pass

import json
import threading
import queue
import math
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


# ─── 1. PATH CONFIGURATION (CROSS-PLATFORM FIX) ───────────────────────────────
def _get_base_path() -> Path:
    """
    Return the application's home directory.
    - Windows Frozen: Same folder as the .exe (Portable)
    - macOS Frozen:   ~/Documents/PhilGEPS_Scraper (Visible to user)
    - Python script:  Folder containing the script
    """
    if getattr(sys, 'frozen', False):
        # --- macOS Specific Logic ---
        if sys.platform == "darwin":
            # On macOS, the .app bundle is read-only or hidden.
            # We save to the user's Documents folder so they can access the CSVs.
            mac_docs_path = Path.home() / "Documents" / "PhilGEPS_Scraper"
            
            try:
                mac_docs_path.mkdir(parents=True, exist_ok=True)
            except Exception:
                # If Documents is restricted, fallback to Home
                return Path.home()
            return mac_docs_path
        
        # --- Windows Logic ---
        # Save next to the .exe
        return Path(sys.executable).parent
    
    # Development mode (running .py file)
    return Path(__file__).resolve().parent

BASE_PATH = _get_base_path()
CONFIG_FILE = str(BASE_PATH / "gui_config.json")


# ── GUI framework ──────────────────────────────────────────────────────────────
try:
    import customtkinter as ctk
    from tkinter import messagebox, filedialog
except ImportError:
    print("ERROR: CustomTkinter not installed. Run: pip install customtkinter")
    sys.exit(1)

# Pandas (optional — needed for Data Review tab)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None           # type: ignore
    HAS_PANDAS = False

# Scraper back-end
try:
    from multi_category_scraper import MultiCategoryScraper, PREDEFINED_CATEGORIES
except ImportError:
    PREDEFINED_CATEGORIES = {}

# ─── App constants ─────────────────────────────────────────────────────────────
APP_NAME    = "PhilGEPS ScraperV2"
APP_VERSION = "2.1.0"

DEFAULT_CONFIG: Dict = {
    "last_categories":       [],
    "limit":                 0,
    "delay":                 0.5,
    "retry_count":           2,
    "skip_cleaning":         False,
    "max_category_workers":  2,
    "max_detail_workers":    5,
    "output_dir":            str(BASE_PATH / "output"),
    "theme":                 "dark",
    "window_geometry":       "1200x850",
    "rows_per_page":         10,
}

COLOR_PALETTE = [
    ("#1f2b3e", "#293952"),
    ("#1f3326", "#2a4533"),
    ("#3e3222", "#52422d"),
    ("#2d223e", "#3c2d52"),
    ("#3e2222", "#522d2d"),
    ("#1f3333", "#2a4545"),
    ("#2b2b2b", "#383838"),
]

STATUS_COLORS = {
    "closed":    ("#2a1f1f", "#3a2a2a"),
    "expired":   ("#2a1f1f", "#3a2a2a"),
    "awarded":   ("#1f2a1f", "#2a3a2a"),
    "cancelled": ("#2e2a1a", "#3e3a2a"),
}

DESIRED_COLUMNS: List[str] = [
    "refid", "reference_number", "solicitation_number",
    "procuring_entity", "title", "category", "status",
    "procurement_mode", "classification",
    "abc_php", "area_of_delivery", "delivery_period",
    "date_published", "closing_datetime", "last_updated",
    "contact_person", "contact_position", "contact_address",
    "contact_email", "contact_phone",
]


# ─── Main application ──────────────────────────────────────────────────────────
class PhilGEPSScraperGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x850")
        self.minsize(950, 650)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = self.load_config()

        self.category_vars:   Dict                    = {}
        self.scraper_thread:  threading.Thread | None = None
        self.is_scraping:     bool                    = False
        self.progress_queue:  queue.Queue             = queue.Queue()
        self._stop_event:     threading.Event         = threading.Event()

        self.current_df             = None   # pd.DataFrame | None
        self.current_page:    int   = 0
        self.rows_per_page:   int   = self.config_data.get("rows_per_page", 10)
        self.total_pages:     int   = 0
        self.table_widgets:   List  = []
        self.header_widgets:  List  = []
        self.last_loaded_file       = None
        self.available_files: Dict[str, Path] = {}

        self.total_cats_selected:  int = 0
        self.cats_completed_count: int = 0

        self.setup_ui()
        self.load_saved_settings()
        self.check_progress_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Background startup check
        threading.Thread(target=self._check_playwright_async, daemon=True).start()

    # ── Playwright Checks ─────────────────────────────────────────────────────
    def _check_playwright(self) -> bool:
        """Return True if Playwright + Chromium are usable."""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            return True
        except Exception:
            return False

    def _check_playwright_async(self):
        if self._check_playwright():
            return   # all good

        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            msg = (
                "The bundled Chromium browser could not start.\n\n"
                "This might be an antivirus issue or a macOS quarantine issue.\n"
                "If on macOS, ensure you ran: xattr -cr 'App Name.app'"
            )
        else:
            msg = (
                "Chromium browser is not installed.\n"
                "Run: playwright install chromium"
            )
        self.after(0, lambda: messagebox.showwarning("Browser Not Ready", msg))

    # ── UI construction ────────────────────────────────────────────────────────
    def setup_ui(self):
        self.tabview = ctk.CTkTabview(self, width=1100, height=800)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)
        self.tab_scraper = self.tabview.add("Scraper Dashboard")
        self.tab_config  = self.tabview.add("Configuration")
        self.tab_about   = self.tabview.add("About")
        self.setup_scraper_tab()
        self.setup_config_tab()
        self.setup_about_tab()

    def setup_scraper_tab(self):
        left = ctk.CTkFrame(self.tab_scraper, width=300)
        left.pack(side="left", fill="y", expand=False, padx=10, pady=10)

        ctk.CTkLabel(left, text="Category Selection",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 10))

        cat_scroll = ctk.CTkScrollableFrame(left, width=280, height=300)
        cat_scroll.pack(pady=5, padx=10, fill="both", expand=True)

        for cat_id, cat_info in PREDEFINED_CATEGORIES.items():
            var = ctk.BooleanVar()
            self.category_vars[cat_id] = var
            ctk.CTkCheckBox(cat_scroll,
                            text=f"{cat_info['name']} ({cat_id})",
                            variable=var,
                            font=ctk.CTkFont(size=12)).pack(anchor="w", pady=5, padx=5)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(pady=5)
        ctk.CTkButton(btn_row, text="Select All", width=120,
                      command=self.select_all_categories).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Clear All",  width=120,
                      command=self.clear_all_categories).pack(side="left", padx=5)

        ctk.CTkLabel(left, text="Quick Settings",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        self._input_row(left, "Limit per Category (0=All):", "limit_entry",  80)
        self._input_row(left, "Delay (sec):",               "delay_entry",  80)

        self.skip_cleaning_var = ctk.BooleanVar()
        ctk.CTkCheckBox(left, text="Skip Data Cleaning",
                        variable=self.skip_cleaning_var).pack(pady=10)

        self.start_button = ctk.CTkButton(
            left, text="START SCRAPING", height=40,
            fg_color="green", hover_color="darkgreen",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_scraping,
        )
        self.start_button.pack(pady=(10, 5), padx=20, fill="x")

        self.stop_button = ctk.CTkButton(
            left, text="STOP", height=30,
            fg_color="darkred", hover_color="red",
            state="disabled", command=self.stop_scraping,
        )
        self.stop_button.pack(pady=(0, 20), padx=20, fill="x")

        right = ctk.CTkFrame(self.tab_scraper)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        prog = ctk.CTkFrame(right, fg_color="transparent")
        prog.pack(fill="x", padx=10, pady=(10, 5))
        self.status_label = ctk.CTkLabel(prog, text="Status: Ready", anchor="w",
                                          font=ctk.CTkFont(weight="bold"))
        self.status_label.pack(fill="x")
        self.progress_bar = ctk.CTkProgressBar(prog)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0)
        self.progress_info = ctk.CTkLabel(prog, text="0 / 0 Categories Completed",
                                           font=ctk.CTkFont(size=11))
        self.progress_info.pack(anchor="e")

        self.log_view    = ctk.CTkTabview(right)
        self.log_view.pack(fill="both", expand=True, padx=5, pady=5)
        self.tab_logs    = self.log_view.add("Live Logs")
        self.log_text    = ctk.CTkTextbox(self.tab_logs, font=("Consolas", 12))
        self.log_text.pack(fill="both", expand=True)
        self.tab_preview = self.log_view.add("Data Review")
        self._build_data_review_panel()

    def _build_data_review_panel(self):
        toolbar1 = ctk.CTkFrame(self.tab_preview, fg_color="transparent")
        toolbar1.pack(fill="x", pady=(5, 0), padx=5)

        ctk.CTkLabel(toolbar1, text="File:").pack(side="left", padx=(0, 4))
        self.file_selector_var = ctk.StringVar(value="Auto (best available)")
        self.file_selector = ctk.CTkComboBox(
            toolbar1, variable=self.file_selector_var,
            values=["Auto (best available)"], width=280,
            command=self._on_file_selected,
        )
        self.file_selector.pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar1, text="⟳ Refresh", width=80,
                      command=self.load_data_preview).pack(side="left", padx=4)
        self.btn_open_file = ctk.CTkButton(
            toolbar1, text="Open in App", width=100,
            fg_color="#2d4a2d", hover_color="#3a6e3a",
            command=self._open_current_file, state="disabled",
        )
        self.btn_open_file.pack(side="left", padx=4)
        ctk.CTkLabel(toolbar1, text="Rows/page:").pack(side="right", padx=(8, 2))
        self.rows_per_page_var = ctk.StringVar(value=str(self.rows_per_page))
        ctk.CTkComboBox(toolbar1, variable=self.rows_per_page_var,
                        values=["5", "10", "25", "50"], width=60,
                        command=self._on_rows_per_page_changed).pack(side="right", padx=(0, 4))

        toolbar2 = ctk.CTkFrame(self.tab_preview, fg_color="transparent")
        toolbar2.pack(fill="x", pady=(2, 4), padx=5)
        self.table_info_lbl = ctk.CTkLabel(toolbar2, text="No file loaded.",
                                            text_color="gray", anchor="w")
        self.table_info_lbl.pack(side="left", fill="x")

        self.table_wrapper = ctk.CTkScrollableFrame(
            self.tab_preview, orientation="horizontal", label_text="Data Grid")
        self.table_wrapper.pack(fill="both", expand=True, padx=5)
        self.header_frame = ctk.CTkFrame(self.table_wrapper, fg_color="transparent")
        self.header_frame.pack(fill="x", side="top", anchor="n")
        self.table_scroll = ctk.CTkScrollableFrame(
            self.table_wrapper, orientation="vertical",
            fg_color="transparent", height=400)
        self.table_scroll.pack(fill="both", expand=True, side="top")

        pager = ctk.CTkFrame(self.tab_preview, height=40, fg_color="transparent")
        pager.pack(fill="x", pady=5, padx=5)
        self.btn_prev = ctk.CTkButton(pager, text="< Prev", width=75,
                                       command=lambda: self.change_page(-1), state="disabled")
        self.btn_prev.pack(side="left", padx=(0, 6))
        self.lbl_page = ctk.CTkLabel(pager, text="Page 0 of 0",
                                      font=ctk.CTkFont(weight="bold"))
        self.lbl_page.pack(side="left", padx=4)
        self.btn_next = ctk.CTkButton(pager, text="Next >", width=75,
                                       command=lambda: self.change_page(1), state="disabled")
        self.btn_next.pack(side="left", padx=6)
        ctk.CTkButton(pager, text="Clear", width=70,
                      fg_color="#5a2020", hover_color="#7a2020",
                      command=self.clear_data_view).pack(side="right", padx=4)

    def _input_row(self, parent, label: str, attr: str, width: int):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(row, width=width)
        entry.pack(side="right")
        setattr(self, attr, entry)

    # ── Configuration tab ──────────────────────────────────────────────────────

    def setup_config_tab(self):
        main = ctk.CTkFrame(self.tab_config)
        main.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(main, text="Advanced Configuration",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(10, 20))

        grid = ctk.CTkFrame(main)
        grid.pack(pady=10, padx=20, fill="x")

        def add_row(r, label, placeholder):
            ctk.CTkLabel(grid, text=label, anchor="w").grid(
                row=r, column=0, padx=20, pady=10, sticky="w")
            e = ctk.CTkEntry(grid, width=200, placeholder_text=placeholder)
            e.grid(row=r, column=1, padx=20, pady=10)
            return e

        self.retry_entry          = add_row(0, "Retry Count:",          "2")
        self.cat_workers_entry    = add_row(1, "Max Category Workers:", "2")
        self.detail_workers_entry = add_row(2, "Max Detail Workers:",   "5")

        ctk.CTkLabel(grid, text="Theme:", anchor="w").grid(
            row=3, column=0, padx=20, pady=10, sticky="w")
        self.theme_var = ctk.StringVar(value="dark")
        ctk.CTkOptionMenu(grid, values=["dark", "light"],
                          variable=self.theme_var,
                          command=lambda t: ctk.set_appearance_mode(t)
                          ).grid(row=3, column=1, padx=20, pady=10)

        ctk.CTkButton(main, text="Reset to Defaults",
                      command=self.reset_to_defaults).pack(pady=20)

        tips = ctk.CTkTextbox(main, width=600, height=150)
        tips.pack(pady=10, padx=20)
        tips.insert("1.0", (
            "Configuration Tips:\n\n"
            "• Retry Count: Times to retry failed categories (recommended: 2–3)\n"
            "• Max Category Workers: Parallel categories (recommended: 2)\n"
            "• Max Detail Workers: Parallel detail pages per category (recommended: 5)\n"
            "• Lower delays = faster scraping but higher risk of rate-limiting\n"
            "• Skip Data Cleaning: shows raw scraped data without formatting fixes\n"
        ))
        tips.configure(state="disabled")

    # ── About tab ─────────────────────────────────────────────────────────────

    def setup_about_tab(self):
        main = ctk.CTkFrame(self.tab_about)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text=APP_NAME,
                     font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30, 10))
        ctk.CTkLabel(main, text=f"Version {APP_VERSION}",
                     font=ctk.CTkFont(size=14)).pack(pady=5)

        desc = ctk.CTkTextbox(main, width=700, height=250)
        desc.pack(pady=20, padx=40)
        desc.insert("1.0", (
            f"About {APP_NAME}\n\n"
            "Features:\n"
            "• Multi-category scraping with parallel processing\n"
            "• Real-time progress monitoring with colour-coded log levels\n"
            "• Automatic data cleaning and standardisation\n"
            "• Cross-platform support (Windows & macOS)\n\n"
            "For documentation, see README.md in the project folder.\n\n"
            "© 2026 - Optima Typographics. All rights reserved.\n"
        ))
        desc.configure(state="disabled")

        ctk.CTkButton(main, text="System Information",
                      width=200, command=self.show_system_info).pack(pady=10)
        ctk.CTkButton(main, text="Run Connection Diagnostics",
                      width=200, command=self.run_diagnostics).pack(pady=10)

    # ── Data Review file management ────────────────────────────────────────────

    def _scan_available_files(self) -> Dict[str, Path]:
        out = Path(self.config_data.get("output_dir", str(BASE_PATH / "output")))
        files: Dict[str, Path] = {}

        cleaned = out / "cleaned" / "philgeps_merged_cleaned.csv"
        if cleaned.exists() and cleaned.stat().st_size > 0:
            files["✅ Cleaned (philgeps_merged_cleaned.csv)"] = cleaned

        merged = out / "merged" / "philgeps_merged.csv"
        if merged.exists() and merged.stat().st_size > 0:
            files["📄 Merged (philgeps_merged.csv)"] = merged

        raw = out / "raw"
        if raw.exists():
            for p in sorted(raw.glob("*.csv")):
                if p.stat().st_size > 0:
                    files[f"📁 Raw: {p.name}"] = p

        return files

    def _refresh_file_selector(self):
        self.available_files = self._scan_available_files()
        labels = ["Auto (best available)"] + list(self.available_files.keys())
        self.file_selector.configure(values=labels)
        if self.file_selector_var.get() not in labels:
            self.file_selector_var.set("Auto (best available)")

    def _resolve_target_file(self):
        sel = self.file_selector_var.get()
        if sel == "Auto (best available)":
            for p in self.available_files.values():
                return p
            return None
        return self.available_files.get(sel)

    def _on_file_selected(self, _selection: str):
        self.last_loaded_file = None
        self.load_data_preview()

    def _on_rows_per_page_changed(self, value: str):
        try:
            self.rows_per_page = int(value)
        except ValueError:
            self.rows_per_page = 10
        if self.current_df is not None:
            self.total_pages  = max(1, math.ceil(len(self.current_df) / self.rows_per_page))
            self.current_page = 0
            self.render_table()

    def _open_current_file(self):
        if not self.last_loaded_file:
            return
        path = Path(self.last_loaded_file)
        if not path.exists():
            messagebox.showwarning("Not Found", f"File no longer exists:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open Failed", str(exc))

    # ── Data Review load & render ──────────────────────────────────────────────

    def load_data_preview(self):
        if not HAS_PANDAS:
            self.table_info_lbl.configure(text="Pandas not installed — run: pip install pandas")
            return

        self.table_info_lbl.configure(text="Scanning for data…")
        self.update_idletasks()
        self._refresh_file_selector()
        target = self._resolve_target_file()

        if not target:
            self.table_info_lbl.configure(text="No CSV data found. Run the scraper first.")
            self.btn_open_file.configure(state="disabled")
            return

        try:
            self.current_df = pd.read_csv(target)
            if self.last_loaded_file != str(target):
                self.current_page     = 0
                self.last_loaded_file = str(target)
                self.btn_open_file.configure(state="normal")
                self._apply_scraper_sort()

            total_rows       = len(self.current_df)
            self.total_pages = max(1, math.ceil(total_rows / self.rows_per_page))
            if self.current_page >= self.total_pages:
                self.current_page = 0

            self.table_info_lbl.configure(
                text=(f"Loaded: {target.name}  "
                      f"({total_rows:,} records) — Grouped by Category")
            )
            self.render_table()
        except Exception as exc:
            self.table_info_lbl.configure(text=f"Error reading file: {exc}")

    # ── KEY SORT LOGIC (Category -> Area -> ABC) ──────────────────────────────
    def _apply_scraper_sort(self):
        if self.current_df is None or self.current_df.empty:
            return
        
        import re as _re

        def area_key(val):
            s = str(val).strip() if pd.notna(val) else ""
            return "ZZZ" + s if not s else s.upper()

        def abc_key(val):
            if pd.isna(val): return 0.0
            txt = _re.sub(r"[^\d.]", "", str(val))
            try:
                # Negative float allows descending sort (High to Low) via ascending=True
                return -float(txt) if txt else 0.0
            except ValueError:
                return 0.0

        df = self.current_df.copy()

        # Identify columns case-insensitively
        cat_col  = next((c for c in df.columns if "category" in c.lower()), None)
        area_col = next((c for c in df.columns if "area" in c.lower()), None)
        abc_col  = next((c for c in df.columns if "abc" in c.lower()), None)

        sort_cols = []
        
        # 1. Primary Sort: Category (Groups data together)
        if cat_col:
            sort_cols.append(cat_col)
        
        # 2. Secondary Sort: Area (Alphabetical)
        if area_col:
            df["_area_key"] = df[area_col].map(area_key)
            sort_cols.append("_area_key")
            
        # 3. Tertiary Sort: ABC (Budget - High to Low)
        if abc_col:
            df["_abc_key"] = df[abc_col].map(abc_key)
            sort_cols.append("_abc_key")
            
        if sort_cols:
            df = df.sort_values(by=sort_cols, ascending=[True]*len(sort_cols))
            
            # Cleanup temp cols
            drops = [c for c in ["_area_key", "_abc_key"] if c in df.columns]
            if drops:
                df = df.drop(columns=drops)
            
            self.current_df = df

    def render_table(self):
        for w in self.table_widgets:  w.destroy()
        self.table_widgets.clear()
        for w in self.header_widgets: w.destroy()
        self.header_widgets.clear()

        if self.current_df is None or self.current_df.empty:
            return

        actual_cols = list(self.current_df.columns)
        cols: List[str] = []
        for desired in DESIRED_COLUMNS:
            for actual in actual_cols:
                if desired in actual.lower() and actual not in cols:
                    cols.append(actual)
                    break
        if not cols:
            cols = actual_cols[:8]

        def col_width(c: str) -> int:
            cl = c.lower()
            if "title"          in cl: return 300
            if "entity"         in cl: return 220
            if "email"          in cl: return 200
            if "address"        in cl: return 200
            if "position"       in cl: return 180
            if "person"         in cl: return 170
            if "area"           in cl: return 180
            if "mode"           in cl: return 180
            if "classification" in cl: return 160
            if "solicitation"   in cl: return 150
            if "delivery"       in cl: return 150
            if "status"         in cl: return 120
            if "phone"          in cl: return 140
            if "ref"            in cl: return 130
            if "abc"            in cl: return 150
            if "date"           in cl or "datetime" in cl: return 160
            if "updated"        in cl: return 160
            if "category"       in cl: return 180
            return 150

        widths  = {c: col_width(c) for c in cols}
        total_w = sum(widths.values()) + len(widths) * 10
        self.header_frame.configure(width=total_w)
        self.table_scroll.configure(width=total_w)

        for i, col in enumerate(cols):
            e = ctk.CTkEntry(self.header_frame, width=widths[col],
                             font=("Arial", 12, "bold"),
                             fg_color="#2b2b2b", border_color="#3a3a3a",
                             text_color="#e0e0e0")
            e.insert(0, col.upper().replace("_", " "))
            e.configure(state="readonly")
            e.grid(row=0, column=i, padx=1, pady=1, sticky="ew")
            self.header_widgets.append(e)

        color_map: Dict[str, tuple] = {}
        if "category" in self.current_df.columns:
            for idx, cat in enumerate(self.current_df["category"].unique()):
                color_map[str(cat)] = COLOR_PALETTE[idx % len(COLOR_PALETTE)]

        status_col = next((c for c in cols if "status" in c.lower()), None)
        start      = self.current_page * self.rows_per_page
        page_df    = self.current_df.iloc[start : start + self.rows_per_page]

        for r_idx, (_, row) in enumerate(page_df.iterrows()):
            bg = self._row_bg_color(row, cols, color_map, status_col, r_idx)
            for c_idx, col in enumerate(cols):
                raw_val = row.get(col)
                val = str(raw_val) if pd.notna(raw_val) else ""
                if "abc" in col.lower() or "budget" in col.lower():
                    val = self._format_currency(val)
                tb = ctk.CTkTextbox(self.table_scroll, width=widths[col], height=70,
                                    wrap="word", font=("Arial", 13),
                                    fg_color=bg, text_color="#e0e0e0")
                tb.insert("0.0", val)
                tb.configure(state="disabled")
                tb.grid(row=r_idx, column=c_idx, padx=1, pady=1, sticky="nsew")
                self.table_widgets.append(tb)

        self.lbl_page.configure(text=f"Page {self.current_page + 1} of {self.total_pages}")
        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self.current_page + 1 < self.total_pages else "disabled")

    # ── Row colour helpers ─────────────────────────────────────────────────────

    def _row_bg_color(self, row, cols, color_map, status_col, r_idx: int) -> str:
        if status_col:
            sv = str(row.get(status_col, "")).strip().lower()
            for kw, pair in STATUS_COLORS.items():
                if kw in sv:
                    return pair[0] if r_idx % 2 == 0 else pair[1]
        cat_val = None
        for c in cols:
            if "category" in c.lower():
                cat_val = str(row.get(c, ""))
                break
        pair = color_map.get(cat_val or "", COLOR_PALETTE[0])
        return pair[0] if r_idx % 2 == 0 else pair[1]

    @staticmethod
    def _format_currency(val: str) -> str:
        try:
            cleaned = val.replace("₱","").replace("PHP","").replace("$","").replace(",","").strip()
            return "{:,.2f}".format(float(cleaned))
        except (ValueError, TypeError):
            return val

    def change_page(self, delta: int):
        new = self.current_page + delta
        if 0 <= new < self.total_pages:
            self.current_page = new
            self.render_table()

    def clear_data_view(self):
        self.current_df = None
        self.current_page = self.total_pages = 0
        self.last_loaded_file = None
        for w in self.table_widgets:  w.destroy()
        self.table_widgets.clear()
        for w in self.header_widgets: w.destroy()
        self.header_widgets.clear()
        self.table_info_lbl.configure(text="Data cleared.")
        self.lbl_page.configure(text="Page 0 of 0")
        self.btn_prev.configure(state="disabled")
        self.btn_next.configure(state="disabled")
        self.btn_open_file.configure(state="disabled")

    # ── Scraping orchestration ─────────────────────────────────────────────────

    def start_scraping(self):
        selected = [cid for cid, var in self.category_vars.items() if var.get()]
        if not selected:
            messagebox.showerror("Error", "Select at least one category.")
            return

        self.total_cats_selected  = len(selected)
        self.cats_completed_count = 0
        self._stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.is_scraping = True
        self.log_text.delete("1.0", "end")
        self.log_message(f"Starting scraping for {self.total_cats_selected} categories…", "info")
        self.progress_bar.set(0)
        self.progress_info.configure(text=f"0 / {self.total_cats_selected} Categories Completed")
        self.log_view.set("Live Logs")

        limit          = int(self.limit_entry.get()          or 0)
        delay          = float(self.delay_entry.get()        or 0.5)
        retry          = int(self.retry_entry.get()          or 2)
        cat_workers    = int(self.cat_workers_entry.get()    or 2)
        detail_workers = int(self.detail_workers_entry.get() or 5)

        self.scraper_thread = threading.Thread(
            target=self._scraper_worker,
            args=(selected, limit, delay, retry, cat_workers, detail_workers),
            daemon=True,
        )
        self.scraper_thread.start()

    def _scraper_worker(self, categories, limit, delay, retry, cat_workers, detail_workers):
        try:
            scraper = MultiCategoryScraper()
            scraper.max_category_workers = cat_workers
            scraper.max_detail_workers   = detail_workers

            # BUG-GUI-2 FIX: pass output_dir from config to the scraper
            output_dir = self.config_data.get("output_dir", str(BASE_PATH / "output"))
            scraper.output_dir  = Path(output_dir)
            scraper.raw_dir     = scraper.output_dir / "raw"
            scraper.merged_dir  = scraper.output_dir / "merged"
            scraper.cleaned_dir = scraper.output_dir / "cleaned"
            scraper.reports_dir = scraper.output_dir / "reports"
            scraper._create_output_directories()

            def on_progress(msg, emoji=""):
                if self._stop_event.is_set():
                    raise SystemExit("Stopped by user")
                full  = f"{emoji} {msg}".strip()
                level = (
                    "success" if any(x in full for x in ("✅","Completed:","saved")) else
                    "error"   if any(x in full for x in ("❌","Failed:","Error"))    else
                    "warning" if any(x in full for x in ("⚠️","Warning:","🔄","Retry")) else
                    "info"
                )
                self.progress_queue.put(("log", full, level))
                if "Completed:" in full or "Failed:" in full:
                    self.progress_queue.put(("cat_complete",))

            scraper.display_progress = on_progress
            self.progress_queue.put(("status", "Scraping…"))
            scraper.scrape_categories_parallel(categories, limit, delay, retry)

            if self._stop_event.is_set():
                return

            if scraper.results["successful_categories"]:
                self.progress_queue.put(("status", "Merging…"))
                merged = scraper.merge_csv_files(scraper.results["successful_categories"])
                if not self.skip_cleaning_var.get():
                    self.progress_queue.put(("status", "Cleaning…"))
                    scraper.clean_data(merged)
                scraper.generate_summary_report()
                self.progress_queue.put(("log",     "All tasks finished.", "success"))
                self.progress_queue.put(("progress", 1.0))
                self.progress_queue.put(("refresh_table",))
            else:
                self.progress_queue.put(("log", "No data retrieved.", "error"))

        except SystemExit:
            self.progress_queue.put(("log", "Stopped by user.", "warning"))
        except Exception as exc:
            self.progress_queue.put(("log", f"CRITICAL ERROR: {exc}", "error"))
        finally:
            self.progress_queue.put(("finished",))

    def stop_scraping(self):
        if not self.is_scraping:
            return
        if not messagebox.askyesno("Stop", "Stop scraping after the current operation completes?"):
            return
        self._stop_event.set()
        self.is_scraping = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Status: Stopping…")
        self.log_message("Stop requested — finishing current operation…", "warning")

    def check_progress_queue(self):
        try:
            while True:
                msg   = self.progress_queue.get_nowait()
                type_ = msg[0]
                if type_ == "log":
                    self.log_message(msg[1], msg[2])
                elif type_ == "status":
                    self.status_label.configure(text=f"Status: {msg[1]}")
                elif type_ == "progress":
                    self.progress_bar.set(msg[1])
                elif type_ == "cat_complete":
                    self.cats_completed_count += 1
                    if self.total_cats_selected > 0:
                        pct = self.cats_completed_count / self.total_cats_selected
                        self.progress_bar.set(pct)
                        self.progress_info.configure(
                            text=f"{self.cats_completed_count} / {self.total_cats_selected} Categories Completed")
                elif type_ == "refresh_table":
                    self.load_data_preview()
                    self.log_view.set("Data Review")
                elif type_ == "finished":
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.is_scraping = False
                    if not self._stop_event.is_set():
                        self.status_label.configure(text="Status: Done")
        except queue.Empty:
            pass
        self.after(100, self.check_progress_queue)

    # ── Category helpers ───────────────────────────────────────────────────────

    def select_all_categories(self):
        for v in self.category_vars.values(): v.set(True)

    def clear_all_categories(self):
        for v in self.category_vars.values(): v.set(False)

    # ── Logging ────────────────────────────────────────────────────────────────

    def log_message(self, message: str, level: str = "info"):
        ts     = datetime.now().strftime("%H:%M:%S")
        colors = {"info": "white", "success": "#4ade80",
                  "warning": "orange", "error": "#f87171"}
        self.log_text.insert("end", f"[{ts}] {message}\n")
        line = self.log_text.index("end-1c").split(".")[0]
        self.log_text.tag_add(level, f"{line}.0", f"{line}.end")
        self.log_text.tag_config(level, foreground=colors.get(level, "white"))
        self.log_text.see("end")

    # ── Diagnostics ────────────────────────────────────────────────────────────

    def show_system_info(self):
        lines = [f"OS:     {sys.platform}", f"Python: {sys.version.split()[0]}", ""]
        pkg_map = {
            "customtkinter":        "customtkinter",
            "playwright":           "playwright",
            "pandas":               "pandas",
            "requests":             "requests",
            "beautifulsoup4 (bs4)": "bs4",
        }
        for display_name, import_name in pkg_map.items():
            try:
                mod = __import__(import_name)
                ver = getattr(mod, "__version__", "installed")
                lines.append(f"✓ {display_name}: {ver}")
            except ImportError:
                lines.append(f"✗ {display_name}: MISSING")

        dlg = ctk.CTkToplevel(self)
        dlg.title("System Information")
        dlg.geometry("420x320")
        dlg.lift()
        tb = ctk.CTkTextbox(dlg, width=400, height=300)
        tb.pack(padx=10, pady=10)
        tb.insert("1.0", "\n".join(lines))
        tb.configure(state="disabled")

    # ── BUG-GUI-3 FIX: call run() directly — no subprocess ────────────────────
    def run_diagnostics(self):
        """
        Run the connection diagnostic and show results in a dialog.
        """
        self.log_message("Running connection diagnostics…", "info")

        def _worker():
            try:
                from test_philgeps_connection import run as diag_run
                output_text, all_passed = diag_run()
            except Exception as exc:
                output_text = f"Diagnostics failed to run:\n{exc}"
                all_passed  = False

            self.after(0, lambda: self._show_diagnostics_result(output_text, all_passed))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_diagnostics_result(self, output_text: str, all_passed: bool):
        """Display diagnostics output in a scrollable dialog."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Connection Diagnostics")
        dlg.geometry("700x550")
        dlg.lift()

        header_color = "#1f3326" if all_passed else "#3e2222"
        header_text  = "✅ All tests passed!" if all_passed else "⚠️  Some tests failed. See details below."
        ctk.CTkLabel(dlg, text=header_text,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     fg_color=header_color, corner_radius=6,
                     ).pack(fill="x", padx=10, pady=(10, 0))

        tb = ctk.CTkTextbox(dlg, font=("Consolas", 11), wrap="none")
        tb.pack(fill="both", expand=True, padx=10, pady=10)
        tb.insert("1.0", output_text)
        tb.configure(state="disabled")

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 10))
        self.log_message(
            "Diagnostics complete — " + ("all passed" if all_passed else "some tests failed"),
            "success" if all_passed else "warning",
        )

    # ── Config persistence ─────────────────────────────────────────────────────

    def load_config(self) -> Dict:
        if Path(CONFIG_FILE).exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    return {**DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def load_saved_settings(self):
        cd = self.config_data
        self.limit_entry.insert(0,          str(cd.get("limit",                0)))
        self.delay_entry.insert(0,          str(cd.get("delay",              0.5)))
        self.skip_cleaning_var.set(              cd.get("skip_cleaning",    False))
        self.retry_entry.insert(0,          str(cd.get("retry_count",           2)))
        self.cat_workers_entry.insert(0,    str(cd.get("max_category_workers",  2)))
        self.detail_workers_entry.insert(0, str(cd.get("max_detail_workers",    5)))
        theme = cd.get("theme", "dark")
        ctk.set_appearance_mode(theme)
        self.theme_var.set(theme)
        rpp = str(cd.get("rows_per_page", 10))
        self.rows_per_page_var.set(rpp)
        self.rows_per_page = int(rpp)
        for cat_id in cd.get("last_categories", []):
            if cat_id in self.category_vars:
                self.category_vars[cat_id].set(True)

    def reset_to_defaults(self):
        if not messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            return
        self.clear_all_categories()
        for attr, val in [("limit_entry","0"),("delay_entry","0.5"),
                          ("retry_entry","2"),("cat_workers_entry","2"),
                          ("detail_workers_entry","5")]:
            w = getattr(self, attr)
            w.delete(0, "end")
            w.insert(0, val)
        self.skip_cleaning_var.set(False)
        self.rows_per_page_var.set("10")
        self.rows_per_page = 10

    def on_closing(self):
        if self.is_scraping:
            if not messagebox.askyesno("Exit", "Scraping is running. Exit anyway?"):
                return
        cd = self.config_data
        cd["limit"]                = int(self.limit_entry.get()          or 0)
        cd["delay"]                = float(self.delay_entry.get()        or 0.5)
        cd["skip_cleaning"]        = self.skip_cleaning_var.get()
        cd["retry_count"]          = int(self.retry_entry.get()          or 2)
        cd["max_category_workers"] = int(self.cat_workers_entry.get()    or 2)
        cd["max_detail_workers"]   = int(self.detail_workers_entry.get() or 5)
        cd["theme"]                = self.theme_var.get()
        cd["rows_per_page"]        = self.rows_per_page
        cd["last_categories"]      = [k for k, v in self.category_vars.items() if v.get()]
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(cd, f, indent=2)
        except Exception:
            pass
        self.destroy()


# ─── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = PhilGEPSScraperGUI()
    app.mainloop()