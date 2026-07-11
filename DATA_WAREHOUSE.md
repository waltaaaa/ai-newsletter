# Data Warehouse — Connection Monitoring Layer

One place that knows about every external data connection the pipeline depends
on, and one place that records whether each connection actually retrieved data
on each run. Built 2026-07-11 from the data-retrieval audit (RC-6: "retrieval
failure is invisible — no central per-connection success/failure record").

## Design

- **`data_warehouse.py`** (repo root)
  - `CONNECTIONS` — static registry of ~31 connections (StatCan WDS groups,
    yfinance batches, BoC Valet, FRED, policy/job/procurement monitors, IAAC,
    RSS tiers, Tavily, etc.), each with id, module, category, cadence,
    expected series, and endpoint notes. **Additive only** — append new
    connections, never remove or rename ids.
  - `connection_runs` (SQLite, dashboard.db) — one row per connection per
    attempt: started/finished, status (`ok|degraded|failed|skipped`),
    items_fetched, items_saved, error summary.
  - `series_accrual` (SQLite) — latest reference period per registered series
    vs its expected frequency; detects "series stopped accruing" even when the
    connection reports ok (e.g. the dead ISQ scrape, RC-9). Refreshed by
    `check_health()` from `indicator_history` / `timeseries`.
  - `record_run(connection_id, status, items_fetched=, items_saved=, error=,
    conn=)` — guaranteed never to raise into the caller.
  - `track(connection_id, conn=)` — context manager / decorator. Catches
    nothing: an exception is recorded as `failed` and re-raised; on normal
    exit records `t.status` (default ok). Set `t.items_fetched` etc. inside
    the block.
  - `check_health(conn=, now=)` — per-connection health: last-success age vs
    cadence (`warn` > 1x, `critical` > 2x — per the audit recommendation),
    consecutive failures (`critical` >= 2), overdue series. Connections never
    recorded are `unknown`, not failed.
  - `write_status_json()` / `log_health_summary()` — JSON export + loud
    `[WAREHOUSE]` stdout lines.

- **`tools/warehouse_report.py`** — CLI: health table + writes
  `docs/data/warehouse_status.json` (mirrored to `public/data/`; deploy syncs
  public/ → docs/). `--json` dumps raw, `--no-write` report-only. Always
  exits 0 (monitoring is informational; the deploy gate stays in
  `tools/validate_briefing_schema.py`).

- **Pipeline hook** — `update_dashboard.py` runs `check_health()` +
  `write_status_json()` after the operator summary at the end of every weekly
  run, printing `[WAREHOUSE][CRITICAL]` / `[WAREHOUSE][WARN]` lines. Wrapped
  in try/except — it can never crash the pipeline.

## Reading warehouse_status.json

```json
{
  "generated_at": "...",
  "summary": {"ok": n, "warn": n, "critical": n, "unknown": n,
              "overdue_series_total": n},
  "connections": [{
    "id": "statcan_wds_vectors", "health": "warn",
    "last_run_at": "...", "last_status": "ok", "last_success_at": "...",
    "days_since_success": 3, "consecutive_failures": 0,
    "overdue_series": [{"name": "housing_starts_total",
                        "latest_period": "2026-05-01", "gap_days": 71,
                        "frequency": "monthly"}],
    "series": [...], "notes": "..."
  }]
}
```

Health levels: `unknown` = never recorded (uninstrumented or job never ran);
`ok` = recent success, nothing overdue; `warn` = dark past cadence, one
failure, degraded, or an overdue series; `critical` = dark past 2x cadence or
>= 2 consecutive failures.

Series overdue thresholds are frequency-aware (daily 9d — tolerant of market
holidays, weekly 16d, monthly 65d, quarterly 150d, annual 460d), replacing the
flat 540-day stale threshold that caught nothing.

## Instrumenting a new connection

1. Append an entry to `CONNECTIONS` in `data_warehouse.py` (never remove one).
   Register any `indicator_history` / `timeseries` series it should keep
   accruing — use only series names verified in code, never invented.
2. At the module's summary point, either:
   ```python
   from data_warehouse import record_run
   record_run("my_connection", "ok" if items else "failed",
              items_fetched=len(raw), items_saved=len(saved),
              error="" if items else "why it failed", conn=conn)
   ```
   or wrap the fetch:
   ```python
   from data_warehouse import track
   with track("my_connection", conn=conn) as t:
       rows = fetch()
       t.items_fetched = len(rows)
   ```
3. Status semantics: `failed` = the connection retrieved nothing it should
   have; `degraded` = partial (some sources errored, budget hit, filters got
   everything); `skipped` = intentionally not attempted (mode-skip);
   `ok` = normal. A quiet-but-healthy week is `ok`, not `degraded`.
4. Both APIs never raise into your code — instrumentation must never break
   retrieval.

## Currently instrumented call sites (2026-07-11)

- `statcan_extended.run_extended_statcan` → `statcan_wds_vectors`, `statcan_wds_meta`
- `phases/data_collection.run` (Phase 1) → `yf_commodities`, `yf_markets`,
  `boc_valet`, `statcan_lfs_primary`, `global_indicators`
- `canadian_markets.fetch_and_store_commodities` → `yf_canadian_proxies`, `statcan_canola`
- `policy_tracker.run_policy_tracker` → `policy_tracker`
- `job_monitor.run_job_monitor` → `job_monitor`
- `procurement_monitor.run_procurement_monitor` → `procurement_monitor`
- `gov_sources._scrape_iaac` → `iaac_registry`
- `iaac_status.run_iaac_status` → `iaac_status_tracker`

The remaining registry entries (RSS tiers, discovery scrapers, Tavily, the
daily CI refresher, etc.) show as `unknown` until their modules adopt
`record_run()` — deliberately distinct from `failed`.
