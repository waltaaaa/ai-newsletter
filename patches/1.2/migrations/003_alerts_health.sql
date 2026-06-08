-- Patch 1.2 — migration 003
-- audit ref: M-3 (project_alerts health columns)
--
-- Adds tracking columns to project_alerts so we can:
--   - Distinguish "alert is fresh" from "alert hasn't been checked in months"
--   - Auto-deactivate alerts after N consecutive empty checks
--   - Surface alert health on the dashboard ops page
--
-- The application code in project_alert_tracker.py does NOT yet read or
-- write these columns — that wiring is intentionally deferred to a future
-- patch (see PATCH_NOTES.md § Open follow-ups). This migration just lays
-- the schema groundwork so the future patch is a code-only delta.
--
-- Run manually:
--   sqlite3 backend/dashboard.db < backend/patches/1.2/migrations/003_alerts_health.sql

BEGIN TRANSACTION;

-- last_check_at: ISO8601 timestamp of most recent fetch attempt
-- (independent of last_checked which the existing code uses; this is
-- explicit about "tried" vs "found items"). Existing `last_checked`
-- is preserved for backward compat.
ALTER TABLE project_alerts ADD COLUMN last_check_at TEXT DEFAULT NULL;

-- last_hit_at: ISO8601 timestamp of the most recent fetch that returned
-- ≥1 article. Used to compute "consecutive_empty_checks".
ALTER TABLE project_alerts ADD COLUMN last_hit_at TEXT DEFAULT NULL;

-- consecutive_empty_checks: zero-based counter, reset on a hit. Future
-- patch will auto-deactivate when this exceeds a threshold (proposed: 12,
-- ≈ 3 months of weekly checks).
ALTER TABLE project_alerts ADD COLUMN consecutive_empty_checks INTEGER DEFAULT 0;

COMMIT;
