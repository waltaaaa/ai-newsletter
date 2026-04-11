# Sector & Industry Research — Week of 2026-04-11
Generated: 2026-04-11 (Agent 1C — Sector Researcher)
Industries covered: All 20 NAICS (5 goods + 15 services)
Search waves: Wave 4 (project sectors) + Wave 4b (NAICS GDP industries) + Wave 7 (mega projects)

---

## 1. Data Quality Audit

Primary input: `docs/data/industry_gdp.json` — StatCan GDP by industry, m/m and y/y changes, all 20 NAICS codes current.
Project universe: 7,427 projects across all sectors. Project-level NAICS tagging is sparse (most projects tagged by descriptive `sector` label rather than by NAICS code), so sector coverage below combines NAICS GDP signal with project-sector aggregates.

### Sector Project Coverage (aggregated from `projects_all.json`, 2026-04-11)

| NAICS | Sector Name | Projects (project-sector) | Aggregate $ | GDP m/m | GDP y/y | Status |
|-------|------------|---------------------------|-------------|---------|---------|--------|
| 11 | Agriculture, Forestry, Fishing, Hunting | 17 agriculture + 13 forestry | ~$5.4B | -1.4% | +5.4% | OK |
| 21 | Mining, Quarrying, Oil & Gas | 192 mining + 42 oil_gas | ~$269B | +1.2% | -0.1% | OK |
| 22 | Utilities | 317 power_energy + 251 energy | ~$523B | +0.6% | -1.7% | OK |
| 23 | Construction | 745 infrastructure + 578 water/wastewater + 350 transit | ~$255B | +1.1% | +2.8% | OK |
| 31-33 | Manufacturing | 47 manufacturing | ~$67B | -1.4% | -4.6% | GAP (value) |
| 41 | Wholesale Trade | — (not tracked in projects) | — | -1.2% | -1.7% | GDP only |
| 44-45 | Retail Trade | — | — | +0.8% | +2.7% | GDP only |
| 48-49 | Transportation & Warehousing | 154 ports/logistics + 82 transport | ~$42B | -0.7% | +1.6% | OK |
| 51 | Information & Cultural | 19 telecom | ~$3B | +0.9% | +3.2% | OK |
| 52 | Finance & Insurance | — | — | +0.5% | +3.2% | GDP only |
| 53 | Real Estate, Rental, Leasing | 157 residential + 60 housing + 68 commercial_mixed | ~$74B | -0.2% | +1.2% | OK |
| 54 | Professional, Scientific, Technical | — | — | -0.1% | -0.4% | GDP only |
| 55 | Management of Companies | — | — | -4.1% | -21.9% | GDP only (collapse) |
| 56 | Administrative & Waste Management | 13 environment | ~$2B | -0.1% | -0.2% | GDP only |
| 61 | Educational Services | 151 education | ~$15B | +0.5% | -1.9% | OK |
| 62 | Health Care & Social Assistance | 230 healthcare | ~$20.5B | +0.0% | +2.1% | OK |
| 71 | Arts, Entertainment, Recreation | 147 tourism_culture | ~$22B | -0.1% | +2.2% | OK |
| 72 | Accommodation & Food Services | — | — | +0.7% | +2.3% | GDP only |
| 81 | Other Services | — | — | +0.2% | +0.3% | GDP only |
| 91 | Public Administration | 191 government + 15 defence | ~$163B | -0.1% | +0.7% | OK |

### Critical Gaps
- From `data_gap_report.md`: weekly delta coverage 95%, monthly 91%, yearly 79%. Overall Data Freshness Grade: B.
- Lumber price timeseries stale since 2023-05-12 (1,065 days old). Lumber data points below come from NRCan and trade coverage, not internal timeseries.
- `jobs.json` and `procurement.json` are empty for week_of 2026-04-11 — no weekly hiring-spike or contract-award feed this cycle. Labour trends below are sourced from StatCan LFS March 2026 release.
- `policy.json` has 3 items this week, all BC-specific (housing and softwood lumber statements).
- NAICS 55 Management of Companies GDP is -21.9% y/y; no supporting project data.

---

## 2. Sector Activity Summary (NAICS GDP, StatCan, Jan 2026 reference)

Gainers (y/y): NAICS 11 Agriculture +5.4%, NAICS 51 Info/Culture +3.2%, NAICS 52 Finance +3.2%, NAICS 23 Construction +2.8%, NAICS 44-45 Retail +2.7%, NAICS 72 Accommodation/Food +2.3%, NAICS 71 Arts/Rec +2.2%, NAICS 62 Healthcare +2.1%, NAICS 48-49 Transport +1.6%, NAICS 53 Real Estate +1.2%, NAICS 91 Public Admin +0.7%, NAICS 81 Other Services +0.3%.

Decliners (y/y): NAICS 55 Management -21.9%, NAICS 31-33 Manufacturing -4.6%, NAICS 61 Education -1.9%, NAICS 22 Utilities -1.7%, NAICS 41 Wholesale -1.7%, NAICS 54 Professional/Scientific -0.4%, NAICS 56 Admin/Waste -0.2%, NAICS 21 Mining & O&G -0.1%.

Source: StatCan Table 36-10-0434, Gross domestic product by industry, January 2026 release — https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm

---

## 3. Sector Spotlights (all 20 NAICS industries)

### GOODS INDUSTRIES

#### NAICS 11: Agriculture, Forestry, Fishing & Hunting
- **GDP**: -1.4% m/m, +5.4% y/y — steepest monthly decline among all 20 industries, offset by strongest y/y growth. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Top story — softwood lumber**: U.S. Department of Commerce released preliminary results of the seventh administrative review of anti-dumping and countervailing duty orders on Canadian softwood lumber. BC Minister of Forests Ravi Parmar issued a response statement April 9, 2026. Source: https://news.gov.bc.ca/releases/2026FOR0011-000394
- **Subsidy response**: Canadian federal and provincial governments have announced more than C$2.1 billion in softwood lumber support in the last seven months, including a $1.2 billion Softwood Lumber Guarantee Program via BDC ($700M August 2025 + $500M November 2025). Quebec added $60M in March 2026 for wood processing working capital. BC announced a Stumpage Payment Deferral Program effective January 1, 2026. Source: https://uslumbercoalition.org/press-release/canadas-new-softwood-lumber-subsidies-exceed-c2-billion-solely-to-prop-up-canadas-massive-and-harmful-excess-lumber-exports-u-s-lumber-coalition/
- **Export exposure**: 66% of Canada's 2024 softwood lumber production was exported, ~90% to the U.S. Source: https://natural-resources.canada.ca/forest-forestry/forest-industry-trade/canada-s-softwood-lumber-industry
- **Fertilizer input**: Nutrien (NTR) at $102.13, -2.8% week, -4.5% month, +56.5% year (commodities.json, week ending 2026-04-11). Potash is a key input for Canadian crop economics.
- **Project activity**: 17 agriculture + 13 forestry records in `projects_all.json`. Forestry project value ~$4.7B.

#### NAICS 21: Mining, Quarrying & Oil/Gas Extraction
- **GDP**: +1.2% m/m, -0.1% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Oil & gas drilling**: Canadian Association of Energy Contractors (CAOEC) projects an average 213 active drilling rigs in 2026 (up from 201 in 2025) with 5,709 wells forecast (+3%). WTI 2026 strip ~US$57/bbl; WCS differential ~US$12.80/bbl. Source: https://atbcm.atb.com/insights/canadian-upstream-2026-outlook/
- **LNG Canada Phase 2**: TC Energy and LNG Canada signed commercial agreements in March 2026 to advance Coastal GasLink Phase 2. Capacity would expand from 2.1 Bcf/d to 5 Bcf/d via five new compressor stations. FID expected late 2026 or early 2027. LNG Canada Phase 1 completed 2025 at ~$40B; Phase 2 ~$33B. Federal Major Projects Office has included Phase 2. Source: https://www.tcenergy.com/newsroom/statements/2026/coastal-gaslink-phase-2-advances-step-forward-with-new-commercial-agreements/
- **Critical minerals**: March 2026 federal announcement — up to $165.2M for 22 projects, unlocking $434M across eight provinces. First and Last Mile Fund provides $1.5B from 2026-2030. Critical Minerals Sovereign Fund $2B over five years. Source: https://www.canada.ca/en/natural-resources-canada/news/2026/03/backgrounder-government-of-canada-invests-to-unlock-canadas-critical-minerals-advantage.html
- **Pipeline scale**: 2024-2034 — nearly 140 planned/proposed mining projects, combined value $117.1B; ~half are critical minerals, worth $72.4B. Source: https://resourceworld.com/canadian-mining-enters-2026-with-confidence-as-gold-copper-and-critical-minerals-redefine-the-sector/
- **M&A**: Anglo-Teck merger of equals announced at ~US$57B — largest copper consolidation transaction in the sector. Source: https://www.torys.com/our-latest-thinking/publications/2026/02/key-trends-in-mining-2026
- **Uranium**: Cameco (CCO) $160.73 (+2.7% week, +197.6% year). Uranium spot proxy (URA ETF) +4.2% week. Source: internal commodities.json, 2026-04-11.
- **Project activity**: 192 mining + 42 oil_gas + 12 coal mines + 19 mineral mines + 8 natural gas processing plants in `projects_all.json`.

#### NAICS 22: Utilities
- **GDP**: +0.6% m/m, -1.7% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Nuclear refurbishment**: Darlington unit 4 reconnected to the grid March 2026, completing the C$12.8B refurbishment programme — C$150M under budget and four months ahead of schedule. Source: https://world-nuclear.org/information-library/country-profiles/countries-a-f/canada-nuclear-power
- **SMR pipeline**: Ontario Power Generation's 300 MWe grid-scale SMR at Darlington targeted for 2028. New Brunswick has committed to 600 MWe of new nuclear as part of a 2035 net-zero electricity plan; first SMR targeted for 2030 at Point Lepreau. Source: https://smractionplan.ca/
- **Grid load**: Canadian Electricity Association estimates power demand could rise ~40% by 2050 (baseline for grid-expansion projects tracked in projects_all.json).
- **Generation mix**: Canada's grid is 81% hydro, nuclear, wind, and solar. Source: https://world-nuclear.org/information-library/country-profiles/countries-a-f/canada-nuclear-power
- **Project activity**: 317 power_energy + 251 energy + 204 clean energy + 14 energy storage + 20 power plants in `projects_all.json` — combined ~$523B in aggregate project value.

#### NAICS 23: Construction
- **GDP**: +1.1% m/m, +2.8% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Housing starts**: February 2026 housing starts 250,900 SAAR units (+4.5% from January's 240,148 SAAR, below consensus 252,500). Source: https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables
- **Industry outlook**: GlobalData projects Canadian construction output +2.2% in 2025, +2.6% in 2026; nonresidential starts projected -7.8% in 2026 as industrial (peaked 2024) and commercial (peaked 2025) normalize. Source: https://www.globenewswire.com/news-release/2026/02/25/3244764/28124/en/Canada-Construction-Industry-Report-2025-Output-to-Grow-by-2-6-in-2-6-in-2026-After-2-2-Growth-in-2025-Driven-by-PPI-in-Residential-and-Non-residential-Construction-and-Transport-I.html
- **Steel input**: Steel (SLX ETF proxy) $98.57, +6.6% week, +6.0% month, +76.3% year (commodities.json, 2026-04-11). Largest weekly move of any construction input in the tracked basket.
- **BC housing policy**: Minister of Housing Christine Boyle issued March 2026 housing highlights (April 10) and April 2026 rental report (April 9) affecting 114 BC projects in housing-eligible sectors. Sources: https://news.gov.bc.ca/releases/2026HMA0042-000398 and https://news.gov.bc.ca/releases/2026HMA0039-000390
- **Project activity**: Infrastructure 745 / $253B, transit & rail 350, water & wastewater 578 — largest project count concentration in the database.

#### NAICS 31-33: Manufacturing
- **GDP**: -1.4% m/m, -4.6% y/y — largest y/y decline among goods-producing industries. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Auto strategy**: PM Carney launched new auto strategy February 5, 2026. $3B Strategic Response Fund (projects >$20M) plus up to $100M Regional Tariff Response Initiative (SME-scale). Source: https://www.pm.gc.ca/en/news/news-releases/2026/02/05/prime-minister-carney-launches-new-strategy-transform-canadas-auto
- **Tariff impact**: After roughly one year of U.S. auto tariffs, Canadian auto production has fallen from ~3M vehicles in 2000 to ~1.3M in 2025. Source: https://www.wardsauto.com/news/usmca-canada-auto-sector-faces-challenges-2026-tariffs-evs/810028/
- **Supply-chain shift**: February 2026 KPMG survey — 82% of Canadian manufacturers and suppliers adjusting supply chain strategies. Source: https://www.rbc.com/en/economics/canadian-analysis/featured-analysis/insights/tracking-the-impact-of-u-s-tariffs-on-five-targeted-canadian-industries/
- **EV battery plants — status**: Volkswagen St. Thomas ($7B, PowerCo, construction began October 2025, operations 2027); Stellantis NextStar Windsor ($5B, expected online 2026, 2,500 jobs, 450,000 vehicles/year); Honda Alliston ($15B, four plants announced April 2024, postponed May citing "changing conditions"). Source: https://www.theglobeandmail.com/business/article-canada-ev-battery-plants-list-honda-stellantis/
- **China EV tariff shift**: Canada to allow up to 49,000 Chinese-made EVs/year at MFN 6.1% rate rather than 100%. Source: https://www.cnbc.com/2026/02/13/canada-china-autos-evs.html
- **Project activity**: 47 manufacturing records totaling ~$67B in `projects_all.json`.

### SERVICES INDUSTRIES

#### NAICS 41: Wholesale Trade
- **GDP**: -1.2% m/m, -1.7% y/y — both monthly and yearly decline. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Context**: Wholesale weakness aligns with manufacturing contraction (-4.6% y/y) and tariffed goods flows; wholesalers of intermediate industrial goods are exposed to the same U.S. trade friction tracked in the auto strategy above.
- **Project activity**: Wholesale trade is not tracked as a project sector in `projects_all.json`. Signal is GDP-only.

#### NAICS 44-45: Retail Trade
- **GDP**: +0.8% m/m, +2.7% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Retail sales**: StatCan advance estimate — retail sales +0.9% in February 2026 (53.4% response rate, subject to revision). January 2026 revised +1.1% to C$69.7B (down from initial 1.5% estimate). Y/y February retail turnover +1.5%. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260320/dq260320a-eng.htm
- **Project activity**: Retail not tracked as a distinct project sector.

#### NAICS 48-49: Transportation & Warehousing
- **GDP**: -0.7% m/m, +1.6% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Market size**: Canada freight & logistics market — US$116.63B in 2026, projected CAGR 4.45% to US$145.05B by 2031. Source: https://www.mordorintelligence.com/industry-reports/canada-freight-logistics-market-study
- **Modal split**: Road freight held 60.97% of tonnage in 2025. Rail investments include 5,900 new grain hopper cars and extended sidings.
- **Port capacity**: Vancouver vessel wait times approaching four days during January–February export surge periods; multi-year (3-5 year) port on-dock rail and siding extension projects in capex plans. Source: https://www.mordorintelligence.com/industry-reports/canada-freight-logistics-market-study
- **Major operators**: CN, CPKC, TFI International, Canada Post (Purolator), Cargojet.
- **Project activity**: 154 ports/logistics + 82 transport_logistics + 26 transit + 10 transmission pipelines + 6 marine port facilities / projects.

#### NAICS 51: Information & Cultural Industries
- **GDP**: +0.9% m/m, +3.2% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Sovereign AI data centres**: Federal government launched a call for proposals January 15, 2026 for sovereign large-scale AI data centres exceeding 100 MW. Source: https://ised-isde.canada.ca/site/ised/en/enabling-large-scale-sovereign-ai-data-centres
- **Microsoft expansion**: Invest Ontario announced April 8, 2026 — Microsoft AI infrastructure expansion with two new data centres in York Region (Markham and Vaughan) supporting 1,250 jobs. Source: https://yorklink.ca/2026/04/08/invest-ontario-welcomes-microsofts-ai-infrastructure-expansion-in-ontario-supporting-1250-jobs-two-new-data-centres-in-york-region/
- **Bell AI Fabric**: Construction began at 1452 McGill Road for Bell Canada's Bell AI Fabric national AI infrastructure platform (April 9, 2026). Source: https://inside.tru.ca/2026/04/09/tru-community-trust-advances-data-centre-development
- **CRTC broadcasting**: CRTC released action plan February 2026 on Canadian content and technology connectivity; Online Streaming Act (Bill C-11) implementation proceeding. Source: https://www.canada.ca/en/radio-television-telecommunications/news/2026/02/crtc-takes-action-to-connect-canadians-through-technology-and-culture.html
- **Project activity**: 19 telecom records (~$2.9B).

#### NAICS 52: Finance & Insurance
- **GDP**: +0.5% m/m, +3.2% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Q1 2026 bank earnings**: RBC adjusted earnings CAD$5.9B (record), EPS $2.94 vs consensus $2.81. TD Canadian P&C net income $2,044M (+12% y/y). CIBC and National Bank also beat consensus; BMO and Scotiabank met consensus. Source: https://dbrs.morningstar.com/research/476102/large-canadian-banks-q1-2026-earnings-round-up-solid-results-with-manageable-pcl-as-uncertainty-lingers-and-risks-escalate
- **LFS signal**: Finance, insurance, real estate, rental and leasing lost 11,000 jobs in March 2026 — first meaningful monthly decline since November 2023. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Fitch view**: 2026 sector risks include geopolitics, trade tensions, and elevated consumer leverage.
- **Project activity**: No direct project tracking.

#### NAICS 53: Real Estate & Rental/Leasing
- **GDP**: -0.2% m/m, +1.2% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **CRE investment**: CBRE projects Canadian commercial real estate investment of $56B in 2026 — third-highest volume on record, +8% from estimated $47B in 2025. Source: https://www.cbre.ca/press-releases/canadian-commercial-real-estate-investment-could-rise-to-56-billion-dollars-in-2026
- **Office**: CBRE forecasts Toronto vacancy falling to 13.4% (from 15.9%); 1.64M sq ft new supply. Source: https://www.cbre.ca/insights/articles/cbre-outlook-canadian-commercial-real-estate-investment-could-rise-to-56-billion-dollar-in-2026
- **Industrial**: Forecast net absorption >20M sq ft in 2026; CUSMA review scheduled for July 2026 flagged as key sensitivity.
- **Pension/REIT deployment**: ~$15B deployed in 2025 across residential, industrial, retail, healthcare REITs — ~1/3 of total investment market, largest share since 2021.
- **BC housing completions**: Two new West Vancouver rental buildings completed, 51 residential/commercial-mixed BC projects affected. Source: https://news.gov.bc.ca/releases/2026HMA0028-000325
- **Project activity**: 157 residential ($41.8B) + 60 housing + 68 commercial_mixed ($29.8B).

#### NAICS 54: Professional, Scientific & Technical Services
- **GDP**: -0.1% m/m, -0.4% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS March 2026**: +12,000 jobs added in NAICS 54. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Composition**: Legal, accounting, architecture/engineering, surveying/mapping, design, management/technical consulting, scientific R&D, advertising. Source: https://ised-isde.canada.ca/app/ixb/cis/summary-sommaire/54
- **Aging workforce**: ~19% of NAICS 54 workforce over age 55. Source: https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-professional-services
- **Project activity**: Not directly tracked; professional services flow into data centre/AI capex (see NAICS 51) and construction engineering inputs.

#### NAICS 55: Management of Companies & Enterprises
- **GDP**: -4.1% m/m, -21.9% y/y — largest y/y contraction of any NAICS industry in the dataset. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Composition**: Holding companies and head offices that manage subsidiaries. Source: https://www23.statcan.gc.ca/imdb/p3VD.pl?Function=getVD&TVD=1369825&CVD=1369826&CPV=55&CST=27012022&CLV=1&MLV=5
- **Interpretation — flagged for analyst review**: -21.9% y/y is an outlier relative to the rest of the industry set and may reflect head-office restructuring or reclassification effects. No project-level signal available.
- **Project activity**: Not tracked.

#### NAICS 56: Administrative & Waste Management Services
- **GDP**: -0.1% m/m, -0.2% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS signal**: Business, building and other support services (part of NAICS 56) lost 9,500 jobs in March 2026 (-1.4%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Structure**: 52.1% of NAICS 56 establishments are micro (<5 employees), 44.9% small, 2.6% medium. Source: https://ised-isde.canada.ca/app/ixb/cis/businesses-entreprises/56
- **Project activity**: 13 environment / remediation records (~$1.9B).

#### NAICS 61: Educational Services
- **GDP**: +0.5% m/m, -1.9% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **International student cap**: IRCC 2026 cap set at 309,670 study permit application spaces — 7% below 2025 target of 437,000; 16% below 2024 target of 485,000. New international student admissions projected to fall from 305,900 to 155,000 (roughly -50%). Master's/doctoral students at public DLIs exempt from PAL/TAL as of January 1, 2026. Source: https://www.canada.ca/en/immigration-refugees-citizenship/news/notices/2026-provincial-territorial-allocations-under-international-student-cap.html
- **Capital**: BC allocation $3.3B postsecondary, +$600M y/y. McGill redevelopment (former Royal Victoria Hospital site) $870M. University of Victoria 510-bed residence — groundbreak May 2026, revised completion 2034 (from 2029).
- **Project activity**: 151 education records (~$14.7B).

#### NAICS 62: Health Care & Social Assistance
- **GDP**: 0.0% m/m, +2.1% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS signal**: Health care and social assistance +5,000 jobs in March 2026 (+0.2%); +94,000 y/y — the largest y/y growth among all industries. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Ontario LTC**: 147 LTC projects / 23,977 beds completed, under construction, or approved as of March 31, 2025. Target 58,000 new/upgraded beds in two years; ~26,000 beds open, under construction, or approved as of February. Source: https://www.cbc.ca/news/canada/toronto/ontario-budget-healthcare-long-term-care-9.7143637
- **Quebec hospitals**: 2026-27 budget allocates $2.3B for major hospital construction and expansion over 10 years. 38% of Quebec's 594 hospital buildings classified "poor" or "very poor" condition as of early 2026. Source: https://www.cbc.ca/news/canada/montreal/quebec-hospital-projects-doctors-staff-react-9.7138974
- **Project activity**: 230 healthcare records (~$20.5B).

#### NAICS 71: Arts, Entertainment & Recreation
- **GDP**: -0.1% m/m, +2.2% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS signal**: Information, culture and recreation (combined LFS grouping covering parts of NAICS 51/71) +8,800 jobs in March 2026 (+1.0%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Employment base**: 402,100 workers nationwide in 2024. Amusement/gambling/recreation 68%, performing arts/spectator sports 25%, heritage institutions 7%. Source: https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-arts
- **FIFA World Cup 2026**: $150M upgrade to BMO Field ahead of June 2026 matches.
- **Project activity**: 147 tourism_culture records (~$22.3B) including 2 ski resorts, 2 resort developments.

#### NAICS 72: Accommodation & Food Services
- **GDP**: +0.7% m/m, +2.3% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS signal**: Accommodation and food services -10,000 jobs in March 2026 (-0.9%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Employment base**: ~1.9M workers nationwide. 2024 vacancy rate 3.8% (~18,230 unfilled) vs 3.1% all-industry average. Source: https://www.workbc.ca/industry-profile/accommodation-and-food-services
- **Tourism revenue**: Rose from $94B (2022) to $109.5B (2023). Source: https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-accommodation

#### NAICS 81: Other Services (except Public Administration)
- **GDP**: +0.2% m/m, +0.3% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **LFS signal**: Other services (personal, repair, religious, civic organizations) +15,000 jobs in March 2026 — largest single-industry monthly gain. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Composition**: Motor vehicle / equipment repair, personal care, funeral, laundry, pet care, religious and civic organizations. Source: https://www23.statcan.gc.ca/imdb/p3VD.pl?Function=getVD&TVD=1369825&CVD=1369826&CPV=81&CST=27012022&CLV=1&MLV=5&D=1

#### NAICS 91: Public Administration
- **GDP**: -0.1% m/m, +0.7% y/y. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm
- **Federal workforce plan**: Carney government plan targets elimination of ~40,000 public service jobs; Employment and Social Development Canada projected to have 15,629 fewer staff in 2029 vs last year. Source: https://www.cbc.ca/news/canada/ottawa/union-budget-carney-public-service-department-plans-9.7133612
- **Budget**: "Canada Strong" 2025-2026 federal budget — C$280B spending over five years, delivered November 2025 by Finance Minister François-Philippe Champagne. Priorities: defence and capital investment. Source: https://www.canada.ca/en/treasury-board-secretariat/services/planned-government-spending/government-expenditure-plan-main-estimates/2026-27-estimates.html
- **Natural resources employment**: LFS — natural resources sector +10,000 jobs in March 2026. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm
- **Project activity**: 191 government (~$43.8B) + 15 defence (~$119.5B) records. Defence is the largest aggregate-value government project bucket in the database.

---

## 4. Commodity Price Impact Analysis (from `commodities.json`, week ending 2026-04-11)

### Energy
- **Cameco (uranium)**: $160.73, +2.7% week, +2.5% month, +197.6% y/y. Affected sectors: NAICS 21, 22. Affected provinces: SK, ON.
- **Uranium spot (URA ETF)**: $50.96, +4.2% week, -0.8% month, +135.7% y/y. Saskatchewan uranium mine expansion and SMR supply chain exposure.
- **Sprott Physical Uranium Trust**: $27.72, -1.9% week, +2.5% month, +46.7% y/y.
- **WTI 2026 strip**: ~US$57/bbl; **WCS differential**: ~US$12.80/bbl. Source: https://atbcm.atb.com/insights/canadian-upstream-2026-outlook/

### Metals
- **Steel (SLX ETF)**: $98.57, +6.6% week, +6.0% month, +76.3% y/y. Largest weekly move of the tracked commodity basket. Affected sectors: NAICS 23 (Construction), NAICS 48-49 (Transport infrastructure).
- **Nickel (NIKL ETF)**: $28.40, 0.0% week (flat). Affected sectors: NAICS 21 (Mining). Affected provinces: ON, QC, NL, MB.

### Agriculture
- **Nutrien (NTR)**: $102.13, -2.8% week, -4.5% month, +56.5% y/y. Affected sectors: NAICS 11, 21. Affected provinces: SK, AB.

### Equities
- **TSX infrastructure basket**: $56.38, +0.5% week, +2.5% month, +45.2% y/y. Affected sectors: NAICS 22, 48-49.

---

## 5. Major Project Announcements by Sector (this week)

- **LNG Canada / Coastal GasLink Phase 2** (NAICS 21/22/23): new commercial agreements executed end of March 2026; Phase 2 FID late 2026 / early 2027; ~$33B. https://www.tcenergy.com/newsroom/statements/2026/coastal-gaslink-phase-2-advances-step-forward-with-new-commercial-agreements/
- **Microsoft York Region data centres** (NAICS 51/23): April 8, 2026 — two new data centres in Markham and Vaughan; 1,250 jobs. https://yorklink.ca/2026/04/08/invest-ontario-welcomes-microsofts-ai-infrastructure-expansion-in-ontario-supporting-1250-jobs-two-new-data-centres-in-york-region/
- **Bell AI Fabric / TRU data centre** (NAICS 51/23): April 9, 2026 — construction begins on 1452 McGill Road data centre. https://inside.tru.ca/2026/04/09/tru-community-trust-advances-data-centre-development
- **Critical minerals federal package** (NAICS 21): March 2026 — $165.2M for 22 projects, unlocking $434M across 8 provinces. https://www.canada.ca/en/natural-resources-canada/news/2026/03/backgrounder-government-of-canada-invests-to-unlock-canadas-critical-minerals-advantage.html
- **BC West Vancouver rental completions** (NAICS 53): March 27, 2026; two new rental buildings completed. https://news.gov.bc.ca/releases/2026HMA0028-000325

---

## 6. Labour Market by Sector (Statistics Canada Labour Force Survey, March 2026)

Released April 10, 2026. Total +14,000 jobs; unemployment rate 6.7% (unchanged). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm

Gainers: Other services +15,000; Professional/scientific/technical (NAICS 54) +12,000; Natural resources +10,000; Information/culture/recreation +8,800; Health care and social assistance +5,000 (+94,000 y/y).

Decliners: Finance, insurance, real estate, rental and leasing -11,000 (first significant monthly decline since November 2023); Accommodation and food services -10,000 (-0.9%); Business, building, and support services -9,500 (-1.4%).

Secondary source — Indeed Hiring Lab commentary: https://www.hiringlab.org/en-ca/2026/04/10/march-2026-labour-force-survey-holding-steady/

---

## 7. Policy and Regulatory Impacts

- **Softwood lumber** — U.S. DOC preliminary results, seventh administrative review: https://news.gov.bc.ca/releases/2026FOR0011-000394
- **BC housing** — Minister statements March highlights and April 2026 rental report: https://news.gov.bc.ca/releases/2026HMA0042-000398 and https://news.gov.bc.ca/releases/2026HMA0039-000390
- **Federal auto strategy** — PM Carney announcement February 5, 2026: https://www.pm.gc.ca/en/news/news-releases/2026/02/05/prime-minister-carney-launches-new-strategy-transform-canadas-auto
- **Critical minerals** — NRCan March 2026 backgrounder: https://www.canada.ca/en/natural-resources-canada/news/2026/03/backgrounder-government-of-canada-invests-to-unlock-canadas-critical-minerals-advantage.html
- **Sovereign AI data centres** — ISED January 15, 2026 call for proposals: https://ised-isde.canada.ca/site/ised/en/enabling-large-scale-sovereign-ai-data-centres
- **Federal workforce plan** — ~40,000 public service job eliminations under Carney budget plan: https://www.cbc.ca/news/canada/ottawa/union-budget-carney-public-service-department-plans-9.7133612
- **International student cap 2026** — 309,670 application spaces; -7% from 2025: https://www.canada.ca/en/immigration-refugees-citizenship/news/notices/2026-provincial-territorial-allocations-under-international-student-cap.html
- **CRTC broadcasting framework** — February 2026 action plan: https://www.canada.ca/en/radio-television-telecommunications/news/2026/02/crtc-takes-action-to-connect-canadians-through-technology-and-culture.html

---

## 8. Emerging Stories and Cross-Sector Trends

- **AI data centre capex cluster (NAICS 51 + 23 + 22)**: Microsoft York Region, Bell AI Fabric, and the federal sovereign AI data centre call for proposals coincide. Data centres connect to utilities (power demand), construction (build-out), and information services (operations).
- **Critical minerals → manufacturing supply chain (NAICS 21 → 31-33)**: The $72.4B critical minerals pipeline (140 projects 2024-2034) connects to Ontario's Stellantis/VW/Honda EV battery cluster — though Honda's $15B Alliston investment was paused May 2025.
- **LNG sequencing (NAICS 21 + 22 + 23 + 48-49)**: Coastal GasLink Phase 2 and LNG Canada Phase 2 are in commercial-agreement stage; FID late 2026 / early 2027 would cascade through pipeline construction, port handling, and natural gas processing.
- **Softwood lumber support and forestry exposure (NAICS 11 + 31-33)**: >$2.1B in federal + provincial supports in seven months; 66% export dependence with ~90% of exports to U.S. BC, Quebec, and federal programs span BDC loan guarantees, stumpage deferral, and working capital.
- **Public service contraction vs health care expansion (NAICS 91 vs 62)**: ~40,000 planned federal job reductions against +94,000 y/y health care employment growth — largest y/y sector gain in the labour force survey.
- **NAICS 55 anomaly**: Management of companies -21.9% y/y — flagged for analyst review; no supporting project data.

---

## 9. Coverage Gaps and Priorities

- **Lumber timeseries stale 1,065 days** (`data_gap_report.md`). Lumber price signal above sourced externally.
- **NAICS 55 Management of Companies -21.9% y/y**: no supporting project coverage; classification reweighting plausible but unverified this cycle.
- **Procurement and jobs feeds empty for week 2026-04-11**: no weekly contract awards or hiring spikes in `jobs.json` / `procurement.json`. Labour trends above rely on StatCan LFS.
- **Wholesale (NAICS 41) and Management (NAICS 55) and NAICS 81**: GDP-only coverage; no project records in the database (expected for non-project-intensive industries).
- **Provincial CPI / unemployment** stale at 2026-02-01 for 9 of 13 provinces (69 days old — outside 60-day window). Affects labour-market cross-reference precision.

---

## 10. Master Source Registry

[1] https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm — Gross domestic product by industry, January 2026 — Statistics Canada — 2026-03-31
[2] https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm — Labour Force Survey, March 2026 — Statistics Canada — 2026-04-10
[3] https://www150.statcan.gc.ca/n1/daily-quotidien/260320/dq260320a-eng.htm — Retail trade, January 2026 — Statistics Canada — 2026-03-20
[4] https://atbcm.atb.com/insights/canadian-upstream-2026-outlook/ — Canadian Upstream 2026 Outlook — ATB Capital Markets — 2026
[5] https://www.tcenergy.com/newsroom/statements/2026/coastal-gaslink-phase-2-advances-step-forward-with-new-commercial-agreements/ — Coastal GasLink Phase 2 advances step forward — TC Energy — 2026-03
[6] https://www.canada.ca/en/natural-resources-canada/news/2026/03/backgrounder-government-of-canada-invests-to-unlock-canadas-critical-minerals-advantage.html — Critical Minerals Backgrounder — NRCan — 2026-03
[7] https://resourceworld.com/canadian-mining-enters-2026-with-confidence-as-gold-copper-and-critical-minerals-redefine-the-sector/ — Canadian Mining 2026 Outlook — Resource World Magazine — 2026
[8] https://www.torys.com/our-latest-thinking/publications/2026/02/key-trends-in-mining-2026 — Key Trends in Mining 2026 — Torys LLP — 2026-02
[9] https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables — Monthly Housing Starts — CMHC — 2026
[10] https://www.globenewswire.com/news-release/2026/02/25/3244764/28124/en/Canada-Construction-Industry-Report-2025-Output-to-Grow-by-2-6-in-2-6-in-2026-After-2-2-Growth-in-2025-Driven-by-PPI-in-Residential-and-Non-residential-Construction-and-Transport-I.html — Canada Construction Industry Report 2025 — GlobalData / GlobeNewswire — 2026-02-25
[11] https://www.pm.gc.ca/en/news/news-releases/2026/02/05/prime-minister-carney-launches-new-strategy-transform-canadas-auto — PM Carney launches auto strategy — PMO — 2026-02-05
[12] https://www.wardsauto.com/news/usmca-canada-auto-sector-faces-challenges-2026-tariffs-evs/810028/ — Canada's auto sector challenges 2026 — WardsAuto — 2026
[13] https://www.rbc.com/en/economics/canadian-analysis/featured-analysis/insights/tracking-the-impact-of-u-s-tariffs-on-five-targeted-canadian-industries/ — Tracking tariff impact on five Canadian industries — RBC Economics — 2026
[14] https://www.theglobeandmail.com/business/article-canada-ev-battery-plants-list-honda-stellantis/ — Canada EV battery plants list — Globe and Mail — 2026
[15] https://www.cnbc.com/2026/02/13/canada-china-autos-evs.html — Canada China EV tariff shift — CNBC — 2026-02-13
[16] https://uslumbercoalition.org/press-release/canadas-new-softwood-lumber-subsidies-exceed-c2-billion-solely-to-prop-up-canadas-massive-and-harmful-excess-lumber-exports-u-s-lumber-coalition/ — Softwood lumber subsidies >$2.1B — U.S. Lumber Coalition — 2026-04
[17] https://natural-resources.canada.ca/forest-forestry/forest-industry-trade/canada-s-softwood-lumber-industry — Canada's softwood lumber industry — NRCan — 2026
[18] https://news.gov.bc.ca/releases/2026FOR0011-000394 — BC Minister statement on softwood lumber administrative review — BC Government News — 2026-04-09
[19] https://news.gov.bc.ca/releases/2026HMA0042-000398 — BC housing March 2026 highlights — BC Government News — 2026-04-10
[20] https://news.gov.bc.ca/releases/2026HMA0039-000390 — BC April 2026 rental report — BC Government News — 2026-04-09
[21] https://news.gov.bc.ca/releases/2026HMA0028-000325 — West Vancouver rental completions — BC Government News — 2026-03-27
[22] https://world-nuclear.org/information-library/country-profiles/countries-a-f/canada-nuclear-power — Nuclear Power in Canada — World Nuclear Association — 2026
[23] https://smractionplan.ca/ — Canada SMR Action Plan — 2026
[24] https://www.cbre.ca/press-releases/canadian-commercial-real-estate-investment-could-rise-to-56-billion-dollars-in-2026 — CRE Outlook — CBRE Canada — 2026
[25] https://www.cbre.ca/insights/articles/cbre-outlook-canadian-commercial-real-estate-investment-could-rise-to-56-billion-dollar-in-2026 — CRE Outlook detail — CBRE Canada — 2026
[26] https://dbrs.morningstar.com/research/476102/large-canadian-banks-q1-2026-earnings-round-up-solid-results-with-manageable-pcl-as-uncertainty-lingers-and-risks-escalate — Q1 2026 bank earnings round-up — DBRS Morningstar — 2026
[27] https://ised-isde.canada.ca/site/ised/en/enabling-large-scale-sovereign-ai-data-centres — Sovereign AI Data Centres — ISED — 2026-01-15
[28] https://yorklink.ca/2026/04/08/invest-ontario-welcomes-microsofts-ai-infrastructure-expansion-in-ontario-supporting-1250-jobs-two-new-data-centres-in-york-region/ — Microsoft York Region data centres — York Link — 2026-04-08
[29] https://inside.tru.ca/2026/04/09/tru-community-trust-advances-data-centre-development — TRU Community Trust data centre — TRU Newsroom — 2026-04-09
[30] https://www.canada.ca/en/radio-television-telecommunications/news/2026/02/crtc-takes-action-to-connect-canadians-through-technology-and-culture.html — CRTC February 2026 action plan — Canada.ca — 2026-02
[31] https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-professional-services — NAICS 54 Ontario sectoral profile — Job Bank — 2025-2026
[32] https://ised-isde.canada.ca/app/ixb/cis/summary-sommaire/54 — NAICS 54 summary — ISED — 2026
[33] https://www23.statcan.gc.ca/imdb/p3VD.pl?Function=getVD&TVD=1369825&CVD=1369826&CPV=55&CST=27012022&CLV=1&MLV=5 — NAICS 55 classification — Statistics Canada — 2026
[34] https://ised-isde.canada.ca/app/ixb/cis/businesses-entreprises/56 — NAICS 56 business statistics — ISED — 2026
[35] https://www.canada.ca/en/immigration-refugees-citizenship/news/notices/2026-provincial-territorial-allocations-under-international-student-cap.html — 2026 international student cap — IRCC — 2026
[36] https://www.cbc.ca/news/canada/toronto/ontario-budget-healthcare-long-term-care-9.7143637 — Ontario LTC bed progress — CBC News — 2026
[37] https://www.cbc.ca/news/canada/montreal/quebec-hospital-projects-doctors-staff-react-9.7138974 — Quebec hospital budget — CBC News — 2026
[38] https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-arts — NAICS 71 Ontario sectoral profile — Job Bank — 2024-2026
[39] https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-accommodation — NAICS 72 Ontario sectoral profile — Job Bank — 2024-2026
[40] https://www.workbc.ca/industry-profile/accommodation-and-food-services — NAICS 72 BC profile — WorkBC — 2026
[41] https://www23.statcan.gc.ca/imdb/p3VD.pl?Function=getVD&TVD=1369825&CVD=1369826&CPV=81&CST=27012022&CLV=1&MLV=5&D=1 — NAICS 81 definitions — Statistics Canada — 2026
[42] https://www.canada.ca/en/treasury-board-secretariat/services/planned-government-spending/government-expenditure-plan-main-estimates/2026-27-estimates.html — 2026-27 Main Estimates — Treasury Board Secretariat — 2026
[43] https://www.cbc.ca/news/canada/ottawa/union-budget-carney-public-service-department-plans-9.7133612 — Federal department plans / public service cuts — CBC News — 2026
[44] https://www.mordorintelligence.com/industry-reports/canada-freight-logistics-market-study — Canada Freight & Logistics Market — Mordor Intelligence — 2026
[45] https://www.hiringlab.org/en-ca/2026/04/10/march-2026-labour-force-survey-holding-steady/ — March 2026 LFS commentary — Indeed Hiring Lab — 2026-04-10
