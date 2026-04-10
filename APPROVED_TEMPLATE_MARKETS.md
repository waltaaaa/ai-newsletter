# Approved Template — Markets Tab

**Approved:** 2026-04-09 (after MKT-01 through MKT-20)
**Status:** Locked. The Markets tab is fully data-refreshed and visually approved.
**Purpose:** Source of truth for the Markets tab layout, data, and editorial rules. Use this file (instead of the full `APPROVED_TEMPLATES.md`) when resuming Markets work to keep context lean.

---

## Lock state (2026-04-09)

- **timeseries.json keys touched:** 41 commodity / FX / equity / index series, 3 diamond series
- **briefing_latest.json blocks touched:** `financialMarkets.indices`, `financialMarkets.fx`, top-level `commodities`, `marketCommentary`, `commodityCommentary`, `financialMarkets.equityNarrative`, `financialMarkets.fxNarrative`, `financialMarkets.commodityNarrative`, top-level `bocRate`
- **Untouched and verified byte-identical:** `financialMarkets.yieldCurve`, `financialMarkets.bocRate`, top-level `yieldCurve`, all 120 + 14 timeseries keys not in the refresh set
- **Page sections:** 5 — Market Commentary, Equity Indices, Foreign Exchange, Government of Canada Yields, Commodities
- **Pill counts:** 9 equity indices, 7 FX pairs
- **Yield curve:** 6 tenors (2Y, 3Y, 5Y, 7Y, 10Y, 30Y)
- **Commodities table:** 43 rows across 9 categories
- **Renderer entry point:** `renderMarkets()` in `docs/js/app.js` (~line 4592)

---

## Page structure (top → bottom)

1. **Market Commentary** — `_buildMktCommentary(fm)` — short factual snapshot paragraph
2. **Equity Indices** — `_buildMktEquities(fm)` — pill grid + range buttons + SVG line chart
3. **Foreign Exchange** — `_buildMktFx(fm)` — pill grid + BoC rate stat + range buttons + SVG line chart
4. **Government of Canada Yields** — `_buildMktYields()` — yield table + 2s10s spread + SVG yield curve
5. **Commodities** — `_buildMktCommodities(fm)` — category tabs + 43-row table with click-to-expand context narratives

Each section is wrapped in a `.section-block` with a `.section-header` containing an accent bar, an `<h3>` title, and a meta line on the right.

---

## 1. Market Commentary

Reads from `fm.summary || fm.commentary || D.marketCommentary || D.market_commentary`. Renders inside a `.narrative` div with `san()` sanitization.

**Editorial format:** 2 short paragraphs, factual numbers only, em-dash lead sentences in `<span class="lead-sentence">`. No banned words. The MKT-11 rebuild produced a snapshot-style commentary (TSX level + WTI + CAD + gold + BoC rate + 2s10s spread). Future pipeline runs should regenerate this from the `tldr-writer-market-commentary` skill once the agent is wired to consume the fresh `financialMarkets` block.

---

## 2. Equity Indices

### Data source
`fm.indices` — array of 9 objects, each: `{name, value, day, mm, yy}`

The renderer maps these into `items[]` with `{name, value, change: it.change || it.day, mm, yy}`.

### Pill structure (locked in MKT-20)
Each pill (`.series-pill`) shows:
- `.pill-name` — index name (13px/600, gray when inactive, Prussian blue when active)
- `.pill-value` — current level (20px/700, tabular-nums)
- `.pill-changes-row` — flex row of three labelled change items:
  - `.pill-chg-item` containing `.pill-chg-label` (small uppercase tag "1W" / "1M" / "1Y") and `.pill-chg-val` (color-coded)
  - Color modifiers: `.up` (`#0d7a3f`), `.down` (`#c4320a`), `.flat` (`#7a8599`)

**No standalone "Year-over-Year" stat row below the pill grid** — that information is now embedded in every pill.

**No narrative paragraph below the chart.** The `equityNarrative` JSON field is preserved for non-frontend consumers (PDF/DOCX) but not rendered.

### Section meta
`"N indices · changes shown 1W / 1M / 1Y"` — explicitly states the column meaning at section level.

### Chart
- SVG line chart rendered by `_mktRenderSvg('equities')` using `_svgTimeseries()`
- Default range: 3 months
- Range buttons: 1M / 3M / 6M / 1Y / 3Y
- Single-select: clicking a pill swaps the chart's data series via `_mktSelectPill()`
- Data source: `_mktTsMap[item.name]` lookup → `loadTimeseries()` → `timeseries.json[<key>]`
- Mapping (in `_mktTsMap` const, ~line 4376):
  - S&P/TSX Composite → `tsx_composite`
  - S&P 500 → `sp500`
  - Dow Jones → `djia`
  - NASDAQ Composite → `nasdaq`
  - FTSE 100 → `ftse100`
  - DAX → `dax`
  - Nikkei 225 → `nikkei225`
  - Shanghai Composite → `idx_shanghai`
  - Hang Seng → `idx_hangseng`

### Indices spec (9 rows)

| Display | tsKey | Yahoo ticker | Currency |
|---|---|---|---|
| S&P/TSX Composite | tsx_composite | ^GSPTSE | CAD |
| S&P 500 | sp500 | ^GSPC | USD |
| Dow Jones | djia | ^DJI | USD |
| NASDAQ Composite | nasdaq | ^IXIC | USD |
| FTSE 100 | ftse100 | ^FTSE | GBP |
| DAX | dax | ^GDAXI | EUR |
| Nikkei 225 | nikkei225 | ^N225 | JPY |
| Shanghai Composite | idx_shanghai | 000001.SS | CNY |
| Hang Seng | idx_hangseng | ^HSI | HKD |

All values are local-currency point levels formatted with comma thousands separators, integer rounding (no decimals).

---

## 3. Foreign Exchange

### Data source
`fm.fx` — array of 7 objects, same `{name, value, day, mm, yy}` shape as indices.

### Pill structure
Same as equities but using `.fx-pill` (smaller, flex:1, text-align:center). The compact override `.fx-pill .pill-chg-*` uses 8px label font and 10px value font so the 1W/1M/1Y triplet fits inside the narrower pill.

### BoC rate stat
A single `.stat-item` block below the pill grid (only when `fm.bocRate` is present): "Bank of Canada Rate" label + value (e.g., `2.25%`). The "Year-over-Year" stat that used to sit next to it was removed in MKT-20.

### Chart
Same SVG mechanism as equities. Single-select pill switching. Range buttons identical.

### FX spec (7 pairs)

| Display | tsKey | Yahoo ticker | Notes |
|---|---|---|---|
| CAD/USD | cadusd | CADUSD=X | Direct (CAD priced in USD) |
| USD/CAD | (derived) | — | `1 / cadusd`, percent-change signs inverted |
| EUR/USD | eurusd | EURUSD=X | Direct |
| GBP/USD | fx_gbpusd | GBPUSD=X | Direct |
| USD/JPY | usdjpy | JPY=X | Direct (USD priced in JPY) |
| USD/CNY | usdcny | CNY=X | Direct (USD priced in CNY) |
| AUD/USD | fx_audusd | AUDUSD=X | Direct |

CAD/USD displays as 4 decimal places (e.g., `0.7236`); USD/JPY as 2 decimals (e.g., `159.09`).

USD/CAD is computed in the inject script as `1 / cadusd_latest_value` and the wk/mm/yy percent changes are sign-inverted. There is no separate Yahoo USD/CAD ticker because Yahoo only publishes one direction and the dashboard wants both for readability.

---

## 4. Government of Canada Yields

### Data source
`D.yieldCurve` (top-level, 6 elements) AND `D.financialMarkets.yieldCurve` (mirror dict with `2Y`, `3Y`, `5Y`, `7Y`, `10Y`, `Long`, `spread_2_10` keys).

**Untouched in the MKT refresh** — preserved byte-identical from the existing pipeline. The yield curve is on a separate refresh cadence (BoC valuation date) and is the responsibility of the existing pipeline.

### Layout
- Yield table: 6 tenor columns × 3 rows (Current, 1 Year Ago, Change in bps)
- Spread row: 2s10s spread with normal/inverted badge + BoC overnight rate on the right
- SVG yield curve chart: current curve (Prussian blue solid) + 1-year-ago curve (red dashed)

### Tenors
2Y (highlighted), 3Y, 5Y, 7Y, 10Y (highlighted), 30Y

---

## 5. Commodities

### Data source
Top-level `D.commodities` array — 43 objects, each:
```json
{
  "name": "WTI Crude",
  "val": "US$98.53/bbl",
  "day": "-11.7%",
  "mm": "+18.1%",
  "yy": "+58.0%",
  "category": "Energy",
  "unit": "bbl",
  "context": "NYMEX WTI front-month futures settlement. Alberta oil sands and Saskatchewan heavy oil exposure."
}
```

### Layout
- **Section meta:** "Click any row for details · 43 commodities"
- **Category tabs** (`.cat-tabs`): All / Energy / Precious Metals / Diamonds / Base Metals / Agriculture / Livestock / Forest Products / Fisheries / Canadian Equity Proxies (9 total + "All")
- **Table:** 5 columns — Commodity (with `.cmd-unit` next to name) | Price | Weekly | M/M | Y/Y
- **Category dividers:** When viewing "All", a `.cmd-group-divider` row separates each category, showing the category name in uppercase
- **Click-to-expand:** Each row has a chevron (`▶ → ▼`) that toggles a `.cmd-expand-row` containing the `context` narrative. `_mktToggleCmdRow()` handles the toggle.
- **Change colors:** `.chg-up` (#0d7a3f), `.chg-down` (#c4320a), `.chg-flat` (#7a8599)

### Category order (locked)
```
Energy → Precious Metals → Diamonds → Base Metals → Agriculture → Livestock → Forest Products → Fisheries → Canadian Equity Proxies
```

The CAT_ORDER array used by the inject scripts in `tmp_mkt_fetch/inject_more.py` and `inject_diamonds.py` is the source of truth for this ordering. Inject scripts use a stable sort on `cat_rank` so within-category insertion order is preserved across rounds.

### 43 commodity rows by category

#### Energy (7)
| Name | tsKey | Source |
|---|---|---|
| WTI Crude | wti | Yahoo CL=F |
| Brent Crude | brent | Yahoo BZ=F |
| Western Canadian Select | (estimated) | WTI − US$13/bbl differential |
| Natural Gas (Henry Hub) | natural_gas | Yahoo NG=F |
| Heating Oil (ULSD) | heating_oil | Yahoo HO=F |
| RBOB Gasoline | gasoline_rbob | Yahoo RB=F |
| BoC Energy Index | boc_energy_index | BoC Valet W.ENER (weekly) |

#### Precious Metals (4)
Gold (gold, GC=F), Silver (silver, SI=F), Platinum (platinum, PL=F), Palladium (palladium, PA=F).

#### Diamonds (1)
| Name | tsKey | Source |
|---|---|---|
| Diamonds (Canadian production) | diamonds_canada_price | StatCan 16-10-0020, vectors 1145997613 (carats shipped) and 1145997965 (value of shipments). Realized C$/ct = value / carats, Canada total. Monthly with ~2-month lag. Weekly column shows `—`. |

#### Base Metals (6)
Copper (copper, HG=F), Aluminum (aluminum, ALI=F), Iron Ore TSI 62% Fe (iron_ore, TIO=F), Uranium Cameco CCJ (cameco_uranium, CCJ), Uranium Sprott URA ETF (sprott_uranium, URA), BoC Metals & Minerals Index (boc_metals_index, W.MTLS — fills the LME nickel/zinc/lead/tin gap).

#### Agriculture (14)
Wheat (wheat, ZW=F), HRW Wheat Kansas (wheat_hrw, KE=F), Oats (oats, ZO=F), Corn (corn, ZC=F), Soybeans (soybeans, ZS=F), Soybean Meal (soybean_meal, ZM=F), Soybean Oil (soybean_oil, ZL=F), Canola (canola, StatCan 32-10-0077 monthly), Sugar #11 (sugar, SB=F), Coffee (coffee, KC=F), Cocoa (cocoa, CC=F), Rough Rice (rice, ZR=F — outlier-cleaned), Cotton (cotton, CT=F), Potash Nutrien NTR (potash_nutrien, NTR).

#### Livestock (4)
Live Cattle (live_cattle, LE=F), Lean Hogs (lean_hogs, HE=F), Feeder Cattle (feeder_cattle, GF=F), Milk Class III (milk_class3, DC=F).

#### Forest Products (2)
Lumber (lumber, LBR=F), BoC Forestry Index (boc_forestry_index, W.FOPR).

#### Fisheries (1)
BoC Fisheries Index (boc_fisheries_index, W.FISH) — only free daily source for Canadian fisheries exposure.

#### Canadian Equity Proxies (4)
Suncor Energy SU (suncor_energy, NYSE:SU), Teck Resources TECK (teck_resources, NYSE:TECK), Barrick Mining ABX.TO (barrick_mining, TSX:ABX), West Fraser Timber WFG (west_fraser, NYSE:WFG).

---

## Display formatting rules

### Pill values
- **Equity indices:** integer point level with comma thousands separators (e.g., `33,478`)
- **FX rates:** 4 decimals for CAD/USD, EUR/USD, GBP/USD, USD/CNY, AUD/USD; 2 decimals for USD/JPY

### Commodity prices
- **USD-denominated commodities:** `US$X.XX/{unit}` (e.g., `US$98.53/bbl`, `US$5.747/lb`)
- **USD-cents commodities (USX currency from Yahoo):** `{value} USc/{unit}` with plain ASCII `USc` prefix (NOT a UTF-8 cent sign — that's the wheat mojibake bug fixed in MKT-07). Tickers: ZW=F, KE=F, ZO=F, ZC=F, ZS=F, ZL=F, SB=F, KC=F, CT=F, GF=F, HE=F, LE=F.
- **CAD-denominated commodities:** `C$X/{unit}` (canola, diamonds, ABX.TO)
- **BoC index series:** `{value} pts` with no currency prefix (W.ENER, W.MTLS, W.FOPR, W.FISH)
- **Equity proxy prices:** `US$X.XX` or `C$X.XX` with no unit suffix

### Change percentages
- Format: `+X.X%` / `-X.X%` (one decimal, signed). Strip any `day` / `M/M` / `W/W` / `YoY` suffix tokens.
- The renderer's `_chgArrow()` prepends `▲ ` for positive and `▼ ` for negative inside the commodity table cells.
- Inside the new pill change row (MKT-20), the arrow is omitted — only the labeled `1W` / `1M` / `1Y` tag appears.
- Empty / null change → display as em dash `—`.

---

## Chart filter behavior (verified working)

`_mktRenderSvg(key)` reads `_mktState[key].range` (months), filters the timeseries by date cutoff, and re-renders the SVG.

`_mktSvgSetRange(btn)` toggles the `.active` class on the clicked range button and calls `_mktRenderSvg(key)`.

`_mktSelectPill(pill)` is single-select — sets `_mktState[key].active = new Set([name])`, swaps `.active` on the pill DOM, and calls `_mktRenderSvg(key)`.

Verified post-MKT-13 with the following point counts on the 9-index, 7-FX setup (data range 5 years):
- equities 1M=22, 3M=62, 6M=124, 1Y=250, 3Y=754
- FX 1M=24, 3M=65, 6M=128, 1Y=257, 3Y=779

If a future pipeline run replaces the 5-year daily data with a different cadence, those counts will change but the pattern (monotonic increase with window) should hold.

---

## Data refresh procedure

The Markets tab is fully data-driven. To refresh, run the canonical fetch + inject pipeline:

1. **`tmp_mkt_fetch/fetch_all.py`** — fetches the original 39-ticker set (9 indices, 7 FX, 4 energy, 4 precious metals, 5 base metals, 9 ag, 2 livestock, 1 lumber, 2 uranium, 1 potash) from Yahoo Finance public chart endpoint. Includes outlier cleaner (MKT-02) for Yahoo decimal-point glitches.
2. **`tmp_mkt_fetch/fetch_more.py`** — fetches the MKT-16 expansion: 10 commodity futures + 4 Canadian equities + 4 BoC Valet weekly indices.
3. **`tmp_mkt_fetch/fetch_diamonds.py`** — fetches StatCan WDS vectors 1145997613 and 1145997965, computes monthly realized C$/ct.
4. **`tmp_mkt_fetch/inject.py`** — injects the 39 base series into `timeseries.json` and rebuilds `briefing_latest.json` indices/fx/commodities.
5. **`tmp_mkt_fetch/inject_more.py`** — injects the 14 new + 2 refreshed series and appends 16 new commodity rows (sorted by CAT_ORDER).
6. **`tmp_mkt_fetch/inject_diamonds.py`** — injects 3 diamond series and appends the Diamonds row in its own category.

All inject scripts perform byte-identical preservation verification on non-touched keys before writing. They write timestamped backups to `docs/data/timeseries.bak_*_pre.json` and `docs/data/briefing_latest.bak_*_pre.json` so the previous state is recoverable.

The yield curve, BoC rate, and any other Markets data not in the touched-key list are not refreshed by these scripts and remain on the existing pipeline cadence.

---

## Renderer files (locked)

| Section | Function | File / line |
|---|---|---|
| Entry point | `renderMarkets()` | `docs/js/app.js` ~4592 |
| Commentary | `_buildMktCommentary(fm)` | ~4612 |
| Equity Indices | `_buildMktEquities(fm)` | ~4620 |
| Foreign Exchange | `_buildMktFx(fm)` | ~4657 |
| Yields | `_buildMktYields()` | ~4695 |
| Commodities | `_buildMktCommodities(fm)` | ~4729 |
| Commodity table | `_buildCmdTable(comms, catFilter)` | ~4754 |
| Category tab handler | `_mktSetCatTab(tab)` | ~4783 |
| Row toggle | `_mktToggleCmdRow(uid)` | ~4777 |
| Chart re-render | `_mktRenderSvg(key)` | ~4558 |
| Range button handler | `_mktSvgSetRange(btn)` | ~4584 |
| Pill click handler | `_mktSelectPill(pill)` | ~4576 |
| SVG line chart | `_svgTimeseries(series, opts)` | ~4511 |
| SVG yield curve | `_svgYieldCurve(yc, ycPrev)` | ~4537 |
| Timeseries key map | `_mktTsMap` const | ~4376 |
| Timeseries loader | `loadTimeseries(docId)` | ~269 |

CSS for the pills, charts, tables, and category tabs lives in `docs/index.html` lines ~1015–1097.

The new MKT-20 classes (`.pill-changes-row`, `.pill-chg-item`, `.pill-chg-label`, `.pill-chg-val`, `.fx-pill .pill-chg-*` overrides) live in the same `#tab-markets` block.

---

## Editorial rules

- **Factual reporting only** per `CLAUDE.md` editorial policy. No banned words: `should`, `must`, `hopefully`, `unfortunately`, `worrying`, `promising`, `encouraging`, `welcome`, `bullish`, `bearish`, `concerning`, `positive` / `negative` (as judgment), `good news` / `bad news`, `optimistic` / `pessimistic`, `troubling` / `reassuring`, `robust`, `significant`, `notably`, `healthy`, `strong` / `weak` (as judgment), `soaring`, `plunging`, `tumbling`, `cratering`, `skyrocketing`.
- **All values must be sourced.** Each commodity row's `context` field cites the futures contract / source explicitly. WCS is the only estimated row and its `context` flags this.
- **Pipeline narrative blocks (`marketCommentary`, `equityNarrative`, `fxNarrative`, `commodityCommentary`) are factual snapshots.** The renderer no longer displays the equity / FX narratives (MKT-20) but the JSON fields remain populated for non-frontend consumers.
- **No new paid services.** Yahoo Finance public chart endpoint, Bank of Canada Valet API, and Statistics Canada WDS API are all free and require no API key.
- **No mojibake.** Prices in cents use plain ASCII `USc` prefix, never the UTF-8 cent sign character.

---

## Known gaps deferred to future tiers

1. **LME physical base metals (Nickel, Zinc, Lead, Tin)** — Yahoo has no free futures feed. Partially closed by the BoC Metals & Minerals Index (W.MTLS) which is a weighted basket of all base metals. Individual daily prices remain unavailable.
2. **Coal (Newcastle), LNG Asia spot** — no free daily source. Partially closed by BoC Energy Index (W.ENER) which includes coal and gas as components. The legacy `coal` and `lng_asia` keys in `timeseries.json` are stale (last 2023, 2015) and should be either refreshed via a pipeline tier that scrapes EIA / IEA monthly data, or removed.
3. **WCS-WTI live differential** — currently a US$13/bbl constant. Could be refreshed weekly from the Alberta Ministry of Energy or the Canada Energy Regulator commodity tracker.
4. **Lumber unit display** — LBR=F (the new 27,500 board feet contract) is labelled `/mbf`. The user may prefer a different display unit if the prior LB=F convention was different.
5. **Fresh narrative regeneration** — the `tldr-writer-market-commentary` agent should be wired to consume the refreshed `financialMarkets` block on the next pipeline run and produce a 150–200-word narrative with project cross-references and source citations. The current `marketCommentary` is a short snapshot, not the full agent-produced narrative.
6. **Diamonds fresh-period gap** — StatCan publishes Table 16-10-0020 with a ~2-month lag. The latest available period will always be 2–3 months behind today's date. The Weekly column for diamonds will always show `—` because the data is monthly, not weekly.

---

## Working artifacts

- `tmp_mkt_fetch/` — fetch scripts, raw responses, cleaned series, summary JSONs, FETCH_REPORT.md, inject reports
- `tmp_mkt_fetch/raw/` — 41 raw Yahoo / BoC / StatCan responses (one per series)
- `tmp_mkt_fetch/series/` — 41 cleaned `[{date, value}]` series files
- `tmp_mkt_fetch/summary.json` — canonical 39-ticker fetch summary (MKT-01)
- `tmp_mkt_fetch/summary_more.json` — 16-ticker expansion summary (MKT-16)
- `tmp_mkt_fetch/diamonds_summary.json` — diamonds row computed metrics (MKT-19)
- `tmp_mkt_fetch/inject_report.json`, `inject_more_report.json` — inject audit trails
- `tmp_mkt_fetch/FETCH_REPORT.md` — full fetch documentation with PASS/FAIL list and known gaps
- Backups (in `docs/data/`):
  - `timeseries.bak_mkt_20260409_194623_pre.json`
  - `briefing_latest.bak_mkt_20260409_194623_pre.json`
  - `timeseries.bak_mkt2_20260409_202239_pre.json`
  - `briefing_latest.bak_mkt2_20260409_202239_pre.json`
  - `timeseries.bak_diam_20260409_204626_pre.json`
  - `briefing_latest.bak_diam_20260409_204626_pre.json`

---

## Patch references

All 20 patches (MKT-01 through MKT-20) documented in `PATCH_LOG.md` under the Markets Tab section. See that file for the per-patch detail of root cause, fix, files changed, and verification steps.
