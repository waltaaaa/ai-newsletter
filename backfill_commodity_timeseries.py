"""
One-time backfill: populate timeseries table with 1 year of weekly
commodity, equity index, and FX historical data from Yahoo Finance.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.
"""

import yfinance as yf
from datetime import datetime
import os, json

from db import init_db, save_dashboard_state

conn = init_db()

# ── Ticker → (doc_id, label, unit, category) ──────────────────
TICKERS = [
    # Commodities
    ("CL=F",  "comm_wti",       "Crude Oil (WTI)",   "bbl",     "Commodities"),
    ("BZ=F",  "comm_brent",     "Crude Oil (Brent)", "bbl",     "Commodities"),
    ("NG=F",  "comm_natgas",    "Natural Gas",       "MMBtu",   "Commodities"),
    ("GC=F",  "comm_gold",      "Gold",              "troy oz", "Commodities"),
    ("SI=F",  "comm_silver",    "Silver",            "troy oz", "Commodities"),
    ("PL=F",  "comm_platinum",  "Platinum",          "troy oz", "Commodities"),
    ("PA=F",  "comm_palladium", "Palladium",         "troy oz", "Commodities"),
    ("HG=F",  "comm_copper",    "Copper",            "lb",      "Commodities"),
    ("ALI=F", "comm_aluminum",  "Aluminum",          "lb",      "Commodities"),
    ("ZW=F",  "comm_wheat",     "Wheat",             "bu",      "Commodities"),
    ("ZC=F",  "comm_corn",      "Corn",              "bu",      "Commodities"),
    ("ZR=F",  "comm_rice",      "Rice",              "cwt",     "Commodities"),
    ("ZS=F",  "comm_soybeans",  "Soybeans",          "bu",      "Commodities"),
    ("KC=F",  "comm_coffee",    "Coffee",            "lb",      "Commodities"),
    ("CC=F",  "comm_cocoa",     "Cocoa",             "t",       "Commodities"),
    ("SB=F",  "comm_sugar",     "Sugar #11",         "lb",      "Commodities"),
    ("CT=F",  "comm_cotton",    "Cotton",            "lb",      "Commodities"),
    ("ZL=F",  "comm_soyoil",    "Soybean Oil",       "lb",      "Commodities"),
    ("ZM=F",  "comm_soymeal",   "Soybean Meal",      "ton",     "Commodities"),
    # Equity Indices
    ("^GSPTSE", "tsx_composite", "TSX Composite",    "pts",     "Equity Indices"),
    ("^GSPC",   "idx_sp500",    "S&P 500",           "pts",     "Equity Indices"),
    ("^DJI",    "idx_djia",     "Dow Jones",         "pts",     "Equity Indices"),
    ("^IXIC",   "idx_nasdaq",   "NASDAQ",            "pts",     "Equity Indices"),
    ("^FTSE",   "idx_ftse",     "FTSE 100",          "pts",     "Equity Indices"),
    ("^GDAXI",  "idx_dax",      "DAX",               "pts",     "Equity Indices"),
    ("^N225",   "idx_nikkei",   "Nikkei 225",        "pts",     "Equity Indices"),
    ("^HSI",    "idx_hangseng", "Hang Seng",         "pts",     "Equity Indices"),
    ("000001.SS","idx_shanghai","Shanghai",           "pts",     "Equity Indices"),
    # FX
    ("CADUSD=X", "cadusd",      "CAD/USD",           "USD",     "Foreign Exchange"),
    ("EURUSD=X", "fx_eurusd",   "EUR/USD",           "",        "Foreign Exchange"),
    ("GBPUSD=X", "fx_gbpusd",   "GBP/USD",           "",        "Foreign Exchange"),
    ("JPY=X",    "fx_usdjpy",   "USD/JPY",           "",        "Foreign Exchange"),
    ("CNY=X",    "fx_usdcny",   "USD/CNY",           "",        "Foreign Exchange"),
    ("AUDUSD=X", "fx_audusd",   "AUD/USD",           "",        "Foreign Exchange"),
]

def backfill():
    tickers_list = [t[0] for t in TICKERS]
    print(f"Downloading 1 year of weekly data for {len(tickers_list)} tickers...")

    try:
        data = yf.download(tickers_list, period="1y", interval="1wk", progress=True)['Close']
    except Exception as e:
        print(f"Batch download failed: {e}")
        conn.close()
        return

    for ticker, doc_id, label, unit, category in TICKERS:
        try:
            col = data[ticker] if len(tickers_list) > 1 else data
            col = col.dropna()
            if len(col) < 2:
                print(f"  SKIP {label}: insufficient data")
                continue

            series = []
            for dt, val in col.items():
                series.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'value': round(float(val), 4)
                })

            # Save to dashboard_state with ts_ prefix (timeseries namespace)
            save_dashboard_state(conn, f"ts_{doc_id}", {
                'label': label,
                'unit': unit,
                'category': category,
                'series': series
            })
            print(f"  OK {label} ({doc_id}): {len(series)} points")

        except Exception as e:
            print(f"  ERR {label}: {e}")
            continue

    conn.close()
    print("\nBackfill complete!")


if __name__ == '__main__':
    backfill()
