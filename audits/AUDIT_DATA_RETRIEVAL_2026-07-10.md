# Data Retrieval Audit — Root Causes of Dropped / Empty Data Points
Repo: /home/user/ai-newsletter · Audit date: 2026-07-10

Owner's problem statement: "Data points dropped between editions, or data returned with empty values when the data exists."

Verdict: both symptoms are real and reproducible in the shipped data files. They are not caused by one bug but by an architectural pattern: **every retrieval path saves only the single latest observation per run, stamps it with whatever date convention that writer uses, prints failures to stdout, and always exits 0.** A missed run, a transient API failure, a freshness-gate rejection, or a stamping-convention mismatch each silently produces a permanent hole — and the export layer's "never lose history" union then preserves every bad point forever while never repairing a missing one.

---

## RC-1 (CRITICAL): Latest-observation-only persistence — fetched history is thrown away

`statcan_extended.py:552-553` fetches `n=14` periods per vector (`n = 14 if frequency == "monthly" ...`), and `_fetch_meta_group` does the same (`statcan_extended.py:764`), but **only `points[-1]` is ever saved** (`statcan_extended.py:568`, `statcan_extended.py:804`). The other 13 fetched observations are discarded.

Consequences, verified in shipped data:
- `docs/data/timeseries.json` → `housing_starts_total` has **4 points total**: `2026-03-01, 2026-04-01, 2026-04-01(dup), 2026-05-01`. StatCan has years of this series; the pipeline had 14 months of it in memory every single run and kept one.
- `healthcare_employment` in `docs/data/indicators.json` history: **one month** (2026-05-01, duplicated — see RC-5). Every META_RESOLVED series added 2026-06-11 will take a year of flawless weekly runs to accumulate 12 chart points; a single missed run across a month boundary (see RC-2) permanently drops that month.
- Same pattern in `phases/data_collection.py` (`fetch_industry_indicators` line ~1396 fetches n=14, archiver stores only the latest via `_archive_indicators_to_history`).

The one place that got this right is canola: `canadian_markets.py:534-538` writes **each** of the 14 monthly points under its own refPer ("re-appending the last 14 months every week backfills history once and is idempotent"). That comment describes exactly the fix every StatCan group needs. `save_indicator`'s upsert (`db.py:1718`) is already idempotent on `(indicator_name, period, province)`, so saving all fetched points is safe today.

## RC-2 (CRITICAL): A missed/failed run across a reference-period boundary = permanent gap

Because of RC-1, the schedule is the only thing standing between a transient failure and a hole:
- `_fetch_wds` chunk failure after 3 attempts (`statcan_extended.py:526-527`) **prints and moves on**; the group is counted in `tables_failed` (`statcan_extended.py:907-911`), the return dict goes into pipeline context, and **nothing downstream reads or persists it** — no alert, no retry next run, no backlog (contrast with the article `extraction_backlog` mechanism which does carry over).
- Freshness-gate rejection (`_is_fresh`, `statcan_extended.py:465-472`; skips at 574-577, 816-819) is print-only. The three archived-cube vectors in `INVESTMENT_BUILDING` (`statcan_extended.py:76-85`) are re-fetched and re-rejected **every run** — permanent noise that trains the operator to ignore `[STALE]` lines.
- WDS items with `status != 'SUCCESS'` are dropped with **no log at all** (`statcan_extended.py:502-503` and `788-789`) — a terminated/renamed vector simply vanishes; the only symptom is "no data returned" at group level.
- Whole-repo evidence of a dark period: last data-refresh commit is `b58f450 2026-06-29`; today is 2026-07-10. Every market series in timeseries.json ends 2026-06-25..29. **Eleven days of daily-cron silence and nothing in the repo flags it** — no "last successful run age" watchdog anywhere.

## RC-3 (CRITICAL, historical but still shipping): mixed date-stamping conventions corrupted series, and gaps from the pre-D5 era were never backfilled

`_archive_indicators_to_history` (`phases/data_collection.py:1511-1562`) now stamps StatCan reference periods and loudly skips rows without one (D5 fix, 2026-06-11). But the pre-fix rows are still in `indicator_history` and still shipped:

`docs/data/timeseries.json` → `AB_unemployment` tail:
```
2026-02-01  6.3   (reference-period stamped)
2026-03-06  6.4   ← run-date stamped (pre-D5 daily runs)
2026-03-09  6.4
2026-03-14  6.3
2026-03-15  6.3
2026-05-01  6.6   (reference period)
2026-05-15  7.0   ← run-date stamped
2026-06-08  6.6   ← run-date stamped
```
Reference periods **2026-03-01 and 2026-04-01 do not exist** — the March and April LFS prints are dropped even though StatCan has them (the data exists; the archiver only ever saw "latest" and stamped it wrong at the time). National `unemployment` shows the identical hole (indicators.json history: `2026-02-01 → 2026-03-06/09/14/15 → 2026-05-01`). The 05-15/06-08 rows carry source `'StatCan'` but land on non-reference dates — the value at 2026-05-15 (7.0) even disagrees with 2026-06-08 (6.6) for what should be the same month. These are almost certainly `tldr-data-refresh` (WebSearch agent) snapshot writes from before the red-team 2.7 provenance rule (`.claude/skills/tldr-data-refresh/SKILL.md:21`).

Worse, `QC_cpi` / `ON_cpi` mix **three quantities** in one series: CPI index levels (93.6, 172.9 — pre-Feb-2026), YoY rates (0.6, 1.5), and disagreeing web-search prints. The export-side H5 guard (`tools/export_dashboard.py:1552-1562`) drops index-valued points only for the `{PROV}_cpi` provincial pull path — but the shipped file shows 93.6/172.9 still present because…

## RC-4 (HIGH): The export "never lose history" union makes bad points immortal and can never fill a gap

`export_timeseries` merges the DB pull into the on-disk file point-wise (`_merge_series_by_date`, `tools/export_dashboard.py:1386-1415`; merge loop 1630-1652). Union semantics mean:
- Corrupt legacy points already on disk (run-date stamps, index/rate mixtures, web prints) are **preserved forever** — the H5 guard filters the DB pull, not the on-disk side, so filtered garbage re-enters from `existing`.
- There is no mechanism to *delete* a wrong point or *repair* a missing one; the only pruning is whole-series removal under `TIMESERIES_PRUNE=1` at 540-day staleness (`timeseries_stale_report.json` currently threshold=540, empty).
- The same union pattern exists in the daily CI writer `tools/refresh_timeseries_commodity.py:_merge_points` (147-187) — with a different sanity gate (median-ratio) than the DB path, so the two writers disagree about which points are acceptable.

## RC-5 (HIGH): Province-name case/format split still produces duplicates and split series

`save_indicator` normalizes only `national` case variants (`db.py:1687-1688`). Provincial writers disagree: Phase 1 archives under **full names** ("Alberta"), statcan_extended QC series write `province='QC'`, backfills wrote codes. Fixes are query-side band-aids:
- `export_timeseries` D1 fix queries both forms (`tools/export_dashboard.py:1517-1540`).
- But the `_IH_SERIES` and history pulls don't: `indicators.json` history shows `healthcare_employment 2026-05-01` **twice** (one row `province='National'` legacy, one `'national'`) because `GROUP BY indicator_name, province, period` (`export_dashboard.py:1195-1201`) treats them as distinct; timeseries `housing_starts_total` ships `2026-04-01` twice for the same reason. Duplicate same-date points render as chart artifacts.

## RC-6 (HIGH): Retrieval failure is invisible — no central per-connection success/failure record

- statcan_extended returns a summary dict (`statcan_extended.py:944-949`) that is never persisted or checked.
- `phases/signals.py` wraps every signal source in `except Exception: print(...)` (lines 29-30, 41-42, 50) — a dead Job Bank feed or SEAO outage produces one stdout line in a GH Actions log nobody reads, and the edition ships with those sections quietly empty.
- `tools/refresh_timeseries_commodity.py:378` **returns 0 even when every series failed** — a yfinance rate-limit day (Yahoo throttles GitHub runner IPs regularly) is a green check with zero new points.
- What exists is partial and disconnected: `pipeline_runs` (per-phase steps/errors, `db.py:248-259`), `rss_feed_health` table (RSS only, `rss_feed_health.py`), `service_health_history` (circuit-breaker snapshots, `service_health.py`), `dashboard_state.feed_health`, `tier_yield_history`/`query_yield_history` (discovery yield only). **No table records "connection X: last attempted, last succeeded, rows saved, last error" across all ~30 connections.**

## RC-7 (MEDIUM): yfinance handling — cache-of-nothing, partial batches, holiday semantics

- `phases/data_collection.py:143-146`: batch `yf.download` failure → `data=None`, per-ticker fallback exists (good, 161-167), but a fully failed result `{"indices": [], "fx": []}` is **not cached-negative-checked** — while a *partially* failed result IS cached for 12h (`_cache.set(..., ttl_hours=12)`, line 211/287), so one bad fetch poisons both the daily and any same-day weekly run.
- Contract-rollover guard (lines 182-187) silently substitutes prev_close — reasonable, but unrecorded.
- Weekend/holiday: `week_ago = col.iloc[-6]` style indexing (canadian_markets.py:293, 332-334) counts trading days, fine; but `finalize.append_to_timeseries` stamps **today** (`phases/finalize.py:128`) for briefing prints — Monday runs write Monday-dated points for Friday closes (excluded from exports via `briefing_print`, so contained).
- Missing 2026-06-19 points (gold, sp500) are the Juneteenth US holiday — correct absence; a naive gap-detector must be trading-calendar aware.

## RC-8 (MEDIUM): Series saved to indicator_history that no export ever ships

META_RESOLVED national series (`retail_sales_national`, `manufacturing_sales_national`, `wholesale_sales_national`, `job_vacancies_total`, `nat_avg_hourly_wage`, all `*_employment` sector series, `energy_exports`/`mineral_exports`/…) are **absent from timeseries.json** because `_IH_SERIES` (`export_dashboard.py:1457-1477`) doesn't list them and `_TIMESERIES_NAMES` (line 97) doesn't either. They reach `indicators.json` history only. Any chart-agent dataKey pointing at them in timeseries.json silently blanks (the validator's cross-reference check covers briefing insightCharts, but the CLAUDE.md-promised "~90 keys, count grows" contract is only half-wired). `comm_uranium`, written weekly by `canadian_markets.py:512`, likewise never ships.

## RC-9 (MEDIUM): Dead upstream sources persist as permanently stale series

- ON quarterly economic accounts + QC ISQ series (`ON_on_exports` … `QC_qc_real_gdp`) frozen at **2025-10-01** in timeseries.json; the ISQ Excel scrape is dead (`tools/refresh_provincial_oea_isq.py`; the QC replacement via WDS covers only permits/trade/retail — the QC WDS series themselves show latest 2026-02/2026-04, i.e. the daily runs skip them or the last weekly run predates newer prints).
- `INVESTMENT_BUILDING` archived-cube vectors (RC-2) and `CONSTRUCTION_PRICE_INDEX` (empty vectors dict, `statcan_extended.py:90-94`) are permanent no-ops still iterated every run.
- indicators.json `validation.failed_indicators` currently flags 8, including the three archived building-investment series (value nulled, `value_raw` kept — correct behavior per D-15) and `rice/national` (period 2026-06-22 flagged, likely recency-vs-frequency rule mismatch: a daily-priced commodity validated under a monthly rule → **an example of "empty value when data exists"**: `value: null, value_raw: 6.38`).

## RC-10 (LOW): 24h/12h caches can serve a failed-partial payload into the weekly edition

`get_global_indicators` caches whatever partial dict it assembled for 24h (`data_collection.py:1280-1287, 1371-1372`); if FRED was down at daily-run time, the weekly run 5 hours later reuses the holey payload. Fields absent → archiver skips (correct), but the edition then shows em-dashes for data that exists — the second symptom in the problem statement.

---

## Concrete examples found (data as shipped)

| Example | File | What's wrong |
|---|---|---|
| `AB_unemployment` missing 2026-03-01, 2026-04-01; has 2026-03-06/09/14/15 instead | docs/data/timeseries.json | RC-3 run-date stamps, never backfilled |
| `unemployment` (national) same hole | docs/data/indicators.json history | RC-3 |
| `QC_cpi` values 93.6→0.6→1.5→-0.4 (index + YoY + web print in one series) | docs/data/timeseries.json | RC-3/RC-4 |
| `housing_starts_total` 4 points, `2026-04-01` duplicated | docs/data/timeseries.json | RC-1 + RC-5 |
| `healthcare_employment` single month, duplicated row | docs/data/indicators.json | RC-1 + RC-5 |
| `retail_sales_national`, `job_vacancies_total`, `nat_avg_hourly_wage`, `comm_uranium` absent | docs/data/timeseries.json | RC-8 |
| `ON_on_*`, `QC_qc_exports` frozen at 2025-10-01 | docs/data/timeseries.json | RC-9 |
| `rice` current value nulled (`value_raw: 6.38`, period 2026-06-22) | docs/data/indicators.json | RC-9 (validator false-positive class) |
| All market series end 2026-06-25..29; today 2026-07-10 | timeseries.json / git log | RC-2/RC-6 (no watchdog) |
| `timeseries_stale_report.json` empty at 540-day threshold | docs/data/timeseries_stale_report.json | threshold too loose to catch any of the above |

## Where existing health checks fall short

- `indicator_validator.py` — validates the **latest row per indicator** (range/delta/recency/units). It cannot see missing periods, run-date stamps, or series that stopped accruing (an absent row is never validated). Its recency check flagged the archived building-investment vectors (good) but false-positives daily commodities under monthly rules (`rice`).
- `rss_feed_health.py` — RSS-only; no equivalent for WDS vectors, yfinance tickers, FRED, BoC, procurement endpoints.
- `service_health.py` — in-run circuit breaker; `persist()` snapshots exist but nothing alerts on trends and it never covers "service up but returned stale/empty".
- `tools/export_dashboard.py` stale report — 540-day threshold catches nothing relevant (monthly series need ~45-60d thresholds by frequency).
- `tldr-data-gap` skill — audits at briefing time via WebSearch, i.e., after the DB already has the hole; fills forward-looking working data, does not repair indicator_history.
- `tools/validate_briefing_schema.py` — validates briefing/dataKey cross-refs, not per-series continuity.
- `pipeline_runs` — phase-level, not connection-level; errors list is free-text JSON.
- **No test in tests/ asserts period continuity of indicator_history or timeseries.json.**

## Recommended fixes (ordered by leverage)

1. **Save all fetched observations, not just the latest** in `_fetch_table_group` / `_fetch_meta_group` / industry-GDP archiving (upsert is already idempotent). This single change retro-fills RC-1 gaps on the next run — including the missing AB/national March-April LFS points, since WDS still serves them.
2. One-time repair script: delete/requarantine run-date-stamped rows (period not matching frequency grid AND metadata lacking `reference_period == period`) from indicator_history, and rebuild timeseries.json provincial/indicator keys from the repaired DB (the union merge will otherwise resurrect them — the rebuild must bypass the on-disk union for repaired keys).
3. Normalize province at the `save_indicator` chokepoint for ALL provinces (full name → code), mirroring the D10 national fix.
4. Central `connection_runs` table (see below) + a "last success age" check wired into the validator deploy gate as WARN, and into a GH Actions step that fails loudly when a connection is dark > its cadence × 2. Make `refresh_timeseries_commodity.py` exit non-zero when >N series fail.
5. Add META_RESOLVED / comm_* keys to `_IH_SERIES`, or derive `_IH_SERIES` from the DB (`SELECT DISTINCT indicator_name`) with an explicit denylist.
6. Frequency-aware stale thresholds in the stale report (monthly 60d, quarterly 150d, daily 7 trading days) instead of a flat 540d.

---

## WAREHOUSE REQUIREMENTS — connection inventory (30 connections)

Each row = one distinct retrieval connection to monitor. "Failure mode" = what happens today when it breaks.

| # | Connection | Module (entry) | Cadence | Current failure mode |
|---|---|---|---|---|
| 1 | StatCan WDS — hardcoded vector groups (34-10-0293/0175, 34-10-0035, 14-10-0326, 12-10-0163, 34-10-0143, 18-10-0205) | statcan_extended.py `_fetch_table_group` | weekly + daily(monthly-only) | chunk fail → stdout print, group lost for the run; non-SUCCESS vector → silent drop; latest-obs-only |
| 2 | StatCan WDS — META_RESOLVED coordinate groups (14-10-0022, 14-10-0063, 14-10-0372, 16-10-0047, 20-10-0008, 20-10-0074, 34-10-0292, 36-10-0112 + QC series) | statcan_extended.py `_fetch_meta_group` | weekly + daily | metadata fetch fail / unmatched member / range / freshness → loud stdout skip, no persistence, no alert; latest-obs-only |
| 3 | StatCan WDS — national+provincial LFS/CPI primary (14-10-0287 etc.) | phases/data_collection.py | weekly + daily | partial payload archived; missing obs_date → skip; pre-D5 rows still polluting |
| 4 | StatCan WDS — industry GDP (36-10-0434) | phases/data_collection.py `fetch_industry_indicators` | weekly | N/A strings on failure; latest-obs-only |
| 5 | StatCan WDS — building permits anomaly signal | statcan_permits.py | weekly | print-and-continue |
| 6 | StatCan farm prices — canola vector 31212214 (32-10-0077) | canadian_markets.py `_fetch_statcan_monthly` | weekly | logger.warning, indicator absent; GOOD: writes all 14 points |
| 7 | Bank of Canada Valet — policy rate, yields, prime | phases/data_collection.py `get_boc_rate`/`_boc_series`; tools/refresh_timeseries_commodity.py | daily + weekly | 1 retry; None on failure → em-dash |
| 8 | yfinance — commodities batch (~35 tickers) | phases/data_collection.py `get_commodities` | daily + weekly | batch fail → per-ticker fallback; partial result cached 12h; per-ticker skip print |
| 9 | yfinance — indices + FX | phases/data_collection.py `get_financial_markets` | daily + weekly | empty dict on total failure (not cached), silent row drop per ticker |
| 10 | yfinance — Canadian proxies (U-UN.TO, FM.TO, SLX, LBR=F, NTR.TO, CCO.TO, basket) | canadian_markets.py | weekly | logger.warning skip; indicator absent from commodities.json |
| 11 | yfinance — daily CI series refresh (~40 keys) | tools/refresh_timeseries_commodity.py (data-refresh.yml, 07:00 UTC) | daily | per-series failed list printed; **exit 0 always**; workflow green on total failure; job itself dark since 2026-06-29 |
| 12 | FRED CSV (no key) — base metals, spreads, curve; global indicators | tools/refresh_timeseries_commodity.py `_fetch_fred`; data_collection `_fred_*` | daily / weekly | fail-soft, series untouched; 24h cache of partial global payload |
| 13 | ECB SDW + BoE IADB + World Bank — global indicators | phases/data_collection.py `get_global_indicators` | weekly (24h cache) | field absent → archiver skips → em-dash in edition |
| 14 | tldr-data-refresh WebSearch agent (Cowork fallback) | .claude/skills/tldr-data-refresh | ad-hoc weekly | writes snapshots; historical source of run-date-stamped pollution; provenance tag honor-system |
| 15 | Google News RSS compound queries (2,574+) | google_news_rss_search.py | weekly | per-query yield history exists (flag-only) |
| 16 | RSS feeds (324+, 6-layer filter) | rss_monitor.py | weekly | best-covered: rss_feed_health table + feed_health state |
| 17 | Government sources tier-1 (IAAC registry, 13 provincial EA registries, CER) | gov_sources.py | weekly | 35 broad except blocks; per-registry failure = stdout only |
| 18 | IAAC status tracker | iaac_status.py | weekly | except → print, statuses silently not updated |
| 19 | SEDAR+ filings | gov_sources.py / discovery | weekly | print-and-continue |
| 20 | Crown corp + university/institutional capital plans | institutional_capital.py | weekly | print-and-continue |
| 21 | Municipal dev applications (15 CMAs) | municipal_dev_apps.py | weekly | print-and-continue |
| 22 | Lobbyist registries | lobbyist_registries.py | weekly | print-and-continue |
| 23 | Policy tracker (~17 LEGISinfo/Gazette/ministry feeds) | policy_tracker.py | weekly | 3 broad excepts; empty policy_snapshots row, briefing section thin |
| 24 | Job monitor (Job Bank Atom, 15 CMAs × 9 sectors) | job_monitor.py | weekly | except → `[WARN]` print in phases/signals.py:41; no snapshot = silent |
| 25 | Procurement monitor (Open Canada, CanadaBuys CSV, SEAO OCDS, DCC PDF) | procurement_monitor.py | weekly | 16 excepts; dead sources skipped "with logged reasons" (stdout) |
| 26 | Regulatory CanLII feeds (10) | rss_feeds.json regulatory + article_filter.py | weekly | via RSS health (covered by #16) |
| 27 | Corporate newswires (12 feeds) + Google Alerts (~25) + key-people RSS + industry trade RSS | rss_monitor.py categories | weekly | via RSS health (#16) |
| 28 | Corporate newsroom sitemap diffs | corporate_newsroom_diff.py | weekly | print-and-continue |
| 29 | Tavily enrichment | tavily_search.py | weekly, budget-capped | budget tracked; failures print |
| 30 | ON OEA / QC ISQ out-of-band scrapes | tools/refresh_provincial_oea_isq.py | manual/monthly | DEAD (ISQ); series frozen 2025-10-01, nothing flags it |

### Minimum warehouse/monitor schema implied
`connection_runs(connection_id, run_id, started_at, finished_at, status[ok|partial|fail|skipped], items_expected, items_fetched, items_saved, last_error, latest_ref_period)` + per-connection registry with declared cadence and frequency-aware max-dark-age; a deploy-gate check that FAILs when any connection with `severity=critical` is dark beyond 2× cadence, and WARNs on partial. All 30 rows above should write to it from a single helper so "silent vs loud" stops being per-module discretion.
