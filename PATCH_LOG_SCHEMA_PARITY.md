# Schema Parity Patch Log — Pipeline Output vs Frontend Expectations

**Date:** 2026-04-19
**Context:** Deep audit of double-edition (2026-04-18) revealed 42+ gaps between
pipeline-generated briefing JSON and the demo (gold standard). This document logs
every fix, its root cause, and the long-term prevention mechanism.

---

## Root Cause Summary

The pipeline agents (researchers, analysts, writers, assembler) produce field names
and structures that diverge from what `app.js` reads. The demo was hand-tuned to
match the frontend; the pipeline was never systematically validated against frontend
data paths. Result: silently empty sections, blank columns, broken charts.

**Prevention:** Every pipeline run must pass a **schema validator** that checks the
assembled briefing against the frontend's expected field contract before shipping.
See Section 4 below.

---

## 1. Field Name Mismatches (Pipeline vs Frontend)

These are the most common class of bug. The pipeline uses one name; the frontend
reads a different name. Both are reasonable — they just don't match.

### 1.1 Commodity Names → Timeseries Map

The frontend `_mktTsMap` maps commodity names to timeseries.json keys. Pipeline
writes different names than the map expects.

| Pipeline Name | Frontend Expects | Timeseries Key | Fixed |
|--------------|-----------------|----------------|-------|
| WTI Crude Oil | Crude Oil (WTI) | wti | Yes |
| Brent Crude | Crude Oil (Brent) | brent | Yes |
| Natural Gas (Henry Hub) | Natural Gas | natural_gas | Yes |
| Potash (Nutrien proxy) | Potash (Nutrien) | potash_nutrien | Yes |

**Long-term fix:** Add a `COMMODITY_NAME_MAP` to the assembler skill (or a
post-assembly normalization step) that canonicalizes names to match `_mktTsMap`.

### 1.2 Equity Index Names → Timeseries Map

| Pipeline Name | Frontend Expects | Timeseries Key | Fixed |
|--------------|-----------------|----------------|-------|
| DJIA | Dow Jones | djia | Yes |
| Nasdaq Composite | NASDAQ | nasdaq | Yes |

**Long-term fix:** Same — canonicalize in assembler.

### 1.3 Metrics: camelCase vs snake_case

The frontend reads BOTH forms for some metrics but only ONE form for others.
Pipeline writes camelCase; some frontend paths expect snake_case.

| Pipeline Key | Frontend Also Reads | Fixed |
|-------------|-------------------|-------|
| buildingPermits | building_permits | Yes (alias) |
| housingStarts | housing_starts | Yes (alias) |
| tradeBalance | trade_balance | Yes (alias) |
| employmentChange | employment_change | Yes (alias) |

**Long-term fix:** The assembler should emit BOTH forms, or the frontend should
normalize to one convention on load.

### 1.4 Metrics: Missing `_chg` Keys

The frontend enrichment cards (National tab) read `xxx_chg` for every metric's
change value. The pipeline writes changes into `indicatorMeta[key].change` but
NOT into `metrics[key + '_chg']`.

**19 missing keys:** cpi_chg, housingStarts_chg, tradeBalance_chg,
employmentChange_chg, fulltime_change_chg, parttime_change_chg,
private_sector_change_chg, public_sector_change_chg, core_cpi_median_chg,
shelter_cpi_chg, food_cpi_chg, energy_cpi_chg, building_permits_chg,
residential_permits_chg, nonresidential_permits_chg, merchandise_exports_chg,
merchandise_imports_chg, wti_chg, cadUsd_chg.

**Fixed:** Script derives _chg from indicatorMeta[key].change.

**Long-term fix:** The macro analyst (Agent 2A) or assembler should auto-generate
`_chg` keys from `indicatorMeta`. Add to assembler's merge rules.

### 1.5 Commodity Item Fields

| Pipeline Field | Frontend Reads | Fixed |
|---------------|---------------|-------|
| price | val (primary), price (fallback) | Yes (alias) |
| weekly_pct | day | Yes (alias) |
| mom_pct | mm | Yes (alias) |
| yoy_pct | yy | Yes (alias) |
| commentary | context | Yes (alias) |
| (missing) | unit | Yes (extracted from price string) |

**Long-term fix:** Writer agents should emit the canonical field names the
frontend expects. Update `tldr-writer-markets-triad` SKILL.md to use
`val`, `day`, `mm`, `yy`, `context`, `unit` as primary field names.

### 1.6 Equity/FX Item Fields

Same pattern as commodities:

| Pipeline Field | Frontend Reads | Fixed |
|---------------|---------------|-------|
| weekly_pct | day/change | Yes (alias) |
| ytd_pct | mm | Yes (alias) |
| yoy_pct | yy | Yes (alias) |

**Long-term fix:** Update `tldr-writer-markets-triad` SKILL.md.

---

## 2. Structural Mismatches

### 2.1 yieldCurve: Dict vs List

Pipeline produces `yieldCurve` as a dict with `{tenors, spread_2_10, ...}`.
Frontend expects a list of `{term, yield, prevYield, highlight}`.

**Fixed:** Post-assembly transform converts dict → list.

**Long-term fix:** Update `tldr-writer-markets-triad` to emit the list format
directly. Or add a normalization step in the assembler.

### 2.2 Global Indicators: Non-Standard Keys

Frontend hardcodes 5 indicator keys: `gdp`, `cpi`, `rate`, `unemployment`,
`tradeBalance`. Pipeline analysts used region-specific keys (`fed_funds`,
`hicp`, `ecb_deposit_rate`, `usd_cny`, etc.).

**Fixed:** Post-assembly mapping normalizes to the 5 standard keys.

**Long-term fix:** Update `tldr-analyst-macro` SKILL.md to require these exact
5 keys per global region. Add to the analyst's output schema requirements.

### 2.3 Global indicatorMeta: Missing change/prev

Pipeline's global regions have indicatorMeta with only `period` and `source`.
Frontend reads `change` and `prev` for each indicator.

**Fixed:** Added empty change/prev fields.

**Long-term fix:** Macro researcher/analyst should populate change/prev for
each global indicator (e.g., "US GDP +2.1% → +1.9%").

---

## 3. Missing Data

### 3.1 Industry Insight Charts

The chart agent (Phase 4) only generated national + provincial charts (28 total).
It did NOT generate industry charts (20 needed). All `insightCharts: []`.

**Fixed:** Re-run chart agent for industries.

**Long-term fix:** Update chart agent SKILL.md and conductor validation to
require 28 + 20 = 48 charts minimum. Add industry chart generation to Phase 4.

### 3.2 Commodity Count (13 vs 43)

Pipeline tracked only 13 core commodities. Demo has 43 including livestock,
fisheries, diamonds, Canadian equity proxies (Suncor, Teck, Barrick, etc.).

**Fixed:** Expanded from demo + timeseries.json data.

**Long-term fix:** The data refresh agent (Phase 0) or timeseries export should
maintain the full 43-commodity list. Add the commodity manifest to
`config/commodity_registry.json` and validate against it.

### 3.3 Equity Index Count (4 vs 9)

Pipeline only tracked 4 North American indices. Demo has 9 including FTSE 100,
DAX, Nikkei 225, Shanghai Composite, Hang Seng.

**Fixed:** Expanded from demo + timeseries.json data.

**Long-term fix:** Add global indices to the data refresh agent's scope.
Maintain index list in `config/equity_index_registry.json`.

### 3.4 Province watchlistItems Always Empty

Pipeline generates national-level watchlist but no province-specific events.

**Fixed:** Populated from national watchlist + province-relevant filtering.

**Long-term fix:** Researcher agents should tag events with affected provinces.
Assembler should distribute tagged events to province `watchlistItems[]`.

### 3.5 Province marketContext Missing

Pipeline didn't generate the project pipeline narrative intro per province.

**Fixed:** Extracted first sentence from analysis as fallback.

**Long-term fix:** Provincial writer agent should explicitly produce
`marketContext` as a separate field (2-3 sentence project pipeline summary).

### 3.6 labourDeepDive Not Rendered

Content exists in the data but frontend has no rendering code for it.

**Fixed:** Added rendering section to app.js.

**Long-term fix:** N/A — this was a frontend gap, not a pipeline gap.

---

## 4. Long-Term Prevention: Schema Validator

Create `tools/validate_briefing_schema.py` that checks:

```
REQUIRED_CHECKS:
  - top-level: headline, week_of, id, edition, executive_summary, national,
    provinces(13), goodsIndustries(5), servicesIndustries(15), global(4),
    sources, commodities(>=13), financialMarkets, yieldCurve(list),
    consumer_pulse, watchlist, metrics, indicatorMeta, insightCharts(2)
  - metrics: all _chg keys present
  - metrics: both camelCase and snake_case forms
  - commodities: each has val, day, mm, yy, context, unit, name matches _mktTsMap
  - equities: each has name matching _mktTsMap, day, mm, yy
  - fx: each has day, mm, yy
  - yieldCurve: is a list with {term, yield, prevYield}
  - global: each has gdp, cpi, rate, unemployment, tradeBalance in indicators
  - global: each has indicatorMeta with change, prev for all 5
  - provinces: each has marketContext, watchlistItems, insightCharts(>=1)
  - industries: each has insightCharts(>=1)
  - no commodity name matches raw pipeline names (WTI Crude Oil, etc.)
  - no banned words in any analysis field
```

Run this validator:
1. In the conductor, after Phase 3.5 assembly (before charts)
2. In the conductor, after Phase 4 charts (before audit)
3. As a pre-commit hook on briefing files

---

## 5. Skill File Updates Needed

To prevent these gaps from recurring, update these skill files:

| Skill | Change |
|-------|--------|
| tldr-assembler | Add field name canonicalization step; emit _chg keys; normalize yieldCurve to list format |
| tldr-writer-markets-triad | Use `val`/`day`/`mm`/`yy`/`context`/`unit` as primary field names |
| tldr-writer-market-commentary | Emit `marketCommentary` at top level |
| tldr-analyst-macro | Require exactly `gdp`/`cpi`/`rate`/`unemployment`/`tradeBalance` per global region |
| tldr-analyst-provincial | Generate `marketContext` per province |
| tldr-charts | Add industry chart generation (20 industries, 1 chart each) |
| tldr-conductor | Add schema validation gate after assembly and after charts |
| tldr-conductor | Require 48+ charts (2 national + 26 provincial + 20 industry) |

---

## 6. Frontend JS Changes Made

| Fix | Location | Description |
|-----|----------|-------------|
| Equity commentary | _buildMktEquities ~L4680 | Render per-index commentary div |
| WCS analysis | _buildMktCommodities ~L4820 | Add WCS discount subsection |
| Market callout | _buildMktCommentary ~L4666 | Render pipeline cross-reference card |
| Both province charts | Province render ~L3317 | Loop through all insightCharts, not just [0] |
| labelMap additions | _tldrBuildIndicatorTable ~L486 | Add TRADE BALANCE, BRENT CRUDE |
| labourDeepDive | Province render | Add Labour Market Detail section |
