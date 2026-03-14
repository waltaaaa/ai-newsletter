"""
deep_verification.py -- Second-source confirmation for single-source projects.

Tier 1 of STEP_2J capacity utilization.
Finds projects with only one evidence URL and runs a targeted verification
query to find independent confirmation. Boosts confidence when confirmed,
flags for review when not.

Budget: 50 queries/day = 350/week
"""

import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_VERIFICATION_PER_RUN = 50

VERIFY_SYSTEM_PROMPT = """You are a fact-checker for a Canadian infrastructure intelligence system.
Your job is to independently verify that a specific capital project exists and is real.
Search for the project name and proponent. Check government sites, news, and corporate announcements.

Return ONLY a valid JSON object (no markdown fences):
{
  "confirmed": true,
  "status": "Under Construction",
  "value_millions": 650,
  "source_url": "https://example.com/article",
  "source_name": "Source publication",
  "confidence_notes": "Any caveats or notes"
}

Rules:
- confirmed: true if you found independent evidence the project exists, false otherwise
- status: current project status if found (Proposed, Approved, Under Construction, Completed, Cancelled, Delayed)
- value_millions: project cost in millions CAD if found, null if not
- source_url: URL of the best independent source found
- source_name: name of the publication or organization
- If you cannot find independent evidence, set confirmed to false
- Do NOT fabricate information. If unsure, set confirmed to false
"""


def select_projects_for_verification(conn, max_candidates=MAX_VERIFICATION_PER_RUN):
    """Select single-source projects needing independent confirmation.

    Priority (highest first):
    1. evidence_count == 1, no gov/known source, high value
    2. evidence_count == 1, low confidence
    3. evidence_count == 1, recently discovered

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns list of (doc_id, project_dict).
    """
    candidates = []
    now = datetime.utcnow()

    if hasattr(conn, 'execute'):
        from db import get_all_projects
        import json as _json
        all_projects = get_all_projects(conn)
        for data in all_projects:
            evidence_raw = data.get("evidence", "[]")
            if isinstance(evidence_raw, str):
                try:
                    evidence = _json.loads(evidence_raw)
                except Exception:
                    evidence = []
            else:
                evidence = evidence_raw or []
            evidence_count = len(evidence)

            if evidence_count != 1:
                continue

            status = (data.get("status") or "").lower()
            if status in ("cancelled", "canceled", "completed"):
                continue

            last_check = data.get("last_verification_check", "")
            if last_check:
                try:
                    lc = datetime.fromisoformat(str(last_check)[:10])
                    if (now - lc).days < 30:
                        continue
                except (ValueError, TypeError):
                    pass

            value_m = _parse_value(data.get("value", ""))
            confidence = data.get("confidence", 0.5)
            has_gov = bool(data.get("has_government_source", False))
            has_known = bool(data.get("has_known_source", False))

            priority = value_m
            if not has_gov and not has_known:
                priority *= 2
            if confidence < 0.4:
                priority *= 1.5

            candidates.append((data.get("norm_key", ""), data, priority))

        candidates.sort(key=lambda x: x[2], reverse=True)
        return [(did, d) for did, d, _ in candidates[:max_candidates]]

    # Legacy Firestore path
    for doc in conn.collection("projects").stream():
        data = doc.to_dict()
        evidence = data.get("evidence", [])
        evidence_count = len(evidence)

        if evidence_count != 1:
            continue

        status = (data.get("status") or "").lower()
        if status in ("cancelled", "canceled", "completed"):
            continue

        # Skip recently verified
        last_check = data.get("last_verification_check", "")
        if last_check:
            try:
                lc = datetime.fromisoformat(str(last_check)[:10])
                if (now - lc).days < 30:
                    continue
            except (ValueError, TypeError):
                pass

        # Parse value for prioritization
        value_m = _parse_value(data.get("value", ""))
        confidence = data.get("confidence", 0.5)
        has_gov = data.get("has_government_source", False)
        has_known = data.get("has_known_source", False)

        priority = value_m
        if not has_gov and not has_known:
            priority *= 2
        if confidence < 0.4:
            priority *= 1.5

        candidates.append((doc.id, data, priority))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return [(did, d) for did, d, _ in candidates[:max_candidates]]


def build_verification_query(doc_id, project):
    """Build a Gemini query to independently confirm a project."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    proponent = project.get("proponent", "")
    value = project.get("value", "")

    location = f"{cma}, {province}" if cma else province
    value_str = f" (estimated {value})" if value and value not in ("", "--", "Not disclosed") else ""
    proponent_str = f" by {proponent}" if proponent and proponent != "Unknown" else ""

    return {
        "query": (
            f"Independently verify: Does the {name} project{proponent_str} "
            f"exist in {location}, Canada{value_str}? "
            f"Find independent confirmation from government records, news articles, "
            f"industry publications, or corporate announcements. "
            f"Report: whether the project is confirmed, its current status, "
            f"estimated value, and your best source URL."
        ),
        "type": "verification",
        "doc_id": doc_id,
        "project_name": name,
    }


def _parse_verification_result(engine_result):
    """Parse a verification query result from gemini_engine."""
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

    return {"confirmed": False, "_grounding_urls": grounding_urls}


def apply_verification_results(conn, results):
    """Write verification results back to SQLite.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns {"confirmed": int, "unconfirmed": int, "errors": int}
    """
    import json as _json
    today = datetime.utcnow().strftime("%Y-%m-%d")
    confirmed = 0
    unconfirmed = 0
    errors = 0
    use_sqlite = hasattr(conn, 'execute')

    for r in results:
        if r.get("error"):
            errors += 1
            continue

        doc_id = r["query"]["doc_id"]
        parsed = r.get("parsed")
        if not parsed:
            errors += 1
            continue

        updates = {"last_verification_check": today}

        if parsed.get("confirmed"):
            confirmed += 1
            grounding_urls = parsed.get("_grounding_urls", [])
            source_url = parsed.get("source_url", "")

            if use_sqlite:
                try:
                    row = conn.execute(
                        "SELECT evidence, confidence, value FROM projects WHERE norm_key = ?",
                        (doc_id,),
                    ).fetchone()
                    if row:
                        evidence = _json.loads(row["evidence"] or "[]")
                        existing_urls = {e.get("url") for e in evidence if e.get("url")}

                        if source_url and source_url.startswith("http") and source_url not in existing_urls:
                            evidence.append({
                                "url": source_url,
                                "name": parsed.get("source_name", ""),
                                "date": today,
                                "source_type": "verification",
                            })
                            existing_urls.add(source_url)

                        for url in grounding_urls:
                            if url and url.startswith("http") and url not in existing_urls:
                                evidence.append({
                                    "url": url, "name": "", "date": today,
                                    "source_type": "verification_grounding",
                                })
                                existing_urls.add(url)

                        updates["evidence"] = _json.dumps(evidence, ensure_ascii=False)
                        updates["evidence_count"] = len(evidence)

                        old_conf = row["confidence"] or 0.3
                        if len(evidence) >= 2:
                            updates["confidence"] = max(old_conf, 0.7)
                        updates["verification_status"] = "confirmed"

                        # Update value if missing
                        val_m = parsed.get("value_millions")
                        if val_m and val_m > 0:
                            cur_val = (row["value"] or "").lower()
                            if cur_val in ("", "--", "not disclosed", "unknown", "n/a", "tbd"):
                                if val_m >= 1000:
                                    updates["value"] = f"C${val_m/1000:.1f}B"
                                else:
                                    updates["value"] = f"C${val_m:.0f}M"
                except Exception as e:
                    logger.warning(f"Verification evidence merge failed: {e}")
            else:
                # Firestore path
                try:
                    doc_ref = conn.collection("projects").document(doc_id)
                    existing = doc_ref.get().to_dict() or {}
                    evidence = existing.get("evidence", [])
                    existing_urls = {e.get("url") for e in evidence if e.get("url")}

                    if source_url and source_url.startswith("http") and source_url not in existing_urls:
                        evidence.append({
                            "url": source_url,
                            "name": parsed.get("source_name", ""),
                            "date": today,
                            "source_type": "verification",
                        })
                        existing_urls.add(source_url)

                    for url in grounding_urls:
                        if url and url.startswith("http") and url not in existing_urls:
                            evidence.append({"url": url, "name": "", "date": today,
                                             "source_type": "verification_grounding"})
                            existing_urls.add(url)

                    updates["evidence"] = evidence
                    updates["evidence_count"] = len(evidence)
                    old_conf = existing.get("confidence", 0.3)
                    if len(evidence) >= 2:
                        updates["confidence"] = max(old_conf, 0.7)
                    updates["verification_status"] = "confirmed"

                    val_m = parsed.get("value_millions")
                    if val_m and val_m > 0:
                        cur_val = (existing.get("value") or "").lower()
                        if cur_val in ("", "--", "not disclosed", "unknown", "n/a", "tbd"):
                            if val_m >= 1000:
                                updates["value"] = f"C${val_m/1000:.1f}B"
                            else:
                                updates["value"] = f"C${val_m:.0f}M"
                except Exception as e:
                    logger.warning(f"Verification evidence merge failed: {e}")

            print(f"    [VERIFIED] {r['query']['project_name'][:50]}")
        else:
            unconfirmed += 1
            updates["verification_status"] = "unconfirmed"
            print(f"    [UNVERIFIED] {r['query']['project_name'][:50]}")

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
                logger.warning(f"[VERIFY] Update failed for {doc_id}: {e}")
        else:
            conn.collection("projects").document(doc_id).update(updates)

    return {"confirmed": confirmed, "unconfirmed": unconfirmed, "errors": errors}


async def run_deep_verification_async(conn, max_queries=MAX_VERIFICATION_PER_RUN):
    """Run verification queries for single-source projects."""
    from gemini_engine import run_batch

    candidates = select_projects_for_verification(conn, max_queries)
    if not candidates:
        print("  [VERIFY] No single-source projects need verification.")
        return {"confirmed": 0, "unconfirmed": 0, "errors": 0}

    queries = [build_verification_query(did, p) for did, p in candidates]
    print(f"  [VERIFY] Checking {len(queries)} single-source projects...")

    raw_results = await run_batch(queries, VERIFY_SYSTEM_PROMPT,
                                  max_concurrent=10, tag="VERIFY")

    # Parse each result
    results = []
    for r in raw_results:
        parsed = _parse_verification_result(r)
        results.append({
            "query": r["query"],
            "parsed": parsed,
            "error": r.get("error"),
        })

    summary = apply_verification_results(conn, results)
    print(f"  [VERIFY] {summary['confirmed']} confirmed, "
          f"{summary['unconfirmed']} unconfirmed, {summary['errors']} errors")
    return summary


def run_verification(conn, max_queries=MAX_VERIFICATION_PER_RUN):
    """Synchronous wrapper."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                run_deep_verification_async(conn, max_queries))
        else:
            return asyncio.run(run_deep_verification_async(conn, max_queries))
    except RuntimeError:
        return asyncio.run(run_deep_verification_async(conn, max_queries))


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
