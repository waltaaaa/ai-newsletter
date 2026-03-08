"""
pipeline_state.py — Shared pipeline state helpers using SQLite via db.py.

Shared helpers for follow-up queries, JSON response parsing,
and pipeline state management in SQLite.
"""

import json
import re
import logging
from datetime import datetime

from db import get_db
from db import save_follow_up_queries as _save_follow_up_queries
from db import get_follow_up_queries as _get_follow_up_queries

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


def store_follow_up_queries(db, queries, conn=None):
    """Store follow-up queries for next week's pipeline run.

    The ``db`` parameter is accepted for backward compatibility but ignored.
    Data is written to SQLite via db.py.

    Args:
        db: Ignored (kept for backward compatibility with Firestore callers).
        queries: List of query strings to store.
        conn: Optional sqlite3.Connection. If None, a new connection is
              obtained via get_db() connecting to the default database file.
    """
    if not queries:
        return
    try:
        active_conn = conn if conn is not None else get_db()
        _save_follow_up_queries(active_conn, queries)
        logger.info(f"Stored {len(queries)} follow-up queries for next week")
    except Exception as e:
        logger.warning(f"Failed to store follow-up queries: {e}")


def get_follow_up_queries(db, conn=None):
    """Retrieve stored follow-up queries at the start of each week's run.

    The ``db`` parameter is accepted for backward compatibility but ignored.
    Data is read from SQLite via db.py. Marks queries as consumed so they
    are not retrieved again.

    Args:
        db: Ignored (kept for backward compatibility with Firestore callers).
        conn: Optional sqlite3.Connection. If None, a new connection is
              obtained via get_db() connecting to the default database file.

    Returns:
        List of query strings, or [] if none pending.
    """
    try:
        active_conn = conn if conn is not None else get_db()
        return _get_follow_up_queries(active_conn)
    except Exception as e:
        logger.warning(f"Failed to read follow-up queries: {e}")
    return []
