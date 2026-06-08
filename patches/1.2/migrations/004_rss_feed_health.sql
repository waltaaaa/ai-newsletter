-- Patch 1.2 — migration 004
-- audit ref: M-7 (per-feed RSS health tracker)
--
-- Documents the schema for the new rss_feed_health table. The application
-- code in backend/rss_feed_health.py creates the table defensively on first
-- use, so this migration only matters if the operator wants the schema
-- present BEFORE the first patched-pipeline run completes.
--
-- Run manually:
--   sqlite3 backend/dashboard.db < backend/patches/1.2/migrations/004_rss_feed_health.sql

BEGIN TRANSACTION;

-- Per-feed health metrics. PK is feed_url so a feed retire-then-re-add
-- preserves history.
CREATE TABLE IF NOT EXISTS rss_feed_health (
    feed_url                TEXT PRIMARY KEY,
    last_success_at         TEXT DEFAULT '',
    last_status             INTEGER DEFAULT 0,
    items_last_7d           INTEGER DEFAULT 0,
    items_lifetime          INTEGER DEFAULT 0,
    first_seen              TEXT DEFAULT '',
    consecutive_empty_weeks INTEGER DEFAULT 0,
    last_check_at           TEXT DEFAULT ''
);

-- Index for the get_dead_feeds() query — operator dashboard queries by
-- consecutive_empty_weeks DESC.
CREATE INDEX IF NOT EXISTS idx_rss_feed_health_empty
    ON rss_feed_health(consecutive_empty_weeks);

COMMIT;
