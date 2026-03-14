# Discovery Audit — Configuration Inventory

> All discovery-related configuration extracted from the CAN-MACRO pipeline.
> Generated 2026-03-13 for gap analysis.

---

## Files in This Directory

### Full Config Files (copied as-is)
| File | Source | Description |
|------|--------|-------------|
| `compound_queries_final.json` | Root | 759 compound queries (province × sector × CMA × cluster) |
| `rss_feeds.json` | Root | 201+ RSS feed URLs across 6 categories |
| `pipeline_config.py` | Root | Model routing, GDP thresholds, NAICS map, dedup config |
| `article_filter.py` | Root | Full 6-layer filter with all keyword sets |

### Extracted Configuration (relevant sections only)
| File | Source | What's Extracted |
|------|--------|------------------|
| `gdelt_config_extract.txt` | `gdelt_monitor.py` | 200 queries: 13 provinces × 5 kw, 30 CMAs × 2 kw, 20 sectors × 2 kw, 30 companies, 5 catchall, 8 economy |
| `google_alerts_config_extract.txt` | `google_alerts.py` | 22 recommended alert queries (not yet configured as feeds) |
| `google_news_rss_config_extract.txt` | `google_news_rss_search.py` | 18 sector keyword maps, province names, query shortening pattern |
| `article_filter_keywords_extract.txt` | `article_filter.py` | 66 Cat A project keywords, 26 Cat B economic keywords, 30 Cat C status keywords, 80 negative keywords |
| `municipal_dev_apps_config_extract.txt` | `municipal_dev_apps.py` | 15 CMAs: 4 API (Vancouver, Calgary, Edmonton, Winnipeg) + 11 HTML portals |
| `institutional_capital_config_extract.txt` | `institutional_capital.py` | 20 institutions: 15 U15 universities + 3 polytechnics + 2 healthcare |
| `gov_sources_config_extract.txt` | `gov_sources.py` | 19 scrapers: 8 federal + 9 provincial EA + 2 securities/crown corp |
| `key_people_config_extract.txt` | `key_people_tracker.py` | 39 people tracked: 5 federal + 13 premiers + 15 mayors + 6 crown corp; 18 active RSS feeds |
| `lobbyist_config_extract.txt` | `lobbyist_registries.py` | 27 project keywords, 10 subject categories, sector inference rules |
| `capacity_queries_config_extract.txt` | `capacity_queries.py` | 115 queries: 15 T2 provincial + 50 T3 CMA + 25 T5 federal + 25 T6 emerging |
| `known_project_sweep_config_extract.txt` | `known_project_sweep.py` | ~208 sweep queries + 47 hardcoded seed projects with values |
| `statcan_permits_config_extract.txt` | `statcan_permits.py` | 20 CMA permit vectors, anomaly threshold (3.0x), Table 34-10-0066-01 |

---

## Discovery Pipeline Summary

### Tier Coverage

| Tier | Source | Queries/Feeds | Cost | Config File |
|------|--------|---------------|------|-------------|
| 1 | Government registries | 19 scrapers | Free | `gov_sources_config_extract.txt` |
| 2 | Google News RSS | 759 queries | Free | `compound_queries_final.json`, `google_news_rss_config_extract.txt` |
| 3 | GDELT DOC 2.0 | ~200 queries | Free | `gdelt_config_extract.txt` |
| 4 | RSS feeds | 201+ feeds | Free | `rss_feeds.json` |
| 5 | Provincial EA registries | 9 scrapers | Free | `gov_sources_config_extract.txt` |
| 6 | SEDAR+ filings | 1 scraper | Free | `gov_sources_config_extract.txt` |
| 7 | Crown corps | 2 scrapers | Free | `gov_sources_config_extract.txt` |
| 8 | Canada Energy Regulator | 1 scraper | Free | `gov_sources_config_extract.txt` |
| 9 | StatCan building permits | 20 CMAs | Free | `statcan_permits_config_extract.txt` |
| 10 | Lobbyist registries | 1 scraper | Free | `lobbyist_config_extract.txt` |
| 11 | Municipal dev apps | 15 CMAs | Free | `municipal_dev_apps_config_extract.txt` |
| 12 | Google Alerts | 22 recommended | Free | `google_alerts_config_extract.txt` |
| 13 | Industry trade RSS | ~15 feeds | Free | `rss_feeds.json` (industry category) |
| 14 | Institutional capital | 20 institutions | Free | `institutional_capital_config_extract.txt` |
| + | Key people RSS | 18 active feeds | Free | `key_people_config_extract.txt` |
| + | Capacity scheduler | ~115 queries | Free | `capacity_queries_config_extract.txt` |
| + | Known project sweep | ~208 + 47 seeds | Free | `known_project_sweep_config_extract.txt` |

### Filter Stack
| Layer | What | Keywords | Config File |
|-------|------|----------|-------------|
| L1 | Government source bypass | — | `article_filter.py` |
| L2 | Dollar-value bypass | ≥ province threshold | `pipeline_config.py` |
| L3 | Below-threshold dampener | — | `article_filter.py` |
| L4 | Keyword co-occurrence | 66 project + 26 economic + 30 status | `article_filter_keywords_extract.txt` |
| L5 | Negative keywords | 80 reject terms (crime/sports/weather) | `article_filter_keywords_extract.txt` |
| L6 | Gemini Flash classification | uncertain = RELEVANT | `article_filter.py` |

---

## Geographic Coverage

### Provinces with Full Coverage (EA + Municipal + RSS + Queries)
ON, QC, AB, BC, SK, MB, NS, NB, NL

### Provinces with Partial Coverage
- PE: Municipal app scraper, no provincial EA scraper
- YT: YESAB EA scraper, no municipal
- NT: MVRB EA scraper, no municipal
- NU: No EA scraper, no municipal

### CMAs Covered by Municipal Dev Apps (15)
Vancouver, Calgary, Edmonton, Winnipeg, Toronto, Ottawa,
Montreal, Hamilton, Halifax, Quebec City, Saskatoon, Regina,
St. John's, Fredericton, Charlottetown

### CMAs Covered by StatCan Permits (20)
Toronto, Montreal, Vancouver, Calgary, Edmonton, Ottawa,
Winnipeg, Quebec City, Hamilton, Kitchener, London, Halifax,
Victoria, Windsor, Saskatoon, Regina, St. John's, Kelowna,
Abbotsford, Barrie

### CMAs in GDELT Queries (30)
Toronto, Montreal, Vancouver, Calgary, Edmonton, Ottawa,
Winnipeg, Quebec City, Hamilton, Kitchener Waterloo,
London Ontario, Halifax, Victoria BC, Windsor Ontario, Oshawa,
Saskatoon, Regina, St Catharines Niagara, Barrie Ontario, Kelowna,
Abbotsford, Sherbrooke, Guelph, Moncton, Saint John NB,
St Johns NL, Fredericton, Saguenay, Trois-Rivieres, Brantford

### CMAs in Capacity Queries — Top 10
Toronto, Montreal, Vancouver, Calgary, Edmonton,
Ottawa-Gatineau, Winnipeg, Quebec City, Hamilton, Halifax

### CMAs in Capacity Queries — Medium 20
Kitchener-Waterloo, Victoria, Saskatoon, Regina, St. John's,
London, Windsor, Oshawa-Durham, Barrie, Kelowna,
Moncton, Saint John, Sudbury, Thunder Bay, Lethbridge,
Red Deer, Nanaimo, Kamloops, Brantford, Guelph

---

## Potential Gap Areas (for analysis)

### No Coverage
- **NU (Nunavut):** No EA scraper, no municipal scraper
- **PE (PEI):** No EA scraper
- **Mayors:** 15 tracked but 0 have RSS feeds configured
- **Crown corp leaders:** 6 tracked but 0 have RSS feeds configured
- **Google Alerts:** 22 recommended but 0 actually configured as RSS feeds

### Limited Coverage
- **GDELT:** HTTP-only (HTTPS blocked by ISP), bail-out after 3 failures — often returns nothing
- **SEDAR+:** Blocks automated requests, relies on Tavily extraction as fallback
- **HTML portal cities (11):** Generic scraping heuristics — may miss city-specific page structures
- **Institutional:** 20 institutions, but page structures vary widely — hit-or-miss extraction
- **French coverage:** Limited to QC, NB, NS (light), PE (light), ON (light) in compound queries
- **Northern territories:** Minimal coverage beyond EA registries

### Sector Gaps in Known Project Seeds
- **Agriculture (0 seeds):** No hardcoded projects
- **Forestry (0 seeds):** No hardcoded projects
- **Telecom (0 seeds):** No data centre or broadband seeds
- **Tourism/culture (2 seeds):** Only Winnipeg
- **Indigenous (1 seed):** Only Wehwehneh Bahgahkinahgohn
- **Environment (1 seed):** Only Diavik Mine Closure
