"""
wayback.py — Wayback Machine integration for CAN-MACRO dashboard.

Provides URL archival via Save Page Now API and historical snapshot
retrieval via CDX API. Used to preserve source URLs and backfill
project history from archived pages.

Rate limit: 4 seconds between calls (Wayback Machine asks for this).

backfill_project_history() builds a complete statusHistory from archived
snapshots using CDX + Tavily Extract + Gemini Flash parsing.
"""

import json
import os
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests
from dotenv import load_dotenv

import service_health

load_dotenv()

# ── Config from .env ─────────────────────────────────────────────────────────

WAYBACK_ENABLED          = os.environ.get('WAYBACK_ENABLED', 'true').lower() == 'true'
WAYBACK_SAVE_ENABLED     = os.environ.get('WAYBACK_SAVE_ENABLED', 'true').lower() == 'true'
WAYBACK_BACKFILL_ENABLED = os.environ.get('WAYBACK_BACKFILL_ENABLED', 'true').lower() == 'true'
WAYBACK_MAX_SNAPSHOTS    = int(os.environ.get('WAYBACK_MAX_SNAPSHOTS_PER_PROJECT', '6'))
WAYBACK_RATE_LIMIT       = float(os.environ.get('WAYBACK_RATE_LIMIT_SECONDS', '4'))

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAN-Macro-Dashboard/2.0'
_HEADERS = {'User-Agent': _UA}

_CDX_API = 'https://web.archive.org/cdx/search/cdx'
_SAVE_API = 'https://web.archive.org/save/'
_AVAILABLE_API = 'https://archive.org/wayback/available'

_last_call_time = 0.0


def _rate_limit():
    """Enforce rate limit between Wayback API calls."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < WAYBACK_RATE_LIMIT:
        time.sleep(WAYBACK_RATE_LIMIT - elapsed)
    _last_call_time = time.time()


# ── Save Page Now ─────────────────────────────────────────────────────────────

def save_page(url: str) -> str | None:
    """
    Submit a URL to Wayback Machine's Save Page Now.
    Returns the archive URL if successful, None otherwise.
    Non-blocking — does not wait for archival to complete.
    """
    if not WAYBACK_ENABLED or not WAYBACK_SAVE_ENABLED:
        return None
    if not url or not url.startswith('http'):
        return None
    health = service_health.get()
    if not health.is_available("wayback"):
        return None

    _rate_limit()
    try:
        r = requests.get(
            f'{_SAVE_API}{url}',
            headers=_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        # Save Page Now returns a redirect to the archived page
        if r.status_code in (200, 301, 302):
            health.record_success("wayback")
            archive_url = r.headers.get('Content-Location') or r.headers.get('Location')
            if archive_url:
                if not archive_url.startswith('http'):
                    archive_url = f'https://web.archive.org{archive_url}'
                return archive_url
            # Sometimes the final URL after redirects IS the archive URL
            if 'web.archive.org' in r.url:
                return r.url
        health.record_failure("wayback", f"HTTP {r.status_code}")
        return None
    except Exception as e:
        health.record_failure("wayback", f"{type(e).__name__}: {e}")
        print(f"  [Wayback] save_page error for {url[:60]}: {type(e).__name__}")
        return None


# ── CDX API — Query all snapshots ─────────────────────────────────────────────

def query_cdx(
    url: str,
    match_type: str = 'exact',
    limit: int = 500,
    from_date: str = '',
    to_date: str = '',
) -> list[dict]:
    """
    Query the Wayback CDX API for all snapshots of a URL.

    Parameters
    ----------
    url : str
        The URL to search for.
    match_type : str
        'exact', 'prefix', 'host', or 'domain'.
    limit : int
        Maximum snapshots to return.
    from_date : str
        Start date in YYYYMMDD format (optional).
    to_date : str
        End date in YYYYMMDD format (optional).

    Returns
    -------
    list[dict] with keys: timestamp, original, mimetype, statuscode, digest, length, archive_url
    Sorted by timestamp ascending.
    """
    if not WAYBACK_ENABLED:
        return []
    health = service_health.get()
    if not health.is_available("wayback"):
        return []

    _rate_limit()
    params = {
        'url': url,
        'matchType': match_type,
        'output': 'json',
        'limit': str(limit),
        'fl': 'timestamp,original,mimetype,statuscode,digest,length',
    }
    if from_date:
        params['from'] = from_date
    if to_date:
        params['to'] = to_date

    try:
        r = requests.get(_CDX_API, params=params, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            health.record_failure("wayback", f"CDX HTTP {r.status_code}")
            return []
        data = r.json()
        if not data or len(data) < 2:
            return []

        health.record_success("wayback")

        # First row is header
        header = data[0]
        snapshots = []
        for row in data[1:]:
            entry = dict(zip(header, row))
            ts = entry.get('timestamp', '')
            orig = entry.get('original', url)
            entry['archive_url'] = f'https://web.archive.org/web/{ts}/{orig}'
            # Parse timestamp to ISO date
            if len(ts) >= 8:
                entry['date'] = f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}'
            else:
                entry['date'] = ''
            snapshots.append(entry)

        # Sort by timestamp ascending
        snapshots.sort(key=lambda s: s.get('timestamp', ''))
        return snapshots

    except Exception as e:
        health.record_failure("wayback", f"{type(e).__name__}: {e}")
        print(f"  [Wayback] CDX query error for {url[:60]}: {type(e).__name__}")
        return []


# ── Select key snapshots ──────────────────────────────────────────────────────

def select_key_snapshots(snapshots: list[dict], max_count: int = 0) -> list[dict]:
    """
    From a list of CDX snapshots, select the most important ones:
    - Earliest snapshot
    - One per calendar year
    - Most recent snapshot

    Parameters
    ----------
    snapshots : list[dict]
        Sorted CDX snapshots from query_cdx().
    max_count : int
        Maximum snapshots to return. 0 = use WAYBACK_MAX_SNAPSHOTS env var.

    Returns
    -------
    list[dict] — Selected snapshots in chronological order.
    """
    if not snapshots:
        return []

    if max_count <= 0:
        max_count = WAYBACK_MAX_SNAPSHOTS

    # Always include earliest and most recent
    selected = {snapshots[0]['timestamp']: snapshots[0]}
    if len(snapshots) > 1:
        selected[snapshots[-1]['timestamp']] = snapshots[-1]

    # One per calendar year
    seen_years = set()
    for snap in snapshots:
        year = snap.get('timestamp', '')[:4]
        if year and year not in seen_years:
            seen_years.add(year)
            selected[snap['timestamp']] = snap

    # Sort and limit
    result = sorted(selected.values(), key=lambda s: s.get('timestamp', ''))
    if len(result) > max_count:
        # Keep earliest, latest, and evenly spaced middle
        if max_count >= 2:
            step = max(1, (len(result) - 2) // (max_count - 2))
            middle = result[1:-1:step][:max_count - 2]
            result = [result[0]] + middle + [result[-1]]
        else:
            result = result[:max_count]

    return result


# ── Check URL availability ────────────────────────────────────────────────────

def check_available(url: str) -> dict | None:
    """
    Quick check if a URL has any Wayback Machine snapshots.
    Returns the closest snapshot info dict, or None.
    """
    if not WAYBACK_ENABLED:
        return None

    _rate_limit()
    try:
        r = requests.get(
            _AVAILABLE_API,
            params={'url': url},
            headers=_HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        closest = (data.get('archived_snapshots') or {}).get('closest')
        return closest if closest and closest.get('available') else None
    except Exception:
        return None


# ── Fetch archived page content ───────────────────────────────────────────────

def fetch_snapshot(archive_url: str, timeout: int = 20) -> str | None:
    """
    Fetch the content of a Wayback Machine snapshot.
    Returns the page text, or None on failure.
    """
    if not WAYBACK_ENABLED:
        return None

    _rate_limit()
    try:
        r = requests.get(archive_url, headers=_HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


# ── Project History Backfill ─────────────────────────────────────────────────

# Lazy-loaded clients (avoid import-time cost)
_gemini_client = None
_tavily_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            api_key = os.environ.get('GEMINI_API_KEY', '').strip()
            if api_key:
                _gemini_client = genai.Client(api_key=api_key)
        except ImportError:
            pass
    return _gemini_client

def _get_tavily():
    global _tavily_client
    if _tavily_client is None:
        try:
            from tavily import TavilyClient
            api_key = os.environ.get('TAVILY_API_KEY', '').strip()
            if api_key:
                _tavily_client = TavilyClient(api_key=api_key)
        except ImportError:
            pass
    return _tavily_client


_GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

_BACKFILL_PROMPT = """This is an archived snapshot of a page about '{project_name}' from {snapshot_date}.

Extract the project status AT THAT POINT IN TIME.

Return ONLY valid JSON (no markdown fences):
{{
  "status": "Proposed|Under Review|Approved|Under Construction|Paused|Expansion|Unknown",
  "detail": "2-3 sentences describing what the page says about the project at this date",
  "value": "Dollar value if mentioned, or empty string",
  "proponent": "Company or entity name if mentioned, or empty string",
  "timeline": "Any timeline or completion date mentioned, or empty string"
}}

Rules:
- Only state what the page explicitly says. If uncertain, set status to "Unknown".
- If the page is garbled, unreadable, or not about this project, return {{"status": "Unknown", "detail": "Page content not parseable", "value": "", "proponent": "", "timeline": ""}}.
- If the page indicates the project is Completed or Cancelled, set status to "Completed" or "Cancelled" so the caller can flag it for review.

Page content (first 6000 chars):
{page_text}"""


# Government registry URL patterns for prefix-based CDX searches
_REGISTRY_DOMAINS = [
    'iaac-aeic.gc.ca',
    'projects.eao.gov.bc.ca',
    'natural-resources.canada.ca',
    'infrastructure.gc.ca',
    'ceaa-acee.gc.ca',
]


def _extract_snapshot_text(archive_url: str) -> str:
    """Extract text from a Wayback snapshot using Tavily or direct fetch."""
    tc = _get_tavily()
    if tc:
        try:
            resp = tc.extract(urls=[archive_url])
            for r in (resp.get('results') or []):
                text = r.get('raw_content') or r.get('content') or ''
                if text:
                    return text[:6000]
        except Exception:
            pass
    # Fallback to direct fetch
    html = fetch_snapshot(archive_url)
    if html:
        # Strip HTML tags for basic text extraction
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:6000]
    return ''


def _parse_snapshot_with_gemini(project_name: str, snapshot_date: str, page_text: str) -> dict:
    """Use Gemini Flash to extract project status from a snapshot."""
    gc = _get_gemini()
    if not gc or not page_text:
        return {}
    try:
        from google.genai import types
        prompt = _BACKFILL_PROMPT.format(
            project_name=project_name,
            snapshot_date=snapshot_date,
            page_text=page_text[:6000],
        )
        response = gc.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                max_output_tokens=1024,
            )
        )
        raw = response.text.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  [Wayback] Gemini parse error: {type(e).__name__}")
        return {}


def _dedup_status_history(entries: list[dict]) -> list[dict]:
    """Dedup consecutive statusHistory entries with same status and no meaningful detail change."""
    if len(entries) <= 1:
        return entries
    result = [entries[0]]
    for entry in entries[1:]:
        prev = result[-1]
        if entry.get('status') == prev.get('status'):
            # Same status — only keep if detail is meaningfully different
            prev_detail = (prev.get('detail') or '').lower().strip()
            curr_detail = (entry.get('detail') or '').lower().strip()
            if prev_detail == curr_detail or len(curr_detail) < 20:
                continue  # skip duplicate
        result.append(entry)
    return result


def _search_gdelt_historical(project_name: str, province: str) -> list[str]:
    """
    Search GDELT for historical articles about a project, then check CDX
    for archived versions of those article URLs.

    Returns a list of archive_urls suitable for Tavily extraction.
    """
    urls = []
    try:
        from gdelt_monitor import _gdelt_search, _NETWORK_ERROR
        keyword = f'"{project_name}" Canada {province}'.strip()
        result = _gdelt_search(keyword, 'project', days_back=365*5, max_records=20)
        if result is _NETWORK_ERROR or not result:
            return []
        for art in result:
            art_url = art.get('url', '')
            if not art_url:
                continue
            snaps = query_cdx(art_url, match_type='exact', limit=5)
            if snaps:
                # Take the most recent archived version
                urls.append(snaps[-1].get('archive_url', ''))
    except Exception as e:
        print(f"  [Wayback] GDELT historical search error: {type(e).__name__}")
    return [u for u in urls if u]


def backfill_project_history(
    project_name: str,
    source_url: str,
    province: str = '',
    current_status: str = '',
    current_detail: str = '',
    today: str = '',
    max_snapshots: int = 0,
) -> dict:
    """
    Build a complete statusHistory from archived snapshots of a project's source URL.

    Process:
      1. Query CDX for source URL snapshots.
      2. Prefix-match for registry projects (IAAC, BC EAO, NRCan, etc.).
      3. Search GDELT for historical articles, check CDX for archived versions.
      4. Select key snapshots (earliest, one per year, most recent).
      5. Fetch snapshot text via Tavily Extract.
      6. Extract historical status using Gemini Flash.
      7. Build chronological statusHistory array.
      8. Dedup consecutive same-status entries.

    Parameters
    ----------
    project_name : str
        The project name (used for Gemini extraction prompts).
    source_url : str
        The primary source URL to query CDX for.
    province : str
        Province name (for GDELT search and logging).
    current_status : str
        Current project status (always appended as last entry).
    current_detail : str
        Current status detail text.
    today : str
        Today's date in ISO format.
    max_snapshots : int
        Maximum snapshots to process (0 = use WAYBACK_MAX_SNAPSHOTS).

    Returns
    -------
    dict with keys:
        history_backfilled: bool
        history_earliest_date: str (ISO date of earliest snapshot)
        statusHistory: list[dict] (chronological entries including current)
        snapshots_processed: int
        snapshots_skipped: int
    """
    if not WAYBACK_ENABLED or not WAYBACK_BACKFILL_ENABLED:
        return {'history_backfilled': False, 'statusHistory': [], 'snapshots_processed': 0, 'snapshots_skipped': 0}
    if not source_url or not source_url.startswith('http'):
        return {'history_backfilled': False, 'statusHistory': [], 'snapshots_processed': 0, 'snapshots_skipped': 0}
    if not today:
        today = datetime.utcnow().strftime('%Y-%m-%d')

    if max_snapshots <= 0:
        max_snapshots = WAYBACK_MAX_SNAPSHOTS

    # Step 1: Query CDX for source URL snapshots
    all_snapshots = query_cdx(source_url, match_type='exact', limit=200)

    # Step 2: For registry projects, also try prefix matching
    from urllib.parse import urlparse
    domain = urlparse(source_url).netloc
    if any(rd in domain for rd in _REGISTRY_DOMAINS):
        prefix_snaps = query_cdx(source_url, match_type='prefix', limit=100)
        # Merge, dedup by timestamp
        seen_ts = {s['timestamp'] for s in all_snapshots}
        for s in prefix_snaps:
            if s['timestamp'] not in seen_ts:
                all_snapshots.append(s)
                seen_ts.add(s['timestamp'])
        all_snapshots.sort(key=lambda s: s.get('timestamp', ''))

    # Step 3: Search GDELT for historical articles about this project
    if project_name and province:
        gdelt_archive_urls = _search_gdelt_historical(project_name, province)
        # Convert archive URLs into snapshot entries for processing
        seen_ts = {s['timestamp'] for s in all_snapshots}
        for archive_url in gdelt_archive_urls[:5]:
            # Extract timestamp from archive URL: /web/YYYYMMDDHHMMSS/
            ts_match = re.search(r'/web/(\d{14})/', archive_url)
            if ts_match and ts_match.group(1) not in seen_ts:
                ts = ts_match.group(1)
                all_snapshots.append({
                    'timestamp': ts,
                    'original': archive_url.split(ts + '/')[-1] if ts in archive_url else '',
                    'archive_url': archive_url,
                    'date': f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}',
                    'statuscode': '200',
                    'mimetype': 'text/html',
                    '_source': 'gdelt_historical',
                })
                seen_ts.add(ts)
        all_snapshots.sort(key=lambda s: s.get('timestamp', ''))

    if not all_snapshots:
        return {
            'history_backfilled': True,
            'history_earliest_date': today,
            'statusHistory': [],
            'snapshots_processed': 0,
            'snapshots_skipped': 0,
        }

    # Step 3: Select key snapshots
    selected = select_key_snapshots(all_snapshots, max_count=max_snapshots)
    # Filter to only status 200 HTML pages
    selected = [s for s in selected
                if s.get('statuscode', '200') == '200'
                and ('text/html' in s.get('mimetype', '') or not s.get('mimetype'))]

    if not selected:
        return {
            'history_backfilled': True,
            'history_earliest_date': today,
            'statusHistory': [],
            'snapshots_processed': 0,
            'snapshots_skipped': 0,
        }

    # Step 4-6: Extract text and parse each snapshot
    history_entries: list[dict] = []
    skipped = 0
    earliest_date = today

    for snap in selected:
        archive_url = snap.get('archive_url', '')
        snap_date = snap.get('date', '')
        if not archive_url or not snap_date:
            skipped += 1
            continue

        if snap_date < earliest_date:
            earliest_date = snap_date

        # Extract text
        text = _extract_snapshot_text(archive_url)
        if not text or len(text) < 50:
            skipped += 1
            continue

        # Parse with Gemini
        parsed = _parse_snapshot_with_gemini(project_name, snap_date, text)
        if not parsed or parsed.get('status') == 'Unknown':
            skipped += 1
            continue

        status = parsed.get('status', 'Unknown')

        # Flag Completed/Cancelled for manual review but don't add to history
        if status in ('Completed', 'Cancelled'):
            print(f"    [Backfill] {project_name[:40]}: {snap_date} -> {status} (flagged for review)")
            skipped += 1
            continue

        detail = (parsed.get('detail') or '').strip()
        entry = {
            'status': status,
            'date': snap_date,
            'detail': detail[:600] if detail else f'{project_name} was {status} as of {snap_date}.',
            'source': {
                'title': f'Wayback Machine snapshot ({snap_date})',
                'url': snap.get('original', source_url),
                'archive_url': archive_url,
                'type': 'archive',
                'verified': True,
                'verified_date': today,
            },
        }
        # Add value/proponent/timeline if extracted
        if parsed.get('value'):
            entry['extracted_value'] = parsed['value']
        if parsed.get('proponent'):
            entry['extracted_proponent'] = parsed['proponent']
        if parsed.get('timeline'):
            entry['extracted_timeline'] = parsed['timeline']

        history_entries.append(entry)

    # Step 7: Sort chronologically
    history_entries.sort(key=lambda e: e.get('date', ''))

    # Step 8: Dedup consecutive same-status entries
    history_entries = _dedup_status_history(history_entries)

    # Current status is always the LAST entry (appended by caller if needed)

    return {
        'history_backfilled': True,
        'history_earliest_date': earliest_date,
        'statusHistory': history_entries,
        'snapshots_processed': len(selected) - skipped,
        'snapshots_skipped': skipped,
    }
