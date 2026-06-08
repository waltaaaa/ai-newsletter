-- Patch 1.2 — migration 002
-- audit ref: M-2 (weekly_briefings table out of sync with on-disk briefings)
--
-- Adds the briefing_json TEXT column + edition TEXT column + unique index
-- on week_of needed for the new _sync_weekly_briefings() upsert in
-- phases/finalize.py.
--
-- The application code (finalize.py) does the same ALTER defensively at
-- runtime, so this migration only matters if you want the schema fixed
-- BEFORE the first patched-pipeline run completes.
--
-- Run manually:
--   sqlite3 backend/dashboard.db < backend/patches/1.2/migrations/002_weekly_briefings_schema.sql
--
-- After running, optionally backfill from on-disk briefing files; sketched
-- at the bottom (commented).

BEGIN TRANSACTION;

-- briefing_json: full final_payload JSON for that week's edition
-- (sections column is kept for legacy compat but is just a fragment).
ALTER TABLE weekly_briefings ADD COLUMN briefing_json TEXT DEFAULT '';

-- edition: the human-readable "EDITION: MAY 12 – MAY 19 // STATUS: ..." line
ALTER TABLE weekly_briefings ADD COLUMN edition TEXT DEFAULT '';

-- Unique index on week_of so INSERT ... ON CONFLICT(week_of) works as upsert.
-- If the table currently has duplicate week_of rows, the CREATE will fail —
-- run the dedup query below first.
CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_briefings_week_of
    ON weekly_briefings(week_of);

COMMIT;

-- Optional dedup (run BEFORE the CREATE UNIQUE INDEX above if it fails):
--   DELETE FROM weekly_briefings
--   WHERE id NOT IN (
--       SELECT MAX(id) FROM weekly_briefings GROUP BY week_of
--   );

-- Optional backfill from on-disk briefing files (operator-only, requires
-- scripting on the OS side — sqlite can't read filesystem). Sketch:
--   For each docs/data/briefing_*.json:
--     - Read week_of from the JSON
--     - INSERT OR REPLACE INTO weekly_briefings(...)
--   Tool: python -c "import json,glob,sqlite3; ..."
