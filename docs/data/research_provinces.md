# Provincial Research — Week of 2026-04-11
Generated: 2026-04-11
Provinces covered: All 13 provinces + 3 territories (16 total, including National rollup)
Search waves: Wave 3 (provincial scan) + policy + projects + IAAC + procurement + labour
Agent: 1B (tldr-researcher-provincial)

---

## 1. Data Quality Audit

### Provincial Indicator Coverage (from docs/data/indicators.json, 2026-04-11 snapshot)

| Region | Indicators | Projects | Pipeline Value | Latest LFS Period | Status |
|--------|------------|----------|----------------|-------------------|--------|
| ON | 20 | 498 | $211.4B | 2026-04-11 | OK |
| QC | 39 | 431 | $75.9B | 2026-04-11 / QC-series 2026-01-01 | OK (richest set) |
| AB | 6 | 664 | $291.9B | 2026-04-11 | OK |
| BC | 6 | 531 | $520.3B | 2026-04-11 | OK |
| SK | 6 | 125 | $28.3B | 2026-04-11 | OK |
| MB | 6 | 2,025 | $6.5B | 2026-04-11 | OK |
| NS | 6 | 295 | $13.0B | 2026-04-11 | OK |
| NB | 6 | 166 | $4.9B | 2026-04-11 | OK |
| NL | 6 | 1,510 | $24.7B | 2026-04-11 | OK |
| PE | 6 | 78 | $1.5B | 2026-04-11 | OK |
| YT | 4 | 97 | $46.3B | 2026-04-11 (LFS) / 2024 (GDP) | GAP — no CPI, no housing starts |
| NT | 4 | 175 | $40.2B | 2026-04-11 (LFS) / 2024 (GDP) | GAP — no CPI, no housing starts |
| NU | 4 | 37 | $1.9B | 2026-04-11 (LFS) / 2024 (GDP) | GAP — no CPI, no housing starts |
| National | 117 | 6,632 | — | 2026-04-11 | OK |

### Critical Gaps Confirmed from data_gap_report.md
- YT, NT, NU: no CPI series (StatCan publishes limited territorial CPI; not a pipeline bug).
- YT, NT, NU: no housing starts (CMHC does not report at territorial level).
- All three territories: GDP anchored to 2024 annual print (StatCan Table 36-10-0402) — rest of indicator set is month-current.
- Ten provinces have the complete six-indicator set (CPI, unemployment, employment rate, participation, GDP, housing starts). National rollup and Quebec carry the largest indicator libraries.

---

## 2. Provincial Spotlights

### Ontario
- **Top story**: Ontario Budget 2026 tabled March 26 by Finance Minister Peter Bethlenfalvy; capital plan raised to more than $210 billion over ten years, with $37 billion slated for 2026-27 alone. The plan includes approximately $64 billion over ten years for health infrastructure (of which ~$50 billion in capital grants), over 50 hospital projects, and ~3,000 new hospital beds. An additional $300 million was added to the Community Sport and Recreation Infrastructure Fund. Balanced-budget target pushed back. Sources: https://budget.ontario.ca/2026/highlights.html ; https://www.renewcanada.net/ontario-budget-2026-includes-infrastructure-spending-but-few-details/ ; https://canada.constructconnect.com/dcn/news/government/2026/04/ontario-budget-outlines-additional-300m-for-sport-rec-infrastructure
- **Key indicators** (indicators.json 2026-04-11): unemployment 7.6%, employment rate 59.6%, participation rate 64.6%, CPI -1.1% (series print), GDP +1.2%, housing starts 67,274. On-series quarterly (2025-07-01 period): Ontario exports $603.36B, imports $603.29B, real household consumption $558.51B, real government expenditure $202.31B, real capital investment $193.72B, goods GDP $177.78B (+0.8%). Source: StatCan Table 36-10-0434 via https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201
- **Project activity**: 498 projects tracked, $211.4B pipeline. Top sectors — infrastructure (195), healthcare (134), transit & rail (106). Statuses — 227 Under Construction, 131 Complete, 88 Approved, 26 Under Review, 26 Proposed. Anchor projects: Ontario Line ($27.43B, Under Construction, Metrolinx/Infrastructure Ontario); GO Expansion ($26.08B, Under Construction); Adaptive Phased Management Deep Geological Repository ($26.00B, Proposed, Nuclear Waste Management Organization). Source: IAAC Registry https://iaac-aeic.gc.ca/050/evaluations
- **Policy developments**: The March 26 budget is the dominant policy event of the week, covered in https://mcmillan.ca/uncategorized/built-to-move-ontario-accelerates-infrastructure-delivery-in-the-2026-budget/ and https://www.dentons.com/en/insights/newsletters/2026/april/8/infrastructure-and-major-projects-perspectives/2026-ontario-budget . No Ontario items appeared in policy.json for week 2026-04-11.
- **Labour trends**: Ontario unemployment at 7.6% is the highest in Central Canada; employment rate 59.6% trails the 60.6% national print.
- **IAAC status**: Deep Geological Repository remains Proposed in the federal Impact Assessment Registry. Ontario hosts the highest concentration of healthcare and transit projects in assessment phases.
- **Procurement**: No single award ≥$5M attributed specifically to Ontario in this week's policy.json feed; Ontario BPS procurement channel covered under the pipeline's provincial procurement monitor.

### Quebec
- **Top story**: Québec Infrastructure Plan 2026-2036 (QIP), tabled March 18 2026, totals $167 billion over ten years. New funding of $12.6 billion is allocated to health and social services, education, higher education, and public transit. Bill 5 creates a fast-track regulatory pathway for "priority national-scale projects" assessed on criteria including prosperity, autonomy, Indigenous consultation, energy-transition targets, and short-term implementability. Sources: https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/secretariat-du-conseil-du-tresor/publications-adm/budgets/2025-2026/en/6-Quebec_Infrastructure_Plan.pdf ; https://www.renewcanada.net/quebec-infrastructure-plan-2026-2036/ ; https://www.blakes.com/insights/quebec-s-bill-5-fast-tracking-priority-national-scale-projects/
- **Key indicators**: unemployment 5.4% (national print) / qc_unemployment_rate 5.2% (ISQ 2026-01-01); CPI +0.6%; employment rate 60.9%; participation 64.4%; GDP +1.3%; housing starts 53,461. Quarterly (2025-07-01): real GDP $487.22B (+0.2%), nominal GDP $646.25B, household consumption $287.44B (-0.3%), business investment $22.71B (+0.1%), exports $205.73B (0.0%), imports $238.50B (-1.5%). Monthly (2025-11-01 to 2025-12-01): monthly GDP $448.03B, manufacturing sales $221.80B, retail sales $189.73B, wholesale sales $208.29B, weekly earnings $1,272.70, international exports $86.18B, international imports $108.67B, residential building permits $20.52B, non-res permits $7.43B. Source: Institut de la statistique du Québec and StatCan https://statistique.quebec.ca/
- **Project activity**: 431 projects, $75.9B pipeline. Top sectors — education (118), infrastructure (100), healthcare (48). Statuses — 279 Approved, 88 Under Review, 36 Under Construction, 27 Proposed. Anchors: Parc éolien Chamouchouane ($9.00B, Proposed, Hydro-Québec/MRC Domaine du Roy); Montreal Metro Blue Line Extension ($4.89B, Under Construction, STM); TES Canada green hydrogen facility ($4.00B, Under Review). Source: IAAC Registry https://iaac-aeic.gc.ca/050/evaluations
- **Policy developments**: QIP 2026-2036 dominant. Bill 5 fast-track mechanism is the legislative event of the quarter. No Quebec-specific items in policy.json for this week.
- **Labour trends**: Employment 4,669.7K (ft 3,752.8K, pt 916.8K), labour force 4,923.8K, participation 64.8%.
- **IAAC status**: TES Canada hydrogen plant and Chamouchouane wind park both active in federal registry.
- **Procurement**: No individual Quebec contract ≥$5M captured in this week's feed.

### Alberta
- **Top story**: Federal-Alberta-Pathways Alliance tri-lateral MOU target date was April 1 2026 for a multi-phased framework on the proposed $16.5B carbon capture and storage trunkline in northern Alberta. The Pathways Alliance rebranded to the "Oil Sands Alliance" in February 2026. First Nations and rural landowners filed a request for additional review of the CCS corridor. Sources: https://worldoil.com/news/2026/2/14/canada-backs-carbon-capture-buildout-to-secure-oil-sands-future-energy-minister-says/ ; https://pathwaysalliance.ca/pathways-project/ ; https://www.cbc.ca/news/canada/edmonton/pathways-carbon-capture-oilsands-alberta-opposition-9.7141067 ; https://iaac-aeic.gc.ca/050/evaluations/proj/89090
- **Key indicators**: unemployment 6.5%, employment rate 64.4%, participation 68.9%, CPI +3.4%, GDP +2.7%, housing starts 48,438. Alberta carries the highest provincial CPI print other than PE and the highest participation rate outside the territories.
- **Project activity**: 664 projects, $291.9B pipeline — the second-largest provincial pipeline after BC. Top sectors — government (143), power & energy (125), infrastructure (111). Statuses — 349 Proposed, 167 Under Construction, 82 Complete, 50 Under Review. Anchors: Telus Infrastructure Upgrades province-wide 2023-2027 ($19.00B, Under Construction); Pathways Alliance CCS Hub Phase 1 ($16.50B, Proposed); AOSP Jackpine ($12.00B, Approved, Canadian Natural Resources Limited). Source: IAAC Registry.
- **Policy developments**: Federal-Alberta MOU framework (carbon price alignment + CCS financing) remained the central file through the week; no Alberta items in policy.json.
- **Labour trends**: Alberta participation at 68.9% remains the highest among provinces, consistent with resource-sector labour demand.
- **IAAC status**: Pathways Alliance CO2 Transportation Network and Storage Hub Project — Impact Assessment registry entry 89090, currently in planning phase. Source: https://iaac-aeic.gc.ca/050/evaluations/proj/89090
- **Procurement**: No single provincial award ≥$5M in this week's policy.json.

### British Columbia
- **Top story**: BC filed three policy items this week — a March housing highlights statement, a reaction to the U.S. Department of Commerce preliminary softwood lumber duty determination, and an April rental report statement — all under Ministers Boyle (Housing) and Parmar (Forests). Wood manufacturers characterized the U.S. softwood process as broken; the U.S. preliminary duty rate came in at just under 25%, below the current ~35% combined rate. Sources: https://news.gov.bc.ca/releases/2026HMA0042-000398 ; https://news.gov.bc.ca/releases/2026FOR0011-000394 ; https://news.gov.bc.ca/releases/2026HMA0039-000390 ; https://www.cbc.ca/news/canada/british-columbia/us-softwood-lumber-tariffs-9.7160025
- **Key indicators**: unemployment 6.7% (in line with national 6.7%), employment rate 60.1%, participation 64.4%, CPI +1.0%, GDP +1.2%, housing starts 41,331. Source: https://news.gov.bc.ca/releases/2026JEG0025-000395
- **Project activity**: 531 projects, $520.3B pipeline — the largest in the country. Top sectors — power & energy (70), mining (57), residential (51). Statuses — 149 Proposed, 146 Under Construction, 124 Under Review, 42 Approved, 29 On Hold. Anchors: LNG Canada Phase 1 ($47.90B, Under Construction, Shell/Petronas/PetroChina/Mitsubishi/Korea Gas); LNG Canada Facility ($40.00B, Complete); LNG Canada Phase 2 ($25.00B, Proposed — no FID). Additional: Woodfibre LNG at Squamish (marine pile works underway). Source: https://www.bc-er.ca/what-we-regulate/major-projects/woodfibre-lng/
- **Policy developments**: Three items in policy.json this week (housing x2, softwood lumber x1), all from news.gov.bc.ca. Affected projects totals: 106 residential-linked, 21 forestry/manufacturing-linked.
- **Labour trends**: BC unemployment in line with national; housing ministry press statements covered rental market and unit delivery for March.
- **IAAC status**: Multiple LNG, mining and hydrogen projects in federal assessment; Woodfibre LNG regulated by BC Energy Regulator.
- **Procurement**: None ≥$5M attributed in this week's policy.json.

### Saskatchewan
- **Top story**: BHP's Jansen potash mine, now 75% complete, has shifted Stage 1 first production to 2027 (one-year slip) and Stage 2 to 2031 (two-year slip); Stage 1 capex is up ~30% from original plan. Total BHP capital in Jansen now ~C$14B. Nutrien remains the largest Saskatchewan producer at 20 Mt/yr across six mines. Sources: https://www.theglobeandmail.com/business/economy/article-bhps-new-potash-mine-is-a-test-case-for-canada-in-how-to-build-big/ ; https://www.mining.com/bhp-delays-jansen-potash-mine-blows-budget-by-30/ ; https://www.bhp.com/what-we-do/global-locations/canada/jansen
- **Key indicators**: unemployment 5.0% (tied lowest among provinces), employment rate 63.9%, participation 67.2%, CPI -0.7%, GDP +3.4%, housing starts 5,486.
- **Project activity**: 125 projects, $28.3B pipeline. Top sectors — other (68), infrastructure (16), power & energy (12). Statuses — 79 Under Review, 30 Under Construction, 10 Proposed, 6 Approved. Anchors: Jansen Stage 1 ($7.50B, Under Construction, BHP); Jansen Stage 2 ($6.40B, Under Construction, BHP); FCL HDRD Plant ($2.00B, Proposed, Federated Co-operatives Limited).
- **Policy developments**: No items in policy.json for SK this week.
- **Labour trends**: Saskatchewan unemployment at 5.0% is tied with Quebec's ISQ print as the lowest in Canada.
- **IAAC status**: Jansen Stages 1 and 2 advance under provincial and federal oversight; no new registry movement this week.
- **Procurement**: None ≥$5M attributed to SK in this week's policy.json.

### Manitoba
- **Top story**: Manitoba Budget 2026, tabled March 24 by the Kinew government, projects a $1.7B deficit in 2025-26 falling to $498M in 2026-27 and an $8M surplus in 2027-28. Strategic infrastructure spending set at $3.7B for the fiscal year (~$4.3B/yr average over five years). Manitoba Hydro receives $1.17B in capital investment; Hydro itself is forecasting a $502M net loss (a $722M swing from prior $220M net income projection) because of water conditions. Sources: https://www.gov.mb.ca/asset_library/en/budget2026/budget2026.pdf ; https://news.gov.mb.ca/news/index.html?item=73198 ; https://www.cbc.ca/news/canada/manitoba/budget-2026-analysis-9.7144691
- **Key indicators**: unemployment 5.6%, employment rate 63.4%, participation 67.1%, CPI +3.1%, GDP +1.1%, housing starts 7,642.
- **Project activity**: 2,025 projects, $6.5B pipeline. Top sectors — other (1,068), water & wastewater (455), energy (152). Statuses — 1,978 Under Review (Manitoba's provincial EA registry contributes the bulk), 36 Under Construction, 9 Approved. Anchors: North End Sewage Treatment Plant (NEWPCC) Upgrades Biosolids ($500M, Approved, City of Winnipeg); Lake Manitoba/Lake St. Martin Outlet Channels Project ($490M, Approved, Province of Manitoba); Pointe du Bois Renewable Energy Project ($390M, Under Construction, Manitoba Hydro).
- **Policy developments**: Budget 2026 is the event of the month. No items in policy.json for MB this week.
- **Labour trends**: Manitoba employment rate 63.4% runs above the national 60.6%.
- **IAAC status**: No major Manitoba projects in registry changes this week.
- **Procurement**: No items ≥$5M in this week's feed.

### Nova Scotia
- **Top story**: Nova Scotia's offshore wind framework approached legislative passage this spring; the regulator issued a Call for Information and Prequalification (open to mid-January 2026) to seed a competitive bidding round. Hydro-Québec filed a Request for Information on potential offshore wind development off Nova Scotia. Sources: https://www.cbc.ca/news/canada/nova-scotia/offshore-wind-projects-9.7135261 ; https://news.hydroquebec.com/news/press-releases/all-quebec/hydro-quebec-launches-request-information-inform-potential-development-offshore-wind-farms-off-nova-scotia.html ; https://www.offshorewind.biz/2026/02/26/nova-scotia-setting-up-framework-for-offshore-wind-revenue/
- **Key indicators**: unemployment 6.6%, employment rate 57.4%, participation 61.4%, CPI +1.5%, GDP +2.7%, housing starts 7,146.
- **Project activity**: 295 projects, $13.0B pipeline. Top sectors — other (105), clean energy (71), infrastructure (23). Statuses — 233 Complete, 32 Under Construction, 14 Approved, 13 Under Review, 3 Proposed. Anchors: Bear Head Energy ($8.00B, Proposed, Bear Head Energy); Boat Harbour Remediation Project ($370M, Approved, Province of Nova Scotia); NSP Battery Storage ($350M, Approved, Nova Scotia Power & WMA).
- **Policy developments**: No items in policy.json for NS this week.
- **Labour trends**: Employment rate 57.4% is the lowest among the 10 provinces; participation 61.4% sits just above NB and NL.
- **IAAC status**: Offshore wind prequalification is jurisdictional (NS/Canada), not IAAC-individual-project stage.
- **Procurement**: None ≥$5M in this week's policy.json.

### New Brunswick
- **Top story**: Northcliff Resources received US$20.7M from the U.S. Department of Defense and a conditional C$8.2M from Ottawa to advance the Sisson tungsten project north of Fredericton. The federal Natural Resources Minister stated intent to accelerate the Sisson timeline. J.D. Irving's $1.1B NextGen pulp mill upgrade remains the largest capital project in NB (new recovery boiler, ~doubling pulp drying capacity, expected to proceed once EIA process is complete). Sources: https://www.canadianminingjournal.com/news/northcliff-advancing-its-sisson-critical-minerals-project-in-new-brunswick/ ; https://www.cbc.ca/news/canada/new-brunswick/sisson-mine-project-revival-1.7554589 ; https://canada.constructconnect.com/dcn/news/projects/2026/03/new-brunswick-government-hoping-to-restart-critical-mineral-mine-south-of-fredericton ; https://canada.constructconnect.com/dcn/news/projects/2024/08/1-1-billion-nextgen-mill-project-making-history-in-saint-john-n-b
- **Key indicators**: unemployment 7.0%, employment rate 56.7%, participation 60.9%, CPI +1.2%, GDP +1.8%, housing starts 6,011.
- **Project activity**: 166 projects, $4.9B pipeline. Top sectors — other (90), infrastructure (29), tourism/culture (12). Statuses — 112 Under Review, 46 Under Construction, 8 Approved. Anchors: Saint John Pulp Mill Upgrades ($1.10B, Under Review, J.D. Irving); Sisson Project ($580M, Approved, Northcliff Resources/HDI Mining/Todd Corp); Trans-Canada Highway Route 2 Twinning ($420M, Under Construction, Province of NB).
- **Policy developments**: No items in policy.json for NB this week; critical minerals positioning continues federally.
- **Labour trends**: Employment rate 56.7% is the lowest provincial print in Canada; unemployment 7.0% among the higher prints.
- **IAAC status**: Sisson project federal review process is active.
- **Procurement**: US DoD award to Northcliff and conditional Canada contribution exceed the $5M threshold.

### Newfoundland and Labrador
- **Top story**: Cenovus targets spring 2026 startup for West White Rose, budgeting $450M-$500M for 2026 offshore expenditures. The project is expected to add 20,000-25,000 bbl/d of production on first oil, ramping toward 80,000 bbl/d gross at full build, with 250 permanent positions. The Province of Newfoundland and Labrador earmarked $90M over three years for offshore exploration incentives. StatCan reports NL oil production up 69.2% in February 2026 vs prior. Sources: https://www.offshore-mag.com/production/news/55338469/cenovus-energy-cenovus-targets-spring-startup-for-west-white-rose-oil-project-offshore-newfoundland ; https://www.cbc.ca/news/canada/newfoundland-labrador/cenovus-white-rose-production-1.7463702 ; https://www.gov.nl.ca/fin/economics/eb-oil/ ; https://www.gov.nl.ca/releases/2026/exec/0303n05/
- **Key indicators**: unemployment 9.5% (highest provincial print), employment rate 52.7% (lowest provincial print), participation 58.3%, CPI +1.8%, GDP +2.4%, housing starts 1,223.
- **Project activity**: 1,510 projects, $24.7B pipeline. Top sectors — other (881), infrastructure (163), transit & rail (151). Statuses — 1,339 Proposed, 126 Cancelled, 31 Under Construction, 8 Approved. Anchors: Grassy Point LNG ($10.00B, Proposed, LNG Newfoundland and Labrador); Kamistiatusset/Kami Iron Ore ($3.86B, Under Review, Champion Iron Limited); White Rose Expansion / West White Rose ($3.80B, Under Construction, Husky/Suncor/Nalcor). Bay du Nord advancement agreement referenced in https://www.gov.nl.ca/releases/2026/exec/0303n05/
- **Policy developments**: Offshore exploration incentive ($90M/3yr) and Bay du Nord advancement agreement are the current provincial files. No items in policy.json for NL this week.
- **Labour trends**: NL holds the highest unemployment rate in Canada; employment rate the lowest.
- **IAAC status**: Kami Iron Ore in federal review; Bay du Nord under advancement discussions.
- **Procurement**: Cenovus 2026 capex budget $450M-$500M disclosed publicly (operator spend, not a government contract award).

### Prince Edward Island
- **Top story**: PEI's 2026-2027 Operating Budget remains in pre-budget consultation. The province reported population +1.6% to 182,657 (through July 2025), employment +1.2% (through October 2025), international exports +12.8% (through August 2025). The Smart Renewables and Electrification Pathways Program has approved >$21.7M across three PEI projects; PEI launched a $10M cleantech R&D fund and three tax-free development zones. The Eastern Kings Wind Farm Expansion (+29.4 MW, seven turbines) remains in commissioning. PEI wind share of provincial generation was 98.2% in 2023 (highest in Canada). Sources: https://www.princeedwardisland.ca/en/service/pre-budget-consultations-2026 ; https://www.investcanada.ca/news/small-province-big-opportunity-renewable ; https://www.cer-rec.gc.ca/en/data-analysis/energy-markets/renewable-energy-canada/provinces/renewable-power-canada-prince-edward-island.html ; https://www.princeedwardisland.ca/en/feature/renewable-energy-indicators
- **Key indicators**: unemployment 7.3%, employment rate 61.6%, participation 66.5%, CPI +5.4% (highest provincial CPI print in Canada), GDP +3.6%, housing starts 963.
- **Project activity**: 78 projects, $1.5B pipeline. Top sectors — infrastructure (39), tourism/culture (16), power & energy (13). Statuses — 70 Under Construction, 4 Approved, 3 Under Review, 1 Proposed. Anchors: Northumberland Strait Submarine Transmission System ($90M, Under Construction, Province of PE); Skinners Pond Wind Energy Centre ($90M, Proposed, Invenergy); PEIEC Wind Farm #5 ($80M, Under Construction, PEI Energy Corporation).
- **Policy developments**: Pre-budget consultations open through spring; SREPs funding approvals. No items in policy.json for PE this week.
- **Labour trends**: Employment and participation in line with regional averages.
- **IAAC status**: No major PEI IAAC file changes this week.
- **Procurement**: SREPs allocations (>$21.7M total across three projects) exceed the $5M threshold; individual award figures not broken out in source.

### Yukon
- **Top story**: The credit agreement between the Government of Yukon and PricewaterhouseCoopers (court-appointed receiver of Victoria Gold) for the Eagle Gold Mine receivership was extended to April 1, 2026. Separately, YESAB panel-review member selection for the Casino Mine (Western Copper and Gold, $3.62B copper/gold/moly/silver open pit, 300 km NW of Whitehorse) was expected to be completed by April 2026 at the earliest. Western Copper and Gold raised $29M to advance permitting. Sources: https://yukon.ca/en/news/eagle-gold-mine-receivership-credit-agreement-extended-april-1-2026 ; https://www.aptnnews.ca/national-news/proposed-casino-mine-inches-forward-to-yukons-first-panel-review/ ; https://www.westerncopperandgold.com/casino-project/ ; https://www.mining.com/western-copper-and-gold-raising-29-million-for-casino-project-in-yukon/
- **Key indicators** (partial — territorial gaps per data_gap_report.md): unemployment 3.9% (lowest in Canada), employment rate 72.1%, participation 75.1%, GDP -3.3% (2024 annual, StatCan Table 36-10-0402). CPI and housing starts NOT AVAILABLE at territorial level.
- **Project activity**: 97 projects, $46.3B pipeline. Top sectors — infrastructure (55), tourism/culture (14), government (9). Statuses — 80 Under Construction, 11 Approved, 3 Proposed, 2 Under Review, 1 On Hold. Anchors: Northern Defence and Infrastructure Investment ($40.00B, Proposed — federal envelope attributed to YT); Casino Mine ($3.62B, Proposed, Western Copper and Gold); Kudz Ze Kayah ($490M, Under Review, BMC Minerals).
- **Policy developments**: Receivership credit extension is a territorial financial action, not a policy.json item. No YT items in policy.json this week.
- **Labour trends**: YT 3.9% unemployment and 75.1% participation are the strongest prints in the country.
- **IAAC status**: Casino Mine is currently in YESAB Panel Review (highest-level territorial assessment), coordinating with federal registry.
- **Procurement**: Victoria Gold receivership financing (amount not publicly disclosed in source) continues via PwC.

### Northwest Territories
- **Top story**: In March 2026 Prime Minister Mark Carney referred the Taltson Hydro Expansion — 60 MW addition doubling NWT hydro capacity with a 270 km transmission line from the Taltson dam (56 km NE of the AB-NWT border) to the Yellowknife system — to the federal Major Projects Office. Current timeline: EA in 2026, commercial structure TBD, FID, construction start 2029, first power 2033. Three NWT priority projects advanced to the Major Projects Office. NWT government released an updated assessment citing vast gold, diamond, lithium, cobalt, copper and zinc reserves at the 2026 national mining convention. Federal support announced for Ekati Diamond Mine continuity. Sources: https://www.theglobeandmail.com/business/article-a-list-of-carneys-major-projects-centred-on-the-north/ ; https://canada.constructconnect.com/dcn/news/projects/2026/03/n-w-t-s-top-three-projects-advance-to-major-projects-office ; https://www.gov.nt.ca/newsroom/taltson-hydro-expansion ; https://www.gov.nt.ca/en/newsroom/minister-cleveland-welcomes-federal-support-ekati-diamond-mine-outlines-next-steps-northern
- **Key indicators** (partial — territorial gaps): unemployment 6.1%, employment rate 65.0%, participation 69.2%, GDP -1.1% (2024 annual). CPI and housing starts NOT AVAILABLE at territorial level.
- **Project activity**: 175 projects, $40.2B pipeline. Top sectors — infrastructure (55), other (49), mining (26). Statuses — 92 Under Review, 56 Under Construction, 20 Approved, 5 Proposed, 2 Complete. Anchors: Arctic Defence and Infrastructure Spending Package NWT ($35.00B, Proposed — federal envelope); Taltson Hydroelectricity Expansion Phase 1 ($1.20B, Under Construction, NTPC); Pine Point ($650M, Under Review, Osisko Metals/Appian).
- **Policy developments**: Federal Major Projects Office referral is the week's dominant file; no NT items in policy.json.
- **Labour trends**: Participation 69.2% is above the national average; unemployment 6.1%.
- **IAAC status**: Taltson Expansion moving to Major Projects Office expedited review; Pine Point in federal review.
- **Procurement**: Ekati continuity support (federal) — amount not disclosed in source.

### Nunavut
- **Top story**: Baffinland Iron Mines reported completion of Inuit consultations and issuance of key regulatory authorizations for the Steensby Inlet railway/port expansion of Mary River (subject to financing and construction agreements, construction to begin in 2026). Nunavut hunters filed a request for reassessment ahead of construction. B2Gold poured first gold at the Goose Mine, Back River Gold Project (Kitikmeot region). Sources: https://www.cbc.ca/news/canada/north/baffinland-says-cleared-for-steensby-project-nunavut-9.7066314 ; https://www.cbc.ca/news/canada/north/baffinland-2026-steensby-hunters-reassessment-1.7498351 ; https://www.baffinland.com/operation/mary-river-mine/
- **Key indicators** (partial — territorial gaps): unemployment 12.1% (highest in Canada, territorial), employment rate 54.2%, participation 61.7%, GDP +7.5% (2024 annual). CPI and housing starts NOT AVAILABLE at territorial level.
- **Project activity**: 37 projects, $1.9B pipeline. Top sectors — infrastructure (13), tourism/culture (6), environment (5). Statuses — 30 Under Construction, 7 Approved. Anchors: Back River Gold Project ($610M, Under Construction, B2Gold Corp); Iqaluit Water Infrastructure Improvement Project ($210M, Under Construction, City of Iqaluit); Powerplant Upgrades and Replacements in Cambridge Bay, Gjoa Haven and Taloyoak ($130M, Under Construction, Qulliq Energy Corporation).
- **Policy developments**: Inuit consultation completion and regulatory authorization on Steensby expansion are the central project-level files. No NU items in policy.json this week.
- **Labour trends**: Nunavut unemployment 12.1% remains the highest in the country.
- **IAAC status**: Steensby Phase of Mary River cleared for construction pending finance; Back River Gold in production.
- **Procurement**: Iqaluit water infrastructure ($210M) and Qulliq powerplant upgrades ($130M) are active public-sector works exceeding $5M.

### National (rollup)
- **Top story**: StatCan's March 2026 Labour Force Survey held the national unemployment rate at 6.7% (unchanged from February). Employment rose +14,000 (+0.1% m/m); employment rate steady at 60.6%; year-over-year employment up +0.4% (~87,100 persons). Youth (15-24) unemployment held at 13.8%. Sources: https://www.hiringlab.org/en-ca/2026/04/10/march-2026-labour-force-survey-holding-steady/ ; https://economics.td.com/ca-employment ; https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703 ; https://news.gov.bc.ca/releases/2026JEG0025-000395
- **Project activity**: 6,632 projects tracked across all regions; all current (lastSeen ≤30 days). Indicator library carries 117 national series.
- **Labour trends**: National unemployment 6.7%; provincial dispersion spans NL 9.5% high to SK 5.0% low; territorial NU 12.1%.

---

## 3. Policy Developments Summary

### Budgets and Fiscal Announcements
- **Ontario** — 2026 Budget tabled March 26, $210B/10yr capital plan, $37B for 2026-27, $64B over 10yr for health infrastructure. https://budget.ontario.ca/2026/highlights.html
- **Quebec** — QIP 2026-2036 tabled March 18, $167B over 10yr; Bill 5 fast-track for priority national-scale projects. https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/secretariat-du-conseil-du-tresor/publications-adm/budgets/2025-2026/en/6-Quebec_Infrastructure_Plan.pdf
- **Manitoba** — Budget 2026 tabled March 24; $3.7B strategic infrastructure; $1.17B Manitoba Hydro capital; deficit $1.7B falling to $498M. https://www.gov.mb.ca/asset_library/en/budget2026/budget2026.pdf
- **Prince Edward Island** — 2026-27 pre-budget consultations underway. https://www.princeedwardisland.ca/en/service/pre-budget-consultations-2026

### Legislation and Regulation
- **Quebec Bill 5** — fast-track for priority national-scale infrastructure projects. https://www.blakes.com/insights/quebec-s-bill-5-fast-tracking-priority-national-scale-projects/
- **Nova Scotia offshore wind framework** — legislative passage approaching; Call for Information and Prequalification open Oct 2025 through mid-January 2026. https://www.cbc.ca/news/canada/nova-scotia/offshore-wind-projects-9.7135261

### Major Policy Shifts
- **Federal-Alberta-Pathways Alliance MOU** — tri-lateral framework target date April 1 2026 for the $16.5B CCS project. https://worldoil.com/news/2026/2/14/canada-backs-carbon-capture-buildout-to-secure-oil-sands-future-energy-minister-says/
- **Federal Major Projects Office** — three NWT projects advanced (Taltson, two others). https://canada.constructconnect.com/dcn/news/projects/2026/03/n-w-t-s-top-three-projects-advance-to-major-projects-office
- **U.S. softwood lumber** — preliminary duty rate ~25% (down from current ~35% combined). https://www.cbc.ca/news/canada/british-columbia/us-softwood-lumber-tariffs-9.7160025 ; https://news.gov.bc.ca/releases/2026FOR0011-000394

---

## 4. Capital Projects by Province

### Value Pipeline by Province
| Region | Count | Total Value | Top Sector | Status Breakdown |
|--------|-------|-------------|------------|------------------|
| BC | 531 | $520.3B | power & energy (70) | 149 Proposed, 146 UC, 124 UR, 42 Approved |
| AB | 664 | $291.9B | government (143) | 349 Proposed, 167 UC, 82 Complete |
| ON | 498 | $211.4B | infrastructure (195) | 227 UC, 131 Complete, 88 Approved |
| QC | 431 | $75.9B | education (118) | 279 Approved, 88 UR, 36 UC |
| YT | 97 | $46.3B | infrastructure (55) | 80 UC, 11 Approved |
| NT | 175 | $40.2B | infrastructure (55) | 92 UR, 56 UC, 20 Approved |
| SK | 125 | $28.3B | other (68) | 79 UR, 30 UC, 10 Proposed |
| NL | 1,510 | $24.7B | other (881) | 1,339 Proposed, 126 Cancelled, 31 UC |
| NS | 295 | $13.0B | other (105) | 233 Complete, 32 UC, 14 Approved |
| MB | 2,025 | $6.5B | other (1,068) | 1,978 UR, 36 UC, 9 Approved |
| NB | 166 | $4.9B | other (90) | 112 UR, 46 UC, 8 Approved |
| NU | 37 | $1.9B | infrastructure (13) | 30 UC, 7 Approved |
| PE | 78 | $1.5B | infrastructure (39) | 70 UC, 4 Approved |

(UC = Under Construction, UR = Under Review. Values rounded; pulled from projects_all.json 2026-04-11.)

---

## 5. IAAC Monitoring
- **ON** — Adaptive Phased Management Deep Geological Repository: Proposed, under federal review. https://iaac-aeic.gc.ca/050/evaluations
- **QC** — TES Canada green hydrogen plant: Under Review. Parc éolien Chamouchouane: Proposed.
- **AB** — Pathways Alliance CO2 Transportation Network and Storage Hub Project (Registry ID 89090): Planning phase. https://iaac-aeic.gc.ca/050/evaluations/proj/89090
- **BC** — Multiple LNG and hydrogen projects active; Woodfibre LNG under BCER.
- **NB** — Sisson Project: Approved status in database; federal minister stated intent to accelerate timeline.
- **NL** — Kamistiatusset (Kami) Iron Ore: Under Review.
- **YT** — Casino Mine: YESAB Panel Review (highest level). Kudz Ze Kayah: Under Review.
- **NT** — Taltson Expansion: advanced to federal Major Projects Office. Pine Point: Under Review.
- **NU** — Mary River/Steensby expansion: regulatory authorizations issued.

---

## 6. Procurement Awards (>=$5M)
- **Federal contracts** (this week's policy.json): none new captured. Pipeline's procurement monitor runs independently (Open Canada, BuyAndSell, Ontario BPS, BC Bid).
- **New Brunswick** — US DoD $20.7M to Northcliff Resources (Sisson tungsten, critical minerals); conditional C$8.2M from Canada. https://www.canadianminingjournal.com/news/northcliff-advancing-its-sisson-critical-minerals-project-in-new-brunswick/
- **Prince Edward Island** — SREPs program: >$21.7M across three projects. https://www.investcanada.ca/news/small-province-big-opportunity-renewable

---

## 7. Labour Market Stories

### Unemployment and Employment (indicators.json, period 2026-04-11 unless noted)
| Region | Unemployment | Employment Rate | Participation | Source |
|--------|--------------|-----------------|---------------|--------|
| ON | 7.6% | 59.6% | 64.6% | StatCan LFS 14-10-0287 |
| QC | 5.4% (national) / 5.2% (ISQ, 2026-01-01) | 60.9% / 61.5% (ISQ) | 64.4% / 64.8% (ISQ) | StatCan + ISQ |
| AB | 6.5% | 64.4% | 68.9% | StatCan LFS |
| BC | 6.7% | 60.1% | 64.4% | StatCan LFS |
| SK | 5.0% | 63.9% | 67.2% | StatCan LFS |
| MB | 5.6% | 63.4% | 67.1% | StatCan LFS |
| NS | 6.6% | 57.4% | 61.4% | StatCan LFS |
| NB | 7.0% | 56.7% | 60.9% | StatCan LFS |
| NL | 9.5% | 52.7% | 58.3% | StatCan LFS |
| PE | 7.3% | 61.6% | 66.5% | StatCan LFS |
| YT | 3.9% | 72.1% | 75.1% | StatCan LFS territorial |
| NT | 6.1% | 65.0% | 69.2% | StatCan LFS territorial |
| NU | 12.1% | 54.2% | 61.7% | StatCan LFS territorial |
| National | 6.7% | 60.6% | — | https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703 |

### Hiring Spikes
Indeed Hiring Lab characterized the March LFS as "holding steady"; no single-province hiring spike flagged for the week. https://www.hiringlab.org/en-ca/2026/04/10/march-2026-labour-force-survey-holding-steady/

### Wage Trends
QC weekly earnings (SEPH) $1,272.70 at December 2025. Other provinces' SEPH values not loaded in indicators.json this run.

---

## 8. Coverage Gaps and Priorities
- **Territorial CPI and housing starts** — structural gap (StatCan/CMHC do not publish at YT/NT/NU level). Labour force and annual GDP are the territorial anchors.
- **Policy.json depth** — only BC filed items for week 2026-04-11 (3 entries). Ontario and Quebec budget/QIP events are missing from policy.json even though they are the week's largest policy files nationally. Flag for the policy_tracker feed coverage (LEGISinfo/Canada Gazette/provincial Finance ministry RSS) to confirm they are captured in subsequent runs.
- **MB project inflation** — Manitoba projects_all count (2,025) is dominated by 1,978 Under Review items carried from the Manitoba Environmental Licensing registry. Average value per project is low ($3.2M). Most are small water/wastewater filings rather than capital-project announcements.
- **NL proposed-project overhang** — 1,339 Proposed / 126 Cancelled. Most "Proposed" entries are historical IAAC entries, not new this week.

---

## 9. Master Source Registry

[1] https://budget.ontario.ca/2026/highlights.html — 2026 Ontario Budget — Government of Ontario — accessed 2026-04-11
[2] https://www.renewcanada.net/ontario-budget-2026-includes-infrastructure-spending-but-few-details/ — Ontario budget 2026 includes infrastructure spending — ReNew Canada — 2026
[3] https://canada.constructconnect.com/dcn/news/government/2026/04/ontario-budget-outlines-additional-300m-for-sport-rec-infrastructure — Ontario budget outlines additional $300M for sport, rec infrastructure — Daily Commercial News — April 2026
[4] https://www.dentons.com/en/insights/newsletters/2026/april/8/infrastructure-and-major-projects-perspectives/2026-ontario-budget — 2026 Ontario Budget — Dentons — April 8 2026
[5] https://mcmillan.ca/uncategorized/built-to-move-ontario-accelerates-infrastructure-delivery-in-the-2026-budget/ — Built to Move — McMillan LLP — April 2026
[6] https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/secretariat-du-conseil-du-tresor/publications-adm/budgets/2025-2026/en/6-Quebec_Infrastructure_Plan.pdf — Québec Infrastructure Plan 2025-2035 — Secrétariat du Conseil du trésor — 2026
[7] https://www.renewcanada.net/quebec-infrastructure-plan-2026-2036/ — Québec Infrastructure Plan 2026-2036 — ReNew Canada — 2026
[8] https://www.blakes.com/insights/quebec-s-bill-5-fast-tracking-priority-national-scale-projects/ — Quebec's Bill 5 — Blakes — 2026
[9] https://worldoil.com/news/2026/2/14/canada-backs-carbon-capture-buildout-to-secure-oil-sands-future-energy-minister-says/ — Canada backs carbon capture buildout — World Oil — Feb 14 2026
[10] https://pathwaysalliance.ca/pathways-project/ — Foundational Project — Pathways Alliance — 2026
[11] https://www.cbc.ca/news/canada/edmonton/pathways-carbon-capture-oilsands-alberta-opposition-9.7141067 — Coalition demands review of Pathways — CBC News — 2026
[12] https://iaac-aeic.gc.ca/050/evaluations/proj/89090 — Pathways Alliance CO2 Transportation Network and Storage Hub Project — IAAC Registry
[13] https://news.gov.bc.ca/releases/2026HMA0042-000398 — Minister's statement on March 2026 housing highlights — BC Government News — April 10 2026
[14] https://news.gov.bc.ca/releases/2026FOR0011-000394 — Minister's statement on softwood lumber administrative review — BC Government News — April 9 2026
[15] https://news.gov.bc.ca/releases/2026HMA0039-000390 — Minister's statement on April 2026 rental report — BC Government News — April 9 2026
[16] https://news.gov.bc.ca/releases/2026JEG0025-000395 — Minister's statement on March 2026 Labour Force Survey results — BC Government News — April 2026
[17] https://www.cbc.ca/news/canada/british-columbia/us-softwood-lumber-tariffs-9.7160025 — U.S. appears to lower Canadian softwood lumber tariffs — CBC News — 2026
[18] https://www.bnnbloomberg.ca/business/2026/04/10/bcs-wood-manufacturers-call-lumber-dispute-with-us-a-broken-process/ — BC wood manufacturers call lumber dispute broken — BNN Bloomberg — April 10 2026
[19] https://www.bc-er.ca/what-we-regulate/major-projects/woodfibre-lng/ — Woodfibre LNG — BC Energy Regulator
[20] https://www.theglobeandmail.com/business/economy/article-bhps-new-potash-mine-is-a-test-case-for-canada-in-how-to-build-big/ — BHP's new potash mine — Globe and Mail — 2026
[21] https://www.mining.com/bhp-delays-jansen-potash-mine-blows-budget-by-30/ — BHP delays Jansen potash mine — MINING.COM — 2026
[22] https://www.bhp.com/what-we-do/global-locations/canada/jansen — Jansen — BHP — 2026
[23] https://www.gov.mb.ca/asset_library/en/budget2026/budget2026.pdf — Manitoba Budget 2026 — Government of Manitoba — March 24 2026
[24] https://news.gov.mb.ca/news/index.html?item=73198 — Good Jobs, Lower Costs, Better Health Care — Manitoba Budget 2026 — March 24 2026
[25] https://www.cbc.ca/news/canada/manitoba/budget-2026-analysis-9.7144691 — 5 potential perils in Wab Kinew's third Manitoba budget — CBC News — 2026
[26] https://www.rbc.com/en/economics/canadian-analysis/provincial-and-fiscal-outlooks/provincial-budgets-and-economic-statements/manitoba-budget-2026-path-to-balance-maintained-despite-negative-in-year-surprise/ — Manitoba Budget 2026 — RBC Economics
[27] https://www.cbc.ca/news/canada/nova-scotia/offshore-wind-projects-9.7135261 — Nova Scotia set to pass offshore wind law — CBC News — 2026
[28] https://news.hydroquebec.com/news/press-releases/all-quebec/hydro-quebec-launches-request-information-inform-potential-development-offshore-wind-farms-off-nova-scotia.html — Hydro-Québec RFI for NS offshore wind — Hydro-Québec — 2026
[29] https://www.offshorewind.biz/2026/02/26/nova-scotia-setting-up-framework-for-offshore-wind-revenue/ — Nova Scotia Setting Up Framework for Offshore Wind Revenue — Offshore Wind — Feb 26 2026
[30] https://novascotia.ca/offshore-wind/ — Offshore wind — Government of Nova Scotia
[31] https://www.canadianminingjournal.com/news/northcliff-advancing-its-sisson-critical-minerals-project-in-new-brunswick/ — Northcliff advancing Sisson critical minerals project — Canadian Mining Journal — 2026
[32] https://www.cbc.ca/news/canada/new-brunswick/sisson-mine-project-revival-1.7554589 — Sisson tungsten mine critical mineral — CBC News — 2026
[33] https://canada.constructconnect.com/dcn/news/projects/2026/03/new-brunswick-government-hoping-to-restart-critical-mineral-mine-south-of-fredericton — NB government hoping to restart critical mineral mine — Daily Commercial News — March 2026
[34] https://www.cbc.ca/news/canada/new-brunswick/jd-irving-reversing-falls-pulp-mill-1.7249554 — Irving plans $1.1B upgrade to west side pulp mill — CBC News — 2024-2026 update
[35] https://www.offshore-mag.com/production/news/55338469/cenovus-energy-cenovus-targets-spring-startup-for-west-white-rose-oil-project-offshore-newfoundland — Cenovus targets spring startup for West White Rose — Offshore Magazine — 2026
[36] https://www.cbc.ca/news/canada/newfoundland-labrador/cenovus-white-rose-production-1.7463702 — West White Rose on target for first oil in 2026 — CBC News — 2026
[37] https://www.gov.nl.ca/fin/economics/eb-oil/ — Oil Production Up 69.2% in February 2026 — NL Department of Finance
[38] https://www.gov.nl.ca/releases/2026/exec/0303n05/ — Agreement to Advance Bay du Nord Project — NL News Releases — March 3 2026
[39] https://www.princeedwardisland.ca/en/service/pre-budget-consultations-2026 — Pre-Budget Consultations 2026 — Government of Prince Edward Island
[40] https://www.investcanada.ca/news/small-province-big-opportunity-renewable — Small province, big opportunity — Invest in Canada — 2025-26
[41] https://www.cer-rec.gc.ca/en/data-analysis/energy-markets/renewable-energy-canada/provinces/renewable-power-canada-prince-edward-island.html — Renewable Energy in Canada – Prince Edward Island — Canada Energy Regulator
[42] https://www.princeedwardisland.ca/en/feature/renewable-energy-indicators — Renewable Energy Indicators — Government of PEI
[43] https://yukon.ca/en/news/eagle-gold-mine-receivership-credit-agreement-extended-april-1-2026 — Eagle Gold Mine receivership credit agreement extended — Government of Yukon
[44] https://www.aptnnews.ca/national-news/proposed-casino-mine-inches-forward-to-yukons-first-panel-review/ — Proposed Casino mine inches forward — APTN News — 2026
[45] https://www.westerncopperandgold.com/casino-project/ — Casino Project — Western Copper and Gold
[46] https://www.mining.com/western-copper-and-gold-raising-29-million-for-casino-project-in-yukon/ — Western Copper and Gold raising $29M — MINING.COM — 2026
[47] https://www.theglobeandmail.com/business/article-a-list-of-carneys-major-projects-centred-on-the-north/ — Carney's four newly announced Northern major projects — Globe and Mail — 2026
[48] https://canada.constructconnect.com/dcn/news/projects/2026/03/n-w-t-s-top-three-projects-advance-to-major-projects-office — NWT's top three projects advance to Major Projects Office — Daily Commercial News — March 2026
[49] https://www.gov.nt.ca/newsroom/taltson-hydro-expansion — Taltson Hydro Expansion — Government of Northwest Territories
[50] https://www.gov.nt.ca/en/newsroom/minister-cleveland-welcomes-federal-support-ekati-diamond-mine-outlines-next-steps-northern — Federal support for Ekati Diamond Mine — GNWT — 2026
[51] https://www.cbc.ca/news/canada/north/baffinland-says-cleared-for-steensby-project-nunavut-9.7066314 — Baffinland cleared to break ground on Steensby — CBC News — 2026
[52] https://www.cbc.ca/news/canada/north/baffinland-2026-steensby-hunters-reassessment-1.7498351 — Nunavut hunters urge reassessment — CBC News — April 2025 / 2026 update
[53] https://www.baffinland.com/operation/mary-river-mine/ — Mary River Mine — Baffinland Iron Mines
[54] https://www.hiringlab.org/en-ca/2026/04/10/march-2026-labour-force-survey-holding-steady/ — March 2026 Labour Force Survey: Holding Steady — Indeed Hiring Lab Canada — April 10 2026
[55] https://economics.td.com/ca-employment — Canadian Employment March 2026 — TD Economics
[56] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703 — Labour force characteristics by province — StatCan Table 14-10-0287 — 2026-04-11
[57] https://iaac-aeic.gc.ca/050/evaluations — Impact Assessment Registry — IAAC — 2026-04-11
[58] https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610040201 — GDP expenditure-based by province — StatCan Table 36-10-0402
[59] https://statistique.quebec.ca/ — Institut de la statistique du Québec — 2026-04-11
[60] https://www.gov.nl.ca/ — Government of Newfoundland and Labrador — 2026-04-11
