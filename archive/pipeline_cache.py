"""
pipeline_cache.py — SQLite-backed cache with TTL for pipeline API responses.

Reduces pipeline runtime by caching expensive API calls (Yahoo Finance,
StatCan WDS, FRED) that don't change frequently.

Usage:
    from pipeline_cache import cache

    # Check cache first, fetch if miss
    data = cache.get("yfinance:commodities")
    if data is None:
        data = expensive_api_call()
        cache.set("yfinance:commodities", data, ttl_hours=12)
"""

import json
import os
import sqlite3
import time
import logging

logger = logging.getLogger(__name__)

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
