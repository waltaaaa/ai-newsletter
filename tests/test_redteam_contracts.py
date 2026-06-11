"""Contract tests for the 2026-06-11 red-team findings (T-5.2 + follow-ups).

Each test pins a behavior the red team found broken or unguarded:
- BC tender rows bypass the $5M floor but must carry a NUMERIC value (never None)
- _extract_value_from_text must parse suffixes on the lowercased text callers pass
- jobs.json / procurement.json exported shapes must match what app.js reads
- Job Bank postings dedup by URL across a sector's term feeds (A#12)
- Week-1 hiring spikes must not fabricate an "Nx normal volume" multiplier
- get_timeseries(include_briefing_prints=False) excludes writer-emitted points (V-F8)
- The microscope generation prompt stays under the ~4KB claude -p host limit (O-F3)
- The Phase 3 cooperative deadline stops new claude calls once the budget is spent (O-F5)
"""
import asyncio
import json
import os
import sqlite3
import time
import types

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── BC no-floor + numeric value (red-team #1/#9) ───────────────────────────

def test_bc_rows_kept_without_value_and_value_is_numeric(monkeypatch):
    import procurement_monitor as pm

    rows = [
        {   # BC row, construction keyword, NO dollar value — must be kept, value 0
            "regionsOfDelivery-regionsLivraison-eng": "British Columbia",
            "title-titre-eng": "Highway 1 construction services",
            "tenderDescription-descriptionAppelOffres-eng": "Roadworks near Kamloops",
            "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/n/1",
            "publicationDate-datePublication": "2026-06-08",
        },
        {   # BC row with a stated value — extracted into both fields
            "regionsOfDelivery-regionsLivraison-eng": "British Columbia",
            "title-titre-eng": "Bridge construction project",
            "tenderDescription-descriptionAppelOffres-eng": "Estimated $12 million scope",
            "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/n/2",
            "publicationDate-datePublication": "2026-06-08",
        },
        {   # Non-BC row — excluded
            "regionsOfDelivery-regionsLivraison-eng": "Ontario",
            "title-titre-eng": "School construction",
            "tenderDescription-descriptionAppelOffres-eng": "",
            "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/n/3",
            "publicationDate-datePublication": "2026-06-08",
        },
    ]
    monkeypatch.setattr(pm, "_fetch_canadabuys_rows", lambda url: rows)

    opportunities = pm.fetch_bc_bid()

    assert len(opportunities) == 2, "BC keyword rows must be kept with NO value floor"
    no_value = next(o for o in opportunities if o["url"].endswith("/1"))
    assert no_value["value"] == 0, "missing value must coerce to numeric 0, never None"
    assert isinstance(no_value["value"], (int, float))
    assert no_value["value_extracted"] is None
    valued = next(o for o in opportunities if o["url"].endswith("/2"))
    assert valued["value"] == 12_000_000


# ── value suffix parsing on lowercased text (red-team #13) ──────────────────

@pytest.mark.parametrize("text,expected", [
    ("contract worth $5m for roadworks", 5_000_000),
    ("estimated at $2.1 billion over ten years", 2_100_000_000),
    ("budget of $750,000 approved", 750_000.0),
    ("valued at $3.5 b", 3_500_000_000),
    ("no dollars here", None),
])
def test_extract_value_suffixes_case_insensitive(text, expected):
    from procurement_monitor import _extract_value_from_text
    assert _extract_value_from_text(text) == expected


# ── exported file shapes match the frontend reads (red-team 4.2/4.3) ────────

@pytest.fixture
def snapshot_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE job_snapshots (week_of TEXT, data TEXT, spikes TEXT)")
    conn.execute("CREATE TABLE procurement_snapshots (week_of TEXT, data TEXT)")
    conn.execute(
        "INSERT INTO job_snapshots VALUES (?, ?, ?)",
        ("2026-06-08", json.dumps({'["A","Toronto","mining"]': 6}),
         json.dumps([{"employer": "A", "signal": "x"}])))
    conn.execute(
        "INSERT INTO procurement_snapshots VALUES (?, ?)",
        ("2026-06-08", json.dumps([{"title": "T", "value": 6_000_000}])))
    conn.commit()
    yield conn
    conn.close()


def test_jobs_export_shape_matches_app_js(snapshot_conn, tmp_path):
    from tools.export_dashboard import export_jobs
    out = export_jobs(snapshot_conn, str(tmp_path))
    data = json.loads(open(out, encoding="utf-8").read())
    # Exported contract: LIST of snapshots, newest first, each with spikes[]
    assert isinstance(data, list) and data, "jobs.json must be a snapshot list"
    assert "week_of" in data[0] and "spikes" in data[0]
    assert isinstance(data[0]["spikes"], list)
    # Frontend contract: app.js reads jobData[0].spikes (both copies)
    for rel in ("docs/js/app.js", "public/js/app.js"):
        src = open(os.path.join(BACKEND, rel), encoding="utf-8").read()
        assert "(jobData[0]||{}).spikes" in src, (
            f"{rel} no longer reads jobData[0].spikes — exported jobs.json "
            f"shape and the frontend read have drifted apart")


def test_procurement_export_shape_matches_app_js(snapshot_conn, tmp_path):
    from tools.export_dashboard import export_procurement
    out = export_procurement(snapshot_conn, str(tmp_path))
    data = json.loads(open(out, encoding="utf-8").read())
    assert isinstance(data, list) and data, "procurement.json must be a snapshot list"
    assert "week_of" in data[0] and "contracts" in data[0]
    assert isinstance(data[0]["contracts"], list)
    for rel in ("docs/js/app.js", "public/js/app.js"):
        src = open(os.path.join(BACKEND, rel), encoding="utf-8").read()
        assert "(procData[0]||{}).contracts" in src, (
            f"{rel} no longer reads procData[0].contracts — exported "
            f"procurement.json shape and the frontend read have drifted apart")


# ── Job Bank dedup across term feeds (red-team A#12) ────────────────────────

def _fake_feed(entries):
    return types.SimpleNamespace(entries=entries, bozo=0)


def test_job_postings_dedup_across_term_feeds(monkeypatch):
    import job_monitor

    entry = {
        "title": "Carpenter",
        "link": "https://www.jobbank.gc.ca/jobposting/123",
        "summary": ("<strong>Employer:</strong> BuildCo Manitoba Inc<br/>"
                    "<strong>Location:</strong> Winnipeg (MB)<br/>"),
    }
    # Every term feed returns the SAME posting — it must count once.
    monkeypatch.setattr(job_monitor, "_fetch_feed", lambda url: _fake_feed([dict(entry)]))

    postings = job_monitor.fetch_job_postings("infrastructure", "Winnipeg")
    assert len(postings) == 1, (
        "the same posting URL appearing in multiple term feeds must be "
        "counted once toward the spike trigger")


def test_week1_spike_signal_has_no_fabricated_multiplier():
    from job_monitor import detect_hiring_spikes

    spikes = detect_hiring_spikes({("BuildCo", "Winnipeg", "mining"): 6}, [])
    assert len(spikes) == 1
    s = spikes[0]
    assert s["multiplier"] is None
    assert "first tracked week" in s["signal"]
    assert "active postings" in s["signal"]
    assert "posted" not in s["signal"], (
        "Job Bank counts measure feed-window presence, not weekly volume — "
        "'posted N jobs' overstates")
    assert "x normal" not in s["signal"]


# ── briefing_print exclusion (red-team V-F8) ────────────────────────────────

def test_get_timeseries_excludes_briefing_prints():
    import db as dbmod

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE timeseries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name TEXT NOT NULL, date TEXT NOT NULL, value REAL,
        unit TEXT DEFAULT '', source TEXT DEFAULT '',
        UNIQUE(series_name, date))""")
    conn.execute("INSERT INTO timeseries (series_name, date, value, source) "
                 "VALUES ('wti', '2026-06-05', 67.5, 'yfinance')")
    conn.execute("INSERT INTO timeseries (series_name, date, value, source) "
                 "VALUES ('wti', '2026-06-08', 98.5, 'briefing_print')")
    conn.commit()

    all_rows = dbmod.get_timeseries(conn, "wti")
    assert len(all_rows) == 2
    clean = dbmod.get_timeseries(conn, "wti", include_briefing_prints=False)
    assert len(clean) == 1
    assert clean[0]["source"] == "yfinance", (
        "writer-emitted points must never become the fact-check baseline")
    conn.close()


# ── microscope prompt stays under the claude -p host limit (red-team O-F3) ──

def test_microscope_prompt_under_4kb_host_limit(monkeypatch):
    import claude_reasoning
    import under_the_microscope as utm

    captured = {}

    async def _capture(system, user_prompt, **kwargs):
        captured["prompt"] = user_prompt
        return {"text": "analysis", "input_tokens": 0, "output_tokens": 0,
                "cost_usd": 0.0}

    monkeypatch.setattr(claude_reasoning, "reason_with_claude_tracked", _capture)

    topic_context = {
        "topic": "Test topic " * 10,
        "description": "D" * 2000,  # capped to 500 in the prompt
        "related_articles": [{"title": "T" * 300} for _ in range(20)],
        "affected_sectors": ["mining", "infrastructure"],
        "affected_provinces": ["MB", "ON"],
        "weeks_running": 2,
    }
    project_data = [{
        "name": f"Project {i} " + "N" * 80,
        "province": "MB", "value": "$1.2B", "status": "Proposed",
        "sector": "mining", "description": "X" * 400,  # dropped by slimming
        "evidence": [{"url": "https://example.com"}] * 5,
    } for i in range(15)]
    indicator_data = {f"indicator_{i}": {"value": i, "change": "+1.0%",
                                         "note": "Y" * 50} for i in range(30)}

    result = asyncio.run(utm.generate_microscope_analysis(
        topic_context, project_data, indicator_data))

    assert result is not None
    assert "prompt" in captured
    assert len(captured["prompt"]) <= 2400, (
        f"microscope prompt is {len(captured['prompt'])} chars — over the "
        f"budget that keeps system+user under the ~4KB claude -p host limit")


# ── Phase 3 cooperative deadline (red-team O-F5) ────────────────────────────

def test_extraction_stops_starting_chunks_past_deadline(monkeypatch):
    from phases import filtering

    def _must_not_run(*args, **kwargs):
        raise AssertionError("claude extraction started past the phase deadline")

    monkeypatch.setattr(filtering, "_parse_projects_with_sonnet", _must_not_run)
    monkeypatch.setattr(filtering, "_flush_backlog", lambda remaining: None)
    # Deadline already passed
    monkeypatch.setattr(filtering, "_PHASE_DEADLINE", time.monotonic() - 1)

    items = [{
        "title": "New $900M smelter announced",
        "summary": "A new smelter project",
        "url": "https://example.com/a1",
        "province": "Manitoba",
        "_l6_passed": True,
    }]
    projects, failed = filtering.extract_projects_from_rss(items)

    assert projects == []
    assert failed == []
