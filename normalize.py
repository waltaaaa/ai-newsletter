"""
normalize.py -- Province, status, and value normalization for project data.

Canonical mappings:
- 13 provinces/territories (2-letter codes)
- 8 project statuses
- Numeric value extraction from text
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Province normalization ──────────────────────────────────────────────────

CANONICAL_PROVINCES = {
    "ON", "QC", "AB", "BC", "SK", "MB", "NS", "NB", "NL", "PE", "YT", "NT", "NU",
}

# Full names → 2-letter codes
_PROVINCE_MAP = {
    # English full names
    "ontario": "ON",
    "quebec": "QC",
    "québec": "QC",
    "alberta": "AB",
    "british columbia": "BC",
    "saskatchewan": "SK",
    "manitoba": "MB",
    "nova scotia": "NS",
    "new brunswick": "NB",
    "newfoundland and labrador": "NL",
    "newfoundland & labrador": "NL",
    "newfoundland": "NL",
    "labrador": "NL",
    "prince edward island": "PE",
    "yukon": "YT",
    "northwest territories": "NT",
    "nunavut": "NU",
    # French full names
    "nouveau-brunswick": "NB",
    "nouveau brunswick": "NB",
    "nouvelle-écosse": "NS",
    "nouvelle écosse": "NS",
    "île-du-prince-édouard": "PE",
    "colombie-britannique": "BC",
    "terre-neuve-et-labrador": "NL",
    "territoires du nord-ouest": "NT",
    "terres du nord-ouest": "NT",
    # Already canonical
    "on": "ON",
    "qc": "QC",
    "ab": "AB",
    "bc": "BC",
    "sk": "SK",
    "mb": "MB",
    "ns": "NS",
    "nb": "NB",
    "nl": "NL",
    "pe": "PE",
    "yt": "YT",
    "nt": "NT",
    "nu": "NU",
    # PEI alternate
    "pei": "PE",
    "p.e.i.": "PE",
    # Yukon alternate
    "yk": "YT",
}

# US states and other invalid values to reject
_REJECT_VALUES = {"wa", "me", "ak", "ia", "ny", "ca", "tx", "fl", "n/a", "—", ""}

# National/multi-province flags → "CA"
_NATIONAL_VALUES = {"canada", "canada-wide", "multiple", "multiple provinces", "national", "pan-canadian", "multi"}

# Separators for multi-province strings
_MULTI_SEP = re.compile(r"[,;|/]|\bet\b")


def normalize_province(raw):
    """Normalize a province string to a canonical 2-letter code.

    Returns:
        tuple: (primary_code, additional_codes_string)
            - primary_code: 2-letter code, "CA" for national, or None if invalid
            - additional_codes_string: comma-separated additional province codes, or ""

    Examples:
        normalize_province("Ontario") → ("ON", "")
        normalize_province("ON, QC") → ("ON", "QC")
        normalize_province("Canada-wide") → ("CA", "")
        normalize_province("WA") → (None, "")
    """
    if not raw or not isinstance(raw, str):
        return (None, "")

    raw = raw.strip()
    low = raw.lower().strip()

    # Reject known invalid values
    if low in _REJECT_VALUES:
        return (None, "")

    # National/multi-province
    if low in _NATIONAL_VALUES:
        return ("CA", "")

    # Direct lookup (single province)
    if low in _PROVINCE_MAP:
        return (_PROVINCE_MAP[low], "")

    # Multi-province: split on separators
    parts = _MULTI_SEP.split(raw)
    if len(parts) > 1:
        codes = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            part_low = part.lower().strip()
            # Handle "QC et autres" → just QC
            if part_low in ("autres", "other", "others"):
                continue
            code = _PROVINCE_MAP.get(part_low)
            if code and code not in codes:
                codes.append(code)
        if codes:
            return (codes[0], ",".join(codes[1:]))

    # Last resort: check if the raw value (case-insensitive) is a 2-letter code
    if len(low) == 2 and low.upper() in CANONICAL_PROVINCES:
        return (low.upper(), "")

    logger.warning(f"Unknown province value: {raw!r}")
    return (None, "")


# ── Status normalization ────────────────────────────────────────────────────

CANONICAL_STATUSES = [
    "Proposed",
    "Under Review",
    "Approved",
    "Under Construction",
    "Partially Complete",
    "Complete",
    "Cancelled",
    "On Hold",
]

# Mapping from lowercase normalized key → canonical status
_STATUS_MAP = {
    # ─── Proposed ───
    "proposed": "Proposed",
    "announced": "Proposed",
    "newly_announced": "Proposed",
    "conceptual": "Proposed",
    "envisioned": "Proposed",
    "coming_soon": "Proposed",
    "upcoming": "Proposed",
    "pending": "Proposed",
    "early_engagement": "Proposed",
    "pre_planning": "Proposed",
    "pre_development": "Proposed",
    "in_pre_development": "Proposed",
    "research phase": "Proposed",
    "exploration": "Proposed",
    "open": "Proposed",
    "open_for_consultation": "Proposed",
    "launched": "Proposed",
    # Real-estate marketing statuses → Proposed (pre-construction)
    "preselling": "Proposed",
    "presale": "Proposed",
    "now_selling": "Proposed",
    "selling": "Proposed",
    "leasing": "Proposed",
    # French
    "proposé": "Proposed",
    "propose": "Proposed",
    "annoncé": "Proposed",
    "annonce": "Proposed",
    # ─── Under Review ───
    "under review": "Under Review",
    "under_review": "Under Review",
    "in_review": "Under Review",
    "under consideration": "Under Review",
    "under_regulatory_evaluation": "Under Review",
    "under_environmental_assessment": "Under Review",
    "registration": "Under Review",
    "permitting": "Under Review",
    "proposed/under review": "Under Review",
    "under_study": "Under Review",
    "eoi_closed": "Under Review",
    # ─── Approved ───
    "approved": "Approved",
    "approved_for_planning": "Approved",
    "approved_delayed": "Approved",
    "funded": "Approved",
    "funding_received": "Approved",
    "funding_announced": "Approved",
    "received_government_funding": "Approved",
    "construction_funding": "Approved",
    "contract_awarded": "Approved",
    "awarded": "Approved",
    # French
    "approuvé": "Approved",
    "approuve": "Approved",
    # ─── Planning/Design → Approved ───
    "planning": "Approved",
    "planned": "Approved",
    "in_planning": "Approved",
    "under_planning": "Approved",
    "planning_and_design": "Approved",
    "planning_design": "Approved",
    "planning & development": "Approved",
    "planning and consultation": "Approved",
    "in planning/development": "Approved",
    "final_planning": "Approved",
    "advanced_planning": "Approved",
    "design": "Approved",
    "in_design": "Approved",
    "under_design": "Approved",
    "design_phase": "Approved",
    "design_development": "Approved",
    "design_underway": "Approved",
    "detailed_design": "Approved",
    "detailed_design_advancing": "Approved",
    "preliminary_design": "Approved",
    "development": "Approved",
    "in_development": "Approved",
    "under_development": "Approved",
    "development_phase": "Approved",
    "developing": "Approved",
    "development and pre-construction": "Approved",
    "advancing development": "Approved",
    # French
    "en_développement": "Approved",
    "en_developpement": "Approved",
    # ─── Pre-construction → Approved ───
    "pre-construction": "Approved",
    "pre_construction": "Approved",
    "preconstruction": "Approved",
    "preparing_for_construction": "Approved",
    "construction_preparation": "Approved",
    # Procurement → Approved
    "procurement": "Approved",
    "in_procurement": "Approved",
    "pre_procurement": "Approved",
    "ready_to_tender": "Approved",
    "seeking_tenders": "Approved",
    "sub_bidding": "Approved",
    "post_bid": "Approved",
    # ─── Under Construction ───
    "under construction": "Under Construction",
    "under_construction": "Under Construction",
    "in_progress": "Under Construction",
    "underway": "Under Construction",
    "active": "Under Construction",
    "ongoing": "Under Construction",
    "on_track": "Under Construction",
    "moving_forward": "Under Construction",
    "under_implementation": "Under Construction",
    "implementation": "Under Construction",
    "restarted": "Under Construction",
    "testing_commissioning": "Under Construction",
    "commissioning": "Under Construction",
    # French
    "en_construction": "Under Construction",
    "en construction": "Under Construction",
    # Project-type words used as status (bad extraction)
    "expansion": "Under Construction",
    "major_renovation": "Under Construction",
    "conversion": "Under Construction",
    "redevelopment": "Under Construction",
    "remediation": "Under Construction",
    "decommission_replace": "Under Construction",
    "under_remediation": "Under Construction",
    # ─── Partially Complete ───
    "partially complete": "Partially Complete",
    "nearing completion": "Partially Complete",
    "nearing_completion": "Partially Complete",
    "nearly_completed": "Partially Complete",
    "winding_down": "Partially Complete",
    # ─── Complete ───
    "completed": "Complete",
    "complete": "Complete",
    "recently_completed": "Complete",
    "operational": "Complete",
    "operating": "Complete",
    "operational_with_ongoing_maintenance": "Complete",
    "closed": "Complete",
    "temporarily_closed": "Complete",
    "planned_closure": "Complete",
    # French
    "achevé": "Complete",
    "acheve": "Complete",
    # ─── Cancelled ───
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    # ─── On Hold ───
    "on hold": "On Hold",
    "on_hold": "On Hold",
    "paused": "On Hold",
    "suspended": "On Hold",
    "deferred": "On Hold",
    "delayed": "On Hold",
    "cost_overruns": "On Hold",
    # French
    "retardé": "On Hold",
    "retarde": "On Hold",
}

# Status progression order for resolving compound statuses
_STATUS_ORDER = {
    "Proposed": 1,
    "Under Review": 2,
    "Approved": 3,
    "Under Construction": 4,
    "Partially Complete": 5,
    "Complete": 6,
    "Cancelled": -1,
    "On Hold": 0,
}

# Compound status separator pattern
_COMPOUND_SEP = re.compile(r"[|,;/]")


def normalize_status(raw):
    """Normalize a status string to one of 8 canonical statuses.

    Returns canonical status string, or "Proposed" if unrecognizable.

    Handles:
    - Case normalization (under_construction → Under Construction)
    - French translations (En_Construction → Under Construction)
    - Compound statuses (On_Hold | Under_Construction → Under Construction)
    - Verbose statuses (Phase 1 Completed, Phase 2 Under Construction → Under Construction)
    """
    if not raw or not isinstance(raw, str):
        return "Proposed"

    raw = raw.strip()

    # Strip parenthetical qualifiers: "Proposed (Phase 1 commencing...)" → "Proposed"
    base = re.sub(r"\s*\(.*?\)\s*", "", raw).strip()

    # Normalize underscores and spaces
    key = base.lower().replace("_", " ").replace("-", " ").strip()
    key = re.sub(r"\s+", " ", key)  # collapse multiple spaces

    # Direct lookup
    result = _STATUS_MAP.get(key)
    if result:
        return result

    # Also try with underscores (some keys use them)
    key_underscore = key.replace(" ", "_")
    result = _STATUS_MAP.get(key_underscore)
    if result:
        return result

    # Compound status: split and take highest progression
    parts = _COMPOUND_SEP.split(raw)
    if len(parts) > 1:
        best = None
        best_order = -2
        for part in parts:
            part = part.strip()
            if not part:
                continue
            sub_status = normalize_status(part)  # recursive
            order = _STATUS_ORDER.get(sub_status, 0)
            if order > best_order:
                best = sub_status
                best_order = order
        if best:
            return best

    # Keyword fallback for verbose statuses
    low = raw.lower()
    if "construct" in low or "underway" in low:
        return "Under Construction"
    if "complet" in low or "achev" in low:
        return "Complete"
    if "approv" in low or "fund" in low:
        return "Approved"
    if "cancel" in low:
        return "Cancelled"
    if "hold" in low or "pause" in low or "suspend" in low or "delay" in low:
        return "On Hold"
    if "review" in low or "assess" in low:
        return "Under Review"
    if "propos" in low or "announc" in low:
        return "Proposed"

    logger.warning(f"Unknown status value: {raw!r} → defaulting to Proposed")
    return "Proposed"


# ── Value parsing ───────────────────────────────────────────────────────────

# Pattern to extract numeric value with optional suffix
_VALUE_PATTERN = re.compile(
    r"(?:C?\$|CAD\s*)\s*"          # Currency prefix: $, C$, CAD
    r"([\d,]+(?:\.\d+)?)"          # Number (with commas and decimal)
    r"\s*"
    r"(B|billion|M|million|K|thousand|T|trillion)?",  # Multiplier suffix
    re.IGNORECASE
)

# French pattern: "500 millions $" or "1,2 milliard $"
_VALUE_PATTERN_FR = re.compile(
    r"([\d\s]+(?:[.,]\d+)?)"       # Number (French uses comma as decimal, space as thousands)
    r"\s*"
    r"(milliards?|millions?|milliers?)"  # French multiplier
    r"\s*(?:\$|CAD)?",
    re.IGNORECASE
)

_MULTIPLIERS = {
    "t": 1_000_000_000_000,
    "trillion": 1_000_000_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
    "milliard": 1_000_000_000,
    "milliards": 1_000_000_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "k": 1_000,
    "thousand": 1_000,
    "millier": 1_000,
    "milliers": 1_000,
}


def parse_value(raw):
    """Extract a numeric CAD value from text.

    Returns float in dollars, or None if unparsable.

    Handles:
    - "$15M", "C$15M", "$1.2B", "$500K"
    - "$100M+", "$100M (hotel portion)"
    - "$11.6B (Q4 2025)"
    - French: "500 millions $", "1,2 milliard $"
    - Range: "$1B-$2B" → midpoint $1.5B
    - Comma thousands: "$1,500,000"
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if raw in ("", "Not disclosed", "N/A", "TBD", "Unknown", "—", "0", "$0", "$0M", "C$0M"):
        return None

    # Try range first: "$1B-$2B" or "$100M to $200M"
    range_match = re.search(
        r"(?:C?\$|CAD\s*)\s*([\d,.]+)\s*(B|billion|M|million|K|thousand)?"
        r"\s*[-–—to]+\s*"
        r"(?:C?\$|CAD\s*)?\s*([\d,.]+)\s*(B|billion|M|million|K|thousand)?",
        raw, re.IGNORECASE
    )
    if range_match:
        low_num = _parse_number(range_match.group(1))
        low_mult = _MULTIPLIERS.get((range_match.group(2) or "").lower(), 1)
        high_num = _parse_number(range_match.group(3))
        high_mult = _MULTIPLIERS.get((range_match.group(4) or range_match.group(2) or "").lower(), 1)
        if low_num is not None and high_num is not None:
            return (low_num * low_mult + high_num * high_mult) / 2

    # Try English pattern: "$15M", "C$1.2B"
    match = _VALUE_PATTERN.search(raw)
    if match:
        num = _parse_number(match.group(1))
        mult = _MULTIPLIERS.get((match.group(2) or "").lower(), 1)
        if num is not None:
            return num * mult

    # Try French pattern: "500 millions $"
    match_fr = _VALUE_PATTERN_FR.search(raw)
    if match_fr:
        num = _parse_number_french(match_fr.group(1))
        mult = _MULTIPLIERS.get(match_fr.group(2).lower(), 1)
        if num is not None:
            return num * mult

    # Last resort: plain number with $ sign (e.g., "$1,500,000")
    plain = re.search(r"(?:C?\$|CAD\s*)\s*([\d,]+(?:\.\d+)?)", raw)
    if plain:
        num = _parse_number(plain.group(1))
        if num is not None and num > 0:
            return num

    return None


def _parse_number(s):
    """Parse a number string like '1,500,000' or '1.5' to float."""
    if not s:
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_number_french(s):
    """Parse a French number string like '1 500' or '1,5' to float."""
    if not s:
        return None
    s = s.strip()
    # French uses space as thousands separator
    s = s.replace(" ", "")
    # French uses comma as decimal separator
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None
