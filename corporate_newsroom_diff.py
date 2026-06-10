"""
corporate_newsroom_diff.py — Weekly corporate newsroom / sitemap diffing.

For each company in config/corporate_watchlist.json that carries a
newsroom_url, politely fetch ONE page per run (the newsroom page, or a
sitemap if the URL ends in .xml / the response is XML), extract press-release
and article URLs, and diff them against the `documents` table: db's
insert_document() upserts on the url_normalized UNIQUE constraint, and
db.is_already_processed() tells new from seen — the diff state comes for
free, no extra table.

New URLs are emitted as article-shaped dicts:
    {title, url, snippet, source, published}
suitable for the standard 6-layer filter (article_filter.filter_articles).
This module does NOT call the filter and does NOT touch the discovery phase —
integration wiring happens later at the call-site.

Public entry point:
    collect_new_articles(conn, companies=None, max_fetches=MAX_FETCHES_PER_RUN)

Politeness rules:
  - 1 fetch per company per run, and at most 1 fetch per DOMAIN per run
    (some watchlist companies share a corporate domain)
  - hard cap MAX_FETCHES_PER_RUN (~200) fetches per run
  - 15 s timeout, identifying User-Agent, random 0.5-1.5 s jitter between
    fetches
  - failures are logged and skipped, never raised

Zero cost — all corporate newsroom pages are free public data.

__main__ smoke mode: runs against the first 3 companies using an IN-MEMORY
documents table (no persistent state is written) and prints what it would
emit.
"""
from __future__ import annotations

import logging
import random
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent
WATCHLIST_PATH = _BACKEND_ROOT / "config" / "corporate_watchlist.json"

MAX_FETCHES_PER_RUN = 200
FETCH_TIMEOUT = 15
USER_AGENT = ("CanadianMacroDashboard/1.0 "
              "(+https://github.com/lagging-indicator; weekly capital-project "
              "discovery; contact: walterbolduc@gmail.com)")

# Path fragments that mark a link as news/press-release-like.
_NEWSY_PATH_HINTS = (
    "/news", "/media", "/press", "/release", "/stories", "/story",
    "/announcement", "/newsroom", "/article", "/insights", "/updates",
)
_YEAR_RE = re.compile(r"/20\d{2}[-/]")
# Link extensions that are never articles.
_SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js",
             ".ico", ".zip", ".mp4", ".mp3", ".webp", ".woff", ".woff2")
_SKIP_PATH_HINTS = ("/login", "/signin", "/subscribe", "/search", "/tag/",
                    "/category/", "/page/", "/feed", "/rss", "/sitemap",
                    "/privacy", "/terms", "/cookie", "/contact", "/careers")

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_NEWS_NS = "{http://www.google.com/schemas/sitemap-news/0.9}"


# ── Fetch (isolated so tests can monkeypatch) ────────────────────────────────

def _fetch(url: str, timeout: int = FETCH_TIMEOUT) -> str | None:
    """GET a URL with the project UA. Returns text or None on any failure."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000)  # 2 MB cap
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except Exception as e:
        logger.warning("newsroom fetch failed for %s: %s", url, e)
        return None


# ── URL extraction (pure, unit-testable) ─────────────────────────────────────

def _looks_like_article(url: str, base_domain: str) -> bool:
    """Heuristic: same-domain link whose path looks like a news article."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = p.netloc.lower().lstrip("www.")
    if base_domain and not (host == base_domain or host.endswith("." + base_domain)):
        return False
    path = (p.path or "").lower()
    if not path or path == "/":
        return False
    if path.endswith(_SKIP_EXT):
        return False
    if any(h in path for h in _SKIP_PATH_HINTS):
        return False
    newsy = any(h in path for h in _NEWSY_PATH_HINTS) or bool(_YEAR_RE.search(path))
    if not newsy:
        return False
    # A listing root like /newsroom/ or a nav link like
    # /News-and-Stories/Glossary isn't an article — require slug depth AND an
    # article-like leaf slug (date digits, several hyphens, or a long slug).
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return False
    leaf = segments[-1]
    sluggy = (any(ch.isdigit() for ch in leaf)
              or leaf.count("-") + leaf.count("_") >= 3
              or len(leaf) >= 30)
    return sluggy


def _base_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def extract_urls_from_sitemap(xml_text: str) -> list[dict]:
    """Parse sitemap / news-sitemap XML. Returns [{url, title, published}].

    Handles plain urlsets and news-sitemaps (google news namespace). Sitemap
    index files yield nothing (we only spend 1 request per company, so we
    don't recurse into child sitemaps).
    """
    out, seen = [], set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for url_el in root.iter(f"{_SITEMAP_NS}url"):
        loc = url_el.find(f"{_SITEMAP_NS}loc")
        if loc is None or not (loc.text or "").strip():
            continue
        u = loc.text.strip()
        if u in seen:
            continue
        seen.add(u)
        title, published = "", ""
        news = url_el.find(f"{_NEWS_NS}news")
        if news is not None:
            t = news.find(f"{_NEWS_NS}title")
            d = news.find(f"{_NEWS_NS}publication_date")
            title = (t.text or "").strip() if t is not None else ""
            published = (d.text or "").strip() if d is not None else ""
        if not published:
            lastmod = url_el.find(f"{_SITEMAP_NS}lastmod")
            published = (lastmod.text or "").strip() if lastmod is not None else ""
        out.append({"url": u, "title": title, "published": published})
    return out


def extract_urls_from_html(html: str, page_url: str) -> list[dict]:
    """Extract article-looking same-domain links from a newsroom HTML page.

    Returns [{url, title, published}] (published empty — listing pages rarely
    carry machine-readable dates; the filter pipeline tolerates it).
    """
    base_domain = _base_domain(page_url)
    out, seen = [], set()
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        anchors = [(a.get("href") or "", a.get_text(" ", strip=True))
                   for a in soup.find_all("a")]
    except Exception:
        # bs4 unavailable or parse blow-up — regex fallback.
        anchors = [(m.group(1), re.sub(r"<[^>]+>", " ", m.group(2)).strip())
                   for m in re.finditer(
                       r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                       html, re.IGNORECASE | re.DOTALL)]
    for href, text in anchors:
        href = href.strip()
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        absolute = urljoin(page_url, href).split("#")[0]
        if absolute in seen:
            continue
        if not _looks_like_article(absolute, base_domain):
            continue
        seen.add(absolute)
        out.append({"url": absolute, "title": (text or "")[:300], "published": ""})
    return out


def extract_article_urls(content: str, source_url: str) -> list[dict]:
    """Dispatch: sitemap XML vs newsroom HTML."""
    stripped = (content or "").lstrip()
    if stripped.startswith("<?xml") or "<urlset" in stripped[:2000] \
            or "<sitemapindex" in stripped[:2000]:
        return extract_urls_from_sitemap(content)
    return extract_urls_from_html(content, source_url)


# ── Diff against the documents table ─────────────────────────────────────────

def diff_new_urls(conn, company: dict, candidates: list[dict]) -> list[dict]:
    """Filter candidates to never-seen URLs, record them in `documents`, and
    return article-shaped dicts. Uses db.is_already_processed for the check
    and db.insert_document (url_normalized UNIQUE upsert) as the diff state.
    """
    import db as dbmod
    articles = []
    for cand in candidates:
        url = cand.get("url") or ""
        if not url:
            continue
        try:
            seen, _status = dbmod.is_already_processed(conn, url)
        except Exception as e:
            logger.warning("documents lookup failed for %s: %s", url, e)
            continue
        if seen:
            continue
        dbmod.insert_document(
            conn, url,
            title=cand.get("title") or "",
            source_tier="corporate_newsroom",
            source_type="press_release",
            published_date=cand.get("published") or "",
        )
        title = cand.get("title") or _title_from_url(url)
        articles.append({
            "title": title,
            "url": url,
            "snippet": "",
            "source": f"{company.get('name', '')} newsroom",
            "published": cand.get("published") or "",
            # Extra context fields — harmless to the 6-layer filter, useful
            # to metadata tagging downstream.
            "discovery_source": "corporate_newsroom_diff",
            "company": company.get("name", ""),
            "sector_hint": company.get("sector", ""),
            "province_hint": company.get("hq_province", ""),
        })
    return articles


def _title_from_url(url: str) -> str:
    """Fallback title: last path slug, de-hyphenated."""
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.\w+$", "", slug)
    return re.sub(r"[-_]+", " ", slug).strip().title()


# ── Main collection job ──────────────────────────────────────────────────────

def load_watchlist(path: Path = WATCHLIST_PATH) -> list[dict]:
    import json
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [c for c in data.get("companies", []) if c.get("newsroom_url")]


def collect_new_articles(conn, companies: list[dict] | None = None,
                         max_fetches: int = MAX_FETCHES_PER_RUN,
                         jitter: bool = True) -> list[dict]:
    """Weekly job. Fetches each company's newsroom once, diffs against the
    documents table, returns new article-shaped dicts ready for
    article_filter.filter_articles. Never raises on per-company failure.
    """
    if companies is None:
        companies = load_watchlist()
    articles: list[dict] = []
    fetched_domains: set[str] = set()
    fetches = 0
    for company in companies:
        if fetches >= max_fetches:
            logger.info("newsroom diff: fetch cap %d reached", max_fetches)
            break
        url = company.get("newsroom_url") or ""
        domain = _base_domain(url)
        if not domain or domain in fetched_domains:
            continue  # politeness: one fetch per domain per run
        fetched_domains.add(domain)
        if jitter and fetches:
            time.sleep(random.uniform(0.5, 1.5))
        fetches += 1
        content = _fetch(url)
        if not content:
            continue
        try:
            candidates = extract_article_urls(content, url)
        except Exception as e:
            logger.warning("newsroom parse failed for %s: %s",
                           company.get("name"), e)
            continue
        new = diff_new_urls(conn, company, candidates)
        if new:
            logger.info("newsroom diff: %s -> %d new of %d extracted",
                        company.get("name"), len(new), len(candidates))
        articles.extend(new)
    return articles


# ── Smoke mode ───────────────────────────────────────────────────────────────

def _smoke() -> None:
    """Run against 3 companies with an in-memory documents table — prints what
    a real run would emit, persists nothing."""
    import sqlite3
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT NOT NULL,
            url_normalized  TEXT UNIQUE NOT NULL,
            content_hash    TEXT,
            title           TEXT,
            published_date  TEXT,
            fetch_date      TEXT DEFAULT (datetime('now')),
            source_tier     TEXT,
            source_type     TEXT,
            fetch_status    TEXT DEFAULT 'fetched',
            is_relevant     INTEGER,
            classification_json TEXT,
            language        TEXT DEFAULT 'en',
            created_at      TEXT DEFAULT (datetime('now'))
        )""")
    companies = load_watchlist()[:3]
    print(f"SMOKE: fetching {len(companies)} newsrooms "
          f"({', '.join(c['name'] for c in companies)})\n")
    arts = collect_new_articles(conn, companies=companies)
    print(f"\nWould emit {len(arts)} article dicts:")
    for a in arts[:25]:
        print(f"  [{a['source']}] {a['title'][:70]!r}\n    {a['url']}")
    if len(arts) > 25:
        print(f"  ... and {len(arts) - 25} more")


if __name__ == "__main__":
    _smoke()
