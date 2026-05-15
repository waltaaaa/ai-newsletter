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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db
from tools.backfill_indicators import backfill_oea, backfill_isq


def main() -> int:
    conn = init_db()
    try:
        oea = backfill_oea(conn, years=5)
        isq = backfill_isq(conn, years=5)
    finally:
        conn.close()
    print(f"[provincial-refresh] OEA={oea} ISQ={isq} observations merged")
    # Never hard-fail the pipeline on provincial source flakiness: a transient
    # Ontario/Quebec outage just leaves the prior values in place (validator
    # treats provincial staleness as WARN, not FAIL).
    return 0


if __name__ == "__main__":
    sys.exit(main())
