"""
Government procurement monitor — tracks federal and provincial contract awards
and tender notices for infrastructure, construction, and major capital projects.

Sources (all free, structured data):
1. Open Canada Proactive Disclosure — awarded contracts with values and vendors
2. BuyAndSell.gc.ca RSS — federal tender notices (enhances existing Tier 1)
3. Ontario BPS Supply Chain — Broader Public Sector procurement
4. BC Bid — BC provincial procurement
5. SEAO (Québec) — public procurement (Système électronique d'appels d'offres)
6. Alberta Purchasing Connection — provincial RFPs

All sources are free. No API keys required for public procurement data.
"""
import feedparser
import requests
import json
import csv
import io
import re
from datetime import datetime, timedelta
import logging

# patch-1.2 (D-9): route every procurement fetch through the shared HTTP client.
# All four sources were dark — same root cause as D-8 (stale URLs + default
# python-requests User-Agent tripping bot-blocks on the CKAN portals). The
# browser UA + certifi TLS clears the bot-blocks. Endpoints live-verified
# 2026-06-09: Open Canada now queried via the CKAN datastore API (full CSV is
# ~627 MB); BuyAndSell replaced by the CanadaBuys open-data tender CSVs;
# Ontario BPS dataset removed upstream (no open-data successor); BC Bid legacy
# RSS retired (CanadaBuys BC-delivery rows used as fallback).
import http_client

logger = logging.getLogger(__name__)

# Minimum contract value to track (filter out small purchases)
MIN_CONTRACT_VALUE = 5_000_000  # $5M — focus on major capital projects

# Construction and infrastructure GSIN/UNSPSC codes to filter on
RELEVANT_GSIN_PREFIXES = [
    "R",   # Construction, maintenance, and repair of structures/facilities
    "N",   # Installation of equipment
    "F",   # Natural resources and conservation
    "S",   # Utilities and housekeeping
    "Z",   # Maintenance and repair of equipment
]

CONSTRUCTION_KEYWORDS = [
    "construction", "infrastructure", "bridge", "highway", "transit",
    "building", "renovation", "expansion", "remediation", "demolition",
    "water treatment", "wastewater", "power plant", "transmission line",
    "hospital", "school", "university", "airport", "port", "rail",
    "pipeline", "refinery", "mine", "processing plant", "data centre",
]


def fetch_open_canada_contracts(days_back=30):
    """
    Fetch recent awarded contracts from Open Canada Proactive Disclosure.
    Uses the CKAN API (free, no key required).

    Returns list of contract dicts.
    """
    contracts = []

    try:
        # Live-verified 2026-06-09 (D-9): the old CKAN package id
        # 'proactive-disclosure-contracts' is gone; the dataset moved to
        # 'd8f85d91-7dec-4fd1-8055-483b77225d8b' ("Proactive Publication -
        # Contracts"). Its full CSV is ~627 MB so we no longer download it;
        # the resource has an active CKAN datastore (1.29M rows), queried here
        # page-by-page sorted by contract_date desc until the lookback cutoff.
        # datastore_search_sql is disabled on open.canada.ca (verified 400),
        # so filtering on value/keywords stays client-side.
        url = "https://open.canada.ca/data/api/3/action/datastore_search"
        resource_id = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"  # Contracts over $10,000

        # Proactive disclosure is published QUARTERLY with a reporting lag
        # (verified 2026-06-09: in June the freshest bulk month was March), so
        # a strict 30-day window would be empty most weeks. Scan at least one
        # quarter back; award_date is carried on every row so downstream
        # consumers can still distinguish genuinely-new awards.
        effective_days = max(days_back, 90)
        cutoff = datetime.now() - timedelta(days=effective_days)
        # Rows with garbage future dates (e.g. 2029) sort first; anything more
        # than ~13 months out is treated as junk and never ends the scan.
        junk_horizon = datetime.now() + timedelta(days=400)
        max_pages = 20  # hard stop: 20 x 1000 rows

        reached_cutoff = False
        for page in range(max_pages):
            params = {
                "resource_id": resource_id,
                "limit": 1000,
                "offset": page * 1000,
                "sort": "contract_date desc",
            }
            resp = http_client.get(url, params=params, timeout=30)
            if resp is None or resp.status_code != 200:
                status = 'network' if resp is None else resp.status_code
                print(f"[PROCUREMENT][open_canada] FAILED status={status} (page {page})")
                break

            records = resp.json().get("result", {}).get("records", [])
            if not records:
                break

            for row in records:
                try:
                    row_date = None
                    raw_date = str(row.get("contract_date") or "")[:10]
                    try:
                        row_date = datetime.strptime(raw_date, "%Y-%m-%d")
                    except ValueError:
                        pass

                    # Sorted desc: a valid date older than the cutoff means
                    # every later row is older still.
                    if row_date is not None and row_date < cutoff:
                        reached_cutoff = True
                        break
                    if row_date is None or row_date > junk_horizon:
                        continue

                    value = _parse_value(row.get("contract_value", "0"))
                    if value < MIN_CONTRACT_VALUE:
                        continue

                    description = str(row.get("description_en") or "").lower()
                    if not any(kw in description for kw in CONSTRUCTION_KEYWORDS):
                        continue

                    contracts.append({
                        "source": "open_canada",
                        "vendor": row.get("vendor_name", "Unknown"),
                        "department": row.get("owner_org_title") or row.get("owner_org", ""),
                        "description": row.get("description_en", ""),
                        "value": value,
                        "award_date": raw_date,
                        "province": _infer_province(row),
                        "url": "https://search.open.canada.ca/contracts/",
                    })
                except Exception as e:
                    logger.debug(f"[PROCUREMENT] Skipped row: {e}")

            if reached_cutoff:
                break

        print(f"[PROCUREMENT] Open Canada: {len(contracts)} relevant contracts (>=${MIN_CONTRACT_VALUE:,})")

    except Exception as e:
        print(f"[WARN] Open Canada procurement fetch failed: {e}")

    return contracts


# Live-verified 2026-06-09 (D-9): buyandsell.gc.ca no longer resolves in DNS
# and canadabuys.canada.ca has no tender RSS feed (/en/tender-opportunities/rss
# is 404). CanadaBuys publishes open-data tender CSVs instead — both confirmed
# 200 with a stable bilingual-header schema.
_CANADABUYS_NEW_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
_CANADABUYS_OPEN_TENDERS_CSV = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

# Per-run cache so the BC Bid fallback doesn't re-download the same CSV.
_canadabuys_cache = {}

_REGION_PROVINCE = {
    "british columbia": "BC", "colombie-britannique": "BC",
    "alberta": "AB", "saskatchewan": "SK", "manitoba": "MB",
    "ontario": "ON", "national capital region": "ON", "ottawa": "ON",
    "quebec": "QC", "québec": "QC",
    "nova scotia": "NS", "nouvelle-écosse": "NS",
    "new brunswick": "NB", "nouveau-brunswick": "NB",
    "newfoundland": "NL", "terre-neuve": "NL",
    "prince edward island": "PE", "yukon": "YT",
    "northwest territories": "NT", "nunavut": "NU",
}


def _fetch_canadabuys_rows(url):
    """Download and parse a CanadaBuys open-data tender CSV (cached per run)."""
    if url in _canadabuys_cache:
        return _canadabuys_cache[url]
    resp = http_client.get(url, timeout=40)
    if resp is None or resp.status_code >= 400:
        status = 'network' if resp is None else resp.status_code
        print(f"[PROCUREMENT][canadabuys] FAILED status={status} {url[:80]}")
        return []
    try:
        rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig", errors="replace"))))
    except Exception as e:
        print(f"[PROCUREMENT][canadabuys] CSV parse failed: {e}")
        return []
    _canadabuys_cache[url] = rows
    return rows


def _province_from_cb_row(row):
    """Province code from a CanadaBuys row's delivery region, else from text."""
    region = (row.get("regionsOfDelivery-regionsLivraison-eng") or "").lower()
    for keyword, code in _REGION_PROVINCE.items():
        if keyword in region:
            return code
    return _extract_province_from_text(
        f"{row.get('title-titre-eng', '')} {row.get('tenderDescription-descriptionAppelOffres-eng', '')}"
    )


def fetch_buyandsell_rss():
    """
    Fetch recent federal tender notices. Primary: CanadaBuys open-data CSV
    (new tender notices). The legacy BuyAndSell RSS attempt is retained as a
    fallback per the additive-only rule, though its domain is DNS-dead.
    Filters for construction and infrastructure categories.
    """
    tenders = []

    for row in _fetch_canadabuys_rows(_CANADABUYS_NEW_TENDERS_CSV):
        try:
            title = row.get("title-titre-eng", "")
            summary = row.get("tenderDescription-descriptionAppelOffres-eng", "")
            text = f"{title} {summary}".lower()

            if any(kw in text for kw in CONSTRUCTION_KEYWORDS):
                value = _extract_value_from_text(text)
                if value and value >= MIN_CONTRACT_VALUE:
                    tenders.append({
                        "source": "canadabuys",
                        "title": title,
                        "description": summary,
                        "value": value,
                        "date": row.get("publicationDate-datePublication", ""),
                        "url": row.get("noticeURL-URLavis-eng", ""),
                        "province": _province_from_cb_row(row),
                    })
        except Exception as e:
            logger.debug(f"[PROCUREMENT] Skipped CanadaBuys row: {e}")

    if tenders:
        print(f"[PROCUREMENT] CanadaBuys: {len(tenders)} relevant tenders")
        return tenders

    # Legacy fallback (additive-only; buyandsell.gc.ca DNS-dead as of 2026-06-09)
    rss_urls = [
        "https://buyandsell.gc.ca/procurement-data/feed/rss",
    ]

    for url in rss_urls:
        try:
            # patch-1.2: fetch with browser UA via http_client, then hand the
            # bytes to feedparser (feedparser.parse(url) uses its own default UA
            # which is bot-blocked). Falls back to feedparser-direct on None.
            resp = http_client.get(url, timeout=20)
            if resp is None or resp.status_code >= 400:
                status = 'network' if resp is None else resp.status_code
                print(f"[PROCUREMENT][buyandsell] FAILED status={status}")
                feed = feedparser.parse(url)
            else:
                feed = feedparser.parse(resp.content)
            for entry in feed.entries:
                title = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                text = f"{title} {summary}"

                if any(kw in text for kw in CONSTRUCTION_KEYWORDS):
                    value = _extract_value_from_text(text)
                    if value and value >= MIN_CONTRACT_VALUE:
                        tenders.append({
                            "source": "buyandsell",
                            "title": entry.get("title", ""),
                            "description": entry.get("summary", ""),
                            "value": value,
                            "date": entry.get("published", ""),
                            "url": entry.get("link", ""),
                            "province": _extract_province_from_text(text),
                        })
        except Exception as e:
            print(f"[WARN] BuyAndSell RSS fetch failed: {e}")

    print(f"[PROCUREMENT] BuyAndSell: {len(tenders)} relevant tenders")
    return tenders


def fetch_ontario_bps():
    """
    Fetch Ontario Broader Public Sector procurement notices.
    BPS Supply Chain Secretariat publishes large infrastructure contracts.
    """
    notices = []

    try:
        # Ontario data catalogue — BPS procurement
        # Live-verified DEAD 2026-06-09 (D-9): the CKAN package
        # 'broader-public-sector-business-document-plan' was removed from
        # data.ontario.ca and package_search found no open-data successor
        # (Ontario tenders moved to the closed Ontario Tenders Portal/Jaggaer).
        # The attempt is kept (additive-only, cheap, in case Ontario restores
        # it); Ontario coverage meanwhile flows from the CanadaBuys CSV rows
        # whose delivery region is Ontario.
        url = "https://data.ontario.ca/api/3/action/package_show"
        params = {"id": "broader-public-sector-business-document-plan"}

        resp = http_client.get(url, params=params, timeout=15)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT][ontario_bps] dataset removed upstream (status={status}; "
                  f"verified dead 2026-06-09) — ON coverage via CanadaBuys")
        else:
            data = resp.json()
            resources = data.get("result", {}).get("resources", [])

            csv_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]
            if csv_resources:
                csv_url = csv_resources[-1].get("url")
                csv_resp = http_client.get(csv_url, timeout=30)
                if csv_resp is None or csv_resp.status_code >= 400:
                    status = 'network' if csv_resp is None else csv_resp.status_code
                    print(f"[PROCUREMENT][ontario_bps] CSV download FAILED status={status}")
                    return []
                reader = csv.DictReader(io.StringIO(csv_resp.text))

                for row in reader:
                    value = _parse_value(row.get("estimated_value", "0"))
                    if value >= MIN_CONTRACT_VALUE:
                        desc = row.get("procurement_description", "").lower()
                        if any(kw in desc for kw in CONSTRUCTION_KEYWORDS):
                            notices.append({
                                "source": "ontario_bps",
                                "description": row.get("procurement_description", ""),
                                "organization": row.get("organization_name", ""),
                                "value": value,
                                "province": "ON",
                                "url": "https://data.ontario.ca/dataset/broader-public-sector-business-document-plan",
                            })

        print(f"[PROCUREMENT] Ontario BPS: {len(notices)} relevant notices")
    except Exception as e:
        print(f"[WARN] Ontario BPS fetch failed: {e}")

    return notices


def fetch_bc_bid():
    """
    Fetch BC Bid procurement opportunities.
    BC's public procurement portal for provincial contracts.
    """
    opportunities = []

    try:
        # BC Bid RSS feed for construction category
        # Live-verified DEAD 2026-06-09 (D-9): the legacy open.dll/RSSFeed path
        # 404s and the refreshed BC Bid platform (Ivalua) exposes no public RSS
        # (every page.aspx path returns the same JS app shell). The old attempt
        # is kept (additive-only); on failure, BC coverage falls back to the
        # CanadaBuys open-tenders CSV filtered to British Columbia delivery.
        url = "https://www.bcbid.gov.bc.ca/open.dll/RSSFeed?Feed=Construction"
        # patch-1.2: fetch with browser UA via http_client, then parse the bytes
        # with feedparser. Falls back to feedparser-direct if the fetch fails.
        resp = http_client.get(url, timeout=20)
        if resp is None or resp.status_code >= 400:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT][bc_bid] legacy feed retired (status={status}; "
                  f"verified dead 2026-06-09) — falling back to CanadaBuys BC rows")
            feed = feedparser.parse(url)
        else:
            feed = feedparser.parse(resp.content)

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            value = _extract_value_from_text(f"{title} {summary}")

            opportunities.append({
                "source": "bc_bid",
                "title": title,
                "description": summary,
                "value": value,
                "province": "BC",
                "url": entry.get("link", ""),
                "date": entry.get("published", ""),
            })

        if not opportunities:
            # CanadaBuys fallback: open tenders delivered in BC that match the
            # construction keyword filter (same semantics as the old BC feed —
            # no minimum-value requirement).
            for row in _fetch_canadabuys_rows(_CANADABUYS_OPEN_TENDERS_CSV):
                try:
                    if _province_from_cb_row(row) != "BC":
                        continue
                    title = row.get("title-titre-eng", "")
                    summary = row.get("tenderDescription-descriptionAppelOffres-eng", "")
                    text = f"{title} {summary}".lower()
                    if not any(kw in text for kw in CONSTRUCTION_KEYWORDS):
                        continue
                    opportunities.append({
                        "source": "canadabuys_bc",
                        "title": title,
                        "description": summary,
                        "value": _extract_value_from_text(text),
                        "province": "BC",
                        "url": row.get("noticeURL-URLavis-eng", ""),
                        "date": row.get("publicationDate-datePublication", ""),
                    })
                except Exception as e:
                    logger.debug(f"[PROCUREMENT] Skipped CanadaBuys BC row: {e}")

        print(f"[PROCUREMENT] BC Bid: {len(opportunities)} construction opportunities")
    except Exception as e:
        print(f"[WARN] BC Bid fetch failed: {e}")

    return opportunities


def _parse_value(value_str):
    """Parse a dollar value string into float."""
    if not value_str:
        return 0
    cleaned = re.sub(r'[,$\s]', '', str(value_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0


def _extract_value_from_text(text):
    """Extract dollar values from free text."""
    patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)',
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)',
        r'\$\s*([\d,]+(?:\.\d+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(',', ''))
            if 'billion' in text[match.start():match.end()+10].lower() or 'B' in text[match.start():match.end()+3]:
                value *= 1_000_000_000
            elif 'million' in text[match.start():match.end()+10].lower() or 'M' in text[match.start():match.end()+3]:
                value *= 1_000_000
            return value
    return None


def _extract_province_from_text(text):
    """Simple province extraction from text."""
    province_map = {
        "ontario": "ON", "toronto": "ON", "ottawa": "ON",
        "quebec": "QC", "québec": "QC", "montréal": "QC", "montreal": "QC",
        "british columbia": "BC", "vancouver": "BC", "victoria bc": "BC",
        "alberta": "AB", "calgary": "AB", "edmonton": "AB",
        "saskatchewan": "SK", "saskatoon": "SK", "regina": "SK",
        "manitoba": "MB", "winnipeg": "MB",
        "nova scotia": "NS", "halifax": "NS",
        "new brunswick": "NB", "moncton": "NB",
        "newfoundland": "NL", "labrador": "NL",
    }
    text_lower = text.lower()
    for keyword, province in province_map.items():
        if keyword in text_lower:
            return province
    return None


def _infer_province(row):
    """Infer province from Open Canada contract row."""
    # Try explicit province field first, then description
    province = row.get("province", "")
    if province:
        return province
    return _extract_province_from_text(
        row.get("description_en", "") + " " + row.get("vendor_name", "")
    )


def link_contracts_to_projects(contracts, conn):
    """
    Match procurement contracts to existing projects by vendor name,
    description keywords, and province.
    """
    cursor = conn.cursor()
    linked = []

    for contract in contracts:
        vendor = contract.get("vendor", contract.get("organization", ""))
        province = contract.get("province")

        if not vendor or vendor == "Unknown":
            continue

        try:
            cursor.execute("""
                SELECT name, province, value, status, sector
                FROM projects
                WHERE (name LIKE ? OR name LIKE ?)
                AND (province = ? OR ? IS NULL)
                ORDER BY value DESC
                LIMIT 3
            """, (
                f"%{vendor}%",
                f"%{vendor.split()[0]}%",
                province, province,
            ))

            matches = cursor.fetchall()
            if matches:
                contract["linked_projects"] = [
                    {"name": m[0], "province": m[1], "value": m[2],
                     "status": m[3], "sector": m[4]}
                    for m in matches
                ]
            else:
                contract["linked_projects"] = []

            linked.append(contract)
        except Exception as e:
            logger.debug(f"[PROCUREMENT] Project linking failed: {e}")

    return linked


def run_procurement_monitor(conn, days_back=30):
    """
    Main entry point. Fetch from all procurement sources, filter, link to projects.

    Returns dict with procurement data for the pipeline context.
    """
    all_contracts = []

    # Federal sources
    all_contracts.extend(fetch_open_canada_contracts(days_back))
    all_contracts.extend(fetch_buyandsell_rss())

    # Provincial sources
    all_contracts.extend(fetch_ontario_bps())
    all_contracts.extend(fetch_bc_bid())

    print(f"[PROCUREMENT] Total: {len(all_contracts)} relevant contracts across all sources")

    # patch-1.2: min-yield DEGRADE log. All four procurement sources were dark
    # (D-9); a whole-run zero means dead endpoints, not a quiet week.
    if not all_contracts:
        print("[PROCUREMENT DEGRADED] 0 items — all procurement sources returned zero")

    # Link to existing projects
    linked = link_contracts_to_projects(all_contracts, conn)
    linked_count = sum(1 for c in linked if c.get("linked_projects"))
    print(f"[PROCUREMENT] Linked {linked_count}/{len(linked)} contracts to existing projects")

    # Save snapshot
    save_procurement_snapshot(conn, all_contracts)

    return {
        "procurement_contracts": all_contracts,
        "procurement_linked": linked,
        "procurement_total_value": sum(c.get("value", 0) for c in all_contracts if c.get("value")),
        "procurement_sources": list(set(c["source"] for c in all_contracts)),
    }


def save_procurement_snapshot(conn, contracts):
    """Save weekly procurement snapshot for historical tracking."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS procurement_snapshots (
            week_of     TEXT NOT NULL,
            data        TEXT NOT NULL,
            created     TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (week_of)
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO procurement_snapshots (week_of, data)
        VALUES (?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d"),
        json.dumps(contracts, default=str),
    ))
    conn.commit()
