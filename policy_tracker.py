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

# patch-1.2 (D-10): shared HTTP client for fetching RSS with a browser UA
# (feedparser's default UA is bot-blocked by several gov feeds), plus
# government_bypass so configured government policy feeds pass through without
# keyword classification (per CLAUDE.md RSS-filter Layer 1).
import http_client

logger = logging.getLogger(__name__)

# patch-1.2: default cap on items sent to keyword classification. All FEDERAL_FEEDS
# and PROVINCIAL_FEEDS are government sources, so they bypass classification
# entirely (government_bypass); this cap only bounds any non-government items
# (e.g. researcher-found) and is parameterised so callers can widen it.
DEFAULT_MAX_CLASSIFY_BATCH = 50

# Levels considered "government source" for the Layer-1 bypass. Every feed in
# FEDERAL_FEEDS / PROVINCIAL_FEEDS carries level 'federal' or 'provincial'.
_GOVERNMENT_LEVELS = frozenset({"federal", "provincial"})


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
                     "water infrastructure", "disaster mitigation",
                     "capital plan", "capital program", "infrastructure program",
                     "infrastructure strategy", "investment program"],
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
                     "accelerated depreciation", "sr&ed",
                     "fiscal framework", "fiscal plan", "budget implementation",
                     "estimates", "supplementary estimates", "main estimates"],
        "sectors": [],  # Affects all sectors
    },
    # Broad catchall — catches generic capital-investment signals that don't
    # fit a narrow category but still indicate policy affecting the project pipeline.
    # Added 2026-04-19 after policy tracker classification was found too strict (1/30
    # pass rate in the 2026-04-18 audit). These keywords intentionally fire on many
    # items — downstream classifier ranks by signal strength.
    "capital_investment": {
        "keywords": ["billion", "$1b", "$2b", "$5b", "$10b", "funding announcement",
                     "investment announcement", "strategic investment",
                     "procurement", "contract award", "federal funding",
                     "provincial funding", "municipal funding", "grant program",
                     "loan guarantee", "equity investment", "fund", "initiative",
                     "announcement", "strategy", "program"],
        "sectors": [],  # Sector is inferred from surrounding text
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

    # patch-1.2 (D-10): track per-feed item counts so a dead feed is
    # distinguishable from a quiet week. All feeds here are government sources.
    per_feed: dict[str, int] = {}

    for feed_id, feed_config in feeds.items():
        feed_count = 0
        try:
            # patch-1.2: fetch with browser UA via http_client, then hand bytes
            # to feedparser (feedparser.parse(url) uses its own UA that several
            # gov feeds bot-block). Falls back to feedparser-direct on failure.
            resp = http_client.get(feed_config["url"], timeout=20)
            if resp is None or resp.status_code >= 400:
                status = 'network' if resp is None else resp.status_code
                print(f"[POLICY][{feed_id}] FAILED status={status}")
                feed = feedparser.parse(feed_config["url"])
            else:
                feed = feedparser.parse(resp.content)

            if feed.bozo and not feed.entries:
                logger.debug(f"[POLICY] Feed failed: {feed_id} — {feed_config['url']}")
                per_feed[feed_id] = 0
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
                    # patch-1.2: mark configured gov feeds for Layer-1 bypass.
                    "government_bypass": feed_config["level"] in _GOVERNMENT_LEVELS,
                }
                all_items.append(item)
                feed_count += 1

            per_feed[feed_id] = feed_count

        except Exception as e:
            per_feed[feed_id] = 0
            print(f"[WARN] Policy feed {feed_id} failed: {e}")

    print(f"[POLICY] Fetched {len(all_items)} items from {len(feeds)} feeds")
    # patch-1.2: per-feed counts (sorted, zero feeds flagged) so operators can
    # see which feeds produced items vs which are dark.
    counts_str = ", ".join(f"{fid}={n}" for fid, n in sorted(per_feed.items()))
    print(f"[POLICY] Per-feed counts: {counts_str}")
    zero_feeds = [fid for fid, n in per_feed.items() if n == 0]
    if zero_feeds:
        print(f"[POLICY] Feeds returning 0 this run: {', '.join(zero_feeds)}")
    return all_items


def classify_policy_items(items, max_batch=DEFAULT_MAX_CLASSIFY_BATCH):
    """
    Classify policy items by policy category and affected sectors.
    Adds 'policy_categories' and 'affected_sectors' fields.

    patch-1.2 (D-10): government_bypass — items from configured government feeds
    (level federal/provincial, flagged 'government_bypass') skip keyword
    classification and count as relevant, per CLAUDE.md RSS-filter Layer 1 (all
    policy feeds are government sources). Keyword classification still runs to
    enrich category/sector tags where it fires, but a government item with no
    keyword hit is no longer dropped. ``max_batch`` bounds the keyword pass over
    non-government (e.g. researcher-found) items.

    Args:
        items: list of policy item dicts.
        max_batch: cap on the number of items the keyword classifier scans
            (additive — government items always pass regardless of this cap).
    """
    classified = 0      # items with at least one keyword-derived category
    bypassed = 0        # government items passed through Layer 1

    for idx, item in enumerate(items):
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

        categories = []
        sectors = set()

        # Keyword pass (enrichment). Bounded by max_batch for non-gov items, but
        # government items are always scanned too so they still get category tags.
        is_gov = bool(item.get("government_bypass")) or \
            item.get("level") in _GOVERNMENT_LEVELS
        if is_gov or idx < max_batch:
            for category, config in INVESTMENT_POLICY_KEYWORDS.items():
                for kw in config["keywords"]:
                    if kw in text:
                        categories.append(category)
                        sectors.update(config["sectors"])
                        break

        item["affected_sectors"] = list(sectors)

        if categories:
            classified += 1
        elif is_gov:
            # Government source with no keyword hit: bypass classification and
            # tag with a generic government category so downstream linking and
            # the relevance filter retain it.
            categories = ["government_policy"]
            item["government_bypass"] = True
            bypassed += 1

        item["policy_categories"] = categories

    # Filter to only investment-relevant items (gov-bypassed items now retained).
    relevant = [i for i in items if i["policy_categories"]]

    print(f"[POLICY] {classified}/{len(items)} keyword-classified, "
          f"{bypassed} government-bypassed -> {len(relevant)} relevant")
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
                "level": item.get("level", "federal"),
                "summary": (item.get("summary") or "")[:300],
                "date": item.get("date", ""),
                "source_description": item.get("source_description", ""),
                "url": item["url"],
            }
            for item in sorted(
                items,
                key=lambda x: x.get("affected_projects_value", 0),
                reverse=True
            )[:20]
        ],
    }


def extract_policy_from_research(research_paths):
    """
    Read researcher output (research_macro.md, research_provinces.md,
    research_sectors.md) and extract policy-relevant items that the RSS feeds
    may have missed. Returns a list of item dicts compatible with the main
    classification path.

    Researchers pick up policy items from sources the RSS feeds don't cover
    (press releases, minister statements, trade publications, direct web search).
    Added 2026-04-19 after the audit found that researcher-found policy items
    were not flowing into policy_snapshots.

    Args:
      research_paths: list of file paths to researcher markdown outputs
    """
    import re as _re

    items = []
    for path in research_paths:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (FileNotFoundError, OSError):
            continue

        # Extract bulleted lines that look like policy announcements:
        # "- [Title](url) — context"  OR  "- Title — context (source: url)"
        line_pattern = _re.compile(
            r"^[\-*]\s+(?:\[([^\]]+)\]\(([^)]+)\)|([^\n]+?))\s*(?:[—–-]\s*(.+?))?$",
            _re.MULTILINE,
        )
        url_pattern = _re.compile(r"https?://\S+")

        for match in line_pattern.finditer(text):
            title_md, url_md, title_plain, context = match.groups()
            title = title_md or title_plain or ""
            title = title.strip()
            if len(title) < 15 or len(title) > 250:
                continue

            url = url_md or ""
            if not url:
                m = url_pattern.search(context or "")
                if m:
                    url = m.group(0)
            if not url:
                continue

            items.append({
                "title": title,
                "url": url.rstrip(".,);"),
                "summary": (context or "")[:300],
                "source_description": f"researcher:{path}",
                "level": "researcher",
                "date": "",
                "province": None,
            })

    return items


def run_policy_tracker(conn, research_paths=None):
    """
    Main entry point. Fetch, classify, detect changes, link to projects.

    Args:
      conn: sqlite3 connection
      research_paths: optional list of researcher output paths
        (research_macro.md, research_provinces.md, research_sectors.md).
        If provided, items extracted from research are merged with RSS items
        before classification. Deduped by URL.

    Returns dict with policy data for the pipeline context.
    """
    # Fetch from all feeds
    all_items = fetch_all_policy_feeds()

    # Merge researcher-found policy items (added 2026-04-19)
    if research_paths:
        research_items = extract_policy_from_research(research_paths)
        seen_urls = {i.get("url", "") for i in all_items if i.get("url")}
        for r in research_items:
            if r["url"] not in seen_urls:
                all_items.append(r)
                seen_urls.add(r["url"])
        logger.info(
            "[POLICY] Merged %d researcher-found items into %d total",
            len(research_items), len(all_items),
        )

    # Classify by policy category and affected sectors
    relevant = classify_policy_items(all_items)

    # patch-1.2 (D-10): min-yield DEGRADE log. With government_bypass, a zero
    # relevant count now means feeds are dark, not over-strict classification.
    if not relevant:
        print("[POLICY DEGRADED] 0 items — no relevant policy developments "
              "(check per-feed counts above for dark feeds)")

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
