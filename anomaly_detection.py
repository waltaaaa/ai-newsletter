"""
anomaly_detection.py — Cross-project anomaly detection.

Per-project anomalies (value spike, status regression, proponent change)
are already handled inline in project_sync.py during upsert.

This module adds cross-project checks that require the full database:
- Possible duplicates: same/similar project name in different provinces
  (might be misattribution, or might be a multi-province project like a pipeline)
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Words to strip before comparing names
_FILLER = {
    "project", "development", "construction", "phase", "expansion",
    "redevelopment", "the", "new", "proposed", "1", "2", "3", "i", "ii", "iii",
}


def _normalize_name(name):
    """Normalize a project name for duplicate comparison."""
    n = (name or "").lower().strip()
    tokens = [t for t in n.split() if t not in _FILLER]
    return " ".join(tokens).strip()


def check_cross_project_anomalies(all_projects):
    """Check for anomalies across the full project database.

    Detects possible duplicates: same or very similar project names
    in different provinces. These might be the same project misattributed,
    or legitimate different projects (e.g. Tim Hortons in ON and AB).

    Args:
        all_projects: list of project dicts (from Firestore snapshot)

    Returns:
        list of anomaly dicts with type, detail, doc_ids, provinces
    """
    anomalies = []

    # Group by normalized name
    name_groups = defaultdict(list)
    for p in all_projects:
        norm = _normalize_name(p.get("name", ""))
        if len(norm) < 5:
            continue
        name_groups[norm].append(p)

    for norm_name, group in name_groups.items():
        if len(group) < 2:
            continue

        provinces = set()
        for p in group:
            prov = p.get("province", "") or ""
            if prov:
                provinces.add(prov)

        if len(provinces) > 1:
            names = [p.get("name", "?") for p in group]
            doc_ids = [p.get("_doc_id", "") for p in group if p.get("_doc_id")]
            anomalies.append({
                "type": "possible_duplicate",
                "detail": (
                    f"'{group[0].get('name', norm_name)}' found in "
                    f"{len(provinces)} provinces: {', '.join(sorted(provinces))}"
                ),
                "projects": names,
                "provinces": sorted(provinces),
                "doc_ids": doc_ids,
            })

    if anomalies:
        logger.info(f"Cross-project anomalies: {len(anomalies)} possible duplicates")
    return anomalies
