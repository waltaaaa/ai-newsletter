"""
db.py — SQLite interface module for CAN-MACRO Dashboard.

Single-module interface to SQLite — no other module needs to import sqlite3 directly.
Maps all 14 Firestore collections to SQLite tables.

Collections mapped:
  1. projects          — main project database
  2. projects_fts      — FTS5 virtual table for full-text search
  3. indicator_history — economic indicator time series
  4. trend_snapshots   — weekly trend analysis snapshots
  5. weekly_briefings  — generated briefings
  6. dashboard_state   — key-value store (latest_briefing, microscope_*, tavily_credits, follow_up_queries)
  7. pipeline_runs     — structured run logs
  8. missed_projects   — user-submitted missing projects
  9. pipeline_improvements — adaptive learning improvements
 10. statcan_indicators — StatCan latest indicator values
 11. timeseries        — commodity/market time series
 12. newsletters       — legacy newsletter collection
 13. pipeline_state    — follow-up queries and state tracking
 14. projects_archive  — soft-deleted / superseded projects

Usage:
    from db import init_db, upsert_project, get_projects, search_projects

    conn = init_db()          # creates dashboard.db, returns connection
    upsert_project(conn, project_dict)
    results = get_projects(conn, province="Ontario")
    hits = search_projects(conn, "LNG pipeline")
"""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# Default database path — override via DB_PATH env var
_DEFAULT_DB_PATH = os.environ.get("DB_PATH", "dashboard.db")

# Status ordering for non-regression logic (from pipeline_config.py)
STATUS_ORDER = {
    "Rumoured": 0,
    "Proposed": 1,
    "Under Review": 2,
    "Approved": 3,
    "Under Construction": 4,
    "Partially Complete": 5,
    "Complete": 6,
    # Terminal/pause states — order -1 means they always apply
    "Cancelled": -1,
    "On Hold": -1,
    "Suspended": -1,
    "Paused": -1,
}

# Terminal states that always override forward states
_TERMINAL_STATES = {"Cancelled", "On Hold", "Suspended", "Paused"}


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTION MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_db(path: str | None = None) -> sqlite3.Connection:
    """Return a sqlite3.Connection with WAL mode, foreign keys ON, Row factory.

    Args:
        path: Path to the database file. Defaults to DB_PATH env var or 'dashboard.db'.
              Use ':memory:' for in-memory databases (tests).

    Returns:
        sqlite3.Connection configured for the pipeline.
    """
    db_path = path if path is not None else _DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for concurrent reads (not applicable to :memory:, silently ignored)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass

    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA CREATION
# ══════════════════════════════════════════════════════════════════════════════

_SCHEMA_SQL = """
-- 1. Projects (main table)
CREATE TABLE IF NOT EXISTS projects (
    rowid           INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_key        TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    province        TEXT NOT NULL,
    cma             TEXT DEFAULT '',
    sector          TEXT DEFAULT '',
    naics_code      TEXT DEFAULT '',
    naics_name      TEXT DEFAULT '',
    value           TEXT DEFAULT 'Not disclosed',
    status          TEXT DEFAULT 'Proposed',
    confidence      REAL DEFAULT 0.3,
    project_type    TEXT DEFAULT '',
    is_brownfield   INTEGER DEFAULT 0,
    proponent       TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    completionDate  TEXT DEFAULT '',
    firstTracked    TEXT DEFAULT '',
    lastUpdated     TEXT DEFAULT '',
    lastSeen        TEXT DEFAULT '',
    created         TEXT DEFAULT '',
    evidence        TEXT DEFAULT '[]',
    discovery_sources TEXT DEFAULT '[]',
    statusHistory   TEXT DEFAULT '[]',
    sources         TEXT DEFAULT '[]',
    tags            TEXT DEFAULT '[]',
    discovery_source TEXT DEFAULT '',
    source_url_quality TEXT DEFAULT '',
    anomalies       TEXT DEFAULT '[]',
    has_government_source INTEGER DEFAULT 0,
    has_known_source INTEGER DEFAULT 0,
    evidence_count  INTEGER DEFAULT 0,
    history_backfilled INTEGER DEFAULT 0,
    history_earliest_date TEXT DEFAULT ''
);

-- 2. FTS5 virtual table for full-text search on projects
CREATE VIRTUAL TABLE IF NOT EXISTS projects_fts USING fts5(
    name,
    description,
    province,
    sector,
    proponent,
    content=projects,
    content_rowid=rowid
);

-- Triggers to keep FTS5 in sync with projects table
CREATE TRIGGER IF NOT EXISTS projects_ai AFTER INSERT ON projects BEGIN
    INSERT INTO projects_fts(rowid, name, description, province, sector, proponent)
    VALUES (new.rowid, new.name, new.description, new.province, new.sector, new.proponent);
END;

CREATE TRIGGER IF NOT EXISTS projects_ad AFTER DELETE ON projects BEGIN
    INSERT INTO projects_fts(projects_fts, rowid, name, description, province, sector, proponent)
    VALUES ('delete', old.rowid, old.name, old.description, old.province, old.sector, old.proponent);
END;

CREATE TRIGGER IF NOT EXISTS projects_au AFTER UPDATE ON projects BEGIN
    INSERT INTO projects_fts(projects_fts, rowid, name, description, province, sector, proponent)
    VALUES ('delete', old.rowid, old.name, old.description, old.province, old.sector, old.proponent);
    INSERT INTO projects_fts(rowid, name, description, province, sector, proponent)
    VALUES (new.rowid, new.name, new.description, new.province, new.sector, new.proponent);
END;

-- 3. Indicator history
CREATE TABLE IF NOT EXISTS indicator_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT NOT NULL,
    category       TEXT DEFAULT '',
    province       TEXT DEFAULT 'National',
    value          REAL,
    period         TEXT DEFAULT '',
    previous_value REAL,
    change         REAL,
    source         TEXT DEFAULT '',
    fetched_at     TEXT DEFAULT '',
    unit           TEXT DEFAULT '',
    frequency      TEXT DEFAULT '',
    description    TEXT DEFAULT '',
    backfilled     INTEGER DEFAULT 0,
    metadata       TEXT DEFAULT '{}',
    UNIQUE(indicator_name, period, province)
);

-- 4. Trend snapshots
CREATE TABLE IF NOT EXISTS trend_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    week_of     TEXT NOT NULL,
    snapshot    TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT ''
);

-- 5. Weekly briefings
CREATE TABLE IF NOT EXISTS weekly_briefings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    week_of      TEXT NOT NULL,
    headline     TEXT DEFAULT '',
    sections     TEXT DEFAULT '{}',
    word_count   INTEGER DEFAULT 0,
    generated_at TEXT DEFAULT '',
    pdf_url      TEXT DEFAULT '',
    docx_url     TEXT DEFAULT ''
);

-- 6. Dashboard state (key-value store)
CREATE TABLE IF NOT EXISTS dashboard_state (
    key        TEXT PRIMARY KEY NOT NULL,
    value      TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT ''
);

-- 7. Pipeline runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    type             TEXT DEFAULT 'weekly',
    status           TEXT DEFAULT 'running',
    started_at       TEXT DEFAULT '',
    completed_at     TEXT DEFAULT '',
    duration_seconds INTEGER DEFAULT 0,
    steps_completed  TEXT DEFAULT '[]',
    errors           TEXT DEFAULT '[]',
    discovery        TEXT DEFAULT '{}',
    api_usage        TEXT DEFAULT '{}'
);

-- 8. Missed projects
CREATE TABLE IF NOT EXISTS missed_projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT DEFAULT '',
    province    TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source_url  TEXT DEFAULT '',
    submitted_at TEXT DEFAULT '',
    data        TEXT DEFAULT '{}'
);

-- 9. Pipeline improvements (adaptive learning)
CREATE TABLE IF NOT EXISTS pipeline_improvements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT DEFAULT '',
    detail      TEXT DEFAULT '',
    created_at  TEXT DEFAULT '',
    data        TEXT DEFAULT '{}'
);

-- 10. StatCan indicators (latest values)
CREATE TABLE IF NOT EXISTS statcan_indicators (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT NOT NULL,
    table_id       TEXT DEFAULT '',
    vector_id      TEXT DEFAULT '',
    value          REAL,
    period         TEXT DEFAULT '',
    unit           TEXT DEFAULT '',
    fetched_at     TEXT DEFAULT '',
    UNIQUE(indicator_name, period)
);

-- 11. Timeseries (commodity/market)
CREATE TABLE IF NOT EXISTS timeseries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    series_name TEXT NOT NULL,
    date        TEXT NOT NULL,
    value       REAL,
    unit        TEXT DEFAULT '',
    source      TEXT DEFAULT '',
    UNIQUE(series_name, date)
);

-- 12. Newsletters (legacy)
CREATE TABLE IF NOT EXISTS newsletters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    published_at TEXT DEFAULT '',
    title        TEXT DEFAULT '',
    content      TEXT DEFAULT '',
    data         TEXT DEFAULT '{}'
);

-- 13. Pipeline state (follow-up queries, misc state)
CREATE TABLE IF NOT EXISTS pipeline_state (
    key        TEXT PRIMARY KEY NOT NULL,
    value      TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT ''
);

-- 14. Projects archive (soft-deleted / superseded)
CREATE TABLE IF NOT EXISTS projects_archive (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id INTEGER,
    norm_key    TEXT DEFAULT '',
    name        TEXT DEFAULT '',
    province    TEXT DEFAULT '',
    data        TEXT DEFAULT '{}',
    archived_at TEXT DEFAULT '',
    reason      TEXT DEFAULT ''
);
"""


def init_db(path: str | None = None) -> sqlite3.Connection:
    """Initialize all database tables and return a connection.

    Idempotent — safe to call multiple times. Uses CREATE TABLE IF NOT EXISTS.

    Args:
        path: Path to the database file. Defaults to DB_PATH env var or 'dashboard.db'.
              Use ':memory:' for in-memory databases (tests).

    Returns:
        sqlite3.Connection with all tables created.
    """
    conn = get_db(path)

    # executescript runs the full schema including multi-statement triggers.
    # It commits any open transaction first, so we call it directly.
    # Note: executescript always commits after completion.
    conn.executescript(_SCHEMA_SQL)

    logger.info(f"Database initialized: {path or _DEFAULT_DB_PATH}")
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _norm_key(name: str, province: str) -> str:
    """Compute dedup key from name + province (matches project_sync.normalize_key)."""
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    p = re.sub(r"[^a-z0-9]", "", province.lower())
    return f"{n}__{p}"


def _to_json(v) -> str:
    """Serialize a value to JSON string."""
    if v is None:
        return "null"
    if isinstance(v, str):
        return v  # assume already JSON or plain string
    return json.dumps(v, ensure_ascii=False)


def _from_json(v, default=None):
    """Deserialize a JSON string; return default on failure."""
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return default


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge_evidence(existing: list, incoming: list) -> list:
    """Merge two evidence arrays without losing URLs or duplicating them.

    Uses normalize_url to detect near-duplicate URLs.
    """
    try:
        from url_utils import normalize_url
    except ImportError:
        def normalize_url(url):  # fallback if url_utils not available
            from urllib.parse import urlparse
            try:
                p = urlparse(url or "")
                return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
            except Exception:
                return url or ""

    seen_urls: set[str] = set()
    merged = []

    for ev in existing:
        url = normalize_url(ev.get("url", ""))
        if url:
            seen_urls.add(url)
        merged.append(ev)

    for ev in incoming:
        url = normalize_url(ev.get("url", ""))
        if not url:
            continue
        if url not in seen_urls:
            seen_urls.add(url)
            merged.append(ev)

    return merged


def _merge_list(existing: list, incoming: list) -> list:
    """Merge two lists without duplicates, preserving order."""
    seen = set(existing)
    result = list(existing)
    for item in incoming:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _should_update_status(existing_status: str, new_status: str) -> bool:
    """Return True if new_status should replace existing_status.

    Rules:
    - Terminal states (Cancelled, On Hold, Suspended, Paused) always apply.
    - Otherwise: only update if new status order > existing status order.
    """
    if new_status in _TERMINAL_STATES:
        return True
    existing_order = STATUS_ORDER.get(existing_status, 0)
    new_order = STATUS_ORDER.get(new_status, -2)
    return new_order > existing_order


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict, parsing JSON columns."""
    if row is None:
        return None
    d = dict(row)
    for col in ("evidence", "discovery_sources", "statusHistory", "sources",
                "tags", "anomalies", "steps_completed", "errors",
                "discovery", "api_usage", "sections", "snapshot"):
        if col in d:
            d[col] = _from_json(d[col], [] if col in ("evidence", "discovery_sources",
                                                        "statusHistory", "sources", "tags",
                                                        "anomalies", "steps_completed", "errors") else {})
    if "value" in d and col == "value":
        pass  # leave value column as-is for dashboard_state
    return d


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_project(conn: sqlite3.Connection, project_dict: dict) -> str:
    """Insert or update a project, enforcing all business rules.

    Business rules:
    1. Evidence merge — new URLs added, existing URLs kept, no duplicates.
    2. Status non-regression — status never goes backward (except terminal states).
    3. Confidence floor — confidence never decreases.

    Args:
        conn: SQLite connection from get_db() or init_db().
        project_dict: Project data dict. Must contain 'name' and 'province'.

    Returns:
        The norm_key for the upserted project.
    """
    name = (project_dict.get("name") or "").strip()
    province = (project_dict.get("province") or "").strip()
    if not name or not province:
        raise ValueError("project_dict must have non-empty 'name' and 'province'")

    key = _norm_key(name, province)
    now = _now_iso()
    today = now[:10]

    with conn:
        existing = conn.execute(
            "SELECT * FROM projects WHERE norm_key = ?", (key,)
        ).fetchone()

        if existing is None:
            # INSERT new project
            evidence = _from_json(
                _to_json(project_dict.get("evidence", [])), []
            )
            discovery_sources = _from_json(
                _to_json(project_dict.get("discovery_sources", [])), []
            )
            status_history = _from_json(
                _to_json(project_dict.get("statusHistory", [])), []
            )
            if not status_history:
                status_history = [{
                    "status": project_dict.get("status", "Proposed"),
                    "date": today,
                    "note": "First tracked",
                }]

            conn.execute("""
                INSERT INTO projects (
                    norm_key, name, province, cma, sector, naics_code, naics_name,
                    value, status, confidence, project_type, is_brownfield,
                    proponent, description, completionDate,
                    firstTracked, lastUpdated, lastSeen, created,
                    evidence, discovery_sources, statusHistory, sources, tags,
                    discovery_source, source_url_quality,
                    has_government_source, has_known_source, evidence_count
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?
                )
            """, (
                key, name, province,
                project_dict.get("cma", ""),
                project_dict.get("sector", ""),
                project_dict.get("naics_code", ""),
                project_dict.get("naics_name", ""),
                project_dict.get("value", "Not disclosed"),
                project_dict.get("status", "Proposed"),
                float(project_dict.get("confidence", 0.3)),
                project_dict.get("project_type", ""),
                1 if project_dict.get("is_brownfield") else 0,
                project_dict.get("proponent", ""),
                project_dict.get("description", ""),
                project_dict.get("completionDate", ""),
                project_dict.get("firstTracked", today),
                project_dict.get("lastUpdated", today),
                today,
                now,
                json.dumps(evidence, ensure_ascii=False),
                json.dumps(discovery_sources, ensure_ascii=False),
                json.dumps(status_history, ensure_ascii=False),
                json.dumps(project_dict.get("sources", []), ensure_ascii=False),
                json.dumps(project_dict.get("tags", []), ensure_ascii=False),
                project_dict.get("discovery_source", ""),
                project_dict.get("source_url_quality", ""),
                1 if project_dict.get("has_government_source") else 0,
                1 if project_dict.get("has_known_source") else 0,
                len(evidence),
            ))
        else:
            # UPDATE existing project
            existing_dict = dict(existing)

            # 1. Merge evidence
            existing_evidence = _from_json(existing_dict.get("evidence", "[]"), [])
            new_evidence_raw = project_dict.get("evidence", [])
            new_evidence = _from_json(_to_json(new_evidence_raw), []) if not isinstance(new_evidence_raw, list) else new_evidence_raw
            merged_evidence = _merge_evidence(existing_evidence, new_evidence)

            # 2. Merge discovery_sources
            existing_ds = _from_json(existing_dict.get("discovery_sources", "[]"), [])
            new_ds = project_dict.get("discovery_sources", [])
            if isinstance(new_ds, str):
                new_ds = _from_json(new_ds, [])
            merged_ds = _merge_list(existing_ds, new_ds)

            # 3. Status non-regression
            existing_status = existing_dict.get("status", "Proposed")
            new_status = project_dict.get("status", existing_status)
            status_changed = False
            if new_status and new_status != existing_status and _should_update_status(existing_status, new_status):
                resolved_status = new_status
                status_changed = True
            else:
                resolved_status = existing_status

            # 4. Confidence floor
            existing_conf = float(existing_dict.get("confidence", 0.3))
            new_conf = float(project_dict.get("confidence", existing_conf))
            resolved_conf = max(existing_conf, new_conf)

            # 5. Append statusHistory entry on change
            existing_history = _from_json(existing_dict.get("statusHistory", "[]"), [])
            if status_changed:
                existing_history.append({
                    "status": resolved_status,
                    "date": today,
                    "note": f"Status changed from {existing_status} to {resolved_status}",
                })

            # 6. Update scalar fields if provided
            description = project_dict.get("description") or existing_dict.get("description", "")
            value = project_dict.get("value") or existing_dict.get("value", "Not disclosed")
            completion = project_dict.get("completionDate") or existing_dict.get("completionDate", "")
            proponent = project_dict.get("proponent") or existing_dict.get("proponent", "")

            conn.execute("""
                UPDATE projects SET
                    status = ?,
                    confidence = ?,
                    evidence = ?,
                    discovery_sources = ?,
                    statusHistory = ?,
                    lastSeen = ?,
                    lastUpdated = ?,
                    description = ?,
                    value = ?,
                    completionDate = ?,
                    proponent = ?,
                    has_government_source = ?,
                    has_known_source = ?,
                    evidence_count = ?
                WHERE norm_key = ?
            """, (
                resolved_status,
                resolved_conf,
                json.dumps(merged_evidence, ensure_ascii=False),
                json.dumps(merged_ds, ensure_ascii=False),
                json.dumps(existing_history, ensure_ascii=False),
                today,
                today if status_changed else existing_dict.get("lastUpdated", today),
                description,
                value,
                completion,
                proponent,
                1 if any(e.get("authority") == "government" for e in merged_evidence) else existing_dict.get("has_government_source", 0),
                1 if any(e.get("is_known_source") for e in merged_evidence) else existing_dict.get("has_known_source", 0),
                len(merged_evidence),
                key,
            ))

    return key


def get_projects(conn: sqlite3.Connection, province: str | None = None,
                 sector: str | None = None, limit: int = 5000) -> list[dict]:
    """Return filtered list of projects.

    Args:
        conn: SQLite connection.
        province: Filter by province name (exact match).
        sector: Filter by sector name (exact match).
        limit: Maximum number of results.

    Returns:
        List of project dicts.
    """
    query = "SELECT * FROM projects"
    params = []
    conditions = []

    if province:
        conditions.append("province = ?")
        params.append(province)
    if sector:
        conditions.append("sector = ?")
        params.append(sector)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" LIMIT {int(limit)}"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_project(conn: sqlite3.Connection, norm_key: str) -> dict | None:
    """Return a single project by norm_key, or None if not found."""
    row = conn.execute(
        "SELECT * FROM projects WHERE norm_key = ?", (norm_key,)
    ).fetchone()
    return dict(row) if row else None


def get_all_projects(conn: sqlite3.Connection) -> list[dict]:
    """Return all projects (for migration verification)."""
    rows = conn.execute("SELECT * FROM projects").fetchall()
    return [dict(row) for row in rows]


def search_projects(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict]:
    """Full-text search on projects using FTS5.

    Args:
        conn: SQLite connection.
        query: Search query string.
        limit: Maximum number of results.

    Returns:
        List of project dicts ordered by relevance.
    """
    try:
        rows = conn.execute("""
            SELECT p.* FROM projects p
            JOIN projects_fts fts ON p.rowid = fts.rowid
            WHERE projects_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS5 search error for '{query}': {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def save_indicator(conn: sqlite3.Connection, indicator_dict: dict) -> None:
    """Insert or replace an economic indicator value.

    Accepts both Firestore-shaped dicts (with 'indicator' and 'date' keys)
    and SQLite-shaped dicts (with 'indicator_name' and 'period' keys).

    Also accepts extra fields: unit, frequency, description, backfilled.

    Args:
        conn: SQLite connection.
        indicator_dict: Indicator data dict.
    """
    # Normalize field names — accept both Firestore and SQLite conventions
    d = dict(indicator_dict)
    if "indicator" in d and "indicator_name" not in d:
        d["indicator_name"] = d.pop("indicator")
    if "date" in d and "period" not in d:
        d["period"] = d.pop("date")

    indicator_name = d.get("indicator_name", "")
    period = d.get("period", "")
    province = d.get("province", "National")
    now = _now_iso()

    with conn:
        conn.execute("""
            INSERT INTO indicator_history (
                indicator_name, category, province, value, period,
                previous_value, change, source, fetched_at,
                unit, frequency, description, backfilled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(indicator_name, period, province)
            DO UPDATE SET
                value = excluded.value,
                previous_value = excluded.previous_value,
                change = excluded.change,
                source = excluded.source,
                fetched_at = excluded.fetched_at,
                unit = COALESCE(excluded.unit, unit),
                frequency = COALESCE(excluded.frequency, frequency),
                description = COALESCE(excluded.description, description),
                backfilled = excluded.backfilled
        """, (
            indicator_name,
            d.get("category", ""),
            province,
            d.get("value"),
            period,
            d.get("previous_value"),
            d.get("change"),
            d.get("source", ""),
            d.get("fetched_at", now),
            d.get("unit", ""),
            d.get("frequency", ""),
            d.get("description", ""),
            1 if d.get("backfilled") else 0,
        ))


def get_indicators(conn: sqlite3.Connection, category: str | None = None,
                   province: str | None = None) -> list[dict]:
    """Return filtered indicator rows.

    Args:
        conn: SQLite connection.
        category: Filter by category (exact match).
        province: Filter by province (exact match).

    Returns:
        List of indicator dicts.
    """
    query = "SELECT * FROM indicator_history"
    params = []
    conditions = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if province:
        conditions.append("province = ?")
        params.append(province)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY fetched_at DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_latest_indicators(conn: sqlite3.Connection) -> list[dict]:
    """Return the most recent value for each indicator_name+province combination."""
    rows = conn.execute("""
        SELECT * FROM indicator_history
        WHERE rowid IN (
            SELECT MAX(rowid) FROM indicator_history
            GROUP BY indicator_name, province
        )
        ORDER BY indicator_name
    """).fetchall()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# BRIEFINGS
# ══════════════════════════════════════════════════════════════════════════════

def save_briefing(conn: sqlite3.Connection, briefing_dict: dict) -> int:
    """Insert a weekly briefing. Returns the new row id.

    Args:
        conn: SQLite connection.
        briefing_dict: Briefing data dict with week_of, headline, sections, word_count.

    Returns:
        Row id of the inserted briefing.
    """
    now = _now_iso()
    sections = briefing_dict.get("sections", {})
    if not isinstance(sections, str):
        sections = json.dumps(sections, ensure_ascii=False)

    with conn:
        cur = conn.execute("""
            INSERT INTO weekly_briefings (week_of, headline, sections, word_count, generated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            briefing_dict.get("week_of", now[:10]),
            briefing_dict.get("headline", ""),
            sections,
            briefing_dict.get("word_count", 0),
            briefing_dict.get("generated_at", now),
        ))
    return cur.lastrowid


def get_latest_briefing(conn: sqlite3.Connection) -> dict | None:
    """Return the most recent weekly briefing."""
    row = conn.execute(
        "SELECT * FROM weekly_briefings ORDER BY week_of DESC, id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["sections"] = _from_json(d.get("sections"), {})
    return d


def get_briefing_archive(conn: sqlite3.Connection, limit: int = 52) -> list[dict]:
    """Return a list of past briefings (most recent first)."""
    rows = conn.execute(
        "SELECT * FROM weekly_briefings ORDER BY week_of DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["sections"] = _from_json(d.get("sections"), {})
        result.append(d)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD STATE
# ══════════════════════════════════════════════════════════════════════════════

def save_dashboard_state(conn: sqlite3.Connection, key: str, value) -> None:
    """Insert or replace a dashboard state key-value pair.

    Args:
        conn: SQLite connection.
        key: State key (e.g., 'latest_briefing', 'tavily_credits').
        value: Any JSON-serializable value.
    """
    now = _now_iso()
    serialized = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    with conn:
        conn.execute("""
            INSERT INTO dashboard_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, serialized, now))


def get_dashboard_state(conn: sqlite3.Connection, key: str):
    """Return the value for a dashboard state key, or None if not found.

    Returns the parsed JSON value (dict, list, string, etc.).
    """
    row = conn.execute(
        "SELECT value FROM dashboard_state WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    return _from_json(row[0])


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUNS
# ══════════════════════════════════════════════════════════════════════════════

def save_pipeline_run(conn: sqlite3.Connection, run_dict: dict) -> int:
    """Insert a pipeline run log. Returns the new row id.

    Args:
        conn: SQLite connection.
        run_dict: Run data dict.

    Returns:
        Row id of the inserted run.
    """
    now = _now_iso()

    def _s(v, default="[]"):
        if v is None:
            return default
        if isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False)

    with conn:
        cur = conn.execute("""
            INSERT INTO pipeline_runs (
                type, status, started_at, completed_at, duration_seconds,
                steps_completed, errors, discovery, api_usage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_dict.get("type", "weekly"),
            run_dict.get("status", "running"),
            run_dict.get("started_at", now),
            run_dict.get("completed_at", ""),
            run_dict.get("duration_seconds", 0),
            _s(run_dict.get("steps_completed", []), "[]"),
            _s(run_dict.get("errors", []), "[]"),
            _s(run_dict.get("discovery", {}), "{}"),
            _s(run_dict.get("api_usage", {}), "{}"),
        ))
    return cur.lastrowid


def update_pipeline_run(conn: sqlite3.Connection, run_id: int, updates: dict) -> None:
    """Update specific fields on an existing pipeline run.

    Args:
        conn: SQLite connection.
        run_id: Row id of the run to update.
        updates: Dict of field -> value pairs to update.
    """
    allowed = {"type", "status", "completed_at", "duration_seconds",
               "steps_completed", "errors", "discovery", "api_usage"}
    set_clauses = []
    params = []
    for field, val in updates.items():
        if field not in allowed:
            continue
        set_clauses.append(f"{field} = ?")
        params.append(val if isinstance(val, (str, int, float)) else json.dumps(val, ensure_ascii=False))

    if not set_clauses:
        return

    params.append(run_id)
    with conn:
        conn.execute(
            f"UPDATE pipeline_runs SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )


def get_pipeline_runs(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Return recent pipeline runs (most recent first).

    Args:
        conn: SQLite connection.
        limit: Maximum number of results.

    Returns:
        List of run dicts.
    """
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for col in ("steps_completed", "errors"):
            d[col] = _from_json(d.get(col), [])
        for col in ("discovery", "api_usage"):
            d[col] = _from_json(d.get(col), {})
        result.append(d)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TAVILY CREDITS
# ══════════════════════════════════════════════════════════════════════════════

_TAVILY_STATE_KEY = "tavily_credits"


def save_tavily_credits(conn: sqlite3.Connection, month: str, used: int) -> None:
    """Store Tavily credit usage for the given month.

    Args:
        conn: SQLite connection.
        month: Month string in 'YYYY-MM' format.
        used: Number of credits used.
    """
    save_dashboard_state(conn, _TAVILY_STATE_KEY, {"month": month, "used": used})


def get_tavily_credits(conn: sqlite3.Connection) -> dict:
    """Return current month's Tavily credit usage.

    Auto-resets to 0 if stored month differs from current month.

    Returns:
        Dict with 'month' (str) and 'used' (int).
    """
    current_month = datetime.utcnow().strftime("%Y-%m")
    data = get_dashboard_state(conn, _TAVILY_STATE_KEY)
    if data and isinstance(data, dict) and data.get("month") == current_month:
        return {"month": current_month, "used": data.get("used", 0)}
    # Reset for new month
    return {"month": current_month, "used": 0}


def increment_tavily_credits(conn: sqlite3.Connection, amount: int = 1) -> None:
    """Atomically increment Tavily credit usage for the current month.

    Args:
        conn: SQLite connection.
        amount: Number of credits to add.
    """
    current = get_tavily_credits(conn)
    new_used = current["used"] + amount
    save_tavily_credits(conn, current["month"], new_used)


# ══════════════════════════════════════════════════════════════════════════════
# FOLLOW-UP QUERIES
# ══════════════════════════════════════════════════════════════════════════════

_FOLLOW_UP_KEY = "follow_up_queries"


def save_follow_up_queries(conn: sqlite3.Connection, queries: list) -> None:
    """Store follow-up queries for next week's pipeline run.

    Args:
        conn: SQLite connection.
        queries: List of query strings.
    """
    save_dashboard_state(conn, _FOLLOW_UP_KEY, {
        "queries": queries,
        "generated": _now_iso(),
        "status": "pending",
        "count": len(queries),
    })


def get_follow_up_queries(conn: sqlite3.Connection) -> list:
    """Retrieve and consume pending follow-up queries.

    Marks them as consumed so they are not retrieved again.

    Returns:
        List of query strings, or [] if none pending.
    """
    data = get_dashboard_state(conn, _FOLLOW_UP_KEY)
    if data and isinstance(data, dict) and data.get("status") == "pending":
        queries = data.get("queries", [])
        # Mark as consumed
        data["status"] = "consumed"
        data["consumed_at"] = _now_iso()
        save_dashboard_state(conn, _FOLLOW_UP_KEY, data)
        return queries
    return []


# ══════════════════════════════════════════════════════════════════════════════
# OTHER COLLECTIONS
# ══════════════════════════════════════════════════════════════════════════════

def save_missed_project(conn: sqlite3.Connection, project_dict: dict) -> int:
    """Insert a user-submitted missed project.

    Args:
        conn: SQLite connection.
        project_dict: Project data dict.

    Returns:
        Row id of the inserted record.
    """
    now = _now_iso()
    with conn:
        cur = conn.execute("""
            INSERT INTO missed_projects (name, province, description, source_url, submitted_at, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project_dict.get("name", ""),
            project_dict.get("province", ""),
            project_dict.get("description", ""),
            project_dict.get("source_url", ""),
            project_dict.get("submitted_at", now),
            json.dumps(project_dict, ensure_ascii=False),
        ))
    return cur.lastrowid


def save_pipeline_improvement(conn: sqlite3.Connection, improvement_dict: dict) -> int:
    """Insert an adaptive learning improvement record.

    Args:
        conn: SQLite connection.
        improvement_dict: Improvement data dict.

    Returns:
        Row id of the inserted record.
    """
    now = _now_iso()
    with conn:
        cur = conn.execute("""
            INSERT INTO pipeline_improvements (type, detail, created_at, data)
            VALUES (?, ?, ?, ?)
        """, (
            improvement_dict.get("type", ""),
            improvement_dict.get("detail", ""),
            improvement_dict.get("created_at", now),
            json.dumps(improvement_dict, ensure_ascii=False),
        ))
    return cur.lastrowid


def save_trend_snapshot(conn: sqlite3.Connection, snapshot_dict: dict) -> int:
    """Insert a weekly trend snapshot.

    Args:
        conn: SQLite connection.
        snapshot_dict: Snapshot data dict with week_of and snapshot fields.

    Returns:
        Row id of the inserted record.
    """
    now = _now_iso()
    snapshot = snapshot_dict.get("snapshot", snapshot_dict)
    if not isinstance(snapshot, str):
        snapshot = json.dumps(snapshot, ensure_ascii=False)

    with conn:
        cur = conn.execute("""
            INSERT INTO trend_snapshots (week_of, snapshot, created_at)
            VALUES (?, ?, ?)
        """, (
            snapshot_dict.get("week_of", now[:10]),
            snapshot,
            snapshot_dict.get("created_at", now),
        ))
    return cur.lastrowid


def get_trend_snapshots(conn: sqlite3.Connection, limit: int = 12) -> list[dict]:
    """Return recent trend snapshots (most recent first).

    Args:
        conn: SQLite connection.
        limit: Maximum number of results.

    Returns:
        List of snapshot dicts.
    """
    rows = conn.execute(
        "SELECT * FROM trend_snapshots ORDER BY week_of DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["snapshot"] = _from_json(d.get("snapshot"), {})
        result.append(d)
    return result


def save_timeseries_point(conn: sqlite3.Connection, series_name: str, date_str: str,
                          value: float | None, unit: str = "", source: str = "") -> None:
    """Upsert a single timeseries data point. Skips if the date already exists.

    Args:
        conn: SQLite connection.
        series_name: Identifier for the series (e.g. 'boc_rate', 'comm_wti').
        date_str: ISO date string (YYYY-MM-DD).
        value: Numeric value; None to skip.
        unit: Optional unit string.
        source: Optional source string.
    """
    if value is None:
        return
    with conn:
        conn.execute("""
            INSERT INTO timeseries (series_name, date, value, unit, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(series_name, date) DO NOTHING
        """, (series_name, date_str, value, unit, source))


def get_timeseries(conn: sqlite3.Connection, series_name: str, limit: int = 52) -> list[dict]:
    """Return timeseries points for a named series, most recent first.

    Args:
        conn: SQLite connection.
        series_name: Identifier for the series.
        limit: Maximum number of results.

    Returns:
        List of dicts with date, value, unit, source.
    """
    rows = conn.execute(
        "SELECT date, value, unit, source FROM timeseries "
        "WHERE series_name = ? ORDER BY date DESC LIMIT ?",
        (series_name, limit)
    ).fetchall()
    return [dict(row) for row in rows]
