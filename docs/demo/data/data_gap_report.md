# Data Gap Report — 2026-03-31

## Critical Gaps (will affect briefing quality)

### 1. Ontario and Quebec briefing analyses are empty
- **Ontario** analysis: "No province-specific articles or signals were available for Ontario this week." (85 chars)
- **Quebec** analysis: "No province-specific articles or signals were available for Quebec this week." (84 chars)
- These are the two largest provinces by GDP. The national briefing references $210B Ontario capital plan and $167B Quebec QIP, but the province tabs have no analysis. This is a data-to-briefing linkage failure, not a data gap.

### 2. Four provinces/territories have ZERO indicators in indicators.json
- **NT** (Northwest Territories): 0 indicator types
- **NU** (Nunavut): 0 indicator types
- **PE** (Prince Edward Island): 0 indicator types
- **YT** (Yukon): 0 indicator types
- StatCan publishes unemployment and CPI for all provinces. These should be populated.

### 3. Trade data frozen at 2003
- `total_exports`: latest = 2003-01-01
- `total_imports`: latest = 2003-01-01
- `agri_exports`: latest = 2003-01-01
- `forestry_exports`: latest = 2003-01-01
- `mineral_exports`: latest = 2003-01-01
- These appear to be legacy placeholders. Either populate from StatCan Table 12-10-0129 or remove to avoid confusion.

### 4. Lumber timeseries frozen since May 2023
- `lumber`: latest data point = 2023-05-12 (1,054 days stale)
- Lumber is a critical Canadian commodity affecting forestry exports and construction costs. The Yahoo Finance ticker may have changed or been delisted.

### 5. Briefing metrics mostly empty
- 9 of 15 briefing metrics are blank: `realGdp`, `nomGdp`, `outputGap`, `shelterCpi`, `participation`, `wageGrowth`, `currentAccount`, `employmentRate`, `participationRate`
- These values exist in indicators.json (`employmentRate`, `participationRate`, `wageGrowth` all have 2026-02-01 or 2026-03-31 data) but are not flowing into the briefing metrics object.

### 6. CAD/USD duplicate with divergent dates
- `cad_usd`: latest = 2026-03-30 (current)
- `cadusd`: latest = 2026-03-19 (12 days stale)
- Two separate indicator keys track the same pair. The timeseries also has both. Consolidate to avoid confusion.

### 7. Missing FX pairs in briefing
- Financial markets section has only 1 FX pair (USD/JPY). Missing: CAD/USD, EUR/USD, USD/CNY
- CAD/USD is the most important FX rate for a Canadian economic dashboard.

---

## Warnings (may affect depth)

### 8. Provincial indicators limited to CPI + unemployment for 8 provinces
- AB, BC, MB, NB, NL, NS, SK each have only 2 indicator types (CPI, unemployment)
- Missing across all 8: `gdp`, `housing_starts`, `employment_rate`, `participation_rate`
- ON has 8 types (CPI, unemployment + 6 economic accounts)
- QC has 15 types (best coverage of any province)
- The pipeline's `statcan_extended.py` fetches provincial housing starts (34-10-0143) and employment (14-10-0022). These may not be propagating to the indicators.json export.

### 9. Nickel price data appears frozen
- commodities.json shows nickel at 28.4 with 0.0% change across all periods (1w, 1m, 1y)
- timeseries.json shows nickel at 17,173 USD/t with identical values for Feb-Mar 2026
- The commodity ETF proxy (NIKL) may have stopped trading or the data source is returning stale values.

### 10. Building permits indicator has ancient data
- `building_permits`: latest period = 2007-04-01 in indicators.json
- This appears to be a legacy stub. The pipeline should either populate this from StatCan Table 34-10-0066 or remove the key.

### 11. Several commodity timeseries have duplicate entries
- Nickel, lumber, and others show duplicate entries per date (same date, same value, different sources: FRED + Yahoo Finance). Not a data gap per se, but adds noise.

### 12. ECB deposit rate stale
- `ecb_deposit_rate`: latest = 2025-02-05 (419 days old)
- ECB has made rate decisions since then. Affects EU section of the global analysis.

### 13. US real GDP lagging
- `us_real_gdp`: latest = 2025-10-01 (Q3 2025)
- Q4 2025 data should be available by now (BEA releases ~3 months after quarter end).

### 14. Ontario economic accounts stale (quarterly)
- All 6 `on_*` indicators (exports, GDP goods, imports, capital investment, consumption, household) stuck at 2025-07-01 (Q2 2025)
- Q3 2025 should be available. These are quarterly so 273 days stale is significant.

### 15. Quebec quarterly indicators also stale
- `qc_business_investment`, `qc_exports`, `qc_imports`, `qc_real_gdp`: all at 2025-07-01
- `qc_intl_exports`, `qc_intl_imports`: at 2025-12-01 (acceptable for quarterly)

### 16. Market index gaps
- `idx_nikkei`: latest = 2026-03-15 (16 days stale)
- `idx_djia`: latest = 2026-03-16 (15 days stale)
- `idx_sp500`: latest = 2026-03-15 (16 days stale)
- Note: The non-prefixed versions (`nikkei225`, `djia`, `sp500`) are more current. The `idx_*` prefix series may be a parallel data path that stopped updating.

### 17. TSX equity proxies stale
- `cameco_uranium`: latest = 2026-03-18 (13 days stale)
- `potash_nutrien`: latest = 2026-03-18 (13 days stale)
- `sprott_uranium`: latest = 2026-03-18 (13 days stale)
- `tsx`: latest = 2026-03-18 (13 days, but `tsx_composite` is current at 2026-03-31)

### 18. Consumer pulse and word cloud empty in briefing
- `consumer_pulse`: empty string (0 chars)
- `word_cloud_topics`: empty array
- `indicatorContextLines`: empty dict
- These are expected briefing sections that are not populated.

### 19. Commodity data quality issues in briefing
- Rice shows day change of -99.0% and YoY of -99.2% -- likely a data error or unit mismatch
- Platinum value is "$6" which is clearly wrong (should be ~$900-1000/oz)
- Soybean Meal value ($315.00) and Palladium ($68) appear to be cross-contaminated or using wrong units

### 20. 2,122 projects stuck at lastSeen = 2026-03-15
- All from `government_backfill` discovery source
- These have not been re-seen in 16 days
- Heaviest provinces: AB (520), QC (399), ON (349), BC (344)
- Not yet at the 30-day staleness threshold but approaching it
- Some have suspect values (e.g., "Beacon Langdon AI Hub" at $100B, "Paul First Nation" building at $40B) suggesting extraction errors in value parsing

### 21. Briefing missing DJIA and Nasdaq from indices
- Only 4 indices shown: TSX, S&P 500, FTSE 100, DAX
- Missing: DJIA, Nasdaq, Nikkei 225 (all have data in indicators.json)

---

## Filled This Run
- (none — audit only, no data refresh)

---

## Coverage Summary

| Metric | Value |
|--------|-------|
| **Provinces with full indicator sets (6 core types)** | 0/13 |
| **Provinces with any indicators** | 9/13 (missing: NT, NU, PE, YT) |
| **Province indicator depth** | QC: 15 types, ON: 8, rest: 2 each |
| **Commodity prices current (7d) in timeseries** | 67/111 keys |
| **Timeseries keys stale 8-30d** | 6/111 |
| **Timeseries keys stale 30+d** | 38/111 |
| **Projects total** | 7,372 |
| **Projects seen in last 7 days** | 5,208 (71%) |
| **Projects seen 8-16 days ago** | 2,164 (29%) |
| **Projects seen 30+ days ago** | 0 |
| **Policy items this week** | 1 (BC housing — Mar 27) |
| **Policy items last 14 days** | 1 (acceptable but thin) |
| **Briefing metrics populated** | 5/15 (33%) |
| **Briefing province analyses populated** | 11/13 (ON, QC empty) |
| **Yield curve complete** | Yes (6 terms: 2Y through Long) |
| **GoC yields current** | Yes (all 2026-03-31) |
| **National macro indicators current** | Yes (GDP, CPI, unemployment, housing starts, BoC rate all current) |
| **Commodity timeseries (non-duplicate keys)** | ~35 commodities tracked |
| **Industries analyzed in briefing** | 20/20 (5 goods + 15 services) |
| **Global regions analyzed** | 4/4 (US, China, EU, UK) |

---

## Priority Actions

1. **Fix Ontario/Quebec briefing** — Research agents need province-specific signals for ON and QC. These provinces have $377B in combined capital announcements this week per the executive summary, yet their province tabs are empty.
2. **Add indicators for NT, NU, PE, YT** — StatCan publishes CPI and unemployment for all provinces including territories.
3. **Fix trade data** — Either connect to StatCan 12-10-0129 for current trade figures or remove the 2003-era stubs.
4. **Fix lumber timeseries** — Find replacement ticker or data source for lumber prices.
5. **Pipe existing indicators into briefing metrics** — `employmentRate`, `participationRate`, and `wageGrowth` all have data but are not appearing in the briefing metrics object.
6. **Add CAD/USD to briefing FX section** — Data exists in indicators.json but is not in the financial markets display.
7. **Investigate commodity data quality** — Rice, Platinum, Palladium, Soybean Meal values in the briefing appear incorrect.
8. **Update ECB rate and US GDP** — Both are significantly stale.
9. **Refresh Ontario quarterly economic accounts** — Q3 2025 data should be available.
10. **Consolidate duplicate indicator keys** — `cad_usd`/`cadusd`, `idx_*`/non-prefixed indices, `tsx`/`tsx_composite`.
