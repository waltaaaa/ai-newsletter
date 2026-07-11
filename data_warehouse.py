"""data_warehouse.py — central connection registry + retrieval monitoring.

One place that knows about every external data connection the pipeline
depends on, and one place that records whether each connection actually
retrieved data on each run.

Motivated by the 2026-07-10 data-retrieval audit (RC-6): retrieval failure
was invisible — every module printed failures to stdout and exited 0, and no
table recorded "connection X: last attempted, last succeeded, rows saved,
last error" across the ~30 connections.

Components
----------
1. CONNECTIONS — static registry of all retrieval connections (id, name,
   module, category, cadence, expected series, notes). ADDITIVE ONLY: new
   connections are appended, existing ids are never removed or renamed.
2. connection_runs (SQLite) — one row per connection per attempt:
   started/finished, status (ok|degraded|failed|skipped), items fetched/saved,
   error summary.
3. series_accrual (SQLite) — latest reference period per registered series vs
   its expected cadence, refreshed by check_health(); detects "series stopped
   accruing" even when the connection itself reports ok.
4. record_run() / track() — the cheap instrumentation API existing modules
   call at their summary points. Both are guaranteed never to raise into the
   caller (track() re-raises the CALLER's exception, but its own bookkeeping
   failures are swallowed with a printed [WAREHOUSE] line).
5. check_health() — per-connection health (last-success age vs cadence,
   consecutive failures, overdue series) + JSON export for the frontend.

Usage (instrumenting a connection):

    from data_warehouse import record_run
    ...
    record_run("policy_tracker", "ok", items_fetched=42, items_saved=12,
               conn=conn)

    from data_warehouse import track
    with track("iaac_registry", conn=conn) as t:
        rows = do_fetch()
        t.items_fetched = len(rows)

See DATA_WAREHOUSE.md for the full design notes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.abspath(__file__))

VALID_STATUSES = ("ok", "degraded", "failed", "skipped")

# ─────────────────────────────────────────────────────────────────────────────
# Connection registry — seeded from the 2026-07-10 data-retrieval audit
# (30-connection inventory). ADDITIVE ONLY.
#
# Fields:
#   id        — stable identifier used by record_run()/track()
#   name      — human-readable label
#   module    — repo-relative path to the entry module (documentation aid;
#               tests assert the file exists)
#   category  — statcan | markets | macro_global | discovery | signals |
#               policy | agent | enrichment
#   cadence   — daily | weekly | monthly | manual | ad-hoc (how often a
#               successful run is expected)
#   series    — list of {"name", "table" ("indicator_history"|"timeseries"),
#               "frequency"} the connection is expected to keep accruing.
#               Only series whose names were verified in code are listed.
#   notes     — endpoint / failure-mode notes from the audit
# ─────────────────────────────────────────────────────────────────────────────

CONNECTIONS = [
    # ── StatCan ──────────────────────────────────────────────────────────
    {
        "id": "statcan_wds_vectors",
        "name": "StatCan WDS — hardcoded vector groups",
        "module": "statcan_extended.py",
        "category": "statcan",
        "cadence": "weekly",
        "series": [
            {"name": "housing_starts_total", "table": "indicator_history", "frequency": "monthly"},
            {"name": "new_housing_price_index", "table": "indicator_history", "frequency": "monthly"},
            {"name": "residential_building_investment", "table": "indicator_history", "frequency": "monthly"},
            {"name": "energy_exports", "table": "indicator_history", "frequency": "monthly"},
            {"name": "construction_vacancies", "table": "indicator_history", "frequency": "quarterly"},
            {"name": "total_capex", "table": "indicator_history", "frequency": "annual"},
        ],
        "notes": "Tables 34-10-0293/0175, 34-10-0035, 14-10-0326, 12-10-0163, "
                 "34-10-0143, 18-10-0205 via _fetch_table_group. Audit #1.",
    },
    {
        "id": "statcan_wds_meta",
        "name": "StatCan WDS — META_RESOLVED coordinate groups",
        "module": "statcan_extended.py",
        "category": "statcan",
        "cadence": "weekly",
        "series": [
            {"name": "healthcare_employment", "table": "indicator_history", "frequency": "monthly"},
            {"name": "retail_sales_national", "table": "indicator_history", "frequency": "monthly"},
            {"name": "manufacturing_sales_national", "table": "indicator_history", "frequency": "monthly"},
            {"name": "job_vacancies_total", "table": "indicator_history", "frequency": "monthly"},
            {"name": "nat_avg_hourly_wage", "table": "indicator_history", "frequency": "monthly"},
            {"name": "household_disposable_income_national", "table": "indicator_history", "frequency": "quarterly"},
        ],
        "notes": "Tables 14-10-0022/0063/0372, 16-10-0047, 20-10-0008/0074, "
                 "34-10-0292, 36-10-0112 + QC series via _fetch_meta_group. Audit #2.",
    },
    {
        "id": "statcan_lfs_primary",
        "name": "StatCan WDS — national+provincial LFS/CPI primary",
        "module": "phases/data_collection.py",
        "category": "statcan",
        "cadence": "weekly",
        "series": [
            {"name": "unemployment", "table": "indicator_history", "frequency": "monthly"},
            {"name": "cpi", "table": "indicator_history", "frequency": "monthly"},
        ],
        "notes": "14-10-0287 etc. Audit #3.",
    },
    {
        "id": "statcan_industry_gdp",
        "name": "StatCan WDS — industry GDP (36-10-0434)",
        "module": "phases/data_collection.py",
        "category": "statcan",
        "cadence": "weekly",
        "series": [],
        "notes": "fetch_industry_indicators. Audit #4.",
    },
    {
        "id": "statcan_permits",
        "name": "StatCan — building permits anomaly signal",
        "module": "statcan_permits.py",
        "category": "signals",
        "cadence": "weekly",
        "series": [],
        "notes": "Audit #5.",
    },
    {
        "id": "statcan_canola",
        "name": "StatCan farm prices — canola vector 31212214",
        "module": "canadian_markets.py",
        "category": "statcan",
        "cadence": "weekly",
        "series": [
            {"name": "canola", "table": "timeseries", "frequency": "monthly"},
        ],
        "notes": "32-10-0077 via _fetch_statcan_monthly; writes all 14 points "
                 "(the reference pattern). Audit #6.",
    },
    # ── Markets ──────────────────────────────────────────────────────────
    {
        "id": "boc_valet",
        "name": "Bank of Canada Valet — policy rate, yields, prime",
        "module": "phases/data_collection.py",
        "category": "markets",
        "cadence": "weekly",
        "series": [],
        "notes": "get_boc_rate/_boc_series + tools/refresh_timeseries_commodity.py. Audit #7.",
    },
    {
        "id": "yf_commodities",
        "name": "yfinance — commodities batch (~35 tickers)",
        "module": "phases/data_collection.py",
        "category": "markets",
        "cadence": "weekly",
        "series": [],
        "notes": "get_commodities; partial result cached 12h. Audit #8.",
    },
    {
        "id": "yf_markets",
        "name": "yfinance — indices + FX",
        "module": "phases/data_collection.py",
        "category": "markets",
        "cadence": "weekly",
        "series": [],
        "notes": "get_financial_markets. Audit #9.",
    },
    {
        "id": "yf_canadian_proxies",
        "name": "yfinance — Canadian commodity proxies",
        "module": "canadian_markets.py",
        "category": "markets",
        "cadence": "weekly",
        "series": [
            {"name": "comm_uranium", "table": "timeseries", "frequency": "weekly"},
            {"name": "comm_lumber", "table": "timeseries", "frequency": "weekly"},
        ],
        "notes": "U-UN.TO, FM.TO, SLX, LBR=F, NTR.TO, CCO.TO, basket. Audit #10.",
    },
    {
        "id": "yf_daily_refresh",
        "name": "yfinance — daily CI timeseries refresh (~40 keys)",
        "module": "tools/refresh_timeseries_commodity.py",
        "category": "markets",
        "cadence": "daily",
        "series": [
            {"name": "gold", "table": "timeseries", "frequency": "daily"},
            {"name": "sp500", "table": "timeseries", "frequency": "daily"},
        ],
        "notes": "data-refresh.yml 07:00 UTC; exits 0 even on total failure "
                 "(RC-6); dark since 2026-06-29 at audit time. Audit #11.",
    },
    {
        "id": "fred_csv",
        "name": "FRED CSV — base metals, spreads, curve",
        "module": "tools/refresh_timeseries_commodity.py",
        "category": "macro_global",
        "cadence": "daily",
        "series": [],
        "notes": "_fetch_fred + data_collection _fred_*; fail-soft. Audit #12.",
    },
    {
        "id": "global_indicators",
        "name": "ECB SDW + BoE IADB + World Bank — global indicators",
        "module": "phases/data_collection.py",
        "category": "macro_global",
        "cadence": "weekly",
        "series": [],
        "notes": "get_global_indicators; 24h cache can serve holey payload (RC-10). Audit #13.",
    },
    {
        "id": "tldr_data_refresh_agent",
        "name": "tldr-data-refresh WebSearch agent (Cowork fallback)",
        "module": ".claude/skills/tldr-data-refresh/SKILL.md",
        "category": "agent",
        "cadence": "ad-hoc",
        "series": [],
        "notes": "Historical source of run-date-stamped pollution (RC-3). Audit #14.",
    },
    # ── Discovery ────────────────────────────────────────────────────────
    {
        "id": "google_news_rss",
        "name": "Google News RSS compound queries (2,574+)",
        "module": "google_news_rss_search.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Per-query yield history exists (flag-only). Audit #15.",
    },
    {
        "id": "rss_feeds",
        "name": "RSS feeds (324+, 6-layer filter)",
        "module": "rss_monitor.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Best-covered today: rss_feed_health table. Audit #16.",
    },
    {
        "id": "gov_registries",
        "name": "Government registries tier-1 (13 provincial EA + CER + federal)",
        "module": "gov_sources.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "35 broad except blocks; per-registry failure = stdout only. Audit #17.",
    },
    {
        "id": "iaac_registry",
        "name": "IAAC registry scrape",
        "module": "gov_sources.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "_scrape_iaac (shared by tier-1 discovery and iaac_status). Audit #17/#18.",
    },
    {
        "id": "iaac_status_tracker",
        "name": "IAAC status tracker",
        "module": "iaac_status.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Status transitions on federal assessments. Audit #18.",
    },
    {
        "id": "sedar_filings",
        "name": "SEDAR+ securities filings",
        "module": "gov_sources.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "_scrape_sedar; print-and-continue. Audit #19.",
    },
    {
        "id": "institutional_capital",
        "name": "Crown corp + university/institutional capital plans",
        "module": "institutional_capital.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Audit #20.",
    },
    {
        "id": "municipal_dev_apps",
        "name": "Municipal development applications (15 CMAs)",
        "module": "municipal_dev_apps.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Audit #21.",
    },
    {
        "id": "lobbyist_registries",
        "name": "Lobbyist registries",
        "module": "lobbyist_registries.py",
        "category": "signals",
        "cadence": "weekly",
        "series": [],
        "notes": "Audit #22.",
    },
    # ── Policy / signals ─────────────────────────────────────────────────
    {
        "id": "policy_tracker",
        "name": "Policy tracker (~17 LEGISinfo/Gazette/ministry feeds)",
        "module": "policy_tracker.py",
        "category": "policy",
        "cadence": "weekly",
        "series": [],
        "notes": "Empty policy_snapshots row on failure; briefing section thin. Audit #23.",
    },
    {
        "id": "job_monitor",
        "name": "Job monitor (Job Bank Atom, 15 CMAs x 9 sectors)",
        "module": "job_monitor.py",
        "category": "signals",
        "cadence": "weekly",
        "series": [],
        "notes": "No snapshot = silent today. Audit #24.",
    },
    {
        "id": "procurement_monitor",
        "name": "Procurement monitor (Open Canada, CanadaBuys, SEAO, DCC)",
        "module": "procurement_monitor.py",
        "category": "signals",
        "cadence": "weekly",
        "series": [],
        "notes": "16 excepts; dead sources skipped with stdout reasons. Audit #25.",
    },
    {
        "id": "regulatory_canlii",
        "name": "Regulatory CanLII feeds (10)",
        "module": "article_filter.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Via rss_feeds.json regulatory category; covered by RSS health. Audit #26.",
    },
    {
        "id": "corporate_newswires",
        "name": "Corporate newswires + Google Alerts + key-people + trade RSS",
        "module": "rss_monitor.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Via RSS health. Audit #27.",
    },
    {
        "id": "corporate_newsroom_diff",
        "name": "Corporate newsroom sitemap diffs",
        "module": "corporate_newsroom_diff.py",
        "category": "discovery",
        "cadence": "weekly",
        "series": [],
        "notes": "Audit #28.",
    },
    {
        "id": "tavily_enrichment",
        "name": "Tavily enrichment searches",
        "module": "tavily_search.py",
        "category": "enrichment",
        "cadence": "weekly",
        "series": [],
        "notes": "Budget-capped (1,000 credits/month). Audit #29.",
    },
    {
        "id": "on_oea_qc_isq",
        "name": "ON OEA / QC ISQ out-of-band scrapes",
        "module": "tools/refresh_provincial_oea_isq.py",
        "category": "statcan",
        "cadence": "manual",
        "series": [
            {"name": "QC_qc_exports", "table": "timeseries", "frequency": "quarterly"},
            {"name": "ON_on_exports", "table": "timeseries", "frequency": "quarterly"},
        ],
        "notes": "ISQ scrape DEAD; series frozen at 2025-10-01 (RC-9). The "
                 "series_accrual check exists precisely to keep this loud. Audit #30.",
    },
]

CONNECTION_IDS = {c["id"] for c in CONNECTIONS}
_BY_ID = {c["id"]: c for c in CONNECTIONS}


def get_connection(connection_id: str) -> dict | None:
    """Return the registry entry for a connection id, or None."""
    return _BY_ID.get(connection_id)


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────────────────────

# Connection dark-age thresholds (days since last success): (warn, critical).
# critical ~= 2x cadence per the audit's recommendation. manual/ad-hoc
# connections are never flagged for darkness (only their series are).
CADENCE_DARK_DAYS = {
    "daily": (2, 4),
    "weekly": (9, 16),
    "monthly": (35, 70),
    "manual": None,
    "ad-hoc": None,
}

# Series accrual thresholds (days since latest reference period) before a
# series is considered overdue. Deliberately generous: publication lag +
# one missed cycle. Frequency-aware per audit recommendation #6 (the flat
# 540d stale threshold catches nothing relevant). "daily" allows for
# weekends/holidays (RC-7: gap detectors must be trading-calendar tolerant).
SERIES_OVERDUE_DAYS = {
    "daily": 9,
    "weekly": 16,
    "monthly": 65,
    "quarterly": 150,
    "annual": 460,
}


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

_WAREHOUSE_SCHEMA = """
CREATE TABLE IF NOT EXISTS connection_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT NOT NULL,
    run_id        TEXT DEFAULT '',
    started_at    TEXT NOT NULL,
    finished_at   TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ok',
    items_fetched INTEGER DEFAULT 0,
    items_saved   INTEGER DEFAULT 0,
    error         TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_connection_runs_conn
    ON connection_runs(connection_id, started_at);

CREATE TABLE IF NOT EXISTS series_accrual (
    series_key    TEXT PRIMARY KEY,
    connection_id TEXT DEFAULT '',
    tbl           TEXT DEFAULT 'indicator_history',
    frequency     TEXT DEFAULT '',
    latest_period TEXT DEFAULT '',
    gap_days      REAL,
    overdue       INTEGER DEFAULT 0,
    last_checked  TEXT DEFAULT ''
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create warehouse tables if absent. Idempotent."""
    conn.executescript(_WAREHOUSE_SCHEMA)
    conn.commit()


def _open_default_conn():
    from db import get_db
    return get_db()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────────
# Recording API
# ─────────────────────────────────────────────────────────────────────────────

def record_run(connection_id: str, status: str, items_fetched: int = 0,
               items_saved: int = 0, error: str = "", conn=None,
               started_at: str | None = None, finished_at: str | None = None,
               run_id: str = "") -> None:
    """Record one connection attempt. NEVER raises into the caller.

    Args:
        connection_id: id from CONNECTIONS (unknown ids are recorded anyway,
            with a printed warning — better a mislabeled row than a lost one).
        status: ok | degraded | failed | skipped.
        items_fetched / items_saved: raw counts (pre/post filter+dedup).
        error: short error summary (truncated to 500 chars).
        conn: existing sqlite3 connection; if None a short-lived one is opened
            against the default DB and closed after the insert.
        started_at / finished_at: ISO timestamps; default = now.
    """
    try:
        if status not in VALID_STATUSES:
            print(f"[WAREHOUSE] record_run: unknown status '{status}' for "
                  f"{connection_id} — recording as 'degraded'")
            status = "degraded"
        if connection_id not in CONNECTION_IDS:
            print(f"[WAREHOUSE] record_run: unregistered connection id "
                  f"'{connection_id}' — recording anyway (add it to "
                  f"data_warehouse.CONNECTIONS)")

        now = _utcnow_iso()
        owns_conn = conn is None or not hasattr(conn, "execute")
        c = _open_default_conn() if owns_conn else conn
        try:
            ensure_schema(c)
            c.execute(
                "INSERT INTO connection_runs (connection_id, run_id, started_at, "
                "finished_at, status, items_fetched, items_saved, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (connection_id, run_id or "", started_at or now,
                 finished_at or now, status,
                 int(items_fetched or 0), int(items_saved or 0),
                 (error or "")[:500]),
            )
            c.commit()
        finally:
            if owns_conn:
                try:
                    c.close()
                except Exception:
                    pass
    except Exception as e:
        # Monitoring must never break retrieval.
        print(f"[WAREHOUSE] record_run failed for {connection_id} "
              f"(non-critical): {type(e).__name__}: {e}")


class track:
    """Context manager / decorator that records a connection run.

    Catches nothing from the wrapped code: an exception is recorded as a
    'failed' run and then propagates unchanged. On normal exit records
    self.status (default 'ok'). Set items_fetched/items_saved/status/error
    on the object inside the block.

        with track("iaac_registry", conn=conn) as t:
            rows = fetch()
            t.items_fetched = len(rows)

        @track("policy_tracker")
        def run_policy_tracker(...):
            ...
    """

    def __init__(self, connection_id: str, conn=None, run_id: str = ""):
        self.connection_id = connection_id
        self.conn = conn
        self.run_id = run_id
        self.items_fetched = 0
        self.items_saved = 0
        self.status = "ok"
        self.error = ""
        self._started_at = None

    def __enter__(self):
        self._started_at = _utcnow_iso()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            record_run(self.connection_id, "failed",
                       items_fetched=self.items_fetched,
                       items_saved=self.items_saved,
                       error=f"{exc_type.__name__}: {exc}",
                       conn=self.conn, started_at=self._started_at,
                       run_id=self.run_id)
        else:
            record_run(self.connection_id, self.status,
                       items_fetched=self.items_fetched,
                       items_saved=self.items_saved,
                       error=self.error,
                       conn=self.conn, started_at=self._started_at,
                       run_id=self.run_id)
        return False  # never suppress exceptions

    def __call__(self, fn):
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with self.__class__(self.connection_id, conn=self.conn,
                                run_id=self.run_id):
                return fn(*args, **kwargs)
        return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

def _parse_period(period: str):
    """Best-effort parse of a reference-period string to a date. Returns None
    on failure. Accepts YYYY-MM-DD, YYYY-MM, YYYY."""
    if not period:
        return None
    s = str(period).strip()[:10]
    for fmt_len, suffix in ((10, ""), (7, "-01"), (4, "-01-01")):
        if len(s) >= fmt_len:
            try:
                return datetime.strptime(s[:fmt_len] + suffix, "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def _latest_period(conn, table: str, name: str) -> str:
    """Latest reference period for a series in indicator_history or timeseries.
    Matches on name only (province variants — RC-5 — all count as accrual)."""
    try:
        if table == "timeseries":
            row = conn.execute(
                "SELECT MAX(date) FROM timeseries WHERE series_name = ?",
                (name,)).fetchone()
        else:
            row = conn.execute(
                "SELECT MAX(period) FROM indicator_history "
                "WHERE indicator_name = ? AND period != ''",
                (name,)).fetchone()
        return (row[0] or "") if row else ""
    except sqlite3.OperationalError:
        return ""  # table absent (fresh/test DB)


def check_health(conn=None, now: datetime | None = None) -> dict:
    """Compute per-connection health and series accrual state.

    Returns a JSON-serializable dict:
        {generated_at, summary: {ok, warn, critical, unknown,
         overdue_series_total}, connections: [{id, name, category, cadence,
         last_run_at, last_status, last_success_at, days_since_success,
         consecutive_failures, health, overdue_series, series, notes}]}

    Health levels:
        unknown  — never recorded (uninstrumented or never run)
        ok       — last success within cadence, no trailing failures
        warn     — dark > 1x cadence, or last run failed, or overdue series
        critical — dark > 2x cadence, or >= 2 consecutive failures
    """
    owns_conn = conn is None or not hasattr(conn, "execute")
    c = _open_default_conn() if owns_conn else conn
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    now_date = now_dt.date()
    checked_at = now_dt.isoformat(timespec="seconds")

    try:
        ensure_schema(c)
        out_conns = []
        summary = {"ok": 0, "warn": 0, "critical": 0, "unknown": 0,
                   "overdue_series_total": 0}

        for spec in CONNECTIONS:
            cid = spec["id"]
            rows = c.execute(
                "SELECT started_at, finished_at, status, items_fetched, "
                "items_saved, error FROM connection_runs "
                "WHERE connection_id = ? ORDER BY started_at DESC, id DESC "
                "LIMIT 20", (cid,)).fetchall()

            last_run_at = rows[0][0] if rows else None
            last_status = rows[0][2] if rows else None
            last_error = rows[0][5] if rows else ""
            last_success_at = None
            consecutive_failures = 0
            counting = True
            for r in rows:
                st = r[2]
                if counting:
                    if st == "failed":
                        consecutive_failures += 1
                    elif st == "skipped":
                        pass  # skipped runs neither break nor extend the streak
                    else:
                        counting = False
                if st in ("ok", "degraded") and last_success_at is None:
                    last_success_at = r[0]

            days_since_success = None
            if last_success_at:
                d = _parse_period(last_success_at)
                if d:
                    days_since_success = (now_date - d).days

            # ── Series accrual ────────────────────────────────────────
            overdue_series = []
            series_state = []
            for s in spec.get("series", []):
                latest = _latest_period(c, s.get("table", "indicator_history"),
                                        s["name"])
                gap_days = None
                overdue = False
                d = _parse_period(latest)
                if d:
                    gap_days = (now_date - d).days
                    threshold = SERIES_OVERDUE_DAYS.get(
                        s.get("frequency", "monthly"), 65)
                    overdue = gap_days > threshold
                elif latest == "":
                    overdue = None  # never accrued / table absent — reported, not flagged
                entry = {"name": s["name"], "table": s.get("table", "indicator_history"),
                         "frequency": s.get("frequency", ""),
                         "latest_period": latest, "gap_days": gap_days,
                         "overdue": bool(overdue) if overdue is not None else None}
                series_state.append(entry)
                if overdue:
                    overdue_series.append(entry)
                # persist to series_accrual
                key = f"{s.get('table','indicator_history')}:{s['name']}"
                c.execute(
                    "INSERT INTO series_accrual (series_key, connection_id, tbl, "
                    "frequency, latest_period, gap_days, overdue, last_checked) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(series_key) DO UPDATE SET "
                    "connection_id=excluded.connection_id, tbl=excluded.tbl, "
                    "frequency=excluded.frequency, "
                    "latest_period=excluded.latest_period, "
                    "gap_days=excluded.gap_days, overdue=excluded.overdue, "
                    "last_checked=excluded.last_checked",
                    (key, cid, s.get("table", "indicator_history"),
                     s.get("frequency", ""), latest, gap_days,
                     1 if overdue else 0, checked_at))

            # ── Health classification ─────────────────────────────────
            if not rows:
                health = "unknown"
            else:
                health = "ok"
                dark = CADENCE_DARK_DAYS.get(spec.get("cadence", "weekly"))
                if dark and days_since_success is not None:
                    warn_d, crit_d = dark
                    if days_since_success > crit_d:
                        health = "critical"
                    elif days_since_success > warn_d:
                        health = "warn"
                if dark and days_since_success is None:
                    # recorded runs but never a success
                    health = "critical"
                if consecutive_failures >= 2:
                    health = "critical"
                elif consecutive_failures == 1 and health == "ok":
                    health = "warn"
                if last_status == "degraded" and health == "ok":
                    health = "warn"
            if overdue_series and health in ("ok", "unknown"):
                health = "warn"

            summary[health] = summary.get(health, 0) + 1
            summary["overdue_series_total"] += len(overdue_series)

            out_conns.append({
                "id": cid,
                "name": spec["name"],
                "module": spec["module"],
                "category": spec["category"],
                "cadence": spec["cadence"],
                "last_run_at": last_run_at,
                "last_status": last_status,
                "last_error": last_error or "",
                "last_success_at": last_success_at,
                "days_since_success": days_since_success,
                "consecutive_failures": consecutive_failures,
                "health": health,
                "overdue_series": overdue_series,
                "series": series_state,
                "notes": spec.get("notes", ""),
            })

        c.commit()
        return {"generated_at": checked_at, "summary": summary,
                "connections": out_conns}
    finally:
        if owns_conn:
            try:
                c.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def write_status_json(health: dict | None = None, conn=None,
                      root: str | None = None) -> list[str]:
    """Write warehouse_status.json to docs/data/ and mirror to public/data/
    (matching the export convention — deploy syncs public/ -> docs/).
    Returns list of paths written. Never raises."""
    paths = []
    try:
        if health is None:
            health = check_health(conn=conn)
        base = root or _ROOT
        for sub in ("docs/data", "public/data"):
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            p = os.path.join(d, "warehouse_status.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(health, f, indent=2, default=str)
            paths.append(p)
    except Exception as e:
        print(f"[WAREHOUSE] write_status_json failed (non-critical): "
              f"{type(e).__name__}: {e}")
    return paths


def log_health_summary(health: dict) -> None:
    """Print loud [WAREHOUSE] lines for failed/overdue connections."""
    try:
        s = health.get("summary", {})
        print(f"[WAREHOUSE] Connection health: {s.get('ok', 0)} ok, "
              f"{s.get('warn', 0)} warn, {s.get('critical', 0)} critical, "
              f"{s.get('unknown', 0)} never-recorded; "
              f"{s.get('overdue_series_total', 0)} overdue series")
        for con in health.get("connections", []):
            if con["health"] == "critical":
                print(f"[WAREHOUSE][CRITICAL] {con['id']}: last success "
                      f"{con['last_success_at'] or 'never'} "
                      f"({con['days_since_success']}d ago), "
                      f"{con['consecutive_failures']} consecutive failures"
                      + (f" — {con['last_error']}" if con.get("last_error") else ""))
            elif con["health"] == "warn":
                why = []
                if con["days_since_success"] is not None:
                    why.append(f"last success {con['days_since_success']}d ago")
                if con["overdue_series"]:
                    why.append("overdue: " + ", ".join(
                        f"{x['name']} (latest {x['latest_period'] or 'none'})"
                        for x in con["overdue_series"]))
                if con["last_status"] == "failed":
                    why.append("last run failed")
                print(f"[WAREHOUSE][WARN] {con['id']}: {'; '.join(why) or con['last_status']}")
            else:
                for x in con.get("overdue_series", []):
                    print(f"[WAREHOUSE][WARN] {con['id']}: series {x['name']} "
                          f"overdue (latest {x['latest_period']}, "
                          f"{x['gap_days']}d old, {x['frequency']})")
    except Exception as e:
        print(f"[WAREHOUSE] log_health_summary failed (non-critical): {e}")
