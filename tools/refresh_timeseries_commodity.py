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
    sp500             <- ^GSPC (yfinance) — S&P 500 index close
    eurusd            <- EURUSD=X (yfinance) — EUR/USD spot
    ftse100           <- ^FTSE (yfinance) — FTSE 100 index close
    usdcny            <- CNY=X (yfinance) — USD/CNY spot

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
    # National-tab global charts (GLOBAL_CHART_CFG in docs/js/app.js)
    ("sp500", "^GSPC", "14mo", "S&P 500 index close"),
    ("eurusd", "EURUSD=X", "14mo", "EUR/USD spot rate"),
    ("ftse100", "^FTSE", "14mo", "FTSE 100 index close"),
    ("usdcny", "CNY=X", "14mo", "USD/CNY spot rate"),
    ("wti", "CL=F", "13mo", "WTI Crude Oil futures (alias)"),
    # Global indices / FX — previously had no refresher (chronically stale)
    ("djia", "^DJI", "14mo", "Dow Jones Industrial Average"),
    ("nasdaq", "^IXIC", "14mo", "NASDAQ Composite"),
    ("nikkei225", "^N225", "14mo", "Nikkei 225"),
    ("dax", "^GDAXI", "14mo", "DAX 40 (Germany)"),
    ("tsx_composite", "^GSPTSE", "14mo", "S&P/TSX Composite"),
    ("usdjpy", "JPY=X", "14mo", "USD/JPY spot rate"),
    ("cadusd", "CADUSD=X", "14mo", "CAD/USD spot rate"),
    # GBP/USD — red-team 2.9 (2026-06-11): the triad's required pair mapped to
    # fx_gbpusd, which never existed in timeseries.json (weekly N/A or
    # unverifiable web print). Independent yfinance feed closes the gap.
    ("fx_gbpusd", "GBPUSD=X", "14mo", "GBP/USD spot rate"),
    # Commodities — previously stale
    ("brent", "BZ=F", "13mo", "Brent Crude Oil futures"),
    ("natural_gas", "NG=F", "13mo", "Henry Hub Natural Gas futures"),
    ("gold", "GC=F", "13mo", "Gold futures"),
    ("silver", "SI=F", "13mo", "Silver futures"),
    ("platinum", "PL=F", "13mo", "Platinum futures"),
    ("palladium", "PA=F", "13mo", "Palladium futures"),
    ("copper", "HG=F", "13mo", "Copper futures"),
    ("aluminum", "ALI=F", "13mo", "Aluminum futures"),
    ("wheat", "ZW=F", "13mo", "Wheat futures"),
    ("corn", "ZC=F", "13mo", "Corn futures"),
    ("soybeans", "ZS=F", "13mo", "Soybean futures"),
    ("coffee", "KC=F", "13mo", "Coffee futures"),
    ("cocoa", "CC=F", "13mo", "Cocoa futures"),
    ("sugar", "SB=F", "13mo", "Sugar futures"),
    ("cotton", "CT=F", "13mo", "Cotton futures"),
    ("rice", "ZR=F", "13mo", "Rough Rice futures"),
    ("soybean_oil", "ZL=F", "13mo", "Soybean Oil futures"),
    ("soybean_meal", "ZM=F", "13mo", "Soybean Meal futures"),
    # Dry-bulk shipping proxy (was single-point; no FRED BDI series exists)
    ("dry_bulk_shipping", "BDRY", "13mo", "Breakwave Dry Bulk Shipping ETF"),
    # Agriculture livestock + uranium proxy — referenced by the industry
    # Key Indicators tables (IND_KEY_INDICATORS in docs/js/app.js) but never
    # fetched until 2026-06-11, so their rows silently dropped.
    ("live_cattle", "LE=F", "13mo", "Live Cattle futures (USD/lb)"),
    ("lean_hogs", "HE=F", "13mo", "Lean Hogs futures (USD/lb)"),
    ("cameco_uranium", "CCJ", "13mo", "Cameco Corp (NYSE) — uranium proxy"),
]

# CME livestock futures quote in US cents/lb; the frontend labels these rows
# USD/lb, so convert at fetch time. Keys not listed here are stored as quoted.
YF_SCALE = {
    "live_cattle": 0.01,
    "lean_hogs": 0.01,
}

# FRED series (no API key — public CSV endpoint). Covers base metals, credit
# spreads, and the 10y-2y curve that have no usable yfinance ticker. NOTE:
# some corporate networks block fred.stlouisfed.org; the fetch fails soft and
# leaves the existing series untouched (succeeds in CI / unrestricted nets).
# (series_key, fred_series_id, description)
FRED_SERIES = [
    ("nickel",            "PNICKUSDM",    "Global price of Nickel (USD/t)"),
    ("zinc",              "PZINCUSDM",    "Global price of Zinc (USD/t)"),
    ("tin",               "PTINUSDM",     "Global price of Tin (USD/t)"),
    ("lead",              "PLEADUSDM",    "Global price of Lead (USD/t)"),
    ("lng_asia",          "PNGASJPUSDM",  "Global price of LNG, Asia (USD/MMBtu)"),
    ("ig_spread",         "BAMLC0A0CM",   "ICE BofA US Corp Index OAS (%)"),
    ("hy_spread",         "BAMLH0A0HYM2", "ICE BofA US High Yield Index OAS (%)"),
    ("yield_curve_10y2y", "T10Y2Y",       "10Y-2Y Treasury spread (%)"),
]

# BoC Valet observations — (series_key, valet_series_id, recent_N)
BOC_SERIES = [
    ("prime_rate",     "V80691311",          300),  # Weekly Chartered Bank Prime
    ("overnight_rate", "V39079",             400),  # BoC policy (overnight) rate
    ("boc_rate",       "V39079",             400),  # alias of policy rate
    ("goc_2y_yield",   "BD.CDN.2YR.DQ.YLD",  400),
    ("goc_3y_yield",   "BD.CDN.3YR.DQ.YLD",  400),
    ("goc_5y_yield",   "BD.CDN.5YR.DQ.YLD",  400),
    ("goc_7y_yield",   "BD.CDN.7YR.DQ.YLD",  400),
    ("goc_10y_yield",  "BD.CDN.10YR.DQ.YLD", 400),
    ("goc_long_yield", "BD.CDN.LONG.DQ.YLD", 400),
]


def _pt_date(p):
    return p.get("date") or p.get("refPer") or p.get("period") or ""


def _merge_points(existing, fresh):
    """Union existing + fresh point lists by date (fresh wins on conflict).

    Preserves deep history — a 13-month yfinance pull must NEVER truncate a
    series that already holds years of data. Returns ascending [{date,value}].
    """
    by_date = {}
    for p in (existing or []):
        d = _pt_date(p)
        if d:
            by_date[d[:10]] = {"date": d[:10], "value": p.get("value")}
    for p in (fresh or []):
        d = _pt_date(p)
        if d and p.get("value") is not None:
            by_date[d[:10]] = {"date": d[:10], "value": p.get("value")}
    return [by_date[k] for k in sorted(by_date)]


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


def _fetch_fred(series_id: str):
    """Fetch a FRED series via the public no-key CSV endpoint.

    Returns ascending [{date,value}]. Raises on network failure so the caller
    can fail soft (FRED is blocked on some corporate nets — see FRED_SERIES).
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "replace")
    lines = text.strip().split("\n")
    points = []
    for ln in lines[1:]:  # skip header
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        d, v = parts[0].strip(), parts[1].strip()
        if not d or v in ("", "."):
            continue
        try:
            points.append({"date": d, "value": float(v)})
        except ValueError:
            continue
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
        scale = YF_SCALE.get(key)
        if scale:
            for p in pts:
                if p.get("value") is not None:
                    p["value"] = round(p["value"] * scale, 4)
        prev_pts = len(ts.get(key, []) or [])
        merged = _merge_points(ts.get(key, []), pts)
        ts[key] = merged
        refreshed.append((key, ticker, prev_pts, len(merged),
                          merged[-1]["date"], label))

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
        merged = _merge_points(ts.get(key, []), pts)
        ts[key] = merged
        refreshed.append((key, f"BoC:{series_id}", prev_pts, len(merged),
                          merged[-1]["date"], f"BoC Valet {series_id}"))

    # FRED series (fail soft — endpoint blocked on some corporate networks)
    for key, fred_id, label in FRED_SERIES:
        if subset is not None and key not in subset:
            continue
        try:
            pts = _fetch_fred(fred_id)
        except Exception as e:
            failed.append((key, f"FRED {fred_id}: {type(e).__name__} "
                                f"(endpoint may be network-blocked here)"))
            continue
        if not pts:
            failed.append((key, f"FRED {fred_id}: no rows"))
            continue
        prev_pts = len(ts.get(key, []) or [])
        merged = _merge_points(ts.get(key, []), pts)
        ts[key] = merged
        refreshed.append((key, f"FRED:{fred_id}", prev_pts, len(merged),
                          merged[-1]["date"], label))

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
