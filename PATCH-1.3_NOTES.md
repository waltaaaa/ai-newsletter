# Patch 1.3 — Discovery Framework Improvements + Capital Map Preview

**Branch:** `patch-1.3` (built on `patch-1.2`, which is applied locally but not deployed)
**Date:** 2026-06-09
**Status:** STAGED — awaiting operator preview approval before merge/deploy
**Source plans:** `DISCOVERY_IMPROVEMENT_PLAN.md` (2026-06-08 audit) + claude.ai "Signal Dispatch" v2.1 gap analysis (`preview-patch-1.3/DISCOVERY_SYSTEM_V2.1_GAP_ANALYSIS.md`)

---

## 1. Discovery fixes implemented in this patch

### C1 — Fuzzy rediscovery fallback in the live upsert (`db.py`)
The live write path matched only the exact `name+province` slug, so any name
variation wrote a duplicate row (measured: 90.8% of projects had exactly one
evidence item; 96.6% had empty multi-tier provenance). After an exact-key miss,
`upsert_project` now runs a blocked fuzzy lookup (same province + ≥4-char
distinctive-token LIKE blocking) using the STRICT guarded matcher from
`tools/dedup_projects_fuzzy.is_duplicate_pair` — series-identifier, proponent,
CMA, and value-ratio contradiction kills, listing URLs excluded from the
shared-URL signal (C6). Biased toward false-negative by design. Disable with
`LI_FUZZY_UPSERT=0`. Merge hits are counted (`db.get_merge_counters`) and
logged as `[DB FUZZY-MERGE]`.

### C2 — Weekly fuzzy-dedup report pass (`phases/finalize.py`)
Every run now executes `tools/dedup_projects_fuzzy.py --report
dedup_report_weekly.md` (dry-run). Merging the backlog stays operator-gated via
`--merge` — never auto-applied.

### C4 — STATUS_ORDER reconciled (`tools/dedup_projects_fuzzy.py`)
The offline tool now ranks the live canonical statuses (adds Rumoured,
On Hold, Suspended, Partially Complete) so merge precedence can't mis-rank.
Legacy aliases kept additively. No Proposed→Announced remap.

### C5 — Hold statuses no longer regress advanced projects (`db.py`)
`On Hold`/`Suspended`/`Paused` were in `_TERMINAL_STATES` (always apply), so a
media article saying "delayed" flipped Under Construction projects to On Hold.
Now only `Cancelled` is unconditional; hold states require an explicit signal
(`explicit_hold`/`regulatory_signal` flag or government-authority evidence on
the incoming record). Suppressed holds are logged, not silently dropped.

### S1 — `source_url` scalar folded into evidence (`project_sync.py`)
Scrapers set a direct deep link on `source_url`, but only `evidence[]` survived
the upsert boundary — the scalar was discarded (28% of projects carried only a
listing-page link). Both `upsert_projects` and `upsert_flat_projects` now fold
it into `evidence[]` with `classify_source_authority` stamped (which also feeds
the government-source confidence bonus and the C5 hold gate). `proponent` is
now forwarded too (it was dropped, weakening the C1 contradiction guard).

### S2 — `source_url_quality` populated (`db.py`, `url_utils.py`)
Was empty for all 7,661 rows. Every insert/update now classifies the best link
as `deep` / `listing` / `homepage` (canonical helpers in `url_utils.py`),
making the listing-only-link problem measurable.

### E6 — Per-reason rejection counters (`db.py`, `project_sync.py`)
`upsert_project` rejections are now counted by reason
(`invalid_province` / `non_project_name` / `no_url`) and surfaced in the flat-
sync summary as `db_*` buckets instead of one opaque `db_rejected` number.

### P2 — MB EA registry no longer blanket-stamps "Under Review" (`gov_sources.py`)
The Manitoba scraper now reads status-bearing cells from the registry row
(approved / licence issued / construction / cancelled / …) via `_map_status`;
the default remains Under Review only when the row states nothing. (NL already
read its status column; 1,952/2,037 MB rows were stuck at Under Review.)

### R3 — Snowball discovery wired (deep-sweep only) (`phases/discovery.py`)
`snowball_discovery.run_snowball_sweep` had zero callers. It now runs in
`--deep-sweep` mode (gated by `SNOWBALL_DISCOVERY_ENABLED`) — it is too
query-heavy (421-query Pass 1) for the weekly run.

### R4 — Known-project sweep cadence (`phases/discovery.py`, `update_dashboard.py`)
The sweep now runs in deep-sweep mode and stamps
`dashboard_state.last_known_sweep_date` (also stamped by `--known-sweep`).
Weekly runs log `[KNOWN-SWEEP OVERDUE]` once the stamp is >35 days old instead
of letting evidence silently go stale.

### Bug fix — new-vs-updated pre-check used the wrong key (`project_sync.py`)
The pre-check built keys from the full province name (`…__manitoba`) while
db.py stores 2-letter codes (`…__mb`), so `get_project()` never found the
existing row: every rediscovery was counted "new" and
`_sync_evidence_and_org` never saw prior state (no status-change events were
generated from this path). Fixed via `_db_key()`; fuzzy merges are also now
counted as updates, not new.

### Carried from patch-1.2 working tree (live-verified 2026-06-09)
- BC EAO: EPIC public-search API endpoint confirmed live (old /api/v2 404s,
  api-public host is DNS-dead) — `gov_sources.py`
- NB EIA: original underscore-less URL is correct; failures were UA bot-blocks
- IWK Health Centre: moved to `iwkhealth.ca` (apex only) — `institutional_capital.py`
- Procurement: Open Canada CKAN datastore API + endpoint re-resolution — `procurement_monitor.py`

## 2. Already done in patch-1.2 (no work needed)
R1 (L7 rerank zeroing — D-11), R2 (extraction timeout retry — D-13),
C3 (discovery_sources stamping — DI-3), S5/P1 (name gates + export-boundary
filing filters — D-1/D-14/DI-1), E7 (per-source health + min-yield DEGRADE),
E9 (confidence decay wired in finalize — M-4).

## 3. Deliberately NOT implemented (needs approval or live verification)
- **Tavily $30/month plan** (v2.1 gap analysis recommendation) — violates the
  ~$20/year budget cap without explicit operator approval.
- **R5** (municipal/institutional URL re-resolution) — partially carried;
  remaining URLs need live verification.
- **S3** (url_verify + Wayback in live path), **P4 remainder**, **P6** (StatCan
  vectors), **E1** (Google News week cache), **R6/R8** — next patch candidates.
- **Territorial co-management boards**: YESAB and MVEIRB scrapers already
  exist; NIRB (Nunavut) is a coverage gap candidate for a future patch.

## 4. Capital map preview (NOT integrated)
`preview-patch-1.3/capital_map_prototype.html` — self-contained single-file
map (Statistics Canada Lambert geometry, choropleth + CMA bubbles + pre-RFP
filter), sample data only. Serve locally:
`python -m http.server 8765 --directory preview-patch-1.3` →
http://localhost:8765/capital_map_prototype.html
Not wired into `docs/` or `public/` — integration happens only after operator
approval, targeting the GitHub Pages frontend (NOT SharePoint).
`ab_test_harness.py` and the v2.1 gap analysis are staged alongside for reference.

## 5. Verification
- `pytest tests -q`: **107 passed, 1 skipped** (10 new regression tests in
  `tests/test_patch13_discovery.py` covering C1, C5, S1, S2, E6 and the
  norm-key bug fix).
- Not yet live-verified: weekly-run end-to-end with the fuzzy fallback against
  the production `dashboard.db` (recommend `LI_MERGE_DEBUG=1` on first run).
