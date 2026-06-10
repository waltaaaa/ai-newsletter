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
