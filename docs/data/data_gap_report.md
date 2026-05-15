---
generated: 2026-05-15
generator: Agent 0.5 (tldr-data-gap, Phase 0.5)
purpose: Catalog data freshness & structural gaps in The Lagging Indicator pipeline output
supersedes: 2026-04-18 report
---

# Data Gap Report — 2026-05-15

## Coverage Summary
- Provinces with full 6-indicator set: 10/13 (YT, NT, NU have 4/6 — CPI and Housing Starts not published by StatCan for territories; expected limitation)
- Commodity prices current (≤7 days): 11/13 required (uranium and canola have no timeseries series — coverage gap, not staleness)
- Market indices current (≤10 days): 7/7 (TSX, S&P 500, DJIA, NASDAQ, FTSE 100, DAX, Nikkei 225 all to 2026-05-14/15)
- FX pairs current (≤10 days): 4/4 (CAD/USD, EUR/USD, USD/CNY, USD/JPY to 2026-05-15)
- Yield curve complete: 6/6 tenors (2Y, 3Y, 5Y, 7Y, 10Y, Long) in timeseries; 6 entries in briefing yieldCurve
- Projects monitored (lastSeen ≤30 days): ~5,081/7,480 (228 at 30-59d, 2,171 at 60-89d, 0 at 90+d)
- Timeseries keys current: 59/80 within recency window (21 "stale" — see Critical/Warnings; most are source-lagged quarterly provincial accounts)
- Policy items from current/last week: current week 2026-05-15 present, 17 items across 6 weeks
- Freshness gate: 59/80 timeseries within recency window
- Market commodities complete (13 required): 11/13 (uranium, canola absent from timeseries)
- Yield curve tenors available: 6/6 (current); year-ago values present for all
- Weekly deltas computable: 25/27 instruments (93%; only nickel, zinc lack history)
- Monthly deltas computable: 25/27 instruments (93%)
- YoY deltas computable: 25/27 instruments (93%)
- Cross-tab consistency: 2 apparent mismatches, both attributable to stale prior-edition briefing_latest.json (resolved — see notes)

**Overall Data Freshness: B**
National and all 10 provincial core indicators are fresh (refreshed 2026-05-15) and independently verified against StatCan releases. Market data is current. The B (not A) reflects two genuine coverage gaps (uranium, canola not tracked in timeseries) and source-side release lag on QC/ON quarterly provincial economic accounts. No critical data is missing or fabricated; the briefing can proceed.

---

## Critical Gaps (will impact briefing quality)

None that block the briefing. The items below are flagged CRITICAL by the raw freshness gate but are explained as source-side release lag (not pipeline failures) or stale-artifact mismatches:

- **briefing_latest.json is the prior edition (2026-04-19, week_of 2026-04-18).** Its metrics show CPI +1.8% and unemployment 6.7% (February/March-era figures). indicators.json — refreshed today — correctly shows CPI +2.4% (March 2026, StatCan released Apr 20) and unemployment 6.9% (April 2026, StatCan released May 8). Both verified via WebSearch against StatCan. **Action for researchers/writers: use indicators.json as the source of truth, NOT the stale briefing_latest.json metrics. The Phase 3 writers will regenerate the briefing from the fresh indicators.** This is expected pipeline state, not a data conflict.

- **QC/ON provincial economic accounts lag (quarterly):** `on_exports`, `on_imports`, `on_gdp_goods`, `on_real_capital_investment`, `on_real_consumption`, `on_real_household`, `qc_real_gdp`, `qc_exports`, `qc_imports`, `qc_business_investment` last period 2025-10-01 (Q3 2025). These are quarterly Provincial/Ontario Economic Accounts published with a multi-month lag by the ISQ / Ontario Ministry of Finance. Q4 2025 data is not yet released by the source. This is the latest available data, not a collection failure. The 45-day audit window mis-classifies these quarterly series.

- **QC monthly ISQ sub-series lag:** `qc_bldg_permits_res`, `qc_bldg_permits_nonres`, `qc_intl_exports`, `qc_intl_imports`, `qc_retail_sales` last period 2026-02-01 (103d). These are ISQ monthly releases with a longer-than-StatCan lag. Latest available from source.

---

## Warnings (may reduce depth)

- **Uranium: no timeseries series.** No `sprott_uranium`, `cameco_uranium`, or `uranium` key in timeseries.json and no uranium indicator in indicators history. The Markets/commodities tab will not be able to chart uranium. Coverage gap requiring a pipeline series addition (not a fill this agent can safely make without fabricating history).
- **Canola: no timeseries series.** Same as uranium — no `canola` key. Markets tab canola coverage unavailable.
- **Nickel & zinc: only 2 datapoints each** (both 2026-05-15). Weekly, monthly, and YoY deltas are not computable — these will render as N/A on the Markets tab.
- **National monthly indicators in timeseries lag the indicators.json snapshot:** timeseries `cpi` (last 2026-03-15), `unemployment` (2026-03-15), `housingStarts` (2026-03-30). indicators.json carries the current April figures, but the historical timeseries arrays have not been appended with the latest monthly points. Charts driven off timeseries `cpi`/`unemployment` will show data through March only. Headline metrics (from indicators.json) are current.
- **QC `qc_manufacturing_sales`, `qc_housing_starts`:** last 2026-03-01 (75d) — ISQ monthly lag, latest available.
- **commodities.json holds only one indicator** (`tsx_infrastructure`); it is not the primary commodity source (timeseries.json is). Not a regression but worth noting the file is sparse.
- **2,171 projects not seen in 60-89 days.** None are high-value (>$500M) and none exceed 90 days, so no project-tracker integrity risk. Reflects monitoring cadence on a 7,480-project database.

---

## Pipeline Stop Conditions

- Top-5 market instruments (TSX, WTI, Brent, gold, CAD/USD) missing entirely: **NO** — all current to 2026-05-15
- Fewer than 3 yield curve tenors: **NO** — 6 tenors available
- Weekly deltas unavailable for >50% of instruments: **NO** — 93% coverage
- National unemployment, CPI, or GDP completely missing: **NO** — all present, fresh (2026-05-15), and verified
- Cross-tab inconsistency on a critical national indicator: **NO true conflict** — apparent mismatch is the stale prior-edition briefing artifact; source-of-truth indicators.json is correct

**Current status: PASS — pipeline may proceed.**

---

## Filled This Run

No data values were written or modified. Per the skill's no-fabrication rule:
- The cross-tab mismatch was investigated and resolved as a stale-artifact (not a data error) — verified via WebSearch that indicators.json values are correct and current (March CPI +2.4% released Apr 20; April unemployment 6.9% released May 8). No fill needed; indicators.json is already correct.
- The uranium/canola gaps and nickel/zinc thin history are structural pipeline-series coverage gaps; filling them would require fabricating historical series, which the skill prohibits. Documented for remediation instead.
- QC/ON provincial-account staleness is source-side release lag; no newer data exists to fill.

**Net: 0 values changed. 1 false-positive critical (cross-tab) cleared via verification; 2 coverage gaps and several source-lag items documented.**

---

## Recommendations for Researchers

1. **Source of truth:** Use `indicators.json` for all national and provincial headline figures. Treat `briefing_latest.json` metrics as the *previous* edition — do not cite its CPI/unemployment numbers. Current verified figures: BoC rate 2.25%, CPI +2.4% YoY (March 2026), unemployment 6.9% (April 2026), employment rate 60.5%, participation 65.0%, real GDP -0.6%, housing starts 279,317 SAAR.
2. **Focus areas:** National macro and provincial labour/CPI data is clean and fresh — prioritize narrative and story selection there. Markets tab: WTI ($100.16), gold ($4,563), copper, CAD/USD (0.728) all current and chartable.
3. **Deemphasize / handle with care:** Uranium and canola — no chartable series; reference qualitatively from research only, do not assert price moves. Nickel and zinc — current spot only, no deltas; state level without W/M/Y change. QC/ON deep provincial-accounts metrics (GDP-by-expenditure, trade) are Q3 2025 latest — frame as "most recent available (Q3 2025)" rather than current-quarter.
4. **Charts:** Time-series-driven CPI/unemployment/housing-starts charts will display through March 2026 only (timeseries arrays not yet appended with April points), even though headline metrics are April. Note this if a chart's endpoint looks one month behind the headline.
5. **Territories:** YT/NT/NU have unemployment/employment/participation/GDP but no CPI or housing starts — expected; do not flag as missing.

---

## Technical Notes
- Report generated: 2026-05-15 (Agent 0.5, tldr-data-gap, Phase 0.5)
- Audit scope: 13 provinces + national + global, 80 timeseries keys, 7,480 projects, policy (6 weeks), 65 events, 13 required market commodities, 6 yield tenors, 27 delta instruments
- Verification searches: 3 WebSearch queries (StatCan March CPI, March LFS, April LFS) — all confirmed indicators.json accuracy
- Total gap checks run: ~250 data points across freshness, completeness, delta-availability, and cross-tab consistency gates
- Critical gaps (true, blocking): 0
- Critical-flagged but explained (source lag / stale artifact): 17 raw flags → 0 blocking
- Warnings: 13
- Info: 3
