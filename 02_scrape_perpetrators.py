"""
Represores Cubanos scraper (v2)
===============================

Scrapes represorescubanos.com for the full perpetrator database.

What changed since v1:
  - Uses BeautifulSoup instead of regex for meta extraction. The site's
    description field can run multi-paragraph with line breaks and
    embedded quotes; regex was too fragile.
  - Default --max-id raised from 1500 to 2200. Real records exist at
    id >= 2082 as of May 2026 (Alberto Hechemendia Manzanarez).
  - Strips the "EXPEDIENTE DE " prefix the site sometimes prepends to
    og:title.
  - New mode 'identify': walks /identify-repressor/{id}, the separate
    ID space for unidentified perpetrators (photo only, no name).
  - New --dry-run flag: parse without writing to db. Use for smoke
    testing a small range.
  - 'stats' subcommand now also prints by URL pattern (detail vs
    identify), and prints the top-name-prefix frequency to sanity
    check that names came out right.

URL patterns:
    https://represorescubanos.com/repressor-detail/{id}   (named records)
    https://represorescubanos.com/identify-repressor/{id} (unnamed; photo-only)

Fields stored per record:
    id, source ('detail'|'identify'), url, name, description,
    image_url, image_local, status, http_code, fetched_at

Usage:
    pip install requests beautifulsoup4 lxml
    python represores_scraper.py scrape --max-id 2200 --delay 1.5
    python represores_scraper.py identify --max-id 600 --delay 1.5
    python represores_scraper.py stats
    python represores_scraper.py images --out images/
    python represores_scraper.py export --csv represores.csv

Test before a real run:
    python represores_scraper.py scrape --start-id 320 --max-id 325 \\
        --stop-after-empty 999 --dry-run
"""

import argparse
import csv
import logging
import random
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger("represores")

BASE = "https://represorescubanos.com"
DETAIL_URL = BASE + "/repressor-detail/{id}"
IDENTIFY_URL = BASE + "/identify-repressor/{id}"
USER_AGENT = (
    "Mozilla/5.0 (research; investigative journalism; "
    "contact: dead-letter-publishing) Python-requests"
)
DEFAULT_DB = "represores.sqlite"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS repressors (
    id           INTEGER NOT NULL,
    source       TEXT NOT NULL,
    url          TEXT NOT NULL,
    name         TEXT,
    description  TEXT,
    image_url    TEXT,
    image_local  TEXT,
    status       TEXT NOT NULL,
    http_code    INTEGER,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (id, source)
);

CREATE INDEX IF NOT EXISTS ix_status ON repressors(status);
CREATE INDEX IF NOT EXISTS ix_source ON repressors(source);
"""


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# HTML / meta extraction (BeautifulSoup-based)
# ---------------------------------------------------------------------------

TITLE_PREFIXES_TO_STRIP = ("EXPEDIENTE DE ", "Expediente de ", "expediente de ")
DEFAULT_TITLES = {
    "represores cubanos",
    "represores",
    "ficha de represor por identificar",
}
DEFAULT_DESC_HINTS = (
    "somos ciudadanos cubanos y de otras nacionalidades",
)


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


def parse_page(html: str) -> dict:
    """Extract metadata from a page using BeautifulSoup."""
    parser = "lxml" if _has_lxml() else "html.parser"
    soup = BeautifulSoup(html, parser)
    meta = {}

    if soup.title and soup.title.string:
        meta["__title__"] = soup.title.string.strip()

    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property")
        if not key:
            continue
        key = key.strip().lower()
        content = tag.get("content")
        if content is None:
            continue
        meta[key] = content.strip()

    return meta


def clean_title(raw: str) -> str:
    """Normalize a name by stripping known site prefixes and whitespace."""
    s = raw.strip()
    for pfx in TITLE_PREFIXES_TO_STRIP:
        if s.startswith(pfx):
            s = s[len(pfx):].strip()
            break
    return s


def is_real_detail(meta: dict) -> bool:
    """Real /repressor-detail/ record: person-specific title + real body."""
    og_title = clean_title(meta.get("og:title", ""))
    desc = (meta.get("og:description") or meta.get("description") or "").strip()

    if not og_title:
        return False
    if og_title.lower() in DEFAULT_TITLES:
        return False
    if any(hint in desc.lower() for hint in DEFAULT_DESC_HINTS):
        return False
    if len(desc) < 40:
        return False
    return True


def is_real_identify(meta: dict) -> bool:
    """
    Real /identify-repressor/ record: no person name (by design), but
    has a real photo and a non-default description.
    """
    img = meta.get("og:image", "")
    desc = (meta.get("og:description") or meta.get("description") or "").strip()
    if not img or img.endswith("/logo.png"):
        return False
    if any(hint in desc.lower() for hint in DEFAULT_DESC_HINTS):
        return False
    if len(desc) < 30:
        return False
    return True


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


class Fetcher:
    def __init__(self, delay: float = 1.5, jitter: float = 0.5, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
        self.delay = delay
        self.jitter = jitter
        self.timeout = timeout

    def get(self, url: str, max_retries: int = 3) -> requests.Response:
        last_exc = None
        for attempt in range(max_retries):
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"server error {r.status_code}")
                return r
            except (requests.RequestException, requests.HTTPError) as e:
                last_exc = e
                backoff = (2 ** attempt) + random.random()
                log.warning("fetch failed %s (attempt %d): %s, sleeping %.1fs",
                            url, attempt + 1, e, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"giving up on {url}: {last_exc}")

    def pace(self):
        time.sleep(self.delay + random.random() * self.jitter)


# ---------------------------------------------------------------------------
# Generic walker
# ---------------------------------------------------------------------------


def _walk(args, url_template: str, source: str, real_predicate, name_extractor):
    """
    Shared loop for the two URL patterns. real_predicate(meta)->bool decides
    whether a fetched page is a real record. name_extractor(meta)->str
    returns the human-readable name (or '' for unnamed records).
    """
    conn = None if args.dry_run else open_db(args.db)
    fetcher = Fetcher(delay=args.delay)

    done = set()
    if conn and not args.refetch:
        for row in conn.execute("SELECT id FROM repressors WHERE source=?", (source,)):
            done.add(row[0])
        log.info("already in db [%s]: %d records", source, len(done))

    consecutive_empty = 0
    ok = empty = err = 0

    for rid in range(args.start_id, args.max_id + 1):
        if rid in done:
            continue

        url = url_template.format(id=rid)
        try:
            r = fetcher.get(url)
        except RuntimeError as e:
            log.error("permanent failure id=%d: %s", rid, e)
            if conn:
                conn.execute(
                    "INSERT OR REPLACE INTO repressors "
                    "(id, source, url, status, http_code, fetched_at) "
                    "VALUES (?, ?, ?, 'http_error', NULL, ?)",
                    (rid, source, url, datetime.utcnow().isoformat()),
                )
                conn.commit()
            err += 1
            consecutive_empty += 1
            fetcher.pace()
            continue

        if r.status_code == 404:
            if conn:
                conn.execute(
                    "INSERT OR REPLACE INTO repressors "
                    "(id, source, url, status, http_code, fetched_at) "
                    "VALUES (?, ?, ?, 'http_error', 404, ?)",
                    (rid, source, url, datetime.utcnow().isoformat()),
                )
                conn.commit()
            consecutive_empty += 1
            fetcher.pace()
            continue

        meta = parse_page(r.text)
        if not real_predicate(meta):
            if conn:
                conn.execute(
                    "INSERT OR REPLACE INTO repressors "
                    "(id, source, url, status, http_code, fetched_at) "
                    "VALUES (?, ?, ?, 'empty', ?, ?)",
                    (rid, source, url, r.status_code,
                     datetime.utcnow().isoformat()),
                )
                conn.commit()
            empty += 1
            consecutive_empty += 1
            log.info("id=%-5d EMPTY", rid)
        else:
            name = name_extractor(meta)
            desc = (meta.get("og:description") or meta.get("description") or "").strip()
            img = meta.get("og:image", "").strip()
            if conn:
                conn.execute(
                    "INSERT OR REPLACE INTO repressors "
                    "(id, source, url, name, description, image_url, status, "
                    " http_code, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'ok', ?, ?)",
                    (rid, source, url, name, desc, img, r.status_code,
                     datetime.utcnow().isoformat()),
                )
                conn.commit()
            ok += 1
            consecutive_empty = 0
            log.info("id=%-5d OK     %s  [desc=%d chars]",
                     rid, (name or "(unnamed)")[:60], len(desc))

        if consecutive_empty >= args.stop_after_empty:
            log.info("stopping: %d consecutive empty IDs reached",
                     args.stop_after_empty)
            break

        fetcher.pace()

    mode = "DRY-RUN" if args.dry_run else "WROTE"
    log.info("%s done [%s].  ok=%d  empty=%d  errors=%d",
             mode, source, ok, empty, err)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_scrape(args):
    _walk(
        args,
        url_template=DETAIL_URL,
        source="detail",
        real_predicate=is_real_detail,
        name_extractor=lambda m: clean_title(m.get("og:title", "")),
    )


def cmd_identify(args):
    _walk(
        args,
        url_template=IDENTIFY_URL,
        source="identify",
        real_predicate=is_real_identify,
        name_extractor=lambda m: "",
    )


def cmd_images(args):
    conn = open_db(args.db)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(delay=args.delay)

    rows = conn.execute(
        "SELECT id, source, image_url FROM repressors "
        "WHERE status='ok' AND image_url IS NOT NULL "
        "AND (image_local IS NULL OR image_local='')"
    ).fetchall()
    log.info("images to download: %d", len(rows))

    for rid, source, img_url in rows:
        if not img_url:
            continue
        ext = Path(urlparse(img_url).path).suffix or ".jpg"
        local = out_dir / f"{source}_{rid}{ext}"
        try:
            r = fetcher.get(img_url)
            if r.status_code == 200 and r.content:
                local.write_bytes(r.content)
                conn.execute(
                    "UPDATE repressors SET image_local=? "
                    "WHERE id=? AND source=?",
                    (str(local), rid, source),
                )
                conn.commit()
                log.info("[%s/%d] image saved -> %s (%d bytes)",
                         source, rid, local.name, len(r.content))
            else:
                log.warning("[%s/%d] image http %d", source, rid, r.status_code)
        except Exception as e:
            log.error("[%s/%d] image fetch failed: %s", source, rid, e)
        fetcher.pace()


def cmd_export(args):
    conn = open_db(args.db)
    rows = conn.execute(
        "SELECT id, source, url, name, description, image_url, image_local, "
        "       fetched_at "
        "FROM repressors WHERE status='ok' ORDER BY source, id"
    ).fetchall()
    cols = ["id", "source", "url", "name", "description",
            "image_url", "image_local", "fetched_at"]
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in rows:
            w.writerow(row)
    log.info("exported %d rows -> %s", len(rows), args.csv)


def cmd_stats(args):
    conn = open_db(args.db)
    print()
    print("status by source")
    print("-" * 60)
    for source, status, count in conn.execute(
        "SELECT source, status, COUNT(*) FROM repressors "
        "GROUP BY source, status ORDER BY source, status"
    ):
        print(f"  {source:9s}  {status:12s}  {count:6d}")

    print()
    print("totals")
    print("-" * 60)
    total = conn.execute("SELECT COUNT(*) FROM repressors").fetchone()[0]
    ok = conn.execute(
        "SELECT COUNT(*) FROM repressors WHERE status='ok'"
    ).fetchone()[0]
    with_img = conn.execute(
        "SELECT COUNT(*) FROM repressors "
        "WHERE status='ok' AND image_local IS NOT NULL AND image_local!=''"
    ).fetchone()[0]
    print(f"  total rows:     {total}")
    print(f"  real records:   {ok}")
    print(f"  images saved:   {with_img}")

    names = [
        r[0] for r in conn.execute(
            "SELECT name FROM repressors "
            "WHERE status='ok' AND source='detail' AND name IS NOT NULL"
        ) if r[0]
    ]
    if names:
        first_words = Counter(n.split()[0] for n in names if n.split())
        print()
        print("top 15 first words in detail names (rank check)")
        print("-" * 60)
        for word, n in first_words.most_common(15):
            print(f"  {word:20s} {n:4d}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite checkpoint path")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _walk_args(s):
        s.add_argument("--start-id", type=int, default=1)
        s.add_argument("--delay", type=float, default=1.5,
                       help="seconds between requests (default 1.5)")
        s.add_argument("--stop-after-empty", type=int, default=80,
                       help="stop after this many consecutive empty IDs")
        s.add_argument("--refetch", action="store_true",
                       help="re-fetch IDs already in the db")
        s.add_argument("--dry-run", action="store_true",
                       help="parse but do not write to db")

    s = sub.add_parser("scrape", help="walk /repressor-detail/{id}")
    _walk_args(s)
    s.add_argument("--max-id", type=int, default=2200,
                   help="upper bound on detail IDs (default 2200)")
    s.set_defaults(func=cmd_scrape)

    s = sub.add_parser("identify", help="walk /identify-repressor/{id}")
    _walk_args(s)
    s.add_argument("--max-id", type=int, default=600,
                   help="upper bound on identify IDs (default 600)")
    s.set_defaults(func=cmd_identify)

    s = sub.add_parser("images", help="download images for OK records")
    s.add_argument("--out", default="images", help="image output directory")
    s.add_argument("--delay", type=float, default=1.0)
    s.set_defaults(func=cmd_images)

    s = sub.add_parser("export", help="export OK records to CSV")
    s.add_argument("--csv", default="represores.csv")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("stats", help="print db stats")
    s.set_defaults(func=cmd_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()