# Provincial Research — Week of 2026-06-15
Generated: 2026-06-15 (Agent 1B — Provincial Researcher)
Provinces covered: All 13 provinces + 3 territories (16 total)
Source basis: docs/data/indicators.json (StatCan), docs/data/projects_all.json (7,103 projects), docs/data/iaac.json (162 active assessments), docs/data/policy.json (federal Senate bills, week of 2026-06-15), docs/data/data_gap_report.md (Grade B, zero critical gaps)
Cross-edition context: cold start — no prior-week thread carryover available.

---

## 1. Data Quality Audit

### Provincial Indicator Coverage

| Region | Indicators | Projects | Active IAAC | Latest indicator period | Status |
|--------|-----------|----------|-------------|--------------------------|--------|
| ON     | 22        | 678      | 42          | 2026-06-08 (LFS)         | OK |
| QC     | 41        | 490      | 20          | 2026-06-08 (LFS)         | OK |
| AB     | 8         | 700      | 29          | 2026-06-08 (LFS)         | OK |
| BC     | 8         | 632      | 29          | 2026-06-08 (LFS)         | OK |
| SK     | 8         | 149      | 10          | 2026-06-08 (LFS)         | OK |
| MB     | 8         | 1,961    | 9           | 2026-06-08 (LFS)         | OK |
| NS     | 8         | 332      | 8           | 2026-06-08 (LFS)         | OK |
| NB     | 8         | 176      | 7           | 2026-06-08 (LFS)         | OK |
| NL     | 8         | 1,524    | 5           | 2026-06-08 (LFS)         | OK |
| PE     | 8         | 86       | 3           | 2026-06-08 (LFS)         | OK |
| YT     | 4         | 113      | 0           | 2026-06-08 (LFS)         | LIMITED (no monthly territorial CPI / housing starts / building permits) |
| NT     | 4         | 205      | 0           | 2026-06-08 (LFS)         | LIMITED (same) |
| NU     | 4         | 52       | 0           | 2026-06-08 (LFS)         | LIMITED (same) |

### Critical Gaps Found
data_gap_report.md (Agent 0.5) reports Grade B with zero critical gaps. Three structural notes carried forward:
- Territorial CPI/housing-starts series are not produced monthly by StatCan, so YT/NT/NU spotlights rely on Labour Force Survey data plus capital-project pipeline rather than price/permit reads.
- Quebec is the deepest-instrumented province (41 series including monthly retail, wholesale, manufacturing sales, employment full-time/part-time split, and weekly earnings) because Phase 1 fetches the parallel Institut de la statistique du Québec series alongside StatCan.
- Provincial-level policy items in policy.json `week_of=2026-06-15` are dominated by federal Senate bills (S-1 through S-214); ministry RSS feeds for provinces were thin this cycle. Provincial policy referenced in the spotlights below derives from announcements in the project evidence base.

---

## 2. Provincial Spotlights

### Ontario
- **Top story:** Toronto-Quebec City Alto High-Speed Rail remains in detailed environmental and federal Impact Assessment workstreams. Status: Under Review.
  - Source: https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train
- **Key indicators (StatCan Labour Force Survey, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 7.0% (highest of the four largest provinces). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Employment rate 60.2%, participation rate 64.7%. Source: same table.
  - CMHC housing starts (12-month rolling): 62,735 units, down 8.4% from 68,524 in the prior reference. Source: https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data
  - Building permits, April 2026: $4.82B (down from $4.91B in March). StatCan Table 34-10-0066. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601
  - Wage growth (LFS average hourly): +2.1% y/y, decelerating 2.1pp from +4.2% the prior month. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301
  - Real provincial GDP (Q3 2025 reference): goods-producing industries -1.5% q/q; capital investment 0.0%; exports +4.3%. StatCan Table 36-10-0222. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201
- **Project activity:** 678 tracked projects. Status mix: Under Construction 227, Complete 148, Proposed 132, Under Review 86, Approved 83. Top sectors by count: infrastructure 222, transport_logistics 139, healthcare 112, mining 37, power_energy 35.
- **Anchor projects with verifiable source URLs:**
  - Eglinton Crosstown West Extension — Under Construction. Source: https://www.metrolinx.com/projects-and-programs/eglinton-crosstown-west-extension
  - CFB Trenton Strategic Tanker Transport Capability Infrastructure (MOB-East) — Under Construction. Source: https://canada.constructconnect.com/dcn/news/infrastructure/2025/12/construction-army-descends-on-cfb-trenton-as-construction-of-tanker-base-set-to-start
  - Toromont Lands / Highway 7 Mixed-Use Redevelopment — Approved.
- **IAAC monitoring:** 42 Ontario projects active in the federal Impact Assessment Registry. Notable: Marten Falls Community Access Road (Ring of Fire access corridor) Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** Ontario carries the lowest employment rate of the major provinces (60.2%) and the highest unemployment (7.0%) at a moment when its housing-starts series is showing the largest absolute year-over-year contraction (-5,789 units against the prior reference). 132 Proposed projects sit in the Ontario pipeline without yet advancing to Approved.

### Quebec
- **Top story:** Battery and EV manufacturing pipeline continues to advance. Quebec Battery Manufacturing Investment Program in Approved status; Des Neiges Wind Farm (Secteur Sud and Charlevoix phases) Under Construction.
  - Source: https://www.lakelandtoday.ca/national-news/construction-work-officially-begins-on-3-billion-wind-farm-in-quebec-government-says-the-largest-project-in-canadian-history
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08; ISQ parallel series):**
  - Unemployment rate 5.6%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Employment rate 60.6%, participation rate 64.1%.
  - Provincial CPI +1.5% y/y; ISQ CPI index 164.3 (March 2026 reference). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - QC employment (LFS): 4,579.0 thousand (April 2026 reference), full-time 3,655.8K, part-time 923.1K.
  - QC manufacturing sales: $228,889M (March 2026). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004801
  - QC retail sales: $193,070M (February 2026). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801
  - QC weekly earnings: $1,280.65 (February 2026 reference, SEPH).
  - QC building permits residential February 2026: $22,783M y/y rolling. Non-residential: $6,513M.
  - Wage growth (LFS average hourly): +4.7% y/y, decelerating 1.2pp from +5.9%.
- **Project activity:** 490 projects tracked. Status mix: Approved 274, Under Review 100, Proposed 60, Under Construction 41, Complete 14. Top sectors: education 110, infrastructure 99, power_energy 49, healthcare 44, transport_logistics 40.
- **Anchor projects:**
  - Des Neiges Wind Farm (Charlevoix and Sud) — Under Construction, $3B program per source.
  - General Dynamics OTS Le Gardeur 155mm projectile load-assemble-pack facility — Approved. Source: https://www.canada.ca/en/department-national-defence/news/2026/03/minister-mcguinty-announces-investments-in-canadas-defence-industrial-base.html
  - General Dynamics OTS Valleyfield Nitrocellulose Production Facility — Approved. Source: same DND release.
  - Glencore Horne Smelter Emissions Reduction Project (Rouyn-Noranda) — Proposed.
- **IAAC monitoring:** 20 Quebec projects active. Port of Quebec International Container Terminal Project remains Under Review; Contrecoeur Marine Terminal Quay 01 seabed raising Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** Quebec runs the lowest unemployment among the major provinces (5.6%) and the deepest active project pipeline by sector breadth — defence (Le Gardeur, Valleyfield), wind power at multi-billion-dollar scale, and education (110 projects). Wage growth is decelerating from a high base (+5.9% → +4.7%), still second only to PE on this metric.

### Alberta
- **Top story:** Calgary Green Line LRT Phase 1 remains Under Construction; Coalspur Mines Vista Coal Mine Phase II Under Review at IAAC.
  - Source (Green Line): https://majorprojects.alberta.ca/details/Calgary-Green-Line-LRT-Phase-1/873
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 6.6%; employment rate 64.6% (highest of the major provinces); participation rate 69.1% (highest in Canada outside the territories). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +1.1% y/y (below the national pace). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +2.7% (database current reading).
  - Housing starts (12-month rolling): 46,064 units, down 4.9% from 48,422.
  - Building permits April 2026: $1.63B, up from $1.58B in March.
  - Wage growth (LFS): +4.8% y/y, decelerating 1.7pp from +6.5%.
- **Project activity:** 700 projects tracked (highest non-wide-net provincial count). Status mix: Proposed 361, Under Construction 175, Complete 83, Under Review 63, Approved 17. Top sectors: power_energy 161, government 141, infrastructure 104, residential 64, oil_gas 61.
- **Anchor projects:**
  - Calgary Green Line LRT Phase 1 — Under Construction.
  - NOVA Gas Transmission GPML Loop No. 4 (Valhalla North Section) — Under Construction. Source: https://www.cer-rec.gc.ca/en/applications-hearings/view-applications-projects/gpml-loop-no-4-valhalla-north-section.html
  - Enbridge Sunrise Natural Gas Pipeline Expansion — Approved.
  - CGC Inc. Wallboard Manufacturing Plant in Wheatland County — Complete (commissioned 2026-06). Source: https://canada.constructconnect.com/joc/news/projects/2026/06/cgc-inc-opens-210m-wallboard-plant-in-wheatland-county
- **IAAC monitoring:** 29 Alberta projects active. Suncor Base Mine Extension Project Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** Alberta posts the highest participation rate in the country (69.1%) and the second-highest employment rate (64.6%) while CPI runs below national pace (+1.1%). The project pipeline is sector-skewed to power_energy (161 records) and government (141 records); 361 of the 700 projects sit in Proposed status, the largest absolute Proposed backlog of any province.

### British Columbia
- **Top story:** LNG project pipeline continues to dominate. LNG Canada Phase 2 Expansion logged as Complete; Woodfibre LNG project Under Construction; Ksi Lisims LNG Approved.
  - Source (Ksi Lisims): https://projects.eao.gov.bc.ca/project/60edc23bc69c5e0023a12539
  - Source (Woodfibre): https://projects.eao.gov.bc.ca/project/588511e1aaecd9001b8272e7
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 6.8%; employment rate 60.5%; participation rate 64.9%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +2.7% y/y (highest among the four largest provinces). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +1.2%.
  - Housing starts (12-month rolling): 40,133 units, down 2.4% from 41,128.
  - Building permits April 2026: $1.82B, down sharply from $3.02B in March (-$1.20B m/m).
  - Wage growth: +1.5% y/y, decelerating 1.0pp from +2.5%.
- **Project activity:** 632 projects tracked. Status mix: Proposed 195, Under Construction 160, Under Review 144, Approved 53, On Hold 28. Top sectors: power_energy 122, mining 94, residential 71, transport_logistics 69, commercial_mixed 34.
- **Anchor projects:**
  - LNG Canada Phase 2 Expansion — Complete.
  - Berg Copper-Molybdenum-Silver Mine — Proposed. Source: https://www2.gov.bc.ca/gov/content/employment-business/economic-development/industry/bc-major-projects-inventory
  - Cambie Street Bridge Seismic Retrofit — Approved (~$200M).
- **IAAC monitoring:** 29 BC projects active. GCT Deltaport Expansion - Berth Four Project Under Review; BC Hydro Second Narrows tower geotechnical investigation Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** BC's building-permits series fell from $3.02B to $1.82B between March and April 2026, a $1.20B one-month drop and the largest absolute provincial decline in the dataset. The drop coincides with CPI running highest among major provinces (+2.7%) and wage growth at the slowest pace (+1.5%). 28 projects on the BC roster sit in On Hold status, the largest On Hold count in the database.

### Saskatchewan
- **Top story:** Bell AI Fabric 300 MW Data Centre (Rural Municipality of Sherwood) in Proposed status alongside the Rook I uranium project Approved at IAAC. Rose Valley Wind Project Under Construction.
  - Source (Bell AI Fabric): https://canada.constructconnect.com/joc/news/projects/2026/05/bird-selected-for-massive-bell-canada-ai-data-centre-near-regina
  - Source (Rook I): IAAC registry, https://iaac-aeic.gc.ca/050/evaluations/
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 6.2%; employment rate 62.6%; participation rate 66.8%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +1.1% y/y. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +3.4% (highest of the major provinces).
  - Housing starts (12-month rolling): 4,472 units, down 17.6% from 5,428 — steepest percentage decline of any province in the current reference. Source: https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data
  - Building permits April 2026: $254M, down from $320M in March.
  - Wage growth: +4.1% y/y, decelerating 0.4pp from +4.5%.
- **Project activity:** 149 projects tracked. Status mix: Proposed 51, Under Construction 41, Under Review 41, Complete 9, Approved 7. Top sectors: infrastructure 41, power_energy 28, mining 24, transport_logistics 9, telecom 7.
- **Anchor projects:**
  - Rose Valley Wind Project — Under Construction.
  - Rook I uranium mine (NexGen Energy) — Approved.
  - Bell AI Fabric 300 MW Data Centre — Proposed.
  - Thor Project Alumina Production Facility (Canadian Energy Metals) — Proposed.
- **IAAC monitoring:** 10 Saskatchewan projects active. Bell AI Fabric Data Centre Project Under Review; Beardy's and Okemasis Cree Nation Solid Waste Removal and Landfill Decommissioning Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** Saskatchewan combines the highest GDP growth read among major provinces (+3.4%) with the steepest housing-starts contraction (-17.6%). The telecom sector enters the SK pipeline materially via the Bell AI Fabric data-centre proposal — first 300 MW-scale AI infrastructure record in the Saskatchewan dataset.

### Manitoba
- **Top story:** Lynn Lake Gold Project Under Construction at IAAC; Portage Place Redevelopment in Winnipeg Under Construction; Deep Sky Manitoba Carbon Removal Facility Proposed.
  - Source (Lynn Lake): https://iaac-aeic.gc.ca/050/evaluations/proj/80140
  - Source (Deep Sky): https://www.deepskyclimate.com/blog/deep-sky-to-build-500-000-tonne-carbon-removal-facility---one-of-the-largest-in-the-world---in-manitoba
  - Source (Portage Place): https://portageplace.ca/development-updates/
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 5.5% (lowest among provinces). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Employment rate 63.1%; participation rate 66.8%.
  - Provincial CPI +3.5% y/y (tied with PE for the highest provincial CPI). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +1.1%.
  - Housing starts (12-month rolling): 7,361 units, down 5.9% from 7,824.
  - Building permits April 2026: $387M, down from $461M in March.
  - Wage growth: +1.8% y/y, decelerating 0.6pp from +2.4% (slowest among prairie provinces).
- **Project activity:** 1,961 projects tracked — the largest count in the database, driven by a wide-net municipal/agricultural ingest. Status mix: Under Review 1,880, Under Construction 39, Proposed 26, Approved 14, Complete 1. Top sectors: infrastructure 617, agriculture 306, power_energy 278, manufacturing 225, environment 146.
- **Anchor projects:**
  - Lynn Lake Gold Project — Under Construction (Alamos Gold; IAAC-tracked).
  - Deep Sky Manitoba Carbon Removal Facility — Proposed (targeting 500,000 tCO2/yr).
  - Portage Place Redevelopment — Under Construction.
  - Endayaan Omaa Housing Development at Naawi-Oodena (Treaty One Nations) — Under Construction. Source: https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/canada-announces-funding-treaty-one-nations
  - Red-Seine-Rat Cooperative Wastewater Treatment Facility — Approved. Source: https://canada.constructconnect.com/joc/news/infrastructure/2026/02/aecon-awarded-contract-to-build-red-seine-rat-wastewater-facility
- **IAAC monitoring:** 9 Manitoba projects active. Twinning of the Trans-Canada Highway in Manitoba Under Review.
- **Distinctive thread:** Manitoba runs the lowest provincial unemployment (5.5%) at the same time as the highest provincial CPI tied with PE (+3.5%). The Lynn Lake Gold and Deep Sky carbon-removal projects together represent the province's two largest greenfield records in the 2026 pipeline.

### Nova Scotia
- **Top story:** Defence procurement activity continues to dominate. Canadian Submarine Program — Hanwha Ocean Proposal in Proposed status; River-class Destroyer Land-Based Test Facility at Hartlen Point Under Construction.
  - Source (River-class): https://www.canada.ca/en/department-national-defence/news/2026/01/the-department-of-national-defence.html
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 7.1%; employment rate 57.3%; participation rate 61.7%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +1.8% y/y. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +2.7%.
  - Housing starts (12-month rolling): 7,241 units, down 2.5% from 7,425.
  - Building permits April 2026: $292M, up from $243M in March (+$49M m/m).
  - Wage growth: +4.2% y/y, accelerating 0.3pp from +3.9% — one of only two provinces where wage growth accelerated rather than decelerated this cycle (the other is NB).
- **Project activity:** 332 projects tracked. Status mix: Complete 234, Under Construction 41, Proposed 27, Under Review 17, Approved 12. Top sectors: power_energy 113, mining 80, infrastructure 48, transport_logistics 25, environment 20.
- **Anchor projects:**
  - River-class Destroyer Land-Based Test Facility — Hartlen Point — Under Construction.
  - Goldboro Gold (Signal Gold) — Complete. Source: https://novascotia.ca/nse/ea/signal-gold-goldboro-project
  - Beaver Dam Mine Project — Under Review. Source: https://novascotia.ca/nse/ea//nse/ea/beaver-dam-mine-project.asp
  - Halifax Transit Mill Cove Ferry Service Phase 2 — Approved.
- **IAAC monitoring:** 8 Nova Scotia projects active. Grand Passage Lifeboat Station (Digby County) Under Review; Removal of Antennas 602/603 at Newport Corner Naval Radio Station CFB Halifax — Cancelled (one of the few Cancelled status transitions logged in the period). Source: https://iaac-aeic.gc.ca/050/evaluations/
- **Distinctive thread:** Nova Scotia is one of two provinces with accelerating wage growth (+4.2% from +3.9%) while building-permits dollar value rose $49M m/m. The defence sector — Hanwha submarine proposal plus Hartlen Point test facility — anchors the proposed-and-under-construction pipeline.

### New Brunswick
- **Top story:** CFB Gagetown Range and Training Area Recapitalization and Ground-Based Air Defence infrastructure Approved; Brighton Mountain Wind Project (J.D. Irving) Approved.
  - Source (CFB Gagetown): https://www.canada.ca/en/department-national-defence/news/2026/04/canada-invests-in-infrastructure-at-cfb-gagetown.html
  - Source (Brighton Mountain): https://www.cbc.ca/news/canada/new-brunswick/jd-irving-wind-farm-brighton-mountain-1.7192190
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 7.2%; employment rate 56.1%; participation rate 60.5%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +0.6% y/y (lowest in the country). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +1.8%.
  - Housing starts (12-month rolling): 5,860 units, up 0.3% from 5,841 — only province other than PE with a positive y/y housing-starts read.
  - Building permits April 2026: $183M, down from $218M in March.
  - Wage growth: +3.6% y/y, accelerating 0.1pp from +3.5%.
- **Project activity:** 176 projects tracked. Status mix: Under Review 112, Under Construction 45, Approved 10, Proposed 9. Top sectors: Other 53, infrastructure 41, tourism_culture 15, power_energy 13, transport_logistics 13.
- **Anchor projects:**
  - Brighton Mountain Wind Project — Approved.
  - CFB Gagetown Range and Training Area Recapitalization — Approved.
  - New Brunswick Museum Construction Phase — Approved.
  - New Brunswick High-Speed Internet Expansion — Approved. Source: https://www.canada.ca/en/innovation-science-economic-development/news/2026/05/government-of-canada-takes-action.html
- **IAAC monitoring:** 7 New Brunswick projects active. Dorchester Health Centre of Excellence Construction Under Review; Fredericton Farm Services Building Replacement Under Review.
- **Distinctive thread:** New Brunswick logs the lowest provincial CPI in Canada (+0.6%) at the same time as one of only two positive housing-starts reads. Defence (CFB Gagetown) and renewable power (Brighton Mountain) dominate the Approved column.

### Newfoundland and Labrador
- **Top story:** EverWind Burin Peninsula Green Fuels Project Proposed; 5 Wing Goose Bay Energy Performance Contract Approved.
  - Source (5 Wing Goose Bay): https://www.canada.ca/en/department-national-defence/news/2026/04/minister-thompson-announces-largest-energy-performance-contract.html
  - Source (EverWind): https://finance.yahoo.com/news/everwind-registers-environmental-assessment-green-144200416.html
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 9.6% (highest of the provinces). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Employment rate 51.3% (lowest of the provinces); participation rate 56.7% (lowest of the provinces).
  - Provincial CPI +2.9% y/y. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +2.4%.
  - Housing starts (12-month rolling): 1,242 units, down 3.9% from 1,293.
  - Building permits April 2026: $49M, up from $44M in March.
  - Wage growth: +0.9% y/y, decelerating 0.3pp from +1.2% (slowest provincial wage growth).
- **Project activity:** 1,524 projects tracked (second-largest provincial count after Manitoba's wide-net ingest). Status mix: Proposed 1,338, Cancelled 124, Under Construction 34, Under Review 15, Approved 12. Top sectors: infrastructure 258, transport_logistics 236, mining 219, forestry 218, agriculture 146.
- **Anchor projects:**
  - 5 Wing Goose Bay Energy Performance Contract — Approved.
  - EverWind Burin Peninsula Green Fuels Project — Proposed.
  - Duck Pond Copper-Zinc Mine — Proposed. Source: https://www.canadianminingjournal.com/news/copper-zinc-development-green-light-given-for-duck-pond
  - Cartwright Junction to Happy Valley-Goose Bay Trans-Labrador Highway — Proposed.
- **IAAC monitoring:** 5 NL projects active including Mortier Bay Marine Terminal Project Under Review.
- **Distinctive thread:** NL has the highest unemployment (9.6%), lowest employment rate (51.3%) and lowest participation rate (56.7%) in the country, paired with the slowest wage growth (+0.9%). The 124 Cancelled-status projects on the NL roster are the largest absolute Cancelled count of any province.

### Prince Edward Island
- **Top story:** Charlottetown District Energy Waste Processing Facility (Enwave) Under Construction; MDS Coating Technologies Facility Expansion (Slemon Park) Approved.
  - Source (Enwave): https://www.hpacmag.com/heating-plumbing-air-conditioning-general/enwave-to-build-prince-edward-island-district-energy
  - Source (MDS Coating): https://www.princeedwardisland.ca/en/news/provincial-and-federal-governments-support-next-phase-of-mds-coating
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 6.7%; employment rate 62.0%; participation rate 66.5%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - Provincial CPI +3.5% y/y (tied with MB for highest). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
  - GDP growth: +3.6% (highest in Canada).
  - Housing starts (12-month rolling): 1,153 units, up 10.0% from 1,048 — only positive double-digit housing-starts read in the country.
  - Building permits April 2026: $70M, up from $55M in March (+$15M, the largest percentage gain of any province).
  - Wage growth: +7.6% y/y, decelerating 1.0pp from +8.6% — highest provincial wage growth.
- **Project activity:** 86 projects tracked. Status mix: Under Construction 69, Approved 7, Proposed 5, Under Review 5. Top sectors: infrastructure 40, tourism_culture 17, power_energy 13, education 5, transport_logistics 3.
- **Anchor projects:**
  - Charlottetown District Energy Waste Processing Facility (Enwave) — Under Construction.
  - MDS Coating Technologies Facility and Equipment Expansion at Slemon Park — Approved.
  - Abegweit's Community Recreation Centre — Approved.
  - Prince County Innovation & Learning Centre — Proposed.
- **IAAC monitoring:** 3 PE projects active — Wharf Reconstruction at Bay Fortune Small Craft Harbour Under Review; Slipway and Breakwater Reconstruction at Seacow Pond SCH Under Review; Breakwater Construction at Tignish SCH Under Review.
- **Distinctive thread:** PE is the country's growth outlier this cycle — highest GDP growth (+3.6%), highest provincial wage growth (+7.6%), highest housing-starts y/y change (+10.0%), tied highest CPI (+3.5%). Almost the entire active project pipeline (69 of 86) is in Under Construction status — the highest Under-Construction ratio of any province.

### Yukon
- **Top story:** Yukon municipal infrastructure pipeline carries multiple Under Construction water/sewer/road upgrades funded via Infrastructure Canada.
  - Source: https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 6.3%; employment rate 70.3% (highest in Canada); participation rate 75.0% (highest in Canada). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - GDP (annual, 2024 reference): -3.3%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201
  - Note: territorial CPI, housing starts, and building permits are not published monthly by StatCan.
- **Project activity:** 113 projects tracked. Status mix: Under Construction 78, Proposed 20, Approved 11, Under Review 2, On Hold 1. Top sectors: infrastructure 56, tourism_culture 16, government 9, transport_logistics 7, power_energy 6.
- **Anchor projects:**
  - Faro Water, Sewer and Road Upgrades Phase 2 — Under Construction.
  - Haines Junction Infrastructure Upgrades Phase 4 — Under Construction.
  - Mayo Water, Sewer and Road Upgrades Phase 4 — Under Construction.
  - Dawson City Recreation Centre Construction — Proposed.
  - Addressing Community Flooding in Carmacks and Little Salmon Carmacks First Nation — Proposed.
- **IAAC monitoring:** No Yukon projects in the federal Impact Assessment Registry this period.
- **Distinctive thread:** Yukon's labour-force participation rate (75.0%) and employment rate (70.3%) are the highest in Canada. The capital-project pipeline is dominated by municipal water/sewer/road work funded through Infrastructure Canada's federal-municipal cost-share programs.

### Northwest Territories
- **Top story:** Hay River Water Treatment Plant Approved; Highway 1, 4, and 7 Reconstruction projects active.
  - Source (Hay River): https://www.canada.ca/en/housing-infrastructure-communities/news/2026/04/building-canada-strong-by-investing.html
  - Source (highways): https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 7.9%; employment rate 65.9%; participation rate 71.5%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - GDP (annual, 2024 reference): -1.1%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201
  - Territorial CPI, housing starts, building permits — not produced monthly by StatCan.
- **Project activity:** 205 projects tracked. Status mix: Under Review 108, Under Construction 56, Approved 22, Proposed 17, Complete 2. Top sectors: infrastructure 69, mining 56, power_energy 19, Other 14, oil_gas 13.
- **Anchor projects:**
  - Highway 1 Reconstruction — Under Construction.
  - Highway 4 Reconstruction — Under Construction.
  - Highway 7 Reconstruction — Approved.
  - Hay River Water Treatment Plant — Approved.
  - Endacho Healing Lodge — Approved.
  - Airport Road Flood Upgrades — Approved.
- **IAAC monitoring:** No NT projects active in the federal Registry this period (territorial projects of equivalent scope flow through the Mackenzie Valley Environmental Impact Review Board rather than IAAC).
- **Distinctive thread:** NT carries the largest territorial mining-project count (56 records) in the dataset and a 2024 GDP read of -1.1% — the second consecutive year of territorial GDP contraction in the historical series, attributed by StatCan's Provincial and Territorial GDP report to declining diamond-mine output.

### Nunavut
- **Top story:** Iqaluit Nukkiksautiit Hydroelectric Project Proposed — Nunavut's first major hydroelectric record.
  - Source: https://www.canada.ca/en/crown-indigenous-relations-northern-affairs/news/2025/11/iqaluit-nukkiksautiit-hydroelectric.html
- **Key indicators (StatCan LFS, reference period 2026-05, release 2026-06-08):**
  - Unemployment rate 12.5% (highest in Canada); employment rate 56.9%; participation rate 65.0%. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703
  - GDP (annual, 2024 reference): +7.5% (highest in Canada). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201
  - Territorial CPI, housing starts, building permits — not produced monthly.
- **Project activity:** 52 projects tracked. Status mix: Under Construction 29, Proposed 13, Approved 7, Complete 3. Top sectors: infrastructure 16, tourism_culture 6, Other 4, mining 4, transport_logistics 4.
- **Anchor projects:**
  - Iqaluit Nukkiksautiit Hydroelectric Project — Proposed.
  - Arctic Bay Water Treatment Plant Construction Phase — Proposed.
  - Pond Inlet Water Treatment Plant Construction Phase — Proposed.
  - Sanikiluaq Water Treatment Plant Detailed Design & Construction — Proposed.
  - Grise Fiord Water Treatment Plant Upgrades Construction — Approved.
- **IAAC monitoring:** No Nunavut projects in the IAAC registry this period (Nunavut projects flow through the Nunavut Impact Review Board).
- **Distinctive thread:** Nunavut posts the highest 2024 GDP read in the country (+7.5%) and simultaneously the highest unemployment (12.5%) — a structural pattern where the territorial economy's GDP is dominated by mining output that does not translate proportionally to local employment. The hydroelectric proposal for Iqaluit is the first such record in the Nunavut pipeline.

---

## 3. Policy Developments Summary

### Federal legislation (week_of=2026-06-15, from policy.json)
20 federal Senate bills appear in the latest week's `top_developments` array. None carry a province tag or affected_sectors. Selected items relevant to capital-investment pipeline:
- S-1 (45-1) — An Act relating to railways. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-1
- S-3 (45-1) — Weights and Measures / Electricity and Gas Inspection Acts amendment. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-3
- S-4 (45-1) — Energy Efficiency Act amendment. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-4
- S-5 (45-1) — Connected Care for Canadians Act. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-5
- S-212 (45-1) — National Strategy for Children and Youth Act (tagged `capital_investment`). Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-212

### Provincial budgets and fiscal announcements
No provincial budgets appear in policy.json `week_of=2026-06-15`. Provincial fiscal context flows through the project evidence base — see the per-province spotlights for Approved/Funded items.

### Major procurement signals (embedded in project evidence)
- DND announcement, 2026-03: defence industrial base investments tied to General Dynamics OTS Le Gardeur and Valleyfield (Quebec). Source: https://www.canada.ca/en/department-national-defence/news/2026/03/minister-mcguinty-announces-investments-in-canadas-defence-industrial-base.html
- DND announcement, 2026-04: largest-ever Energy Performance Contract awarded for 5 Wing Goose Bay (NL). Source: https://www.canada.ca/en/department-national-defence/news/2026/04/minister-thompson-announces-largest-energy-performance-contract.html
- DND announcement, 2026-04: infrastructure investment at CFB Gagetown (NB). Source: https://www.canada.ca/en/department-national-defence/news/2026/04/canada-invests-in-infrastructure-at-cfb-gagetown.html
- ISED announcement, 2026-05: New Brunswick High-Speed Internet Expansion. Source: https://www.canada.ca/en/innovation-science-economic-development/news/2026/05/government-of-canada-takes-action.html
- Housing, Infrastructure and Communities Canada, 2026-04: Hay River (NT) water treatment plant funding. Source: https://www.canada.ca/en/housing-infrastructure-communities/news/2026/04/building-canada-strong-by-investing.html
- Department of Finance, 2026-05: Small Craft Harbours Program National Repair and Renewal (~$1B). Source: https://www.canada.ca/en/department-finance/news/2026/05/government-of-canada-investing-nearly-1-billion.html
- Treaty One Nations / CMHC, 2026: Naawi-Oodena (MB) housing announcement. Source: https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/canada-announces-funding-treaty-one-nations

---

## 4. Capital Projects — Pipeline Aggregates by Province

| Province | Projects | Top sector (count) | Largest status group |
|----------|---------:|--------------------|----------------------|
| MB | 1,961 | infrastructure (617) | Under Review (1,880) |
| NL | 1,524 | infrastructure (258) | Proposed (1,338) |
| AB | 700 | power_energy (161) | Proposed (361) |
| ON | 678 | infrastructure (222) | Under Construction (227) |
| BC | 632 | power_energy (122) | Proposed (195) |
| QC | 490 | education (110) | Approved (274) |
| NS | 332 | power_energy (113) | Complete (234) |
| NT | 205 | infrastructure (69) | Under Review (108) |
| NB | 176 | Other (53) | Under Review (112) |
| SK | 149 | infrastructure (41) | Proposed (51) |
| YT | 113 | infrastructure (56) | Under Construction (78) |
| PE | 86 | infrastructure (40) | Under Construction (69) |
| NU | 52 | infrastructure (16) | Under Construction (29) |

Total tracked across the 13 jurisdictions: 7,098 projects (database total 7,103 including a small `provinces_additional` overlap).

---

## 5. IAAC Monitoring — Active Federal Assessments

Active count by province (from docs/data/iaac.json, lastSeen=2026-06-15):

| Province | Active IAAC | Notable items |
|----------|------------:|---------------|
| ON | 42 | Marten Falls Community Access Road; Rockcliffe Control Station Relocation |
| BC | 29 | GCT Deltaport Expansion Berth Four; BC Hydro Second Narrows tower investigation |
| AB | 29 | Suncor Base Mine Extension; Parks Canada Brazeau Lake Bridge Replacement |
| QC | 20 | Port of Quebec International Container Terminal; Contrecoeur Marine Terminal Quay 01 |
| SK | 10 | Bell AI Fabric Data Centre; Beardy's & Okemasis Cree Nation Solid Waste Removal |
| MB | 9 | Lynn Lake Gold (Under Construction); Trans-Canada Highway Twinning |
| NS | 8 | Grand Passage Lifeboat Station; CFB Halifax Antenna Removal (Cancelled) |
| NB | 7 | Dorchester Health Centre of Excellence; Fredericton Farm Services Building |
| NL | 5 | Mortier Bay Marine Terminal; MIFN MEGH Cabin |
| PE | 3 | Bay Fortune SCH wharf; Seacow Pond SCH slipway; Tignish SCH breakwater |
| YT/NT/NU | 0 | Northern projects flow through territorial regulators, not IAAC |

Total active IAAC entries this period: 162. Registry portal: https://iaac-aeic.gc.ca/050/evaluations/

---

## 6. Labour Market Snapshot — All Provinces and Territories

StatCan Labour Force Survey, reference period 2026-05, release date 2026-06-08. Source table for all rates: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703

| Region | Unemployment | Employment rate | Participation rate | Wage growth (y/y) |
|--------|-------------:|----------------:|-------------------:|------------------:|
| MB | 5.5% | 63.1% | 66.8% | +1.8% |
| QC | 5.6% | 60.6% | 64.1% | +4.7% |
| SK | 6.2% | 62.6% | 66.8% | +4.1% |
| YT | 6.3% | 70.3% | 75.0% | n/a |
| AB | 6.6% | 64.6% | 69.1% | +4.8% |
| PE | 6.7% | 62.0% | 66.5% | +7.6% |
| BC | 6.8% | 60.5% | 64.9% | +1.5% |
| ON | 7.0% | 60.2% | 64.7% | +2.1% |
| NS | 7.1% | 57.3% | 61.7% | +4.2% |
| NB | 7.2% | 56.1% | 60.5% | +3.6% |
| NT | 7.9% | 65.9% | 71.5% | n/a |
| NL | 9.6% | 51.3% | 56.7% | +0.9% |
| NU | 12.5% | 56.9% | 65.0% | n/a |

Wage growth source (LFS average hourly earnings, all employees): https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301

### Wage growth direction (LFS average hourly y/y, May 2026 vs prior reference)
- **Accelerating:** NS (+3.9 → +4.2), NB (+3.5 → +3.6).
- **Decelerating:** PE (+8.6 → +7.6), AB (+6.5 → +4.8), QC (+5.9 → +4.7), SK (+4.5 → +4.1), ON (+4.2 → +2.1), MB (+2.4 → +1.8), BC (+2.5 → +1.5), NL (+1.2 → +0.9).

### CPI direction (StatCan provincial CPI y/y, May 2026)
- Lowest: NB +0.6%, AB +1.1%, SK +1.1%, QC +1.5%.
- Highest: MB +3.5%, PE +3.5%, NL +2.9%, BC +2.7%.
- Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401

### Housing-starts direction (12-month rolling, May 2026 reference vs prior)
- Positive: PE +10.0%, NB +0.3%.
- Negative: SK -17.6%, ON -8.4% (largest absolute decline), MB -5.9%, AB -4.9%, NL -3.9%, NS -2.5%, BC -2.4%.
- Source: https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data

---

## 7. Cross-Province Patterns

1. **The "low CPI, low wage growth" pair:** BC carries the highest CPI among major provinces (+2.7%) and slowest wage growth (+1.5%). NB carries the lowest CPI (+0.6%) but mid-range wage growth (+3.6%). The cross-reference engine does not link these into a single causal story; both are reported as distinct provincial reads.
2. **Atlantic wage acceleration:** NS and NB are the only two provinces where wage growth accelerated rather than decelerated between the prior and current LFS reference.
3. **PE outlier cluster:** PE simultaneously holds the highest GDP growth (+3.6%), highest wage growth (+7.6%), highest housing-starts growth (+10.0%), and tied-highest CPI (+3.5%). The province's pipeline is 80% Under Construction (69 of 86 projects), the highest construction-intensity ratio in the dataset.
4. **Saskatchewan housing-starts contraction:** -17.6% is the steepest housing-starts read in the country, against +3.4% GDP growth — a divergence the cross-reference engine flags but does not interpret.
5. **Newfoundland and Labrador labour weakness:** highest unemployment (9.6%), lowest employment rate (51.3%), lowest participation (56.7%), slowest wage growth (+0.9%) — a four-axis weak labour signal.
6. **Nunavut paradox:** highest 2024 GDP growth (+7.5%) and highest unemployment (12.5%) — territorial mining output dominates GDP without translating proportionally to local employment.
7. **Defence-heavy Atlantic/Quebec corridor:** General Dynamics OTS Le Gardeur and Valleyfield (QC), CFB Gagetown recapitalization (NB), CFB Trenton MOB-East (ON), River-class Destroyer Land-Based Test Facility at Hartlen Point (NS), 5 Wing Goose Bay EPC (NL) — a clear defence-industrial pipeline running east of the Manitoba border this cycle.

---

## 8. Coverage Gaps and Priorities

1. **Provincial ministry RSS feeds underrepresented in latest policy.json week.** All 20 entries in `top_developments` for week_of=2026-06-15 are federal Senate bills. Provincial budgets, ministry releases, and provincial Gazette items not surfacing. Recommend a one-time re-pull of provincial policy feeds for week 24 of 2026 before Agent 2B (provincial analyst) consumes this research.
2. **Territorial CPI / housing starts:** YT/NT/NU lack monthly price and starts indicators because StatCan does not publish those series for territories. Any territory-level price commentary must use the territorial GDP annual series only (2024 reference).
3. **Project value coverage:** A large share of the 7,103 projects carry no `value` figure (parsed_value=0 across most top-by-value queries). This is a known limitation — the URL hard gate is satisfied (every project has an evidence URL) but value extraction remains incomplete. Per CLAUDE.md `value_confirmed`/`value_high`/`value_low` columns are additive-only when ranges are stated.
4. **Manitoba wide-net ingest:** 1,880 of 1,961 MB projects sit in Under Review status — a known artifact of the municipal/agricultural ingest pipeline. Aggregate sector counts for MB should be interpreted with this volume context.

---

## 9. Master Source Registry

[1] StatCan Table 14-10-0287 — Labour Force Survey provincial monthly rates — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703 — Reference 2026-05, released 2026-06-08 — All provincial unemployment/employment/participation rates above
[2] StatCan Table 18-10-0004 — Consumer Price Index, monthly, provinces — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401 — 2026-05 — All provincial CPI y/y reads above
[3] StatCan Table 14-10-0063 — Employee wages by industry, monthly — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301 — 2026-05 — All wage growth reads
[4] StatCan Table 34-10-0066 — Building permits by census metropolitan area / province — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601 — 2026-04 — All building permit values above
[5] StatCan Table 36-10-0402 — GDP, expenditure-based, provincial and territorial, annual — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201 — 2024 reference — Territorial GDP reads
[6] StatCan Table 36-10-0222 — GDP, income and expenditure accounts, provincial — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201 — Q3 2025 — Ontario goods-producing/capital-investment/exports detail
[7] StatCan Table 14-10-0022 — LFS employment by sector, monthly — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201 — 2026-05 — Provincial employment detail
[8] CMHC Housing Data — https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data — 2026-05 reference, 12-month rolling — All housing-starts reads
[9] IAAC Registry — https://iaac-aeic.gc.ca/050/evaluations/ — 2026-06-15 — All IAAC project status reads
[10] Alto High-Speed Rail — https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train — ON top story
[11] Metrolinx Eglinton Crosstown West Extension — https://www.metrolinx.com/projects-and-programs/eglinton-crosstown-west-extension — ON anchor project
[12] Daily Commercial News — CFB Trenton MOB-East construction — https://canada.constructconnect.com/dcn/news/infrastructure/2025/12/construction-army-descends-on-cfb-trenton-as-construction-of-tanker-base-set-to-start — ON anchor
[13] Lakeland Today — Quebec Des Neiges Wind Farm $3B — https://www.lakelandtoday.ca/national-news/construction-work-officially-begins-on-3-billion-wind-farm-in-quebec-government-says-the-largest-project-in-canadian-history — QC top story
[14] DND — Defence industrial base investments (Le Gardeur, Valleyfield) — https://www.canada.ca/en/department-national-defence/news/2026/03/minister-mcguinty-announces-investments-in-canadas-defence-industrial-base.html — QC, federal procurement
[15] BC EAO — Ksi Lisims LNG project record — https://projects.eao.gov.bc.ca/project/60edc23bc69c5e0023a12539 — BC anchor
[16] BC EAO — Woodfibre LNG project record — https://projects.eao.gov.bc.ca/project/588511e1aaecd9001b8272e7 — BC anchor
[17] BC Major Projects Inventory — https://www2.gov.bc.ca/gov/content/employment-business/economic-development/industry/bc-major-projects-inventory — BC anchor (Berg Cu-Mo-Ag)
[18] Alberta Major Projects — Calgary Green Line LRT Phase 1 — https://majorprojects.alberta.ca/details/Calgary-Green-Line-LRT-Phase-1/873 — AB top story
[19] CER — NOVA Gas Transmission GPML Loop No. 4 — https://www.cer-rec.gc.ca/en/applications-hearings/view-applications-projects/gpml-loop-no-4-valhalla-north-section.html — AB anchor
[20] ConstructConnect — CGC Inc. $210M Wheatland County wallboard plant — https://canada.constructconnect.com/joc/news/projects/2026/06/cgc-inc-opens-210m-wallboard-plant-in-wheatland-county — AB project completion
[21] ConstructConnect — Bird selected for Bell Canada AI data centre near Regina — https://canada.constructconnect.com/joc/news/projects/2026/05/bird-selected-for-massive-bell-canada-ai-data-centre-near-regina — SK top story
[22] IAAC — Lynn Lake Gold Project — https://iaac-aeic.gc.ca/050/evaluations/proj/80140 — MB top story
[23] Deep Sky — Manitoba carbon removal facility — https://www.deepskyclimate.com/blog/deep-sky-to-build-500-000-tonne-carbon-removal-facility---one-of-the-largest-in-the-world---in-manitoba — MB anchor
[24] Portage Place — Redevelopment updates — https://portageplace.ca/development-updates/ — MB anchor
[25] CMHC — Naawi-Oodena Treaty One Nations housing funding — https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/canada-announces-funding-treaty-one-nations — MB anchor
[26] ConstructConnect — Aecon Red-Seine-Rat wastewater contract — https://canada.constructconnect.com/joc/news/infrastructure/2026/02/aecon-awarded-contract-to-build-red-seine-rat-wastewater-facility — MB anchor
[27] DND — River-class Destroyer Land-Based Test Facility, Hartlen Point — https://www.canada.ca/en/department-national-defence/news/2026/01/the-department-of-national-defence.html — NS top story
[28] Nova Scotia Environment — Beaver Dam Mine Project — https://novascotia.ca/nse/ea//nse/ea/beaver-dam-mine-project.asp — NS anchor
[29] Nova Scotia Environment — Goldboro (Signal Gold) — https://novascotia.ca/nse/ea/signal-gold-goldboro-project — NS anchor
[30] CBC News — J.D. Irving Brighton Mountain Wind Farm — https://www.cbc.ca/news/canada/new-brunswick/jd-irving-wind-farm-brighton-mountain-1.7192190 — NB top story
[31] DND — CFB Gagetown infrastructure investment — https://www.canada.ca/en/department-national-defence/news/2026/04/canada-invests-in-infrastructure-at-cfb-gagetown.html — NB anchor
[32] ISED — New Brunswick High-Speed Internet Expansion — https://www.canada.ca/en/innovation-science-economic-development/news/2026/05/government-of-canada-takes-action.html — NB anchor
[33] DND — 5 Wing Goose Bay Energy Performance Contract — https://www.canada.ca/en/department-national-defence/news/2026/04/minister-thompson-announces-largest-energy-performance-contract.html — NL top story
[34] Yahoo Finance — EverWind Burin Peninsula Green Fuels EA registration — https://finance.yahoo.com/news/everwind-registers-environmental-assessment-green-144200416.html — NL anchor
[35] Canadian Mining Journal — Duck Pond Copper-Zinc Mine — https://www.canadianminingjournal.com/news/copper-zinc-development-green-light-given-for-duck-pond — NL anchor
[36] HPAC Magazine — Enwave Charlottetown District Energy — https://www.hpacmag.com/heating-plumbing-air-conditioning-general/enwave-to-build-prince-edward-island-district-energy — PE top story
[37] PEI Government — MDS Coating Technologies (Slemon Park) — https://www.princeedwardisland.ca/en/news/provincial-and-federal-governments-support-next-phase-of-mds-coating — PE anchor
[38] Infrastructure Canada — Geomap of federal infrastructure investments — https://www.infrastructure.gc.ca/gmap-gcarte/index-eng.html — YT/NT/NU/PE/NB municipal infrastructure
[39] Housing, Infrastructure and Communities Canada — Hay River water treatment funding — https://www.canada.ca/en/housing-infrastructure-communities/news/2026/04/building-canada-strong-by-investing.html — NT top story
[40] CIRNAC — Iqaluit Nukkiksautiit Hydroelectric Project — https://www.canada.ca/en/crown-indigenous-relations-northern-affairs/news/2025/11/iqaluit-nukkiksautiit-hydroelectric.html — NU top story
[41] Parliament of Canada LEGISinfo — Senate bills 45-1 (S-1 through S-214 referenced above) — https://www.parl.ca/legisinfo/en/bill/45-1/ — Federal policy
[42] Department of Finance — Small Craft Harbours Program — https://www.canada.ca/en/department-finance/news/2026/05/government-of-canada-investing-nearly-1-billion.html — Cross-province (NL, PE, NB, NS, QC, ON, BC)
