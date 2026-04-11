# Provincial Research — Week Ending April 11, 2026

**Agent 1B — Provincial Researcher**
**Research date:** 2026-04-11
**Briefing week_of:** 2026-04-11
**Data vintage:** StatsCan Labour Force Survey March 2026 (released April 10, 2026); StatsCan CPI February 2026 (released March 18, 2026) — March CPI scheduled for April 20; CMHC Housing Starts February 2026 (released March 17, 2026).
**Provinces covered:** All 13 provinces + 3 territories (16 total)
**Search waves:** File ingestion (indicators.json, projects_all.json, events.json, policy.json, iaac.json, data_gap_report.md) + prior-week research_provinces.md continuity check.

---

## 1. Data Quality Audit

### Provincial Indicator Coverage (core indicators: CPI, unemployment, housing starts, participation rate, employment rate)
| Province | Core Indicators | Projects in DB | Latest Update | Status |
|----------|-----------------|----------------|----------------|--------|
| ON | 6 (CPI, UE, ER, PR, HS, GDP) + 6 ON-series | 661 | 2026-04-11 | OK |
| QC | 6 + 11 QC-series (incl. manufacturing, retail, permits) | 502 | 2026-04-11 | OK |
| AB | 6 | 739 | 2026-04-11 | OK |
| BC | 6 | 658 | 2026-04-11 | OK |
| SK | 6 | 221 | 2026-04-11 | OK |
| MB | 6 | 2063 | 2026-04-11 | OK |
| NS | 6 | 337 | 2026-04-11 | OK |
| NB | 6 | 208 | 2026-04-11 | OK |
| NL | 6 | 1560 | 2026-04-11 | OK |
| PE | 6 (CPI, UE present after March 2026 LFS) | 98 | 2026-04-11 | OK |
| YT | 2 (Unemployment, GDP — no CPI, territory limitation) | 125 | 2026-02-01 | PARTIAL |
| NT | 2 (Unemployment, GDP — no CPI, territory limitation) | 188 | 2026-02-01 | PARTIAL |
| NU | 2 (Unemployment, GDP — no CPI, territory limitation) | 57 | 2026-02-01 | PARTIAL |

### Critical Gaps (per data_gap_report.md, 2026-04-11)
- PE missing StatsCan CPI and Unemployment in the legacy prefixed keys (PE_cpi, PE_unemployment), but March 2026 LFS has delivered full Prince Edward Island unemployment (7.3%) and Feb CPI (+5.4% y/y) under the full-province-name key set. Report accordingly.
- YT/NT/NU lack monthly CPI from StatCan consumer price survey (expected territory limitation — monthly LFS provides only unemployment; CPI is published territorially only as Whitehorse, Yellowknife, Iqaluit city indexes).
- Provincial CPI and unemployment under prefixed keys (ON_cpi, ON_unemployment, etc.) show period 2026-02-01 (69 days old). The 2026-04-11 full-name dataset (e.g., "Ontario": unemployment +7.6%, cpi -1.1%) reflects March 2026 LFS release.

---

## 2. Provincial Spotlights (ALL 13 PROVINCES + 3 TERRITORIES)

### Ontario

**Top story:** The Eglinton Crosstown LRT opened February 2026, delivering 19 km of rapid transit with 10 km underground. Ontario's 2026 Budget released March 26, 2026, projected a $13.8 billion deficit for 2026-27 with $244.2 billion in planned spending. Source: [Ontario Budget 2026](https://budget.ontario.ca/2026/contents.html); [CP24 2026 Budget recap](https://www.cp24.com/local/toronto/2026/03/26/ontario-reveals-2026-budget-heres-how-it-could-affect-your-pocketbook/); [MNP Ontario 2026 Budget Highlights](https://www.mnp.ca/en/insights/directory/ontario-2026-budget-highlights); [Hicks Morley 2026 Ontario Budget](https://hicksmorley.com/2026/03/27/highlights-of-the-2026-ontario-budget/).

**Key indicators (March 2026 LFS, released April 10):**
- Unemployment rate: 7.6% (unchanged m/m). Source: [StatsCan Labour Force Survey, March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 59.6% (−0.1pp m/m). Participation rate: 64.6% (unchanged).
- CPI: −1.1% y/y (February 2026), from −1.6% in January. Ontario is the only jurisdiction posting negative headline CPI; HST provinces bear the largest base-year impact from the 2025 GST holiday. Source: [StatsCan Consumer Price Index, February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 67,274 (Ontario, Feb 2026 SAAR) vs 65,757 previous. Source: [CMHC Housing Market Information Portal](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +1.2% (2024, provincial accounts). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 661 tracked projects. Top pipeline by value includes Highway 413 and Bradford Bypass ($31.00B, Under Construction), Ontario Line ($27.43B, Under Construction), GO Expansion ($26.08B, Under Construction), Adaptive Phased Management Deep Geological Repository ($26.00B, Proposed), and Bruce Nuclear Refurbishment ($13.00B, Under Construction). New IAAC Under Review entries this period: Canadian Armed Forces Training Area (CAFTA) Winona Range upgrades and the New Nuclear at Wesleyville Project (a prospective SMR/large reactor site east of Port Hope). Sources: [Canadian Impact Assessment Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA); Ontario Budget 2026 (chapter 1B).

**Policy developments:** Ontario Budget 2026 capital plan covers $210 billion over 10 years, including $37 billion in 2026-27. Small-business corporate tax rate reduced from 3.2% to 2.2%. $4 billion Protect Ontario Account Investment Fund targets AI, defence, advanced manufacturing, and life sciences. A temporary HST rebate for new homes is costed at $2.2 billion in joint tax relief. Sources: [Ontario Budget 2026 chapter 1B](https://budget.ontario.ca/2026/chapter-1b-building.html); [OCC Rapid Policy 2026 Ontario Budget](https://occ.ca/rapidpolicy/2026-ontario-provincial-budget/).

**Labour trends:** Ontario's 7.6% unemployment rate remains the highest of the big-four provinces (ON, QC, AB, BC). Toronto CMA unemployment hovered around 8.5% in the March 2026 LFS.

**IAAC status:** 26 Ontario projects in federal assessment registry. Notable: CAFTA Winona Range Upgrades; New Nuclear at Wesleyville Project (Clean Energy). Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** procurement.json recorded 0 contracts for the week_of 2026-04-11. Federal and provincial contract feeds produced no awards ≥$5M during the sample window.

---

### Quebec

**Top story:** Quebec's 2026-27 Budget (released March 25, 2026) outlined an $8.6 billion deficit for 2026-27 and added $5 billion to the 10-year capital plan, bringing it to $167 billion. $1.7 billion was allocated over five years for economic transformation, including $480 million for critical and strategic minerals. Sources: [Quebec 2026-27 Budget Speech (PDF)](https://www.finances.gouv.qc.ca/Budget_and_update/budget/documents/Budget2627_BudgetSpeech.pdf); [KPMG 2026 Quebec Budget Highlights](https://kpmg.com/ca/en/insights/2026/03/highlights-of-the-2026-quebec-budget.html); [Quebec Gov press release](https://www.quebec.ca/en/news/actualites/detail/budget-2026-2027-press-release-no-3-of-3-more-than-17-billion-to-accelerate-quebecs-economic-transformation-69185).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 5.4% (−0.5pp from 5.9%). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 60.9% (+0.2pp). Participation: 64.4% (−0.1pp).
- CPI: +0.6% y/y (Feb 2026), from +0.7% previous. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Provincial real GDP: $487,223M (2025 Q3). Manufacturing sales: $224,427.64M (Jan 2026). Retail sales: $190,191.25M (Jan 2026). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201); [Table 16-10-0048-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004801)
- Housing starts: 53,461 (Feb 2026 SAAR) vs 51,982 previous. Building permits Jan 2026: residential $25.87B, non-residential $10.27B. Source: [CMHC](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- International exports Dec 2025: $89,038M; international imports Dec 2025: $99,921M. Source: [StatsCan Table 12-10-0176-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1210017601)

**Project activity:** 502 tracked projects, $89.6B pipeline. Largest: Parc éolien zone Chamouchouane ($9.00B, Proposed), Quebec Transport Infrastructure Investment Plan 2026-2028 ($8.00B), Revised Montreal Metro Blue Line Extension ($4.89B, Under Construction), green hydrogen production plant ($4.00B, Under Review), Québec City Tramway TramCité ($3.76B, Under Construction). Sector mix: education (118), infrastructure (103), other (50). Source: projects_quebec.json (7-day ingestion window).

**Policy developments:** Quebec GDP projections: 0.8% (2025), +1.1% (2026 baseline, stable-tariff scenario); −0.2% in 2026 if U.S. exits USMCA. Source: [KPMG 2026 Quebec Budget Highlights](https://kpmg.com/ca/en/insights/2026/03/highlights-of-the-2026-quebec-budget.html).

**Labour trends:** Quebec posted the largest unemployment-rate decline of the big provinces in March (−0.5pp), bringing the rate to 5.4% — the lowest of the four largest provinces.

**IAAC status:** 13 Quebec projects in registry. New Under Review: Leamy Creek Pathway Re-Naturalization (Gatineau); YUL Montreal-Trudeau Airport Weather Station installation (sector: ports & logistics); Closure of M Bridge and floating boardwalk at Wapizagonke (La Mauricie). Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** No weekly contracts ≥$5M registered in procurement.json for the week_of 2026-04-11.

---

### Alberta

**Top story:** Alberta Budget 2026 (released February 27, 2026) implemented a new 8% income tax bracket on the first $60,000 of taxable income and projected a deficit for 2026-27 on weaker oil-royalty assumptions. The budget tabled a $28.3B capital plan over three years. Sources: [Alberta Budget Highlights](https://www.alberta.ca/budget-highlights); [Raymond James 2026 Alberta Budget Highlights](https://www.raymondjames.ca/commentary-and-insights/tax-planning/2026/03/02/2026-ab-budget-highlights); [Calgary Chamber 2026 Budget submission](https://calgarychamber.com/whats-new/submission-2026-alberta-budget-policy/).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 6.5% (+0.2pp from 6.3%). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 64.4% (unchanged). Participation rate: 68.9% (+0.2pp, highest in Canada).
- CPI: +3.4% y/y (Feb 2026), from +4.9% previous — largest provincial decline. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 48,438 (Feb 2026 SAAR) vs 48,896 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +2.7% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 739 tracked projects, $349.6B pipeline (second-largest province pipeline behind BC). Top value: Alberta Budget 2026 Capital Plan ($28.30B, Proposed), Telus Infrastructure Upgrades province-wide 2023-2027 ($19.00B, Under Construction), Pathways Alliance Carbon Capture and Storage ($16.50B, Proposed), AOSP Jackpine ($12.00B, Approved). Sector mix concentrated in power/energy (124), government (146), and infrastructure (113). Source: projects_alberta.json.

**Policy developments:** Alberta Budget 2026 committed to fixed-term mortgage-rule alignment and construction-labour capacity funding. Calgary Chamber submitted a pre-budget requesting increases to skilled-trades training allocations and industrial carbon pricing clarity. Source: [Calgary Chamber submission](https://calgarychamber.com/whats-new/submission-2026-alberta-budget-policy/).

**Labour trends:** Alberta's participation rate (68.9%) remains the highest in Canada. The 0.2pp uptick in unemployment contrasts with prairie neighbours SK (−0.6pp) and MB (−0.1pp).

**IAAC status:** 24 Alberta projects in registry — second only to Ontario. New Under Review: APEX Utilities Opasikoniwew Housing Authority Hoole Creek Road Subdivision Phase 2 Gasification; Tsuut'ina Bullhead Road Sewer Line; Mînî Thnî Lift Station. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### British Columbia

**Top story:** BC Minister of Forests Ravi Parmar issued a statement on April 9, 2026, responding to preliminary results of the U.S. Department of Commerce's seventh administrative review of anti-dumping and countervailing duty orders on Canadian softwood lumber. BC Minister of Housing Christine Boyle released statements April 10 on the March 2026 housing highlights and April 9 on the April 2026 rental report. Sources: [BC Government News Forests — 2026FOR0011-000394](https://news.gov.bc.ca/releases/2026FOR0011-000394); [BC Government News Housing — 2026HMA0042-000398](https://news.gov.bc.ca/releases/2026HMA0042-000398); [BC Government News Housing — 2026HMA0039-000390](https://news.gov.bc.ca/releases/2026HMA0039-000390).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 6.7% (+0.6pp from 6.1% — largest provincial increase this month). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 60.1% (−0.4pp). Participation rate: 64.4% (unchanged).
- CPI: +1.0% y/y (Feb 2026), from +1.3% previous. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 41,331 (Feb 2026 SAAR) vs 41,492 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +1.2% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 658 tracked projects, $509.6B pipeline — largest in Canada. Top value: LNG Canada Phase 1 ($47.90B, Under Construction), LNG Canada Phase 2 ($25.00B, Proposed), Kitimat Clean Oil Refinery ($22.00B, Under Review), Peace River Site C Hydro-electric ($16.00B, Under Construction). Top sectors: power/energy (68), mining (56), other (65). Source: projects_british_columbia.json.

**Policy developments:** 3 BC policy announcements recorded this week (all housing- and forestry-related). Affected projects totals per policy.json: 114 for housing highlights; 21 for softwood lumber; 114 for rental report. Source: docs/data/policy.json (week_of 2026-04-11).

**Labour trends:** BC recorded the largest month-over-month unemployment rise (+0.6pp) in March 2026 among all provinces.

**IAAC status:** 11 BC projects in federal registry. New Under Review: Amrize Coquitlam Depots Maintenance Dredge; Gwa'sala-'Nakwaxda'xw Nations Tsulquate Subdivision; Shell Beach Erosion Control Project Portland Island. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Saskatchewan

**Top story:** Saskatchewan Budget 2026-27 (released March 19, 2026) titled "Protecting Saskatchewan" tabled a $4.3 billion capital plan. The budget included targeted potash royalty stability and advanced manufacturing incentives. Sources: [Saskatchewan 2026-27 Budget announcement](https://www.saskatchewan.ca/government/news-and-media/2026/march/18/2026-27-budget-protecting-saskatchewan); [Raymond James 2026 Saskatchewan Budget Highlights](https://www.raymondjames.com/dotcom-canada/commentary-and-insights/2026/03/20/2026-sk-budget-highlights).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 5.0% (−0.6pp from 5.6%, lowest in Canada). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 63.9% (+0.5pp). Participation: 67.2% (+0.1pp).
- CPI: −0.7% y/y (Feb 2026), from +1.2% previous — flipped negative, largest swing in the country. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 5,486 (Feb 2026 SAAR) vs 5,327 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +3.4% (2024 — second-fastest provincial growth). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 221 tracked projects, $38.3B pipeline. Top value: BHP Jansen Stage 1 ($7.50B, Under Construction), Jansen Stage 2 ($6.40B, Under Construction), Saskatchewan 2026-27 Capital Budget ($4.30B, Approved), FCL HDRD renewable diesel plant ($2.00B, Proposed), Bell Canada AI Data Centre RM of Sherwood ($1.70B, Proposed).

**Policy developments:** Saskatchewan 2026-27 capital envelope covered infrastructure, health facilities, and schools. Source: [Saskatchewan Budget 2026-27](https://www.saskatchewan.ca/government/news-and-media/2026/march/18/2026-27-budget-protecting-saskatchewan).

**Labour trends:** Saskatchewan's 5.0% unemployment is the lowest provincial rate in Canada for March 2026.

**IAAC status:** 8 Saskatchewan projects in registry. New Under Review: Northern Lights Casino Expansion and Renovation; Kistaphinanihk Office Building; Deschambault Lake Road Resurfacing and Drainage Improvements. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Manitoba

**Top story:** Manitoba Budget 2026 (announced March 2026) introduced a record $3.8 billion capital investment plan. Sources: [News release — Manitoba Budget 2026](https://news.gov.mb.ca/news/index.html?item=73197); [CCPA Manitoba Budget 2026](https://www.policyalternatives.ca/news-research/manitoba-budget-2026/); [Canadian Innovators — Sovereign Value-Added](https://www.canadianinnovators.org/content/manitoba-should-stay-the-course-on-sovereign-value-added-).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 5.6% (−0.1pp from 5.7%). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 63.4% (+0.9pp, largest monthly increase). Participation: 67.1% (+0.8pp).
- CPI: +3.1% y/y (Feb 2026), from +3.4% previous. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 7,642 (Feb 2026 SAAR) vs 7,799 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +1.1% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 2,063 tracked projects (the largest project count of any province — the discovery pipeline's Manitoba signal-to-noise is heavily influenced by the federal Green and Inclusive Community Buildings RSS feed). $14.6B pipeline. Top value: Manitoba Budget 2026 Capital Plan ($3.80B), North End Water Pollution Control Centre upgrade ($3.20B, Under Construction), Portage Place Redevelopment Healthcare Centre ($0.65B, Under Construction), NEWPCC Biosolids Facilities ($0.50B, Approved), Lake Manitoba/Lake St. Martin Outlet Channels ($0.49B, Approved). Top sectors: Other (1,078), Water & Wastewater (456), Energy (152).

**Policy developments:** CCPA analysis of Manitoba Budget 2026 noted capital commitments to housing, healthcare, and trades training. Source: [CCPA Manitoba Budget 2026](https://www.policyalternatives.ca/news-research/manitoba-budget-2026/).

**Labour trends:** Manitoba posted the largest month-over-month gain in employment rate (+0.9pp to 63.4%) of any province in March 2026.

**IAAC status:** 6 Manitoba projects in registry. New: Hnausa Wharf Replacement; 98 Manitoba Street Environmental Remediation; New Resort Development 116 TaWaPit Drive Wasagaming (status transitioned to Cancelled). Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Nova Scotia

**Top story:** Nova Scotia 2026-27 Budget (released March 2026). The fiscal plan maintained capital investment for healthcare and infrastructure. Sources: [Nova Scotia Budget 2026-27](https://novascotia.ca/budget/); [Scotiabank Nova Scotia Budget 2026-27 post](https://www.scotiabank.com/ca/en/about/economics/economics-publications/post.other-publications.fiscal); [Yahoo Finance — Highlights from Nova Scotia's 2026-27 budget](https://ca.finance.yahoo.com/news/highlights-nova-scotias-2026-27-202543812.html).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 6.6% (−0.5pp from 7.1%). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 57.4% (+0.4pp). Participation rate: 61.4% (+0.1pp).
- CPI: +1.5% y/y (Feb 2026), from +1.7% previous. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 7,146 (Feb 2026 SAAR) vs 7,252 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +2.7% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 337 tracked projects, $18.6B pipeline. Top value: Bear Head Energy ammonia/hydrogen ($8.00B, Proposed), Nova Scotia Capital Plan 2026-27 ($3.50B, Proposed), CFB Halifax Dockyard & Stadacona Power and Service Infrastructure Upgrades ($1.20B, Proposed), 14 Wing Greenwood Hangar and Drone Infrastructure ($0.65B, Proposed), Boat Harbour Remediation ($0.37B, Approved). Top sectors: Other (123), Clean Energy (73), infrastructure (24).

**IAAC status:** 3 Nova Scotia projects in registry. Under Review: Tufts Cove Generation Station Rock Revetment; Floating Wharf Replacement at Meteghan Small Craft Harbour; Deconstruction of New Glasgow Armoury NG1. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### New Brunswick

**Top story:** New Brunswick 2026-2027 Budget (tabled March 17, 2026). Sources: [Legislative Assembly NB Budget PDF](https://legnb.ca/content/house_business/61/2/tabled_documents/2026-03-17%20Budget%202026-2027%20%20F); [Baker Tilly tax update on NB 2026-2027 budget](https://www.bakertilly.ca/insights/tax-alert-nb-2026-2027-budget); [TD Economics — New Brunswick Budget](https://economics.td.com/new-brunswick-budget).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 7.0% (unchanged). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 56.7% (+0.2pp). Participation: 60.9% (+0.2pp).
- CPI: +1.2% y/y (Feb 2026), from +2.4% previous — half-reduction m/m. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 6,011 (Feb 2026 SAAR) vs 6,454 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +1.8% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 208 tracked projects, $5.2B pipeline. Top value: Saint John Pulp Mill Upgrades ($1.10B, Under Review), Sisson Project tungsten/molybdenum ($0.58B, Approved), Twinning of Trans-Canada Highway Route 2 ($0.42B, Under Construction), Port Saint John West Side Terminals Modernization ($0.21B, Under Construction). New Brunswick Museum Construction Phase ($50M, Approved), Dieppe Boulevard Extension ($12M, Under Construction), Sydney Street Courthouse Theatre ($12M, Approved).

**IAAC status:** 5 New Brunswick projects in registry. Under Review: Cap Saint Louis Wharf Repairs 2026; Maliseet Road and Principale Street Stormwater and Drainage Upgrades Madawaska; Graham Road Maintenance and New Culvert CFB Gagetown. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Newfoundland and Labrador

**Top story:** Newfoundland and Labrador entered the Budget 2026 public consultation phase. Sources: [Government of NL Finance — Economics](https://www.gov.nl.ca/fin/economics/); [NLFED 2026 NLFL Provincial Budget Submission](https://nlfed.ca/2026-nlfl-provincial-budget-submission/); [NFLD Bulletin — Public Input Budget 2026](https://www.facebook.com/NFLDBulletin/posts/province-launches-public-input-for-budget-2026january-20).

**Key indicators (March 2026 LFS):**
- Unemployment rate: 9.5% (+0.3pp from 9.2% — highest provincial rate in Canada). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 52.7% (unchanged). Participation rate: 58.3% (+0.2pp).
- CPI: +1.8% y/y (Feb 2026), from +2.3% previous. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 1,223 (Feb 2026 SAAR) vs 1,194 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +2.4% (2024). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Project activity:** 1,560 tracked projects (inflated by the same federal community-buildings feed affecting MB), $32.0B pipeline. Top value: Grassy Point LNG ($10.00B, Proposed), Bay du Nord Offshore Oil Project Benefits Agreement ($6.40B, Approved), Kamistiatusset (Kami) iron ore ($3.86B, Under Review), White Rose Expansion West ($3.80B, Under Construction), White Rose Expansion ($2.30B, Under Construction).

**IAAC status:** 5 NL projects in registry. Under Review: Upgrade of existing softball field east of Base Gymnasium (CFB Goose Bay vicinity); New construction of Perimeter Fence and Site Improvements at former USAF Experimental Facility; Point Rousse Port Expansion Project. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Labour trends:** NL's 9.5% unemployment is the highest of any province in March 2026.

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Prince Edward Island

**Top story:** PEI announced its 2026-27 Capital Budget — focus on schools, healthcare, and infrastructure under a five-year capital envelope. A Canada-PEI cooperation agreement was also signed. Sources: [Province of PEI — 2026-27 Capital Budget LinkedIn post](https://www.linkedin.com/posts/province-of-pei_pei-has-announced-its-capital-budget-for-activity-739); [govpe Facebook post on PEI Capital Budget 2026-27](https://www.facebook.com/govpe/posts/pei-has-announced-its-capital-budget-for-2026-27-outlining-a-fi); [Yahoo Finance — PEI and Canada sign co-operation agreement](https://finance.yahoo.com/economy/policy/articles/prince-edward-island-canada-sign-173100420.html).

**Key indicators (March 2026 LFS):** PE is NOT a data gap in the March 2026 LFS release — the legacy `PE_cpi`/`PE_unemployment` prefixed keys are absent in indicators.json, but the full-name "Prince Edward Island" record is current.
- Unemployment rate: 7.3% (+0.1pp from 7.2%). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm)
- Employment rate: 61.6% (−0.2pp). Participation: 66.5% (−0.1pp).
- CPI: +5.4% y/y (Feb 2026), from +7.3% previous — highest provincial inflation rate. Source: [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm)
- Housing starts: 963 (Feb 2026 SAAR) vs 1,112 previous. Source: [CMHC Housing Data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data)
- Real GDP growth: +3.6% (2024 — fastest provincial growth). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)

**Data-gap note:** data_gap_report.md lists "PE: missing CPI (PE_cpi); PE: missing Unemployment Rate (PE_unemployment)" — these reference the legacy prefixed keys. The March 2026 LFS has populated the full-province-name record, so PE indicator coverage is functionally complete for the briefing. No fabrication required.

**Project activity:** 98 tracked projects, $2.9B pipeline. Top value: PEI 2026-27 Capital Budget Healthcare and Education Infrastructure ($0.49B, Proposed), PEI Capital Budget 2026-27 five-year plan ($0.49B, Proposed), PEI Mental Health Campus Completion ($0.13B, Under Construction), PEI Affordable Housing Construction 300+ Units ($0.10B, Proposed), Northumberland Strait Submarine Transmission System ($0.09B, Under Construction).

**IAAC status:** 2 PEI projects in registry. Under Review: Wharf Reconstruction at Mink River Small Craft Harbour; Breakwater Construction at Tignish SCH. Source: [IAAC Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

**Procurement:** None ≥$5M in procurement.json for the week_of 2026-04-11.

---

### Yukon

**Top story:** Yukon's capital planning cycle continues under Budget 2026. No territorial policy announcements registered in policy.json or events.json for the week_of 2026-04-11.

**Key indicators:**
- Unemployment rate: 3.9% (Feb 2026 LFS, period 2026-02-01 — territorial LFS data is reported monthly with a lag). Source: [StatsCan Labour Force Survey — territories](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201)
- Real GDP: −3.3% (2024 annual, StatsCan provincial accounts — GDP contraction driven by placer gold and mineral-extraction output). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)
- CPI: Territory-level CPI is not published monthly; Whitehorse city CPI series is a separate release. Gap flagged in data_gap_report.md as expected territory limitation.

**Project activity:** 125 tracked projects, $47.4B pipeline (driven by Northern Defence and Infrastructure Investment $40.00B, Proposed). Top non-defence: Casino Mine ($3.62B, Proposed), Whitehorse Power Centres Project ($0.52B, Proposed), Kudz Ze Kayah zinc/copper ($0.49B, Under Review), Yukon Budget 2026 Capital Plan ($0.39B, Proposed).

**IAAC status:** 0 Yukon projects in IAAC registry this week (Yukon's larger projects are assessed under the Yukon Environmental and Socio-economic Assessment Act rather than the federal Impact Assessment Act).

**Policy developments:** No significant developments recorded in policy.json for the week.

**Procurement:** None ≥$5M registered.

---

### Northwest Territories

**Top story:** NWT major capital focus remains on Mackenzie Valley Highway construction and Taltson Hydro Expansion. No territorial policy announcements registered this week in policy.json or events.json.

**Key indicators:**
- Unemployment rate: 5.3% (Feb 2026 LFS, period 2026-02-01). Source: [StatsCan LFS — territories](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201)
- Real GDP: −1.1% (2024 annual). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)
- CPI: Not published territorially on a monthly basis; Yellowknife city CPI is the closest proxy. Flagged as expected territory limitation.

**Project activity:** 188 tracked projects, $44.2B pipeline (driven by Arctic Defence and Infrastructure Spending Package NWT $35.00B, Proposed). Top non-defence: Mackenzie Valley Highway Construction Start ($2.00B, Approved), Taltson Hydro Expansion ($2.00B, Approved), Taltson Hydroelectricity Expansion Phase 1 ($1.20B, Under Construction), Pine Point lead/zinc ($0.65B, Under Review). Top sectors: infrastructure (57), mining (27).

**IAAC status:** 0 NWT projects in federal IAAC registry this week (NWT uses the Mackenzie Valley Resource Management Act process).

**Policy developments:** No significant developments recorded in policy.json.

**Procurement:** None ≥$5M registered.

---

### Nunavut

**Top story:** Nunavut major capital focus remains on mining (Baffinland Mary River rail and port expansion; Back River gold) and federal-territorial housing (Nunavut 750 Homes Initiative). No territorial policy announcements registered this week in policy.json or events.json.

**Key indicators:**
- Unemployment rate: 10.8% (Feb 2026 LFS, period 2026-02-01 — highest in Canada). Source: [StatsCan LFS — territories](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201)
- Real GDP: +7.5% (2024 annual — fastest growth in Canada, driven by mining output). Source: [StatsCan Table 36-10-0222-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)
- CPI: Not published territorially on a monthly basis; Iqaluit city CPI is the closest proxy. Flagged as expected territory limitation.

**Project activity:** 57 tracked projects, $38.9B pipeline (driven by Northern Defence and Infrastructure $32.00B, Proposed). Top non-defence: Baffinland Mary River Steensby Rail and Port Expansion ($3.00B, Approved), Back River Gold Project ($0.61B, Under Construction), Nunavut 750 Homes Initiative ($0.48B, Under Construction), Baker Lake Modular Housing 750-Home Program First Delivery ($0.48B, Under Construction). Top sectors: infrastructure (19), tourism/culture (6), environment (5). Discovered this week: Arctic Bay Water Treatment Plant Construction Phase ($49M, Proposed).

**IAAC status:** 0 Nunavut projects in federal IAAC registry this week (Nunavut uses the Nunavut Impact Review Board process under the Nunavut Agreement).

**Policy developments:** No significant developments recorded in policy.json.

**Procurement:** None ≥$5M registered.

---

### National (context for provincial comparisons)

**Top story:** StatsCan's March 2026 Labour Force Survey (released April 10, 2026) reported the national unemployment rate held at 6.7% while employment gains were concentrated in Quebec (−0.5pp unemployment), Saskatchewan (−0.6pp), and Nova Scotia (−0.5pp), partially offset by increases in British Columbia (+0.6pp) and Newfoundland and Labrador (+0.3pp). Source: [StatsCan Labour Force Survey March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm).

**Key indicators (week_of 2026-04-11):**
- National unemployment: 6.7% (March 2026, unchanged m/m).
- National CPI: +1.8% y/y (February 2026).
- National real GDP: +1.9% (2024 annual).
- Bank of Canada overnight rate: 2.25% (target). Source: [Bank of Canada Key Interest Rate](https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/)
- Next BoC decision: April 16, 2026.

---

## 3. Policy Developments Summary

### Budgets Referenced (already released, still relevant context)
- **Ontario Budget 2026** (Mar 26). [budget.ontario.ca/2026/contents.html](https://budget.ontario.ca/2026/contents.html)
- **Quebec Budget 2026-27** (Mar 25). [finances.gouv.qc.ca Budget Speech PDF](https://www.finances.gouv.qc.ca/Budget_and_update/budget/documents/Budget2627_BudgetSpeech.pdf)
- **Alberta Budget 2026** (Feb 27). [alberta.ca/budget-highlights](https://www.alberta.ca/budget-highlights)
- **Saskatchewan Budget 2026-27** (Mar 19). [saskatchewan.ca — 2026-27 Budget Protecting Saskatchewan](https://www.saskatchewan.ca/government/news-and-media/2026/march/18/2026-27-budget-protecting-saskatchewan)
- **Manitoba Budget 2026** (Mar 2026). [news.gov.mb.ca — Budget 2026](https://news.gov.mb.ca/news/index.html?item=73197)
- **New Brunswick Budget 2026-2027** (Mar 17). [legnb.ca Budget PDF](https://legnb.ca/content/house_business/61/2/tabled_documents/2026-03-17%20Budget%202026-2027%20%20F)
- **Nova Scotia Budget 2026-27** (Mar 2026). [novascotia.ca/budget](https://novascotia.ca/budget/)
- **PEI Capital Budget 2026-27** (Mar 2026). [Yahoo Finance PEI-Canada agreement](https://finance.yahoo.com/economy/policy/articles/prince-edward-island-canada-sign-173100420.html)
- **Newfoundland Labrador Budget 2026** — under public consultation. [gov.nl.ca/fin/economics](https://www.gov.nl.ca/fin/economics/)

### Legislation and Regulation Recorded This Week
- **BC:** Minister's statement April 10, 2026 on March 2026 housing highlights — 114 affected residential/infrastructure/telecom/transport-logistics projects per policy.json linkage. Source: [news.gov.bc.ca 2026HMA0042-000398](https://news.gov.bc.ca/releases/2026HMA0042-000398).
- **BC:** Minister of Forests statement April 9, 2026 on U.S. softwood lumber administrative review — 21 affected forestry/manufacturing/oil-gas/agriculture projects per linkage. Source: [news.gov.bc.ca 2026FOR0011-000394](https://news.gov.bc.ca/releases/2026FOR0011-000394).
- **BC:** Minister's statement April 9, 2026 on April 2026 rental report — 114 affected projects per linkage. Source: [news.gov.bc.ca 2026HMA0039-000390](https://news.gov.bc.ca/releases/2026HMA0039-000390).

No federal policy announcements recorded in policy.json for the week_of 2026-04-11. policy.json summary: 3 items, all BC-provincial-level.

---

## 4. Capital Projects by Province

### New IAAC Under Review Entries (registered 2026-04-11 or recent week)
- **QC:** Leamy Creek Pathway Re-Naturalization; YUL Montreal-Trudeau Weather Station; Wapizagonke M Bridge closure and floating boardwalk.
- **BC:** Amrize Coquitlam Depots Maintenance Dredge; Gwa'sala-'Nakwaxda'xw Tsulquate Subdivision; Shell Beach Erosion Control Portland Island.
- **ON:** CAFTA Winona Range Upgrades; New Nuclear at Wesleyville; Madahòkì Farm Lodge Expansion.
- **AB:** APEX Utilities Opasikoniwew Housing Authority — Hoole Creek Road Subdivision Phase 2 Gasification; Tsuut'ina Bullhead Road Sewer Line; Mînî Thnî Lift Station.
- **SK:** Northern Lights Casino Expansion; Kistaphinanihk Office Building; Deschambault Lake Road Resurfacing.
- **MB:** Hnausa Wharf Replacement; 98 Manitoba Street Environmental Remediation; New Resort 116 TaWaPit Drive Wasagaming (Cancelled).
- **NS:** Tufts Cove Generation Station Rock Revetment; Meteghan Floating Wharf Replacement; New Glasgow Armoury Deconstruction.
- **NB:** Cap Saint Louis Wharf Repairs 2026; Madawaska Maliseet Road Stormwater Upgrades; CFB Gagetown Graham Road Culvert.
- **NL:** CFB Goose Bay Softball Field Upgrade; Former USAF Experimental Site Fence and Improvements; Point Rousse Port Expansion.
- **PE:** Mink River Wharf Reconstruction; Tignish SCH Breakwater.

Source: [Canadian Impact Assessment Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

### Value Pipeline by Province (parsed_value, projects_all.json, 2026-04-11)
| Province | Count | Total Value | Top Sector | Dominant Status |
|----------|-------|-------------|-----------|-----------------|
| BC | 658 | $509.6B | power_energy | Proposed 254 / Under Construction 153 |
| AB | 739 | $349.6B | government | Proposed 388 / Under Construction 172 |
| ON | 661 | $254.4B | infrastructure | Under Construction 234 / Proposed 152 |
| QC | 502 | $89.6B | education | Approved 281 / Under Review 94 |
| YT | 125 | $47.4B | defence | Under Construction 80 / Proposed 31 |
| NT | 188 | $44.2B | infrastructure | Under Review 92 / Under Construction 57 |
| NU | 57 | $38.9B | infrastructure | Under Construction 36 / Proposed 12 |
| SK | 221 | $38.3B | Other | Proposed 90 / Under Review 85 |
| NL | 1560 | $32.0B | Other | Proposed 1379 / Cancelled 126 |
| NS | 337 | $18.6B | Other | Complete 235 / Proposed 41 |
| MB | 2063 | $14.6B | Other | Under Review 1980 / Under Construction 42 |
| NB | 208 | $5.2B | Other | Under Review 114 / Under Construction 46 |
| PE | 98 | $2.9B | infrastructure | Under Construction 74 / Proposed 15 |

---

## 5. IAAC Monitoring

Federal Impact Assessment Registry entries in the dashboard (iaac.json): 103 total (ON 26, AB 24, QC 13, BC 11, SK 8, MB 6, NL 5, NB 5, NS 3, PE 2, YT/NT/NU 0). All listed entries are currently in Under Review status except for one Manitoba resort file registered as Cancelled. No entries transitioned to Approved or Decision Statement in the week_of 2026-04-11 window. Source: [Canadian Impact Assessment Registry](https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA).

---

## 6. Procurement Awards (≥$5M)

procurement.json (docs/data/procurement.json): 0 contracts recorded for week_of 2026-04-11. Six prior-week rollups (2026-03-14 through 2026-04-11) also show empty arrays. Federal and provincial contract feeds (Open Canada, BuyAndSell, Ontario BPS, BC Bid) produced no matching awards at or above the $5M threshold during the sample window.

---

## 7. Labour Market Stories

### Provincial Unemployment — March 2026 LFS (released April 10, 2026)
| Province | Mar 2026 | Feb 2026 | Change | Source |
|----------|---------|---------|--------|--------|
| NL | 9.5% | 9.2% | +0.3pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| ON | 7.6% | 7.6% | unchanged | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| PE | 7.3% | 7.2% | +0.1pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| NB | 7.0% | 7.0% | unchanged | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| BC | 6.7% | 6.1% | +0.6pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| NS | 6.6% | 7.1% | −0.5pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| AB | 6.5% | 6.3% | +0.2pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| MB | 5.6% | 5.7% | −0.1pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| QC | 5.4% | 5.9% | −0.5pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| SK | 5.0% | 5.6% | −0.6pp | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| **CA** | **6.7%** | **6.7%** | **unchanged** | [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm) |
| YT | 3.9% (Feb) | — | — | [StatsCan Table 14-10-0292-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201) |
| NT | 5.3% (Feb) | — | — | [StatsCan Table 14-10-0292-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201) |
| NU | 10.8% (Feb) | — | — | [StatsCan Table 14-10-0292-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201) |

### Provincial CPI — February 2026 (latest monthly release)
| Province | Feb 2026 y/y | Jan 2026 y/y | Change | Source |
|----------|-------------|-------------|--------|--------|
| PE | +5.4% | +7.3% | −1.9pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| AB | +3.4% | +4.9% | −1.5pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| MB | +3.1% | +3.4% | −0.3pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| NL | +1.8% | +2.3% | −0.5pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| NS | +1.5% | +1.7% | −0.2pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| NB | +1.2% | +2.4% | −1.2pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| BC | +1.0% | +1.3% | −0.3pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| QC | +0.6% | +0.7% | −0.1pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| SK | −0.7% | +1.2% | −1.9pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| ON | −1.1% | −1.6% | +0.5pp | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |
| **CA** | **+1.8%** | **+2.3%** | **−0.5pp** | [StatsCan CPI February 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm) |

### Hiring Spikes (job_monitor RSS via jobs.json)
jobs.json recorded no spikes for the week_of 2026-04-11 (empty `spikes` array across the last six weekly rollups). No sector- or CMA-level hiring anomalies triggered.

### Wage Trends
No provincial wage series are tracked at sub-national level in the indicators feed beyond the LFS employment counts. National average hourly wage (StatsCan LFS, all employees) +3.6% y/y (March 2026). Source: [StatsCan LFS March 2026](https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm).

---

## 8. Coverage Gaps and Priorities

1. **Territorial CPI (YT/NT/NU):** Monthly CPI not published territorially. Whitehorse, Yellowknife, and Iqaluit city-level CPI are separate StatsCan releases. Closing this gap would require adding the three city series to the pipeline data_collection phase.
2. **Provincial prefixed indicator keys stale:** `ON_cpi`, `ON_unemployment`, etc., still reference 2026-02-01 period while the full-province-name keys have updated to 2026-04-11 / 2026-03-01. Dashboard consumers should prefer the full-name records until the prefixed keys are refreshed.
3. **procurement.json empty across six weeks:** 0 contracts recorded. Either the Open Canada / BuyAndSell / Ontario BPS / BC Bid feeds are returning no matches above the $5M threshold, or a pipeline ingestion issue is suppressing results. Worth verifying the procurement_monitor.py run log before next week.
4. **jobs.json empty across six weeks:** same pattern — all weekly rollups empty. job_monitor.py ingestion likely warrants a health check.
5. **Manitoba and NL project counts inflated:** MB at 2063 and NL at 1560 project counts are dominated by federal Green and Inclusive Community Buildings feed entries; median parsed_value is <$5M. Provincial projects above the GDP threshold ($40M MB, $17M NL) number far fewer.
6. **Policy.json sparse outside BC:** All 3 policy items this week were BC-provincial. No federal, ON, QC, AB, or other provincial items registered. This is unusual given that most provinces tabled budgets in March; the pipeline policy_tracker.py cutoff may be lagging the budget-tabling dates.

---

## 9. Master Source Registry

[1] https://www150.statcan.gc.ca/n1/daily-quotidien/260410/dq260410a-eng.htm — StatsCan Labour Force Survey, March 2026 — Statistics Canada — 2026-04-10
[2] https://www150.statcan.gc.ca/n1/daily-quotidien/260318/dq260318a-eng.htm — StatsCan Consumer Price Index, February 2026 — Statistics Canada — 2026-03-18
[3] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201 — Table 36-10-0222-01 Provincial and Territorial Real GDP — Statistics Canada
[4] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004801 — Table 16-10-0048-01 Manufacturing Sales — Statistics Canada
[5] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1210017601 — Table 12-10-0176-01 International Trade in Goods — Statistics Canada
[6] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410029201 — Table 14-10-0292-01 Labour Force Characteristics, Territories — Statistics Canada
[7] https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data — CMHC Housing Market Data (Feb 2026 starts) — CMHC
[8] https://iaac-aeic.gc.ca/050/evaluations?culture=en-CA — Canadian Impact Assessment Registry — IAAC
[9] https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/ — Key Interest Rate — Bank of Canada
[10] https://budget.ontario.ca/2026/contents.html — Ontario 2026 Budget — Government of Ontario — 2026-03-26
[11] https://budget.ontario.ca/2026/chapter-1b-building.html — Ontario 2026 Budget Chapter 1B Building — Government of Ontario
[12] https://www.cp24.com/local/toronto/2026/03/26/ontario-reveals-2026-budget-heres-how-it-could-affect-your-pocketbook/ — Ontario Budget Summary — CP24 — 2026-03-26
[13] https://www.mnp.ca/en/insights/directory/ontario-2026-budget-highlights — Ontario 2026 Budget Highlights — MNP — 2026-03
[14] https://hicksmorley.com/2026/03/27/highlights-of-the-2026-ontario-budget/ — Highlights of the 2026 Ontario Budget — Hicks Morley — 2026-03-27
[15] https://occ.ca/rapidpolicy/2026-ontario-provincial-budget/ — 2026 Ontario Provincial Budget Rapid Policy Update — OCC — 2026-03-26
[16] https://www.finances.gouv.qc.ca/Budget_and_update/budget/documents/Budget2627_BudgetSpeech.pdf — Quebec 2026-27 Budget Speech — Ministère des Finances Québec — 2026-03-25
[17] https://kpmg.com/ca/en/insights/2026/03/highlights-of-the-2026-quebec-budget.html — 2026 Quebec Budget Highlights — KPMG Canada — 2026-03
[18] https://www.quebec.ca/en/news/actualites/detail/budget-2026-2027-press-release-no-3-of-3-more-than-17-billion-to-accelerate-quebecs-economic-transformation-69185 — Quebec Budget Press Release 3 of 3 — Gouvernement du Québec — 2026-03-25
[19] https://www.alberta.ca/budget-highlights — Alberta Budget 2026 Highlights — Government of Alberta — 2026-02-27
[20] https://www.raymondjames.ca/commentary-and-insights/tax-planning/2026/03/02/2026-ab-budget-highlights — 2026 Alberta Budget Highlights — Raymond James Canada — 2026-03-02
[21] https://calgarychamber.com/whats-new/submission-2026-alberta-budget-policy/ — Submission: 2026 Alberta Budget — Calgary Chamber — 2026-01
[22] https://news.gov.bc.ca/releases/2026HMA0042-000398 — Minister's Statement March 2026 Housing Highlights — BC Government News — 2026-04-10
[23] https://news.gov.bc.ca/releases/2026FOR0011-000394 — Minister's Statement on Softwood Lumber Administrative Review — BC Government News — 2026-04-09
[24] https://news.gov.bc.ca/releases/2026HMA0039-000390 — Minister's Statement April 2026 Rental Report — BC Government News — 2026-04-09
[25] https://news.gov.bc.ca/releases/2026HMA0028-000325 — Opening More Homes in West Vancouver — BC Government News — 2026-03-27
[26] https://www.saskatchewan.ca/government/news-and-media/2026/march/18/2026-27-budget-protecting-saskatchewan — Saskatchewan 2026-27 Budget Protecting Saskatchewan — Government of Saskatchewan — 2026-03-19
[27] https://www.raymondjames.com/dotcom-canada/commentary-and-insights/2026/03/20/2026-sk-budget-highlights — 2026 Saskatchewan Budget Highlights — Raymond James — 2026-03-20
[28] https://news.gov.mb.ca/news/index.html?item=73197 — Manitoba Government Announces Budget 2026 — Government of Manitoba — 2026-03
[29] https://www.policyalternatives.ca/news-research/manitoba-budget-2026/ — Manitoba Budget 2026 — Canadian Centre for Policy Alternatives — 2026-03
[30] https://www.canadianinnovators.org/content/manitoba-should-stay-the-course-on-sovereign-value-added- — Manitoba Should Stay the Course — Canadian Innovators — 2026-03
[31] https://ca.finance.yahoo.com/news/highlights-nova-scotias-2026-27-202543812.html — Highlights from Nova Scotia's 2026-27 Budget — Yahoo Finance — 2026-03
[32] https://novascotia.ca/budget/ — Budget 2026 to 2027 — Government of Nova Scotia
[33] https://www.scotiabank.com/ca/en/about/economics/economics-publications/post.other-publications.fiscal — Nova Scotia 2026-27 Budget Post — Scotiabank Economics — 2026-03
[34] https://legnb.ca/content/house_business/61/2/tabled_documents/2026-03-17%20Budget%202026-2027%20%20F — New Brunswick 2026-2027 Budget PDF — Legislative Assembly of New Brunswick — 2026-03-17
[35] https://www.bakertilly.ca/insights/tax-alert-nb-2026-2027-budget — Key Tax Updates NB 2026-2027 Budget — Baker Tilly Canada — 2026-03-17
[36] https://economics.td.com/new-brunswick-budget — 2026 New Brunswick Budget — TD Economics — 2026-03
[37] https://www.gov.nl.ca/fin/economics/ — NL Department of Finance Economics — Government of Newfoundland and Labrador
[38] https://nlfed.ca/2026-nlfl-provincial-budget-submission/ — 2026 NLFL Provincial Budget Submission — Newfoundland and Labrador Federation of Labour — 2026-01
[39] https://www.facebook.com/NFLDBulletin/posts/province-launches-public-input-for-budget-2026january-20 — NL Province Launches Public Input for Budget 2026 — NFLD Bulletin — 2026-01-20
[40] https://www.linkedin.com/posts/province-of-pei_pei-has-announced-its-capital-budget-for-activity-739 — PEI 2026-27 Capital Budget announcement — Province of PEI LinkedIn — 2026-03
[41] https://www.facebook.com/govpe/posts/pei-has-announced-its-capital-budget-for-2026-27-outlining-a-fi — PEI Capital Budget 2026-27 Five-Year Plan — govpe Facebook — 2026-03
[42] https://finance.yahoo.com/economy/policy/articles/prince-edward-island-canada-sign-173100420.html — PEI and Canada Sign Co-operation Agreement — Yahoo Finance — 2026-03
[43] https://publications.gc.ca/collections/collection_2026/dec-ced/Iu90-1-15-2026-eng.pdf — Canada Economic Development for Quebec Regions 2026-27 Plan — Government of Canada
[44] https://www.demersbeaulne.com/en/2026/03/18/quebecs-2026-2027-budget-what-you-need-to-know/ — Quebec 2026-2027 Budget What You Need to Know — Demers Beaulne — 2026-03-18
[45] https://www.statcan.gc.ca/en/subjects-start/economic_accounts/canadian-economic-news/2026-march — Canadian Economic News March 2026 Edition — Statistics Canada — 2026-03
