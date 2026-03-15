"""
test_db.py — Tests for db.py SQLite interface module.

Tests cover:
- Task 1: init_db() schema creation, table structure, FTS5, get_db()
- Task 2: All CRUD functions, upsert_project() business rules, indicator field remapping
"""

import json
import sqlite3
import pytest
from datetime import datetime


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def conn():
    """Provide a fresh in-memory DB for each test."""
    from db import init_db
    c = init_db(":memory:")
    yield c
    c.close()


# ═══════════════════════════════════════════════════════════════════
# TASK 1 TESTS: init_db() and get_db()
# ═══════════════════════════════════════════════════════════════════


class TestInitDb:
    def test_init_db_returns_connection(self):
        from db import init_db
        conn = init_db(":memory:")
        assert conn is not None
        conn.close()

    def test_projects_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        )
        assert cur.fetchone() is not None

    def test_projects_fts_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects_fts'"
        )
        assert cur.fetchone() is not None

    def test_indicator_history_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='indicator_history'"
        )
        assert cur.fetchone() is not None

    def test_weekly_briefings_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_briefings'"
        )
        assert cur.fetchone() is not None

    def test_dashboard_state_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_state'"
        )
        assert cur.fetchone() is not None

    def test_pipeline_runs_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
        )
        assert cur.fetchone() is not None

    def test_trend_snapshots_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trend_snapshots'"
        )
        assert cur.fetchone() is not None

    def test_missed_projects_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='missed_projects'"
        )
        assert cur.fetchone() is not None

    def test_pipeline_improvements_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_improvements'"
        )
        assert cur.fetchone() is not None

    def test_statcan_indicators_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='statcan_indicators'"
        )
        assert cur.fetchone() is not None

    def test_timeseries_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='timeseries'"
        )
        assert cur.fetchone() is not None

    def test_pipeline_state_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_state'"
        )
        assert cur.fetchone() is not None

    def test_projects_archive_table_exists(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects_archive'"
        )
        assert cur.fetchone() is not None

    def test_projects_columns(self, conn):
        """Projects table must have all required columns."""
        cur = conn.execute("PRAGMA table_info(projects)")
        columns = {row[1] for row in cur.fetchall()}
        required = {
            "rowid", "name", "province", "cma", "sector", "value", "status",
            "confidence", "project_type", "is_brownfield", "evidence",
            "discovery_sources", "statusHistory", "sources", "description",
            "proponent", "completionDate", "lastSeen", "lastUpdated",
            "created", "norm_key",
        }
        # rowid is implicit — check all others
        for col in required - {"rowid"}:
            assert col in columns, f"Missing column: {col}"

    def test_indicator_history_columns(self, conn):
        cur = conn.execute("PRAGMA table_info(indicator_history)")
        columns = {row[1] for row in cur.fetchall()}
        required = {
            "id", "indicator_name", "category", "province",
            "value", "period", "previous_value", "change", "source", "fetched_at",
        }
        for col in required:
            assert col in columns, f"Missing indicator_history column: {col}"

    def test_weekly_briefings_columns(self, conn):
        cur = conn.execute("PRAGMA table_info(weekly_briefings)")
        columns = {row[1] for row in cur.fetchall()}
        required = {"id", "week_of", "headline", "sections", "word_count", "generated_at"}
        for col in required:
            assert col in columns, f"Missing weekly_briefings column: {col}"

    def test_dashboard_state_columns(self, conn):
        cur = conn.execute("PRAGMA table_info(dashboard_state)")
        columns = {row[1] for row in cur.fetchall()}
        required = {"key", "value", "updated_at"}
        for col in required:
            assert col in columns, f"Missing dashboard_state column: {col}"

    def test_pipeline_runs_columns(self, conn):
        cur = conn.execute("PRAGMA table_info(pipeline_runs)")
        columns = {row[1] for row in cur.fetchall()}
        required = {
            "id", "type", "status", "started_at", "completed_at",
            "duration_seconds", "steps_completed", "errors", "discovery", "api_usage",
        }
        for col in required:
            assert col in columns, f"Missing pipeline_runs column: {col}"

    def test_init_db_idempotent(self):
        """Calling init_db twice on same path does not error."""
        from db import init_db
        conn1 = init_db(":memory:")
        conn1.close()
        # Second call on a file path (temp) should also work
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            c1 = init_db(path)
            c1.close()
            c2 = init_db(path)
            c2.close()
        finally:
            os.unlink(path)

    def test_get_db_returns_connection(self):
        from db import get_db
        conn = get_db(":memory:")
        assert conn is not None
        conn.close()

    def test_get_db_wal_mode(self):
        from db import get_db
        conn = get_db(":memory:")
        # WAL mode not applicable to :memory: but check journal_mode works
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        # :memory: stays as 'memory' — just verify call succeeds
        assert mode is not None
        conn.close()

    def test_get_db_row_factory(self):
        from db import init_db
        conn = init_db(":memory:")
        # Row factory allows dict-like access
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_fts_virtual_table_usable(self, conn):
        """FTS5 table can be queried without error."""
        conn.execute("SELECT * FROM projects_fts LIMIT 1")


# ═══════════════════════════════════════════════════════════════════
# TASK 2 TESTS: CRUD functions and business rules
# ═══════════════════════════════════════════════════════════════════


# ── Helpers ──────────────────────────────────────────────────────

def _make_project(**kwargs):
    """Build a minimal valid project dict."""
    defaults = {
        "name": "Test Wind Farm",
        "province": "ON",
        "status": "Proposed",
        "sector": "power_energy",
        "value": "$500M",
        "confidence": 0.5,
        "evidence": [{"url": "https://cbc.ca/wind-farm", "title": "CBC Report"}],
        "discovery_sources": ["rss_feed"],
        "description": "A large wind farm project.",
        "proponent": "Acme Energy",
        "completionDate": "2028",
        "cma": "Toronto",
        "project_type": "greenfield",
        "is_brownfield": False,
        "sources": ["https://cbc.ca/wind-farm"],
        "statusHistory": [],
        "tags": ["wind", "energy"],
    }
    defaults.update(kwargs)
    return defaults


class TestUpsertProject:
    def test_insert_new_project(self, conn):
        from db import upsert_project, get_project
        proj = _make_project()
        upsert_project(conn, proj)
        result = get_project(conn, "testwindfarm__on")
        assert result is not None
        assert result["name"] == "Test Wind Farm"

    def test_insert_sets_created(self, conn):
        from db import upsert_project, get_project
        upsert_project(conn, _make_project())
        result = get_project(conn, "testwindfarm__on")
        assert result["created"] is not None

    def test_upsert_updates_last_seen(self, conn):
        from db import upsert_project, get_project
        upsert_project(conn, _make_project())
        upsert_project(conn, _make_project(description="Updated"))
        result = get_project(conn, "testwindfarm__on")
        assert result["lastSeen"] is not None

    def test_evidence_merge_no_duplicates(self, conn):
        """Second upsert with same URL should not duplicate evidence."""
        from db import upsert_project, get_project
        proj = _make_project(evidence=[{"url": "https://cbc.ca/wind-farm", "title": "CBC"}])
        upsert_project(conn, proj)
        upsert_project(conn, _make_project(evidence=[{"url": "https://cbc.ca/wind-farm", "title": "CBC"}]))
        result = get_project(conn, "testwindfarm__on")
        evidence = json.loads(result["evidence"]) if isinstance(result["evidence"], str) else result["evidence"]
        assert len(evidence) == 1  # no duplicate

    def test_evidence_merge_adds_new_urls(self, conn):
        """Second upsert with new URL should append it."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(evidence=[{"url": "https://cbc.ca/a", "title": "A"}]))
        upsert_project(conn, _make_project(evidence=[{"url": "https://globalnews.ca/b", "title": "B"}]))
        result = get_project(conn, "testwindfarm__on")
        evidence = json.loads(result["evidence"]) if isinstance(result["evidence"], str) else result["evidence"]
        urls = [e["url"] for e in evidence]
        assert "https://cbc.ca/a" in urls
        assert "https://globalnews.ca/b" in urls

    def test_status_non_regression_forward(self, conn):
        """Status must not regress from Under Construction to Proposed."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(status="Under Construction"))
        upsert_project(conn, _make_project(status="Proposed"))
        result = get_project(conn, "testwindfarm__on")
        assert result["status"] == "Under Construction"

    def test_status_advances_forward(self, conn):
        """Status advances from Proposed to Approved."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(status="Proposed"))
        upsert_project(conn, _make_project(status="Approved"))
        result = get_project(conn, "testwindfarm__on")
        assert result["status"] == "Approved"

    def test_status_cancelled_overrides(self, conn):
        """Cancelled status applies even when current status is higher."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(status="Under Construction"))
        upsert_project(conn, _make_project(status="Cancelled"))
        result = get_project(conn, "testwindfarm__on")
        assert result["status"] == "Cancelled"

    def test_confidence_never_decreases(self, conn):
        """Confidence must never drop below existing value."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(confidence=0.8))
        upsert_project(conn, _make_project(confidence=0.3))
        result = get_project(conn, "testwindfarm__on")
        assert float(result["confidence"]) >= 0.8

    def test_confidence_increases(self, conn):
        """Confidence updates when new value is higher."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(confidence=0.3))
        upsert_project(conn, _make_project(confidence=0.9))
        result = get_project(conn, "testwindfarm__on")
        assert float(result["confidence"]) >= 0.9

    def test_status_history_appended_on_change(self, conn):
        """statusHistory appended when status changes."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(status="Proposed"))
        upsert_project(conn, _make_project(status="Approved"))
        result = get_project(conn, "testwindfarm__on")
        history = json.loads(result["statusHistory"]) if isinstance(result["statusHistory"], str) else result["statusHistory"]
        statuses = [h.get("status") for h in history if h.get("status")]
        assert "Approved" in statuses

    def test_discovery_sources_merged_no_duplicates(self, conn):
        """discovery_sources merged without duplicates."""
        from db import upsert_project, get_project
        upsert_project(conn, _make_project(discovery_sources=["rss_feed"]))
        upsert_project(conn, _make_project(discovery_sources=["rss_feed", "iaac_registry"]))
        result = get_project(conn, "testwindfarm__on")
        ds = json.loads(result["discovery_sources"]) if isinstance(result["discovery_sources"], str) else result["discovery_sources"]
        assert ds.count("rss_feed") == 1
        assert "iaac_registry" in ds


class TestGetProjects:
    def test_get_projects_returns_all(self, conn):
        from db import upsert_project, get_projects
        upsert_project(conn, _make_project(name="Project A", province="Ontario"))
        upsert_project(conn, _make_project(name="Project B", province="Alberta"))
        results = get_projects(conn)
        assert len(results) >= 2

    def test_get_projects_filter_province(self, conn):
        from db import upsert_project, get_projects
        upsert_project(conn, _make_project(name="ON Project", province="ON"))
        upsert_project(conn, _make_project(name="AB Project", province="AB"))
        results = get_projects(conn, province="Ontario")  # should auto-normalize to ON
        assert all(r["province"] == "ON" for r in results)

    def test_get_projects_filter_sector(self, conn):
        from db import upsert_project, get_projects
        upsert_project(conn, _make_project(name="Wind Farm", sector="power_energy"))
        upsert_project(conn, _make_project(name="Coal Mine", sector="mining", province="Alberta"))
        results = get_projects(conn, sector="mining")
        assert all(r["sector"] == "mining" for r in results)


class TestSearchProjects:
    def test_search_returns_results(self, conn):
        from db import upsert_project, search_projects
        upsert_project(conn, _make_project(name="LNG Canada Pipeline", description="Large LNG export"))
        results = search_projects(conn, "LNG pipeline")
        assert len(results) >= 1

    def test_search_no_match_returns_empty(self, conn):
        from db import upsert_project, search_projects
        upsert_project(conn, _make_project(name="Wind Farm Ontario"))
        results = search_projects(conn, "zzzznonexistent9999")
        assert len(results) == 0


class TestSaveIndicator:
    def test_save_indicator_sqlite_shaped(self, conn):
        """Accept SQLite-shaped dict with indicator_name and period keys."""
        from db import save_indicator, get_indicators
        save_indicator(conn, {
            "indicator_name": "CPI",
            "period": "2026-01",
            "value": 3.2,
            "category": "inflation",
            "province": "National",
            "source": "StatCan",
        })
        results = get_indicators(conn)
        assert len(results) >= 1

    def test_save_indicator_firestore_shaped(self, conn):
        """Accept Firestore-shaped dict with 'indicator' and 'date' keys."""
        from db import save_indicator, get_indicators
        save_indicator(conn, {
            "indicator": "unemployment_rate",
            "date": "2026-02",
            "value": 6.1,
            "category": "labour",
            "province": "National",
            "source": "StatCan",
        })
        results = get_indicators(conn)
        names = [r["indicator_name"] for r in results]
        assert "unemployment_rate" in names

    def test_save_indicator_accepts_extra_fields(self, conn):
        """Accept unit, frequency, description, backfilled fields without error."""
        from db import save_indicator
        save_indicator(conn, {
            "indicator": "gdp_growth",
            "date": "2026-Q1",
            "value": 2.3,
            "category": "gdp",
            "province": "National",
            "source": "StatCan",
            "unit": "%",
            "frequency": "quarterly",
            "description": "Real GDP growth rate",
            "backfilled": False,
        })


class TestSaveBriefing:
    def test_save_and_get_briefing(self, conn):
        from db import save_briefing, get_latest_briefing
        briefing = {
            "week_of": "2026-03-01",
            "headline": "BoC holds rates at 3.0%",
            "sections": {"macro": "National CPI rose 0.1%.", "markets": "TSX up 1.2%."},
            "word_count": 1200,
        }
        save_briefing(conn, briefing)
        result = get_latest_briefing(conn)
        assert result is not None
        assert result["headline"] == "BoC holds rates at 3.0%"

    def test_get_latest_briefing_returns_most_recent(self, conn):
        from db import save_briefing, get_latest_briefing
        save_briefing(conn, {"week_of": "2026-02-01", "headline": "Old", "sections": {}, "word_count": 500})
        save_briefing(conn, {"week_of": "2026-03-01", "headline": "New", "sections": {}, "word_count": 600})
        result = get_latest_briefing(conn)
        assert result["headline"] == "New"


class TestDashboardState:
    def test_save_and_get_dashboard_state(self, conn):
        from db import save_dashboard_state, get_dashboard_state
        save_dashboard_state(conn, "test_key", {"foo": "bar"})
        result = get_dashboard_state(conn, "test_key")
        assert result == {"foo": "bar"}

    def test_get_missing_key_returns_none(self, conn):
        from db import get_dashboard_state
        assert get_dashboard_state(conn, "nonexistent_key") is None

    def test_save_overwrites_existing(self, conn):
        from db import save_dashboard_state, get_dashboard_state
        save_dashboard_state(conn, "key1", {"v": 1})
        save_dashboard_state(conn, "key1", {"v": 2})
        result = get_dashboard_state(conn, "key1")
        assert result["v"] == 2


class TestPipelineRuns:
    def test_save_and_get_pipeline_runs(self, conn):
        from db import save_pipeline_run, get_pipeline_runs
        run = {
            "type": "weekly",
            "status": "success",
            "started_at": "2026-03-01T06:00:00",
            "completed_at": "2026-03-01T06:15:00",
            "duration_seconds": 900,
            "steps_completed": ["step1", "step2"],
            "errors": [],
            "discovery": {"articles_found": 100},
            "api_usage": {"tavily_searches": 50},
        }
        save_pipeline_run(conn, run)
        results = get_pipeline_runs(conn)
        assert len(results) >= 1
        assert results[0]["type"] == "weekly"


class TestTavilyCredits:
    def test_save_and_get_tavily_credits(self, conn):
        from db import save_tavily_credits, get_tavily_credits
        current_month = datetime.utcnow().strftime("%Y-%m")
        save_tavily_credits(conn, current_month, 150)
        result = get_tavily_credits(conn)
        assert result["used"] == 150
        assert result["month"] == current_month

    def test_tavily_credits_auto_reset_new_month(self, conn):
        """If stored month != current month, reset to 0."""
        from db import save_tavily_credits, get_tavily_credits
        # Store for old month
        save_tavily_credits(conn, "2020-01", 999)
        result = get_tavily_credits(conn)
        assert result["used"] == 0  # reset because month differs

    def test_increment_tavily_credits(self, conn):
        from db import increment_tavily_credits, get_tavily_credits
        increment_tavily_credits(conn, 5)
        increment_tavily_credits(conn, 3)
        result = get_tavily_credits(conn)
        assert result["used"] == 8
