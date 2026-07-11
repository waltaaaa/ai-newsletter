"""
Job posting monitor — detects hiring spikes as leading indicators for project activity.

Sources:
1. Government of Canada Job Bank Atom/RSS feed (free, structured, reliable) — PRIMARY.
   Verified live 2026-06-11:
   https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed?searchstring={kw}&fprov={PR}&sort=D
   - `searchstring` filters by keyword (server-side)
   - `fprov` filters by two-letter province code (server-side; verified with fprov=AB)
   - CMA-level filtering is NOT supported server-side — done client-side by parsing
     the "Location: City (PR)" line embedded in each entry's summary HTML.
   - Employer name is in the summary HTML ("Employer: ..."), not the author field.
2. Indeed RSS — REMOVED. Indeed discontinued its public RSS endpoint
   (https://ca.indeed.com/rss) years ago; it now returns an HTML page that
   feedparser silently parses as an empty feed. This was a dead external
   endpoint, not an adaptive-learning keyword, so the additive-only rule does
   not apply. Do not re-add without verifying a live feed exists.

Outputs:
- Hiring spike alerts linked to projects by employer name + location
- Aggregate hiring volume by CMA and sector for trend reporting

Does NOT track individual postings — aggregates by employer + geography.
"""
import feedparser
import json
import logging
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote_plus

try:
    import requests
except ImportError:  # pragma: no cover — requests is a pipeline dependency
    requests = None

logger = logging.getLogger(__name__)

# Job Bank Atom/RSS feed — keyword + province filtering server-side (verified live 2026-06-11).
# The old pattern (/jobsearch/jobsearch?...&rss=1) returns the HTML search page — the
# rss=1 param is ignored. The real feed endpoint is /jobsearch/feed/jobSearchRSSfeed.
JOB_BANK_RSS = ("https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"
                "?searchstring={keyword}&fprov={province}&sort=D")

# Browser User-Agent — Job Bank serves the feed fine to scripted clients, but use a
# real UA to avoid bot heuristics.
_HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}

# Per-process feed cache — the feed is keyed by (keyword, province), so all CMAs in
# the same province share one HTTP fetch per search term.
_FEED_CACHE = {}

# Sector-specific search terms mapped to NAICS keys
SECTOR_SEARCH_TERMS = {
    "oil_gas": ["pipeline construction", "oilfield", "drilling", "refinery operator", "LNG plant"],
    "mining": ["mine construction", "mining engineer", "mill operator", "exploration geologist"],
    "infrastructure": ["civil engineer construction", "highway construction", "bridge construction",
                       "water treatment plant", "transit construction"],
    "power_energy": ["solar installation", "wind turbine technician", "nuclear operator",
                     "electrical substation", "power plant construction"],
    "residential": ["residential construction", "condo construction", "housing development",
                    "framing carpenter", "residential project manager"],
    "commercial_mixed": ["commercial construction", "office tower construction",
                         "retail construction", "mixed-use development"],
    "manufacturing": ["manufacturing plant setup", "factory construction", "assembly line"],
    "healthcare": ["hospital construction", "healthcare facility", "long-term care construction"],
    "defence": ["military construction", "DND contract", "shipyard"],
}

# Job Bank-specific search terms (ADDITIVE — SECTOR_SEARCH_TERMS above is preserved
# unchanged). Job Bank's searchstring matches against job TITLES, so the Indeed-style
# multi-word phrases above return 0 server-side ("residential construction": 0 entries,
# verified live 2026-06-11). These occupation-style terms were yield-tested live:
# construction=100, machine operator=56, carpenter=22, welder=15, electrician=13 (ON);
# pipeline=9, drilling=1 (AB).
JOB_BANK_SECTOR_TERMS = {
    "oil_gas": ["pipeline", "drilling", "rig"],
    "mining": ["mining", "miner", "geologist"],
    "infrastructure": ["construction", "civil engineer", "heavy equipment operator"],
    "power_energy": ["electrician", "power", "wind turbine"],
    "residential": ["carpenter", "roofer", "plumber"],
    "commercial_mixed": ["construction manager", "construction estimator", "concrete"],
    "manufacturing": ["manufacturing", "assembler", "welder"],
    "healthcare": ["nurse", "long-term care", "hospital"],
    "defence": ["shipyard", "military", "defence"],
}

# Job Bank location strings within a CMA — postings list borough/suburb names
# ("North York (ON)", "Mississauga (ON)"), so the core city name alone misses most of
# the metro area. Matching is substring + accent-insensitive, scoped to the province
# feed, so short names cannot collide across provinces.
JOB_BANK_CMA_CITIES = {
    "Toronto": ["Toronto", "North York", "Scarborough", "Etobicoke", "East York",
                "Mississauga", "Brampton", "Vaughan", "Concord", "Woodbridge",
                "Markham", "Richmond Hill", "Pickering", "Ajax", "Whitby", "Oshawa",
                "Oakville"],
    "Montreal": ["Montréal", "Laval", "Longueuil", "Brossard", "Saint-Laurent",
                 "Dorval", "Anjou", "Terrebonne", "Pointe-Claire", "Boucherville"],
    "Vancouver": ["Vancouver", "Burnaby", "Surrey", "Richmond", "Coquitlam",
                  "New Westminster", "Delta", "Langley", "Maple Ridge"],
    "Calgary": ["Calgary", "Airdrie", "Chestermere", "Cochrane", "Okotoks"],
    "Edmonton": ["Edmonton", "Sherwood Park", "St. Albert", "Leduc", "Spruce Grove",
                 "Fort Saskatchewan", "Nisku", "Acheson"],
    "Ottawa": ["Ottawa", "Kanata", "Nepean", "Orléans", "Gloucester"],
    "Halifax": ["Halifax", "Dartmouth", "Bedford"],
    "St. John's": ["St. John's", "Mount Pearl", "Paradise"],
    "Fort McMurray": ["Fort McMurray", "Wood Buffalo"],
    "Saint John": ["Saint John", "Rothesay", "Quispamsis"],
    # Winnipeg, Saskatoon, Regina, Kitimat, Sudbury: core city name suffices
}

# Major CMAs to monitor — maps to CMA names and Job Bank region IDs
CMA_REGIONS = {
    "Toronto": {"province": "ON", "indeed_location": "Toronto, ON", "job_bank_region": "5535"},
    "Montreal": {"province": "QC", "indeed_location": "Montréal, QC", "job_bank_region": "24462"},
    "Vancouver": {"province": "BC", "indeed_location": "Vancouver, BC", "job_bank_region": "59933"},
    "Calgary": {"province": "AB", "indeed_location": "Calgary, AB", "job_bank_region": "48825"},
    "Edmonton": {"province": "AB", "indeed_location": "Edmonton, AB", "job_bank_region": "48835"},
    "Ottawa": {"province": "ON", "indeed_location": "Ottawa, ON", "job_bank_region": "35505"},
    "Winnipeg": {"province": "MB", "indeed_location": "Winnipeg, MB", "job_bank_region": "46602"},
    "Halifax": {"province": "NS", "indeed_location": "Halifax, NS", "job_bank_region": "12205"},
    "Saskatoon": {"province": "SK", "indeed_location": "Saskatoon, SK", "job_bank_region": "47725"},
    "Regina": {"province": "SK", "indeed_location": "Regina, SK", "job_bank_region": "47730"},
    "St. John's": {"province": "NL", "indeed_location": "St. John's, NL", "job_bank_region": "10010"},
    "Fort McMurray": {"province": "AB", "indeed_location": "Fort McMurray, AB", "job_bank_region": "48832"},
    "Kitimat": {"province": "BC", "indeed_location": "Kitimat, BC", "job_bank_region": "59"},
    "Saint John": {"province": "NB", "indeed_location": "Saint John, NB", "job_bank_region": "13310"},
    "Sudbury": {"province": "ON", "indeed_location": "Sudbury, ON", "job_bank_region": "35580"},
}

# Anomaly threshold — flag when a single employer's postings exceed this multiplier
# of their average over the past 4 weeks
SPIKE_THRESHOLD = 3.0

# Total wall-clock budget for one job-monitor run (red-team A#14: a full run
# issues up to ~270 sequential fetches x 30s timeout with no budget — a slow
# Job Bank day added unbounded wall-clock to Phase 4). Cached URLs are free;
# only live fetches burn budget. When exceeded, remaining fetches are skipped
# with a loud log line so a truncated week is visible, not silent.
JOB_MONITOR_BUDGET_SECONDS = int(os.getenv("JOB_MONITOR_BUDGET_SECONDS", "480"))


def _normalize_place(text):
    """Lowercase and strip accents for place-name comparison (Montréal == Montreal)."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _entry_location(entry):
    """Extract 'City (PR)' location string from a Job Bank entry's summary HTML."""
    m = re.search(r"Location:</strong>\s*([^<]+)", entry.get("summary", ""))
    return m.group(1).strip() if m else ""


def _fetch_feed(url):
    """
    Fetch and parse a feed URL with a browser User-Agent, with per-process caching.
    Returns a feedparser result. Raises on HTTP/network failure so the caller can log it.
    """
    if url in _FEED_CACHE:
        return _FEED_CACHE[url]

    if requests is not None:
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=30)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    else:
        # Fallback: let feedparser fetch directly (no custom UA control over redirects)
        feed = feedparser.parse(url, request_headers=_HTTP_HEADERS)

    # Red-team A#14: an HTTP-200 error/HTML page parses as a bozo feed with no
    # entries and used to be cached and consumed as a legitimate empty result.
    # Still cache it (refetching a broken URL for every CMA in the province is
    # worse), but log loudly so "0 postings" is distinguishable from "feed broken".
    if getattr(feed, "bozo", 0) and not feed.entries:
        print(f"[JOBS WARN] non-feed response cached for {url} "
              f"(bozo: {getattr(feed, 'bozo_exception', 'unknown')}) — "
              f"treating as 0 postings this run")

    _FEED_CACHE[url] = feed
    return feed


def fetch_job_postings(sector_key, cma_name, source="job_bank"):
    """
    Fetch recent job postings for a sector + CMA combination.
    Returns list of dicts with employer, title, location, date.

    `source` is retained for signature compatibility. "indeed" is dead (Indeed
    discontinued public RSS) — all values route to Job Bank.
    """
    cma = CMA_REGIONS.get(cma_name)
    if not cma:
        return []

    if source == "indeed":
        # Indeed public RSS was discontinued — silently returning empty feeds since
        # at least March. Route to Job Bank instead.
        print(f"[JOBS] source='indeed' is dead (Indeed discontinued public RSS) — using Job Bank for {cma_name}")

    # City names for client-side CMA filtering — CMA alias list when defined,
    # else the core city from the legacy indeed_location field ("Montréal, QC").
    cities = JOB_BANK_CMA_CITIES.get(
        cma_name, [cma["indeed_location"].split(",")[0].strip()]
    )
    cities_norm = [_normalize_place(c) for c in cities]

    # Job Bank title-style terms when available; fall back to the legacy
    # Indeed-style phrases for any sector not yet mapped.
    terms = JOB_BANK_SECTOR_TERMS.get(sector_key) or SECTOR_SEARCH_TERMS.get(sector_key, [])
    all_postings = []
    # Red-team A#12: the same posting routinely appears in two of a sector's
    # term feeds ("construction" + "heavy equipment operator") and double-counted
    # toward the >=5 spike trigger. Dedup by posting URL across this sector+CMA.
    seen_urls = set()

    for term in terms[:3]:  # Limit to 3 terms per sector to control fetch volume
        try:
            url = JOB_BANK_RSS.format(
                keyword=quote_plus(term),
                province=cma["province"],
            )
            feed = _fetch_feed(url)

            matched = 0
            for entry in feed.entries:
                link = entry.get("link", "")
                if link and link in seen_urls:
                    continue
                location_norm = _normalize_place(_entry_location(entry))
                # Province feed contains all cities — keep only this CMA's postings
                if not any(c in location_norm for c in cities_norm):
                    continue
                if link:
                    seen_urls.add(link)
                posting = {
                    "title": entry.get("title", ""),
                    "employer": _extract_employer(entry),
                    "location": cma_name,
                    "province": cma["province"],
                    "sector": sector_key,
                    "date": entry.get("published", "") or entry.get("updated", ""),
                    "url": entry.get("link", ""),
                }
                all_postings.append(posting)
                matched += 1
                if matched >= 20:  # Cap per term, matching the old per-feed limit
                    break

        except Exception as e:
            print(f"[JOBS] Failed to fetch job_bank feed for '{term}' in {cma_name} ({cma['province']}): {e}")

    return all_postings


def _extract_employer(entry):
    """Extract employer name from a job posting RSS entry."""
    # Job Bank puts the employer in the summary HTML: "<strong>Employer:</strong> Name<br/>"
    m = re.search(r"Employer:</strong>\s*([^<]+)", entry.get("summary", ""))
    if m:
        return m.group(1).strip()
    # Some feeds use the author field
    author = entry.get("author", "")
    if author:
        return author
    # Legacy Indeed format put employer in the title as "Job Title - Employer"
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Unknown"


def aggregate_by_employer(postings):
    """
    Aggregate postings by employer + location.
    Returns dict: {(employer, location, sector): count}
    """
    counts = defaultdict(int)
    for p in postings:
        key = (p["employer"], p["location"], p["sector"])
        counts[key] += 1
    return dict(counts)


def detect_hiring_spikes(current_counts, historical_counts):
    """
    Compare current week's employer counts against rolling 4-week average.
    Flag any employer whose posting count exceeds SPIKE_THRESHOLD x average.

    Args:
        current_counts: dict from aggregate_by_employer for this week
        historical_counts: list of dicts from previous 4 weeks

    Returns:
        list of spike alerts
    """
    averages = defaultdict(float)
    for week_counts in historical_counts:
        for key, count in week_counts.items():
            averages[key] += count
    for key in averages:
        averages[key] /= max(len(historical_counts), 1)

    spikes = []
    for key, count in current_counts.items():
        employer, location, sector = key
        avg = averages.get(key, 0)

        if count >= 5 and (avg == 0 or count >= avg * SPIKE_THRESHOLD):
            # 2026-06-11 red-team fix: with no prior baseline (avg == 0) a
            # "{N}.0x normal volume" claim is fabrication — there is no
            # "normal" yet. Keep the spike, but multiplier is None and the
            # signal says so explicitly.
            # Red-team A#12: Job Bank entries carry no published dates — counts
            # measure presence in the feed's newest-100 window, not weekly
            # posting volume. "posted N jobs" overstated; say what is measured.
            if avg == 0:
                multiplier = None
                signal = (f"{employer} has {count} active postings in {location} "
                          f"({sector}) (first tracked week — no prior baseline)")
            else:
                multiplier = round(count / max(avg, 1), 1)
                signal = (f"{employer} has {count} active postings in {location} "
                          f"({sector}) — {multiplier}x its tracked average")
            spikes.append({
                "employer": employer,
                "location": location,
                "sector": sector,
                "current_count": count,
                "average_count": round(avg, 1),
                "multiplier": multiplier,
                "signal": signal,
            })

    return sorted(spikes, key=lambda x: x["current_count"], reverse=True)


# CMA name -> two-letter province code, matching what projects.province
# actually stores (verified read-only 2026-06-11: AB, BC, MB, NB, NL, NS, NT,
# NU, ON, PE, QC, SK, YT, CA — two-letter codes, never full names or CMA
# names). 2026-06-11 red-team fix: link_spikes_to_projects used to bind the
# raw CMA name ("Toronto") to projects.province, so linking could NEVER match.
CMA_TO_PROVINCE = {
    "Toronto": "ON", "Ottawa": "ON", "Hamilton": "ON", "Kitchener": "ON",
    "London": "ON", "Oshawa": "ON", "St. Catharines": "ON", "Barrie": "ON",
    "Sudbury": "ON",
    "Montreal": "QC", "Quebec City": "QC",
    "Vancouver": "BC", "Victoria": "BC", "Kelowna": "BC", "Abbotsford": "BC",
    "Kitimat": "BC",
    "Calgary": "AB", "Edmonton": "AB", "Fort McMurray": "AB",
    "Winnipeg": "MB",
    "Saskatoon": "SK", "Regina": "SK",
    "Halifax": "NS",
    "St. John's": "NL",
    "Saint John": "NB",
}

# Employer names whose normalized form is one of these generic words must not
# be used as a LIKE match key (same false-link guard as procurement_monitor).
_GENERIC_EMPLOYER_WORDS = {
    "construction", "les", "groupe", "gestion", "canada", "inc",
    "ltd", "limited", "corp", "corporation", "company", "services",
    "group", "unknown",
}


def link_spikes_to_projects(spikes, conn):
    """
    Attempt to match hiring spikes to projects in the database by employer name
    and location/province.

    2026-06-11 red-team fix: the CMA name is mapped to the two-letter province
    code before binding (the old code bound "Toronto" against province codes —
    zero matches ever). The first-word LIKE clause was dropped at the same
    time: only the full employer name (>= 6 chars, not a generic word) is
    matched, against project name or proponent — false links are editorial
    fabrication, linking less is fine.
    """
    linked = []
    cursor = conn.cursor()

    for spike in spikes:
        province = CMA_TO_PROVINCE.get(spike.get("location", ""))
        employer = (spike.get("employer") or "").strip()
        if (not province or len(employer) < 6
                or employer.lower() in _GENERIC_EMPLOYER_WORDS):
            spike["linked_projects"] = []
            linked.append(spike)
            continue

        try:
            cursor.execute("""
                SELECT name, province, value, status, sector
                FROM projects
                WHERE (name LIKE ? OR proponent LIKE ?)
                AND province = ?
                ORDER BY value DESC
                LIMIT 3
            """, (
                f"%{employer}%",
                f"%{employer}%",
                province,
            ))

            matches = cursor.fetchall()
            spike["linked_projects"] = [
                {"name": m[0], "province": m[1], "value": m[2],
                 "status": m[3], "sector": m[4]}
                for m in matches
            ]
        except Exception as e:
            print(f"[JOBS] Project linking failed for {spike['employer']}: {e}")
            spike["linked_projects"] = []

        linked.append(spike)

    return linked


def _serialize_key(key):
    """Serialize a tuple key to a JSON-safe string."""
    return json.dumps(list(key))


def _deserialize_key(key_str):
    """Deserialize a JSON string back to a tuple key."""
    return tuple(json.loads(key_str))


def save_job_snapshot(conn, employer_counts, spikes, run_date):
    """
    Save weekly job posting snapshot to the database for historical comparison.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO job_snapshots (week_of, data, spikes)
        VALUES (?, ?, ?)
    """, (
        run_date,
        json.dumps({_serialize_key(k): v for k, v in employer_counts.items()}),
        json.dumps(spikes, default=str),
    ))
    conn.commit()


def get_historical_counts(conn, weeks=4):
    """Load previous N weeks of employer counts for spike detection."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data FROM job_snapshots
        ORDER BY week_of DESC
        LIMIT ?
    """, (weeks,))

    historical = []
    for row in cursor.fetchall():
        try:
            data = json.loads(row[0])
            counts = {}
            for k, v in data.items():
                try:
                    counts[_deserialize_key(k)] = v
                except (json.JSONDecodeError, TypeError):
                    pass
            historical.append(counts)
        except json.JSONDecodeError:
            pass

    return historical


def run_job_monitor(conn, sectors=None, cmas=None):
    """
    Main entry point. Fetch postings, aggregate, detect spikes, link to projects.

    Args:
        conn: SQLite connection
        sectors: list of sector keys to monitor (defaults to all)
        cmas: list of CMA names to monitor (defaults to all)

    Returns:
        dict with job_spikes, employer_counts, summary stats
    """
    sectors = sectors or list(SECTOR_SEARCH_TERMS.keys())
    cmas = cmas or list(CMA_REGIONS.keys())

    all_postings = []
    start = time.monotonic()
    budget_hit = False

    for sector in sectors:
        for cma in cmas:
            if time.monotonic() - start > JOB_MONITOR_BUDGET_SECONDS:
                budget_hit = True
                break
            postings = fetch_job_postings(sector, cma, source="job_bank")
            all_postings.extend(postings)
        if budget_hit:
            print(f"[JOBS WARN] time budget {JOB_MONITOR_BUDGET_SECONDS}s exhausted "
                  f"at sector '{sector}' — remaining sector/CMA combinations skipped "
                  f"this run (counts are partial; raise JOB_MONITOR_BUDGET_SECONDS "
                  f"if this recurs)")
            break

    print(f"[JOBS] Fetched {len(all_postings)} postings across {len(sectors)} sectors, {len(cmas)} CMAs")

    if not all_postings:
        print("[JOBS DEGRADED] 0 postings fetched across all sources — feeds dead or blocked; snapshot will be empty")

    current_counts = aggregate_by_employer(all_postings)
    historical = get_historical_counts(conn)
    spikes = detect_hiring_spikes(current_counts, historical)

    if spikes:
        spikes = link_spikes_to_projects(spikes, conn)
        print(f"[JOBS] Detected {len(spikes)} hiring spikes")
        for s in spikes[:5]:
            print(f"  → {s['signal']}")

    run_date = datetime.now().strftime("%Y-%m-%d")
    save_job_snapshot(conn, current_counts, spikes, run_date)

    # Warehouse instrumentation (RC-6): a zero-posting week means dead/blocked
    # feeds (see [JOBS DEGRADED] above), not a quiet labour market — record it
    # as a failed connection run. Never raises.
    try:
        from data_warehouse import record_run
        if not all_postings:
            _wh_status, _wh_err = "failed", "0 postings across all Job Bank feeds (dead or blocked)"
        elif budget_hit:
            _wh_status, _wh_err = "degraded", "time budget exhausted — partial sector/CMA coverage"
        else:
            _wh_status, _wh_err = "ok", ""
        record_run("job_monitor", _wh_status,
                   items_fetched=len(all_postings), items_saved=len(current_counts),
                   error=_wh_err, conn=conn)
    except Exception as _wh_e:
        print(f"[WAREHOUSE] job_monitor recording failed (non-critical): {_wh_e}")

    return {
        "job_postings_total": len(all_postings),
        "job_spikes": spikes,
        "job_employer_counts": current_counts,
        "job_sectors_monitored": sectors,
        "job_cmas_monitored": cmas,
    }
