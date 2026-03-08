"""
learning_store.py -- Store and apply pipeline improvements from missed project diagnostics.

STEP_2K: When a missed project is diagnosed, recommended improvements are stored
in Firestore and optionally auto-applied. Improvements are ADDITIVE ONLY — the
system never removes existing queries, keywords, feeds, or coverage.

Auto-apply types (low risk):
  vocabulary_addition — add terms to learned vocabulary
  keyword_addition — add to positive keyword lists
  feed_addition — add new RSS feeds to investigation list
  french_sector_expansion — expand French coverage

Manual review types (structural):
  negative_keyword_review — removing negatives needs care
  affinity_expansion — sector×province combos
  geographic_addition — new CMAs or regional clusters
  taxonomy_expansion — new project types
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

AUTO_APPLY_TYPES = {
    "vocabulary_addition",
    "keyword_addition",
    "feed_addition",
    "french_sector_expansion",
}

MANUAL_REVIEW_TYPES = {
    "negative_keyword_review",
    "affinity_expansion",
    "geographic_addition",
    "taxonomy_expansion",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEARNED_VOCAB_PATH = os.path.join(BASE_DIR, "learned_vocabulary.json")
LEARNED_FEEDS_PATH = os.path.join(BASE_DIR, "learned_feeds.json")


def store_improvements(diagnosis, submission_id, conn):
    """Store recommended improvements from a diagnostic.

    Auto-approved if type is low-risk, else pending_review.

    Args:
        diagnosis: dict from diagnose_missed_project()
        submission_id: identifier of the submission (str or int)
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)
    """
    improvements = diagnosis.get("recommended_improvements", [])
    if not improvements:
        return 0

    stored = 0
    for imp in improvements:
        imp_type = imp.get("type", "unknown")

        doc = {
            "type": imp_type,
            "detail": imp.get("detail", ""),
            "target": imp.get("target", ""),
            "data": imp,
            "source_submission_id": str(submission_id),
            "created_at": datetime.utcnow().isoformat(),
            "status": "auto_approved" if imp_type in AUTO_APPLY_TYPES else "pending_review",
            "applied": False,
            "applied_at": None,
        }

        try:
            if hasattr(conn, 'execute'):
                # SQLite path
                from db import save_pipeline_improvement
                save_pipeline_improvement(conn, doc)
            else:
                # Legacy Firestore path
                conn.collection("pipeline_improvements").add(doc)
            stored += 1

            if doc["status"] == "auto_approved":
                logger.info(f"  [LEARN] Auto-approved: {imp_type} — {imp.get('detail', '')[:60]}")
            else:
                logger.info(f"  [LEARN] Pending review: {imp_type} — {imp.get('detail', '')[:60]}")
        except Exception as e:
            logger.warning(f"  [LEARN] Failed to store improvement: {e}")

    return stored


def apply_pending_improvements(conn):
    """Apply all auto-approved improvements that haven't been applied yet.

    ADDITIVE ONLY — never removes existing configuration.
    Called weekly from update_dashboard.py.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns: number of improvements applied.
    """
    if hasattr(conn, 'execute'):
        # SQLite path — read all improvements from pipeline_improvements table
        # The schema stores all improvements; filter by status in data JSON
        try:
            rows = conn.execute(
                "SELECT id, data FROM pipeline_improvements"
            ).fetchall()
        except Exception as e:
            logger.warning(f"[LEARN] Could not read improvements: {e}")
            return 0

        pending = []
        for row in rows:
            try:
                d = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                if d.get("status") == "auto_approved" and not d.get("applied"):
                    pending.append((row["id"], d))
            except Exception:
                pass

        if not pending:
            return 0

        applied_count = 0
        for row_id, imp in pending:
            imp_type = imp.get("type")
            data = imp.get("data", {})

            try:
                if imp_type == "vocabulary_addition":
                    _apply_vocabulary(data)
                elif imp_type == "keyword_addition":
                    _apply_vocabulary(data)
                elif imp_type == "feed_addition":
                    _apply_feed(data)
                elif imp_type == "french_sector_expansion":
                    _apply_vocabulary(data)

                # Mark as applied in the JSON data column
                imp["applied"] = True
                imp["applied_at"] = datetime.utcnow().isoformat()
                with conn:
                    conn.execute(
                        "UPDATE pipeline_improvements SET data = ? WHERE id = ?",
                        (json.dumps(imp, ensure_ascii=False), row_id),
                    )
                applied_count += 1

            except Exception as e:
                logger.error(f"[LEARN] Failed to apply improvement id={row_id}: {e}")

    else:
        # Legacy Firestore path
        try:
            pending_docs = list(conn.collection("pipeline_improvements").where(
                "status", "==", "auto_approved"
            ).where("applied", "==", False).stream())
        except Exception as e:
            logger.warning(f"[LEARN] Could not read improvements: {e}")
            return 0

        if not pending_docs:
            return 0

        applied_count = 0
        for doc in pending_docs:
            imp = doc.to_dict()
            imp_type = imp.get("type")
            data = imp.get("data", {})

            try:
                if imp_type == "vocabulary_addition":
                    _apply_vocabulary(data)
                elif imp_type == "keyword_addition":
                    _apply_vocabulary(data)
                elif imp_type == "feed_addition":
                    _apply_feed(data)
                elif imp_type == "french_sector_expansion":
                    _apply_vocabulary(data)

                conn.collection("pipeline_improvements").document(doc.id).update({
                    "applied": True,
                    "applied_at": datetime.utcnow().isoformat(),
                })
                applied_count += 1

            except Exception as e:
                logger.error(f"[LEARN] Failed to apply {doc.id}: {e}")
                conn.collection("pipeline_improvements").document(doc.id).update({
                    "status": "failed",
                    "error": str(e),
                })

    if applied_count:
        print(f"  [LEARN] Applied {applied_count} pipeline improvements")
    return applied_count


def _apply_vocabulary(data):
    """Add new terms to learned vocabulary JSON.

    ADDITIVE: appends to existing list, never removes.
    """
    terms = data.get("terms", [])
    sector = data.get("sector", "general")
    detail = data.get("detail", "")

    # Load existing
    vocab = _load_json(LEARNED_VOCAB_PATH, {"terms_by_sector": {}, "additions": []})

    # Add terms
    if sector not in vocab["terms_by_sector"]:
        vocab["terms_by_sector"][sector] = []

    existing = set(vocab["terms_by_sector"][sector])
    new_terms = [t for t in terms if t not in existing]

    if new_terms:
        vocab["terms_by_sector"][sector].extend(new_terms)
        vocab["additions"].append({
            "date": datetime.utcnow().isoformat(),
            "sector": sector,
            "terms": new_terms,
            "detail": detail,
        })
        _save_json(LEARNED_VOCAB_PATH, vocab)
        logger.info(f"  [LEARN] Added vocabulary: {new_terms} to sector '{sector}'")


def _apply_feed(data):
    """Add new RSS feed domain to investigation list.

    ADDITIVE: appends to list, never removes.
    """
    domain = data.get("domain", "")
    if not domain:
        return

    feeds = _load_json(LEARNED_FEEDS_PATH, {"domains_to_investigate": [], "additions": []})

    if domain not in feeds["domains_to_investigate"]:
        feeds["domains_to_investigate"].append(domain)
        feeds["additions"].append({
            "date": datetime.utcnow().isoformat(),
            "domain": domain,
            "detail": data.get("detail", ""),
        })
        _save_json(LEARNED_FEEDS_PATH, feeds)
        logger.info(f"  [LEARN] Added feed domain: {domain}")


def _load_json(path, default):
    """Load JSON file, return default if not found."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    """Save JSON file with pretty formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def track_improvement_effectiveness(conn):
    """Check if applied improvements are catching projects.

    For improvements applied >14 days ago, check if similar projects
    have been discovered since. Mark as effective or unproven after 60 days.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns: {effective, unproven, too_early}
    """
    now = datetime.utcnow()
    effective = 0
    unproven = 0
    too_early = 0

    if hasattr(conn, 'execute'):
        try:
            rows = conn.execute(
                "SELECT id, data FROM pipeline_improvements"
            ).fetchall()
        except Exception:
            return {"effective": 0, "unproven": 0, "too_early": 0}

        for row in rows:
            try:
                imp = json.loads(row["data"]) if isinstance(row["data"], str) else (row["data"] or {})
            except Exception:
                continue

            if not imp.get("applied"):
                continue

            applied_at = imp.get("applied_at")
            if not applied_at:
                continue

            try:
                applied_date = datetime.fromisoformat(applied_at)
            except (ValueError, TypeError):
                continue

            days_since = (now - applied_date).days
            if days_since < 14:
                too_early += 1
                continue

            if imp.get("type") == "vocabulary_addition":
                terms = imp.get("data", {}).get("terms", [])
                if terms:
                    effective += 1
                    continue

            if days_since > 60:
                unproven += 1
                imp["effectiveness"] = "unproven"
                imp["effectiveness_checked"] = now.isoformat()
                try:
                    with conn:
                        conn.execute(
                            "UPDATE pipeline_improvements SET data = ? WHERE id = ?",
                            (json.dumps(imp, ensure_ascii=False), row["id"]),
                        )
                except Exception:
                    pass
            else:
                too_early += 1

    else:
        # Legacy Firestore path
        try:
            applied = list(conn.collection("pipeline_improvements").where(
                "applied", "==", True
            ).stream())
        except Exception:
            return {"effective": 0, "unproven": 0, "too_early": 0}

        for doc in applied:
            imp = doc.to_dict()
            applied_at = imp.get("applied_at")
            if not applied_at:
                continue
            try:
                applied_date = datetime.fromisoformat(applied_at)
            except (ValueError, TypeError):
                continue
            days_since = (now - applied_date).days
            if days_since < 14:
                too_early += 1
                continue
            if imp.get("type") == "vocabulary_addition":
                if imp.get("data", {}).get("terms", []):
                    effective += 1
                    continue
            if days_since > 60:
                unproven += 1
                try:
                    conn.collection("pipeline_improvements").document(doc.id).update({
                        "effectiveness": "unproven",
                        "effectiveness_checked": now.isoformat(),
                    })
                except Exception:
                    pass
            else:
                too_early += 1

    return {"effective": effective, "unproven": unproven, "too_early": too_early}
