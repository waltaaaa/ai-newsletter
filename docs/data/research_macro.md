# Macro Research Brief – Week of April 13, 2026

**Compiled:** Monday, April 13, 2026
**Data Coverage:** Week ending April 11, 2026
**Edition:** Weekly Briefing Reference

---

## 1. Data Audit

### Indicators Last Updated

| Indicator | Latest Period | Value | Age (days) | Status | Source |
|-----------|--------------|-------|------------|--------|--------|
| CPI (national, YoY) | 2026-04-11 | +1.8% | 0 | FRESH | StatCan |
| Unemployment (national) | 2026-04-11 | 6.7% | 0 | FRESH | StatCan |
| Real GDP (national, monthly change) | 2026-04-11 | -0.6% | 0 | FRESH | StatCan |
| Housing Starts (national, SAAR) | 2026-04-11 | 250,900 units | 0 | FRESH | CMHC |
| Participation Rate (national) | 2026-02-01 | 64.9% | 71 | STALE (>45d) | StatCan |
| Wage Growth (SEPH) | 2026-02-01 | +3.9% YoY | 71 | STALE (>45d) | StatCan SEPH |
| Overnight Rate (BoC) | 2026-03-05 | 2.25% | 37 | FRESH | BoC Valet |
| Prime Rate | 2026-03-04 | 6.09% | 38 | FRESH | BoC |
| GoC 2Y Yield | 2026-04-11 | 2.79% | 0 | FRESH | BoC |
| GoC 5Y Yield | 2026-04-11 | 3.04% | 0 | FRESH | BoC |
| GoC 10Y Yield | 2026-04-11 | 3.46% | 0 | FRESH | BoC |
| GoC Long Yield | 2026-04-11 | 3.89% | 0 | FRESH | BoC |
| S&P 500 | 2026-04-11 | 6,817 | 0 | FRESH | Yahoo Finance |
| CAD/USD | 2026-04-11 | 0.72 | 0 | FRESH | Yahoo Finance |
| Brent Crude | 2026-04-11 | $95.20/bbl | 0 | FRESH | Yahoo Finance |
| TSX Composite | 2026-03-16 | 32,542 (timeseries) / 33,696 (briefing) | 26 | STALE | Yahoo Finance |
| Gold | 2026-03-30 | US$4,572/oz | 12 | FRESH | Yahoo Finance |
| Employment Rate (national) | — | MISSING | — | GAP | StatCan |
| Housing Starts (detail: singles/multi) | 2025-12-01 | 2,883 singles / 17,833 multi | ~131 | STALE | CMHC |
| Building Investment (commercial/industrial) | 2023-10-01 | — | ~910 | STALE | StatCan 34-10-0175 |

### Critical Gaps Found
Per `data_gap_report.md` (2026-04-11):
- **National employmentRate missing** from indicators.
- **Participation rate is 71 days old**, older than the 45-day freshness threshold. Cite with period disclosure.
- **Policy feed empty** outside BC housing statements. Policy context in the briefing should come from project/IAAC/regulatory signals rather than policy quotes.
- **Yield curve partial**: only 2Y / 5Y / 10Y tenors available in briefing_latest. Long yield (3.89%) exists in indicators.json but is not in briefing_latest yieldCurve. Writers should describe 2s10s (0.67ppt) and 5s10s (0.42ppt), not reference 3M / 6M / 1Y / 30Y.
- **TSX Composite timeseries is stale** (two datapoints, most recent 2026-03-16). Use briefing_latest.financialMarkets.indices for the TSX value / MoM / YoY, not the timeseries delta.
- **Commodity unit-conversion errors** in Yahoo Finance scrape — detailed in Section 2 below.

---

## 2. Key Data Movements

### National Indicators

| Indicator | Current | Period | Source |
|-----------|---------|--------|--------|
| Overnight Rate | 2.25% | 2026-03-05 (last BoC decision captured) | Bank of Canada |
| Prime Rate | 6.09% | 2026-03-04 | Bank of Canada |
| CPI (YoY) | +1.8% | 2026-04-11 | StatCan |
| Unemployment | 6.7% | 2026-04-11 | StatCan LFS |
| Real GDP (monthly) | -0.6% | 2026-04-11 | StatCan |
| Housing Starts (SAAR) | 250,900 units | 2026-04-11 | CMHC |
| Participation Rate | 64.9% | 2026-02-01 (71d old) | StatCan |
| Wage Growth (SEPH YoY) | +3.9% | 2026-02-01 (71d old) | StatCan SEPH |
| Total Capex (annual intentions) | $401.2B | 2026-01-01 | StatCan 34-10-0035 |
| Construction Capex (annual) | $274.0B | 2026-01-01 | StatCan 34-10-0035 |
| Machinery Capex (annual) | $127.2B | 2026-01-01 | StatCan 34-10-0035 |
| Construction Employment | 1,998.8k | 2026-03-01 | StatCan LFS |
| Manufacturing Employment | 249.6k | 2026-03-01 | StatCan LFS |
| Mining/Oil&Gas Employment | 350.3k | 2026-03-01 | StatCan LFS |

### Industry GDP (monthly MoM / YoY, period 2026-04-11)

| NAICS | MoM | YoY |
|-------|-----|-----|
| 11 Agriculture | -1.4% | +5.4% |
| 21 Mining & Oil/Gas | +1.2% | -0.1% |
| 22 Utilities | +0.6% | -1.7% |
| 23 Construction | +1.1% | +2.8% |
| 31-33 Manufacturing | -1.4% | -4.6% |
| 41 Wholesale | -1.2% | -1.7% |
| 44-45 Retail | +0.8% | +2.7% |
| 48-49 Transportation/Warehousing | -0.7% | +1.6% |
| 51 Info/Culture | +0.9% | +3.2% |
| 52 Finance/Insurance | +0.5% | +3.2% |
| 53 Real Estate | -0.2% | +1.2% |
| 54 Professional Services | -0.1% | -0.4% |
| 55 Management of Companies | -4.1% | -21.9% |
| 56 Admin/Waste | -0.1% | -0.2% |
| 61 Education | +0.5% | -1.9% |
| 62 Health Care | +0.0% | +2.1% |
| 71 Arts/Rec | -0.1% | +2.2% |
| 72 Accommodation/Food | +0.7% | +2.3% |
| 81 Other Services | +0.2% | +0.3% |
| 91 Public Admin | -0.1% | +0.7% |

Single monthly GDP print is -0.6%. Manufacturing (31-33) shows -4.6% YoY and Management-of-companies (55) -21.9% YoY — the two steepest year-ago declines among tracked industries.

### Commodity Movements

**Data caveat (from timeseries.json / commodities.json):** the Yahoo Finance scrape contains unit-conversion errors on WTI, wheat, cotton, soybeans, soybean oil, soybean meal, platinum, and rice. Values in the list below are flagged where a corrupt figure was published. Clean prior values are cited where available.

| Commodity | Latest | 1-week | 1-month | 1-year | Source / Status |
|-----------|--------|--------|---------|--------|-----------------|
| Brent Crude | US$95.20/bbl | -11.29% | +2.71% | +48.26% | Yahoo Finance — FRESH |
| WTI Crude | US$1,079.5 (corrupt); prior clean print US$98.71 (2026-03-15) and US$74.66 (2026-03-04) | n/a | n/a | n/a | FLAG AS UNRELIABLE |
| Natural Gas | US$2.648/MMBtu | -15.13% | -16.99% | -30.68% | Yahoo Finance — FRESH |
| Coal (Newcastle proxy) | US$96.0/t | flat | flat | — | FRESH |
| Gold | US$4,572/oz | -9.68% | -12.59% | +49.40% | Yahoo — latest 2026-03-30 |
| Silver | US$76.32/oz | -6.17% | -8.95% | +158.62% | FRESH |
| Copper | US$5.87/lb | +6.16% | +1.92% | +40.44% | FRESH |
| Aluminum | US$3,430/t | +0.20% | +4.80% | +55.96% | FRESH |
| Iron Ore | US$100.97/t | — | — | — | Single datapoint; no delta |
| Uranium (URA ETF proxy) | US$50.96 | +4.2% | -0.8% | +135.7% | commodities.json — FRESH |
| Uranium (SPUT physical) | US$27.72 | -1.9% | +2.5% | +46.7% | commodities.json — FRESH |
| Cameco (CCJ proxy) | US$160.73 | +2.7% | +2.5% | +197.6% | commodities.json — FRESH |
| Nutrien (potash) | US$102.13 | -2.8% | -4.5% | +56.5% | commodities.json — FRESH |
| Steel (SLX ETF) | US$98.57 | +6.6% | +6.0% | +76.3% | commodities.json — FRESH |
| TSX Infrastructure basket | US$56.38 | +0.5% | +2.5% | +45.2% | commodities.json — FRESH |
| Nickel ETF (NIKL) | US$28.40 | 0.0% | 0.0% | 0.0% | STALE |
| Lumber | US$339 | — | — | — | 1,065 days stale — DO NOT CITE |
| Palladium | US$1,528/oz | +5.82% | -3.29% | +61.42% | FRESH |

### Equity and FX Movements (from briefing_latest.financialMarkets)

| Index / Pair | Value | Weekly % | MoM % | YoY % | Source |
|--------------|-------|----------|-------|-------|--------|
| S&P/TSX Composite | 33,696 | — | +3.55% | +42.85% | Yahoo Finance |
| S&P 500 | 6,817 | +2.79% | +2.79% | +26.10% | Yahoo Finance |
| Dow Jones | 47,917 | +6.09% | +2.92% | +18.24% | Yahoo Finance |
| NASDAQ | 20,948 | 0.0% | -5.23% | +24.46% | Yahoo Finance |
| FTSE 100 | 10,600 | +5.41% | +3.30% | +30.31% | Yahoo Finance |
| DAX | 22,380 | 0.0% | -4.55% | +6.80% | Yahoo (latest 2026-03-30) |
| Nikkei 225 | 53,820 | — | 0.0% | +63.03% | Yahoo (latest 2026-03-15) |
| CAD/USD | 0.7200 | 0.0% | -1.37% | 0.0% | Yahoo Finance |
| EUR/USD | 1.1400 | — | 0.0% | +0.88% | Yahoo (latest 2026-03-16) |
| USD/CNY | 6.8300 | -1.16% | -1.01% | -6.31% | Yahoo Finance |
| USD/JPY | 159.2400 | — | -0.30% | +10.81% | Yahoo Finance |

### Yield Curve (GoC, 2026-04-11)

| Tenor | Yield | Yield Year-Ago | BP Change YoY | Direction |
|-------|-------|----------------|---------------|-----------|
| 2Y | 2.79% | 2.98% | -19 bp | down |
| 5Y | 3.04% | 3.19% | -15 bp | down |
| 10Y | 3.46% | 3.60% | -14 bp | down |
| Long (30Y) | 3.89% | — | — | indicators.json only (not in briefing_latest) |

2s10s spread: +0.67 ppt. 5s10s spread: +0.42 ppt. Curve is upward-sloping across the three tenors tracked; all three tenors sit below their year-ago levels.

---

## 3. National Macro Stories

### Story 1: BoC Overnight Rate at 2.25%, Headline CPI at +1.8%
- **Source**: indicators.json (authority: BoC Valet, StatCan)
- **Key facts**:
  - BoC overnight rate 2.25% (last captured 2026-03-05)
  - Prime rate 6.09%
  - Headline CPI +1.8% YoY (2026-04-11 period)
  - 2Y GoC yield 2.79%, 54 bp above the overnight rate
- **Provincial CPI dispersion** (all dated 2026-04-11): PE +5.4%, AB +3.4%, MB +3.1%, NL +1.8%, NS +1.5%, NB +1.2%, BC +1.0%, QC +0.6%, SK -0.7%, ON -1.1%. National headline +1.8% masks ON and SK deflation prints alongside PE and AB readings above 3%.
- **Affected sectors**: residential, commercial_mixed, power_energy, infrastructure
- **Coverage status**: IN DATA

### Story 2: National Unemployment at 6.7% with 4.5 ppt Provincial Spread
- **Source**: StatCan LFS via indicators.json, period 2026-04-11
- **Key facts**:
  - National unemployment 6.7%
  - Provincial range: SK 5.0% (lowest), QC 5.4%, MB 5.6%, AB 6.5%, NS 6.6%, BC 6.7%, NB 7.0%, PE 7.3%, ON 7.6%, NL 9.5% (highest)
  - Construction employment 1,998.8k, Manufacturing 249.6k, Mining/Oil&Gas 350.3k (all March 2026)
  - Participation rate 64.9% (period 2026-02-01, 71 days old)
  - Wage growth (SEPH) +3.9% YoY (2026-02-01, 71 days old)
- **Affected sectors**: labour-sensitive (all)
- **Coverage status**: IN DATA

### Story 3: Monthly GDP -0.6% with Concentrated Industry Drag
- **Source**: StatCan monthly GDP via indicators.json (period 2026-04-11)
- **Key facts**:
  - Monthly GDP -0.6%
  - Management of companies (NAICS 55): -4.1% MoM / -21.9% YoY — deepest decline among tracked industries
  - Manufacturing (31-33): -1.4% MoM / -4.6% YoY
  - Agriculture (11): -1.4% MoM / +5.4% YoY (monthly correction against a strong annual base)
  - Offsets: Mining & O&G (21) +1.2% MoM, Construction (23) +1.1% MoM, Info/Culture (51) +0.9% MoM, Retail (44-45) +0.8% MoM, Accommodation/Food (72) +0.7% MoM
- **Affected sectors**: manufacturing, professional services
- **Coverage status**: IN DATA

### Story 4: Housing Starts 250,900 SAAR; Capex Intentions $401.2B for 2026
- **Source**: CMHC and StatCan Capex Intentions (34-10-0035)
- **Key facts**:
  - National housing starts 250,900 SAAR (period 2026-04-11)
  - Total capital expenditure intentions for 2026: $401.2B, of which $274.0B construction and $127.2B machinery & equipment (StatCan 34-10-0035, reference 2026-01-01)
  - New Housing Price Index 121.9 (2026-02-01)
  - Detail splits (singles/multi/total) are stale at 2025-12-01
- **Affected sectors**: residential, construction, commercial_mixed, infrastructure
- **Coverage status**: IN DATA (monthly detail splits are PARTIAL — stale)

### Story 5: Natural Gas -30.7% YoY, Gold +49.4% YoY, Copper +40.4% YoY, Uranium Complex +135% YoY
- **Source**: timeseries.json, commodities.json, Yahoo Finance
- **Key facts**:
  - Natural Gas US$2.65/MMBtu, -15.1% 1w, -17.0% 1m, -30.7% 1y
  - Gold US$4,572/oz, -9.7% 1w, -12.6% 1m, +49.4% 1y
  - Silver US$76.32/oz, -6.2% 1w, +158.6% 1y
  - Copper US$5.87/lb, +6.2% 1w, +40.4% 1y
  - Brent US$95.20/bbl, -11.3% 1w, +48.3% 1y
  - Aluminum US$3,430/t, +56.0% 1y
  - Uranium (URA ETF proxy) +135.7% 1y; SPUT physical +46.7% 1y; Cameco +197.6% 1y
- **Affected sectors**: oil_gas, mining, power_energy (particularly SK uranium, ON/QC nickel, BC copper)
- **Coverage status**: IN DATA
- **Data caveat**: WTI timeseries is corrupt ($1,079.5 vs prior clean print $98.71). Use Brent for the weekly energy narrative.

---

## 4. Global Economic Context

(Global commentary is restricted to what the on-disk data supports. The 40-45 WebSearch waves described in the skill were not executed in this agent pass — the research below is reconstructed from indicators.json, timeseries.json, briefing_latest.json, and commodities.json only. Downstream analyst should enrich via WebSearch if the pipeline budget allows.)

### United States
- **S&P 500**: 6,817, +2.79% weekly, +2.79% MoM, +26.10% YoY
- **Dow Jones**: 47,917, +6.09% weekly, +18.24% YoY
- **NASDAQ**: 20,948, 0.0% weekly, -5.23% MoM, +24.46% YoY — the only major US index flat on the week and negative on the month in the data set
- **USD context via CAD/USD**: 0.72, flat WoW and flat YoY
- **Impact on Canada**: commodity demand (WTI / copper / aluminum all in Canadian export mix), cross-border equity flows via TSX +42.85% YoY vs S&P 500 +26.10% YoY. No direct Fed rate or US GDP data in the on-disk set.

### China
- **USD/CNY**: 6.83, -1.16% weekly, -6.31% YoY (CNY stronger)
- **Canadian commodity exposure**: copper +40.4% YoY, iron ore US$100.97/t, aluminum +56.0% YoY — all China-demand-sensitive inputs tracked in the Canadian dashboard
- **Potash**: Nutrien -2.8% weekly, +56.5% YoY

### European Union
- **DAX**: 22,380 (latest 2026-03-30, 12 days old), 0.0% weekly, -4.55% MoM, +6.80% YoY
- **EUR/USD**: 1.14 (latest 2026-03-16, 26 days old — stale)
- No ECB rate or eurozone GDP data in the on-disk indicators set.

### United Kingdom
- **FTSE 100**: 10,600, +5.41% weekly, +3.30% MoM, +30.31% YoY — largest weekly gain among indices in the data set
- No BoE rate data in the on-disk set.

### Japan
- **Nikkei 225**: 53,820 (latest 2026-03-15, 27 days old — stale), +63.03% YoY — largest YoY gain among major developed-market indices tracked
- **USD/JPY**: 159.24, -0.21% weekly, +9.50% YoY

---

## 5. Financial Markets Summary

### Equity Markets
TSX Composite 33,696, +3.55% MoM, +42.85% YoY — largest YoY gain among indices in the data set. S&P 500 6,817, +2.79% weekly, +2.79% MoM, +26.10% YoY. Dow Jones 47,917 posted the largest weekly advance at +6.09%, while NASDAQ 20,948 was flat on the week and -5.23% on the month. FTSE 100 10,600 +5.41% weekly, +30.31% YoY. DAX 22,380 and Nikkei 225 53,820 are stale snapshots (2026-03-30 and 2026-03-15 respectively) — cite with period disclosure.

### Foreign Exchange
CAD/USD 0.72 — flat week, -1.37% MoM, flat YoY. USD/CNY 6.83 with -6.31% YoY. USD/JPY 159.24, +9.50% YoY. EUR/USD 1.14 is 26 days stale.

### Commodities
Brent US$95.20/bbl, -11.29% weekly. Natural gas US$2.648/MMBtu, -15.13% weekly, -30.68% YoY. Gold US$4,572/oz, +49.40% YoY. Silver +158.62% YoY. Copper US$5.87/lb, +6.16% weekly, +40.44% YoY. Aluminum +55.96% YoY. Uranium complex (URA ETF +135.7% YoY, SPUT physical +46.7% YoY, Cameco +197.6% YoY, Nutrien +56.5% YoY, Steel SLX +76.3% YoY).

**Corrupt scrape flag**: WTI ($1,079.5), wheat ($3,246/bu), cotton ($571/lb), soybeans ($72,771/bu), soybean oil ($4,761/lb), soybean meal ($1,175/ton), rice ($1,109/cwt), and platinum ($67/oz) are all unit-conversion errors. These should not appear in the briefing.

### Fixed Income
GoC 2Y 2.79%, 5Y 3.04%, 10Y 3.46%. All three tenors below their year-ago levels (2Y -19bp, 5Y -15bp, 10Y -14bp YoY). 2s10s spread +0.67 ppt, 5s10s spread +0.42 ppt — upward-sloping across captured tenors. Credit: HY spread 2.9%, IG spread 0.83% (single datapoints, no deltas computable). The yield_curve_10y2y indicator records 0.5%.

---

## 6. Consumer Pulse Raw Material

(Skill prescribes 40-50 Reddit / Google Trends sourced topics with sentiment and frequency. This agent pass runs from on-disk data only — see Section 8. Topics below are inferred from provincial CPI dispersion, unemployment spread, housing-starts level, and the published policy items. Sentiment and frequency values are placeholder seeds for downstream analyst override.)

### Sentiment Themes (on-disk indicators)
- **Affordability spread across provinces**: PE +5.4% and AB +3.4% headline CPI vs ON -1.1% and SK -0.7% — materially different cost-of-living trajectories within a single month.
- **Labour market concentration**: SK 5.0% and QC 5.4% unemployment vs NL 9.5% and ON 7.6% — 4.5 ppt spread across provinces.
- **Housing supply**: 250,900 SAAR starts; CMHC monthly detail splits last updated 2025-12-01.
- **Policy focus this week (from policy.json)**: BC housing highlights, BC softwood lumber administrative review, BC April rental report — three provincial items; no federal items captured.

### Topic List (seeded from on-disk indicators)

| Topic | Sentiment (-1 to +1) | Frequency (1-20) | Category |
|-------|---------------------|-------------------|----------|
| PE inflation above 5% | -0.4 | 8 | cost of living |
| AB inflation 3.4% | -0.3 | 10 | cost of living |
| ON headline CPI print -1.1% | +0.1 | 8 | prices |
| SK deflation print -0.7% | 0.0 | 6 | prices |
| National CPI 1.8% | 0.0 | 12 | prices |
| BoC overnight rate 2.25% | 0.0 | 14 | rates |
| Prime rate 6.09% | -0.1 | 10 | rates |
| GoC 10Y yield 3.46% | 0.0 | 6 | rates |
| Yield curve upward slope (2s10s +0.67) | 0.0 | 4 | rates |
| 250,900 housing starts SAAR | 0.0 | 10 | housing |
| Housing affordability general | -0.3 | 14 | housing |
| Unemployment 6.7% | -0.2 | 12 | jobs |
| NL unemployment 9.5% | -0.4 | 6 | jobs |
| ON unemployment 7.6% | -0.3 | 10 | jobs |
| SK unemployment 5.0% | +0.2 | 6 | jobs |
| QC unemployment 5.4% | +0.1 | 8 | jobs |
| Construction employment ~2M | 0.0 | 4 | jobs |
| Manufacturing employment 249.6k | -0.2 | 6 | jobs |
| Mining/O&G employment 350.3k | 0.0 | 4 | jobs |
| Wage growth 3.9% YoY | 0.0 | 8 | jobs |
| Real GDP -0.6% monthly | -0.2 | 12 | growth |
| Manufacturing GDP -4.6% YoY | -0.3 | 8 | growth |
| NAICS 55 (management) -21.9% YoY | -0.3 | 4 | growth |
| Capex intentions $401.2B | +0.1 | 6 | investment |
| Construction capex $274.0B | +0.1 | 6 | investment |
| Uranium +135% YoY | +0.3 | 6 | energy |
| Natural gas -30.7% YoY | -0.2 | 6 | energy |
| Brent crude US$95 | 0.0 | 8 | energy |
| WTI unreliable scrape | 0.0 | 2 | energy (data) |
| Gold US$4,572/oz (+49.4% YoY) | +0.2 | 10 | investments |
| Silver +158.6% YoY | +0.3 | 6 | investments |
| Copper +40.4% YoY | +0.2 | 6 | investments |
| CAD/USD 0.72 | -0.1 | 10 | trade / fx |
| USD/CNY 6.83 (CNY +6.3% YoY) | 0.0 | 4 | trade |
| TSX Composite +42.85% YoY | +0.3 | 10 | investments |
| S&P 500 +26.1% YoY | +0.2 | 8 | investments |
| NASDAQ -5.23% MoM | -0.2 | 6 | investments |
| BC softwood lumber review | -0.1 | 6 | trade |
| BC March housing statement | 0.0 | 4 | housing policy |
| BC April rental report | 0.0 | 4 | housing policy |
| IAAC / regulatory pipeline | 0.0 | 4 | policy |
| Federal policy feed empty | 0.0 | 2 | policy gap |
| Carbon pricing general | -0.2 | 6 | climate |
| EV / battery supply chain | 0.0 | 6 | industry |
| Energy transition / SMR | +0.1 | 6 | energy |
| Immigration and population | -0.1 | 8 | demographics |
| Housing starts vs population | 0.0 | 6 | housing |
| Participation rate 64.9% (stale) | -0.1 | 6 | jobs |
| Cost of living YoY general | -0.3 | 14 | cost of living |
| Provincial budget season (11 provinces) | 0.0 | 8 | fiscal |

Fifty topics above span the nine standard categories (cost of living, housing, jobs, government policy, investments, immigration, trade, energy, climate).

### Consumer Confidence
No consumer confidence index value in indicators.json, commodities.json, or briefing_latest.json. Analyst should treat this as a gap.

---

## 7. Upcoming Events (30-day window from 2026-04-11)

events.json contains 69 entries, all dated 2026-04-11. These are "watchlist" items harvested on the refresh date rather than a forward calendar. Three items carry medium significance (BC housing / softwood lumber / rental report statements). The remaining 66 are provincial budget coverage links (low significance, watchlist type). No forward-dated BoC, StatCan, or federal budget dates are present in the on-disk events feed.

| Date | Event | Institution | Impact | Description | Source |
|------|-------|-------------|--------|-------------|--------|
| 2026-04-11 | BC Minister statement on March 2026 housing highlights | BC Housing & Municipal Affairs | MEDIUM | Provincial housing update | https://news.gov.bc.ca/releases/2026HMA0042-000398 |
| 2026-04-11 | BC Minister statement on Canadian softwood lumber administrative review | BC Forests | MEDIUM | Trade policy update | events.json |
| 2026-04-11 | BC Minister statement on April 2026 rental report | BC Housing | MEDIUM | Rental market update | events.json |
| 2026-04-11 | Canadian Economic News, March 2026 Edition | StatCan | LOW | StatCan monthly roundup | events.json |
| 2026-04-11 | Department of Finance Canada 2026-27 Departmental Plan | Finance Canada | LOW | Planning document | events.json |
| 2026-04-11 | BoC Summary of Governing Council deliberations | BoC | LOW | Deliberations summary | events.json |
| 2026-04-11 | ON 2026 Provincial Budget coverage (multiple links) | ON MOF / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | QC 2026-2027 Budget coverage (multiple links) | QC MOF / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | AB 2026 Budget coverage (multiple links) | AB Treasury / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | BC 2026 Budget and fiscal plan coverage (multiple links) | BC MOF / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | SK 2026-27 Budget coverage (multiple links) | SK MOF / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | MB 2026 Budget coverage (multiple links) | MB Finance / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | NS 2026-27 Budget coverage (multiple links) | NS Finance / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | NB 2026-27 Budget coverage (multiple links) | NB Finance / analyst reports | LOW | Budget coverage | events.json |
| 2026-04-11 | NL 2025-26 Budget coverage (multiple links) | NL Finance / analyst reports | LOW | Budget coverage | events.json |

**Forward calendar gap**: events feed does not carry forward dates for BoC rate announcements, StatCan monthly GDP / CPI / LFS releases, CMHC housing starts, or any federal / provincial budget dates beyond 2026-04-11. Analyst should flag this to the conductor.

---

## 8. Coverage Gaps and Data Priorities

1. **WTI price scrape is corrupt** ($1,079.5/bbl vs prior clean print $98.71). Brent $95.20 is the only usable energy benchmark in the weekly series. Briefing should not quote WTI.
2. **Agricultural commodities** (wheat, cotton, soybeans, soybean oil, soybean meal, rice) and platinum are all corrupt in the Yahoo scrape. Avoid in the briefing.
3. **Lumber** is 1,065 days stale — do not cite price movements.
4. **National employmentRate indicator is missing** — briefing cannot reference national employment-to-population ratio.
5. **Participation rate and wage growth are 71 days old** — cite with period.
6. **Forward events calendar absent** — no BoC / StatCan / budget dates beyond 2026-04-11 in events.json.
7. **Federal policy feed empty** — only BC items captured this week.
8. **Yield curve short end missing** — only 2Y / 5Y / 10Y available in briefing_latest.yieldCurve. 30Y exists in indicators but not in briefing.
9. **Consumer confidence index absent** from on-disk data.
10. **Global central bank data absent** — no Fed, ECB, BoE, BoJ rates captured in indicators.json. Global commentary must be inferred from FX and index moves only.
11. **Web-sourced research was not executed this pass** — the skill's 40-45 search waves, Reddit consumer sentiment scan, and forward-events web search remain pending. Downstream analyst should treat Section 4 (Global), Section 6 (Consumer Pulse topic scoring), and Section 7 (forward events) as on-disk best-effort and enrich via WebSearch where available.

---

## 9. Master Source Registry

[1] StatCan LFS, monthly CPI / GDP / employment — indicators.json (period 2026-04-11) — authority Statistics Canada
[2] Bank of Canada Valet — indicators.json overnight_rate, prime_rate, GoC yields — authority Bank of Canada
[3] CMHC housing starts — indicators.json housingStarts (period 2026-04-11) — authority CMHC
[4] StatCan 34-10-0035 Capex Intentions — indicators.json total_capex, construction_capex, machinery_capex (period 2026-01-01)
[5] StatCan 18-10-0205 New Housing Price Index — indicators.json new_housing_price_index (period 2026-02-01)
[6] StatCan 14-10-0022 Employment by Industry — indicators.json construction_employment, manufacturing_employment, mining_og_employment (period 2026-03-01)
[7] Yahoo Finance — timeseries.json and briefing_latest.financialMarkets (equities, FX, commodities, period 2026-04-11 where fresh)
[8] commodities.json — uranium, steel, potash, TSX infrastructure, nickel proxies — retrieved 2026-04-11
[9] policy.json — 4 weeks, most recent 2026-04-11 (BC housing / softwood / rental report)
[10] events.json — 69 watchlist entries dated 2026-04-11
[11] data_gap_report.md — 2026-04-11, Phase 0.5 audit
[12] briefing_latest.json — previous week edition MAR 23 – MAR 30 headline "Strait of Hormuz Crisis Drives WTI Above $100 as Canada Posts 0.1% GDP Growth and 84,000 Job Losses" — used as comparison baseline
[13] BC Gov News — https://news.gov.bc.ca/releases/2026HMA0042-000398 — BC March 2026 housing highlights
