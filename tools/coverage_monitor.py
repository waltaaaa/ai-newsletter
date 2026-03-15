"""
coverage_monitor.py -- Coverage growth monitoring for the project database.

Three functions:
1. coverage_audit() — compare DB projects vs government backfill sources
2. staleness_watchlist() — flag projects not rediscovered in 60+ days
3. gap_analysis() — identify underrepresented sectors/provinces for query tuning

Usage:
    python tools/coverage_monitor.py                # Run all three reports
    python tools/coverage_monitor.py --audit        # Coverage audit only
    python tools/coverage_monitor.py --stale        # Staleness report only
    python tools/coverage_monitor.py --gaps         # Gap analysis only
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))


def coverage_audit(conn):
    """Compare DB projects against government backfill baseline.

    Shows:
    - How many backfill projects are still in the DB
    - How many new projects the pipeline has discovered beyond backfill
    - Province/sector coverage rates
    """
    from db import get_projects

    all_projects = get_projects(conn, limit=50000)
    total = len(all_projects)

    # Count by discovery source
    by_source = Counter()
    for p in all_projects:
        ds = p.get("discovery_source", "") or "unknown"
        # Normalize backfill sources
        if "backfill" in ds:
            by_source["government_backfill"] += 1
        elif "call4" in ds:
            by_source["pipeline_call4"] += 1
        elif ds:
            by_source[ds] += 1
        else:
            by_source["unknown"] += 1

    # Count by province
    by_province = Counter(p.get("province", "??") for p in all_projects)

    # Count by sector
    by_sector = Counter(p.get("sector", "unknown") for p in all_projects)

    # Count by status
    by_status = Counter(p.get("status", "Unknown") for p in all_projects)

    # Value coverage
    with_value = sum(1 for p in all_projects if p.get("parsed_value"))
    total_value = sum(p.get("parsed_value", 0) or 0 for p in all_projects)

    print(f"\n{'='*60}")
    print(f"  COVERAGE AUDIT — {date.today().isoformat()}")
    print(f"{'='*60}")
    print(f"\n  Total projects: {total}")
    print(f"  With dollar values: {with_value} ({100*with_value/max(total,1):.0f}%)")
    print(f"  Total value: ${total_value/1e9:.1f}B")

    print(f"\n  By discovery source:")
    for src, cnt in by_source.most_common():
        print(f"    {src}: {cnt}")

    print(f"\n  By province:")
    for prov in sorted(by_province.keys()):
        print(f"    {prov}: {by_province[prov]}")

    print(f"\n  By sector (top 10):")
    for sector, cnt in by_sector.most_common(10):
        print(f"    {sector}: {cnt}")

    print(f"\n  By status:")
    for status, cnt in by_status.most_common():
        print(f"    {status}: {cnt}")

    return {
        "total": total,
        "by_source": dict(by_source),
        "by_province": dict(by_province),
        "by_sector": dict(by_sector),
        "with_value": with_value,
    }


def staleness_watchlist(conn, stale_days=60):
    """Flag projects not rediscovered in 60+ days.

    A project is considered stale if lastSeen is older than stale_days.
    Returns list of stale projects grouped by severity.
    """
    today = date.today()
    cutoff = (today - timedelta(days=stale_days)).isoformat()
    cutoff_critical = (today - timedelta(days=120)).isoformat()

    stale = conn.execute("""
        SELECT name, province, status, lastSeen, confidence, parsed_value
        FROM projects
        WHERE lastSeen < ? AND status NOT IN ('Complete', 'Cancelled')
        ORDER BY parsed_value DESC NULLS LAST
    """, (cutoff,)).fetchall()

    critical = [r for r in stale if (r["lastSeen"] or "") < cutoff_critical]
    warning = [r for r in stale if r not in critical]

    print(f"\n{'='*60}")
    print(f"  STALENESS WATCHLIST — {today.isoformat()}")
    print(f"{'='*60}")
    print(f"\n  Stale (>{stale_days}d): {len(stale)} projects")
    print(f"  Critical (>120d): {len(critical)} projects")
    print(f"  Warning ({stale_days}-120d): {len(warning)} projects")

    if critical:
        print(f"\n  CRITICAL (>120 days, may need removal):")
        for r in critical[:15]:
            val = f"${r['parsed_value']/1e6:.0f}M" if r["parsed_value"] else "N/A"
            print(f"    {r['province']} | {r['name'][:50]} | {r['status']} | last: {r['lastSeen']} | {val}")

    if warning:
        print(f"\n  WARNING ({stale_days}-120 days):")
        for r in warning[:15]:
            val = f"${r['parsed_value']/1e6:.0f}M" if r["parsed_value"] else "N/A"
            print(f"    {r['province']} | {r['name'][:50]} | {r['status']} | last: {r['lastSeen']} | {val}")

    return {"stale": len(stale), "critical": len(critical), "warning": len(warning)}


def gap_analysis(conn):
    """Identify underrepresented sectors/provinces for query tuning.

    Compares actual DB coverage against expected distribution.
    Suggests sectors/provinces that need more discovery queries.
    """
    from pipeline_config import PROVINCE_GDP_THRESHOLDS
    from project_schema import SECTORS

    all_projects = conn.execute(
        "SELECT province, sector, COUNT(*) as cnt FROM projects GROUP BY province, sector"
    ).fetchall()

    # Build coverage matrix
    prov_sector = {}
    prov_totals = Counter()
    sector_totals = Counter()
    for row in all_projects:
        key = (row["province"], row["sector"])
        prov_sector[key] = row["cnt"]
        prov_totals[row["province"]] += row["cnt"]
        sector_totals[row["sector"]] += row["cnt"]

    total = sum(prov_totals.values())
    all_sectors = set(SECTORS.keys())
    all_provinces = set(PROVINCE_GDP_THRESHOLDS.keys()) - {"CA"}

    print(f"\n{'='*60}")
    print(f"  GAP ANALYSIS — {date.today().isoformat()}")
    print(f"{'='*60}")

    # Provinces with < 2% of total projects (underrepresented)
    print(f"\n  Underrepresented provinces (<2% of {total} projects):")
    gaps_province = []
    for prov in sorted(all_provinces):
        cnt = prov_totals.get(prov, 0)
        pct = 100 * cnt / max(total, 1)
        if pct < 2.0:
            gaps_province.append(prov)
            print(f"    {prov}: {cnt} projects ({pct:.1f}%)")

    # Sectors with 0 projects in any province
    print(f"\n  Missing sector coverage (0 projects in province):")
    gaps_sector = []
    for prov in sorted(all_provinces):
        missing = [s for s in all_sectors if prov_sector.get((prov, s), 0) == 0]
        if missing and prov_totals.get(prov, 0) > 0:
            # Only flag if the province has SOME projects (not zero across the board)
            gaps_sector.extend([(prov, s) for s in missing])
            if len(missing) <= 5:
                print(f"    {prov}: missing {', '.join(missing)}")

    # Sectors globally underrepresented
    print(f"\n  Globally underrepresented sectors (<1% of total):")
    for sector in sorted(all_sectors):
        cnt = sector_totals.get(sector, 0)
        pct = 100 * cnt / max(total, 1)
        if pct < 1.0:
            print(f"    {sector}: {cnt} projects ({pct:.1f}%)")

    # Suggested new query topics (additive only)
    suggestions = []
    for prov in gaps_province:
        suggestions.append(f"Add more discovery queries for {prov} across all sectors")
    for prov, sector in gaps_sector[:10]:
        suggestions.append(f"Add {sector} queries for {prov}")

    if suggestions:
        print(f"\n  Suggested query additions (additive only):")
        for s in suggestions[:15]:
            print(f"    + {s}")

    return {
        "underrepresented_provinces": gaps_province,
        "missing_sector_coverage": len(gaps_sector),
        "suggestions": suggestions[:15],
    }


def main():
    parser = argparse.ArgumentParser(description="Coverage monitoring")
    parser.add_argument("--audit", action="store_true", help="Run coverage audit only")
    parser.add_argument("--stale", action="store_true", help="Run staleness report only")
    parser.add_argument("--gaps", action="store_true", help="Run gap analysis only")
    args = parser.parse_args()

    import db
    conn = db.init_db()
    conn.row_factory = __import__("sqlite3").Row

    run_all = not (args.audit or args.stale or args.gaps)

    if run_all or args.audit:
        coverage_audit(conn)
    if run_all or args.stale:
        staleness_watchlist(conn)
    if run_all or args.gaps:
        gap_analysis(conn)

    conn.close()


if __name__ == "__main__":
    main()
