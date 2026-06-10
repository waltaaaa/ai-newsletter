"""quality-pass-1.4 G5 — tiered project-alert polling tests.

Covers: tier classification + due-date math, value-ranked hard cap
(overflow defers, never deactivates), and the call-site gate change
(due-based check every weekly run instead of first-week-of-month).

All HTTP is mocked.
"""
import asyncio
import inspect
import sqlite3
from datetime import datetime, timedelta

import pytest

import project_alert_tracker as pat
from pipeline_config import PROVINCE_GDP_THRESHOLDS


# ── Tier classification ───────────────────────────────────────────────────────

def test_under_construction_is_weekly():
    assert pat.classify_alert_tier(
        "Under Construction", None, "Ontario", 0) == "weekly"


def test_high_value_is_weekly_even_if_not_uc():
    on_threshold = PROVINCE_GDP_THRESHOLDS["ON"]
    assert pat.classify_alert_tier(
        "Proposed", 2 * on_threshold, "Ontario", 0) == "weekly"
    assert pat.classify_alert_tier(
        "Approved", 2.5 * on_threshold, "ON", 0) == "weekly"


def test_uc_beats_stale_and_below_threshold():
    # Weekly precedence: a stale, below-threshold UC project still polls weekly
    assert pat.classify_alert_tier(
        "Under Construction", 1_000_000, "Ontario", 1) == "weekly"


def test_standard_statuses_are_monthly():
    for status in ("Proposed", "Under Review", "Approved"):
        assert pat.classify_alert_tier(status, None, "Ontario", 0) == "monthly"
    # Unclassified statuses default to monthly
    assert pat.classify_alert_tier("Announced", None, "Ontario", 0) == "monthly"


def test_stale_or_below_threshold_is_quarterly():
    assert pat.classify_alert_tier("Proposed", None, "Ontario", 1) == "quarterly"
    # Below the ON threshold ($500M)
    assert pat.classify_alert_tier(
        "Proposed", 10_000_000, "Ontario", 0) == "quarterly"


def test_province_threshold_accepts_name_and_code():
    assert pat._province_threshold("Ontario") == PROVINCE_GDP_THRESHOLDS["ON"]
    assert pat._province_threshold("ON") == PROVINCE_GDP_THRESHOLDS["ON"]
    assert pat._province_threshold("Nunavut") == PROVINCE_GDP_THRESHOLDS["NU"]
    assert pat._province_threshold("") == 0.0


# ── Due-date math ─────────────────────────────────────────────────────────────

_NOW = datetime(2026, 6, 10, 12, 0, 0)


def _iso(days_ago):
    return (_NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_due_date_math_per_tier():
    # weekly: due after 7 days
    assert pat.is_alert_due("weekly", _iso(8), now=_NOW)
    assert not pat.is_alert_due("weekly", _iso(3), now=_NOW)
    # monthly: due after 28 days
    assert pat.is_alert_due("monthly", _iso(29), now=_NOW)
    assert not pat.is_alert_due("monthly", _iso(20), now=_NOW)
    # quarterly: due after 90 days
    assert pat.is_alert_due("quarterly", _iso(91), now=_NOW)
    assert not pat.is_alert_due("quarterly", _iso(60), now=_NOW)


def test_never_checked_alerts_are_always_due():
    assert pat.is_alert_due("weekly", None, now=_NOW)
    assert pat.is_alert_due("monthly", "", now=_NOW)
    assert pat.is_alert_due("quarterly", "garbage-date", now=_NOW)


# ── Due selection + cap ranking ───────────────────────────────────────────────

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE projects (
        norm_key TEXT PRIMARY KEY, name TEXT, province TEXT, proponent TEXT,
        cma TEXT, status TEXT, parsed_value REAL, is_stale INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE project_alerts (
        id INTEGER PRIMARY KEY, project_id INTEGER, norm_key TEXT UNIQUE,
        query_text TEXT, rss_url TEXT, last_checked TEXT,
        last_found_articles INTEGER DEFAULT 0, check_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1)""")
    return conn


def _add(conn, key, status="Under Construction", value=None, stale=0,
         last_checked=None, active=1, province="Ontario"):
    conn.execute(
        "INSERT INTO projects (norm_key, name, province, status, parsed_value, is_stale)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (key, key, province, status, value, stale))
    conn.execute(
        "INSERT INTO project_alerts (norm_key, query_text, rss_url, last_checked, active)"
        " VALUES (?, ?, ?, ?, ?)",
        (key, f"q-{key}", f"https://news.google.com/rss?q={key}", last_checked, active))


def test_get_due_alerts_selects_only_due():
    conn = _make_conn()
    # UC, checked 8 days ago -> weekly, due
    _add(conn, "uc_due", last_checked=_iso(8))
    # UC, checked 2 days ago -> weekly, NOT due
    _add(conn, "uc_fresh", last_checked=_iso(2))
    # Proposed, checked 20 days ago -> monthly, NOT due
    _add(conn, "prop_fresh", status="Proposed", last_checked=_iso(20))
    # Proposed, checked 30 days ago -> monthly, due
    _add(conn, "prop_due", status="Proposed", last_checked=_iso(30))
    # Stale, checked 60 days ago -> quarterly, NOT due
    _add(conn, "stale_fresh", status="Proposed", stale=1, last_checked=_iso(60))
    # Inactive alert never selected
    _add(conn, "inactive", last_checked=_iso(100), active=0)

    result = pat.get_due_alerts(conn, now=_NOW)
    keys = {a["norm_key"] for a in result["alerts"]}
    assert keys == {"uc_due", "prop_due"}
    assert result["due_total"] == 2
    assert result["overflow"] == 0
    assert result["tier_counts"]["weekly"] == 1
    assert result["tier_counts"]["monthly"] == 1


def test_cap_ranks_by_value_desc_nulls_last_and_defers_overflow():
    conn = _make_conn()
    # All UC + never checked -> all due weekly
    _add(conn, "v_900m", value=900_000_000)
    _add(conn, "v_null", value=None)
    _add(conn, "v_2b", value=2_000_000_000)
    _add(conn, "v_50m", value=50_000_000)
    _add(conn, "v_null2", value=None)

    result = pat.get_due_alerts(conn, now=_NOW, max_polls=3)
    ranked = [a["norm_key"] for a in result["alerts"]]
    assert ranked == ["v_2b", "v_900m", "v_50m"]  # NULLS LAST -> cut first
    assert result["due_total"] == 5
    assert result["overflow"] == 2

    # The cap must NEVER deactivate the deferred alerts
    active = conn.execute(
        "SELECT COUNT(*) FROM project_alerts WHERE active = 1").fetchone()[0]
    assert active == 5


def test_max_polls_default_constant():
    assert pat.MAX_ALERT_POLLS_PER_RUN == 1200


# ── Full check run with mocked HTTP ───────────────────────────────────────────

def test_run_check_polls_due_set_and_updates_metadata(monkeypatch):
    conn = _make_conn()
    conn.row_factory = sqlite3.Row
    _add(conn, "uc_due", last_checked=_iso(10))       # due
    _add(conn, "uc_fresh", last_checked=_iso(1))      # not due
    # Terminal project: must be deactivated, never polled
    _add(conn, "done", status="Completed", last_checked=_iso(100))

    fetched_urls = []

    async def fake_fetch(session, feed, semaphore):
        fetched_urls.append(feed["url"])
        return [{"url": "https://example.com/article-1", "title": "update"}]

    import google_news_rss_search
    monkeypatch.setattr(google_news_rss_search, "fetch_rss_feed", fake_fetch)
    # No jitter in tests
    monkeypatch.setattr(pat, "_ALERT_FETCH_JITTER", (0.0, 0.0))

    result = asyncio.run(pat.run_monthly_alert_check(conn))

    assert result["alerts_checked"] == 1
    assert result["deactivated"] == 1
    assert result["articles_found"] == 1
    assert fetched_urls == ["https://news.google.com/rss?q=uc_due"]
    # Articles tagged with the alert discovery tier
    assert result["articles"][0]["_discovery_tier"] == "project_alert"

    # last_checked updated ONLY for the polled alert
    polled = conn.execute(
        "SELECT last_checked, check_count FROM project_alerts WHERE norm_key='uc_due'"
    ).fetchone()
    assert polled["check_count"] == 1
    assert polled["last_checked"] != _iso(10)
    fresh = conn.execute(
        "SELECT check_count FROM project_alerts WHERE norm_key='uc_fresh'"
    ).fetchone()
    assert fresh["check_count"] == 0


# ── Call-site gate change ─────────────────────────────────────────────────────

def test_discovery_call_site_no_longer_gated_on_first_week():
    import phases.discovery as discovery
    src = inspect.getsource(discovery.run)
    # The due-based check runs every weekly run
    assert "run_monthly_alert_check_sync" in src
    assert "if is_first_week_of_month()" not in src


def test_is_first_week_helper_kept_for_compat():
    # Additive-only: the old helper still exists and returns a bool
    assert isinstance(pat.is_first_week_of_month(), bool)
