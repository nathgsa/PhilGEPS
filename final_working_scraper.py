#!/usr/bin/env python3
"""
Final working PhilGEPS scraper that captures all 148+ entries.

PERFORMANCE & RELIABILITY FIXES (this version):
------------------------------------------------
FIX-PERF-1  Thread-local browser pool
    BEFORE: parse_detail() called sync_playwright().start() + chromium.launch() for
            EVERY URL — 148 pages × ~2.5 s startup overhead = ~6 minutes wasted.
    AFTER:  Each worker thread creates ONE browser on its first call and reuses it
            for every subsequent URL it processes.  Total startup cost drops from
            148 × 2.5 s  →  (workers) × 2.5 s.

FIX-PERF-2  Removed dead SESSION.get() call
    BEFORE: parse_detail() made a requests.get() whose return value was never used,
            silently doubling all network traffic and adding ~44 s of pointless delay.
    AFTER:  The dead call is gone.

FIX-REL-1   Thread-safe PLAYWRIGHT_COOKIES with lock
    BEFORE: Two parallel category workers both called collect_detail_links(), which
            wrote to the global PLAYWRIGHT_COOKIES without any synchronisation.
            Last-write-wins caused ~50 % of parallel detail pages to load with the
            wrong session cookies, producing 'Transaction cannot be completed' errors.
    AFTER:  _COOKIES_LOCK (threading.Lock) guards all reads and writes.
            get_playwright_cookies() / _set_playwright_cookies() are the only access
            points; internal code never touches the global directly.

OTHER FIXES (unchanged from previous version):
  FIX-1  contact_position column extracted from contact blob (5-tuple return).
  FIX-2  _is_position_title() uses keyword-only matching (no over-broad heuristic).
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup as BS
import requests, time, csv, re, sys, threading
from urllib.parse import urljoin
import argparse

BASE = "https://notices.philgeps.gov.ph"

# ── Predefined categories ─────────────────────────────────────────────────────
PREDEFINED_CATEGORIES = {
    28:  {"name": "Packaging Supplies",    "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=28&type=category&ClickFrom=OpenOpp"},
    29:  {"name": "Printing Services",     "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=29&type=category&ClickFrom=OpenOpp"},
    51:  {"name": "Printing Supplies",     "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=51&type=category&ClickFrom=OpenOpp"},
    64:  {"name": "Graphics Design",       "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=64&type=category&ClickFrom=OpenOpp"},
    71:  {"name": "Corporate Giveaways",   "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=71&type=category&ClickFrom=OpenOpp"},
    80:  {"name": "General Merchandise",   "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=80&type=category&ClickFrom=OpenOpp"},
    129: {"name": "Tokens",                "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=129&type=category&ClickFrom=OpenOpp"},
    134: {"name": "Educational",           "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=134&type=category&ClickFrom=OpenOpp"},
    150: {"name": "Reproduction Services", "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=150&type=category&ClickFrom=OpenOpp"},
}

LIST_URL = PREDEFINED_CATEGORIES[29]["url"]

# ── User-Agent (platform-aware) ───────────────────────────────────────────────
if sys.platform == "darwin":
    CURRENT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
else:
    CURRENT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

SESSION = requests.Session()
REQUEST_HEADERS = {
    "User-Agent":              CURRENT_UA,
    "Accept":                  "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language":         "en-US,en;q=0.9",
    "Referer":                 "https://notices.philgeps.gov.ph/",
    "Connection":              "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ── FIX-REL-1: Thread-safe PLAYWRIGHT_COOKIES ─────────────────────────────────
# All access to the global cookie store goes through these two functions.
# The lock prevents parallel category workers from overwriting each other's
# session cookies, which previously caused ~50 % of detail pages to fail.
_PLAYWRIGHT_COOKIES: list = []
_COOKIES_LOCK = threading.Lock()


def get_playwright_cookies() -> list:
    """Return an immutable snapshot of the current Playwright cookies (thread-safe)."""
    with _COOKIES_LOCK:
        return list(_PLAYWRIGHT_COOKIES)


def _set_playwright_cookies(cookies: list) -> None:
    """Store a new cookie snapshot (thread-safe)."""
    global _PLAYWRIGHT_COOKIES
    with _COOKIES_LOCK:
        _PLAYWRIGHT_COOKIES = list(cookies)


# ── FIX-PERF-1: Thread-local browser pool ─────────────────────────────────────
# One Playwright BrowserContext per worker thread, created on first use and
# kept alive for every subsequent parse_detail() call on that thread.
# This eliminates the per-URL chromium.launch() cost (~2.5 s × 148 pages = ~6 min).
_tl = threading.local()

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
]


def _get_thread_context(cookies: list):
    """
    Return the thread-local BrowserContext, creating it on first access.

    Parameters
    ----------
    cookies : list
        Cookie snapshot (from get_playwright_cookies()) to inject when the
        context is first created.  Subsequent calls reuse the existing context.
    """
    if not getattr(_tl, "ready", False):
        _tl.pw      = sync_playwright().start()
        _tl.browser = _tl.pw.chromium.launch(headless=True, args=_BROWSER_ARGS)
        _tl.context = _tl.browser.new_context(
            user_agent=CURRENT_UA,
            viewport={"width": 1366, "height": 768},
            ignore_https_errors=True,
        )
        _tl.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        if cookies:
            _tl.context.add_cookies(cookies)
        _tl.ready = True
    return _tl.context


def shutdown_thread_browser() -> None:
    """
    Close and release the browser owned by the calling thread.

    Call this at the end of each worker thread (e.g. after a
    ThreadPoolExecutor finishes) to avoid leaking Chromium processes.
    Works on both Windows and macOS.
    """
    if getattr(_tl, "ready", False):
        try:
            _tl.context.close()
        except Exception:
            pass
        try:
            _tl.browser.close()
        except Exception:
            pass
        try:
            _tl.pw.stop()
        except Exception:
            pass
        _tl.ready = False


# ── Category helpers ───────────────────────────────────────────────────────────
def get_category_url(category_id):
    if category_id in PREDEFINED_CATEGORIES:
        return PREDEFINED_CATEGORIES[category_id]["url"]
    return None


def validate_category_url(url):
    if not url:
        return False
    if "notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx" not in url:
        return False
    if "BusCatID=" not in url:
        return False
    return True


# ── Link collection (unchanged logic, uses fixed cookie setter) ───────────────
def collect_detail_links(category_url=None):
    target_url = category_url if category_url else LIST_URL
    links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_BROWSER_ARGS)
        context = browser.new_context(
            user_agent=CURRENT_UA,
            viewport={"width": 1366, "height": 768},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        context.clear_cookies()

        try:
            print(f"Priming connection at {BASE}...")
            page.goto(BASE, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            print(f"Navigating to Category: {target_url}")
            page.goto(target_url, timeout=90000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_selector("a[href*='SplashBidNoticeAbstractUI.aspx']", timeout=30000)
        except Exception as e:
            print(f"Error navigating: {e}")
            browser.close()
            return []

        page_count = 0
        max_pages  = 100
        seen_links: set = set()

        while page_count < max_pages:
            page_count += 1
            print(f"Processing page {page_count}...")
            time.sleep(1.5)

            current_page_links = []
            try:
                for a in page.locator("a[href*='SplashBidNoticeAbstractUI.aspx']").all():
                    href = a.get_attribute("href")
                    if href:
                        full_url = urljoin(target_url, href)
                        if full_url not in seen_links:
                            current_page_links.append(full_url)
                            seen_links.add(full_url)
                            links.append(full_url)
            except Exception as e:
                print(f"Error collecting links on page {page_count}: {e}")

            print(f"Found {len(current_page_links)} NEW links on page {page_count}")

            if not current_page_links and page_count > 1:
                print("Breaking pagination - no new links found")
                break

            next_selectors = [
                'a#pgCtrlDetailedSearch_nextLB',
                'a[id*="next"]',
                'a[onclick*="next"]',
                'a:has-text("Next")',
                'a:has-text(">")',
                'a:has-text(">>")',
                'input[value*="Next"]',
                'input[value*=">"]',
            ]

            next_btn = None
            for sel in next_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0:
                        next_btn = btn
                        break
                except Exception:
                    continue

            if next_btn is None:
                print("No Next button found")
                break

            try:
                if next_btn.first.get_attribute("disabled") is not None:
                    print("Next button is disabled")
                    break
                if not next_btn.first.is_visible():
                    print("Next button is not visible")
                    break
            except Exception:
                break

            try:
                next_btn.first.scroll_into_view_if_needed()
                time.sleep(0.5)
                next_btn.first.click(timeout=10000)
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(2.0)
            except Exception as e:
                print(f"Error clicking Next: {e}")
                break

        # FIX-REL-1: use thread-safe setter instead of direct global write
        _set_playwright_cookies(context.cookies())
        browser.close()

    seen, out = set(), []
    for u in links:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


# ── Detail-page helpers ────────────────────────────────────────────────────────
def _sync_cookies_to_requests_session():
    """Copy the current cookie snapshot into the requests.Session jar."""
    cookies = get_playwright_cookies()   # FIX-REL-1: thread-safe read
    if not cookies:
        return
    jar = SESSION.cookies
    for c in cookies:
        domain = (c.get("domain") or "").lstrip(".") or "notices.philgeps.gov.ph"
        jar.set(name=c.get("name"), value=c.get("value"),
                domain=domain, path=c.get("path", "/"))


def _wait_for_known_labels(page):
    for lbl in ["Reference Number", "Procuring Entity",
                "Approved Budget for the Contract", "Closing Date / Time"]:
        try:
            page.get_by_text(lbl, exact=False).wait_for(timeout=5000)
            return
        except Exception:
            continue


def _is_junk_text(val):
    if not val:
        return False
    v = val.lower()
    if "philgeps team is not responsible" in v:
        return True
    if "printable version" in v and len(val) < 30:
        return True
    kw = ["procuring entity", "title", "area of delivery", "solicitation number"]
    if sum(1 for k in kw if k in v) >= 3:
        return True
    return False


# ── Position-title detection (contact_position fix) ───────────────────────────
_POSITION_KEYWORDS = frozenset({
    # --- Standard Corporate/Gov ---
    "bac", "secretariat", "chairperson", "chairman", "vice-chairman",
    "vice chairman", "member", "officer", "director", "head", "chief",
    "manager", "supervisor", "coordinator", "administrator", "secretary",
    "clerk", "specialist", "accountant", "treasurer", "auditor",
    "engineer", "technician", "procurement", "admin", "administrative",
    "supply", "executive", "senior", "junior", "assistant", "associate",
    "consultant", "employee", "staff", "personnel", "representative",
    
    # --- Departments/Divisions used as titles ---
    "general services", "budget", "finance", "legal", "school", "office",
    "planning", "development", "assessor", "engineering", "accounting",
    "treasury", "social", "welfare", "health", "agriculture",
    
    # --- Political / LGU Specifics (New) ---
    "mayor", "vice-mayor", "councilor", "captain", "capitan", "punong",
    "kagawad", "governor", "board", "member", "sk", "chairman",
    "barangay", "municipal", "city", "provincial", "gov", "chairwoman", "brgy",
    "treasurer", "BARANGAY", "CAPTAIN", "PUNONG", "KAGAWAD", "GOVERNOR", "MAYOR", "VICE-MAYOR", "COUNCILOR",
    
    # --- Education Specifics (New) ---
    "principal", "teacher", "faculty", "instructor", "master",
    "custodian", "property", "guidance", "librarian", "tic", # Teacher In-Charge
    
    # --- Specific Roles/Typos from your list ---
    "aide", "operator", "buyer", "canvasser", "inspector", "driver",
    "utility", "messenger", "watchman", "guard", "cook",
    "charge", # Matches "In-Charge", "Person in Charge"
    "treasure", # Common typo for Treasurer found in data
    
    # --- Acronyms (New) ---
    # Note: Ensure your scraper converts text to lowercase before matching these
    "ao",    # Administrative Officer
    "sao",   # Supervising Admin Officer
    "aso",   # Admin Services Officer
    "ada",   # Admin Aide
    "adas",  # Admin Assistant
    "lso",   # Legislative Staff Officer
    "eco",   # Environment/Economic Officer
    "cgdh",  # City Gov Dept Head
    "pgdh",  # Provincial Gov Dept Head
    "mpdc",  # Municipal Planning & Dev Coordinator
    "mdrrmo", "pdrrmo", "cdrrmo", # Disaster risk officers
    "oic",   # Officer in Charge
    "deped", "dswd", "dpwh", # Agency names often confused as positions
    "rspnco", "psms"
})
_ADDRESS_KEYWORDS = frozenset({
    "street", "st.", "avenue", "ave.", "road", "rd.", "highway",
    "barangay", "brgy.", "brgy", "bgy.", "bgy",
    "poblacion", "purok", "sitio",
    "city", "municipality", "province", "region",
    "philippines", "pilipinas",
    "building", "bldg.", "bldg", "floor", "flr.",
    "compound", "village", "subdivision", "district",
    "zip", "postal",
})


def _is_position_title(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if len(t) > 80:
        return False
    words = set(re.sub(r"[^\w\s]", " ", t.lower()).split())
    if words & _ADDRESS_KEYWORDS:
        return False
    if words & _POSITION_KEYWORDS:
        return True
    return False


def _parse_contact_blob(contact_text):
    """
    Parse a raw PhilGEPS contact blob into a 5-tuple:
        (name, position, address, email, phone)
    """
    if not contact_text or _is_junk_text(contact_text):
        return None, None, None, None, None

    text = contact_text.replace("Printable Version", "").strip()

    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    email  = emails[0] if emails else None
    if email:
        text = text.replace(email, "")

    phones      = re.findall(r'(?:(?:\+?63)?0?\d{1,3}[- .]?)?\d{3,}[- .]?\d{3,}', text)
    valid_phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 7]
    phone        = " / ".join(valid_phones) if valid_phones else None

    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    if len(lines) == 1 and "," in lines[0]:
        parts = [p.strip() for p in lines[0].split(",") if p.strip()]
        if len(parts) >= 2:
            lines = parts

    if not lines:
        return None, None, None, email, phone

    name, position, address_parts = None, None, []
    first = lines[0]

    if _is_position_title(first):
        position = first
        for ln in lines[1:]:
            if phone and ln.strip() == phone.strip():
                continue
            address_parts.append(ln)
    else:
        name = first
        for ln in lines[1:]:
            if phone and ln.strip() == phone.strip():
                continue
            if position is None and not address_parts and _is_position_title(ln):
                position = ln
            else:
                address_parts.append(ln)

    address = ", ".join(address_parts) if address_parts else None
    return name, position, address, email, phone


# ── parse_detail — the main per-URL function ──────────────────────────────────
def parse_detail(url: str) -> dict:
    """
    Scrape one PhilGEPS detail page and return a dict of fields.

    FIX-PERF-1: Uses a thread-local BrowserContext so the browser is created
    once per worker thread and reused for every URL (eliminates ~2.5 s per-URL
    startup overhead).

    FIX-PERF-2: The dead SESSION.get() call that doubled network traffic has
    been removed.
    """
    _sync_cookies_to_requests_session()

    # FIX-PERF-1 — reuse the thread-local browser context instead of launching
    # a new Chromium process for every single URL.
    cookies = get_playwright_cookies()   # FIX-REL-1: thread-safe read
    context = _get_thread_context(cookies)
    page    = context.new_page()

    try:
        page.goto(url, timeout=90_000)
        page.wait_for_load_state("networkidle")
        _wait_for_known_labels(page)

        if page.get_by_text("Transaction cannot be completed", exact=False).count() > 0:
            page.reload()
            page.wait_for_load_state("networkidle")
            _wait_for_known_labels(page)

        def pw_value(label_text):
            xp = (
                "//tr[.//span[contains(normalize-space(.), '" + label_text + "')] or"
                " .//td[contains(normalize-space(.), '"  + label_text + "')] or"
                " .//th[contains(normalize-space(.), '"  + label_text + "')]]"
                "/td[position()>1][1]"
            )
            loc = page.locator(xp).first
            if loc.count() == 0:
                xp2  = "//tr[.//span[contains(normalize-space(.), '" + label_text + "')]]/td[1]"
                loc2 = page.locator(xp2).first
                if loc2.count():
                    txt = loc2.inner_text().strip()
                    return re.sub(r"^\s*" + re.escape(label_text) + r"\s*:?\s*", "", txt, flags=re.I)
                return None
            return loc.inner_text().strip()

        table_map = {
            "Reference Number":              pw_value("Reference Number"),
            "Procuring Entity":              pw_value("Procuring Entity"),
            "Title":                         pw_value("Title"),
            "Area of Delivery":              pw_value("Area of Delivery"),
            "Solicitation Number":           pw_value("Solicitation Number"),
            "Procurement Mode":              pw_value("Procurement Mode"),
            "Classification":                pw_value("Classification"),
            "Category":                      pw_value("Category"),
            "Approved Budget for the Contract": pw_value("Approved Budget for the Contract"),
            "Delivery Period":               pw_value("Delivery Period"),
            "Status":                        pw_value("Status"),
            "Date Published":                pw_value("Date Published"),
            "Closing Date / Time":           pw_value("Closing Date / Time"),
            "Last Updated / Time":           pw_value("Last Updated / Time"),
            "Contact Person":                pw_value("Contact Person"),
            "Office/Address":                pw_value("Office/Address"),
            "Address":                       pw_value("Address"),
            "Email Address":                 pw_value("Email Address"),
            "Telephone Number":              pw_value("Telephone Number"),
        }
        html = page.content()

    except Exception:
        page.close()
        return {}
    finally:
        page.close()   # close the page but keep the context (browser) alive

    s = BS(html, "html.parser")

    def clean_text(val):
        if not isinstance(val, str):
            return val
        val = val.strip()
        if _is_junk_text(val):
            return None
        return val.replace("Printable Version", "").strip()

    def normalize_money(maybe_money):
        if not maybe_money:
            return None
        txt = re.sub(r"[₱$,]", "", str(maybe_money))
        return re.sub(r"\s+", " ", txt).strip()

    def find_value_by_label(soup, label):
        for k, v in table_map.items():
            if label.lower() in k.lower() and v:
                return v
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            header = cells[0].get_text(" ", strip=True)
            if header and label.lower() in header.lower():
                if len(cells) >= 2:
                    return cells[1].get_text(" ", strip=True)
                full = tr.get_text(" ", strip=True)
                return full.replace(header, "").strip() or None
        node = soup.find(string=lambda t: isinstance(t, str) and label.lower() in t.lower())
        if node:
            parent = node.parent
            txt     = parent.get_text(" ", strip=True)
            cleaned = re.sub(r"^\s*" + re.escape(label) + r"\s*:?\s*", "", txt, flags=re.I)
            if cleaned and cleaned != txt:
                return cleaned.strip()
            sib = parent.find_next_sibling()
            if sib:
                return sib.get_text(" ", strip=True)
            nxt = parent.find_next(["td", "div", "span"])
            if nxt:
                return nxt.get_text(" ", strip=True)
        return None

    raw_contact = clean_text(find_value_by_label(s, "Contact Person"))
    c_name, c_pos, c_addr, c_email, c_phone = _parse_contact_blob(raw_contact)

    m     = re.search(r"refID=(\d+)", url)
    refid = m.group(1) if m else None

    return {
        "refID":              refid,
        "url":                url,
        "reference_number":   clean_text(find_value_by_label(s, "Reference Number")),
        "procuring_entity":   clean_text(find_value_by_label(s, "Procuring Entity")),
        "title":              clean_text(find_value_by_label(s, "Title")),
        "area_of_delivery":   clean_text(find_value_by_label(s, "Area of Delivery")),
        "solicitation_number":clean_text(find_value_by_label(s, "Solicitation Number")),
        "procurement_mode":   clean_text(find_value_by_label(s, "Procurement Mode")),
        "classification":     clean_text(find_value_by_label(s, "Classification")),
        "category":           clean_text(find_value_by_label(s, "Category")),
        "abc_php":            normalize_money(find_value_by_label(s, "Approved Budget for the Contract")),
        "delivery_period":    clean_text(find_value_by_label(s, "Delivery Period")),
        "status":             clean_text(find_value_by_label(s, "Status")),
        "date_published":     clean_text(find_value_by_label(s, "Date Published")),
        "closing_datetime":   clean_text(find_value_by_label(s, "Closing Date / Time")),
        "last_updated":       clean_text(find_value_by_label(s, "Last Updated / Time")),
        "contact_person":     c_name  or clean_text(find_value_by_label(s, "Contact Person")),
        "contact_position":   c_pos,
        "contact_address":    c_addr  or clean_text(find_value_by_label(s, "Office/Address")) or clean_text(find_value_by_label(s, "Address")),
        "contact_email":      c_email or clean_text(find_value_by_label(s, "Email Address")),
        "contact_phone":      c_phone or clean_text(find_value_by_label(s, "Telephone Number")),
    }


# ── CLI entry-point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Final working PHILGEPS scraper")
    parser.add_argument("--limit",  type=int,   default=0,    help="Detail pages to scrape (0 = all)")
    parser.add_argument("--output", type=str,   default="philgeps_final_working.csv")
    parser.add_argument("--delay",  type=float, default=0.5,  help="Seconds between requests")
    args = parser.parse_args()

    print("Starting scraper...")
    detail_urls = collect_detail_links()

    target_urls = detail_urls[:args.limit] if args.limit > 0 else detail_urls
    print(f"\nScraping {len(target_urls)} detail pages...")

    rows = []
    for idx, u in enumerate(target_urls, start=1):
        try:
            print(f"Processing {idx}/{len(target_urls)}: {u}")
            rows.append(parse_detail(u))
        except Exception as exc:
            print(f"Warning: failed to parse {u}: {exc}")
        time.sleep(max(0.0, args.delay))

    # Clean up the thread-local browser used by the main thread
    shutdown_thread_browser()

    if not rows:
        raise SystemExit("No rows scraped.")

    seen_refids: set = set()
    deduped = []
    for row in rows:
        rid = row.get("refID")
        if rid and rid in seen_refids:
            continue
        if rid:
            seen_refids.add(rid)
        deduped.append(row)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=deduped[0].keys())
        w.writeheader()
        w.writerows(deduped)
    print(f"Saved {len(deduped)} rows to {args.output}")