"""
project_dedup.py — Multi-source project deduplication and merging.

Projects discovered by multiple queries or tiers are merged, not duplicated.
Multiple independent discoveries increase the project's confidence score.

Used by update_dashboard.py to deduplicate raw project mentions from:
  - Compound Gemini queries (Tier 2)
  - RSS feeds (Tier 4)
  - GDELT validation (Tier 3)
  - Perplexity gap-fill (Tier 3B)
  - Government registries (Tier 1)
"""

import re
from collections import defaultdict
from project_schema import normalize_project_type, is_brownfield, STATUS_PROGRESSION
from url_utils import normalize_url, classify_source_authority, validate_url


# -- Filler words removed during key generation --
_FILLER = {'project', 'development', 'the', 'new', 'proposed', 'phase',
           'redevelopment', 'construction', 'of', 'and', 'for', 'in', 'at',
           'le', 'la', 'les', 'du', 'de', 'des',
           # Building-type words that vary across sources
           'mall', 'centre', 'center', 'complex', 'building', 'tower',
           'facility', 'plant', 'station', 'terminal', 'hub', 'campus',
           'expansion', 'renovation', 'retrofit', 'upgrade', 'replacement',
           'modernization', 'restoration', 'conversion', 'remediation'}


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
