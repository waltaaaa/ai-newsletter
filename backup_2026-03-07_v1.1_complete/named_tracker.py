"""
named_tracker.py -- Weekly status updates for top 200 projects by value.

Tier 4 of STEP_2J capacity utilization.
Maintains a watchlist of highest-value projects and runs targeted status
queries each week to catch granular updates (subcontract awards, phase
completions, regulatory decisions, timeline revisions).

Budget: 50 queries/day = 350/week
Rotation: 200 projects / 4 batches = 50/batch (checked once per 4 weeks)
"""

import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_TRACKING_PER_RUN = 50
WATCHLIST_SIZE = 200

TRACKING_SYSTEM_PROMPT = """You are a Canadian infrastructure project analyst providing weekly status updates.
For the named project, search for the most recent news and government announcements.
Focus on changes from the past 4 weeks.

Return ONLY a valid JSON object (no markdown fences):
{
  "has_update": true,
  "status": "Under Construction",
  "status_changed": false,
  "milestone": "Construction reached 60% in Feb 2026",
  "value_change_millions": null,
  "completion_update": null,
  "detail": "Brief description of the latest news",
  "source_url": "https://example.com/article",
  "source_name": "Publication name",
  "date_reported": "2026-03-01"
}

Rules:
- has_update: true if you found any news in the past 4 weeks, false if nothing found
- status: current status (Proposed, Approved, Under Construction, Completed, Cancelled, Delayed)
- status_changed: true only if status differs from what was provided
- milestone: specific progress update if found, null if none
- value_change_millions: new value in millions CAD if cost changed, null if same
- completion_update: new expected completion date if changed, null if same
- detail: 1-2 sentence factual summary of latest news
- If no updates found, return {"has_update": false, "detail": "No recent updates found"}
"""


def select_top_projects(db, max_candidates=MAX_TRACKING_PER_RUN):
    """Select top projects by value for weekly tracking.

    Takes the top 200 by value, excludes recently checked and terminal statuses,
    returns the 50 least-recently-checked.
    """
    candidates = []
    now = datetime.utcnow()

    for doc in db.collection("projects").stream():
        data = doc.to_dict()

        status = (data.get("status") or "").lower()
        if status in ("cancelled", "canceled"):
            continue

        # Skip recently checked
        last_check = data.get("last_named_check", "")
        if last_check:
            try:
                lc = datetime.fromisoformat(str(last_check)[:10])
                if (now - lc).days < 7:
                    continue
            except (ValueError, TypeError):
                pass

        value_m = _parse_value(data.get("value", ""))
        days_since_check = 9999
        if last_check:
            try:
                lc = datetime.fromisoformat(str(last_check)[:10])
                days_since_check = (now - lc).days
            except (ValueError, TypeError):
                pass

        candidates.append((doc.id, data, value_m, days_since_check))

    # Sort by value descending, take top WATCHLIST_SIZE
    candidates.sort(key=lambda x: x[2], reverse=True)
    watchlist = candidates[:WATCHLIST_SIZE]

    # From watchlist, sort by least-recently-checked, take max_candidates
    watchlist.sort(key=lambda x: x[3], reverse=True)
    return [(did, d) for did, d, _, _ in watchlist[:max_candidates]]


def build_tracking_query(doc_id, project):
    """Build a targeted status update query for a watchlisted project."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    proponent = project.get("proponent", "")
    status = project.get("status", "unknown")
    value = project.get("value", "")

    location = f"{cma}, {province}" if cma else province
    value_str = f" (estimated {value})" if value and value not in ("", "--", "Not disclosed") else ""
    proponent_str = f" by {proponent}" if proponent and proponent != "Unknown" else ""

    return {
        "query": (
            f"What is the latest news about the {name} project{proponent_str} "
            f"in {location}, Canada{value_str}? "
            f"Current known status: {status}. "
            f"Has there been any update in the past four weeks including: "
            f"construction milestones, contract awards, regulatory decisions, "
            f"timeline changes, cost revisions, phase completions, partner changes, "
            f"community consultations, environmental approvals, or government funding? "
            f"For each update found, provide: what changed, the date, and the source URL."
        ),
        "type": "named_tracking",
        "doc_id": doc_id,
        "project_name": name,
        "previous_status": status,
    }


def _parse_tracking_result(engine_result):
    """Parse a tracking query result from gemini_engine."""
    text = engine_result.get("text", "")
    grounding_urls = [g["url"] if isinstance(g, dict) else g
                      for g in engine_result.get("grounding_urls", [])]

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
                        return data
                    except json.JSONDecodeError:
                        pass
                    break

    return {"has_update": False, "_grounding_urls": grounding_urls}


def apply_tracking_results(db, results):
    """Write tracking results to Firestore.

    Returns {"updated": int, "checked": int, "errors": int}
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    updated = 0
    checked = 0
    errors = 0

    for r in results:
        if r.get("error"):
            errors += 1
            continue

        doc_id = r["query"]["doc_id"]
        parsed = r.get("parsed")
        if not parsed:
            errors += 1
            continue

        doc_ref = db.collection("projects").document(doc_id)
        updates = {
            "last_named_check": today,
            "lastSeen": today,
        }

        if parsed.get("has_update") and parsed.get("detail"):
            checked += 1

            # Status change
            if parsed.get("status_changed") and parsed.get("status"):
                new_status = parsed["status"]
                old_status = r["query"]["previous_status"]
                updates["status"] = new_status
                updates["lastUpdated"] = today

                # Append to statusHistory
                try:
                    existing = doc_ref.get().to_dict() or {}
                    history = existing.get("statusHistory", [])
                    entry = {
                        "date": today,
                        "status": new_status,
                        "note": f"Status: {old_status} -> {new_status}",
                        "detail": parsed.get("detail", ""),
                    }
                    urls = parsed.get("_grounding_urls", [])
                    if urls:
                        entry["source"] = {"url": urls[0], "title": ""}
                    elif parsed.get("source_url"):
                        entry["source"] = {
                            "url": parsed["source_url"],
                            "title": parsed.get("source_name", ""),
                        }
                    history.append(entry)
                    updates["statusHistory"] = history
                except Exception:
                    pass

                updated += 1
                print(f"    [TRACK] {r['query']['project_name'][:40]} "
                      f"({old_status} -> {new_status})")

            # Value change
            val_m = parsed.get("value_change_millions")
            if val_m and val_m > 0:
                if val_m >= 1000:
                    updates["value"] = f"C${val_m/1000:.1f}B"
                else:
                    updates["value"] = f"C${val_m:.0f}M"
                updates["lastUpdated"] = today
                updated += 1

            # Milestone (no status change but still a meaningful update)
            if parsed.get("milestone") and not parsed.get("status_changed"):
                try:
                    existing = doc_ref.get().to_dict() or {}
                    history = existing.get("statusHistory", [])
                    entry = {
                        "date": today,
                        "status": parsed.get("status", r["query"]["previous_status"]),
                        "note": parsed["milestone"],
                        "detail": parsed.get("detail", ""),
                    }
                    urls = parsed.get("_grounding_urls", [])
                    if urls:
                        entry["source"] = {"url": urls[0], "title": ""}
                    history.append(entry)
                    updates["statusHistory"] = history
                    updates["lastUpdated"] = today
                except Exception:
                    pass
        else:
            checked += 1

        doc_ref.update(updates)

    return {"updated": updated, "checked": checked, "errors": errors}


async def run_named_tracking_async(db, max_queries=MAX_TRACKING_PER_RUN):
    """Run tracking queries for top projects by value."""
    from gemini_engine import run_batch

    candidates = select_top_projects(db, max_queries)
    if not candidates:
        print("  [TRACK] No projects need tracking this run.")
        return {"updated": 0, "checked": 0, "errors": 0}

    queries = [build_tracking_query(did, p) for did, p in candidates]
    print(f"  [TRACK] Checking {len(queries)} high-value projects...")

    raw_results = await run_batch(queries, TRACKING_SYSTEM_PROMPT,
                                  max_concurrent=10, tag="TRACK")

    results = []
    for r in raw_results:
        parsed = _parse_tracking_result(r)
        results.append({
            "query": r["query"],
            "parsed": parsed,
            "error": r.get("error"),
        })

    summary = apply_tracking_results(db, results)
    print(f"  [TRACK] {summary['updated']} updates, "
          f"{summary['checked']} checked, {summary['errors']} errors")
    return summary


def run_named_tracking_sync(db, max_queries=MAX_TRACKING_PER_RUN):
    """Synchronous wrapper."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                run_named_tracking_async(db, max_queries))
        else:
            return asyncio.run(run_named_tracking_async(db, max_queries))
    except RuntimeError:
        return asyncio.run(run_named_tracking_async(db, max_queries))


def _parse_value(val_str):
    """Parse value string to millions float."""
    if not val_str:
        return 0
    s = str(val_str).upper().replace(',', '').replace('$', '').replace('C', '')
    m = re.match(r'\s*(\d+(?:\.\d+)?)\s*(B|M|K)?', s)
    if not m:
        return 0
    n = float(m.group(1))
    unit = (m.group(2) or 'M')
    if unit == 'B':
        n *= 1000
    elif unit == 'K':
        n /= 1000
    return n
