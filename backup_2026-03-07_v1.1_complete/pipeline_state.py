"""
pipeline_state.py — Shared Firestore pipeline state helpers.

Shared helpers for follow-up queries, JSON response parsing,
and pipeline state management in Firestore.
"""

import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_json_response(response):
    """Parse JSON from an AI model response, stripping markdown fences."""
    if not response:
        return None

    cleaned = re.sub(r'```json\s*', '', response)
    cleaned = re.sub(r'```\s*', '', cleaned).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find JSON object
    obj_start = cleaned.find('{')
    if obj_start >= 0:
        depth = 0
        for i in range(obj_start, len(cleaned)):
            if cleaned[i] == '{':
                depth += 1
            elif cleaned[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[obj_start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def store_follow_up_queries(db, queries):
    """Store follow-up queries for next week's pipeline run."""
    if not queries:
        return
    try:
        db.collection("pipeline_state").document("follow_up_queries").set({
            "queries": queries,
            "generated": datetime.utcnow().isoformat(),
            "status": "pending",
            "count": len(queries),
        })
        logger.info(f"Stored {len(queries)} follow-up queries for next week")
    except Exception as e:
        logger.warning(f"Failed to store follow-up queries: {e}")


def get_follow_up_queries(db):
    """Retrieve stored follow-up queries at the start of each week's run."""
    try:
        doc = db.collection("pipeline_state").document("follow_up_queries").get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("status") == "pending":
                db.collection("pipeline_state").document("follow_up_queries").update({
                    "status": "consumed",
                    "consumed_at": datetime.utcnow().isoformat(),
                })
                return data.get("queries", [])
    except Exception as e:
        logger.warning(f"Failed to read follow-up queries: {e}")
    return []
