"""
project_dedup.py — Multi-source project deduplication and merging.

Projects discovered by multiple queries or tiers are merged, not duplicated.
Multiple independent discoveries increase the project's confidence score.

Phase 5 adds weighted multi-factor scoring for DB-level dedup matching:
  - Deterministic ID matches (filing IDs, municipal app IDs)
  - Name similarity (exact normalized + fuzzy)
  - Organization matching via organizations table
  - Geography, sector, capex proximity
  - Shared evidence URLs
  - Contradiction penalties

Used by update_dashboard.py to deduplicate raw project mentions from:
  - Compound Gemini queries (Tier 2)
  - RSS feeds (Tier 4)
  - GDELT validation (Tier 3)
  - Perplexity gap-fill (Tier 3B)
  - Government registries (Tier 1)
"""

import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from project_schema import normalize_project_type, is_brownfield, STATUS_PROGRESSION
from url_utils import normalize_url, classify_source_authority, validate_url


# ══════════════════════════════════════════════════════════════════════════════
# WEIGHTED DEDUP SCORING (Phase 5)
# ══════════════════════════════════════════════════════════════════════════════

DEDUP_WEIGHTS = {
    'same_filing_id':           50,
    'same_municipal_app_id':    45,
    'exact_normalized_name':    25,
    'same_organization':        15,
    'same_municipality':        10,
    'same_sector':               5,
    'capex_within_20pct':        8,
    'fuzzy_name_above_85':      15,
    'shared_evidence_url':      20,
    'contradictory_province':  -20,
    'contradictory_sector':    -15,
    'semantic_similarity_above_90': 20,
    'semantic_similarity_above_80': 10,
}

DEDUP_THRESHOLDS = {
    'auto_match':   60,   # auto-merge
    'likely_match': 35,   # flag for Claude QA pass
    'likely_new':    0,   # below 35, treat as new
}


def _parse_value_numeric(val) -> float | None:
    """Parse a dollar value to a float in millions, or None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).upper().replace(',', '').replace('$', '').replace('C', '').strip()
    m = re.match(r'(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2) or 'M'
    if unit == 'B':
        n *= 1000
    elif unit == 'K':
        n /= 1000
    return n


def _values_within_pct(val1, val2, pct=0.20) -> bool:
    """Check if two dollar values are within pct of each other."""
    v1 = _parse_value_numeric(val1)
    v2 = _parse_value_numeric(val2)
    if v1 is None or v2 is None or v1 == 0 or v2 == 0:
        return False
    return abs(v1 - v2) / max(v1, v2) <= pct


def _resolve_org(proponent, conn):
    """Resolve a proponent string to a canonical org ID via the organizations table."""
    if not proponent or not conn:
        return None
    try:
        from db import resolve_organization
        return resolve_organization(conn, proponent)
    except Exception:
        return None


def _shared_evidence_urls(candidate, existing, conn) -> bool:
    """Check if candidate and existing share any evidence URLs."""
    if not conn:
        return False
    try:
        cand_id = candidate.get('rowid')
        exist_id = existing.get('rowid')
        if not cand_id or not exist_id:
            return False
        from db import get_evidence_for_project
        cand_urls = {r.get('url_normalized') for r in get_evidence_for_project(conn, cand_id)}
        exist_urls = {r.get('url_normalized') for r in get_evidence_for_project(conn, exist_id)}
        return bool(cand_urls & exist_urls)
    except Exception:
        return False


def _get_identifiers(project_id, conn) -> dict:
    """Get official identifiers from project_identifiers table."""
    if not conn or not project_id:
        return {}
    try:
        rows = conn.execute(
            "SELECT id_type, id_value FROM project_identifiers WHERE project_id = ?",
            (project_id,)
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


def compute_match_score(candidate: dict, existing: dict, conn=None) -> int:
    """Compute weighted match score between a candidate and existing project.

    Used for DB-level dedup when upserting projects that didn't match on norm_key.

    Args:
        candidate: new project dict (may have 'rowid' if already in DB)
        existing: existing project dict from DB (should have 'rowid')
        conn: SQLite connection for org/evidence/identifier lookups

    Returns:
        Integer score. ≥60 = auto-merge, 35-59 = likely match, <35 = likely new.
    """
    score = 0

    # Deterministic ID checks
    if conn:
        cand_ids = _get_identifiers(candidate.get('rowid'), conn)
        exist_ids = _get_identifiers(existing.get('rowid'), conn)
        for id_type in ('iaac', 'cer', 'provincial_ea', 'filing'):
            if cand_ids.get(id_type) and cand_ids[id_type] == exist_ids.get(id_type):
                score += DEDUP_WEIGHTS['same_filing_id']
                break
        for id_type in ('municipal_app', 'permit'):
            if cand_ids.get(id_type) and cand_ids[id_type] == exist_ids.get(id_type):
                score += DEDUP_WEIGHTS['same_municipal_app_id']
                break

    # Name similarity
    cand_key = candidate.get('norm_key', '')
    exist_key = existing.get('norm_key', '')
    if cand_key and exist_key:
        if cand_key == exist_key:
            score += DEDUP_WEIGHTS['exact_normalized_name']
        elif SequenceMatcher(None, cand_key, exist_key).ratio() >= 0.85:
            score += DEDUP_WEIGHTS['fuzzy_name_above_85']

    # Semantic similarity via NIM embeddings
    if os.environ.get('SEMANTIC_DEDUP_ENABLED', 'true').lower() == 'true':
        try:
            from embeddings_cache import get_similarity
            sim = get_similarity(
                f"{candidate.get('name', '')} {candidate.get('description', '')}",
                f"{existing.get('name', '')} {existing.get('description', '')}",
            )
            if sim >= 0.90:
                score += DEDUP_WEIGHTS['semantic_similarity_above_90']
            elif sim >= 0.80:
                score += DEDUP_WEIGHTS['semantic_similarity_above_80']
        except ImportError:
            pass
        except Exception as e:
            # NIM unavailable — dedup falls back to string matching
            pass

    # Organization match
    cand_org = _resolve_org(candidate.get('proponent'), conn)
    exist_org = _resolve_org(existing.get('proponent'), conn)
    if cand_org and exist_org and cand_org == exist_org:
        score += DEDUP_WEIGHTS['same_organization']

    # Geography
    cand_cma = (candidate.get('cma') or '').lower().strip()
    exist_cma = (existing.get('cma') or '').lower().strip()
    if cand_cma and cand_cma == exist_cma:
        score += DEDUP_WEIGHTS['same_municipality']

    # Sector
    cand_sector = (candidate.get('sector') or '').lower().strip()
    exist_sector = (existing.get('sector') or '').lower().strip()
    if cand_sector and exist_sector:
        if cand_sector == exist_sector:
            score += DEDUP_WEIGHTS['same_sector']
        else:
            score += DEDUP_WEIGHTS['contradictory_sector']

    # Province contradiction
    cand_prov = (candidate.get('province') or '').upper().strip()
    exist_prov = (existing.get('province') or '').upper().strip()
    if cand_prov and exist_prov and cand_prov != exist_prov:
        score += DEDUP_WEIGHTS['contradictory_province']

    # Capex proximity
    cand_val = candidate.get('value_millions') or candidate.get('value')
    exist_val = existing.get('value_millions') or existing.get('value')
    if _values_within_pct(cand_val, exist_val, 0.20):
        score += DEDUP_WEIGHTS['capex_within_20pct']

    # Shared evidence URLs
    if _shared_evidence_urls(candidate, existing, conn):
        score += DEDUP_WEIGHTS['shared_evidence_url']

    return score


# -- Filler words removed during key generation --
# NOTE: Building-type words (mall, centre, tower, facility, plant, station,
# terminal, hub, campus) are NOT filler — they carry semantic meaning for
# project identity. "Westbank Centre" and "Westbank Tower" are different projects.
_FILLER = {'project', 'development', 'the', 'new', 'proposed',
           'redevelopment', 'construction', 'of', 'and', 'for', 'in', 'at',
           'le', 'la', 'les', 'du', 'de', 'des',
           'expansion', 'renovation', 'retrofit', 'upgrade', 'replacement',
           'modernization', 'restoration', 'conversion', 'remediation'}
# NOTE: "phase" deliberately excluded — "LNG Canada" and "LNG Canada Phase 1"
# are distinct projects that must not merge.


def generate_dedup_key(project):
    """Generate a normalized deduplication key.

    Uses province + city + normalized name as the composite key.
    Handles minor naming variations (e.g., "Portage Place Redevelopment"
    vs "Portage Place Mall Redevelopment").
    """
    name = project.get("name", "")
    province = ""
    city = ""

    location = project.get("location", {})
    if isinstance(location, dict):
        province = (location.get("province") or "").upper().strip()
        city = (location.get("city") or "").lower().strip()
    # Fallback: flat province/cma fields (from compound_discovery output)
    if not province:
        province = (project.get("province") or "").upper().strip()
    if not city:
        city = (project.get("cma") or project.get("city") or "").lower().strip()

    # Normalize name: lowercase, remove punctuation, collapse whitespace
    name_norm = name.lower()
    name_norm = re.sub(r'[^a-z0-9\s]', '', name_norm)
    words = name_norm.split()
    words = [w for w in words if w not in _FILLER]
    name_norm = ' '.join(words)

    return f"{province}:{city}:{name_norm}"


def deduplicate_projects(raw_projects):
    """Deduplicate a list of raw project dicts from multiple discovery sources.

    Args:
        raw_projects: list of project dicts (from compound queries, RSS, GDELT, etc.)

    Returns:
        list of deduplicated project dicts with merged evidence and confidence scores
    """
    if not raw_projects:
        return []

    buckets = defaultdict(list)

    for project in raw_projects:
        key = generate_dedup_key(project)
        buckets[key].append(project)

    buckets = _union_buckets_by_shared_url(buckets)

    merged = []
    for key, group in buckets.items():
        if len(group) == 1:
            base = group[0]
            base["_dedup_count"] = 1
            base.setdefault("discovery_sources", [])
            _ensure_evidence(base)
            base["confidence"] = calculate_confidence(base)
            _enrich_taxonomy(base)
            merged.append(base)
        else:
            base = _select_best_base(group)
            _ensure_evidence(base)
            base.setdefault("discovery_sources", [])
            for other in group:
                if other is not base:
                    _merge_into(base, other)
            base["_dedup_count"] = len(group)
            base["confidence"] = calculate_confidence(base)
            _enrich_taxonomy(base)
            merged.append(base)

    return merged


def _collect_project_urls(project) -> set:
    """All specific (non-listing) URLs attached to a raw flat project."""
    try:
        from tools.dedup_projects_fuzzy import url_set, is_listing_url
    except ImportError:
        return set()
    urls = set()
    for arr in (project.get('_evidence'), project.get('evidence'), project.get('sources')):
        urls |= url_set(arr)
    su = project.get('source_url')
    if su and isinstance(su, str):
        urls.add(su.strip())
    return {u for u in urls if u and not is_listing_url(u)}


def _union_buckets_by_shared_url(buckets):
    """Second dedup pass: union exact-key buckets that cite the same article.

    One article extracted twice (within a run, or by the selective and RSS
    extractors) routinely yields name re-phrasings — "Deep Sky Carbon Removal
    Facility" vs "Deep Sky Carbon Removal — ENGIE Partnership" — that land in
    different exact-key buckets and become duplicate DB rows. A shared specific
    URL plus the strict guarded pair test (is_duplicate_pair: token overlap,
    contradiction checks on CMA/proponent/value/series-identifier) merges them
    here instead.
    """
    try:
        from tools.dedup_projects_fuzzy import (
            is_duplicate_pair, normalize_name)
    except ImportError:
        return buckets

    keys = list(buckets.keys())
    if len(keys) < 2:
        return buckets

    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    bucket_urls = {k: _collect_project_urls(buckets[k][0]) for k in keys}
    url_to_keys = defaultdict(list)
    for k in keys:
        prov = k.split(':', 1)[0]
        for u in bucket_urls[k]:
            url_to_keys[(prov, u)].append(k)

    for (_prov, _u), shared_keys in url_to_keys.items():
        if len(shared_keys) < 2:
            continue
        # Frequency guard: one article legitimately yields a handful of
        # extraction variants — a URL spanning many distinct-name buckets is
        # a roundup/listing page, not an identity signal.
        if len(shared_keys) > 6:
            continue
        for i in range(len(shared_keys)):
            for j in range(i + 1, len(shared_keys)):
                a, b = shared_keys[i], shared_keys[j]
                ra, rb = find(a), find(b)
                if ra == rb:
                    continue
                p1, p2 = buckets[a][0], buckets[b][0]
                n1 = normalize_name(p1.get('name', ''))
                n2 = normalize_name(p2.get('name', ''))
                if is_duplicate_pair(p1, p2, n1, n2,
                                     bucket_urls[a], bucket_urls[b],
                                     threshold=0.85):
                    parent[ra] = rb

    out = defaultdict(list)
    merged_away = 0
    for k in keys:
        root = find(k)
        if root != k:
            merged_away += 1
        out[root].extend(buckets[k])
    if merged_away:
        print(f"  [DEDUP] shared-URL pass merged {merged_away} same-article name variants")
    return out


def _ensure_evidence(project):
    """Ensure the project has an evidence list from ALL available source fields.

    Collects from: _evidence (grounding), source_url, sources array.
    Deduplicates by normalized URL. Enriches with authority classification.
    """
    if "evidence" not in project:
        project["evidence"] = []

    seen_urls = set()
    for e in project["evidence"]:
        norm = normalize_url(e.get("url", ""))
        if norm:
            seen_urls.add(norm)

    def _add(url, name="", date="", source_type="unknown"):
        if not url or not url.startswith("http"):
            return
        norm = normalize_url(url)
        if norm in seen_urls:
            return
        validation = validate_url(url)
        project["evidence"].append({
            "url": url,
            "url_normalized": norm,
            "name": name,
            "date": date,
            "source_type": source_type,
            "authority": classify_source_authority(url),
            "url_valid": validation["valid"],
            "is_known_source": validation.get("is_known_source", False),
        })
        seen_urls.add(norm)

    # From _evidence array (built by Gemini parser with grounding URLs)
    _ev = project.get("_evidence", [])
    for e in _ev:
        _add(e.get("url", ""), e.get("name", ""), e.get("date", ""),
             e.get("source_type", "gemini_grounding"))

    # Top-level source_url
    src_url = project.get("source_url", "")
    _add(src_url,
         project.get("source_title") or project.get("source_name", ""),
         project.get("date_reported", ""),
         "extracted")

    # Legacy 'sources' array
    for s in project.get("sources", []):
        if isinstance(s, dict):
            _add(s.get("url", ""), s.get("title", ""), "", "legacy")

    # Aggregate fields
    project["evidence_count"] = len(project["evidence"])
    project["has_government_source"] = any(
        e.get("authority") == "government" for e in project["evidence"]
    )
    project["has_known_source"] = any(
        e.get("is_known_source") for e in project["evidence"]
    )


def _enrich_taxonomy(project):
    """Ensure project has normalized project_type and is_brownfield fields."""
    ptype = normalize_project_type(project.get("project_type", ""))
    project["project_type"] = ptype
    project["is_brownfield"] = is_brownfield(ptype)


def _select_best_base(group):
    """Select the best base project from a group of duplicates.

    Prefers: government source > highest value > most detail.
    """
    def score(p):
        s = 0
        if p.get("value_millions") or p.get("value_numeric"):
            s += 1000
        if p.get("source_url"):
            s += 100
        if p.get("proponent"):
            s += 50
        if p.get("description"):
            s += 25
        # Prefer government discovery sources
        ds = p.get("discovery_source", "")
        if ds in ("federal_registry", "iaac", "bc_eao", "nrcan", "infra_canada"):
            s += 500
        return s

    return max(group, key=score)


def _merge_into(base, other):
    """Merge 'other' project data into 'base' -- NEVER lose evidence URLs."""
    # Collect existing normalized URLs to avoid duplicates
    base.setdefault("evidence", [])
    base_urls = set()
    for e in base["evidence"]:
        norm = normalize_url(e.get("url", ""))
        if norm:
            base_urls.add(norm)

    # Ensure other has evidence built
    _ensure_evidence(other)

    # Merge from other's evidence array
    for ev in other.get("evidence", []):
        url = ev.get("url", "")
        norm = normalize_url(url)
        if norm and norm not in base_urls:
            base["evidence"].append(ev)
            base_urls.add(norm)

    # Merge from other's _evidence array (from Gemini parser)
    for ev in other.get("_evidence", []):
        url = ev.get("url", "")
        norm = normalize_url(url)
        if norm and norm not in base_urls:
            validation = validate_url(url)
            base["evidence"].append({
                "url": url,
                "url_normalized": norm,
                "name": ev.get("name", ""),
                "date": ev.get("date", ""),
                "source_type": ev.get("source_type", "gemini_grounding"),
                "authority": classify_source_authority(url),
                "url_valid": validation["valid"],
                "is_known_source": validation.get("is_known_source", False),
            })
            base_urls.add(norm)

    # Merge from other's top-level source_url
    other_url = other.get("source_url", "")
    if other_url and other_url.startswith("http"):
        norm = normalize_url(other_url)
        if norm and norm not in base_urls:
            validation = validate_url(other_url)
            base["evidence"].append({
                "url": other_url,
                "url_normalized": norm,
                "name": other.get("source_title") or other.get("source_name", ""),
                "date": other.get("date_reported", ""),
                "source_type": "extracted",
                "authority": classify_source_authority(other_url),
                "url_valid": validation["valid"],
                "is_known_source": validation.get("is_known_source", False),
            })
            base_urls.add(norm)

    # Update aggregate fields
    base["evidence_count"] = len(base["evidence"])
    base["has_government_source"] = any(
        e.get("authority") == "government" for e in base["evidence"]
    )
    base["has_known_source"] = any(
        e.get("is_known_source") for e in base["evidence"]
    )

    # Use higher value if available
    other_val = other.get("value_millions") or other.get("value_numeric")
    base_val = base.get("value_millions") or base.get("value_numeric")
    try:
        if other_val and (not base_val or float(other_val) > float(base_val)):
            base["value_millions"] = other_val
            if other.get("value"):
                base["value"] = other["value"]
    except (ValueError, TypeError):
        pass

    # Update status if more advanced in lifecycle
    new_status = other.get("status", "Proposed")
    old_status = base.get("status", "Proposed")
    if STATUS_PROGRESSION.get(new_status, 0) > STATUS_PROGRESSION.get(old_status, 0):
        base["status"] = new_status

    # Fill missing fields from other
    for field in ["proponent", "description", "sector", "project_type",
                  "naics_2digit", "naics_code", "cma"]:
        if not base.get(field) and other.get(field):
            base[field] = other[field]

    # Track discovery sources
    source_tag = (other.get("_source_query_sector")
                  or other.get("discovery_source")
                  or other.get("_discovery_tier", "unknown"))
    if source_tag not in base["discovery_sources"]:
        base["discovery_sources"].append(source_tag)


# -- Government domain patterns for confidence scoring --
_GOV_DOMAINS = frozenset({
    'canada.ca', '.gc.ca', 'news.ontario', 'quebec.ca',
    'alberta.ca', 'gov.bc.ca', '.gov.mb.ca', 'novascotia.ca',
    'gnb.ca', 'gov.nl.ca', '.toronto.ca', '.montreal.ca',
    '.vancouver.ca', '.calgary.ca', '.edmonton.ca', '.ottawa.ca',
    '.winnipeg.ca', '.halifax.ca', 'saskatchewan.ca',
})


def calculate_confidence(project):
    """Calculate confidence score based on evidence quantity and quality.

    Score ranges from 0.0 to 1.0:
    - 0.1-0.3: Single source, unverified
    - 0.3-0.5: Multiple news sources
    - 0.5-0.7: Government source + news sources
    - 0.7-0.9: Multiple government sources + verified value
    - 0.9-1.0: Official registry + government + multiple news
    """
    evidence = project.get("evidence", [])
    sources = project.get("discovery_sources", [])

    score = 0.1  # base

    # Evidence count bonus
    evidence_count = len(evidence)
    score += min(evidence_count * 0.1, 0.3)

    # Government source bonus (use authority field if present, fallback to domain check)
    gov_count = 0
    for e in evidence:
        if e.get("authority") == "government":
            gov_count += 1
        else:
            url = (e.get("url") or "").lower()
            if any(d in url for d in _GOV_DOMAINS):
                gov_count += 1
    score += min(gov_count * 0.15, 0.3)

    # Value verified bonus
    val = project.get("value_millions") or project.get("value_numeric")
    try:
        if val and float(val) > 0:
            score += 0.1
    except (ValueError, TypeError):
        pass

    # Multiple discovery tiers bonus
    if len(sources) >= 3:
        score += 0.1
    elif len(sources) >= 2:
        score += 0.05

    return min(round(score, 2), 1.0)


# -- Test harness --
def run_dedup_tests():
    """Verify deduplication logic with test cases."""
    print("\n" + "=" * 60)
    print("  PROJECT DEDUP — VERIFICATION")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test 1: Same project, slightly different names
    test_projects = [
        {"name": "Portage Place Redevelopment",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 650,
         "source_url": "https://cbc.ca/1",
         "discovery_source": "gemini_compound"},
        {"name": "Portage Place Mall Redevelopment",
         "location": {"city": "winnipeg", "province": "MB"},
         "value_millions": 600,
         "source_url": "https://winnipegfreepress.com/2",
         "discovery_source": "rss_remediated"},
        {"name": "Portage Place Redevelopment Project",
         "location": {"city": "Winnipeg", "province": "MB"},
         "value_millions": 650,
         "source_url": "https://news.gov.mb.ca/3",
         "discovery_source": "federal_registry"},
    ]

    deduped = deduplicate_projects(test_projects)

    if len(deduped) == 1:
        passed += 1
        print(f"  [PASS] 3 mentions -> 1 project")
    else:
        failed += 1
        print(f"  [FAIL] Expected 1 project, got {len(deduped)}")

    if deduped and len(deduped[0].get("evidence", [])) == 3:
        passed += 1
        print(f"  [PASS] 3 evidence sources merged")
    else:
        failed += 1
        ev_count = len(deduped[0].get("evidence", [])) if deduped else 0
        print(f"  [FAIL] Expected 3 evidence sources, got {ev_count}")

    if deduped and (deduped[0].get("value_millions") or 0) == 650:
        passed += 1
        print(f"  [PASS] Highest value kept (650)")
    else:
        failed += 1
        print(f"  [FAIL] Wrong value: {deduped[0].get('value_millions') if deduped else 'N/A'}")

    if deduped and deduped[0].get("_dedup_count") == 3:
        passed += 1
        print(f"  [PASS] Dedup count = 3")
    else:
        failed += 1
        print(f"  [FAIL] Wrong dedup count")

    # Test 2: Different projects should NOT merge
    diff_projects = [
        {"name": "LNG Canada Phase 2",
         "location": {"city": "kitimat", "province": "BC"},
         "value_millions": 18000, "source_url": "https://a.com"},
        {"name": "Trans Mountain Expansion",
         "location": {"city": "burnaby", "province": "BC"},
         "value_millions": 30000, "source_url": "https://b.com"},
    ]
    deduped2 = deduplicate_projects(diff_projects)
    if len(deduped2) == 2:
        passed += 1
        print(f"  [PASS] 2 different projects stay separate")
    else:
        failed += 1
        print(f"  [FAIL] Expected 2 projects, got {len(deduped2)}")

    # Test 3: Taxonomy enrichment
    test_p = [{"name": "Test Retrofit",
               "province": "ON",
               "project_type": "deep_retrofit",
               "source_url": "https://x.com"}]
    deduped3 = deduplicate_projects(test_p)
    if deduped3 and deduped3[0]["project_type"] == "retrofit":
        passed += 1
        print(f"  [PASS] 'deep_retrofit' normalized to 'retrofit'")
    else:
        failed += 1
        print(f"  [FAIL] project_type not normalized")

    if deduped3 and deduped3[0]["is_brownfield"] is True:
        passed += 1
        print(f"  [PASS] is_brownfield = True for retrofit")
    else:
        failed += 1
        print(f"  [FAIL] is_brownfield not set correctly")

    # Test 4: Confidence scoring
    high_conf = {
        "name": "Test High",
        "province": "ON",
        "value_millions": 500,
        "evidence": [
            {"url": "https://infrastructure.canada.ca/1"},
            {"url": "https://cbc.ca/2"},
            {"url": "https://news.ontario.ca/3"},
        ],
        "discovery_sources": ["gemini_compound", "rss_remediated", "federal_registry"],
    }
    conf = calculate_confidence(high_conf)
    if conf >= 0.7:
        passed += 1
        print(f"  [PASS] High-confidence project scores {conf}")
    else:
        failed += 1
        print(f"  [FAIL] Expected >= 0.7, got {conf}")

    print(f"\n  {'=' * 60}")
    print(f"  RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print(f"  {'=' * 60}\n")
    return failed == 0
