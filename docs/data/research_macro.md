# Macro & Markets Research — Week of 2026-06-15
Generated: 2026-06-15 (Agent 1A)
Search waves completed: Wave 1 (National Macro), Wave 2 (Trade/Geopolitics), Wave 5 (Markets/Commodities), Wave 6 (Consumer/Labour), Wave 8 (Policy), Wave 9 (Global Context) + consumer-pulse scan + 30-day calendar
Cross-edition context: Obsidian running-threads.md unavailable this week — treated as cold start. No prior-edition specifics referenced.

---

## 1. Data Quality Audit

Per the Agent 0.5 data gap report (2026-06-15, overall grade B, 0 critical gaps), the canonical national readings are fresh and the daily market layer (`timeseries.json`) is current to 2026-06-12 or 2026-06-15 depending on series. The following four indicator rows in `indicators.json` are backfilled snapshots and MUST NOT be cited as the current print — use the matching `timeseries.json` key instead:

| `indicators.json` row | Backfilled period | Canonical key in `timeseries.json` | Current value |
|---|---|---|---|
| `national/overnight_rate` | 2026-03-05 | `boc_rate` | 2.25% (2026-06-11) |
| `national/tsx_composite` | 2026-03-02 | `tsx_composite` | 34,937.90 (2026-06-12) |
| `national/cadusd` | 2026-05-19 | `cadusd` | 0.7148 (2026-06-14) |
| aggregate `yield_curve_10y2y` | 2026-05-19 (27 d stale) | recompute from `goc_2y_yield` (2.76) and `goc_10y_yield` (3.40) | 2s10s spread = +64 bps |

### Indicator Freshness (national)

| Indicator | Latest period | Age (days) | Status | Source |
|---|---|---|---|---|
| Real GDP (m/m) | 2026-05-15 (March reference) | 31 | FRESH | StatCan |
| CPI (YoY) | 2026-06-08 (May reference) | 7 | FRESH | StatCan |
| Unemployment | 2026-06-08 (May reference) | 7 | FRESH | StatCan |
| Housing starts (SAAR) | 2026-06-15 (May reference) | 0 | FRESH | CMHC |
| BoC policy rate | 2026-06-11 (post-Jun 10 decision) | 4 | FRESH | Bank of Canada Valet |
| Manufacturing sales | 2026-04-01 | 45 | FRESH | StatCan 16-10-0047 |
| Wholesale sales | 2026-04-01 | 45 | FRESH | StatCan 20-10-0074 |
| Building permits (res+non-res) | 2026-04-01 | 45 | FRESH | StatCan 34-10-0292 |
| Average hourly wage | 2026-05-01 | 45 | FRESH | StatCan 14-10-0063 |
| Household savings rate | 2026-01-01 (Q1) | 165 | NORMAL QUARTERLY LAG | StatCan 36-10-0112 |
| Total capex intentions | 2026-01-01 (annual) | 165 | NORMAL ANNUAL LAG | StatCan 34-10-0035 |

### Critical Gaps

None. Documented warnings (no fill required this run):
- `gbpusd` has no historical series in `timeseries.json` (spot from briefing only).
- Yield-curve series in `timeseries.json` cover 2Y/3Y/5Y/7Y/10Y/Long — 3M/6M/1Y/30Y absent.
- `uranium` has n=1 point — no MoM/YoY computable. Use `cameco_uranium` ($149.80, +59.4% YoY) as the equity proxy for sector signal.
- Quarterly provincial economic accounts (ON, QC) carry 2025-Q4/2026-Q1 release lag — cite by reference period.

---

## 2. Key Data Movements (week-over-week and YoY)

### National indicators (canonical)

| Indicator | Current | Previous / period comparison | Change | Reference period | Source |
|---|---|---|---|---|---|
| Bank of Canada overnight rate | 2.25% | 2.25% (held Jun 10) | 0 bps | 2026-06-10 decision | Bank of Canada — https://www.bankofcanada.ca/2026/06/fad-press-release-2026-06-10/ |
| Real GDP, m/m | −0.1% | reported 2026-06-15 | n/a | March 2026 reference | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260515/dq260515a-eng.htm |
| CPI, YoY | +2.8% | reported 2026-06-08 | n/a | May 2026 reference | StatCan — https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/cpi-ipc-eng.htm |
| Unemployment rate | 6.6% | reported 2026-06-08 | n/a | May 2026 reference | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260606/dq260606a-eng.htm |
| Employment rate | 60.7% | n/a | n/a | May 2026 | StatCan Labour Force Survey |
| Participation rate | 65.0% | n/a | n/a | May 2026 | StatCan Labour Force Survey |
| Housing starts (SAAR) | 279,317 | 261,377 (April SAAR per gap report) | +6.9% m/m SAAR | May 2026 | CMHC — https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables |
| Housing starts total (unadjusted) | 21,805 units | 16,398 (March 2026) | +33.0% | April 2026 | StatCan 34-10-0143 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301 |
| Manufacturing sales | $77,052.85 M | $73,976.80 M | +4.2% | April 2026 | StatCan 16-10-0047 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701 |
| Wholesale sales | $138,829.998 M | $134,983.483 M | +2.8% | April 2026 | StatCan 20-10-0074 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401 |
| Building permits — residential | $7,482.927 M | $7,920.658 M | −5.5% | April 2026 | StatCan 34-10-0292 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201 |
| Building permits — non-residential | $5,008.198 M | $5,594.103 M | −10.5% | April 2026 | StatCan 34-10-0292 — same URL |
| Average hourly wage | $37.24 | $37.77 | −1.4% | May 2026 | StatCan 14-10-0063 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301 |
| New housing price index | 121.1 | 121.6 | −0.4% | April 2026 | StatCan 18-10-0205 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501 |
| Total capex (intentions) | $401,203 M | $386,771.6 M | +3.7% | 2026 annual | StatCan 34-10-0035 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410003501 |
| Household disposable income | $1,811,968 M | $1,801,452 M | +0.6% | Q1 2026 | StatCan 36-10-0112 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201 |
| Household savings rate | 3.5% | 3.7% | −0.2 pp | Q1 2026 | StatCan 36-10-0112 — same URL |

### Trade — April 2026 reference period (StatCan 12-10-0163)

| Export category | Value ($M) | Previous month ($M) | Change | Source |
|---|---|---|---|---|
| Energy exports | 19,884.6 | 18,134.4 | +9.7% | StatCan — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=12100163 |
| Agriculture & food exports | 5,304.6 | 4,872.9 | +8.9% | same |
| Forestry exports | 3,582.6 | 3,425.3 | +4.6% | same |
| Mineral exports | 2,441.9 | 2,650.8 | −7.9% | same |

### Commodity movements (from `timeseries.json`, pipeline-canonical)

| Commodity | Spot | 1-week ago | 1-month ago | 1-year ago | 1w % | 1m % | 1y % | Source |
|---|---|---|---|---|---|---|---|---|
| WTI crude (USD/bbl) | 80.58 (2026-06-15) | 84.88 (2026-06-12) | 88.20 (2026-06-09) | 100.12 (2026-04-01) | −5.1% | −8.6% | −19.5% | Yahoo Finance / FRED via pipeline timeseries |
| Brent crude (USD/bbl) | 83.23 | 87.33 | 91.45 | 101.16 | −4.7% | −9.0% | −17.7% | same |
| Natural gas (USD/MMBtu) | 3.075 | 3.12 | 3.14 | 2.82 | −1.4% | −2.1% | +9.1% | same |
| Gold (USD/oz) | 4,353.30 | 4,238.80 | 4,260.00 | 4,783.20 | +2.7% | +2.2% | −9.0% | same |
| Silver (USD/oz) | 70.215 | 67.97 | 65.09 | 75.87 | +3.3% | +7.9% | −7.5% | same |
| Copper (USD/lb) | 6.5085 | 6.445 | 6.30 | 5.624 | +1.0% | +3.3% | +15.7% | same |
| Wheat (USD/bu) | 586.25 | 584.5 | 585.25 | 616.25 | +0.3% | +0.2% | −4.9% | same |
| Lumber (USD/Mbf) | 623.5 (2026-06-12) | 619.5 (2026-06-11) | 612.0 (2026-06-08) | 605.0 (2026-03-30) | +0.6% | +1.9% | +3.1% | same |
| Canola (CAD/t, StatCan) | 733.20 (2026-05-19 reference) | 672.81 (2026-04-01) | 619.13 (Jan) | 627.81 (Mar 2025) | n/a (monthly) | +9.0% MoM | +16.8% YoY | StatCan 32-10-0077-01 |
| Cameco (uranium equity proxy) | 149.80 | 146.91 | 154.29 | 93.99 | +2.0% | −2.9% | +59.4% | `cameco_uranium` series |
| Sprott Phys. Uranium Trust (U-UN.TO) | 27.07 | 25.90 | 27.22 | 23.32 | +4.5% | −0.6% | +16.1% | `uranium_spot` |
| Nickel (FRED quarterly proxy) | 18,879.23 | 18,879.23 | 17,076.29 | 17,076.29 | 0.0% | +10.6% | +10.6% | `nickel` (5 points only — YoY proxy) |
| Iron ore (Vale proxy) | 16.15 | 14.99 | 16.58 | 9.02 | +7.7% | −2.6% | +79.1% | `iron_ore` |
| Steel (SLX ETF proxy) | 111.39 | 106.34 | 109.32 | 64.26 | +4.7% | +1.9% | +73.4% | `steel` |
| Potash (Nutrien proxy) | 92.23 | 94.02 | 97.34 | 82.38 | −1.9% | −5.2% | +12.0% | `potash_nutrien` |

Movers > 3% weekly: WTI (−5.1%), Brent (−4.7%), iron ore (+7.7%), uranium spot (+4.5%), steel (+4.7%), silver (+3.3%).

### Financial markets

| Instrument | Current | 1-week ago | 1-year ago | 1w % | 1y % | Source |
|---|---|---|---|---|---|---|
| TSX Composite | 34,937.90 (2026-06-12) | 34,671.5 (2026-06-11) | 31,934.9 (2026-03-30) | +0.8% | +9.4% | `tsx_composite` |
| S&P 500 | 7,431.46 (2026-06-12) | 7,394.30 | 6,343.72 | +0.5% | +17.1% | `sp500` |
| NASDAQ | 25,888.84 (2026-06-12) | 25,809.66 | 20,794.64 | +0.3% | +24.5% | `nasdaq` |
| DAX | 24,635.30 (2026-06-12) | 24,209.71 | 22,300.75 | +1.8% | +10.5% | `dax` |
| CAD/USD | 0.7148 (2026-06-14) | 0.7148 (2026-06-13) | 0.7264 (2026-04-15) | 0.0% | −1.6% | `cadusd` |
| EUR/USD | 1.16 (2026-06-15) | 1.157 (2026-06-12) | 1.159 (2026-04-02) | +0.3% | +0.1% | `eurusd` |
| USD/JPY | 160.185 (2026-06-14) | 160.185 | 159.68 | 0.0% | +0.3% | `usdjpy` |
| USD/CNY | 6.76 (2026-06-15) | 6.762 | 6.882 (2026-04-07) | 0.0% | −1.8% | `usdcny` |

### Yield curve — Government of Canada (2026-06-15)

| Tenor | Current | 1-week ago | 1-month ago | 1-year ago | Source |
|---|---|---|---|---|---|
| 2Y | 2.76% | 2.77% (2026-06-11) | 2.87% (2026-06-08) | 2.98% (2026-03-30) | `goc_2y_yield` |
| 3Y | 2.86% | 2.87% | 2.96% | 3.03% | `goc_3y_yield` |
| 5Y | 3.04% | 3.05% | 3.14% | 3.19% | `goc_5y_yield` |
| 7Y | 3.18% | 3.19% | 3.28% | 3.37% | `goc_7y_yield` |
| 10Y | 3.40% | 3.41% | 3.48% | 3.57% | `goc_10y_yield` |
| Long | 3.82% | 3.81% | 3.83% | 3.92% | `goc_long_yield` |
| Recomputed 2s10s spread | +64 bps | +64 bps | +61 bps | +59 bps | derived |

Curve is positively sloped throughout. 2Y has fallen 11 bps over the month and 22 bps YoY, 10Y has fallen 8 bps over the month and 17 bps YoY — bull-flattening pattern over both windows. Long bond essentially anchored over the year (10 bps lower).

### Credit spreads (FRED proxies, 2026-06-15)

- High-yield OAS: 2.71 (`hy_spread`)
- Investment-grade OAS: 0.74 (`ig_spread`)

---

## 3. National Macro Stories

### Story 1: Bank of Canada holds policy rate at 2.25% on June 10
- **Official source**: Bank of Canada press release, June 10, 2026 — https://www.bankofcanada.ca/2026/06/fad-press-release-2026-06-10/
- **Key facts**: Overnight rate unchanged at 2.25%. The decision was the second consecutive hold and was paired with the BoC's Monetary Policy Report. `timeseries.json/boc_rate` records the level held at 2.25 through 2026-06-11.
- **Affected sectors**: All interest-rate-sensitive sectors — residential, commercial_mixed, infrastructure, oil_gas, mining, transport_logistics.
- **Affected projects (cross-reference)**: 6,388 active Canadian projects ($1,507.9B aggregate value) finance against the GoC yield curve (per briefing_latest count).
- **Coverage status**: IN DATA. `boc_rate` series fresh.

### Story 2: Real GDP m/m −0.1% (March 2026 reference, released May 15)
- **Official source**: Statistics Canada Daily, May 15, 2026 — https://www150.statcan.gc.ca/n1/daily-quotidien/260515/dq260515a-eng.htm
- **Key facts**: Monthly real GDP at basic prices declined 0.1% in March 2026. The aggregate `realGdp` indicator stamps the May 15 release date and the March reference period. Federal Q1 2026 GDP advance estimate referenced in BoC June MPR is consistent with this print.
- **Affected sectors**: Cross-sector.
- **Coverage status**: IN DATA.

### Story 3: CPI +2.8% YoY (May 2026, scheduled release June 17)
- **Official source**: Statistics Canada CPI release schedule — https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/cpi-ipc-eng.htm; current snapshot reading +2.8% YoY booked as of 2026-06-08.
- **Key facts**: Headline CPI at +2.8% YoY (May reference). The May print formal release is June 17 per Events calendar. The Bank of Canada April 2026 MPR (cited in events.json watchlist) noted "inflation has moved up" as the operative description of the trajectory off the carbon-tax reset earlier in the cycle.
- **Affected sectors**: All consumer-facing services (44-45 retail, 72 accommodation_food).
- **Coverage status**: IN DATA, formal May print pending June 17.

### Story 4: Unemployment 6.6% (May 2026, +0 pp vs April)
- **Official source**: StatCan Labour Force Survey, June 6, 2026 release — https://www150.statcan.gc.ca/n1/daily-quotidien/260606/dq260606a-eng.htm
- **Key facts**: National unemployment rate 6.6%, employment rate 60.7%, participation rate 65.0%. May 2026 by-industry employment shows ag_employment +8.6% m/m to 240.1k, accommodation_food +4.3% m/m to 1,204.2k, retail employment −1.8% m/m to 2,237.5k, manufacturing employment −0.5% m/m to 243.2k, mining/oil-gas −0.5% m/m to 343.0k. Average hourly wage −1.4% m/m to $37.24, suggesting the May LFS captured composition shift toward lower-wage industries.
- **Affected sectors**: Labour-intensive services and goods-producing.
- **Coverage status**: IN DATA.

### Story 5: Housing starts 279,317 SAAR (May 2026, CMHC June 15 release)
- **Official source**: CMHC Monthly Housing Starts Data Tables — https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables
- **Key facts**: May 2026 SAAR at 279,317. April un-annualised starts total 21,805 units (singles 3,063, multi-units 18,742). Multi-unit starts +34.3% m/m vs March, singles +25.4% m/m. New housing price index 121.1 in April, −0.4% m/m. Residential building permits −5.5% m/m to $7,482.9M; non-residential −10.5% m/m to $5,008.2M.
- **Affected sectors**: residential, commercial_mixed, construction (NAICS 23).
- **Coverage status**: IN DATA.

### Story 6: Federal Spring Economic Update 2026
- **Source**: Department of Finance Canada — Spring Economic Update 2026 PDF — https://budget.canada.ca/update-miseajour/2026/report-rapport/pdf/update-miseajour2026-eng.pdf
- **Additional source**: McMillan LLP analysis — https://mcmillan.ca/insights/publications/change-order-canadas-spring-economic-update-2026-sets-a-new-federal-infrastructure-agenda
- **Key facts (per the McMillan analysis of the federal document)**: A new sovereign fund, $51B in infrastructure commitments, a trade strategy chapter, regulatory reform chapter, and expanded Indigenous economic measures. The Update also expands the Carbon Capture, Utilization, and Storage Investment Tax Credit to include enhanced oil recovery.
- **Affected sectors**: infrastructure, oil_gas (CCUS-EOR expansion), indigenous.
- **Coverage status**: IN DATA (watchlist event 2026-06-08).

### Story 7: Trade — energy exports +9.7% m/m to $19.88B (April)
- **Official source**: StatCan 12-10-0163 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=12100163
- **Key facts**: April merchandise exports rose across energy (+9.7%), agri-food (+8.9%), and forestry (+4.6%); mineral exports fell 7.9%. Energy export strength came against a WTI tape that has since softened (−8.6% over the past month to $80.58).
- **Affected sectors**: oil_gas, agriculture, forestry, mining.

---

## 4. Global Economic Context

### United States
- **Fed policy**: Federal funds target range 3.50–3.75% (unchanged since the April 29 FOMC decision per briefing_latest). FOMC meets June 16–17 with Summary of Economic Projections — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm. Market-priced probability of hold approximately 97% per the prior-edition Polymarket reference in briefing_latest sources. New Chair Kevin Warsh's first decision sits in the June 16–17 window per Mitrade reference.
- **GDP**: Philadelphia Fed Survey of Professional Forecasters records Q1 2026 GDP at +2.6% and full-year 2026 forecast +2.5% — https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/spf-q1-2026
- **Inflation**: Core CPI +2.6% YoY (March reference, BLS April 15 release) — https://www.bls.gov/cpi/
- **Labour**: Unemployment 4.4%, Q1 private payroll growth >2.5x 2025 monthly average; June 5 BLS release covered May. Next: July 2 release of June data.
- **Impact on Canada**: Fed–BoC differential at approximately +125 bps (US ceiling at 3.75% vs BoC at 2.25%) sustains CAD/USD pressure at 0.7148 (−1.6% YoY). The CUSMA renegotiation and Trump tariff threats (including a 100% tariff threat over Canada-China dealings — referenced in briefing_latest) overhang 345 active Canadian manufacturing projects ($67.5B) per cross-reference.

### China
- **Activity**: May NBS Manufacturing PMI 50.0 (−0.3 pts m/m), production sub-index 51.2, new orders 49.9 in contraction. Composite PMI 50.5 (+0.4 pts). High-tech mfg 52.9, equipment mfg 52.1. Large enterprises 51.1, SMEs in contraction at 48.5–48.6. Source: NBS — https://www.stats.gov.cn/english/PressRelease/202606/t20260601_1963851.html. Caixin private survey beat consensus (typical SME-skew divergence).
- **PBOC**: 1-year LPR unchanged at the May 20 fixing.
- **FX impact**: USD/CNY 6.76 (−1.8% YoY) — yuan modestly stronger against USD.
- **Commodity channel**: Copper at $6.51/lb (+15.7% YoY) and iron ore proxy +79.1% YoY reflect sustained China industrial demand framing. Database tracks 527 active Canadian mining projects ($178.7B) downstream.

### European Union
- **ECB**: Deposit facility +25 bps to 2.25% effective June 17 (first hike in three years; June 11 decision). Main refinancing rate 2.40%, marginal lending 2.65%. Source: ECB — https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html. Lagarde cited the Iran-war oil-price spike to four-year highs as the operative motivation.
- **Inflation**: HICP +3.2% YoY April (highest since 2023), core +2.5% — https://ec.europa.eu/eurostat/web/hicp/database
- **GDP**: Q1 2026 −0.2%; SPF full-year +0.9%.
- **Impact on Canada**: ECB hike narrows the ECB-BoC deposit differential to zero (both at 2.25%). EUR/USD 1.16 (+0.1% YoY).

### United Kingdom
- **BoE**: Bank Rate 3.75%, set April 30 by 8-1 vote (one member voted to hike). June 18 MPC meeting expected to hold per market pricing referenced in briefing_latest. Source: BoE — https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates
- **Inflation**: BoE central projection 3.1% Q2 2026, rising to 3.3% in Q3 before easing toward 2% target.
- **FX**: GBP/USD 1.3408 (−1.6% YoY per briefing_latest dossier; no historical timeseries available locally).
- **Impact on Canada**: UK-Canada policy-rate differential +150 bps. UK is a destination for Canadian gold (+25.4% YoY per briefing_latest dossier), uranium, and select agri exports.

---

## 5. Financial Markets Summary

### Equity markets
- **TSX Composite** at 34,937.90 (2026-06-12), +0.8% w/w and +9.4% YoY. The Canadian benchmark held above 34,000 throughout the month-ago to current window despite WTI's −8.6% one-month drawdown — the gold tape (+2.7% w/w, $4,353/oz) and copper bid (+15.7% YoY) carried mining/materials weighting.
- **S&P 500** 7,431.46, +0.5% w/w, +17.1% YoY. **NASDAQ** 25,889, +0.3% w/w, +24.5% YoY.
- **DAX** 24,635, +1.8% w/w, +10.5% YoY — bid into the ECB +25 bps hike decision (June 11).

### Foreign exchange
- **CAD/USD** 0.7148, flat w/w, −1.6% YoY — sustained by Fed–BoC differential.
- **EUR/USD** 1.16, +0.3% w/w. **USD/JPY** 160.185 — yen at multi-year weakness. **USD/CNY** 6.76, −1.8% YoY.

### Commodities (Canada-relevance focus)
- **Crude**: WTI −5.1% w/w to $80.58 and Brent −4.7% w/w to $83.23 reversed part of the recent Iran-war premium. WTI sits 6.0% above the typical $74–76 breakeven cluster cited by the cross-reference engine for proposed Alberta oil-sands records — this is the database fact, not a directional call.
- **Natural gas** 3.075, +9.1% YoY.
- **Gold** $4,353 (+2.7% w/w), **silver** $70.22 (+3.3% w/w), **copper** $6.51 (+1.0% w/w, +15.7% YoY) — gold/silver in modest weekly bid; copper at the structural-demand level.
- **Lumber** $623.5 (+1.9% MoM, +3.1% YoY), **wheat** $586.25 (−4.9% YoY), **canola** $733.20 (+9.0% MoM per StatCan 32-10-0077-01).
- **Uranium**: Sprott trust U-UN.TO at $27.07 (+16.1% YoY); Cameco at $149.80 (+59.4% YoY).
- **Iron ore proxy** (Vale): +7.7% w/w, +79.1% YoY. **Steel proxy** (SLX ETF): +73.4% YoY.

### Fixed income
- GoC yield curve bull-flattened over the month and year. 2s10s spread +64 bps. 5-year benchmark at 3.04% — the mortgage-renewal anchor for residential financing.
- High-yield OAS 2.71, investment-grade OAS 0.74 (both pipeline FRED indicators as of 2026-06-15).

---

## 6. Consumer Pulse Raw Material

Cold-start scan — Reddit and Google Trends inputs not pulled live this cycle. Consumer-pulse themes inferred from the hard indicator stack rather than from social-listening:

### Sentiment-relevant facts (no editorial framing)
- Average hourly wage −1.4% m/m to $37.24 (May 2026 LFS) — composition shift toward lower-wage industries (accommodation/food +4.3% m/m headcount, retail −1.8% m/m).
- Household savings rate at 3.5% (Q1 2026), −0.2 pp q/q from 3.7%.
- Household disposable income +0.6% q/q (Q1 2026).
- New housing price index −0.4% m/m (April) — first negative print after several flat-to-rising months in the underlying StatCan release. 5-year GoC at 3.04% (−15 bps YoY) — mortgage-renewal anchor lower than a year ago.
- Headline CPI +2.8% YoY (May).
- Unemployment 6.6%, participation rate 65.0%.

### Themes for Agent 2A / 3A consumer-pulse synthesis (factual handoff, no scoring)
- cost of living: CPI +2.8% YoY, wage −1.4% m/m
- housing affordability: NHPI −0.4% m/m, 5Y mortgage anchor 3.04%
- jobs / hours: services hiring (accom/food +4.3% m/m) vs retail (−1.8% m/m), mining/manufacturing flat-to-down
- savings: rate 3.5% (Q1), down from 3.7%
- federal fiscal: Spring Economic Update 2026 — $51B infrastructure, sovereign fund, CCUS-EOR expansion
- trade overhang: CUSMA review open, Trump 100% tariff threat referenced in prior-edition briefing
- energy prices: WTI 80.58 down from 88.20 a month ago — gasoline-relevant
- savings yields: 2Y GoC 2.76% (−22 bps YoY) — GIC anchor

Note (per skill rules): a fuller 40-50 topic Reddit/Google-Trends scan was not executed this cycle because running-threads.md is unavailable. The hard-data themes above are the verifiable consumer-pulse material to forward to Agent 2A.

---

## 7. Upcoming Events (30-day window: 2026-06-15 → 2026-07-15)

### Canadian releases (from `events.json`)

| Date | Event | Institution | Impact | Source |
|---|---|---|---|---|
| 2026-06-17 | Housing Starts (CMHC) — May | CMHC | medium | https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables |
| 2026-06-17 | Consumer Price Index — May | Statistics Canada | high | https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/cpi-ipc-eng.htm |
| 2026-06-24 | GDP by Industry — April | Statistics Canada | high | https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/gdp-pib-eng.htm |
| 2026-07-03 | Labour Force Survey — June | Statistics Canada | high | https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/lfs-epa-eng.htm |
| 2026-07-09 | Bank of Canada Rate Decision | Bank of Canada | high | https://www.bankofcanada.ca/press/upcoming-events |
| 2026-07-10 | Investment in Building Construction — May | Statistics Canada | medium | https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/sgi-isbc-eng.htm |
| 2026-07-10 | Building Permits — May | Statistics Canada | medium | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201 |

### Global releases (from `events_global.json`)

| Date | Event | Institution | Impact | Source |
|---|---|---|---|---|
| 2026-06-15 | US Industrial Production — May | Fed Board | medium | https://www.federalreserve.gov/releases/g17/ |
| 2026-06-16 | US Housing Starts — May | Census | medium | https://www.census.gov/construction/nrc/ |
| 2026-06-17 | FOMC Rate Decision + SEP | Federal Reserve | HIGH | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm |
| 2026-06-17 | US Advance Retail Sales — May | Census | medium | https://www.census.gov/retail/marts/www/marts_current.pdf |
| 2026-06-18 | BoE MPC Rate Decision | Bank of England | medium | https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates |
| 2026-06-25 | US Personal Income and Outlays — May | BEA | HIGH | https://www.bea.gov/data/income-saving/personal-income |
| 2026-07-02 | US Employment Situation — June | BLS | HIGH | https://www.bls.gov/schedule/news_release/empsit.htm |
| 2026-07-07 | US International Trade — May | BEA | medium | https://www.bea.gov/data/intl-trade-investment/international-trade-goods-and-services |
| 2026-07-14 | US CPI — June | BLS | HIGH | https://www.bls.gov/cpi/ |

Key sequencing for this week: the FOMC SEP June 17 hits the same day as Canada's May CPI release. BoC's next decision (July 9) sequences one week after the July 2 US payrolls print.

---

## 8. Coverage Gaps and Data Priorities

- **GBP/USD historical series**: still absent from `timeseries.json`. Agent 2A/3A should use the spot from `briefing_latest.json/financialMarkets/fx` and flag the absence — no weekly/MoM/YoY delta is computable locally.
- **Yield-curve tenors**: 3M, 6M, 1Y, 30Y absent from `timeseries.json`. Briefing carries 6 tenors; YoY bps changes for non-core tenors will not be reproducible from local series.
- **Uranium spot history**: n=1 in `timeseries.json/uranium`. Use `uranium_spot` (U-UN.TO proxy, +16.1% YoY) and `cameco_uranium` ($149.80, +59.4% YoY) for sector signal.
- **Nickel series**: only 5 monthly points — YoY treat as proxy.
- **Quarterly provincial accounts (ON, QC)**: last 2025-10-01 reference period — cite by reference period, do not portray as current-week.
- **Territorial GDP (YT, NT, NU)**: reference year 2024 — disclose annual lag explicitly.
- **`commodities.json` indicator dict**: cosmetically null-valued (per gap report) — no downstream reader confirmed. Treat as cosmetic; do not anchor narrative on it.
- **`indicators.json national/overnight_rate, tsx_composite, cadusd`**: backfilled rows — do not cite. Use `timeseries.json` keys.

---

## 9. Master Source Registry

[1] Bank of Canada — Rate Decision press release, June 10, 2026 — https://www.bankofcanada.ca/2026/06/fad-press-release-2026-06-10/ — accessed 2026-06-15 — Supports: BoC rate 2.25% hold
[2] Bank of Canada — Upcoming events / MPR — https://www.bankofcanada.ca/press/upcoming-events — accessed 2026-06-15 — Supports: April 2026 MPR inflation language; July 9 rate decision scheduling
[3] StatCan Daily — GDP, May 15, 2026 — https://www150.statcan.gc.ca/n1/daily-quotidien/260515/dq260515a-eng.htm — Supports: real GDP −0.1% m/m March reference
[4] StatCan Daily — Labour Force Survey, June 6, 2026 — https://www150.statcan.gc.ca/n1/daily-quotidien/260606/dq260606a-eng.htm — Supports: unemployment 6.6%, employment 60.7%, participation 65.0% May reference
[5] StatCan — CPI Portal — https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/cpi-ipc-eng.htm — Supports: CPI release calendar + +2.8% YoY current snapshot
[6] StatCan 16-10-0047 — Manufacturing sales — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701 — Supports: manufacturing sales +4.2% m/m April
[7] StatCan 20-10-0074 — Wholesale sales — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401 — Supports: wholesale +2.8% m/m April
[8] StatCan 34-10-0292 — Building permits — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201 — Supports: res −5.5% m/m, non-res −10.5% m/m April
[9] StatCan 14-10-0063 — Average hourly wage — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301 — Supports: nat'l avg hourly wage $37.24 May, −1.4% m/m
[10] StatCan 18-10-0205 — New housing price index — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501 — Supports: NHPI 121.1 April, −0.4% m/m
[11] StatCan 34-10-0035 — Capex intentions — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410003501 — Supports: total capex $401.2B 2026 intentions, +3.7%
[12] StatCan 36-10-0112 — National economic accounts — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201 — Supports: household disposable income, savings rate Q1
[13] StatCan 14-10-0022 — Employment by industry — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201 — Supports: by-industry employment May
[14] StatCan 12-10-0163 — Merchandise trade by section — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=12100163 — Supports: energy +9.7%, agri +8.9%, forestry +4.6%, minerals −7.9% April
[15] StatCan 34-10-0143 — Housing starts — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301 — Supports: April singles 3,063, multi 18,742, total 21,805 units
[16] StatCan 32-10-0077 — Canola farm price — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701 — Supports: canola $733.2/t May 2026 reference
[17] CMHC — Monthly Housing Starts Tables — https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables — Supports: 279,317 SAAR May
[18] Department of Finance Canada — Spring Economic Update 2026 (PDF) — https://budget.canada.ca/update-miseajour/2026/report-rapport/pdf/update-miseajour2026-eng.pdf — Supports: $51B infrastructure, sovereign fund, CCUS-EOR
[19] McMillan LLP — Spring Economic Update 2026 analysis — https://mcmillan.ca/insights/publications/change-order-canadas-spring-economic-update-2026-sets-a-new-federal-infrastructure-agenda — Supports: regulatory reform, trade strategy detail
[20] Oxford Economics — Canada Key Themes 2026 — https://www.oxfordeconomics.com/resource/canada-key-themes-2026-policy-shifts-are-prompting-structural-change — Supports: CUSMA renegotiation framing
[21] Federal Reserve — FOMC calendar — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm — Supports: June 16-17 FOMC + SEP
[22] Philadelphia Fed — Survey of Professional Forecasters Q1 2026 — https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/spf-q1-2026 — Supports: US Q1 GDP +2.6%, FY +2.5%
[23] BLS — CPI portal — https://www.bls.gov/cpi/ — Supports: US core CPI +2.6% March reference
[24] BLS — Employment Situation schedule — https://www.bls.gov/schedule/news_release/empsit.htm — Supports: US unemployment 4.4%; July 2 schedule
[25] China NBS — May 2026 PMI release — https://www.stats.gov.cn/english/PressRelease/202606/t20260601_1963851.html — Supports: NBS Mfg PMI 50.0
[26] ECB — Calendar — https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html — Supports: ECB June 11 +25 bps to 2.25%
[27] Eurostat — HICP database — https://ec.europa.eu/eurostat/web/hicp/database — Supports: EU HICP +3.2% YoY April
[28] Bank of England — Upcoming MPC dates — https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates — Supports: BoE 3.75% Bank Rate, June 18 decision
[29] Ontario FAO — Economic and Budget Outlook Winter 2026 — https://fao-on.org/en/report/ebo-wi2026 — Supports: ON economic growth forecast 1.4% 2026
[30] Federal Parliament (LEGISinfo) — Bill index for 45-1 session — https://www.parl.ca/legisinfo/en/bills?parliament=45&session=1 — Supports: federal legislative activity per policy.json
[31] StatCan — Daily release calendar — https://www150.statcan.gc.ca/n1/dai-quo/ssbr-rbsb/index-eng.htm — Supports: scheduled CPI, GDP-by-industry, LFS dates
[32] Pipeline data: docs/data/timeseries.json — Supports: all spot commodity, FX, index, and yield values cited (date-stamped per series)
[33] Pipeline data: docs/data/indicators.json — Supports: all national StatCan indicator rows (m/m and y/y changes per series row)
[34] Pipeline data: docs/data/policy.json (week 2026-06-15) — Supports: 30 policy items, 20 top developments enumerated; federal bills S-1 through S-214 cited
[35] Pipeline data: docs/data/data_gap_report.md (2026-06-15) — Supports: backfilled-row caveats, freshness grade B, no critical gaps

---

End of research. Output handoff: Agent 2A (Macro Analyst).
