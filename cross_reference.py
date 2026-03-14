"""
cross_reference.py -- Link macro indicators to project pipeline trends.

Maps directional changes in economic indicators to expected effects on
project sectors, enabling the weekly report to explain correlations
(e.g., "BoC rate cut → accelerating real estate pipeline").
"""

import logging

from pipeline_config import NAICS_MAP

logger = logging.getLogger(__name__)

# Map abbreviated sector names (used in INDICATOR_PROJECT_LINKS) to the full
# NAICS sector names stored in the projects table via pipeline_config.NAICS_MAP.
_XREF_TO_NAICS = {
    "Agriculture":      NAICS_MAP["11"],
    "Mining & O&G":     NAICS_MAP["21"],
    "Utilities":        NAICS_MAP["22"],
    "Construction":     NAICS_MAP["23"],
    "Manufacturing":    NAICS_MAP["31-33"],
    "Wholesale":        NAICS_MAP["41"],
    "Retail":           NAICS_MAP["44-45"],
    "Transportation":   NAICS_MAP["48-49"],
    "Information":      NAICS_MAP["51"],
    "Finance":          NAICS_MAP["52"],
    "Real Estate":      NAICS_MAP["53"],
    "Professional":     NAICS_MAP["54"],
    "Management":       NAICS_MAP["55"],
    "Admin & Waste":    NAICS_MAP["56"],
    "Education":        NAICS_MAP["61"],
    "Health Care":      NAICS_MAP["62"],
    "Entertainment":    NAICS_MAP["71"],
    "Accommodation":    NAICS_MAP["72"],
    "Other Services":   NAICS_MAP["81"],
    "Public Admin":     NAICS_MAP["91"],
}

# Mapping: indicator -> list of (sector, relationship)
# relationship: "positive" = indicator up → sector activity up
#               "negative" = indicator up → sector activity down
#               "lagged_positive" / "lagged_negative" = effect with 1-2 quarter delay
INDICATOR_PROJECT_LINKS = {
    "boc_overnight_rate": [
        ("Real Estate", "negative"),
        ("Construction", "negative"),
        ("Finance", "lagged_positive"),
        ("Retail", "negative"),
    ],
    "cpi_yoy": [
        ("Construction", "negative"),        # higher costs → fewer starts
        ("Real Estate", "lagged_negative"),
        ("Manufacturing", "negative"),
    ],
    "unemployment_rate": [
        ("Construction", "negative"),         # higher unemployment → less activity
        ("Retail", "negative"),
        ("Public Admin", "lagged_positive"),  # gov spending responds to unemployment
    ],
    "gdp_quarterly": [
        ("Construction", "positive"),
        ("Manufacturing", "positive"),
        ("Real Estate", "positive"),
        ("Mining & O&G", "positive"),
        ("Transportation", "positive"),
    ],
    "wti_crude": [
        ("Mining & O&G", "positive"),
        ("Utilities", "lagged_positive"),
        ("Transportation", "negative"),       # higher fuel costs
        ("Manufacturing", "negative"),
    ],
    "cad_usd": [
        ("Manufacturing", "negative"),        # stronger CAD → less export competitive
        ("Mining & O&G", "negative"),
        ("Retail", "positive"),               # cheaper imports
    ],
    "sp_tsx": [
        ("Finance", "positive"),
        ("Real Estate", "lagged_positive"),
        ("Construction", "lagged_positive"),
    ],
    "housing_starts": [
        ("Construction", "positive"),
        ("Real Estate", "positive"),
        ("Manufacturing", "lagged_positive"), # building materials
    ],
}


def cross_reference_trends(indicator_trends, sector_trends):
    """Cross-reference indicator trends with sector momentum.

    Identifies correlations and divergences between macro indicators
    and project pipeline activity.

    Args:
        indicator_trends: dict from indicator_trends.compute_indicator_trends()
        sector_trends: dict from sector_trends.compute_project_trends()

    Returns:
        dict with correlations, divergences, and narrative hints
    """
    if not indicator_trends or not sector_trends:
        return {"error": "insufficient_data"}

    momentum = sector_trends.get("sector_momentum", {})
    correlations = []
    divergences = []

    for indicator, links in INDICATOR_PROJECT_LINKS.items():
        ind_data = indicator_trends.get(indicator, {})
        ind_direction = ind_data.get("direction", "unknown")

        if ind_direction in ("insufficient_data", "no_data", "error", "unknown"):
            continue

        for sector, relationship in links:
            # Translate abbreviated name to full NAICS name used in DB
            naics_sector = _XREF_TO_NAICS.get(sector, sector)
            sect_data = momentum.get(naics_sector, {})
            sect_label = sect_data.get("label", "unknown")

            if sect_label == "unknown":
                continue

            # Determine expected sector direction based on indicator + relationship
            if relationship in ("positive", "lagged_positive"):
                expected = "accelerating" if ind_direction == "rising" else "decelerating"
            else:
                expected = "decelerating" if ind_direction == "rising" else "accelerating"

            is_lagged = "lagged" in relationship

            entry = {
                "indicator": indicator,
                "indicator_direction": ind_direction,
                "sector": sector,
                "sector_momentum": sect_label,
                "relationship": relationship,
                "expected_momentum": expected,
                "is_lagged": is_lagged,
            }

            if sect_label == expected:
                entry["match"] = True
                correlations.append(entry)
            elif sect_label != "stable" and expected != "stable":
                entry["match"] = False
                divergences.append(entry)

    # Generate narrative hints
    hints = []

    for c in correlations:
        if not c["is_lagged"]:
            rel = "supporting" if c["relationship"] == "positive" else "constraining"
            hints.append(
                f"{c['indicator'].replace('_', ' ').title()} ({c['indicator_direction']}) "
                f"is {rel} {c['sector']} activity ({c['sector_momentum']})"
            )

    for d in divergences:
        hints.append(
            f"DIVERGENCE: {d['indicator'].replace('_', ' ').title()} ({d['indicator_direction']}) "
            f"suggests {d['sector']} should be {d['expected_momentum']}, "
            f"but it's {d['sector_momentum']}"
        )

    print(f"  [XREF] {len(correlations)} correlations, {len(divergences)} divergences")

    return {
        "correlations": correlations,
        "divergences": divergences,
        "narrative_hints": hints,
        "total_links_checked": sum(len(v) for v in INDICATOR_PROJECT_LINKS.values()),
    }
