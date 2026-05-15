# Provincial Research — Week of 2026-05-15
Generated: 2026-05-15
Provinces covered: All 13 provinces + 3 territories (16 total). Note: Canada's provinces number 10; "13 provinces" in the pipeline schema denotes the 10 provinces + 3 territories. All 13 jurisdictions + National are covered below.
Agent: 1B (tldr-researcher-provincial)
Search waves: Wave 3 (provincial scan, 13 searches) + policy + projects + IAAC + procurement + labour
Source of truth: indicators.json (refreshed 2026-05-15). briefing_latest.json is the prior edition (2026-04-19) and is NOT cited for metrics, per data_gap_report.md.

---

## 1. Data Quality Audit

### Provincial Indicator Coverage (from indicators.json snapshot array, 253 entries)
| Region | Indicators | Projects | Latest Indicator Period | Status |
|--------|-----------|----------|--------------------------|--------|
| National | 118 | n/a | 2026-05-15 (LFS Apr, CPI Mar) | OK |
| ON | 20 (6 core + 14 econ-account) | 728 | 2026-05-15; econ accounts Q3 2025 | OK (provincial accounts source-lagged) |
| QC | 39 (6 core + 33 ISQ series) | 520 | 2026-05-15; ISQ sub-series Feb–Mar 2026; accounts Q3 2025 | OK (ISQ source lag) |
| AB | 6 | 733 | 2026-05-15 | OK |
| BC | 6 | 694 | 2026-05-15 | OK |
| SK | 6 | 216 | 2026-05-15 | OK |
| MB | 6 | 2,054 | 2026-05-15 | OK |
| NS | 6 | 339 | 2026-05-15 | OK |
| NB | 6 | 198 | 2026-05-15 | OK |
| NL | 6 | 1,561 | 2026-05-15 | OK |
| PE | 6 | 82 | 2026-05-15 | OK |
| YT | 4 | 123 | 2026-05-15 (GDP 2024) | OK (CPI/housing starts not published for territories — expected) |
| NT | 4 | 182 | 2026-05-15 (GDP 2024) | OK (same territorial limitation) |
| NU | 4 | 47 | 2026-05-15 (GDP 2024) | OK (same territorial limitation) |
| CA (cross-jurisdiction) | n/a | 3 | 2026-05-15 | OK (multi-province federal items) |

### Critical Gaps Found (per data_gap_report.md, 2026-05-15)
- **No blocking gaps.** Overall freshness grade: B.
- QC/ON quarterly provincial economic accounts (on_exports, on_imports, on_gdp_goods, on_real_capital_investment, on_real_consumption, on_real_household, qc_real_gdp, qc_exports, qc_imports, qc_business_investment) last period Q3 2025 (2025-10-01). This is source-side release lag (ISQ / Ontario Ministry of Finance multi-month lag), not a pipeline failure. Frame as "most recent available (Q3 2025)."
- QC monthly ISQ sub-series (qc_bldg_permits_res/nonres, qc_intl_exports/imports, qc_retail_sales) last period 2026-02-01; qc_manufacturing_sales, qc_housing_starts last 2026-03-01 — ISQ longer-than-StatCan lag, latest available.
- Pipeline signal files (signals.json, procurement.json) returned **0 job-spike and 0 procurement contract entries** for week 2026-05-15. Procurement awards section below relies on project-database status changes and policy.json, not the empty signals feed. Documented as a coverage gap for this run.
- Uranium and canola have no timeseries series (markets-tab gap, not provincial).

---

## 2. Provincial Spotlights (ALL 13 JURISDICTIONS + 3 TERRITORIES + NATIONAL)

### National (context for provincial reading)
- **Key indicators (indicators.json, 2026-05-15):** unemployment 6.9% (April 2026 LFS, StatCan released May 8, +0.2pp from March); CPI +2.4% YoY (March 2026, StatCan released Apr 20); real GDP -0.6%; employment rate 60.5%; participation rate 65.0%; housing starts 279,317 SAAR (CMHC); BoC overnight rate 2.25% (set 2026-03-05); prime rate 6.09%; wage growth +3.9% (SEPH, Feb 2026).
- **National LFS detail (StatCan The Daily, April 2026):** national rate up 0.2pp to 6.9%; employment fell in Quebec (-43,000; -0.9%), Newfoundland and Labrador (-5,200; -2.1%), Saskatchewan (-4,000; -0.6%), New Brunswick (-2,700; -0.7%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm
- **National policy (policy.json, week 2026-04-19):** federal items in scope — U.S. Section 232 tariff restructuring to 50% duties (affects 520 tracked projects in manufacturing/mining/oil_gas; https://www.canada.ca/en/department-finance/news/2026/04/canada-responds-to-us-tariff-actions.html); Build Communities Strong Fund $51B (2,196 projects, infrastructure/transport; https://www.infrastructure.gc.ca/plan/build-communities-strong-eng.html); Critical Minerals Alliance Round 2 $12.1B (421 mining projects; https://www.canada.ca/en/natural-resources-canada/news/2026/03/critical-minerals-alliance.html); Canadian Sovereign AI Compute Strategy $1.7B+ (17 projects; https://ised-isde.canada.ca/site/ai-strategy/en).

### Ontario
- **Top story:** Honda indefinitely suspended its $15B Ontario EV and battery investment (Alliston). The pipeline tracks five related Honda ON project records (~$15B each as first-tracked entries this week). Honda stated the suspension does not affect current Alliston employment or Civic/CR-V production; the proposed EV facility had been projected at ~1,000 incremental jobs and was tied to up to $5B pledged federal/Ontario funding not yet disbursed. Source: https://www.cbc.ca/news/business/honda-ev-plant-ontario-9.7190021 ; https://www.electrive.com/2026/05/11/honda-to-withdraw-from-canada-projects/
- **Key indicators (indicators.json):** unemployment 7.5%; CPI +2.9% YoY; employment rate 59.9%; participation rate 64.8%; GDP +1.2%; housing starts 62,735. Provincial accounts (Q3 2025, latest available): exports $638,705M (+4.3%), imports $610,076M (+1.2%), goods GDP $177,899M (-1.5%), real capital investment $189,358M (0.0%), real consumption $781,588M (+0.6%). Ontario Budget 2026 projects provincial unemployment 7.7% (2025) → 7.4% (2026); real GDP avg 1.4%/yr 2025–2028; deficit $12.3B 2025-26. Source: https://budget.ontario.ca/2026/chapter-1b-economy.html ; https://www.rbc.com/en/economics/canadian-analysis/provincial-and-fiscal-outlooks/provincial-budgets-and-economic-statements/ontario-budget-2026-delayed-path-to-balance/
- **Project activity:** 728 projects, ~$360B pipeline (top sector: infrastructure); 233 records updated since 2026-05-08. Notable status changes: Agnico Eagle Northeastern Ontario Mining Expansion ($14B) Proposed→Approved; Detour Lake Underground Mine ($2B) first tracked; Toronto Pearson International Airport Redevelopment ($3B) first tracked; Ontario Correctional Capacity Expansion — 2,500 Beds ($3B) first tracked.
- **Policy developments:** Ontario Budget 2026 — $210B ten-year capital plan, $111.3B infrastructure 2025-26 to 2027-28 (+$13.6B vs 2025 FES, incl. +$11.0B transit), $31B roads/highways (policy.json week 2026-04-19; affects 412 tracked projects). Source: https://budget.ontario.ca/2026/index.html ; https://budget.ontario.ca/2026/chapter-2.html
- **Labour trends:** Ontario added 80,900 net jobs in 2025; 2026 softer on slower growth and reduced population growth from federal immigration changes (Ontario Budget 2026). Source: https://budget.ontario.ca/2026/chapter-1b-economy.html
- **IAAC status (iaac.json):** 26 ON projects in registry, most-recent update 2026-05-15. Under Review entries include: Repave Various Roads, Garrison Petawawa (Infrastructure); Michipicoten First Nation Construction of Two Residential Multiplexes (Housing); Royal Military College Turf Fields — CFB Kingston (Education).
- **Procurement:** No contract entries in signals.json/procurement.json for week 2026-05-15 (pipeline returned empty set — coverage gap). Project-database proxy: Agnico Eagle ON expansion advanced Proposed→Approved.

### Quebec
- **Top story:** Quebec employment fell 43,300 in April 2026 (-0.9%), cumulative loss ~87,000 jobs over the first four months of 2026; unemployment rose to 6.2%. Nearly half of the 87,000 losses concentrated in construction and manufacturing; about one quarter in financial services. Source: https://www.desjardins.com/en/savings-investment/economic-studies/quebec-employment-8-may-2026.html ; https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm
- **Key indicators (indicators.json):** unemployment 6.2% (qc_unemployment_rate 6.2%, Apr 2026); CPI -0.4% YoY; employment rate 60.4%; participation rate 64.4%; GDP +1.3%; housing starts 53,461; qc_employment 4,579.0K; qc_labour_force 4,882.3K; qc_weekly_earnings $1,280.65 (Feb 2026); qc_manufacturing_sales $228,889M (Mar 2026); qc_retail_sales $193,069.88M (Feb 2026). Provincial accounts (Q3 2025, latest available): qc_real_gdp $486,872.74M (-0.1%), qc_nominal_gdp $652,636M, qc_exports $208,930M (+0.2%), qc_business_investment $78,776.36M (+0.3%).
- **Project activity:** 520 projects, ~$78.4B (top sector: education); 91 records updated since 2026-05-08.
- **Policy developments:** Quebec Budget 2026-27 — $167B infrastructure plan (policy.json week 2026-04-19; affects 289 tracked projects). Quebec Infrastructure Plan 2025–2035 cited at a record $164B over 10 years (Port of Montreal Contrecœur expansion; REM northern/western branches; blue line extension). Telesat Lightspeed project: $1.8B invested, 600 jobs in Québec. Source: https://www.budget.finances.gouv.qc.ca/budget/2026-2027/index.asp ; https://www.quebec.ca/en/news/actualites/detail/18-billion-invested-and-600-jobs-created-in-quebec-by-the-telesat-lightspeed-project ; https://capitalhillgroup.ca/quebecs-new-economic-vision-2025-2026/
- **Labour trends:** Montréal International guided 54 projects in 2025 ($2.628B, 3,720 jobs) in defence/aerospace, life sciences, cleantech, IT/AI. Source: https://www.canada.ca/en/economic-development-quebec-regions/news/2026/03/government-of-canada-invests-7-million-to-attract-international-investments-with-montreal-international.html
- **IAAC status (iaac.json):** 12 QC projects; Under Review 2026-05-15 includes Replacement of the LL2367 navigation aid at Longue Pointe, Traverse (Other).
- **Procurement:** No signals.json entries (empty set this run).

### Alberta
- **Top story:** ATB raised Alberta 2026 real GDP forecast to 2.7% (from 2.1% in December) and nominal GDP to +6% (from +0.7%), on higher oil prices; WTI 2026 forecast lifted to ~US$75/bbl. A separate report projects Alberta's fiscal position could move from a ~$9.4B deficit to a ~$6B surplus if high oil prices are sustained. Source: https://www.cbc.ca/news/canada/edmonton/atb-alberta-oil-gas-economy-forecast-9.7143848 ; https://www.bnnbloomberg.ca/business/2026/05/13/high-oil-prices-could-turn-94b-alberta-deficit-into-6b-surplus-report/
- **Key indicators (indicators.json):** unemployment 7.0%; CPI +1.3% YoY; employment rate 64.4%; participation rate 69.2%; GDP +2.7%; housing starts 46,064. Non-residential construction investment cited +22% YoY; residential -10%, starts easing from ~65,000 (2025) to ~47,000. Youth unemployment ~14.4%. Source: https://businesscouncilab.com/advocacy-category/statements-advocacy/spring-economic-snapshot-2026/
- **Project activity:** 733 projects, ~$346.9B (top sector: government); 78 records updated since 2026-05-08. Notable: Olds AI Data Centre Hub — Alberta ($50B) first tracked; Enbridge Sunrise Natural Gas Pipeline Expansion ($4B) first tracked.
- **Policy developments:** Canada–Alberta Co-operation Agreement on environmental and impact assessment (signed Apr 2, 2026; max two-year assessment timeline). Source: https://www.canada.ca/en/impact-assessment-agency/news/2026/04/alberta-and-canada-sign-co-operation-agreement-to-accelerate-major-project-assessments.html
- **Labour trends:** ~85,000 jobs added over the prior year (per spring snapshot); unemployment 7.0% per indicators.json, in line with national.
- **IAAC status (iaac.json):** 17 AB projects. Flipi Gas-Fired Generation Project (Energy, TransAlta, 460 MW near Rimbey) → Approved 2026-05-15 (IAAC early decision, 64-day review). Kainai Interconnect Project, Goodstoney Aggregate Pit Expansion, Chipewyan Prairie Subdivision Phase 5, Lubicon Summerland Road → Under Review 2026-05-15. Source: https://www.canada.ca/en/impact-assessment-agency/news/2026/04/government-of-canada-provides-early-decision-on-flipi-gas-fired-generation-project-in-alberta.html
- **Procurement:** No signals.json entries (empty set this run).

### British Columbia
- **Top story:** B.C. Budget 2026 includes $3M to support mineral permitting improvements and introduces fixed timelines for mineral exploration permits (a Canadian first — applications processed in as little as 40 days), building on prior major-mine review timeline reductions of ~35%. B.C. is Canada's largest copper producer and only molybdenum producer. Source: https://www.canadianminingjournal.com/featured-article/british-columbias-mining-month-2026-mining-investment-creating-jobs-building-british-columbias-economy/
- **Key indicators (indicators.json):** unemployment 6.8% (below national 6.9%); CPI +2.0% YoY; employment rate 60.0%; participation rate 64.4%; GDP +1.2%; housing starts 40,133. Source: https://news.gov.bc.ca/releases/2026FIN0019-000513
- **Project activity:** 694 projects, ~$511.3B (largest provincial pipeline value); 172 records updated since 2026-05-08. Notable first-tracked: TELUS AI Data Centre Expansion — B.C. ($9B); Surrey Langley SkyTrain Extension ($6B); BC Hydro Wind Energy Program — Four New Renewable Projects ($4.3B); Tilbury Island LNG Expansion ($3B).
- **Policy developments (policy.json week 2026-05-15):** "Strong response to 2025 call for power, delivering clean, affordable energy" (BC Government, provincial, energy_transition; affects 137 tracked projects across mining/oil_gas/power_energy; https://news.gov.bc.ca/releases/2026ECS0014-000552); "Advancing made-in-B.C. health technology to strengthen patient care" (https://news.gov.bc.ca/releases/2026JEG0036-000550); FIFA World Cup 2026 ticket donation program (https://news.gov.bc.ca/releases/2026TACS0025-000556). Prior week (2026-04-19): "Accelerating short-term rental opt-out process" (housing; 51 projects; https://news.gov.bc.ca/releases/2026HMA0045-000428).
- **Labour trends:** Mining-sector job creation emphasized in BC Mining Month 2026 messaging; specific labour figures not published in source.
- **IAAC status (iaac.json):** 17 BC projects. Multiple Under Review 2026-05-15: Sts'ailes Nation Subdivision/Water/Wastewater upgrades; Amrize Pitt River Quarry Maintenance Dredging; Degnen Bay Small Craft Harbour Remediation; New Fibre Installation — Nuchatlaht / Kingcome (Telecommunications); CFAD Rocky Point RP138 Remediation.
- **Procurement:** No signals.json entries (empty set this run).

### Saskatchewan
- **Top story:** Saskatchewan's mining sector generated >$12.8B in mineral sales in 2025 (+19% vs 2024). Potash sales +18% to $9.3B; uranium sales +24% to $3.2B (industry record). Mining employs >20,000 directly/via contractors, with >$3B annual procurement from Saskatchewan businesses. Source: https://www.saskatchewan.ca/government/news-and-media/2026/may/07/saskatchewan-mining-sector-delivering-strong-results-and-a-bright-future
- **Key indicators (indicators.json):** unemployment 5.6% (second-lowest among provinces, below national 6.9%); CPI +2.3% YoY; employment rate 63.3%; participation rate 67.1%; GDP +3.4%; housing starts 4,472. April LFS: employment -4,000 (-0.6%). Real GDP growth cited ~3.1% (2025) and 3.6% (2026). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm ; https://globalnews.ca/news/10395277/saskatchewan-economy-growth-mining-industry-investment-deloitte-canada/
- **Project activity:** 216 projects, ~$30.1B; 93 records updated since 2026-05-08. Notable first-tracked: Bell AI Fabric 300 MW Data Centre — Rural Municipality of Sherwood ($1.7B).
- **Policy developments:** No new Saskatchewan-specific policy items in policy.json recent weeks; mining-sector results release (May 7) is informational.
- **Labour trends:** Potash, oil, and uranium roles pay 20–40% above equivalent roles; average provincial salary ~$65,300 (2026). Source: https://www.universitymagazine.ca/average-salary-in-saskatchewan-2026
- **IAAC status (iaac.json):** 6 SK projects. Under Review 2026-05-15: Muscowpetung Saulteaux Nation Solid Waste Transfer Station; Blanket Permit — SaskEnergy — Northern Lights IR No. 220; Blanket Permit — SaskEnergy — Gasification of Sakimay.
- **Procurement:** No signals.json entries (empty set this run).

### Manitoba
- **Top story:** Manitoba Budget 2026 — largest-ever capital budget at $3.8B this year, $4.3B/yr average over five years; $21.6B infrastructure over five years ($9.5B via crown agencies incl. Manitoba Hydro). Includes $262.5M federal/provincial over five years for Arctic Gateway Group (Port of Churchill, Hudson Bay rail) plus a $10M Churchill Catalyst Fund. Source: https://news.gov.mb.ca/news/index.html?item=73198 ; https://www.gov.mb.ca/asset_library/en/budget2026/budget2026.pdf
- **Key indicators (indicators.json):** unemployment 5.0% (lowest among provinces); CPI +3.3% YoY (highest provincial CPI ex-PE); employment rate 63.1%; participation rate 66.5%; GDP +1.1%; housing starts 7,361.
- **Project activity:** 2,054 projects (largest provincial count in database), ~$6.7B; 31 records updated since 2026-05-08.
- **Policy developments:** Budget 2026 capital plan as above; commitment to train 40% more apprentices in skilled trades; 4,054 net new health-care staff. Source: https://www.gov.mb.ca/budget2026/index.html
- **Labour trends:** Budget messaging cites wages outpacing inflation and steady employment growth; specific LFS provincial figure not separately reported in source.
- **IAAC status (iaac.json):** 6 MB projects. Under Review 2026-05-15: Potential Regional Assessment of the Trans-Canada Highway Improvement Project; 2026 Airfield Improvements Project.
- **Procurement:** No signals.json entries (empty set this run).

### Nova Scotia
- **Top story:** Nova Scotia advancing offshore wind: first call for bids in 2026 for up to 5 GW, with subsequent calls for up to 10 GW more; a 2.5 GW call managed by the Canada–Nova Scotia Offshore Energy Regulator (prequalification launched Oct 2025). Premier Houston's Wind West Strategic Plan describes a $60B plan for 5 GW. >50 companies active in aligned supply-chain sectors. Source: https://novascotia.ca/offshore-wind/ ; https://www.cbc.ca/news/canada/nova-scotia/offshore-wind-projects-9.7135261
- **Key indicators (indicators.json):** unemployment 6.3%; CPI +1.7% YoY; employment rate 57.4%; participation rate 61.3%; GDP +2.7%; housing starts 7,241.
- **Project activity:** 339 projects, ~$13B; 46 records updated since 2026-05-08.
- **Policy developments:** Nova Scotia Powering the Economy Act (policy.json week 2026-04-19; power_energy; affects 45 tracked projects). Source: https://novascotia.ca/news/release/?id=20260409002 ; https://news.novascotia.ca/en/2026/02/24/province-introduces-legislation-power-economy
- **Labour trends:** No NS-specific job-spike data in signals.json (empty set). Offshore wind supply-chain teaming agreement (Riggs Distler, Smulders, Cherubini Bridges) cited as fabrication capacity build-out.
- **IAAC status (iaac.json):** 8 NS projects. Under Review 2026-05-15: Regional Assessment of Oil and Gas Exploratory Drilling in the Canada–Nova Scotia Offshore Area (Energy); Marshdale Natural Gas Power Generation Facility Project (Energy).
- **Procurement:** No signals.json entries (empty set this run).

### New Brunswick
- **Top story:** New Brunswick launched an economic development strategy targeting 10% economic growth by 2030 (critical minerals, trade corridors/ports, energy capacity, interprovincial trade). 2026-27 budget tabled Mar 17, 2026 — no new taxes, anticipated deficit CA$1.39B. Opportunities NB providing up to $54.3M over three years for company modernization. Source: https://www.gnb.ca/en/news/n-b.2026.04.government-launches-economic-development-strategy.html ; https://www.mnp.ca/en/insights/directory/2026-new-brunswick-budget-highlights
- **Key indicators (indicators.json):** unemployment 7.2%; CPI +1.0% YoY (lowest provincial CPI); employment rate 56.3%; participation rate 60.6%; GDP +1.8%; housing starts 5,860. April LFS: employment -2,700 (-0.7%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm
- **Project activity:** 198 projects, ~$7.1B; 32 records updated since 2026-05-08.
- **Policy developments:** Energy plan — +600 MW SMR at Point Lepreau by 2035; +1,400 MW wind, +200 MW grid-scale solar, +300 MW behind-the-meter solar; up to $25M via Smart Renewables and Electrification Pathways for the Neweg Wind Project. Source: https://www2.gnb.ca/content/gnb/en/corporate/promo/clean-energy.html
- **Labour trends:** Strategy targets +3.3% labour productivity, +16.8% private-sector capital investment, +3.9% export volume by 2030.
- **IAAC status (iaac.json):** 5 NB projects. Under Review 2026-05-15: Repair Parking Lot K-4 Compound — 5th Canadian Division Support Base Gagetown (Ports & Logistics).
- **Procurement:** No signals.json entries. Cross-jurisdiction Small Craft Harbours Program — National Infrastructure Renewal ($958M) records first tracked across NB/NL/CA.

### Newfoundland and Labrador
- **Top story:** Equinor submitted the Bay du Nord development application to Newfoundland and Labrador's energy regulator in early May 2026. The March 2026 provincial agreement with Equinor and BP provides up to $6.4B in direct provincial revenue in phase one; project investment ~$14B; ~430M barrels recoverable; sanction targeted 2027, first oil ~2031. Offshore oil/gas sustains ~20,000 jobs, ~20% of provincial GDP, ~55% of exports. Source: https://www.cbc.ca/news/canada/newfoundland-labrador/equinor-bay-du-nord-development-application-9.7188650 ; https://www.gov.nl.ca/releases/2026/exec/0303n05/
- **Key indicators (indicators.json):** unemployment 10.0% (highest provincial); CPI +2.3% YoY; employment rate 51.6% (lowest provincial); participation rate 57.3%; GDP +2.4%; housing starts 1,242. April LFS: employment -5,200 (-2.1%). Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm
- **Project activity:** 1,561 projects, ~$25.8B; 54 records updated since 2026-05-08. Small Craft Harbours Program — 2026 Spring Economic Update Investment ($958M) first tracked.
- **Policy developments:** NL Budget boosts offshore exploration funding (worldoil.com, Apr 30, 2026). Bay du Nord life-of-field benefits/royalties/equity-option agreement. Source: https://worldoil.com/news/2026/4/30/newfoundland-and-labrador-budget-boosts-offshore-exploration-funding/ ; https://www.gov.nl.ca/releases/2026/exec/0304n02/
- **Labour trends:** Largest single-month percentage employment decline among provinces in April 2026 (-2.1%).
- **IAAC status (iaac.json):** 3 NL projects. Under Review 2026-05-15: Chapel's Cove Breakwater Mitigation Project (Water & Wastewater); Main Beach Armour Stone (Other).
- **Procurement:** No signals.json entries (empty set this run).

### Prince Edward Island
- **Top story:** PEI 2026 budget tabled Apr 14, 2026 — five-year capital plan totaling $1.6B in infrastructure; FY2026/27 deficit pegged at $409.9M (~3.5% of GDP); new personal income tax bracket above $200,000 and increased non-resident property taxes. Nominal GDP assumed +4% (2026/2027); real GDP +2% (2026/2027), down from ~2.4% (2025). Source: https://www.princeedwardisland.ca/en/information/finance-and-affordability/budget-address-2026 ; https://www.scotiabank.com/ca/en/about/economics/economics-publications/post.other-publications.fiscal-policy.fiscal-pulse.provincial-budget-analyses-and-updates.prince-edward-island-.prince-edward-island-2026-27-budget--april-14--2026-.html
- **Key indicators (indicators.json):** unemployment 8.0%; CPI +4.0% YoY (highest provincial CPI); employment rate 61.2%; participation rate 66.5%; GDP +3.6% (highest provincial GDP growth); housing starts 1,153.
- **Project activity:** 82 projects, ~$1.5B (top sector: infrastructure); 4 records updated since 2026-05-08.
- **Policy developments:** Budget 2026 — health care, affordability, energy security focus; capital plan as above.
- **Labour trends:** No PE-specific job-spike data in signals.json (empty set).
- **IAAC status (iaac.json):** 2 PE projects in registry; no status changes flagged this week beyond the 2026-05-15 sweep timestamp.
- **Procurement:** No signals.json entries (empty set this run).

### Yukon
- **Top story:** Yukon tabled a $2.46B 2026-27 budget ($2.07B operations, $385M capital) with an $81.8M deficit. Capital spending down as Nisutlin Bay Bridge replacement and Whitehorse airport runway projects wind down; Energy/Mines/Resources and Highways/Public Works budgets cut. Canada–Yukon Workforce Tariff Response: $1.5M over three years for tariff-affected construction, transportation, and mining workers/employers. Source: https://www.cbc.ca/news/canada/north/yukon-party-government-budget-2026-27-9.7134152 ; https://yukon.ca/en/news/budget-2026-begins-road-fiscal-recovery ; https://www.canada.ca/en/employment-social-development/news/2026/05/governments-of-canada-and-yukon-partner-to-support-tariff-impacted-workers-and-strengthen-workforce.html
- **Key indicators (indicators.json):** unemployment 5.3%; employment rate 71.2% (highest among all jurisdictions); participation rate 75.2%; GDP -3.3% (period 2024-01-01, latest available — CPI and housing starts not published by StatCan for territories, expected limitation).
- **Project activity:** 123 projects, ~$46.4B (top sector: infrastructure); 27 records updated since 2026-05-08.
- **Policy developments:** Budget 2026 prioritizes energy-grid affordability/reliability, health care, housing, education, public safety.
- **Labour trends:** Economic outlook cites modest growth on strong metal prices and higher placer gold production; tariff-response workforce funding as above.
- **IAAC status (iaac.json):** No YT projects in the 102-record IAAC dataset.
- **Procurement:** No signals.json entries (empty set this run).

### Northwest Territories
- **Top story:** Diamond industry contracting — Rio Tinto plans to close Diavik in March 2026 (ore reserves exhausted); Gahcho Kué (De Beers / Mountain Province) continues to 2031. The three operating mines directly/indirectly employ >1,500 residents and account for ~one-fifth of NWT GDP. GNWT released a geological assessment of 1,721 mineral showings spanning 19 critical minerals (lithium, cobalt, copper, zinc) as a diversification path; commercial attractiveness contingent on substantially higher prices. Source: https://www.bnnbloomberg.ca/tariffs/2026/01/01/northwest-territories-facing-a-hard-as-diamonds-reality-as-pivotal-industry-wanes/ ; https://www.miningnewsnorth.com/story/2026/03/06/news/nwt-study-maps-critical-minerals-potential/9572.html
- **Key indicators (indicators.json):** unemployment 6.8%; employment rate 66.1%; participation rate 70.9%; GDP -1.1% (period 2024-01-01, latest available; CPI/housing starts not published for territories).
- **Project activity:** 182 projects, ~$40.1B (top sector: infrastructure); 8 records updated since 2026-05-08.
- **Policy developments:** Critical-minerals geoscience assessment release (Mar 2026) as above; no NT-specific policy.json item this week.
- **Labour trends:** Diavik closure (Mar 2026) removes a portion of the >1,500 diamond-sector jobs; no specific replacement figure published.
- **IAAC status (iaac.json):** No NT projects in the 102-record IAAC dataset.
- **Procurement:** No signals.json entries (empty set this run).

### Nunavut
- **Top story:** PM Carney referred the Grays Bay Road and Port project (deepwater export terminal + airstrip, dual-use civilian/military) to the Major Projects Office on Mar 12, 2026. CanNor announced >$13M for four Nunavut projects in April 2026, including $4.5M to West Kitikmeot Resources Corp. for Grays Bay environmental/feasibility studies, $4.5M to Sedna ROV, and $1.1M for an Iqaluit economic-development hub. Canada–Nunavut joint funding of $2.45M for foundational geoscience/critical-mineral research on south/central Baffin Island. Source: https://www.canada.ca/en/northern-economic-development/news/2026/04/the-government-of-canada-invests-in-projects-to-strengthen-nunavuts-economy-infrastructure-and-arctic-security.html ; https://nunavutnews.com/2026/04/22/federal-government-commits-up-to-13-million-for-four-nunavut-projects/
- **Key indicators (indicators.json):** unemployment 12.0% (highest among all jurisdictions); employment rate 55.0% (lowest among all jurisdictions); participation rate 62.5%; GDP +7.5% (period 2024-01-01, latest available; CPI/housing starts not published for territories).
- **Project activity:** 47 projects, ~$2B (top sector: infrastructure); 10 records updated since 2026-05-08.
- **Policy developments:** Grays Bay Major Projects Office referral; CanNor funding package as above.
- **Labour trends:** No NU-specific job-spike data in signals.json (empty set).
- **IAAC status (iaac.json):** No NU projects in the 102-record IAAC dataset.
- **Procurement:** No signals.json entries; CanNor funding (project-grant proxy) documented above.

---

## 3. Policy Developments Summary

### Budgets and Fiscal Announcements
- Ontario Budget 2026 — $210B ten-year capital plan; $111.3B infrastructure 2025-26 to 2027-28 (+$13.6B; +$11.0B transit); deficit $12.3B 2025-26. https://budget.ontario.ca/2026/index.html
- Quebec Budget 2026-27 — $167B infrastructure plan (policy.json); Quebec Infrastructure Plan 2025–2035 record $164B/10yr. https://www.budget.finances.gouv.qc.ca/budget/2026-2027/index.asp
- Manitoba Budget 2026 — $3.8B largest-ever capital budget; $21.6B/5yr infrastructure. https://www.gov.mb.ca/budget2026/index.html
- New Brunswick Budget 2026-27 — tabled Mar 17, 2026; CA$1.39B deficit; no new taxes. https://www.mnp.ca/en/insights/directory/2026-new-brunswick-budget-highlights
- PEI Budget 2026-27 — tabled Apr 14, 2026; $1.6B/5yr capital plan; $409.9M deficit. https://www.princeedwardisland.ca/en/information/finance-and-affordability/budget-address-2026
- Yukon Budget 2026-27 — $2.46B; $81.8M deficit. https://yukon.ca/en/news/budget-2026-begins-road-fiscal-recovery

### Legislation and Regulation
- Nova Scotia Powering the Economy Act (power_energy; 45 tracked projects). https://novascotia.ca/news/release/?id=20260409002
- Federal S-212 (45-1) National Strategy for Children and Youth Act — placed in Order of Precedence Mar 12, 2026 (policy.json, federal, capital_investment). https://www.parl.ca/legisinfo/en/bill/45-1/S-212
- B.C. — accelerating short-term rental opt-out process (housing; 51 projects). https://news.gov.bc.ca/releases/2026HMA0045-000428
- Canada–Alberta Co-operation Agreement on environmental/impact assessment (max 2-year timeline). https://www.canada.ca/en/impact-assessment-agency/news/2026/04/alberta-and-canada-sign-co-operation-agreement-to-accelerate-major-project-assessments.html

### Major Policy Shifts
- U.S. Section 232 tariff restructuring to 50% duties — 520 tracked projects (manufacturing/mining/oil_gas). https://www.canada.ca/en/department-finance/news/2026/04/canada-responds-to-us-tariff-actions.html
- Build Communities Strong Fund $51B — 2,196 tracked projects. https://www.infrastructure.gc.ca/plan/build-communities-strong-eng.html
- Critical Minerals Alliance Round 2 $12.1B — 421 tracked projects. https://www.canada.ca/en/natural-resources-canada/news/2026/03/critical-minerals-alliance.html
- B.C. 2025 call for power response (energy_transition; 137 tracked projects). https://news.gov.bc.ca/releases/2026ECS0014-000552

---

## 4. Capital Projects by Province

### New Projects Discovered / First Tracked This Week (notable, value-tagged)
- AB: Olds AI Data Centre Hub ($50B); Enbridge Sunrise Natural Gas Pipeline Expansion ($4B)
- ON: Honda EV/battery records (5 entries, ~$15B each — project indefinitely suspended per CBC); Agnico Eagle ON gold mining capital records ($10–14B); Detour Lake Underground Mine ($2B); Toronto Pearson Redevelopment ($3B); Ontario Correctional Capacity Expansion 2,500 Beds ($3B)
- BC: TELUS AI Data Centre Expansion ($9B); Surrey Langley SkyTrain Extension ($6B); BC Hydro Wind Energy Program — 4 projects ($4.3B); Tilbury Island LNG Expansion ($3B)
- SK: Bell AI Fabric 300 MW Data Centre — RM of Sherwood ($1.7B)
- NL/NB/CA: Small Craft Harbours Program — Spring Economic Update 2026 ($958M, cross-jurisdiction)

### Status Changes
- ON: Agnico Eagle Northeastern Ontario Mining Expansion ($14B) — Proposed → Approved
- BC: North Shore Wastewater Treatment Plant — Under Construction → Complete (Metro Vancouver; ACCIONA legal settlement, independent review proceeding)
- 882 project records updated (lastUpdated ≥ 2026-05-08); status-history entries dated 2026-05-15 reflect the weekly monitoring sweep.

### Value Pipeline by Province
| Region | Count | Total Value ($B) | Top Sector |
|--------|-------|------------------|-----------|
| BC | 694 | 511.3 | Other |
| ON | 728 | 360.0 | infrastructure |
| AB | 733 | 346.9 | government |
| QC | 520 | 78.4 | education |
| YT | 123 | 46.4 | infrastructure |
| NT | 182 | 40.1 | infrastructure |
| SK | 216 | 30.1 | Other |
| NL | 1,561 | 25.8 | Other |
| NS | 339 | 13.0 | Other |
| NB | 198 | 7.1 | Other |
| MB | 2,054 | 6.7 | Other |
| CA | 3 | 2.9 | Ports & Logistics |
| NU | 47 | 2.0 | infrastructure |
| PE | 82 | 1.5 | infrastructure |

---

## 5. IAAC Monitoring (iaac.json, 102 registry projects)

### Projects in Assessment — by province
ON 26, AB 17, BC 17, QC 12, NS 8, MB 6, SK 6, NB 5, NL 3, PE 2. (No YT/NT/NU projects in this dataset.)

### Status Changes (status_history dated 2026-05-15 sweep)
- **AB — Flipi Gas-Fired Generation Project (Energy):** → Approved. TransAlta, 460 MW natural-gas facility ~18 km SW of Rimbey; IAAC early decision, 64-day review. https://www.canada.ca/en/impact-assessment-agency/news/2026/04/government-of-canada-provides-early-decision-on-flipi-gas-fired-generation-project-in-alberta.html
- Numerous Under Review entries dated 2026-05-15 across AB, BC, ON, SK, NS, NL, NB, MB, QC, PE (Indigenous infrastructure/water/wastewater, defence-base works, fibre installation, aggregate/quarry, energy). Registry: https://iaac-aeic.gc.ca/050/evaluations/exploration?active=true&showMap=false&document_type=project

---

## 6. Procurement Awards (≥$5M)

The pipeline procurement feed (procurement.json and signals.json `procurement`) returned **0 contract entries for week 2026-05-15** (and 0 for prior weeks in the file). No federal or provincial contract-award notices are available from the pipeline this run. This is a documented coverage gap, not a finding of zero awards. Project-database status changes serve as the only procurement-adjacent proxy: Agnico Eagle ON expansion (Proposed→Approved), and federally-funded items (Small Craft Harbours $958M; CanNor Nunavut $13M; Neweg Wind up to $25M NB) are captured via policy/project records and cited above.

---

## 7. Labour Market Stories

### Unemployment and Employment (indicators.json, April 2026 LFS basis; StatCan released May 8, 2026)
| Region | Unemployment | Employment Rate | Participation | Source |
|--------|-------------|-----------------|---------------|--------|
| National | 6.9% | 60.5% | 65.0% | https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm |
| ON | 7.5% | 59.9% | 64.8% | indicators.json / StatCan |
| QC | 6.2% | 60.4% | 64.4% | indicators.json / StatCan |
| AB | 7.0% | 64.4% | 69.2% | indicators.json / StatCan |
| BC | 6.8% | 60.0% | 64.4% | https://news.gov.bc.ca/releases/2026FIN0019-000513 |
| SK | 5.6% | 63.3% | 67.1% | indicators.json / StatCan |
| MB | 5.0% | 63.1% | 66.5% | indicators.json / StatCan |
| NS | 6.3% | 57.4% | 61.3% | indicators.json / StatCan |
| NB | 7.2% | 56.3% | 60.6% | indicators.json / StatCan |
| NL | 10.0% | 51.6% | 57.3% | indicators.json / StatCan |
| PE | 8.0% | 61.2% | 66.5% | indicators.json / StatCan |
| YT | 5.3% | 71.2% | 75.2% | indicators.json / StatCan |
| NT | 6.8% | 66.1% | 70.9% | indicators.json / StatCan |
| NU | 12.0% | 55.0% | 62.5% | indicators.json / StatCan |

### Employment Changes (April 2026 LFS, StatCan The Daily)
- Quebec -43,000 (-0.9%); Newfoundland and Labrador -5,200 (-2.1%); Saskatchewan -4,000 (-0.6%); New Brunswick -2,700 (-0.7%). National rate +0.2pp to 6.9%. Source: https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm
- Quebec cumulative 2026: ~87,000 jobs lost over four months; ~half in construction/manufacturing, ~one quarter in financial services. https://www.desjardins.com/en/savings-investment/economic-studies/quebec-employment-8-may-2026.html

### Hiring Spikes
- Pipeline job-monitor feed (signals.json `job_spikes`) returned 0 spikes for week 2026-05-15 — no hiring-spike alerts available this run (coverage gap). Qualitative: Saskatchewan mining employs >20,000 (potash/uranium/oil wages 20–40% above equivalents); Manitoba Budget 2026 commits to +40% apprentice training and 4,054 net new health-care staff.

### Wage Trends
- National wage growth +3.9% (SEPH, Feb 2026, indicators.json). QC weekly earnings $1,280.65 (Feb 2026, indicators.json qc_weekly_earnings). Saskatchewan average salary ~$65,300 (2026); resource-sector journeypersons/operators $85,000–$115,000. https://www.universitymagazine.ca/average-salary-in-saskatchewan-2026

---

## 8. Coverage Gaps and Priorities

- **Procurement feed empty (signals.json/procurement.json):** 0 contract awards captured for week 2026-05-15. Recommend a supplementary procurement search if the analyst requires ≥$5M federal/provincial award detail; not resolvable from current pipeline data.
- **Job-spike feed empty (signals.json):** 0 hiring-spike alerts. Sector hiring framed qualitatively from web research only.
- **QC/ON provincial economic accounts at Q3 2025:** source-side release lag (ISQ / Ontario Min. of Finance). Frame GDP-by-expenditure and provincial trade as "most recent available (Q3 2025)."
- **Territories (YT/NT/NU):** no CPI or housing-starts series (expected — StatCan does not publish these for territories); territorial GDP latest is 2024 annual. No IAAC registry projects for YT/NT/NU in iaac.json.
- **Honda ON ($15B):** project records remain "first tracked" in projects_all.json, but May 2026 reporting indicates indefinite suspension — analyst should treat the five Honda ON records as suspended/at-risk, not active pipeline, and not double-count the ~$15B across five near-duplicate records.
- **Stories found in research not yet in policy.json:** Bay du Nord regulatory submission (NL); Yukon tariff-response workforce funding; CanNor Nunavut funding package; Canada–Alberta IA cooperation agreement; New Brunswick economic development strategy / SMR plan; Nova Scotia offshore wind Wind West $60B plan. Flagged for analyst incorporation from the source registry below.

---

## 9. Master Source Registry

[1] https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm — Labour Force Survey, April 2026 — Statistics Canada — 2026-05-08 — national + provincial employment changes
[2] https://budget.ontario.ca/2026/chapter-1b-economy.html — Ontario Budget 2026, Economy — Government of Ontario — 2026 — ON labour/GDP outlook
[3] https://budget.ontario.ca/2026/index.html — Ontario Budget 2026 — Government of Ontario — 2026 — $210B capital plan
[4] https://budget.ontario.ca/2026/chapter-2.html — Ontario Budget 2026, Fiscal Plan — Government of Ontario — 2026 — infrastructure $111.3B
[5] https://www.rbc.com/en/economics/canadian-analysis/provincial-and-fiscal-outlooks/provincial-budgets-and-economic-statements/ontario-budget-2026-delayed-path-to-balance/ — Ontario Budget 2026: Delayed path to balance — RBC Economics — 2026 — ON deficit
[6] https://www.cbc.ca/news/business/honda-ev-plant-ontario-9.7190021 — Honda halting $15B EV plant development in Ontario — CBC News — 2026-05 — ON Honda suspension
[7] https://www.electrive.com/2026/05/11/honda-to-withdraw-from-canada-projects/ — Honda to withdraw from Canada projects — electrive.com — 2026-05-11 — ON Honda
[8] https://www.desjardins.com/en/savings-investment/economic-studies/quebec-employment-8-may-2026.html — Quebec: Strike Two for the Labour Market in 2026 — Desjardins — 2026-05-08 — QC employment
[9] https://www.budget.finances.gouv.qc.ca/budget/2026-2027/index.asp — Quebec Budget 2026-2027 — Gouvernement du Québec — 2026 — QC infrastructure plan
[10] https://www.quebec.ca/en/news/actualites/detail/18-billion-invested-and-600-jobs-created-in-quebec-by-the-telesat-lightspeed-project — Telesat Lightspeed $1.8B / 600 jobs — Gouvernement du Québec — 2026 — QC investment
[11] https://capitalhillgroup.ca/quebecs-new-economic-vision-2025-2026/ — Quebec's New Economic Vision 2025-2026 — Capital Hill Group — 2026 — QC infrastructure
[12] https://www.canada.ca/en/economic-development-quebec-regions/news/2026/03/government-of-canada-invests-7-million-to-attract-international-investments-with-montreal-international.html — Montréal International investments — Canada.ca — 2026-03 — QC FDI
[13] https://www.cbc.ca/news/canada/edmonton/atb-alberta-oil-gas-economy-forecast-9.7143848 — Alberta GDP forecast / ATB — CBC News — 2026 — AB GDP
[14] https://www.bnnbloomberg.ca/business/2026/05/13/high-oil-prices-could-turn-94b-alberta-deficit-into-6b-surplus-report/ — Alberta deficit-to-surplus report — BNN Bloomberg — 2026-05-13 — AB fiscal
[15] https://businesscouncilab.com/advocacy-category/statements-advocacy/spring-economic-snapshot-2026/ — Spring Economic Snapshot 2026 — Business Council of Alberta — 2026 — AB jobs/investment
[16] https://www.canadianminingjournal.com/featured-article/british-columbias-mining-month-2026-mining-investment-creating-jobs-building-british-columbias-economy/ — BC Mining Month 2026 — Canadian Mining Journal — 2026-05-15 — BC mining permitting
[17] https://news.gov.bc.ca/releases/2026FIN0019-000513 — Minister's statement on April LFS results — BC Government News — 2026-05 — BC unemployment 6.8%
[18] https://news.gov.bc.ca/releases/2026ECS0014-000552 — Strong response to 2025 call for power — BC Government News — 2026-05-13 — BC energy (137 projects)
[19] https://news.gov.bc.ca/releases/2026JEG0036-000550 — Made-in-B.C. health technology — BC Government News — 2026-05-13 — BC policy
[20] https://news.gov.bc.ca/releases/2026TACS0025-000556 — FIFA World Cup 2026 ticket donation — BC Government News — 2026-05-14 — BC policy
[21] https://news.gov.bc.ca/releases/2026HMA0045-000428 — Accelerating short-term rental opt-out — BC Government News — 2026-04 — BC housing (51 projects)
[22] https://www.saskatchewan.ca/government/news-and-media/2026/may/07/saskatchewan-mining-sector-delivering-strong-results-and-a-bright-future — SK mining sector results — Government of Saskatchewan — 2026-05-07 — SK mineral sales
[23] https://globalnews.ca/news/10395277/saskatchewan-economy-growth-mining-industry-investment-deloitte-canada/ — SK growth / Deloitte — Global News — 2026 — SK GDP
[24] https://www.universitymagazine.ca/average-salary-in-saskatchewan-2026 — Average Salary in Saskatchewan 2026 — University Magazine — 2026 — SK wages
[25] https://news.gov.mb.ca/news/index.html?item=73198 — Manitoba Budget 2026 — Province of Manitoba — 2026 — MB capital budget
[26] https://www.gov.mb.ca/asset_library/en/budget2026/budget2026.pdf — Manitoba Budget 2026 (full) — Province of Manitoba — 2026 — MB infrastructure $21.6B
[27] https://www.gov.mb.ca/budget2026/index.html — Manitoba Budget 2026 portal — Province of Manitoba — 2026 — MB apprentices/health staff
[28] https://novascotia.ca/offshore-wind/ — Offshore wind — Government of Nova Scotia — 2026 — NS 5 GW call for bids
[29] https://www.cbc.ca/news/canada/nova-scotia/offshore-wind-projects-9.7135261 — NS offshore wind law — CBC News — 2026 — NS offshore wind
[30] https://novascotia.ca/news/release/?id=20260409002 — Powering the Economy Act — Government of Nova Scotia — 2026-04-09 — NS legislation (45 projects)
[31] https://news.novascotia.ca/en/2026/02/24/province-introduces-legislation-power-economy — NS Powering the Economy legislation introduced — Government of Nova Scotia — 2026-02-24 — NS legislation
[32] https://www.gnb.ca/en/news/n-b.2026.04.government-launches-economic-development-strategy.html — NB economic development strategy — Government of New Brunswick — 2026-04 — NB 10% growth target
[33] https://www.mnp.ca/en/insights/directory/2026-new-brunswick-budget-highlights — 2026 New Brunswick Budget Highlights — MNP — 2026 — NB budget/deficit
[34] https://www2.gnb.ca/content/gnb/en/corporate/promo/clean-energy.html — Powering our Economy with Clean Energy — Government of New Brunswick — 2026 — NB SMR/wind/solar
[35] https://www.cbc.ca/news/canada/newfoundland-labrador/equinor-bay-du-nord-development-application-9.7188650 — Equinor submits Bay du Nord plans — CBC News — 2026-05 — NL Bay du Nord
[36] https://www.gov.nl.ca/releases/2026/exec/0303n05/ — Agreement to Advance Bay du Nord — Government of NL — 2026-03-03 — NL revenue/jobs
[37] https://www.gov.nl.ca/releases/2026/exec/0304n02/ — NL offshore industry milestone — Government of NL — 2026-03-04 — NL offshore
[38] https://worldoil.com/news/2026/4/30/newfoundland-and-labrador-budget-boosts-offshore-exploration-funding/ — NL budget offshore exploration funding — World Oil — 2026-04-30 — NL budget
[39] https://www.princeedwardisland.ca/en/information/finance-and-affordability/budget-address-2026 — PEI Budget Address 2026 — Government of PEI — 2026-04-14 — PE budget
[40] https://www.scotiabank.com/ca/en/about/economics/economics-publications/post.other-publications.fiscal-policy.fiscal-pulse.provincial-budget-analyses-and-updates.prince-edward-island-.prince-edward-island-2026-27-budget--april-14--2026-.html — PEI 2026-27 Budget analysis — Scotiabank Economics — 2026-04-14 — PE deficit/GDP
[41] https://www.cbc.ca/news/canada/north/yukon-party-government-budget-2026-27-9.7134152 — Yukon $82M deficit budget — CBC News — 2026 — YT budget
[42] https://yukon.ca/en/news/budget-2026-begins-road-fiscal-recovery — Budget 2026 begins road to fiscal recovery — Government of Yukon — 2026 — YT budget detail
[43] https://www.canada.ca/en/employment-social-development/news/2026/05/governments-of-canada-and-yukon-partner-to-support-tariff-impacted-workers-and-strengthen-workforce.html — Canada–Yukon Workforce Tariff Response — Canada.ca — 2026-05 — YT workforce funding
[44] https://www.bnnbloomberg.ca/tariffs/2026/01/01/northwest-territories-facing-a-hard-as-diamonds-reality-as-pivotal-industry-wanes/ — NWT diamond industry waning — BNN Bloomberg — 2026-01-01 — NT diamonds/GDP
[45] https://www.miningnewsnorth.com/story/2026/03/06/news/nwt-study-maps-critical-minerals-potential/9572.html — NWT critical minerals study — North of 60 Mining News — 2026-03-06 — NT critical minerals
[46] https://www.canada.ca/en/northern-economic-development/news/2026/04/the-government-of-canada-invests-in-projects-to-strengthen-nunavuts-economy-infrastructure-and-arctic-security.html — CanNor Nunavut investments — Canada.ca — 2026-04 — NU funding
[47] https://nunavutnews.com/2026/04/22/federal-government-commits-up-to-13-million-for-four-nunavut-projects/ — Federal $13M for four Nunavut projects — Nunavut News — 2026-04-22 — NU funding detail
[48] https://www.canada.ca/en/impact-assessment-agency/news/2026/04/government-of-canada-provides-early-decision-on-flipi-gas-fired-generation-project-in-alberta.html — IAAC early decision, Flipi Gas-Fired Generation — Canada.ca — 2026-04 — AB IAAC
[49] https://www.canada.ca/en/impact-assessment-agency/news/2026/04/alberta-and-canada-sign-co-operation-agreement-to-accelerate-major-project-assessments.html — Canada–Alberta IA cooperation agreement — Canada.ca — 2026-04-02 — AB policy
[50] https://iaac-aeic.gc.ca/050/evaluations/exploration?active=true&showMap=false&document_type=project — Canadian Impact Assessment Registry — Canada.ca — 2026 — IAAC registry
[51] https://www.canada.ca/en/department-finance/news/2026/04/canada-responds-to-us-tariff-actions.html — Canada responds to US tariff actions — Canada.ca — 2026-04 — federal tariff (520 projects)
[52] https://www.infrastructure.gc.ca/plan/build-communities-strong-eng.html — Build Communities Strong Fund $51B — Infrastructure Canada — 2026 — federal (2,196 projects)
[53] https://www.canada.ca/en/natural-resources-canada/news/2026/03/critical-minerals-alliance.html — Critical Minerals Alliance Round 2 $12.1B — NRCan — 2026-03 — federal (421 projects)
[54] https://ised-isde.canada.ca/site/ai-strategy/en — Canadian Sovereign AI Compute Strategy — ISED — 2026 — federal (17 projects)
[55] https://www.parl.ca/legisinfo/en/bill/45-1/S-212 — Bill S-212 National Strategy for Children and Youth Act — Parliament of Canada — 2026-03-12 — federal legislation
[56] https://budget.ontario.ca/2026/eco-fiscal.html — Ontario Budget 2026, Economic and Fiscal Overview — Government of Ontario — 2026 — ON fiscal
[57] https://fao-on.org/en/report/2026-ontario-budget-note/ — 2026 Ontario Budget Note — Financial Accountability Office of Ontario — 2026 — ON fiscal analysis
</content>
