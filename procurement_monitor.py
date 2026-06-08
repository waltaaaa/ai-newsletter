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
# browser UA + certifi TLS clears the bot-blocks; stale CKAN ids / migrated
# hosts are flagged with TODO(patch-1.2 live-verify) below.
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
        # Proactive Disclosure — Contracts over $10K
        # TODO(patch-1.2 live-verify): CKAN package id 'proactive-disclosure-contracts'
        #   returns 404 (D-9). The dataset was renamed/migrated. Candidate: the new
        #   contracts search API at https://search.open.canada.ca/contracts/ (verify
        #   the JSON/CSV download endpoint), or re-resolve the current CKAN package id
        #   via https://open.canada.ca/data/api/3/action/package_search?q=proactive+disclosure+contracts
        url = "https://open.canada.ca/data/api/3/action/package_show"
        params = {"id": "proactive-disclosure-contracts"}

        resp = http_client.get(url, params=params, timeout=15)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT][open_canada] FAILED status={status}")
            return []

        data = resp.json()
        resources = data.get("result", {}).get("resources", [])

        # Find the most recent CSV resource
        csv_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]
        if not csv_resources:
            print("[PROCUREMENT] No CSV resources found in Open Canada contracts")
            return []

        # Download and parse the most recent CSV
        csv_url = csv_resources[-1].get("url")
        if csv_url:
            csv_resp = http_client.get(csv_url, timeout=30)
            if csv_resp is None or csv_resp.status_code >= 400:
                status = 'network' if csv_resp is None else csv_resp.status_code
                print(f"[PROCUREMENT][open_canada] CSV download FAILED status={status}")
                return []
            reader = csv.DictReader(io.StringIO(csv_resp.text))

            cutoff = datetime.now() - timedelta(days=days_back)

            for row in reader:
                try:
                    value = _parse_value(row.get("contract_value", "0"))
                    if value < MIN_CONTRACT_VALUE:
                        continue

                    description = row.get("description_en", "").lower()
                    if not any(kw in description for kw in CONSTRUCTION_KEYWORDS):
                        continue

                    contracts.append({
                        "source": "open_canada",
                        "vendor": row.get("vendor_name", "Unknown"),
                        "department": row.get("owner_org", ""),
                        "description": row.get("description_en", ""),
                        "value": value,
                        "award_date": row.get("contract_date", ""),
                        "province": _infer_province(row),
                        "url": f"https://open.canada.ca/data/en/dataset/proactive-disclosure-contracts",
                    })
                except Exception as e:
                    logger.debug(f"[PROCUREMENT] Skipped row: {e}")

        print(f"[PROCUREMENT] Open Canada: {len(contracts)} relevant contracts (>=${MIN_CONTRACT_VALUE:,})")

    except Exception as e:
        print(f"[WARN] Open Canada procurement fetch failed: {e}")

    return contracts


def fetch_buyandsell_rss():
    """
    Fetch recent federal tender notices from BuyAndSell.gc.ca RSS.
    Filters for construction and infrastructure categories.
    """
    tenders = []

    # TODO(patch-1.2 live-verify): buyandsell.gc.ca migrated to
    #   canadabuys.canada.ca (D-9). The old RSS path likely 404s. Re-resolve the
    #   current tender-notices feed under canadabuys.canada.ca (candidate:
    #   https://canadabuys.canada.ca/en/tender-opportunities/rss or the open-data
    #   tenders CSV). The old URL is kept (additive) until the new one is confirmed.
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
        # TODO(patch-1.2 live-verify): confirm CKAN package id
        #   'broader-public-sector-business-document-plan' still resolves on
        #   data.ontario.ca (D-9 reported Ontario BPS zero). If renamed, re-resolve
        #   via data.ontario.ca/api/3/action/package_search?q=broader+public+sector+procurement
        url = "https://data.ontario.ca/api/3/action/package_show"
        params = {"id": "broader-public-sector-business-document-plan"}

        resp = http_client.get(url, params=params, timeout=15)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT][ontario_bps] FAILED status={status}")
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
        # TODO(patch-1.2 live-verify): confirm the BC Bid RSS endpoint. The legacy
        #   open.dll/RSSFeed path may have been retired with the BC Bid platform
        #   refresh (D-9 reported BC Bid zero). Candidate: the current bcbid.gov.bc.ca
        #   public opportunities feed/API. Old URL kept (additive) until confirmed.
        url = "https://www.bcbid.gov.bc.ca/open.dll/RSSFeed?Feed=Construction"
        # patch-1.2: fetch with browser UA via http_client, then parse the bytes
        # with feedparser. Falls back to feedparser-direct if the fetch fails.
        resp = http_client.get(url, timeout=20)
        if resp is None or resp.status_code >= 400:
            status = 'network' if resp is None else resp.status_code
            print(f"[PROCUREMENT][bc_bid] FAILED status={status}")
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
