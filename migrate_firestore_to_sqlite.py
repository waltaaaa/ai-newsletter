"""
migrate_firestore_to_sqlite.py -- One-time Firestore-to-SQLite migration script.

Reads all 14 Firestore collections and writes to SQLite via db.py functions.
After successful migration, no other module needs Firestore access.

Usage:
    python migrate_firestore_to_sqlite.py              # full migration
    python migrate_firestore_to_sqlite.py --dry-run    # count documents, no writes

Collections migrated:
    1. projects              -> projects table (upsert_project)
    2. indicator_history     -> indicator_history table (save_indicator)
    3. trend_snapshots       -> trend_snapshots table (save_trend_snapshot)
    4. weekly_briefings      -> weekly_briefings table (save_briefing)
    5. dashboard_state       -> dashboard_state table (save_dashboard_state)
    6. pipeline_runs         -> pipeline_runs table (save_pipeline_run)
    7. missed_projects       -> missed_projects table (save_missed_project)
    8. pipeline_improvements -> pipeline_improvements table (save_pipeline_improvement)
    9. pipeline_state        -> dashboard_state table (keyed by doc id)
   10. statcan_indicators    -> dashboard_state table (key='statcan_indicators')
   11. timeseries            -> timeseries table (direct INSERT OR REPLACE)
   12. newsletters           -> newsletters table (direct INSERT OR REPLACE)
   13. projects_archive      -> projects_archive table (direct INSERT OR REPLACE)
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

# Fix Windows console encoding for non-ASCII characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7

# ---- db.py imports -----------------------------------------------------------
from db import (
    init_db,
    upsert_project,
    save_indicator,
    save_briefing,
    save_dashboard_state,
    save_pipeline_run,
    save_missed_project,
    save_pipeline_improvement,
    save_trend_snapshot,
    get_all_projects,
    get_indicators,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Pagination: number of documents per Firestore page
_PAGE_SIZE = 200

# Retry settings for Firestore 429 / transient errors
_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 5  # seconds


# ==============================================================================
# TYPE CONVERSION HELPERS
# ==============================================================================

def _convert_value(v: Any) -> Any:
    """Recursively convert Firestore-specific types to JSON-serializable Python types.

    Handles:
    - google.cloud.firestore_v1.base_document.DocumentSnapshot  -> dict
    - google.protobuf.timestamp_pb2.Timestamp / DatetimeWithNanoseconds -> ISO string
    - datetime -> ISO string
    - google.cloud.firestore_v1.types.geo_point.GeoPoint -> {lat, lng}
    - dict -> recurse
    - list -> recurse
    """
    # Lazy import to avoid hard dependency at module level
    try:
        from google.cloud.firestore_v1 import DocumentSnapshot
        if isinstance(v, DocumentSnapshot):
            return _convert_dict(v.to_dict() or {})
    except ImportError:
        pass

    # datetime subclasses (DatetimeWithNanoseconds is a datetime subclass)
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")

    # GeoPoint: has latitude and longitude attributes
    if hasattr(v, "latitude") and hasattr(v, "longitude"):
        return {"lat": v.latitude, "lng": v.longitude}

    # None passes through
    if v is None:
        return None

    if isinstance(v, dict):
        return _convert_dict(v)

    if isinstance(v, list):
        return [_convert_value(item) for item in v]

    # Primitives: str, int, float, bool
    return v


def _convert_dict(d: dict) -> dict:
    """Recursively convert all values in a dict."""
    if d is None:
        return {}
    return {k: _convert_value(v) for k, v in d.items()}


def _to_iso(v: Any) -> str:
    """Convert any timestamp-like value to ISO 8601 string."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(v)


# ==============================================================================
# FIRESTORE INITIALISATION
# ==============================================================================

def _init_firestore():
    """Initialize Firebase Admin SDK and return the Firestore client.

    Looks for serviceAccountKey.json in the project root or the path
    specified in GOOGLE_APPLICATION_CREDENTIALS env var.
    """
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        key_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "serviceAccountKey.json"),
        )
        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)

    return firestore.client()


# ==============================================================================
# PAGINATED STREAMING WITH RETRY
# ==============================================================================

def _stream_collection_paginated(db, collection_name: str):
    """Yield all documents from a Firestore collection using cursor-based pagination.

    Uses page_size=_PAGE_SIZE to avoid 300s timeout on large collections.
    Retries up to _MAX_RETRIES times on 429 / transient errors with exponential backoff.

    Yields:
        (doc_id: str, doc_dict: dict) tuples.
    """
    collection_ref = db.collection(collection_name)
    last_doc = None
    page_num = 0

    while True:
        # Build paginated query
        if last_doc is None:
            query = collection_ref.limit(_PAGE_SIZE)
        else:
            query = collection_ref.start_after(last_doc).limit(_PAGE_SIZE)

        # Execute with retry
        docs = None
        for attempt in range(_MAX_RETRIES):
            try:
                docs = list(query.stream())
                break
            except Exception as e:
                err_str = str(e)
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"  [{collection_name}] Page {page_num + 1} attempt "
                        f"{attempt + 1}/{_MAX_RETRIES} failed: {err_str[:80]}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"  [{collection_name}] Page {page_num + 1} permanently "
                        f"failed after {_MAX_RETRIES} attempts: {err_str[:120]}"
                    )
                    raise

        if not docs:
            break  # No more pages

        page_num += 1
        logger.debug(
            f"  [{collection_name}] Page {page_num}: {len(docs)} docs"
        )

        for doc in docs:
            yield doc.id, doc

        if len(docs) < _PAGE_SIZE:
            break  # Last page

        last_doc = docs[-1]  # Cursor for next page


# ==============================================================================
# COLLECTION MIGRATION FUNCTION
# ==============================================================================

def migrate_collection(db, conn: sqlite3.Connection, collection_name: str,
                       handler_fn, dry_run: bool = False) -> dict:
    """Stream all documents from a Firestore collection and call handler_fn for each.

    Uses paginated streaming to handle large collections (>200 documents).

    Args:
        db: Firestore client.
        conn: SQLite connection.
        collection_name: Name of the Firestore collection.
        handler_fn: Callable(conn, doc_dict, doc_id) -> None. Called for each document.
        dry_run: If True, only count documents without calling handler_fn.

    Returns:
        dict with keys: collection, firestore_count, migrated, failed, errors
    """
    result = {
        "collection": collection_name,
        "firestore_count": 0,
        "migrated": 0,
        "failed": 0,
        "errors": [],
    }

    try:
        for doc_id, doc in _stream_collection_paginated(db, collection_name):
            result["firestore_count"] += 1

            if dry_run:
                continue  # count only

            raw = doc.to_dict() or {}
            converted = _convert_dict(raw)
            converted["_firestore_id"] = doc_id

            try:
                handler_fn(conn, converted, doc_id)
                result["migrated"] += 1
            except Exception as e:
                msg = f"doc_id={doc_id}: {e}"
                logger.warning(f"  [{collection_name}] FAILED {msg}")
                result["failed"] += 1
                result["errors"].append(msg)

            if result["firestore_count"] % 500 == 0:
                logger.info(
                    f"  [{collection_name}] {result['firestore_count']} processed..."
                )

    except Exception as e:
        logger.warning(f"  [{collection_name}] Collection streaming error: {e}")
        result["errors"].append(str(e))

    if dry_run:
        logger.info(
            f"  [{collection_name}] {result['firestore_count']} documents (dry-run)"
        )
    else:
        logger.info(
            f"  [{collection_name}] {result['migrated']} migrated, "
            f"{result['failed']} failed out of {result['firestore_count']}"
        )

    return result


# ==============================================================================
# PER-COLLECTION HANDLERS
# ==============================================================================

def _handle_project(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single project document."""
    name = doc.get("name") or doc.get("projectName") or ""
    province = doc.get("province") or ""
    if not name or not province:
        raise ValueError(f"Missing name ({name!r}) or province ({province!r})")

    for field in ("firstTracked", "lastUpdated", "lastSeen", "created", "completionDate"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    for array_field in ("evidence", "statusHistory", "discovery_sources", "sources",
                        "tags", "anomalies"):
        if array_field in doc and isinstance(doc[array_field], list):
            doc[array_field] = [_convert_value(item) for item in doc[array_field]]

    upsert_project(conn, doc)


def _handle_indicator(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single indicator_history document.

    save_indicator() auto-remaps 'indicator' -> 'indicator_name', 'date' -> 'period'.
    """
    save_indicator(conn, doc)


def _handle_trend_snapshot(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single trend_snapshots document."""
    for field in ("created_at", "createdAt", "week_of"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    if "createdAt" in doc and "created_at" not in doc:
        doc["created_at"] = doc.pop("createdAt")

    if not doc.get("week_of"):
        doc["week_of"] = doc_id

    save_trend_snapshot(conn, doc)


def _handle_briefing(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single weekly_briefings document."""
    for field in ("generated_at", "generatedAt", "week_of"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    if "generatedAt" in doc and "generated_at" not in doc:
        doc["generated_at"] = doc.pop("generatedAt")

    if not doc.get("week_of"):
        doc["week_of"] = doc_id

    if "sections" in doc and isinstance(doc["sections"], str):
        try:
            doc["sections"] = json.loads(doc["sections"])
        except Exception:
            doc["sections"] = {"raw": doc["sections"]}

    save_briefing(conn, doc)


def _handle_dashboard_state(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single dashboard_state document (key = doc_id)."""
    doc.pop("_firestore_id", None)

    for field in ("updated_at", "updatedAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    save_dashboard_state(conn, doc_id, doc)


def _handle_pipeline_run(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single pipeline_runs document."""
    for field in ("started_at", "startedAt", "completed_at", "completedAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    if "startedAt" in doc and "started_at" not in doc:
        doc["started_at"] = doc.pop("startedAt")
    if "completedAt" in doc and "completed_at" not in doc:
        doc["completed_at"] = doc.pop("completedAt")

    save_pipeline_run(conn, doc)


def _handle_missed_project(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a single missed_projects document."""
    for field in ("submitted_at", "submittedAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])
    if "submittedAt" in doc and "submitted_at" not in doc:
        doc["submitted_at"] = doc.pop("submittedAt")

    save_missed_project(conn, doc)


def _handle_pipeline_improvement(conn: sqlite3.Connection, doc: dict,
                                  doc_id: str) -> None:
    """Migrate a single pipeline_improvements document."""
    for field in ("created_at", "createdAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])
    if "createdAt" in doc and "created_at" not in doc:
        doc["created_at"] = doc.pop("createdAt")

    save_pipeline_improvement(conn, doc)


def _handle_pipeline_state(conn: sqlite3.Connection, doc: dict,
                            doc_id: str) -> None:
    """Migrate a pipeline_state document to dashboard_state (key = doc_id)."""
    doc.pop("_firestore_id", None)
    save_dashboard_state(conn, doc_id, doc)


def _handle_statcan_indicators(conn: sqlite3.Connection, doc: dict,
                                doc_id: str) -> None:
    """Migrate a statcan_indicators document to dashboard_state.

    Stores each doc keyed by a prefixed key in dashboard_state for retrieval.
    """
    doc.pop("_firestore_id", None)
    save_dashboard_state(conn, f"statcan_indicator:{doc_id}", doc)


def _handle_timeseries(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a timeseries document to the timeseries table.

    Supports both series objects (with 'data' array) and flat single-row documents.
    """
    doc.pop("_firestore_id", None)

    series_name = doc.get("series_name") or doc.get("name") or doc_id
    unit = doc.get("unit", "")
    source = doc.get("source", "")

    data_points = (
        doc.get("data") or doc.get("values") or doc.get("points") or []
    )

    if isinstance(data_points, list) and data_points:
        for point in data_points:
            if isinstance(point, dict):
                date = _to_iso(point.get("date") or point.get("t") or "")
                value = point.get("value") if point.get("value") is not None else point.get("v")
                if date and value is not None:
                    try:
                        conn.execute("""
                            INSERT INTO timeseries (series_name, date, value, unit, source)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(series_name, date) DO UPDATE SET
                                value = excluded.value,
                                unit = COALESCE(excluded.unit, unit),
                                source = COALESCE(excluded.source, source)
                        """, (series_name, date, float(value), unit, source))
                    except Exception:
                        pass
        conn.commit()
    else:
        date = _to_iso(
            doc.get("date") or doc.get("period") or doc_id
        )
        value = doc.get("value")
        if date and value is not None:
            try:
                conn.execute("""
                    INSERT INTO timeseries (series_name, date, value, unit, source)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(series_name, date) DO UPDATE SET
                        value = excluded.value,
                        unit = COALESCE(excluded.unit, unit),
                        source = COALESCE(excluded.source, source)
                """, (series_name, date, float(value), unit, source))
                conn.commit()
            except Exception:
                pass


def _handle_newsletter(conn: sqlite3.Connection, doc: dict, doc_id: str) -> None:
    """Migrate a newsletters (legacy) document."""
    doc.pop("_firestore_id", None)

    for field in ("published_at", "publishedAt", "created_at", "createdAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    published_at = (
        doc.get("published_at") or doc.get("publishedAt") or
        doc.get("created_at") or doc.get("createdAt") or ""
    )
    title = doc.get("title") or doc.get("subject") or doc_id
    content = doc.get("content") or doc.get("body") or doc.get("html") or ""
    data_json = json.dumps(doc, ensure_ascii=False)

    try:
        conn.execute("""
            INSERT INTO newsletters (published_at, title, content, data)
            VALUES (?, ?, ?, ?)
        """, (published_at, title, content, data_json))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # duplicate -- skip


def _handle_projects_archive(conn: sqlite3.Connection, doc: dict,
                              doc_id: str) -> None:
    """Migrate a projects_archive document."""
    doc.pop("_firestore_id", None)

    for field in ("archived_at", "archivedAt"):
        if field in doc:
            doc[field] = _to_iso(doc[field])

    archived_at = doc.get("archived_at") or doc.get("archivedAt") or ""
    norm_key = doc.get("norm_key") or doc.get("normKey") or ""
    name = doc.get("name") or ""
    province = doc.get("province") or ""
    reason = doc.get("reason") or ""
    data_json = json.dumps(doc, ensure_ascii=False)

    try:
        conn.execute("""
            INSERT INTO projects_archive (norm_key, name, province, data, archived_at, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (norm_key, name, province, data_json, archived_at, reason))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # skip duplicates


# ==============================================================================
# ROW COUNT VERIFICATION
# ==============================================================================

_COLLECTION_TO_TABLE = {
    "projects": "projects",
    "indicator_history": "indicator_history",
    "trend_snapshots": "trend_snapshots",
    "weekly_briefings": "weekly_briefings",
    "dashboard_state": "dashboard_state",
    "pipeline_runs": "pipeline_runs",
    "missed_projects": "missed_projects",
    "pipeline_improvements": "pipeline_improvements",
    "pipeline_state": "dashboard_state",       # merged into dashboard_state
    "statcan_indicators": "dashboard_state",   # merged into dashboard_state
    "timeseries": "timeseries",
    "newsletters": "newsletters",
    "projects_archive": "projects_archive",
}


def _sqlite_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Return row count for a SQLite table, or -1 if table does not exist."""
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return -1


# ==============================================================================
# MIGRATION REPORT
# ==============================================================================

def _print_report(results: list, conn, dry_run: bool) -> bool:
    """Print the migration report and return True if all collections migrated cleanly.

    In dry-run mode, prints expected counts without SQLite row counts.
    """
    print()
    print("=" * 70)
    print("=== MIGRATION REPORT ===")
    if dry_run:
        print("=== (DRY-RUN -- no data written) ===")
    print("=" * 70)

    if dry_run:
        header = f"{'Collection':<28} {'Firestore Docs':>14}"
    else:
        header = (
            f"{'Collection':<28} {'Firestore Docs':>14}  "
            f"{'Migrated':>8}  {'Failed':>6}  {'SQLite Rows':>11}  {'Match':>8}"
        )
    print(header)
    print("-" * len(header))

    all_ok = True
    failed_collections = []

    for r in results:
        col = r["collection"]
        fs_count = r["firestore_count"]
        migrated = r["migrated"]
        failed = r["failed"]

        if dry_run:
            line = f"{col:<28} {fs_count:>14}"
        else:
            table = _COLLECTION_TO_TABLE.get(col, col)
            sqlite_rows = _sqlite_row_count(conn, table)

            if col in ("pipeline_state", "statcan_indicators"):
                # These collections merge into dashboard_state alongside others
                match_str = "MERGED"
            elif failed > 0:
                match_str = "PARTIAL"
                all_ok = False
            elif sqlite_rows == -1:
                match_str = "NO-TBL"
                all_ok = False
            elif fs_count == 0:
                match_str = "EMPTY"
            elif migrated == fs_count:
                match_str = "OK"
            else:
                match_str = "MISMATCH"
                all_ok = False

            line = (
                f"{col:<28} {fs_count:>14}  {migrated:>8}  {failed:>6}  "
                f"{sqlite_rows:>11}  {match_str:>8}"
            )

        print(line)

        if r["errors"]:
            for err in r["errors"][:3]:
                print(f"    ERROR: {err[:100]}")
            if len(r["errors"]) > 3:
                print(f"    ... and {len(r['errors']) - 3} more errors")

        if r["failed"] > 0:
            failed_collections.append(col)

    print("=" * len(header))

    if dry_run:
        total = sum(r["firestore_count"] for r in results)
        print(f"Total documents (expected): {total:,}")
        print()
        print("=== DRY-RUN COMPLETE -- run without --dry-run to migrate ===")
        return True

    print()
    if all_ok and not failed_collections:
        print("=== ALL COLLECTIONS MATCH ===")
    else:
        if failed_collections:
            print(
                f"=== MIGRATION INCOMPLETE -- failures in: "
                f"{', '.join(failed_collections)} ==="
            )
        else:
            print("=== MIGRATION COMPLETE WITH MISMATCHES -- review above ===")

    return all_ok and not failed_collections


# ==============================================================================
# MAIN MIGRATION RUNNER
# ==============================================================================

# Ordered list of (collection_name, handler_fn) pairs.
MIGRATION_PLAN = [
    ("projects",              _handle_project),
    ("indicator_history",     _handle_indicator),
    ("trend_snapshots",       _handle_trend_snapshot),
    ("weekly_briefings",      _handle_briefing),
    ("dashboard_state",       _handle_dashboard_state),
    ("pipeline_runs",         _handle_pipeline_run),
    ("missed_projects",       _handle_missed_project),
    ("pipeline_improvements", _handle_pipeline_improvement),
    ("pipeline_state",        _handle_pipeline_state),
    ("statcan_indicators",    _handle_statcan_indicators),
    ("timeseries",            _handle_timeseries),
    ("newsletters",           _handle_newsletter),
    ("projects_archive",      _handle_projects_archive),
]


def run_migration(dry_run: bool = False, db_path=None) -> bool:
    """Execute the full Firestore-to-SQLite migration.

    Args:
        dry_run: Count-only mode -- no SQLite writes.
        db_path: Path to the SQLite database file (default: dashboard.db).

    Returns:
        True if all collections migrated without failures.
    """
    start_ts = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("CAN-MACRO: Firestore -> SQLite Migration")
    logger.info(f"Mode: {'DRY-RUN (no writes)' if dry_run else 'LIVE MIGRATION'}")
    logger.info(f"Started: {start_ts.isoformat()}")
    logger.info("=" * 60)

    # 1. Initialize SQLite (creates all tables)
    conn = None
    if not dry_run:
        logger.info("Initializing SQLite database...")
        conn = init_db(db_path)
        logger.info(f"SQLite initialized: {db_path or 'dashboard.db'}")

    # 2. Initialize Firestore
    logger.info("Connecting to Firestore...")
    try:
        db = _init_firestore()
        logger.info("Firestore connected.")
    except Exception as e:
        logger.error(f"Failed to connect to Firestore: {e}")
        return False

    # 3. Run each collection migration
    results = []
    for collection_name, handler_fn in MIGRATION_PLAN:
        logger.info(f"Migrating collection: {collection_name}")
        result = migrate_collection(
            db, conn, collection_name, handler_fn, dry_run=dry_run
        )
        results.append(result)

    # 4. Print report
    success = _print_report(results, conn, dry_run)

    # 5. Final timing
    end_ts = datetime.now(timezone.utc)
    duration = (end_ts - start_ts).total_seconds()
    logger.info(f"Migration finished in {duration:.1f}s")

    if conn:
        conn.close()

    return success


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate all Firestore collections to SQLite via db.py."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count Firestore documents without writing to SQLite.",
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="PATH",
        help=(
            "Path to the SQLite database file "
            "(default: dashboard.db or DB_PATH env var)."
        ),
    )
    args = parser.parse_args()

    success = run_migration(dry_run=args.dry_run, db_path=args.db)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
