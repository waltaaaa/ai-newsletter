"""
project_schema.py -- Project document schema and type taxonomy.

Defines the project type taxonomy (greenfield vs brownfield subtypes),
NAICS-aligned sector categories, status progression, and build_project_document()
which enforces the hard gate: no verifiable source URL = no Firestore write.
"""

import logging

logger = logging.getLogger(__name__)

# -- Project type taxonomy --
PROJECT_TYPES = {
    # Greenfield
    "greenfield":           "New construction on previously unused or cleared land",
    # Brownfield subtypes
    "redevelopment":        "Demolish and rebuild on same previously developed site",
    "adaptive_reuse":       "Convert building to fundamentally different use",
    "major_renovation":     "Significant upgrade retaining original structure",
    "expansion":            "Addition to existing facility",
    "retrofit":             "Structural or systems upgrade to existing facility",
    "restoration":          "Heritage or historical rehabilitation",
    "remediation":          "Environmental cleanup, with or without redevelopment",
    "conversion":           "Use-type change (e.g., office to residential)",
    "modernization":        "Technology or systems upgrade to existing facility",
    "decommission_replace": "Shut down old facility, build replacement",
}

BROWNFIELD_TYPES = {
    "redevelopment", "adaptive_reuse", "major_renovation", "expansion",
    "retrofit", "restoration", "remediation", "conversion",
    "modernization", "decommission_replace",
}

# -- NAICS-aligned sector categories --
SECTORS = {
    "oil_gas":              "Oil, Gas & Hydrogen",
    "mining":               "Mining & Critical Minerals",
    "infrastructure":       "Civil Infrastructure",
    "power_energy":         "Power Generation, Transmission & Clean Energy",
    "manufacturing":        "Manufacturing & Industrial",
    "transport_logistics":  "Ports, Airports & Logistics",
    "healthcare":           "Healthcare & Life Sciences",
    "education":            "Education & Research",
    "residential":          "Residential & Housing Development",
    "commercial_mixed":     "Commercial & Mixed-Use Development",
    "agriculture":          "Agriculture & Agri-Food Processing",
    "forestry":             "Forestry & Wood Products",
    "defence":              "Defence, Security & Federal Facilities",
    "telecom":              "Telecommunications & Digital Infrastructure",
    "indigenous":           "Indigenous Infrastructure & Reconciliation",
    "environment":          "Environmental & Remediation",
    "tourism_culture":      "Tourism, Culture & Recreation",
    "government":           "Government & Institutional Buildings",
}

# -- Project status progression (for update logic) --
STATUS_PROGRESSION = {
    "Rumoured": 0,
    "Proposed": 1,
    "Approved": 2,
    "Under Construction": 3,
    "Completed": 4,
    "Paused": 2.5,
    "Cancelled": -1,
}

# ─────────────────────────────────────────────────────────────────────────────
# Status enum (D-4 — single source of truth for canonical project statuses)
# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE.md documents the canonical set. Audit found DB drift: 'Proposed' (2698),
# 'Under Review' (2664), 'Complete' (510), 'On Hold' (31), 'In Service' (sparse)
# — all non-canonical. normalize_status() folds them into the canonical set.
# Migration 001_backfill_status_enum.sql does a one-time DB-side backfill so
# historical rows match new writes.

CANONICAL_STATUSES = {
    'Announced',
    'Approved',
    'Under Construction',
    'Operational',
    'Completed',
    'Cancelled',
    'Paused',
    'Under Review',
}

STATUS_ALIASES = {
    # Drift observed in the DB (2026-06-08 audit) → canonical mapping
    'Proposed':       'Announced',
    'Complete':       'Completed',
    'In Service':     'Operational',
    'On Hold':        'Paused',
    'Rumoured':       'Announced',
    'Rumored':        'Announced',
    # Common scraper outputs that don't match documented set
    'proposed':       'Announced',
    'complete':       'Completed',
    'completed':      'Completed',
    'announced':      'Announced',
    'approved':       'Approved',
    'cancelled':      'Cancelled',
    'canceled':       'Cancelled',
    'paused':         'Paused',
    'on hold':        'Paused',
    'on-hold':        'Paused',
    'in service':     'Operational',
    'operational':    'Operational',
    'under review':   'Under Review',
    'under construction': 'Under Construction',
    'in construction': 'Under Construction',
    'construction':   'Under Construction',
}


def normalize_status(raw):
    """Fold any incoming status string into the canonical set.

    Args:
        raw: Status string from any source (scraper, classifier, manual edit).
             None or empty input → safe default 'Announced'.

    Returns:
        Member of CANONICAL_STATUSES. Never returns None.
    """
    if not raw:
        return 'Announced'
    s = str(raw).strip()
    if s in CANONICAL_STATUSES:
        return s
    if s in STATUS_ALIASES:
        return STATUS_ALIASES[s]
    # Case-insensitive lookup as last resort
    lower = s.lower()
    if lower in STATUS_ALIASES:
        return STATUS_ALIASES[lower]
    # Unknown values default to Announced (safest — lowest in STATUS_PROGRESSION
    # except Cancelled). This means a typo gets a low-confidence label, never a
    # higher-confidence one.
    return 'Announced'


def is_brownfield(project_type):
    """Check if a project type is brownfield."""
    return project_type in BROWNFIELD_TYPES


def normalize_project_type(raw):
    """Normalize a project_type string to a valid taxonomy value."""
    if not raw:
        return "greenfield"
    raw = raw.strip().lower().replace(' ', '_').replace('-', '_')
    if raw in PROJECT_TYPES:
        return raw
    # Common aliases
    aliases = {
        "new_build": "greenfield",
        "new_construction": "greenfield",
        "brownfield": "redevelopment",
        "renovation": "major_renovation",
        "rehab": "rehabilitation",
        "rehabilitation": "major_renovation",
        "upgrade": "modernization",
        "refit": "retrofit",
        "deep_retrofit": "retrofit",
        "energy_retrofit": "retrofit",
        "seismic_upgrade": "retrofit",
        "demolish_rebuild": "decommission_replace",
        "teardown": "decommission_replace",
        "repurpose": "adaptive_reuse",
        "repurposing": "adaptive_reuse",
        "infill": "greenfield",
    }
    return aliases.get(raw, "greenfield")


def build_project_document(extracted):
    """Build a Firestore-ready project document.

    Returns None if no verifiable source URL exists (hard gate).
    """
    from url_utils import normalize_url, validate_url, classify_source_authority

    # Domains to reject — Gemini grounded search redirects, not real sources
    _REJECT_DOMAINS = ("vertexaisearch.cloud.google.com", "vertexaisearch.cloud.goog")

    # -- Collect ALL evidence with URLs --
    evidence = []
    seen_urls = set()

    # From _evidence array (built by Gemini parser with grounding URLs)
    for e in extracted.get("_evidence", []):
        url = e.get("url", "")
        if url and url.startswith("http") and not any(d in url for d in _REJECT_DOMAINS):
            norm = normalize_url(url)
            if norm not in seen_urls:
                validation = validate_url(url)
                evidence.append({
                    "url": url,
                    "url_normalized": norm,
                    "name": e.get("name", ""),
                    "date": e.get("date", ""),
                    "source_type": e.get("source_type", "unknown"),
                    "authority": classify_source_authority(url),
                    "url_valid": validation["valid"],
                    "is_known_source": validation.get("is_known_source", False),
                })
                seen_urls.add(norm)

    # From existing evidence array (already built by dedup)
    for e in extracted.get("evidence", []):
        url = e.get("url", "")
        if url and url.startswith("http") and not any(d in url for d in _REJECT_DOMAINS):
            norm = normalize_url(url)
            if norm not in seen_urls:
                validation = validate_url(url)
                evidence.append({
                    "url": url,
                    "url_normalized": norm,
                    "name": e.get("name", ""),
                    "date": e.get("date", ""),
                    "source_type": e.get("source_type", "unknown"),
                    "authority": e.get("authority") or classify_source_authority(url),
                    "url_valid": validation["valid"],
                    "is_known_source": e.get("is_known_source") or validation.get("is_known_source", False),
                })
                seen_urls.add(norm)

    # Fallback: check top-level source_url field
    top_url = extracted.get("source_url", "")
    if top_url and top_url.startswith("http") and not any(d in top_url for d in _REJECT_DOMAINS):
        norm = normalize_url(top_url)
        if norm not in seen_urls:
            validation = validate_url(top_url)
            evidence.append({
                "url": top_url,
                "url_normalized": norm,
                "name": extracted.get("source_title") or extracted.get("source_name", ""),
                "date": extracted.get("date_reported", ""),
                "source_type": "extracted",
                "authority": classify_source_authority(top_url),
                "url_valid": validation["valid"],
                "is_known_source": validation.get("is_known_source", False),
            })

    # -- HARD GATE: No URL = no project --
    if not evidence:
        logger.warning(
            f"REJECTED: '{extracted.get('name')}' -- no verifiable source URL. "
            f"This project will NOT be written to Firestore."
        )
        return None

    ptype = normalize_project_type(extracted.get("project_type", ""))

    location = extracted.get("location", {})
    if isinstance(location, str):
        location = {"city": location, "province": None, "cma": None}

    return {
        "name": extracted.get("name", "Unknown Project"),
        "proponent": extracted.get("proponent"),
        "location": {
            "city": (location.get("city") if isinstance(location, dict) else None),
            "province": (location.get("province") if isinstance(location, dict) else None),
            "cma": (location.get("cma") if isinstance(location, dict) else None),
        },
        "value_millions": extracted.get("value_millions") or extracted.get("value_numeric"),
        "currency": extracted.get("currency", "CAD"),
        "status": extracted.get("status", "Proposed"),
        "project_type": ptype,
        "is_brownfield": is_brownfield(ptype),
        "sector": extracted.get("sector"),
        "description": extracted.get("description"),
        "evidence": evidence,
        "evidence_count": len(evidence),
        "has_government_source": any(e["authority"] == "government" for e in evidence),
        "has_known_source": any(e.get("is_known_source") for e in evidence),
        "confidence": extracted.get("confidence", 0.5),
        "discovery_sources": extracted.get("discovery_sources", []),
    }
