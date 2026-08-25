#!/usr/bin/env python3
"""
Prisoners Defenders Cuba — Political Prisoner Scraper v2
=========================================================
Strategy:
  1. Load the list page (lista.prisonersdefenders.org/?s=) with network
     interception enabled. Capture any AJAX/XHR/fetch calls that load
     the prisoner cards — WordPress custom search plugins almost always
     hit a REST endpoint returning JSON. If we catch it, we get all
     1260 records in one shot.

  2. If no JSON endpoint is found, parse the card grid HTML directly,
     extract name + slug + card-level fields, paginate through all pages,
     then visit each individual prisoner slug page for the full record.

  3. All data written to CSV + JSONL + SQLite. Checkpoint file for
     crash recovery. Graceful SIGINT/SIGTERM shutdown.

Config at top of file — edit directly, no CLI flags.

Setup:
    pip install playwright beautifulsoup4 lxml aiofiles rich
    playwright install chromium
    python3 scraper_prisoners_defenders.py

Author: August Holloway / Impunity Graph
"""

import asyncio
import csv
import json
import logging
import re
import signal
import sqlite3
import time
import random
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these directly
# ─────────────────────────────────────────────────────────────────

BASE_URL         = "https://lista.prisonersdefenders.org"
LIST_URL         = "https://lista.prisonersdefenders.org/?s="
CONCURRENCY      = 3          # parallel detail page fetches
DELAY_BETWEEN    = (1.2, 2.5) # seconds random delay between requests
PAGE_TIMEOUT     = 30_000     # ms navigation timeout
WAIT_TIMEOUT     = 10_000     # ms element wait timeout
MAX_RETRIES      = 4
HEADLESS         = True       # set False to watch browser and solve captchas manually

OUTPUT_DIR       = Path(".")
CHECKPOINT_FILE  = OUTPUT_DIR / "checkpoint_slugs.txt"
CSV_FILE         = OUTPUT_DIR / "prisoners.csv"
JSONL_FILE       = OUTPUT_DIR / "prisoners.jsonl"
DB_FILE          = OUTPUT_DIR / "prisoners.db"
LOG_FILE         = OUTPUT_DIR / "scraper.log"
SLUGS_FILE       = OUTPUT_DIR / "slugs.txt"   # cache of all discovered slugs

# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

console = Console()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True, show_path=False),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("scraper")

# ─────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────

@dataclass
class Prisoner:
    slug:               str
    url:                str
    name:               Optional[str] = None
    gender:             Optional[str] = None
    age_current:        Optional[str] = None
    age_at_arrest:      Optional[str] = None
    province:           Optional[str] = None
    arrest_date:        Optional[str] = None
    charge_type:        Optional[str] = None
    sentence_years:     Optional[str] = None
    prison:             Optional[str] = None
    penal_status:       Optional[str] = None
    prisoner_type:      Optional[str] = None
    political_org:      Optional[str] = None
    dob:                Optional[str] = None
    observations:       Optional[str] = None
    scraped_at:         str = field(
                            default_factory=lambda: datetime.now(timezone.utc).isoformat()
                        )
    parse_error:        Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]


# ─────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prisoners (
            slug            TEXT PRIMARY KEY,
            url             TEXT,
            name            TEXT,
            gender          TEXT,
            age_current     TEXT,
            age_at_arrest   TEXT,
            province        TEXT,
            arrest_date     TEXT,
            charge_type     TEXT,
            sentence_years  TEXT,
            prison          TEXT,
            penal_status    TEXT,
            prisoner_type   TEXT,
            political_org   TEXT,
            dob             TEXT,
            observations    TEXT,
            scraped_at      TEXT,
            parse_error     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skipped (
            slug        TEXT PRIMARY KEY,
            reason      TEXT,
            checked_at  TEXT
        )
    """)
    conn.commit()
    return conn


def db_upsert_prisoner(conn: sqlite3.Connection, p: Prisoner) -> None:
    d = p.to_dict()
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    updates = ", ".join(f"{k}=excluded.{k}" for k in d if k != "slug")
    conn.execute(
        f"INSERT INTO prisoners ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(slug) DO UPDATE SET {updates}",
        list(d.values())
    )
    conn.commit()


def db_insert_skipped(conn: sqlite3.Connection, slug: str, reason: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO skipped VALUES (?, ?, ?)",
        (slug, reason, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()


def db_get_done_slugs(conn: sqlite3.Connection) -> set[str]:
    # Guard against old v1 schema which used 'id' not 'slug'
    cols = {row[1] for row in conn.execute("PRAGMA table_info(prisoners)").fetchall()}
    if "slug" not in cols:
        log.warning("Old DB schema detected — dropping and recreating tables")
        conn.execute("DROP TABLE IF EXISTS prisoners")
        conn.execute("DROP TABLE IF EXISTS skipped")
        conn.commit()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prisoners (
                slug TEXT PRIMARY KEY, url TEXT, name TEXT, gender TEXT,
                age_current TEXT, age_at_arrest TEXT, province TEXT,
                arrest_date TEXT, charge_type TEXT, sentence_years TEXT,
                prison TEXT, penal_status TEXT, prisoner_type TEXT,
                political_org TEXT, dob TEXT, observations TEXT,
                scraped_at TEXT, parse_error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skipped (
                slug TEXT PRIMARY KEY, reason TEXT, checked_at TEXT
            )
        """)
        conn.commit()
        return set()
    done = {r["slug"] for r in conn.execute("SELECT slug FROM prisoners").fetchall()}
    skipped = {r["slug"] for r in conn.execute("SELECT slug FROM skipped").fetchall()}
    return done | skipped


# ─────────────────────────────────────────────────────────────────
# CHECKPOINT
# ─────────────────────────────────────────────────────────────────

def load_done_slugs_from_checkpoint() -> set[str]:
    if CHECKPOINT_FILE.exists():
        slugs = {
            line.strip()
            for line in CHECKPOINT_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        log.info(f"Checkpoint: {len(slugs)} slugs already processed")
        return slugs
    return set()


async def save_checkpoint(slug: str) -> None:
    async with aiofiles.open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        await f.write(f"{slug}\n")


def load_slug_cache() -> list[str]:
    if SLUGS_FILE.exists():
        slugs = [
            line.strip()
            for line in SLUGS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        log.info(f"Slug cache: {len(slugs)} slugs loaded from {SLUGS_FILE}")
        return slugs
    return []


async def save_slug_cache(slugs: list[str]) -> None:
    async with aiofiles.open(SLUGS_FILE, "w", encoding="utf-8") as f:
        await f.write("\n".join(slugs) + "\n")
    log.info(f"Slug cache saved: {len(slugs)} slugs to {SLUGS_FILE}")


# ─────────────────────────────────────────────────────────────────
# HTML PARSERS
# ─────────────────────────────────────────────────────────────────

LABEL_MAP = {
    "fecha de detención":    "arrest_date",
    "fecha de detencion":    "arrest_date",
    "tipo de delito":        "charge_type",
    "condena":               "sentence_years",
    "prisión":               "prison",
    "prision":               "prison",
    "estado penal":          "penal_status",
    "tipo de preso":         "prisoner_type",
    "organización política": "political_org",
    "organizacion politica": "political_org",
    "fecha de nacimiento":   "dob",
    "edad actual":           "age_current",
    "edad en la detención":  "age_at_arrest",
    "edad en la detencion":  "age_at_arrest",
    "provincia":             "province",
    "género":                "gender",
    "genero":                "gender",
}


def parse_prisoner_page(html: str, slug: str, url: str) -> Optional[Prisoner]:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.find("title")
    title_text = title_el.get_text(strip=True).lower() if title_el else ""
    for sig in ["no encontrad", "not found", "404", "host not in allowlist"]:
        if sig in title_text or sig in html.lower()[:300]:
            return None

    h1 = soup.find("h1")
    name = h1.get_text(strip=True) if h1 else None
    if not name or len(name) < 3:
        return None

    p = Prisoner(slug=slug, url=url, name=name)

    # Strategy 1: badge/label divs
    for el in soup.find_all(class_=re.compile(r"badge|label|field|dato|etiqueta|key", re.I)):
        raw = el.get_text(strip=True).lower().rstrip(":")
        if raw in LABEL_MAP:
            sib = el.find_next_sibling()
            val = sib.get_text(strip=True) if sib else ""
            if not val:
                val = el.parent.get_text(separator=" ", strip=True)
                val = val.replace(el.get_text(strip=True), "").strip().lstrip(":")
            if val and not getattr(p, LABEL_MAP[raw]):
                setattr(p, LABEL_MAP[raw], val)

    # Strategy 2: definition lists
    for dt in soup.find_all("dt"):
        raw = dt.get_text(strip=True).lower().rstrip(":")
        dd = dt.find_next_sibling("dd")
        if dd and raw in LABEL_MAP and not getattr(p, LABEL_MAP[raw]):
            setattr(p, LABEL_MAP[raw], dd.get_text(strip=True))

    # Strategy 3: table rows
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            raw = cells[0].get_text(strip=True).lower().rstrip(":")
            val = cells[1].get_text(strip=True)
            if raw in LABEL_MAP and val and not getattr(p, LABEL_MAP[raw]):
                setattr(p, LABEL_MAP[raw], val)

    # Strategy 4: text scan
    for label_key, field_name in LABEL_MAP.items():
        if getattr(p, field_name):
            continue
        pattern = re.compile(re.escape(label_key), re.I)
        el = soup.find(string=pattern)
        if el and el.parent:
            full_text = el.parent.get_text(separator=" ", strip=True)
            cleaned = re.sub(pattern, "", full_text).strip().lstrip(":").strip()
            if cleaned and len(cleaned) < 200:
                setattr(p, field_name, cleaned)

    # Sidebar: gender, age, province
    sidebar = soup.find(class_=re.compile(r"card|sidebar|perfil|info|preso", re.I))
    if sidebar:
        for line in sidebar.get_text(separator="\n", strip=True).splitlines():
            ll = line.strip().lower()
            if not ll:
                continue
            if "hombre" in ll and not p.gender:
                p.gender = "Hombre"
            elif "mujer" in ll and not p.gender:
                p.gender = "Mujer"
            m = re.search(r"edad actual[:\s]+(\d+)", ll)
            if m and not p.age_current:
                p.age_current = m.group(1)
            if not p.province and 3 < len(line.strip()) < 40:
                if re.match(r"^[A-Za-zÀ-ÿ\s,]+$", line.strip()):
                    if not any(kw in ll for kw in ["edad", "hombre", "mujer", "preso", "año"]):
                        p.province = line.strip()

    # Observations
    for obs_label in soup.find_all(string=re.compile(r"observacion|descripci", re.I)):
        parent = obs_label.parent
        if parent:
            nxt = parent.find_next_sibling()
            if nxt:
                obs = nxt.get_text(separator=" ", strip=True)
                if len(obs) > 20:
                    p.observations = obs[:3000]
                    break

    # Clean sentence to numeric
    if p.sentence_years:
        m = re.search(r"(\d+(?:[.,]\d+)?)", p.sentence_years)
        if m:
            p.sentence_years = m.group(1).replace(",", ".")

    return p


def parse_cards_from_html(html: str) -> list[dict]:
    """Extract slug + card-level fields from the list page grid."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Find all links pointing to /prisioneros/<slug>/
    seen = set()
    for link in soup.find_all("a", href=re.compile(r"/prisioneros/[a-z]")):
        href = link.get("href", "")
        slug = href.rstrip("/").split("/")[-1]
        if not slug or slug in seen or len(slug) < 3:
            continue
        seen.add(slug)

        # Walk up to find the card container
        card_el = link
        for _ in range(4):
            if card_el.parent:
                card_el = card_el.parent
            else:
                break

        text = card_el.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name = lines[0] if lines else link.get_text(strip=True)

        record = {"slug": slug, "url": href, "name": name}
        for line in lines[1:]:
            ll = line.lower()
            if "estado penal:" in ll:
                record["penal_status"] = line.split(":", 1)[-1].strip()
            elif "prisión:" in ll or "prision:" in ll:
                record["prison"] = line.split(":", 1)[-1].strip()
            elif "edad" in ll:
                m = re.search(r"(\d+)", line)
                if m:
                    record["age_at_arrest"] = m.group(1)
        results.append(record)

    return results


# ─────────────────────────────────────────────────────────────────
# BROWSER CONTEXT
# ─────────────────────────────────────────────────────────────────

async def make_context(browser: Browser) -> BrowserContext:
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="es-ES",
        timezone_id="Europe/Madrid",
        viewport={"width": 1440, "height": 900},
        accept_downloads=False,
        java_script_enabled=True,
        extra_http_headers={
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT": "1",
        },
    )
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['es-ES','es','en'] });
    """)
    return ctx


# ─────────────────────────────────────────────────────────────────
# PHASE 1: DISCOVER ALL SLUGS
# ─────────────────────────────────────────────────────────────────

async def discover_slugs(browser: Browser) -> list[str]:
    log.info("Phase 1: Discovering all prisoner slugs...")

    ctx = await make_context(browser)
    intercepted_json: list[dict] = []

    async def handle_response(response: Response) -> None:
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            body = await response.json()
            url = response.url
            if isinstance(body, list) and len(body) > 10:
                intercepted_json.append({"url": url, "data": body})
                log.info(f"Intercepted JSON array: {len(body)} items from {url[:80]}")
            elif isinstance(body, dict):
                for key in ("data", "posts", "results", "items", "prisoners", "presos"):
                    if key in body and isinstance(body[key], list) and len(body[key]) > 5:
                        intercepted_json.append({"url": url, "data": body[key]})
                        log.info(f"Intercepted JSON dict[{key}]: {len(body[key])} items")
                        break
        except Exception:
            pass

    page = await ctx.new_page()
    page.on("response", handle_response)
    await page.route(
        "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,mp4,mp3,ico}",
        lambda route: route.abort()
    )

    log.info(f"Loading list page: {LIST_URL}")
    try:
        await page.goto(LIST_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
    except Exception as e:
        log.warning(f"List page warning: {e}")

    await asyncio.sleep(3)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(2)

    # Method A: JSON interception
    if intercepted_json:
        log.info(f"Method A: extracting slugs from intercepted JSON")
        slugs = []
        for item in intercepted_json:
            for record in item["data"]:
                for key in ("slug", "post_name", "link", "url", "permalink"):
                    if key in record:
                        val = str(record[key])
                        slug = val.rstrip("/").split("/")[-1]
                        if slug and len(slug) > 2:
                            slugs.append(slug)
                            break
        if slugs:
            slugs = list(dict.fromkeys(slugs))
            log.info(f"Method A: {len(slugs)} unique slugs via JSON")
            await page.close()
            await ctx.close()
            return slugs

    # Method B: brute-force URL pagination
    # WordPress standard: /?s=&paged=N  or  /page/N/?s=
    # We try both patterns and stop when a page returns no new slugs.
    log.info("Method B: brute-force URL pagination")
    all_cards: list[dict] = []
    CONSECUTIVE_EMPTY = 0
    MAX_EMPTY = 3      # stop after 3 pages with no new slugs
    MAX_PAGES = 100    # hard ceiling

    # Collect page 1 which is already loaded
    html = await page.content()
    cards = parse_cards_from_html(html)
    all_cards.extend(cards)
    log.info(f"Page 1: {len(cards)} cards (total {len(all_cards)})")

    for page_num in range(2, MAX_PAGES + 1):
        if CONSECUTIVE_EMPTY >= MAX_EMPTY:
            log.info(f"Stopping after {MAX_EMPTY} consecutive empty pages")
            break

        # Try both common WordPress pagination patterns
        urls_to_try = [
            f"{BASE_URL}/?s=&paged={page_num}",
            f"{BASE_URL}/page/{page_num}/?s=",
            f"{BASE_URL}/?paged={page_num}",
        ]

        got_cards = False
        for try_url in urls_to_try:
            await asyncio.sleep(random.uniform(*DELAY_BETWEEN))
            try:
                await page.goto(try_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
                await asyncio.sleep(1.5)
                html = await page.content()

                # Bail if redirected back to page 1
                if page.url.rstrip("/") in (
                    BASE_URL, f"{BASE_URL}/?s=", f"{BASE_URL}/"
                ):
                    log.info(f"Page {page_num}: redirected to homepage — pagination ended")
                    CONSECUTIVE_EMPTY = MAX_EMPTY
                    break

                existing_slugs = {c["slug"] for c in all_cards}
                cards = parse_cards_from_html(html)
                new_cards = [c for c in cards if c["slug"] not in existing_slugs]

                if new_cards:
                    all_cards.extend(new_cards)
                    log.info(
                        f"Page {page_num} ({try_url.split('?')[1]}): "
                        f"+{len(new_cards)} new (total {len(all_cards)})"
                    )
                    CONSECUTIVE_EMPTY = 0
                    got_cards = True
                    break  # this URL pattern works, no need to try others
                elif cards:
                    # Got cards but all duplicates — pagination ended
                    log.info(f"Page {page_num}: all duplicates — pagination likely ended")
                    CONSECUTIVE_EMPTY = MAX_EMPTY
                    break
            except Exception as e:
                log.warning(f"Page {page_num} {try_url}: {e}")

        if not got_cards:
            CONSECUTIVE_EMPTY += 1
            log.debug(f"Page {page_num}: no new cards ({CONSECUTIVE_EMPTY}/{MAX_EMPTY} empty)")

    await page.close()
    await ctx.close()

    slugs = list(dict.fromkeys(c["slug"] for c in all_cards))
    log.info(f"Phase 1 complete: {len(slugs)} unique slugs")
    return slugs


# ─────────────────────────────────────────────────────────────────
# PHASE 2: FETCH DETAIL PAGES
# ─────────────────────────────────────────────────────────────────

async def fetch_prisoner(
    ctx: BrowserContext,
    slug: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, Optional[Prisoner], str]:
    url = f"{BASE_URL}/prisioneros/{slug}/"

    async with semaphore:
        await asyncio.sleep(random.uniform(*DELAY_BETWEEN))

        for attempt in range(1, MAX_RETRIES + 1):
            page: Optional[Page] = None
            try:
                page = await ctx.new_page()
                await page.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,mp4,mp3,ico}",
                    lambda route: route.abort()
                )
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT
                )
                status = response.status if response else 0

                if status == 404:
                    await page.close()
                    return slug, None, "not_found"

                if status == 403:
                    await page.close()
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(5 * attempt)
                        continue
                    return slug, None, "forbidden"

                try:
                    await page.wait_for_selector("h1", timeout=WAIT_TIMEOUT)
                except Exception:
                    pass

                html = await page.content()
                await page.close()

                prisoner = parse_prisoner_page(html, slug, url)
                if prisoner is None:
                    return slug, None, "parse_empty"

                log.info(
                    f"  ✓ {prisoner.name} | "
                    f"{prisoner.charge_type or '?'} | "
                    f"{prisoner.sentence_years or '?'}yr | "
                    f"{prisoner.prison or '?'}"
                )
                return slug, prisoner, "ok"

            except Exception as e:
                log.warning(f"  {slug}: attempt {attempt} — {type(e).__name__}: {e}")
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(3 * attempt)
                else:
                    log.error(f"  {slug}: all {MAX_RETRIES} attempts failed")
                    return slug, None, f"error:{type(e).__name__}"

    return slug, None, "unknown"


# ─────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────

def init_csv(path: Path) -> None:
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=Prisoner.field_names()).writeheader()


def append_csv(path: Path, p: Prisoner) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=Prisoner.field_names()).writerow(p.to_dict())


async def append_jsonl(path: Path, p: Prisoner) -> None:
    async with aiofiles.open(path, "a", encoding="utf-8") as f:
        await f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self):
        self.ok = self.not_found = self.errors = 0
        self.start = time.time()

    def rate(self) -> float:
        elapsed = time.time() - self.start
        total = self.ok + self.not_found + self.errors
        return total / elapsed if elapsed > 0 else 0

    def eta(self, remaining: int) -> str:
        r = self.rate()
        if r == 0:
            return "--:--:--"
        secs = int(remaining / r)
        h, rem = divmod(secs, 3600)
        return f"{h:02d}:{rem//60:02d}:{rem%60:02d}"

    def summary(self) -> str:
        elapsed = time.time() - self.start
        return (
            f"Found={self.ok} | NotFound={self.not_found} | "
            f"Errors={self.errors} | "
            f"Rate={self.rate():.1f}/s | "
            f"Elapsed={elapsed:.0f}s"
        )


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 60)
    log.info("Prisoners Defenders Cuba — Scraper v2 (slug-based)")
    log.info("=" * 60)

    conn = init_db(DB_FILE)
    init_csv(CSV_FILE)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        # Phase 1: slug discovery
        slugs = load_slug_cache()
        if not slugs:
            slugs = await discover_slugs(browser)
            if not slugs:
                log.error("No slugs discovered — check the site manually or set HEADLESS=False")
                await browser.close()
                conn.close()
                return
            await save_slug_cache(slugs)
        else:
            log.info(f"Using cached slugs: {len(slugs)}")

        # Filter already done
        done = db_get_done_slugs(conn) | load_done_slugs_from_checkpoint()
        todo = [s for s in slugs if s not in done]
        log.info(f"Slugs: total={len(slugs)} done={len(done)} remaining={len(todo)}")

        if not todo:
            log.info("All slugs processed.")
            await browser.close()
            conn.close()
            return

        # Phase 2: detail pages
        stats = Stats()
        semaphore = asyncio.Semaphore(CONCURRENCY)
        shutdown_event = asyncio.Event()

        def handle_signal():
            log.warning("Shutdown signal — finishing current batch")
            shutdown_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

        contexts = [await make_context(browser) for _ in range(CONCURRENCY)]

        log.info("Warming up session...")
        try:
            warm = await contexts[0].new_page()
            await warm.goto(BASE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            await warm.close()
            log.info("Session warm")
        except Exception as e:
            log.warning(f"Warmup failed: {e}")

        BATCH = CONCURRENCY * 8

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching prisoner pages...", total=len(todo))

            for batch_start in range(0, len(todo), BATCH):
                if shutdown_event.is_set():
                    break

                batch = todo[batch_start: batch_start + BATCH]
                tasks = [
                    fetch_prisoner(contexts[i % len(contexts)], slug, semaphore)
                    for i, slug in enumerate(batch)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        log.error(f"Gather exception: {result}")
                        stats.errors += 1
                        progress.advance(task)
                        continue

                    slug, prisoner, status = result

                    if status == "ok" and prisoner:
                        stats.ok += 1
                        db_upsert_prisoner(conn, prisoner)
                        append_csv(CSV_FILE, prisoner)
                        await append_jsonl(JSONL_FILE, prisoner)
                    elif status in ("not_found", "parse_empty"):
                        stats.not_found += 1
                        db_insert_skipped(conn, slug, status)
                    else:
                        stats.errors += 1
                        db_insert_skipped(conn, slug, status)

                    await save_checkpoint(slug)
                    progress.advance(task)

                remaining = len(todo) - (batch_start + len(batch))
                log.info(f"Batch | {stats.summary()} | Remaining={remaining} | ETA={stats.eta(remaining)}")

        for ctx in contexts:
            await ctx.close()
        await browser.close()

    conn.close()

    log.info("=" * 60)
    log.info("COMPLETE")
    log.info(stats.summary())
    log.info(f"  CSV:   {CSV_FILE}")
    log.info(f"  JSONL: {JSONL_FILE}")
    log.info(f"  DB:    {DB_FILE}")
    log.info("=" * 60)
    log.info("Analysis queries:")
    log.info(f'  sqlite3 {DB_FILE} "SELECT charge_type, COUNT(*) n FROM prisoners GROUP BY charge_type ORDER BY n DESC"')
    log.info(f'  sqlite3 {DB_FILE} "SELECT prison, COUNT(*) n FROM prisoners GROUP BY prison ORDER BY n DESC LIMIT 20"')
    log.info(f'  sqlite3 {DB_FILE} "SELECT AVG(CAST(sentence_years AS REAL)) FROM prisoners WHERE sentence_years IS NOT NULL"')
    log.info(f'  sqlite3 {DB_FILE} "SELECT province, COUNT(*) n FROM prisoners GROUP BY province ORDER BY n DESC"')


if __name__ == "__main__":
    asyncio.run(main())