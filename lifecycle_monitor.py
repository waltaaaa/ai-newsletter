"""
lifecycle_monitor.py -- Automated Gemini-based status monitoring for tracked projects.

Selects high-value stale projects and runs targeted Gemini grounded search
queries to check for status changes, delays, cost revisions, or completions.

Reuses the async Gemini pattern from cost_finder.py.
"""

import asyncio
import aiohttp
import json
import re
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
MAX_CONCURRENT = 10
RETRY_DELAY = 60
MAX_MONITOR_PER_RUN = 20

MONITOR_SYSTEM_PROMPT = """You are a Canadian infrastructure project analyst. For the project described, check if there have been any recent updates, milestones, delays, cost changes, or completion announcements.

Respond with ONLY a JSON object (no markdown fences):
{
  "status": "Under Construction",
  "status_changed": true,
  "detail": "1-2 sentence description of the latest update",
  "value_change": null,
  "completion_update": null,
  "source_description": "Source name and date"
}

Rules:
- status: one of "Proposed", "Approved", "Under Construction", "Completed", "Cancelled", "Suspended", "Delayed"
- status_changed: true if the status differs from what was provided, false otherwise
- detail: specific factual update (e.g., "Construction reached 60% completion in Feb 2026")
- value_change: new value in millions CAD if cost changed, null if unchanged
- completion_update: new expected completion date if changed, null if unchanged
- If no updates found, respond: {"status_changed": false, "detail": "No recent updates found"}
"""


def _parse_value_string(val_str):
    """Parse a value string like 'C$650M' into millions float."""
    if not val_str:
        return 0
    s = str(val_str).upper().replace(',', '')
    m = re.match(r'[C$]*\s*(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return 0
    n = float(m.group(1))
    unit = m.group(2) or 'M'
    if unit == 'B':
        n *= 1000
    elif unit == 'K':
        n /= 1000
    return n


def select_projects_for_monitoring(conn, max_candidates=MAX_MONITOR_PER_RUN):
    """Select high-value stale projects for status monitoring.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)
    """
    candidates = []
    now = datetime.utcnow()

    if hasattr(conn, 'execute'):
        from db import get_all_projects
        all_projects = get_all_projects(conn)
        for data in all_projects:
            doc_id = data.get("norm_key", "")
            if not doc_id:
                continue

            status = (data.get("status") or "").lower()
            if status in ("cancelled", "canceled", "completed"):
                continue

            last_seen = data.get("lastSeen") or data.get("lastUpdated") or ""
            days_since = 9999
            if last_seen:
                try:
                    ls = datetime.fromisoformat(str(last_seen)[:10])
                    days_since = (now - ls).days
                except (ValueError, TypeError):
                    pass

            last_monitor = data.get("last_lifecycle_check", "")
            if last_monitor:
                try:
                    lm = datetime.fromisoformat(str(last_monitor)[:10])
                    if (now - lm).days < 21:
                        continue
                except (ValueError, TypeError):
                    pass

            value_m = _parse_value_string(data.get("value", ""))

            priority = 0
            if value_m >= 500 and days_since >= 30:
                priority = 100 + value_m / 100
            elif value_m >= 100 and days_since >= 60:
                priority = 50 + value_m / 100
            elif "construction" in status and days_since >= 45:
                priority = 30
            elif data.get("is_stale"):
                priority = 10

            if priority > 0:
                candidates.append((doc_id, data, priority))

        candidates.sort(key=lambda x: x[2], reverse=True)
        return [(did, d) for did, d, _ in candidates[:max_candidates]]

    # Legacy Firestore path
    for doc in conn.collection("projects").stream():
        data = doc.to_dict()
        doc_id = doc.id

        # Skip cancelled/completed
        status = (data.get("status") or "").lower()
        if status in ("cancelled", "canceled", "completed"):
            continue

        # Calculate days since last update
        last_seen = data.get("lastSeen") or data.get("lastUpdated") or ""
        days_since = 9999
        if last_seen:
            try:
                ls = datetime.fromisoformat(str(last_seen)[:10])
                days_since = (now - ls).days
            except (ValueError, TypeError):
                pass

        # Skip recently monitored
        last_monitor = data.get("last_lifecycle_check", "")
        if last_monitor:
            try:
                lm = datetime.fromisoformat(str(last_monitor)[:10])
                if (now - lm).days < 21:
                    continue
            except (ValueError, TypeError):
                pass

        # Parse value for prioritization
        value_m = _parse_value_string(data.get("value", ""))

        priority = 0
        if value_m >= 500 and days_since >= 30:
            priority = 100 + value_m / 100
        elif value_m >= 100 and days_since >= 60:
            priority = 50 + value_m / 100
        elif "construction" in status and days_since >= 45:
            priority = 30
        elif data.get("is_stale"):
            priority = 10

        if priority > 0:
            candidates.append((doc_id, data, priority))

    candidates.sort(key=lambda x: x[2], reverse=True)
    result = [(did, d) for did, d, _ in candidates[:max_candidates]]
    return result


def build_monitor_query(doc_id, project):
    """Build a Gemini query to check a project's current status."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    status = project.get("status", "unknown")
    value = project.get("value", "")

    location = f"{cma}, {province}" if cma else province
    value_str = f" (estimated {value})" if value and value != "--" else ""

    return {
        "query": (
            f"What is the current status of the {name} project in "
            f"{location}, Canada{value_str}? Has there been any update, "
            f"milestone, delay, cost change, or completion announcement "
            f"in the past 8 weeks? Previous known status: {status}."
        ),
        "type": "lifecycle_monitor",
        "doc_id": doc_id,
        "project_name": name,
        "previous_status": status,
    }


async def _query_gemini_monitor(session, semaphore, query_obj, attempt=0):
    """Send one lifecycle monitoring query to Gemini."""
    from gemini_engine import query_one
    result = await query_one(session, semaphore, query_obj,
                             MONITOR_SYSTEM_PROMPT, attempt)
    if result.get("error"):
        return {"error": result["error"], "query": query_obj}

    text = result.get("text", "")
    grounding_urls = [g["url"] if isinstance(g, dict) else g
                      for g in result.get("grounding_urls", [])]

    # Parse JSON from text
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)

    obj_start = text.find('{')
    if obj_start >= 0:
        depth = 0
        for i in range(obj_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[obj_start:i + 1])
                        data["_grounding_urls"] = grounding_urls
                        return {"update": data, "query": query_obj}
                    except json.JSONDecodeError:
                        pass
                    break

    return {"update": None, "query": query_obj}


async def run_lifecycle_monitoring(conn):
    """Run lifecycle monitoring for high-value stale projects.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)
    """
    if not GEMINI_API_KEY:
        print("  [MONITOR] No GEMINI_API_KEY -- skipping.")
        return {"updated": 0, "checked": 0, "errors": 0}

    candidates = select_projects_for_monitoring(conn)
    if not candidates:
        print("  [MONITOR] No projects need monitoring.")
        return {"updated": 0, "checked": 0, "errors": 0}

    queries = [build_monitor_query(did, p) for did, p in candidates]
    print(f"  [MONITOR] Checking {len(queries)} high-value projects...")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with aiohttp.ClientSession() as session:
        tasks = [_query_gemini_monitor(session, semaphore, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    updated = 0
    errors = 0
    now_iso = datetime.utcnow().isoformat()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    use_sqlite = hasattr(conn, 'execute')

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            errors += 1
            continue
        if r.get("error"):
            errors += 1
            continue

        doc_id = r["query"]["doc_id"]
        update = r.get("update")
        if not update:
            continue

        updates = {"last_lifecycle_check": now_iso}

        if update.get("status_changed") and update.get("status"):
            new_status = update["status"]
            detail = update.get("detail", "")
            old_status = r["query"]["previous_status"]

            updates["status"] = new_status
            updates["lastSeen"] = today
            updates["lastUpdated"] = today

            # Append to statusHistory
            if use_sqlite:
                try:
                    row = conn.execute(
                        "SELECT statusHistory FROM projects WHERE norm_key = ?",
                        (doc_id,),
                    ).fetchone()
                    history = json.loads(row["statusHistory"] or "[]") if row else []
                    entry = {
                        "date": today,
                        "status": new_status,
                        "note": f"Status: {old_status} -> {new_status}",
                        "detail": detail,
                    }
                    urls = update.get("_grounding_urls", [])
                    if urls:
                        entry["source"] = {"url": urls[0], "title": ""}
                    history.append(entry)
                    updates["statusHistory"] = json.dumps(history, ensure_ascii=False)
                except Exception:
                    pass
            else:
                try:
                    doc_ref = conn.collection("projects").document(doc_id)
                    existing = doc_ref.get().to_dict() or {}
                    history = existing.get("statusHistory", [])
                    entry = {
                        "date": today,
                        "status": new_status,
                        "note": f"Status: {old_status} -> {new_status}",
                        "detail": detail,
                    }
                    urls = update.get("_grounding_urls", [])
                    if urls:
                        entry["source"] = {"url": urls[0], "title": ""}
                    history.append(entry)
                    updates["statusHistory"] = history
                except Exception:
                    pass

            # Value change
            if update.get("value_change"):
                val = update["value_change"]
                if val >= 1000:
                    updates["value"] = f"C${val / 1000:.1f}B"
                else:
                    updates["value"] = f"C${val:.0f}M"

            updated += 1
            print(f"    Updated: {r['query']['project_name'][:40]} "
                  f"({old_status} -> {new_status})")
        else:
            updates["lastSeen"] = today

        # Apply updates
        if use_sqlite:
            set_clauses = [f"{k} = ?" for k in updates]
            params = list(updates.values()) + [doc_id]
            try:
                with conn:
                    conn.execute(
                        f"UPDATE projects SET {', '.join(set_clauses)} WHERE norm_key = ?",
                        params,
                    )
            except Exception as e:
                logger.warning(f"[MONITOR] Update failed for {doc_id}: {e}")
        else:
            conn.collection("projects").document(doc_id).update(updates)

    print(f"  [MONITOR] {updated} status changes, "
          f"{len(candidates) - updated - errors} unchanged, {errors} errors")

    return {"updated": updated, "checked": len(candidates), "errors": errors}


def run_lifecycle_search(conn):
    """Synchronous wrapper for run_lifecycle_monitoring()."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            print("  [MONITOR] Cannot run in existing event loop")
            return {"updated": 0, "checked": 0, "errors": 0}
        return loop.run_until_complete(run_lifecycle_monitoring(conn))
    else:
        return asyncio.run(run_lifecycle_monitoring(conn))
