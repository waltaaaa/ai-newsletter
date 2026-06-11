"""
db.py — SQLite interface module for CAN-MACRO Dashboard.

Single-module interface to SQLite — no other module needs to import sqlite3 directly.
Maps all 24 tables to SQLite.

Tables:
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
 15. evidence          — normalized evidence rows (from projects.evidence JSON)
 16. documents         — URL fetch/classification tracking
 17. project_events    — normalized status/cost change timeline
 18. organizations     — canonical proponent entities
 19. organization_aliases — proponent name variants
 20. project_organizations — project-to-organization links
 21. project_identifiers — official IDs (IAAC, CER, municipal app, etc.)
 22. job_snapshots     — weekly job posting aggregates and hiring spike alerts
 23. policy_snapshots  — weekly policy/legislative developments with sector/project linkages

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
from collections import Counter
from datetime import datetime

from normalize import normalize_province, normalize_status, parse_value

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

# Terminal states that always override forward states.
# C5 (2026-06-08 audit): hold states are no longer unconditional — a media
# article saying "delayed" was flipping Under Construction projects to On Hold
# through this set. Only Cancelled remains always-apply; holds are gated in
# _should_update_status (require an explicit/government-backed signal).
_TERMINAL_STATES = {"Cancelled"}
_HOLD_STATES = {"On Hold", "Suspended", "Paused"}

# E6 (2026-06-08 audit): per-reason rejection counters. upsert_project prints
# and returns None on rejection, so callers only ever see an undifferentiated
# "skipped" count. These module-level counters let the orchestration layer log
# a breakdown (rejected_no_url / non_project_name / invalid_province / …).
REJECTION_COUNTERS: Counter = Counter()


def get_rejection_counters(reset: bool = False) -> dict:
    """Return (and optionally reset) the per-reason upsert rejection counters."""
    snapshot = dict(REJECTION_COUNTERS)
    if reset:
        REJECTION_COUNTERS.clear()
    return snapshot


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
    history_earliest_date TEXT DEFAULT '',
    official_ids    TEXT DEFAULT '{}',
    announcement_date TEXT DEFAULT '',
    start_date      TEXT DEFAULT '',
    parsed_value    REAL,
    provinces_additional TEXT DEFAULT ''
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

-- 15. Evidence (normalized from projects.evidence JSON)
CREATE TABLE IF NOT EXISTS evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(rowid),
    url             TEXT NOT NULL,
    url_normalized  TEXT,
    source_type     TEXT,
    source_tier     TEXT,
    source_weight   REAL DEFAULT 0.5,
    field_claimed   TEXT,
    extracted_value TEXT,
    extraction_date TEXT,
    published_date  TEXT,
    confidence      REAL DEFAULT 0.5,
    content_hash    TEXT,
    is_primary      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, url_normalized, field_claimed)
);

CREATE INDEX IF NOT EXISTS idx_evidence_project ON evidence(project_id);
CREATE INDEX IF NOT EXISTS idx_evidence_url ON evidence(url_normalized);
CREATE INDEX IF NOT EXISTS idx_evidence_source_type ON evidence(source_type);

-- Audit M4 (2026-06-11): hot-query indexes on the projects table. Export,
-- province filters, status counters, and stale detection all scan these
-- columns on a 6k+ row table.
CREATE INDEX IF NOT EXISTS idx_projects_province ON projects(province);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_sector ON projects(sector);
CREATE INDEX IF NOT EXISTS idx_projects_lastseen ON projects(lastSeen);

-- 16. Documents (URL fetch/classification tracking)
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    url_normalized  TEXT UNIQUE NOT NULL,
    content_hash    TEXT,
    title           TEXT,
    published_date  TEXT,
    fetch_date      TEXT DEFAULT (datetime('now')),
    source_tier     TEXT,
    source_type     TEXT,
    fetch_status    TEXT DEFAULT 'fetched',
    is_relevant     INTEGER,
    classification_json TEXT,
    language        TEXT DEFAULT 'en',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url_normalized);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(fetch_status);

-- 17. Project events (normalized from projects.statusHistory JSON)
CREATE TABLE IF NOT EXISTS project_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(rowid),
    event_type      TEXT NOT NULL,
    event_date      TEXT,
    detected_date   TEXT DEFAULT (datetime('now')),
    status_before   TEXT,
    status_after    TEXT,
    cost_before     TEXT,
    cost_after      TEXT,
    summary         TEXT,
    evidence_id     INTEGER REFERENCES evidence(id),
    source_url      TEXT,
    is_material     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_project ON project_events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON project_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_date ON project_events(event_date);

-- 18. Organizations (canonical proponent names)
CREATE TABLE IF NOT EXISTS organizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name  TEXT UNIQUE NOT NULL,
    org_type        TEXT,
    hq_province     TEXT,
    website         TEXT,
    ticker          TEXT,
    sedar_id        TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 19. Organization aliases
CREATE TABLE IF NOT EXISTS organization_aliases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    alias           TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    UNIQUE(organization_id, alias_normalized)
);

CREATE INDEX IF NOT EXISTS idx_org_aliases_norm ON organization_aliases(alias_normalized);

-- 20. Project-organization links
CREATE TABLE IF NOT EXISTS project_organizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(rowid),
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    role            TEXT DEFAULT 'proponent',
    source_evidence_id INTEGER REFERENCES evidence(id),
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, organization_id, role)
);

-- 21. Project identifiers (official IDs from registries/filings)
CREATE TABLE IF NOT EXISTS project_identifiers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(rowid),
    id_type         TEXT NOT NULL,
    id_value        TEXT NOT NULL,
    source_url      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(id_type, id_value)
);

CREATE INDEX IF NOT EXISTS idx_identifiers_type_value ON project_identifiers(id_type, id_value);
CREATE INDEX IF NOT EXISTS idx_identifiers_project ON project_identifiers(project_id);

CREATE TABLE IF NOT EXISTS miss_audit_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_date      TEXT DEFAULT (datetime('now')),
    province        TEXT,
    sector          TEXT,
    miss_type       TEXT,
    description     TEXT,
    suggested_action TEXT,
    resolved        INTEGER DEFAULT 0
);

-- 22. Job snapshots (weekly job posting aggregates and hiring spike alerts)
CREATE TABLE IF NOT EXISTS job_snapshots (
    week_of     TEXT NOT NULL,
    data        TEXT NOT NULL,
    spikes      TEXT,
    created     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (week_of)
);

-- 23. Policy snapshots (weekly policy/legislative developments with sector/project linkages)
CREATE TABLE IF NOT EXISTS policy_snapshots (
    week_of     TEXT NOT NULL,
    data        TEXT NOT NULL,
    summary     TEXT,
    created     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (week_of)
);

-- 24. Claude checkpoints (resume-after-crash for expensive API calls)
CREATE TABLE IF NOT EXISTS claude_checkpoints (
    run_id    TEXT NOT NULL,
    call_name TEXT NOT NULL,
    response  TEXT,
    cost_usd  REAL DEFAULT 0,
    created   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, call_name)
);

-- 25. Project changes (append-only change log for temporal detection)
CREATE TABLE IF NOT EXISTS project_changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    change_date TEXT NOT NULL DEFAULT (date('now')),
    change_type TEXT NOT NULL,
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    source_url  TEXT DEFAULT '',
    significance REAL DEFAULT 0.5,
    sweep_id    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_project_changes_project ON project_changes(project_id);
CREATE INDEX IF NOT EXISTS idx_project_changes_date ON project_changes(change_date);

-- 26. Cache (persistent pipeline cache — embeddings, page text, OCR, etc.)
CREATE TABLE IF NOT EXISTS cache (
    cache_key   TEXT PRIMARY KEY,
    cache_type  TEXT NOT NULL,
    value       BLOB NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL,
    hit_count   INTEGER DEFAULT 0,
    last_hit_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(cache_type);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);

-- 27. Feedback (append-only learning signals from each sweep)
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_id    TEXT NOT NULL,
    sweep_date  TEXT NOT NULL DEFAULT (date('now')),
    signal_type TEXT NOT NULL,
    signal_key  TEXT NOT NULL,
    signal_value TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(signal_type);
CREATE INDEX IF NOT EXISTS idx_feedback_sweep ON feedback(sweep_id);

-- 28. Learned config (optimized configuration from learning engine)
CREATE TABLE IF NOT EXISTS learned_config (
    config_key   TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by   TEXT NOT NULL,
    prior_value  TEXT,
    reason       TEXT
);

-- 29. Sweep metrics (per-sweep performance metrics for regression detection)
CREATE TABLE IF NOT EXISTS sweep_metrics (
    sweep_id                  TEXT PRIMARY KEY,
    sweep_date                TEXT NOT NULL,
    total_queries_run         INTEGER DEFAULT 0,
    total_projects_extracted  INTEGER DEFAULT 0,
    new_projects              INTEGER DEFAULT 0,
    updated_projects          INTEGER DEFAULT 0,
    claude_corrections        INTEGER DEFAULT 0,
    claude_confirmations      INTEGER DEFAULT 0,
    dedup_merges              INTEGER DEFAULT 0,
    snowball_queries_generated INTEGER DEFAULT 0,
    snowball_new_projects     INTEGER DEFAULT 0,
    avg_confidence_score      REAL DEFAULT 0,
    nim_api_calls             INTEGER DEFAULT 0,
    claude_api_calls          INTEGER DEFAULT 0,
    cache_hit_rate            REAL DEFAULT 0,
    wall_time_seconds         INTEGER DEFAULT 0
);

-- 30. Project alerts (automatic Google News RSS tracking per project)
CREATE TABLE IF NOT EXISTS project_alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL,
    norm_key            TEXT NOT NULL UNIQUE,
    query_text          TEXT NOT NULL,
    rss_url             TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_checked        TEXT DEFAULT NULL,
    last_found_articles INTEGER DEFAULT 0,
    check_count         INTEGER DEFAULT 0,
    active              INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_project_alerts_active ON project_alerts(active);
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

    # Phase 5 migration: add official_ids column if missing (existing DBs)
    try:
        conn.execute("SELECT official_ids FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE projects ADD COLUMN official_ids TEXT DEFAULT '{}'")
        conn.commit()

    # Confidence decay migration: add decay tracking columns if missing
    try:
        conn.execute("SELECT display_confidence FROM projects LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE projects ADD COLUMN display_confidence REAL DEFAULT 0.3")
        conn.execute("ALTER TABLE projects ADD COLUMN days_since_update INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE projects ADD COLUMN is_stale INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE projects ADD COLUMN needs_review INTEGER DEFAULT 0")
        conn.commit()

    # Verification & cost-finding migration: add columns needed by Phase 8
    # NEW-1 (2026-06-08 audit): quality_tier is read by tools/export_dashboard.py
    #   (export_all_projects ORDER BY CASE quality_tier) and written by
    #   tools/cleanup_projects.py, but was never in the canonical schema — so a
    #   fresh/empty DB crashed export and broke 5 pytest cases. Create it here so
    #   the column always exists; cleanup_projects.py still refines per-row values.
    for col, typedef in [
        ("value_millions", "REAL DEFAULT NULL"),
        ("urls_checked_at", "TEXT DEFAULT ''"),
        ("last_verification_check", "TEXT DEFAULT ''"),
        ("cost_unfindable", "INTEGER DEFAULT 0"),
        ("cost_search_attempts", "INTEGER DEFAULT 0"),
        ("last_cost_search", "TEXT DEFAULT ''"),
        ("verification_status", "TEXT DEFAULT ''"),
        ("value_notes", "TEXT DEFAULT ''"),
        ("value_low_millions", "REAL DEFAULT NULL"),
        ("quality_tier", "TEXT DEFAULT 'registry'"),
        # G7 (quality-pass-1.4): value semantics — currency ISO code, stated
        # range bounds (in millions), and scope ('phase'|'program'|'').
        # Old rows stay NULL/default; no backfill.
        ("currency", "TEXT DEFAULT 'CAD'"),
        ("value_low", "REAL DEFAULT NULL"),
        ("value_high", "REAL DEFAULT NULL"),
        ("value_scope", "TEXT DEFAULT ''"),
        # G8 (quality-pass-1.4): count of distinct triangulation axes with
        # >=1 observation (regulatory / financial_disclosure / commercial /
        # pre_public / media). Computed in upsert_project via triangulation.py.
        ("axes_satisfied", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM projects LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {typedef}")
            conn.commit()

    # G12 (quality-pass-1.4): republication tracking on the evidence table.
    # republication_of references the evidence rowid of the original row with
    # the same content_hash within the same project. Republications contribute
    # zero weight to confidence; URLs are never dropped.
    try:
        conn.execute("SELECT republication_of FROM evidence LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE evidence ADD COLUMN republication_of INTEGER")
        conn.commit()

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


def _has_real_value(v) -> bool:
    """G7: True if a value string carries actual information (not a placeholder)."""
    if v is None:
        return False
    s = str(v).strip().lower()
    return s not in ("", "—", "-", "not disclosed", "n/a", "unknown", "null", "none")


def _axes_satisfied_safe(evidence, discovery_sources) -> int:
    """G8: triangulation axes count; never raises (returns 0 on any failure)."""
    try:
        from triangulation import axes_satisfied
        return axes_satisfied(evidence or [], discovery_sources or [])
    except Exception as e:
        logger.debug(f"axes_satisfied failed (non-fatal): {e}")
        return 0


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

    S4 (quality-pass-1.4): after the union, the merged array is stable-sorted
    by link quality (deep > listing > homepage > unknown, ties keep original
    position) so evidence[0] is the most project-specific deep link — the
    frontend's SOURCE column links evidence[0]. firstTracked is a separate
    column, so nothing keys off evidence[0] as "earliest". The union itself
    is unchanged: URLs are NEVER dropped.
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

    # S4: deep links first (stable sort — original order is the tiebreaker)
    try:
        from url_utils import classify_url_quality
        _quality_rank = {"deep": 3, "listing": 2, "homepage": 1}
        merged.sort(key=lambda ev: -_quality_rank.get(
            classify_url_quality((ev or {}).get("url", "")), 0))
    except ImportError:
        pass

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


def _should_update_status(existing_status: str, new_status: str,
                          explicit_hold: bool = False) -> bool:
    """Return True if new_status should replace existing_status.

    Rules:
    - Cancelled always applies (true terminal state).
    - Hold states (On Hold / Suspended / Paused) apply ONLY when the signal is
      explicit (regulatory stop-work / government source) — C5: previously they
      were unconditional, so any media mention of "delayed" regressed an
      Under Construction project to On Hold.
    - Otherwise: only update if new status order > existing status order.
    """
    if new_status in _TERMINAL_STATES:
        return True
    if new_status in _HOLD_STATES:
        return explicit_hold
    existing_order = STATUS_ORDER.get(existing_status, 0)
    new_order = STATUS_ORDER.get(new_status, -2)
    return new_order > existing_order


def _has_explicit_hold_signal(project_dict: dict) -> bool:
    """True if an incoming hold status is backed by an explicit signal.

    Accepted signals: an explicit caller flag (regulatory stop-work orders,
    IAAC suspensions set explicit_hold=True), or government-authority evidence
    on the incoming record itself.
    """
    if project_dict.get("explicit_hold") or project_dict.get("regulatory_signal"):
        return True
    if project_dict.get("has_government_source"):
        return True
    evidence = project_dict.get("evidence") or []
    if isinstance(evidence, str):
        evidence = _from_json(evidence, [])
    return any(isinstance(e, dict) and e.get("authority") == "government"
               for e in evidence)


# ──────────────────────────────────────────────────────────────────────────────
# Name-quality gate helpers (D-1, D-14)
# ──────────────────────────────────────────────────────────────────────────────

# Date string pattern: "January 31, 2025", "Jan 31, 2025", "January 31 2025"
_DATE_NAME_RE = re.compile(
    r'^\s*(?:January|February|March|April|May|June|July|August|September|October|November|December|'
    r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\s*$',
    re.IGNORECASE
)
# Pure ISO date
_ISO_DATE_RE = re.compile(r'^\s*\d{4}-\d{2}-\d{2}\s*$')

# Nav-item / boilerplate exact-match list. Lower-cased for matching.
_NAV_ITEM_NAMES = {
    'open data', 'press room', 'sign-up to discover', 'instagram',
    'subscribe for updates', 'find a document', 'onboarding', 'accessibility',
    'metrolinx newsletter', 'staff portal', 'body-worn camera program',
    'travel & hospitality expenses', 'latest stories', 'sign-up for updates',
    'manage your experience', 'subscription configuration',
    'region and project preferences', 'detailed expense report',
    # Additional generic nav/page items observed in audit
    'contact us', 'about us', 'about', 'home', 'sitemap', 'privacy',
    'privacy policy', 'terms of use', 'terms and conditions', 'careers',
    'jobs', 'newsletter', 'news', 'news releases', 'media', 'media room',
    'media centre', 'media center', 'login', 'log in', 'sign in', 'sign up',
    'register', 'subscribe', 'unsubscribe', 'search', 'menu', 'help',
    'faq', 'faqs', 'frequently asked questions', 'rss', 'rss feed',
    'twitter', 'facebook', 'linkedin', 'youtube', 'tiktok',
    'follow us', 'share', 'social media', 'language selection',
    'change language', 'français', 'english', 'en français',
    'projects', 'project', 'document', 'documents', 'resources',
    'publications', 'reports', 'links', 'related links', 'quick links',
    'top of page', 'back to top', 'skip to content', 'skip to main content',
}

# Markdown header / fragment prefixes that indicate the "name" is a doc fragment
_MD_HEADER_PREFIXES = ('#', '**', '- ')

# Minimum alphabetic characters in a real project name
_MIN_ALPHA_CHARS = 4


def _is_non_project_name(name: str) -> bool:
    """Return True if the name is structurally non-project (nav-item, date, fragment).

    Catches the D-1 (Metrolinx nav-item pollution) and D-14 (Saskatchewan
    date-string project names) failure modes at the upsert boundary.
    """
    if not name:
        return True
    stripped = name.strip()
    if not stripped:
        return True
    # Date strings (e.g. "July 31, 2025" or ISO "2025-07-31")
    if _DATE_NAME_RE.match(stripped):
        return True
    if _ISO_DATE_RE.match(stripped):
        return True
    # Markdown header fragments
    if stripped.startswith(_MD_HEADER_PREFIXES):
        return True
    # Nav-item exact match (case-insensitive)
    if stripped.lower() in _NAV_ITEM_NAMES:
        return True
    # Entirely numeric (e.g. "12345" or "2025")
    if stripped.replace(',', '').replace('.', '').replace(' ', '').isdigit():
        return True
    # Entirely punctuation/symbols
    if not any(c.isalnum() for c in stripped):
        return True
    # Too few alphabetic characters (< 4)
    alpha_count = sum(1 for c in stripped if c.isalpha())
    if alpha_count < _MIN_ALPHA_CHARS:
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# P1 — non-project DOCUMENT-type filter (promoted from tools/export_dashboard)
# ──────────────────────────────────────────────────────────────────────────────

# Non-project DOCUMENT types that EA registries emit as rows (Forest Management
# Plans, reports, EIS, terms of reference, RFPs, public notices). These are not
# capital projects and were flooding the MB/NL provincial counts (discovery
# audit: MB 2,037 rows / ~50 with a real value; NL 1,554 / ~48). Applied at
# INGESTION (gov_sources scrapers, value-less rows only) and at EXPORT
# (tools/export_dashboard, which imports this with a local fallback).
NON_PROJECT_DOCTYPE_RE = re.compile(
    r"\b(forest management plan|"
    r"annual report|monitoring report|status report|background report|"
    r"environmental impact statement|"
    r"terms of reference|"
    r"discussion paper|"
    r"request for (proposal|comment|information|qualification)|"
    r"public (comment|notice|consultation)|"
    r"notice of (commencement|determination))\b",
    re.IGNORECASE,
)


def is_non_project_doctype(name) -> bool:
    """True if `name` looks like a registry DOCUMENT filing, not a capital project."""
    return bool(name and NON_PROJECT_DOCTYPE_RE.search(name))


# ──────────────────────────────────────────────────────────────────────────────
# C1 — fuzzy rediscovery fallback (2026-06-08 audit)
# ──────────────────────────────────────────────────────────────────────────────
# The live upsert matched only on the exact name+province slug, so a project
# re-found with ANY name variation ("Site C" vs "Site C Hydroelectric Dam")
# wrote a brand-new row — measured result: 90.8% of projects carried exactly one
# evidence item and 96.6% had empty multi-tier provenance. After an exact-key
# miss we now run a blocked fuzzy lookup that reuses the STRICT guarded matcher
# from tools/dedup_projects_fuzzy (series-identifier, proponent, CMA and
# value-ratio contradiction kills — biased toward false-negative, so "Surmont
# (ConocoPhillips)" vs "Surmont (MEG)" stay distinct). Disable: LI_FUZZY_UPSERT=0.

_FUZZY_STOPWORDS = {
    'project', 'projects', 'expansion', 'phase', 'stage', 'the', 'and', 'of',
    'in', 'at', 'on', 'for', 'to', 'a', 'an', 'redevelopment', 'development',
    'plant', 'facility', 'centre', 'center', 'building', 'mine', 'plan',
    'corp', 'inc', 'ltd', 'ltee', 'limited',
    # Keep in sync with tools/dedup_projects_fuzzy._STOPWORDS — announcement-
    # framing words make poor blocking tokens (they match half the table).
    'partnership', 'agreement', 'announcement', 'deal', 'initiative',
    'investment', 'proposal',
}

# Observability: fuzzy-merge hits per process (read via get_merge_counters)
MERGE_COUNTERS: Counter = Counter()


def get_merge_counters(reset: bool = False) -> dict:
    """Return (and optionally reset) the fuzzy-merge counters."""
    snapshot = dict(MERGE_COUNTERS)
    if reset:
        MERGE_COUNTERS.clear()
    return snapshot


def _fuzzy_find_existing(conn: sqlite3.Connection, name: str, province: str,
                         project_dict: dict) -> str | None:
    """Blocked fuzzy lookup for an existing duplicate row after an exact-key miss.

    Blocking: same province + name LIKE on up to 3 longest distinctive (≥4-char)
    tokens. Matching: tools/dedup_projects_fuzzy.is_duplicate_pair — the same
    guarded matcher the offline consolidation tool uses (C6: listing URLs are
    excluded from the shared-URL signal). Returns the matched norm_key or None.
    """
    try:
        from tools.dedup_projects_fuzzy import (
            normalize_name, is_duplicate_pair, url_set)
        from url_utils import is_listing_url
    except ImportError:
        return None

    n1 = normalize_name(name)
    if not n1:
        return None

    urls1 = {u for u in (url_set(project_dict.get('evidence'))
                         | url_set(project_dict.get('sources')))
             if not is_listing_url(u)}

    rows = []

    # URL-first candidate lookup: an incoming article URL already attached to
    # a project (evidence table) is the strongest rediscovery signal there is.
    # Re-extractions of the same story across runs land here directly, even
    # when the LLM re-phrased the project name beyond fuzzy-blocking reach.
    if urls1:
        try:
            from url_utils import normalize_url as _norm_url
            norm_urls = [u2 for u2 in (_norm_url(u) for u in urls1) if u2]
            if norm_urls:
                ph = ",".join("?" * len(norm_urls))
                rows.extend(conn.execute(
                    f"SELECT DISTINCT p.norm_key, p.name, p.cma, p.proponent, "
                    f"p.parsed_value, p.evidence, p.sources "
                    f"FROM evidence e JOIN projects p ON p.rowid = e.project_id "
                    f"WHERE p.province = ? AND e.url_normalized IN ({ph})",
                    (province, *norm_urls),
                ).fetchall())
        except Exception as _e:
            logger.warning(f"[DB] URL-first rediscovery lookup failed (non-fatal): {_e}")

    block_tokens = sorted(
        (t for t in set(n1.split()) if len(t) >= 4 and t not in _FUZZY_STOPWORDS),
        key=len, reverse=True)[:3]
    if block_tokens:
        clauses = " OR ".join(["name LIKE ?"] * len(block_tokens))
        rows.extend(conn.execute(
            f"SELECT norm_key, name, cma, proponent, parsed_value, evidence, sources "
            f"FROM projects WHERE province = ? AND ({clauses})",
            (province, *[f"%{t}%" for t in block_tokens]),
        ).fetchall())
    if not rows:
        return None
    p1 = {
        'name': name,
        'cma': project_dict.get('cma', ''),
        'proponent': project_dict.get('proponent', ''),
        'parsed_value': project_dict.get('parsed_value'),
    }
    for r in rows:
        n2 = normalize_name(r['name'])
        if not n2:
            continue
        urls2 = {u for u in (url_set(r['evidence']) | url_set(r['sources']))
                 if not is_listing_url(u)}
        p2 = {'name': r['name'], 'cma': r['cma'], 'proponent': r['proponent'],
              'parsed_value': r['parsed_value']}
        if is_duplicate_pair(p1, p2, n1, n2, urls1, urls2, threshold=0.85):
            return r['norm_key']
    return None


def _best_link_quality(evidence: list) -> str:
    """S2: classify the best link on a project as deep/listing/homepage."""
    try:
        from url_utils import best_link_quality
    except ImportError:
        return ""
    urls = []
    for e in evidence or []:
        if isinstance(e, dict) and e.get("url"):
            urls.append(e["url"])
        elif isinstance(e, str):
            urls.append(e)
    return best_link_quality(urls)


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

_TIER_RANK = {'featured': 2, 'registry': 1, 'archive': 0}


def _quality_tier_safe(project_dict: dict) -> str:
    """Tier a project at write time using the canonical rules from
    tools/cleanup_projects.compute_tier.

    The quality_tier column was added by ALTER TABLE with no DEFAULT, so rows
    inserted by the pipeline carried NULL — and the exporter's ORDER BY CASE
    sorts NULL after 'archive'. Every new discovery (including marquee
    projects) was buried below the registry backfill until an operator re-ran
    the cleanup tool. Assigning the tier here closes that gap.
    """
    try:
        from tools.cleanup_projects import compute_tier
        return compute_tier({
            'parsed_value': project_dict.get('parsed_value'),
            'province': project_dict.get('province'),
            'discovery_source': project_dict.get('discovery_source', ''),
            'confidence': project_dict.get('confidence', 0.0),
        })
    except Exception:
        return 'registry'


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

    # Auto-normalize province
    primary_prov, additional_prov = normalize_province(province)
    if primary_prov is None:
        print(f"[DB] Rejected project with invalid province: {name} ({province!r})")
        REJECTION_COUNTERS["invalid_province"] += 1
        return None
    province = primary_prov
    project_dict["province"] = province
    if additional_prov:
        project_dict["provinces_additional"] = additional_prov

    # Auto-normalize status
    raw_status = project_dict.get("status", "Proposed")
    project_dict["status"] = normalize_status(raw_status)

    # Auto-populate parsed_value from value text
    if project_dict.get("parsed_value") is None:
        raw_value = project_dict.get("value")
        if raw_value:
            project_dict["parsed_value"] = parse_value(raw_value)

    # Keep value_millions in lockstep with parsed_value — ranking surfaces
    # (microscope candidate sort, briefing value rollups) read value_millions,
    # so a NULL here makes a priced project rank as $0.
    if project_dict.get("value_millions") is None and project_dict.get("parsed_value"):
        project_dict["value_millions"] = round(project_dict["parsed_value"] / 1_000_000, 3)

    # Value reasonableness gate: flag projects > $50B as suspicious
    pv = project_dict.get("parsed_value")
    if pv and pv > 50_000_000_000:
        logger.warning(f"[DB] Project value ${pv/1e9:.1f}B exceeds $50B cap: {name} ({province}). "
                       "Capping at $50B — may be program budget assigned to sub-project.")
        project_dict["parsed_value"] = 50_000_000_000
        project_dict["value"] = "C$50.0B (capped)"
        if "anomalies" not in project_dict:
            project_dict["anomalies"] = []
        if isinstance(project_dict["anomalies"], str):
            try:
                project_dict["anomalies"] = json.loads(project_dict["anomalies"])
            except (json.JSONDecodeError, TypeError):
                project_dict["anomalies"] = []
        project_dict["anomalies"].append(f"Original value ${pv/1e9:.1f}B exceeded $50B cap")

    # Name-quality gate: reject structurally non-project names (D-1, D-14)
    # Catches nav-item pollution (Metrolinx "Open Data", "Press Room", etc.)
    # and date-string project names (Saskatchewan "July 31, 2025").
    # Runs BEFORE the URL hard gate so cheap structural checks short-circuit first.
    if _is_non_project_name(name):
        print(f"[DB] Rejected project with non-project name: {name!r}")
        REJECTION_COUNTERS["non_project_name"] += 1
        return None

    # URL hard gate: reject projects with no evidence URLs
    evidence = project_dict.get("evidence", [])
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except (json.JSONDecodeError, TypeError):
            evidence = []
    if not evidence or len(evidence) == 0:
        print(f"[DB] Rejected project with no evidence URL: {name}")
        REJECTION_COUNTERS["no_url"] += 1
        return None

    key = _norm_key(name, province)
    now = _now_iso()
    today = now[:10]

    with conn:
        existing = conn.execute(
            "SELECT * FROM projects WHERE norm_key = ?", (key,)
        ).fetchone()

        # C1: fuzzy rediscovery fallback. On an exact-key miss, look for a
        # guarded duplicate (same province, blocked token lookup, strict
        # contradiction-checked matcher) and merge into it instead of writing
        # a near-duplicate row. Fail-safe: any error falls back to INSERT.
        if existing is None and os.environ.get("LI_FUZZY_UPSERT", "1") != "0":
            try:
                fuzzy_key = _fuzzy_find_existing(conn, name, province, project_dict)
            except Exception as _e:
                fuzzy_key = None
                logger.warning(f"[DB] Fuzzy fallback failed (non-fatal): {_e}")
            if fuzzy_key:
                row = conn.execute(
                    "SELECT * FROM projects WHERE norm_key = ?", (fuzzy_key,)
                ).fetchone()
                if row is not None:
                    existing = row
                    key = fuzzy_key
                    MERGE_COUNTERS["fuzzy_merged"] += 1
                    print(f"  [DB FUZZY-MERGE] '{name}' ({province}) -> existing "
                          f"'{row['name']}' [{fuzzy_key}]")

        if existing is None:
            # INSERT new project
            evidence = _from_json(
                _to_json(project_dict.get("evidence", [])), []
            )
            discovery_sources = _from_json(
                _to_json(project_dict.get("discovery_sources", [])), []
            )
            # DI-3 (2026-06-08 audit): callers almost always pass only the scalar
            # `discovery_source`, leaving discovery_sources[] empty (96.6% of rows).
            # Seed the array from the scalar so per-project provenance is tracked
            # (prerequisite for D-3 additive-confidence and E-1 merge provenance).
            _ds_scalar = (project_dict.get("discovery_source", "") or "").strip()
            if _ds_scalar and _ds_scalar not in discovery_sources:
                discovery_sources.append(_ds_scalar)
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
                    has_government_source, has_known_source, evidence_count,
                    announcement_date, start_date, parsed_value, provinces_additional,
                    currency, value_low, value_high, value_scope, axes_satisfied,
                    value_millions, quality_tier
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
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
                # S2: stamp link quality (deep/listing/homepage) at write time
                project_dict.get("source_url_quality") or _best_link_quality(evidence),
                1 if project_dict.get("has_government_source") else 0,
                1 if project_dict.get("has_known_source") else 0,
                len(evidence),
                project_dict.get("announcement_date", ""),
                project_dict.get("start_date", ""),
                project_dict.get("parsed_value"),
                project_dict.get("provinces_additional", ""),
                # G7: value semantics — currency defaults CAD; range bounds stay
                # NULL unless a range was explicitly stated (never fabricated).
                project_dict.get("currency") or "CAD",
                project_dict.get("value_low"),
                project_dict.get("value_high"),
                project_dict.get("value_scope") or "",
                # G8: triangulation axes satisfied by evidence + provenance
                _axes_satisfied_safe(evidence, discovery_sources),
                project_dict.get("value_millions"),
                project_dict.get("quality_tier") or _quality_tier_safe(project_dict),
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
            # DI-3: fold the scalar discovery_source into the array on every
            # rediscovery so provenance accumulates across tiers/weeks.
            _ds_scalar = (project_dict.get("discovery_source", "") or "").strip()
            if _ds_scalar and _ds_scalar not in merged_ds:
                merged_ds = merged_ds + [_ds_scalar]

            # D-3 diagnostic (opt-in via LI_MERGE_DEBUG=1): reveals whether
            # rediscovery actually adds evidence. ~91% of projects sit at exactly
            # one evidence item; this line shows if merges are happening at all.
            if os.environ.get("LI_MERGE_DEBUG") == "1":
                _added = len(merged_evidence) - len(existing_evidence)
                print(f"  [MERGE] {name[:60]} evidence {len(existing_evidence)}->"
                      f"{len(merged_evidence)} (+{_added}); ds {len(existing_ds)}->{len(merged_ds)}")

            # 3. Status non-regression
            existing_status = existing_dict.get("status", "Proposed")
            new_status = project_dict.get("status", existing_status)
            status_changed = False
            explicit_hold = (new_status in _HOLD_STATES
                             and _has_explicit_hold_signal(project_dict))
            if new_status and new_status != existing_status and _should_update_status(existing_status, new_status, explicit_hold):
                resolved_status = new_status
                status_changed = True
            else:
                resolved_status = existing_status
                # C5 observability: a hold signal that was NOT applied is worth
                # a log line — the project may genuinely be paused, but media
                # "delayed" mentions alone don't regress status anymore.
                if (new_status in _HOLD_STATES and new_status != existing_status
                        and not explicit_hold):
                    print(f"  [DB] Hold signal on '{name}' not applied "
                          f"({existing_status} kept; no explicit/government signal)")

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

            # G7: value precedence — a value backed by government/registry
            # authority beats a media-sourced value REGARDLESS of recency.
            # Ties (both gov or both media) keep existing behavior: incoming
            # non-empty value wins. Value-semantics fields (currency, range,
            # scope) follow whichever value won.
            incoming_value = project_dict.get("value")
            existing_value = existing_dict.get("value", "Not disclosed")
            incoming_gov = bool(project_dict.get("has_government_source")) or any(
                isinstance(e, dict) and e.get("authority") == "government"
                for e in (new_evidence or [])
            )
            existing_gov = bool(existing_dict.get("has_government_source"))
            # Existing gov-backed value is kept against ANY non-gov incoming
            # value (real, placeholder, or absent) — recency does not matter.
            keep_existing_value = (
                _has_real_value(existing_value)
                and existing_gov and not incoming_gov
            )
            if keep_existing_value:
                value = existing_value
                pv = existing_dict.get("parsed_value")
                currency = existing_dict.get("currency") or "CAD"
                value_low = existing_dict.get("value_low")
                value_high = existing_dict.get("value_high")
                value_scope = existing_dict.get("value_scope") or ""
            else:
                value = incoming_value or existing_value
                pv = project_dict.get("parsed_value") or existing_dict.get("parsed_value")
                currency = project_dict.get("currency") or existing_dict.get("currency") or "CAD"
                value_low = project_dict.get("value_low")
                if value_low is None:
                    value_low = existing_dict.get("value_low")
                value_high = project_dict.get("value_high")
                if value_high is None:
                    value_high = existing_dict.get("value_high")
                value_scope = project_dict.get("value_scope") or existing_dict.get("value_scope") or ""

            completion = project_dict.get("completionDate") or existing_dict.get("completionDate", "")
            proponent = project_dict.get("proponent") or existing_dict.get("proponent", "")

            # Re-tier from the merged state (a value arriving later can promote
            # registry -> featured). Never downgrade: a curated/hand-promoted
            # tier survives any recompute.
            recomputed_tier = _quality_tier_safe({
                'parsed_value': pv,
                'province': existing_dict.get('province'),
                'discovery_source': (project_dict.get('discovery_source')
                                     or existing_dict.get('discovery_source', '')),
                'confidence': resolved_conf,
            })
            existing_tier = existing_dict.get('quality_tier') or ''
            if _TIER_RANK.get(existing_tier, -1) >= _TIER_RANK.get(recomputed_tier, 0):
                resolved_tier = existing_tier
            else:
                resolved_tier = recomputed_tier
            announcement = project_dict.get("announcement_date") or existing_dict.get("announcement_date", "")
            start = project_dict.get("start_date") or existing_dict.get("start_date", "")
            prov_add = project_dict.get("provinces_additional") or existing_dict.get("provinces_additional", "")

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
                    evidence_count = ?,
                    announcement_date = ?,
                    start_date = ?,
                    parsed_value = ?,
                    value_millions = COALESCE(?, value_millions),
                    quality_tier = ?,
                    provinces_additional = ?,
                    currency = ?,
                    value_low = ?,
                    value_high = ?,
                    value_scope = ?,
                    axes_satisfied = ?,
                    source_url_quality = ?
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
                announcement,
                start,
                pv,
                (round(pv / 1_000_000, 3) if pv else None),
                resolved_tier,
                prov_add,
                currency,
                value_low,
                value_high,
                value_scope,
                # G8: recompute axes from merged evidence + provenance (merged
                # data only grows, so the count never regresses)
                _axes_satisfied_safe(merged_evidence, merged_ds),
                # S2: re-classify link quality from the merged evidence (S4-lite:
                # quality reflects the best link now on the project)
                _best_link_quality(merged_evidence),
                key,
            ))

    return key


def get_projects(conn: sqlite3.Connection, province: str | None = None,
                 sector: str | None = None, limit: int = 5000) -> list[dict]:
    """Return filtered list of projects.

    Args:
        conn: SQLite connection.
        province: Filter by province name or 2-letter code. Auto-normalized.
        sector: Filter by sector name (exact match).
        limit: Maximum number of results.

    Returns:
        List of project dicts.
    """
    query = "SELECT * FROM projects"
    params = []
    conditions = []

    if province:
        # Normalize province name to 2-letter code (e.g. "Ontario" → "ON")
        prov_code, _ = normalize_province(province)
        conditions.append("province = ?")
        params.append(prov_code or province)
    if sector:
        conditions.append("sector = ?")
        params.append(sector)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # NEW-3 (2026-06-08 audit): deterministic order. Without ORDER BY the result
    # set follows physical row order, which the per-run VACUUM reshuffles — so the
    # exported province/all-projects JSON churned every run even when nothing
    # changed (and LIMIT could silently drop different rows). norm_key is a stable,
    # VACUUM-proof tiebreaker (derived from name+province, unique per project).
    query += " ORDER BY lastSeen DESC, norm_key ASC"
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

    Also accepts extra fields: unit, frequency, description, backfilled, source_meta.

    source_meta (optional dict) stores provenance metadata for data grounding:
        {
            "authority": "StatCan",           # institution that published the number
            "reference_period": "2026-03",    # exact period the number covers
            "retrieved_at": "2026-03-31T...", # when the pipeline fetched this value
            "source_url": "https://...",      # direct link to the source
            "table_id": "14-10-0287",         # StatCan table ID (if applicable)
            "vector_id": 2057614,             # StatCan vector ID (if applicable)
        }
    source_meta is stored in the existing metadata JSON column, merged with
    any existing metadata rather than overwriting.

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

    # Build metadata JSON — merge source_meta into existing metadata
    metadata = {}
    if d.get("metadata"):
        if isinstance(d["metadata"], str):
            try:
                metadata = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif isinstance(d["metadata"], dict):
            metadata = dict(d["metadata"])

    source_meta = d.get("source_meta")
    if source_meta and isinstance(source_meta, dict):
        # Always set retrieved_at to now if not explicitly provided
        if "retrieved_at" not in source_meta:
            source_meta["retrieved_at"] = now
        metadata["source_meta"] = source_meta

    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else '{}'

    with conn:
        conn.execute("""
            INSERT INTO indicator_history (
                indicator_name, category, province, value, period,
                previous_value, change, source, fetched_at,
                unit, frequency, description, backfilled, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                backfilled = excluded.backfilled,
                metadata = CASE
                    WHEN excluded.metadata != '{}' THEN excluded.metadata
                    ELSE metadata
                END
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
            metadata_json,
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
    """Return the most recent value for each indicator_name+province combination.

    'Most recent' = latest `period` (reference date), with `rowid` as tiebreaker.
    Picking by period (not by insertion order) is important because old backfill
    runs can insert rows out-of-order; picking by MAX(rowid) would then shadow
    the correct current weekly values with stale orphans.
    """
    old_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM (
            SELECT ih.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY indicator_name, province
                       ORDER BY period DESC, rowid DESC
                   ) AS _rn
            FROM indicator_history ih
        )
        WHERE _rn = 1
        ORDER BY indicator_name
    """).fetchall()
    conn.row_factory = old_factory
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# BRIEFINGS
# ══════════════════════════════════════════════════════════════════════════════

def save_briefing(conn: sqlite3.Connection, briefing_dict: dict) -> int:
    """Upsert a weekly briefing by week_of. Returns the row id.

    Application-level UPSERT (no schema change required). Avoids the
    duplicate-row problem where two writers for the same week_of left stale
    rows in the table. The row with the LATEST generated_at and a non-empty
    headline is the authoritative one; earlier writes for the same week_of
    are updated in place rather than producing new id rows.

    Rules:
    - If a row exists for week_of AND its generated_at is older than the
      incoming record → UPDATE (replace headline/sections/word_count/generated_at).
    - If a row exists AND is at least as recent AND the incoming headline is
      empty → keep existing row (no-op, return existing id).
    - If a row exists AND is older OR has an empty headline → UPDATE.
    - Otherwise (no matching row) → INSERT.

    Args:
        conn: SQLite connection.
        briefing_dict: Briefing data dict with week_of, headline, sections, word_count.

    Returns:
        Row id of the upserted briefing.
    """
    now = _now_iso()
    sections = briefing_dict.get("sections", {})
    if not isinstance(sections, str):
        sections = json.dumps(sections, ensure_ascii=False)

    week_of = briefing_dict.get("week_of", now[:10])
    incoming_headline = briefing_dict.get("headline", "") or ""
    incoming_generated_at = briefing_dict.get("generated_at", now) or now
    incoming_word_count = briefing_dict.get("word_count", 0)

    with conn:
        existing = conn.execute(
            "SELECT id, headline, generated_at FROM weekly_briefings "
            "WHERE week_of = ? ORDER BY generated_at DESC, id DESC LIMIT 1",
            (week_of,),
        ).fetchone()

        if existing is None:
            cur = conn.execute(
                """INSERT INTO weekly_briefings
                   (week_of, headline, sections, word_count, generated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (week_of, incoming_headline, sections, incoming_word_count, incoming_generated_at),
            )
            return cur.lastrowid

        # Row exists — decide update vs no-op
        existing_id = existing["id"] if hasattr(existing, "__getitem__") else existing[0]
        existing_headline = (existing["headline"] if hasattr(existing, "__getitem__") else existing[1]) or ""
        existing_generated_at = (existing["generated_at"] if hasattr(existing, "__getitem__") else existing[2]) or ""

        # Skip update when the incoming record has empty headline and existing is populated + newer/equal
        if not incoming_headline and existing_headline and incoming_generated_at <= existing_generated_at:
            return existing_id

        # Update in place (always safe — replaces with the freshest non-empty data)
        conn.execute(
            """UPDATE weekly_briefings
               SET headline = ?, sections = ?, word_count = ?, generated_at = ?
               WHERE id = ?""",
            (
                incoming_headline or existing_headline,
                sections,
                incoming_word_count,
                max(incoming_generated_at, existing_generated_at),
                existing_id,
            ),
        )
        return existing_id


def cleanup_duplicate_briefings(conn: sqlite3.Connection) -> int:
    """Remove duplicate weekly_briefings rows, keeping the authoritative row per week_of.

    Authoritative row = latest generated_at with a non-empty headline (falls back
    to latest generated_at if all rows have empty headlines, then to highest id).

    Returns the number of rows deleted. Safe to run repeatedly — idempotent.
    Called once at pipeline startup from the Phase 1 migrations block.
    """
    rows = conn.execute(
        "SELECT id, week_of, headline, generated_at FROM weekly_briefings"
    ).fetchall()
    if not rows:
        return 0

    by_week: dict[str, list] = {}
    for r in rows:
        week_of = r["week_of"] if hasattr(r, "__getitem__") else r[1]
        by_week.setdefault(week_of, []).append(r)

    to_delete: list[int] = []
    for week_of, group in by_week.items():
        if len(group) <= 1:
            continue
        def _rank(r):
            rid = r["id"] if hasattr(r, "__getitem__") else r[0]
            head = (r["headline"] if hasattr(r, "__getitem__") else r[2]) or ""
            gen = (r["generated_at"] if hasattr(r, "__getitem__") else r[3]) or ""
            return (1 if head.strip() else 0, gen, rid)
        group_sorted = sorted(group, key=_rank, reverse=True)
        keeper = group_sorted[0]
        keeper_id = keeper["id"] if hasattr(keeper, "__getitem__") else keeper[0]
        for r in group_sorted[1:]:
            rid = r["id"] if hasattr(r, "__getitem__") else r[0]
            if rid != keeper_id:
                to_delete.append(rid)

    if to_delete:
        with conn:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(
                f"DELETE FROM weekly_briefings WHERE id IN ({placeholders})",
                to_delete,
            )
    return len(to_delete)


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
    """Return a list of past briefings (most recent first).

    Filters out rows with empty headlines or word_count=0 — those are stub
    inserts from failed prior runs (legacy weekly_briefing.py path) that would
    otherwise regress the exported briefing_archive.json with placeholder
    entries. A real briefing always has a headline string and word_count > 0.
    """
    rows = conn.execute(
        """SELECT * FROM weekly_briefings
           WHERE headline IS NOT NULL AND TRIM(headline) != ''
             AND COALESCE(word_count, 0) > 0
           ORDER BY week_of DESC, id DESC LIMIT ?""",
        (limit,),
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
# CLAUDE CHECKPOINTS (resume-after-crash)
# ══════════════════════════════════════════════════════════════════════════════


def save_checkpoint(conn: sqlite3.Connection, run_id: str, call_name: str,
                    response: str, cost: float = 0.0) -> None:
    """Save a Claude API response checkpoint for crash recovery.

    Args:
        conn: SQLite connection.
        run_id: Pipeline run ID (str).
        call_name: Identifier for the Claude call (e.g. 'call1-macro').
        response: Raw JSON response text.
        cost: Cost in USD for this call.
    """
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO claude_checkpoints
                (run_id, call_name, response, cost_usd, created)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (str(run_id), call_name, response, cost))


def get_checkpoint(conn: sqlite3.Connection, run_id: str,
                   call_name: str) -> dict | None:
    """Retrieve a cached Claude response for a given run + call.

    Returns:
        Dict with keys response (str), cost_usd (float) if found, else None.
    """
    row = conn.execute(
        "SELECT response, cost_usd FROM claude_checkpoints WHERE run_id=? AND call_name=?",
        (str(run_id), call_name),
    ).fetchone()
    if row is None:
        return None
    return {"response": row["response"], "cost_usd": row["cost_usd"]}


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


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_WEIGHT = {
    'federal_registry': 1.00,
    'provincial_registry': 0.98,
    'securities_filing': 0.96,
    'company_ir': 0.92,
    'gov_newsroom': 0.88,
    'municipal_record': 0.84,
    'procurement': 0.82,
    'trade_publication': 0.72,
    'business_media': 0.70,
    'local_news': 0.62,
    'rss_feed': 0.55,
    'google_news': 0.50,
    'gdelt': 0.45,
    'aggregator': 0.25,
}


def _classify_source_type(url: str, discovery_source: str = '') -> str:
    """Infer source_type from URL domain or discovery_source field."""
    from url_utils import _extract_domain, _GOV_PATTERNS_COMPILED

    if discovery_source:
        ds = discovery_source.lower()
        if ds in ('iaac', 'bc_eao', 'infrastructure_canada', 'nrcan'):
            return 'federal_registry'
        if 'provincial' in ds or '_ea' in ds:
            return 'provincial_registry'
        if ds in ('sedar', 'securities'):
            return 'securities_filing'
        if ds in ('canadabuys', 'procurement'):
            return 'procurement'
        if ds == 'municipal':
            return 'municipal_record'
        if ds == 'google_news_rss':
            return 'google_news'
        if ds == 'gdelt':
            return 'gdelt'
        if ds in ('rss', 'rss_feed'):
            return 'rss_feed'

    if not url:
        return 'aggregator'

    domain = _extract_domain(url)
    if any(p.search(domain) for p in _GOV_PATTERNS_COMPILED):
        return 'gov_newsroom'
    if '.gc.ca' in domain or '.gov.' in domain:
        return 'gov_newsroom'

    trade = {'dailycommercialnews.com', 'constructconnect.com', 'on-sitemag.com',
             'canadianminingjournal.com', 'northernminer.com', 'renewcanada.net',
             'jwnenergy.com', 'oilsandsmagazine.com'}
    if domain in trade:
        return 'trade_publication'

    major = {'cbc.ca', 'globalnews.ca', 'thestar.com', 'theglobeandmail.com',
             'nationalpost.com', 'bnnbloomberg.ca', 'reuters.com', 'bloomberg.com',
             'ici.radio-canada.ca', 'lapresse.ca', 'ledevoir.com'}
    if domain in major:
        return 'business_media'

    from url_utils import KNOWN_GOOD_DOMAINS
    if domain in KNOWN_GOOD_DOMAINS:
        return 'local_news'

    if 'news.google.com' in domain or 'google.com/alerts' in domain:
        return 'google_news'

    return 'aggregator'


def _evidence_content_hash(title: str = '', snippet: str = '') -> str | None:
    """G12: sha256 of normalized title+snippet (lowercase, whitespace-collapsed).

    Returns None when there is no content to hash — an empty-content hash would
    make every contentless evidence row within a project 'collide'.
    """
    import hashlib
    content = re.sub(r'\s+', ' ', f"{title or ''} {snippet or ''}".lower()).strip()
    if not content:
        return None
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def insert_evidence(conn: sqlite3.Connection, project_id: int, url: str,
                    discovery_source: str = '', field_claimed: str = 'general',
                    extracted_value: str = '', published_date: str = '',
                    title: str = '', snippet: str = '') -> int | None:
    """Insert a single evidence row. Returns row id or None on conflict.

    G12 (quality-pass-1.4): populates content_hash from normalized
    title+snippet. On a hash collision within the same project, the new row's
    republication_of is set to the original evidence rowid — republications
    contribute zero weight to confidence scoring but the URL is kept.
    """
    from url_utils import normalize_url
    norm = normalize_url(url)
    if not norm:
        return None

    source_type = _classify_source_type(url, discovery_source)
    weight = SOURCE_WEIGHT.get(source_type, 0.5)
    content_hash = _evidence_content_hash(title, snippet)

    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO evidence (
                    project_id, url, url_normalized, source_type, source_weight,
                    field_claimed, extracted_value, extraction_date, published_date,
                    content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
                ON CONFLICT(project_id, url_normalized, field_claimed) DO NOTHING
            """, (project_id, url, norm, source_type, weight,
                  field_claimed, extracted_value, published_date, content_hash))
            new_id = cur.lastrowid if cur.rowcount > 0 else None

            # G12: same content already on this project -> mark republication
            if new_id and content_hash:
                orig = conn.execute("""
                    SELECT id FROM evidence
                    WHERE project_id = ? AND content_hash = ? AND id < ?
                    ORDER BY id LIMIT 1
                """, (project_id, content_hash, new_id)).fetchone()
                if orig:
                    conn.execute(
                        "UPDATE evidence SET republication_of = ? WHERE id = ?",
                        (orig[0], new_id))
        return new_id
    except Exception as e:
        logger.debug(f"Evidence insert skipped for {url}: {e}")
        return None


def get_evidence_for_project(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    """Return all evidence rows for a project, ordered by source weight."""
    rows = conn.execute(
        "SELECT * FROM evidence WHERE project_id = ? ORDER BY source_weight DESC",
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

def is_already_processed(conn: sqlite3.Connection, url: str, content_hash: str = None):
    """Check if URL was already fetched. Returns (is_processed, status)."""
    from url_utils import normalize_url
    norm = normalize_url(url)
    if not norm:
        return False, 'new'
    row = conn.execute(
        "SELECT content_hash, fetch_status FROM documents WHERE url_normalized = ?", (norm,)
    ).fetchone()
    if not row:
        return False, 'new'
    if content_hash and row[0] != content_hash:
        return False, 'changed'
    return True, row[1]


def insert_document(conn: sqlite3.Connection, url: str, title: str = '',
                    source_tier: str = '', source_type: str = '',
                    published_date: str = '', content_hash: str = None) -> int | None:
    """Insert a document record. Returns row id or None on conflict."""
    from url_utils import normalize_url
    norm = normalize_url(url)
    if not norm:
        return None
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO documents (url, url_normalized, title, source_tier,
                    source_type, published_date, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_normalized) DO UPDATE SET
                    fetch_date = datetime('now'),
                    title = COALESCE(NULLIF(excluded.title, ''), title),
                    content_hash = COALESCE(excluded.content_hash, content_hash)
            """, (url, norm, title, source_tier, source_type, published_date, content_hash))
        return cur.lastrowid
    except Exception as e:
        logger.debug(f"Document insert error for {url}: {e}")
        return None


def update_document_classification(conn: sqlite3.Connection, url: str,
                                   is_relevant: bool, classification_json: str = '') -> None:
    """Update classification result for a document."""
    from url_utils import normalize_url
    norm = normalize_url(url)
    with conn:
        conn.execute("""
            UPDATE documents SET is_relevant = ?, classification_json = ?,
                fetch_status = 'classified'
            WHERE url_normalized = ?
        """, (1 if is_relevant else 0, classification_json, norm))


def update_document_status(conn: sqlite3.Connection, url: str, status: str) -> None:
    """Update fetch_status for a document."""
    from url_utils import normalize_url
    norm = normalize_url(url)
    with conn:
        conn.execute(
            "UPDATE documents SET fetch_status = ? WHERE url_normalized = ?",
            (status, norm)
        )


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

def insert_project_event(conn: sqlite3.Connection, project_id: int,
                         event_type: str, event_date: str = '',
                         status_before: str = '', status_after: str = '',
                         cost_before: str = '', cost_after: str = '',
                         summary: str = '', evidence_id: int = None,
                         source_url: str = '', is_material: bool = False) -> int:
    """Insert a project event row. Returns row id."""
    with conn:
        cur = conn.execute("""
            INSERT INTO project_events (
                project_id, event_type, event_date, status_before, status_after,
                cost_before, cost_after, summary, evidence_id, source_url, is_material
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, event_type, event_date or _now_iso()[:10],
              status_before, status_after, cost_before, cost_after,
              summary, evidence_id, source_url,
              1 if is_material else 0))
    return cur.lastrowid


def get_project_events(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    """Return all events for a project, ordered by event_date."""
    rows = conn.execute(
        "SELECT * FROM project_events WHERE project_id = ? ORDER BY event_date DESC",
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# ORGANIZATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_org_name(name: str) -> str:
    """Normalize an organization name for matching."""
    import re
    s = name.strip()
    # Strip common suffixes
    for suffix in ('Inc.', 'Inc', 'Ltd.', 'Ltd', 'Corp.', 'Corp',
                   'LP', 'L.P.', 'LLC', 'LLP', 'Co.', 'Co',
                   'Ltée', 'Limitée', 'S.E.C.'):
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip().rstrip(',')
    return re.sub(r'\s+', ' ', s).strip()


def resolve_organization(conn: sqlite3.Connection, proponent: str) -> int | None:
    """Find or create an organization from a proponent name. Returns org id."""
    if not proponent or not proponent.strip():
        return None

    norm = _normalize_org_name(proponent).lower()
    if not norm:
        return None

    # Search aliases
    row = conn.execute(
        "SELECT organization_id FROM organization_aliases WHERE alias_normalized = ?",
        (norm,)
    ).fetchone()
    if row:
        return row[0]

    # Create new organization + alias
    canonical = _normalize_org_name(proponent)
    with conn:
        cur = conn.execute(
            "INSERT INTO organizations (canonical_name) VALUES (?)",
            (canonical,)
        )
        org_id = cur.lastrowid
        conn.execute(
            "INSERT INTO organization_aliases (organization_id, alias, alias_normalized) VALUES (?, ?, ?)",
            (org_id, proponent.strip(), norm)
        )
    return org_id


def link_project_organization(conn: sqlite3.Connection, project_id: int,
                              organization_id: int, role: str = 'proponent') -> None:
    """Link a project to an organization."""
    try:
        with conn:
            conn.execute("""
                INSERT INTO project_organizations (project_id, organization_id, role)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id, organization_id, role) DO NOTHING
            """, (project_id, organization_id, role))
    except Exception as e:
        logger.debug(f"Project-org link skipped: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT IDENTIFIERS (Phase 5)
# ══════════════════════════════════════════════════════════════════════════════

_VALID_ID_TYPES = frozenset({
    'iaac', 'cer', 'provincial_ea', 'municipal_app',
    'sedar', 'permit', 'filing', 'other',
})


def insert_project_identifier(conn: sqlite3.Connection, project_id: int,
                               id_type: str, id_value: str,
                               source_url: str = '') -> int | None:
    """Insert an official project identifier. Returns row id or None on conflict."""
    if not id_value or id_type not in _VALID_ID_TYPES:
        return None
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO project_identifiers (project_id, id_type, id_value, source_url)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id_type, id_value) DO NOTHING
            """, (project_id, id_type, id_value.strip(), source_url))
        return cur.lastrowid if cur.rowcount > 0 else None
    except Exception as e:
        logger.debug(f"Identifier insert skipped ({id_type}={id_value}): {e}")
        return None


def get_project_identifiers(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    """Return all identifiers for a project."""
    rows = conn.execute(
        "SELECT * FROM project_identifiers WHERE project_id = ?",
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def find_project_by_identifier(conn: sqlite3.Connection, id_type: str,
                                id_value: str) -> int | None:
    """Find a project by an official identifier. Returns project_id or None."""
    row = conn.execute(
        "SELECT project_id FROM project_identifiers WHERE id_type = ? AND id_value = ?",
        (id_type, id_value.strip())
    ).fetchone()
    return row[0] if row else None
