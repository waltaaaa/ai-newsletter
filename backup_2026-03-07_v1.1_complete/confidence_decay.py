"""
confidence_decay.py -- Time-based confidence decay for project records.

Run weekly after discovery. Reduces display_confidence for projects
that haven't been re-discovered or mentioned in recent pipeline runs.
The base 'confidence' field is never modified -- only display_confidence
is adjusted, so decay is automatically reversed when a project is
re-discovered (confidence is recalculated from scratch).

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


def apply_confidence_decay(db):
    """Apply confidence decay to all projects in Firestore.

    Uses batch writes (500 per batch) for efficiency.
    Returns summary dict.
    """
    print("\n[DECAY] Applying confidence decay...")
    batch = db.batch()
    batch_count = 0
    total = 0
    decayed = 0
    stale = 0
    review = 0

    for doc in db.collection("projects").stream():
        data = doc.to_dict()
        last_seen = data.get("lastSeen") or data.get("lastUpdated") or ""
        base_conf = data.get("confidence", 0.3)

        result = calculate_decay(last_seen, base_conf)

        updates = {
            "display_confidence": result["display_confidence"],
            "days_since_update": result["days_stale"],
        }

        # Only write is_stale/needs_review if they changed
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

        batch.update(db.collection("projects").document(doc.id), updates)
        batch_count += 1
        total += 1

        if batch_count >= 500:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    print(f"  [DECAY] {total} projects processed: "
          f"{decayed} decayed, {stale} stale, {review} need review")

    return {"total": total, "decayed": decayed, "stale": stale, "needs_review": review}
