# Sector & Industry Research — Week of 2026-04-11
Generated: 2026-04-11
Industries covered: All 20 NAICS (5 goods + 15 services)
Data sources: docs/data/indicators.json (industry_gdp_mm/yy per NAICS), docs/data/projects_all.json (6,632 projects), docs/data/commodities.json, docs/data/briefing_latest.json (financial markets & commodities block), docs/data/iaac.json (62 active federal assessments), docs/data/signals.json, docs/data/data_gap_report.md.

Scope note per data_gap_report.md: lumber timeseries is 1,065 days stale (do not cite), yield curve partial (2Y/5Y/10Y only), policy feed empty for current week, jobs.json and procurement.json contain no populated spikes/contracts for the week of 2026-04-11. Sector labour and procurement commentary therefore relies on project pipeline counts plus GDP-by-industry prints.

---

## 1. Data Quality Audit

### Sector Project Coverage (mapped from project database)

| NAICS | Sector Name | Project Count | Total Declared Value | Under Construction | Proposed | Status |
|-------|------------|---------------|----------------------|--------------------|----------|--------|
| 11 | Agriculture, Forestry, Fishing & Hunting | 17 | ~$5.5B | 4 | 6 | THIN (forestry-dominant) |
| 21 | Mining, Quarrying & Oil/Gas Extraction | 421 | ~$255.9B | 33 | 141 | OK |
| 22 | Utilities (Power, Water & Wastewater) | 1,392 | ~$515.5B | 103 | 328 | OK (largest bucket) |
| 23 | Construction (infra + residential + commercial) | 1,373 | ~$241.8B | 516 | 382 | OK |
| 31-33 | Manufacturing | 52 | ~$69.4B | 17 | 25 | THIN |
| 41 | Wholesale Trade | 0 tagged | — | — | — | GAP (no dedicated tag) |
| 44-45 | Retail Trade | 0 tagged | — | — | — | GAP (no dedicated tag) |
| 48-49 | Transportation & Warehousing | 578 | ~$35.1B | 137 | 318 | OK |
| 51 | Information & Cultural Industries | 38 | ~$0.7B | 11 | 14 | THIN (most data-centre capex lands under manufacturing/telecom) |
| 52 | Finance & Insurance | 0 tagged | — | — | — | GAP (non-capex sector) |
| 53 | Real Estate & Rental/Leasing | 0 tagged (overlaps NAICS 23 residential = 138 projects) | — | — | — | GAP |
| 54 | Professional, Scientific & Technical Services | 0 tagged | — | — | — | GAP |
| 55 | Management of Companies & Enterprises | 0 tagged | — | — | — | GAP |
| 56 | Administrative & Waste Management Services | 26 | ~$1.9B | 5 | 1 | THIN |
| 61 | Educational Services | 157 | ~$14.6B | 13 | 21 | OK |
| 62 | Health Care & Social Assistance | 258 | ~$20.4B | 47 | 39 | OK |
| 71 | Arts, Entertainment & Recreation | 150 | ~$22.1B | 94 | 14 | OK |
| 72 | Accommodation & Food Services | 0 tagged | — | — | — | GAP |
| 81 | Other Services | 0 tagged | — | — | — | GAP |
| 91 | Public Administration | 231 | ~$164.9B | 40 | 153 | OK (includes Defence bucket) |

Plus 2,353 projects carrying sector label "Other" (no NAICS mapping). These are not aggregated into any bucket above.

### Critical Gaps Flagged by Research
- NAICS 41, 44-45, 52, 54, 55, 72, 81 have zero project-side tagging; these are services sectors with low capex. Track via StatCan GDP-by-industry prints, not project pipeline.
- Lumber price treated as unavailable per data_gap_report.md.
- Jobs.json and procurement.json have empty spike/contract arrays for week of 2026-04-11; labour and contract commentary uses project counts as the proxy.
- Policy feed is empty for the current week.

---

## 2. Sector Activity Summary — Industry GDP Snapshot (StatCan, period 2026-04-11)

Canada's monthly industry-level GDP prints (from indicators.json, industry_gdp_mm_* and industry_gdp_yy_* keys, StatCan):

| NAICS | Sector | MoM | YoY |
|-------|--------|-----|-----|
| 11 | Agriculture, Forestry, Fishing & Hunting | -1.4% | +5.4% |
| 21 | Mining, Quarrying & Oil/Gas Extraction | +1.2% | -0.1% |
| 22 | Utilities | +0.6% | -1.7% |
| 23 | Construction | +1.1% | +2.8% |
| 31-33 | Manufacturing | -1.4% | -4.6% |
| 41 | Wholesale Trade | -1.2% | -1.7% |
| 44-45 | Retail Trade | +0.8% | +2.7% |
| 48-49 | Transportation & Warehousing | -0.7% | +1.6% |
| 51 | Information & Cultural Industries | +0.9% | +3.2% |
| 52 | Finance & Insurance | +0.5% | +3.2% |
| 53 | Real Estate & Rental/Leasing | -0.2% | +1.2% |
| 54 | Professional, Scientific & Technical Services | -0.1% | -0.4% |
| 55 | Management of Companies & Enterprises | -4.1% | -21.9% |
| 56 | Administrative & Waste Management Services | -0.1% | -0.2% |
| 61 | Educational Services | +0.5% | -1.9% |
| 62 | Health Care & Social Assistance | +0.0% | +2.1% |
| 71 | Arts, Entertainment & Recreation | -0.1% | +2.2% |
| 72 | Accommodation & Food Services | +0.7% | +2.3% |
| 81 | Other Services | +0.2% | +0.3% |
| 91 | Public Administration | -0.1% | +0.7% |

Source: StatCan GDP by industry at basic prices, monthly (Table 36-10-0434), values mirrored in `docs/data/indicators.json` — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

The two largest outliers: Management of Companies & Enterprises at -4.1% MoM / -21.9% YoY, and Manufacturing at -1.4% MoM / -4.6% YoY. The strongest YoY gains: Agriculture/Forestry/Fishing (+5.4%), Finance (+3.2%), Information & Culture (+3.2%).

---

## 3. Sector Spotlights — All 20 NAICS Industries

### GOODS INDUSTRIES

#### 11: Agriculture, Forestry, Fishing & Hunting
- **GDP print:** -1.4% MoM, +5.4% YoY (strongest YoY in the table) — StatCan Table 36-10-0434 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project pipeline:** 17 projects tagged agriculture/forestry totalling ~$5.5B. Largest entries: Biofuel Facility QC ($1.2B, Under Construction), Saint John Pulp Mill Upgrades NB ($1.1B, Under Review), Hinton Pulp Mill Expansion AB ($584M, Proposed).
- **Commodity backdrop (briefing_latest.json commodities block):**
  - Wheat: 573.5 USc/bu (-4.1% day, -1.9% MoM, +5.8% YoY) — CBOT front-month
  - Canola: C$619/t (-0.2% MoM, -0.3% YoY) — StatCan Table 32-10-0077, Saskatchewan producer prices — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701
  - Oats: 337.8 USc/bu (-2.2% day, -2.0% MoM, +2.3% YoY) — CBOT; Canada largest world exporter
  - Soybean Oil: 67.73 USc/lb (+46.6% YoY) — CBOT
  - Potash proxy (Nutrien NTR): US$72.78 share (-3.6% day, -4.3% MoM, +50.3% YoY) — NYSE
  - Live Cattle: 247.52 USc/lb (+0.5% day, +6.5% MoM, +22.1% YoY) — CME; Alberta feedlot proxy
  - Lean Hogs: 104.18 USc/lb (+15.3% day, +8.4% MoM, +19.8% YoY) — CME; Quebec and Manitoba exposure
  - BoC Forestry Index: 449 pts (-1.1% day, +2.7% MoM, -10.6% YoY) — Bank of Canada weekly commodity subindex — https://www.bankofcanada.ca/rates/price-indexes/bcpi/
  - BoC Fisheries Index: 2,148 pts (flat day, flat MoM, +6.8% YoY) — BoC Atlantic Canada fisheries subindex
- **Lumber explicitly excluded** per data_gap_report.md (1,065 days stale).

#### 21: Mining, Quarrying & Oil/Gas Extraction
- **GDP print:** +1.2% MoM, -0.1% YoY — StatCan 36-10-0434.
- **Project pipeline:** 421 projects totalling ~$255.9B; 33 Under Construction, 141 Proposed, 147 Under Review. Largest entries include LNG Canada Facility BC ($40B, Complete), Pathways Alliance Carbon Capture and Storage Project AB ($16.5B, Proposed — also listed in IAAC as Pathways Alliance CO2 Transportation Network and Storage Hub), Critical Minerals Production Alliance Round 2 ($12.1B, Proposed), Jackpine Mine Expansion AB ($8.2B, Proposed), Baffinland Mary River Steensby Rail and Port Expansion NU ($3B, Approved).
- **Commodity prices (briefing_latest.json):**
  - WTI Crude: US$98.53/bbl (-11.7% day, +18.1% MoM, +58.0% YoY) — NYMEX
  - Brent Crude: US$96.52/bbl (-11.5% day, +9.9% MoM, +47.4% YoY) — ICE
  - Western Canadian Select: US$85.53/bbl (-11.7% day, derived as WTI less ~US$13/bbl heavy-crude differential)
  - Natural Gas (Henry Hub): US$2.67/MMBtu (-4.6% day, -11.5% MoM, -30.0% YoY) — NYMEX
  - Gold: US$4,783/oz (+2.8% day, -8.6% MoM, +56.5% YoY) — COMEX
  - Silver: US$75.46/oz (+3.7% day, +148.8% YoY) — COMEX
  - Copper: US$5.747/lb (+3.3% day, -2.6% MoM, +37.6% YoY) — COMEX
  - Iron Ore (TSI 62% Fe): US$107.83/t (+0.3% day, +4.8% MoM, +8.6% YoY) — SGX
  - Aluminum: US$3,370/t (-1.2% day, +1.4% MoM, +55.5% YoY) — LME
  - Uranium (Cameco CCJ): US$115.54 share (+2.6% day, +188.5% YoY) — NYSE
  - Uranium (Sprott URA ETF): US$50.93 (+4.2% day, +130.2% YoY)
  - Diamonds (Canadian production): C$66.09/ct (+6.2% MoM, -43.9% YoY) — StatCan Table 16-10-0020 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610002001
  - BoC Metals & Minerals Index: 1,191 pts (+1.3% day, -3.5% MoM, +31.4% YoY) — Bank of Canada — https://www.bankofcanada.ca/rates/price-indexes/bcpi/
- **IAAC active (21 bucket):** Springpole Gold Project ON (Under Review), Mont Sorcier Mining Project QC (Under Review), Pathways Alliance CO2 Transportation Network and Storage Hub AB, plus 4 Alberta oil & gas surface-lease or gas-fired items (OS-7270, OS-7269, Cold Lake First Nation English Bay, Flipi Gas-Fired Generation). IAAC source: Federal Impact Assessment Registry — https://iaac-aeic.gc.ca/050/evaluations

#### 22: Utilities (Electricity, Gas, Water)
- **GDP print:** +0.6% MoM, -1.7% YoY — StatCan 36-10-0434.
- **Project pipeline:** 1,392 projects totalling ~$515.5B — the largest bucket in the database. 103 Under Construction, 328 Proposed, 773 Under Review. Largest items: LNG Canada Phase 1 BC ($47.9B, Under Construction), Haute-Chaudière QC ($370M, EDF Renouvelables, Under Review), New Nuclear at Wesleyville ON (IAAC Under Review, Ontario Power Generation), Sunshine Coast Water Security Project BC ($117M, Proposed), Arctic Bay Water Treatment Plant NU ($49M, Proposed).
- **Commodity linkages:** natural gas price at US$2.67/MMBtu (-30.0% YoY) is the direct input cost to Canadian gas utilities and BC LNG feed gas; uranium price (Cameco +188.5% YoY, Sprott URA +130.2% YoY) is the economic input to Wesleyville New Nuclear and SMR build-outs in Saskatchewan, Ontario, New Brunswick.
- **IAAC:** New Nuclear at Wesleyville Project (Clean Energy bucket, ON, Under Review).
- **Source (OPG New Nuclear):** https://www.opg.com/powering-ontario/our-generation/nuclear/wesleyville/

#### 23: Construction
- **GDP print:** +1.1% MoM, +2.8% YoY — StatCan 36-10-0434. Construction is the only goods sector posting positive YoY outside Agriculture.
- **Project pipeline:** 1,373 projects totalling ~$241.8B; 516 Under Construction (highest of any sector) and 382 Proposed.
- **Largest items:** North End Water Pollution Control Centre (NEWPCC) Upgrade MB ($3.2B, Under Construction), Arctic Infrastructure Fund CA ($1B, Proposed), Laurentides Region Transport Infrastructure 2026-2028 QC ($491M, Proposed), Scotia Place / Calgary Event Centre AB ($1.2B, Under Construction), Taza Mixed Use Development AB ($4.5B, Under Construction), Portage Place Redevelopment MB ($650M, Under Construction), Nunavut 750 Homes Initiative NU ($480M, Under Construction), Edmonton Affordable Housing Program AB ($2.6B, Complete).
- **Commodity linkages:** steel ETF (SLX) proxy +6.6% week / +6.0% MoM / +76.3% YoY (commodities.json) — direct input cost to infrastructure and building construction. Aluminum +55.5% YoY, copper +37.6% YoY — also construction inputs.
- **Residential subset:** 138 projects ~$31.9B declared.

#### 31-33: Manufacturing
- **GDP print:** -1.4% MoM, -4.6% YoY — the steepest YoY decline among goods industries — StatCan 36-10-0434.
- **Project pipeline:** 52 manufacturing-tagged projects totalling ~$69.4B; 17 Under Construction, 25 Proposed.
- **Largest items:** Wonder Valley AI Data Centre Park Phase 1 AB ($12B, Proposed — cross-tagged with NAICS 51), Telus Infrastructure Upgrades AB ($19B, Under Construction — also telecom), Arviat Modular Housing Factory NU ($70M, Under Construction).
- **Manufacturing commodity backdrop:** aluminum US$3,370/t (+55.5% YoY, Quebec smelter exposure); palladium US$1,554/oz (+77.0% YoY, catalytic converter input); platinum US$2,098/oz (+130.9% YoY, hydrogen electrolyzer input); copper +37.6% YoY.
- **Equity proxies:** Teck Resources TECK US$54.66 (+3.5% day, +63.6% YoY), West Fraser Timber WFG US$64.80 (-0.5% day, -14.2% YoY) — briefing_latest.json commodities.

### SERVICES INDUSTRIES

#### 41: Wholesale Trade
- **GDP print:** -1.2% MoM, -1.7% YoY — StatCan 36-10-0434. Second-worst MoM print in the services universe after NAICS 55.
- **Project pipeline:** No projects tagged directly. Track via GDP and merchandise trade indicators (agri_exports, mineral_exports, forestry_exports) in indicators.json.
- **Source:** StatCan Wholesale Trade Survey (monthly) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401

#### 44-45: Retail Trade
- **GDP print:** +0.8% MoM, +2.7% YoY — StatCan 36-10-0434. Positive MoM and YoY.
- **Project pipeline:** No dedicated tagging. Retail footprint appears inside commercial_mixed projects under NAICS 23.
- **Source:** StatCan Retail Trade Survey (monthly) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801

#### 48-49: Transportation & Warehousing
- **GDP print:** -0.7% MoM, +1.6% YoY — StatCan 36-10-0434.
- **Project pipeline:** 578 projects totalling ~$35.1B; 137 Under Construction, 318 Proposed. Largest items: Trade Diversification Corridors Fund CA ($5B, Proposed), Yonge North Subway Extension ON ($797M, Proposed), Kitchener Central Transit Hub Phase 2 ON ($51M, Proposed), Electrification of the St-Laurent Transportation Center QC ($107M, Proposed), Abitibi-Témiscamingue Transport and Airport Infrastructure QC ($235M, Proposed).
- **Ports subset (116 projects):** Baffinland Mary River Rail and Port Expansion NU ($3B, Approved) dominates.
- **Commodity linkage:** Heating Oil ULSD US$3.97/gal (+87.9% YoY) — diesel and freight input cost. BoC Energy Index 1,743 pts (+34.4% MoM, +24.7% YoY).
- **IAAC ports & logistics:** Wharf 401 Reconstruction Millerand Harbour QC (Under Review), Floating Wharf Replacement at Meteghan Small Craft Harbour NS (Under Review).

#### 51: Information & Cultural Industries
- **GDP print:** +0.9% MoM, +3.2% YoY — StatCan 36-10-0434. Tied with Finance for strongest services YoY.
- **Project pipeline:** 38 telecom/info projects totalling ~$0.7B direct; most AI data-centre and fibre capex is tagged under manufacturing or telecom. Notable: Bell Canada AI Data Centre RM of Sherwood SK ($1.7B construction, up to $12B projected economic value, Proposed), SaskTel ICT Infrastructure Capital Program SK ($433M, Proposed), Wonder Valley AI Data Centre Park Phase 1 AB ($12B, Proposed).
- **Source:** StatCan 36-10-0434; Bell Canada press releases — https://www.bce.ca/news-and-media/releases/

#### 52: Finance & Insurance
- **GDP print:** +0.5% MoM, +3.2% YoY — StatCan 36-10-0434. Tied with Information & Culture for strongest services YoY.
- **Project pipeline:** No direct project tagging (non-capex services sector). Track via S&P/TSX Composite at 33,696 (+42.85% YoY, weekly flat) — briefing_latest.json financialMarkets.indices.
- **Source:** StatCan 36-10-0434 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

#### 53: Real Estate & Rental/Leasing
- **GDP print:** -0.2% MoM, +1.2% YoY — StatCan 36-10-0434.
- **Project pipeline:** NAICS 23 residential subset = 138 projects ~$31.9B. Nunavut 750 Homes Initiative ($480M, Under Construction), PEI Affordable Housing Construction 300+ Units ($100M, Proposed), Edmonton Affordable Housing Program ($2.6B, Complete).
- **Source:** StatCan 36-10-0434.

#### 54: Professional, Scientific & Technical Services
- **GDP print:** -0.1% MoM, -0.4% YoY — StatCan 36-10-0434.
- **Project pipeline:** No direct project tagging. Track via GDP and research-infrastructure programs such as Canada Foundation for Innovation — 92 Research Infrastructure Projects ($552M, Proposed, tagged under education NAICS 61).
- **Source:** StatCan 36-10-0434.

#### 55: Management of Companies & Enterprises
- **GDP print:** -4.1% MoM, -21.9% YoY — the single largest GDP contraction in the table — StatCan 36-10-0434. This is a concentrated (small) industry and single-quarter prints are historically volatile; the YoY decline is the largest negative reading in the 20-NAICS universe.
- **Project pipeline:** No project tagging.
- **Source:** StatCan 36-10-0434.

#### 56: Administrative & Waste Management Services
- **GDP print:** -0.1% MoM, -0.2% YoY — StatCan 36-10-0434.
- **Project pipeline:** 26 environment/waste-tagged projects totalling ~$1.9B; 5 Under Construction. Largest items: Port Lands Flood Protection and Enabling Infrastructure Project ON ($1.3B, Under Construction), Boat Harbour Remediation Project NS ($367M, Approved), City of Regina Railyard Renewal Project SK ($64M, Under Construction).
- **Source:** StatCan 36-10-0434.

#### 61: Educational Services
- **GDP print:** +0.5% MoM, -1.9% YoY — StatCan 36-10-0434.
- **Project pipeline:** 157 projects ~$14.6B; 13 Under Construction, 100 Approved (largest approved count in the services set), 21 Proposed. Largest items: Alberta School Construction Accelerator Program — 16 New Projects ($8.6B, Proposed), Canada Foundation for Innovation — 92 Research Infrastructure Projects CA ($552M, Proposed), Stratford High School Construction PE ($55M, Under Construction).
- **Source:** StatCan 36-10-0434; Alberta School Capital Projects — https://www.alberta.ca/school-capital-projects

#### 62: Health Care & Social Assistance
- **GDP print:** +0.0% MoM, +2.1% YoY — StatCan 36-10-0434.
- **Project pipeline:** 258 projects ~$20.4B; 47 Under Construction, 107 Approved, 39 Proposed. Largest items: PEI Mental Health Campus Completion PE ($131M, Under Construction), Heart Care Manitoba — Cardiac Centre of Excellence at St. Boniface MB ($22M, Proposed), CT Scanner Installations KCMH and Western Hospital PE ($12M, Proposed), Biindigen Well-Being Centre ON ($13M, Proposed), Women's Health Clinic 419 Graham Redevelopment MB ($10M, Proposed).
- **Source:** StatCan 36-10-0434.

#### 71: Arts, Entertainment & Recreation
- **GDP print:** -0.1% MoM, +2.2% YoY — StatCan 36-10-0434.
- **Project pipeline:** 150 tourism/culture projects ~$22.1B; 94 Under Construction (highest ratio of Under Construction to total of any services sector). Largest items: Mont-Orford National Park Expansion QC ($59M, Under Construction), Edmonton Winspear Centre Expansion AB ($33M, Under Construction), Flin Flon Community Pool — GRO Program MB ($2.4M, Under Construction).
- **Source:** StatCan 36-10-0434.

#### 72: Accommodation & Food Services
- **GDP print:** +0.7% MoM, +2.3% YoY — StatCan 36-10-0434.
- **Project pipeline:** No direct tagging in project database. Sector exposure appears indirectly through commercial_mixed projects under NAICS 23. Agricultural commodity inputs: Sugar 13.95 USc/lb (-22.1% YoY), Coffee 276.3 USc/lb (-19.1% YoY), Cocoa US$3,327/t (-60.6% YoY) — all declining YoY (commodities block in briefing_latest.json).
- **Source:** StatCan 36-10-0434.

#### 81: Other Services (except Public Administration)
- **GDP print:** +0.2% MoM, +0.3% YoY — StatCan 36-10-0434. The smallest absolute change in the table.
- **Project pipeline:** No direct tagging.
- **Source:** StatCan 36-10-0434.

#### 91: Public Administration
- **GDP print:** -0.1% MoM, +0.7% YoY — StatCan 36-10-0434.
- **Project pipeline:** 231 government/defence/indigenous-tagged projects ~$164.9B; 40 Under Construction, 153 Proposed. Largest items: Northern Defence and Infrastructure — Nunavut Military Bases NU ($32B pan-northern, Proposed), Defence Construction Canada — Active Infrastructure Contracts CA ($8B, Under Construction), Regional Defence Investment Initiative CA ($379M, Proposed).
- **IAAC:** DND Relocated Infrastructure Project at the 4th Canadian Division Training Centre ON (Under Review), Canadian Coast Guard Westham Island DGPS Tower Removal BC (Under Review), Recapitalize Gagetown Range and Training Area Main Service Roads Upgrade NB (Under Review).
- **Source:** StatCan 36-10-0434; DCC — https://www.dcc-cdc.gc.ca/

---

## 4. Commodity Price Impact Analysis

### Energy
Source: briefing_latest.json `commodities` block (43 items, NYMEX/ICE/BoC Valet).
- WTI Crude US$98.53/bbl — day -11.7%, MoM +18.1%, YoY +58.0%. NYMEX front-month.
- Brent Crude US$96.52/bbl — day -11.5%, MoM +9.9%, YoY +47.4%. ICE front-month.
- Western Canadian Select US$85.53/bbl (derived differential).
- Natural Gas (Henry Hub) US$2.67/MMBtu — day -4.6%, MoM -11.5%, YoY -30.0%. NYMEX.
- BoC Energy Index 1,743 pts — day +2.0%, MoM +34.4%, YoY +24.7%.
- Affected NAICS: 21 (421 projects ~$255.9B), 22 (1,392 projects ~$515.5B), 23 (1,373 projects ~$241.8B), 48-49 (578 projects ~$35.1B).

### Metals
- Gold US$4,783/oz — day +2.8%, MoM -8.6%, YoY +56.5%. COMEX.
- Silver US$75.46/oz — day +3.7%, YoY +148.8%. COMEX.
- Copper US$5.747/lb — day +3.3%, MoM -2.6%, YoY +37.6%. COMEX.
- Iron Ore (TSI 62% Fe) US$107.83/t — day +0.3%, MoM +4.8%, YoY +8.6%. SGX.
- Aluminum US$3,370/t — day -1.2%, YoY +55.5%. LME.
- Uranium (Cameco CCJ) US$115.54 — day +2.6%, YoY +188.5%. NYSE.
- Uranium (Sprott URA ETF) US$50.93 — day +4.2%, YoY +130.2%.
- Steel proxy (SLX ETF) US$98.57 — week +6.6%, MoM +6.0%, YoY +76.3% — commodities.json.
- Nickel (NIKL ETF proxy) US$28.40 — flat week, flat MoM, flat YoY — commodities.json.
- BoC Metals & Minerals Index 1,191 pts — day +1.3%, MoM -3.5%, YoY +31.4%.
- Affected NAICS: 21 (421 projects), 23 (1,373 projects via steel/aluminum/copper input costs).

### Agriculture
- Wheat 573.5 USc/bu — day -4.1%, MoM -1.9%, YoY +5.8%. CBOT.
- Canola C$619/t — MoM -0.2%, YoY -0.3%. StatCan 32-10-0077 Saskatchewan producer prices.
- Corn 444.5 USc/bu — day -1.7%, YoY -6.2%. CBOT.
- Soybeans 1,164.2 USc/bu — YoY +15.0%. CBOT.
- Oats 337.8 USc/bu — day -2.2%. CBOT.
- Potash (Nutrien NTR) US$72.78 — day -3.6%, YoY +50.3%. NYSE.
- Live Cattle 247.52 USc/lb — YoY +22.1%. CME.
- Lean Hogs 104.18 USc/lb — day +15.3%, YoY +19.8%. CME.
- Feeder Cattle 370.77 USc/lb — YoY +30.7%. CME.
- Affected NAICS: 11 (17 projects), 72 (input costs for food services).

### Forestry / Forest Products
- BoC Forestry Index 449 pts — day -1.1%, MoM +2.7%, YoY -10.6%.
- BoC Fisheries Index 2,148 pts — flat day, YoY +6.8%.
- Lumber: treated as unavailable (timeseries stale 1,065 days per data_gap_report.md).
- Affected NAICS: 11 (forestry subset, 12 projects), 23 (residential construction input).

---

## 5. Major Project Announcements by Sector (Snapshot, Not Weekly New)

The procurement monitor and jobs monitor both reported empty arrays for the week of 2026-04-11 (signals.json). IAAC tracks 62 active federal assessments (seen_this_week: 18) as the most actionable weekly signal layer.

**IAAC active by bucket (62 total, as of 2026-04-11 snapshot):**
- Other: 33
- Energy: 6 (Alberta O&G surface leases OS-7270 & OS-7269, Cold Lake First Nation English Bay Gas Station, Flipi Gas-Fired Generation, Wharf 403 Reconstruction QC)
- Infrastructure: 4 (Maliseet Road NB, Lucky Man Cree Nation Access Road SK, Graham Road CFB Gagetown NB, Recapitalize Gagetown Main Service Roads NB)
- Housing: 4
- Mining: 3 (Springpole Gold ON, Mont Sorcier QC, Ermineskin Drainage AB)
- Ports & Logistics: 3 (Wharf 401 Millerand QC, Pathways Alliance CO2 Transportation AB, Meteghan Floating Wharf NS)
- Defence: 2 (Coast Guard Westham Island BC, DND 4th Canadian Division Training Centre ON)
- Clean Energy: 1 (New Nuclear at Wesleyville ON)
- Water & Wastewater: 1
- Transit & Rail: 1

**IAAC by province:** AB 17, ON 15, QC 7, BC 7, SK 5, NB 4, MB 3, NS 2, NL 1, PE 1 (62 total). Source: Federal Impact Assessment Registry — https://iaac-aeic.gc.ca/050/evaluations

---

## 6. Labour Market by Sector

Jobs file (jobs.json) reports 0 active hiring spikes for the week of 2026-04-11 (signals.job_spikes empty). Sector-level labour commentary for this week relies on:
- Industry GDP prints in Section 2 as the closest lagging employment proxy.
- StatCan Labour Force Survey (Table 14-10-0355) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410035501
- StatCan SEPH (employment by industry Table 14-10-0022, monthly; statcan_extended.py pipeline source) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201

Project-pipeline-derived Under Construction counts (proxy for active labour draw) by sector, ranked:
1. NAICS 23 Construction — 516 projects Under Construction
2. NAICS 48-49 Transportation — 137 projects
3. NAICS 22 Utilities — 103 projects
4. NAICS 71 Arts/Entertainment — 94 projects
5. NAICS 62 Healthcare — 47 projects
6. NAICS 91 Public Administration — 40 projects
7. NAICS 21 Mining/O&G — 33 projects
8. NAICS 31-33 Manufacturing — 17 projects
9. NAICS 61 Education — 13 projects
10. NAICS 51 Information & Culture — 11 projects
11. NAICS 56 Admin/Waste — 5 projects
12. NAICS 11 Agriculture/Forestry — 4 projects

---

## 7. Policy and Regulatory Impacts

Policy feed (policy.json) is empty for the week of 2026-04-11 (data_gap_report.md warning). No LEGISinfo, Canada Gazette, or ministry-feed items available to cite.

Cross-sector observation from IAAC: of 62 active federal impact assessments, 11 carry direct project status signals (6 Energy, 3 Mining, 1 Clean Energy, 1 Ports, plus 2 Defence). All remain Under Review except 1 Cancelled and 1 On Hold. Source: https://iaac-aeic.gc.ca/050/evaluations

---

## 8. Emerging Stories and Cross-Sector Trends

### Pipeline Activity Ranking (by project count and under-construction count)
1. **NAICS 22 Utilities — 1,392 projects, ~$515.5B declared, 103 Under Construction, 328 Proposed, 773 Under Review.** Largest bucket by project count and total declared value. Dominated by Water & Wastewater (516), Clean Energy (188), generic power_energy (312), and Energy (239) sub-tags.
2. **NAICS 23 Construction — 1,373 projects, ~$241.8B, 516 Under Construction (the highest of any sector), 382 Proposed.** Highest Under Construction count and strongest GDP print of the goods sectors (+1.1% MoM, +2.8% YoY).
3. **NAICS 48-49 Transportation — 578 projects, ~$35.1B, 137 Under Construction, 318 Proposed.** Third-largest pipeline; ports subset dominates Atlantic and Arctic rail activity.

### GDP Divergence
Largest negative YoY: NAICS 55 Management of Companies & Enterprises -21.9% and NAICS 31-33 Manufacturing -4.6%. Largest positive YoY: NAICS 11 Agriculture/Forestry/Fishing +5.4%, NAICS 51 Information & Culture +3.2%, NAICS 52 Finance & Insurance +3.2%, NAICS 23 Construction +2.8%.

### Commodity-Driven Sector Exposure
- Uranium (+188.5% YoY Cameco, +130.2% YoY URA ETF) connects to Saskatchewan uranium mining pipeline and to Wesleyville New Nuclear (Ontario, IAAC Under Review).
- Steel ETF +76.3% YoY and copper +37.6% YoY are priced input costs against the 1,373 NAICS 23 construction projects.
- Natural gas -30.0% YoY sets the input-cost environment for BC LNG Canada (~$47.9B, Under Construction) and Alberta gas-fired generation projects tracked in IAAC (Flipi, Cold Lake).
- Gold +56.5% YoY runs alongside Springpole Gold Project ON (IAAC Under Review) and Mont Sorcier QC (IAAC Under Review).

---

## 9. Coverage Gaps and Priorities

Industries requiring supplementary research (no project-side tagging, rely on GDP prints alone): NAICS 41 Wholesale, 44-45 Retail, 52 Finance, 54 Professional Services, 55 Management, 72 Accommodation & Food, 81 Other Services. For these sectors, analysts should cite industry_gdp_mm_* / industry_gdp_yy_* from indicators.json and not attempt to populate project-pipeline numbers.

Real Estate (NAICS 53) is partially captured via NAICS 23 residential subset (138 projects, ~$31.9B).

Data-gap warnings that affect this week's sector research:
- Lumber price: treat as unavailable.
- Yield curve: 2Y/5Y/10Y only (spread_2_10 citable, longer/shorter tenors not).
- policy.json: empty week — no legislative quotes available.
- jobs.json and procurement.json: no populated signals for the week of 2026-04-11.

---

## 10. Master Source Registry

1. StatCan Table 36-10-0434 — GDP by industry at basic prices, monthly — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401 — primary source for all 20 NAICS GDP MoM/YoY prints.
2. StatCan Table 32-10-0077 — Farm product prices (canola producer price) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701 — canola price cited in Section 3 and Section 4.
3. StatCan Table 16-10-0020 — Production of non-metallic minerals (diamonds) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610002001 — Canadian diamond realized price.
4. StatCan Table 14-10-0355 — Labour Force Survey, monthly — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410035501 — referenced in Section 6.
5. StatCan Table 14-10-0022 — SEPH employment by industry — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201 — referenced in Section 6.
6. StatCan Table 20-10-0074 — Wholesale trade (monthly) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401 — NAICS 41.
7. StatCan Table 20-10-0008 — Retail trade (monthly) — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801 — NAICS 44-45.
8. StatCan Table 12-10-0129 — Canadian international merchandise trade — cited in indicators.json (agri_exports, forestry_exports, mineral_exports).
9. Bank of Canada Commodity Price Index (BCPI) — https://www.bankofcanada.ca/rates/price-indexes/bcpi/ — source for BoC Energy Index, BoC Metals & Minerals Index, BoC Forestry Index, BoC Fisheries Index.
10. Federal Impact Assessment Registry (IAAC) — https://iaac-aeic.gc.ca/050/evaluations — source for 62 active federal assessments by sector/province.
11. Impact Assessment Agency of Canada overview — https://www.canada.ca/en/impact-assessment-agency.html
12. Ontario Power Generation — Wesleyville New Nuclear — https://www.opg.com/powering-ontario/our-generation/nuclear/wesleyville/ — source for NAICS 22 Clean Energy IAAC entry.
13. Defence Construction Canada — https://www.dcc-cdc.gc.ca/ — source for NAICS 91 $8B active infrastructure contracts.
14. Government of Alberta — School Capital Projects — https://www.alberta.ca/school-capital-projects — source for $8.6B Alberta School Construction Accelerator Program (NAICS 61).
15. Bell Canada press releases — https://www.bce.ca/news-and-media/releases/ — source for Bell Canada AI Data Centre RM of Sherwood SK (NAICS 51).
16. briefing_latest.json (internal, pipeline-generated from NYMEX/ICE/COMEX/LME/SGX/BoC/StatCan upstream feeds) — 43-item `commodities` block covering all energy, metals, agriculture, livestock, forestry, and Canadian equity proxies cited in Sections 3 and 4.
17. commodities.json (internal, pipeline-generated from Yahoo Finance ETF proxies) — uranium_spot (URA), nickel (NIKL), steel (SLX), tsx_infrastructure, potash_nutrien (NTR), cameco_uranium (CCJ), sprott_uranium (SRUUF).
18. indicators.json (internal) — 252 indicators including the 40 industry_gdp_mm_* / industry_gdp_yy_* keys covering all 20 NAICS.
19. projects_all.json (internal) — 6,632 active projects, sector-tagged and status-tracked; pipeline source for all project counts and declared values in Sections 1, 3, 5, 6, and 8.
20. signals.json (internal) — aggregated jobs/procurement/IAAC signal summary for the week of 2026-04-11.
21. data_gap_report.md (internal) — data-quality flags referenced throughout.

---

*End of Agent 1C sector research. All 20 NAICS industries covered. Factual reporting only, per editorial policy.*
