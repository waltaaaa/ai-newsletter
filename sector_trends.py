"""
sector_trends.py -- Project pipeline trend analysis by sector, province, status.

Computes period-over-period changes in:
- New project announcements by sector and province
- Total pipeline value by sector and province
- Status transitions (proposed→approved→construction→completed)
- Greenfield vs brownfield mix
- Geographic concentration shifts

Periods: weekly, monthly, quarterly, year-over-year.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Standard NAICS sector mapping
SECTOR_ORDER = [
    "Agriculture", "Mining & O&G", "Utilities", "Construction",
    "Manufacturing", "Wholesale", "Retail", "Transportation",
    "Information & Telecom", "Finance", "Real Estate", "Professional Services",
    "Management", "Admin & Waste", "Education", "Health Care",
    "Entertainment", "Accommodation", "Other Services", "Public Admin",
]

STATUS_PROGRESSION = [
    "Proposed", "Approved", "Under Construction", "Completed",
]

PERIOD_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


def _parse_date(val):
    """Parse ISO date string to datetime, returns None on failure."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _get_value(p):
    """Extract numeric value in millions from a project dict."""
    v = p.get("value_millions")
    if v is not None:
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
    # Fallback: parse value string
    val_str = str(p.get("value", "") or "")
    import re
    m = re.search(r"\$([\d,.]+)\s*(B|billion)", val_str, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "")) * 1000
    m = re.search(r"\$([\d,.]+)\s*(M|million)", val_str, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return 0.0


def _projects_in_period(projects, start, end, date_field="firstSeen"):
    """Filter projects whose date_field falls within [start, end)."""
    result = []
    for p in projects:
        dt = _parse_date(p.get(date_field) or p.get("lastSeen") or p.get("lastUpdated"))
        if dt and start <= dt < end:
            result.append(p)
    return result


def compute_sector_breakdown(projects):
    """Count projects and total value by sector."""
    sectors = defaultdict(lambda: {"count": 0, "value": 0.0})
    for p in projects:
        sector = p.get("sector", "Unknown") or "Unknown"
        sectors[sector]["count"] += 1
        sectors[sector]["value"] += _get_value(p)
    return dict(sectors)


def compute_province_breakdown(projects):
    """Count projects and total value by province."""
    provinces = defaultdict(lambda: {"count": 0, "value": 0.0})
    for p in projects:
        prov = p.get("province", "Unknown") or "Unknown"
        provinces[prov]["count"] += 1
        provinces[prov]["value"] += _get_value(p)
    return dict(provinces)


def compute_status_breakdown(projects):
    """Count projects by status."""
    statuses = defaultdict(int)
    for p in projects:
        status = p.get("status", "Unknown") or "Unknown"
        statuses[status] += 1
    return dict(statuses)


def compute_type_breakdown(projects):
    """Count greenfield vs brownfield (expansion/redevelopment)."""
    types = {"greenfield": 0, "brownfield": 0, "unknown": 0}
    brownfield_kw = {"expansion", "redevelopment", "renovation", "upgrade",
                     "modernization", "retrofit", "rehabilitation"}
    for p in projects:
        name = (p.get("name", "") or "").lower()
        ptype = (p.get("type", "") or "").lower()
        combined = f"{name} {ptype}"
        if any(kw in combined for kw in brownfield_kw):
            types["brownfield"] += 1
        elif name:
            types["greenfield"] += 1
        else:
            types["unknown"] += 1
    return types


def compute_period_trends(projects, period="monthly"):
    """Compute trends for current vs previous period.

    Returns dict with current_count, previous_count, change, pct_change,
    plus sector and province breakdowns for each period.
    """
    now = datetime.utcnow()
    days = PERIOD_DAYS.get(period, 30)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    current = _projects_in_period(projects, current_start, now)
    previous = _projects_in_period(projects, previous_start, current_start)

    cur_count = len(current)
    prev_count = len(previous)
    change = cur_count - prev_count
    pct = round((change / prev_count * 100) if prev_count > 0 else 0, 1)

    cur_value = sum(_get_value(p) for p in current)
    prev_value = sum(_get_value(p) for p in previous)
    val_change = cur_value - prev_value
    val_pct = round((val_change / prev_value * 100) if prev_value > 0 else 0, 1)

    return {
        "period": period,
        "period_days": days,
        "current": {
            "count": cur_count,
            "value_millions": round(cur_value, 1),
            "sectors": compute_sector_breakdown(current),
            "provinces": compute_province_breakdown(current),
        },
        "previous": {
            "count": prev_count,
            "value_millions": round(prev_value, 1),
            "sectors": compute_sector_breakdown(previous),
            "provinces": compute_province_breakdown(previous),
        },
        "count_change": change,
        "count_pct_change": pct,
        "value_change_millions": round(val_change, 1),
        "value_pct_change": val_pct,
    }


def compute_sector_momentum(projects):
    """Classify each sector as accelerating, decelerating, or stable.

    Uses 3-month vs previous 3-month comparison.
    """
    now = datetime.utcnow()
    q1_start = now - timedelta(days=90)
    q0_start = q1_start - timedelta(days=90)

    current_q = _projects_in_period(projects, q1_start, now)
    previous_q = _projects_in_period(projects, q0_start, q1_start)

    cur_sectors = compute_sector_breakdown(current_q)
    prev_sectors = compute_sector_breakdown(previous_q)

    all_sectors = set(list(cur_sectors.keys()) + list(prev_sectors.keys()))
    momentum = {}
    for s in all_sectors:
        cur = cur_sectors.get(s, {"count": 0, "value": 0.0})
        prev = prev_sectors.get(s, {"count": 0, "value": 0.0})
        count_diff = cur["count"] - prev["count"]
        if prev["count"] == 0:
            if cur["count"] > 0:
                label = "accelerating"
            else:
                label = "stable"
        elif count_diff / prev["count"] > 0.15:
            label = "accelerating"
        elif count_diff / prev["count"] < -0.15:
            label = "decelerating"
        else:
            label = "stable"
        momentum[s] = {
            "label": label,
            "current_count": cur["count"],
            "previous_count": prev["count"],
            "change": count_diff,
        }
    return momentum


def compute_geographic_shifts(projects):
    """Detect shifts in provincial share of pipeline.

    Compares current quarter to previous quarter province distribution.
    """
    now = datetime.utcnow()
    q1_start = now - timedelta(days=90)
    q0_start = q1_start - timedelta(days=90)

    current_q = _projects_in_period(projects, q1_start, now)
    previous_q = _projects_in_period(projects, q0_start, q1_start)

    cur_provs = compute_province_breakdown(current_q)
    prev_provs = compute_province_breakdown(previous_q)

    cur_total = sum(v["count"] for v in cur_provs.values()) or 1
    prev_total = sum(v["count"] for v in prev_provs.values()) or 1

    all_provs = set(list(cur_provs.keys()) + list(prev_provs.keys()))
    shifts = {}
    for prov in all_provs:
        cur_share = cur_provs.get(prov, {"count": 0})["count"] / cur_total
        prev_share = prev_provs.get(prov, {"count": 0})["count"] / prev_total
        shift = round(cur_share - prev_share, 3)
        shifts[prov] = {
            "current_share": round(cur_share, 3),
            "previous_share": round(prev_share, 3),
            "shift": shift,
            "direction": "growing" if shift > 0.02 else ("shrinking" if shift < -0.02 else "stable"),
        }
    return shifts


def compute_pipeline_health(projects):
    """Compute overall pipeline health metrics."""
    total = len(projects)
    if total == 0:
        return {"total": 0, "health": "insufficient_data"}

    statuses = compute_status_breakdown(projects)
    proposed = statuses.get("Proposed", 0)
    approved = statuses.get("Approved", 0)
    under_construction = statuses.get("Under Construction", 0)
    completed = statuses.get("Completed", 0)
    cancelled = statuses.get("Cancelled", 0)
    suspended = statuses.get("Suspended", 0)

    active = proposed + approved + under_construction
    cancelled_rate = round(cancelled / total, 3) if total > 0 else 0
    completion_rate = round(completed / total, 3) if total > 0 else 0

    # Count with values
    valued = sum(1 for p in projects if _get_value(p) > 0)
    total_value = sum(_get_value(p) for p in projects)

    return {
        "total_projects": total,
        "active_projects": active,
        "completed": completed,
        "cancelled": cancelled,
        "suspended": suspended,
        "cancellation_rate": cancelled_rate,
        "completion_rate": completion_rate,
        "valued_projects": valued,
        "value_coverage": round(valued / total, 3) if total > 0 else 0,
        "total_value_millions": round(total_value, 1),
    }


def compute_project_trends(conn):
    """Main entry point: compute all project trends from SQLite.

    Args:
        conn: sqlite3.Connection from db.py (or a Firestore client for
              backward compatibility — detected by duck-typing)

    Returns:
        dict with all trend data, ready for storage or report generation
    """
    print("\n[TRENDS] Computing project pipeline trends...")

    # Load all projects
    projects = []
    # Detect SQLite connection vs legacy Firestore client
    if hasattr(conn, 'execute'):
        from db import get_all_projects
        projects = get_all_projects(conn)
    else:
        # Legacy Firestore path (kept for backward compatibility)
        for doc in conn.collection("projects").stream():
            d = doc.to_dict()
            d["_doc_id"] = doc.id
            projects.append(d)

    if not projects:
        print("  [TRENDS] No projects found")
        return {"error": "no_projects"}

    print(f"  [TRENDS] Analyzing {len(projects)} projects...")

    trends = {
        "computed_at": datetime.utcnow().isoformat(),
        "total_projects": len(projects),
        "overall": compute_pipeline_health(projects),
        "status_breakdown": compute_status_breakdown(projects),
        "type_breakdown": compute_type_breakdown(projects),
        "sectors": compute_sector_breakdown(projects),
        "provinces": compute_province_breakdown(projects),
        "period_trends": {},
        "sector_momentum": compute_sector_momentum(projects),
        "geographic_shifts": compute_geographic_shifts(projects),
    }

    # Compute trends for each period
    for period in PERIOD_DAYS:
        trends["period_trends"][period] = compute_period_trends(projects, period)

    # Summary stats
    accel = sum(1 for v in trends["sector_momentum"].values() if v["label"] == "accelerating")
    decel = sum(1 for v in trends["sector_momentum"].values() if v["label"] == "decelerating")
    growing = sum(1 for v in trends["geographic_shifts"].values() if v["direction"] == "growing")

    print(f"  [TRENDS] Sectors: {accel} accelerating, {decel} decelerating")
    print(f"  [TRENDS] Provinces: {growing} growing share")
    print(f"  [TRENDS] Pipeline: {trends['overall']['total_value_millions']:.0f}M total value")

    return trends
