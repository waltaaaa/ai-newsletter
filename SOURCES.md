# CAN-MACRO Strategic Dashboard — Complete Source Inventory

> Auto-generated source reference. 14-tier discovery pipeline + economic data APIs.

---

## Tier 1 — Federal Registries

| Registry | URL | Method |
|---|---|---|
| IAAC (Impact Assessment Agency) | `https://iaac-aeic.gc.ca/050/evaluations/exploration?culture=en-CA` | HTML scrape |
| BC Environmental Assessment Office | `https://www.projects.eao.gov.bc.ca/api/v2/projects?fields=name,eacDecision,status,proponent,sector,region,description&pageSize=200` | JSON API |
| Infrastructure Canada | `https://infrastructure.gc.ca/alt-format/opendata/project-list-liste-de-projets-bil.json` | JSON open data |
| CanadaBuys Contracts | `https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv` | CSV stream (first 2MB) |
| NRCan Major Projects Inventory | `https://natural-resources.canada.ca/science-and-data/data-and-analysis/major-projects-inventory/22218` + XLSX | HTML + XLSX |
| Canada Energy Regulator | `https://www.cer-rec.gc.ca/en/applications-hearings/view-applications-projects/` | HTML scrape |
| Ontario Environmental Registry | `https://ero.ontario.ca/search` | HTML scrape |
| Canada Infrastructure Bank | `https://cib-bic.ca/en/investments/` | Tavily/HTML |
| Metrolinx Project Tracker | `https://www.metrolinx.com/en/projects-and-programs` | Next.js JSON |

---

## Tier 2 — Google News RSS Search (759 queries)

**File:** `google_news_rss_search.py` | **Query file:** `compound_queries_final.json`
**Endpoint:** `https://news.google.com/rss/search?q={terms}&hl=en-CA&gl=CA&ceid=CA:en` (free, unlimited)

| Category | Count |
|---|---|
| English province-sector queries | 179 |
| French province-sector queries (QC) | 60 |
| CMA-sector queries | 280 |
| Regional-sector queries | 210 |
| Lifecycle queries | 30 |
| **Total** | **759** |

---

## Tier 3 — GDELT (~200 queries, reduced role)

**File:** `gdelt_monitor.py`
**Endpoint:** `http://api.gdeltproject.org/api/v2/doc/doc` (HTTP only — HTTPS blocked by ISP)

Bail-out after 3 consecutive failures. Largely superseded by Google News RSS.

---

## Tier 4 — RSS Feeds (201 feeds)

**File:** `rss_feeds.json`

### Federal Government (21 feeds)

| Feed | URL |
|---|---|
| Transport Canada | `https://www.canada.ca/en/transport-canada.atom.xml` |
| Natural Resources Canada | `https://www.canada.ca/en/natural-resources-canada.atom.xml` |
| ISED | `https://www.canada.ca/en/innovation-science-economic-development.atom.xml` |
| Infrastructure Canada | `https://www.canada.ca/en/office-infrastructure.atom.xml` |
| Department of National Defence | `https://www.canada.ca/en/department-national-defence.atom.xml` |
| Public Services and Procurement | `https://www.canada.ca/en/public-services-procurement.atom.xml` |
| Canada Energy Regulator | `https://www.canada.ca/en/energy-regulator.atom.xml` |
| Agriculture and Agri-Food Canada | `https://www.canada.ca/en/agriculture-agri-food.atom.xml` |
| Fisheries and Oceans Canada | `https://www.canada.ca/en/fisheries-oceans.atom.xml` |
| Health Canada | `https://www.canada.ca/en/health-canada.atom.xml` |
| Environment and Climate Change Canada | `https://www.canada.ca/en/environment-climate-change.atom.xml` |
| Department of Finance Canada | `https://www.canada.ca/en/department-finance.atom.xml` |
| Crown-Indigenous Relations | `https://www.canada.ca/en/crown-indigenous-relations-northern-affairs.atom.xml` |
| Immigration, Refugees and Citizenship | `https://www.canada.ca/en/immigration-refugees-citizenship.atom.xml` |
| Public Health Agency of Canada | `https://www.canada.ca/en/public-health.atom.xml` |
| Canadian Heritage | `https://www.canada.ca/en/canadian-heritage.atom.xml` |
| Employment and Social Development | `https://www.canada.ca/en/employment-social-development.atom.xml` |
| Treasury Board Secretariat | `https://www.canada.ca/en/treasury-board-secretariat.atom.xml` |
| Financial Consumer Agency | `https://www.canada.ca/en/financial-consumer-agency.atom.xml` |
| Canada Gazette | `https://gazette.gc.ca/rss/sc-rb-eng.xml` |
| Open Government | `https://open.canada.ca/data/en/feeds/dataset.atom` |

### Provincial Government (14 feeds — all bypass RSS filters)

| Province | URL |
|---|---|
| British Columbia | `https://news.gov.bc.ca/feed` |
| Alberta | `https://www.alberta.ca/news.rss` |
| Saskatchewan | `https://www.saskatchewan.ca/government/news-and-media/rss` |
| Manitoba | `https://news.gov.mb.ca/news/rss` |
| Ontario | `https://news.ontario.ca/newsroom/en/rss` |
| Quebec | `https://www.quebec.ca/nouvelles/rss` |
| Quebec Assemblée nationale | `https://www.assnat.qc.ca/fr/fils-rss/rss.xml` |
| New Brunswick | `https://www2.gnb.ca/content/gnb/en/news/rss.xml` |
| Nova Scotia | `https://novascotia.ca/news/feed/` |
| Prince Edward Island | `https://www.princeedwardisland.ca/en/news/feed` |
| Newfoundland & Labrador | `https://www.gov.nl.ca/releases/feed/` |
| Yukon | `https://yukon.ca/en/news/rss.xml` |
| Northwest Territories | `https://www.gov.nt.ca/en/newsroom/feed` |
| Nunavut | `https://news.gov.nu.ca/feed/` |

### Municipal (1 feed)

| Feed | URL |
|---|---|
| CivicInfo BC | `https://www.civicinfo.bc.ca/feeds/rss` |

### CBC (22 feeds)

CBC Top Stories, Canada, Business, Politics, Indigenous, Marketplace + regional feeds for BC, Calgary, Edmonton, Saskatchewan, Manitoba, Thunder Bay, Sudbury, Windsor, Kitchener-Waterloo, Toronto, Hamilton, Ottawa, Montreal, New Brunswick, PEI, Nova Scotia, Newfoundland & Labrador, North

### CTV (15 feeds)

Top Stories, Business, Politics, Atlantic, Ottawa, Toronto, Kitchener, Winnipeg, Calgary, Edmonton, Vancouver, Saskatchewan, Montreal, Northern Ontario, London

### Global News (5 feeds)

Top, Canada, Business, Politics, Money

### Postmedia (17 feeds)

National Post, Financial Post, Vancouver Sun, The Province (Vancouver), Calgary Herald, Edmonton Journal, Edmonton Sun, Calgary Sun, Regina Leader-Post, Saskatoon StarPhoenix, Winnipeg Sun, Ottawa Citizen, Ottawa Sun, Toronto Sun, Montreal Gazette, Windsor Star, London Free Press, Hamilton Spectator

### Independent / Wire (13 feeds)

Globe and Mail Business, Toronto Star, Canada's National Observer, Business in Vancouver (BIV), Canada Newswire (CNW), Maclean's, SaltWire Network, Daily Commercial News, Journal of Commerce, Northern Miner, ReNew Canada, BNN Bloomberg, Reuters Canada

### Industry Trade (22 feeds)

| Feed | URL |
|---|---|
| On-Site Magazine | `https://www.on-sitemag.com/feed/` |
| Canadian Architect | `https://www.canadianarchitect.com/feed/` |
| Canadian Consulting Engineer | `https://www.canadianconsultingengineer.com/feed/` |
| Canadian Mining Journal | `https://www.canadianminingjournal.com/feed/` |
| Mining.com | `https://www.mining.com/feed/` |
| JWN Energy (Daily Oil Bulletin) | `https://www.jwnenergy.com/feed/` |
| Electric Energy Online | `https://electricenergyonline.com/feed/` |
| RENX (Real Estate News Exchange) | `https://renx.ca/feed/` |
| Storeys | `https://storeys.com/feed/` |
| Journal Constructo (QC) | `https://www.journalconstructo.com/feed/` |
| Infra Québec | `https://infra.quebec/feed` |
| Heavy Equipment Guide | `https://www.heavyequipmentguide.ca/feed/` |
| Canadian Infrastructure Bank | `https://cib-bic.ca/en/media-centre/feed/` |
| Canadian Construction Association | `https://www.cca-acc.com/feed/` |
| Parliamentary Budget Officer | `https://distribution-a617274656661637473.pbo-dpb.ca/rss-feed.xml` |
| PDAC (Mining Association) | `https://www.pdac.ca/feed` |
| Clean Energy Canada | `https://cleanenergycanada.org/feed/` |
| Smart Prosperity Institute | `https://institute.smartprosperity.ca/feed` |
| Pembina Institute | `https://www.pembina.org/feed` |
| Canadian Real Estate Magazine | `https://www.canadianrealestatemagazine.ca/feed/` |
| Livabl (Real Estate) | `https://www.livabl.com/feed` |
| BetterDwelling | `https://betterdwelling.com/feed/` |
| Electric Autonomy Canada | `https://electricautonomy.ca/feed/` |

### Regional Media (20 feeds)

Winnipeg Free Press, Chronicle Herald (Halifax), The Telegram (St. John's), Telegraph-Journal (NB), The Guardian (PEI), North Bay Nugget, Sudbury Star, Sault Star, Lethbridge Herald, Prince George Citizen, Kamloops This Week, Penticton Herald, Northern News Services (NWT/NU), Yukon News, Whitehorse Star, Waterloo Region Record, St. Catharines Standard, Peterborough Examiner, Cape Breton Post, Truro Daily News

### Business Media (18 feeds)

The Logic, BetaKit (Tech), Daily Hive, Western Investor, Alberta Venture, CBC Marketplace, iPolitics, The Hub, Rabble.ca, Canadian Business, CMHC News, CBC Indigenous, Narcity (Toronto/Vancouver/Montreal/Calgary), UrbanToronto

---

## Tier 5 — Provincial EA Registries (10 scrapers)

| Province/Territory | URL | Method |
|---|---|---|
| Quebec BAPE | `https://www.bape.gouv.qc.ca/fr/dossiers/` | HTML scrape |
| Alberta EA | `https://www.alberta.ca/environmental-impact-assessments-current-projects` | HTML scrape |
| Saskatchewan EA | `https://www.saskatchewan.ca/business/environmental-protection-and-sustainability/environmental-assessment/environmental-assessment-projects` | HTML scrape |
| Manitoba EA | `https://www.gov.mb.ca/sd/eal/registries/` | HTML scrape |
| Nova Scotia EA | `https://novascotia.ca/nse/ea/projects.asp` | HTML scrape |
| New Brunswick EIA | `https://www2.gnb.ca/content/gnb/en/departments/elg/environment/content/environmental_impactassessment.html` | HTML scrape |
| Newfoundland & Labrador EA | `https://www.gov.nl.ca/ecc/env-assessment/projects-list/` | HTML scrape |
| PEI (no formal EA registry) | — | — |
| Yukon YESAB | `https://yesabregistry.ca/projects` | HTML scrape |
| NWT Mackenzie Valley Review Board | `https://new.reviewboard.ca/en/registry` | HTML scrape |

---

## Tier 6 — SEDAR+ Securities Filings

| Source | URL | Method |
|---|---|---|
| SEDAR+ | `https://www.sedarplus.ca/csa-party/records/record.html?lang=en` | Tavily extract (blocks direct scraping) |

---

## Tier 7 — Crown Corporation Capital Plans

Covered by CIB and Metrolinx in Tier 1, plus RSS feeds for CMHC, CIB, Metrolinx in Tier 4.

---

## Tier 8 — Canada Energy Regulator

Covered in Tier 1 (CER applications scraper) and Tier 4 (CER RSS feed).

---

## Tier 9 — StatCan Building Permits (Anomaly Detection)

**File:** `statcan_permits.py`
**Table:** 34-10-0066-01 — Building permits by type of structure and type of work
**Anomaly threshold:** current month > 3.0x the 12-month moving average

**20 CMAs tracked:**

| CMA | Vector ID |
|---|---|
| Toronto | 77987 |
| Montreal | 77971 |
| Vancouver | 78009 |
| Calgary | 77951 |
| Edmonton | 77953 |
| Ottawa | 77979 |
| Winnipeg | 77967 |
| Quebec City | 77973 |
| Hamilton | 77981 |
| Kitchener | 77985 |
| London | 77983 |
| Halifax | 77957 |
| Victoria | 78007 |
| Windsor | 77993 |
| Saskatoon | 77947 |
| Regina | 77945 |
| St. John's | 77939 |
| Kelowna | 78005 |
| Abbotsford | 78003 |
| Barrie | 77997 |

---

## Tier 10 — Federal Lobbyist Registry

**File:** `lobbyist_registries.py`

| Source | URL | Method |
|---|---|---|
| Lobbyist Registry bulk data | `https://lobbycanada.gc.ca/media/zwcjycef/registrations_enregistrements_ocl_cal.zip` | ZIP/CSV download |

Filtered for infrastructure, energy, mining, transport, housing, defence subject matters. Lookback: entries with effective_date >= 2025.

---

## Tier 11 — Municipal Development Applications (15 CMAs)

**File:** `municipal_dev_apps.py`

### Open Data API Cities

| City | URL | Method | Threshold |
|---|---|---|---|
| Vancouver | `https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/issued-building-permits/records` | CKAN v2 | $175M+ |
| Calgary | `https://data.calgary.ca/resource/6933-unw5.json` | Socrata | $200M+ |
| Edmonton | `https://data.edmonton.ca/resource/24uj-dj8v.json` | Socrata | $200M+ |
| Winnipeg | `https://data.winnipeg.ca/resource/m4wt-mqkb.json` | Socrata | $40M+ |

### HTML Portal Cities

| City | URL |
|---|---|
| Toronto | `https://www.toronto.ca/city-government/planning-development/application-information-centre/` |
| Ottawa | `https://devapps.ottawa.ca/en/` |
| Montreal | `https://ocpm.qc.ca/fr/consultations-publiques` |
| Hamilton | `https://www.hamilton.ca/develop-property/planning-applications` |
| Halifax | `https://www.halifax.ca/business/planning-development/applications` |
| Quebec City | `https://www.ville.quebec.qc.ca/citoyens/permis/` |
| Saskatoon | `https://www.saskatoon.ca/business-development/planning/development-permits` |
| Regina | `https://www.regina.ca/business-development/building-property-maintenance/building-permits/` |
| St. John's | `https://www.stjohns.ca/en/business-investment/development-applications.aspx` |
| Fredericton | `https://www.fredericton.ca/en/building-renovating` |
| Charlottetown | `https://www.charlottetown.ca/departments/planning-and-heritage` |

---

## Tier 12 — Google Alerts (25 alerts)

**File:** `google_alerts.py`
Manual setup at `https://google.com/alerts` with RSS delivery mode.

**Alert queries by category:**

- **High-value catch-alls:** `"billion dollar" project Canada construction`, `"hundred million" project Canada construction`, `"major project" approved Canada`, `"construction begins" Canada million`
- **Brownfield/adaptive reuse:** redevelopment, adaptive reuse, conversion residential, revitalization
- **Sector-specific:** mine approved, pipeline approved, LNG project, data centre, battery plant, SMR, transit extension, hospital construction, affordable housing
- **French language:** projet majeur, réaménagement Québec, construction approuvé Québec
- **Status changes:** project delayed, cost overrun, project cancelled

---

## Tier 13 — Industry Trade RSS

Included in Tier 4 RSS feeds (22 industry trade feeds listed above).

---

## Tier 14 — University/Institutional Capital Plans (20 institutions)

**File:** `institutional_capital.py`

### U15 Research Universities

| Institution | Province | URL |
|---|---|---|
| University of Toronto | ON | `https://www.fs.utoronto.ca/capital-projects/` |
| UBC | BC | `https://planning.ubc.ca/` |
| McGill University | QC | `https://www.mcgill.ca/facilities/` |
| Université de Montréal | QC | `https://di.umontreal.ca/` |
| University of Alberta | AB | `https://www.ualberta.ca/facilities-operations/` |
| University of Calgary | AB | `https://www.ucalgary.ca/facilities/` |
| McMaster University | ON | `https://facilities.mcmaster.ca/` |
| University of Ottawa | ON | `https://www.uottawa.ca/facilities/` |
| Université Laval | QC | `https://www.ulaval.ca/` |
| Queen's University | ON | `https://www.queensu.ca/pps/` |
| University of Manitoba | MB | `https://umanitoba.ca/physical-plant/` |
| Dalhousie University | NS | `https://www.dal.ca/dept/facilities-management.html` |
| University of Saskatchewan | SK | `https://facilities.usask.ca/` |
| Western University | ON | `https://www.uwo.ca/facilities/` |
| University of Waterloo | ON | `https://uwaterloo.ca/plant-operations/` |

### Major Polytechnics

| Institution | Province | URL |
|---|---|---|
| BCIT | BC | `https://www.bcit.ca/about/` |
| SAIT | AB | `https://www.sait.ca/about-sait` |
| George Brown College | ON | `https://www.georgebrown.ca/about` |

### Healthcare Research Institutions

| Institution | Province | URL |
|---|---|---|
| SickKids — Project Horizon | ON | `https://www.sickkids.ca/en/about/project-horizon/` |
| MUHC (McGill University Health Centre) | QC | `https://muhc.ca/` |

---

## Economic Data APIs

### Bank of Canada Valet API

**Endpoint:** `https://www.bankofcanada.ca/valet/observations/{series_id}/json`

| Series ID | Description |
|---|---|
| V39079 | Overnight policy rate |
| BD.CDN.2YR.DQ.YLD | GoC 2-year bond yield |
| BD.CDN.3YR.DQ.YLD | GoC 3-year bond yield |
| BD.CDN.5YR.DQ.YLD | GoC 5-year bond yield |
| BD.CDN.7YR.DQ.YLD | GoC 7-year bond yield |
| BD.CDN.10YR.DQ.YLD | GoC 10-year bond yield |
| BD.CDN.LONG.DQ.YLD | GoC long bond yield |

### StatCan Web Data Service (WDS)

**Endpoint:** `https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods` (POST)

**National indicators:**

| Vector | Description | Table |
|---|---|---|
| 41690973 | CPI all-items Canada | 18-10-0004-01 |
| 2062815 | Unemployment rate SA | 14-10-0287-01 |
| 62305752 | Quarterly real GDP | 36-10-0104-01 |

**Provincial unemployment (Table 14-10-0287-01):**
NL=2063004, PEI=2063193, NS=2063382, NB=2063571, QC=2063760, ON=2063949, MB=2064138, SK=2064327, AB=2064516, BC=2064705

**Provincial CPI (Table 18-10-0004-01):**
NL=41690914, PEI=41690915, NS=41690916, NB=41690917, QC=41690918, ON=41690919, MB=41690920, SK=41690921, AB=41690922, BC=41690923

**Provincial real GDP annual (Table 36-10-0402-01):**
NL=62464519, PEI=62464824, NS=62465129, NB=62465434, QC=62465739, ON=62466044, MB=62466349, SK=62466654, AB=62466959, BC=62467264

**Industry GDP — 20 NAICS sectors (Table 36-10-0434-01):**

| NAICS | Sector | Vector |
|---|---|---|
| 11 | Agriculture | 65201229 |
| 21 | Mining/Oil & Gas | 65201236 |
| 22 | Utilities | 65201254 |
| 23 | Construction | 65201258 |
| 31-33 | Manufacturing | 65201263 |
| 41 | Wholesale | 65201358 |
| 44-45 | Retail | 65201368 |
| 48-49 | Transportation | 65201381 |
| 51 | Information/Culture | 65201398 |
| 52 | Finance/Insurance | 65201407 |
| 53 | Real Estate | 65201419 |
| 54 | Professional Services | 65201429 |
| 55 | Management | 65201441 |
| 56 | Admin/Waste | 65201442 |
| 61 | Education | 65201452 |
| 62 | Health Care | 65201457 |
| 71 | Entertainment | 65201463 |
| 72 | Accommodation/Food | 65201468 |
| 81 | Other Services | 65201471 |
| 91 | Public Administration | 65201476 |

**StatCan Key Indicators JSON feed:**
`https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ.json` (71 national indicators)

### CMHC Housing Starts

Scrapes monthly news release pages:
`https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/{year}/housing-starts-{month}-{year}`

### FRED (Federal Reserve Bank of St. Louis)

**Endpoint:** `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}` (no API key)

| Series | Description |
|---|---|
| DFF | US Federal Funds effective rate |
| UNRATE | US unemployment rate |
| CPIAUCSL | US CPI all urban |
| A191RL1Q225SBEA | US real GDP growth QoQ annualized |
| GBRCPIALLMINMEI | UK CPI all items YoY |
| LRHUTTTTGBM156S | UK harmonised unemployment rate |
| CLVMNACSCAB1GQGB | UK real GDP QoQ |
| CLVMNACSCAB1GQEA19 | EA19 real GDP QoQ |

### ECB Statistical Data Warehouse

**Endpoint:** `https://data-api.ecb.europa.eu/service/data/{dataflow}/{key}?format=jsondata&lastNObservations=1`

| Dataflow | Key | Description |
|---|---|---|
| FM | B.U2.EUR.4F.KR.DFR.LEV | ECB deposit facility rate |
| ICP | M.U2.N.000000.4.ANR | Euro Area HICP YoY |
| LFSI | M.I8.S.UNEHRT.TOTAL0.15_74.T | Euro Area unemployment rate |

### Bank of England

**Endpoint:** `https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp`
**Series:** IUMABEDR (BoE Bank Rate)

### World Bank Open Data

**Endpoint:** `https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}?format=json&mrv=5`

| Country | Indicator | Description |
|---|---|---|
| CHN | NY.GDP.MKTP.KD.ZG | China GDP growth annual % |
| CHN | FP.CPI.TOTL.ZG | China CPI inflation annual % |

### Yahoo Finance (yfinance)

**Commodities (21 tickers):**

| Category | Tickers |
|---|---|
| Energy | CL=F (WTI), BZ=F (Brent), NG=F (Nat Gas), MTF=F (Coal), PN=F (Propane) |
| Precious Metals | GC=F (Gold), SI=F (Silver), PL=F (Platinum), PA=F (Palladium) |
| Base Metals | HG=F (Copper), ALI=F (Aluminum) |
| Grains | ZW=F (Wheat), ZC=F (Corn), ZR=F (Rice), ZS=F (Soybeans) |
| Softs | KC=F (Coffee), CC=F (Cocoa), SB=F (Sugar), CT=F (Cotton) |
| Oils & Meals | ZL=F (Soybean Oil), ZM=F (Soybean Meal) |

**Equity Indices (7):** ^GSPTSE (TSX), ^GSPC (S&P 500), ^IXIC (NASDAQ), ^DJI (Dow Jones), ^FTSE (FTSE 100), ^GDAXI (DAX), ^N225 (Nikkei 225)

**FX Pairs (4):** CADUSD=X, EURUSD=X, USDCNY=X, USDJPY=X

---

## AI / Enrichment Services

| Service | Role | Budget |
|---|---|---|
| Gemini 2.5 Flash (no grounding) | Classification, extraction, RSS processing | Free tier (unlimited) |
| Claude Sonnet 4.5 | All reasoning — briefing, commentary, analysis | ~$55/year |
| Tavily Search API | Targeted enrichment (cost-finding, verification, tracking) | 1,000 credits/month (free tier) |

---

## Key People Tracking

**File:** `key_people_tracker.py`

15 RSS feeds in `rss_feeds.json` `key_people` category (all bypass filters), plus 4 federal minister feeds via `io.canada.ca` Atom API:

- Minister of Finance
- Minister of Housing and Infrastructure
- Minister of Energy and Natural Resources
- Minister of Transport

---

## Summary

| Category | Count |
|---|---|
| Google News RSS queries | 759 |
| RSS feeds | 201 |
| Federal registry scrapers | 9 |
| Provincial EA scrapers | 10 |
| Municipal dev app scrapers | 15 CMAs |
| Institutional capital scrapers | 20 |
| Economic API series (BoC + StatCan + FRED + ECB + BoE + World Bank) | 70+ vectors |
| Yahoo Finance tickers | 32 |
| Google Alert queries | 25 |
| Lobbyist registry | 1 |
| SEDAR+ | 1 |
| GDELT queries | ~200 |
| Tavily enrichment budget | 1,000/month |
| **Total distinct source endpoints** | **~1,100+** |
