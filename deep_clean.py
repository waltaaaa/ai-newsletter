"""
deep_clean.py — Comprehensive database cleanup.

Removes:
  1. Non-capital entries (financing instruments, strategies, tax policies)
  2. Individual station entries with parent transit projects (sub-components, not projects)
  3. Transit construction sub-sites (portals, shafts, bridge areas)

Fixes:
  4. Broken UTF-8 value fields ("—" garbage -> "Not disclosed")
  5. Single-word descriptions from government_backfill ("Roadwork." etc. -> "")

Run: python deep_clean.py [--dry-run]
"""

import sqlite3
import json
import re
import sys
from datetime import date

DB_PATH = "dashboard.db"


def archive_and_delete(conn, rowid, reason, dry_run):
    """Archive a project and delete it from the main table."""
    r = conn.execute("SELECT * FROM projects WHERE rowid = ?", (rowid,)).fetchone()
    if not r:
        return False
    rd = dict(r)
    name = rd.get("name", "?")[:55]

    if dry_run:
        print(f"  DRY-RUN REMOVE #{rowid}: {name} — {reason}")
        return True

    data = json.dumps({k: rd[k] for k in rd if k != "rowid" and rd[k] is not None})
    conn.execute(
        "INSERT INTO projects_archive (original_id, norm_key, name, province, data, archived_at, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rowid, rd.get("norm_key", ""), rd.get("name", ""), rd.get("province", ""),
         data, date.today().isoformat(), f"deep_clean: {reason}"),
    )
    conn.execute("DELETE FROM projects WHERE rowid = ?", (rowid,))
    print(f"  REMOVED #{rowid}: {name} — {reason}")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    before = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"Projects before: {before}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    removed = 0
    fixed_values = 0
    fixed_desc = 0

    # ══════════════════════════════════════════════════════════════════
    # 1. REMOVE NON-CAPITAL ENTRIES
    # ══════════════════════════════════════════════════════════════════
    print("=== 1. NON-CAPITAL ENTRIES ===")

    non_capital = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '%Equity Purchase%'
            OR name LIKE '%Loan Guarantee Program%'
            OR name LIKE '%Economic Strategy%'
            OR name LIKE '%Licence Plate Tax%'
    """).fetchall()

    for r in non_capital:
        if archive_and_delete(conn, r["rowid"], "non-capital entry (financing/strategy/tax policy)", dry_run):
            removed += 1

    # ══════════════════════════════════════════════════════════════════
    # 2. REMOVE INDIVIDUAL STATION ENTRIES WITH PARENT PROJECTS
    # ══════════════════════════════════════════════════════════════════
    print("\n=== 2. INDIVIDUAL TRANSIT STATION ENTRIES ===")

    # Lines with confirmed parent projects that capture the full scope
    STATION_SUFFIXES = [
        ("ECLRT", "#35259 Eglinton Crosstown LRT $12.6B"),
        ("HML", "#35261 Hazel McCallion LRT $5.7B"),
        ("FWLRT", "#35264 Finch West LRT $3.6B"),
        ("Eglinton Crosstown West Extension", "#35266 ECWE $3.2B"),
        ("Eglinton Crosstown West Exteion", "#35266 ECWE (typo variant)"),  # typo in data
    ]

    for suffix, parent_info in STATION_SUFFIXES:
        stations = conn.execute(
            "SELECT rowid, name FROM projects WHERE name LIKE ?",
            (f"% Station - {suffix}%",),
        ).fetchall()
        if stations:
            print(f"  {suffix}: {len(stations)} stations (parent: {parent_info})")
        for s in stations:
            if archive_and_delete(conn, s["rowid"], f"station sub-component of {parent_info}", dry_run):
                removed += 1

    # Ontario Line stations + sub-components (parent: #35254 Ontario Line $27.4B)
    ontario_line_subs = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            (name LIKE '%Station - Ontario Line%'
             OR name LIKE '%- Ontario Line%')
            AND rowid != 35254 AND rowid != 35285
    """).fetchall()
    if ontario_line_subs:
        print(f"  Ontario Line: {len(ontario_line_subs)} sub-entries (parent: #35254 $27.4B)")
    for s in ontario_line_subs:
        if archive_and_delete(conn, s["rowid"], "sub-component of #35254 Ontario Line $27.4B", dry_run):
            removed += 1

    # O-Train completed stations (Confederation Line is built)
    otrain_complete = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '% - O-Train Line' AND status = 'Complete'
    """).fetchall()
    if otrain_complete:
        print(f"  O-Train (complete): {len(otrain_complete)} completed station entries")
    for s in otrain_complete:
        if archive_and_delete(conn, s["rowid"], "completed O-Train station (Confederation Line built)", dry_run):
            removed += 1

    # O-Train future extension stations — keep one per direction, remove individual stops
    # O-Train Line West: keep concept, remove individual stops
    otrain_west = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '% - O-Train Line West' AND status = 'Proposed'
    """).fetchall()
    if len(otrain_west) > 1:
        print(f"  O-Train West: {len(otrain_west)} proposed stations -> keeping 1")
        # Keep first, archive rest
        for s in otrain_west[1:]:
            if archive_and_delete(conn, s["rowid"], "individual O-Train West station (keeping 1 representative)", dry_run):
                removed += 1

    otrain_east = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '% - O-Train Line East' AND status = 'Proposed'
    """).fetchall()
    if len(otrain_east) > 1:
        print(f"  O-Train East: {len(otrain_east)} proposed stations -> keeping 1")
        for s in otrain_east[1:]:
            if archive_and_delete(conn, s["rowid"], "individual O-Train East station (keeping 1 representative)", dry_run):
                removed += 1

    # O-Train proposed general stations
    otrain_proposed = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '% - O-Train Line' AND status = 'Proposed'
    """).fetchall()
    if len(otrain_proposed) > 1:
        print(f"  O-Train (proposed general): {len(otrain_proposed)} -> keeping 1")
        for s in otrain_proposed[1:]:
            if archive_and_delete(conn, s["rowid"], "individual O-Train station (keeping 1 representative)", dry_run):
                removed += 1

    # SSE (Scarborough Subway Extension) sub-entries
    sse_subs = conn.execute("""
        SELECT rowid, name FROM projects WHERE name LIKE '% - SSE%'
    """).fetchall()
    # Check if parent Scarborough Subway exists
    scarborough_parent = conn.execute(
        "SELECT rowid, name FROM projects WHERE name LIKE '%Scarborough Subway%' AND name NOT LIKE '%Station%'"
    ).fetchall()
    if sse_subs and scarborough_parent:
        print(f"  SSE: {len(sse_subs)} sub-entries (parent: #{scarborough_parent[0]['rowid']})")
        for s in sse_subs:
            if archive_and_delete(conn, s["rowid"], f"sub-component of Scarborough Subway Extension", dry_run):
                removed += 1
    elif sse_subs and not scarborough_parent:
        # No parent — keep the station entries but note it
        print(f"  SSE: {len(sse_subs)} entries, no parent found — keeping")

    # ══════════════════════════════════════════════════════════════════
    # 3. REMOVE TRANSIT CONSTRUCTION SUB-SITES
    # ══════════════════════════════════════════════════════════════════
    print("\n=== 3. TRANSIT CONSTRUCTION SUB-SITES ===")

    # Patterns: "Launch shaft", "Tunnel", "Portal", "Bridge area", "Extraction shaft"
    sub_site_patterns = [
        "launch shaft%", "tunnel%site%", "portal%site%", "%extraction shaft%",
        "%bridge area%", "Advanced Tunnel%Portal%", "Mount Dennis Shaft%",
        "%Operations, Maintenance, Storage Facility - %",
    ]
    for pat in sub_site_patterns:
        subs = conn.execute(
            "SELECT rowid, name FROM projects WHERE name LIKE ?", (pat,)
        ).fetchall()
        for s in subs:
            if archive_and_delete(conn, s["rowid"], "construction sub-site (shaft/portal/tunnel), not independent project", dry_run):
                removed += 1

    # Durham BRT individual road segments
    brt_segments = conn.execute("""
        SELECT rowid, name FROM projects WHERE name LIKE '%Segment (Durham BRT)%'
    """).fetchall()
    if brt_segments:
        print(f"  Durham BRT: {len(brt_segments)} individual road segments")
        for s in brt_segments:
            if archive_and_delete(conn, s["rowid"], "individual BRT road segment, not independent project", dry_run):
                removed += 1

    # GO Station parking expansions (completed, sub-component of Metrolinx GO expansion)
    go_parking = conn.execute("""
        SELECT rowid, name FROM projects WHERE
            name LIKE '%GO Station Parking Expansion%' AND status = 'Complete'
    """).fetchall()
    if go_parking:
        print(f"  GO Parking: {len(go_parking)} completed parking expansions")
        for s in go_parking:
            if archive_and_delete(conn, s["rowid"], "completed GO parking expansion (sub-component of Metrolinx)", dry_run):
                removed += 1

    # Barrie Double Track contracts (sub-components)
    barrie = conn.execute("""
        SELECT rowid, name FROM projects WHERE name LIKE 'Barrie Double Track - Contract%'
    """).fetchall()
    if len(barrie) > 1:
        print(f"  Barrie Double Track: {len(barrie)} contract entries -> keeping 1")
        for s in barrie[1:]:
            if archive_and_delete(conn, s["rowid"], "individual Barrie track contract (keeping 1)", dry_run):
                removed += 1

    # ICIP funding duplicates (same project listed as both main + ICIP funding portion)
    icip = conn.execute("""
        SELECT rowid, name FROM projects WHERE name LIKE '%(ICIP%' OR name LIKE '%(Investing in Canada%'
    """).fetchall()
    for r in icip:
        # Check if a parent project exists without the ICIP suffix
        base_name = re.sub(r'\s*\((?:ICIP|Investing in Canada).*?\)', '', r["name"]).strip()
        parent = conn.execute(
            "SELECT rowid, name FROM projects WHERE name LIKE ? AND rowid != ?",
            (f"{base_name[:40]}%", r["rowid"]),
        ).fetchone()
        if parent:
            if archive_and_delete(conn, r["rowid"], f"ICIP funding portion of #{parent['rowid']}", dry_run):
                removed += 1

    # ══════════════════════════════════════════════════════════════════
    # 4. FIX BROKEN VALUE FIELDS
    # ══════════════════════════════════════════════════════════════════
    print("\n=== 4. BROKEN VALUE FIELDS ===")
    if not dry_run:
        cursor = conn.execute("""
            UPDATE projects SET value = 'Not disclosed', parsed_value = NULL
            WHERE length(value) <= 2 AND value != '' AND value NOT LIKE '$%' AND value NOT LIKE '%M' AND value NOT LIKE '%B'
        """)
        fixed_values = cursor.rowcount
        print(f"  Fixed {fixed_values} broken value fields -> 'Not disclosed'")
    else:
        count = conn.execute("""
            SELECT COUNT(*) FROM projects
            WHERE length(value) <= 2 AND value != '' AND value NOT LIKE '$%' AND value NOT LIKE '%M' AND value NOT LIKE '%B'
        """).fetchone()[0]
        print(f"  DRY-RUN: Would fix {count} broken value fields")
        fixed_values = count

    # ══════════════════════════════════════════════════════════════════
    # 5. FIX SINGLE-WORD DESCRIPTIONS
    # ══════════════════════════════════════════════════════════════════
    print("\n=== 5. SINGLE-WORD DESCRIPTIONS ===")
    if not dry_run:
        cursor = conn.execute("""
            UPDATE projects SET description = ''
            WHERE length(description) > 0 AND description NOT LIKE '% %'
        """)
        fixed_desc = cursor.rowcount
        print(f"  Cleared {fixed_desc} single-word descriptions (sector labels from government_backfill)")
    else:
        count = conn.execute("""
            SELECT COUNT(*) FROM projects WHERE length(description) > 0 AND description NOT LIKE '% %'
        """).fetchone()[0]
        print(f"  DRY-RUN: Would clear {count} single-word descriptions")
        fixed_desc = count

    # ══════════════════════════════════════════════════════════════════
    # COMMIT AND REPORT
    # ══════════════════════════════════════════════════════════════════
    if not dry_run:
        conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    print(f"\n{'='*60}")
    print(f"DEEP CLEAN RESULTS")
    print(f"{'='*60}")
    print(f"Projects before: {before}")
    print(f"Projects after:  {after}")
    print(f"Removed: {removed}")
    print(f"Value fields fixed: {fixed_values}")
    print(f"Descriptions cleared: {fixed_desc}")

    conn.close()


if __name__ == "__main__":
    main()
