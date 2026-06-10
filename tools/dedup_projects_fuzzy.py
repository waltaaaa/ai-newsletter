"""
dedup_projects_fuzzy.py — Retroactive fuzzy project dedup with source consolidation.

The in-tree `dedup_audit.py` only catches exact (lowercased) name+province matches.
This tool catches the cases the user actually sees in the briefing:
  - "Site C Dam" vs "Site C Hydroelectric Dam" vs "Site C"
  - "Pathways Alliance CCS (Phase 1)" vs "Pathways Alliance Carbon Capture"
  - Same project recorded twice with different sources / discovery tiers

Match signals (within the same province):
  1. Shared evidence URL (very strong — same article cited)
  2. Normalized-name exact match after stripping decoration suffixes
  3. difflib SequenceMatcher ratio >= 0.85

When two projects merge:
  - sources, evidence, discovery_sources arrays consolidated unique-by-URL
  - statusHistory merged chronologically (de-duped by status+date+URL)
  - value: highest parsed_value wins
  - status: most-advanced wins (per STATUS_ORDER)
  - confidence: max wins
  - lastSeen: most recent wins; firstTracked: earliest wins
  - All "official_ids" set-merged

Usage (from backend/):
    python tools/dedup_projects_fuzzy.py                  # dry run, prints report
    python tools/dedup_projects_fuzzy.py --merge          # apply merges
    python tools/dedup_projects_fuzzy.py --report-only out.md   # write report markdown
    python tools/dedup_projects_fuzzy.py --threshold 0.88  # tighter fuzzy bar
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Constants ────────────────────────────────────────────────────────────────
# C4 (2026-06-08 audit): aligned with the live canonical statuses from
# normalize.py CANONICAL_STATUSES (Proposed / Under Review / Approved /
# Under Construction / Partially Complete / Complete / Cancelled / On Hold).
# Legacy aliases (Announced, Operational, Completed, …) are kept additively so
# the tool still ranks rows written before normalize.py became the single
# source of truth. Hold states rank with Under Construction (a paused build is
# not less advanced than one under construction) — merge precedence should
# never pick a hold over the same project's more advanced sibling row.
STATUS_ORDER = {
    'Cancelled': -1,
    'Rumoured': 0,
    'Proposed': 0, 'Announced': 0,
    'Under Review': 1,
    'Approved': 2,
    'Under Construction': 3, 'Paused': 3, 'Expansion': 3,
    'On Hold': 3, 'Suspended': 3,
    'Partially Complete': 4,
    'Operational': 4, 'In Service': 4,
    'Completed': 5, 'Complete': 5,
}

NAME_TO_CODE = {
    'British Columbia': 'BC', 'Alberta': 'AB', 'Saskatchewan': 'SK',
    'Manitoba': 'MB', 'Ontario': 'ON', 'Quebec': 'QC', 'Québec': 'QC',
    'New Brunswick': 'NB', 'Nova Scotia': 'NS',
    'Prince Edward Island': 'PE', 'PEI': 'PE',
    'Newfoundland and Labrador': 'NL', 'Newfoundland': 'NL',
    'Yukon': 'YT', 'Northwest Territories': 'NT', 'Nunavut': 'NU',
}

# Decoration suffixes/prefixes that don't change project identity.
_DECORATIONS = [
    r'\s*\(phase\s*\d+[a-z]?\)',
    r'\s*phase\s+\d+[a-z]?',
    r'\s*\(stage\s*\d+[a-z]?\)',
    r'\s*\(province[\s-]wide\b[^)]*\)',
    r'\s*\(canada[\s-]wide\b[^)]*\)',
    r'\s*\(\d{4}[-\s]\d{4}\)',
    r'\s*\(\d{4}\)',
    r'\s*[-–]\s*phase\s+\d+',
    r'\s*[-–]\s*stage\s+\d+',
    r'\s*\bproject\b\s*$',
    r'\s*\bfacility\b\s*$',
    r'\s*\bexpansion\b\s*$',
    r'\s*\bupgrade[s]?\b\s*$',
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _DECORATIONS]
_WS_RE = re.compile(r'\s+')
_PUNCT_RE = re.compile(r'[^\w\s]')


def norm_province(raw: str) -> str:
    if not raw:
        return ''
    raw = raw.strip()
    return NAME_TO_CODE.get(raw, raw[:2].upper())


def normalize_name(name: str) -> str:
    """Strip decorations, lowercase, collapse whitespace."""
    if not name:
        return ''
    s = name.lower().strip()
    for pat in _COMPILED:
        s = pat.sub('', s)
    s = _PUNCT_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s)
    return s.strip()


def parse_value(val) -> float:
    """Parse a value to dollars. Returns 0 on failure."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).upper().replace(',', '').replace('$', '').replace('C', '').strip()
    m = re.match(r'(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return 0
    n = float(m.group(1))
    unit = m.group(2) or 'M'
    if unit == 'B':
        n *= 1_000_000_000
    elif unit == 'M':
        n *= 1_000_000
    elif unit == 'K':
        n *= 1_000
    return n


def status_rank(status: str) -> int:
    return STATUS_ORDER.get((status or '').strip(), 0)


def url_set(items) -> set:
    """Extract a set of URLs from an evidence/sources array (handles both dict and str entries)."""
    out = set()
    if not items:
        return out
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            return out
    for it in (items or []):
        if isinstance(it, dict):
            u = it.get('url') or it.get('href') or ''
            if u:
                out.add(u.strip())
        elif isinstance(it, str) and it.startswith('http'):
            out.add(it.strip())
    return out


def merge_unique(*lists, key='url'):
    """Concatenate dict-arrays, dedup by `key`. Falls back to whole-dict equality for items missing the key."""
    seen = set()
    merged = []
    for lst in lists:
        if not lst:
            continue
        if isinstance(lst, str):
            try:
                lst = json.loads(lst)
            except Exception:
                continue
        for it in lst:
            if isinstance(it, dict):
                k = it.get(key) or json.dumps(it, sort_keys=True)
            else:
                k = str(it)
            if k in seen:
                continue
            seen.add(k)
            merged.append(it)
    return merged


def merge_status_history(*histories):
    """Merge statusHistory arrays. De-dup by (status, date, source_url).
    Order chronologically by date."""
    seen = set()
    merged = []
    for h in histories:
        if not h:
            continue
        if isinstance(h, str):
            try:
                h = json.loads(h)
            except Exception:
                continue
        for entry in h:
            if not isinstance(entry, dict):
                continue
            src = entry.get('source', {}) or {}
            url = src.get('url') if isinstance(src, dict) else ''
            k = (entry.get('status', ''), entry.get('date', ''), url)
            if k in seen:
                continue
            seen.add(k)
            merged.append(entry)
    merged.sort(key=lambda e: e.get('date', ''))
    return merged


def fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ── Main ─────────────────────────────────────────────────────────────────────

def load_projects(conn):
    """Load every project row as a dict."""
    conn.row_factory = __import__('sqlite3').Row
    rows = conn.execute("SELECT * FROM projects").fetchall()
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        for j in ('evidence', 'sources', 'discovery_sources', 'statusHistory',
                  'official_ids', 'tags', 'provinces_additional', 'anomalies'):
            v = d.get(j)
            if isinstance(v, str):
                try:
                    d[j] = json.loads(v) if v else []
                except Exception:
                    d[j] = []
        out.append(d)
    return out


_STOPWORDS = {
    'project', 'projects', 'expansion', 'phase', 'stage', 'the', 'and', 'of',
    'in', 'at', 'on', 'for', 'to', 'a', 'an', 'redevelopment', 'development',
    'plant', 'facility', 'centre', 'center', 'building', 'mine', 'plan',
    'corp', 'inc', 'ltd', 'ltee', 'limited',
}


def distinctive_tokens(s: str) -> set:
    """Tokens minus stopwords. Singletons that distinguish a project."""
    if not s:
        return set()
    toks = {t for t in s.split() if t and t not in _STOPWORDS and len(t) > 2}
    return toks


# Generic facility vocabulary: names made only of these (plus stopwords) describe
# a KIND of project, not a specific one. Provincial EA registries emit many rows
# literally named "Wastewater Treatment Plant" or "Manufacturing Facility" —
# identical names that are different real-world projects.
GENERIC_FACILITY_TERMS = {
    'wastewater', 'water', 'sewage', 'treatment', 'lagoon', 'sewer', 'storm',
    'manufacturing', 'processing', 'production', 'industrial',
    'subdivision', 'residential', 'housing', 'apartment', 'condo',
    'gravel', 'sand', 'quarry', 'pit', 'aggregate', 'extraction',
    'school', 'elementary', 'secondary', 'high',
    'bridge', 'highway', 'road', 'street', 'interchange', 'overpass',
    'hog', 'dairy', 'poultry', 'barn', 'feedlot', 'livestock', 'swine',
    'drainage', 'ditching', 'ditch', 'culvert', 'dyke', 'dike',
    'well', 'landfill', 'waste', 'transfer', 'station', 'recycling',
    'collection', 'forcemain', 'supply', 'system', 'systems', 'rural',
    'pipeline', 'pipelines', 'extension', 'extensions', 'connection',
    'trunk', 'provincial', 'upgrading',
    'solar', 'wind', 'farm', 'energy', 'power', 'substation', 'transmission',
    'warehouse', 'storage', 'distribution', 'terminal',
    'hospital', 'clinic', 'care', 'health',
    'upgrades', 'improvements', 'rehabilitation', 'replacement', 'renovation',
    'new', 'proposed', 'municipal', 'regional', 'community',
}


def is_generic_name(norm_name: str) -> bool:
    """True when a normalized name has no token that could identify a specific
    project — every distinctive token is generic facility vocabulary (or there
    are no distinctive tokens at all). Such names must not merge on name alone."""
    toks = distinctive_tokens(norm_name)
    if not toks:
        return True
    return all(t in GENERIC_FACILITY_TERMS for t in toks)


def has_corroboration(p1: dict, p2: dict, urls1: set = None, urls2: set = None) -> bool:
    """A second identity signal beyond the (generic) name: same proponent,
    same CMA, parsed values within 1.5x, or a shared non-listing evidence URL.

    urls1/urls2: pre-extracted (listing-filtered) URL sets when the caller has
    them — the live upsert path passes stripped project dicts without evidence,
    so deriving from p1/p2 alone would silently drop the URL signal there."""
    pr1 = (p1.get('proponent') or '').strip().lower()
    pr2 = (p2.get('proponent') or '').strip().lower()
    if pr1 and pr1 == pr2:
        return True
    cma1 = (p1.get('cma') or '').strip().lower()
    cma2 = (p2.get('cma') or '').strip().lower()
    if cma1 and cma1 == cma2:
        return True
    v1 = p1.get('parsed_value') or 0
    v2 = p2.get('parsed_value') or 0
    if v1 and v2 and max(v1, v2) / max(1, min(v1, v2)) <= 1.5:
        return True
    if urls1 is None:
        urls1 = {u for u in url_set(p1.get('evidence')) if not is_listing_url(u)}
    if urls2 is None:
        urls2 = {u for u in url_set(p2.get('evidence')) if not is_listing_url(u)}
    return bool(urls1 & urls2)


def is_listing_url(u: str) -> bool:
    """Detect URLs that are clearly multi-project listing pages, not specific project pages.

    C6: url_utils.is_listing_url is the canonical copy (shared with the live
    upsert's fuzzy fallback in db.py). The inline pattern list below is a
    fallback so this tool still runs standalone (python tools/dedup_projects_fuzzy.py
    from any cwd, where the backend root may not be on sys.path).
    """
    try:
        from url_utils import is_listing_url as _canonical
        return _canonical(u)
    except ImportError:
        pass
    if not u:
        return True
    u_low = u.lower()
    # Common patterns for listing/inventory pages
    return any(p in u_low for p in (
        '/major-projects-inventory',
        '/major_projects_inventory',
        '/projects-list',
        '/project-list',
        '/projects.aspx',
        '/registry/projects',
        '/inventory.pdf',
        '/mpi-',
        '/budget-',
        '/budget2',
        '/page=',
        '?search=',
    ))


_NUM_RE = re.compile(r'\b\d+\b')
# Tokens that signal a series identifier (district/zone N, line N, etc.)
_SERIES_PRECURSORS = {
    'zone', 'district', 'line', 'phase', 'stage', 'route', 'ward', 'subdivision',
    'block', 'parcel', 'lot', 'unit', 'sector', 'campus', 'building',
    'arrondissement', 'borough',
}


_CONNECTORS = {'de', 'of', 'the', 'la', 'le', 'du', 'des', 'and', 'a', 'an'}


def differing_series_identifier(n1: str, n2: str) -> bool:
    """True if both names contain a series precursor (zone/district/etc.) but
    the following non-connector identifier differs. Used to reject false-positive
    merges like 'Zone 5' vs 'Zone 8', or 'arrondissement de Saint-Laurent' vs
    'arrondissement de Verdun'."""
    tok1 = n1.split()
    tok2 = n2.split()
    for s in _SERIES_PRECURSORS:
        if s in tok1 and s in tok2:
            try:
                idx1 = tok1.index(s)
                idx2 = tok2.index(s)
            except ValueError:
                continue
            # Scan forward skipping connectors; find first content token after the precursor
            i1 = idx1 + 1
            while i1 < len(tok1) and tok1[i1] in _CONNECTORS:
                i1 += 1
            i2 = idx2 + 1
            while i2 < len(tok2) and tok2[i2] in _CONNECTORS:
                i2 += 1
            if i1 < len(tok1) and i2 < len(tok2):
                if tok1[i1] != tok2[i2]:
                    return True
    # Distinct number sets — "Highway 1 - 264 Street" vs "Highway 1 - Mt Lehman" share "1" but differ on extras
    nums1 = set(_NUM_RE.findall(n1))
    nums2 = set(_NUM_RE.findall(n2))
    if nums1 and nums2 and nums1 != nums2:
        # Both names have explicit numbers and they don't match
        # Only reject if neither is a strict subset (subset suggests "Phase 1" vs "Phases 1 & 2")
        if not (nums1 < nums2 or nums2 < nums1):
            return True
    return False


def is_duplicate_pair(p1: dict, p2: dict, n1: str, n2: str,
                       urls1: set, urls2: set, threshold: float) -> bool:
    """Strict pairwise duplicate test. STRICT — biased toward false-negative.

    Required: same province (caller enforces). Then ANY of:
      A) Identical normalized names.
      B) Normalized names with Jaccard token overlap (distinctive tokens) >= 0.85
         AND fuzzy ratio >= max(threshold, 0.92).
      C) Shared specific evidence/source URL AND Jaccard >= 0.7
         AND not contradicting on (proponent, value, CMA, series identifier).

    Generic-name gate: when the name carries no project-identifying token
    ("Wastewater Treatment Plant", "Manufacturing Facility"), name agreement —
    even exact — is not identity. Paths A and B then additionally require
    corroboration (same proponent/CMA, compatible values, or shared URL).
    """
    if not n1 or not n2:
        return False
    if n1 == n2:
        if is_generic_name(n1):
            return has_corroboration(p1, p2, urls1, urls2)
        return True

    # Series-identifier guard catches "Zone 5" vs "Zone 8" type pairs
    if differing_series_identifier(n1, n2):
        return False

    t1 = distinctive_tokens(n1)
    t2 = distinctive_tokens(n2)
    if not (t1 and t2):
        return False
    shared = t1 & t2
    if not shared:
        return False
    union_count = len(t1 | t2)
    jacc = len(shared) / max(1, union_count)

    r = fuzzy_match(n1, n2)
    has_shared_url = bool(urls1 & urls2)

    # B path — high token + char overlap
    path_b = jacc >= 0.85 and r >= max(threshold, 0.92)
    # Generic names can clear B on vocabulary alone — require a second signal.
    if path_b and is_generic_name(n1) and is_generic_name(n2):
        path_b = has_corroboration(p1, p2, urls1, urls2)

    # C path — shared specific URL with moderate name overlap
    # (the shared non-listing URL is itself the corroborating signal)
    path_c = has_shared_url and jacc >= 0.7

    if not (path_b or path_c):
        return False

    # Contradiction checks — kill the merge if attributes disagree
    cma1 = (p1.get('cma') or '').strip().lower()
    cma2 = (p2.get('cma') or '').strip().lower()
    if cma1 and cma2 and cma1 != cma2:
        return False
    pr1 = (p1.get('proponent') or '').strip().lower()
    pr2 = (p2.get('proponent') or '').strip().lower()
    if pr1 and pr2 and pr1 != pr2 and r < 0.95:
        return False
    # Same project should not span very different parsed_values
    v1 = p1.get('parsed_value') or 0
    v2 = p2.get('parsed_value') or 0
    if v1 and v2:
        ratio = max(v1, v2) / max(1, min(v1, v2))
        if ratio > 5.0:  # one is >5x the other
            return False

    return True


def find_clusters(projects, fuzzy_threshold=0.85):
    """Group projects into merge clusters via STRICT pairwise verification.

    A cluster is only valid if EVERY new addition is duplicate of the cluster
    seed (or whichever existing member is most similar). No transitive unions
    via near-misses — that's what caused the 571-row BC mega-cluster bug.

    Signals (combined, must all pass `is_duplicate_pair`):
      - within same province
      - normalized name fuzzy match >= threshold OR substring
      - shared distinctive token (non-stopword)
      - Jaccard token overlap >= 0.5
      - compatible proponents
    """
    n = len(projects)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_prov = defaultdict(list)
    by_norm = defaultdict(list)
    norm_cache = []
    url_cache = []
    for i, p in enumerate(projects):
        prov = norm_province(p.get('province', ''))
        norm = normalize_name(p.get('name', ''))
        urls = url_set(p.get('evidence')) | url_set(p.get('sources'))
        # Drop "listing" page URLs from the dedup signal — they group every project
        # listed on a Major Projects Inventory PDF together.
        urls = {u for u in urls if not is_listing_url(u)}
        norm_cache.append(norm)
        url_cache.append(urls)
        by_prov[prov].append(i)
        if norm:
            by_norm[(prov, norm)].append(i)

    # Pass 1 — exact normalized name within province. Exact match is safe ONLY
    # for names with an identifying token; generic registry names ("Wastewater
    # Treatment Plant" x N in MB) go through the full pairwise test, which
    # requires corroboration for them.
    for (prov, norm), idxs in by_norm.items():
        if len(idxs) > 1:
            base = idxs[0]
            generic = is_generic_name(norm)
            for j in idxs[1:]:
                if generic and not is_duplicate_pair(
                        projects[base], projects[j], norm, norm,
                        url_cache[base], url_cache[j], fuzzy_threshold):
                    continue
                union(base, j)

    # Pass 2 — STRICT pairwise (no transitive chaining).
    # Strategy: for each project, find at MOST ONE duplicate among others in the
    # same province. Use the strict `is_duplicate_pair` test. Once matched, mark
    # both as paired and don't extend the cluster further. Caps false-positive
    # blast radius.
    paired = set()
    for prov, idxs in by_prov.items():
        if len(idxs) < 2:
            continue
        # Pre-bucket by first distinctive token for fast lookup
        token_buckets = defaultdict(list)
        for i in idxs:
            tokens = {t for t in norm_cache[i].split() if len(t) >= 4 and t not in _STOPWORDS}
            for t in tokens:
                token_buckets[t].append(i)
        for i in idxs:
            if i in paired:
                continue
            ni = norm_cache[i]
            if not ni:
                continue
            # Candidate pool: any other project sharing a 4+ char distinctive token
            tokens_i = {t for t in ni.split() if len(t) >= 4 and t not in _STOPWORDS}
            candidates = set()
            for t in tokens_i:
                candidates.update(token_buckets[t])
            candidates.discard(i)
            best = None
            best_ratio = 0.0
            for j in candidates:
                if j in paired:
                    continue
                if find(i) == find(j):
                    continue
                nj = norm_cache[j]
                if not is_duplicate_pair(projects[i], projects[j], ni, nj,
                                         url_cache[i], url_cache[j], fuzzy_threshold):
                    continue
                r = fuzzy_match(ni, nj)
                if r > best_ratio:
                    best = j
                    best_ratio = r
            if best is not None:
                union(i, best)
                paired.add(i)
                paired.add(best)

    # Pass 3 — shared SPECIFIC URL with strict pair-test. URLs that pass
    # `is_listing_url` are already excluded above.
    url_to_idx = defaultdict(list)
    for i, urls in enumerate(url_cache):
        prov = norm_province(projects[i].get('province', ''))
        for u in urls:
            url_to_idx[(prov, u)].append(i)
    for (prov, u), idxs in url_to_idx.items():
        if len(idxs) < 2:
            continue
        for ai in range(len(idxs)):
            for bj in range(ai + 1, len(idxs)):
                a, b = idxs[ai], idxs[bj]
                if find(a) == find(b):
                    continue
                n1 = norm_cache[a]
                n2 = norm_cache[b]
                if is_duplicate_pair(projects[a], projects[b], n1, n2,
                                     url_cache[a], url_cache[b], fuzzy_threshold):
                    union(a, b)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    return [c for c in clusters.values() if len(c) > 1]


def pick_primary(cluster_idxs, projects):
    """Pick the primary project: most evidence, then highest value, then most-advanced status, then oldest firstTracked."""
    scored = []
    for i in cluster_idxs:
        p = projects[i]
        ev = len(p.get('evidence') or [])
        val = p.get('parsed_value') or parse_value(p.get('value', ''))
        sr = status_rank(p.get('status', ''))
        ft = p.get('firstTracked') or '9999-12-31'
        scored.append((ev, val, sr, -ord(ft[0] or 'z'), i))
    scored.sort(reverse=True)
    return scored[0][4]


def merge_cluster(cluster_idxs, projects):
    """Return (primary_dict, secondary_idxs_to_delete)."""
    pi = pick_primary(cluster_idxs, projects)
    primary = dict(projects[pi])
    others = [i for i in cluster_idxs if i != pi]
    for j in others:
        sec = projects[j]
        primary['evidence'] = merge_unique(primary.get('evidence'), sec.get('evidence'))
        primary['sources'] = merge_unique(primary.get('sources'), sec.get('sources'))

        # discovery_sources is sometimes a list of strings, sometimes dicts
        ds_a = primary.get('discovery_sources') or []
        ds_b = sec.get('discovery_sources') or []
        # If both single discovery_source strings, combine
        ds_combined = list(ds_a) if isinstance(ds_a, list) else [ds_a]
        ds_combined.extend(ds_b if isinstance(ds_b, list) else [ds_b])
        # Plus the legacy single discovery_source column
        for src_obj in (primary, sec):
            sds = src_obj.get('discovery_source')
            if sds and sds not in ds_combined:
                ds_combined.append(sds)
        # Dedup preserving order
        seen = set()
        ds_unique = []
        for x in ds_combined:
            if not x:
                continue
            key = x if isinstance(x, str) else json.dumps(x, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            ds_unique.append(x)
        primary['discovery_sources'] = ds_unique

        primary['statusHistory'] = merge_status_history(
            primary.get('statusHistory'), sec.get('statusHistory'))

        # Values
        pv = primary.get('parsed_value') or parse_value(primary.get('value', ''))
        sv = sec.get('parsed_value') or parse_value(sec.get('value', ''))
        if sv > pv:
            primary['value'] = sec.get('value') or primary.get('value')
            primary['parsed_value'] = sv

        # Status — most advanced
        if status_rank(sec.get('status', '')) > status_rank(primary.get('status', '')):
            primary['status'] = sec.get('status')

        # Confidence — max
        pc = float(primary.get('confidence') or 0)
        sc = float(sec.get('confidence') or 0)
        if sc > pc:
            primary['confidence'] = sc

        # Dates — preserve earliest firstTracked, latest lastSeen
        ft_a = primary.get('firstTracked') or '9999-12-31'
        ft_b = sec.get('firstTracked') or '9999-12-31'
        primary['firstTracked'] = min(ft_a, ft_b)
        ls_a = primary.get('lastSeen') or ''
        ls_b = sec.get('lastSeen') or ''
        primary['lastSeen'] = max(ls_a, ls_b)
        primary['lastUpdated'] = max(primary.get('lastUpdated', ''), sec.get('lastUpdated', ''))

        # Backfill missing scalar fields from secondary
        for f in ('proponent', 'description', 'cma', 'naics_code', 'naics_name',
                  'sector', 'project_type', 'completionDate'):
            if not primary.get(f) and sec.get(f):
                primary[f] = sec[f]

        # Merge official_ids
        oa = primary.get('official_ids') or []
        ob = sec.get('official_ids') or []
        if isinstance(oa, dict): oa = [oa]
        if isinstance(ob, dict): ob = [ob]
        oc = list(oa) + [x for x in ob if x not in oa]
        primary['official_ids'] = oc

        # Government source flag — sticky-OR
        primary['has_government_source'] = bool(
            primary.get('has_government_source') or sec.get('has_government_source'))
        primary['has_known_source'] = bool(
            primary.get('has_known_source') or sec.get('has_known_source'))

    # Refresh evidence_count
    primary['evidence_count'] = len(primary.get('evidence') or [])
    return primary, others


def serialize_for_db(p: dict) -> dict:
    """Convert nested lists/dicts back to JSON strings for SQLite TEXT columns."""
    out = dict(p)
    for j in ('evidence', 'sources', 'discovery_sources', 'statusHistory',
              'official_ids', 'tags', 'provinces_additional', 'anomalies'):
        v = out.get(j)
        if isinstance(v, (list, dict)):
            out[j] = json.dumps(v, ensure_ascii=False)
    return out


def write_back(conn, primary: dict, secondary_norm_keys: list[str]):
    """UPDATE primary row, DELETE secondary rows."""
    serialized = serialize_for_db(primary)
    cols = [
        'name', 'province', 'cma', 'sector', 'naics_code', 'naics_name',
        'value', 'status', 'confidence', 'project_type', 'is_brownfield',
        'proponent', 'description', 'completionDate', 'firstTracked',
        'lastUpdated', 'lastSeen', 'evidence', 'discovery_sources',
        'statusHistory', 'sources', 'tags', 'discovery_source',
        'has_government_source', 'has_known_source', 'evidence_count',
        'official_ids', 'parsed_value', 'provinces_additional',
        'anomalies',
    ]
    set_clause = ', '.join(f'{c} = ?' for c in cols)
    values = [serialized.get(c) for c in cols] + [primary['norm_key']]
    with conn:
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE norm_key = ?", values
        )
        for k in secondary_norm_keys:
            if k and k != primary['norm_key']:
                conn.execute("DELETE FROM projects WHERE norm_key = ?", (k,))


def run(args):
    import sqlite3
    conn = sqlite3.connect('dashboard.db')

    projects = load_projects(conn)
    print(f"Loaded {len(projects)} projects.")

    clusters = find_clusters(projects, fuzzy_threshold=args.threshold)
    print(f"Found {len(clusters)} duplicate clusters covering "
          f"{sum(len(c) for c in clusters)} projects "
          f"(would collapse to {len(clusters)}, removing "
          f"{sum(len(c) for c in clusters) - len(clusters)} rows).")

    if not clusters:
        return

    # Sort clusters by size descending for the report
    clusters.sort(key=lambda c: -len(c))

    # Distribution of cluster sizes
    from collections import Counter as _C
    size_dist = _C(len(c) for c in clusters)
    # Source consolidation impact
    cross_source = 0
    for cl in clusters:
        sources = set()
        for idx in cl:
            ds = projects[idx].get('discovery_source')
            if ds:
                sources.add(ds)
        if len(sources) > 1:
            cross_source += 1

    report_lines = [
        f"# Fuzzy Project Dedup Report",
        f"",
        f"_Generated: {datetime.utcnow().isoformat()}Z_",
        f"_Threshold: SequenceMatcher >= {args.threshold}_",
        f"",
        f"## Summary",
        f"",
        f"- Total projects scanned: **{len(projects)}**",
        f"- Duplicate clusters found: **{len(clusters)}**",
        f"- Projects in clusters: **{sum(len(c) for c in clusters)}**",
        f"- Rows that would be removed: **{sum(len(c) for c in clusters) - len(clusters)}**",
        f"- Clusters spanning multiple discovery sources: **{cross_source}** "
        f"(these are the primary value of the dedup — same project, different sources)",
        f"",
        f"### Cluster size distribution",
        f"",
        f"| Cluster size | # of clusters |",
        f"|--------------|---------------|",
    ]
    for sz in sorted(size_dist.keys()):
        report_lines.append(f"| {sz} rows | {size_dist[sz]} |")
    report_lines.extend([
        f"",
        f"## All clusters",
        f"",
    ])

    merges_to_apply = []
    for cluster in clusters:
        primary_dict, secondary_idxs = merge_cluster(cluster, projects)
        secondary_norm_keys = [projects[j]['norm_key'] for j in secondary_idxs]
        merges_to_apply.append((primary_dict, secondary_norm_keys))

        report_lines.append(f"### {primary_dict.get('province', '')} — {primary_dict.get('name', '')}")
        report_lines.append(f"")
        report_lines.append(f"- **Merging {len(cluster)} rows into 1**")
        for idx in cluster:
            p = projects[idx]
            ev = len(p.get('evidence') or [])
            ds = p.get('discovery_source', '?')
            val = p.get('value', '—')
            st = p.get('status', '?')
            report_lines.append(
                f"  - `{p.get('norm_key','')}` — name={p.get('name','')!r}, value={val}, "
                f"status={st}, ev={ev}, src={ds}"
            )
        merged_sources = primary_dict.get('discovery_sources') or []
        report_lines.append(
            f"- **Merged discovery_sources:** {merged_sources}"
        )
        report_lines.append(
            f"- **Merged evidence URLs:** {len(primary_dict.get('evidence') or [])}"
        )
        report_lines.append('')

    report = '\n'.join(report_lines)
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report written to {args.report}")
    else:
        # Print first 100 cluster summary lines to stdout
        print('\n'.join(report_lines[:200]))

    if not args.merge:
        print("\n[DRY RUN] No changes applied. Re-run with --merge to apply.")
        return

    # Safety: create a dashboard.db backup before any merge
    import shutil
    backup_path = f"dashboard.db.predupe_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
    print(f"\n[BACKUP] Creating safety backup at {backup_path}...")
    shutil.copy('dashboard.db', backup_path)

    print(f"\nApplying merges to {len(merges_to_apply)} clusters...")
    for i, (primary, secondary_keys) in enumerate(merges_to_apply, 1):
        try:
            write_back(conn, primary, secondary_keys)
        except Exception as e:
            print(f"  [ERROR] cluster {i} {primary.get('name', '')!r}: {e}")
        if i % 100 == 0:
            print(f"  ... {i}/{len(merges_to_apply)}")
    print(f"Done. {len(merges_to_apply)} clusters merged, "
          f"{sum(len(s) for _, s in merges_to_apply)} secondary rows removed.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--merge', action='store_true', help='Apply merges (default: dry run)')
    parser.add_argument('--report', metavar='PATH', help='Write markdown report to PATH')
    parser.add_argument('--threshold', type=float, default=0.85,
                        help='Fuzzy name-match threshold (0.0-1.0, default 0.85)')
    args = parser.parse_args()
    run(args)
