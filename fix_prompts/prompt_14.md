Run this with: `claude -p "$(cat fix_prompts/prompt_14.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to expand government procurement tracking beyond the existing BuyAndSell scraper. Federal and provincial procurement datasets are structured, free, and contain contract values, vendors, and project descriptions that directly map to projects in the database. Read the relevant files before making changes.

## Context

The current Tier 1 BuyAndSell scraper catches federal tender listings but misses awarded contracts, proactive disclosure data, and provincial procurement entirely. Awarded contracts confirm that a project has moved from "proposed" to at least "approved" — often with exact dollar values. Provincial procurement portals cover infrastructure that federal sources miss: highways, hospitals, schools, transit.

## Part 1: Create `procurement_monitor.py`

Create a new file `procurement_monitor.py`:

```python
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
        url = "https://open.canada.ca/data/api/3/action/package_show"
        params = {"id": "proactive-disclosure-contracts"}
        
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[PROCUREMENT] Open Canada API returned {resp.status_code}")
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
            csv_resp = requests.get(csv_url, timeout=30)
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
        
        print(f"[PROCUREMENT] Open Canada: {len(contracts)} relevant contracts (≥${MIN_CONTRACT_VALUE:,})")
        
    except Exception as e:
        print(f"[WARN] Open Canada procurement fetch failed: {e}")
    
    return contracts


def fetch_buyandsell_rss():
    """
    Fetch recent federal tender notices from BuyAndSell.gc.ca RSS.
    Filters for construction and infrastructure categories.
    """
    tenders = []
    
    rss_urls = [
        "https://buyandsell.gc.ca/procurement-data/feed/rss",
    ]
    
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
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
        url = "https://data.ontario.ca/api/3/action/package_show"
        params = {"id": "broader-public-sector-business-document-plan"}
        
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            resources = data.get("result", {}).get("resources", [])
            
            csv_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]
            if csv_resources:
                csv_url = csv_resources[-1].get("url")
                csv_resp = requests.get(csv_url, timeout=30)
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
        url = "https://www.bcbid.gov.bc.ca/open.dll/RSSFeed?Feed=Construction"
        feed = feedparser.parse(url)
        
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
```

## Part 2: Integrate into the discovery phase

File: `phases/discovery.py`

Add procurement monitoring as a new sub-step in the discovery phase. It runs alongside the existing tiers:

```python
try:
    from procurement_monitor import run_procurement_monitor
    procurement_results = run_procurement_monitor(conn)
    context.update(procurement_results)
except ImportError:
    print("[WARN] procurement_monitor not available, skipping procurement tracking")
except Exception as e:
    print(f"[WARN] Procurement monitor failed: {e}")
```

## Part 3: Update CLAUDE.md

Add to Repository Layout:
```
├── procurement_monitor.py      # Government procurement tracking (federal + provincial, free APIs)
```

Add to Discovery Pipeline section:
```
Procurement Monitor: Tracks federal and provincial contract awards and tenders from
Open Canada Proactive Disclosure, BuyAndSell RSS, Ontario BPS, and BC Bid.
Filters for construction/infrastructure contracts ≥$5M. Links awards to existing
projects for status confirmation. Zero cost — all public data.
```

Add `procurement_snapshots` to the database table documentation.

## Important constraints

- All sources are FREE public data. No API keys required.
- $5M minimum filter prevents thousands of small IT/office contracts from cluttering results
- Construction keyword filter focuses on capital projects, not services/consulting
- The Open Canada CKAN API is rate-limited but generous — no issues at weekly cadence
- BC Bid RSS URL may need verification — the exact URL format changes occasionally. If it fails, the try/except handles it gracefully.
- Provincial sources beyond ON and BC can be added incrementally. QC (SEAO) and AB are the next priorities but may require French parsing for SEAO.
