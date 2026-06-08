"""
rss_feed_health.py — Per-feed RSS health tracker (audit M-7).

The repo already aggregates "X items from Y/Z feeds" in rss_monitor.py and
persists a JSON snapshot in dashboard_state.feed_health. That gives a
this-run view but doesn't answer:

  - Which 180 of the 333 feeds returned zero items this week, and how
    many of them are seasonal vs dead?
  - How many consecutive weekly runs has feed F been empty?
  - How long since feed F last returned a successful HTTP response?
  - Which feeds are candidates for retirement (additive-only invariant —
    we flag, we don't remove)?

This module persists per-feed metrics in a normalized SQLite table so
those questions become a SELECT, not a transcript-grep.

Schema:

    CREATE TABLE rss_feed_health (
        feed_url TEXT PRIMARY KEY,
        last_success_at TEXT,
        last_status INTEGER,        -- HTTP status of most recent fetch
        items_last_7d INTEGER DEFAULT 0,
        items_lifetime INTEGER DEFAULT 0,
        first_seen TEXT,
        consecutive_empty_weeks INTEGER DEFAULT 0
    )

Integration:
  - Call record_fetch(conn, feed_url, status, items_count) once per feed
    fetch from rss_monitor.fetch_all_feeds.
  - On weekly run completion, optionally call get_dead_feeds(conn) to
    surface candidates for retirement.

The module is safe to import even if the table doesn't exist — init() is
called automatically on first use and is idempotent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_TABLE_INIT_DONE = False


def init(conn) -> None:
    """Create the rss_feed_health table if it doesn't exist. Idempotent."""
    global _TABLE_INIT_DONE
    if _TABLE_INIT_DONE:
        return
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rss_feed_health (
                    feed_url                TEXT PRIMARY KEY,
                    last_success_at         TEXT DEFAULT '',
                    last_status             INTEGER DEFAULT 0,
                    items_last_7d           INTEGER DEFAULT 0,
                    items_lifetime          INTEGER DEFAULT 0,
                    first_seen              TEXT DEFAULT '',
                    consecutive_empty_weeks INTEGER DEFAULT 0,
                    last_check_at           TEXT DEFAULT ''
                )
            """)
            # Index for the get_dead_feeds query
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rss_feed_health_empty "
                "ON rss_feed_health(consecutive_empty_weeks)"
            )
        _TABLE_INIT_DONE = True
    except Exception as e:
        logger.warning(f"rss_feed_health init failed: {e}")


def _now_iso() -> str:
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def record_fetch(conn, feed_url: str, status: int, items_count: int) -> None:
    """Record one fetch attempt for a feed.

    Args:
        conn: sqlite3.Connection
        feed_url: the feed URL (PK)
        status: HTTP status code; 0 if request never completed (network error)
        items_count: number of items the fetch produced (after `days_back` filter)

    Behaviour:
      - INSERTs a row on first sight (first_seen = now)
      - On a fetch with items_count > 0:
          * sets last_success_at = now (regardless of status, as long as
            items came back; a 200 with 0 items is still 'empty')
          * resets consecutive_empty_weeks = 0
          * adds items_count to items_lifetime
      - On a fetch with items_count == 0:
          * increments consecutive_empty_weeks
          * does NOT touch last_success_at
      - Always updates last_status, last_check_at, items_last_7d.

    items_last_7d is a coarse approximation — for now we store the most
    recent run's count. A future patch can roll a true 7-day sum across
    multiple runs.
    """
    if not feed_url:
        return
    init(conn)

    now = _now_iso()
    try:
        existing = conn.execute(
            "SELECT items_lifetime, consecutive_empty_weeks, first_seen, last_success_at "
            "FROM rss_feed_health WHERE feed_url = ?",
            (feed_url,),
        ).fetchone()

        if existing is None:
            first_seen = now
            new_lifetime = max(items_count, 0)
            consecutive_empty = 0 if items_count > 0 else 1
            last_success = now if items_count > 0 else ''
        else:
            first_seen = existing[2] or now
            prev_lifetime = existing[0] or 0
            prev_empty = existing[1] or 0
            prev_success = existing[3] or ''
            if items_count > 0:
                new_lifetime = prev_lifetime + items_count
                consecutive_empty = 0
                last_success = now
            else:
                new_lifetime = prev_lifetime
                consecutive_empty = prev_empty + 1
                last_success = prev_success

        with conn:
            conn.execute(
                """INSERT INTO rss_feed_health
                       (feed_url, last_success_at, last_status, items_last_7d,
                        items_lifetime, first_seen, consecutive_empty_weeks,
                        last_check_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(feed_url) DO UPDATE SET
                       last_success_at         = excluded.last_success_at,
                       last_status             = excluded.last_status,
                       items_last_7d           = excluded.items_last_7d,
                       items_lifetime          = excluded.items_lifetime,
                       consecutive_empty_weeks = excluded.consecutive_empty_weeks,
                       last_check_at           = excluded.last_check_at
                """,
                (feed_url, last_success, int(status or 0),
                 max(items_count, 0), new_lifetime, first_seen,
                 consecutive_empty, now),
            )
    except Exception as e:
        # Health tracking is non-critical — don't propagate
        logger.debug(f"record_fetch failed for {feed_url}: {e}")


def mark_empty(conn, feed_url: str) -> None:
    """Record an explicitly-empty fetch (no items returned) for a feed.

    Convenience wrapper around record_fetch with items_count=0 and
    status=200 (the request succeeded; the feed just had nothing new).
    Use this when the caller knows the HTTP succeeded but the parsed
    feed had zero entries — distinguishes from a 404 / network error.
    """
    record_fetch(conn, feed_url, status=200, items_count=0)


def get_dead_feeds(conn, threshold_weeks: int = 8) -> list[dict]:
    """Return feeds that have been empty for >= threshold_weeks runs.

    These are candidates-for-retirement — operator decides. The additive-
    only invariant means this module does not remove them; it flags.

    Args:
        conn: sqlite3.Connection
        threshold_weeks: minimum consecutive_empty_weeks to qualify

    Returns:
        list of dicts ordered by consecutive_empty_weeks DESC:
            {feed_url, last_success_at, items_lifetime, consecutive_empty_weeks,
             first_seen, last_status}
        Empty list on error.
    """
    init(conn)
    try:
        rows = conn.execute(
            """SELECT feed_url, last_success_at, items_lifetime,
                      consecutive_empty_weeks, first_seen, last_status
               FROM rss_feed_health
               WHERE consecutive_empty_weeks >= ?
               ORDER BY consecutive_empty_weeks DESC, items_lifetime ASC
            """,
            (int(threshold_weeks),),
        ).fetchall()
    except Exception as e:
        logger.warning(f"get_dead_feeds query failed: {e}")
        return []

    out = []
    for r in rows:
        out.append({
            "feed_url": r[0],
            "last_success_at": r[1] or '',
            "items_lifetime": r[2] or 0,
            "consecutive_empty_weeks": r[3] or 0,
            "first_seen": r[4] or '',
            "last_status": r[5] or 0,
        })
    return out


def get_health_summary(conn) -> dict:
    """Return aggregate counts for the dashboard ops page.

    {
        total_feeds:    int,
        active:         feeds with at least one success this run
        dormant:        feeds with 1-7 consecutive empty weeks
        dead_candidate: feeds with >=8 consecutive empty weeks
        lifetime_items: sum across all feeds
    }
    """
    init(conn)
    try:
        row = conn.execute(
            """SELECT COUNT(*),
                      SUM(CASE WHEN consecutive_empty_weeks = 0 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN consecutive_empty_weeks BETWEEN 1 AND 7 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN consecutive_empty_weeks >= 8 THEN 1 ELSE 0 END),
                      SUM(items_lifetime)
               FROM rss_feed_health
            """
        ).fetchone()
    except Exception as e:
        logger.warning(f"get_health_summary failed: {e}")
        return {"total_feeds": 0, "active": 0, "dormant": 0,
                "dead_candidate": 0, "lifetime_items": 0}
    if not row:
        return {"total_feeds": 0, "active": 0, "dormant": 0,
                "dead_candidate": 0, "lifetime_items": 0}
    return {
        "total_feeds":    int(row[0] or 0),
        "active":         int(row[1] or 0),
        "dormant":        int(row[2] or 0),
        "dead_candidate": int(row[3] or 0),
        "lifetime_items": int(row[4] or 0),
    }
