# Patch 1.2 — Rollback procedure

## Code rollback

```bash
cd /c/AI_newsletter/backend

# 1. Find the merge commit for patch-1.2 on main (or whichever
#    integration branch the patch was merged into)
git log --merges --oneline | grep "patch-1.2"
# → <merge-sha> Merge branch 'patch-1.2'

# 2. Revert it
git revert -m 1 <merge-sha>
```

This restores the source tree to commit
`72beb2b7930a7cdd75810b05cf70fc1dd5d49375` (the pre-patch HEAD of `main`,
recorded in `manifest.json: rollback_commit`).

The eight patch-1.2 fix commits and the framework commit are all reverted
together by the single `git revert -m 1`.

**Patch dependency:** no patch currently declares `depends_on: ["1.2"]`.
If one is added later (e.g. patch 1.3 that wires `consecutive_empty_checks`
auto-deactivation on top of the columns added by migration 003), that
newer patch must be rolled back first.

## Data rollback

All five migrations in this patch are predominantly additive (new tables
or new columns). The status backfill (001) is the only one that rewrites
data and is reversible only if you took a snapshot before applying.

| Migration                              | Reversible? | Rollback strategy |
|----------------------------------------|-------------|-------------------|
| `001_backfill_status_enum.sql`         | No (without snapshot) | The `UPDATE projects SET status=...` queries replace old values with canonical ones. The old values (`Proposed`, `Complete`, `On Hold`, `In Service`) are lost. If you need to roll back AND keep the old values, take a backup of the `projects.status` column BEFORE applying 001: `CREATE TABLE projects_status_backup_pre_1_2 AS SELECT rowid, status FROM projects;` Then reverse via: `UPDATE projects SET status = (SELECT status FROM projects_status_backup_pre_1_2 WHERE projects_status_backup_pre_1_2.rowid = projects.rowid);` |
| `002_weekly_briefings_schema.sql`      | Yes (no-op)  | The added columns (`briefing_json`, `edition`) and unique index are harmless to leave in place. SQLite does not support `DROP COLUMN` cleanly across versions; leave them. |
| `003_alerts_health.sql`                | Yes (no-op)  | Three new nullable columns. Leave them. |
| `004_rss_feed_health.sql`              | Yes (DROP)   | `DROP TABLE IF EXISTS rss_feed_health;` is safe — table is purely an additive monitoring sink. |
| `005_service_health_history.sql`       | Yes (DROP)   | `DROP TABLE IF EXISTS service_health_history;` is safe — same shape as 004. |

### After rollback — verification

- [ ] `python -m py_compile` on each file in `files_modified` and
      `files_added` — should still compile after the revert (the revert
      removes the additions).
- [ ] Pipeline runs without erroring on the removed features. The new
      `[UPSERT]`, `[DECAY]`, `[ALERTS]`, `[PHASE_BEGIN]`,
      `[PHASE_END]`, `[SEMANTIC]`, and persisted-health markers no longer
      appear in the run log — expected.
- [ ] Edit `backend/patches/1.2/manifest.json`: set `applied_at` to `""`.
- [ ] Commit `chore(patch-1.2): rolled back on YYYY-MM-DD`.

## Partial rollback

If only one or two fixes need to be reverted (e.g. M-4 decay revealed too
many stale projects for the dashboard to handle gracefully), revert
individual commits:

```bash
# Revert just the decay wiring
git revert e4cd086

# Revert just M-3 prioritize_alerts
git revert 061511b
```

This leaves the rest of patch 1.2 in place. The migrations remain
applied — that's a feature: schema additions are forward-compatible
even if the code that reads them is reverted.
