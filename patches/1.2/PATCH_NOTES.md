# Patch 1.2 — audit fixes: discovery, monitoring, decay, alerts

**Status:** Drafted
**Branch:** `patch-1.2`
**Author:** Claude Code agent
**Date drafted:** 2026-06-08
**Audit references:** D-2, D-4, M-2, M-3, M-4, M-5, M-7, M-8, M-9

---

## Summary

Patch 1.2 is the first formal patch shipped under the new
`backend/patches/` framework. It addresses eight findings from
`PIPELINE_AUDIT.md` (the 2026-06-08 audit) — all monitoring or boundary-
hardening work, none of it disturbing the running pipeline's hot path.

The fixes break into two themes:

- **Boundary hardening at the upsert layer (D-2, D-4).** Silent rejections
  and status drift are now caught and surfaced before they reach `db.py`.
- **Closing monitoring gaps (M-2, M-3, M-4, M-5, M-7, M-8, M-9).** Five
  separate "silent degradation" failure modes the operator could not see
  are now persisted to SQLite or printed to the run log with structured
  markers.

---

## Why (audit linkage)

Per `PIPELINE_AUDIT.md` (2026-06-08):

- **D-2** — `upsert_flat_projects` does not enforce the URL hard gate;
  rejections are silent and bucketed only as `Skipped: N` → addressed by
  **Fix 1**.
- **D-4** — DB has 3,400+ rows with non-canonical status (`Proposed`,
  `Complete`, `On Hold`) → addressed by **Fix 2**.
- **M-2** — `weekly_briefings` table 3-week stale vs on-disk briefings →
  addressed by **Fix 3**.
- **M-4** — `confidence_decay.py` exists but is wired into no phase; 0
  projects flagged stale → addressed by **Fix 4**.
- **M-3** — Only 18% of Under Construction projects carry an alert
  (the ones most likely to change status) → addressed by **Fix 5**.
- **M-7** — 333 RSS feeds configured, 153 returning items, no per-feed
  history table → addressed by **Fix 6**.
- **M-8** — Pipeline log has no machine-readable phase boundary markers
  → addressed by **Fix 7** (first half).
- **M-9** — Silent 20-minute semantic-dedup loop — operator can't tell
  wedged from working → addressed by **Fix 7** (second half).
- **M-5** — Service health covers only 7 services; in-memory only →
  addressed by **Fix 8**.

---

## What changed

### Fix 1 — D-2: URL hard gate + rejection-reason breakdown (commit `271ee68`)

- File: `backend/project_sync.py`
- Added `_project_has_url()` helper and `_CANONICAL_PROVINCES` set.
- `upsert_flat_projects` now pre-validates rows for `no_name`, `no_province`,
  `invalid_province`, `no_url` BEFORE forwarding to `db.upsert_project`.
- Rejection bookkeeping uses a `Counter`. New log line:
  `[UPSERT] {n} processed, {new} new, {updated} updated, {skipped} skipped`
  followed by `Rejection reasons: {dict}`.
- No changes to `db.py` (Agent 1 owns it).

### Fix 2 — D-4: status enum normalization at upsert boundary (commit `b4bdb95`)

- File: `backend/project_schema.py`
- Added `CANONICAL_STATUSES` frozenset, `STATUS_ALIASES` dict, and
  `normalize_status(raw)` function.
- Folds `Proposed → Announced`, `Complete → Completed`,
  `In Service → Operational`, `On Hold → Paused`, etc.
- Unknown values default to `Announced` (safest).
- `project_sync.py` (already shipped in commit `271ee68`) calls
  `normalize_status()` at the upsert boundary.

### Fix 3 — M-2: weekly_briefings table sync (commit `8c883e3`)

- File: `backend/phases/finalize.py`
- Added `_sync_weekly_briefings(conn, final_payload)` — defensive
  `INSERT OR REPLACE` keyed on `week_of`. Creates the table + adds
  `briefing_json` / `edition` columns + unique index if missing.
- Called from inside the `Final assembly + push to SQLite` block right
  after `save_dashboard_state('newsletter_latest', ...)`.
- Logs `[FINALIZE] weekly_briefings synced for week_of={...}` on success.

### Fix 4 — M-4: wire `confidence_decay` into Phase 6 (commit `e4cd086`)

- File: `backend/phases/finalize.py`
- At top of `run()` (before StatCan snapshot, timeseries, export), import
  `confidence_decay.apply_confidence_decay` and invoke with `conn`.
- Logs `[DECAY] N decayed, M stale, K need review` and writes three
  `logger.log_metric` entries under the `decay` bucket.
- No changes to `confidence_decay.py` itself — its existing
  `apply_confidence_decay` already matches the CLAUDE.md schedule
  (31-60d -0.05, 61-90 -0.10, 91-120 -0.15, 121+ -0.20, 181+ stale).

### Fix 5 — M-3: per-status alert prioritization (commit `061511b`)

- Files: `backend/project_alert_tracker.py`, `backend/phases/finalize.py`
- New `prioritize_alerts(conn)` walks the projects table for
  `status='Under Construction'` rows; registers or reactivates alerts as
  needed. Logs `[ALERTS] {with_alerts}/{total} Under Construction
  projects have alerts`.
- `deactivate_terminal_projects` now also matches `Completed`
  (post-D-4 canonical form) alongside legacy `Complete`.
- Wired into `phases/finalize.py` after the decay step.

### Fix 6 — M-7: per-feed RSS health tracker (commit `b4d0805`)

- New file: `backend/rss_feed_health.py`
- New SQLite table `rss_feed_health(feed_url PK, last_success_at,
  last_status, items_last_7d, items_lifetime, first_seen,
  consecutive_empty_weeks, last_check_at)`.
- Functions: `record_fetch`, `mark_empty`, `get_dead_feeds`,
  `get_health_summary`. Table is defensively `CREATE`d on first use.
- Integrated into `rss_monitor.fetch_all_feeds` after the existing
  `_persist_feed_health` call. Non-critical try/except.

### Fix 7 — M-8 + M-9: structured phase markers + progress prints (commit `012b353`)

- Files: `backend/update_dashboard.py`, `backend/semantic_article_dedup.py`
- `update_dashboard.py`: every phase invocation is wrapped with
  `[PHASE_BEGIN <name> t=<epoch>]` and
  `[PHASE_END <name> t=<epoch> dt=<sec> status=<ok|timeout|error|cached>]`.
  Human-readable header preserved.
- `semantic_article_dedup.py`: progress prints every 100 comparisons in
  the O(N²) cosine loop:
  `[SEMANTIC] processed K/N comparisons (t+Xs)`.

### Fix 8 — M-5: service health expansion + DB persistence (commit `90cfeb7`)

- Files: `backend/service_health.py`, `backend/update_dashboard.py`
- New `_thresholds` entries: `claude_cli`, `groq`, `anthropic_api`,
  `statcan_wds`, `statcan_csv`, `nim_nemotron`, `nim_deepseek`,
  `nim_rerank`, `nim_embed`, `nim_ocr` (all threshold = 3).
- New `ServiceHealth.persist(conn, run_id)` method writes a snapshot of
  every threshold'd service to a new `service_health_history` table.
- `update_dashboard.py` calls `health.persist(conn, run_log._run_id)`
  once at the end of the run, just before the final `get_status()` print.

---

## Migrations to apply

Five SQL files under `backend/patches/1.2/migrations/`. The pipeline does
**not** run them automatically. The application code creates the tables /
adds the columns defensively on first use, so these migrations are only
required if you want the schema present BEFORE the first patched-pipeline
run completes (or if you want the D-4 status backfill).

```bash
cd backend
sqlite3 dashboard.db < patches/1.2/migrations/001_backfill_status_enum.sql
sqlite3 dashboard.db < patches/1.2/migrations/002_weekly_briefings_schema.sql
sqlite3 dashboard.db < patches/1.2/migrations/003_alerts_health.sql
sqlite3 dashboard.db < patches/1.2/migrations/004_rss_feed_health.sql
sqlite3 dashboard.db < patches/1.2/migrations/005_service_health_history.sql
```

Order matters only for `001` (status enum backfill — should run before the
first patched-pipeline write to projects, otherwise the new writes go in
canonical form and historical rows stay drifted).

**Important:** the active weekly pipeline run was in flight while this
patch was drafted. Do not apply migrations against `dashboard.db` while
the run holds a write lock — wait for the run to finalize.

---

## Verification

After applying:

- [ ] `python -m py_compile backend/project_sync.py backend/project_schema.py`
      `backend/phases/finalize.py backend/project_alert_tracker.py`
      `backend/rss_feed_health.py backend/rss_monitor.py`
      `backend/update_dashboard.py backend/semantic_article_dedup.py`
      `backend/service_health.py` exits 0.
- [ ] Run `python backend/patches/apply_patch.py verify 1.2` — exits 0.
- [ ] After the next pipeline run:
    - **D-2:** Log line `[UPSERT] N processed ... Rejection reasons: {...}`
      appears. Buckets should sum to `skipped`.
    - **D-4:** `SELECT DISTINCT status FROM projects` returns only the
      eight canonical statuses (post-backfill).
    - **M-2:** `SELECT week_of, headline FROM weekly_briefings
      ORDER BY week_of DESC LIMIT 5` shows the current week + recent
      history. `[FINALIZE] weekly_briefings synced for week_of=...`
      appears in the log.
    - **M-4:** `SELECT COUNT(*) FROM projects WHERE is_stale=1` returns
      > 0 (it was 0 across all 7,717 rows before this patch).
      `[DECAY] N decayed, M flagged stale, K need review` appears.
    - **M-3:** `[ALERTS] X/Y Under Construction projects have alerts`
      shows X close to Y. `project_alerts` has new rows for previously
      uncovered UC projects.
    - **M-7:** `SELECT COUNT(*) FROM rss_feed_health` returns > 0.
      `get_dead_feeds(conn, 8)` returns a list of retirement candidates.
    - **M-8:** Run log contains `[PHASE_BEGIN ...]` and `[PHASE_END ...
      dt=N status=ok]` for every phase. Grepping for `PHASE_END.*error`
      gives a fast post-mortem.
    - **M-9:** During Phase 3 semantic dedup, log contains
      `[SEMANTIC] processed N/M comparisons (t+Xs)` markers every 100
      iterations.
    - **M-5:** `SELECT service, status, failure_count FROM
      service_health_history WHERE run_id = <latest>` returns a row for
      every threshold'd service.

---

## Rollback

See `rollback.md` in this folder.

Code revert: `git revert -m 1 <merge-sha-of-patch-1.2>`.
Migrations: see `rollback.md` § Data rollback. All five migrations are
additive (no DROPs, no UPDATEs that lose information except 001).

---

## Open follow-ups

Items deliberately left undone, with the TODO marker location:

- **L6 NIM classifier progress prints (M-9 second half)** — semantic
  dedup got progress markers; the L6 NIM classifier in
  `article_filter.filter_articles` did not, to avoid touching the active
  filter chain mid-pipeline-run. Tracked as TODO in commit `012b353`'s
  message.
- **rss_monitor real HTTP status code** — `rss_feed_health.record_fetch`
  receives `status=200 if items>0 else 0`. The actual HTTP status from
  `_fetch_one` isn't surfaced today. Wiring it through would let the
  ops page distinguish 404-dead from 200-empty. TODO comment lives at
  the `record_fetch` call site in `rss_monitor.py`.
- **project_alerts auto-deactivation by consecutive_empty_checks (M-3
  second half)** — migration `003_alerts_health.sql` adds the columns
  but the application code does not yet read/write them. Wiring is a
  code-only change for a future patch.
- **weekly_briefings on-disk backfill (M-2)** — Future patch: a one-off
  script that walks `docs/data/briefing_*.json` and inserts missing
  weeks. Migration `002` is schema-only.
- **D-1, D-3, D-5..D-15** — most of these need either a scraper rewrite
  (D-1, D-14, D-8), DB-level changes (D-3 evidence merge — touches db.py),
  research (D-5 StatCan vectors), or live-pipeline data (D-6 commodity
  poisons). All are deferred to future patches or to operator follow-up.
- **E-1..E-6** — efficiency items not in this patch's scope.

The framework's `depends_on` chain means a future patch addressing any of
these will declare `depends_on: ["1.2"]` and ship as `1.3`.
