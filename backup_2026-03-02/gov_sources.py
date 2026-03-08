"""
gov_sources.py — Government data source fetchers for EconF Weekly

Currently provides:
  fetch_statcan_indicators()       — StatCan key economic indicators JSON feed
  save_statcan_indicators(db, ...) — Write snapshot to Firestore
"""

import re
import requests
from datetime import date

_STATCAN_IND_URL = "https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ.json"

_MONTHS = {
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
}


def _en(field) -> str:
    """Extract English string from a {en: ..., fr: ...} field, or cast to str."""
    if isinstance(field, dict):
        return str(field.get('en') or '')
    return str(field or '')


def _clean(s: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s or '')).strip()


def _infer_frequency(refper: str) -> str:
    lower = (refper or '').lower()
    if 'quarter' in lower:
        return 'Quarterly'
    if any(m in lower for m in _MONTHS):
        return 'Monthly'
    return 'Annual'


def _make_abs_url(path: str) -> str:
    if not path:
        return ''
    if path.startswith('http'):
        return path
    return f"https://www150.statcan.gc.ca{path}"


def _completeness(ind: dict) -> int:
    """Score an indicator record: higher = more data fields populated."""
    return sum([
        bool(ind.get('value')),
        bool(ind.get('change')),
        bool(ind.get('refPer')),
        bool(ind.get('releaseDate')),
        bool(ind.get('changeDetail')),
        bool(ind.get('tableUrl')),
        bool(ind.get('dailyUrl')),
    ])


def fetch_statcan_indicators() -> list[dict]:
    """
    Fetch StatCan key economic indicators from the JSON feed.
    Returns a list of indicator dicts. Returns [] (never raises) on failure.

    The feed contains geo-breakdown records (geo_code 0 = national, 1-13 = provinces/
    territories). We keep only geo_code == 0 (national level), then deduplicate by
    indicator name, keeping the record with the most populated fields.

    Each dict:
        name         str   — indicator name (English)
        value        str   — current value, HTML stripped
        change       str   — growth rate string, e.g. "+1.2%"
        arrow        int   — 1=up, 2=down, 0=flat/neutral
        changeDetail str   — human description, e.g. "rose 1.2%"
        refPer       str   — reference period, e.g. "January 2026"
        releaseDate  str   — ISO date of publication, e.g. "2026-02-14"
        frequency    str   — Monthly | Quarterly | Annual
        tableUrl     str   — link to StatCan data table
        dailyUrl     str   — link to The Daily release
        dailyTitle   str   — title of The Daily release
    """
    print("  Fetching StatCan key indicators...")
    try:
        resp = requests.get(
            _STATCAN_IND_URL, timeout=20,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; EconF/1.0)'}
        )
        resp.raise_for_status()
        raw_all = resp.json().get('results', {}).get('indicators', [])

        # ── Step 1: keep only national (geo_code == 0) records ──────────────
        raw_national = [r for r in raw_all if int(r.get('geo_code') or 0) == 0]
        print(f"  [StatCan] {len(raw_all)} raw records -> {len(raw_national)} national (geo_code=0)")

        # ── Step 2: parse each record ────────────────────────────────────────
        parsed: list[dict] = []
        for ind in raw_national:
            name = _clean(_en(ind.get('title')))
            if not name:
                continue  # skip rows with no name

            refper   = _clean(_en(ind.get('refper')))
            if not refper:
                continue  # skip section-header/footnote rows with no period

            value    = _clean(_en(ind.get('value')))
            rel_date = str(ind.get('release_date') or '')

            gr            = ind.get('growth_rate') or {}
            change        = _clean(_en(gr.get('growth')))
            arrow         = int(gr.get('arrow_direction') or 0)
            change_detail = _clean(_en(gr.get('details')))

            # Skip rows with neither a value nor a growth figure
            if not value and not change:
                continue

            daily_url   = _make_abs_url(_clean(_en(ind.get('daily_url'))))
            daily_title = _clean(_en(ind.get('daily_title')))

            source    = str(ind.get('source') or '').strip()
            table_url = (
                f"https://www150.statcan.gc.ca/t1/tbl1/en/table/0{source}-eng"
                if source else ''
            )

            parsed.append({
                'name':         name,
                'value':        value,
                'change':       change,
                'arrow':        arrow,
                'changeDetail': change_detail,
                'refPer':       refper,
                'releaseDate':  rel_date,
                'frequency':    _infer_frequency(refper),
                'tableUrl':     table_url,
                'dailyUrl':     daily_url,
                'dailyTitle':   daily_title,
            })

        # ── Step 3: deduplicate by name (keep most complete record) ──────────
        seen: dict[str, dict] = {}
        for ind in parsed:
            key = ind['name'].lower().strip()
            if key not in seen or _completeness(ind) > _completeness(seen[key]):
                seen[key] = ind
        indicators = list(seen.values())

        # ── Step 4: sanity-check count ───────────────────────────────────────
        n = len(indicators)
        if n > 75:
            # Count how many times each name appeared in the parsed list before dedup
            from collections import Counter
            name_counts = Counter(i['name'].lower().strip() for i in parsed)
            suspects = sorted(
                [(nm, cnt) for nm, cnt in name_counts.items() if cnt > 1],
                key=lambda x: -x[1]
            )
            print(f"  [StatCan] WARNING: {n} indicators after dedup (expected 65-75). Suspect duplicates:")
            for nm, cnt in suspects[:10]:
                print(f"    [{cnt}x] {nm!r}")
        elif n < 65:
            print(f"  [StatCan] WARNING: only {n} indicators after dedup (expected 65-75). Check feed.")

        _print_indicators(indicators)
        return indicators

    except Exception as e:
        print(f"  [WARN] StatCan indicators fetch failed: {e}")
        return []


def _print_indicators(indicators: list[dict]) -> None:
    """Print indicator names alphabetically (safe for all console encodings)."""
    n = len(indicators)
    print(f"  Fetched {n} StatCan indicators (national level):")
    for ind in sorted(indicators, key=lambda x: x['name']):
        safe = ind['name'].encode('ascii', errors='replace').decode('ascii')
        print(f"    {safe}")


def save_statcan_indicators(db, indicators: list[dict]) -> None:
    """
    Write StatCan indicators snapshot to Firestore statcan_indicators/latest.
    Overwrites on each run. Skips write if indicators list is empty (preserves cached data).
    Never raises.
    """
    if not indicators:
        print("  [StatCan] No fresh indicators — skipping Firestore write (cached data preserved).")
        return
    try:
        db.collection('statcan_indicators').document('latest').set({
            'updatedAt':  date.today().isoformat(),
            'indicators': indicators,
        })
        print(f"  [StatCan] Saved {len(indicators)} indicators to Firestore.")
    except Exception as e:
        print(f"  [StatCan] Firestore write failed (non-critical): {e}")
