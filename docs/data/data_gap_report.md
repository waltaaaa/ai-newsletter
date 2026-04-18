---
generated: 2026-04-18
generator: Claude Code parity audit (manual application of tldr-data-gap protocol)
purpose: Catalog data freshness & structural gaps in The Lagging Indicator pipeline output
supersedes: 2026-03-31 report
---

# Data Gap Report — 2026-04-18

## Overall grade: C  →  projected A- after next successful pipeline run

Most freshness gaps trace to a single root cause: no successful end-to-end pipeline run has completed since 2026-04-11 (Phase 5 Conductor crashed on nested `claude -p`). The underlying data sources are healthy. One pipeline rerun resolves most freshness issues.

Frontend parity with demo is verified: `https://waltaaaa.github.io/ai-newsletter/` serves `app.js?v=20260412212116` (commit `437a280`).

---

## Critical (will impact briefing quality)

1. **Market data stale 19–34 days across all core daily series**
   Root cause: pipeline hasn't run. Commodities (WTI, brent, natural_gas, gold, silver, copper, aluminum, platinum, lumber, soybean_oil) latest 2026-03-15 or 2026-03-30. Indices (TSX, S&P 500, DJIA, Nasdaq) same range. FX (CAD/USD, EUR/USD, USD/CNY, USD/JPY) same range.
   → Self-heals on pipeline rerun.

2. **Policy feed empty (`policy.json` items: 0)**
   Root cause: pipeline hasn't run. LEGISinfo, Canada Gazette, and 17 ministry feeds haven't been fetched since stub period.
   → Self-heals on pipeline rerun.

3. **12 validator failures — mostly phantom**
   - 5 phantom failures (copper/global, gold/global, lumber/global, natural_gas/global, wti_oil/global): zero rows in history with province='global'. Validator receives stale input keys.
   - 1 genuine staleness: lumber/national last 2023-05-12 (Yahoo Finance feed broken).
   - 6 in-range values (aluminum, natural_gas, platinum, silver, soybean_oil, wti/national) currently within validator bounds — failures from a prior period's delta check.
   → Self-heals on pipeline rerun, except lumber (needs feed repair).

4. **National employment/participation rates returning N/A**
   Root cause: v2062811 returned employment count, not rate. v2062803 terminated.
   → **FIXED in commit `045558e` (2026-04-18).** Now uses v2062817 (emp rate, 60.6%) and v2062816 (part rate, 64.9%). Verified against StatCan WDS. Will produce values on next pipeline run.

## Warnings (reduce depth but don't break briefing)

5. **briefing.yieldCurve has 3 tenors (2Y, 5Y, 10Y)**
   Only short-core / long-core available. Missing: 3M, 6M, 1Y, 30Y. Data exists in `indicators.json` history as `goc_3y_yield`, `goc_7y_yield`, `goc_long_yield` — could be harvested into yieldCurve but requires export-layer change.
   → Matches demo (not a parity regression). Structural, deferred.

6. **Provincial indicator matrix: data exists but under inconsistent keys**
   Coverage check expected `('ON', 'employment_rate')` etc. Actual storage:
   - QC uses `qc_employment_rate`, `qc_housing_starts`, `qc_participation_rate`, `qc_unemployment_rate` (province-prefixed in indicator_name)
   - Other provinces use `participationRate` (camelCase, no prefix, with `province=ON/AB/...`)
   Mixed convention makes province-level cross-references fragile. Not missing data, just heterogeneous schema.
   → Tech debt, not a freshness gap.

## Structural gaps (matches demo — NOT parity regressions)

These exist in both live and demo. Not blocking the port but worth tracking for future work.

7. **`timeseries.json` scope (35 keys)**
   Contains only commodities (21), indices (7), FX (4), crypto (2), BoC rate (1). **No yield curve tenors, no Canadian-specific commodities (uranium, nickel, canola, potash, iron_ore), no economic indicators (CPI, unemployment, employment_rate).**
   Frontend renders yields from `briefing.yieldCurve` and commodities not in timeseries.json from `briefing.commodities` snapshot. Works, but no history-chart fallback available for these items in Data Explorer.

8. **StatCan Daily feed items (71) have no history**
   `gov_sources.py` scrapes StatCan Daily release and captures `productId` but not `vectorId`. Selecting one of these items in the Data Explorer renders empty chart. Documented as Change #21 caveat. Proper fix requires productId→vectorId mapping layer (`getCubeMetadata` or curated map).

9. **6,615 projects, 2,207 with `lastSeen` 30–60 days old**
   Zero projects at 60+ days. All have evidence URLs (URL hard gate intact — prior audit's "empty evidenceLinks" claim was a false alarm; field is `evidence` not `evidenceLinks`).
   → Expected. Alert tracker should continue to age these.

## Commodities present/missing check (13 required by Markets tab)

| Commodity | timeseries.json | Status |
|---|---|---|
| WTI | ✓ (stale) | Covered, needs refresh |
| Brent | ✓ (stale) | Covered, needs refresh |
| Natural gas | ✓ (stale) | Covered, needs refresh |
| Gold | ✓ (stale) | Covered, needs refresh |
| Silver | ✓ (stale) | Covered, needs refresh |
| Copper | ✓ (stale) | Covered, needs refresh |
| Aluminum | ✓ (stale) | Covered, needs refresh |
| Lumber | ✓ (stale) | Covered, 2023 data — feed broken |
| Uranium (sprott/cameco) | ✗ | Missing from timeseries — render from briefing only |
| Nickel | ✗ | Missing from timeseries |
| Canola | ✗ | Missing from timeseries |
| Potash (nutrien) | ✗ | Missing from timeseries |
| Iron ore | ✗ | Missing from timeseries |

## Yield curve tenor check (7 required for full curve)

| Tenor | briefing.yieldCurve | indicators.json history | timeseries.json |
|---|---|---|---|
| 3M | ✗ | ✗ | ✗ |
| 6M | ✗ | ✗ | ✗ |
| 1Y | ✗ | ✗ | ✗ |
| 2Y | ✓ | ✓ | ✗ |
| 3Y | ✗ | ✓ (goc_3y_yield) | ✗ |
| 5Y | ✓ | ✓ | ✗ |
| 7Y | ✗ | ✓ (goc_7y_yield) | ✗ |
| 10Y | ✓ | ✓ | ✗ |
| 30Y | ✗ | ✗ (goc_long_yield exists, semantics unclear) | ✗ |

Core 2Y/5Y/10Y available — meets skill minimum. Full-curve narrative limited.

## Recommendations

### For the next pipeline run (will resolve items 1–4)

```bash
cd "/c/Users/walte/OneDrive/Desktop/AI newsletter"
# From a standalone shell — NOT nested claude -p
python update_dashboard.py 2>&1 | tee pipeline_20260418.log
```

### For researchers (Agent 1A/1B/1C)

1. **Markets tab narrative:** Be cautious with the 5 commodities (uranium, nickel, canola, potash, iron_ore) not in timeseries — rely on briefing snapshot, no chart history available.
2. **Yield curve narrative:** Can reference short-core (2Y), mid-core (5Y), long-core (10Y). If 3Y/7Y are useful, harvest from `indicators.json` history.
3. **Policy angle:** Currently no policy items. Do a scan-based WebSearch if policy-driven project stories are central to the edition.
4. **Provincial deep-dive caution:** Mixed schema between QC (province-prefixed keys) and other provinces (camelCase keys with separate province field) — verify values appear where you expect when cross-referencing.

### Structural work (deferred, not blocking parity)

- Populate `timeseries.json` with yield-curve tenors and Canadian commodities for full Data Explorer chart support.
- Add productId→vectorId mapping for StatCan Daily feed items (71 indicators gain history).
- Repair lumber feed (Yahoo Finance source broken since 2023-05-12).
- Harmonize provincial indicator key schema.

---

**Port + vector fix commits on origin/main:**
- `437a280` — Demo → live frontend port
- `045558e` — National emp/part rate vectors (v2062811→v2062817, v2062803→v2062816)

**Safety tag:** `backup-pre-port-2026-04-18` (rollback point on origin).
