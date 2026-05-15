# Macro & Markets Research — Week of 2026-05-15
Generated: 2026-05-15
Search waves completed: Wave 1 (national macro), Wave 2 (trade/geopolitics), Wave 5 (financial markets/commodities), Wave 6 (consumer/labour), Wave 9 (global context) + consumer sentiment + 30-day events
Source of truth: `docs/data/indicators.json` (refreshed 2026-05-15). `briefing_latest.json` is the prior edition (week_of 2026-04-18) — its CPI/unemployment metrics are NOT used.

---

## 1. Data Quality Audit

### Indicator Freshness
| Indicator | Latest Period | Status | Notes |
|-----------|--------------|--------|-------|
| CPI (YoY) | 2026-05-15 snapshot (March 2026 ref) | FRESH | +2.4% YoY, StatCan released 2026-04-20 |
| Unemployment | 2026-05-15 snapshot (April 2026 ref) | FRESH | 6.9%, StatCan LFS released 2026-05-08 |
| Employment rate | 2026-05-15 snapshot (April 2026 ref) | FRESH | 60.5% |
| Participation rate | 2026-05-15 snapshot (April 2026 ref) | FRESH | 65.0% |
| Real GDP | 2026-05-15 snapshot (Q4 2025 ref) | FRESH | -0.6% annualized Q4 2025 |
| Housing Starts | 2026-05-15 snapshot (March 2026 ref) | FRESH | 279,317 indicators.json headline; CMHC March SAAR 235,852 (see note) |
| BoC overnight rate | 2026-03-05 (held 2026-04-29) | FRESH | 2.25%, fourth consecutive hold |
| Wage growth | 2026-02-01 (SEPH) | ACCEPTABLE | +3.9%, SEPH publishes with ~2-month lag |

### Critical Gaps Found (from data_gap_report.md, 2026-05-15)
- **briefing_latest.json is stale** (prior edition, 2026-04-19, week_of 2026-04-18; shows CPI +1.8%, unemployment 6.7%). Per the gap report, indicators.json is authoritative. Verified independently this run via StatCan: March CPI +2.4% (released Apr 20), April unemployment 6.9% (released May 8).
- **Uranium & canola: no timeseries series.** Markets/commodities tab cannot chart these. Reference qualitatively only — do not assert price moves.
- **Nickel & zinc: only 2 datapoints each (both 2026-05-15).** Weekly/monthly/YoY deltas not computable — state spot level only (nickel ~$17,076/t, zinc ~$3,182/t per indicators.json FRED feed).
- **National CPI/unemployment/housing-starts timeseries arrays lag one month** behind the indicators.json snapshot. Charts driven off timeseries `cpi` (last 2026-03-15 = 2.3), `unemployment` (last 2026-03-15 = 6.7), `housingStarts` (last 2026-03-30) display through March only; headline metrics (indicators.json) are April. Note this if a chart endpoint looks a month behind the headline.
- **QC/ON quarterly provincial economic accounts** last at Q3 2025 — source-side release lag, frame as "most recent available (Q3 2025)."
- **Housing starts cross-tab note:** indicators.json carries 279,317 SAAR as the national headline; CMHC's official March 2026 release reports the all-areas monthly SAAR at 235,852 units (down 6% from February's 250,961). Six-month trend 248,378. Actual starts in centres ≥10,000 pop were 16,398 units, +10% YoY. Analyst should reconcile the headline figure against the CMHC monthly SAAR; the CMHC release is the authoritative March print.
- **policy.json sparse:** 6 weeks present but 0 items per week — no policy items available from the pipeline this run. Use research-sourced policy/trade developments below.

---

## 2. Key Data Movements (Week-over-Week)

### National Indicators
| Indicator | Current | Prior Edition | Period | Source |
|-----------|---------|---------------|--------|--------|
| BoC overnight rate | 2.25% | 2.25% | held 2026-04-29 | Bank of Canada — https://www.bankofcanada.ca/2026/04/fad-press-release-2026-04-29/ |
| CPI (YoY) | +2.4% | +1.8% (Feb) | March 2026 | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260420/dq260420a-eng.htm |
| Unemployment | 6.9% | 6.7% | April 2026 | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm |
| Employment rate | 60.5% | 60.6% | April 2026 | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm |
| Participation rate | 65.0% | 64.9% | April 2026 | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm |
| Real GDP | -0.6% (annualized) | n/a | Q4 2025 | StatCan — https://www150.statcan.gc.ca/n1/pub/36-28-0001/2026004/article/00005-eng.htm |
| Trade balance | +$1.8B surplus | -$5.1B deficit (Feb) | March 2026 | StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260505/dq260505a-eng.htm |

### Commodity Movements (timeseries.json; weekly = vs 2026-05-08, monthly = vs ~2026-04-15, YoY = vs ~2025-05-15)
| Commodity | Current (2026-05-15) | Weekly | Monthly | YoY | Source |
|-----------|----------------------|--------|---------|-----|--------|
| WTI Crude | $100.16/bbl | +5.0% (from 95.42) | +9.7% (from 91.29) | +62.5% (from 61.62) | Yahoo Finance / timeseries.json |
| Brent Crude | $108.59/bbl | +7.2% (from 101.29) | +14.4% (from 94.93) | +68.3% (from 64.53) | Yahoo Finance / timeseries.json |
| Natural Gas | $2.92/MMBtu | +5.9% (from 2.76) | +11.8% (from 2.61) | -13.2% (from 3.36) | Yahoo Finance / timeseries.json |
| Gold | $4,563.20/oz | -3.3% (from 4720.40) | -4.9% (from 4800.00) | +41.7% (from 3220.70) | Yahoo Finance / timeseries.json |
| Silver | $78.79/oz | -2.0% (from 80.40) | n/a | n/a | Yahoo Finance / timeseries.json |
| Copper | $6.34/lb | +1.5% (from 6.25) | +4.4% (from 6.07) | +36.5% (from 4.64) | Yahoo Finance / timeseries.json |
| Lumber | $584.50 | +1.4% (from 576.50; 2026-05-14) | n/a | n/a | Yahoo Finance / timeseries.json |
| Wheat | 655.00/bu | +7.8% (from 607.50) | +10.3% (from 593.75) | +22.9% (from 532.75) | Yahoo Finance / timeseries.json |

Movements >3% weekly: WTI (+5.0%), Brent (+7.2%), natural gas (+5.9%), gold (-3.3%), wheat (+7.8%).

### Financial Market Movements (timeseries.json)
| Index/FX | Current | Weekly | Monthly | YoY | Source |
|----------|---------|--------|---------|-----|--------|
| TSX Composite | 34,268 (2026-05-14) | +1.2% (from 33,857) | +0.5% (from 34,102) | +33.4% (from 25,693) | Yahoo Finance / timeseries.json |
| S&P 500 | 7,501 (2026-05-14) | +2.2% (from 7,337) | +7.7% (from 6,967) | +27.3% (from 5,893) | Yahoo Finance / timeseries.json |
| DJIA | 50,063 (2026-05-14) | +0.9% (from 49,597) | n/a | n/a | Yahoo Finance / timeseries.json |
| NASDAQ | 26,635 (2026-05-14) | +3.2% (from 25,806) | n/a | n/a | Yahoo Finance / timeseries.json |
| CAD/USD | 0.7276 | -0.6% (from 0.7320) | +0.2% (from 0.7264) | +1.7% (from 0.7154) | Yahoo Finance / timeseries.json |
| EUR/USD | 1.1640 | -0.8% (from 1.1732) | n/a | n/a | Yahoo Finance / timeseries.json |

### Yield Curve (GoC, timeseries.json; current 2026-05-13)
| Tenor | Current | ~Week Ago (2026-05-06) | Change | Source |
|-------|---------|------------------------|--------|--------|
| 2Y GoC | 2.96% | 2.91% | +5 bps | Bank of Canada |
| 3Y GoC | 3.04% | — | — | Bank of Canada |
| 5Y GoC | 3.22% | — | — | Bank of Canada |
| 7Y GoC | 3.36% | — | — | Bank of Canada |
| 10Y GoC | 3.56% (3.58 ts) | 3.51% | +5 to +7 bps | Bank of Canada |
| Long GoC | 3.91% | — | — | Bank of Canada |
| 10Y–2Y | +60 bps | +60 bps | positive (un-inverted) | Bank of Canada |

Curve shape: positively sloped; 10Y–2Y ~+60 bps. The curve steepened modestly on the week — short and long ends both rose ~5–7 bps, consistent with energy-driven inflation repricing while the BoC stays on hold. IG spread 0.76%, HY spread 2.76% (FRED, 2026-05-15).

---

## 3. National Macro Stories

### Story 1: Bank of Canada holds policy rate at 2.25% for a fourth consecutive decision; cites Middle East war and U.S. tariff uncertainty
- **Source**: Bank of Canada — https://www.bankofcanada.ca/2026/04/fad-press-release-2026-04-29/
- **Additional sources**: https://www.cbc.ca/news/business/bank-of-canada-interest-rate-april-2026-9.7181093 ; https://www.bankofcanada.ca/2026/05/summary-of-governing-council-deliberations-fixed-announcement-date-of-april-29-2026/ ; https://www.ratehub.ca/blog/bank-of-canada-holds-interest-rate-at-2-25-for-fourth-time-in-april-2026-announcement/
- **Key facts**:
  - Policy rate maintained at 2.25% on 2026-04-29; held at this level since October 2025.
  - Governing Council looking through the war's immediate inflation impact but "will not let higher energy prices become persistent inflation."
  - BoC projects inflation easing back to the 2% target in 2027.
  - Economy expected to grow at a moderate pace while adjusting to U.S. tariffs.
- **Official source**: BoC press release + Monetary Policy Report (2026-04-29).
- **Affected sectors**: residential (mortgage rates), commercial_mixed, infrastructure financing, all rate-sensitive sectors.
- **Coverage status**: IN DATA (overnight_rate 2.25%, prime_rate 6.09%).
- **NOTE / DISCREPANCY**: events.json lists "Bank of Canada Rate Decision" on 2026-06-04 (high). The BoC April release states the next scheduled announcement is **2026-06-10**. Analyst should treat **June 10, 2026** as the authoritative next BoC date and flag the events.json June 4 entry for correction.

### Story 2: Middle East conflict / Strait of Hormuz disruption drives oil to ~$100 and pushes Canadian inflation higher
- **Source**: CNBC — https://www.cnbc.com/2026/05/14/oil-prices-today-wti-brent-hormuz-trump-xi-meeting.html
- **Additional sources**: IEA Oil Market Report May 2026 — https://www.iea.org/reports/oil-market-report-may-2026 ; https://www.fxleaders.com/news/2026/05/01/wti-crude-oil-price-today-may-1-2026-trading-near-106-hormuz-supply-shock/
- **Key facts**:
  - WTI ~$100–103/bbl mid-May; June contract settled $101.17 on 2026-05-14. WTI +62.5% YoY.
  - IEA: crude and fuel flows through the Strait of Hormuz fell ~4 million bpd in March–April; market could stay materially undersupplied through October even if the conflict resolves.
  - IEA described the disruption as exceeding the 1970s oil crises in scale.
  - March CPI gasoline component +21.2% month over month — the largest monthly gasoline increase on record (StatCan).
- **Affected sectors**: oil_gas (Canadian producers; WCS exposure), transport_logistics (fuel costs), manufacturing (input costs), consumer (pump prices).
- **Coverage status**: IN DATA (wti, brent, natural_gas current in timeseries).

### Story 3: Canadian economy contracted 0.6% annualized in Q4 2025; full-year 2025 growth 1.7%, slowest since 2016 ex-pandemic
- **Source**: StatCan — https://www150.statcan.gc.ca/n1/pub/36-28-0001/2026004/article/00005-eng.htm
- **Additional sources**: https://www.cbc.ca/news/business/canada-gdp-dec-2025-9.7108015 ; https://www.theglobeandmail.com/business/economy/article-canada-gdp-data-fourth-quarter-2025/
- **Key facts**:
  - Real GDP -0.6% annualized in Q4 2025 vs BoC/consensus expectation of flat; inventory withdrawals weighed on production.
  - Full-year 2025 real GDP +1.7%, down from ~2% in each of the prior two years.
  - Lower exports, particularly to the U.S., the main 2025 drag; U.S. tariffs on steel, aluminum and motor vehicles remained in effect.
  - Three in ten manufacturers reported a major negative tariff impact; one in five plan to delay investment/expenditure due to tariffs.
- **Affected sectors**: manufacturing, oil_gas (export volumes), transport_logistics, all trade-exposed sectors.
- **Coverage status**: IN DATA (realGdp -0.6%).

### Story 4: Canada swings to a $1.8B trade surplus in March (first since September 2025) on crude and gold exports
- **Source**: StatCan — https://www150.statcan.gc.ca/n1/daily-quotidien/260505/dq260505a-eng.htm
- **Additional sources**: https://www.cbc.ca/news/business/trade-numbers-surplus-march-2026-9.7187910 ; https://economics.td.com/ca-merchandise-trade
- **Key facts**:
  - Merchandise trade balance moved from a $5.1B February deficit to a $1.8B March surplus.
  - Surplus with the U.S. widened from $2.9B (Feb) to $7.1B (March); exports to the U.S. +8.3% (highest since March 2025), led by crude oil and passenger cars/light trucks.
  - Exports to non-U.S. destinations +9.1% m/m, an all-time high; metal/mineral and energy products posted the largest increases.
  - Imports from the U.S. -1.2% (lower aircraft imports).
- **Affected sectors**: oil_gas, mining, manufacturing (autos), transport_logistics.
- **Coverage status**: PARTIAL (national agri/mineral/forestry export rows in indicators.json carry stale 2003-01 period — flag; trade-balance narrative driven from research).

### Story 5: March housing starts lose momentum; CMHC monthly SAAR -6% to 235,852
- **Source**: CMHC — https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/housing-starts-march-2026
- **Additional sources**: https://storeys.com/cmhc-housing-starts-march-2026/ ; https://www.mpamag.com/ca/mortgage-industry/market-updates/march-housing-starts-slip-as-cmhc-warns-construction-momentum-keeps-fading/572153
- **Key facts**:
  - Total all-areas monthly SAAR 235,852 units in March, -6% from 250,961 in February.
  - Six-month trend -2.9% to 248,378 units.
  - Actual starts in centres ≥10,000 pop: 16,398 units, +10% YoY; YTD 49,206, +9% (BC, ON, QC led).
  - Among large cities: Montreal +26% YoY, Toronto +23%, Vancouver +21% (multi-unit driven).
- **Affected sectors**: residential, construction, infrastructure.
- **Coverage status**: IN DATA but headline reconciliation needed (indicators.json 279,317 vs CMHC March SAAR 235,852 — see Section 1).

---

## 4. Global Economic Context

### United States
- Federal Reserve held the fed funds target at **3.50%–3.75%** on 2026-04-29 — third consecutive hold. Source: https://www.cnbc.com/2026/04/29/fed-interest-rate-decision-april-2026.html
- FOMC statement: "Inflation is elevated, in part reflecting the recent increase in global energy prices"; conflict pushed inflation to a near-two-year high.
- Powell's likely final meeting as Chair; Kevin Warsh appointment effective 2026-05-15. Source: https://www.cnn.com/2026/04/29/economy/fed-decision-powell-warsh
- Markets pricing no Fed changes through the rest of 2026 and into 2027.
- **Impact on Canada**: Fed-BoC differential (~3.50–3.75% vs 2.25%) supports a softer CAD; U.S. solid growth supports Canadian export demand even amid tariffs.

### China
- Q1 2026 GDP **+5.0%** (vs +4.5% Q4 2025; above ~4.8% consensus; top of the 4.5–5% target band). Source: https://www.china-briefing.com/news/chinas-q1-2026-gdp/
- March official manufacturing PMI 50.4 (+1.4 pts m/m, expansionary); Caixin/RatingDog reading softened to 50.8 from 52.1. Source: https://www.stats.gov.cn/english/PressRelease/202604/t20260416_1963326.html
- Mid-East war lifting input costs into China factory data.
- **Impact on Canada**: Resilient Chinese demand supports copper (+36.5% YoY), iron ore and energy export prices; potash/canola channel relevant qualitatively (no timeseries).

### European Union
- ECB held all three key rates on 2026-04-30 (deposit 2.00%, MRO 2.15%, marginal lending 2.40%). Source: https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260430~81b7179e6f.en.html
- Economists surveyed by Bloomberg expect two ECB quarter-point hikes in 2026 (June and September) as the Iran war drives inflation higher. Source: https://www.bloomberg.com/news/articles/2026-05-11/ecb-to-hike-rates-twice-in-2026-as-inflation-jumps-survey-shows
- **Impact on Canada**: Energy-driven global inflation regime; potential ECB tightening supports EUR and global yields, reinforcing the Canadian yield back-up.

### United Kingdom
- Bank of England held Bank Rate at **3.75%** on 2026-04-30 — second consecutive hold, third decision without a cut; MPC voted 8–1. Source: https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate
- **Impact on Canada**: Confirms a synchronized G7 "hold" stance through April amid the energy shock; supports global term-premium repricing reflected in GoC yields.

---

## 5. Financial Markets Summary

### Equity Markets
TSX Composite 34,268 (2026-05-14): +1.2% weekly, +0.5% monthly, +33.4% YoY — energy and bank weightings supportive amid high crude. S&P 500 7,501 (+2.2% wk, +27.3% YoY), DJIA 50,063 (+0.9% wk), NASDAQ 26,635 (+3.2% wk). Nikkei 225 ~61,409, FTSE 100 ~10,187, DAX ~24,137 (indicators.json, 2026-05-14/15). Equities firm into a high-stakes U.S.–China summit and continued Middle East monitoring.

### Foreign Exchange
CAD/USD 0.7276 (-0.6% wk, +1.7% YoY). The wide Fed–BoC rate gap (3.50–3.75% vs 2.25%) caps CAD despite supportive crude prices. EUR/USD 1.1640 (-0.8% wk); USD/CNY 6.78; USD/JPY 158.33 (indicators.json).

### Commodities
Energy dominates: WTI $100.16 (+62.5% YoY), Brent $108.59 (+68.3% YoY), natural gas $2.92 (+11.8% monthly, -13.2% YoY). Gold $4,563 — off its January record (~$5,595) and -3.3% on the week / -4.9% monthly, but +41.7% YoY; central-bank buying could exceed 1,200 tonnes in 2026 per World Gold Council. Copper $6.34 (+36.5% YoY). Wheat 655 (+22.9% YoY). Uranium and canola not tracked in timeseries — reference qualitatively only. Nickel ~$17,076/t and zinc ~$3,182/t — spot only, no deltas.

### Fixed Income
GoC curve positively sloped, 10Y–2Y ~+60 bps. Yields backed up ~5–7 bps on the week (2Y 2.96%, 10Y 3.56–3.58%, Long 3.91%) as energy-driven inflation re-priced while the BoC stays on hold. IG spread 0.76%, HY spread 2.76% — contained credit conditions.

---

## 6. Consumer Pulse Raw Material

### Sentiment Themes
Cost-of-living attention is concentrated on gasoline: national average pump price rose to $1.92/L (2026-05-12) from $1.87/L (2026-05-05), +~3% in a week; NL highest at $2.09/L, AB lowest at $1.79/L (https://www.finder.com/ca/research/canadian-gas-prices). StatCan: gasoline +21.2% month over month in March (record), +5.9% YoY. Wages have outpaced prices for 3+ years (SEPH wage growth +3.9%), partially offsetting. Rental affordability improving — national rent-to-income ratio fell to 29% (below the 30% threshold for the first time in 6+ years); average rent -5.3% YoY to $2,008 (https://www.cibc.com/en/personal-banking/smart-advice/buying-or-renting-a-home/how-canadians-feel-about-housing-market.html). Mortgage stress: lowest 5-year fixed ~4.04%, edging up as energy-driven inflation lifts fixed rates; 70% of prospective buyers say conditions are too uncertain to judge timing. Labour-market unease: 18,000 jobs lost in April, unemployment 6.9%, youth unemployment 14.3%, long-term unemployment share 22.5%.

### Word Cloud Topics
| Topic | Sentiment | Frequency |
|-------|-----------|-----------|
| gas prices | -0.7 | 19 |
| oil shock / Middle East war | -0.6 | 17 |
| inflation | -0.5 | 18 |
| cost of living | -0.6 | 18 |
| Bank of Canada hold | -0.1 | 12 |
| interest rates | -0.3 | 15 |
| mortgage rates | -0.4 | 14 |
| housing affordability | -0.4 | 16 |
| rent | +0.1 | 13 |
| home prices | -0.3 | 12 |
| jobs lost | -0.6 | 14 |
| unemployment | -0.5 | 14 |
| youth unemployment | -0.6 | 9 |
| layoffs | -0.5 | 10 |
| wages | +0.2 | 11 |
| grocery prices | -0.5 | 13 |
| U.S. tariffs | -0.6 | 15 |
| CUSMA review | -0.3 | 11 |
| trade war | -0.5 | 12 |
| Carney government | -0.1 | 10 |
| federal spring update | -0.1 | 8 |
| GDP contraction | -0.4 | 9 |
| recession fears | -0.5 | 11 |
| TSX / stock market | +0.3 | 10 |
| gold | +0.2 | 8 |
| RRSP / TFSA savings | 0.0 | 7 |
| household debt | -0.4 | 10 |
| energy sector jobs | +0.2 | 8 |
| Alberta oil | +0.3 | 8 |
| WCS / pipeline | +0.1 | 6 |
| immigration | -0.2 | 9 |
| population growth | -0.1 | 7 |
| diesel / fuel costs | -0.5 | 9 |
| supply chain | -0.3 | 7 |
| manufacturing slowdown | -0.4 | 8 |
| auto sector | -0.3 | 7 |
| construction slowdown | -0.3 | 7 |
| housing starts | -0.2 | 6 |
| first-time buyers | -0.3 | 8 |
| renters | +0.1 | 8 |
| affordability | -0.5 | 14 |
| Fed rate hold | -0.1 | 7 |
| Canadian dollar | -0.2 | 8 |
| China demand | +0.1 | 6 |
| copper / mining | +0.2 | 6 |
| wheat / grain prices | +0.1 | 6 |
| carbon pricing | -0.2 | 6 |
| provincial budgets | -0.1 | 9 |
| economic uncertainty | -0.5 | 14 |

### Consumer Confidence
No fresh standalone confidence index obtained this run; build from gasoline (+21.2% m/m record March print), labour softening (April -18,000 jobs, 6.9% unemployment), and improving rent affordability (rent-to-income 29%). Many households still report cost-of-living pressure though real wages remain positive.

---

## 7. Upcoming Events (30-day window from 2026-05-15)

| Date | Event | Institution | Impact | Description | Source URL |
|------|-------|-------------|--------|-------------|-----------|
| 2026-05-17 | Consumer Price Index (April 2026) | Statistics Canada | HIGH | April inflation print; market watching gasoline pass-through from the oil shock | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401 |
| 2026-05-17 | Housing Starts (CMHC, April 2026) | CMHC / StatCan | MEDIUM | April SAAR; momentum trend watched after March -6% | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301 |
| 2026-05-24 | GDP by Industry (monthly) | Statistics Canada | MEDIUM | Monthly industry GDP; tariff/inventory effects | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401 |
| 2026-06-01 | USTR report to Congress on CUSMA intent | USTR / U.S. Trade Rep | HIGH | Greer must report whether to extend CUSMA as-is or pursue changes | https://www.cbc.ca/news/politics/cusma-review-2026-what-trump-wants-9.7026216 |
| 2026-06-03 | Labour Force Survey (May 2026) | Statistics Canada | HIGH | May employment/unemployment; follows April -18,000 jobs | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701 |
| 2026-06-10 | Bank of Canada Rate Decision | Bank of Canada | HIGH | Next scheduled BoC announcement per the April 29 release (NOTE: events.json incorrectly lists June 4) | https://www.bankofcanada.ca/2026/04/fad-press-release-2026-04-29/ |
| 2026-06-10 | Investment in Building Construction | Statistics Canada | MEDIUM | Building construction investment data | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410017501 |
| 2026-06-10 | Building Permits | Statistics Canada | MEDIUM | Building permits — forward construction signal | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601 |
| 2026 (ongoing) | 2026 Spring Economic Update follow-through | Dept. of Finance Canada | MEDIUM | "Canada Strong for All" measures implementation | https://www.canada.ca/en/department-finance/news/2026/04/government-of-canada-releases-2026-spring-economic-update-canada-strong-for-all.html |
| ~2026-07-01 | CUSMA six-year review formal meeting | Canada / U.S. / Mexico | HIGH | Formal review; U.S. may push 10-year annual-review framework | https://www.cbc.ca/news/politics/cusma-review-2026-what-trump-wants-9.7026216 |
| Recurring | Weekly national gasoline price update | Finder / NRCan | MEDIUM | Pump-price tracking amid oil shock | https://www.finder.com/ca/research/canadian-gas-prices |
| Recurring | StatCan trade balance (April 2026) | Statistics Canada | MEDIUM | Next merchandise trade print after March surplus | https://www150.statcan.gc.ca/n1/daily-quotidien/260505/dq260505a-eng.htm |
| Provincial | Provincial budgets implementation (AB, BC, ON, QC, SK, MB, NS, NB, NL, PE) | Provincial governments | MEDIUM | 2026-27 budgets tabled; implementation tracked | https://www.ontario.ca/budget |

(Events.json otherwise carries ~50 "watchlist/low" provincial-budget reference links dated 2026-05-15 — informational, not scheduled releases.)

---

## 8. Coverage Gaps and Data Priorities

- **Housing starts headline reconciliation:** indicators.json 279,317 SAAR vs CMHC March all-areas SAAR 235,852 — analyst must reconcile and cite the CMHC March release as authoritative for the March print.
- **BoC next-decision date error:** events.json shows 2026-06-04; BoC's own release says 2026-06-10. Flag for the conductor/fixer.
- **Trade export indicators stale-period rows:** national agri_exports/mineral_exports/forestry_exports in indicators.json carry 2003-01-01 period rows — do not cite these as current; use the StatCan March 2026 trade narrative instead.
- **Uranium & canola:** no timeseries — Markets tab cannot chart; treat qualitatively. Nickel/zinc spot only.
- **CPI/unemployment/housing-starts timeseries one month behind** the indicators.json headline — chart endpoints will read March; headline is April. Documented for chart agent.
- **policy.json empty** (0 items across 6 weeks) — policy/trade narrative must come from research (CUSMA, tariffs, Spring Economic Update covered above).
- **Wage growth period** 2026-02-01 (SEPH lag) — acceptable but note the reference month.

---

## 9. Master Source Registry

[1] https://www.bankofcanada.ca/2026/04/fad-press-release-2026-04-29/ — Bank of Canada maintains policy rate at 2¼% — Bank of Canada — 2026-04-29
[2] https://www.bankofcanada.ca/2026/05/summary-of-governing-council-deliberations-fixed-announcement-date-of-april-29-2026/ — Summary of Governing Council deliberations — Bank of Canada — 2026-05
[3] https://www.cbc.ca/news/business/bank-of-canada-interest-rate-april-2026-9.7181093 — BoC holds key rate at 2.25% amid uncertainty — CBC News — 2026-04-29
[4] https://www.ratehub.ca/blog/bank-of-canada-holds-interest-rate-at-2-25-for-fourth-time-in-april-2026-announcement/ — BoC holds rate fourth time — Ratehub — 2026-04-29
[5] https://www150.statcan.gc.ca/n1/daily-quotidien/260420/dq260420a-eng.htm — Consumer Price Index, March 2026 — Statistics Canada — 2026-04-20
[6] https://economics.td.com/ca-cpi — Canadian CPI (March 2026) — TD Economics — 2026-04
[7] https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm — Labour Force Survey, April 2026 — Statistics Canada — 2026-05-08
[8] https://www.hiringlab.org/en-ca/2026/05/08/april-2026-labour-force-survey-stuck-in-neutral/ — April 2026 LFS: Stuck in Neutral — Indeed Hiring Lab — 2026-05-08
[9] https://thehub.ca/2026/05/12/canadas-112000-jobs-lost-in-private-sector-in-2026-more-pronounced-as-government-cuts-employment-and-hiring-too/ — Private-sector jobs lost in 2026 — The Hub — 2026-05-12
[10] https://www150.statcan.gc.ca/n1/pub/36-28-0001/2026004/article/00005-eng.htm — Recent developments in the Canadian economy: Spring 2026 — Statistics Canada — 2026
[11] https://www.cbc.ca/news/business/canada-gdp-dec-2025-9.7108015 — Canada's economy contracted unexpectedly in Q4 2025 — CBC News — 2026
[12] https://www.theglobeandmail.com/business/economy/article-canada-gdp-data-fourth-quarter-2025/ — Canada's economy contracts in final quarter of 2025 — Globe and Mail — 2026
[13] https://www150.statcan.gc.ca/n1/daily-quotidien/260505/dq260505a-eng.htm — Canadian international merchandise trade, March 2026 — Statistics Canada — 2026-05-05
[14] https://www.cbc.ca/news/business/trade-numbers-surplus-march-2026-9.7187910 — Canada posts trade surplus in March — CBC News — 2026-05-05
[15] https://economics.td.com/ca-merchandise-trade — Canadian Merchandise Trade (March 2026) — TD Economics — 2026-05
[16] https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/housing-starts-march-2026 — Housing starts for March 2026 — CMHC — 2026-04
[17] https://storeys.com/cmhc-housing-starts-march-2026/ — Canadian housing starts lost steam in March — STOREYS — 2026-04
[18] https://www.mpamag.com/ca/mortgage-industry/market-updates/march-housing-starts-slip-as-cmhc-warns-construction-momentum-keeps-fading/572153 — March housing starts slip — Canadian Mortgage Professional — 2026-04
[19] https://www.cnbc.com/2026/05/14/oil-prices-today-wti-brent-hormuz-trump-xi-meeting.html — Oil hovers ~$100 after Trump-Xi Hormuz discussion — CNBC — 2026-05-14
[20] https://www.iea.org/reports/oil-market-report-may-2026 — Oil Market Report — May 2026 — IEA — 2026-05
[21] https://www.fxleaders.com/news/2026/05/01/wti-crude-oil-price-today-may-1-2026-trading-near-106-hormuz-supply-shock/ — WTI near $106, Hormuz supply shock — FXLeaders — 2026-05-01
[22] https://tradingeconomics.com/canada/stock-market — Canada Stock Market Index (TSX) — Trading Economics — 2026-05-14
[23] https://www.cnbc.com/2026/04/29/fed-interest-rate-decision-april-2026.html — Fed holds rates steady amid dissent — CNBC — 2026-04-29
[24] https://www.cnn.com/2026/04/29/economy/fed-decision-powell-warsh — Key takeaways from Powell's last meeting — CNN Business — 2026-04-29
[25] https://www.china-briefing.com/news/chinas-q1-2026-gdp/ — China's GDP grows 5% in Q1 2026 — China Briefing — 2026-04
[26] https://www.stats.gov.cn/english/PressRelease/202604/t20260416_1963326.html — National economy good start in Q1 — China NBS — 2026-04-16
[27] https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260430~81b7179e6f.en.html — ECB monetary policy decisions — European Central Bank — 2026-04-30
[28] https://www.bloomberg.com/news/articles/2026-05-11/ecb-to-hike-rates-twice-in-2026-as-inflation-jumps-survey-shows — ECB to hike twice in 2026 — Bloomberg — 2026-05-11
[29] https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate — BoE holds Bank Rate at 3.75% — Bank of England — 2026-04-30
[30] https://www.finder.com/ca/research/canadian-gas-prices — Average gas price per litre in Canada — Finder — 2026-05-12
[31] https://www.cibc.com/en/personal-banking/smart-advice/buying-or-renting-a-home/how-canadians-feel-about-housing-market.html — How Canadians feel about housing — CIBC — 2026
[32] https://www.ratehub.ca/mortgages/canada-housing-affordability — Canada housing affordability — Ratehub — 2026
[33] https://www.investing.com/news/commodities-news/global-gold-demand-inches-up-in-q1-2026-hits-record-high--world-gold-council-4643597 — Global gold demand record Q1 2026 — Investing.com / WGC — 2026
[34] https://www.mining.com/central-banks-gold-buying-momentum-carries-into-2026/ — Central banks' gold buying 2026 — MINING.COM — 2026
[35] https://www.cbc.ca/news/politics/cusma-review-2026-what-trump-wants-9.7026216 — CUSMA review 2026 — CBC News — 2026
[36] https://www.hilltimes.com/2026/04/29/as-mexico-and-u-s-are-set-to-start-the-cusma-review-canada-continues-waiting-game/501662/ — CUSMA review waiting game — Hill Times — 2026-04-29
[37] https://www.cbc.ca/news/politics/carney-trade-take-time-trump-9.7173453 — Carney: U.S. trade talks will take time — CBC News — 2026
[38] https://www.canada.ca/en/department-finance/news/2026/04/government-of-canada-releases-2026-spring-economic-update-canada-strong-for-all.html — 2026 Spring Economic Update — Dept. of Finance Canada — 2026-04
[39] https://budget.canada.ca/update-miseajour/2026/report-rapport/overview-apercu-en.html — Economic and fiscal overview, Spring Update 2026 — Dept. of Finance — 2026-04
[40] https://www.bankofcanada.ca/2026/04/opening-statement-2026-04-29/ — Monetary Policy Report press conference opening statement — Bank of Canada — 2026-04-29
