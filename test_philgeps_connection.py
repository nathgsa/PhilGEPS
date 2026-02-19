#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhilGEPS Website Connection Diagnostic Tool

BUG FIXED:
  BUG-DIAG-1  GUI called subprocess(['python','test_philgeps_connection.py']) which
              fails inside a .exe because no .py files exist.  Added a run()
              function that the GUI can call directly:
                  from test_philgeps_connection import run
                  output, all_passed = run()

  BUG-DIAG-2  Windows encoding crash on older Python — reconfigure() guard
              already present; kept and tightened.
"""

import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import requests
from datetime import datetime


# ── Helpers ────────────────────────────────────────────────────────────────────

def _header(text: str) -> str:
    return "\n" + "=" * 60 + "\n" + text + "\n" + "=" * 60


def test_basic_connection() -> tuple:
    lines = [_header("Test 1: Basic Internet Connection")]
    try:
        r = requests.get("https://www.google.com", timeout=5)
        lines += ["✓ Internet connection: OK", f"  Status: {r.status_code}"]
        return True, lines
    except Exception as e:
        lines += ["✗ Internet connection: FAILED", f"  Error: {e}"]
        return False, lines


def test_philgeps_homepage() -> tuple:
    lines = [_header("Test 2: PhilGEPS Homepage Access")]
    url = "https://notices.philgeps.gov.ph/"
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        lines += [
            "✓ PhilGEPS homepage: Accessible",
            f"  Status: {r.status_code}",
            f"  Final URL: {r.url}",
            f"  Redirects: {len(r.history)}",
        ]
        return True, lines
    except requests.exceptions.TooManyRedirects:
        lines += ["✗ PhilGEPS homepage: TOO MANY REDIRECTS",
                  "  The website is redirecting in a loop"]
        return False, lines
    except Exception as e:
        lines += ["✗ PhilGEPS homepage: FAILED", f"  Error: {e}"]
        return False, lines


def test_philgeps_category_page() -> tuple:
    lines = [_header("Test 3: PhilGEPS Category Page Access")]
    url = ("https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/"
           "SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=29"
           "&type=category&ClickFrom=OpenOpp")
    headers = {
        'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36',
        'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        lines += [
            "✓ Category page: Accessible",
            f"  Status: {r.status_code}",
            f"  Final URL: {r.url[:80]}...",
            f"  Redirects: {len(r.history)}",
            f"  Content length: {len(r.content)} bytes",
        ]
        return True, lines
    except requests.exceptions.TooManyRedirects:
        lines += ["✗ Category page: TOO MANY REDIRECTS",
                  "  The website may be blocking automated access."]
        return False, lines
    except Exception as e:
        lines += ["✗ Category page: FAILED", f"  Error: {e}"]
        return False, lines


def test_playwright_access() -> tuple:
    lines = [_header("Test 4: Playwright Browser Access")]
    try:
        from playwright.sync_api import sync_playwright
        url = ("https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/"
               "SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=29"
               "&type=category&ClickFrom=OpenOpp")
        with sync_playwright() as p:
            lines.append("  Launching browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/120.0.0.0 Safari/537.36')
            )
            page = context.new_page()
            lines.append("  Navigating to PhilGEPS...")
            try:
                page.goto(url, timeout=30000, wait_until='domcontentloaded')
                lines += [
                    "✓ Playwright access: SUCCESS",
                    f"  Final URL: {page.url[:80]}...",
                    f"  Page title: {page.title()[:50]}...",
                ]
                browser.close()
                return True, lines
            except Exception as e:
                lines += ["✗ Playwright access: FAILED", f"  Error: {e}"]
                browser.close()
                return False, lines
    except ImportError:
        lines += ["✗ Playwright not installed",
                  "  Run: pip install playwright",
                  "  Then: playwright install chromium"]
        return False, lines
    except Exception as e:
        lines += [f"✗ Playwright test failed: {e}"]
        return False, lines


def check_dns() -> tuple:
    import socket
    lines = [_header("Test 5: DNS Resolution")]
    hostname = "notices.philgeps.gov.ph"
    try:
        ip = socket.gethostbyname(hostname)
        lines += [f"✓ DNS Resolution: OK", f"  {hostname} → {ip}"]
        return True, lines
    except socket.gaierror as e:
        lines += [f"✗ DNS Resolution: FAILED",
                  f"  Cannot resolve {hostname}",
                  f"  Error: {e}"]
        return False, lines


def _recommendations(results: dict) -> list:
    lines = [_header("Recommendations")]
    if all(results.values()):
        lines += [
            "✓ All tests passed!",
            "",
            "Your connection to PhilGEPS is working normally.",
            "If scraping still fails, wait a few minutes then retry.",
        ]
        return lines
    lines.append("Some tests failed. Here's what to do:")
    if not results.get('internet'):
        lines += ["", "❌ CRITICAL: No internet connection",
                  "   → Check your network connection and firewall"]
    if not results.get('homepage'):
        lines += ["", "⚠️  Cannot access PhilGEPS homepage",
                  "   → Site may be down. Try in a browser first."]
    if not results.get('category'):
        lines += ["", "⚠️  Cannot access category pages",
                  "   → PhilGEPS may have anti-bot protection active",
                  "   → Try a VPN if you are outside the Philippines"]
    if not results.get('playwright'):
        lines += ["", "⚠️  Playwright browser automation failed",
                  "   → Reinstall: playwright install chromium"]
    if not results.get('dns'):
        lines += ["", "❌ DNS resolution failed",
                  "   → Try Google DNS (8.8.8.8)"]
    return lines


# ── BUG-DIAG-1 FIX: importable run() function ─────────────────────────────────
def run() -> tuple:
    """
    Run all diagnostic tests and return (output_text, all_passed).

    Called by scraper_gui.py's 'Run Connection Diagnostics' button so the
    diagnostics work inside a frozen .exe without launching a subprocess.

    Returns
    -------
    output_text : str
        Full diagnostic report as a single string.
    all_passed  : bool
        True if every test passed.
    """
    buf = io.StringIO()

    def emit(line: str = ""):
        buf.write(line + "\n")

    emit("=" * 60)
    emit("PhilGEPS Scraper - Connection Diagnostic Tool")
    emit("=" * 60)
    emit(f"Date/Time : {datetime.now()}")
    emit(f"Platform  : {sys.platform}")
    emit("")
    emit("Running tests, please wait…")

    tests = [
        ('internet',  test_basic_connection),
        ('dns',       check_dns),
        ('homepage',  test_philgeps_homepage),
        ('category',  test_philgeps_category_page),
        ('playwright',test_playwright_access),
    ]

    results = {}
    for key, fn in tests:
        ok, lines = fn()
        results[key] = ok
        for line in lines:
            emit(line)

    for line in _recommendations(results):
        emit(line)

    emit(_header("Summary"))
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    emit(f"Tests passed: {passed}/{total}")
    emit("")
    if passed == total:
        emit("✅ Your system is ready to run the scraper!")
    else:
        emit("⚠️  Some issues detected. Follow recommendations above.")

    return buf.getvalue(), all(results.values())


# ── CLI entry-point (unchanged behaviour) ─────────────────────────────────────
def main():
    output, all_passed = run()
    print(output)
    input("Press Enter to exit...")


if __name__ == '__main__':
    main()
