"""
change_detector.py — Temporal change detection for Canadian capital projects.

Compares extracted projects against their prior DB state and produces a
structured change log. Transforms the newsletter from "here's a list of
projects" to "here's what moved this week."

Change types:
  - new: Not in DB at all
  - status: Status moved forward (or backward)
  - cost: Capital cost estimate changed
  - timeline: Completion date shifted
  - ownership: Proponent/operator changed
  - scope: Description materially different
  - reconfirmed: Seen again, no changes (project is still alive)
  - silent: In DB but not seen in N weeks

Significance scoring:
  - Status advance (proposed -> under construction): HIGH (0.9)
  - Cost increase > 50%: HIGH (0.8)
  - Cost tweak < 10%: LOW (0.2)
  - Timeline slip < 6 months: LOW (0.2)
  - Timeline slip > 2 years: HIGH (0.8)
  - Gone silent > 8 weeks: MEDIUM (0.5)

Integration:
  Extract -> Dedup -> Validate -> Detect Changes -> Upsert -> Write
  The change_summary feeds into the newsletter writing phase.
"""

import json
import logging
import re
from datetime import date, datetime, timedelta
from enum import Enum

from pipeline_config import CHANGE_DETECTION_ENABLED

logger = logging.getLogger(__name__)

SILENT_WEEKS_THRESHOLD = 8  # weeks without being seen before alerting


class ChangeType(Enum):
    NEW_PROJECT = "new"
    STATUS_CHANGE = "status"
    COST_CHANGE = "cost"
    TIMELINE_CHANGE = "timeline"
    OWNERSHIP_CHANGE = "ownership"
    SCOPE_CHANGE = "scope"
    RECONFIRMED = "reconfirmed"
    GONE_SILENT = "silent"


# Status ordering for detecting advances vs. regressions
_STATUS_ORDER = {
    "Proposed": 0, "Under Review": 1, "Approved": 2,
    "Under Construction": 3, "Partially Complete": 4, "Complete": 5,
    "Cancelled": -1, "On Hold": -2, "Suspended": -2, "Paused": -2,
}


# ── Value parsing ─────────────────────────────────────────────────────────

def _parse_value_millions(val) -> float | None:
    """Parse a dollar value string to millions."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).upper().replace(",", "").replace("$", "").replace("C", "").strip()
    m = re.match(r"(\d+(?:\.\d+)?)\s*(B|M|K)?", s)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2) or "M"
    if unit == "B":
        n *= 1000
    elif unit == "K":
        n /= 1000
    return n


def _parse_year(val) -> int | None:
    """Extract a 4-digit year from a date/year string."""
    if not val:
        return None
    m = re.search(r"(20\d{2})", str(val))
    return int(m.group(1)) if m else None


# ── Significance scoring ──────────────────────────────────────────────────

def _score_status_change(old_status: str, new_status: str) -> float:
    """Score the significance of a status change."""
    old_ord = _STATUS_ORDER.get(old_status, -99)
    new_ord = _STATUS_ORDER.get(new_status, -99)

    # Terminal state transitions (cancelled, paused)
    if new_ord < 0:
        return 0.85

    # Forward advance
    if new_ord > old_ord:
        gap = new_ord - old_ord
        if gap >= 2:
            return 0.9  # big jump (proposed -> under construction)
        return 0.7

    # Regression
    if new_ord < old_ord:
        return 0.6

    return 0.1  # same status


def _score_cost_change(old_val: float, new_val: float) -> float:
    """Score the significance of a cost change."""
    if old_val == 0:
        return 0.5  # new value disclosed
    pct = abs(new_val - old_val) / old_val
    if pct >= 0.50:
        return 0.8
    if pct >= 0.20:
        return 0.5
    if pct >= 0.10:
        return 0.3
    return 0.2  # minor refinement


def _score_timeline_change(old_year: int, new_year: int) -> float:
    """Score the significance of a timeline change."""
    shift = abs(new_year - old_year)
    if shift >= 3:
        return 0.8
    if shift >= 2:
        return 0.6
    if shift >= 1:
        return 0.4
    return 0.2


# ── Core change detection ─────────────────────────────────────────────────

def _find_db_match(project: dict, conn) -> dict | None:
    """Find the existing DB record matching an extracted project.

    Tries norm_key first, then fuzzy name + province match.
    """
    norm_key = project.get("norm_key", "")
    if norm_key:
        row = conn.execute(
            "SELECT * FROM projects WHERE norm_key = ?", (norm_key,)
        ).fetchone()
        if row:
            return dict(row)

    # Fallback: name + province
    name = project.get("project_name") or project.get("name", "")
    province = project.get("province", "")
    if name and province:
        rows = conn.execute(
            "SELECT * FROM projects WHERE province = ? AND name LIKE ?",
            (province, f"%{name[:30]}%"),
        ).fetchall()
        if rows:
            return dict(rows[0])

    return None


def detect_changes(
    extracted_projects: list[dict],
    conn,
    sweep_id: str = "",
) -> list[dict]:
    """Compare extracted projects against their DB records.

    Args:
        extracted_projects: Newly extracted project dicts.
        conn: SQLite connection.
        sweep_id: Identifier for this sweep run.

    Returns:
        List of change records, each with:
          project_name, change_type, field, old_value, new_value,
          source_url, significance
    """
    if not CHANGE_DETECTION_ENABLED:
        return []

    changes = []
    today = date.today().isoformat()

    for proj in extracted_projects:
        name = proj.get("project_name") or proj.get("name", "Unknown")
        source_url = proj.get("source_url", "")

        db_record = _find_db_match(proj, conn)

        if db_record is None:
            # New project
            changes.append({
                "project_id": None,
                "project_name": name,
                "change_type": ChangeType.NEW_PROJECT.value,
                "field": None,
                "old_value": None,
                "new_value": name,
                "source_url": source_url,
                "significance": 0.7,
                "change_date": today,
                "sweep_id": sweep_id,
            })
            continue

        project_id = db_record.get("rowid")
        has_change = False

        # Status change
        old_status = db_record.get("status", "")
        new_status = proj.get("status", "")
        if new_status and old_status and new_status != old_status:
            sig = _score_status_change(old_status, new_status)
            changes.append({
                "project_id": project_id,
                "project_name": name,
                "change_type": ChangeType.STATUS_CHANGE.value,
                "field": "status",
                "old_value": old_status,
                "new_value": new_status,
                "source_url": source_url,
                "significance": sig,
                "change_date": today,
                "sweep_id": sweep_id,
            })
            has_change = True

        # Cost change
        old_cost = _parse_value_millions(
            db_record.get("parsed_value") or db_record.get("value")
        )
        new_cost = _parse_value_millions(
            proj.get("estimated_value") or proj.get("value")
        )
        if old_cost and new_cost and old_cost != new_cost:
            pct = abs(new_cost - old_cost) / old_cost if old_cost else 0
            if pct >= 0.10:  # only report changes >= 10%
                sig = _score_cost_change(old_cost, new_cost)
                changes.append({
                    "project_id": project_id,
                    "project_name": name,
                    "change_type": ChangeType.COST_CHANGE.value,
                    "field": "capital_cost",
                    "old_value": str(old_cost),
                    "new_value": str(new_cost),
                    "source_url": source_url,
                    "significance": sig,
                    "change_date": today,
                    "sweep_id": sweep_id,
                })
                has_change = True

        # Timeline change
        old_year = _parse_year(db_record.get("completionDate"))
        new_year = _parse_year(
            proj.get("completionDate") or proj.get("timeline")
        )
        if old_year and new_year and old_year != new_year:
            sig = _score_timeline_change(old_year, new_year)
            changes.append({
                "project_id": project_id,
                "project_name": name,
                "change_type": ChangeType.TIMELINE_CHANGE.value,
                "field": "timeline",
                "old_value": str(old_year),
                "new_value": str(new_year),
                "source_url": source_url,
                "significance": sig,
                "change_date": today,
                "sweep_id": sweep_id,
            })
            has_change = True

        # Ownership change
        old_prop = (db_record.get("proponent") or "").strip().lower()
        new_prop = (proj.get("proponent") or "").strip().lower()
        if old_prop and new_prop and old_prop != new_prop:
            changes.append({
                "project_id": project_id,
                "project_name": name,
                "change_type": ChangeType.OWNERSHIP_CHANGE.value,
                "field": "proponent",
                "old_value": db_record.get("proponent", ""),
                "new_value": proj.get("proponent", ""),
                "source_url": source_url,
                "significance": 0.5,
                "change_date": today,
                "sweep_id": sweep_id,
            })
            has_change = True

        # If no changes detected, mark as reconfirmed
        if not has_change:
            changes.append({
                "project_id": project_id,
                "project_name": name,
                "change_type": ChangeType.RECONFIRMED.value,
                "field": None,
                "old_value": None,
                "new_value": None,
                "source_url": source_url,
                "significance": 0.1,
                "change_date": today,
                "sweep_id": sweep_id,
            })

    return changes


def detect_gone_silent(conn, weeks: int = SILENT_WEEKS_THRESHOLD) -> list[dict]:
    """Find projects that haven't been seen in N weeks.

    Args:
        conn: SQLite connection.
        weeks: Number of weeks threshold.

    Returns:
        List of change records for gone-silent projects.
    """
    if not CHANGE_DETECTION_ENABLED:
        return []

    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
    today = date.today().isoformat()

    rows = conn.execute(
        "SELECT rowid, name, province, lastSeen, status FROM projects "
        "WHERE lastSeen != '' AND lastSeen < ? "
        "AND status NOT IN ('Complete', 'Cancelled', 'Abandoned')",
        (cutoff,),
    ).fetchall()

    changes = []
    for row in rows:
        r = dict(row)
        changes.append({
            "project_id": r.get("rowid"),
            "project_name": r.get("name", "Unknown"),
            "change_type": ChangeType.GONE_SILENT.value,
            "field": "lastSeen",
            "old_value": r.get("lastSeen", ""),
            "new_value": None,
            "source_url": "",
            "significance": 0.5,
            "change_date": today,
            "sweep_id": "",
        })

    if changes:
        logger.info(f"Gone-silent detection: {len(changes)} projects not seen in {weeks}+ weeks")

    return changes


# ── Persistence ───────────────────────────────────────────────────────────

def save_changes(conn, changes: list[dict]):
    """Save change records to the project_changes table.

    Args:
        conn: SQLite connection.
        changes: List of change record dicts from detect_changes().
    """
    if not changes:
        return

    for ch in changes:
        conn.execute(
            "INSERT INTO project_changes "
            "(project_id, change_date, change_type, field, old_value, "
            "new_value, source_url, significance, sweep_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ch.get("project_id"),
                ch.get("change_date", date.today().isoformat()),
                ch.get("change_type", ""),
                ch.get("field"),
                ch.get("old_value"),
                ch.get("new_value"),
                ch.get("source_url", ""),
                ch.get("significance", 0.5),
                ch.get("sweep_id", ""),
            ),
        )
    conn.commit()
    logger.info(f"Saved {len(changes)} change records to project_changes")


# ── Change summary for newsletter writing ─────────────────────────────────

def generate_change_summary(changes: list[dict]) -> str:
    """Produce a structured change summary for the newsletter writing phase.

    Groups by editorial value:
      1. Status advances (highest editorial value)
      2. Cost changes > 20%
      3. New projects (high capital cost first)
      4. Timeline shifts
      5. Gone-silent alerts
    """
    if not changes:
        return "No project changes detected this week."

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for ch in changes:
        ct = ch.get("change_type", "")
        by_type.setdefault(ct, []).append(ch)

    # Sort each group by significance (descending)
    for group in by_type.values():
        group.sort(key=lambda x: x.get("significance", 0), reverse=True)

    sections = []

    # 1. Status advances
    status_changes = by_type.get(ChangeType.STATUS_CHANGE.value, [])
    if status_changes:
        lines = [f"**Status Changes ({len(status_changes)}):**"]
        for ch in status_changes[:15]:
            lines.append(
                f"- {ch['project_name']}: {ch.get('old_value', '?')} -> "
                f"{ch.get('new_value', '?')} (significance: {ch.get('significance', 0):.1f})"
            )
        sections.append("\n".join(lines))

    # 2. Cost changes
    cost_changes = by_type.get(ChangeType.COST_CHANGE.value, [])
    if cost_changes:
        lines = [f"**Cost Changes ({len(cost_changes)}):**"]
        for ch in cost_changes[:10]:
            lines.append(
                f"- {ch['project_name']}: ${ch.get('old_value', '?')}M -> "
                f"${ch.get('new_value', '?')}M"
            )
        sections.append("\n".join(lines))

    # 3. New projects
    new_projects = by_type.get(ChangeType.NEW_PROJECT.value, [])
    if new_projects:
        lines = [f"**New Projects ({len(new_projects)}):**"]
        for ch in new_projects[:20]:
            lines.append(f"- {ch['project_name']}")
        sections.append("\n".join(lines))

    # 4. Timeline shifts
    timeline_changes = by_type.get(ChangeType.TIMELINE_CHANGE.value, [])
    if timeline_changes:
        lines = [f"**Timeline Changes ({len(timeline_changes)}):**"]
        for ch in timeline_changes[:10]:
            lines.append(
                f"- {ch['project_name']}: {ch.get('old_value', '?')} -> "
                f"{ch.get('new_value', '?')}"
            )
        sections.append("\n".join(lines))

    # 5. Gone silent
    silent = by_type.get(ChangeType.GONE_SILENT.value, [])
    if silent:
        lines = [f"**Gone Silent ({len(silent)}):**"]
        for ch in silent[:10]:
            lines.append(
                f"- {ch['project_name']} (last seen: {ch.get('old_value', 'unknown')})"
            )
        sections.append("\n".join(lines))

    # 6. Reconfirmed count
    reconfirmed = by_type.get(ChangeType.RECONFIRMED.value, [])
    if reconfirmed:
        sections.append(f"**Reconfirmed:** {len(reconfirmed)} projects seen with no changes")

    # Stats
    total = len(changes)
    high_sig = sum(1 for c in changes if c.get("significance", 0) >= 0.7)
    sections.insert(0, f"**Weekly Change Summary:** {total} changes detected, {high_sig} high-significance")

    return "\n\n".join(sections)
