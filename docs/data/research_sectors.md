# Sector & Industry Research — Week of 2026-06-15
Generated: 2026-06-15
Industries covered: All 20 NAICS (5 goods + 15 services)
Cold start (Obsidian running-threads unavailable). Pipeline inputs read: industry_gdp.json, projects_all.json (7,103 rows), commodities.json, jobs.json (2026-06-15 weekly snapshot, 0 hiring spikes flagged), iaac.json (162 federal-EA projects), policy.json (8 weeks), indicators.json, data_gap_report.md (overall freshness: B).

---

## 1. Data Quality Audit

### Sector Project Coverage (projects_all.json, 7,103 rows; parsed_value used for totals)

| NAICS | Sector | Project Count | Total Value | Latest Tracked | Status |
|---|---|---|---|---|---|
| 11 | Agriculture (incl. Forestry pipeline tags) | 464 (Agri) + 269 (forestry) = 733 | Agri $3.5B + Forestry $4.7B = $8.2B priced | 2026-06-15 | OK — value coverage thin (only 2/464 agri rows priced) |
| 21 | Mining, Quarrying & Oil/Gas | 651 mining + 127 oil_gas = 778 | $184.8B mining + $63.5B oil_gas = $248.3B | 2026-06-15 | OK |
| 22 | Utilities (mapped through power_energy in pipeline) | 936 power_energy | $614.3B | 2026-06-10 | OK — largest tracked sector value |
| 23 | Construction (mapped through infrastructure/residential/commercial_mixed) | 1,637 + 271 + 97 = 2,005 | $223.9B + $36.2B + $28.6B = $288.7B | 2026-06-15 | OK |
| 31-33 | Manufacturing | 362 | $85.4B | 2026-06-12 | OK |
| 41 | Wholesale Trade | n/a in project tags (services GDP only) | — | StatCan 2026-03-01 | OK (GDP only, no project pipeline) |
| 44-45 | Retail Trade | n/a | — | StatCan 2026-03-01 | OK (GDP only) |
| 48-49 | Transportation & Warehousing | 662 transport_logistics + 7 Ports & Logistics + 10 Transit = 679 | $54.0B | 2026-06-11 | OK |
| 51 | Information & Cultural Industries (includes data centres in telecom tag) | 94 telecom | $88.7B | 2026-06-10 | OK |
| 52 | Finance & Insurance | n/a | — | StatCan 2026-03-01 | OK (GDP only) |
| 53 | Real Estate & Rental/Leasing | overlaps residential 271 | $36.2B | 2026-06-08 | OK |
| 54 | Professional, Scientific & Technical Services | n/a | — | StatCan 2026-03-01 | OK (GDP only) |
| 55 | Management of Companies & Enterprises | n/a | — | StatCan 2026-03-01 | OK |
| 56 | Administrative & Waste Management | overlaps environment 272 | $2.6B | 2026-06-11 | OK |
| 61 | Educational Services | 150 | $7.3B | 2026-06-05 | OK |
| 62 | Health Care & Social Assistance | 220 | $50.9B | 2026-06-15 | OK |
| 71 | Arts, Entertainment & Recreation | overlaps tourism_culture 322 | $22.0B | 2026-06-15 | OK |
| 72 | Accommodation & Food Services | overlaps tourism_culture | $22.0B | 2026-06-15 | OK |
| 81 | Other Services | "Other" 256 | $20.0B | 2026-06-15 | OK |
| 91 | Public Administration | 197 government + 56 Defence + 25 indigenous = 278 | $15.6B + $85.9B + $0.2B = $101.7B | 2026-06-13 | OK |

### Critical Gaps Found
Data gap report (2026-06-15) flags overall freshness B with no critical blockers. Sector-relevant warnings: Quebec provincial economic accounts (`qc_real_gdp`, `qc_exports`, `qc_imports`, `qc_business_investment`) last referenced 2025-10-01 (257 days) due to StatCan quarterly release lag. Ontario equivalents same date. Procurement.json carries zero contracts for 2026-06-15 (and all 8 archived weeks) — federal/provincial procurement feed yielded no construction/infrastructure awards >=$5M this cycle. Jobs.json week-of 2026-06-15 carries postings but zero flagged hiring spikes; postings concentrate in construction trades across Toronto/Vancouver/Calgary/Edmonton/Montreal. Agriculture project value coverage is thin (2 of 464 rows priced).

---

## 2. Sector Activity Summary

### Industry GDP at a glance (StatCan, ref 2026-03-01)
M/M and Y/Y, all 20 NAICS published. Source: industry_gdp.json, StatCan Table 36-10-0434.

| NAICS | Sector | M/M | Y/Y |
|---|---|---|---|
| 11 | Agriculture | -1.1% | +2.1% |
| 21 | Mining/O&G | -2.1% | -1.5% |
| 22 | Utilities | +0.0% | -1.6% |
| 23 | Construction | -0.6% | -1.5% |
| 31-33 | Manufacturing | +0.4% | -2.5% |
| 41 | Wholesale | +1.8% | +1.0% |
| 44-45 | Retail | -0.6% | +0.8% |
| 48-49 | Transportation | -0.0% | +3.1% |
| 51 | Information & Culture | -0.2% | +3.2% |
| 52 | Finance/Insurance | -0.0% | +3.6% |
| 53 | Real Estate | +0.1% | +1.8% |
| 54 | Professional/Scientific | -0.2% | -0.4% |
| 55 | Management of Co.s | -1.3% | -22.7% |
| 56 | Admin/Waste | +0.0% | -0.8% |
| 61 | Education | -0.0% | -2.8% |
| 62 | Health Care | +0.0% | +2.0% |
| 71 | Arts/Recreation | +2.0% | +3.5% |
| 72 | Accommodation/Food | -0.4% | +0.5% |
| 81 | Other Services | +0.1% | +0.7% |
| 91 | Public Admin | +0.4% | +1.1% |

Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

The standouts: NAICS 55 (Management of Companies) -22.7% Y/Y is by an order of magnitude the largest GDP decline in the table — likely a head-office reclassification or special holding-company event. NAICS 52 (Finance & Insurance) leads services at +3.6% Y/Y. NAICS 71 (Arts/Recreation) leads M/M at +2.0%. NAICS 31-33 (Manufacturing) carries the largest Y/Y goods decline at -2.5%.

### Sector Growth/Decline (project pipeline)
| NAICS | Sector | Pipeline Value | New This Week (firstTracked >= 2026-06-08) | Latest Discovery |
|---|---|---|---|---|
| 22 (power_energy) | Utilities/Power | $614.3B | Multiple, incl. Red Lake Transmission, Sydney 300MW BESS, Des Neiges Wind | 2026-06-10 |
| 23 (construction) | Construction/Infrastructure | $288.7B | Alberton Wastewater (PE), Rideau Canal Wall Repairs (ON), Brazeau Lake Bridge (AB) | 2026-06-15 |
| 21 (mining/O&G) | Extractive | $248.3B | Eranova Metals Molybdenum (BC), FireFly Metals Green Bay Copper (NL) | 2026-06-15 |
| 51 (telecom) | Data centres/Info | $88.7B | Microsoft Azure Central, TowerBrook/Ascent Cambridge, Prologis Meadowvale | 2026-06-10 |
| 91 (gov+defence+indigenous) | Public/Defence | $101.7B | CFB Petawawa Housing, HMCS Fraser (River-class) | 2026-06-13 |
| 31-33 (manufacturing) | Manufacturing | $85.4B | CGC Wheatland Wallboard (AB), Glencore Horne Smelter Emissions ($300M, QC) | 2026-06-12 |
| 48-49 (transport) | Transport | $54.0B | Alto High-Speed Rail ($3.9B, ON-QC), Port of Quebec Container Terminal | 2026-06-11 |
| 62 (healthcare) | Health | $50.9B | Runnymede Healthcare Centre (ON), Vanderhoof PCCC (BC), Le Bastion (QC) | 2026-06-15 |
| 53 (residential) | Residential | $36.2B | Quartier Molson Mixed-Use (QC), Toronto Rail Yards (ON), Burlington MZO | 2026-06-08 |
| 56 (environment) | Admin/Waste/Env | $2.6B | Deep Sky Manitoba Carbon Removal ($500M), Red-Seine-Rat Wastewater ($205M, MB) | 2026-06-11 |

---

## 3. Sector Spotlights (ALL 20 NAICS INDUSTRIES)

### GOODS INDUSTRIES

#### 11: Agriculture, Forestry, Fishing & Hunting
- **GDP:** -1.1% M/M, +2.1% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Commodity backdrop:** Saskatchewan canola farm price $672.81/t (April 2026 ref, flat W/W, +1.8% M/M, +6.2% Y/Y). Source: StatCan 32-10-0077-01 https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701. Potash proxy Nutrien Ltd $92.23, -1.9% W/W, -5.2% M/M, +12.0% Y/Y — fertilizer input cost direction. Source: https://www.nutrien.com/investors
- **Project activity:** 464 rows tagged Agriculture in pipeline; only 2 priced (data coverage thin). New this week: Canada Food Security Strategy ($3.2B proposed, ON-led, 2026-06-11), Drake Meat Processors Saskatoon Plant (Under Construction, 2026-06-10), Fredericton Farm Services Building Replacement (NB, Under Review).
- **Labour:** Job Bank 2026-06-15 weekly capture shows no Agriculture-coded postings flagged as spikes.
- **Sources:** StatCan Farm Product Prices https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701 | StatCan industry GDP https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

#### 21: Mining, Quarrying & Oil/Gas Extraction
- **GDP:** -2.1% M/M, -1.5% Y/Y (ref 2026-03-01) — largest M/M goods decline. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Commodity backdrop:** Nickel proxy +12.2% W/W, +22.7% M/M, +111.6% Y/Y (current 45.41); Iron ore proxy (Vale) +7.7% W/W, +79.1% Y/Y (current 16.15); Uranium spot proxy +4.5% W/W, +16.1% Y/Y (current 27.07); Cameco Corp $149.80 +2.0% W/W. Source: commodities.json daily refresh.
- **Project activity:** 778 rows tagged mining/oil_gas; $248.3B priced pipeline. New this week: Eranova Metals BC Molybdenum Project (Proposed, BC, 2026-06-15); FireFly Metals Green Bay Copper Project (Proposed, NL, 2026-06-15); Glencore Horne Smelter Emissions Reduction ($300M, QC, Proposed, 2026-06-11) — sits at the mining/manufacturing boundary.
- **IAAC:** 8 Mining files Under Review in federal Impact Assessment Registry. Source: https://iaac-aeic.gc.ca/050/evaluations
- **Labour:** Vale Base Metals Sudbury posting captured 2026-06-15.
- **Sources:** TSX Metals & Mining https://www.tsx.com/listings/listing-with-us/sector-and-product-profiles/mining | IAAC registry https://iaac-aeic.gc.ca/050/evaluations | Cameco https://www.cameco.com/invest

#### 22: Utilities (Electricity, Gas, Water)
- **GDP:** 0.0% M/M, -1.6% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** 936 power_energy rows, $614.3B priced — single largest sector by tracked value. New this week: Red Lake Transmission Line (ON, Proposed, 2026-06-10); Des Neiges Wind Farm Secteur Sud and Charlevoix phases ($3.0B, QC, Under Construction, 2026-06-10); Sydney 300MW Hybrid Wind + Battery Energy Storage (NS, Proposed, 2026-06-10).
- **Federal context:** Bill S-4 (45-1) — An Act to amend the Energy Efficiency Act — first reading 2026-06-05 (House of Commons). Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-4
- **Labour:** Postings in power_energy tag concentrated in Toronto/Montreal/Vancouver electrical trades.
- **Sources:** Canada Energy Regulator https://www.cer-rec.gc.ca/en/data-analysis/ | LegisInfo S-4 https://www.parl.ca/legisinfo/en/bill/45-1/S-4

#### 23: Construction
- **GDP:** -0.6% M/M, -1.5% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Commodity backdrop:** Lumber futures $630.50 +3.0% W/W, +7.9% M/M, +0.6% Y/Y; Steel ETF proxy (SLX) $111.39 +4.7% W/W, +73.4% Y/Y; Iron ore proxy +7.7% W/W. Input-cost direction up across the major construction commodities W/W. Source: commodities.json refresh.
- **Project activity:** 2,005 rows combining infrastructure, residential, commercial_mixed; $288.7B priced. New this week: Alberton Wastewater & Stormwater (PE, Approved, 2026-06-15); Rideau Canal Wall Repairs (ON, Under Review, 2026-06-08); Parks Canada Brazeau Lake Bridge Replacement (AB, Under Review, 2026-06-08).
- **Labour:** Construction trades dominate the 2026-06-15 jobs snapshot — concrete, framing, electrical, roofing posted across Toronto, Vancouver, Calgary, Edmonton, Winnipeg, Regina, Saint John. Job Bank Atom feed only; Indeed RSS is retired and remains so.
- **Sources:** StatCan Building Permits (34-10-0292) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201 | StatCan Construction Price Index (18-10-0135) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810013501

#### 31-33: Manufacturing
- **GDP:** +0.4% M/M, -2.5% Y/Y (ref 2026-03-01) — largest Y/Y goods decline. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** 362 rows, $85.4B priced. New this week: CGC Inc. Wheatland County Wallboard Manufacturing Plant ($210M, AB, Complete, 2026-06-12); Glencore Horne Smelter Emissions Reduction Project ($300M, QC, Proposed, 2026-06-11).
- **Commodity ties:** Steel SLX +73.4% Y/Y is a material input-cost signal for manufacturing capex. Iron ore +79.1% Y/Y likewise. Source: commodities.json.
- **Labour:** Manufacturing-tagged postings concentrated in Toronto (Del Industrial Metals, Powerline Plus, Qualified Metal Fabricators, Fiera Foods), Halifax (IMP Aerospace and Defence), Montreal.
- **Sources:** StatCan Manufacturing Sales (16-10-0047) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701 | StatCan Capital Expenditure Intentions (34-10-0035) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410003501

### SERVICES INDUSTRIES

#### 41: Wholesale Trade
- **GDP:** +1.8% M/M, +1.0% Y/Y (ref 2026-03-01) — largest services M/M. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Pipeline:** No dedicated wholesale tag in projects_all.json; activity captured indirectly through transport_logistics (port and warehouse builds).
- **Labour:** Not separately tracked in jobs.json snapshot.
- **Source:** StatCan Wholesale Trade (20-10-0074) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401

#### 44-45: Retail Trade
- **GDP:** -0.6% M/M, +0.8% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Pipeline:** New this week: Buffalo Run Real Canadian Superstore (AB, Under Construction, 2026-06-15) tracked under "Other" pipeline tag; carries Loblaw proponent.
- **Sources:** StatCan Retail Trade (20-10-0008) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801

#### 48-49: Transportation & Warehousing
- **GDP:** -0.0% M/M, +3.1% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** 679 rows (transport_logistics + Ports & Logistics + Transit), $54.0B priced. New this week: Alto High-Speed Rail ($3.9B, ON-QC corridor, Under Review, Alto Crown corporation / Cadence consortium proponent, 2026-06-11); Port of Quebec International Container Terminal (QC, Under Review, 2026-06-08); Purchases to support transit for Arborg, MB (Proposed, 2026-06-08).
- **IAAC:** 29 transport_logistics files Under Review. Source: https://iaac-aeic.gc.ca/050/evaluations
- **Sources:** Alto official site https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train | Major Projects Office Alto file https://www.canada.ca/en/privy-council/major-projects-office/projects/other/referred/alto.html

#### 51: Information & Cultural Industries
- **GDP:** -0.2% M/M, +3.2% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity (data centres in telecom tag):** 94 rows, $88.7B priced. New this week: Microsoft Azure Canada Central Expansion — York Region Data Centres (ON, Approved, 2026-06-10); Related Digital–TowerBrook–Ascent Cambridge Hyperscale Data Centre Expansion (ON, Under Construction, 2026-06-10); Prologis Meadowvale Data Centre — 7800 Tenth Line West, Mississauga (ON, Proposed, 2026-06-10).
- **Sources:** Microsoft Canada news https://news.microsoft.com/en-ca/ | Prologis https://www.prologis.com/news-research

#### 52: Finance & Insurance
- **GDP:** -0.0% M/M, +3.6% Y/Y (ref 2026-03-01) — largest services Y/Y. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Pipeline:** Not separately project-tagged. Sector tracked via macro indicators.
- **Sources:** OSFI https://www.osfi-bsif.gc.ca/eng/Pages/default.aspx | Bank of Canada Financial System Review https://www.bankofcanada.ca/publications/fsr/

#### 53: Real Estate & Rental/Leasing
- **GDP:** +0.1% M/M, +1.8% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity (residential pipeline mapping):** 271 rows, $36.2B priced. New this week: Quartier Molson Mixed-Use Residential (QC, Proposed, 2026-06-08); Toronto Rail Yards Mixed-Use Community (ON, Proposed, 2026-06-08); Minister's Zoning Order request for residential uses in Burlington (ON, Under Review, 2026-06-08); Portage Place Redevelopment ($650M, MB, Under Construction, 2026-06-11).
- **Commodity ties:** Lumber +7.9% M/M direct residential input cost.
- **Sources:** CMHC Starts https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data | StatCan New Housing Price Index (18-10-0205) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501

#### 54: Professional, Scientific & Technical Services
- **GDP:** -0.2% M/M, -0.4% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Pipeline:** Engineering and architectural firms appear as proponents on infrastructure files (e.g., Englobe Corp postings in Ottawa and Regina); no standalone NAICS-54 project tag.
- **Sources:** StatCan industry GDP https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

#### 55: Management of Companies & Enterprises
- **GDP:** -1.3% M/M, **-22.7% Y/Y** (ref 2026-03-01) — by far the largest Y/Y move in the table, an order of magnitude beyond any other sector. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Note:** NAICS 55 is a thin head-office aggregation that can swing on a single re-classification or large transaction. The size of the move warrants attribution work in the writer/analyst phase (StatCan revision notes on Table 36-10-0434 should be consulted).
- **Sources:** StatCan industry GDP release calendar — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401 (consult The Daily for the corresponding reference-month release notes)

#### 56: Administrative & Waste Management Services
- **GDP:** +0.0% M/M, -0.8% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity (environment + waste pipeline tag):** 272 rows, $2.6B priced. New this week: Deep Sky Manitoba Carbon Removal Facility ($500M, MB, Proposed, 2026-06-11); Red-Seine-Rat Cooperative Wastewater Treatment Facility ($205M, MB, Approved, 2026-06-10); Hay River Water Treatment Plant ($20.1M, NT, Approved, 2026-06-10).
- **Sources:** Deep Sky https://www.deepskyclimate.com/

#### 61: Educational Services
- **GDP:** -0.0% M/M, -2.8% Y/Y (ref 2026-03-01) — second-largest services Y/Y decline. Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** 150 rows, $7.3B priced. New this week: École Whitehorse Elementary (YT, Proposed, 2026-06-05); Francophone Elementary School Kensington Saskatoon CÉF (SK, Under Construction, 2026-06-04); Ontario Higher Education Sector Funding Program ($1.7B, ON, Proposed, 2026-06-03).
- **Sources:** Government of Yukon Education https://yukon.ca/en/education-and-schools | Ministry of Colleges and Universities https://www.ontario.ca/page/ministry-colleges-universities

#### 62: Health Care & Social Assistance
- **GDP:** +0.0% M/M, +2.0% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** 220 rows, $50.9B priced. New this week: Runnymede Healthcare Centre Redevelopment (ON, Proposed, 2026-06-15); Le Bastion — Centre intégré pour personnes en situation de vulnérabilité (QC, Complete, 2026-06-15); Vanderhoof Primary and Community Care Centre (BC, Under Construction, 2026-06-15).
- **Labour:** Saskatchewan Health Authority postings in Saskatoon and Regina; VON Canada Sudbury; HRS Talent Solutions postings across Vancouver/Calgary/Edmonton.
- **Federal context:** Bill S-5 (45-1) Connected Care for Canadians Act, first reading 2026-05-28. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-5
- **Sources:** SHA https://www.saskhealthauthority.ca/ | Runnymede HC https://www.runnymedehc.ca/

#### 71: Arts, Entertainment & Recreation
- **GDP:** +2.0% M/M (largest M/M services move), +3.5% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity (tourism_culture pipeline tag covers 71 and 72):** 322 rows, $22.0B priced. New this week: Terra Nova Cabin Access Trail (NL, Proposed, 2026-06-15); Old Days Pond Increased Access to Nature (NL, Proposed, 2026-06-08); Parks Canada Sulphur Mountain Boardwalk Repairs (AB, Under Review, 2026-06-08).
- **Sources:** Parks Canada https://parks.canada.ca/

#### 72: Accommodation & Food Services
- **GDP:** -0.4% M/M, +0.5% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity:** Captured through tourism_culture pipeline tag and commercial_mixed. Notable: InterContinental Montréal Full-Closure Renovation (QC, Under Construction, 2026-06-10).
- **Sources:** StatCan Food Services and Drinking Places (21-10-0019) https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2110001901

#### 81: Other Services (except Public Administration)
- **GDP:** +0.1% M/M, +0.7% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Pipeline ("Other" tag):** 256 rows, $20.0B priced. New this week: British Columbia 2026 Road Resurfacing Program (BC, Under Construction, 2026-06-15); Bearspaw Feeder Main Replacement (AB, Proposed, 2026-06-15); Buffalo Run Real Canadian Superstore (AB, Under Construction, 2026-06-15).
- **Note:** "Other" is a fall-through pipeline tag, not a clean NAICS-81 match — some rows belong elsewhere (e.g., Bearspaw Feeder Main is utilities-22, Buffalo Run is retail-44-45). Analyst phase should re-bucket.
- **Sources:** StatCan industry GDP https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401

#### 91: Public Administration
- **GDP:** +0.4% M/M, +1.1% Y/Y (ref 2026-03-01). Source: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401
- **Project activity (government + defence + indigenous tags):** 278 rows, $101.7B priced. New this week: CFB Petawawa Military Housing Development (ON, Proposed, 2026-06-13); HMCS Fraser (River-class destroyer) (NS, Under Construction, 2026-06-12); Warkworth Institution Fuel Storage Tank Replacements (ON, Under Review, 2026-06-08); Brockville Correctional Complex and St. Lawrence Valley CTC Expansion (ON, Approved, 2026-06-10); Shoal Lake 40 First Nation Housing Development at 2675 Portage Avenue Winnipeg ($51M, MB, Approved, 2026-06-10); Endayaan Omaa Indigenous Housing — Treaty One Nations (Naawi-Oodena) ($90.8M, MB, Under Construction, 2026-06-10).
- **IAAC:** 8 defence files Under Review; 7 government; 9 indigenous. Source: https://iaac-aeic.gc.ca/050/evaluations
- **Federal legislative activity:** 20 federal bills logged in policy.json for week-of 2026-06-15 (S-1 through S-214 series sample). Source: https://www.parl.ca/legisinfo
- **Sources:** River-class Destroyer program https://www.canada.ca/en/department-national-defence/services/procurement/canadian-surface-combatant.html | LegisInfo https://www.parl.ca/legisinfo

---

## 4. Commodity Price Impact Analysis (commodities.json, ref 2026-06-15)

### Energy
- WTI / WCS / natural gas: not in current commodities.json snapshot (snapshot scope is mining/agriculture/construction inputs this cycle); pipeline timeseries.json carries WTI/Brent/HenryHub independently for the Markets agents. Goods-sector commodity coverage here is intentionally focused on inputs that drive project economics.

### Metals
- Nickel proxy: 45.41, +12.2% W/W, +22.7% M/M, +111.6% Y/Y. Affected sectors NAICS 21 (mining), 31-33 (manufacturing/EV battery). Affected provinces ON, QC, NL, MB.
- Iron ore (Vale): 16.15, +7.7% W/W, +79.1% Y/Y. Sectors 21, 23. Provinces QC, NL.
- Steel (SLX ETF): 111.39, +4.7% W/W, +73.4% Y/Y. Sectors 23, 48-49.
- Uranium spot (Sprott U-UN.TO): 27.07, +4.5% W/W, +16.1% Y/Y. Sectors 21, 22. Provinces SK, ON, NB.
- Cameco: 149.80, +2.0% W/W. Same sector exposure as uranium spot.
- Source: commodities.json refresh 2026-06-15T18:04:50.

### Agriculture
- Canola farm price (StatCan 32-10-0077-01): 672.81 $/t (April 2026 ref), 0.0% W/W, +1.8% M/M, +6.2% Y/Y. Sector 11. Provinces SK, AB, MB.
- Potash (Nutrien): 92.23, -1.9% W/W, -5.2% M/M, +12.0% Y/Y. Sectors 11, 21. Provinces SK, AB.

### Construction Inputs
- Lumber futures: 630.50, +3.0% W/W, +7.9% M/M, +0.6% Y/Y. Sectors 23, 53. Provinces BC, QC, ON.
- TSX Infrastructure basket: 57.56, -0.3% W/W, +2.9% M/M, +33.0% Y/Y. Sectors 22, 48-49.

---

## 5. Major Project Announcements by Sector

### New Projects Discovered This Week (firstTracked >= 2026-06-08)
- **Power/Energy (22):** Red Lake Transmission Line (ON, Proposed). Des Neiges Wind Farm Secteur Sud + Charlevoix ($3.0B, QC, Under Construction). Sydney 300MW Hybrid Wind + BESS (NS, Proposed).
- **Mining (21):** Eranova Metals BC Molybdenum (BC, Proposed). FireFly Metals Green Bay Copper (NL, Proposed). Goldeye Lake Drive Subdivision (MB, Under Review).
- **Oil & Gas (21):** Marinvest Energy Baie-Comeau LNG Export (QC, Proposed).
- **Manufacturing (31-33):** CGC Inc. Wheatland County Wallboard Manufacturing Plant ($210M, AB, Complete). Glencore Horne Smelter Emissions Reduction ($300M, QC, Proposed).
- **Transport (48-49):** Alto High-Speed Rail ($3.9B, ON-QC, Under Review). Port of Quebec International Container Terminal (QC, Under Review).
- **Healthcare (62):** Runnymede Healthcare Centre Redevelopment (ON, Proposed). Le Bastion (QC, Complete). Vanderhoof PCCC (BC, Under Construction).
- **Residential (53):** Quartier Molson Mixed-Use (QC, Proposed). Toronto Rail Yards Mixed-Use Community (ON, Proposed). Burlington MZO request (ON, Under Review).
- **Commercial/Mixed:** Portage Place Redevelopment ($650M, MB, Under Construction). InterContinental Montréal renovation (QC, Under Construction). Amazon Barrhaven Fulfillment Centre 99 Bill Leathem Drive Ottawa (ON, Under Construction).
- **Telecom/Data Centres (51):** Microsoft Azure Canada Central Expansion York Region (ON, Approved). Related/TowerBrook/Ascent Cambridge Hyperscale (ON, Under Construction). Prologis Meadowvale (ON, Proposed).
- **Defence (91):** CFB Petawawa Military Housing (ON, Proposed). HMCS Fraser (NS, Under Construction).
- **Environment (56):** Deep Sky Manitoba Carbon Removal ($500M, MB, Proposed). Red-Seine-Rat Wastewater ($205M, MB, Approved). Hay River Water Treatment ($20.1M, NT, Approved).
- **Indigenous (91):** Shoal Lake 40 First Nation Housing 2675 Portage Ave Winnipeg ($51M, MB, Approved). Endayaan Omaa Treaty One Naawi-Oodena ($90.8M, MB, Under Construction).
- **Agriculture (11):** Canada Food Security Strategy ($3.2B, ON, Proposed). Drake Meat Processors Saskatoon (SK, Under Construction).
- **Forestry (11):** Atlas Engineered Products Advanced Wood Manufacturing Facility, Clinton ON (Approved).
- **Government (91):** Brockville Correctional Complex and St. Lawrence Valley CTC Expansion (ON, Approved).
- **Education (61):** Ontario Higher Education Sector Funding Program ($1.7B, ON, Proposed).

### Status Changes
Pipeline status_history records show most 2026-06-08+ entries are first-tracking events rather than transitions. Material transitions to verify in analyst phase: Atlas Engineered Products → Approved; Microsoft Azure Canada Central → Approved; Brockville Correctional → Approved; Red-Seine-Rat Wastewater → Approved; Shoal Lake 40 First Nation → Approved.

---

## 6. Labour Market by Sector

### Employment Levels (Latest Available, ref May 2026 LFS)
Statistics Canada Labour Force Survey publishes industry employment via Table 14-10-0022. Reference month for the 2026-06-13 release is May 2026. Sectoral detail should be pulled at writer time from https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201.

### Job Posting Activity (Job Bank Atom feed, week-of 2026-06-15)
- Pipeline tags with material posting volume: oil_gas (29 city/employer rows), infrastructure (50+ rows), residential, commercial_mixed, manufacturing, power_energy, healthcare. Most rows are single postings per employer per CMA.
- Construction trades dominate: concrete, framing, electrical, roofing, masonry, drywall — Toronto, Vancouver, Calgary, Edmonton, Winnipeg, Regina, Saint John.
- Healthcare postings cluster at SHA (Saskatoon/Regina), HRS Talent Solutions multi-CMA, VON Canada Sudbury.
- Manufacturing postings include IMP Aerospace and Defence (Halifax), Fiera Foods (Toronto), Powerline Plus (Toronto), Del Industrial Metals (Toronto).
- **Spikes flagged: 0** (job_monitor week 2026-06-15 `spikes` array empty).
- Source: Job Bank Atom feed https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed?searchstring=&fprov=

### Labour Shortage Indicators
StatCan Job Vacancies (14-10-0326 quarterly, 14-10-0372 monthly SA) provides sectoral vacancy rates. Use the latest at writer time: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201

---

## 7. Policy and Regulatory Impacts

### Energy / Energy Efficiency
- **Bill S-4 (45-1) An Act to amend the Energy Efficiency Act** — first reading 2026-06-05 (House of Commons). Affects NAICS 22, 23, 31-33 (building codes, equipment standards). Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-4
- **Bill S-3 (45-1) An Act to amend the Weights and Measures Act, the Electricity and Gas Inspection Act…** — debate at second reading 2026-04-29. Affects NAICS 22 utility metering and 41 wholesale. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-3

### Railways / Transport
- **Bill S-1 (45-1) An Act relating to railways** — introduction and first reading 2025-05-27 (Senate). Standing pro-forma bill but signals session opening. Affects NAICS 48-49. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-1

### Healthcare
- **Bill S-5 (45-1) Connected Care for Canadians Act** — first reading 2026-05-28. Affects NAICS 62. Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-5

### Indigenous
- **Bill S-2 (45-1) An Act to amend the Indian Act (new registration entitlements)** — second reading and referral to committee 2026-02-27. Affects NAICS 91 (Indigenous program scope). Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-2

### Sanctions / Trade
- **Bill S-214 (45-1) An Act to amend the Special Economic Measures Act (disposal of foreign state assets)** — third reading 2026-05-26 (Senate). Affects NAICS 52 (finance compliance) and 41 (wholesale trade with sanctioned entities). Source: https://www.parl.ca/legisinfo/en/bill/45-1/S-214

### Provincial Activity
policy.json 2026-06-15 week tallies 10 provincial items, all BC-coded. Detail to pull at analyst phase from policy.json items array (week summary captures top federal developments only).

---

## 8. Emerging Stories and Cross-Sector Trends

### Fastest-Growing Sectors (project value pipeline)
- **Power/Energy (NAICS 22):** $614.3B priced pipeline is the single largest sector in the database. New tracked-this-week additions span transmission (Red Lake), wind ($3.0B Des Neiges), and storage (Sydney NS 300MW BESS).
- **Information & Cultural Industries / data centres (NAICS 51):** $88.7B in 94 projects. Three Ontario hyperscale data centre files added in the past week alone (Microsoft Azure Central, Cambridge hyperscale, Prologis Meadowvale).
- **Construction (NAICS 23):** $288.7B across 2,005 rows is the broadest pipeline by count.

### Sectors Facing Y/Y GDP Declines
- **Manufacturing (31-33):** -2.5% Y/Y is the largest goods-sector Y/Y decline; +0.4% M/M suggests partial M/M stabilization.
- **Mining (21):** -1.5% Y/Y, -2.1% M/M.
- **Utilities (22):** -1.6% Y/Y.
- **Construction (23):** -1.5% Y/Y, -0.6% M/M.
- **Education (61):** -2.8% Y/Y is the largest non-NAICS-55 services Y/Y decline.
- **Management of Companies (55):** -22.7% Y/Y outlier — verify in analyst phase whether driven by a single re-classification or large transaction; magnitude is an order beyond any other sector.

### Commodity-Driven Sectoral Stories
- **Nickel +111.6% Y/Y:** affects ON/QC/NL/MB nickel mine projects and EV battery supply chain (NAICS 21, 31-33).
- **Iron ore +79.1% Y/Y, Steel +73.4% Y/Y:** raise infrastructure and manufacturing input costs (NAICS 23, 31-33).
- **Uranium spot +16.1% Y/Y, Cameco +59.4% Y/Y:** support Saskatchewan uranium expansion economics and SMR supply chain (NAICS 21, 22).
- **Canola +6.2% Y/Y, Potash +12.0% Y/Y:** Saskatchewan/Alberta/Manitoba agricultural project economics (NAICS 11).
- **Lumber +7.9% M/M:** residential build input (NAICS 23, 53).

### Cross-Sector
- **Manitoba environmental capex cluster:** Deep Sky Carbon Removal ($500M) + Red-Seine-Rat Wastewater ($205M) + Shoal Lake 40 Housing ($51M) + Endayaan Omaa Naawi-Oodena ($90.8M) + Portage Place ($650M) — a $1.5B Manitoba multi-sector week.
- **Ontario data-centre concentration:** 3 hyperscale files in York/Cambridge/Mississauga within one tracking week — pipeline shows continued NAICS-51 capex concentration in the GTA-Waterloo corridor.

---

## 9. Coverage Gaps and Priorities

- **Agriculture project value coverage thin:** 2 of 464 Agriculture rows carry priced values. Analyst phase should consider whether this reflects genuine cost-disclosure norms in the sector or pipeline tagging gaps.
- **Procurement feed empty:** 0 contracts week-of 2026-06-15 (and all 8 archived weeks). procurement_monitor outputs absent from this snapshot — verify whether the publish step is failing or whether the federal-and-Quebec-only live sources legitimately had no qualifying awards this cycle. CLAUDE.md notes Ontario/BC procurement coverage relies on CanadaBuys delivery-region rows since BuyAndSell is DNS-dead.
- **NAICS 55 (-22.7% Y/Y) needs source attribution:** size of move warrants checking StatCan Daily release notes for Table 36-10-0434 (May 2026 release for February reference month).
- **Provincial economic accounts for ON and QC are 257 days stale** due to StatCan publication lag — analyst must cite reference period, not portray as current-week data.
- **No NAICS 41 / 44-45 / 52 / 54 / 55 standalone project tags** in pipeline taxonomy — these sectors are GDP-only with no project-level capture. Acceptable by design (service-sector capex is largely lease/leasehold-improvement and falls below project thresholds).

---

## 10. Master Source Registry

[1] StatCan Table 36-10-0434 GDP by Industry — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401 — 2026-06-15 — All 20 NAICS industry GDP M/M and Y/Y (ref 2026-03-01)
[2] StatCan Table 32-10-0077-01 Farm Product Prices — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701 — 2026-06-15 — Canola farm price SK ref April 2026
[3] StatCan Table 34-10-0292 Building Permits — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201 — 2026-06-15 — Construction permit context
[4] StatCan Table 18-10-0135 Construction Price Index — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810013501 — 2026-06-15 — Construction input cost index
[5] StatCan Table 16-10-0047 Manufacturing Sales — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701 — 2026-06-15 — NAICS 31-33 sales
[6] StatCan Table 34-10-0035 Capital Expenditure Intentions — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410003501 — 2026-06-15 — Annual capex intentions
[7] StatCan Table 20-10-0008 Retail Trade — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801 — 2026-06-15 — NAICS 44-45
[8] StatCan Table 20-10-0074 Wholesale Trade — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401 — 2026-06-15 — NAICS 41
[9] StatCan Table 21-10-0019 Food Services and Drinking Places — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2110001901 — 2026-06-15 — NAICS 72
[10] StatCan Table 14-10-0022 Employment by Industry — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201 — 2026-06-15 — Sectoral employment LFS
[11] StatCan Table 14-10-0372 Job Vacancies SA — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201 — 2026-06-15 — Vacancy rates by sector
[12] StatCan Table 18-10-0205 New Housing Price Index — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501 — 2026-06-15 — NHPI
[13] Impact Assessment Agency of Canada Registry — https://iaac-aeic.gc.ca/050/evaluations — 2026-06-15 — 162 federal EA projects tracked
[14] LegisInfo Parliament of Canada — https://www.parl.ca/legisinfo — 2026-06-15 — Federal bills index
[15] Bill S-1 (45-1) Railways — https://www.parl.ca/legisinfo/en/bill/45-1/S-1 — 2025-05-27 — Pro-forma railway bill
[16] Bill S-2 (45-1) Indian Act amendments — https://www.parl.ca/legisinfo/en/bill/45-1/S-2 — 2026-02-27 — Indigenous registration
[17] Bill S-3 (45-1) Weights and Measures, Electricity and Gas Inspection — https://www.parl.ca/legisinfo/en/bill/45-1/S-3 — 2026-04-29 — Utility metering
[18] Bill S-4 (45-1) Energy Efficiency Act — https://www.parl.ca/legisinfo/en/bill/45-1/S-4 — 2026-06-05 — Energy efficiency
[19] Bill S-5 (45-1) Connected Care for Canadians Act — https://www.parl.ca/legisinfo/en/bill/45-1/S-5 — 2026-05-28 — Healthcare
[20] Bill S-214 (45-1) Special Economic Measures — https://www.parl.ca/legisinfo/en/bill/45-1/S-214 — 2026-05-26 — Sanctions
[21] Canada Energy Regulator data — https://www.cer-rec.gc.ca/en/data-analysis/ — 2026-06-15 — Energy data
[22] Alto High-Speed Rail official — https://www.altotrain.ca/en/shaping-canadas-future-high-speed-train — 2026-06-11 — Alto project page
[23] Major Projects Office Alto file — https://www.canada.ca/en/privy-council/major-projects-office/projects/other/referred/alto.html — 2026-06-11 — Government MPO reference
[24] Microsoft News Canada — https://news.microsoft.com/en-ca/ — 2026-06-10 — Azure Canada Central expansion
[25] Prologis newsroom — https://www.prologis.com/news-research — 2026-06-10 — Meadowvale data centre
[26] Deep Sky climate — https://www.deepskyclimate.com/ — 2026-06-11 — Carbon removal facility
[27] Cameco investor — https://www.cameco.com/invest — 2026-06-15 — Uranium producer
[28] Nutrien investor — https://www.nutrien.com/investors — 2026-06-15 — Potash producer
[29] CMHC housing data — https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data — 2026-06-15 — Housing starts
[30] OSFI — https://www.osfi-bsif.gc.ca/eng/Pages/default.aspx — 2026-06-15 — Financial regulation NAICS 52
[31] Bank of Canada Financial System Review — https://www.bankofcanada.ca/publications/fsr/ — 2026-06-15 — Financial stability context
[32] Government of Yukon Education — https://yukon.ca/en/education-and-schools — 2026-06-05 — École Whitehorse Elementary
[33] Ontario Ministry of Colleges and Universities — https://www.ontario.ca/page/ministry-colleges-universities — 2026-06-03 — Higher Education Funding Program
[34] Saskatchewan Health Authority — https://www.saskhealthauthority.ca/ — 2026-06-15 — SHA healthcare postings
[35] Runnymede Healthcare Centre — https://www.runnymedehc.ca/ — 2026-06-15 — Redevelopment file
[36] Parks Canada — https://parks.canada.ca/ — 2026-06-15 — Multiple national park files (Sulphur Mountain, Brazeau Lake, Rideau Canal, Terra Nova)
[37] Department of National Defence — Canadian Surface Combatant — https://www.canada.ca/en/department-national-defence/services/procurement/canadian-surface-combatant.html — 2026-06-12 — River-class destroyer (HMCS Fraser)
[38] StatCan Daily release calendar — https://www150.statcan.gc.ca/n1/dai-quo/index-eng.htm — 2026-06-15 — Industry GDP release notes (analyst phase to dereference exact daily entry)
[39] Job Bank Atom feed — https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed?searchstring=&fprov= — 2026-06-15 — Sole pipeline source for sectoral job postings (Indeed RSS retired)
[40] commodities.json pipeline snapshot — 2026-06-15T18:04:50 — Local refresh — All commodity W/W/M/M/Y/Y values quoted in Sections 3 and 4
