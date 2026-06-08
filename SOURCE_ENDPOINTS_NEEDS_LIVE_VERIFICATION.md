# Source endpoints needing live re-verification — patch v1.2

The structural fixes in patch v1.2 (shared `http_client.py` with a browser
User-Agent + certifi TLS + per-host retry, BC EAO querystring repair,
government_bypass, per-source/per-feed counts, and tier DEGRADE logging) clear
the **systemic** root causes of the silent-zero scrapers (uniform 403 bot-blocks
and `CERTIFICATE_VERIFY_FAILED`).

The endpoints below cannot be confirmed from this offline environment. Each is
flagged in-code with `# TODO(patch-1.2 live-verify): ...`. An operator with
network access must re-resolve and confirm them. **Do not mark an endpoint
"fixed" until a live probe returns a 2xx with the expected body shape.**

How to test (all from `C:/AI_newsletter/backend`):

```
# Quick status + content-type probe using the shared client:
./.venv/Scripts/python.exe -c "import http_client; r=http_client.get('<URL>'); print(r.status_code, r.headers.get('content-type'), len(r.content))"

# JSON endpoints — confirm the parsed shape:
./.venv/Scripts/python.exe -c "import http_client,json; d=http_client.get_json('<URL>'); print(type(d), (list(d)[:5] if isinstance(d,dict) else len(d)))"
```

When confirmed: swap the `_*` URL constant to the verified value (keep the old
one as a commented fallback — CLAUDE.md is additive-only, never delete a source)
and remove the corresponding `TODO(patch-1.2 live-verify)` comment.

---

## D-7 — Provincial EA registries (`gov_sources.py`)

| Source | Current URL (in code) | Suspected correct URL | How to verify |
|--------|-----------------------|-----------------------|---------------|
| **BC EAO** | `https://www.projects.eao.gov.bc.ca/api/v2/projects?fields=...&pageSize=200` (leading `&` bug already fixed) | `https://api-public.eao.gov.bc.ca/api/projects?fields=...&pageSize=200` — kept in code as `_BC_EAO_API_CANDIDATE` | GET the candidate; expect HTTP 200 JSON with `searchResults[]` and per-project `eacDecision`/`proponent` keys. If shape matches, set `_BC_EAO_API = _BC_EAO_API_CANDIDATE`. |
| **NB EIA** | `https://www2.gnb.ca/content/gnb/en/departments/elg/environment/content/environmental_impactassessment.html` | underscore variant `.../environmental_impact_assessment.html` (per D-7 audit), then re-resolve the sub-page anchors (determination / comprehensive review) | GET the landing page; confirm 200 and that the determination/comprehensive-review sub-page links resolve (not 404). Update `_NB_EIA_URL` + anchor-matching keywords if the page structure changed. |
| **IWK Health** (Tier 14, `institutional_capital.py`) | `https://www.iwk.nshealth.ca/news` | same URL — the failure was TLS (`CERTIFICATE_VERIFY_FAILED`), now fixed by certifi verification in `http_client` | GET via `http_client`; expect 200 with no SSL error. If it now succeeds, no URL change needed — just confirm. |

---

## D-8 — Tiers 13/14 airport / port / transit (403/404)

403s were uniform bot-blocks — the browser UA in `http_client` should clear
them. 404s are stale paths and need manual re-resolution.

### Tier 14 institutional (`institutional_capital.py`, `UNIVERSITY_SOURCES`)

| Source | Current URL | Failure (pre-patch) | How to verify / re-resolve |
|--------|-------------|---------------------|----------------------------|
| Vancouver Airport Authority (YVR) | `https://www.yvr.ca/en/media` | 403 | Re-probe with browser UA; if still non-200, find current media/news path on yvr.ca |
| Calgary Airport Authority (YYC) | `https://www.yyc.com/en/media` | 404 | Re-resolve current media/news URL on yyc.com |
| Ottawa International Airport (YOW) | `https://yow.ca/en/corporate/media` | 404 | Re-resolve current media path on yow.ca |
| Winnipeg Airport Authority | `https://www.waa.ca/media` | 404 | Re-resolve current news/media path on waa.ca |
| Halifax Stanfield International Airport | `https://halifaxstanfield.ca/news` | 404 | Re-resolve current news path |
| Vancouver Fraser Port Authority | `https://www.portvancouver.com/news-and-media/` | 403 | Re-probe with browser UA; re-resolve if still failing |
| Port of Montreal | `https://www.port-montreal.com/en/news` | 403 | Re-probe with browser UA |
| Port of Halifax | `https://www.portofhalifax.ca/news/` | 403 | Re-probe with browser UA |
| Port of Thunder Bay | `https://www.portofthunderbay.com/news/` | 404 | Re-resolve current news path |
| Edmonton Transit Service | `https://www.edmonton.ca/ets/ets-news` | 404 | Re-resolve current ETS news path on edmonton.ca |

> All other airport/port/transit/university/healthcare URLs in
> `UNIVERSITY_SOURCES` should be re-probed once with the new browser UA; any
> that still return >=400 need the same per-authority path re-resolution.

### Tier 13 municipal (`municipal_dev_apps.py`, `MUNICIPAL_SOURCES`)

| Source | Current URL | Issue | How to verify / re-resolve |
|--------|-------------|-------|----------------------------|
| Kitchener | `https://open-kitchenergis.opendata.arcgis.com/api/download/v1/items/3ee5...e508/csv?layers=0` | ArcGIS download URL — confirm item id + that it returns CSV (not 404/HTML) | GET; expect `text/csv`. Re-resolve the ArcGIS item id if 404. |
| London ON | `https://opendata.london.ca/datasets/building-permits/explore` | `/explore` is a human viewer page, not a data API | Find the dataset's GeoJSON/CSV API endpoint (ArcGIS `query?f=json` or download URL). |
| Victoria | `https://opendata.victoria.ca/datasets/development-tracker/explore` | `/explore` viewer page, not data API | Same as London — resolve the underlying ArcGIS/Socrata data endpoint. |
| HTML-portal cities (Toronto, Ottawa, Montreal OCPM, Hamilton, Halifax, Quebec City, Saskatoon, Regina, St. John's, Fredericton, Charlottetown, Oshawa, St. Catharines, Moncton, Kelowna, Barrie, Guelph, Abbotsford) | see `MUNICIPAL_SOURCES` | mix of 403 (now likely cleared by browser UA) and generic HTML scraping that may not match the live page structure | Re-probe each with the new UA; for any that 404, re-resolve the current planning/development-applications path; spot-check that `_scrape_html_portal` still extracts dollar values from the live markup. |

---

## D-9 — Procurement monitor (`procurement_monitor.py`)

| Source | Current URL / id | Issue | Suspected correct endpoint | How to verify |
|--------|------------------|-------|----------------------------|---------------|
| **Open Canada** | CKAN `package_show?id=proactive-disclosure-contracts` | 404 — package id dead/renamed | new contracts search API `https://search.open.canada.ca/contracts/` (resolve JSON/CSV download), or re-resolve CKAN id via `package_search?q=proactive+disclosure+contracts` | Run `package_search` to find the live id; confirm a CSV resource downloads and has `contract_value`/`description_en` columns. |
| **BuyAndSell** | `https://buyandsell.gc.ca/procurement-data/feed/rss` | migrated to `canadabuys.canada.ca` | candidate tender feed under `https://canadabuys.canada.ca/en/tender-opportunities/rss`, or the canadabuys open-data tenders CSV | GET candidate; confirm it parses as RSS/Atom (feedparser `entries` non-empty) or valid CSV. |
| **Ontario BPS** | CKAN `package_show?id=broader-public-sector-business-document-plan` on `data.ontario.ca` | zero rows — confirm id still valid | re-resolve via `data.ontario.ca/api/3/action/package_search?q=broader+public+sector+procurement` | Confirm package resolves and exposes a CSV with `estimated_value`/`procurement_description`. |
| **BC Bid** | `https://www.bcbid.gov.bc.ca/open.dll/RSSFeed?Feed=Construction` | legacy `open.dll` path likely retired with BC Bid platform refresh | current bcbid.gov.bc.ca public opportunities feed/API | GET; confirm RSS/Atom parses with non-empty `entries`. |

---

## D-10 — Policy classifier (`policy_tracker.py`, `provincial_policy_monitor.py`)

No URL re-resolution required for the classifier change itself — the
government_bypass + per-feed counts + parameterised batch are code-only fixes.
However, the per-feed count logging will now reveal which **policy RSS feeds**
are dark. After the first live run, review the `[POLICY] Per-feed counts:` and
`[POLICY] Feeds returning 0 this run:` lines and re-resolve any zero feeds (the
same browser-UA fix may already have revived several). Feeds to watch (reported
empty pre-patch): provincial finance feeds in `provincial_policy_monitor.py`
(`on_finance`, `qc_finance`, `ab_finance`, `mb_finance`, `sk_finance`,
`ns_finance`, `nb_finance`, `nl_finance`) and `federal_budget`
(`https://budget.canada.ca/rss`).
