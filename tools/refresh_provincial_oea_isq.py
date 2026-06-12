"""refresh_provincial_oea_isq.py — Refresh Ontario OEA + Quebec ISQ series.

Runs the Ontario Economic Accounts and Quebec ISQ extractors from
backfill_indicators.py and merges the results into dashboard.db. This is the
reproducible, CI-runnable form of the issue #1 provincial-data fix: the
ON_on_* / QC_qc_* timeseries are sourced from provincial Excel workbooks
(data.ontario.ca / statistique.quebec.ca), not from the regular pipeline, so
without this step they go stale. Safe to run repeatedly — save_indicator
merges by (indicator, province, date).

Only OEA + ISQ are run here (the other backfill_indicators sources — BoC,
StatCan, Yahoo, FRED, ECB — are owned by the regular pipeline / commodity
refresh and are intentionally not duplicated).

Run: python tools/refresh_provincial_oea_isq.py
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db
from tools.backfill_indicators import backfill_oea, backfill_isq

# D8: monthly ISQ series older than this many days mean the scrape is dark or
# the workbook layout drifted — the run must be LOUD about it (non-zero exit),
# not "0 rows merged, exit 0" forever.
_ISQ_MONTHLY_MAX_AGE_DAYS = 100

# TODO(D8 durable fix — needs live network validation before switching): the
# QC_qc_* monthly series scraped from the ISQ Excel workbook have durable WDS
# replacements that the pipeline already knows how to fetch:
#   - qc_bldg_permits_res / qc_bldg_permits_nonres → StatCan 34-10-0292
#     (building permits by province; QC coordinates, same active cube used
#     for the national series in statcan_extended.META_RESOLVED_GROUPS)
#   - qc_intl_exports / qc_intl_imports → StatCan 12-10-0163 (merchandise
#     trade by commodity/province, BoP, SA — successor to dead 12-10-0129)
# Rewiring was deliberately NOT done in the 2026-06-12 audit pass because the
# QC coordinates must be resolved and validated against live WDS metadata.


def _isq_monthly_staleness(conn) -> tuple[str | None, int | None]:
    """Return (latest_period, age_days) of the freshest monthly ISQ row."""
    row = conn.execute("""
        SELECT MAX(period) FROM indicator_history
        WHERE province = 'QC' AND frequency = 'monthly'
          AND source = 'Institut de la statistique du Québec'
    """).fetchone()
    latest = row[0] if row else None
    if not latest:
        return None, None
    try:
        age = (date.today() - datetime.strptime(latest[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return latest, None
    return latest, age


def main() -> int:
    conn = init_db()
    exit_code = 0
    try:
        oea = backfill_oea(conn, years=5)
        isq = backfill_isq(conn, years=5)
        print(f"[provincial-refresh] OEA={oea} ISQ={isq} observations merged")

        # OEA flakiness stays a warning only (transient data.ontario.ca
        # outages leave prior values in place; validator WARNs on staleness).
        if oea == 0:
            print("[provincial-refresh][WARN] OEA wrote ZERO rows — "
                  "data.ontario.ca download or workbook layout may have changed")

        # D8: ISQ failures must be loud. Exit non-zero when the run wrote
        # nothing, or when the freshest monthly QC point is >100 days old —
        # both mean the QC_qc_* series are going silently stale.
        if isq == 0:
            print("[provincial-refresh][ERROR] ISQ wrote ZERO rows — "
                  "statistique.quebec.ca scrape failed or the 'indicat' "
                  "workbook layout changed. QC series are going stale.",
                  file=sys.stderr)
            exit_code = 1
        else:
            latest, age = _isq_monthly_staleness(conn)
            if latest is None:
                print("[provincial-refresh][ERROR] ISQ run wrote rows but no "
                      "monthly QC observations exist in indicator_history — "
                      "monthly row indices may have drifted.", file=sys.stderr)
                exit_code = 1
            elif age is not None and age > _ISQ_MONTHLY_MAX_AGE_DAYS:
                print(f"[provincial-refresh][ERROR] Freshest monthly ISQ "
                      f"observation is {latest} ({age} days old > "
                      f"{_ISQ_MONTHLY_MAX_AGE_DAYS}) — the ISQ workbook is "
                      f"lagging or the scrape is reading a stale block.",
                      file=sys.stderr)
                exit_code = 1
            else:
                print(f"[provincial-refresh] ISQ monthly freshness OK "
                      f"(latest {latest}, {age} days old)")
    finally:
        conn.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
