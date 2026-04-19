#!/usr/bin/env python3
"""
refresh_timeseries_commodity.py — surgical refresh of commodity/equity-proxy
and rate timeseries directly into docs/data/timeseries.json.

Free data sources only: yfinance + Bank of Canada Valet. No paid APIs.

Usage:
    python tools/refresh_timeseries_commodity.py
    python tools/refresh_timeseries_commodity.py --dry-run
    python tools/refresh_timeseries_commodity.py --series iron_ore potash_nutrien

Why this exists:
    - timeseries.json is the ground truth for the Markets tab + insightCharts
    - Several series (commodity proxies, crypto, prime_rate) are backed by
      external APIs rather than indicator_history in the DB. When the
      weekly pipeline doesn't run, these go stale. This script is the
      durable additive refresh path so future runs keep them live.
    - Hand-patched content in timeseries.json is preserved — only the
      keys listed here are updated in-place.

Series map:
    iron_ore          <- VALE (yfinance) — iron-ore equity proxy
    potash_nutrien    <- NTR.TO (yfinance)
    lumber            <- LBR=F (yfinance)
    wti_oil, wti_crude <- CL=F (yfinance)
    prime_rate        <- BoC Valet V80691311
    bitcoin           <- BTC-USD (yfinance)
    ethereum          <- ETH-USD (yfinance)

Each run writes >= ~250 daily points (~13 months) to give enough history
for chart smoothing + min_points checks.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

TIMESERIES_PATH = os.path.join("docs", "data", "timeseries.json")

# (series_key, yfinance_ticker, period, description)
YF_SERIES = [
    ("iron_ore", "VALE", "13mo", "VALE (NYSE) equity proxy — iron ore miner"),
    ("potash_nutrien", "NTR.TO", "13mo", "Nutrien Ltd (TSX) — potash producer"),
    ("lumber", "LBR=F", "13mo", "Random Length Lumber futures"),
    ("wti_oil", "CL=F", "13mo", "WTI Crude Oil futures"),
    ("wti_crude", "CL=F", "13mo", "WTI Crude Oil futures (alias)"),
    ("bitcoin", "BTC-USD", "13mo", "Bitcoin USD spot"),
    ("ethereum", "ETH-USD", "13mo", "Ethereum USD spot"),
]

# BoC Valet observations — (series_key, valet_series_id, recent_N)
BOC_SERIES = [
    ("prime_rate", "V80691311", 300),  # Weekly Chartered Bank Prime Rate
]


def _load_ts():
    if not os.path.exists(TIMESERIES_PATH):
        return {}
    with open(TIMESERIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_ts(ts):
    with open(TIMESERIES_PATH, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2)


def _fetch_yf(ticker: str, period: str):
    import yfinance as yf

    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=False)
    if df is None or len(df) == 0:
        return []
    points = []
    for idx, row in df.iterrows():
        try:
            date_str = idx.date().isoformat()
        except Exception:
            date_str = str(idx)[:10]
        close = row.get("Close")
        if close is None or (isinstance(close, float) and (close != close)):
            continue
        try:
            points.append({"date": date_str, "value": float(close)})
        except (TypeError, ValueError):
            continue
    # Ensure chronological order (yfinance already returns ascending)
    points.sort(key=lambda p: p["date"])
    return points


def _fetch_boc(series_id: str, recent_n: int):
    url = (
        f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?"
        f"recent={recent_n}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.loads(r.read())
    obs = payload.get("observations", [])
    points = []
    for o in obs:
        d = o.get("d")
        if not d:
            continue
        sv = o.get(series_id, {}) or {}
        raw = sv.get("v") if isinstance(sv, dict) else None
        if raw in (None, ""):
            continue
        try:
            points.append({"date": d, "value": float(raw)})
        except (TypeError, ValueError):
            continue
    # BoC returns desc; sort asc
    points.sort(key=lambda p: p["date"])
    return points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Report changes without writing.")
    ap.add_argument("--series", nargs="*", default=None,
                    help="Optional subset of series_keys to refresh.")
    args = ap.parse_args()

    ts = _load_ts()
    if not ts:
        print(f"[refresh_timeseries_commodity] Warning: {TIMESERIES_PATH} "
              "did not load or is empty.")

    subset = set(args.series) if args.series else None

    refreshed = []
    skipped = []
    failed = []

    # yfinance series
    for key, ticker, period, label in YF_SERIES:
        if subset is not None and key not in subset:
            continue
        try:
            pts = _fetch_yf(ticker, period)
        except Exception as e:
            failed.append((key, f"yfinance {ticker}: {e}"))
            continue
        if not pts:
            failed.append((key, f"yfinance {ticker}: no rows"))
            continue
        prev_pts = len(ts.get(key, []) or [])
        ts[key] = pts
        refreshed.append((key, ticker, prev_pts, len(pts), pts[-1]["date"], label))

    # BoC Valet series
    for key, series_id, recent_n in BOC_SERIES:
        if subset is not None and key not in subset:
            continue
        try:
            pts = _fetch_boc(series_id, recent_n)
        except Exception as e:
            failed.append((key, f"BoC {series_id}: {e}"))
            continue
        if not pts:
            failed.append((key, f"BoC {series_id}: no rows"))
            continue
        prev_pts = len(ts.get(key, []) or [])
        ts[key] = pts
        refreshed.append((key, f"BoC:{series_id}", prev_pts, len(pts),
                          pts[-1]["date"], "Weekly Chartered Bank Prime Rate"))

    # Report
    print("[refresh_timeseries_commodity] Results:")
    for (k, src, prev, now, last, lbl) in refreshed:
        print(f"  ~ {k:20s} <- {src:14s}  prev={prev:4d} now={now:4d} "
              f"last={last}  ({lbl})")
    for k, reason in failed:
        print(f"  ! {k:20s} FAILED: {reason}")
    for k in skipped:
        print(f"  . {k:20s} skipped")

    if args.dry_run:
        print("  [dry-run] No files written.")
        return 0

    if refreshed:
        _write_ts(ts)
        print(f"  Wrote {TIMESERIES_PATH} (series updated: {len(refreshed)}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
