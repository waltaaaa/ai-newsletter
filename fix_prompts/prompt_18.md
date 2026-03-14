Run this with: `claude -p "$(cat fix_prompts/prompt_18.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to enhance the existing IAAC (Impact Assessment Agency of Canada) tracking to capture project status changes, not just initial registrations. Status transitions through the assessment process are direct confirmations of project progress. Read the relevant files before making changes.

## Context

The existing Tier 1 IAAC scraper in `gov_sources.py` catches new project registrations, but the IAAC Registry also publishes timeline updates: when a project moves from public comment to panel review, when a decision statement is issued, when conditions are set. Each of these is a status change event that should update the corresponding project record in the database.

IAAC has a public API at `https://iaac-aeic.gc.ca/050/evaluations` that supports searching by project status and date range.

## Part 1: Create `iaac_status.py`

```python
"""
IAAC project status tracker — monitors the Impact Assessment Registry for
status changes on projects under federal assessment.

Enhances the existing Tier 1 IAAC scraper by tracking status transitions:
- New submissions → Proposed
- Planning phase → Under Review 
- Public comment period → Under Review
- Panel review → Under Review
- Decision statement issued → Approved / Not Approved
- Conditions set → Approved (with conditions)
- Post-decision monitoring → Under Construction (if construction reported)

Uses the public IAAC Registry API (free, no key required).
"""
import requests
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

IAAC_API_BASE = "https://iaac-aeic.gc.ca/050/evaluations"

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


def fetch_iaac_projects(days_back=30):
    """
    Fetch projects from the IAAC Registry that have had status updates
    in the specified timeframe.
    """
    projects = []
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    try:
        # The IAAC registry supports search by date range
        # Try the HTML page with date filter, then parse
        url = f"{IAAC_API_BASE}"
        params = {
            "culture": "en-CA",
            "sortby": "LastUpdate",
            "ascending": "false",
        }
        
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"[IAAC] Registry returned {resp.status_code}")
            return []
        
        # Parse the IAAC registry response
        # NOTE: The IAAC API format may be HTML or JSON depending on endpoint.
        # Check existing gov_sources.py for the current IAAC parsing pattern
        # and extend it rather than writing a new parser.
        
        projects = _parse_iaac_response(resp.text)
        print(f"[IAAC] Found {len(projects)} projects with recent updates")
        
    except Exception as e:
        print(f"[WARN] IAAC status fetch failed: {e}")
    
    return projects


def _parse_iaac_response(html_or_json):
    """
    Parse IAAC registry response. Implementation depends on the response format.
    Check existing gov_sources.py for the pattern used and extend it.
    """
    # IMPORTANT: Read gov_sources.py first to see how IAAC is currently parsed.
    # Extend that parser to also extract:
    # - current assessment phase
    # - last update date
    # - decision status (if available)
    # - conditions (if post-decision)
    projects = []
    return projects


def detect_status_changes(iaac_projects, conn):
    """
    Compare IAAC project statuses against the database and flag changes.
    
    Returns list of status change events.
    """
    cursor = conn.cursor()
    changes = []
    
    for iaac_project in iaac_projects:
        iaac_name = iaac_project.get("name", "")
        iaac_phase = iaac_project.get("phase", "")
        new_status = IAAC_STATUS_MAP.get(iaac_phase)
        
        if not new_status or not iaac_name:
            continue
        
        # Try to find matching project in database
        try:
            cursor.execute("""
                SELECT name, status, province, sector, value
                FROM projects
                WHERE name LIKE ? OR name LIKE ?
                ORDER BY value DESC
                LIMIT 1
            """, (f"%{iaac_name}%", f"%{iaac_name.split()[0]}%"))
            
            match = cursor.fetchone()
            
            if match:
                db_name, db_status, db_province, db_sector, db_value = match
                
                if db_status != new_status:
                    changes.append({
                        "project_name": db_name,
                        "iaac_name": iaac_name,
                        "old_status": db_status,
                        "new_status": new_status,
                        "iaac_phase": iaac_phase,
                        "province": db_province,
                        "sector": db_sector,
                        "value": db_value,
                        "source": iaac_project.get("url", ""),
                        "update_date": iaac_project.get("last_update", ""),
                    })
            else:
                # IAAC project not in database — could be a new discovery
                changes.append({
                    "project_name": iaac_name,
                    "iaac_name": iaac_name,
                    "old_status": None,
                    "new_status": new_status,
                    "iaac_phase": iaac_phase,
                    "province": iaac_project.get("province"),
                    "sector": _map_sector(iaac_project),
                    "value": iaac_project.get("value"),
                    "source": iaac_project.get("url", ""),
                    "update_date": iaac_project.get("last_update", ""),
                    "is_new_discovery": True,
                })
                
        except Exception as e:
            logger.debug(f"[IAAC] Status check failed for {iaac_name}: {e}")
    
    if changes:
        print(f"[IAAC] Detected {len(changes)} status changes")
    
    return changes


def _map_sector(iaac_project):
    """Map IAAC project type to NAICS sector key."""
    project_type = iaac_project.get("type", "")
    return IAAC_SECTOR_MAP.get(project_type, "infrastructure")


def run_iaac_status(conn, days_back=30):
    """
    Main entry point. Fetch IAAC projects, detect status changes.
    
    Returns dict with IAAC status data for pipeline context.
    """
    projects = fetch_iaac_projects(days_back)
    changes = detect_status_changes(projects, conn)
    
    return {
        "iaac_projects_checked": len(projects),
        "iaac_status_changes": changes,
        "iaac_new_discoveries": [c for c in changes if c.get("is_new_discovery")],
    }
```

**CRITICAL:** Before implementing the parser, read `gov_sources.py` to see how IAAC is currently handled. Extend the existing pattern — do not duplicate or replace it. The `_parse_iaac_response` function should reuse whatever parsing logic already exists.

## Part 2: Integrate into discovery phase

File: `phases/discovery.py`

Add after existing Tier 1 government source processing:

```python
try:
    from iaac_status import run_iaac_status
    iaac_results = run_iaac_status(conn)
    context.update(iaac_results)
    
    # Apply status changes to projects
    for change in iaac_results.get("iaac_status_changes", []):
        if not change.get("is_new_discovery") and change["old_status"] != change["new_status"]:
            # Update project status (respecting non-regression rule)
            _update_project_status(conn, change)
            
except ImportError:
    print("[WARN] iaac_status not available")
except Exception as e:
    print(f"[WARN] IAAC status tracking failed: {e}")
```

Make sure the status update respects the non-regression rule from CLAUDE.md — status only advances forward in the progression, never backwards.

## Part 3: Update CLAUDE.md

Add to Repository Layout:
```
├── iaac_status.py              # IAAC assessment status change tracker
```

Add to Discovery section:
```
IAAC Status Tracker: Monitors the federal Impact Assessment Registry for
status transitions on projects under assessment. Maps IAAC phases to project
statuses and updates the database when projects advance through the assessment
process. Also detects IAAC projects not yet in the database as new discoveries.
Enhances existing Tier 1 IAAC registration tracking. Zero cost.
```

## Important constraints

- Read `gov_sources.py` first — extend, don't replace
- Status updates must respect the non-regression rule (status only advances)
- IAAC is federal only — provincial EA status tracking is separate (Tier 5) and handled by existing code
- The IAAC website occasionally changes its HTML structure. The parser should fail gracefully.
- "Terminated" and "Withdrawn" map to "Cancelled" — these ARE valid status regressions (terminal states always override per CLAUDE.md)
