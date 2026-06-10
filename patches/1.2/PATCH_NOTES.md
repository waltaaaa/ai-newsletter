# Patch 1.2 — discovery recall, week-to-week consistency, provincial accuracy, efficiency

**Status:** Implemented, tested (97 passed / 1 skipped / 0 failed); pending in-browser
verification of the presentation port and operator live-verification of external endpoints.
**Branch:** `patch-1.2` (fresh, rebuilt on `main` @ `3409046`; prior draft preserved as `patch-1.2-draft`)
**Date:** 2026-06-08
**Audit sources:** `PIPELINE_AUDIT.md` (original 31-issue log) + `PROJECT_AUDIT_2026-06-08_consolidated.md`
(8-auditor verification) + `DISCOVERY_IMPROVEMENT_PLAN.md`.
**Safety snapshot before apply:** git tag `pre-patch-1.2-snapshot-20260608` + branch `backup/pre-patch-1.2-snapshot`.

---

## What this patch is

Patch 1.2 consolidates two earlier unmerged branches (`patch-1.2-draft`,
`audit-fixes-20260608`) onto current `main` and adds the high-impact fixes that
neither branch had. It targets four goals the operator called out: **find all
qualifying projects**, **consolidate duplicates / attach real source links**,
**report provincial data accurately**, and **run more consistently and efficiently
week-to-week**.

The audit also *corrected* the original issue log in two important ways, both
honored here:

1. **D-4 ("status enum drift") is NOT a data bug.** Every status in `dashboard.db`
   is already canonical per `normalize.py`. The real defect was three conflicting
   *vocabularies* (DI-5). The old fix (remap `Proposed→Announced`) would have
   *corrupted* 2,698 correct rows — it has been neutralized.
2. **The pollution (D-1/D-14) is already published live** (DI-1) and worse than
   reported (46 Saskatchewan date-string rows, not 9). Export-boundary gates now
   keep it out of `docs/data` even if upstream regresses.

---

## Fixes included

### Discovery / recall ("find all qualifying projects")
| ID | Fix | File(s) |
|----|-----|---------|
| **D-11** | L7 NIM rerank is a relevance FILTER, not a top-50 cap. Every article scored in <=512 chunks; kept by `RERANK_MIN_LOGIT`; logit distribution logged; **sanity guard** falls back to the full L6 set if rerank would drop >80% (was starving extraction: 25,176 Google-News articles -> 0). | `article_filter.py` |
| **D-7..D-10** | Shared `http_client.py` (browser UA, `Accept-Language: en-CA`, certifi TLS, per-host retry/backoff) wired into every Tier-1/5/13/14 + procurement + policy scraper; BC EAO querystring bug fixed; IWK certifi fix; per-source health + **min-yield DEGRADE** logs; **D-10 government_bypass** passthrough (policy yield 1/3 -> 2/3 in unit check). | `http_client.py` (new), `gov_sources.py`, `municipal_dev_apps.py`, `institutional_capital.py`, `procurement_monitor.py`, `policy_tracker.py`, `provincial_policy_monitor.py` |
| **D-13** | Claude Code per-chunk timeout: retry-once + 300s for large chunks (from `audit-fixes`). | `phases/filtering.py` |
| **E-5/E-6** | RSS extraction workers 3->6; selective Claude extraction parallelized (3 workers) — ~60% wall-clock saving on that phase. | `phases/filtering.py`, `claude_reasoning.py` |

### Week-to-week consistency ("operate as intended, same each week")
| ID | Fix | File(s) |
|----|-----|---------|
| **D-16** | `briefing_archive.json` export is **additive** — unions on-disk + DB by `week_of`, never shrinks (was collapsing the edition dropdown 8->1 on each clean run; previously survived only via a manual git restore). | `tools/export_dashboard.py` |
| **NEW-2/M-2** | `weekly_briefings` table now written every finalize (`_sync_weekly_briefings`), with a one-time backfill of missing weeks. | `phases/finalize.py` |
| **NEW-4** | An empty/soft-failed conductor payload no longer clobbers `newsletter_latest` — prior edition preserved, run demoted **critical**. | `phases/finalize.py` |
| **NEW-3** | Deterministic export order (`get_projects`: `ORDER BY lastSeen DESC, norm_key ASC`; `export_all_projects`: `norm_key` tiebreaker) — kills VACUUM-driven churn so unchanged data produces an unchanged file. | `db.py`, `tools/export_dashboard.py` |
| **NEW-1** | `quality_tier` added to the canonical schema in `init_db` — fixes the export crash on a fresh DB and the 5 export tests. | `db.py` |
| **export coverage** | `microscope.json` (Under the Microscope) was never wired into `export_all` — now exported. | `tools/export_dashboard.py` |
| **M-1/NEW-7** | Phase-crash and empty-payload events logged `severity=critical` so run status is honest (`success`/`degraded`/`partial`). | `update_dashboard.py`, `phases/finalize.py`, `pipeline_logging.py` |
| **M-8/M-9** | Structured `[PHASE_BEGIN/END]` markers + progress prints in long loops (from `patch-1.2-draft`). | `update_dashboard.py`, `semantic_article_dedup.py` |

### Provincial accuracy ("accurately report provincial projects")
| ID | Fix | File(s) |
|----|-----|---------|
| **Provincial over-count + DI-1** | Export-boundary gates drop structurally-invalid names (nav items, date strings) and **valueless non-project document filings** (Forest Management Plans, reports, EIS, terms of reference) from the published province lists. Rows remain in the DB (additive-only preserved). Fixes the MB (2,037 raw) / NL (1,554 raw) inflation. | `tools/export_dashboard.py` (+ `db._is_non_project_name`) |
| **D-15** | Indicators that fail validation are blanked (`value=null`, `_stale=true`, `value_raw` kept) so the frontend renders an **em-dash** instead of a stale/wrong number (e.g. agri_exports frozen at 2003, Ontario CPI 6.8%). `fmtNum` renders null as em-dash. | `tools/export_dashboard.py`, `docs/js/app.js`, `public/js/app.js` |
| **D-12** | Cross-province CPI outlier check (from `audit-fixes`). | `indicator_validator.py` |

### Tracking / dedup ("consolidate duplicates, attach source links")
| ID | Fix | File(s) |
|----|-----|---------|
| **DI-3** | The scalar `discovery_source` is now folded into the `discovery_sources[]` array on insert AND rediscovery (was empty for 96.6% of rows) — restores per-project provenance. | `db.py` |
| **D-3** | Opt-in `LI_MERGE_DEBUG=1` prints evidence-merge before/after so the operator can confirm whether rediscovery consolidates (the diagnostic the audit asked for). Fuzzy consolidation remains the `tools/dedup_projects_fuzzy.py` cadence tool (kept on `main`; not added to the hot upsert path to avoid false-merge risk). | `db.py` |
| **D-1/D-14** | Name-quality gate at the upsert boundary (from `audit-fixes`) + export-boundary gate (DI-1) as defense-in-depth. | `db.py`, `tools/export_dashboard.py` |
| **M-3** | `prioritize_alerts` for Under Construction projects; `_DEACTIVATE_STATUSES` includes `Completed`. | `project_alert_tracker.py` |
| **M-4** | `confidence_decay` wired into Phase 6 (from `patch-1.2-draft`); drives staleness off the honest `lastSeen` (2,344 rows are genuinely 30d+). | `phases/finalize.py`, `confidence_decay.py` |
| **M-5/M-7** | service_health expanded + persisted; per-feed RSS health table (from `patch-1.2-draft`). | `service_health.py`, `rss_feed_health.py`, `rss_monitor.py` |

### Accuracy / replication
| ID | Fix | File(s) |
|----|-----|---------|
| **D-4 / DI-5** | `normalize.py` is the single status source of truth; `project_schema.normalize_status` delegates to it; migration 001 neutralized (no Proposed->Announced remap). | `project_schema.py`, `patches/1.2/migrations/001_backfill_status_enum.sql` |
| **NEW-8** | Test baselines un-staled: query-count assert is now a floor (additive-only), lookback scoped to instruction-style queries (keyword queries are windowed at fetch — E-4), brownfield live test marked `skip`. | `tests/test_compound_queries.py`, `tests/test_brownfield_discovery.py` |

### Presentation (Demo -> live parity, code-only)
Ported the Demo's Economist-style SVG insight + markets + yield-curve chart engines,
Data Explorer overhaul, chart-intro prose, FX grid, industry header, 1400px max-width;
cache-bust `?v=20260608a`. **Live-only features preserved** (Projects "new this week"
filter/sort, province Labour Market Detail, WCS analysis). `docs/` and `public/` kept
byte-identical. (`PRES-01..14`.)

---

## Migrations

`backend/patches/1.2/migrations/` — applied by the operator (the app also creates
tables/columns defensively on first use):

```bash
cd backend
# 001 is now a NO-OP (DI-5) — safe to run, changes nothing.
sqlite3 dashboard.db < patches/1.2/migrations/002_weekly_briefings_schema.sql
sqlite3 dashboard.db < patches/1.2/migrations/003_alerts_health.sql
sqlite3 dashboard.db < patches/1.2/migrations/004_rss_feed_health.sql
sqlite3 dashboard.db < patches/1.2/migrations/005_service_health_history.sql
```

Do not apply while a pipeline run holds a write lock.

---

## Verification

- PASS **Test suite: 97 passed, 1 skipped, 0 failed** (was 8 failed / 90 passed pre-patch).
- PASS Every changed `.py` compiles.
- PASS `normalize_status('Proposed') == 'Proposed'` (no drift); canon matches `normalize.py`.
- PASS Export determinism + additive archive verified via the export test suite.
- WARN **Presentation port needs an in-browser pass** — `node` was unavailable for a real
  JS parse (brace/paren/bracket balance verified OK; static server returns HTTP 200).
  Visually check the Brief / National / Industries / Markets / Explorer tabs and the
  SVG charts/tooltips before deploy.
- DONE **External endpoints live-verified 2026-06-09** — see
  `SOURCE_ENDPOINTS_NEEDS_LIVE_VERIFICATION.md` for the full resolution log.
  Highlights: BC EAO re-pointed at the EPIC search API (0 → 358 projects);
  NB EIA migrated to www.gnb.ca and re-scoped; all 4 procurement sources
  restored (Open Canada via CKAN datastore, BuyAndSell → CanadaBuys CSVs,
  BC Bid → CanadaBuys BC fallback; Ontario BPS confirmed removed upstream);
  ~25 Tier-13/14 URLs re-resolved; D-5/D-15 StatCan vectors resolved against
  the ACTIVE cubes (34-10-0292 permits, 14-10-0063 wages, 12-10-0163 exports —
  the old agri_exports vector pointed at a wrong, 2003-frozen cube) with fetch
  loops added for provincial buildingPermits/wageGrowth; http_client no longer
  advertises brotli it cannot decode (was corrupting ArcGIS Online responses).
  Still dark (correct URLs, server-side blocks): Port of Montreal, Port of
  Halifax, Kelowna (WAF/TLS fingerprinting).

---

## Deferred (documented, not in this patch)

Lower-value or higher-risk items left for a follow-up so the applied patch stays
testable and safe: E-2 (phase-cache TTL), E-3/E-10 (conductor Popen+watchdog —
hot-path, unverifiable offline), E-4/E-7/E-9 (article-cache / `pipeline_cache`
wiring), E-8 (numpy-vectorize semantic dedup), NEW-5 (conductor model pinning),
NEW-9 (timeseries prune), D-5 vector population, D-6 commodity fallback,
PATCH-FRAMEWORK manifest completeness. See `PROJECT_AUDIT_2026-06-08_consolidated.md`
section 5 for the full list.

---

## Rollback

`git checkout main` (or the `backup/pre-patch-1.2-snapshot` branch / tag). The DB
migrations are additive (new tables/columns) and 001 is a no-op, so no data rollback
is required. See `patches/1.2/rollback.md`.
