"""
update_dashboard.py — CAN-MACRO Strategic Dashboard Pipeline

Architecture (3 layers):
  DATA COLLECTION  — Government APIs, RSS feeds (~80), GDELT news, registries, Tavily Extract,
                     Yahoo Finance (all facts, no AI)
  ANALYSIS         — Claude Sonnet 4.5 writes all analysis from collected facts
                     (4 calls: national+global, provincial, industry, project extraction)
  STATUS TRACKING  — Perplexity Sonar Pro checks stale projects (4+ weeks without activity)

Steps:
  1  Hard data       — BoC Valet, StatCan WDS, CMHC, Yahoo Finance, FRED, ECB, BoE
  2a RSS feeds       — ~80 government feeds (federal + 13 provincial + 17+ municipal)
  2b Gov registries  — IAAC, BC EAO, NRCan, Infrastructure Canada, BuyAndSell
  2c GDELT           — Free news search for Canadian articles (project + economy topics)
  2d Tavily Extract  — Full article text from top 100 GDELT URLs
  3  Claude Sonnet   — 4 analysis calls (national/global, provincial, industries, projects)
  4a Passive match   — Match GDELT/RSS project mentions against Firestore
  4b Stale checks    — Perplexity for projects unseen 4+ weeks
  5  URL verify      — HEAD check every citation URL; drop dead links
  6  Firestore push  — /newsletters, /projects, /statcan_indicators, /timeseries
  7  Timeseries      — Append current values for Data Explorer chart

Flags:
  python update_dashboard.py               — normal weekly run
  python update_dashboard.py --deep-sweep  — monthly full NAICS sweep
  python update_dashboard.py --test-feeds  — test all RSS feed URLs
  python update_dashboard.py --seed-projects — full project seed (registries + GDELT + Perplexity)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import pytz
import re
import requests
import yfinance as yf
import feedparser
import socket
import anthropic
from google import genai
from google.genai import types
from datetime import datetime, date, timedelta
import time
import concurrent.futures
import rss_monitor
import gdelt_monitor
from dotenv import load_dotenv
from project_sync import upsert_projects, upsert_flat_projects
from gov_sources import fetch_statcan_indicators, save_statcan_indicators, fetch_registry_projects
from pipeline_config import OPUS_MODEL, SONNET_MODEL, GEMINI_MODEL
from citation_audit import (
    CITATION_RULES, run_citation_audit, save_audit_log,
)

try:
    from tavily import TavilyClient as _TavilyClient
    _HAS_TAVILY = True
except ImportError:
    _HAS_TAVILY = False
    print("[WARN] tavily-python not installed — Tavily Extract will be skipped")

# ==========================================
# 1. CONFIGURATION & AUTH
# ==========================================

load_dotenv()


def _fmt_period(dt_str: str) -> str:
    """Convert 'YYYY-MM-DD' or 'YYYY-MM' to 'Mon YYYY' for display."""
    if not dt_str:
        return ''
    try:
        return datetime.strptime(dt_str[:7], '%Y-%m').strftime('%b %Y')
    except Exception:
        return dt_str[:7]


def _calc_change(cur: str | None, prev: str | None) -> str:
    """Compute signed numeric difference between two formatted indicator strings."""
    if not cur or not prev:
        return ''
    try:
        c = float(str(cur).replace('%', '').replace(',', '').replace('+', '').strip())
        p = float(str(prev).replace('%', '').replace(',', '').replace('+', '').strip())
        d = c - p
        unit = 'pp' if '%' in str(cur) else ''
        return f"{d:+.1f}{unit}"
    except Exception:
        return ''


PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "").strip()
TAVILY_API_KEY     = os.environ.get("TAVILY_API_KEY", "").strip()

if not PERPLEXITY_API_KEY:
    print("[WARN] PERPLEXITY_API_KEY not set — stale checks will be skipped")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set in .env")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in .env")
if not TAVILY_API_KEY:
    print("[WARN] TAVILY_API_KEY not set — article extraction will be skipped")

# Tavily client (optional)
tavily_client = None
if _HAS_TAVILY and TAVILY_API_KEY:
    try:
        tavily_client = _TavilyClient(api_key=TAVILY_API_KEY)
    except Exception as e:
        print(f"[WARN] Tavily client init failed: {e}")

if not firebase_admin._apps:
    service_account_info = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if service_account_info:
        cred = credentials.Certificate(json.loads(service_account_info))
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db             = firestore.client()
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
gemini_client  = genai.Client(api_key=GEMINI_API_KEY)

# ── Watchlist for official context injection ─────────────────────────────────
_WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), 'watchlist.json')
_WATCHLIST = {}
if os.path.exists(_WATCHLIST_PATH):
    with open(_WATCHLIST_PATH, 'r', encoding='utf-8') as _wf:
        _WATCHLIST = json.load(_wf)

# ==========================================
# 2. HARD DATA (unchanged)
# ==========================================

def get_live_commodities():
    print("Fetching live commodity data from Yahoo Finance...")

    TICKER_MAP = [
        # Energy
        ("CL=F",  "Energy",                     "Crude Oil (WTI)",   "bbl",     lambda x: f"${x:.2f}"),
        ("BZ=F",  "Energy",                     "Crude Oil (Brent)", "bbl",     lambda x: f"${x:.2f}"),
        ("NG=F",  "Energy",                     "Natural Gas",       "MMBtu",   lambda x: f"${x:.3f}"),
        ("MTF=F", "Energy",                     "Coal (Newcastle)",  "t",       lambda x: f"${x:.2f}"),
        ("PN=F",  "Energy",                     "Propane",           "gal",     lambda x: f"${x:.4f}"),
        # Precious Metals
        ("GC=F",  "Precious Metals",            "Gold",              "troy oz", lambda x: f"${x:,.0f}"),
        ("SI=F",  "Precious Metals",            "Silver",            "troy oz", lambda x: f"${x:.2f}"),
        ("PL=F",  "Precious Metals",            "Platinum",         "troy oz", lambda x: f"${x:,.0f}"),
        ("PA=F",  "Precious Metals",            "Palladium",        "troy oz", lambda x: f"${x:,.0f}"),
        # Base Metals
        ("HG=F",  "Base Metals",                "Copper",            "lb",      lambda x: f"${x:.4f}"),
        ("ALI=F", "Base Metals",                "Aluminum",          "lb",      lambda x: f"${x:.4f}"),
        # Agriculture - Grains
        ("ZW=F",  "Agriculture - Grains",       "Wheat",             "bu",      lambda x: f"${x:.2f}"),
        ("ZC=F",  "Agriculture - Grains",       "Corn",              "bu",      lambda x: f"${x:.2f}"),
        ("ZR=F",  "Agriculture - Grains",       "Rice",              "cwt",     lambda x: f"${x:.2f}"),
        ("ZS=F",  "Agriculture - Grains",       "Soybeans",          "bu",      lambda x: f"${x:.2f}"),
        # Agriculture - Softs
        ("KC=F",  "Agriculture - Softs",        "Coffee",            "lb",      lambda x: f"${x:.4f}"),
        ("CC=F",  "Agriculture - Softs",        "Cocoa",             "t",       lambda x: f"${x:,.0f}"),
        ("SB=F",  "Agriculture - Softs",        "Sugar #11",         "lb",      lambda x: f"${x:.4f}"),
        ("CT=F",  "Agriculture - Softs",        "Cotton",            "lb",      lambda x: f"${x:.4f}"),
        # Agriculture - Oils & Meals
        ("ZL=F",  "Agriculture - Oils & Meals", "Soybean Oil",       "lb",      lambda x: f"${x:.4f}"),
        ("ZM=F",  "Agriculture - Oils & Meals", "Soybean Meal",      "ton",     lambda x: f"${x:.2f}"),
    ]

    CATEGORY_COLORS = {
        "Energy":                     "text-orange-500",
        "Precious Metals":            "text-yellow-500",
        "Base Metals":                "text-slate-500",
        "Agriculture - Grains":       "text-lime-600",
        "Agriculture - Softs":        "text-emerald-600",
        "Agriculture - Oils & Meals": "text-green-600",
        "Fertilizers":                "text-teal-600",
        "Livestock":                  "text-rose-500",
    }

    all_tickers = [t[0] for t in TICKER_MAP]

    try:
        data = yf.download(all_tickers, period="1y", progress=False)['Close']
    except Exception as e:
        print(f"  Batch download failed: {e}")
        data = None

    categories = {}
    summary = {}

    for ticker, category, name, unit, fmt in TICKER_MAP:
        try:
            if data is None:
                raise ValueError("No data available")
            col = data[ticker] if len(all_tickers) > 1 else data
            col = col.dropna()
            if len(col) < 2:
                continue
            current = float(col.iloc[-1])
            year_ago = float(col.iloc[0])
            yy_pct = ((current - year_ago) / year_ago) * 100
            yy_str = f"{'+' if yy_pct >= 0 else ''}{yy_pct:.1f}%"
            day_str = ''
            if len(col) >= 2:
                prev_close = float(col.iloc[-2])
                if prev_close:
                    day_pct = ((current - prev_close) / prev_close) * 100
                    day_str = f"{'+' if day_pct >= 0 else ''}{day_pct:.1f}%"
            val_str = fmt(current)
            if category not in categories:
                categories[category] = []
            categories[category].append({"name": name, "unit": unit, "val": val_str, "yy": yy_str, "day": day_str})
            summary[name] = val_str
        except Exception as e:
            print(f"  Skipping {ticker} ({name}): {e}")
            continue

    structured = [
        {"category": cat, "color": CATEGORY_COLORS.get(cat, "text-cyan-600"), "items": items}
        for cat, items in categories.items()
    ]

    print(f"  Fetched {sum(len(c['items']) for c in structured)} commodities across {len(structured)} categories.")
    return {"structured": structured, "summary": summary}


def get_financial_markets():
    print("Fetching live financial market data from Yahoo Finance...")

    INDICES = [
        ("^GSPTSE", "TSX Composite",  "Canada"),
        ("^GSPC",   "S&P 500",        "USA"),
        ("^IXIC",   "NASDAQ",         "USA"),
        ("^DJI",    "Dow Jones",      "USA"),
        ("^FTSE",   "FTSE 100",       "UK"),
        ("^GDAXI",  "DAX",            "Germany"),
        ("^N225",   "Nikkei 225",     "Japan"),
    ]
    FX = [
        ("CADUSD=X", "CAD/USD"),
        ("EURUSD=X", "EUR/USD"),
        ("USDCNY=X", "USD/CNY"),
        ("USDJPY=X", "USD/JPY"),
    ]

    all_tickers = [t[0] for t in INDICES] + [t[0] for t in FX]
    try:
        data = yf.download(all_tickers, period="1y", progress=False)['Close']
    except Exception as e:
        print(f"  Financial markets download failed: {e}")
        return {"indices": [], "fx": []}

    def get_row(ticker, label, extra=None):
        try:
            col = (data[ticker] if len(all_tickers) > 1 else data).dropna()
            if len(col) < 2:
                return None
            current  = float(col.iloc[-1])
            prev     = float(col.iloc[-2])
            year_ago = float(col.iloc[0])
            day_pct  = ((current - prev) / prev) * 100
            yy_pct   = ((current - year_ago) / year_ago) * 100
            row = {
                "name":  label,
                "value": f"{current:,.2f}" if current < 1000 else f"{current:,.0f}",
                "day":   f"{'+' if day_pct >= 0 else ''}{day_pct:.2f}%",
                "yy":    f"{'+' if yy_pct >= 0 else ''}{yy_pct:.1f}%",
            }
            if extra:
                row.update(extra)
            return row
        except Exception:
            return None

    indices = [r for t, l, region in INDICES for r in [get_row(t, l, {"region": region})] if r]
    fx      = [r for t, l in FX for r in [get_row(t, l)] if r]

    print(f"  Fetched {len(indices)} indices, {len(fx)} FX pairs.")
    return {"indices": indices, "fx": fx}


def get_boc_rate() -> dict:
    """Return {'rate': '2.75%', 'prev': '3.00%', 'date': 'YYYY-MM-DD'}."""
    print("Fetching live BoC Policy Rate...")
    try:
        url = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=2"
        response = requests.get(url).json()
        obs = response['observations']
        rate = f"{float(obs[-1]['V39079']['v']):.2f}%"
        prev = f"{float(obs[0]['V39079']['v']):.2f}%" if len(obs) >= 2 else ''
        date_str = obs[-1].get('d', '')
        return {'rate': rate, 'prev': prev, 'date': date_str}
    except Exception:
        return {'rate': '2.75%', 'prev': '', 'date': ''}


def _boc_series(series_id: str, recent: int = 1) -> str | None:
    """Fetch latest observation from BoC Valet. Retries once after 5 s on failure."""
    def _fetch():
        url = f"https://www.bankofcanada.ca/valet/observations/{series_id}/json?recent={recent}"
        resp = requests.get(url, timeout=10).json()
        obs = resp.get('observations', [])
        if not obs:
            return None
        val = obs[-1].get(series_id, {}).get('v')
        return str(val) if val is not None else None

    try:
        result = _fetch()
        if result is not None:
            return result
    except Exception:
        pass
    time.sleep(5)
    try:
        return _fetch()
    except Exception:
        return None


def _cmhc_housing_starts() -> float | None:
    """
    Fetch the latest monthly SAAR of total housing starts for all of Canada
    directly from the CMHC monthly news release page.
    Tries the most recent 4 months to account for publication lag (~11 business days).
    """
    today = date.today()
    for months_back in range(4):
        target = today.replace(day=1)
        for _ in range(months_back):
            target = (target - timedelta(days=1)).replace(day=1)
        month_name = target.strftime('%B').lower()
        year = target.year
        url = (f"https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/"
               f"{year}/housing-starts-{month_name}-{year}")
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                continue
            # "SAAR of housing starts for all areas in Canada was ... (238,049 units)"
            m = re.search(r'for all areas in Canada[^(]{0,120}\((\d{1,3},\d{3})', resp.text)
            if m:
                val = float(m.group(1).replace(',', ''))
                if 100_000 <= val <= 500_000:
                    return val
        except Exception:
            continue
    return None


def _cmhc_provincial_housing_starts() -> dict:
    """
    Parse CMHC monthly news release for provincial housing starts SAAR (6-month trend).
    Returns {province_name: {total, prev_total, pct_change, refPer}}.
    Returns {} on failure. Tries the most recent 4 months for publication lag.

    Source: Table 0 of the CMHC news release — "Seasonally Adjusted at Annual Rates
    — 6 Month Moving Average (Trend) (Provinces — 10,000+)".
    Columns: Province | Single-Dec | Single-Jan | % | All-Dec | All-Jan | % |
             Total-Dec | Total-Jan | %
    """
    today = date.today()
    for months_back in range(4):
        target = today.replace(day=1)
        for _ in range(months_back):
            target = (target - timedelta(days=1)).replace(day=1)
        month_name = target.strftime('%B').lower()
        year = target.year
        url = (f"https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/"
               f"{year}/housing-starts-{month_name}-{year}")
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                continue

            tables = re.findall(r'<table[^>]*>.*?</table>', resp.text, re.DOTALL | re.IGNORECASE)
            if not tables:
                continue

            # Table 0: provincial SAAR trend
            tbl = re.sub(r'<[^>]+>', ' ', tables[0])
            tbl = re.sub(r'&[a-z]+;', '', tbl)
            tbl = re.sub(r'\s+', ' ', tbl)

            # Extract reference month from table title (e.g. "January 2026")
            rm = re.search(
                r'(January|February|March|April|May|June|July|August|'
                r'September|October|November|December)\s+(\d{4})',
                tbl, re.IGNORECASE
            )
            refper = rm.group(0) if rm else f"{target.strftime('%B')} {year}"

            # Match province rows:
            # Province-abbr [Single-prev] [Single-curr] [%] [All-prev] [All-curr] [%]
            #               [Total-prev]  [Total-curr]  [%]
            prov_re = re.compile(
                r'(N\.L\.|P\.E\.I\.|N\.S\.|N\.B\.|Qc|Ont\.|Man\.|Sask\.|Alta\.|B\.C\.)'
                r'\s+([\d,]+)\s+([\d,]+)\s+(-?\d+)'   # Single: prev curr %
                r'\s+([\d,]+)\s+([\d,]+)\s+(-?\d+)'   # All Others: prev curr %
                r'\s+([\d,]+)\s+([\d,]+)\s+(-?\d+)'   # Total: prev curr %
            )

            result = {}
            for m in prov_re.finditer(tbl):
                abbr  = m.group(1)
                pname = _CMHC_PROV_ABBR.get(abbr)
                if not pname:
                    continue
                result[pname] = {
                    'total':      int(m.group(9).replace(',', '')),
                    'prev_total': int(m.group(8).replace(',', '')),
                    'pct_change': int(m.group(10)),
                    'refPer':     refper,
                }

            if result:
                print(f"  [CMHC] Provincial housing starts ({refper}): {len(result)} provinces")
                return result

        except Exception:
            continue
    return {}


def get_national_indicators() -> dict:
    """
    Fetch national economic indicators from StatCan WDS (CPI, unemployment)
    and CMHC news releases (housing starts SAAR).
    Returns {'values': {field: formatted_str | None}, 'sources': {field: source_label}}.
    Gracefully returns None for any series that fails — never raises.
    """
    print("Fetching national indicators from StatCan WDS...")
    values      = {}
    prev_values = {}
    obs_dates   = {}
    sources     = {'bocRate': 'BoC'}

    # Batch fetch CPI + unemployment — n=14 gives 14 obs for prev-month YoY
    wds_data = _statcan_wds([_CPI_VECTOR, _UNEMP_VECTOR], n=14)

    # CPI (all-items) — YoY from index levels (obs[-1] vs obs[-13] = 12 months apart)
    cpi_obs = wds_data.get(_CPI_VECTOR, [])
    if len(cpi_obs) >= 13:
        try:
            latest   = float(cpi_obs[-1]['value'])
            year_ago = float(cpi_obs[-13]['value'])
            yoy      = ((latest - year_ago) / year_ago) * 100
            values['cpi']    = f"+{yoy:.1f}%" if yoy >= 0 else f"{yoy:.1f}%"
            sources['cpi']   = 'StatCan'
            obs_dates['cpi'] = cpi_obs[-1].get('refPer', '')
        except Exception:
            pass
    if len(cpi_obs) >= 14:
        try:
            prev_latest   = float(cpi_obs[-2]['value'])
            prev_year_ago = float(cpi_obs[-14]['value'])
            prev_yoy      = ((prev_latest - prev_year_ago) / prev_year_ago) * 100
            prev_values['cpi'] = f"+{prev_yoy:.1f}%" if prev_yoy >= 0 else f"{prev_yoy:.1f}%"
        except Exception:
            pass

    # Unemployment rate — latest observation
    unemp_obs = wds_data.get(_UNEMP_VECTOR, [])
    if unemp_obs:
        try:
            values['unemployment']    = f"{float(unemp_obs[-1]['value']):.1f}%"
            sources['unemployment']   = 'StatCan'
            obs_dates['unemployment'] = unemp_obs[-1].get('refPer', '')
        except Exception:
            pass
    if len(unemp_obs) >= 2:
        try:
            prev_values['unemployment'] = f"{float(unemp_obs[-2]['value']):.1f}%"
        except Exception:
            pass

    # Housing Starts — CMHC SAAR from CMHC monthly news release (direct source)
    starts = _cmhc_housing_starts()
    if starts is not None:
        values['housingStarts']  = f"{starts:,.0f}"
        sources['housingStarts'] = 'CMHC'

    print(f"  CPI={values.get('cpi','N/A')}  Unemployment={values.get('unemployment','N/A')}  "
          f"HousingStarts={values.get('housingStarts','N/A')}")
    return {'values': values, 'prev_values': prev_values, 'obs_dates': obs_dates, 'sources': sources}


# ── Provincial unemployment — StatCan WDS vector IDs ─────────────────────────
# Table 14-10-0287-01 (PID 14100287): Unemployment rate, both sexes, 15 years+, SA
# Coordinate {geo}.7.1.1.1.1 — geo: 2=NL, 3=PEI, 4=NS, 5=NB, 6=QC, 7=ON, 8=MB, 9=SK, 10=AB, 11=BC
_PROV_UNEMP_VIDS = {
    "Newfoundland and Labrador": 2063004,
    "Prince Edward Island":      2063193,
    "Nova Scotia":               2063382,
    "New Brunswick":             2063571,
    "Quebec":                    2063760,
    "Ontario":                   2063949,
    "Manitoba":                  2064138,
    "Saskatchewan":              2064327,
    "Alberta":                   2064516,
    "British Columbia":          2064705,
}

# ── Provincial CPI — StatCan WDS vector IDs ───────────────────────────────────
# Table 18-10-0004-01: CPI All-items by province, monthly
_PROV_CPI_VIDS = {
    "Newfoundland and Labrador": 41690914,
    "Prince Edward Island":      41690915,
    "Nova Scotia":               41690916,
    "New Brunswick":             41690917,
    "Quebec":                    41690918,
    "Ontario":                   41690919,
    "Manitoba":                  41690920,
    "Saskatchewan":              41690921,
    "Alberta":                   41690922,
    "British Columbia":          41690923,
}

# ── Provincial real GDP — StatCan WDS vector IDs ─────────────────────────────
# Table 36-10-0402-01: GDP at basic prices by province, All industries,
# Chained (2017) dollars, annual. n=2 gives current + prior year for Y/Y.
_PROV_GDP_VIDS = {
    "Newfoundland and Labrador": 62464519,
    "Prince Edward Island":      62464824,
    "Nova Scotia":               62465129,
    "New Brunswick":             62465434,
    "Quebec":                    62465739,
    "Ontario":                   62466044,
    "Manitoba":                  62466349,
    "Saskatchewan":              62466654,
    "Alberta":                   62466959,
    "British Columbia":          62467264,
}

# ── CMHC provincial housing starts abbreviation map ──────────────────────────
# Matches abbreviations used in CMHC monthly news release tables
_CMHC_PROV_ABBR = {
    "N.L.":   "Newfoundland and Labrador",
    "P.E.I.": "Prince Edward Island",
    "N.S.":   "Nova Scotia",
    "N.B.":   "New Brunswick",
    "Qc":     "Quebec",
    "Ont.":   "Ontario",
    "Man.":   "Manitoba",
    "Sask.":  "Saskatchewan",
    "Alta.":  "Alberta",
    "B.C.":   "British Columbia",
}


def get_provincial_indicators() -> dict:
    """
    Fetch provincial unemployment (StatCan LFS), CPI (StatCan), and real GDP
    (StatCan Table 36-10-0402-01, annual) from StatCan WDS in two batch calls.
    Returns {province_name: {field: value, field_src: 'StatCan'}}.
    Territories are not covered by these series.
    """
    print("Fetching provincial indicators from StatCan WDS...")
    result = {}

    # Batch 1: unemployment (10) + CPI (10) — n=14 for prev-month YoY on CPI
    all_vids = list(_PROV_UNEMP_VIDS.values()) + list(_PROV_CPI_VIDS.values())
    data = _statcan_wds(all_vids, n=14)

    # Batch 2: provincial annual real GDP (10) — n=2 for current + prior year Y/Y
    gdp_data = _statcan_wds(list(_PROV_GDP_VIDS.values()), n=2)

    # Unemployment — latest value (SA, both sexes, 15+, Table 14-10-0287-01)
    for prov, vid in _PROV_UNEMP_VIDS.items():
        obs = data.get(vid, [])
        if obs:
            try:
                val = float(obs[-1]['value'])
                if 1.0 <= val <= 30.0:  # sanity check: valid unemployment rate range
                    updates = {
                        'unemployment':      f"{val:.1f}%",
                        'unemployment_src':  'StatCan',
                        'unemployment_date': obs[-1].get('refPer', ''),
                    }
                    if len(obs) >= 2:
                        prev_val = float(obs[-2]['value'])
                        if 1.0 <= prev_val <= 30.0:
                            updates['unemployment_prev'] = f"{prev_val:.1f}%"
                    result.setdefault(prov, {}).update(updates)
            except Exception:
                pass

    # CPI — YoY from index levels, obs[-1] vs obs[-13] = 12 months apart
    for prov, vid in _PROV_CPI_VIDS.items():
        obs = data.get(vid, [])
        if len(obs) >= 13:
            try:
                latest   = float(obs[-1]['value'])
                year_ago = float(obs[-13]['value'])
                yoy      = ((latest - year_ago) / year_ago) * 100
                updates = {
                    'cpi':      f"+{yoy:.1f}%" if yoy >= 0 else f"{yoy:.1f}%",
                    'cpi_src':  'StatCan',
                    'cpi_date': obs[-1].get('refPer', ''),
                }
                if len(obs) >= 14:
                    prev_latest   = float(obs[-2]['value'])
                    prev_year_ago = float(obs[-14]['value'])
                    if prev_year_ago:
                        prev_yoy = ((prev_latest - prev_year_ago) / prev_year_ago) * 100
                        updates['cpi_prev'] = f"+{prev_yoy:.1f}%" if prev_yoy >= 0 else f"{prev_yoy:.1f}%"
                result.setdefault(prov, {}).update(updates)
            except Exception:
                pass

    # Real GDP — annual Y/Y growth from chained-dollar levels (Table 36-10-0402-01)
    # n=2: obs[-1]=current year, obs[-2]=prior year — enough for one Y/Y growth rate
    for prov, vid in _PROV_GDP_VIDS.items():
        obs = gdp_data.get(vid, [])
        if len(obs) >= 2:
            try:
                curr = float(obs[-1]['value'])
                prev = float(obs[-2]['value'])
                if prev:
                    yoy      = (curr - prev) / prev * 100
                    ref_year = obs[-1].get('refPer', '')[:4]
                    updates  = {
                        'gdp':      f"+{yoy:.1f}%" if yoy >= 0 else f"{yoy:.1f}%",
                        'gdp_src':  'StatCan',
                        'gdp_date': ref_year,  # e.g. "2024"
                    }
                    result.setdefault(prov, {}).update(updates)
            except Exception:
                pass

    # Housing starts — CMHC monthly news release (provincial SAAR trend)
    prov_starts = _cmhc_provincial_housing_starts()
    for pname, starts in prov_starts.items():
        updates = {
            'housingStarts':      f"{starts['total']:,}",
            'housingStarts_src':  'CMHC',
            'housingStarts_date': starts['refPer'],
            'housingStarts_prev': f"{starts['prev_total']:,}",
        }
        result.setdefault(pname, {}).update(updates)

    n_unemp   = sum(1 for v in result.values() if 'unemployment' in v)
    n_cpi     = sum(1 for v in result.values() if 'cpi' in v)
    n_gdp     = sum(1 for v in result.values() if 'gdp' in v)
    n_housing = sum(1 for v in result.values() if 'housingStarts' in v)
    print(f"  Unemployment: {n_unemp} | CPI: {n_cpi} | GDP: {n_gdp} | Housing starts: {n_housing} provinces")
    for prov, vals in sorted(result.items()):
        u = vals.get('unemployment', '—')
        c = vals.get('cpi', '—')
        g = vals.get('gdp', '—')
        h = vals.get('housingStarts', '—')
        print(f"    {prov[:25]:<25}  unemp={u:<8}  cpi={c:<8}  gdp={g:<8}  starts={h}")
    return result


# ==========================================
# GLOBAL INDICATOR FETCHERS
# (US: FRED public CSV · EU: ECB SDW API · UK: BoE IADB)
# ==========================================

def _fred_latest(series_id: str) -> float | None:
    """Latest observation from FRED public CSV endpoint (no API key required)."""
    try:
        url  = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        for line in reversed(resp.text.strip().split('\n')):
            if line.startswith('DATE'):
                continue
            val = line.split(',')[-1].strip()
            if val and val != '.':
                return float(val)
        return None
    except Exception:
        return None


def _fred_yoy(series_id: str) -> float | None:
    """
    Fetch 14 months from FRED and return YoY % change.
    Used for CPI (index level → need two readings 12 months apart).
    """
    try:
        start = (date.today() - timedelta(days=430)).isoformat()
        url   = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
                 f"?id={series_id}&observation_start={start}")
        resp  = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().split('\n'):
            if line.startswith('DATE'):
                continue
            val = line.split(',')[-1].strip()
            if val and val != '.':
                try:
                    rows.append(float(val))
                except ValueError:
                    pass
        if len(rows) < 13:
            return None
        latest, year_ago = rows[-1], rows[-13]
        if year_ago == 0:
            return None
        return ((latest - year_ago) / year_ago) * 100
    except Exception:
        return None


def _ecb_last(dataflow: str, key: str) -> float | None:
    """Latest observation from ECB Statistical Data Warehouse REST API."""
    try:
        url  = (f"https://data-api.ecb.europa.eu/service/data/{dataflow}/{key}"
                f"?format=jsondata&lastNObservations=1")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        series = list(data['dataSets'][0]['series'].values())[0]
        obs    = list(series['observations'].values())[0]
        return float(obs[0])
    except Exception:
        return None


def _boe_bank_rate() -> float | None:
    """Latest Bank of England Bank Rate from BoE public IADB CSV download."""
    try:
        url  = ("https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
                "?Travel=NIxSUx&SeriesCodes=IUMABEDR&UsingCodes=Y&CSVF=TT&html.x=1&html.y=1")
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        for line in reversed(resp.text.strip().split('\n')):
            line = line.strip().strip('"')
            if not line or line.lower().startswith('date'):
                continue
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2:
                val = parts[-1]
                if val:
                    try:
                        return float(val)
                    except ValueError:
                        pass
        return None
    except Exception:
        return None


def _fred_qoq(series_id: str) -> float | None:
    """
    Fetch a quarterly level index from FRED and return the most recent QoQ % change.
    Used for EU and UK real GDP (SA, chained volume).
    """
    try:
        start = (date.today() - timedelta(days=550)).isoformat()
        url   = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
                 f"?id={series_id}&observation_start={start}")
        resp  = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().split('\n'):
            if line.startswith('DATE'):
                continue
            val = line.split(',')[-1].strip()
            if val and val != '.':
                try:
                    rows.append(float(val))
                except ValueError:
                    pass
        if len(rows) < 2:
            return None
        latest, prev = rows[-1], rows[-2]
        return ((latest / prev) - 1) * 100 if prev else None
    except Exception:
        return None


def _world_bank_latest(iso3: str, indicator: str) -> float | None:
    """
    Most recent non-null value from the World Bank Open Data API (annual frequency).
    Free, no key required.
    """
    try:
        url  = (f"https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}"
                f"?format=json&mrv=5&per_page=5")
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        data = resp.json()
        if len(data) < 2 or not data[1]:
            return None
        for entry in data[1]:
            if entry.get('value') is not None:
                return float(entry['value'])
        return None
    except Exception:
        return None


def get_global_indicators() -> dict:
    """
    Fetch GDP, CPI, policy rate, and unemployment for US, EU, UK, China
    from primary API sources.
      US:  FRED (Federal Reserve Bank of St. Louis) — BLS/BEA data
      EU:  ECB Statistical Data Warehouse
      UK:  BoE IADB (rate) + FRED OECD harmonised series (CPI, unemployment, GDP)
      China: World Bank Open Data API (annual, best available public source)
    Returns {region: {field: 'X.X%', field_src: 'SOURCE'}}.
    """
    print("Fetching global indicators from primary APIs...")
    result = {}

    # ── United States (FRED — BLS/BEA) ────────────────────────────
    print("  US (FRED/BLS/BEA)...", end=" ", flush=True)
    us = {}
    v = _fred_latest('DFF')              # Fed Funds effective rate (daily, FRED)
    if v is not None:
        us['rate'] = f"{v:.2f}%";  us['rate_src'] = 'FRED'
    v = _fred_latest('UNRATE')           # Unemployment rate (BLS, monthly SA)
    if v is not None:
        us['unemployment'] = f"{v:.1f}%";  us['unemployment_src'] = 'FRED/BLS'
    v = _fred_yoy('CPIAUCSL')            # CPI all urban, YoY (BLS)
    if v is not None:
        us['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  us['cpi_src'] = 'FRED/BLS'
    v = _fred_latest('A191RL1Q225SBEA')  # Real GDP growth annualised QoQ (BEA)
    if v is not None:
        us['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  us['gdp_src'] = 'FRED/BEA'
    result['United States'] = us
    print(f"rate={us.get('rate','—')} unemp={us.get('unemployment','—')} "
          f"cpi={us.get('cpi','—')} gdp={us.get('gdp','—')}")

    # ── European Union (ECB SDW + FRED for GDP) ────────────────────
    print("  EU (ECB SDW + FRED)...", end=" ", flush=True)
    eu = {}
    v = _ecb_last('FM',   'B.U2.EUR.4F.KR.DFR.LEV')       # ECB deposit facility rate
    if v is not None:
        eu['rate'] = f"{v:.2f}%";  eu['rate_src'] = 'ECB'
    v = _ecb_last('ICP',  'M.U2.N.000000.4.ANR')           # HICP 12-month % change
    if v is not None:
        eu['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  eu['cpi_src'] = 'ECB/Eurostat'
    v = _ecb_last('LFSI', 'M.I8.S.UNEHRT.TOTAL0.15_74.T') # Euro Area unemployment
    if v is not None:
        eu['unemployment'] = f"{v:.1f}%";  eu['unemployment_src'] = 'ECB/Eurostat'
    # EA19 real GDP QoQ — FRED OECD Quarterly National Accounts series
    v = _fred_qoq('CLVMNACSCAB1GQEA19')
    if v is not None:
        eu['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  eu['gdp_src'] = 'FRED/Eurostat'
    result['European Union'] = eu
    print(f"rate={eu.get('rate','—')} cpi={eu.get('cpi','—')} "
          f"unemp={eu.get('unemployment','—')} gdp={eu.get('gdp','—')}")

    # ── United Kingdom (BoE + FRED OECD harmonised series) ────────
    print("  UK (BoE + FRED/ONS)...", end=" ", flush=True)
    uk = {}
    v = _boe_bank_rate()                 # BoE Bank Rate (BoE IADB)
    if v is not None:
        uk['rate'] = f"{v:.2f}%";  uk['rate_src'] = 'BoE'
    v = _fred_yoy('GBRCPIALLMINMEI')     # UK CPI all items YoY (OECD/ONS via FRED)
    if v is not None:
        uk['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['cpi_src'] = 'FRED/ONS'
    v = _fred_latest('LRHUTTTTGBM156S')  # UK harmonised unemployment rate (OECD/ONS)
    if v is not None:
        uk['unemployment'] = f"{v:.1f}%";  uk['unemployment_src'] = 'FRED/ONS'
    v = _fred_qoq('CLVMNACSCAB1GQGB')   # UK real GDP QoQ SA (ONS via FRED)
    if v is not None:
        uk['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['gdp_src'] = 'FRED/ONS'
    result['United Kingdom'] = uk
    print(f"rate={uk.get('rate','—')} cpi={uk.get('cpi','—')} "
          f"unemp={uk.get('unemployment','—')} gdp={uk.get('gdp','—')}")

    # ── China (World Bank Open Data — annual, best available source) ──
    print("  China (World Bank)...", end=" ", flush=True)
    cn = {}
    v = _world_bank_latest('CHN', 'NY.GDP.MKTP.KD.ZG')  # GDP growth annual %
    if v is not None:
        cn['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  cn['gdp_src'] = 'World Bank'
    v = _world_bank_latest('CHN', 'FP.CPI.TOTL.ZG')     # CPI inflation annual %
    if v is not None:
        cn['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  cn['cpi_src'] = 'World Bank'
    # Unemployment: China NBS urban rate not reliably available via free API
    result['China'] = cn
    print(f"gdp={cn.get('gdp','—')} cpi={cn.get('cpi','—')}")

    return result


# ==========================================
# STATCAN WDS — INDUSTRY GDP
# ==========================================

# StatCan WDS vector IDs for Table 36-10-0434-01
# Real GDP at basic prices (2012=100), monthly, seasonally adjusted
# Source: Statistics Canada CANSIM vectors
_INDUSTRY_VECTORS: dict[str, int] = {
    '11':    65201229,  # Agriculture, forestry, fishing and hunting
    '21':    65201236,  # Mining, quarrying, and oil and gas extraction
    '22':    65201254,  # Utilities
    '23':    65201258,  # Construction
    '31-33': 65201263,  # Manufacturing
    '41':    65201358,  # Wholesale trade
    '44-45': 65201368,  # Retail trade
    '48-49': 65201381,  # Transportation and warehousing
    '51':    65201398,  # Information and cultural industries
    '52':    65201407,  # Finance and insurance
    '53':    65201419,  # Real estate and rental and leasing
    '54':    65201429,  # Professional, scientific and technical services
    '55':    65201441,  # Management of companies and enterprises
    '56':    65201442,  # Administrative and support, waste management and remediation services
    '61':    65201452,  # Educational services
    '62':    65201457,  # Health care and social assistance
    '71':    65201463,  # Arts, entertainment and recreation
    '72':    65201468,  # Accommodation and food services
    '81':    65201471,  # Other services (except public administration)
    '91':    65201476,  # Public administration
}

# Quarterly real GDP — Table 36-10-0104-01, chain-volume index (2012=100)
_GDP_QUARTERLY_VECTOR = 62305752

# National CPI, unemployment, and housing starts — fetched directly from StatCan WDS
_CPI_VECTOR           = 41690973  # Table 18-10-0004-01, CPI All-items Canada
_UNEMP_VECTOR         = 2062815   # Table 14-10-0287-01, LFS unemployment rate Canada SA
_HOUSING_STARTS_VECTOR = 44176028  # NOTE: actually Table 18-10-0049-01 (NHPI) — not used; national housing starts fetched via _cmhc_housing_starts() instead

# StatCan WDS endpoint (POST, JSON, public — no API key required)
_STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"


def _statcan_wds(vector_ids: list, n: int = 14) -> dict:
    """
    Fetch the last N observations for a list of StatCan WDS vector IDs.
    Returns {vectorId: [{'refPer': 'YYYY-MM-DD', 'value': float}]} sorted by date.
    Retries once after 5 s on failure.
    """
    payload = [{"vectorId": vid, "latestN": n} for vid in vector_ids]

    def _fetch():
        resp = requests.post(
            _STATCAN_WDS_URL, json=payload, timeout=20,
            headers={'Content-Type': 'application/json',
                     'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'}
        )
        resp.raise_for_status()
        result = {}
        for item in resp.json():
            if item.get('status') != 'SUCCESS':
                continue
            obj = item.get('object', {})
            vid = obj.get('vectorId')
            points = sorted(
                [{'refPer': p.get('refPer', ''), 'value': p.get('value')}
                 for p in obj.get('vectorDataPoint', [])
                 if p.get('value') is not None],
                key=lambda x: x['refPer']
            )
            result[vid] = points
        return result

    try:
        r = _fetch()
        if r:
            return r
    except Exception as e:
        print(f"  [StatCan WDS] First attempt failed: {e}")

    time.sleep(5)
    try:
        return _fetch()
    except Exception as e:
        print(f"  [StatCan WDS] Retry failed: {e}")
        return {}


def _compute_mm_yy(obs: list) -> tuple:
    """Compute M/M and Y/Y % changes from a sorted list of {refPer, value} observations."""
    try:
        if len(obs) < 2:
            return None, None
        latest = float(obs[-1]['value'])
        prev   = float(obs[-2]['value'])
        mm = ((latest - prev) / prev * 100) if prev else None
        yy = None
        if len(obs) >= 13:
            year_ago = float(obs[-13]['value'])
            yy = ((latest - year_ago) / year_ago * 100) if year_ago else None
        return mm, yy
    except Exception:
        return None, None


def fetch_industry_indicators() -> dict:
    """
    Fetch M/M and Y/Y GDP changes for 20 dashboard industries from StatCan WDS
    (Table 36-10-0434-01), plus quarterly real GDP for the national indicator.

    Returns:
        {
            naics_code: {'mm': '+X.X%', 'yy': '+X.X%', 'src': 'StatCan'},
            '_gdp_quarterly': '+X.X%',       # QoQ annualised real GDP
            '_gdp_quarterly_src': 'StatCan',
        }
    """
    print("  Fetching industry GDP from StatCan WDS...")
    all_vectors = list(_INDUSTRY_VECTORS.values()) + [_GDP_QUARTERLY_VECTOR]
    data = _statcan_wds(all_vectors, n=14)
    result = {}

    # Industry M/M and Y/Y
    for naics_code, vector_id in _INDUSTRY_VECTORS.items():
        obs = data.get(vector_id, [])
        mm, yy = _compute_mm_yy(obs)
        result[naics_code] = {
            'mm':  (f"+{mm:.1f}%" if mm >= 0 else f"{mm:.1f}%") if mm is not None else 'N/A',
            'yy':  (f"+{yy:.1f}%" if yy >= 0 else f"{yy:.1f}%") if yy is not None else 'N/A',
            'src': 'StatCan' if (mm is not None or yy is not None) else 'N/A',
        }

    # National real GDP (quarterly QoQ annualised)
    gdp_obs = data.get(_GDP_QUARTERLY_VECTOR, [])
    if len(gdp_obs) >= 2:
        try:
            latest = float(gdp_obs[-1]['value'])
            prev_q = float(gdp_obs[-2]['value'])
            if prev_q:
                qoq_ann = (((latest / prev_q) ** 4) - 1) * 100
                result['_gdp_quarterly'] = (
                    f"+{qoq_ann:.1f}%" if qoq_ann >= 0 else f"{qoq_ann:.1f}%"
                )
                result['_gdp_quarterly_src'] = 'StatCan'
        except Exception:
            pass

    n_ind = sum(1 for k in result if not k.startswith('_'))
    gdp_str = result.get('_gdp_quarterly', 'N/A')
    print(f"  Industry: {n_ind}/{len(_INDUSTRY_VECTORS)} sectors | GDP: {gdp_str}")
    return result


def fetch_primary_indicators() -> dict:
    """
    Master primary-source data fetcher. Consolidates ALL API calls before any AI analysis.

    Returns:
        {
            'national':   {'values': {field: str}, 'sources': {field: label}},
            'provinces':  {province: {field: str, field_src: label}},
            'global':     {region: {field: str, field_src: label}},
            'industries': {naics_code: {'mm': str, 'yy': str, 'src': label}},
        }
    Any field that exhausts all retries is omitted (caller sets N/A).
    """
    print("\n[STEP 1b] Fetching ALL primary source indicators...")
    nat  = get_national_indicators()
    prov = get_provincial_indicators()
    glob = get_global_indicators()
    ind  = fetch_industry_indicators()

    # Inject quarterly real GDP into national values
    if ind.get('_gdp_quarterly'):
        nat['values']['realGdp']    = ind['_gdp_quarterly']
        nat['sources']['realGdp']   = ind.get('_gdp_quarterly_src', 'StatCan')

    n_nat  = len(nat['values'])
    n_prov = sum(len([k for k in v if not k.endswith('_src')]) for v in prov.values())
    n_glob = sum(len([k for k in v if not k.endswith('_src')]) for v in glob.values())
    n_ind  = sum(1 for k in ind if not k.startswith('_'))
    print(f"  Primary indicators ready: "
          f"national={n_nat}, provinces={n_prov}, global={n_glob}, industries={n_ind}")

    return {'national': nat, 'provinces': prov, 'global': glob, 'industries': ind}


def get_goc_yields():
    print("Fetching live GoC yield curve from Bank of Canada...")

    SERIES_MAP = [
        ("BD.CDN.2YR.DQ.YLD",  "2Y",   True),
        ("BD.CDN.3YR.DQ.YLD",  "3Y",   False),
        ("BD.CDN.5YR.DQ.YLD",  "5Y",   False),
        ("BD.CDN.7YR.DQ.YLD",  "7Y",   False),
        ("BD.CDN.10YR.DQ.YLD", "10Y",  True),
        ("BD.CDN.LONG.DQ.YLD", "Long", False),
    ]
    series_ids = ",".join(s[0] for s in SERIES_MAP)

    try:
        resp_current = requests.get(
            f"https://www.bankofcanada.ca/valet/observations/{series_ids}/json?recent=1",
            timeout=10
        ).json()
        latest = resp_current['observations'][-1]

        year_ago     = (date.today() - timedelta(days=365)).isoformat()
        year_ago_end = (date.today() - timedelta(days=355)).isoformat()
        resp_history = requests.get(
            f"https://www.bankofcanada.ca/valet/observations/{series_ids}/json"
            f"?start_date={year_ago}&end_date={year_ago_end}",
            timeout=10
        ).json()
        historical = resp_history['observations'][-1] if resp_history.get('observations') else None

        yield_curve     = []
        current_vals    = []
        historical_vals = []

        for series_id, term, highlight in SERIES_MAP:
            val = latest.get(series_id, {}).get('v')
            if val is None:
                continue
            yield_curve.append({"term": term, "yield": f"{float(val):.2f}%", "highlight": highlight})
            current_vals.append(float(val))
            if historical:
                hist_val = historical.get(series_id, {}).get('v')
                historical_vals.append(float(hist_val) if hist_val else None)

        clean_hist = [v for v in historical_vals if v is not None]
        charts = {
            "yieldCurveCurrent":  current_vals,
            "yieldCurveLastYear": clean_hist if len(clean_hist) == len(current_vals) else []
        }

        print(f"  Fetched {len(yield_curve)} GoC yield terms (current + 1-yr prior).")
        return {"yieldCurve": yield_curve, "charts": charts}

    except Exception as e:
        print(f"  GoC yield fetch failed: {e}")
        return None


def fetch_news_context(rss_items: list | None = None) -> str:
    """
    Format RSS items for use as news context in Claude prompts.
    Prefers federal economic/infrastructure items for macro context.
    Falls back to fetching live if rss_items is None (legacy path).
    """
    if rss_items is None:
        # Legacy path: fetch a small set of feeds directly
        print("Gathering latest economic news feeds...")
        rss_items = rss_monitor.fetch_all_feeds(days_back=7)
    # Federal economic + StatCan/BoC items first, then project-relevant items
    fed_eco  = [i for i in rss_items if i['source_level'] == 'federal'
                and i['category'] in ('economic',)]
    proj_rel = rss_monitor.filter_project_relevant(rss_items)
    # Deduplicate (proj_rel may overlap with fed_eco)
    seen_urls: set[str] = set()
    combined: list[dict] = []
    for item in (fed_eco + proj_rel):
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            combined.append(item)
    return rss_monitor.format_for_context(combined, max_items=40)


# ==========================================
# 3. SOURCE VERIFICATION
# ==========================================

def _check_url(url: str) -> bool:
    """HEAD request (5 s timeout) to verify a URL is reachable. Returns False on any error."""
    if not url or not url.startswith('http'):
        return False
    try:
        r = requests.head(url, timeout=5, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'})
        return r.status_code < 400
    except Exception:
        return False


def _collect_source_dicts(payload: dict) -> list:
    """Return every source dict object (by reference) from known payload locations."""
    srcs = []
    srcs.extend(payload.get('national', {}).get('sources', []))
    for g in payload.get('global', []):
        srcs.extend(g.get('sources', []))
    for ind in payload.get('goodsIndustries', []) + payload.get('servicesIndustries', []):
        srcs.extend(ind.get('industrySources', []))
    for prov in payload.get('provinces', []):
        srcs.extend(prov.get('sources', []))
        for prj in prov.get('projects', []):
            srcs.extend(prj.get('sources', []))
    return srcs


def verify_source_urls(payload: dict) -> dict:
    """
    Walk every source object in the payload and run concurrent HEAD checks.
    Any URL that returns 4xx/5xx or fails is cleared to '' (title is kept).
    """
    print("\n[SOURCE VERIFICATION] Checking all source URLs...")
    all_srcs   = _collect_source_dicts(payload)
    urls       = [s.get('url', '') for s in all_srcs]
    checkable  = [(i, u) for i, u in enumerate(urls) if u and u.startswith('http')]

    if not checkable:
        print("  No URLs to check.")
        return payload

    print(f"  Checking {len(checkable)} URLs (concurrent HEAD requests)...")
    indices, to_check = zip(*checkable)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_check_url, to_check))

    dead = 0
    for idx, is_live in zip(indices, results):
        if not is_live:
            all_srcs[idx]['url'] = ''
            dead += 1

    print(f"  Live: {len(checkable) - dead}  Dead (cleared): {dead}")
    return payload


# ==========================================
# 4. TIMESERIES STORE
# ==========================================

def append_to_timeseries(payload: dict, financial_markets: dict, boc_rate: str):
    """
    Append one data point per tracked variable to /timeseries/{var_id} in Firestore.
    Creates the document if it doesn't exist; skips duplicate dates.
    Variables tracked: BoC rate, CPI, unemployment, GoC yields, CAD/USD, TSX Composite.
    """
    print("\n[TIMESERIES] Appending data points...")
    today_str = date.today().isoformat()
    ts_ref    = db.collection('timeseries')

    def _upsert(doc_id: str, label: str, unit: str, category: str, raw_value):
        """Parse raw_value to float and upsert into the timeseries doc."""
        if raw_value is None:
            return
        try:
            val_f = float(str(raw_value).replace('%', '').replace('$', '').replace(',', '').strip())
        except Exception:
            return
        point   = {'date': today_str, 'value': val_f}
        doc_ref = ts_ref.document(doc_id)
        snap    = doc_ref.get()
        if snap.exists:
            if any(p['date'] == today_str for p in snap.to_dict().get('series', [])):
                return  # already have today
            doc_ref.update({'series': firestore.ArrayUnion([point])})
        else:
            doc_ref.set({'label': label, 'unit': unit, 'category': category, 'series': [point]})

    # BoC Rate
    _upsert('boc_rate', 'BoC Policy Rate', '%', 'National', boc_rate.replace('%', ''))

    # National metrics
    m = payload.get('metrics', {})
    _upsert('canada_cpi',          'Canada CPI (YoY)',       '%', 'National',
            (m.get('cpi') or '').replace('%', '').replace('+', ''))
    _upsert('canada_unemployment',  'Canada Unemployment',    '%', 'National',
            (m.get('unemployment') or '').replace('%', ''))

    # Yield curve terms
    for yc in payload.get('yieldCurve', []):
        term = yc.get('term', '')
        yval = yc.get('yield', '')
        if term and yval:
            _upsert(f'yield_{term.lower()}', f'GoC {term} Yield', '%', 'Yield Curve',
                    yval.replace('%', ''))

    # CAD/USD
    for fx in financial_markets.get('fx', []):
        if 'CAD/USD' in fx.get('name', '') or 'CADUSD' in fx.get('name', ''):
            _upsert('cadusd', 'CAD/USD Rate', 'USD', 'Foreign Exchange',
                    fx.get('value', '').replace(',', ''))

    # TSX Composite
    for idx in financial_markets.get('indices', []):
        if 'TSX' in idx.get('name', ''):
            _upsert('tsx_composite', 'TSX Composite', 'pts', 'Equity Indices',
                    idx.get('value', '').replace(',', ''))

    print("  Timeseries update complete.")


# ==========================================
# 5. PERPLEXITY (stale project checks only)
# ==========================================

def _query_perplexity(query: str, label: str = "", system_prompt: str = None,
                      max_tokens: int = 1000) -> str:
    """Single Perplexity Sonar Pro query with retry. Returns raw text."""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": system_prompt or (
                    "You are a Canadian economic and financial news researcher. "
                    "Provide factual, sourced, up-to-date information. "
                    "Cite publication names and dates. Be specific about figures and events."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": max_tokens,
    }

    for attempt in range(4):
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 3:
                print(f" [ERR: {e}]")
                return ""
            time.sleep(2 ** attempt)
    return ""


# ==========================================
# 5b. TAVILY ARTICLE EXTRACTION (STEP 2d)
# ==========================================

def extract_article_texts(article_urls: list[str], batch_size: int = 5) -> list[dict]:
    """
    Use Tavily Extract API to pull full text from article URLs.
    Processes in batches of batch_size URLs per API credit.
    Returns list of {url, title, text} dicts.

    Args:
        article_urls: List of URLs from GDELT or RSS.
        batch_size:   URLs per Tavily Extract call (5 = 1 credit).
    """
    if not tavily_client:
        print("  [Tavily] No client available — skipping article extraction.")
        return []

    print(f"  [Tavily] Extracting text from {len(article_urls)} URLs "
          f"in batches of {batch_size}...")

    extracted: list[dict] = []
    for i in range(0, len(article_urls), batch_size):
        batch = article_urls[i:i + batch_size]
        try:
            result = tavily_client.extract(urls=batch)
            for r in result.get('results', []):
                url  = r.get('url') or ''
                text = r.get('raw_content') or r.get('content') or ''
                if url and text:
                    extracted.append({
                        'url':   url,
                        'title': r.get('title') or '',
                        'text':  text[:6000],  # cap per article
                    })
        except Exception as e:
            print(f"  [Tavily] Batch {i//batch_size + 1} failed: {e}")
        time.sleep(0.5)

    print(f"  [Tavily] Extracted text from {len(extracted)}/{len(article_urls)} URLs")
    return extracted


# ==========================================
# 5b. WEEKLY PROJECT RESEARCH
# ==========================================

_PROJECT_SYSTEM_PROMPT = (
    "You are a Canadian infrastructure and capital markets researcher. "
    "Provide factual, sourced information about real capital projects in Canada. "
    "Be specific about project names, dollar values, proponents, and status. "
    "Only include real, verifiable projects. Do not fabricate."
)

_PROJECT_SCHEMA = """\
{
  "projects": [
    {
      "name": "Full official project name",
      "description": "One concise sentence (max 20 words) describing the project and its proponent",
      "province": "Exact Canadian province or territory name",
      "cma": "Census Metropolitan Area or nearest city/town",
      "sector": "One of: Energy | Mining | Transit | Housing | Defence | Manufacturing | Technology | Healthcare | Agriculture | Telecommunications | Ports & Logistics | Other",
      "naics_code": "NAICS code string, e.g. '21' or '31-33'",
      "tags": ["tag1", "tag2"],
      "value": "$X.XB or $XXXM — use '\\u2014' if unknown",
      "status": "One of: Announced | Approved | Under Construction | Operational | Completed | Cancelled",
      "completionDate": "Expected completion e.g. '2027' — use '' if unknown",
      "announced": "YYYY-MM-DD — use today if unknown",
      "sources": [
        {"id": 1, "title": "Publication \\u2014 Article Title, Month YYYY", "url": "direct link or ''"}
      ]
    }
  ]
}"""

WEEKLY_PROJECT_SECTORS = [
    ("Energy (Oil & Gas)",
     "New oil, gas, pipeline, or LNG capital projects announced in Canada this week — "
     "named proponents, CAD investment values, provinces, and current status."),
    ("Clean Energy",
     "New renewable energy, wind, solar, hydro, nuclear, hydrogen, or carbon capture projects "
     "announced in Canada this week — developer, value, province, status."),
    ("Mining",
     "New mining, potash, critical minerals, gold, copper, or mineral processing projects "
     "announced in Canada this week — operator, value, province, status."),
    ("Infrastructure",
     "New road, bridge, highway, tunnel, or civil infrastructure projects announced or approved "
     "in Canada this week — government funder, value, province."),
    ("Transit & Rail",
     "New urban transit, light rail, subway, GO train, or commuter rail projects announced in "
     "Canada this week — proponent, value, province, status."),
    ("Housing",
     "New large-scale housing developments, affordable housing, or mixed-use projects announced "
     "in Canada this week — developer, unit count or value, province."),
    ("Defence",
     "New defence procurement, military base construction, or national security capital projects "
     "announced in Canada this week — DND, contractor, value."),
    ("Healthcare",
     "New hospital, long-term care, cancer centre, or health facility construction announced in "
     "Canada this week — government funder, value, province, status."),
    ("Technology & Data",
     "New data centre, AI facility, semiconductor plant, or tech infrastructure projects "
     "announced in Canada this week — proponent, value, province."),
    ("Ports & Logistics",
     "New port expansion, intermodal terminal, warehouse, or logistics facility projects "
     "announced in Canada this week — operator, value, province."),
    ("Agriculture",
     "New agri-food processing plant, grain terminal, or agricultural infrastructure project "
     "announced in Canada this week — proponent, value, province."),
    ("Manufacturing",
     "New automotive, steel, chemicals, pulp, or advanced manufacturing investment announced "
     "in Canada this week — company, value, province, jobs created."),
    ("Telecommunications",
     "New telecom network expansion, 5G infrastructure, or rural broadband project announced "
     "in Canada this week — carrier, value, province."),
    ("Water & Wastewater",
     "New water treatment, wastewater, or flood mitigation infrastructure project announced "
     "in Canada this week — municipality, value, province."),
    ("Education",
     "New university building, college campus expansion, or major school construction announced "
     "in Canada this week — institution, value, province."),
    ("Tourism & Hospitality",
     "New resort, hotel, convention centre, or cultural infrastructure project announced in "
     "Canada this week — developer, value, province, status."),
]

DEEP_SWEEP_NAICS = [
    ("11",  "Agriculture & Agri-processing"),
    ("21",  "Mining, Oil & Gas Extraction"),
    ("22",  "Utilities & Energy"),
    ("23",  "Construction & Civil Infrastructure"),
    ("31",  "Food & Beverage Manufacturing"),
    ("32",  "Chemical & Plastics Manufacturing"),
    ("33",  "Primary & Fabricated Metal"),
    ("48",  "Air, Rail & Truck Transportation"),
    ("49",  "Pipeline & Water Transportation"),
    ("51",  "Information & Cultural Industries"),
    ("52",  "Finance & Insurance"),
    ("53",  "Real Estate"),
    ("54",  "Professional, Scientific & Tech Services"),
    ("56",  "Administrative & Support Services"),
    ("61",  "Education"),
    ("62",  "Healthcare & Social Assistance"),
    ("71",  "Arts, Entertainment & Recreation"),
    ("72",  "Accommodation & Food Services"),
    ("81",  "Other Services"),
    ("91",  "Defence & Public Administration"),
]

_WEEKLY_PROVINCES = [
    "Ontario", "Quebec", "Alberta", "British Columbia",
    "Saskatchewan", "Manitoba", "Nova Scotia", "New Brunswick",
    "Newfoundland and Labrador", "Prince Edward Island",
    "Yukon", "Northwest Territories", "Nunavut",
]

_PROV_WEEKLY_THRESHOLDS = {
    "Ontario": "$100M", "Quebec": "$50M", "Alberta": "$50M",
    "British Columbia": "$50M", "Saskatchewan": "$20M", "Manitoba": "$20M",
    "Nova Scotia": "$15M", "New Brunswick": "$15M",
    "Newfoundland and Labrador": "$15M", "Prince Edward Island": "$5M",
    "Yukon": "$3M", "Northwest Territories": "$3M", "Nunavut": "$3M",
}

_PROV_DEEP_THRESHOLDS = {
    "Ontario": "$200M", "Quebec": "$100M", "Alberta": "$100M",
    "British Columbia": "$100M", "Saskatchewan": "$30M", "Manitoba": "$25M",
    "Nova Scotia": "$15M", "New Brunswick": "$15M",
    "Newfoundland and Labrador": "$15M", "Prince Edward Island": "$5M",
    "Yukon": "$3M", "Northwest Territories": "$3M", "Nunavut": "$3M",
}


def _parse_projects_with_haiku(raw_text: str, province: str, context_label: str = "") -> list:
    """
    Use Claude Haiku 4.5 to parse a Perplexity result into structured project records.
    If province is a specific province name, forces all extracted projects to that province.
    If province is 'Canada', lets Haiku determine the province from context.
    """
    if not raw_text.strip():
        return []

    system_prompt = (
        "You are a data extraction assistant specializing in Canadian capital projects. "
        "Parse the provided text and return a valid JSON object matching the schema exactly. "
        "Only include projects that are real and clearly described in the source text. "
        "Do not fabricate projects or details not present in the source text. "
        "Return only the JSON object — no markdown fences, no explanation."
    )

    if province and province != "Canada":
        prov_instruction = f"Province: {province} (force all extracted projects to this province)"
    else:
        prov_instruction = (
            "Province: Determine from project context "
            "(set the exact Canadian province or territory name for each project)"
        )

    user_prompt = f"""Extract all capital projects from the text below.

{prov_instruction}
Context: {context_label}

Return only this JSON structure (no markdown, no explanation):
{_PROJECT_SCHEMA}

If no valid projects are found, return: {{"projects": []}}

SOURCE TEXT:
{raw_text}"""

    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = msg.content[0].text.strip()
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                projects = parsed.get("projects", [])
                if isinstance(projects, list):
                    # Force province if explicitly specified
                    if province and province != "Canada":
                        for p in projects:
                            p['province'] = province
                    return projects
            return []
        except json.JSONDecodeError as e:
            if attempt == 3:
                print(f"\n    [HAIKU JSON ERROR] {context_label}: {e}")
                return []
            time.sleep(1)
        except Exception as e:
            if attempt == 3:
                print(f"\n    [HAIKU ERROR] {context_label}: {e}")
                return []
            time.sleep(2 ** attempt)
    return []


def fetch_project_research(deep_sweep: bool = False) -> list:
    """
    Run project-finding Perplexity queries for the weekly pipeline.
    Weekly mode: 13 provincial + 16 sector + 2 status-change queries (~31 total).
    Deep sweep mode (--deep-sweep): adds 20 NAICS × 13 provinces = 260 extra queries.

    Returns a flat list of raw project dicts with 'province' field set.
    """
    print("\n[PROJECT RESEARCH] Running project queries...")
    all_projects  = []
    total_queries = 0

    def run_query(label: str, query: str, province: str = "Canada") -> None:
        nonlocal total_queries
        print(f"  {label}...", end=" ", flush=True)
        raw = _query_perplexity(query, label, system_prompt=_PROJECT_SYSTEM_PROMPT, max_tokens=1500)
        total_queries += 1
        time.sleep(2)
        if raw:
            projects = _parse_projects_with_haiku(raw, province, label)
            print(f"{len(projects)} found")
            all_projects.extend(projects)
        else:
            print("empty")

    # ── Weekly: 1 broad query per province ───────────────────────
    print("\n  [Weekly] Provincial queries (13)...")
    for prov in _WEEKLY_PROVINCES:
        thr = _PROV_WEEKLY_THRESHOLDS.get(prov, "$10M")
        run_query(
            prov,
            f"New major capital projects worth {thr} or more (CAD) announced, approved, or "
            f"reaching a milestone in {prov} this week — infrastructure, energy, mining, transit, "
            f"housing, defence, healthcare. Name the proponent, investment value, location, "
            f"and current status. Cite news sources with publication name and date.",
            province=prov,
        )

    # ── Weekly: sector-specific queries ──────────────────────────
    print("\n  [Weekly] Sector queries...")
    for sector_label, query in WEEKLY_PROJECT_SECTORS:
        run_query(sector_label, query)

    # ── Weekly: status change queries ────────────────────────────
    print("\n  [Weekly] Status change queries...")
    run_query(
        "Delays/Cancellations",
        "Canadian infrastructure or capital projects that announced significant delays, cost "
        "overruns, cancellations, or regulatory setbacks this week — named project, reason, "
        "revised timeline or cost, province. Only real, verified events from this week.",
    )
    run_query(
        "Milestones/Completions",
        "Canadian capital projects that broke ground, achieved a major construction milestone, "
        "received final approval, or reached completion this week — named project, proponent, "
        "value, province.",
    )

    # ── Monthly deep sweep (--deep-sweep flag only) ───────────────
    if deep_sweep:
        print(f"\n  [Deep Sweep] {len(DEEP_SWEEP_NAICS)} NAICS × {len(_WEEKLY_PROVINCES)} provinces "
              f"= {len(DEEP_SWEEP_NAICS) * len(_WEEKLY_PROVINCES)} queries...")
        six_months_ago = (date.today() - timedelta(days=180)).strftime("%B %Y")
        for prov in _WEEKLY_PROVINCES:
            thr = _PROV_DEEP_THRESHOLDS.get(prov, "$10M")
            print(f"\n    {prov}:")
            for naics_code, sector_label in DEEP_SWEEP_NAICS:
                run_query(
                    f"{naics_code}/{prov[:10]}",
                    f"Major {sector_label} (NAICS {naics_code}) projects worth {thr} or more (CAD) "
                    f"announced, approved, or under construction in {prov} since {six_months_ago}. "
                    f"List project name, proponent, value, status, completion date, and nearest city.",
                    province=prov,
                )

    print(f"\n  Project research complete: {total_queries} queries, "
          f"{len(all_projects)} raw projects found.")
    return all_projects


def extract_projects_from_rss(rss_items: list) -> list:
    """
    Extract structured capital project data directly from RSS news items
    using Claude Haiku — no Perplexity query needed.

    Filters project-relevant items, groups by province, then calls
    _parse_projects_with_haiku() on each group.  Returns a flat list of
    raw project dicts in the same format as fetch_project_research().
    """
    proj_items = rss_monitor.filter_project_relevant(rss_items)
    if not proj_items:
        print("  [RSS PROJECTS] No project-relevant items found in RSS feeds.")
        return []

    print(f"\n  [RSS PROJECTS] Extracting from {len(proj_items)} relevant RSS items...")

    # Group by province (federal items go under 'Canada')
    by_province: dict[str, list] = {}
    for item in proj_items:
        prov = item.get('province') or 'Canada'
        by_province.setdefault(prov, []).append(item)

    all_projects: list = []
    for province, items in sorted(by_province.items()):
        text = rss_monitor.format_for_context(items, max_items=20)
        if not text.strip():
            continue
        projects = _parse_projects_with_haiku(
            f"Government news releases from {province}:\n\n{text}",
            province if province != 'Canada' else 'Canada',
            f"RSS/{province[:15]}",
        )
        if projects:
            print(f"    {province}: {len(projects)} projects from RSS")
        all_projects.extend(projects)

    print(f"  [RSS PROJECTS] {len(all_projects)} total projects extracted from RSS")
    return all_projects


# ==========================================
# 4. CLAUDE HAIKU ANALYSIS (3 focused calls)
# ==========================================

_CLAUDE_SYSTEM = (
    "You are a Senior Canadian Macroeconomist and financial journalist. "
    "Write precise, data-driven analysis with specific figures, dates, and named entities. "
    "Never write generic commentary. Every sentence must reference a real event, figure, or data point. "
    "NEVER invent URLs — only cite URLs that appear in the provided source material. "
    "Output ONLY valid JSON matching the schema exactly. No markdown fences. No explanation before or after the JSON."
)

# Model routing: Opus for macro writing, Sonnet for extraction/secondary, Gemini for mechanical
_CLAUDE_MODEL = SONNET_MODEL  # default for backward compat


def _call_claude(prompt: str, label: str, max_tokens: int = 8096, model: str = '') -> dict:
    """Call Claude with specified model and parse JSON. Falls back to Gemini on parse failure."""
    use_model = model or _CLAUDE_MODEL
    raw_content = ""
    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=use_model,
                max_tokens=max_tokens,
                system=_CLAUDE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_content = msg.content[0].text.strip()
            # Strip accidental markdown fences
            if raw_content.startswith("```"):
                parts = raw_content.split("```")
                raw_content = parts[1] if len(parts) > 1 else raw_content
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            return json.loads(raw_content)
        except json.JSONDecodeError:
            if attempt == 3:
                print(f"    [CLAUDE JSON ERROR] {label} — trying Gemini repair...")
                return _repair_with_gemini(raw_content, label)
            time.sleep(1)
        except Exception as e:
            err_str = str(e).lower()
            # Opus 404 → automatic Sonnet fallback (API key may lack Opus access)
            if use_model == OPUS_MODEL and use_model != SONNET_MODEL and (
                'not_found' in err_str or '404' in err_str or 'could not resolve' in err_str
            ):
                print(f"    [MODEL FALLBACK] {use_model} unavailable — switching to {SONNET_MODEL}")
                use_model = SONNET_MODEL
                continue  # retry immediately with Sonnet, don't burn an attempt
            if attempt == 3:
                print(f"    [CLAUDE ERROR] {label}: {e}")
                return {}
            time.sleep(2 ** attempt)
    return {}


# ── Watchlist context builders ───────────────────────────────────────────────

def _build_canadian_officials_context() -> str:
    """Build VERIFIED CANADIAN OFFICIALS block from watchlist.json public_figures_canada."""
    figures = _WATCHLIST.get('public_figures_canada', [])
    if not figures:
        return ''
    lines = ['VERIFIED CANADIAN OFFICIALS (use these names and titles exactly):']
    for f in figures:
        name = f.get('name') or f.get('current_holder') or ''
        role = f.get('role') or ''
        entity = f.get('entity_name') or ''
        if name and role:
            lines.append(f'- {name}, {role}')
        elif name and entity:
            lines.append(f'- {name}, {entity}')
    lines.append('')
    lines.append('If an article mentions an official not on this list, use the name and title from the article. Never guess or invent titles.')
    return '\n'.join(lines)


def _build_global_officials_context() -> str:
    """Build VERIFIED GLOBAL OFFICIALS block from watchlist.json global_watchlist."""
    entries = _WATCHLIST.get('global_watchlist', [])
    if not entries:
        return ''
    # Group by jurisdiction
    by_jur: dict[str, list] = {}
    for e in entries:
        jur = e.get('jurisdiction') or 'Other'
        by_jur.setdefault(jur, []).append(e)
    lines = ['VERIFIED GLOBAL OFFICIALS (use these names and titles exactly):']
    for jur, officials in by_jur.items():
        parts = []
        for o in officials:
            name = o.get('current_holder') or o.get('entity_name') or ''
            role = o.get('role') or ''
            if name and role:
                parts.append(f'{name} ({role})')
        if parts:
            lines.append(f'{jur}: {", ".join(parts)}')
    lines.append('')
    lines.append('If an article mentions an official not on this list, use the name and title from the article.')
    return '\n'.join(lines)


def _build_provincial_officials_context(province: str) -> str:
    """Build VERIFIED [PROVINCE] OFFICIALS block from watchlist.json provincial_officials."""
    officials = _WATCHLIST.get('provincial_officials', [])
    if not officials:
        return ''
    # Map province names to abbreviations and vice versa
    _abbr_to_name = {
        'BC': 'British Columbia', 'AB': 'Alberta', 'SK': 'Saskatchewan',
        'MB': 'Manitoba', 'ON': 'Ontario', 'QC': 'Quebec',
        'NB': 'New Brunswick', 'NS': 'Nova Scotia', 'PE': 'Prince Edward Island',
        'NL': 'Newfoundland and Labrador', 'YT': 'Yukon',
        'NT': 'Northwest Territories', 'NU': 'Nunavut',
    }
    _name_to_abbr = {v: k for k, v in _abbr_to_name.items()}
    # Filter to this province
    prov_abbr = _name_to_abbr.get(province, province)
    filtered = [o for o in officials if o.get('jurisdiction') in (province, prov_abbr)]
    if not filtered:
        return ''
    lines = [f'VERIFIED {province.upper()} OFFICIALS (use these titles exactly):']
    for o in filtered:
        name = o.get('current_holder') or ''
        role = o.get('role') or ''
        entity = o.get('entity_name') or ''
        if name and role:
            lines.append(f'- {role}: {name}')
        elif name and entity:
            lines.append(f'- {entity}: {name}')
    lines.append('')
    lines.append('If an article names an official not on this list, use the name and title from the article.')
    return '\n'.join(lines)


def _repair_with_gemini(broken_json: str, label: str) -> dict:
    """Use Gemini 2.5 Flash to repair malformed JSON output from Claude."""
    if not broken_json:
        return {}
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=(
                "The following JSON is malformed. Return ONLY the corrected valid JSON. "
                "No markdown. No explanation.\n\n" + broken_json
            ),
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                max_output_tokens=32768,
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"    [GEMINI REPAIR ERROR] {label}: {e}")
        return {}


def _hard_data_summary(hard_data: dict, rss_items: list[dict] | None = None) -> str:
    """Format hard data into a concise string for Claude prompts."""
    commodity_lines = "\n".join(
        f"  {name}: {val}"
        for name, val in hard_data['commodities']['summary'].items()
    )
    indices_lines = "\n".join(
        f"  {i['name']}: {i['value']} (day {i['day']}, YoY {i['yy']})"
        for i in hard_data.get('financial_markets', {}).get('indices', [])
    )
    fx_lines = "\n".join(
        f"  {f['name']}: {f['value']} (day {f['day']}, YoY {f['yy']})"
        for f in hard_data.get('financial_markets', {}).get('fx', [])
    )

    # Primary source indicators block — Claude writes ABOUT these but must not change them
    pi = hard_data.get('primary_indicators', {})
    primary_section = ""
    if pi:
        nat_vals = pi.get('national', {}).get('values', {})
        primary_section = (
            "\n\nPRIMARY SOURCE INDICATORS (authoritative — reference these exact values in analysis):\n"
            f"  Real GDP (QoQ ann.): {nat_vals.get('realGdp', 'N/A')} (StatCan)\n"
            f"  CPI (YoY):           {nat_vals.get('cpi', 'N/A')} (StatCan)\n"
            f"  Unemployment:        {nat_vals.get('unemployment', 'N/A')} (StatCan)\n"
            f"  Housing Starts:      {nat_vals.get('housingStarts', 'N/A')} (CMHC/StatCan)\n"
        )
        ind_data = pi.get('industries', {})
        ind_lines = [
            f"    NAICS {code}: M/M={d.get('mm','N/A')}, Y/Y={d.get('yy','N/A')}"
            for code, d in ind_data.items()
            if not code.startswith('_')
        ]
        if ind_lines:
            primary_section += (
                "  Industry GDP — StatCan Table 36-10-0434-01 "
                "(use these M/M and Y/Y values in analysis):\n" +
                "\n".join(ind_lines) + "\n"
            )

    # Build government news context from RSS items (if available)
    rss_items = rss_items or hard_data.get('rss_items', [])
    news_ctx  = fetch_news_context(rss_items) if rss_items else hard_data.get('news_context', '')

    return (
        f"Bank of Canada Policy Rate: {hard_data['boc_rate']}\n\n"
        f"Commodity Prices (Yahoo Finance — authoritative):\n{commodity_lines}\n\n"
        f"Equity Indices (Yahoo Finance — authoritative):\n{indices_lines}\n\n"
        f"FX Rates (Yahoo Finance — authoritative):\n{fx_lines}\n\n"
        f"Government & Economic News (RSS — federal + project-relevant):\n{news_ctx}"
        f"{primary_section}"
    )


def _format_articles_for_prompt(articles: list[dict], max_chars: int = 20000) -> str:
    """Format extracted articles in structured format for Claude prompts.

    Each article formatted as:
      ARTICLE [N]:
      Source type: news_article | government_press_release | canada_gazette
      Headline: "Exact headline"
      URL: https://verified-url
      Text: [full article text]
    """
    if not articles:
        return "(no articles available)"
    lines = []
    total = 0
    for i, a in enumerate(articles, 1):
        url   = a.get('url', '')
        title = a.get('title', '')
        text  = a.get('text', '')[:1500]
        # Determine source type
        src_type = 'news_article'
        if a.get('feed_id') or a.get('feed_name'):
            src_type = 'government_press_release'
        elif 'gazette' in url.lower():
            src_type = 'canada_gazette'
        elif any(d in url for d in ('.gc.ca', 'canada.ca', '.gov.')):
            src_type = 'government_press_release'
        chunk = (
            f"ARTICLE [{i}]:\n"
            f"Source type: {src_type}\n"
            f"Headline: \"{title}\"\n"
            f"URL: {url}\n"
            f"Text: {text}\n"
        )
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return '\n'.join(lines)


def generate_claude_analysis(hard_data: dict, articles: list[dict],
                             rss_items: list[dict] | None = None) -> dict:
    """
    Four-call Claude pipeline with model routing:
      Call 1: Macro — Claude Opus (executive_summary, national, global, globalVectors, watchlist)
      Call 2: Industries + Markets — Claude Sonnet (goodsIndustries, servicesIndustries, yieldCurve)
      Call 3: Provincial — Claude Sonnet (all 13 provinces with analysis, indicators, projects)
      Call 4: Project extraction — Claude Sonnet (structured project records)

    Post-writing citation audit runs after each call.
    """
    print(f"\n[STEP 3] Claude analysis (4 calls, {len(articles)} articles)...")
    print(f"  Models: Opus={OPUS_MODEL}, Sonnet={SONNET_MODEL}")
    today_str    = date.today().strftime('%B %d, %Y')
    hard_summary = _hard_data_summary(hard_data, rss_items)

    # Build watchlist context blocks
    cdn_officials_ctx = _build_canadian_officials_context()
    global_officials_ctx = _build_global_officials_context()

    # Build consumer sentiment context (if available)
    sentiment_ctx = ''
    try:
        from sentiment import collect_sentiment, SENTIMENT_ENABLED
        if SENTIMENT_ENABLED:
            sentiment_data = collect_sentiment()
            if sentiment_data:
                topics = sentiment_data.get('topics', [])
                s_idx  = sentiment_data.get('sentiment_index', 'N/A')
                top_5  = topics[:5] if topics else []
                topic_lines = '\n'.join(
                    f"  - {t.get('topic', '?')}: {t.get('sentiment', '?')} "
                    f"(mentions: {t.get('mention_count', 0)}, sources: {t.get('source', '?')})"
                    for t in top_5
                )
                sentiment_ctx = (
                    f"\n\nCONSUMER SENTIMENT PULSE (from Reddit, Google Trends, CBC comments):\n"
                    f"  Sentiment Index: {s_idx} (0=very negative, 100=very positive)\n"
                    f"  Top concerns/topics ({len(topics)} total):\n{topic_lines}\n"
                    f"  Use this data to add a 1-2 sentence consumer pulse note in the executive summary.\n"
                )
                # Store for Firestore push later
                hard_data['_sentiment_result'] = sentiment_data
                print(f"  [Sentiment] Collected {len(topics)} topics, index={s_idx}")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [Sentiment] Collection failed (non-critical): {type(e).__name__}")

    # Split articles by topic for focused prompts
    economy_arts  = [a for a in articles if a.get('topic') == 'economy']
    project_arts  = [a for a in articles if a.get('topic') == 'project']
    all_arts_text = _format_articles_for_prompt(economy_arts[:50])

    # Collect citation audit results
    audit_results = []

    # ── CALL 1: National + Global + Watchlist (OPUS) ───────────────
    print(f"  [1/4] National + Global + Watchlist (Opus)...")

    call1 = _call_claude(f"""Today: {today_str}

HARD DATA (authoritative — use exact figures):
{hard_summary}

{cdn_officials_ctx}

{global_officials_ctx}

NEWS ARTICLES FROM GDELT + GOVERNMENT RSS (cite by article number — use URLs exactly as given):
{all_arts_text}
{sentiment_ctx}
{CITATION_RULES}

INSTRUCTIONS:
1. executive_summary: Up to 250 words. Structure: (a) single most important Canadian macro development this week; (b) 2-3 sentences on the national picture with specific data figures; (c) 1-2 sentences on the most significant provincial story; (d) 1 sentence on a major project or infrastructure development; (e) 1-2 sentences on commodities, yields, or CAD; (f) closing: key risk or opportunity ahead. Use <strong> tags on key figures. Bloomberg-style — direct, specific, no filler.
2. metrics: Fill ALL fields from the articles above EXCEPT the following — leave as empty string "": cpi, shelterCpi, unemployment, participation, realGdp. These are injected from StatCan/BoC primary APIs. bocRate must match the hard data exactly. Never estimate primary API fields.
3. national: 5-6 bullet points, up to 250 words total. Every bullet cites a specific event, figure, and date from the articles above. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-700 text-sm"><li>...</li></ul>
4. global: For each of US 🇺🇸, China 🇨🇳, EU 🇪🇺, UK 🇬🇧 — 3-4 bullets focused ONLY on direct Canada impact. Set ALL "indicators" fields to "" (injected from APIs). Format: <ul class="list-disc list-inside space-y-2 text-slate-700 text-sm"><li>...</li></ul>
5. globalVectors: One short sentence each for "us", "china", "eu".
6. watchlist: 15-25 upcoming events (next 4 weeks). Use exact dates from articles. High=rate decisions/CPI/jobs. Medium=GDP/trade/housing. Monitoring=international indirect exposures.

OUTPUT: Valid JSON only. No markdown. No text outside the JSON.

SCHEMA:
{{
    "executive_summary": "",
    "metrics": {{
        "realGdp": "", "nomGdp": "", "outputGap": "", "cpi": "", "shelterCpi": "",
        "bocRate": "{hard_data['boc_rate']}", "unemployment": "", "participation": "",
        "wageGrowth": "", "currentAccount": "", "agCrop": "", "farmCash": ""
    }},
    "national": {{
        "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700 text-sm\\"><li>specific bullet <sup>1</sup></li></ul>",
        "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": ""}}]
    }},
    "global": [
        {{"region": "United States", "emoji": "🇺🇸", "indicators": {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}}, "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700 text-sm\\"><li>Canada-impact bullet <sup>1</sup></li></ul>", "sources": [{{"id": 1, "title": "", "url": ""}}]}},
        {{"region": "China", "emoji": "🇨🇳", "indicators": {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}}, "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700 text-sm\\"><li>Canada-impact bullet <sup>1</sup></li></ul>", "sources": [{{"id": 1, "title": "", "url": ""}}]}},
        {{"region": "European Union", "emoji": "🇪🇺", "indicators": {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}}, "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700 text-sm\\"><li>Canada-impact bullet <sup>1</sup></li></ul>", "sources": [{{"id": 1, "title": "", "url": ""}}]}},
        {{"region": "United Kingdom", "emoji": "🇬🇧", "indicators": {{"gdp": "+X.X%", "cpi": "+X.X%", "rate": "X.XX%", "unemployment": "X.X%"}}, "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700 text-sm\\"><li>Canada-impact bullet <sup>1</sup></li></ul>", "sources": [{{"id": 1, "title": "", "url": ""}}]}}
    ],
    "globalVectors": {{"us": "", "china": "", "eu": ""}},
    "watchlist": [
        {{
            "date": "Mar 14",
            "week_label": "This Week",
            "institution": "Statistics Canada",
            "event_name": "Consumer Price Index",
            "description": "One sentence on what to watch and why it matters for Canada.",
            "impact": "high"
        }}
    ]
}}""", "call1-macro", max_tokens=8096, model=OPUS_MODEL)

    # Citation audit for Call 1
    audit1 = run_citation_audit(call1 or {}, 'call1-macro', anthropic_client=anthropic_client)
    audit1['_label'] = 'call1-macro'
    audit_results.append(audit1)

    # ── CALL 2: Industries + Markets (SONNET) ────────────────────
    print(f"  [2/4] Industries + yields (Sonnet)...")
    industry_arts_text = _format_articles_for_prompt(
        [a for a in economy_arts if any(kw in (a.get('title','') + a.get('text','')).lower()
                                        for kw in ('energy','oil','gas','mining','manufactur',
                                                   'agriculture','housing','finance','tech',
                                                   'health','yield','bond','retail','transit',
                                                   'transport','warehouse','wholesale','telecom',
                                                   'real estate','education','university',
                                                   'entertainment','hotel','tourism','waste',
                                                   'military','defense','government'))][:50]
    )

    call2 = _call_claude(f"""Today: {today_str}

HARD DATA:
{hard_summary}

NEWS ARTICLES (cite URLs verbatim — never invent):
{industry_arts_text}

INSTRUCTIONS:
1. goodsIndustries: Exactly 5 goods-producing sectors. For each:
   - code: NAICS code string exactly as listed below
   - name: sector display name
   - mm: set to "" — injected from StatCan Table 36-10-0434-01 primary API; must not be estimated
   - yy: set to "" — injected from StatCan; must not be estimated
   - analysis: up to 100 words as HTML bullets referencing the PRIMARY SOURCE INDICATOR M/M and Y/Y values provided in the hard data above. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-600 text-xs"><li>...</li></ul>
   - industrySources: array of {{id, title, url}}
   - isNegative: boolean — set based on the M/M value shown in PRIMARY SOURCE INDICATORS above
   - subsectors: 2-3 subsectors each with code, name, mm set to ""

   The 5 goods sectors (in this order):
   - code "11", name "Agriculture"
   - code "21", name "Mining & Energy"
   - code "22", name "Utilities"
   - code "23", name "Construction"
   - code "31-33", name "Manufacturing"

2. servicesIndustries: Exactly 15 services-producing sectors. Same format as goodsIndustries — mm and yy must be "" (injected from StatCan API).

   The 15 services sectors (in this order):
   - code "41", name "Wholesale Trade"
   - code "44-45", name "Retail Trade"
   - code "48-49", name "Transportation & Warehousing"
   - code "51", name "Information & Culture"
   - code "52", name "Finance & Insurance"
   - code "53", name "Real Estate"
   - code "54", name "Professional Services"
   - code "55", name "Management"
   - code "56", name "Admin & Waste Mgmt"
   - code "61", name "Education"
   - code "62", name "Health Care"
   - code "71", name "Entertainment & Recreation"
   - code "72", name "Accommodation & Food"
   - code "81", name "Other Services"
   - code "91", name "Public Administration"

3. yieldCurve: Full GoC curve 1M through 30Y. Use Perplexity yield data above as primary source; fall back to plausible estimates only if no data available. highlight: true on 2Y and 10Y only.

4. charts: yieldCurveCurrent (array of float values matching yieldCurve order), yieldCurveLastYear (array of floats for 1-yr prior, or empty array [] if unavailable).

CITATION RULES: Every industry analysis bullet ends with <sup>N</sup>. Only use URLs from the articles above.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "goodsIndustries": [
        {{
            "code": "11", "name": "Agriculture", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": ""}}],
            "isNegative": false,
            "subsectors": [{{"code": "", "name": "", "mm": ""}}]
        }}
    ],
    "servicesIndustries": [
        {{
            "code": "41", "name": "Wholesale Trade", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "", "url": ""}}],
            "isNegative": false,
            "subsectors": [{{"code": "", "name": "", "mm": ""}}]
        }}
    ],
    "yieldCurve": [
        {{"term": "1M", "yield": "", "highlight": false}},
        {{"term": "3M", "yield": "", "highlight": false}},
        {{"term": "6M", "yield": "", "highlight": false}},
        {{"term": "1Y", "yield": "", "highlight": false}},
        {{"term": "2Y", "yield": "", "highlight": true}},
        {{"term": "5Y", "yield": "", "highlight": false}},
        {{"term": "10Y", "yield": "", "highlight": true}},
        {{"term": "30Y", "yield": "", "highlight": false}}
    ],
    "charts": {{
        "yieldCurveCurrent": [],
        "yieldCurveLastYear": []
    }}
}}""", "call2-industries", max_tokens=8096, model=SONNET_MODEL)

    # Citation audit for Call 2
    audit2 = run_citation_audit(call2 or {}, 'call2-industries', anthropic_client=anthropic_client)
    audit2['_label'] = 'call2-industries'
    audit_results.append(audit2)

    # ── CALL 3: Provinces (SONNET) ────────────────────────────────
    print(f"  [3/4] Provinces (all 13, Sonnet)...")

    # Build provincial article context: matching articles + RSS items per province
    prov_arts_text = _format_articles_for_prompt(economy_arts[:60], max_chars=18000)
    rss_ctx        = rss_monitor.format_for_context(rss_items or [], max_items=60) if rss_items else ''

    # Build provincial officials context from watchlist (all provinces in one block)
    prov_officials_lines = []
    for prov_name in ['Ontario', 'Quebec', 'Alberta', 'British Columbia', 'Saskatchewan',
                      'Manitoba', 'Nova Scotia', 'New Brunswick', 'Newfoundland and Labrador',
                      'Prince Edward Island', 'Yukon', 'Northwest Territories', 'Nunavut']:
        ctx = _build_provincial_officials_context(prov_name)
        if ctx:
            prov_officials_lines.append(ctx)
    prov_officials_ctx = '\n'.join(prov_officials_lines)

    call3 = _call_claude(f"""Today: {today_str}
Bank of Canada Policy Rate: {hard_data['boc_rate']}

NEWS ARTICLES (cite by article number — use URLs exactly as given):
{prov_arts_text}

GOVERNMENT RSS NEWS RELEASES:
{rss_ctx[:8000]}

{prov_officials_ctx}

{CITATION_RULES}

INSTRUCTIONS — Generate the 'provinces' array for ALL 13 provinces and territories (in this order):
Ontario, Quebec, Alberta, British Columbia, Saskatchewan, Manitoba, Nova Scotia, New Brunswick, Newfoundland & Labrador, Prince Edward Island, Yukon, Northwest Territories, Nunavut

For EACH:
a) indicators: Set ALL four fields (gdp, unemployment, cpi, housingStarts) to "" — they will be overwritten from primary data APIs (StatCan) and must not be estimated or hallucinated.
b) analysis: 3-4 bullets of SPECIFIC events from the past 1-4 weeks. Name events, companies, figures, and dates. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
c) sources: Array matching bullet numbers. id, title (Publication — Article Title, Month YYYY), url (direct link or "" if uncertain).
d) projects: 2-4 major capital projects. Each: name, description (1 sentence, max 20 words, names the proponent), sector, value (e.g. "$4.2B"), status (Announced/Approved/Under Construction/Operational/Completed/Cancelled), completionDate (e.g. "2027" or ""), cma (nearest city/CMA), tags (array of 1-3 strings), sources (array with id/title/url).

BAD bullets: "Ontario's economy continues its growth trajectory" / "The sector is seeing significant investment"
GOOD bullets: "StatCan reported Ontario unemployment rose to 6.8% in March, up from 6.5% in February, driven by layoffs in the Kitchener-Waterloo tech corridor. <sup>1</sup>"

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "provinces": [
        {{
            "name": "Ontario",
            "indicators": {{"gdp": "+X.X%", "unemployment": "X.X%", "cpi": "+X.X%", "housingStarts": "XX,XXX"}},
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700\\"><li>specific event with figure and date. <sup>1</sup></li><li>another specific event. <sup>2</sup></li></ul>",
            "sources": [{{"id": 1, "title": "StatCan — Labour Force Survey, March 2026", "url": ""}}, {{"id": 2, "title": "Globe and Mail — Article Title, March 2026", "url": ""}}],
            "projects": [
                {{
                    "name": "Project Name",
                    "description": "One sentence max 20 words naming what it is and who is building it.",
                    "sector": "Energy",
                    "value": "$X.XB",
                    "status": "Under Construction",
                    "completionDate": "2027",
                    "cma": "Greater Toronto Area",
                    "tags": ["tag1", "tag2"],
                    "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": ""}}]
                }}
            ]
        }}
    ]
}}""", "call3-provinces", max_tokens=10000, model=SONNET_MODEL)

    # Citation audit for Call 3
    audit3 = run_citation_audit(call3 or {}, 'call3-provinces', anthropic_client=anthropic_client)
    audit3['_label'] = 'call3-provinces'
    audit_results.append(audit3)

    # ── CALL 4: Project extraction from GDELT articles ────────────
    print("  [4/4] Project extraction from articles...")
    proj_arts_text = _format_articles_for_prompt(project_arts[:60], max_chars=20000)

    _PROJ_EXTRACT_SCHEMA = """{
  "projects": [
    {
      "project_name": "Full official project name",
      "province": "Exact Canadian province or territory name",
      "cma": "Census Metropolitan Area or nearest city",
      "sector": "Energy | Mining | Transit | Housing | Defence | Manufacturing | Technology | Healthcare | Agriculture | Telecommunications | Ports & Logistics | Clean Energy | Water & Wastewater | Education | Other",
      "naics_code": "NAICS code string e.g. '21'",
      "tags": ["tag1", "tag2"],
      "estimated_value": "$X.XB or $XXXM or '' if unknown",
      "status": "Announced | Approved | Under Construction | Completed | Cancelled | Suspended",
      "detail": "2-3 sentence description of what the article reports about this project",
      "source": {"title": "article title", "url": "article URL verbatim", "date": "published date"}
    }
  ]
}"""

    call4_raw = _call_claude(f"""Today: {today_str}

PROJECT DISCOVERY ARTICLES (extract capital projects — use article URLs verbatim):
{proj_arts_text}

INSTRUCTIONS:
For each article that mentions a Canadian capital project worth $5M or more,
extract structured data. Only include real, clearly described projects.
Never fabricate project details not present in the articles.

Output ONLY valid JSON. No markdown. No text outside JSON.

SCHEMA:
{_PROJ_EXTRACT_SCHEMA}

If no projects found, return: {{"projects": []}}""",
        "call4-projects", max_tokens=8096, model=SONNET_MODEL)

    extracted_projects = (call4_raw or {}).get('projects', [])
    print(f"  [Call 4] Extracted {len(extracted_projects)} projects from articles")

    # ── Merge all four results ─────────────────────────────────────
    payload = {}
    payload.update(call1 or {})
    payload.update(call2 or {})
    if call3 and 'provinces' in call3:
        payload['provinces'] = call3['provinces']
    elif not payload.get('provinces'):
        payload['provinces'] = []

    # Store GDELT-extracted projects separately for Step 4a matching
    payload['_gdelt_projects'] = extracted_projects

    # ── Save citation audit log ────────────────────────────────────
    if audit_results:
        save_audit_log(audit_results)
        all_passed = all(a.get('passed', True) for a in audit_results)
        total_cites = sum(a.get('total_citations', 0) for a in audit_results)
        total_failed = sum(a.get('failed_count', 0) for a in audit_results)
        status = 'ALL PASSED' if all_passed else 'SOME FAILED (>30% removal — review before publish)'
        print(f"  [Citation Audit] {status}: {total_cites} citations, {total_failed} failed")
        payload['_citation_audit'] = {
            'passed': all_passed,
            'total_citations': total_cites,
            'total_failed': total_failed,
            'calls': [{
                'label': a.get('_label', ''),
                'passed': a.get('passed', True),
                'citations': a.get('total_citations', 0),
                'failed': a.get('failed_count', 0),
                'removal_pct': a.get('removal_pct', 0),
            } for a in audit_results],
        }

    print("  Claude analysis complete.")
    return payload


# ==========================================
# 6b. INDICATOR VALIDATION
# ==========================================

def _build_indicator_meta(nat: dict, boc_data: dict) -> dict:
    """Build indicatorMeta dict from primary-source national indicators."""
    meta = {}
    field_defs = {
        'cpi':           ('CPI YoY',        '%'),
        'unemployment':  ('Unemployment',    '%'),
        'bocRate':       ('BoC Rate',        '%'),
        'housingStarts': ('Housing Starts',  ''),
    }
    for field, (_label, _unit) in field_defs.items():
        if field == 'bocRate':
            cur  = boc_data.get('rate', '')
            prev = boc_data.get('prev', '')
            dt   = boc_data.get('date', '')
            src  = 'BoC'
        else:
            cur  = nat.get('values', {}).get(field, '')
            prev = nat.get('prev_values', {}).get(field, '')
            dt   = nat.get('obs_dates', {}).get(field, '')
            src  = nat.get('sources', {}).get(field, '')
        meta[field] = {
            'prev':    prev,
            'change':  _calc_change(cur, prev),
            'period':  _fmt_period(dt),
            'obsDate': dt,
            'source':  src,
            'context': '',
        }
    return meta


def generate_context_lines(ind_meta: dict, national_values: dict) -> dict:
    """Single Haiku call to generate plain-English context for each national indicator."""
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        items = []
        for field, m in ind_meta.items():
            cur = national_values.get(field, '')
            items.append(
                f"- {field}: value={cur}, prev={m.get('prev','')}, "
                f"change={m.get('change','')}, period={m.get('period','')}"
            )
        prompt = (
            "For each Canadian economic indicator below, write ONE specific sentence (10-15 words) "
            "explaining the key driver or market implication. Use concrete numbers where relevant. "
            "Respond with a JSON object: {\"field\": \"sentence\"}.\n\n"
            + "\n".join(items)
        )
        msg = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = msg.content[0].text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            lines = json.loads(json_match.group())
            print(f"  [CONTEXT LINES] Generated {len(lines)} context lines.")
            return lines
    except Exception as e:
        print(f"  [CONTEXT LINES] Failed (non-critical): {e}")
    return {}


def validate_indicators(final_payload: dict, primary: dict) -> None:
    """
    Cross-check every injected indicator in final_payload against primary_indicators.
    Logs a WARNING if the payload value does not match the API value.
    Does NOT modify the payload — the assembly steps have already overwritten everything.
    """
    print("\n[VALIDATION] Cross-checking indicator provenance...")
    mismatches = 0

    # National metrics
    m = final_payload.get('metrics', {})
    for field, api_val in primary.get('national', {}).get('values', {}).items():
        if not api_val:
            continue
        payload_val = m.get(field)
        if payload_val and payload_val not in ('N/A', api_val):
            print(f"  [WARN] national.{field}: payload='{payload_val}', api='{api_val}'")
            mismatches += 1

    # Industry M/M and Y/Y
    ind_data = primary.get('industries', {})
    for list_key in ('goodsIndustries', 'servicesIndustries'):
        for ind_entry in final_payload.get(list_key, []):
            code = (ind_entry.get('code') or '').strip()
            api_ind = ind_data.get(code) or ind_data.get(code.split('/')[0].strip(), {})
            for field in ('mm', 'yy'):
                api_val    = api_ind.get(field)
                payload_val = ind_entry.get(field)
                if (api_val and api_val != 'N/A' and
                        payload_val and payload_val not in ('N/A', api_val)):
                    print(f"  [WARN] industry[{code}].{field}: "
                          f"payload='{payload_val}', api='{api_val}'")
                    mismatches += 1

    if mismatches == 0:
        print("  All injected indicators match primary sources.")
    else:
        print(f"  {mismatches} mismatch(es) logged "
              "(payload already contains the correct API values).")


# ==========================================
# 7. FINAL PIPELINE
# ==========================================

def _check_stale_projects(db) -> None:
    """
    STEP 4b: Use Perplexity to check status of projects not seen in 4+ weeks.
    Updates Firestore directly. Non-critical — never raises.
    """
    stale_cutoff = (date.today() - timedelta(days=28)).isoformat()
    try:
        docs = db.collection('projects').where('lastSeen', '<', stale_cutoff).limit(10).stream()
        stale = list(docs)
        if not stale:
            print("  [Stale check] No projects older than 4 weeks.")
            return
        print(f"  [Stale check] Checking {len(stale)} stale projects via Perplexity...")
        for doc in stale:
            p = doc.to_dict()
            name     = p.get('name', '')
            province = p.get('province', '')
            if not name:
                continue
            print(f"    Querying: {name[:50]}...", end=" ", flush=True)
            result = _query_perplexity(
                f"What is the current status of '{name}' in {province}? "
                f"Has there been any construction progress, delays, budget changes, "
                f"or regulatory updates in the past 3 months?",
                label=name[:30],
                max_tokens=500,
            )
            time.sleep(2)
            if not result:
                # Flag as status unknown
                try:
                    doc.reference.update({
                        'lastSeen': date.today().isoformat(),
                        'statusNote': f"Status Unknown — Last Updated {date.today().isoformat()}",
                    })
                    print("flagged unknown")
                except Exception:
                    print("update failed")
                continue
            # Parse Perplexity result with Claude to extract structured update
            try:
                update_data = _call_claude(
                    f"Extract a structured status update from this text about '{name}':\n\n{result}\n\n"
                    f"Return JSON: {{\"status\": \"...\", \"detail\": \"1-3 sentence specific description\", "
                    f"\"source\": {{\"title\": \"...\", \"url\": \"\"}}}}",
                    label=f"stale/{name[:20]}", max_tokens=400
                )
                if update_data and update_data.get('detail'):
                    history_entry = {
                        'status': update_data.get('status', p.get('status', '')),
                        'date':   date.today().isoformat(),
                        'detail': update_data['detail'],
                        'source': update_data.get('source', {}),
                    }
                    from firebase_admin import firestore as _fs
                    doc.reference.update({
                        'lastSeen':      date.today().isoformat(),
                        'status':        update_data.get('status', p.get('status', '')),
                        'statusHistory': _fs.ArrayUnion([history_entry]),
                    })
                    print(f"updated -> {update_data.get('status','?')}")
                else:
                    print("no structured update")
            except Exception as e:
                print(f"parse error: {e}")
    except Exception as e:
        print(f"  [Stale check] Error: {e}")


def seed_projects(deep_sweep: bool = False) -> None:
    """
    --seed-projects: Full project seed from all sources.
    1. Government registries (IAAC, BC EAO, NRCan, Infrastructure Canada, BuyAndSell)
    2. GDELT backfill (30-day window)
    3. Perplexity gap fill (weekly project queries)
    """
    print("\n[SEED PROJECTS] Running full project seed...")

    # Tier 1: Government registries
    registry_projects = fetch_registry_projects(tavily_client=tavily_client)
    if registry_projects:
        # Convert registry format to flat project format expected by upsert_flat_projects
        flat = []
        for p in registry_projects:
            flat.append({
                'name':             p.get('name', ''),
                'province':         p.get('province', ''),
                'cma':              p.get('cma', ''),
                'sector':           p.get('sector', 'Other'),
                'value':            p.get('value', ''),
                'status':           p.get('status', 'Announced'),
                'description':      p.get('name', ''),
                'discovery_source': p.get('discovery_source', 'federal_registry'),
                'sources': [{'id': 1, 'title': p.get('discovery_source', ''),
                             'url': p.get('source_url', '')}],
                'announced':        date.today().isoformat(),
                'naics_code':       '',
                'tags':             [],
                'completionDate':   '',
            })
        upsert_flat_projects(db, flat)

    # Tier 2: GDELT 30-day backfill
    gdelt_arts = gdelt_monitor.fetch_gdelt_articles(days_back=30)
    proj_urls  = [a['url'] for a in gdelt_monitor.top_articles(gdelt_arts, max_total=100, topic_filter='project')]
    if proj_urls and tavily_client:
        extracted = extract_article_texts(proj_urls, batch_size=5)
        if extracted:
            # Use Claude to extract projects from these articles
            proj_arts_text = _format_articles_for_prompt(extracted, max_chars=20000)
            raw = _call_claude(
                f"Extract all Canadian capital projects from these articles.\n\n{proj_arts_text}\n\n"
                f"Return JSON: {{\"projects\": [{{\"project_name\": \"\", \"province\": \"\", "
                f"\"sector\": \"\", \"estimated_value\": \"\", \"status\": \"\", \"detail\": \"\", "
                f"\"source\": {{\"url\": \"\", \"title\": \"\", \"date\": \"\"}}}}]}}",
                "seed-projects", max_tokens=8096
            )
            gdelt_projects = (raw or {}).get('projects', [])
            if gdelt_projects:
                flat = [_normalize_extracted_project(p) for p in gdelt_projects]
                upsert_flat_projects(db, [p for p in flat if p])

    # Tier 3: Perplexity gap fill
    print("\n  [Seed] Perplexity gap fill...")
    research_projects = fetch_project_research(deep_sweep=deep_sweep)
    if research_projects:
        upsert_flat_projects(db, research_projects)

    print("\n[SEED PROJECTS] Complete.")


def _normalize_extracted_project(p: dict) -> dict | None:
    """Convert a Call 4 project extract to the flat project format."""
    name = p.get('project_name') or p.get('name') or ''
    if not name or len(name) < 5:
        return None
    src = p.get('source') or {}
    return {
        'name':             name,
        'province':         p.get('province', ''),
        'cma':              p.get('cma', ''),
        'sector':           p.get('sector', 'Other'),
        'naics_code':       p.get('naics_code', ''),
        'tags':             p.get('tags', []),
        'value':            p.get('estimated_value', ''),
        'status':           p.get('status', 'Announced'),
        'description':      p.get('detail', '')[:200],
        'discovery_source': 'gdelt_news',
        'sources': [{'id': 1, 'title': src.get('title', ''),
                     'url': src.get('url', ''), 'date': src.get('date', '')}],
        'announced':        src.get('date') or date.today().isoformat(),
        'completionDate':   '',
    }


def update_dashboard(deep_sweep: bool = False):
    try:
        # ── STEP 1: Hard Data ──────────────────────────────────────
        print("\n[STEP 1] Fetching hard data...")
        commodity_data    = get_live_commodities()
        financial_markets = get_financial_markets()
        boc_data          = get_boc_rate()
        yield_data        = get_goc_yields()

        # Government RSS feeds — ~80 feeds fetched concurrently
        days_back = 30 if deep_sweep else 7
        rss_items    = rss_monitor.fetch_all_feeds(days_back=days_back)
        statcan_inds = fetch_statcan_indicators()

        hard_data = {
            'commodities':       commodity_data,
            'financial_markets': financial_markets,
            'boc_rate':          boc_data['rate'],
            'rss_items':         rss_items,
        }

        # ── STEP 1b: Primary source indicators (consolidated) ────────
        primary_ind  = fetch_primary_indicators()
        national_ind = primary_ind['national']
        prov_ind     = primary_ind['provinces']
        global_ind   = primary_ind['global']
        hard_data['primary_indicators'] = primary_ind

        # ── STEP 2a: RSS already fetched above ────────────────────

        # ── STEP 2b: Government registries ────────────────────────
        registry_projects = fetch_registry_projects(tavily_client=tavily_client)

        # ── STEP 2c: GDELT news discovery ─────────────────────────
        print("\n[STEP 2c] GDELT news discovery...")
        gdelt_articles = gdelt_monitor.fetch_gdelt_articles(days_back=days_back)

        # ── STEP 2d: Tavily article extraction ────────────────────
        print("\n[STEP 2d] Tavily article extraction...")
        top_urls = [a['url'] for a in gdelt_monitor.top_articles(gdelt_articles, max_total=100)]
        extracted_articles = extract_article_texts(top_urls, batch_size=5)
        # Carry topic tag from GDELT metadata into extracted articles
        url_to_meta = {a['url']: a for a in gdelt_articles}
        for art in extracted_articles:
            meta = url_to_meta.get(art['url'], {})
            art['topic']   = meta.get('topic', 'economy')
            art['keyword'] = meta.get('keyword', '')

        # ── STEP 3: Claude Sonnet analysis ────────────────────────
        final_payload = generate_claude_analysis(hard_data, extracted_articles, rss_items)

        # ── STEP 4a: Inject authoritative hard data (overrides AI) ─
        final_payload['commodities']      = commodity_data['structured']
        final_payload['financialMarkets'] = financial_markets
        if yield_data:
            final_payload['yieldCurve'] = yield_data['yieldCurve']
            final_payload['charts']     = yield_data['charts']

        # ── STEP 4b: National metrics — API or N/A, never AI ───────
        m = final_payload.setdefault('metrics', {})
        m['bocRate'] = boc_data['rate']
        nat_src = {'bocRate': 'BoC'}
        # Fields that MUST come from a primary API (or N/A — never AI-estimated)
        for field, src_key in [('cpi', 'cpi'), ('unemployment', 'unemployment'),
                                ('housingStarts', 'housingStarts'), ('realGdp', 'realGdp')]:
            api_val = national_ind['values'].get(field)
            if api_val:
                m[field]       = api_val
                nat_src[field] = national_ind['sources'].get(src_key, 'StatCan')
            else:
                m[field]       = 'N/A'
                nat_src[field] = 'N/A'
        # shelterCpi is from the same StatCan release as CPI
        if m.get('cpi') == 'N/A':
            m['shelterCpi'] = 'N/A';  nat_src['shelterCpi'] = 'N/A'
        else:
            nat_src.setdefault('shelterCpi', 'StatCan')
        # Secondary fields — no real-time primary API; values from Claude analysis only
        for field in ('nomGdp', 'outputGap', 'participation',
                      'wageGrowth', 'currentAccount', 'agCrop', 'farmCash'):
            nat_src.setdefault(field, 'N/A')
        final_payload['indicatorSources'] = nat_src

        # ── STEP 4c: Global indicators — API or N/A, never AI ──────
        for entry in final_payload.get('global', []):
            region  = entry.get('region', '')
            real    = global_ind.get(region, {})
            ind     = entry.setdefault('indicators', {})
            ind_src = entry.setdefault('indicatorSources', {})
            for field in ('gdp', 'cpi', 'rate', 'unemployment'):
                api_val = real.get(field)
                if api_val:
                    ind[field]     = api_val
                    ind_src[field] = real.get(f'{field}_src', 'API')
                else:
                    ind[field]     = 'N/A'
                    ind_src[field] = 'N/A'

        # ── STEP 4d: Provincial indicators — API or N/A, never AI ──
        for prov in final_payload.get('provinces', []):
            prov_name = prov.get('name', '')
            ind = prov.setdefault('indicators', {})
            src = prov.setdefault('indicatorSources', {})
            real = prov_ind.get(prov_name, {})
            for field in ('unemployment', 'cpi', 'gdp', 'housingStarts'):
                api_val = real.get(field)
                if api_val:
                    ind[field] = api_val
                    src[field] = real.get(f'{field}_src', 'StatCan')
                else:
                    ind[field] = 'N/A'
                    src[field] = 'N/A'

        # ── STEP 4e: Indicator metadata (prev, change badge, obs date, context) ─
        final_payload['indicatorMeta'] = _build_indicator_meta(national_ind, boc_data)

        # Generate plain-English context lines via Haiku (non-critical)
        m_vals = final_payload.get('metrics', {})
        ctx = generate_context_lines(final_payload['indicatorMeta'], m_vals)
        for field, sentence in ctx.items():
            if field in final_payload['indicatorMeta']:
                final_payload['indicatorMeta'][field]['context'] = sentence

        # Staleness check — log if any obs date is older than 45 days
        stale_cutoff = (date.today() - timedelta(days=45)).isoformat()
        for field, m_entry in final_payload['indicatorMeta'].items():
            obs_dt = m_entry.get('obsDate', '')
            if obs_dt and obs_dt < stale_cutoff:
                print(f"  [STALE WARNING] {field}: obs date {obs_dt} is older than 45 days")

        # Provincial indicatorMeta — prev value + change badge per province
        for prov in final_payload.get('provinces', []):
            prov_name = prov.get('name', '')
            raw = prov_ind.get(prov_name, {})
            prov['indicatorMeta'] = {
                'unemployment': {
                    'prev':    raw.get('unemployment_prev', ''),
                    'change':  _calc_change(raw.get('unemployment', ''), raw.get('unemployment_prev', '')),
                    'period':  _fmt_period(raw.get('unemployment_date', '')),
                    'obsDate': raw.get('unemployment_date', ''),
                },
                'cpi': {
                    'prev':    raw.get('cpi_prev', ''),
                    'change':  _calc_change(raw.get('cpi', ''), raw.get('cpi_prev', '')),
                    'period':  _fmt_period(raw.get('cpi_date', '')),
                    'obsDate': raw.get('cpi_date', ''),
                },
                'housingStarts': {
                    'prev':    raw.get('housingStarts_prev', ''),
                    'change':  _calc_change(raw.get('housingStarts', ''), raw.get('housingStarts_prev', '')),
                    'period':  raw.get('housingStarts_date', ''),
                    'obsDate': raw.get('housingStarts_date', ''),
                },
                'gdp': {
                    'prev':    '',  # would need n=3 to compute prior-year growth
                    'change':  '',
                    'period':  raw.get('gdp_date', ''),  # e.g. "2024"
                    'obsDate': raw.get('gdp_date', ''),
                },
            }

        # ── STEP 4f: Industry indicators — API or N/A, never AI ────
        ind_api = primary_ind['industries']
        for list_key in ('goodsIndustries', 'servicesIndustries'):
            for ind_entry in final_payload.get(list_key, []):
                code = (ind_entry.get('code') or '').strip()
                # Try exact match, then first segment of "21/22"-style codes
                api_data = ind_api.get(code) or ind_api.get(code.split('/')[0].strip())
                if api_data and api_data.get('src') != 'N/A':
                    ind_entry['mm']           = api_data.get('mm', 'N/A')
                    ind_entry['yy']           = api_data.get('yy', 'N/A')
                    ind_entry['isNegative']   = (ind_entry['mm'] or '').startswith('-')
                    ind_entry['indicatorSrc'] = api_data.get('src', 'StatCan')
                else:
                    ind_entry['mm']           = 'N/A'
                    ind_entry['yy']           = 'N/A'
                    ind_entry['isNegative']   = False
                    ind_entry['indicatorSrc'] = 'N/A'
                # Subsectors: no 3-digit StatCan data fetched — set N/A
                for sub in ind_entry.get('subsectors', []):
                    sub['mm'] = 'N/A'

        # ── STEP 4g: Validate indicator provenance ──────────────────
        validate_indicators(final_payload, primary_ind)

        # ── STEP 4e: Verify source URLs ─────────────────────────────
        verify_source_urls(final_payload)

        # ── STEP 4a: Passive project matching (GDELT + RSS extractions) ─
        if final_payload.get('provinces'):
            upsert_projects(db, final_payload['provinces'])

        # Projects extracted by Claude Call 4 from GDELT articles
        gdelt_projects = final_payload.pop('_gdelt_projects', [])
        if gdelt_projects:
            flat = [_normalize_extracted_project(p) for p in gdelt_projects]
            upsert_flat_projects(db, [p for p in flat if p])

        # RSS project extraction (free — no Perplexity needed)
        rss_projects = extract_projects_from_rss(rss_items)
        if rss_projects:
            upsert_flat_projects(db, rss_projects)

        # Registry projects
        if registry_projects:
            flat = []
            for p in registry_projects:
                flat.append({
                    'name':             p.get('name', ''),
                    'province':         p.get('province', ''),
                    'cma':              '',
                    'sector':           p.get('sector', 'Other'),
                    'naics_code':       '',
                    'tags':             [],
                    'value':            p.get('value', ''),
                    'status':           p.get('status', 'Announced'),
                    'description':      p.get('name', ''),
                    'discovery_source': p.get('discovery_source', 'federal_registry'),
                    'sources': [{'id': 1, 'title': p.get('discovery_source', ''),
                                 'url': p.get('source_url', '')}],
                    'announced':        date.today().isoformat(),
                    'completionDate':   '',
                })
            upsert_flat_projects(db, flat)

        # ── STEP 4b: Stale project checks (Perplexity) ─────────────
        print("\n[STEP 4b] Checking stale projects...")
        _check_stale_projects(db)

        # ── STEP 5d: StatCan indicators snapshot ───────────────────
        save_statcan_indicators(db, statcan_inds)

        # ── STEP 6: Timeseries ─────────────────────────────────────
        append_to_timeseries(final_payload, financial_markets, boc_data['rate'])

        # ── Edition string ─────────────────────────────────────────
        toronto_tz = pytz.timezone('America/Toronto')
        today      = datetime.now(toronto_tz)
        last_week  = today - timedelta(days=7)
        final_payload["edition"] = (
            f"EDITION: {last_week.strftime('%b %d').upper()} – "
            f"{today.strftime('%b %d').upper()} // STATUS: AI-SYNTHESIZED"
        )

        # ── STEP 6b: Consumer sentiment to Firestore ────────────────
        sentiment_result = hard_data.get('_sentiment_result')
        if sentiment_result:
            try:
                db.collection('newsletters').document('latest_sentiment').set({
                    'updatedAt': date.today().isoformat(),
                    'consumer_sentiment': sentiment_result,
                })
                print("  [Sentiment] Saved to Firestore")
            except Exception as e:
                print(f"  [Sentiment] Firestore write failed (non-critical): {e}")

        # ── STEP 7: Push to Firestore ──────────────────────────────
        print("\n[STEP 7] Pushing to Firestore...")
        dated_id = today.strftime('%Y-%m-%d')
        db.collection('newsletters').document('latest').set(final_payload)
        db.collection('newsletters').document(dated_id).set(final_payload)
        print("[OK] Dashboard successfully updated.")

    except Exception as e:
        import traceback
        print(f"[ERROR] Pipeline failed: {e}")
        traceback.print_exc()


def audit_all_citations():
    """Link rot audit: re-verify ALL URLs in /projects and /newsletters, archive dead links."""
    from url_verify import verify_url as _vurl, quick_reject as _qr
    from wayback import save_page as _wsave

    print(f"\n{'='*70}")
    print(f"  --audit-citations: Link Rot Audit")
    print(f"{'='*70}\n")

    total = 0
    passed = 0
    dead_archived = 0
    dead_unarchived = 0
    failures = []

    # Check all project source URLs
    print("  Checking /projects collection...")
    for snap in db.collection('projects').stream():
        doc = snap.to_dict()
        name = doc.get('name', '(unnamed)')
        for entry in (doc.get('statusHistory') or []):
            src = entry.get('source', {})
            url = src.get('url', '')
            if not url:
                continue
            total += 1
            if _qr(url):
                continue
            result = _vurl(url, name)
            if result.get('accepted'):
                passed += 1
            else:
                # Dead link — check for archive
                archive_url = src.get('archive_url', '')
                if archive_url:
                    entry['link_status'] = 'link_rotted_archived'
                    dead_archived += 1
                else:
                    # Attempt Wayback save
                    saved = _wsave(url)
                    if saved:
                        entry['link_status'] = 'link_rotted_archived'
                        entry.setdefault('source', {})['archive_url'] = saved
                        dead_archived += 1
                    else:
                        entry['link_status'] = 'link_rotted_unarchived'
                        dead_unarchived += 1
                failures.append({
                    'name': name,
                    'url': url,
                    'reason': result.get('reason', 'dead'),
                    'has_archive': bool(archive_url or (saved if 'saved' in dir() else False)),
                })

    # Check newsletter citation URLs
    print("  Checking /newsletters/latest citations...")
    latest = db.collection('newsletters').document('latest').get()
    if latest.exists:
        payload = latest.to_dict()
        for section_key in ('national', 'global', 'provinces', 'goodsIndustries', 'servicesIndustries'):
            _audit_section_urls(payload, section_key, failures, _vurl, _qr)

    dead_total = dead_archived + dead_unarchived
    print(f"\n  Total URLs checked: {total}")
    print(f"  Passed:             {passed}")
    print(f"  Dead (archived):    {dead_archived}")
    print(f"  Dead (unarchived):  {dead_unarchived}")

    if failures:
        audit_file = f'link_audit_{date.today().isoformat()}.txt'
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write(f"Link Rot Audit — {date.today().isoformat()}\n{'='*60}\n\n")
            for fl in failures:
                archive_note = ' (has archive)' if fl.get('has_archive') else ' (NO archive)'
                f.write(f"Project: {fl['name']}\n  URL: {fl['url']}\n  "
                        f"Reason: {fl['reason']}{archive_note}\n\n")
            f.write(f"\nSummary: {passed} OK, {dead_archived} dead+archived, "
                    f"{dead_unarchived} dead+unarchived out of {total}\n")
        print(f"  Report saved to {audit_file}")


def _audit_section_urls(payload, section_key, failures, _vurl, _qr):
    """Helper: check source URLs in a payload section."""
    data = payload.get(section_key)
    if not data:
        return
    items = data if isinstance(data, list) else [data]
    for item in items:
        for src in (item.get('sources') or []) + (item.get('industrySources') or []):
            url = src.get('url', '')
            if url and not _qr(url):
                result = _vurl(url, src.get('title', ''))
                if not result.get('accepted'):
                    failures.append({
                        'name': section_key,
                        'url': url,
                        'reason': result.get('reason', 'dead'),
                        'has_archive': False,
                    })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CAN-MACRO Dashboard Pipeline")
    parser.add_argument(
        '--deep-sweep', action='store_true',
        help='Monthly deep NAICS sweep (20 sectors x 13 provinces = 260 extra Perplexity queries)'
    )
    parser.add_argument(
        '--test-feeds', action='store_true',
        help='Test all government RSS feed URLs and report which are live/dead. Does not run the pipeline.'
    )
    parser.add_argument(
        '--seed-projects', action='store_true',
        help='Full project seed from all sources: registries + GDELT + Perplexity gap fill.'
    )
    parser.add_argument(
        '--audit-citations', action='store_true',
        help='Re-verify ALL URLs in DB + newsletter. Flag dead links, attempt Wayback archive.'
    )
    args = parser.parse_args()

    if args.test_feeds:
        rss_monitor.test_feeds()
    elif args.seed_projects:
        seed_projects(deep_sweep=args.deep_sweep)
    elif args.audit_citations:
        audit_all_citations()
    else:
        update_dashboard(deep_sweep=args.deep_sweep)
