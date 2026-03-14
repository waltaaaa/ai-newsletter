"""
compound_queries.py — Compound query loader and accessor.

Loads 759 compound queries from compound_queries_final.json.
Covers:
- 13 provinces x 18 NAICS sectors (English, affinity-filtered)
- French queries: QC (full 18 sectors), NB (full), NS (light 8 sectors), PE (light), ON (light)
- 35 CMAs x 8 urban sectors
- 30 regional clusters x 7 resource sectors
- Lifecycle/status queries for all provinces (EN + FR)

Every query has a 4-week lookback window and requests both greenfield and brownfield projects.
759 total = 108/day = 22% of Gemini 500 RPD free tier.
"""

import json
import os

QUERIES_FILE = os.path.join(os.path.dirname(__file__), "config", "compound_queries_final.json")

_cached_queries = None


def load_queries():
    global _cached_queries
    if _cached_queries is None:
        with open(QUERIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cached_queries = data["queries"]
    return _cached_queries


def get_weekly_queries():
    """Return ALL queries for the weekly run. No rotation needed — fits free tier."""
    return load_queries()


def get_queries_by_tier(tier):
    """Filter by geo tier: 'province', 'cma', 'regional_cluster'."""
    return [q for q in load_queries() if q.get("geo_tier") == tier]


def get_queries_by_language(lang):
    """Filter by language: 'en' or 'fr'."""
    return [q for q in load_queries() if q.get("language") == lang]


_PROV_CODE_TO_NAME = {
    "ON": "Ontario", "QC": "Quebec", "AB": "Alberta", "BC": "British Columbia",
    "SK": "Saskatchewan", "MB": "Manitoba", "NS": "Nova Scotia", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "PE": "Prince Edward Island",
    "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
}

def get_queries_by_province(prov_code):
    """All queries for a province (matches both 2-letter code and full name)."""
    full = _PROV_CODE_TO_NAME.get(prov_code, prov_code)
    return [q for q in load_queries()
            if q.get("province") in (prov_code, full)]


def get_queries_by_sector(sector_key):
    """All queries for a sector across all geographies."""
    return [q for q in load_queries() if q.get("sector") == sector_key]
