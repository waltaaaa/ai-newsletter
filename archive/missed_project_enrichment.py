"""
missed_project_enrichment.py -- Process user-submitted missed projects.

STEP_2K: Reads pending submissions from missed_projects table (SQLite) or
Firestore collection (legacy), merges them into the main projects via
upsert_flat_projects, then runs targeted Gemini queries to fill missing
fields (cost, proponent, description). Finally triggers diagnostic analysis.

Budget: 20 queries/run from the ~97-query daily buffer.
"""

import json
import re
import logging
from datetime import datetime

# db.py provides the SQLite interface used for submission updates
from db import save_missed_project  # noqa: F401 — imported for duck-typing callers

logger = logging.getLogger(__name__)

MAX_ENRICHMENT_QUERIES = 20

ENRICHMENT_SYSTEM_PROMPT = """You are a Canadian infrastructure project research analyst.
Given a project name and location, find factual details from official sources.

Return ONLY a valid JSON object (no markdown fences):
{
  "value_millions": 650,
  "proponent": "Company or government agency name",
  "description": "One-paragraph factual description of the project",
  "status": "Under Construction",
  "source_url": "https://...",
  "source_name": "Publication name",
  "sector": "NAICS 2-digit code or sector name",
  "cma": "Census Metropolitan Area if applicable"
}

Rules:
- value_millions: estimated cost in millions CAD, null if not found
- proponent: the lead developer/owner/agency, null if not found
- description: factual 2-3 sentence description, null if not found
- status: current status (Proposed, Approved, Under Construction, Completed, Delayed), null if unknown
- Only report facts you can verify from search results
- If you cannot find information about this project, return {"found": false}
"""


def process_pending_submissions(conn, max_queries=MAX_ENRICHMENT_QUERIES):
    """Process pending missed_projects submissions.

    1. Read pending submissions from missed_projects table/collection
    2. Merge each into main projects via upsert_flat_projects
    3. Run Gemini enrichment for missing fields
    4. Run diagnostics to identify why project was missed
    5. Update submission status

    Args:
        conn: sqlite3.Connection from db.py (preferred) or Firestore client
              (backward compatible — detected by duck-typing)

    Returns: {processed, new, merged, enriched, errors}
    """
    import json as _json
    from project_sync import upsert_flat_projects
    use_sqlite = hasattr(conn, 'execute')

    # Fetch pending submissions
    pending = []
    if use_sqlite:
        try:
            rows = conn.execute(
                "SELECT id, data FROM missed_projects WHERE json_extract(data, '$.processing_status') = 'pending'"
            ).fetchall()
            for row in rows:
                data = _json.loads(row["data"] or "{}")
                data["_doc_id"] = str(row["id"])
                pending.append(data)
        except Exception as e:
            logger.warning(f"[MISSED] Could not read missed_projects: {e}")
            return {"processed": 0, "errors": 1}
    else:
        try:
            for doc in conn.collection("missed_projects").where(
                "processing_status", "==", "pending"
            ).stream():
                data = doc.to_dict()
                data["_doc_id"] = doc.id
                pending.append(data)
        except Exception as e:
            logger.warning(f"[MISSED] Could not read missed_projects: {e}")
            return {"processed": 0, "errors": 1}

    if not pending:
        print("  [MISSED] No pending submissions.")
        return {"processed": 0, "new": 0, "merged": 0, "enriched": 0, "errors": 0}

    print(f"  [MISSED] Processing {len(pending)} submissions...")

    summary = {"processed": 0, "new": 0, "merged": 0, "enriched": 0, "errors": 0}
    enrichment_queries = []

    def _update_submission(submission_id, updates_dict):
        """Helper to update a missed_project submission row."""
        if use_sqlite:
            try:
                row = conn.execute(
                    "SELECT data FROM missed_projects WHERE id = ?",
                    (submission_id,),
                ).fetchone()
                data = _json.loads(row["data"] or "{}") if row else {}
                data.update(updates_dict)
                with conn:
                    conn.execute(
                        "UPDATE missed_projects SET data = ? WHERE id = ?",
                        (_json.dumps(data, ensure_ascii=False), submission_id),
                    )
            except Exception as e:
                logger.warning(f"[MISSED] Submission update failed: {e}")
        else:
            conn.collection("missed_projects").document(submission_id).update(updates_dict)

    for sub in pending:
        submission_id = sub["_doc_id"]
        name = sub.get("name", "").strip()
        province = sub.get("province", "").strip()

        if not name or not province:
            _update_submission(submission_id, {
                "processing_status": "error",
                "error": "Missing name or province",
            })
            summary["errors"] += 1
            continue

        # Build flat project for upsert
        flat = {
            "name": name,
            "province": province,
            "cma": sub.get("city", ""),
            "sector": sub.get("sector", ""),
            "value": f"C${sub['value_millions']:.0f}M" if sub.get("value_millions") else "Not disclosed",
            "status": sub.get("status", "Proposed"),
            "proponent": sub.get("proponent", ""),
            "project_type": sub.get("project_type", "new_build"),
            "description": sub.get("description", ""),
            "discovery_source": "user_submission",
            "discovery_sources": ["user_submission"],
            "confidence": 0.3,
            "sources": [],
            "evidence": [],
        }

        if sub.get("source_url"):
            flat["sources"] = [{"url": sub["source_url"], "title": "User-submitted source"}]
            flat["evidence"] = [{
                "url": sub["source_url"],
                "name": "User-submitted source",
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "source_type": "user_submission",
            }]
            flat["evidence_count"] = 1
            flat["confidence"] = 0.4

        # Merge into main projects
        try:
            upsert_flat_projects(conn, [flat])
            summary["processed"] += 1
        except Exception as e:
            logger.error(f"[MISSED] Upsert failed for '{name}': {e}")
            summary["errors"] += 1
            _update_submission(submission_id, {
                "processing_status": "error",
                "error": str(e),
            })
            continue

        # Update submission status
        _update_submission(submission_id, {"processing_status": "diagnosing"})

        # Check if enrichment needed
        needs_enrichment = []
        if not sub.get("value_millions"):
            needs_enrichment.append("cost")
        if not sub.get("proponent"):
            needs_enrichment.append("proponent")
        if not sub.get("description") or len(sub.get("description", "")) < 30:
            needs_enrichment.append("description")

        if needs_enrichment and len(enrichment_queries) < max_queries:
            enrichment_queries.append({
                "query": _build_enrichment_query(name, province, sub),
                "type": "missed_enrichment",
                "submission_id": submission_id,
                "project_name": name,
                "province": province,
                "needs": needs_enrichment,
            })

    # Run enrichment queries via Gemini
    if enrichment_queries:
        _run_enrichment(conn, enrichment_queries, summary)

    # Run diagnostics for all processed submissions
    try:
        from missed_project_diagnostics import diagnose_missed_project
        from learning_store import store_improvements

        for sub in pending:
            if sub.get("_doc_id") and sub.get("name"):
                try:
                    diagnosis = diagnose_missed_project(sub)
                    _update_submission(sub["_doc_id"], {
                        "diagnosis": diagnosis,
                        "processing_status": "complete",
                        "learning_applied": bool(diagnosis.get("recommended_improvements")),
                    })
                    if diagnosis.get("recommended_improvements"):
                        store_improvements(diagnosis, sub["_doc_id"], conn)
                except Exception as e:
                    logger.warning(f"[MISSED] Diagnosis failed for '{sub['name']}': {e}")
                    _update_submission(sub["_doc_id"], {"processing_status": "complete"})
    except ImportError:
        logger.warning("[MISSED] Diagnostics module not available, skipping")

    print(f"  [MISSED] Done: {summary['processed']} processed, "
          f"{summary['enriched']} enriched, {summary['errors']} errors")
    return summary


def _build_enrichment_query(name, province, submission):
    """Build a targeted Gemini query for enriching a missed project."""
    city = submission.get("city", "")
    proponent = submission.get("proponent", "")
    location = f"{city}, {province}" if city else province

    parts = [f"Find detailed information about the {name} project"]
    if proponent:
        parts.append(f"by {proponent}")
    parts.append(f"in {location}, Canada.")
    parts.append("What is the estimated cost, who is the developer/proponent, "
                 "what is the current construction status, and what does the project involve?")

    return " ".join(parts)


def _run_enrichment(conn, queries, summary):
    """Run enrichment queries through Gemini and apply results.

    Args:
        conn: sqlite3.Connection from db.py (preferred) or Firestore client
    """
    import json as _json
    from gemini_engine import run_batch_sync

    print(f"  [MISSED] Running {len(queries)} enrichment queries...")
    raw_results = run_batch_sync(queries, ENRICHMENT_SYSTEM_PROMPT,
                                  max_concurrent=10, tag="ENRICH")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    use_sqlite = hasattr(conn, 'execute')

    for result in raw_results:
        if result.get("error"):
            continue

        q = result["query"]
        parsed = _parse_enrichment_result(result)
        if not parsed or parsed.get("found") is False:
            continue

        # Find the project by name + province
        name = q["project_name"]
        province = q["province"]

        try:
            updates = {"lastSeen": today, "lastUpdated": today}

            if parsed.get("value_millions") and "cost" in q.get("needs", []):
                val = parsed["value_millions"]
                if val >= 1000:
                    updates["value"] = f"C${val/1000:.1f}B"
                else:
                    updates["value"] = f"C${val:.0f}M"

            if parsed.get("proponent") and "proponent" in q.get("needs", []):
                updates["proponent"] = parsed["proponent"]

            if parsed.get("description") and "description" in q.get("needs", []):
                updates["description"] = parsed["description"]

            if parsed.get("status"):
                updates["status"] = parsed["status"]

            if parsed.get("cma"):
                updates["cma"] = parsed["cma"]

            if parsed.get("sector"):
                updates["naics_code"] = parsed["sector"]

            if use_sqlite:
                # Find norm_key by name + province
                row = conn.execute(
                    "SELECT norm_key, evidence FROM projects WHERE name = ? AND province = ? LIMIT 1",
                    (name, province),
                ).fetchone()
                if not row:
                    continue
                norm_key = row["norm_key"]

                # Add grounding URLs as evidence
                grounding = result.get("grounding_urls", [])
                if grounding:
                    evidence = _json.loads(row["evidence"] or "[]")
                    existing_urls = {e.get("url") for e in evidence if e.get("url")}
                    for url_info in grounding[:3]:
                        url = url_info if isinstance(url_info, str) else url_info.get("url", "")
                        if url and url not in existing_urls:
                            evidence.append({
                                "url": url,
                                "name": "Enrichment source",
                                "date": today,
                                "source_type": "gemini_enrichment",
                            })
                            existing_urls.add(url)
                    updates["evidence"] = _json.dumps(evidence, ensure_ascii=False)
                    updates["evidence_count"] = len(evidence)

                set_clauses = [f"{k} = ?" for k in updates]
                params = list(updates.values()) + [norm_key]
                with conn:
                    conn.execute(
                        f"UPDATE projects SET {', '.join(set_clauses)} WHERE norm_key = ?",
                        params,
                    )
            else:
                # Firestore path
                matches = conn.collection("projects").where(
                    "province", "==", province
                ).where("name", "==", name).limit(1).stream()

                doc_ref = None
                for m in matches:
                    doc_ref = conn.collection("projects").document(m.id)
                    break

                if not doc_ref:
                    continue

                # Add grounding URLs as evidence
                grounding = result.get("grounding_urls", [])
                if grounding:
                    existing = doc_ref.get().to_dict() or {}
                    evidence = existing.get("evidence", [])
                    for url_info in grounding[:3]:
                        url = url_info if isinstance(url_info, str) else url_info.get("url", "")
                        if url and not any(e.get("url") == url for e in evidence):
                            evidence.append({
                                "url": url,
                                "name": "Enrichment source",
                                "date": today,
                                "source_type": "gemini_enrichment",
                            })
                    updates["evidence"] = evidence
                    updates["evidence_count"] = len(evidence)

                doc_ref.update(updates)

            summary["enriched"] += 1
            print(f"    [ENRICH] {name[:40]} -- enriched "
                  f"({', '.join(k for k in updates if k not in ('lastSeen','lastUpdated'))})")

        except Exception as e:
            logger.warning(f"[ENRICH] Failed to apply for '{name}': {e}")


def _parse_enrichment_result(engine_result):
    """Parse enrichment response from Gemini."""
    text = engine_result.get("text", "")

    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)

    # Find JSON object
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
                        return json.loads(text[obj_start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break
    return None
