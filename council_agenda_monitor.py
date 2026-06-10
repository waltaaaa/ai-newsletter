"""
council_agenda_monitor.py — Municipal council agenda mining PILOT (3 CMAs).

Weekly job: fetch upcoming/recent council + committee agendas for the pilot
CMAs, scan item titles/summaries for capital-project keywords, and emit
article-shaped dicts tagged discovery_source='council_agenda' via
collect_agenda_items(). Output dicts are shaped for the standard 6-layer
filter (article_filter.filter_articles) — this module does NOT call the
filter and does NOT touch the discovery phase; integration wiring happens
later at the call-site.

PLATFORM PROBE RESULTS (probed 2026-06-10, server-side GET with project UA):
  Toronto      TMMIS (custom) — secure.toronto.ca/council/api 403 Access
               Denied (Akamai blocks non-browser clients, browser UA also
               403); app.toronto.ca timed out; CKAN open-data portal has no
               agenda-items dataset. NOT fetchable server-side.
  Ottawa       eScribe — pub-ottawa.escribemeetings.com 200. WebMethod
               MeetingsCalendarView.aspx/GetCalendarMeetings returns meeting
               JSON; Meeting.aspx?Id=<guid>&Agenda=Agenda renders agenda item
               titles server-side (.AgendaItemTitle). FETCHABLE.
  Mississauga  eScribe — pub-mississauga.escribemeetings.com 200. FETCHABLE.
  Brampton     eScribe — pub-brampton.escribemeetings.com 200. fetchable.
  Hamilton     eScribe — pub-hamilton.escribemeetings.com 200. fetchable.
  London       eScribe — pub-london.escribemeetings.com 200. fetchable.
  Vaughan      eScribe — pub-vaughan.escribemeetings.com 200. fetchable.
  Markham      eScribe — pub-markham.escribemeetings.com 200 (NOT Legistar;
               markham.legistar.com -> "Invalid parameters!"). fetchable.
  Kitchener    eScribe — pub-kitchener.escribemeetings.com 200 (NOT
               Legistar). fetchable.
  Windsor      Custom — City of Windsor Open Data Catalogue,
               opendata.citywindsor.ca/Tools/CouncilAgendas, server-rendered
               listing of ~1,000 agenda/minutes/item PDFs with meeting type +
               date encoded in the URL path. citywindsor.civicweb.net /
               events.citywindsor.ca do not resolve. FETCHABLE (weaker
               signal: item titles are mostly generic filenames).

PILOT SELECTION: Ottawa (eScribe), Windsor (custom open-data), Mississauga
(eScribe, separate tenant). NOTE ON THE DISTINCT-PLATFORM REQUIREMENT: only
TWO distinct platform families are actually fetchable server-side among the
ten candidate CMAs — every candidate except Toronto/Windsor runs eScribe,
Toronto is bot-blocked, and no candidate runs Legistar or CivicWeb. The
third pilot CMA therefore re-uses eScribe on a separate tenant, which still
exercises tenant-level variation (different committee structures, bilingual
agendas in Ottawa vs English-only in Mississauga).

4-WEEK PILOT SUCCESS CRITERION: the pilot graduates to a permanent discovery
tier if it surfaces >= 5 unique-first projects per month (projects that enter
the database from a council agenda item BEFORE any other discovery tier sees
them — measured via discovery_source='council_agenda' on first-write).
Otherwise it is dropped at the 4-week review.

Politeness: 1 calendar request + at most MAX_MEETINGS_PER_CMA agenda
fetches per CMA per run, 15 s timeout, identifying UA, jitter between
fetches, failures logged not raised. Zero cost — public data.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
import urllib.request
from datetime import date, timedelta
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 15
USER_AGENT = ("CanadianMacroDashboard/1.0 "
              "(+https://github.com/lagging-indicator; weekly capital-project "
              "discovery; contact: walterbolduc@gmail.com)")
MAX_MEETINGS_PER_CMA = 8
# Look back 7 days and ahead 21 days for meetings.
WINDOW_BACK_DAYS = 7
WINDOW_AHEAD_DAYS = 21

# Capital-project signal keywords for agenda item titles (small inline list —
# intentionally NOT shared with the RSS filter's keyword sets).
PROJECT_KEYWORDS = (
    "construction", "development", "rezoning", "re-zoning", "zoning by-law",
    "zoning bylaw", "capital", "infrastructure", "expansion", "redevelopment",
    "site plan", "official plan amendment", "subdivision", "demolition",
    "transit project", "watermain", "wastewater", "recreation centre",
    "community centre",
)
DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*\s*(?:million|billion|[mb]\b)?", re.I)

PILOT_CMAS = {
    "Ottawa": {"platform": "escribe",
               "base": "https://pub-ottawa.escribemeetings.com/"},
    "Mississauga": {"platform": "escribe",
                    "base": "https://pub-mississauga.escribemeetings.com/"},
    "Windsor": {"platform": "windsor_opendata",
                "base": "https://opendata.citywindsor.ca/Tools/CouncilAgendas"},
}


# ── Keyword scan (pure, unit-testable) ───────────────────────────────────────

def scan_title(title: str) -> list[str]:
    """Return the matched signals in an agenda item title ([] = no signal)."""
    if not title:
        return []
    low = title.lower()
    hits = [k for k in PROJECT_KEYWORDS if k in low]
    m = DOLLAR_RE.search(title)
    if m:
        hits.append(f"dollar:{m.group(0).strip()}")
    return hits


def make_article(cma: str, title: str, url: str, published: str,
                 meeting_name: str, signals: list[str]) -> dict:
    """Article-shaped dict for the standard 6-layer filter."""
    return {
        "title": title.strip(),
        "url": url,
        "snippet": f"{cma} {meeting_name} agenda item. Signals: "
                   f"{', '.join(signals)}",
        "source": f"{cma} council agenda ({meeting_name})",
        "published": published,
        "discovery_source": "council_agenda",
        "cma": cma,
        "province_hint": "ON",
    }


# ── HTTP (isolated so tests can monkeypatch) ────────────────────────────────

def _get(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return resp.read(3_000_000).decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("council fetch failed for %s: %s", url, e)
        return None


def _post_json(url: str, payload: dict) -> dict | None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning("council POST failed for %s: %s", url, e)
        return None


# ── eScribe driver (Ottawa, Mississauga) ─────────────────────────────────────

def parse_escribe_meetings(payload: dict) -> list[dict]:
    """Parse GetCalendarMeetings JSON -> [{id, name, start}]."""
    out = []
    for m in (payload or {}).get("d", []) or []:
        mid = m.get("ID") or ""
        if not mid:
            continue
        start = (m.get("StartDate") or "").replace("/", "-")[:10]
        out.append({"id": mid, "name": m.get("MeetingName", ""),
                    "start": start})
    return out


def parse_escribe_agenda_titles(html: str) -> list[str]:
    """Extract agenda item titles from a server-rendered eScribe agenda page.

    Titles live in elements carrying the AgendaItemTitle class. bs4 when
    available; regex fallback otherwise. De-duped, noise filtered.
    """
    titles: list[str] = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        els = soup.select(".AgendaItemTitle")
        raw = [e.get_text(" ", strip=True) for e in els]
    except Exception:
        raw = [re.sub(r"<[^>]+>", " ", m.group(1)).strip()
               for m in re.finditer(
                   r'class="[^"]*AgendaItemTitle[^"]*"[^>]*>(.*?)</',
                   html, re.DOTALL)]
    seen = set()
    for t in raw:
        t = re.sub(r"\s+", " ", t).strip()
        # Drop numbering prefixes ("3.1 ") and obvious boilerplate
        t = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", t)
        if len(t) < 8 or t.lower() in seen:
            continue
        seen.add(t.lower())
        titles.append(t)
    return titles


def collect_escribe(cma: str, base: str,
                    max_meetings: int = MAX_MEETINGS_PER_CMA) -> list[dict]:
    today = date.today()
    payload = _post_json(
        urljoin(base, "MeetingsCalendarView.aspx/GetCalendarMeetings"),
        {"calendarStartDate": (today - timedelta(days=WINDOW_BACK_DAYS)).isoformat(),
         "calendarEndDate": (today + timedelta(days=WINDOW_AHEAD_DAYS)).isoformat()})
    if not payload:
        return []
    meetings = parse_escribe_meetings(payload)[:max_meetings]
    articles = []
    for m in meetings:
        time.sleep(random.uniform(0.5, 1.5))
        agenda_url = urljoin(
            base, f"Meeting.aspx?Id={m['id']}&Agenda=Agenda&lang=English")
        html = _get(agenda_url)
        if not html:
            continue
        for title in parse_escribe_agenda_titles(html):
            signals = scan_title(title)
            if signals:
                articles.append(make_article(
                    cma, title, agenda_url, m["start"], m["name"], signals))
    return articles


# ── Windsor open-data driver ─────────────────────────────────────────────────

_WINDSOR_DATE_RE = re.compile(
    r"/(?:Council-)?(?P<year>20\d{2})/(?:(?P<committee>[A-Z]{3,6})/)?"
    r"(?P<month>\d{2})-(?P<day>\d{2})/", re.I)


def parse_windsor_agenda_links(html: str, page_url: str) -> list[dict]:
    """Extract agenda-document links from the Windsor CouncilAgendas tool.

    Returns [{title, url, published, meeting}]. Meeting type + date are
    encoded in the document path:
      .../Council-2026/06-08/Agenda.pdf
      .../Standing%20Committees/2026/DHSC/06-01/Item10.1-AppendicesB&C.pdf
    Only item-level documents (Item*.pdf) and named reports carry any
    project signal — bare 'Agenda'/'Minutes' links are skipped by the
    keyword scan downstream.
    """
    out = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        anchors = [(a.get("href") or "", a.get_text(" ", strip=True))
                   for a in soup.find_all("a")]
    except Exception:
        anchors = [(m.group(1), re.sub(r"<[^>]+>", " ", m.group(2)).strip())
                   for m in re.finditer(
                       r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                       html, re.IGNORECASE | re.DOTALL)]
    for href, text in anchors:
        if ".pdf" not in (href or "").lower():
            continue
        url = urljoin(page_url, href)
        m = _WINDSOR_DATE_RE.search(url.replace("%20", " "))
        published, meeting = "", "Council"
        if m:
            published = f"{m.group('year')}-{m.group('month')}-{m.group('day')}"
            if m.group("committee"):
                meeting = m.group("committee").upper()
        # The anchor text plus the de-slugged filename is the best available
        # "title" — Windsor doesn't render item summaries server-side.
        fname = url.rsplit("/", 1)[-1]
        fname = re.sub(r"\.pdf.*$", "", fname, flags=re.I)
        fname = re.sub(r"[-_%]+", " ", fname)
        title = (text or "").strip()
        if fname.lower() not in title.lower():
            title = f"{title} ({fname})".strip()
        out.append({"title": title, "url": url,
                    "published": published, "meeting": meeting})
    return out


def collect_windsor(cma: str, base: str) -> list[dict]:
    html = _get(base)
    if not html:
        return []
    today = date.today()
    cutoff = (today - timedelta(days=WINDOW_BACK_DAYS * 4)).isoformat()
    articles = []
    for doc in parse_windsor_agenda_links(html, base):
        # Recent-only: the tool lists years of history
        if doc["published"] and doc["published"] < cutoff:
            continue
        signals = scan_title(doc["title"])
        if signals:
            articles.append(make_article(
                cma, doc["title"], doc["url"], doc["published"],
                doc["meeting"], signals))
    return articles


# ── Public entry point ───────────────────────────────────────────────────────

def collect_agenda_items(cmas: dict | None = None) -> list[dict]:
    """Weekly job: returns article-shaped dicts (discovery_source=
    'council_agenda') for every pilot-CMA agenda item that matches a
    project keyword. Per-CMA failures are logged and skipped."""
    cmas = cmas if cmas is not None else PILOT_CMAS
    articles: list[dict] = []
    for cma, cfg in cmas.items():
        try:
            if cfg["platform"] == "escribe":
                found = collect_escribe(cma, cfg["base"])
            elif cfg["platform"] == "windsor_opendata":
                found = collect_windsor(cma, cfg["base"])
            else:
                logger.warning("unknown council platform %r for %s",
                               cfg["platform"], cma)
                continue
            logger.info("council agendas: %s -> %d keyword hits", cma, len(found))
            articles.extend(found)
        except Exception as e:
            logger.warning("council agenda collection failed for %s: %s", cma, e)
    return articles


# ── Smoke mode ───────────────────────────────────────────────────────────────

def _smoke() -> None:
    """Print findings for one CMA (Ottawa) — no DB, no filter, network only."""
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    one = {"Ottawa": PILOT_CMAS["Ottawa"]}
    arts = collect_agenda_items(one)
    print(f"\nSMOKE (Ottawa): {len(arts)} agenda items with project signals")
    for a in arts[:20]:
        print(f"  [{a['published']}] {a['title'][:80]!r}")
        print(f"      {a['snippet'][:100]}")
    if len(arts) > 20:
        print(f"  ... and {len(arts) - 20} more")


if __name__ == "__main__":
    _smoke()
