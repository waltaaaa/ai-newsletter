"""
confidence_decay.py -- Source-weighted confidence scoring + time-based decay.

Two stages:
  1. compute_confidence() — evidence-weighted base score using the evidence table.
     Reads source_weight, recency, extraction confidence, agreement bonus, ID bonus.
  2. calculate_decay() — applies staleness decay on top of the base score.
     Only modifies display_confidence; base confidence is recalculated on re-discovery.

Decay schedule:
  0-30 days since lastSeen: No decay
  31-60 days:  -0.05
  61-90 days:  -0.10
  91-120 days: -0.15
  121-180 days: -0.20
  180+ days:   -0.25
"""

import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DECAY_SCHEDULE = [
    (30,  0.00),
    (60,  0.05),
    (90,  0.10),
    (120, 0.15),
    (180, 0.20),
    (9999, 0.25),
]


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE-WEIGHTED CONFIDENCE (Phase 5)
# ══════════════════════════════════════════════════════════════════════════════

def _recency_factor(date_str):
    """Decay factor based on age of evidence."""
    if not date_str:
        return 0.5
    try:
        dt = datetime.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        return 0.5
    days_old = max((datetime.utcnow() - dt).days, 0)
    if days_old <= 30:
        return 1.0
    elif days_old <= 60:
        return 0.90
    elif days_old <= 90:
        return 0.75
    elif days_old <= 120:
        return 0.60
    elif days_old <= 180:
        return 0.45
    else:
        return 0.30


def compute_confidence(project_id, conn):
    """Source-weighted confidence using the evidence table.

    confidence = max(source_weight * recency * extraction_confidence)
    across all evidence rows, with bonuses for:
    - multiple independent source types (agreement_bonus)
    - official identifiers present (id_bonus)

    Falls back to 0.3 (legacy default) if no evidence rows exist.
    """
    from db import get_evidence_for_project
    evidence_rows = get_evidence_for_project(conn, project_id)

    # G12 (quality-pass-1.4): republications contribute ZERO weight — only
    # rows with distinct content count toward the score and agreement bonus.
    # The republished rows (and their URLs) stay in the evidence table.
    evidence_rows = [r for r in evidence_rows if not r.get('republication_of')]

    if not evidence_rows:
        return 0.3  # legacy default — no evidence yet

    scores = []
    for row in evidence_rows:
        recency = _recency_factor(row.get('published_date') or row.get('extraction_date'))
        weight = row.get('source_weight') or 0.5
        ext_conf = row.get('confidence') or 0.5
        scores.append(weight * recency * ext_conf)

    base_score = max(scores)

    # Agreement bonus: multiple independent source types
    unique_types = set(r.get('source_type', 'unknown') for r in evidence_rows)
    agreement_bonus = min(len(unique_types) * 0.03, 0.15)

    # Identifier bonus: official IDs recorded in evidence
    has_official_id = any(
        r.get('field_claimed') in ('official_id', 'iaac', 'cer', 'provincial_ea',
                                    'municipal_app', 'sedar', 'permit', 'filing')
        for r in evidence_rows
    )
    id_bonus = 0.10 if has_official_id else 0.0

    return min(round(base_score + agreement_bonus + id_bonus, 2), 1.0)


def calculate_decay(last_seen, base_confidence):
    """Calculate decayed confidence score.

    Args:
        last_seen: ISO date string or datetime of last evidence/mention
        base_confidence: confidence score before decay (0.0-1.0)

    Returns:
        dict with display_confidence, days_stale, is_stale, needs_review
    """
    now = datetime.utcnow()
    days_stale = 9999

    if last_seen:
        if isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen[:10])
            except (ValueError, TypeError):
                last_seen = None
        if last_seen:
            days_stale = max((now - last_seen).days, 0)

    decay = 0.0
    for threshold, amount in DECAY_SCHEDULE:
        if days_stale <= threshold:
            decay = amount
            break

    display = max(round(base_confidence - decay, 2), 0.05)

    return {
        "display_confidence": display,
        "days_stale": days_stale,
        "is_stale": days_stale > 120,
        "needs_review": days_stale > 180,
        "decay_applied": round(decay, 2),
    }


def apply_confidence_decay(conn):
    """Apply confidence decay to all projects in SQLite.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns summary dict.
    """
    print("\n[DECAY] Applying confidence decay...")
    total = 0
    decayed = 0
    stale = 0
    review = 0

    if hasattr(conn, 'execute'):
        # SQLite path
        from db import get_all_projects
        import json

        projects = get_all_projects(conn)
        recomputed = 0
        for data in projects:
            norm_key = data.get("norm_key", "")
            if not norm_key:
                continue

            last_seen = data.get("lastSeen") or data.get("lastUpdated") or ""

            # Phase 5: recompute base confidence from evidence table
            project_rowid = data.get("rowid")
            if project_rowid:
                new_conf = compute_confidence(project_rowid, conn)
                if new_conf != data.get("confidence", 0.3):
                    try:
                        with conn:
                            conn.execute(
                                "UPDATE projects SET confidence = ? WHERE rowid = ?",
                                (new_conf, project_rowid),
                            )
                        recomputed += 1
                    except Exception as e:
                        logger.debug(f"[DECAY] Confidence recompute failed for {norm_key}: {e}")
                base_conf = new_conf
            else:
                base_conf = data.get("confidence", 0.3)

            result = calculate_decay(last_seen, base_conf)

            if result["is_stale"]:
                stale += 1
            if result["needs_review"]:
                review += 1
            if result["decay_applied"] > 0:
                decayed += 1

            # Update only changed fields
            old_stale = bool(data.get("is_stale", False))
            old_review = bool(data.get("needs_review", False))

            set_clauses = [
                "display_confidence = ?",
                "days_since_update = ?",
            ]
            params = [result["display_confidence"], result["days_stale"]]

            if result["is_stale"] != old_stale:
                set_clauses.append("is_stale = ?")
                params.append(1 if result["is_stale"] else 0)
            if result["needs_review"] != old_review:
                set_clauses.append("needs_review = ?")
                params.append(1 if result["needs_review"] else 0)

            params.append(norm_key)
            try:
                with conn:
                    conn.execute(
                        f"UPDATE projects SET {', '.join(set_clauses)} WHERE norm_key = ?",
                        params,
                    )
            except Exception as e:
                logger.warning(f"[DECAY] Update failed for {norm_key}: {e}")

            # A6 (quality-pass-1.4): log a confidence_decay event so decay is
            # auditable instead of silent. One event per project per decay run,
            # and only when the displayed value actually changed — repeated
            # daily runs within the same decay bucket write nothing.
            old_display = data.get("display_confidence")
            if (result["decay_applied"] > 0 and project_rowid
                    and result["display_confidence"] != old_display):
                try:
                    from db import insert_project_event
                    insert_project_event(
                        conn, project_rowid, 'confidence_decay',
                        summary=(
                            f"Confidence decay: display "
                            f"{old_display if old_display is not None else base_conf} "
                            f"-> {result['display_confidence']} "
                            f"(base {base_conf}, {result['days_stale']} days since "
                            f"last seen, bucket -{result['decay_applied']})"
                        ),
                    )
                except Exception as e:
                    logger.debug(f"[DECAY] Event log failed for {norm_key}: {e}")

            total += 1

    else:
        # Legacy Firestore path (kept for backward compatibility)
        import json as _json
        batch = conn.batch()
        batch_count = 0

        for doc in conn.collection("projects").stream():
            data = doc.to_dict()
            last_seen = data.get("lastSeen") or data.get("lastUpdated") or ""
            base_conf = data.get("confidence", 0.3)

            result = calculate_decay(last_seen, base_conf)

            updates = {
                "display_confidence": result["display_confidence"],
                "days_since_update": result["days_stale"],
            }

            old_stale = data.get("is_stale", False)
            old_review = data.get("needs_review", False)
            if result["is_stale"] != old_stale:
                updates["is_stale"] = result["is_stale"]
            if result["needs_review"] != old_review:
                updates["needs_review"] = result["needs_review"]

            if result["is_stale"]:
                stale += 1
            if result["needs_review"]:
                review += 1
            if result["decay_applied"] > 0:
                decayed += 1

            batch.update(conn.collection("projects").document(doc.id), updates)
            batch_count += 1
            total += 1

            if batch_count >= 500:
                batch.commit()
                batch = conn.batch()
                batch_count = 0

        if batch_count > 0:
            batch.commit()

    recomputed_count = recomputed if hasattr(conn, 'execute') else 0
    print(f"  [DECAY] {total} projects processed: "
          f"{recomputed_count} recomputed, {decayed} decayed, {stale} stale, {review} need review")

    return {"total": total, "recomputed": recomputed_count, "decayed": decayed,
            "stale": stale, "needs_review": review}
