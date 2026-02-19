#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         PhilGEPS ScraperV2 — One-Click Build Script             ║
║                                                                  ║
║  Windows → produces  dist/PhilGEPS_ScraperV2.exe                ║
║  macOS   → produces  dist/PhilGEPS_ScraperV2.app                ║
║                                                                  ║
║  HOW TO RUN:                                                     ║
║    python build.py                                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import shutil
import subprocess
import platform
from pathlib import Path

# ── Coloured output helpers (graceful fallback on Windows) ─────────────────────
def _c(code, text):
    if sys.platform == "win32" and not os.environ.get("WT_SESSION"):
        return text          # No ANSI in old cmd.exe
    return f"\033[{code}m{text}\033[0m"

def ok(msg):    print(_c("92", f"  ✓ {msg}"))
def info(msg):  print(_c("96", f"  ▸ {msg}"))
def warn(msg):  print(_c("93", f"  ⚠ {msg}"))
def fail(msg):  print(_c("91", f"  ✗ {msg}")); sys.exit(1)
def header(msg):print(_c("1;97", f"\n{'═'*60}\n  {msg}\n{'═'*60}"))


# ══════════════════════════════════════════════════════════════════
# 1.  CONFIGURATION — edit here if needed
# ══════════════════════════════════════════════════════════════════
APP_NAME        = "PhilGEPS_ScraperV2"
ENTRY_SCRIPT    = "scraper_gui.py"          # main GUI entry-point
ICON_WIN        = "assets/icon.ico"
ICON_MAC        = "assets/icon.icns"
ONE_FILE        = False                     # True = single .exe (slower launch)
                                            # False = one-dir bundle (recommended)
CONSOLE_WINDOW  = False                     # False hides the terminal window


# ══════════════════════════════════════════════════════════════════
# 2.  PREFLIGHT CHECKS
# ══════════════════════════════════════════════════════════════════
def check_prerequisites():
    header("Step 1 — Preflight checks")

    # Python version
    if sys.version_info < (3, 8):
        fail(f"Python 3.8+ required (you have {sys.version.split()[0]})")
    ok(f"Python {sys.version.split()[0]}")

    # PyInstaller
    try:
        import PyInstaller
        ok(f"PyInstaller {PyInstaller.__version__}")
    except ImportError:
        fail("PyInstaller not found.  Run: pip install pyinstaller")

    # CustomTkinter
    try:
        import customtkinter
        ok(f"customtkinter {customtkinter.__version__}")
    except ImportError:
        fail("customtkinter not found.  Run: pip install customtkinter")

    # Playwright
    try:
        import playwright
        ok("playwright installed")
    except ImportError:
        fail("playwright not found.  Run: pip install playwright && playwright install chromium")

    # Entry script exists
    if not Path(ENTRY_SCRIPT).exists():
        fail(f"Entry script not found: {ENTRY_SCRIPT}")
    ok(f"Entry script found: {ENTRY_SCRIPT}")


# ══════════════════════════════════════════════════════════════════
# 3.  COLLECT DATA FILES
# ══════════════════════════════════════════════════════════════════
def find_customtkinter_data():
    """Return (src_dir, 'customtkinter') tuple for customtkinter assets."""
    import customtkinter
    ctk_dir = Path(customtkinter.__file__).parent
    return (str(ctk_dir), "customtkinter")


def find_playwright_browser():
    """
    Locate the installed Chromium browser and return
    (browser_src_dir, 'playwright/driver/package/.local-browsers') so the
    frozen app finds it at the path scraper_gui.py expects.
    Returns None if the browser cannot be found (build will still succeed
    but the app will need playwright installed separately).
    """
    # Ask the playwright CLI where it keeps browsers
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout + result.stderr
    except Exception:
        output = ""

    # Common install locations (playwright stores browsers here by default)
    candidates = []

    if sys.platform == "win32":
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates += [
            local_app / "ms-playwright",
            Path.home() / "AppData" / "Local" / "ms-playwright",
        ]
    elif sys.platform == "darwin":
        candidates += [
            Path.home() / "Library" / "Caches" / "ms-playwright",
            Path.home() / ".cache" / "ms-playwright",
        ]
    else:
        candidates += [
            Path.home() / ".cache" / "ms-playwright",
        ]

    # Also check the playwright package's own .local-browsers (pip install --no-deps layout)
    try:
        import playwright
        pkg_browsers = Path(playwright.__file__).parent / "driver" / "package" / ".local-browsers"
        if pkg_browsers.exists():
            candidates.insert(0, pkg_browsers.parent)
    except Exception:
        pass

    for candidate in candidates:
        if candidate.exists():
            chromium_dirs = list(candidate.glob("chromium*"))
            if chromium_dirs:
                info(f"Found Chromium browser at: {candidate}")
                return (str(candidate), "playwright/driver/package/.local-browsers")

    warn("Could not auto-detect Playwright browser location.")
    warn("The app will still build, but you may need to run")
    warn("  playwright install chromium")
    warn("on the target machine, OR manually set PLAYWRIGHT_BROWSERS_PATH.")
    return None


def find_playwright_driver():
    """Bundle the playwright driver (node binary) so it can launch browsers."""
    try:
        import playwright
        driver_dir = Path(playwright.__file__).parent / "driver"
        if driver_dir.exists():
            return (str(driver_dir), "playwright/driver")
    except Exception:
        pass
    return None


def collect_project_data():
    """Extra project files to include (JSON configs, docs, etc.)."""
    extras = []
    for pattern in ["*.json", "*.md", "*.txt", "*.bat"]:
        for f in Path(".").glob(pattern):
            extras.append((str(f), "."))
    return extras


# ══════════════════════════════════════════════════════════════════
# 4.  HIDDEN IMPORTS
# ══════════════════════════════════════════════════════════════════
HIDDEN_IMPORTS = [
    # Core scraper modules
    "final_working_scraper",
    "multi_category_scraper",
    "data_cleaner",
    "test_philgeps_connection",

    # Playwright internals
    "playwright",
    "playwright.sync_api",
    "playwright._impl._api_types",
    "playwright._impl._browser",
    "playwright._impl._browser_context",
    "playwright._impl._page",
    "playwright._impl._element_handle",
    "playwright._impl._locator",
    "playwright._impl._network",

    # BeautifulSoup
    "bs4",
    "bs4.builder",
    "bs4.builder._html5lib",
    "bs4.builder._htmlparser",
    "bs4.builder._lxml",

    # Data
    "pandas",
    "pandas._libs",
    "pandas._libs.tslibs",
    "pandas.io.formats.style",
    "numpy",
    "numpy.core._multiarray_umath",

    # Requests & networking
    "requests",
    "requests.adapters",
    "urllib3",
    "certifi",
    "charset_normalizer",

    # GUI
    "customtkinter",
    "customtkinter.windows",
    "customtkinter.windows.widgets",
    "customtkinter.windows.widgets.core_rendering",
    "darkdetect",
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",

    # Standard library often missed
    "threading",
    "queue",
    "json",
    "csv",
    "re",
    "math",
    "subprocess",
    "shutil",
    "logging",
    "argparse",
    "typing",
    "pathlib",
    "datetime",
    "io",
    "socket",
    "concurrent.futures",
]


# ══════════════════════════════════════════════════════════════════
# 5.  BUILD
# ══════════════════════════════════════════════════════════════════
def build():
    header("Step 2 — Collecting assets")

    datas = []

    # CustomTkinter
    ctk_data = find_customtkinter_data()
    datas.append(ctk_data)
    ok(f"customtkinter assets: {ctk_data[0]}")

    # Playwright driver
    pw_driver = find_playwright_driver()
    if pw_driver:
        datas.append(pw_driver)
        ok(f"playwright driver:    {pw_driver[0]}")
    else:
        warn("playwright driver not found — skipping")

    # Playwright browser (Chromium)
    pw_browser = find_playwright_browser()
    if pw_browser:
        datas.append(pw_browser)
        ok(f"Chromium browser:     {pw_browser[0]}")

    # Project extras (configs, docs)
    extras = collect_project_data()
    datas.extend(extras)
    if extras:
        ok(f"Project extras:       {len(extras)} file(s)")

    # ── Determine separator (: on POSIX, ; on Windows) ──────────────────────
    SEP = ";" if sys.platform == "win32" else ":"

    # ── Build PyInstaller command ────────────────────────────────────────────
    header("Step 3 — Running PyInstaller")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
    ]

    # windowed / console
    if CONSOLE_WINDOW:
        cmd.append("--console")
    else:
        cmd.append("--windowed")

    # one-file vs one-dir
    if ONE_FILE:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # macOS: produce a proper .app bundle
    if sys.platform == "darwin":
        cmd.append("--windowed")        # ensures .app is created
        if Path(ICON_MAC).exists():
            cmd += ["--icon", ICON_MAC]
            ok(f"Icon: {ICON_MAC}")
        else:
            warn(f"No icon found ({ICON_MAC}) — building without icon")

    # Windows icon
    if sys.platform == "win32":
        if Path(ICON_WIN).exists():
            cmd += ["--icon", ICON_WIN]
            ok(f"Icon: {ICON_WIN}")
        else:
            warn(f"No icon found ({ICON_WIN}) — building without icon")

    # Data files
    for src, dst in datas:
        cmd += ["--add-data", f"{src}{SEP}{dst}"]

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", imp]

    # Exclude heavy unused packages to keep bundle small
    for exc in ["matplotlib", "scipy", "IPython", "notebook", "pytest"]:
        cmd += ["--exclude-module", exc]

    # Entry point
    cmd.append(ENTRY_SCRIPT)

    info("Command:\n    " + " ".join(cmd[:6]) + " …")
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail("PyInstaller exited with errors (see output above).")

    # ── Post-build info ──────────────────────────────────────────────────────
    header("Step 4 — Done!")

    dist = Path("dist")
    if sys.platform == "darwin":
        app = dist / f"{APP_NAME}.app"
        if app.exists():
            ok(f"macOS app bundle:  {app.resolve()}")
            print()
            print(_c("97",  "  To run:"))
            print(_c("96",  f"    open \"{app}\""))
            print()
            print(_c("93",  "  First-run on macOS (removes quarantine flag):"))
            print(_c("96",  f'    xattr -cr "{app}"'))
            print(_c("96",  f'    open "{app}"'))
        else:
            warn(f"Expected .app not found at {app}")
    else:
        if ONE_FILE:
            exe = dist / f"{APP_NAME}.exe"
        else:
            exe = dist / APP_NAME / f"{APP_NAME}.exe"
        if exe.exists():
            ok(f"Windows executable:  {exe.resolve()}")
            print()
            print(_c("97",  "  To run:"))
            print(_c("96",  f'    start "" "{exe}"'))
        else:
            warn(f"Expected .exe not found — check dist/ folder")

    print()
    ok("Build complete.")


# ══════════════════════════════════════════════════════════════════
# 6.  ENTRY
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(_c("1;96", f"""
╔══════════════════════════════════════════════════════════════════╗
║         PhilGEPS ScraperV2 — Build Script                       ║
║         Platform: {platform.system():<45}║
╚══════════════════════════════════════════════════════════════════╝"""))

    check_prerequisites()
    build()
