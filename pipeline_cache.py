"""
pipeline_cache.py — Persistent SQLite-backed caching layer.

Eliminates redundant NIM API calls across weekly sweeps:
  - Embeddings: project names rarely change (90-day TTL)
  - Page text: news articles don't update (14-day TTL)
  - Gov pages: update quarterly (90-day TTL)
  - OCR results: PDFs don't change (90-day TTL)
  - Search URLs: track which URLs we've already extracted (7-day TTL)

Expected impact: ~60-65% reduction in NIM API calls after first sweep.

Usage:
    from pipeline_cache import get_cache
    cache = get_cache(conn)
    cache.evict_expired()  # run at sweep start

    cached = cache.get("https://...", "page_text")
    if cached is None:
        text = fetch_page(url)
        cache.set("https://...", text, "page_text")
"""

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# TTL defaults (days) by cache type
DEFAULT_TTL = {
    "embedding": 90,
    "page_text": 14,
    "gov_page": 90,
    "search_url": 7,
    "ocr": 90,
    "query_result": 0,  # never cached
}


# ── Phase-level cache helpers (E-2) ───────────────────────────────────────────
#
# update_dashboard.py used to embed date.today() in the phase cache key, so a
# next-day retry re-ran every phase from scratch. These helpers give it a
# stable per-phase key plus a freshness check against a `_completed_at` UTC
# ISO timestamp stored inside the cached payload. Pure functions — importable
# by tests without update_dashboard's heavy module init.

PHASE_CACHE_TTL_HOURS_DEFAULT = 24


def phase_cache_ttl_hours() -> float:
    """TTL in hours for phase-level cache entries (env: PHASE_CACHE_TTL_HOURS)."""
    raw = os.environ.get("PHASE_CACHE_TTL_HOURS", "")
    try:
        val = float(raw)
        if val > 0:
            return val
    except (TypeError, ValueError):
        pass
    return PHASE_CACHE_TTL_HOURS_DEFAULT


def phase_cache_key(phase: str) -> str:
    """Stable (date-independent) dashboard_state key for a pipeline phase."""
    return f"phase_cache_{phase.replace(' ', '_')}"


def phase_cache_fresh(cached_dict, ttl_hours: float = None) -> bool:
    """True when a cached phase payload is complete and within TTL.

    Requires a `_completed` flag and a parseable `_completed_at` UTC ISO
    timestamp; a payload missing either is rejected (forces a re-run).
    """
    if not isinstance(cached_dict, dict) or not cached_dict.get("_completed"):
        return False
    completed_at = cached_dict.get("_completed_at")
    if not completed_at:
        return False
    try:
        ts = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None) - ts.utcoffset()
    if ttl_hours is None:
        ttl_hours = phase_cache_ttl_hours()
    return datetime.utcnow() - ts < timedelta(hours=ttl_hours)


class PipelineCache:
    """Unified cache with type-specific TTLs. SQLite-backed."""

    def __init__(self, conn):
        self._conn = conn
        self._hits = 0
        self._misses = 0

    def get(self, key: str, cache_type: str):
        """Return cached value if exists and not expired. None otherwise."""
        now = datetime.utcnow().isoformat()
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache "
            "WHERE cache_key = ? AND cache_type = ?",
            (key, cache_type),
        ).fetchone()

        if row is None:
            self._misses += 1
            return None

        expires = row[1] if isinstance(row, (list, tuple)) else row["expires_at"]
        if expires and expires < now:
            # Expired — delete and return miss
            self._conn.execute(
                "DELETE FROM cache WHERE cache_key = ? AND cache_type = ?",
                (key, cache_type),
            )
            self._misses += 1
            return None

        # Hit — update stats
        self._conn.execute(
            "UPDATE cache SET hit_count = hit_count + 1, last_hit_at = ? "
            "WHERE cache_key = ? AND cache_type = ?",
            (now, key, cache_type),
        )
        self._hits += 1

        raw = row[0] if isinstance(row, (list, tuple)) else row["value"]
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def set(self, key: str, value, cache_type: str, ttl_days: int = None):
        """Store value with TTL. Uses type default if ttl_days not specified."""
        if ttl_days is None:
            ttl_days = DEFAULT_TTL.get(cache_type, 14)

        if ttl_days == 0:
            return  # never cache this type

        now = datetime.utcnow()
        expires = (now + timedelta(days=ttl_days)).isoformat()

        serialized = json.dumps(value) if not isinstance(value, (str, bytes)) else value

        self._conn.execute(
            "INSERT OR REPLACE INTO cache "
            "(cache_key, cache_type, value, created_at, expires_at, hit_count, last_hit_at) "
            "VALUES (?, ?, ?, ?, ?, 0, NULL)",
            (key, cache_type, serialized, now.isoformat(), expires),
        )
        self._conn.commit()

    def has(self, key: str, cache_type: str) -> bool:
        """Check existence without retrieving."""
        now = datetime.utcnow().isoformat()
        row = self._conn.execute(
            "SELECT 1 FROM cache WHERE cache_key = ? AND cache_type = ? AND expires_at > ?",
            (key, cache_type, now),
        ).fetchone()
        return row is not None

    def evict_expired(self) -> int:
        """Remove all expired entries. Run at sweep start.

        Returns:
            Number of entries evicted.
        """
        now = datetime.utcnow().isoformat()
        cursor = self._conn.execute(
            "DELETE FROM cache WHERE expires_at < ?", (now,),
        )
        count = cursor.rowcount
        self._conn.commit()
        if count:
            logger.info(f"[CACHE] Evicted {count} expired entries")
        return count

    def stats(self) -> dict:
        """Return cache hit/miss stats for logging."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        # Count entries by type
        rows = self._conn.execute(
            "SELECT cache_type, COUNT(*) FROM cache GROUP BY cache_type"
        ).fetchall()
        by_type = {}
        for row in rows:
            ct = row[0] if isinstance(row, (list, tuple)) else row["cache_type"]
            cnt = row[1] if isinstance(row, (list, tuple)) else row[1]
            by_type[ct] = cnt

        total_entries = sum(by_type.values())

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "entries": total_entries,
            "by_type": by_type,
        }

    def clear(self, cache_type: str = None):
        """Clear cache entries. If cache_type given, only clear that type."""
        if cache_type:
            self._conn.execute(
                "DELETE FROM cache WHERE cache_type = ?", (cache_type,),
            )
        else:
            self._conn.execute("DELETE FROM cache")
        self._conn.commit()


# ── Module-level singleton ────────────────────────────────────────────────

_cache = None


def get_cache(conn=None) -> PipelineCache:
    """Return the global PipelineCache singleton."""
    global _cache
    if _cache is None:
        if conn is None:
            raise RuntimeError("PipelineCache requires a DB connection on first call")
        _cache = PipelineCache(conn)
    return _cache
