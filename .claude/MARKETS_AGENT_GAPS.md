# Markets Tab — Writing Agent Gaps

The redesigned Markets tab requires narrative commentary that the current pipeline does not produce. This document maps every gap between what the mockup expects and what the agents deliver today.

---

## What Exists Today

### Writing Agents (writing_agents.py)
- 8 macro agents: exec_summary, national, consumer_pulse, watchlist, 4x global regions
- 1 industry summary agent
- 20 sector agents (5 goods + 15 services)
- 1 yield curve data extraction (data only, no narrative)

### Export (export_dashboard.py)
- `financialMarkets.indices` — 7 indices with current value only (no weekly/MoM/YoY change, no commentary)
- `financialMarkets.fx` — 4 pairs with current value only (no weekly/MoM/YoY change, no commentary)
- `commodities` — grouped by category, current value only (no weekly/MoM/YoY change, no commentary, no 52-week range)
- `yieldCurve` — 3 tenors (2Y, 5Y, 10Y) with current value only (no 1-year-ago, no change, no commentary)

### Legacy Code (canadian_markets.py)
- `generate_market_commentary()` — produces a single unified market narrative via Claude, called from `phases/narrative.py`. Not part of the modern writing_agents.py pipeline.

---

## What the Redesign Requires

### 1. Market Commentary (Section 1)
**Field:** `market_commentary`
**Status:** PARTIALLY EXISTS — legacy `generate_market_commentary()` produces this, but it's not wired into writing_agents.py

**Action needed:** Migrate to a dedicated `market_commentary` agent in writing_agents.py. The prompt should receive: equity index data, FX data, yield data, commodity data, project cross-reference counts. Output: 2-paragraph narrative with em dash lead sentences, a callout box with project cross-references, and source list.

### 2. Equity Index Data (Section 2)
**Fields needed per index:** `value`, `weekly_pct`, `ytd_pct`, `yoy_pct`, `high_52w`, `low_52w`
**Status:** MISSING — export only provides current value

**Action needed:**
- In `export_dashboard.py` `_build_market_data()`: query `indicator_history` for weekly/monthly/yearly change calculations, 52-week high/low
- Add `weekly_pct`, `ytd_pct`, `yoy_pct`, `high_52w`, `low_52w` to each index object

### 3. Equity Commentary (Section 2)
**Field:** Per-index `commentary` in each equity object, plus a selected-index narrative
**Status:** MISSING — no agent produces this

**Action needed:** Add a `market_equities` agent to writing_agents.py. Receives: 7 index values + changes, project database counts by sector. Produces: em dash narrative for the default view (TSX), plus a brief note per index. Can be a single agent producing all index commentary in one pass.

### 4. FX Data (Section 3)
**Fields needed per pair:** `value`, `weekly_pct`, `mom_pct`, `yoy_pct`
**Status:** MISSING — export only provides current value

**Action needed:**
- In `export_dashboard.py`: calculate weekly/MoM/YoY changes from `indicator_history`
- Add `weekly_pct`, `mom_pct`, `yoy_pct` to each FX object
- Add `boc_rate` to the FX section data

### 5. FX Commentary (Section 3)
**Field:** `fx_commentary`
**Status:** MISSING — no agent produces this

**Action needed:** Add FX narrative to the `market_commentary` agent (or a separate `market_fx` agent). Receives: 4 FX pairs with changes, BoC rate, trade-exposed project counts. Produces: em dash narrative, 2-3 sentences.

### 6. Yield Data (Section 4)
**Fields needed:** Current yields for 7 tenors (3M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y), 1-year-ago values, basis point changes, 2s10s spread, curve shape (normal/inverted), BoC rate
**Status:** PARTIALLY EXISTS — yield_curve agent extracts current values for 3 tenors only

**Action needed:**
- Expand yield_curve agent to extract all 7 tenors (add 3M, 1Y, 20Y, 30Y)
- Add 1-year-ago values from `indicator_history` (look back ~52 weeks)
- Calculate basis point changes
- Calculate 2s10s spread and classify as normal/inverted
- Store in `indicator_history` during data collection: `goc_3m_yield`, `goc_1y_yield`, `goc_20y_yield`, `goc_30y_yield`

### 7. Yield Commentary (Section 4)
**Field:** `yield_commentary`
**Status:** MISSING — yield_curve agent is data-only

**Action needed:** Either extend the yield_curve agent to also produce a 2-3 sentence narrative, or add it to the `market_commentary` agent. Receives: yield table data, spread, BoC rate, rate-sensitive project counts. Produces: em dash narrative about curve shape and rate environment.

### 8. Commodity Data (Section 5)
**Fields needed per commodity:** `price`, `weekly_pct`, `mom_pct`, `yoy_pct`, `high_52w`, `low_52w`, `avg_1y`, `projects_affected`
**Status:** PARTIALLY EXISTS — export has current value only, no change calculations

**Action needed:**
- In `export_dashboard.py`: calculate weekly/MoM/YoY from `indicator_history`
- Query 52-week high/low and 1-year average from timeseries
- Count `projects_affected` from project database by commodity-to-sector mapping
- Add missing commodities: uranium, nickel, canola, potash (Nutrien proxy NTR.TO), WCS discount
- Restructure commodity categories to match mockup: Energy (4), Precious Metals (2), Base Metals (3), Agriculture (3), Forest Products (1)

### 9. Per-Commodity Commentary (Section 5)
**Field:** `commentary` per commodity object
**Status:** MISSING — no agent produces per-commodity narratives

**Action needed:** Add a `market_commodities` agent to writing_agents.py. This is the largest new writing task. Receives: 13 commodity prices with changes, project cross-reference counts per commodity, recent articles mentioning each commodity. Produces: 1-2 sentence em dash narrative per commodity, plus a 2-3 sentence overall commodity summary.

**Alternative:** Split into 2 agents — `market_commodities_energy` (WTI, Brent, Natural Gas, WCS) and `market_commodities_other` (Gold, Silver, Copper, Uranium, Nickel, Canola, Wheat, Potash, Lumber) to run in parallel.

### 10. Commodity Summary Commentary (Section 5 footer)
**Field:** `commodity_commentary`
**Status:** MISSING

**Action needed:** Include in the `market_commodities` agent output as a top-level summary field.

---

## New Agents Required

| Agent Name | Parallel Group | Input | Output | Words |
|---|---|---|---|---|
| `market_commentary` | Group 3 (Markets) | All market data + project counts | 2 paragraphs + callout + sources | 150-200 |
| `market_equities` | Group 3 (Markets) | 7 indices + changes + project counts | Per-index narrative + TSX detail | 100-150 |
| `market_fx_yields` | Group 3 (Markets) | 4 FX pairs + yield table + BoC rate + project counts | FX narrative + yield narrative | 100-150 |
| `market_commodities` | Group 3 (Markets) | 13 commodities + changes + project counts + articles | Per-commodity narrative + summary | 300-400 |

**Total new writing: ~650-900 words across 4 agents, running in parallel as "Group 3 — Markets"**

---

## Data Collection Additions

### indicator_history (Phase 1)

New indicators to fetch (Bank of Canada / yfinance):

| Indicator | Source | Frequency |
|---|---|---|
| `goc_3m_yield` | Bank of Canada | weekly |
| `goc_1y_yield` | Bank of Canada | weekly |
| `goc_20y_yield` | Bank of Canada | weekly |
| `goc_30y_yield` | Bank of Canada | weekly |
| `uranium` | UxC or Cameco proxy (CCO.TO) | weekly |
| `nickel` | yfinance (LME proxy) | weekly |
| `canola` | yfinance RS=F or ICE | weekly |
| `potash_nutrien` | yfinance NTR.TO | weekly |
| `wcs_discount` | calculated (WTI - WCS) | weekly |

### export_dashboard.py Changes

1. **Change calculation function:** New helper `_calc_changes(conn, indicator_name)` that returns `weekly_pct`, `mom_pct`, `yoy_pct`, `high_52w`, `low_52w`, `avg_1y` from `indicator_history`
2. **Apply to all indices, FX pairs, and commodities**
3. **Expand yield curve:** 3 tenors → 7 tenors, add 1-year-ago lookup
4. **Add project cross-reference counts:** Query project database for affected counts per commodity/sector
5. **Restructure commodity categories** to match mockup grouping (5 categories, 13 items)

### writing_agents.py Changes

1. Add `_build_market_commentary_prompt()` — receives all market data, project counts
2. Add `_build_market_equities_prompt()` — receives index data + changes
3. Add `_build_market_fx_yields_prompt()` — receives FX + yield data
4. Add `_build_market_commodities_prompt()` — receives commodity data + articles
5. In `run_all_writing_agents()`: add 4 new tasks to the tasks dict as "Group 3"
6. In result assembly: merge market agent outputs into briefing JSON

### conductor.py Changes

1. Phase 3 (Writing) already runs agents in parallel — the 4 new market agents join the pool
2. Phase 3.5 (Assembly) needs to merge `market_commentary`, `equity_commentary`, `fx_commentary`, `yield_commentary`, `commodity_commentary` into the final JSON

---

---

## Industries Tab — Agent Output Format Gap

The 20 sector agents in writing_agents.py currently output HTML bullets (`<ul><li>`), but the redesigned Industries tab expandable rows expect narrative prose with em dash lead sentences.

### Current Output
```html
<ul class="list-disc list-inside space-y-2 text-slate-600 text-xs">
  <li>Mining & Energy GDP declined 1.2% month-over-month<sup>1</sup></li>
  <li>WTI crude traded below $70/bbl for the third week<sup>2</sup></li>
</ul>
```

### Required Output
```html
<p><span class="lead-sentence">Mining & Energy GDP declined 1.2% month-over-month</span> — WTI crude traded below $70/bbl for the third consecutive week, affecting 12 Alberta oil sands projects ($18.2B) with breakeven costs above the current price.<sup>1,2</sup></p>
```

### Action Options

**Option A (prompt change):** Update `_build_sector_prompt()` to request narrative prose instead of bullets. Change the format instruction from `<ul><li>` to `<p><span class="lead-sentence">` pattern. This is the cleanest approach — fixes it at the source.

**Option B (post-processing):** Keep bullet output, add a conversion function in the frontend or assembly step that converts bullets to prose. The INDUSTRIES_IMPLEMENTATION_GUIDE.md already documents a `convertBulletsToNarrative()` function for this. More fragile.

**Recommended: Option A** — update the 20 sector prompts to output narrative prose directly.

### Prompt Change (writing_agents.py line 402-403)

Replace:
```
Write sector analysis as HTML bullets (150 words):
Format: <ul class="list-disc list-inside space-y-2 text-slate-600 text-xs"><li>...</li></ul>
```

With:
```
Write sector analysis as narrative prose (150-200 words):
Format: <p><span class="lead-sentence">{key fact}</span> — {supporting detail with data}<sup>N</sup></p>
Use 2-3 paragraphs with em dash lead sentences. Each paragraph should connect an indicator or event to specific project database impacts. No bullet points.
```

### Schema Change

Replace `"analysis": "<ul>...</ul>"` with `"analysis": "<p><span class=\"lead-sentence\">...</span> — ...</p>"` in the output schema.

---

## Implementation Priority

1. **Data first:** Add change calculations to export_dashboard.py (all downstream depends on this)
2. **Yield expansion:** Fetch 4 additional yield tenors + 1-year-ago values
3. **Missing commodities:** Add uranium, nickel, canola, potash, WCS to data collection
4. **Market commentary agent:** Migrate from legacy canadian_markets.py
5. **Commodity commentary agent:** Largest new writing task
6. **Equities + FX/Yields agents:** Smaller, can run in parallel
7. **Assembly wiring:** Connect new outputs to briefing JSON
