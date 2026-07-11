"""Tests for data_warehouse.py — connection registry, run recording, health."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import data_warehouse as dw
from data_warehouse import (
    CONNECTIONS, CONNECTION_IDS, check_health, ensure_schema, record_run,
    track, write_status_json,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    ensure_schema(c)
    yield c
    c.close()


# ── Registry integrity ────────────────────────────────────────────────────

def test_registry_ids_unique():
    ids = [c["id"] for c in CONNECTIONS]
    assert len(ids) == len(set(ids))


def test_registry_covers_audit_inventory():
    # The 2026-07-10 audit inventoried 30 connections.
    assert len(CONNECTIONS) >= 30


def test_registry_modules_exist():
    for c in CONNECTIONS:
        path = os.path.join(ROOT, c["module"])
        assert os.path.exists(path), f"{c['id']}: module {c['module']} missing"


def test_registry_required_fields():
    for c in CONNECTIONS:
        for field in ("id", "name", "module", "category", "cadence", "series", "notes"):
            assert field in c, f"{c.get('id')}: missing {field}"
        assert c["cadence"] in dw.CADENCE_DARK_DAYS, f"{c['id']}: unknown cadence"
        for s in c["series"]:
            assert s["table"] in ("indicator_history", "timeseries")
            assert s["frequency"] in dw.SERIES_OVERDUE_DAYS


def test_registry_key_ids_present():
    for cid in ("statcan_wds_vectors", "statcan_wds_meta", "policy_tracker",
                "job_monitor", "procurement_monitor", "iaac_registry",
                "iaac_status_tracker", "yf_commodities", "boc_valet"):
        assert cid in CONNECTION_IDS


# ── record_run ────────────────────────────────────────────────────────────

def test_record_run_inserts_row(conn):
    record_run("policy_tracker", "ok", items_fetched=40, items_saved=12, conn=conn)
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["connection_id"] == "policy_tracker"
    assert row["status"] == "ok"
    assert row["items_fetched"] == 40
    assert row["items_saved"] == 12
    assert row["error"] == ""


def test_record_run_failed_with_error(conn):
    record_run("job_monitor", "failed", error="0 postings", conn=conn)
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["status"] == "failed"
    assert row["error"] == "0 postings"


def test_record_run_unknown_status_downgraded(conn):
    record_run("job_monitor", "bogus", conn=conn)
    row = conn.execute("SELECT status FROM connection_runs").fetchone()
    assert row["status"] == "degraded"


def test_record_run_unregistered_id_still_recorded(conn, capsys):
    record_run("not_a_real_connection", "ok", conn=conn)
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["connection_id"] == "not_a_real_connection"
    assert "unregistered" in capsys.readouterr().out


def test_record_run_never_raises():
    # A broken conn object must not propagate.
    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("boom")
        def executescript(self, *a, **k):
            raise RuntimeError("boom")
    record_run("policy_tracker", "ok", conn=Broken())  # must not raise


def test_record_run_truncates_error(conn):
    record_run("policy_tracker", "failed", error="x" * 2000, conn=conn)
    row = conn.execute("SELECT error FROM connection_runs").fetchone()
    assert len(row["error"]) == 500


# ── track() ───────────────────────────────────────────────────────────────

def test_track_records_ok(conn):
    with track("iaac_registry", conn=conn) as t:
        t.items_fetched = 7
        t.items_saved = 7
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["status"] == "ok"
    assert row["items_fetched"] == 7


def test_track_records_failure_and_reraises(conn):
    with pytest.raises(ValueError):
        with track("iaac_registry", conn=conn):
            raise ValueError("network down")
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["status"] == "failed"
    assert "network down" in row["error"]


def test_track_as_decorator(conn):
    @track("sedar_filings", conn=conn)
    def fetch():
        return [1, 2, 3]
    assert fetch() == [1, 2, 3]
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["connection_id"] == "sedar_filings"
    assert row["status"] == "ok"


def test_track_status_override(conn):
    with track("rss_feeds", conn=conn) as t:
        t.status = "degraded"
        t.error = "3 feeds dark"
    row = conn.execute("SELECT * FROM connection_runs").fetchone()
    assert row["status"] == "degraded"
    assert row["error"] == "3 feeds dark"


# ── check_health ──────────────────────────────────────────────────────────

def _iso(dt):
    return dt.isoformat(timespec="seconds")


def test_health_unknown_when_never_recorded(conn):
    health = check_health(conn=conn)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["tavily_enrichment"]["health"] == "unknown"
    assert health["summary"]["unknown"] > 0


def test_health_ok_for_recent_success(conn):
    now = datetime.now(timezone.utc)
    record_run("policy_tracker", "ok", items_fetched=10, conn=conn,
               started_at=_iso(now - timedelta(days=1)))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["policy_tracker"]["health"] == "ok"
    assert by_id["policy_tracker"]["days_since_success"] == 1


def test_health_warn_when_dark_past_cadence(conn):
    now = datetime.now(timezone.utc)
    # weekly cadence: warn at >9 days, critical at >16 days
    record_run("policy_tracker", "ok", conn=conn,
               started_at=_iso(now - timedelta(days=12)))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["policy_tracker"]["health"] == "warn"


def test_health_critical_when_dark_past_2x_cadence(conn):
    now = datetime.now(timezone.utc)
    record_run("policy_tracker", "ok", conn=conn,
               started_at=_iso(now - timedelta(days=20)))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["policy_tracker"]["health"] == "critical"


def test_health_critical_on_consecutive_failures(conn):
    now = datetime.now(timezone.utc)
    record_run("job_monitor", "ok", conn=conn,
               started_at=_iso(now - timedelta(days=3)))
    record_run("job_monitor", "failed", error="e1", conn=conn,
               started_at=_iso(now - timedelta(days=2)))
    record_run("job_monitor", "failed", error="e2", conn=conn,
               started_at=_iso(now - timedelta(days=1)))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["job_monitor"]["consecutive_failures"] == 2
    assert by_id["job_monitor"]["health"] == "critical"


def test_health_single_failure_is_warn(conn):
    now = datetime.now(timezone.utc)
    record_run("job_monitor", "ok", conn=conn,
               started_at=_iso(now - timedelta(days=2)))
    record_run("job_monitor", "failed", error="e1", conn=conn,
               started_at=_iso(now - timedelta(days=1)))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    assert by_id["job_monitor"]["consecutive_failures"] == 1
    assert by_id["job_monitor"]["health"] == "warn"


def test_series_accrual_overdue_detection(conn):
    """A monthly series whose latest reference period is 4 months old must be
    flagged overdue; a fresh one must not."""
    now = datetime.now(timezone.utc)
    conn.execute(
        "CREATE TABLE indicator_history (indicator_name TEXT, province TEXT, "
        "value REAL, period TEXT)")
    stale = (now - timedelta(days=120)).strftime("%Y-%m-01")
    fresh = (now - timedelta(days=20)).strftime("%Y-%m-01")
    conn.execute("INSERT INTO indicator_history VALUES ('housing_starts_total', 'national', 20000, ?)", (stale,))
    conn.execute("INSERT INTO indicator_history VALUES ('new_housing_price_index', 'national', 125.0, ?)", (fresh,))
    record_run("statcan_wds_vectors", "ok", conn=conn, started_at=_iso(now))

    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    overdue_names = [s["name"] for s in by_id["statcan_wds_vectors"]["overdue_series"]]
    assert "housing_starts_total" in overdue_names
    assert "new_housing_price_index" not in overdue_names
    # connection reported ok but has an overdue series → at least warn
    assert by_id["statcan_wds_vectors"]["health"] == "warn"
    # persisted to series_accrual
    row = conn.execute(
        "SELECT overdue, latest_period FROM series_accrual "
        "WHERE series_key = 'indicator_history:housing_starts_total'").fetchone()
    assert row["overdue"] == 1
    assert row["latest_period"] == stale


def test_series_accrual_timeseries_table(conn):
    now = datetime.now(timezone.utc)
    conn.execute(
        "CREATE TABLE timeseries (series_name TEXT, date TEXT, value REAL)")
    stale = (now - timedelta(days=200)).strftime("%Y-%m-%d")
    conn.execute("INSERT INTO timeseries VALUES ('canola', ?, 700.0)", (stale,))
    health = check_health(conn=conn, now=now)
    by_id = {c["id"]: c for c in health["connections"]}
    overdue = [s["name"] for s in by_id["statcan_canola"]["overdue_series"]]
    assert "canola" in overdue


def test_check_health_survives_missing_data_tables(conn):
    # No indicator_history/timeseries tables at all — must not raise.
    health = check_health(conn=conn)
    assert "connections" in health
    assert len(health["connections"]) == len(CONNECTIONS)


def test_write_status_json(tmp_path, conn):
    (tmp_path / "docs" / "data").mkdir(parents=True)
    (tmp_path / "public" / "data").mkdir(parents=True)
    health = check_health(conn=conn)
    paths = write_status_json(health=health, root=str(tmp_path))
    assert len(paths) == 2
    import json
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        assert data["summary"]
        assert len(data["connections"]) == len(CONNECTIONS)


def test_health_json_serializable(conn):
    import json
    now = datetime.now(timezone.utc)
    record_run("boc_valet", "ok", conn=conn, started_at=_iso(now))
    json.dumps(check_health(conn=conn, now=now), default=str)
