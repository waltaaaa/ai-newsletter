# Source endpoints — live verification COMPLETED 2026-06-09

The live-verification pass this document called for was executed on 2026-06-09
from a network-connected session. Every endpoint below was probed through the
shared `http_client`; dead endpoints were re-resolved (WebSearch + re-probe)
and the code updated. The in-code `TODO(patch-1.2 live-verify)` markers have
been replaced with `Live-verified 2026-06-09` comments at each fix site.

Systemic fix found during the pass: `http_client` advertised
`Accept-Encoding: br` without a brotli decoder installed, which made every
brotli-preferring host (notably ArcGIS Online) return undecodable bytes.
`br` removed from the header.

## D-7 — Provincial EA registries: RESOLVED

| Source | Outcome |
|--------|---------|
| **BC EAO** | Old `/api/v2/projects` 404; suspected `api-public.` host is DNS-dead. **Fixed:** EPIC public-search API `https://projects.eao.gov.bc.ca/api/public/search?dataset=Project&pageNum=0&pageSize=1000` returns the exact `[{searchResults, meta}]` shape the parser expects. Live yield: **358 projects** (133 Approved / 119 Under Review / 74 Cancelled / 32 Completed). |
| **NB EIA** | GNB migrated to `www.gnb.ca` under `/en/topic/environment-resources/`; relative links 404 on the old `www2` host (root cause of the dead anchors). **Fixed:** scraper now targets `projects/current.html` (one `<h2>` per project) with a scoped landing-page crawl as fallback; sub-links resolve via `urljoin`. Live yield: 1 project (NB Power ARC SMR) — NB genuinely has one current EA review. The underscore-variant URL guess from the audit is the one that 404s. |
| **IWK Health** (Tier 14) | TLS still fails on `www.iwk.nshealth.ca` (broken chain server-side, certifi can't fix) AND `www.iwkhealth.ca` (hostname-mismatched cert). **Fixed:** org moved to apex `https://iwkhealth.ca/news` — 200. |

## D-8 — Tiers 13/14: RESOLVED (2 hosts remain bot-blocked)

Browser-UA cleared most 403s as predicted. The 404s were genuine page moves,
all re-resolved and verified 200 through `http_client` (see per-entry comments
in `institutional_capital.py` / `municipal_dev_apps.py`):

- **Airports:** YYC `/en-us/media-centre/news-releases`; YOW `/en/corporate/media-centre/press-releases`; Winnipeg moved domains `waa.ca → ywg.ca/en/newsroom/`; Halifax Stanfield `/news-releases/`; YVR newsroom moved to `https://news.yvr.ca/` (no bot block).
- **Ports:** Thunder Bay TLD `.com → .ca`; Vancouver Fraser `/about/news`; Montreal nested `/en/the-port-of-montreal/news/news` — **still 403 to all non-browser clients (TLS fingerprinting)**; Halifax moved domains to `porthalifax.ca/media-centre/` — **also still 403 (aggressive WAF, even Wayback is blocked)**. Both URLs are correct and kept; health logs will show the 403s until their WAFs relax.
- **Transit:** Edmonton `/ets/transit-news`.
- **Universities / colleges / health (Tier 14):** 14/15 re-resolved and verified 200 through `http_client` — Queen's (`/facilities/`), U Manitoba (`/facilities/`), uOttawa (projects-construction page), Western (`/fm/`), Dalhousie (campus-development), Humber (`/today/media-releases`), Mohawk (`/about/news`), NAIT (`/newsroom` — listing is JS-rendered), Seneca (media-releases under news-and-events), BC Children's (`/about-us/current-projects`), Eastern Health → **NL Health Services** (`nlhealthservices.ca/news-centre/`), Sask Health (`/news-events/news`), Sunnybrook (`/newsroom/`). **Conestoga** moved to `blogs1.conestogac.on.ca/news/` but that host serves an incomplete TLS chain (fails certifi; browsers tolerate it) — correct URL kept, dark until they fix the chain. **George Brown** is entirely Akamai-blocked (403 on every path incl. robots.txt) — no unblocked path exists; coverage via Google News RSS.
- **Municipal:** Hamilton, Oshawa, Regina, Saskatoon, St. Catharines, St. John's, Fredericton, Charlottetown, Barrie, Abbotsford, Quebec City page moves applied. **Kitchener** now uses its ArcGIS `Building_Permits` FeatureServer (carries `CONSTRUCTION_VALUE`; new `arcgis` approach added). Kelowna remains bot-blocked (403). London/Victoria machine endpoints exist but carry **no dollar-value fields**, so they cannot pass the value gate — HTML viewer pages kept.

## D-9 — Procurement monitor: RESOLVED (all four sources)

| Source | Outcome |
|--------|---------|
| **Open Canada** | Old CKAN package id gone; dataset is `d8f85d91-7dec-4fd1-8055-483b77225d8b`, but its full CSV is **627 MB**. **Fixed:** queries the active CKAN **datastore API** (resource `fac950c0-...`, 1.29M rows) paginated `sort=contract_date desc` with a junk-future-date guard. `datastore_search_sql` is disabled (400) — filtering stays client-side. Proactive disclosure publishes **quarterly**, so the scan uses `max(days_back, 90)`. Live yield: 2 construction contracts ≥$5M (2026-03). |
| **BuyAndSell** | `buyandsell.gc.ca` is DNS-dead; CanadaBuys has **no tender RSS**. **Fixed:** CanadaBuys open-data CSVs (`newTenderNotice-…csv` / `openTenderNotice-…csv`, both 200, stable bilingual headers, province via `regionsOfDelivery`). Old RSS kept as fallback (additive). No award-notice CSV exists under any probed name. |
| **Ontario BPS** | CKAN package **removed upstream**; `package_search` finds no open-data successor (Ontario tenders moved to the closed Jaggaer portal). Attempt kept (cheap; in case it returns); ON coverage flows from CanadaBuys Ontario-delivery rows. |
| **BC Bid** | Legacy `open.dll/RSSFeed` retired; new Ivalua platform has no public feed (every path returns the JS app shell). **Fixed:** falls back to CanadaBuys open-tenders CSV filtered to British Columbia delivery. Live yield: 56 BC construction opportunities. |

## D-5 / D-15 — StatCan vectors: RESOLVED

| Series | Outcome |
|--------|---------|
| Provincial building permits | Audit pointed at Table 34-10-0066 — **inactive since 2023-10** (and successor 34-10-0285 archived 2025-03). Resolved against the active **34-10-0292** (value of permits, total structure+work, SA current, $ thousands). 10 vectors populated in `_PROV_BUILDING_PERMITS_VIDS`, validated (refPer 2026-03; ON $4.87B/mo). Fetch + format loop added to `get_provincial_indicators` (renders `$X.XXB`/`$XM`). |
| Provincial wage growth | Resolved against **14-10-0063** (avg hourly wage, both FT/PT, all industries, total gender, 15+; active to 2026-05). 10 vectors in `_PROV_WAGE_VIDS`, validated. Surfaced as YoY % (same construction as CPI). |
| `agri_exports` frozen at 2003 (+ energy/mineral/forestry) | Root cause found: the old vectors pointed at Table 12-10-0129 = "Canadian domestic export **concentration**" (ratios/indexes ending 2003) — wrong cube entirely. Re-resolved against the active **12-10-0163** (merchandise trade by commodity, BoP, SA, $M). All four new vectors validated (refPer 2026-04: energy $19.9B, agri $5.3B, forestry $3.6B, mineral $2.4B) and all fit the `indicator_validator` ranges. |

Gotcha recorded for future vector work: `getSeriesInfoFromCubePidCoord`
responses are **not returned in request order** — always match results back by
the echoed `coordinate`, or province/commodity vectors get scrambled (the
scramble produces individually-plausible but swapped values).

## D-10 — Policy feeds

Code-only fixes were already in patch-1.2. The per-feed zero-count review still
needs a full pipeline run (`[POLICY] Per-feed counts:` lines) — unchanged.

# quality-pass-1.4 — G3/G4 new-source probes (2026-06-10)

Every endpoint below was live-probed through the shared `http_client` (or
`requests` with the browser UA for POST) on 2026-06-10 before any scraper was
written.

## G3 — Northern & Indigenous registries

| Source | Probe result | Verdict |
|--------|--------------|---------|
| **NIRB (Nunavut)** | `nirb.ca` is server-rendered Drupal (200). `/project-search` and `/active-reviews` 404. Public registry is an iframe to `/portal/registry-search.php` (PHP, server-side). **POST** `/portal/registry-search-results.php` with `{lang:en, action:search, whattosearchfor:project, searchonlyactive:on}` returns 200 (~10.7 MB) embedding a `geometry_layer = eval('([...])')` JS array with `application_id`, `nirb_file_number`, `application_date`, `project_name`, `proponent_name`, `activity_type` — fully parseable without JS. Project URL pattern `https://www.nirb.ca/project/{application_id}` (200). | **WORKING (POST + embedded JSON)** |
| **MVLWB (NWT)** | `mvlwb.com/registry` 200, server-rendered Drupal table (50 rows/page): Company / Activity / File Number / Start Date / Expiry Date, row links `https://mvlwb.com/registry/{file}`. Default sort is oldest-first; `?search_api_views_fulltext=&order=date_start&sort=desc` returns the 50 most recent authorizations (verified: May 2026 permits for GNWT-INF, Teck Metals, Fortune Minerals, Rackla Metals). | **WORKING (GET, sorted desc)** |
| **ISC Indigenous Community Infrastructure** | open.canada.ca CKAN dataset `62155d6f-9167-4972-b77c-b90734b628dc` ("Indigenous Community Infrastructure", org `isc-sac`). The earlier candidate "National First Nations infrastructure investment plan" (`66566638-...`) is HTML/PDF-only from 2015-16 — useless. The real resource is `Indigenous_Community_Infrastructure_CSV.zip` on `data.sac-isc.gc.ca` (200, application/zip, 1.65 MB, 28,974 rows). Columns: Province/Territory, Community, Internal Project Number, Infrastructure Category, Project Name, Description, Project Status (Ongoing 12,451 / Completed 16,523), ISC Departmental Investment (dollar values only on ~half the rows, essentially never on Ongoing rows — value-floor filtering is impossible; keyword+category filtering used instead). | **WORKING (CSV-in-zip via CKAN)** |

### G3 — Indigenous development corporation newsrooms (watchlist probes)

Verified 200 with substantive HTML: Inuvialuit (`inuvialuit.com/news`), Nunasi
(`nunasi.com/news/`), Athabasca Basin (`athabascabasin.ca/news/`), Des Nedhe
(`desnedhe.com/news/`), Fort McKay Group (`fortmckaygroup.com/news/`),
Membertou (`membertoucorporate.ca/news`), Nch'ḵay̓ (`www.nchkay.com/news/` —
apex host has a hostname-mismatched cert, www works), Haisla
(`haisla.ca/news/` — `haisea.ca` is DNS-dead), Six Nations of the Grand River
(`sndevcorp.ca/news/`), Whitecap (`whitecapdevcorp.com/news/`), Tłı̨chǫ
(`tlicho.ca/news` — `tlichoinvestment.com` DNS-dead), Penticton Indian Band
(`pibdc.ca/news/`), Makivik → rebranded **Makivvik**: `makivvik.ca/news` 200
(`makivik.org/news/` and all news paths 404), Miawpukek Horizon — own domain
503 on every path; parent venture newsroom `horizonmaritime.com/news` 200.
**Osoyoos Indian Band Development Corp**: root `oibdc.ca` 200 but no
news/media path exists (404) — entry added with `newsroom_url: null`
(Google News RSS site-search coverage only).

## G4 — Procurement remainder

| Source | Probe result | Verdict |
|--------|--------------|---------|
| **SEAO (Québec)** | Données Québec CKAN: `package_show?id=systeme-electronique-dappel-doffres-seao` (200). Resources are weekly `hebdo_YYYYMMDD_YYYYMMDD.json` + monthly `mensuel_*.json` files in **OCDS** (Open Contracting Data Standard) format. Download URL = resource `url` + `download/{name}` (verified 200). Latest weekly file: 5,767 releases, 4,205 with awards; `tender.mainProcurementCategory` distribution works=1,460 / services=2,512 / goods=1,537. Each release carries `tender.title` (French), `buyer.name`, `awards[].value.amount` (CAD) and `awards[].suppliers[].name`. | **WORKING (OCDS JSON weekly files)** |
| **DCC (Defence Construction Canada)** | `dcc-cdc.gc.ca` 200; `/industry/contract-awards` 404 (JSON backend error page). Real listing: "Contract Activity" page links a PDF on the corporate MFT share: `https://dccmft.dcc-cdc.gc.ca/?u=contracts_public&p=public&path=/Recently_Awarded_Contracts.pdf` — 200, application/pdf, ~140 KB, 9 pages, regenerated continuously (probe copy dated 2026-06-10). Tabular text extracts cleanly with PyMuPDF (`fitz`, already in the venv): Project Number / Contract Number / MERX Number / Description / Location / Award Date / Award Amount / Contractor / City / Province. | **WORKING (PDF via fitz — no HTML/CSV alternative exists)** |
| **SaskTenders** | `sasktenders.ca` apex times out (25 s); `www.sasktenders.ca/content/public/Search.aspx` 200 but it is a 1.7 MB ASP.NET WebForms page — results require `__VIEWSTATE` postbacks, no RSS, no open-data export. | **DARK — rely on CanadaBuys SK delivery rows** (documented inline like ontario_bps) |
| **Alberta Purchasing Connection** | `purchasingconnection.ca` 200 but serves an Angular SPA shell (`data-beasties-container`, empty body); no public API or RSS discovered. | **DARK — rely on CanadaBuys AB delivery rows** (documented inline like ontario_bps) |
