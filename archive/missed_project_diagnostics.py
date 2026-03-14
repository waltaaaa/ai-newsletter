"""
missed_project_diagnostics.py -- Diagnose why a project was missed.

STEP_2K: For each user-submitted missed project, runs backward through the
discovery pipeline to identify which tier SHOULD have caught it and what
specific failure prevented detection. All checks are LOCAL (no Gemini queries).

Diagnostic categories:
  VOCABULARY_GAP — project terminology not in any compound query
  GEOGRAPHIC_GAP — city/region not covered by CMA or regional queries
  SECTOR_GAP — sector×province combo missing from compound queries
  SOURCE_GAP — source domain not in RSS feed list
  LANGUAGE_GAP — no French queries for this province×sector
  VALUE_BELOW_THRESHOLD — project value below province threshold
"""

import os
import re
import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Province name → code mapping
PROV_CODES = {
    "Ontario": "ON", "Quebec": "QC", "Alberta": "AB",
    "British Columbia": "BC", "Saskatchewan": "SK", "Manitoba": "MB",
    "Nova Scotia": "NS", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Prince Edward Island": "PE",
    "Yukon": "YT", "Northwest Territories": "NT", "Nunavut": "NU",
}

STOP_WORDS = {
    "the", "of", "and", "in", "at", "for", "a", "an", "to", "is", "on", "by",
    "project", "new", "phase", "development", "construction", "building",
    "centre", "center", "facility", "plant", "station", "system",
}


def diagnose_missed_project(submission):
    """Run full diagnostic on a missed project submission.

    All checks are local — reads compound_queries_final.json, rss_monitor.py
    config, etc. No Gemini queries used.

    Returns:
        dict with failure_categories, failure_details, recommended_improvements,
        confidence_in_diagnosis
    """
    name = submission.get("name", "")
    province = submission.get("province", "")
    city = submission.get("city", "")
    sector = submission.get("sector", "")
    value_m = submission.get("value_millions")
    source_url = submission.get("source_url", "")
    user_notes = submission.get("user_notes", "")

    diagnosis = {
        "failure_categories": [],
        "failure_details": [],
        "recommended_improvements": [],
        "confidence_in_diagnosis": 0.0,
    }

    # Load compound queries (cached)
    queries = _load_compound_queries()
    all_query_text = " ".join(q.get("query", "").lower() for q in queries)

    # ── Check 1: Vocabulary gap ──
    vocab = _check_vocabulary(name, all_query_text, sector)
    if vocab["gap_found"]:
        diagnosis["failure_categories"].append("VOCABULARY_GAP")
        diagnosis["failure_details"].append(vocab["detail"])
        diagnosis["recommended_improvements"].extend(vocab["improvements"])

    # ── Check 2: Geographic gap ──
    geo = _check_geographic(city, province, queries)
    if geo["gap_found"]:
        diagnosis["failure_categories"].append("GEOGRAPHIC_GAP")
        diagnosis["failure_details"].append(geo["detail"])
        diagnosis["recommended_improvements"].extend(geo["improvements"])

    # ── Check 3: Sector×Province gap ──
    sec = _check_sector_coverage(province, sector, queries)
    if sec["gap_found"]:
        diagnosis["failure_categories"].append("SECTOR_GAP")
        diagnosis["failure_details"].append(sec["detail"])
        diagnosis["recommended_improvements"].extend(sec["improvements"])

    # ── Check 4: Source gap ──
    if source_url:
        src = _check_source_coverage(source_url)
        if src["gap_found"]:
            diagnosis["failure_categories"].append("SOURCE_GAP")
            diagnosis["failure_details"].append(src["detail"])
            diagnosis["recommended_improvements"].extend(src["improvements"])

    # ── Check 5: Language gap ──
    if province in ("Quebec", "QC", "New Brunswick", "NB") or \
       (user_notes and any(w in user_notes.lower() for w in ["french", "français"])):
        lang = _check_language(province, sector, queries)
        if lang["gap_found"]:
            diagnosis["failure_categories"].append("LANGUAGE_GAP")
            diagnosis["failure_details"].append(lang["detail"])
            diagnosis["recommended_improvements"].extend(lang["improvements"])

    # ── Check 6: Value threshold ──
    if value_m is not None:
        thresh = _check_threshold(province, value_m, queries)
        if thresh["gap_found"]:
            diagnosis["failure_categories"].append("VALUE_BELOW_THRESHOLD")
            diagnosis["failure_details"].append(thresh["detail"])

    # Confidence in diagnosis
    n = len(diagnosis["failure_categories"])
    if n > 0:
        diagnosis["confidence_in_diagnosis"] = min(0.3 + 0.15 * n, 0.9)

    return diagnosis


def _load_compound_queries():
    """Load compound queries from JSON file."""
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "compound_queries_final.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _check_vocabulary(name, all_query_text, sector):
    """Check if project name terms appear in compound queries."""
    words = set(re.findall(r'[a-z]+', name.lower()))
    words -= STOP_WORDS

    missing = [w for w in words if len(w) > 3 and w not in all_query_text]

    if missing:
        return {
            "gap_found": True,
            "detail": f"Terms not in any compound query: {missing}",
            "improvements": [{
                "type": "vocabulary_addition",
                "terms": missing,
                "sector": sector,
                "detail": f"Add terms to query vocabulary for '{sector or 'general'}': {missing}",
                "target": "learned_vocabulary.json",
            }],
        }
    return {"gap_found": False}


def _check_geographic(city, province, queries):
    """Check if the city is covered by CMA or regional queries."""
    if not city:
        return {"gap_found": False}

    city_lower = city.lower()
    found = any(city_lower in q.get("query", "").lower() for q in queries)

    if not found:
        return {
            "gap_found": True,
            "detail": f"City '{city}' in {province} not found in any CMA or regional query.",
            "improvements": [{
                "type": "geographic_addition",
                "city": city,
                "province": province,
                "detail": f"Add '{city}' to CMA or regional cluster queries for {province}",
                "target": "compound_queries_final.json",
            }],
        }
    return {"gap_found": False}


def _check_sector_coverage(province, sector, queries):
    """Check if sector×province combination exists in compound queries."""
    if not sector or not province:
        return {"gap_found": False}

    sector_lower = sector.lower()
    prov_lower = province.lower()

    # Check if any query targets this sector + province
    found = any(
        sector_lower in q.get("sector", "").lower()
        and prov_lower in q.get("province", "").lower()
        for q in queries
    )

    # Also check if sector terms appear in province queries
    if not found:
        found = any(
            prov_lower in q.get("province", "").lower()
            and sector_lower in q.get("query", "").lower()
            for q in queries
        )

    if not found:
        return {
            "gap_found": True,
            "detail": f"No compound query covers sector '{sector}' in {province}.",
            "improvements": [{
                "type": "affinity_expansion",
                "province": province,
                "sector": sector,
                "detail": f"Add '{sector}' to {province} sector affinity list",
                "target": "compound_queries_final.json",
            }],
        }
    return {"gap_found": False}


def _check_source_coverage(source_url):
    """Check if source URL domain is in our RSS feed list."""
    try:
        domain = urlparse(source_url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return {"gap_found": False}

    if not domain:
        return {"gap_found": False}

    # Load RSS feed domains
    known_domains = _get_rss_domains()

    if domain not in known_domains:
        return {
            "gap_found": True,
            "detail": f"Source domain '{domain}' is not in our RSS feed list.",
            "improvements": [{
                "type": "feed_addition",
                "domain": domain,
                "detail": f"Investigate adding RSS feed for '{domain}'",
                "target": "learned_feeds.json",
            }],
        }
    return {"gap_found": False}


def _get_rss_domains():
    """Extract domains from RSS feed configuration."""
    domains = set()
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        rss_path = os.path.join(base, "rss_monitor.py")
        with open(rss_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract URLs from the FEEDS_CONFIG
        urls = re.findall(r"'url'\s*:\s*'(https?://[^']+)'", content)
        for url in urls:
            try:
                d = urlparse(url).netloc.lower()
                if d.startswith("www."):
                    d = d[4:]
                domains.add(d)
            except Exception:
                pass
    except Exception:
        pass
    return domains


def _check_language(province, sector, queries):
    """Check if French coverage exists for this province×sector."""
    fr_queries = [q for q in queries if q.get("language") == "fr"]

    if not fr_queries:
        return {
            "gap_found": True,
            "detail": f"No French-language queries found in the pipeline.",
            "improvements": [{
                "type": "french_sector_expansion",
                "province": province,
                "sector": sector or "general",
                "detail": f"Add French queries for {province}",
                "target": "compound_queries_final.json",
            }],
        }

    prov_lower = province.lower()
    if sector:
        sector_lower = sector.lower()
        found = any(
            prov_lower in q.get("province", "").lower()
            and sector_lower in q.get("query", "").lower()
            for q in fr_queries
        )
    else:
        found = any(prov_lower in q.get("province", "").lower() for q in fr_queries)

    if not found:
        return {
            "gap_found": True,
            "detail": f"No French query covers '{sector or 'any sector'}' in {province}.",
            "improvements": [{
                "type": "french_sector_expansion",
                "province": province,
                "sector": sector or "general",
                "detail": f"Add French query for '{sector or 'general'}' in {province}",
                "target": "compound_queries_final.json",
            }],
        }
    return {"gap_found": False}


def _check_threshold(province, value_m, queries):
    """Check if project value is below province query threshold."""
    # Extract thresholds from queries for this province
    prov_lower = province.lower()
    thresholds = []
    for q in queries:
        if prov_lower in q.get("province", "").lower():
            t = q.get("threshold_m")
            if t:
                thresholds.append(t)

    if not thresholds:
        return {"gap_found": False}

    min_threshold = min(thresholds)
    if value_m < min_threshold:
        return {
            "gap_found": True,
            "detail": (f"Project value (${value_m:.0f}M) is below minimum "
                       f"threshold (${min_threshold:.0f}M) for {province} queries."),
        }
    return {"gap_found": False}
