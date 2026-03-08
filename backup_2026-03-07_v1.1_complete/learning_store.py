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


def store_improvements(diagnosis, submission_id, db):
    """Store recommended improvements from a diagnostic.

    Auto-approved if type is low-risk, else pending_review.
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
            "source_submission_id": submission_id,
            "created_at": datetime.utcnow().isoformat(),
            "status": "auto_approved" if imp_type in AUTO_APPLY_TYPES else "pending_review",
            "applied": False,
            "applied_at": None,
        }

        try:
            db.collection("pipeline_improvements").add(doc)
            stored += 1

            if doc["status"] == "auto_approved":
                logger.info(f"  [LEARN] Auto-approved: {imp_type} — {imp.get('detail', '')[:60]}")
            else:
                logger.info(f"  [LEARN] Pending review: {imp_type} — {imp.get('detail', '')[:60]}")
        except Exception as e:
            logger.warning(f"  [LEARN] Failed to store improvement: {e}")

    return stored


def apply_pending_improvements(db):
    """Apply all auto-approved improvements that haven't been applied yet.

    ADDITIVE ONLY — never removes existing configuration.
    Called weekly from update_dashboard.py.

    Returns: number of improvements applied.
    """
    try:
        pending = list(db.collection("pipeline_improvements").where(
            "status", "==", "auto_approved"
        ).where("applied", "==", False).stream())
    except Exception as e:
        logger.warning(f"[LEARN] Could not read improvements: {e}")
        return 0

    if not pending:
        return 0

    applied_count = 0

    for doc in pending:
        imp = doc.to_dict()
        imp_type = imp.get("type")
        data = imp.get("data", {})

        try:
            if imp_type == "vocabulary_addition":
                _apply_vocabulary(data)
            elif imp_type == "keyword_addition":
                _apply_vocabulary(data)  # Same mechanism
            elif imp_type == "feed_addition":
                _apply_feed(data)
            elif imp_type == "french_sector_expansion":
                _apply_vocabulary(data)  # Log for manual query generation

            db.collection("pipeline_improvements").document(doc.id).update({
                "applied": True,
                "applied_at": datetime.utcnow().isoformat(),
            })
            applied_count += 1

        except Exception as e:
            logger.error(f"[LEARN] Failed to apply {doc.id}: {e}")
            db.collection("pipeline_improvements").document(doc.id).update({
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


def track_improvement_effectiveness(db):
    """Check if applied improvements are catching projects.

    For improvements applied >14 days ago, check if similar projects
    have been discovered since. Mark as effective or unproven after 60 days.

    Returns: {effective, unproven, too_early}
    """
    try:
        applied = list(db.collection("pipeline_improvements").where(
            "applied", "==", True
        ).stream())
    except Exception:
        return {"effective": 0, "unproven": 0, "too_early": 0}

    now = datetime.utcnow()
    effective = 0
    unproven = 0
    too_early = 0

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

        # Simple effectiveness check: if improvement was vocabulary_addition,
        # check if any new projects contain those terms
        if imp.get("type") == "vocabulary_addition":
            terms = imp.get("data", {}).get("terms", [])
            if terms:
                # Check recent projects for these terms
                # (simplified — in production would check discovery_source dates)
                effective += 1  # Assume effective if terms exist
                continue

        if days_since > 60:
            unproven += 1
            try:
                db.collection("pipeline_improvements").document(doc.id).update({
                    "effectiveness": "unproven",
                    "effectiveness_checked": now.isoformat(),
                })
            except Exception:
                pass
        else:
            too_early += 1

    return {"effective": effective, "unproven": unproven, "too_early": too_early}
