"""
pipeline_store.py — Consolidated pipeline state and caching.

Two components:
  - PipelineCache: SQLite-backed key-value cache with TTL (was pipeline_cache.py)
  - PipelineState: Follow-up query storage and JSON parsing (was pipeline_state.py)

Usage:
    from pipeline_store import cache          # TTL cache singleton
    from pipeline_store import PipelineCache  # class, if custom path needed
    from pipeline_store import parse_json_response, store_follow_up_queries, get_follow_up_queries
"""

import json
import os
import re
import sqlite3
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineCache — SQLite-backed TTL cache (was pipeline_cache.py)
# ═══════════════════════════════════════════════════════════════════════════════

_CACHE_DIR = os.path.join(os.path.dirname(__file__), '.cache')
_CACHE_DB = os.path.join(_CACHE_DIR, 'pipeline.db')


class PipelineCache:
    """SQLite-backed key-value cache with TTL expiry."""

    def __init__(self, db_path=None):
        self._db_path = db_path or _CACHE_DB
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expires_at REAL NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
        except Exception as e:
            logger.warning(f"Cache init failed: {e}")

    def get(self, key):
        """Get a cached value if not expired.

        Returns:
            Deserialized value, or None if missing/expired.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?",
                    (key,)
                ).fetchone()
                if row and row[1] > time.time():
                    return json.loads(row[0])
                # Expired — clean up
                if row:
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None

    def set(self, key, value, ttl_hours=24):
        """Store a value with TTL.

        Args:
            key: Cache key string
            value: Any JSON-serializable value
            ttl_hours: Hours until expiry
        """
        try:
            expires_at = time.time() + (ttl_hours * 3600)
            serialized = json.dumps(value, default=str)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (key, serialized, expires_at, time.time())
                )
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")

    def clear_expired(self):
        """Remove all expired entries."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                deleted = conn.execute(
                    "DELETE FROM cache WHERE expires_at < ?",
                    (time.time(),)
                ).rowcount
                if deleted:
                    print(f"  [CACHE] Cleared {deleted} expired entries")
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

    def stats(self):
        """Return cache statistics."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                valid = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
                    (time.time(),)
                ).fetchone()[0]
                return {"total": total, "valid": valid, "expired": total - valid}
        except Exception:
            return {"total": 0, "valid": 0, "expired": 0}


# Module-level singleton
cache = PipelineCache()


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineState — Follow-up queries and JSON parsing (was pipeline_state.py)
# ═══════════════════════════════════════════════════════════════════════════════

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
        from db import get_db
        from db import save_follow_up_queries as _save_follow_up_queries
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
        from db import get_db
        from db import get_follow_up_queries as _get_follow_up_queries
        active_conn = conn if conn is not None else get_db()
        return _get_follow_up_queries(active_conn)
    except Exception as e:
        logger.warning(f"Failed to read follow-up queries: {e}")
    return []
