"""
project_alert_tracker.py -- Automatic Google News RSS tracking per project.

When the pipeline discovers a new investment project, it is registered here
with a targeted Google News RSS query. On the first weekly pipeline run of
each month, all active alerts are fetched, filtered, and fed back into the
discovery pipeline for extraction and status updates.

Projects are deactivated from tracking when their status reaches Cancelled
or Complete. On Hold / Suspended projects stay tracked since they may resume.
"""

import asyncio
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

# Terminal states that trigger alert deactivation
_DEACTIVATE_STATUSES = {"Cancelled", "Complete"}


# ── Query construction ───────────────────────────────────────────────

def build_alert_query(project: dict) -> str:
    """Build a Google News search query for a tracked project.

    Args:
        project: dict with at least 'name' and 'province'. May also have
                 'proponent' and 'cma'.

    Returns:
        Search query string like: "Project Name" Proponent Province Canada
    """
    from google_news_rss_search import PROV_NAMES

    name = (project.get("name") or "").strip()
    province = project.get("province") or ""
    proponent = (project.get("proponent") or "").strip()
    cma = (project.get("cma") or "").strip()

    province_full = PROV_NAMES.get(province, province)

    # Quoted project name, truncated for overly long names
    query_name = name[:60] if len(name) > 60 else name
    parts = [f'"{query_name}"']

    # Add proponent if meaningful
    skip_proponents = {"unknown", "", "various", "government of canada",
                       "government", "provincial government", "n/a"}
    if proponent and proponent.lower() not in skip_proponents:
        parts.append(proponent[:30])

    # Add CMA if single location (skip compound like "Toronto|Ottawa")
    if cma and "|" not in cma:
        parts.append(cma)

    parts.append(province_full)
    parts.append("Canada")

    return " ".join(parts)


# ── Registration ─────────────────────────────────────────────────────

def register_new_project_alert(conn, norm_key: str) -> bool:
    """Register a single project for alert tracking.

    Idempotent — skips if already registered or project is in a terminal state.

    Returns:
        True if registered, False if skipped.
    """
    from google_news_rss_search import build_google_news_url
    from db import get_project

    project = get_project(conn, norm_key)
    if not project:
        return False

    # Skip terminal projects
    status = (project.get("status") or "").strip()
    if status in _DEACTIVATE_STATUSES:
        return False

    query = build_alert_query(project)
    rss_url = build_google_news_url(query)

    try:
        conn.execute(
            """INSERT INTO project_alerts (project_id, norm_key, query_text, rss_url)
               VALUES (
                   (SELECT rowid FROM projects WHERE norm_key = ?),
                   ?, ?, ?
               )
               ON CONFLICT(norm_key) DO NOTHING""",
            (norm_key, norm_key, query, rss_url),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Alert registration failed for {norm_key}: {e}")
        return False


def register_batch(conn, norm_keys: list) -> int:
    """Register multiple projects for alert tracking.

    Args:
        conn: SQLite connection
        norm_keys: list of norm_key strings for newly inserted projects

    Returns:
        Count of newly registered alerts.
    """
    if not norm_keys:
        return 0

    registered = 0
    for key in norm_keys:
        try:
            if register_new_project_alert(conn, key):
                registered += 1
        except Exception as e:
            logger.warning(f"Alert registration error for {key}: {e}")
    return registered


# ── Deactivation ─────────────────────────────────────────────────────

def deactivate_terminal_projects(conn) -> int:
    """Deactivate alerts for projects that reached Cancelled or Complete.

    Returns:
        Count of deactivated alerts.
    """
    cursor = conn.execute(
        """UPDATE project_alerts SET active = 0
           WHERE active = 1 AND norm_key IN (
               SELECT norm_key FROM projects
               WHERE status IN ('Cancelled', 'Complete')
           )"""
    )
    conn.commit()
    count = cursor.rowcount
    if count:
        logger.info(f"Deactivated {count} project alerts (terminal status)")
    return count


# ── Monthly check logic ──────────────────────────────────────────────

def is_first_week_of_month() -> bool:
    """Return True if today is day 1-7 (first weekly run of the month)."""
    return date.today().day <= 7


def _get_active_alerts(conn) -> list:
    """Fetch all active alert records joined with project metadata."""
    rows = conn.execute(
        """SELECT pa.id, pa.norm_key, pa.query_text, pa.rss_url,
                  p.name, p.province, p.proponent, p.cma, p.status
           FROM project_alerts pa
           JOIN projects p ON pa.norm_key = p.norm_key
           WHERE pa.active = 1"""
    ).fetchall()
    return [dict(r) for r in rows]


async def run_monthly_alert_check(conn) -> dict:
    """Fetch Google News RSS for all active tracked projects.

    Steps:
        1. Deactivate terminal projects
        2. Fetch active alerts
        3. Batch RSS fetching (semaphore 50)
        4. Deduplicate articles by URL
        5. Update tracking metadata

    Returns:
        dict with keys: articles, alerts_checked, deactivated, articles_found
    """
    import aiohttp
    from google_news_rss_search import fetch_rss_feed

    # Step 1: Clean up terminal projects
    deactivated = deactivate_terminal_projects(conn)

    # Step 2: Get active alerts
    alerts = _get_active_alerts(conn)
    if not alerts:
        return {
            "articles": [],
            "alerts_checked": 0,
            "deactivated": deactivated,
            "articles_found": 0,
        }

    print(f"  [ALERT-TRACKER] Checking {len(alerts)} active project alerts...")

    # Step 3: Batch RSS fetch
    semaphore = asyncio.Semaphore(50)
    all_articles = []
    seen_urls = set()
    alert_article_counts = {}  # alert_id -> count

    async with aiohttp.ClientSession() as session:
        # Process in batches of 500
        for batch_start in range(0, len(alerts), 500):
            batch = alerts[batch_start:batch_start + 500]

            # Build feed dicts compatible with fetch_rss_feed
            feeds = []
            feed_to_alert = {}
            for alert in batch:
                feed = {
                    "url": alert["rss_url"],
                    "short_query": alert["query_text"][:80],
                    "province": alert.get("province"),
                    "sector": None,
                    "language": "en",
                }
                feeds.append(feed)
                feed_to_alert[id(feed)] = alert

            # Concurrent fetch
            tasks = [
                fetch_rss_feed(session, feed, semaphore) for feed in feeds
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect articles with dedup
            for feed, result in zip(feeds, results):
                alert = feed_to_alert[id(feed)]
                if isinstance(result, Exception):
                    logger.warning(
                        f"Alert feed error ({alert['norm_key']}): {result}"
                    )
                    alert_article_counts[alert["id"]] = 0
                    continue

                count = 0
                for article in (result or []):
                    url = article.get("url") or article.get("link") or ""
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        # Override discovery tier tag
                        article["_discovery_tier"] = "project_alert"
                        article["_alert_norm_key"] = alert["norm_key"]
                        article["_province"] = alert.get("province")
                        all_articles.append(article)
                        count += 1
                alert_article_counts[alert["id"]] = count

    # Step 4: Update tracking metadata
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for alert in alerts:
        try:
            conn.execute(
                """UPDATE project_alerts
                   SET last_checked = ?, last_found_articles = ?,
                       check_count = check_count + 1
                   WHERE id = ?""",
                (now_iso, alert_article_counts.get(alert["id"], 0), alert["id"]),
            )
        except Exception as e:
            logger.warning(f"Alert metadata update failed ({alert['id']}): {e}")
    conn.commit()

    print(
        f"  [ALERT-TRACKER] {len(alerts)} alerts checked, "
        f"{len(all_articles)} unique articles found"
    )

    return {
        "articles": all_articles,
        "alerts_checked": len(alerts),
        "deactivated": deactivated,
        "articles_found": len(all_articles),
    }


def run_monthly_alert_check_sync(conn) -> dict:
    """Synchronous wrapper for run_monthly_alert_check.

    Handles the asyncio event loop, including nested loops via nest_asyncio.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an event loop — use nest_asyncio
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.warning("nest_asyncio not available; creating new loop")
            loop = None

    if loop and loop.is_running():
        return loop.run_until_complete(run_monthly_alert_check(conn))
    else:
        return asyncio.run(run_monthly_alert_check(conn))
