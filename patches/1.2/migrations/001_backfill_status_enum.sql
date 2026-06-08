-- Patch 1.2 — migration 001
-- audit ref: D-4 (status enum drift)
--
-- One-time backfill of historical projects to the canonical status enum.
-- The application code already normalizes on every upsert (D-4 commit), so
-- this only catches rows written before the fix.
--
-- Counts before backfill (per 2026-06-08 audit):
--   Proposed:           2,698
--   Under Review:       2,664   (already canonical — kept)
--   Under Construction: 1,055   (already canonical — kept)
--   Approved:             596   (already canonical — kept)
--   Complete:             510
--   Cancelled:            163   (already canonical — kept)
--   On Hold:               31
--
-- Run manually:
--   sqlite3 backend/dashboard.db < backend/patches/1.2/migrations/001_backfill_status_enum.sql
--
-- This script is idempotent — re-running it is a no-op.

BEGIN TRANSACTION;

UPDATE projects SET status='Completed'   WHERE status='Complete';
UPDATE projects SET status='Announced'   WHERE status='Proposed';
UPDATE projects SET status='Paused'      WHERE status='On Hold';
UPDATE projects SET status='Operational' WHERE status='In Service';
UPDATE projects SET status='Announced'   WHERE status='Rumoured';
UPDATE projects SET status='Announced'   WHERE status='Rumored';

-- Catch any case-variant drift
UPDATE projects SET status='Announced'         WHERE status IN ('announced', 'proposed');
UPDATE projects SET status='Completed'         WHERE status IN ('complete', 'completed');
UPDATE projects SET status='Approved'          WHERE status='approved';
UPDATE projects SET status='Cancelled'         WHERE status IN ('cancelled', 'canceled');
UPDATE projects SET status='Paused'            WHERE status IN ('paused', 'on hold', 'on-hold');
UPDATE projects SET status='Operational'       WHERE status IN ('operational', 'in service');
UPDATE projects SET status='Under Construction' WHERE status IN ('under construction', 'in construction', 'construction');
UPDATE projects SET status='Under Review'      WHERE status='under review';

-- Catchall: anything still outside the canonical set becomes Announced.
-- This is a safety net; if the count is non-zero after the explicit maps
-- above, the operator should review BEFORE running this line. To audit,
-- comment out the UPDATE and run:
--   SELECT status, COUNT(*) FROM projects
--   WHERE status NOT IN ('Announced','Approved','Under Construction',
--                        'Operational','Completed','Cancelled','Paused',
--                        'Under Review')
--   GROUP BY status;
UPDATE projects SET status='Announced'
WHERE status NOT IN (
    'Announced', 'Approved', 'Under Construction', 'Operational',
    'Completed',  'Cancelled', 'Paused', 'Under Review'
);

COMMIT;

-- Post-migration sanity check (run separately, not part of the BEGIN/COMMIT):
--   SELECT status, COUNT(*) FROM projects GROUP BY status ORDER BY 2 DESC;
-- Expected: only the eight canonical statuses appear.
