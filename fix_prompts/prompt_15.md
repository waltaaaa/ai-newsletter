Run this with: `claude -p "$(cat fix_prompts/prompt_15.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to create a policy and legislative tracking module. For an economic forecaster, knowing which bills, regulations, and policy announcements are moving through the system is essential context. A housing accelerator bill, a carbon pricing change, or a new critical minerals strategy directly affects the viability and timeline of projects in the database. Read the relevant files before making changes.

## Context

Policy and legislative changes are upstream drivers of capital investment. Right now the pipeline catches policy news incidentally through RSS and Google News, but has no systematic tracking of:
- Bills moving through Parliament or provincial legislatures
- Regulatory changes (Canada Gazette, provincial gazettes)
- Budget announcements and fiscal updates
- Trade policy changes (tariffs, export controls, trade agreements)
- Sector-specific policy (energy transition, housing, defence procurement)

This module creates a structured policy feed that tracks legislative and regulatory developments, classifies them by affected sector and province, and makes them available to the narrative and analysis phases.

## Part 1: Create `policy_tracker.py`

```python
"""
Policy and legislative tracker — monitors government policy actions that
affect capital investment and economic development.

Sources (all free, no API keys):
1. LEGISinfo RSS — federal bills (House of Commons + Senate)
2. Canada Gazette RSS — regulatory changes, orders in council
3. Provincial legislative feeds (where available)
4. Bank of Canada announcements (supplements existing BoC tracking)
5. Department of Finance news releases
6. Key ministry RSS feeds (ISED, NRCan, ECCC, Transport, Infrastructure)

Output: Structured policy events with sector/province classification,
status tracking (introduced → committee → passed → royal assent),
and links to affected projects in the database.
"""
import feedparser
import requests
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ── Federal Legislative Sources ──

FEDERAL_FEEDS = {
    # LEGISinfo — bills in Parliament
    "legisinfo_house": {
        "url": "https://www.parl.ca/legisinfo/en/bills/rss",
        "source_type": "legislation",
        "level": "federal",
        "description": "Federal bills — House of Commons and Senate",
    },
    # Canada Gazette — regulations and orders
    "gazette_part1": {
        "url": "https://www.gazette.gc.ca/rss/part1-en.xml",
        "source_type": "regulation",
        "level": "federal",
        "description": "Canada Gazette Part I — proposed regulations",
    },
    "gazette_part2": {
        "url": "https://www.gazette.gc.ca/rss/part2-en.xml",
        "source_type": "regulation",
        "level": "federal",
        "description": "Canada Gazette Part II — enacted regulations",
    },
    # Department of Finance
    "finance_news": {
        "url": "https://www.canada.ca/en/department-finance/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "Department of Finance — budgets, fiscal updates, tax policy",
    },
    # Innovation, Science and Economic Development (ISED)
    "ised_news": {
        "url": "https://www.canada.ca/en/innovation-science-economic-development/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "ISED — industrial policy, broadband, innovation",
    },
    # Natural Resources Canada
    "nrcan_news": {
        "url": "https://www.canada.ca/en/natural-resources-canada/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "NRCan — energy, mining, forestry, critical minerals",
    },
    # Environment and Climate Change Canada
    "eccc_news": {
        "url": "https://www.canada.ca/en/environment-climate-change/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "ECCC — carbon pricing, environmental regulation, CEPA",
    },
    # Transport Canada
    "transport_news": {
        "url": "https://www.canada.ca/en/transport-canada/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "Transport — infrastructure, ports, rail, aviation policy",
    },
    # Infrastructure Canada
    "infra_news": {
        "url": "https://www.canada.ca/en/office-infrastructure/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "Infrastructure Canada — ICIP, housing accelerator, transit fund",
    },
    # Canada Housing (CMHC-adjacent)
    "housing_news": {
        "url": "https://www.canada.ca/en/canada-mortgage-housing-corporation/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "CMHC — housing policy, NHSA, affordability measures",
    },
    # Global Affairs (trade policy)
    "gac_news": {
        "url": "https://www.canada.ca/en/global-affairs/news.atom",
        "source_type": "trade_policy",
        "level": "federal",
        "description": "Global Affairs — trade agreements, tariffs, export controls",
    },
    # National Defence
    "dnd_news": {
        "url": "https://www.canada.ca/en/department-national-defence/news.atom",
        "source_type": "policy_announcement",
        "level": "federal",
        "description": "DND — defence procurement, base infrastructure",
    },
}

# ── Provincial Legislative Sources ──
# Not all provinces have reliable RSS. These are the ones that do.

PROVINCIAL_FEEDS = {
    "ontario_newsroom": {
        "url": "https://news.ontario.ca/en/rss/allnews",
        "source_type": "policy_announcement",
        "level": "provincial",
        "province": "ON",
        "description": "Ontario Newsroom — all provincial announcements",
    },
    "bc_news": {
        "url": "https://news.gov.bc.ca/feed",
        "source_type": "policy_announcement",
        "level": "provincial",
        "province": "BC",
        "description": "BC Government News",
    },
    "alberta_news": {
        "url": "https://www.alberta.ca/news-rss.aspx",
        "source_type": "policy_announcement",
        "level": "provincial",
        "province": "AB",
        "description": "Alberta Government News",
    },
    "quebec_news": {
        "url": "https://www.quebec.ca/nouvelles/rss",
        "source_type": "policy_announcement",
        "level": "provincial",
        "province": "QC",
        "description": "Quebec Government News (may be French)",
    },
    "sk_news": {
        "url": "https://www.saskatchewan.ca/rss",
        "source_type": "policy_announcement",
        "level": "provincial",
        "province": "SK",
        "description": "Saskatchewan Government News",
    },
}


# ── Policy Classification ──

# Keywords that indicate a policy item affects capital investment / projects
INVESTMENT_POLICY_KEYWORDS = {
    "housing": {
        "keywords": ["housing", "zoning", "density", "rental", "affordable housing",
                     "building code", "development charges", "housing accelerator",
                     "nhsa", "cmhc", "purpose-built rental"],
        "sectors": ["residential"],
    },
    "energy_transition": {
        "keywords": ["carbon tax", "carbon pricing", "clean fuel", "emissions cap",
                     "net zero", "clean electricity", "renewable", "ev mandate",
                     "hydrogen strategy", "critical minerals", "smr", "nuclear"],
        "sectors": ["power_energy", "oil_gas", "mining"],
    },
    "infrastructure_funding": {
        "keywords": ["infrastructure bank", "icip", "investing in canada",
                     "transit fund", "trade corridor", "broadband", "green infrastructure",
                     "water infrastructure", "disaster mitigation"],
        "sectors": ["infrastructure", "transport_logistics", "telecom"],
    },
    "trade_policy": {
        "keywords": ["tariff", "trade agreement", "export control", "softwood lumber",
                     "buy canadian", "procurement policy", "cusma", "cptpp",
                     "foreign investment", "investment canada act", "national security review"],
        "sectors": ["manufacturing", "forestry", "agriculture", "oil_gas"],
    },
    "defence": {
        "keywords": ["defence policy", "norad modernization", "shipbuilding",
                     "canadian surface combatant", "fighter jet", "defence procurement",
                     "military infrastructure"],
        "sectors": ["defence"],
    },
    "resource_development": {
        "keywords": ["mining act", "impact assessment", "ceaa", "pipeline approval",
                     "offshore", "exploration", "royalties", "tenure",
                     "environmental assessment", "indigenous consultation"],
        "sectors": ["mining", "oil_gas", "forestry"],
    },
    "healthcare_infrastructure": {
        "keywords": ["hospital funding", "health infrastructure", "long-term care",
                     "health facility", "medical campus"],
        "sectors": ["healthcare"],
    },
    "fiscal_policy": {
        "keywords": ["budget", "fiscal update", "fall economic statement",
                     "deficit", "capital gains", "tax credit", "investment tax credit",
                     "accelerated depreciation", "sr&ed"],
        "sectors": [],  # Affects all sectors
    },
}

# Legislative status progression
BILL_STATUS_ORDER = [
    "introduced",
    "first_reading",
    "second_reading",
    "committee",
    "report_stage",
    "third_reading",
    "senate",
    "royal_assent",
    "in_force",
]


def fetch_all_policy_feeds():
    """
    Fetch items from all configured policy RSS feeds.
    Returns list of policy event dicts.
    """
    all_items = []
    feeds = {**FEDERAL_FEEDS, **PROVINCIAL_FEEDS}
    
    for feed_id, feed_config in feeds.items():
        try:
            feed = feedparser.parse(feed_config["url"])
            
            if feed.bozo and not feed.entries:
                logger.debug(f"[POLICY] Feed failed: {feed_id} — {feed_config['url']}")
                continue
            
            for entry in feed.entries[:20]:  # Limit per feed
                item = {
                    "feed_id": feed_id,
                    "source_type": feed_config["source_type"],
                    "level": feed_config["level"],
                    "province": feed_config.get("province"),
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "date": entry.get("published", entry.get("updated", "")),
                    "source_description": feed_config["description"],
                }
                all_items.append(item)
            
        except Exception as e:
            print(f"[WARN] Policy feed {feed_id} failed: {e}")
    
    print(f"[POLICY] Fetched {len(all_items)} items from {len(feeds)} feeds")
    return all_items


def classify_policy_items(items):
    """
    Classify policy items by policy category and affected sectors.
    Adds 'policy_categories' and 'affected_sectors' fields.
    """
    classified = 0
    
    for item in items:
        text = f"{item['title']} {item['summary']}".lower()
        
        categories = []
        sectors = set()
        
        for category, config in INVESTMENT_POLICY_KEYWORDS.items():
            for kw in config["keywords"]:
                if kw in text:
                    categories.append(category)
                    sectors.update(config["sectors"])
                    break
        
        item["policy_categories"] = categories
        item["affected_sectors"] = list(sectors)
        
        if categories:
            classified += 1
    
    # Filter to only investment-relevant items
    relevant = [i for i in items if i["policy_categories"]]
    
    print(f"[POLICY] {classified}/{len(items)} items classified as investment-relevant")
    return relevant


def detect_policy_changes(current_items, conn):
    """
    Compare current policy items against previous week's snapshot.
    Flag new policy developments and status changes.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT data FROM policy_snapshots
            ORDER BY week_of DESC LIMIT 1
        """)
        row = cursor.fetchone()
        previous = json.loads(row[0]) if row else []
    except Exception:
        previous = []
    
    previous_urls = {p.get("url") for p in previous}
    
    new_items = [i for i in current_items if i["url"] not in previous_urls]
    
    if new_items:
        print(f"[POLICY] {len(new_items)} new policy developments this week")
    
    return new_items


def link_policy_to_projects(items, conn):
    """
    Link policy items to affected projects by sector and province.
    A housing policy in Ontario → residential projects in ON.
    """
    cursor = conn.cursor()
    
    for item in items:
        sectors = item.get("affected_sectors", [])
        province = item.get("province")
        
        if not sectors:
            continue
        
        try:
            placeholders = ",".join(["?" for _ in sectors])
            query = f"""
                SELECT name, province, value, status, sector
                FROM projects
                WHERE sector IN ({placeholders})
            """
            params = list(sectors)
            
            if province:
                query += " AND province = ?"
                params.append(province)
            
            query += " ORDER BY value DESC LIMIT 10"
            
            cursor.execute(query, params)
            matches = cursor.fetchall()
            
            item["affected_projects_count"] = len(matches)
            item["affected_projects_sample"] = [
                {"name": m[0], "province": m[1], "value": m[2],
                 "status": m[3], "sector": m[4]}
                for m in matches[:5]
            ]
            
            # Calculate total value of affected projects
            if province:
                cursor.execute(f"""
                    SELECT COUNT(*), SUM(value)
                    FROM projects
                    WHERE sector IN ({placeholders}) AND province = ?
                """, params)
            else:
                cursor.execute(f"""
                    SELECT COUNT(*), SUM(value)
                    FROM projects
                    WHERE sector IN ({placeholders})
                """, sectors)
            
            count_row = cursor.fetchone()
            item["affected_projects_total"] = count_row[0] if count_row else 0
            item["affected_projects_value"] = count_row[1] if count_row and count_row[1] else 0
            
        except Exception as e:
            logger.debug(f"[POLICY] Project linking failed: {e}")
            item["affected_projects_count"] = 0
    
    return items


def save_policy_snapshot(conn, items):
    """Save weekly policy snapshot for change detection and historical tracking."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_snapshots (
            week_of     TEXT NOT NULL,
            data        TEXT NOT NULL,
            summary     TEXT,
            created     TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (week_of)
        )
    """)
    
    # Generate summary for the narrative phase
    summary = generate_policy_summary(items)
    
    cursor.execute("""
        INSERT OR REPLACE INTO policy_snapshots (week_of, data, summary)
        VALUES (?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d"),
        json.dumps(items, default=str),
        json.dumps(summary, default=str),
    ))
    conn.commit()


def generate_policy_summary(items):
    """
    Generate a structured summary of this week's policy developments
    for use by the narrative phase.
    """
    by_category = defaultdict(list)
    by_province = defaultdict(list)
    by_level = defaultdict(list)
    
    for item in items:
        for cat in item.get("policy_categories", []):
            by_category[cat].append(item)
        if item.get("province"):
            by_province[item["province"]].append(item)
        by_level[item["level"]].append(item)
    
    return {
        "total_items": len(items),
        "by_category": {k: len(v) for k, v in by_category.items()},
        "by_province": {k: len(v) for k, v in by_province.items()},
        "by_level": {k: len(v) for k, v in by_level.items()},
        "top_developments": [
            {
                "title": item["title"],
                "source_type": item["source_type"],
                "categories": item["policy_categories"],
                "affected_sectors": item["affected_sectors"],
                "affected_projects_total": item.get("affected_projects_total", 0),
                "affected_projects_value": item.get("affected_projects_value", 0),
                "province": item.get("province"),
                "url": item["url"],
            }
            for item in sorted(
                items,
                key=lambda x: x.get("affected_projects_value", 0),
                reverse=True
            )[:10]
        ],
    }


def run_policy_tracker(conn):
    """
    Main entry point. Fetch, classify, detect changes, link to projects.
    
    Returns dict with policy data for the pipeline context.
    """
    # Fetch from all feeds
    all_items = fetch_all_policy_feeds()
    
    # Classify by policy category and affected sectors
    relevant = classify_policy_items(all_items)
    
    # Detect new developments vs. previous week
    new_items = detect_policy_changes(relevant, conn)
    
    # Link to affected projects
    relevant = link_policy_to_projects(relevant, conn)
    
    # Save snapshot
    save_policy_snapshot(conn, relevant)
    
    # Generate summary for narrative phase
    summary = generate_policy_summary(relevant)
    
    return {
        "policy_items": relevant,
        "policy_new_items": new_items,
        "policy_summary": summary,
        "policy_feed_count": len(FEDERAL_FEEDS) + len(PROVINCIAL_FEEDS),
    }
```

## Part 2: Integrate into the discovery phase

File: `phases/discovery.py`

Add policy tracking alongside other discovery tiers:

```python
try:
    from policy_tracker import run_policy_tracker
    policy_results = run_policy_tracker(conn)
    context.update(policy_results)
    print(f"[Phase 2] Policy tracker: {len(policy_results['policy_items'])} relevant items, "
          f"{len(policy_results['policy_new_items'])} new this week")
except ImportError:
    print("[WARN] policy_tracker not available, skipping policy monitoring")
except Exception as e:
    print(f"[WARN] Policy tracker failed: {e}")
```

## Part 3: Add database tables

File: `db.py`

Add the `policy_snapshots` table to schema initialization. Document in CLAUDE.md:

```
| `policy_snapshots` | Weekly policy/legislative developments with sector/project linkages |
```

## Part 4: Update CLAUDE.md

Add to Repository Layout:
```
├── policy_tracker.py           # Policy & legislative tracking (LEGISinfo, Gazette, ministry feeds)
```

Add a new section to CLAUDE.md:

```
### Policy Tracking

Monitors ~20 federal and provincial RSS feeds for legislative and regulatory
developments affecting capital investment. Sources include LEGISinfo (federal bills),
Canada Gazette (regulations), and ministry news feeds for Finance, ISED, NRCan, 
ECCC, Transport, Infrastructure, CMHC, Global Affairs, and DND.

Policy items are classified into 8 categories (housing, energy_transition, 
infrastructure_funding, trade_policy, defence, resource_development, 
healthcare_infrastructure, fiscal_policy) and linked to affected projects 
by sector and province. The policy_summary output feeds into the narrative 
phase for the weekly briefing.

Zero cost — all government RSS feeds are free public data.
```

## Important constraints

- All sources are FREE government RSS feeds. No API keys, no scraping.
- Policy items are classified by keyword matching, not LLM — keeps it zero-cost and deterministic.
- The `affected_projects_value` calculation is the key metric: it tells you "this housing bill affects 23 residential projects worth $4.1B in Ontario." That's the number that matters for the briefing.
- Provincial feed URLs may change — wrap each in try/except. Quebec feed may return French content; the keyword matching still works because policy terms are often similar in both languages (e.g., "infrastructure", "pipeline").
- The Canada.ca Atom feeds are reliable but occasionally restructure. If a ministry feed stops working, the circuit breaker pattern applies.
- Policy tracking is FACTUAL — the module records what happened (bill introduced, regulation enacted), not what it means. Interpretation belongs in the Claude analysis calls where it's properly framed as analytical, not predictive.
