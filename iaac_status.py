"""
IAAC project status tracker — monitors the Impact Assessment Registry for
status changes on projects under federal assessment.

Enhances the existing Tier 1 IAAC scraper by tracking status transitions:
- New submissions -> Proposed
- Planning phase -> Under Review
- Public comment period -> Under Review
- Panel review -> Under Review
- Decision statement issued -> Approved / Not Approved
- Conditions set -> Approved (with conditions)
- Post-decision monitoring -> Under Construction (if construction reported)

Uses the public IAAC Registry API (free, no key required).
Reuses IAAC scraping infrastructure from gov_sources.py.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Map IAAC assessment phases to our project status taxonomy
IAAC_STATUS_MAP = {
    "Planning Phase": "Under Review",
    "Impact Statement": "Under Review",
    "Public Comment": "Under Review",
    "Panel Review": "Under Review",
    "Decision Statement": "Approved",
    "Post Decision - Follow-up Programs": "Under Construction",
    "Comprehensive Study": "Under Review",
    "Screening": "Under Review",
    "Substitution": "Under Review",
    "Terminated": "Cancelled",
    "Withdrawn": "Cancelled",
}

# IAAC sectors to our NAICS keys
IAAC_SECTOR_MAP = {
    "Oil and Gas": "oil_gas",
    "Mining": "mining",
    "Hydro": "power_energy",
    "Nuclear": "power_energy",
    "Transportation": "transport_logistics",
    "Industrial": "manufacturing",
    "Marine": "transport_logistics",
    "Defence": "defence",
    "Waste Management": "environment",
}


def fetch_iaac_projects():
    """
    Fetch projects from the IAAC Registry by reusing the existing scraper
    from gov_sources.py. Returns list of project dicts with status info.
    """
    try:
        from gov_sources import _scrape_iaac
        projects = _scrape_iaac()
        print(f"[IAAC-STATUS] Fetched {len(projects)} projects from registry")
        return projects
    except ImportError:
        print("[WARN] Could not import _scrape_iaac from gov_sources")
        return []
    except Exception as e:
        print(f"[WARN] IAAC status fetch failed: {e}")
        return []


def detect_status_changes(iaac_projects, conn):
    """
    Compare IAAC project statuses against the database and flag changes.

    Returns list of status change events.
    """
    from db import _should_update_status
    cursor = conn.cursor()
    changes = []

    for proj in iaac_projects:
        iaac_name = proj.get("name", "")
        iaac_status = proj.get("status", "")

        if not iaac_status or not iaac_name:
            continue

        # Use the first significant word(s) for fuzzy matching
        # IAAC names are typically formal project names
        name_words = iaac_name.split()
        first_word = name_words[0] if name_words else ""

        try:
            cursor.execute("""
                SELECT name, status, province, sector, value
                FROM projects
                WHERE name LIKE ? OR name LIKE ?
                ORDER BY value DESC
                LIMIT 1
            """, (f"%{iaac_name}%", f"%{first_word}%"))

            match = cursor.fetchone()

            if match:
                db_name = match["name"] if hasattr(match, "keys") else match[0]
                db_status = match["status"] if hasattr(match, "keys") else match[1]
                db_province = match["province"] if hasattr(match, "keys") else match[2]
                db_sector = match["sector"] if hasattr(match, "keys") else match[3]
                db_value = match["value"] if hasattr(match, "keys") else match[4]

                # Only report if status would actually change per non-regression rule
                if db_status != iaac_status and _should_update_status(db_status, iaac_status):
                    changes.append({
                        "project_name": db_name,
                        "iaac_name": iaac_name,
                        "old_status": db_status,
                        "new_status": iaac_status,
                        "province": db_province,
                        "sector": db_sector,
                        "value": db_value,
                        "source": proj.get("source_url", ""),
                        "update_date": datetime.now().strftime("%Y-%m-%d"),
                    })
            else:
                # IAAC project not in database — new discovery
                changes.append({
                    "project_name": iaac_name,
                    "iaac_name": iaac_name,
                    "old_status": None,
                    "new_status": iaac_status,
                    "province": proj.get("province"),
                    "sector": proj.get("sector", "infrastructure"),
                    "value": proj.get("value"),
                    "source": proj.get("source_url", ""),
                    "update_date": datetime.now().strftime("%Y-%m-%d"),
                    "is_new_discovery": True,
                })

        except Exception as e:
            logger.debug(f"[IAAC-STATUS] Status check failed for {iaac_name}: {e}")

    if changes:
        print(f"[IAAC-STATUS] Detected {len(changes)} status changes")

    return changes


def apply_status_changes(changes, conn):
    """
    Apply detected status changes to the database via upsert_project.
    Respects non-regression rule (handled by db.upsert_project).
    """
    from db import upsert_project

    applied = 0
    for change in changes:
        # Skip entries with missing name or province (required by db.upsert_project)
        if not change.get("project_name") or not change.get("province"):
            continue

        if change.get("is_new_discovery"):
            # New project — insert via upsert_project with URL hard gate
            source_url = change.get("source", "")
            if not source_url:
                continue  # URL hard gate — no URL = no write

            upsert_project(conn, {
                "name": change["project_name"],
                "province": change["province"],
                "status": change["new_status"],
                "source_url": source_url,
                "discovery_source": "iaac_status_tracker",
                "sector": change.get("sector", "infrastructure"),
                "value": change.get("value"),
                "evidence": [{"url": source_url, "date": change.get("update_date", ""),
                              "source": "IAAC Registry"}],
            })
            applied += 1
        else:
            # Existing project — update status via upsert_project
            # upsert_project internally enforces non-regression
            source_url = change.get("source", "")
            upsert_project(conn, {
                "name": change["project_name"],
                "province": change.get("province", ""),
                "status": change["new_status"],
                "source_url": source_url or "",
                "discovery_source": "iaac_status_tracker",
                "sector": change.get("sector", ""),
                "evidence": [{"url": source_url, "date": change.get("update_date", ""),
                              "source": "IAAC Registry Status Update"}] if source_url else [],
            })
            applied += 1

    if applied:
        conn.commit()
        print(f"[IAAC-STATUS] Applied {applied} status updates to database")

    return applied


def run_iaac_status(conn):
    """
    Main entry point. Fetch IAAC projects, detect status changes, apply updates.

    Returns dict with IAAC status data for pipeline context.
    """
    projects = fetch_iaac_projects()
    changes = detect_status_changes(projects, conn)

    # Apply changes to database
    applied = 0
    update_changes = [c for c in changes if not c.get("is_new_discovery")]
    new_discoveries = [c for c in changes if c.get("is_new_discovery")]

    if update_changes or new_discoveries:
        applied = apply_status_changes(changes, conn)

    # Warehouse instrumentation (RC-6): record the tracker outcome. Zero
    # projects fetched means the registry scrape failed (statuses silently
    # not updated today) — record it as failed. Never raises.
    try:
        from data_warehouse import record_run
        record_run("iaac_status_tracker",
                   "ok" if projects else "failed",
                   items_fetched=len(projects), items_saved=applied,
                   error="" if projects else "0 projects from IAAC registry — no status updates applied",
                   conn=conn)
    except Exception as _wh_e:
        print(f"[WAREHOUSE] iaac_status recording failed (non-critical): {_wh_e}")

    return {
        "iaac_projects_checked": len(projects),
        "iaac_status_changes": update_changes,
        "iaac_new_discoveries": new_discoveries,
        "iaac_updates_applied": applied,
    }
