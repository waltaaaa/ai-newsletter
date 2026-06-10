"""
project_alert_tracker.py -- Automatic Google News RSS tracking per project.

When the pipeline discovers a new investment project, it is registered here
with a targeted Google News RSS query.

quality-pass-1.4 G5: polling is TIER-BASED and due-driven, computed at query
time (no schema change). Every weekly run selects the alerts whose tier
cadence has elapsed:

  - weekly    (7d):  status 'Under Construction' OR parsed_value >= 2x the
                     province GDP threshold
  - monthly  (28d):  Proposed / Under Review / Approved (and any status not
                     otherwise classified)
  - quarterly(90d):  is_stale=1 or parsed_value below the province threshold

A hard cap (MAX_ALERT_POLLS_PER_RUN) ranks the due set by parsed_value DESC
(NULLS LAST); overflow simply waits for the next run — alerts are never
deactivated by the cap.

Projects are deactivated from tracking when their status reaches Cancelled
or Complete. On Hold / Suspended projects stay tracked since they may resume.
"""

import asyncio
import logging
import random
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

# Terminal states that trigger alert deactivation
_DEACTIVATE_STATUSES = {"Cancelled", "Complete", "Completed"}  # M-3: include 'Completed' variant

# ── G5: tier configuration ───────────────────────────────────────────

# Hard cap on alert polls per run. Overflow waits for the next run;
# the cap NEVER deactivates an alert.
MAX_ALERT_POLLS_PER_RUN = 1200

# Concurrency lowered from 50 → 20 (G5) and per-fetch jitter added so the
# every-week due-based polling stays under Google News rate-limit radar.
_ALERT_FETCH_CONCURRENCY = 20
_ALERT_FETCH_JITTER = (0.2, 1.0)

# Tier cadences in days
TIER_DUE_DAYS = {"weekly": 7, "monthly": 28, "quarterly": 90}

_MONTHLY_STATUSES = {"Proposed", "Under Review", "Approved"}

# Weekly tier: parsed_value >= multiplier x province threshold
_WEEKLY_VALUE_MULTIPLIER = 2.0


def _province_threshold(province: str) -> float:
    """Canonical province GDP threshold (accepts full name or 2-letter code)."""
    try:
        from pipeline_config import PROVINCE_GDP_THRESHOLDS, PROVINCES
    except ImportError:
        return 0.0
    prov = (province or "").strip()
    if prov.upper() in PROVINCE_GDP_THRESHOLDS:
        return float(PROVINCE_GDP_THRESHOLDS[prov.upper()])
    for p in PROVINCES:
        if p.get("name", "").lower() == prov.lower():
            return float(p.get("threshold_val") or 0)
    return 0.0


def classify_alert_tier(status: str, parsed_value, province: str,
                        is_stale) -> str:
    """Classify an alert into its polling tier. Pure function (G5 tests).

    Precedence: weekly beats quarterly beats monthly — an Under Construction
    project polls weekly even if it is stale or below threshold.
    """
    status = (status or "").strip()
    threshold = _province_threshold(province)
    value = None
    try:
        if parsed_value is not None:
            value = float(parsed_value)
    except (TypeError, ValueError):
        value = None

    if status == "Under Construction":
        return "weekly"
    if value is not None and threshold > 0 and value >= _WEEKLY_VALUE_MULTIPLIER * threshold:
        return "weekly"
    if (is_stale in (1, True)) or (
            value is not None and threshold > 0 and value < threshold):
        return "quarterly"
    if status in _MONTHLY_STATUSES:
        return "monthly"
    return "monthly"


def is_alert_due(tier: str, last_checked, now: datetime | None = None) -> bool:
    """True if the alert's tier cadence has elapsed since last_checked.

    Never-checked alerts (NULL/unparseable last_checked) are always due.
    """
    now = now or datetime.utcnow()
    if not last_checked:
        return True
    raw = str(last_checked).strip().rstrip("Z")
    parsed = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw[:19] if "T" in fmt or " " in fmt else raw[:10], fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return True
    days = TIER_DUE_DAYS.get(tier, TIER_DUE_DAYS["monthly"])
    return (now - parsed) > timedelta(days=days)


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
               WHERE status IN ('Cancelled', 'Complete', 'Completed')
           )"""
    )
    conn.commit()
    count = cursor.rowcount
    if count:
        logger.info(f"Deactivated {count} project alerts (terminal status)")
    return count


# ── M-3: per-status alert prioritization ─────────────────────────────
#
# Audit found only 194/1,055 (18%) of Under Construction projects carry an
# alert, yet UC projects are the most likely to change status (construction
# milestones, delays, completion). prioritize_alerts() guarantees every UC
# project has an active alert. Runs every weekly run (independent of the
# is_first_week_of_month() gate for the monthly fetch).

def prioritize_alerts(conn) -> dict:
    """Ensure every Under Construction project carries an active alert.

    Iterates the projects table looking for status='Under Construction'
    rows that either have no project_alerts entry or have one with
    active=0, and reactivates / registers them.

    Idempotent. Safe to call every weekly run.

    Returns:
        dict with keys:
          - under_constr_total:        count of UC projects in projects table
          - under_constr_with_alerts:  count with active project_alerts row
          - alerts_created:            new alerts registered this call
          - alerts_reactivated:        alerts flipped from active=0 to active=1
    """
    try:
        rows = conn.execute(
            """SELECT p.norm_key,
                      COALESCE(pa.active, -1) AS alert_active
               FROM projects p
               LEFT JOIN project_alerts pa ON pa.norm_key = p.norm_key
               WHERE p.status = 'Under Construction'"""
        ).fetchall()
    except Exception as e:
        logger.warning(f"prioritize_alerts query failed: {e}")
        return {
            "under_constr_total": 0,
            "under_constr_with_alerts": 0,
            "alerts_created": 0,
            "alerts_reactivated": 0,
        }

    total = len(rows)
    with_alerts = 0
    created = 0
    reactivated = 0

    for row in rows:
        norm_key = row[0] if not hasattr(row, 'keys') else row['norm_key']
        alert_active = row[1] if not hasattr(row, 'keys') else row['alert_active']

        if alert_active == 1:
            with_alerts += 1
            continue
        if alert_active == 0:
            # alert exists but is deactivated — reactivate
            try:
                conn.execute(
                    "UPDATE project_alerts SET active = 1 WHERE norm_key = ?",
                    (norm_key,),
                )
                reactivated += 1
                with_alerts += 1
            except Exception as e:
                logger.warning(f"Reactivate alert {norm_key} failed: {e}")
        else:
            # alert_active == -1 means no alert row exists yet — register
            try:
                if register_new_project_alert(conn, norm_key):
                    created += 1
                    with_alerts += 1
            except Exception as e:
                logger.warning(f"Register alert {norm_key} failed: {e}")

    try:
        conn.commit()
    except Exception:
        pass

    print(
        f"  [ALERTS] {with_alerts}/{total} Under Construction projects have alerts "
        f"({created} created, {reactivated} reactivated)"
    )

    return {
        "under_constr_total": total,
        "under_constr_with_alerts": with_alerts,
        "alerts_created": created,
        "alerts_reactivated": reactivated,
    }


# ── Due-based check logic (G5; formerly monthly) ─────────────────────

def is_first_week_of_month() -> bool:
    """Return True if today is day 1-7 (first weekly run of the month).

    G5: no longer gates the alert check (the due-based selection runs every
    weekly run); kept for backward compatibility (additive-only rule).
    """
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


def get_due_alerts(conn, now: datetime | None = None,
                   max_polls: int = MAX_ALERT_POLLS_PER_RUN) -> dict:
    """G5: select the alerts whose tier cadence has elapsed.

    Joins projects for status / parsed_value / is_stale, classifies each
    active alert into weekly / monthly / quarterly, keeps the due ones,
    ranks by parsed_value DESC NULLS LAST and applies the hard cap.

    Returns dict with keys:
        alerts        — capped, ranked list of due alert dicts
        due_total     — due count before the cap
        overflow      — alerts deferred to the next run by the cap
        tier_counts   — {tier: due count} (pre-cap)
    """
    cursor = conn.execute(
        """SELECT pa.id, pa.norm_key, pa.query_text, pa.rss_url,
                  pa.last_checked,
                  p.name, p.province, p.proponent, p.cma, p.status,
                  p.parsed_value, p.is_stale
           FROM project_alerts pa
           JOIN projects p ON pa.norm_key = p.norm_key
           WHERE pa.active = 1"""
    )
    columns = [d[0] for d in cursor.description]
    rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

    due = []
    tier_counts = {"weekly": 0, "monthly": 0, "quarterly": 0}
    for row in rows:
        tier = classify_alert_tier(
            row.get("status"), row.get("parsed_value"),
            row.get("province"), row.get("is_stale"))
        if is_alert_due(tier, row.get("last_checked"), now=now):
            row["_tier"] = tier
            tier_counts[tier] += 1
            due.append(row)

    # Rank by parsed_value DESC, NULLS LAST
    def _rank_key(r):
        v = r.get("parsed_value")
        try:
            v = float(v) if v is not None else None
        except (TypeError, ValueError):
            v = None
        return (v is None, -(v or 0.0))

    due.sort(key=_rank_key)
    capped = due[:max_polls]
    return {
        "alerts": capped,
        "due_total": len(due),
        "overflow": max(0, len(due) - len(capped)),
        "tier_counts": tier_counts,
    }


async def _fetch_feed_with_jitter(session, feed, semaphore, fetch_fn):
    """G5: jittered fetch wrapper — spreads request starts 0.2-1.0s apart."""
    await asyncio.sleep(random.uniform(*_ALERT_FETCH_JITTER))
    return await fetch_fn(session, feed, semaphore)


async def run_monthly_alert_check(conn) -> dict:
    """Fetch Google News RSS for the DUE subset of tracked projects (G5).

    Steps:
        1. Deactivate terminal projects
        2. Select due alerts (tiered cadence, value-ranked, hard-capped)
        3. Batch RSS fetching (semaphore 20, jittered)
        4. Deduplicate articles by URL
        5. Update tracking metadata (only for alerts actually polled)

    Returns:
        dict with keys: articles, alerts_checked, deactivated, articles_found,
        due_total, overflow, tier_counts
    """
    import aiohttp
    from google_news_rss_search import fetch_rss_feed

    # Step 1: Clean up terminal projects
    deactivated = deactivate_terminal_projects(conn)

    # Step 2: Get due alerts (G5 tier selection at query time)
    due = get_due_alerts(conn)
    alerts = due["alerts"]
    if due["overflow"]:
        print(f"  [ALERT-TRACKER] {due['due_total']} alerts due; polling top "
              f"{len(alerts)} by value (cap {MAX_ALERT_POLLS_PER_RUN}); "
              f"{due['overflow']} deferred to next run")
    if not alerts:
        return {
            "articles": [],
            "alerts_checked": 0,
            "deactivated": deactivated,
            "articles_found": 0,
            "due_total": due["due_total"],
            "overflow": due["overflow"],
            "tier_counts": due["tier_counts"],
        }

    tc = due["tier_counts"]
    print(f"  [ALERT-TRACKER] Checking {len(alerts)} due project alerts "
          f"(weekly {tc['weekly']} / monthly {tc['monthly']} / "
          f"quarterly {tc['quarterly']} due)...")

    # Step 3: Batch RSS fetch (G5: semaphore 20 + jitter)
    semaphore = asyncio.Semaphore(_ALERT_FETCH_CONCURRENCY)
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

            # Concurrent fetch (jittered, G5)
            tasks = [
                _fetch_feed_with_jitter(session, feed, semaphore, fetch_rss_feed)
                for feed in feeds
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
        "due_total": due["due_total"],
        "overflow": due["overflow"],
        "tier_counts": due["tier_counts"],
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
