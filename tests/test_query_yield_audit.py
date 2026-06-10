"""quality-pass-1.4 R8 — per-query yield audit tests.

record_week keeps a rolling 8-week history in dashboard_state (no new table)
and flags queries with 4+ consecutive zero-yield weeks into the existing
pipeline_improvements table. Flag/deprioritize ONLY — nothing is ever removed
from config (ADDITIVE-ONLY invariant).
"""
import pytest

from db import init_db, get_dashboard_state
from query_yield_audit import (
    record_week, update_tier_history, QUERY_HISTORY_KEY,
    MAX_WEEKS, ZERO_YIELD_WEEKS,
)


@pytest.fixture()
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


QUERY = "mining mine mineral project Saskatchewan 2026"


def _improvement_rows(conn):
    return conn.execute(
        "SELECT detail FROM pipeline_improvements WHERE type = 'query_zero_yield'"
    ).fetchall()


def test_four_zero_weeks_flagged(conn):
    """A query that yielded once, then went 4 consecutive zero weeks → flagged."""
    record_week(conn, {QUERY: 5}, week_of="2026-04-27")
    flagged = []
    for week in ("2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"):
        flagged = record_week(conn, {}, week_of=week)
    assert QUERY in flagged
    details = [r[0] for r in _improvement_rows(conn)]
    assert QUERY in details


def test_three_zero_then_nonzero_not_flagged(conn):
    record_week(conn, {QUERY: 5}, week_of="2026-04-27")
    for week in ("2026-05-04", "2026-05-11", "2026-05-18"):
        record_week(conn, {}, week_of=week)
    flagged = record_week(conn, {QUERY: 2}, week_of="2026-05-25")
    assert QUERY not in flagged
    assert _improvement_rows(conn) == []


def test_never_issued_query_not_flagged(conn):
    """Only queries that appeared in the history at least once count."""
    for week in ("2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25",
                 "2026-06-01"):
        flagged = record_week(conn, {}, week_of=week)
    assert flagged == []
    assert _improvement_rows(conn) == []


def test_history_capped_at_eight_weeks(conn):
    for i in range(1, 13):
        record_week(conn, {QUERY: i}, week_of=f"2026-03-{i:02d}")
    history = get_dashboard_state(conn, QUERY_HISTORY_KEY)
    assert len(history) == MAX_WEEKS
    # Most recent weeks kept
    assert history[-1]["week_of"] == "2026-03-12"
    assert history[0]["week_of"] == "2026-03-05"


def test_same_week_rerun_replaces_entry(conn):
    record_week(conn, {QUERY: 1}, week_of="2026-06-08")
    record_week(conn, {QUERY: 9}, week_of="2026-06-08")
    history = get_dashboard_state(conn, QUERY_HISTORY_KEY)
    assert len(history) == 1
    assert history[0]["counts"][QUERY] == 9


def test_flag_not_duplicated_across_weeks(conn):
    record_week(conn, {QUERY: 5}, week_of="2026-04-27")
    for week in ("2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25",
                 "2026-06-01"):
        record_week(conn, {}, week_of=week)
    # Flagged in two consecutive runs but only one improvement row written
    assert len(_improvement_rows(conn)) == 1


def test_zero_yield_weeks_constant_is_four():
    assert ZERO_YIELD_WEEKS == 4
