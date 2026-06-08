"""
provincial_policy_monitor.py -- Track provincial and federal policy changes
affecting capital investment.

Sources polled via RSS:
- Federal Department of Finance, Parliament, Budget
- Provincial finance ministries (ON, QC, AB, BC, etc.)
- Energy regulators (CER, AER, BCUC)

Flow:
1. Fetch policy RSS feeds via requests + feedparser
2. Classify via Gemini Flash (policy-relevant vs not)
3. Assess economic impact via Claude Sonnet for significant items
"""

import json
import logging
import os
from datetime import datetime, timedelta

import feedparser
import requests

# patch-1.2 (D-10): shared HTTP client — browser UA + certifi TLS clears the
# bot-blocks / cert failures that left several provincial finance feeds dark.
import http_client

logger = logging.getLogger(__name__)

# patch-1.2: default keyword/LLM classification batch size (was hardcoded 30 at
# the classify_policy_articles call site). Parameterised so callers can widen it.
DEFAULT_MAX_BATCH = 50

# ── Policy RSS feeds ─────────────────────────────────────────────────

POLICY_FEEDS = {
    # Federal
    "federal_finance": {
        "name": "Department of Finance Canada",
        "url": "https://www.canada.ca/en/department-finance.atom.xml",
        "scope": "federal",
    },
    "federal_budget": {
        "name": "Budget / Fall Economic Statement",
        "url": "https://budget.canada.ca/rss",
        "scope": "federal",
    },
    # Provincial finance
    "on_finance": {
        "name": "Ontario Ministry of Finance",
        "url": "https://news.ontario.ca/en/newsroom/treasury-board-secretariat",
        "scope": "ON",
    },
    "qc_finance": {
        "name": "Quebec Finance Ministry",
        "url": "https://www.quebec.ca/en/government/news/rss",
        "scope": "QC",
    },
    "ab_finance": {
        "name": "Alberta Treasury Board and Finance",
        "url": "https://www.alberta.ca/treasury-board-and-finance-news-rss",
        "scope": "AB",
    },
    "bc_finance": {
        "name": "BC Ministry of Finance",
        "url": "https://news.gov.bc.ca/ministries/finance/feed",
        "scope": "BC",
    },
    "mb_finance": {
        "name": "Manitoba Finance",
        "url": "https://news.gov.mb.ca/news/rss.xml",
        "scope": "MB",
    },
    "sk_finance": {
        "name": "Saskatchewan Finance",
        "url": "https://www.saskatchewan.ca/rss/government",
        "scope": "SK",
    },
    "ns_finance": {
        "name": "Nova Scotia Finance",
        "url": "https://novascotia.ca/news/rss/",
        "scope": "NS",
    },
    "nb_finance": {
        "name": "New Brunswick Finance",
        "url": "https://www2.gnb.ca/content/gnb/en/news.rss.xml",
        "scope": "NB",
    },
    "nl_finance": {
        "name": "Newfoundland Finance",
        "url": "https://www.gov.nl.ca/releases/feed/",
        "scope": "NL",
    },
    # Energy regulators
    "cer": {
        "name": "Canada Energy Regulator",
        "url": "https://www.cer-rec.gc.ca/en/about/news-room/rss.html",
        "scope": "federal",
        "topic": "energy_regulation",
    },
    "aer": {
        "name": "Alberta Energy Regulator",
        "url": "https://www.aer.ca/news/feed",
        "scope": "AB",
        "topic": "energy_regulation",
    },
}

POLICY_CATEGORIES = [
    "budget_capital_spending",
    "tax_incentive",
    "regulatory_change",
    "housing_policy",
    "energy_policy",
    "mining_royalty",
    "infrastructure_funding",
    "trade_policy",
    "indigenous_policy",
    "environmental_regulation",
    "immigration_workforce",
    "procurement_policy",
]

# ── Gemini Flash classification prompt ───────────────────────────────

POLICY_CLASSIFICATION_PROMPT = """You are classifying government news releases for a Canadian economic intelligence tracker.

An article is POLICY_RELEVANT if it describes:
- Budget or fiscal update with capital spending allocations
- Tax incentives or credits affecting business investment
- Regulatory changes to environmental assessment, permitting, or approvals
- Housing policy changes (zoning reform, accelerator programs)
- Energy policy (clean energy mandates, carbon pricing, electricity rules)
- Mining or resource royalty changes
- Infrastructure funding program announcements
- Trade policy changes affecting construction materials or investment
- Indigenous consultation or reconciliation policy changes
- Environmental regulation changes affecting project development
- Immigration or workforce policy affecting construction labour
- Procurement policy (P3 frameworks, buy-Canadian requirements)

NOT_RELEVANT: general political news, personnel appointments, routine admin, social services (unless facility construction).

Articles:
{articles}

Return JSON array:
[{{"index": 0, "classification": "POLICY_RELEVANT", "category": "housing_policy", "headline": "...", "snippet": "..."}}, ...]
Only include POLICY_RELEVANT articles in the output."""


# ── Feed processing ──────────────────────────────────────────────────

def _fetch_feed(feed_id, feed_info, since_days=7):
    """Fetch and parse a single RSS feed, returning recent entries."""
    url = feed_info["url"]
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    articles = []
    try:
        # patch-1.2: route through shared http_client (browser UA + certifi TLS
        # + retry) instead of the thin 'CAN-Macro-Dashboard/1.0' UA that several
        # provincial finance feeds bot-blocked.
        resp = http_client.get(url, timeout=15)
        if resp is None or resp.status_code != 200:
            status = 'network' if resp is None else resp.status_code
            print(f"[POLICY][{feed_id}] FAILED status={status}")
            return []
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries[:20]:
            # Check date
            published = None
            for date_field in ("published_parsed", "updated_parsed"):
                dt_tuple = getattr(entry, date_field, None)
                if dt_tuple:
                    try:
                        published = datetime(*dt_tuple[:6])
                    except (TypeError, ValueError):
                        pass
                    break
            if published and published < cutoff:
                continue

            articles.append({
                "feed_id": feed_id,
                "scope": feed_info.get("scope", "unknown"),
                "topic": feed_info.get("topic", "general"),
                "headline": getattr(entry, "title", ""),
                "snippet": getattr(entry, "summary", "")[:500],
                "url": getattr(entry, "link", ""),
                "published": published.isoformat() if published else None,
                # patch-1.2: every POLICY_FEEDS source is a government feed →
                # eligible for Layer-1 government_bypass during classification.
                "government_bypass": True,
            })
    except Exception as e:
        logger.debug(f"Policy feed {feed_id} failed: {e}")
    return articles


def fetch_all_policy_feeds(since_days=7):
    """Fetch all policy RSS feeds, return combined article list."""
    all_articles = []
    # patch-1.2 (D-10): per-feed counts so a dark feed is distinguishable from a
    # quiet week.
    per_feed = {}
    for feed_id, info in POLICY_FEEDS.items():
        articles = _fetch_feed(feed_id, info, since_days)
        per_feed[feed_id] = len(articles)
        all_articles.extend(articles)
    logger.info(f"Policy feeds: {len(all_articles)} articles from "
                f"{len(POLICY_FEEDS)} feeds")
    counts_str = ", ".join(f"{fid}={n}" for fid, n in sorted(per_feed.items()))
    print(f"[POLICY] Per-feed counts: {counts_str}")
    zero_feeds = [fid for fid, n in per_feed.items() if n == 0]
    if zero_feeds:
        print(f"[POLICY] Feeds returning 0 this run: {', '.join(zero_feeds)}")
    return all_articles


def classify_policy_articles(articles, max_batch=DEFAULT_MAX_BATCH):
    """Classify articles using Groq LLaMA 3.3 70B (replaces Gemini Flash).

    Returns list of policy-relevant articles with category.

    patch-1.2 (D-10): government_bypass — articles flagged 'government_bypass'
    (every POLICY_FEEDS source is a government feed) are retained as relevant
    even when the LLM does not surface them, per CLAUDE.md RSS-filter Layer 1.
    The LLM pass still runs to assign categories where it can; ``max_batch``
    (default DEFAULT_MAX_BATCH, was a hardcoded 30) bounds the LLM batch size.
    On LLM failure, government items still pass through (fail-open).
    """
    if not articles:
        return []

    from groq_client import generate as groq_generate

    batch = articles[:max_batch]

    # Index of government items so they can be retained regardless of the LLM.
    gov_indices = {i for i, a in enumerate(batch) if a.get("government_bypass")}

    relevant_by_idx = {}

    # Format articles for classification
    batch_text = "\n\n".join(
        f"[{i}] {a['headline']}\n{a['snippet'][:200]}"
        for i, a in enumerate(batch)
    )

    prompt = POLICY_CLASSIFICATION_PROMPT.format(articles=batch_text)
    system = "You are a policy classification assistant for Canadian economic intelligence."

    try:
        text = groq_generate(system, prompt)
        if text:
            # Parse JSON response
            import re
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text).strip()

            classified = json.loads(text)
            for item in classified:
                idx = item.get("index", -1)
                if 0 <= idx < len(batch):
                    article = batch[idx].copy()
                    article["category"] = item.get("category", "unknown")
                    article["classification"] = "POLICY_RELEVANT"
                    relevant_by_idx[idx] = article
    except Exception as e:
        logger.warning(f"Policy classification failed: {e}")
        # Fail-open for government sources only (handled by the bypass below).

    # Government_bypass: retain any government article the LLM did not surface.
    bypassed = 0
    for idx in gov_indices:
        if idx not in relevant_by_idx:
            article = batch[idx].copy()
            article["category"] = article.get("topic", "government_policy")
            article["classification"] = "POLICY_RELEVANT"
            article["government_bypass"] = True
            relevant_by_idx[idx] = article
            bypassed += 1

    relevant = [relevant_by_idx[i] for i in sorted(relevant_by_idx)]
    if bypassed:
        print(f"[POLICY] {bypassed} government items retained via government_bypass")
    return relevant


async def assess_policy_impact(policy_article, affected_projects,
                               indicator_context):
    """Use Claude Sonnet to assess a policy change's impact on capital investment."""
    from claude_reasoning import reason_with_claude_tracked

    system = (
        "You are a senior Canadian economic policy analyst. Assess how this "
        "government policy change affects capital investment and construction "
        "activity across Canada. Be specific about sectors, provinces, mechanism, "
        "magnitude (high/medium/low), and timeline (immediate/3-6mo/1-2yr). "
        "Reference specific projects from the database when possible."
    )

    project_summary = json.dumps([{
        "name": p.get("name"),
        "province": p.get("province") or (p.get("location", {}) or {}).get("province"),
        "sector": p.get("sector"),
        "value_millions": p.get("value_millions"),
        "status": p.get("status"),
    } for p in affected_projects[:20]], indent=2)

    user_prompt = f"""POLICY ANNOUNCEMENT:
{policy_article['headline']}
{policy_article['snippet']}
Source: {policy_article.get('url', 'unknown')}
Scope: {policy_article.get('scope', 'unknown')}
Category: {policy_article.get('category', 'unknown')}

POTENTIALLY AFFECTED PROJECTS:
{project_summary}

CURRENT ECONOMIC CONTEXT:
{json.dumps(indicator_context, indent=2)}

Assess the economic impact. Structure as:
1. SUMMARY (2-3 sentences)
2. AFFECTED SECTORS AND MECHANISM
3. SPECIFIC PROJECTS IMPACTED
4. MAGNITUDE AND TIMELINE
5. RISKS OR UNCERTAINTIES"""

    return await reason_with_claude_tracked(
        system, user_prompt, task_name="policy_assessment", max_tokens=2000,
    )


def process_policy_feeds(conn=None, since_days=7, db=None,
                         max_batch=DEFAULT_MAX_BATCH):
    """Main entry point: fetch, classify, and store policy developments.

    Args:
        conn: sqlite3.Connection from db.py (preferred)
        since_days: how many days back to fetch articles
        db: deprecated Firestore client; ignored (kept for backward compatibility)
        max_batch: classification batch size (patch-1.2: was hardcoded 30).

    Returns list of policy-relevant articles with classifications.
    """
    print("\n[POLICY] Scanning policy feeds...")

    # 1. Fetch feeds
    articles = fetch_all_policy_feeds(since_days)
    if not articles:
        print("  [POLICY] No articles from feeds")
        # patch-1.2 (D-10): min-yield DEGRADE log — all feeds dark this run.
        print("[POLICY DEGRADED] 0 items — no articles from any provincial/federal feed")
        return []

    # 2. Classify (government_bypass retains gov items even if LLM misses them)
    relevant = classify_policy_articles(articles, max_batch=max_batch)
    print(f"  [POLICY] {len(relevant)}/{len(articles)} articles policy-relevant")
    if not relevant:
        print("[POLICY DEGRADED] 0 items — 0 relevant of "
              f"{len(articles)} fetched (check per-feed counts above)")

    # 3. Store in SQLite
    if relevant and conn and hasattr(conn, 'execute'):
        try:
            from db import save_dashboard_state
            week_key = datetime.utcnow().strftime("%Y-W%W")
            save_dashboard_state(conn, f"policy_developments_{week_key}", {
                "articles": relevant,
                "count": len(relevant),
                "scanned_at": datetime.utcnow().isoformat(),
                "total_feeds": len(POLICY_FEEDS),
                "total_articles": len(articles),
            })
        except Exception as e:
            logger.warning(f"Failed to store policy developments: {e}")

    # Summarize by category
    by_cat = {}
    for a in relevant:
        cat = a.get("category", "unknown")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    if by_cat:
        print(f"  [POLICY] Categories: {by_cat}")

    return relevant
