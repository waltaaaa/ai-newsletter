-- Patch 1.2 — migration 005
-- audit ref: M-5 (service health is in-memory only)
--
-- Documents the schema for service_health_history. The application code
-- (backend/service_health.py ServiceHealth.persist) creates the table
-- defensively on first call, so this migration is only needed if the
-- operator wants the schema present before the first patched-pipeline
-- run completes.
--
-- Run manually:
--   sqlite3 backend/dashboard.db < backend/patches/1.2/migrations/005_service_health_history.sql

BEGIN TRANSACTION;

-- Per-run, per-service health snapshot. PK is (run_id, service) so a row
-- can be updated mid-run via INSERT OR REPLACE without breaking history.
CREATE TABLE IF NOT EXISTS service_health_history (
    run_id        INTEGER,
    service       TEXT,
    status        TEXT,            -- 'ok' | 'degraded' | 'dead'
    failure_count INTEGER DEFAULT 0,
    recorded_at   TEXT,
    PRIMARY KEY (run_id, service)
);

-- Common query: "show me the dead-rate trend for service X over the last
-- 8 weekly runs". Index on service speeds that up.
CREATE INDEX IF NOT EXISTS idx_service_health_history_service
    ON service_health_history(service);

COMMIT;
