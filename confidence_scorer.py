"""
confidence_scorer.py — Source-aware confidence scoring for extracted projects.

Replaces the simpler evidence-count scoring in project_dedup.py with a
multi-factor score that accounts for source type, corroboration, field
completeness, value specificity, and validation status.

Factors:
  1. Source type (highest weight among all corroborating sources)
  2. Corroboration count (multiple independent sources)
  3. Field completeness (name + cost + status + location + proponent)
  4. Specificity (exact dollar figure vs vague language)
  5. Validation status (confirmed > corrected > flagged)

Editorial tiers:
  >= 0.80: confirmed    — include in main briefing
  >= 0.50: probable     — include with caveat
  >= 0.30: watch_list   — mention in supplementary section
  <  0.30: unverified   — hold for next week's corroboration

Integration:
  Extract -> Dedup -> Validate -> Detect Changes -> Score Confidence -> Upsert -> Write
"""

import logging
import re
from urllib.parse import urlparse

from pipeline_config import CONFIDENCE_SCORING_ENABLED

logger = logging.getLogger(__name__)

# Source type weights (higher = more reliable)
SOURCE_WEIGHTS = {
    "government_api": 1.0,
    "government_press": 0.95,
    "regulatory_filing": 0.90,
    "securities_filing": 0.90,
    "wire_service": 0.75,
    "national_media": 0.70,
    "industry_publication": 0.70,
    "local_media": 0.50,
    "blog_other": 0.30,
    "unknown": 0.40,
}

# Domain-to-source-type mapping for automatic classification
_DOMAIN_MAP = {
    # Government
    "canada.ca": "government_press",
    "gc.ca": "government_press",
    "ontario.ca": "government_press",
    "quebec.ca": "government_press",
    "alberta.ca": "government_press",
    "gov.bc.ca": "government_press",
    "saskatchewan.ca": "government_press",
    "gov.mb.ca": "government_press",
    "novascotia.ca": "government_press",
    "gnb.ca": "government_press",
    "gov.nl.ca": "government_press",
    # Regulatory
    "iaac-aeic.gc.ca": "regulatory_filing",
    "cer-rec.gc.ca": "regulatory_filing",
    "aer.ca": "regulatory_filing",
    "sedar.com": "securities_filing",
    "sedarplus.ca": "securities_filing",
    # Wire services
    "reuters.com": "wire_service",
    "bloomberg.com": "wire_service",
    "bnnbloomberg.ca": "wire_service",
    # National media
    "theglobeandmail.com": "national_media",
    "nationalpost.com": "national_media",
    "cbc.ca": "national_media",
    "financialpost.com": "national_media",
    # Industry
    "jwnenergy.com": "industry_publication",
    "dailyoilbulletin.com": "industry_publication",
    "mining.com": "industry_publication",
    "renewableenergyworld.com": "industry_publication",
    "constructconnect.com": "industry_publication",
    # Local media
    "vancouversun.com": "local_media",
    "calgaryherald.com": "local_media",
    "edmontonjournal.com": "local_media",
    "thestar.com": "local_media",
    "montrealgazette.com": "local_media",
    "winnipegfreepress.com": "local_media",
    "halifaxexaminer.ca": "local_media",
}


def classify_source_type(url: str) -> str:
    """Classify a URL into a source type category."""
    if not url:
        return "unknown"
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return "unknown"

    # Check exact domain match
    if domain in _DOMAIN_MAP:
        return _DOMAIN_MAP[domain]

    # Check suffix matches (e.g., "news.ontario.ca" matches "ontario.ca")
    for pattern, stype in _DOMAIN_MAP.items():
        if domain.endswith(pattern):
            return stype

    return "unknown"


def _best_source_weight(project: dict) -> tuple[float, str]:
    """Find the highest source weight among all evidence URLs."""
    best_weight = 0.0
    best_type = "unknown"

    # Check source_type field (from gov_api_ingest)
    st = project.get("source_type", "")
    if st in SOURCE_WEIGHTS:
        w = SOURCE_WEIGHTS[st]
        if w > best_weight:
            best_weight = w
            best_type = st

    # Check evidence array
    for ev in project.get("evidence", []):
        url = ev.get("url", "")
        st = classify_source_type(url)
        w = SOURCE_WEIGHTS.get(st, 0.30)
        if w > best_weight:
            best_weight = w
            best_type = st

        # Also check authority field from existing dedup
        auth = ev.get("authority", "")
        if auth == "government" and best_weight < 0.95:
            best_weight = 0.95
            best_type = "government_press"

    # Check top-level source_url
    src_url = project.get("source_url", "")
    if src_url:
        st = classify_source_type(src_url)
        w = SOURCE_WEIGHTS.get(st, 0.30)
        if w > best_weight:
            best_weight = w
            best_type = st

    return best_weight, best_type


def _distinct_evidence_count(evidence: list) -> int:
    """G12 (quality-pass-1.4): count evidence entries with distinct content.

    Works off the projects.evidence JSON array (this scorer runs pre-upsert,
    before the evidence table exists for the project). An entry is a
    republication — and contributes ZERO to corroboration — when its
    normalized URL was already seen, or its normalized title/snippet content
    matches an earlier entry. URLs are never dropped; they just don't double-count.
    """
    seen_urls: set[str] = set()
    seen_content: set[str] = set()
    distinct = 0
    for ev in evidence or []:
        if isinstance(ev, str):
            url, content = ev.strip().lower(), ""
        elif isinstance(ev, dict):
            url = (ev.get("url_normalized") or ev.get("url") or "").strip().lower()
            title = (ev.get("title") or ev.get("name") or "")
            snippet = (ev.get("snippet") or ev.get("summary") or "")
            content = re.sub(r"\s+", " ", f"{title} {snippet}".lower()).strip()
        else:
            continue
        is_dup = (bool(url) and url in seen_urls) or \
                 (bool(content) and content in seen_content)
        if url:
            seen_urls.add(url)
        if content:
            seen_content.add(content)
        if not is_dup:
            distinct += 1
    return distinct


def _corroboration_score(project: dict) -> float:
    """Score based on number of independent sources.

    G12: republished/duplicate-content evidence counts zero — only distinct
    URLs/content corroborate.
    """
    evidence = project.get("evidence", [])
    sources = project.get("discovery_sources", [])
    count = max(_distinct_evidence_count(evidence), len({str(s) for s in sources}), 1)

    if count >= 5:
        return 0.20
    if count >= 3:
        return 0.15
    if count >= 2:
        return 0.10
    return 0.0


def _completeness_score(project: dict) -> float:
    """Score based on field completeness."""
    score = 0.0
    if project.get("name") or project.get("project_name"):
        score += 0.04
    if project.get("province"):
        score += 0.03
    if project.get("cma") or project.get("city"):
        score += 0.02
    if project.get("sector"):
        score += 0.02
    if project.get("proponent"):
        score += 0.02
    if project.get("status") and project["status"] != "Proposed":
        score += 0.02
    if project.get("description"):
        score += 0.01

    # Cost field — with specificity bonus
    val = project.get("value") or project.get("estimated_value") or ""
    val_str = str(val).strip().lower()
    if val_str and val_str not in ("not disclosed", "n/a", "unknown", ""):
        score += 0.04
        # Exact figure bonus (has digits)
        if re.search(r'\d', val_str):
            score += 0.03
    return score


def _validation_score(project: dict) -> float:
    """Score based on Claude validation status (Phase 7)."""
    status = project.get("_validation_status", "")
    if status == "confirmed":
        return 0.10
    if status == "corrected":
        return 0.05
    if status == "flagged":
        return -0.10
    return 0.0  # not validated


def compute_confidence(project: dict) -> float:
    """Compute confidence score for a project.

    Returns: float 0.0-1.0
    """
    # Base score from best source
    source_weight, _ = _best_source_weight(project)
    base = source_weight * 0.45  # source type is ~45% of score

    # Add factors
    score = base
    score += _corroboration_score(project)
    score += _completeness_score(project)
    score += _validation_score(project)

    return round(min(max(score, 0.0), 1.0), 3)


def assign_confidence_tier(score: float) -> str:
    """Map score to editorial tier."""
    if score >= 0.80:
        return "confirmed"
    if score >= 0.50:
        return "probable"
    if score >= 0.30:
        return "watch_list"
    return "unverified"


def score_projects(projects: list[dict]) -> list[dict]:
    """Score and tier a list of projects in-place.

    Adds fields: confidence_score, confidence_tier, best_source_type, source_count.
    """
    if not CONFIDENCE_SCORING_ENABLED:
        return projects

    for proj in projects:
        score = compute_confidence(proj)
        _, best_type = _best_source_weight(proj)

        proj["confidence_score"] = score
        proj["confidence_tier"] = assign_confidence_tier(score)
        proj["best_source_type"] = best_type
        proj["source_count"] = max(
            len(proj.get("evidence", [])),
            len(proj.get("discovery_sources", [])),
            1,
        )

    # Log tier distribution
    tiers = {}
    for p in projects:
        t = p.get("confidence_tier", "unscored")
        tiers[t] = tiers.get(t, 0) + 1
    logger.info(f"Confidence scoring: {tiers}")

    return projects
