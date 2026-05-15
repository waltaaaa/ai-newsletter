# Sector & Industry Research — Week of 2026-05-15
Generated: 2026-05-15
Industries covered: All 20 NAICS (5 goods + 15 services)
Agent: 1C (tldr-researcher-sector)
Search waves: Wave 4 (project sectors) + Wave 4b (NAICS GDP industries) + Wave 7 (mega projects) + labour/GDP cross-checks
Note: indicators.json is source of truth (BoC 2.25%, CPI +2.4% YoY March, unemployment 6.9% April, real GDP -0.6%, housing starts 279,317 SAAR). briefing_latest.json (2026-04-19) metrics are stale and not cited.

---

## 1. Data Quality Audit

Project database: 7,480 projects total. 830 first-tracked in the last 21 days. Status distribution: Under Review 2,631; Proposed 2,577; Under Construction 1,023; Approved 561; Complete 501; Cancelled 156; On Hold 31. Project records carry mixed sector taxonomies (project-sector labels plus NAICS codes); values are stored as formatted strings ($X M/B).

### Sector Project Coverage (project-sector aggregation, parsed values)
| NAICS | Sector Name | Project Count | Total Value | Status |
|-------|------------|-------------|-------------|--------|
| 11 | Agriculture, Forestry, Fishing | ~14 (agriculture 2, forestry 12) | ~$4.7B | GAP — low project count, supplement with research |
| 21 | Mining, Quarrying, Oil/Gas | ~447 (mining 347, oil_gas 39, mineral mines/coal/quarries ~61) | ~$315B+ | OK |
| 22 | Utilities | ~830 (power_energy 310, Energy 280, Clean Energy 203, Water/Wastewater 588 partial) | ~$474B | OK |
| 23 | Construction | ~1,074 (infrastructure) + cross-sector | ~$134.6B | OK |
| 31-33 | Manufacturing | ~78 (Manufacturing 77, aerospace 1) | ~$129B | OK |
| 41 | Wholesale Trade | sparse — research-driven | n/a | GAP — covered via StatCan |
| 44-45 | Retail Trade | sparse — research-driven | n/a | GAP — covered via StatCan |
| 48-49 | Transportation & Warehousing | ~583 (Ports & Logistics 162, Transit & Rail 354, transport_logistics 67) | ~$32B | OK |
| 51 | Information & Cultural | ~36 (Technology) + telecom 48 | ~$71B | OK |
| 52 | Finance & Insurance | sparse — research-driven | n/a | GAP — covered via StatCan/ISED |
| 53 | Real Estate & Rental/Leasing | ~202 (residential 138, commercial_mixed 64) | ~$59B | OK |
| 54 | Professional/Scientific/Technical | sparse — research-driven | n/a | GAP — covered via ISED |
| 55 | Management of Companies | sparse — no discrete pipeline | n/a | GAP — covered via context |
| 56 | Admin & Waste Management | ~14 (environment) + waste facilities ~6 | ~$2.5B | GAP — covered via research |
| 61 | Educational Services | ~150 (Education) | ~$5.3B | OK |
| 62 | Health Care & Social Assistance | ~253 (Healthcare) | ~$21B | OK |
| 71 | Arts, Entertainment & Recreation | subset of tourism_culture 142 | ~$21.7B (with 72) | OK |
| 72 | Accommodation & Food Services | subset of tourism_culture 142 | shared | OK |
| 81 | Other Services | sparse — research-driven | n/a | GAP — covered via research |
| 91 | Public Administration | ~173 (government) | ~$6.5B | OK |

### Critical Gaps Found
Per `data_gap_report.md` (2026-05-15, Overall Freshness B): no blocking gaps. Uranium and canola have no timeseries series (qualitative reference only — do not assert price moves). Nickel/zinc spot-only (no W/M/Y deltas). QC/ON quarterly provincial economic accounts last Q3 2025 (source-side lag). National monthly timeseries (cpi, unemployment, housingStarts) lag indicators.json by one month — charts display through March only. Service-industry NAICS (41, 44-45, 52, 54, 55, 56, 81) have thin discrete project pipelines by design — covered via StatCan/ISED industry data and research below.

---

## 2. Sector Activity Summary

| NAICS | Sector | Recent Tracking | Value Trend | Activity |
|-------|--------|------------|------------|----------|
| 21 | Mining & Energy | 43 new (mining) in 21d | ↑ | HIGH — $12.1B critical-minerals capital unlocked |
| 22 | Utilities/Power | 36 new (Energy) in 21d | ↑ | HIGH — nuclear strategy, AI-data-centre power demand |
| 48-49 | Transportation | 137 new (Transit/Rail + Ports) in 21d | ↑ | HIGH — Ontario $210B 10-yr capital plan |
| 23 | Construction | 44 new (infrastructure) in 21d | → | HIGH — multi-billion build-out |
| 31-33 | Manufacturing | 28 new in 21d | ↑ | MEDIUM — PMI 53.3 April, +1.8% Feb GDP |
| 62 | Healthcare | within Healthcare 253 | ↑ | MEDIUM — BC $6.4B, QC $2.3B/10yr |
| 11 | Agriculture | 2 discrete | → | LOW pipeline, HIGH policy ($5B FCC coalition) |
| 51 | Info/Telecom | 29 new (Technology) in 21d | ↑ | HIGH — sovereign AI data centres |

---

## 3. Sector Spotlights (ALL 20 NAICS INDUSTRIES)

### GOODS INDUSTRIES

#### 11: Agriculture, Forestry, Fishing & Hunting
- **Top story**: Farm Credit Canada convened a coalition of 20+ investment organizations prepared to deploy up to $5 billion into Canadian agriculture and food innovation by 2030; combined with FCC's May 2025 commitment this represents $7 billion in new investment by 2030 [6].
- **Key data**: Sector drives $150 billion of GDP, $100 billion of exports, one in nine jobs [4]. The five-year, $3.5-billion Sustainable Canadian Agricultural Partnership continues; $75 million over five years (2026-27 to 2030-31) added to AgriMarketing Market Diversification streams [5]. Agriculture and Agri-Food Canada 2026-27 planned spending: $3,677,569,159 [4].
- **Project activity**: Only ~2 discrete agriculture projects + ~12 forestry in the database; pipeline is research-led, not project-led. Forestry: Western Forest Products extended closure of its Chemainus, B.C. sawmill (down since June 2025) through end of 2026; BC allowable annual cut down one-third over 20 years [9]. Western SPF 2×4 #2&Btr lumber priced US$490/mfbm early April 2026 [8].
- **Labour trends**: U.S. Section 232 tariffs plus higher AD/CVD raise Canadian lumber producer costs an estimated 25-30%; rural community employment most affected [9].
- **Emerging trends**: Market diversification away from U.S.; agri-tech investment; potash exploration spending intentions +64% to $130M for non-metals in 2026 [2].

#### 21: Mining, Quarrying & Oil/Gas Extraction
- **Top story**: Canada secured 30 new critical-minerals partnerships unlocking $12.1 billion in mining-project capital with 12 allied partners; a separate $165.2M for 22 projects unlocks $434M across eight provinces [3]. New First and Last Mile Fund backed by $1.5 billion federal funding for mine-supporting infrastructure [3].
- **Key data**: Junior exploration spending 2025 $2.27 billion (+8%); 2026 intentions point to $2.91 billion (record). Iron-ore exploration intentions rise to $114M in 2026; non-metals (potash) +64% to $130M [2]. Oil-drilling/gas-extraction industry market size $227.6 billion in 2026 [1].
- **Project activity**: ~447 mining/oil-gas projects, ~$315B+ pipeline. NexGen Energy Rook I uranium project (SK) in final federal licence hearings; BC Critical Minerals Office added Northisle North Island, Surge Berg, Defense Metals Wicheeda [3]. Western Canada drilling: 213 average active rigs in 2026 (up from 201), 5,709 wells (+~3%) [1]. Oil-sands proposals total 4.1 million bbl/d combined capacity [1].
- **Labour trends**: Capital expenditure in oil and gas projected to rise from $50B (2025) to $57B by 2039 (Current Measures) [1].
- **Emerging trends**: Industry consolidation, accelerated permitting, national-interest foreign-investment review.

#### 22: Utilities (Electricity, Gas, Water)
- **Top story**: Natural Resources Canada is developing a new Nuclear Energy Strategy (release end of 2026) on four objectives: new builds, global supply/export, uranium/fuel expansion, and innovation incl. fusion [announced at CNA2026, April 2026] [10].
- **Key data**: Canada produced 623 TWh of electricity in 2024 — 65% renewable, 78% non-GHG; nuclear 13.5%, hydro 57.4% [11]. $40-million 2026-27 federal investment to assess a Canadian-controlled microreactor for remote/northern DND facilities [10].
- **Project activity**: ~830 utilities/power/water projects (~$474B). OPG–Port Hope agreement for new nuclear at Wesleyville site; project description submitted to IAAC, up to 10 GWe envisaged (AP1000/EPR/CANDU MONARK/BWRX-300), first unit targeted 2040 [11]. Synapse Data Centre Inc. $10-billion data-centre-plus-gas-power plan, rural Alberta [25].
- **Labour trends**: AI data-centre power demand (Telus cluster 85→150 MW) is a new structural electricity-load driver [25].
- **Emerging trends**: SMR/microreactor deployment; clean-power data-centre integration; uranium supply chain.

#### 23: Construction
- **Top story**: Ontario's most ambitious provincial capital plan in Canadian history — more than $210 billion over 10 years, including $37 billion in 2026-27 [13].
- **Key data**: Much of Canadian heavy-civil activity is urban transit, energy infrastructure, transportation corridors, port expansions, regional utilities [13]. February 2026 construction within national GDP supported broad activity; manufacturing-led February GDP +0.2% [22].
- **Project activity**: ~1,074 infrastructure projects (~$134.6B) plus cross-sector. Active: George Massey Tunnel replacement ($4.15B, 8-lane, major construction 2026, BC); GO Transit Bowmanville Extension (18.7 km, broke ground Jan 2026); Queensborough Bridge upgrade ($20.8M contract, spring 2026 start) [13]. Under Construction examples in DB: Calgary Green Line LRT Phase 1 ($6.2B), Taza Mixed Use ($4.5B).
- **Labour trends**: Heavy-civil labour demand concentrated in transit and energy corridors [13].
- **Emerging trends**: P3 delivery, transit-corridor megaprojects, port expansion.

#### 31-33: Manufacturing
- **Top story**: S&P Global Canada Manufacturing PMI rose to 53.3 in April 2026 from 50.0 in March — strongest improvement in business conditions since June 2022 [16][20].
- **Key data**: February 2026 manufacturing sales $71.2 billion (+3.6% m/m); manufacturing led February GDP, +1.8% (largest sector gain since January 2023, durable goods +3.6%) [19][22]. January 2026 production -4.20% y/y; Q4 2025 industrial capacity use 78.5% (-0.4 pt q/q) [16].
- **Project activity**: ~78 manufacturing projects (~$129B). Battery/EV: Electra Battery Materials — $20M federal investment (Strategic Response Fund) toward $99.4M cobalt-sulfate expansion, Temiskaming Shores, ON [24]. Umicore CAM/precursor factory, Loyalist ON (production 2026); Ford/EcoProBM/SK On cathode plant Bécancour QC (2026); BASF CAM/recycling Bécancour [24]. Northvolt QC funding ended Sept 2025 (parent collapse) [24]. DB: Dow Net-Zero Polyethylene ($11.5B AB), Dow Path2Zero ($10.1B AB).
- **Labour trends**: Fastest manufacturing employment rise in 13 months (April PMI); input costs rose at fastest pace in 3.5+ years (fuel/freight); confidence below long-run average on U.S. tariff concern [16][20].
- **Emerging trends**: EV/battery supply chain, U.S. tariff uncertainty, durable-goods recovery.

### SERVICES INDUSTRIES

#### 41: Wholesale Trade
- **Top story**: Wholesale sales rose 1.9% in March 2026 (ex-petroleum/oilseed-grain); Q1 2026 wholesale sales +1.8% vs Q1 2025 [StatCan, 2026-05-14] [26].
- **Key data**: Machinery, equipment & supplies subsector +6.5% to $19.5B (computer/communications equipment +17.9% to $5.9B); personal/household goods +0.8% to $13.3B (pharmaceuticals +1.0% to $7.8B) [26]. March wholesale +1.9% vs +1.4% expected.
- **Project activity**: No discrete pipeline (distribution/warehousing capital captured under NAICS 48-49). Linked to manufacturing recovery and import flows.
- **Labour trends**: Tied to goods-producing recovery; tracked via StatCan wholesale series.
- **Emerging trends**: Computer/communications equipment demand strength; pharmaceutical wholesale growth.

#### 44-45: Retail Trade
- **Top story**: Retail sales increased 0.7% to $72.1 billion in February 2026; advance estimate +0.6% m/m for March (third consecutive monthly gain) [StatCan / TD] [26].
- **Key data**: Retail sales +3.80% y/y in February 2026 [26]. March GDP: retail trade decreased, partly offsetting wholesale and transportation gains [27].
- **Project activity**: Retail capital largely embedded in commercial_mixed (e.g., Oakridge Park 650,000 sq ft retail opening spring 2026) [21].
- **Labour trends**: Tracked via StatCan; consumer discretionary spending pressured by trade tensions and slow income growth [17].
- **Emerging trends**: Mixed-use retail integration; e-commerce/last-mile logistics overlap.

#### 48-49: Transportation & Warehousing
- **Top story**: Transport Canada working with railways to cut freight rates for interprovincial steel and lumber beginning spring 2026; rail terminal expansion and double-tracking underway nationally [Transport Canada 2026-27 Departmental Plan] [12].
- **Key data**: Canada's ports serve a $1.9 trillion international-trade economy; Prince Rupert intermodal investment; containerized cargo projected 4.33% CAGR 2026-2031 [12]. Transportation and warehousing was a positive contributor to March 2026 GDP [27].
- **Project activity**: ~583 transport/rail/port projects (~$32B); 137 new in last 21 days (Transit & Rail + Ports & Logistics). GO Transit Bowmanville Extension; port terminal expansions [13][12].
- **Labour trends**: Road freight held 60.97% of freight market 2025; rail competitiveness improving via terminal upgrades [12].
- **Emerging trends**: Green/intermodal logistics now baseline expectation; rail-rate relief for steel/lumber.

#### 51: Information & Cultural Industries
- **Top story**: Government of Canada and TELUS advanced sovereign AI infrastructure; Vancouver/Kamloops data-centre cluster starting at 85 MW power draw scaling to 150 MW by 2032, 98% clean hydro [2026-05] [25]. Bell named Bird Construction for Sherwood AI data centre, SK [2026-05-14] [25].
- **Key data**: Sovereign large-scale AI data-centre call for proposals (>100 MW) ran Jan 15–Feb 15 2026 [25]. Canada data-centre market USD 13.06B in 2026 (from USD 11.46B 2025), USD 25.09B by 2031 (13.95% CAGR) [14]. Telecom cumulative network investment $64.4B since 2020; 5G requires ~$26B investment, projected +250,000 jobs and +$40B GDP by 2026 [14]. Canadian media a $22.6B GDP industry, 193,120 jobs; creative industries $65.3B GDP / 668,367 jobs (2024) [51a]. Culture-sector nominal GDP $16.7B Q3 2025 (+0.2%) [51a].
- **Project activity**: ~36 Technology + ~48 telecom projects (~$71B+); 29 new Technology in 21 days. Synapse $10B AB; Bell Sherwood SK; Telus BC cluster [25].
- **Labour trends**: Telecom operators moderating capex (networks near full population reach); AI data-centre construction labour rising [14].
- **Emerging trends**: Sovereign AI compute; data-centre-power coupling; Canadian media displaced by non-Canadian digital platforms (94% of digital ad spend) [51a].

#### 52: Finance & Insurance
- **Top story**: 2026 Spring Economic Update includes measures on national investment, banking competition, housing support, and financial-crime reduction affecting banking, insurance and payments [52a][52b].
- **Key data**: Finance & insurance +0.3% m/m February 2026; sector generates $167 billion GDP, 8.5% of total economic output [52a]. Six largest banks hold 93% of banking assets [52a]. Q1 2026 GDP tracking ~1.7% (TD) after Q4 2025 contraction [52a].
- **Project activity**: No discrete capital pipeline (services industry); office-space demand overlaps NAICS 53.
- **Labour trends**: Stable; sector tracked via StatCan GDP-by-industry [52a].
- **Emerging trends**: Open-banking/financial-sector competition reform; AML framework strengthening; digital finance.

#### 53: Real Estate & Rental/Leasing
- **Top story**: National housing starts +6% y/y in 2025 to 259,000 units; CMHC projects starts to decline 2026-2028 on elevated costs, softer demand, higher inventories [residential a].
- **Key data**: Toronto condo resale prices down ~15-18% from 2022 peak by late 2025; rental starts exceeded condo apartment starts in City of Toronto for first time [residential a]. Federal First-Time Home Buyers' GST/HST Rebate became law March 12 2026 (Bill C-4), up to $50,000 [residential a]. Office-loan lender budgets "surged" for 2026 — first rebound in six years [commercial a].
- **Project activity**: ~202 residential/commercial_mixed projects (~$59B). Oakridge Park (5.0M sq ft, 28 acres, 3,000+ units, 700,000 sq ft office; retail opens spring 2026) [21]; Anthem two Vancouver mixed-use rental towers (construction early 2026); Welland residential development advancing [residential a][21].
- **Labour trends**: Residential construction labour shifting toward rental/purpose-built.
- **Emerging trends**: Condo-to-rental shift; office recovery on return-to-office; HST relief programs for pre-construction condos (Apr 1 2026–Mar 31 2027).

#### 54: Professional, Scientific & Technical Services
- **Top story**: NAICS 54 GDP grew 2.2% in 2024 vs 2.0% for the overall economy (NAICS 11-91); slight job growth expected over 2024-2026 in Ontario [54a].
- **Key data**: 2024 sector GDP: BC $26.3B (7.99% of provincial), AB $19.4B (5.06%), ON $74.4B (8.6%, 2023), MB $2.6B, SK $2.2B [54a]. No discrete 2026 GDP figure published yet.
- **Project activity**: No discrete capital pipeline; engineering/architecture/IT services support construction and AI-data-centre buildout (cross-references NAICS 23, 51).
- **Labour trends**: Slight job growth Ontario 2024-2026 [54a].
- **Emerging trends**: AI/data-centre engineering demand; professional-services support to critical-minerals and defence programs.

#### 55: Management of Companies & Enterprises
- **Top story**: No significant standalone developments found in research for Management of Companies this week. Activity is embedded in corporate-headquarters and holding-company structures rather than discrete projects.
- **Key data**: No discrete StatCan release this week specific to NAICS 55; sector moves with broader corporate-investment cycle (oil-and-gas capex $50B→$57B, manufacturing turnaround) [1][16].
- **Project activity**: No discrete capital pipeline (holding/head-office function).
- **Labour trends**: Tracked within broader business-services employment; LFS April showed business/building/support services +22,000 jobs (NAICS 55/56 grouping) [labour a].
- **Emerging trends**: Corporate consolidation in mining (national-interest FDI review) [3].

#### 56: Administrative & Waste Management Services
- **Top story**: Environment Journal 2026 Top 25 Remediation Projects total $5.03 billion — nuclear-waste cleanup, mining remediation, brownfield redevelopment; Kitchener Green Residential Subdivision ($63M) ranked #10 [56a].
- **Key data**: 2024: 110,597 non-employer establishments + 53,288 employer establishments in NAICS 56; 52.1% micro-businesses [56b]. Federal Contaminated Sites Action Plan continues under ECCC [56a].
- **Project activity**: ~14 environment + ~6 waste-management facilities in DB (~$2.5B). Top-25 remediation slate $5.03B [56a].
- **Labour trends**: Business, building and other support services +22,000 jobs in April 2026 LFS (largest sector gain) [labour a].
- **Emerging trends**: In-situ/bioremediation, digital monitoring/GIS, low-carbon remediation methods [56a].

#### 61: Educational Services
- **Top story**: University of Toronto unveiled the Temerty Building — nine-storey, 388,000 sq ft, consolidating Faculty of Medicine and Arts & Science at King's College Circle, St. George campus [edu a].
- **Key data**: UBC Gateway Health Building $189.91M (occupancy 2026); Camosun College engineering renovation (construction fall 2026, completion spring 2029); Ontario investing $1B+ over five years from 2025-26 for postsecondary renewal [edu a].
- **Project activity**: ~150 education projects (~$5.3B).
- **Labour trends**: Construction labour for campus renewal; sector employment tracked via StatCan.
- **Emerging trends**: Campus real-estate intensification; medical/health-faculty consolidation.

#### 62: Health Care & Social Assistance
- **Top story**: BC delivering more than $6.4 billion in new hospital construction starting 2025-2026 — 30 hospital/health-facility projects, 11 long-term-care centres, four cancer centres across five health regions [health a].
- **Key data**: New St. Paul's Hospital Vancouver (1.2M sq ft, complete 2026, open 2027); Dawson Creek hospital ($590M, ~92% complete); Prince George patient tower ($1.58B phase 2); Quebec allocated $2.3 billion over 10 years for hospital construction/expansion in 2026-27 budget [health a].
- **Project activity**: ~253 healthcare projects (~$21B).
- **Labour trends**: Health care and social assistance +18,000 jobs in April 2026 LFS [labour a].
- **Emerging trends**: Long-term-care and cancer-centre buildout; hospital-repair backlog (QC).

#### 71: Arts, Entertainment & Recreation
- **Top story**: BC Place Vancouver upgraded to host seven FIFA World Cup 2026 matches — expected to attract 350,000+ fans and generate ~$1 billion in additional BC visitor spending 2026-31 [tourism a].
- **Key data**: Ontario NAICS 71 employed 177,700 (2024), $8.2B+ GDP; Quebec job growth 2024-2026 expected negative on changed consumer habits and funding lag [71a]. International Convention Attraction Fund secured 116 events (~324,200 attendees, $803.3M direct impact) as of March 2026 [tourism a].
- **Project activity**: Subset of ~142 tourism_culture projects (~$21.7B with NAICS 72). Federal $726,000 in Corleck Building cultural space, Toronto [tourism a].
- **Labour trends**: Moderate-to-slow employment growth Ontario; negative Quebec [71a].
- **Emerging trends**: FIFA World Cup 2026 venue/event spending; discretionary-spending sensitivity to trade tensions.

#### 72: Accommodation & Food Services
- **Top story**: Canada hotel construction pipeline at record Q1 2026 levels — 331 hotel projects / 45,401 rooms; Ontario leads with 190 projects / 27,567 rooms (57%); Toronto 71 projects / 11,420 rooms [tourism b].
- **Key data**: Canada hospitality market USD 21.34B in 2026 (from USD 20.29B 2025) → USD 27.46B by 2031 (5.18% CAGR); ~1.9M workers, ~9.5% of national employment; CoStar projects 1.9% RevPAR growth Canada 2026 [72a].
- **Project activity**: Shared with tourism_culture (~$21.7B). 45,401-room hotel pipeline [tourism b].
- **Labour trends**: Accommodation and food services +13,000 jobs in April 2026 LFS [labour a]; persistent labour shortage; reduced international-student/temporary-work permits constraining supply [72a].
- **Emerging trends**: Luxury-hotel pipeline growth; FIFA 2026 demand; margin pressure from energy/tax/insurance costs.

#### 81: Other Services (except Public Administration)
- **Top story**: No significant standalone capital developments found in research for Other Services this week (personal/repair/civic/religious organizations — research-led, no discrete project pipeline).
- **Key data**: Sector moves with consumer discretionary spending, pressured by trade tensions and slow household-income growth per Bank of Canada outlook [71a]. Tracked via StatCan GDP-by-industry.
- **Project activity**: No discrete capital pipeline.
- **Labour trends**: Tracked within broader services employment; LFS April showed overall employment little changed (-18,000) [labour a].
- **Emerging trends**: Consumer-confidence sensitivity to U.S. trade tensions [71a].

#### 91: Public Administration
- **Top story**: Federal 2026-27 Main Estimates present $502.8 billion in budgetary spending ($230.4B voted, $272.4B statutory) [91a].
- **Key data**: Department of Finance 2026-27 planned spending $158,271,364,374 (incl. $158,123,516,663 statutory/transfers); Public Services and Procurement Canada is central purchasing agent and real-property manager; Canada achieved NATO 2% GDP defence-spending target in 2025-26 [91a][defence a]. BC budget 2026 shows rising deficit and tax increases; Ontario hiring freeze on non-essential positions since 2018 [91a].
- **Project activity**: ~173 government projects (~$6.5B); federal/provincial capital programs cross-reference construction, defence, healthcare.
- **Labour trends**: Provincial efficiency measures (Ontario hiring freeze); federal procurement reform [91a].
- **Emerging trends**: Defence Investment Agency legislation (Spring 2026) moving Defence Construction Canada under DIA [defence a].

---

## 4. Commodity Price Impact Analysis

(Per data_gap_report: WTI ~$100.16, gold ~$4,563, copper, CAD/USD 0.728 current and chartable in timeseries.json; uranium and canola NOT in timeseries — qualitative reference only.)

### Energy (Oil & Gas)
- **Affected sectors**: NAICS 21 (Mining & Energy), 22 (Utilities), 23 (Construction), 48-49 (Transport), 31-33 (Manufacturing inputs).
- Oil-and-gas market size $227.6B in 2026; 2026 capex ~$50B; 213 average active rigs, 5,709 wells (+~3%) [1]. Oil-sands proposals total 4.1M bbl/d combined [1]. ~447 mining/oil-gas projects (~$315B+) in pipeline.

### Metals
- **Affected sectors**: NAICS 21 (Mining).
- Critical-minerals capital unlocked: $12.1B (30 partnerships) + $434M (22 projects) [3]. Junior exploration 2026 intentions $2.91B record; iron-ore $114M, non-metals/potash $130M (+64%) [2]. Gold ~$4,563 (timeseries, current). Nickel/zinc spot-only — state level without W/M/Y deltas.

### Agricultural Commodities
- **Affected sectors**: NAICS 11 (Agriculture), 72 (Food Services).
- Canola: NO timeseries series — do not assert price moves; reference qualitatively. Lumber: Western SPF 2×4 #2&Btr US$490/mfbm early April 2026 [8]. Sector $150B GDP / $100B exports [4].

### Utilities / Electricity
- **Affected sectors**: NAICS 22 (Utilities), 23 (Construction), 31-33 (Manufacturing), 51 (Data centres), 62 (Healthcare).
- 623 TWh generated 2024 (65% renewable); AI data-centre load a new structural driver (Telus 85→150 MW; Synapse $10B + gas plant) [11][25]. Uranium: NO timeseries series — qualitative reference only; NexGen Rook I in final licence hearings [3].

---

## 5. Major Project Announcements by Sector

### New / Advancing This Period
- **Manufacturing (31-33)**: Electra Battery Materials cobalt-sulfate expansion, Temiskaming Shores ON — $99.4M project, $20M federal Strategic Response Fund [2026-05] [24].
- **Information/Utilities (51/22)**: TELUS sovereign AI data-centre cluster Vancouver/Kamloops 85→150 MW [2026-05] [25]; Bell Sherwood AI data centre SK, Bird Construction named [2026-05-14] [25].
- **Mining (21)**: $12.1B critical-minerals capital via 30 partnerships [2026-03] [3]; NexGen Rook I federal licence hearings [3].
- **Defence (91/23)**: Phase 2 military housing — ~7,500 RHUs, 25 sites, >$3.7B; CFB Gagetown infrastructure completion March 2026 [defence a].
- **Construction/Transport (23/48-49)**: GO Transit Bowmanville Extension broke ground Jan 2026; Queensborough Bridge $20.8M contract spring 2026 [13].
- **Healthcare (62)**: Quebec $2.3B/10yr hospital allocation in 2026-27 budget; BC $6.4B starting 2025-26 [health a].

### Status Changes
DB: Under Construction 1,023; Approved 561. Notable Under Construction: Calgary Green Line LRT Phase 1 ($6.2B), Dow Net-Zero Polyethylene ($11.5B AB), Dow Path2Zero ($10.1B AB), Air Products Hydrogen ($4.6B AB), Taza Mixed Use ($4.5B AB).

---

## 6. Labour Market by Sector

### Employment (April 2026 LFS, StatCan released 2026-05-08) [labour a]
| NAICS | Sector | April Change | Source |
|-------|--------|------------|--------|
| 56/55 | Business, building & support services | +22,000 | [labour a] |
| 62 | Health care & social assistance | +18,000 | [labour a] |
| 72 | Accommodation & food services | +13,000 | [labour a] |
| All | Total employment | -18,000 (-0.1%); rate 60.5%; unemployment 6.9% | [labour a] |

Provincial: ON +42,000; QC -43,000; NL -5,200; SK -4,000; NB -2,700 [labour a].

### Labour Shortage Indicators
- **72 Accommodation & food**: most acute shortage; reduced international-student/temporary-work permits constraining supply [72a].
- **31-33 Manufacturing**: fastest employment rise in 13 months (April PMI 53.3) [16].
- **11 Forestry**: rural employment contraction from sawmill closures and tariff cost increases (25-30%) [9].

---

## 7. Policy and Regulatory Impacts

### Energy Transition / Carbon Policy
New Nuclear Energy Strategy (release end 2026) — new builds, export, uranium/fuel, fusion; $40M microreactor assessment [10][11]. AI data-centre proposals favour Indigenous participation and minimized environmental impact [25].

### Trade Policy
U.S. Section 232 + AD/CVD raise Canadian lumber costs 25-30% [9]; manufacturing confidence below long-run average on U.S. tariff uncertainty [16]; AgriMarketing market-diversification streams ($75M/5yr) respond to trade instability [5]; rail-rate relief for interprovincial steel/lumber spring 2026 [12].

### Environmental Regulation
Federal Contaminated Sites Action Plan continues (ECCC); Top-25 remediation slate $5.03B [56a]. IAAC reviewing OPG Wesleyville nuclear and LNG Canada terminal [11].

### Sector-Specific Regulation
Defence Investment Agency legislation Spring 2026 (Defence Construction Canada moved under DIA) [defence a]; financial-sector competition/AML reform in 2026 Spring Economic Update [52a][52b]; expanded federal defence-buying powers for national/economic-security cases [defence a].

---

## 8. Emerging Stories and Cross-Sector Trends

### Fastest Growing
- **Mining/critical minerals (21)**: $12.1B capital unlocked, record junior exploration intentions $2.91B [2][3].
- **Information/data centres (51/22)**: sovereign AI buildout (Telus, Bell, Synapse) — market USD 13.06B→25.09B by 2031 [14][25].
- **Manufacturing (31-33)**: PMI 53.3 (highest since June 2022), +1.8% Feb GDP [16][19].

### Headwinds
- **Forestry (11)**: U.S. tariffs (25-30% cost increase), sawmill closures, declining BC cut [9].
- **Residential (53)**: CMHC projects housing-starts decline 2026-2028; condo presales weak [residential a].
- **Arts/recreation (71)** Quebec: negative job growth 2024-2026 [71a].

### Sectoral Shifts
- Condo → purpose-built rental (53) [residential a]; U.S.-export → market diversification (11, 31-33) [5]; electricity load shifting toward AI data centres (22/51) [25].

---

## 9. Coverage Gaps and Priorities

- **Discrete-pipeline-sparse NAICS** (41, 44-45, 52, 54, 55, 81): no project records by design — covered via StatCan/ISED industry data and research. Analyst should treat these as research-driven, not project-count-driven.
- **Agriculture (11)**: only ~2 discrete projects — pipeline relies on policy/investment-coalition data [4][6].
- **Uranium/canola**: no timeseries — qualitative only.
- **NAICS 55 / 81**: thinnest coverage; documented as "no significant standalone developments" with macro-cycle context.

---

## 10. Master Source Registry

[1] https://www.canadianenergycentre.ca/five-things-to-watch-in-canadas-oil-and-gas-industry-in-2026/ ; https://boereport.com/2026/01/05/five-things-to-watch-in-canadas-oil-and-gas-industry-in-2026/ ; https://www.ibisworld.com/canada/industry/oil-drilling-gas-extraction/103/ ; https://www.cer-rec.gc.ca/en/data-analysis/canada-energy-future/2026/results/ — Canada oil & gas 2026 drilling/capex — 2026-01 — drilling, rigs, market size, capex
[2] https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis/minerals-mining-publications/canadian-mineral-exploration-information-bulletin-0 — NRCan Mineral Exploration Bulletin — 2026 — junior exploration spending intentions
[3] https://www.canada.ca/en/natural-resources-canada/news/2026/03/canada-secures-30-new-critical-minerals-partnerships-and-unlocks-121-billion-in-mining-project-capital.html ; https://www.canada.ca/en/natural-resources-canada/news/2026/03/backgrounder-government-of-canada-invests-to-unlock-canadas-critical-minerals-advantage.html ; https://news.gov.bc.ca/releases/2026MCM0010-000179 — NRCan / BC critical minerals — 2026-03 — $12.1B capital, $165.2M/22 projects, First & Last Mile Fund
[4] https://agriculture.canada.ca/en/department/transparency/departmental-plan/2026-27-departmental-plan — AAFC 2026-27 Departmental Plan — 2026 — $150B GDP, spending $3.68B
[5] https://www.canada.ca/en/agriculture-agri-food/news/2026/02/the-government-of-canada-strengthens-support-for-agricultural-exports-with-a-new-market-diversification-program.html — AAFC market diversification — 2026-02 — $75M/5yr AgriMarketing
[6] https://www.fcc-fac.ca/en/about-fcc/media-centre/news-releases/2026/coalition-investment-canadian-agriculture-food — FCC $5B coalition — 2026 — $5B/$7B agri investment by 2030
[8] https://www.pulpandpapercanada.com/early-2026-lumber-prices-match-previous-two-years/ — Pulp & Paper Canada — 2026 — Western SPF US$490/mfbm April 2026
[9] https://www.pulpandpapercanada.com/canadas-lumber-industry-at-crossroads-report/ ; https://www.pulpandpapercanada.com/wfp-extends-closure-of-chemainus-sawmill/ — Pulp & Paper Canada — 2026 — Section 232/AD-CVD 25-30% cost, Chemainus closure, BC cut decline
[10] https://www.canada.ca/en/natural-resources-canada/news/2026/04/government-of-canada-commits-to-new-strategy-for-nuclear-energy.html ; https://www.ans.org/news/2026-04-30/article-7995/nuclear-energy-strategy-announced-at-cna2026/ — NRCan Nuclear Strategy — 2026-04 — strategy 4 objectives, $40M microreactor
[11] https://energy-information.canada.ca/en/energy-facts/clean-power-low-carbon-fuels ; https://world-nuclear.org/information-library/country-profiles/countries-a-f/canada-nuclear-power ; https://iaac-aeic.gc.ca/050/evaluations/proj/80038 — CCEI / WNA / IAAC — 2026 — 623 TWh, OPG Wesleyville, LNG Canada
[12] https://tc.canada.ca/en/corporate-services/transparency/corporate-management-reporting/departmental-plans-dp/transport-canada-2026-2027-departmental-plan ; https://www.freightamigo.com/en/blog/logistics/largest-ports-in-canada-a-2026-logistics-guide/ ; https://railgateway.ca/blog/canada-rail-shipping — Transport Canada / logistics — 2026 — rail-rate relief, port intermodal, $1.9T trade
[13] https://budget.ontario.ca/2026/chapter-1b-building.html ; https://www.on-sitemag.com/features/canadas-multi-billion-dollar-build-out/ ; https://news.gov.bc.ca/releases/2026TT0025-000178 ; https://canada.constructconnect.com/joc/news/projects/2026/02/20-8m-contract-awarded-for-queensborough-bridge-upgrade — Ontario Budget 2026 / On-Site / BC Gov — 2026 — $210B/10yr plan, Massey Tunnel, Bowmanville, Queensborough
[14] https://www.pwc.com/ca/en/industries/telecommunications/5g-digital-economy.html ; https://crtc.gc.ca/eng/publications/reports/PolicyMonitoring/2026/ctmr.htm ; https://www.mordorintelligence.com/industry-reports/canada-data-center-market — PwC / CRTC / Mordor — 2026 — $26B 5G, $64.4B telecom capex, data-centre USD 13.06B
[16] https://www.plant.ca/economy/canadas-manufacturing-sector-improves-for-second-straight-month-sp-global/ ; https://tradingeconomics.com/canada/manufacturing-production — Plant.ca / TradingEconomics — 2026-04 — PMI 53.3, capacity 78.5%, employment rise
[17] https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-arts — Job Bank NAICS 71 Ontario — 2024-2026 — discretionary-spending pressure
[19] https://globalnews.ca/news/11823847/canada-economy-manufacturing-data-statistics-canada/ — Global News / StatCan — 2026 — Feb manufacturing sales $71.2B, +1.8% GDP
[20] https://tradingeconomics.com/canada/manufacturing-pmi — TradingEconomics S&P Global PMI — 2026-04 — PMI 53.3
[21] https://www.cbre.ca/insights/articles/6-canadian-commercial-real-estate-projects-to-watch-for-in-2026 — CBRE Canada — 2026 — Oakridge Park, Anthem Vancouver towers
[22] https://www150.statcan.gc.ca/n1/daily-quotidien/260430/dq260430a-eng.htm — StatCan GDP by industry Feb 2026 — 2026-04-30 — manufacturing-led +0.2%
[24] https://www.canada.ca/en/innovation-science-economic-development/news/2026/05/government-of-canada-announces-major-investment-with-electra-battery-materials-to-expand-its-refinery-in-temiskaming-shores-ontario.html ; https://www.canada.ca/en/campaign/critical-minerals-in-canada/canadas-critical-minerals-strategy/canadas-critical-minerals-strategy-progress-update.html — ISED / NRCan — 2026-05 — Electra $99.4M/$20M, Umicore/Ford/BASF Bécancour, Northvolt ended
[25] https://www.canada.ca/en/innovation-science-economic-development/news/2026/05/government-of-canada-and-telus-advance-work-to-build-sovereign-ai-infrastructure.html ; https://www.620ckrm.com/2026/05/14/bell-names-local-contractor-architect-for-sherwood-ai-data-centre-project/ ; https://thenarwhal.ca/olds-alberta-ai-data-centre/ ; https://ised-isde.canada.ca/site/ised/en/enabling-large-scale-sovereign-ai-data-centres — ISED / 620CKRM / Narwhal — 2026-05 — Telus cluster, Bell Sherwood, Synapse $10B
[26] https://www150.statcan.gc.ca/n1/daily-quotidien/260514/dq260514a-eng.htm ; https://www150.statcan.gc.ca/n1/daily-quotidien/260424/dq260424a-eng.htm ; https://economics.td.com/ca-retail-sales — StatCan / TD — 2026-05-14 — wholesale +1.9% March, retail +0.7% Feb
[27] https://tradingeconomics.com/canada/monthly-gdp-mom ; https://www150.statcan.gc.ca/n1/daily-quotidien/260331/dq260331a-eng.htm — StatCan / TradingEconomics — 2026 — March GDP unchanged, wholesale/transport up, retail/mining down; Q1 +0.4%
[51a] https://chamber.ca/news/arts-and-culture-sector-contributes-131-billion-to-canadas-economy/ ; https://marketingnewscanada.com/news/canadian-media-is-a-226-billion-industry-its-also-in-crisis ; https://www150.statcan.gc.ca/n1/daily-quotidien/260113/dq260113c-eng.htm — Cdn Chamber / Marketing News / StatCan — 2026 — creative $65.3B GDP, media $22.6B, culture $16.7B Q3
[52a] https://en.wikipedia.org/wiki/Economy_of_Canada ; https://economics.td.com/ca-real-gdp ; https://ised-isde.canada.ca/app/ixb/cis/summary-sommaire/52 — TD / ISED — 2026 — finance +0.3% Feb, $167B GDP/8.5%, six banks 93%
[52b] https://www.fasken.com/en/knowledge/2026/05/federal-spring-economic-update-2026-highlights-affecting-financial-services — Fasken — 2026-05 — Spring Economic Update financial-services measures
[54a] https://ised-isde.canada.ca/app/ixb/cis/gdp-pid/54 ; https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-professional-services — ISED / Job Bank — 2024-2026 — NAICS 54 +2.2% 2024, provincial GDP
[56a] https://environmentjournal.ca/top-25-report-to-highlight-largest-remediation-projects-in-canada/ ; https://mte85.com/about/news/kitchener-green-subdivision-top25-remediation-project/ ; https://www.canada.ca/en/environment-climate-change/corporate/transparency/priorities-management/departmental-plans/2026-2027.html — Environment Journal / MTE / ECCC — 2026 — Top 25 $5.03B, Kitchener Green $63M, FCSAP
[56b] https://ised-isde.canada.ca/app/ixb/cis/summary-sommaire/56 — ISED Canadian Industry Statistics NAICS 56 — 2024 — establishment counts
[71a] https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-arts ; https://www.jobbank.gc.ca/trend-analysis/job-market-reports/quebec/sectoral-profile-arts — Job Bank NAICS 71 — 2024-2026 — ON 177,700/$8.2B, QC negative growth
[72a] https://www.mordorintelligence.com/industry-reports/hospitality-industry-in-canada ; https://www.cushmanwakefield.com/en/canada/insights/canadian-lodging-industry-overview ; https://www.jobbank.gc.ca/trend-analysis/job-market-reports/ontario/sectoral-profile-accommodation — Mordor / Cushman & Wakefield / Job Bank — 2026 — market USD 21.34B, 1.9M workers, 1.9% RevPAR
[91a] https://www.canada.ca/en/treasury-board-secretariat/services/planned-government-spending/government-expenditure-plan-main-estimates/2026-27-estimates.html ; https://www.canada.ca/en/department-finance/corporate/transparency/plans-performance/departmental-plans/2026-2027/dp-combined.html ; https://www.theglobeandmail.com/canada/british-columbia/article-bc-budget-2026-highlights-deficit-tax-public-service/ ; https://budget.ontario.ca/2026/chapter-1b-services.html — TBS / Finance / Globe / Ontario — 2026-27 — $502.8B Main Estimates, Finance $158.3B, BC/ON measures
[defence a] https://www.canada.ca/en/department-national-defence/news/2026/02/government-of-canada-investing-in-historic-military-housing-expansion-to-support-caf-members-and-families.html ; https://www.canada.ca/en/department-national-defence/news/2026/04/canada-invests-in-infrastructure-at-canadian-forces-base-gagetown.html ; https://www.canada.ca/en/department-national-defence/news/2026/03/canada-achieves-the-2-of-gross-domestic-product-defence-spending-benchmark.html ; https://www.cbc.ca/news/politics/defence-equipment-military-politics-9.7191921 — DND / CBC — 2026 — Phase 2 housing >$3.7B/7,500 RHU, Gagetown, 2% GDP, DIA legislation
[edu a] https://www.utoronto.ca/news/u-t-unveils-design-temerty-building ; https://facilities.ubc.ca/projects/projects-on-campus/completed-projects/gateway-building/ ; https://news.gov.bc.ca/releases/2026INF0017-000314 ; https://www.ontario.ca/page/published-plans-and-annual-reports-2025-2026-ministry-colleges-universities-research-excellence-and-security — U of T / UBC / BC Gov / Ontario — 2026 — Temerty, UBC Gateway $189.91M, Camosun, ON $1B/5yr
[health a] https://canada.constructconnect.com/joc/news/infrastructure/2025/02/more-than-6-4b-in-b-c-hospital-construction-starting-in-2025 ; https://helpstpauls.com/why-give/new-st-pauls-hospital/ ; https://www.cbc.ca/news/canada/british-columbia/new-dawson-creek-hospital-almost-complete-9.7168843 ; https://www.cbc.ca/news/canada/montreal/quebec-hospital-projects-doctors-staff-react-9.7138974 — JOC / St Paul's / CBC — 2026 — BC $6.4B, St Paul's, Dawson Creek $590M, QC $2.3B/10yr
[tourism a] https://news.gov.bc.ca/releases/2026TACS0022-000545 ; https://www.canada.ca/en/innovation-science-economic-development/news/2026/04/minister-valdez-announces-federal-funding-to-attract-major-international-events-and-boost-canadian-tourism.html ; https://sensomagazine.ca/en/entertainment/art/canada-investment-corleck-building-toronto/ — BC Gov / ISED / Senso — 2026 — BC Place FIFA, $1B visitor spending, ICAF 116 events, Corleck $726K
[tourism b] https://www.travelandtourworld.com/news/article/canada-shows-record-breaking-growth-in-its-hotel-construction-pipeline-in-q1-2026-highlighting-promising-future-for-luxury-tourism-and-hospitality-development-nationwide/ — Travel And Tour World — 2026 Q1 — 331 hotel projects / 45,401 rooms
[residential a] https://storeys.com/spring-2026-supply-report-cmhc/ ; https://www.rbc.com/en/economics/canadian-analysis/canadian-housing/special-housing-reports/navigating-torontos-frozen-pre-construction-condo-market/ ; https://canada.constructconnect.com/dcn/news/projects/2026/05/indications-of-massive-welland-residential-development-moving-forward-without-requested-grant ; https://pegasuslending.com/blog/pre-construction-condos-canada-2026/ — Storeys/CMHC / RBC / DCN / Pegasus — 2026 — starts 259,000, condo -15-18%, Bill C-4 GST rebate, Welland
[commercial a] https://storeys.com/lenders-canada-commercial-real-estate/ ; https://www.cbre.ca/insights/articles/6-canadian-commercial-real-estate-projects-to-watch-for-in-2026 — Storeys / CBRE — 2026 — office-loan budgets surged, mixed-use pipeline
[labour a] https://www150.statcan.gc.ca/n1/daily-quotidien/260508/dq260508a-eng.htm ; https://economics.td.com/ca-employment — StatCan LFS April 2026 / TD — 2026-05-08 — -18,000 jobs, 6.9% unemployment, sector gains
