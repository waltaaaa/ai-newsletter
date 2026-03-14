"""
update_dashboard.py — CAN-MACRO Strategic Dashboard Pipeline

Architecture (3 layers):
  DATA COLLECTION  — Government APIs, RSS feeds (~201), GDELT news, Google News RSS,
                     registries, Tavily enrichment, Yahoo Finance (all facts, no AI)
  ANALYSIS         — Claude Sonnet writes all analysis from collected facts
                     (gap analysis, extraction recovery, dedup QA, meta-analysis, briefing)
  STATUS TRACKING  — Stale project checks (projects unseen 4+ weeks)

Discovery Pipeline:
  Tier 1  Government registries — IAAC, BC EAO, NRCan, Infrastructure Canada, BuyAndSell
  Tier 2  Google News RSS — 759 compound queries as free RSS feeds (replaces Gemini grounded search)
  Tier 3  GDELT validation — Reduced to ~200 queries, three-layer filter → Tavily
  Tier 3B Perplexity gap-fill — Monthly deep-sweep only (13 queries)
  Tier 4  RSS feeds — ~201 feeds (government + CBC + CTV + Postmedia + industry)
  Tier 5  Consumer sentiment — Reddit, Google Trends, CBC comments, Gemini extraction
  Tier 13 Municipal development applications — Open Data APIs + HTML portals
  Tier 14 Institutional capital plans — U15 universities, polytechnics, hospitals

Flags:
  python update_dashboard.py               — normal weekly run
  python update_dashboard.py --deep-sweep  — monthly full sweep (all tiers at max)
  python update_dashboard.py --test-feeds  — test all RSS feed URLs
  python update_dashboard.py --seed-projects — full project seed (registries + GDELT)
  python update_dashboard.py --test-sentiment — run sentiment collection only, print results
  python update_dashboard.py --test-queries  — GDELT dry run: hit counts per query
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

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
from dotenv import load_dotenv
from project_sync import upsert_projects, upsert_flat_projects
from gov_sources import fetch_statcan_indicators, save_statcan_indicators, fetch_registry_projects
from pipeline_config import SONNET_MODEL, GEMINI_MODEL, GEMINI_SEARCH_ENABLED, CLAUDE_COST_CAP_USD
from citation_audit import (
    CITATION_RULES, run_citation_audit, save_audit_log,
)
from google_news_rss_search import run_google_news_search
# Perplexity removed — function covered by compound queries + enrichment tiers
from article_filter import filter_articles
import local_llm
from quality_report import generate_quality_report
from project_dedup import deduplicate_projects
from project_schema import normalize_project_type, is_brownfield
from db import (init_db, get_db, get_all_projects, get_projects, save_indicator, get_indicators,
                save_briefing, get_latest_briefing, save_dashboard_state, get_dashboard_state,
                save_trend_snapshot, save_timeseries_point,
                save_checkpoint, get_checkpoint)
from pipeline_logging import PipelineRunLogger
from pipeline_store import cache as _cache
from export_dashboard import export_all
import service_health

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


ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "").strip()
TAVILY_API_KEY     = os.environ.get("TAVILY_API_KEY", "").strip()
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

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
gemini_client  = genai.Client(api_key=GEMINI_API_KEY)

# ── Claude API cost tracking (per-run) ────────────────────────────────────────
# Sonnet 4.6: $3/MTok input, $15/MTok output
_CLAUDE_INPUT_COST_PER_MTOK = 3.0
_CLAUDE_OUTPUT_COST_PER_MTOK = 15.0
_claude_run_cost_usd = 0.0
_claude_run_tokens = {"input": 0, "output": 0}


class CostCapExceeded(Exception):
    """Raised when Claude API cost exceeds the per-run cap."""
    pass

# Initialize SQLite connection
conn = init_db()

# Initialize Tavily credit tracking with SQLite connection
from tavily_search import set_tracking_db, can_use_tavily
set_tracking_db(conn)

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

    # Check cache first (12-hour TTL — commodities update daily)
    cached = _cache.get("yfinance:commodities")
    if cached is not None:
        print(f"  Using cached commodity data ({len(cached.get('structured', []))} categories)")
        return cached

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

    result = {"structured": structured, "summary": summary}
    print(f"  Fetched {sum(len(c['items']) for c in structured)} commodities across {len(structured)} categories.")
    _cache.set("yfinance:commodities", result, ttl_hours=12)
    return result


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

    # Check cache first (12-hour TTL)
    cached = _cache.get("yfinance:markets")
    if cached is not None:
        print(f"  Using cached market data ({len(cached.get('indices', []))} indices)")
        return cached

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

    result = {"indices": indices, "fx": fx}
    print(f"  Fetched {len(indices)} indices, {len(fx)} FX pairs.")
    _cache.set("yfinance:markets", result, ttl_hours=12)
    return result


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
    except Exception as e:
        print(f"  [WARN] BoC rate fetch failed: {e}")
        return {'rate': None, 'prev': '', 'date': ''}


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
    except Exception as e:
        print(f"  [WARN] BoC rate fetch attempt 1 failed: {e}")
    time.sleep(5)
    try:
        return _fetch()
    except Exception as e:
        print(f"  [WARN] BoC rate fetch attempt 2 failed: {e}")
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

    # Batch fetch CPI + unemployment + employment rate + participation rate — n=14 for YoY
    wds_data = _statcan_wds([_CPI_VECTOR, _UNEMP_VECTOR, _EMPRATE_VECTOR, _PARTRATE_VECTOR], n=14)

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
        except Exception as e:
            print(f"  [WARN] CPI parsing failed: {e}")
    if len(cpi_obs) >= 14:
        try:
            prev_latest   = float(cpi_obs[-2]['value'])
            prev_year_ago = float(cpi_obs[-14]['value'])
            prev_yoy      = ((prev_latest - prev_year_ago) / prev_year_ago) * 100
            prev_values['cpi'] = f"+{prev_yoy:.1f}%" if prev_yoy >= 0 else f"{prev_yoy:.1f}%"
        except Exception as e:
            print(f"  [WARN] CPI previous value parsing failed: {e}")

    # Unemployment rate — latest observation
    unemp_obs = wds_data.get(_UNEMP_VECTOR, [])
    if unemp_obs:
        try:
            values['unemployment']    = f"{float(unemp_obs[-1]['value']):.1f}%"
            sources['unemployment']   = 'StatCan'
            obs_dates['unemployment'] = unemp_obs[-1].get('refPer', '')
        except Exception as e:
            print(f"  [WARN] Unemployment parsing failed: {e}")
    if len(unemp_obs) >= 2:
        try:
            prev_values['unemployment'] = f"{float(unemp_obs[-2]['value']):.1f}%"
        except Exception as e:
            print(f"  [WARN] Unemployment previous value parsing failed: {e}")

    # Employment rate — latest observation
    emprate_obs = wds_data.get(_EMPRATE_VECTOR, [])
    if emprate_obs:
        try:
            values['employmentRate']    = f"{float(emprate_obs[-1]['value']):.1f}%"
            sources['employmentRate']   = 'StatCan'
            obs_dates['employmentRate'] = emprate_obs[-1].get('refPer', '')
        except Exception as e:
            print(f"  [WARN] Employment rate parsing failed: {e}")
    if len(emprate_obs) >= 2:
        try:
            prev_values['employmentRate'] = f"{float(emprate_obs[-2]['value']):.1f}%"
        except Exception as e:
            print(f"  [WARN] Employment rate previous value parsing failed: {e}")

    # Participation rate — latest observation
    partrate_obs = wds_data.get(_PARTRATE_VECTOR, [])
    if partrate_obs:
        try:
            values['participationRate']    = f"{float(partrate_obs[-1]['value']):.1f}%"
            sources['participationRate']   = 'StatCan'
            obs_dates['participationRate'] = partrate_obs[-1].get('refPer', '')
        except Exception as e:
            print(f"  [WARN] Participation rate parsing failed: {e}")
    if len(partrate_obs) >= 2:
        try:
            prev_values['participationRate'] = f"{float(partrate_obs[-2]['value']):.1f}%"
        except Exception as e:
            print(f"  [WARN] Participation rate previous value parsing failed: {e}")

    # Housing Starts — CMHC SAAR from CMHC monthly news release (direct source)
    starts = _cmhc_housing_starts()
    if starts is not None:
        values['housingStarts']  = f"{starts:,.0f}"
        sources['housingStarts'] = 'CMHC'

    print(f"  CPI={values.get('cpi','N/A')}  Unemployment={values.get('unemployment','N/A')}  "
          f"EmpRate={values.get('employmentRate','N/A')}  PartRate={values.get('participationRate','N/A')}  "
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

# ── Provincial employment rate — StatCan WDS vector IDs ──────────────────────
# Table 14-10-0287-01 (PID 14100287): Employment rate, both sexes, 15 years+, SA
_PROV_EMPRATE_VIDS = {
    "Newfoundland and Labrador": 2062998,
    "Prince Edward Island":      2063187,
    "Nova Scotia":               2063376,
    "New Brunswick":             2063565,
    "Quebec":                    2063754,
    "Ontario":                   2063943,
    "Manitoba":                  2064132,
    "Saskatchewan":              2064321,
    "Alberta":                   2064510,
    "British Columbia":          2064699,
}

# ── Provincial participation rate — StatCan WDS vector IDs ───────────────────
# Table 14-10-0287-01 (PID 14100287): Participation rate, both sexes, 15 years+, SA
_PROV_PARTRATE_VIDS = {
    "Newfoundland and Labrador": 2062992,
    "Prince Edward Island":      2063181,
    "Nova Scotia":               2063370,
    "New Brunswick":             2063559,
    "Quebec":                    2063748,
    "Ontario":                   2063937,
    "Manitoba":                  2064126,
    "Saskatchewan":              2064315,
    "Alberta":                   2064504,
    "British Columbia":          2064693,
}

# ── National employment and participation — StatCan WDS vector IDs ───────────
_EMPRATE_VECTOR   = 2062809   # Table 14-10-0287-01, Employment rate Canada SA
_PARTRATE_VECTOR  = 2062803   # Table 14-10-0287-01, Participation rate Canada SA

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

    # Batch 1: unemployment (10) + CPI (10) + employment rate (10) + participation rate (10) — n=14
    all_vids = (list(_PROV_UNEMP_VIDS.values()) + list(_PROV_CPI_VIDS.values())
                + list(_PROV_EMPRATE_VIDS.values()) + list(_PROV_PARTRATE_VIDS.values()))
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
            except Exception as e:
                print(f"  [WARN] Provincial unemployment ({prov}): {e}")

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
            except Exception as e:
                print(f"  [WARN] Provincial CPI ({prov}): {e}")

    # Employment rate — latest value (SA, both sexes, 15+, Table 14-10-0287-01)
    for prov, vid in _PROV_EMPRATE_VIDS.items():
        obs = data.get(vid, [])
        if obs:
            try:
                val = float(obs[-1]['value'])
                if 30.0 <= val <= 80.0:
                    updates = {
                        'employmentRate':      f"{val:.1f}%",
                        'employmentRate_src':  'StatCan',
                        'employmentRate_date': obs[-1].get('refPer', ''),
                    }
                    if len(obs) >= 2:
                        prev_val = float(obs[-2]['value'])
                        if 30.0 <= prev_val <= 80.0:
                            updates['employmentRate_prev'] = f"{prev_val:.1f}%"
                    result.setdefault(prov, {}).update(updates)
            except Exception as e:
                print(f"  [WARN] Provincial employment rate ({prov}): {e}")

    # Participation rate — latest value (SA, both sexes, 15+, Table 14-10-0287-01)
    for prov, vid in _PROV_PARTRATE_VIDS.items():
        obs = data.get(vid, [])
        if obs:
            try:
                val = float(obs[-1]['value'])
                if 40.0 <= val <= 80.0:
                    updates = {
                        'participationRate':      f"{val:.1f}%",
                        'participationRate_src':  'StatCan',
                        'participationRate_date': obs[-1].get('refPer', ''),
                    }
                    if len(obs) >= 2:
                        prev_val = float(obs[-2]['value'])
                        if 40.0 <= prev_val <= 80.0:
                            updates['participationRate_prev'] = f"{prev_val:.1f}%"
                    result.setdefault(prov, {}).update(updates)
            except Exception as e:
                print(f"  [WARN] Provincial participation rate ({prov}): {e}")

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
            except Exception as e:
                print(f"  [WARN] Provincial GDP ({prov}): {e}")

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
    # Check cache first (24hr TTL — these indicators change slowly)
    if _cache:
        cached = _cache.get("global_indicators")
        if cached:
            print("Fetching global indicators from cache (24hr TTL)...")
            return cached
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

    # Cache for 24 hours
    if _cache:
        _cache.set("global_indicators", result, ttl_hours=24)
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
        except Exception as e:
            print(f"  [WARN] Quarterly GDP parsing failed: {e}")

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


def _archive_indicators_to_history(primary_ind: dict) -> None:
    """Write each indicator value to the indicator_history table for trend tracking.

    Schema per record: {indicator_name, province, period, value, unit, source, frequency, backfilled}
    """
    today_str = date.today().isoformat()
    count = 0

    # National indicators
    nat_vals = primary_ind.get('national', {}).get('values', {})
    nat_srcs = primary_ind.get('national', {}).get('sources', {})
    for field, value in nat_vals.items():
        if not value or value == 'N/A':
            continue
        save_indicator(conn, {
            'indicator': field,
            'province': 'national',
            'date': today_str,
            'value': str(value),
            'unit': '%' if any(k in field.lower() for k in ['rate', 'cpi', 'gdp', 'unemployment']) else '',
            'source': nat_srcs.get(field, ''),
            'frequency': 'monthly',
            'backfilled': False,
        })
        count += 1

    # Provincial indicators
    for province, prov_data in primary_ind.get('provinces', {}).items():
        for field, value in prov_data.items():
            if field.endswith('_src') or not value or value == 'N/A':
                continue
            save_indicator(conn, {
                'indicator': field,
                'province': province,
                'date': today_str,
                'value': str(value),
                'unit': '%' if any(k in field.lower() for k in ['rate', 'cpi', 'unemployment']) else '',
                'source': prov_data.get(f'{field}_src', ''),
                'frequency': 'monthly',
                'backfilled': False,
            })
            count += 1

    print(f"  [HISTORY] Archived {count} indicator values to indicator_history")


def _archive_market_data_to_history(financial_markets: dict, commodity_data: dict, yield_data: dict) -> None:
    """Save financial market data to indicator_history so it exports to indicators.json."""
    today_str = date.today().isoformat()
    count = 0

    def _save(name, value_str, unit='', source='Yahoo Finance'):
        nonlocal count
        if not value_str:
            return
        try:
            val = str(value_str).replace('$', '').replace(',', '').replace('%', '').strip()
            float(val)  # validate it's numeric
        except (ValueError, TypeError):
            return
        save_indicator(conn, {
            'indicator': name,
            'province': 'national',
            'date': today_str,
            'value': val,
            'unit': unit,
            'source': source,
            'frequency': 'daily',
            'backfilled': False,
        })
        count += 1

    # Equity indices
    IDX_MAP = {
        'TSX Composite': 'tsx_composite', 'S&P/TSX': 'tsx_composite',
        'S&P 500': 'sp500', 'Dow Jones': 'djia', 'NASDAQ': 'nasdaq',
        'FTSE 100': 'ftse100', 'DAX': 'dax', 'Nikkei 225': 'nikkei225',
    }
    for idx in financial_markets.get('indices', []):
        name = IDX_MAP.get(idx.get('name', ''))
        if name:
            _save(name, idx.get('value'), 'pts')

    # FX pairs
    FX_MAP = {
        'CAD/USD': 'cadusd', 'EUR/USD': 'eurusd',
        'USD/CNY': 'usdcny', 'USD/JPY': 'usdjpy',
    }
    for fx in financial_markets.get('fx', []):
        name = FX_MAP.get(fx.get('name', ''))
        if name:
            _save(name, fx.get('value'))

    # Commodities
    COMM_MAP = {
        'Crude Oil (WTI)': 'wti', 'Crude Oil (Brent)': 'brent',
        'Natural Gas': 'natural_gas', 'Gold': 'gold', 'Silver': 'silver',
        'Platinum': 'platinum', 'Palladium': 'palladium',
        'Copper': 'copper', 'Aluminum': 'aluminum',
        'Wheat': 'wheat', 'Corn': 'corn', 'Rice': 'rice',
        'Soybeans': 'soybeans', 'Coffee': 'coffee', 'Cocoa': 'cocoa',
        'Sugar #11': 'sugar', 'Cotton': 'cotton',
        'Soybean Oil': 'soybean_oil', 'Soybean Meal': 'soybean_meal',
        'Coal (Newcastle)': 'coal', 'Propane': 'propane', 'Lumber': 'lumber',
    }
    for cat in commodity_data.get('structured', []):
        for item in cat.get('items', []):
            name = COMM_MAP.get(item.get('name', ''))
            if name:
                _save(name, item.get('val'), item.get('unit', ''))

    # Yield curve
    for yc in (yield_data or {}).get('yieldCurve', []):
        term = yc.get('term', '')
        if term:
            _save(f'goc_{term.lower()}_yield', yc.get('yield'), '%', 'Bank of Canada')

    print(f"  [HISTORY] Archived {count} market data points to indicator_history")


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
    Append one data point per tracked variable to the timeseries table in SQLite.
    Skips duplicate dates (ON CONFLICT DO NOTHING).
    Variables tracked: BoC rate, CPI, unemployment, GoC yields, CAD/USD, TSX Composite.
    """
    print("\n[TIMESERIES] Appending data points...")
    today_str = date.today().isoformat()

    def _upsert(series_name: str, unit: str, raw_value):
        """Parse raw_value to float and upsert into the timeseries table."""
        if raw_value is None:
            return
        try:
            val_f = float(str(raw_value).replace('%', '').replace('$', '').replace(',', '').strip())
        except Exception:
            return
        save_timeseries_point(conn, series_name, today_str, val_f, unit=unit)

    # BoC Rate
    _upsert('boc_rate', '%', boc_rate.replace('%', ''))

    # National metrics
    m = payload.get('metrics', {})
    _upsert('canada_cpi',         '%', (m.get('cpi') or '').replace('%', '').replace('+', ''))
    _upsert('canada_unemployment', '%', (m.get('unemployment') or '').replace('%', ''))

    # Yield curve terms
    for yc in payload.get('yieldCurve', []):
        term = yc.get('term', '')
        yval = yc.get('yield', '')
        if term and yval:
            _upsert(f'yield_{term.lower()}', '%', yval.replace('%', ''))

    # CAD/USD
    for fx in financial_markets.get('fx', []):
        if 'CAD/USD' in fx.get('name', '') or 'CADUSD' in fx.get('name', ''):
            _upsert('cadusd', 'USD', fx.get('value', '').replace(',', ''))

    # TSX Composite
    for idx in financial_markets.get('indices', []):
        if 'TSX' in idx.get('name', ''):
            _upsert('tsx_composite', 'pts', idx.get('value', '').replace(',', ''))

    # Commodities
    COMM_ID_MAP = {
        'Crude Oil (WTI)': 'comm_wti', 'Crude Oil (Brent)': 'comm_brent',
        'Natural Gas': 'comm_natgas', 'Gold': 'comm_gold', 'Silver': 'comm_silver',
        'Platinum': 'comm_platinum', 'Palladium': 'comm_palladium',
        'Copper': 'comm_copper', 'Aluminum': 'comm_aluminum',
        'Wheat': 'comm_wheat', 'Corn': 'comm_corn', 'Rice': 'comm_rice',
        'Soybeans': 'comm_soybeans', 'Coffee': 'comm_coffee', 'Cocoa': 'comm_cocoa',
        'Sugar #11': 'comm_sugar', 'Cotton': 'comm_cotton',
        'Soybean Oil': 'comm_soyoil', 'Soybean Meal': 'comm_soymeal',
        'Coal (Newcastle)': 'comm_coal', 'Propane': 'comm_propane',
    }
    for cat in payload.get('commodities', []):
        for item in (cat.get('items', []) if isinstance(cat, dict) else []):
            name = item.get('name', '')
            series_id = COMM_ID_MAP.get(name)
            if series_id:
                _upsert(series_id, item.get('unit', ''),
                        item.get('val', '').replace('$', '').replace(',', ''))

    # Other equity indices
    IDX_ID_MAP = {
        'S&P 500': 'idx_sp500', 'Dow Jones': 'idx_djia', 'NASDAQ': 'idx_nasdaq',
        'FTSE 100': 'idx_ftse', 'DAX': 'idx_dax', 'Nikkei 225': 'idx_nikkei',
        'Hang Seng': 'idx_hangseng', 'Shanghai': 'idx_shanghai',
    }
    for idx in financial_markets.get('indices', []):
        name = idx.get('name', '')
        series_id = IDX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, 'pts', idx.get('value', '').replace(',', ''))

    # Other FX pairs
    FX_ID_MAP = {
        'EUR/USD': 'fx_eurusd', 'GBP/USD': 'fx_gbpusd', 'USD/JPY': 'fx_usdjpy',
        'USD/CNY': 'fx_usdcny', 'AUD/USD': 'fx_audusd',
    }
    for fx_item in financial_markets.get('fx', []):
        name = fx_item.get('name', '')
        series_id = FX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, '', fx_item.get('value', '').replace(',', ''))

    print("  Timeseries update complete.")


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


def _parse_projects_with_sonnet(raw_text: str, province: str, context_label: str = "") -> list:
    """
    Use Claude Sonnet to parse a Perplexity result into structured project records.
    If province is a specific province name, forces all extracted projects to that province.
    If province is 'Canada', lets Sonnet determine the province from context.
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

    global _claude_run_cost_usd, _claude_run_tokens

    if _claude_run_cost_usd >= CLAUDE_COST_CAP_USD:
        print(f"    [COST CAP] ${_claude_run_cost_usd:.4f} >= ${CLAUDE_COST_CAP_USD:.2f} cap — skipping {context_label}")
        return []

    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            # Track cost
            in_tok = getattr(msg.usage, 'input_tokens', 0)
            out_tok = getattr(msg.usage, 'output_tokens', 0)
            _claude_run_tokens["input"] += in_tok
            _claude_run_tokens["output"] += out_tok
            call_cost = (in_tok * _CLAUDE_INPUT_COST_PER_MTOK + out_tok * _CLAUDE_OUTPUT_COST_PER_MTOK) / 1_000_000
            _claude_run_cost_usd += call_cost
            print(f"    [COST] {context_label}: {in_tok:,} in + {out_tok:,} out = ${call_cost:.4f} (run total: ${_claude_run_cost_usd:.4f}/${CLAUDE_COST_CAP_USD:.2f})")

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
                print(f"\n    [SONNET JSON ERROR] {context_label}: {e}")
                return []
            time.sleep(1)
        except Exception as e:
            if attempt == 3:
                print(f"\n    [SONNET ERROR] {context_label}: {e}")
                return []
            time.sleep(2 ** attempt)
    return []




def extract_projects_from_rss(rss_items: list) -> tuple:
    """
    Extract structured capital project data directly from RSS news items
    using Claude Sonnet — extracts directly from RSS text.

    Filters project-relevant items, groups by province, then calls
    _parse_projects_with_sonnet() on each group.  Returns a tuple of
    (flat project list, failed article list for Pro recovery).
    """
    proj_items = rss_monitor.filter_project_relevant(rss_items)
    if not proj_items:
        print("  [RSS PROJECTS] No project-relevant items found in RSS feeds.")
        return [], []

    print(f"\n  [RSS PROJECTS] Extracting from {len(proj_items)} relevant RSS items...")

    # Group by province (federal items go under 'Canada')
    by_province: dict[str, list] = {}
    for item in proj_items:
        prov = item.get('province') or 'Canada'
        by_province.setdefault(prov, []).append(item)

    all_projects: list = []
    failed_articles: list = []
    for province, items in sorted(by_province.items()):
        text = rss_monitor.format_for_context(items, max_items=20)
        if not text.strip():
            continue
        projects = _parse_projects_with_sonnet(
            f"Government news releases from {province}:\n\n{text}",
            province if province != 'Canada' else 'Canada',
            f"RSS/{province[:15]}",
        )
        if projects:
            # Inject RSS article URLs as evidence (model often can't extract them)
            rss_urls = [{"url": i.get('url') or i.get('link') or '',
                         "name": i.get('source_name', ''),
                         "date": (i.get('published') or '')[:10],
                         "source_type": "rss_government" if i.get('source_level') != 'media' else "rss_news"}
                        for i in items if (i.get('url') or i.get('link'))]
            for p in projects:
                p.setdefault('_evidence', [])
                existing = {e.get('url') for e in p['_evidence']}
                # Add all RSS URLs from this province group as evidence
                for ru in rss_urls:
                    if ru['url'] not in existing:
                        p['_evidence'].append(ru)
                        existing.add(ru['url'])
                # Also set source_url if missing
                if not p.get('source_url') and rss_urls:
                    p['source_url'] = rss_urls[0]['url']
            print(f"    {province}: {len(projects)} projects from RSS")
        else:
            # Sonnet found no projects — collect articles for Pro recovery
            for item in items:
                failed_articles.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "url": item.get("url") or item.get("link", ""),
                    "source_name": item.get("source_name", ""),
                    "province": province,
                })
        all_projects.extend(projects)

    print(f"  [RSS PROJECTS] {len(all_projects)} extracted, "
          f"{len(failed_articles)} articles queued for Pro recovery")
    return all_projects, failed_articles


# ==========================================
# 4. CLAUDE SONNET ANALYSIS (3 focused calls)
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


# Known source URL patterns: match title keywords → canonical URL
_SOURCE_URL_MAP = [
    ('statistics canada', 'daily', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'gdp', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401'),
    ('statistics canada', 'labour', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'),
    ('statistics canada', 'cpi', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401'),
    ('statistics canada', 'trade', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'payroll', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'retail', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'housing', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'investment', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'balance', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'manufacturing', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'wholesale', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'permit', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'population', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statcan', '', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('bank of canada', 'rate', 'https://www.bankofcanada.ca/rates/interest-rates/'),
    ('bank of canada', 'policy', 'https://www.bankofcanada.ca/rates/interest-rates/'),
    ('bank of canada', 'business outlook', 'https://www.bankofcanada.ca/publications/bos/'),
    ('bank of canada', 'financial', 'https://www.bankofcanada.ca/publications/'),
    ('bank of canada', 'monetary', 'https://www.bankofcanada.ca/publications/mpr/'),
    ('bank of canada', '', 'https://www.bankofcanada.ca/'),
    ('cmhc', 'housing start', 'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research'),
    ('cmhc', '', 'https://www.cmhc-schl.gc.ca/'),
    ('bureau of labor', '', 'https://www.bls.gov/'),
    ('bls', 'employment', 'https://www.bls.gov/news.release/empsit.nr0.htm'),
    ('bls', 'cpi', 'https://www.bls.gov/cpi/'),
    ('federal reserve', '', 'https://www.federalreserve.gov/'),
    ('bureau of economic analysis', '', 'https://www.bea.gov/'),
    ('bea', 'gdp', 'https://www.bea.gov/data/gdp'),
    ('eurostat', '', 'https://ec.europa.eu/eurostat'),
    ('ecb', '', 'https://www.ecb.europa.eu/'),
    ('ons', '', 'https://www.ons.gov.uk/'),
    ('bank of england', '', 'https://www.bankofengland.co.uk/'),
    ('national bureau of statistics', 'china', 'http://www.stats.gov.cn/english/'),
    ('globe and mail', '', 'https://www.theglobeandmail.com/'),
    ('financial post', '', 'https://financialpost.com/'),
    ('reuters', '', 'https://www.reuters.com/'),
    ('bloomberg', '', 'https://www.bloomberg.com/'),
    ('cbc', '', 'https://www.cbc.ca/news'),
    ('iea', '', 'https://www.iea.org/'),
    ('imf', '', 'https://www.imf.org/'),
    ('world bank', '', 'https://www.worldbank.org/'),
    ('oecd', '', 'https://www.oecd.org/'),
    ('infrastructure canada', '', 'https://www.infrastructure.gc.ca/'),
    ('natural resources canada', '', 'https://natural-resources.canada.ca/'),
    ('nrcan', '', 'https://natural-resources.canada.ca/'),
    ('transport canada', '', 'https://tc.canada.ca/en'),
    ('ised', '', 'https://ised-isde.canada.ca/site/ised/en'),
    ('innovation, science and economic development', '', 'https://ised-isde.canada.ca/site/ised/en'),
    ('employment and social development', '', 'https://www.canada.ca/en/employment-social-development.html'),
    ('esdc', '', 'https://www.canada.ca/en/employment-social-development.html'),
    ('immigration, refugees and citizenship', '', 'https://www.canada.ca/en/immigration-refugees-citizenship.html'),
    ('department of finance', '', 'https://www.canada.ca/en/department-finance.html'),
    ('treasury board', '', 'https://www.canada.ca/en/treasury-board-secretariat.html'),
    ('yahoo finance', '', 'https://finance.yahoo.com/'),
]


def _enrich_source_urls(payload: dict):
    """Post-process Claude output: fill in empty source URLs from known title patterns."""
    def _match_url(title: str) -> str:
        t = title.lower()
        for keywords in _SOURCE_URL_MAP:
            *parts, url = keywords
            if all(p in t for p in parts if p):
                return url
        return ''

    def _fix_sources(sources: list):
        fixed = 0
        for s in sources:
            if isinstance(s, dict) and not s.get('url') and s.get('title'):
                matched = _match_url(s['title'])
                if matched:
                    s['url'] = matched
                    fixed += 1
        return fixed

    total_fixed = 0
    # Fix top-level sources
    for key in ('sources', 'industrySources'):
        if isinstance(payload.get(key), list):
            total_fixed += _fix_sources(payload[key])
    # Fix nested sources (national, global, provinces)
    for key in ('national', 'global', 'provinces', 'goodsIndustries', 'servicesIndustries'):
        val = payload.get(key)
        if isinstance(val, dict):
            if isinstance(val.get('sources'), list):
                total_fixed += _fix_sources(val['sources'])
            # Province sub-dicts
            for sub in val.values():
                if isinstance(sub, dict) and isinstance(sub.get('sources'), list):
                    total_fixed += _fix_sources(sub['sources'])
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and isinstance(item.get('sources'), list):
                    total_fixed += _fix_sources(item['sources'])
                    # Also check nested projects
                    for proj in item.get('projects', []):
                        if isinstance(proj, dict) and isinstance(proj.get('sources'), list):
                            total_fixed += _fix_sources(proj['sources'])
    if total_fixed:
        print(f"  [Source URLs] Enriched {total_fixed} empty source URLs from known patterns")


def _is_truncated(text: str) -> bool:
    """Check if JSON response was truncated (doesn't end with valid closure)."""
    stripped = text.rstrip()
    if not stripped:
        return True
    return stripped[-1] not in ('}', ']')


def _repair_json(broken_json: str, label: str) -> dict:
    """Try local LLM first, then Haiku, then Gemini."""
    if not broken_json:
        return {}

    # Try local LLM first (free, no network)
    try:
        result = local_llm.repair_json(broken_json)
        if result is not None:
            print(f"    [LOCAL REPAIR OK] {label}")
            return result
    except Exception as e:
        print(f"    [LOCAL REPAIR FAILED] {label}: {e}")

    repair_prompt = (
        "The following JSON is malformed or truncated. Return ONLY the corrected valid JSON. "
        "No markdown. No explanation.\n\n" + broken_json
    )
    # Try Claude Haiku (cheap, always available)
    try:
        msg = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16384,
            messages=[{"role": "user", "content": repair_prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        print(f"    [HAIKU REPAIR OK] {label}")
        return result
    except Exception as e:
        print(f"    [HAIKU REPAIR FAILED] {label}: {e}")

    # Fall back to Gemini if available via circuit breaker
    health = service_health.get()
    if health.is_available("gemini"):
        return _repair_with_gemini(broken_json, label)

    print(f"    [REPAIR FAILED] {label}: all repair methods exhausted")
    return {}


def _call_claude(prompt: str, label: str, max_tokens: int = 8096, model: str = '',
                 run_id: str = '') -> dict:
    """Call Claude with specified model and parse JSON.

    Features:
    - Checkpointing: if run_id is set, checks for cached response before calling
    - Truncation detection: if response hit max_tokens, retries with +4096
    - JSON repair: tries Haiku first, then Gemini fallback
    """
    global _claude_run_cost_usd, _claude_run_tokens

    # ── Checkpoint check — return cached response if available ────────────
    if run_id:
        cached = get_checkpoint(conn, run_id, label)
        if cached:
            try:
                result = json.loads(cached["response"])
                print(f"    [CHECKPOINT HIT] {label} — using cached response (saved ${cached['cost_usd']:.4f})")
                return result
            except (json.JSONDecodeError, TypeError):
                pass  # corrupted checkpoint, re-run

    # ── Pre-call cost cap check ──────────────────────────────────────────────
    if _claude_run_cost_usd >= CLAUDE_COST_CAP_USD:
        print(f"    [COST CAP] ${_claude_run_cost_usd:.4f} >= ${CLAUDE_COST_CAP_USD:.2f} cap — skipping {label}")
        return {}

    use_model = model or _CLAUDE_MODEL
    raw_content = ""
    current_max_tokens = max_tokens
    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=use_model,
                max_tokens=current_max_tokens,
                system=_CLAUDE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            # ── Track cost ───────────────────────────────────────────────
            in_tok = getattr(msg.usage, 'input_tokens', 0)
            out_tok = getattr(msg.usage, 'output_tokens', 0)
            _claude_run_tokens["input"] += in_tok
            _claude_run_tokens["output"] += out_tok
            call_cost = (in_tok * _CLAUDE_INPUT_COST_PER_MTOK + out_tok * _CLAUDE_OUTPUT_COST_PER_MTOK) / 1_000_000
            _claude_run_cost_usd += call_cost
            print(f"    [COST] {label}: {in_tok:,} in + {out_tok:,} out = ${call_cost:.4f} (run total: ${_claude_run_cost_usd:.4f}/${CLAUDE_COST_CAP_USD:.2f})")

            raw_content = msg.content[0].text.strip()

            # ── Truncation detection ─────────────────────────────────────
            if out_tok >= current_max_tokens - 10 and _is_truncated(raw_content):
                current_max_tokens += 4096
                print(f"    [TRUNCATED] {label}: hit {out_tok} tokens — retrying with max_tokens={current_max_tokens}")
                time.sleep(1)
                continue

            # Strip accidental markdown fences
            if raw_content.startswith("```"):
                parts = raw_content.split("```")
                raw_content = parts[1] if len(parts) > 1 else raw_content
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            parsed = json.loads(raw_content)

            # ── Save checkpoint on success ────────────────────────────────
            if run_id:
                try:
                    save_checkpoint(conn, run_id, label, json.dumps(parsed, ensure_ascii=False), call_cost)
                except Exception as e:
                    print(f"    [CHECKPOINT SAVE WARN] {label}: {e}")

            return parsed
        except json.JSONDecodeError:
            if attempt == 3:
                print(f"    [CLAUDE JSON ERROR] {label} — trying repair...")
                repaired = _repair_json(raw_content, label)
                if repaired and run_id:
                    try:
                        save_checkpoint(conn, run_id, label, json.dumps(repaired, ensure_ascii=False), call_cost)
                    except Exception:
                        pass
                return repaired
            time.sleep(1)
        except CostCapExceeded:
            raise
        except Exception as e:
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
      Call 1: Macro — Claude Sonnet (executive_summary, national, global, globalVectors, watchlist)
      Call 2: Industries + Markets — Claude Sonnet (goodsIndustries, servicesIndustries, yieldCurve)
      Call 3: Provincial — Claude Sonnet (all 13 provinces with analysis, indicators, projects)
      Call 4: Project extraction — Claude Sonnet (structured project records)

    Post-writing citation audit runs after each call.
    """
    print(f"\n[STEP 3] Claude analysis (4 calls, {len(articles)} articles)...")
    print(f"  Model: Sonnet={SONNET_MODEL}")
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

    # ── CALL 1: Macro Tab (SONNET) ───────────────────────────────
    print(f"  [1/4] Macro Tab — exec summary, national, global, watchlist, consumer pulse (Sonnet)...")

    call1 = _call_claude(f"""Today: {today_str}

VERIFIED DATA (use exactly, never modify round or reinterpret):
{hard_summary}

{cdn_officials_ctx}

{global_officials_ctx}

RECENT NEWS AND PRESS RELEASES (cite by article number):
{all_arts_text}
{sentiment_ctx}
{CITATION_RULES}

Write:

1. EXECUTIVE SUMMARY (8-12 bullet points)
Format as HTML: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
Each bullet is 1-2 sentences with a specific fact, figure, or development. Use <strong> tags on key figures.
Cover: top macro story, supporting data, risks/counterpoints, consumer sentiment texture, upcoming catalysts.
Every bullet ends with <sup>N</sup> citation.

2. NATIONAL ANALYSIS (8-12 bullet points)
Format as HTML: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
Each bullet: one specific data point, event, or development with numbers and dates.
Cover: dominant domestic theme, data deep-dive, secondary developments, implications.
Every bullet ends with <sup>N</sup> citation.

3. GLOBAL VECTORS (6-8 bullets each):
Format each as HTML: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
US: impact on Canadian trade, rates, currency. China: impact on commodities, investment. EU: impact on trade, regulatory alignment. UK: impact on trade, financial linkages.
Per vector: first bullets cover what happened, last bullets cover what it means for Canada. No generic commentary. Each bullet ends with <sup>N</sup>.

4. INDICATOR CONTEXT LINES: 1 sentence each, under 20 words, plain English for: bocRate, cpi, unemployment, housingStarts, realGdp.

5. WATCHLIST: 15-25 upcoming events with dates, impact rating (high/medium/low), description, source URLs where available.

6. CONSUMER PULSE (6-8 bullet points):
Format as HTML: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
Each bullet: one specific consumer trend, sentiment signal, or discussion topic. Ground in sentiment data. Note divergences (e.g. consumer anxiety about housing rising even as rate cuts accelerate). Tone: observational and analytical. Do NOT use footnote citations — reference sentiment data naturally: "Reddit discussions in r/PersonalFinanceCanada dominated by..." or "Google search interest in tariff queries surged..."

7. metrics: Fill ALL fields from articles EXCEPT — leave as "": cpi, shelterCpi, unemployment, participation, realGdp. These are injected from StatCan/BoC primary APIs. bocRate must match "{hard_data['boc_rate']}".

8. WORD CLOUD TOPICS: Extract 40-60 meaningful economic topics/phrases from this week's news. These power a word cloud visualization. Each topic should be 1-3 words, e.g. "tariff threat", "rate cut", "housing affordability", "LNG exports", "auto layoffs", "tech hiring freeze", "lumber prices", "fiscal deficit", "immigration policy". Assign each a sentiment_score (-1.0 to +1.0, negative=bad for Canada, positive=good) and frequency (1-10 importance weight, 10=dominant story). Prioritize specificity over generality. BAD: "economy", "growth", "markets". GOOD: "tariff retaliation", "BoC rate hold", "Alberta oil sands", "EV battery plant".

Style: Bloomberg terminal meets FT editorial. Use bullet points (<ul><li>) for ALL analysis sections — no paragraphs. Every bullet references a specific event, figure, or date. DO NOT discuss stock market movements, equity index levels, or stock performance (e.g. TSX, S&P 500, Dow, NASDAQ gains/losses). Rate changes, yield changes, FX, and bond markets ARE fair game. BANNED: economy continues to grow, markets remain volatile, positive outlook contingent on demand, remains to be seen, going forward.

OUTPUT: Valid JSON only. No markdown. No text outside the JSON.

SCHEMA:
{{
    "executive_summary": "<ul class='list-disc list-inside space-y-2 text-slate-700'><li>8-12 bullets with <sup>N</sup> citations and <strong> on key figures</li></ul>",
    "metrics": {{
        "realGdp": "", "nomGdp": "", "outputGap": "", "cpi": "", "shelterCpi": "",
        "bocRate": "{hard_data['boc_rate']}", "unemployment": "", "participation": "",
        "wageGrowth": "", "currentAccount": "", "agCrop": "", "farmCash": ""
    }},
    "national": {{
        "analysis": "<ul class='list-disc list-inside space-y-2 text-slate-700'><li>8-12 bullets with <sup>N</sup> citations</li></ul>",
        "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://example.com/article"}}]
    }},
    "global": [
        {{"region": "United States", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": ""}}, "analysis": "<ul class='list-disc list-inside space-y-2 text-slate-700'><li>6-8 bullets with <sup>N</sup> citations</li></ul>", "sources": [{{"id": 1, "title": "", "url": "https://..."}}]}},
        {{"region": "China", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": ""}}, "analysis": "<ul>...</ul>", "sources": []}},
        {{"region": "European Union", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": ""}}, "analysis": "<ul>...</ul>", "sources": []}},
        {{"region": "United Kingdom", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": ""}}, "analysis": "<ul>...</ul>", "sources": []}}
    ],
    "globalVectors": {{"us": "", "china": "", "eu": ""}},
    "consumer_pulse": "<ul class='list-disc list-inside space-y-2 text-slate-700'><li>6-8 bullets, no footnote citations, observational tone</li></ul>",
    "indicatorContextLines": {{"bocRate": "", "cpi": "", "unemployment": "", "housingStarts": "", "realGdp": ""}},
    "watchlist": [
        {{
            "date": "Mar 14",
            "week_label": "This Week",
            "institution": "Statistics Canada",
            "event_name": "Consumer Price Index",
            "description": "One sentence on what to watch and why it matters for Canada.",
            "impact": "high",
            "source_url": "https://www150.statcan.gc.ca/n1/daily-quotidien/en"
        }}
    ],
    "word_cloud_topics": [
        {{"topic": "tariff retaliation", "sentiment_score": -0.7, "frequency": 9}},
        {{"topic": "BoC rate hold", "sentiment_score": 0.2, "frequency": 7}},
        {{"topic": "housing affordability", "sentiment_score": -0.5, "frequency": 6}}
    ]
}}""", "call1-macro", max_tokens=12000, model=SONNET_MODEL)

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

VERIFIED DATA:
{hard_summary}

RECENT ARTICLES (grouped by industry — cite by article number, use URLs exactly as given):
{industry_arts_text}

{CITATION_RULES}

Write:

1. INDUSTRY EXECUTIVE SUMMARY (8-12 bullet points):
Format as HTML: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
Each bullet: one specific cross-cutting industry development with figures and citations. Lead with the single biggest sectoral story. Identify themes spanning multiple sectors. Note structural shifts or emerging trends. Every bullet ends with <sup>N</sup>.

2. SECTOR ANALYSIS — goodsIndustries: Exactly 5 goods-producing sectors. Per sector: 150 words in bullets. 3-digit NAICS subsector commentary where data supports.
   For each:
   - code: NAICS code string exactly as listed below
   - name: sector display name
   - mm: set to "" — injected from StatCan Table 36-10-0434-01; must not be estimated
   - yy: set to "" — injected from StatCan; must not be estimated
   - analysis: HTML bullets referencing the PRIMARY SOURCE INDICATOR M/M and Y/Y from hard data. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-600 text-xs"><li>...</li></ul>
   - industrySources: array of {{id, title, url}}
   - isNegative: boolean — set based on the M/M value in PRIMARY SOURCE INDICATORS
   - subsectors: 2-3 subsectors each with code, name, mm set to ""

   The 5 goods sectors: "11" Agriculture, "21" Mining & Energy, "22" Utilities, "23" Construction, "31-33" Manufacturing.

3. servicesIndustries: Exactly 15 services-producing sectors. Same format as goodsIndustries — mm and yy must be "".

   The 15 services sectors: "41" Wholesale Trade, "44-45" Retail Trade, "48-49" Transportation & Warehousing, "51" Information & Culture, "52" Finance & Insurance, "53" Real Estate, "54" Professional Services, "55" Management, "56" Admin & Waste Mgmt, "61" Education, "62" Health Care, "71" Entertainment & Recreation, "72" Accommodation & Food, "81" Other Services, "91" Public Administration.

4. yieldCurve: Full GoC curve 1M through 30Y. highlight: true on 2Y and 10Y only.

5. charts: yieldCurveCurrent (array of float values matching yieldCurve order), yieldCurveLastYear (array of floats for 1-yr prior, or empty []).

DO NOT discuss stock market movements, equity index levels, or stock performance (e.g. TSX, S&P 500, Dow, NASDAQ gains/losses). Rate changes, yield changes, FX, and bond markets ARE fair game.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "industry_executive_summary": "<ul class='list-disc list-inside space-y-2 text-slate-700'><li>8-12 bullets with <sup>N</sup> citations</li></ul>",
    "goodsIndustries": [
        {{
            "code": "11", "name": "Agriculture", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://..."}}],
            "isNegative": false,
            "subsectors": [{{"code": "", "name": "", "mm": ""}}]
        }}
    ],
    "servicesIndustries": [
        {{
            "code": "41", "name": "Wholesale Trade", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "", "url": "https://..."}}],
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
}}""", "call2-industries", max_tokens=10000, model=SONNET_MODEL)

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
b) analysis: 5-8 bullets of SPECIFIC events from the past 1-4 weeks. Name events, companies, figures, and dates. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-700"><li>...</li></ul>
c) sources: Array matching bullet numbers. id, title (Publication — Article Title, Month YYYY), url (direct link to the publication — REQUIRED, use the publication's homepage if exact article URL unknown).
d) projects: 2-4 major capital projects. Each: name, description (1 sentence, max 20 words, names the proponent), sector, value (e.g. "$4.2B"), status (Announced/Approved/Under Construction/Operational/Completed/Cancelled), completionDate (e.g. "2027" or ""), cma (nearest city/CMA), tags (array of 1-3 strings), sources (array with id/title/url).

BAD bullets: "Ontario's economy continues its growth trajectory" / "The sector is seeing significant investment"
GOOD bullets: "StatCan reported Ontario unemployment rose to 6.8% in March, up from 6.5% in February, driven by layoffs in the Kitchener-Waterloo tech corridor. <sup>1</sup>"

DO NOT discuss stock market movements, equity index levels, or stock performance. Rate changes, yield changes, FX, and bond markets ARE fair game.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "provinces": [
        {{
            "name": "Ontario",
            "indicators": {{"gdp": "+X.X%", "unemployment": "X.X%", "cpi": "+X.X%", "housingStarts": "XX,XXX"}},
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-700\\"><li>specific event with figure and date. <sup>1</sup></li><li>another specific event. <sup>2</sup></li></ul>",
            "sources": [{{"id": 1, "title": "StatCan — Labour Force Survey, March 2026", "url": "https://..."}}, {{"id": 2, "title": "Globe and Mail — Article Title, March 2026", "url": "https://..."}}],
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
                    "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://example.com/article"}}]
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

    # Ensure new fields are present
    if not payload.get('consumer_pulse'):
        payload['consumer_pulse'] = ''
    if not payload.get('industry_executive_summary'):
        payload['industry_executive_summary'] = ''

    # ── Enrich source URLs: map known titles to real URLs ─────────
    _enrich_source_urls(payload)

    # ── Apply citation audit: remove failed claims from text ──────
    from citation_audit import remove_failed_claims
    for audit in audit_results:
        if not audit.get('passed', True):
            # If audit failed (>30% removal), flag for review
            print(f"  [Citation Audit] {audit.get('_label', '?')}: FAILED — flagging for manual review")
        failed_cites = audit.get('failed_citations', [])
        unsourced = audit.get('unsourced_claims', [])
        if failed_cites or unsourced:
            # Remove failed claims from relevant text fields
            for text_key in ('executive_summary', 'consumer_pulse', 'industry_executive_summary'):
                if payload.get(text_key):
                    payload[text_key] = remove_failed_claims(
                        payload[text_key], failed_cites, unsourced)
            # Remove from national analysis
            if payload.get('national', {}).get('analysis'):
                payload['national']['analysis'] = remove_failed_claims(
                    payload['national']['analysis'], failed_cites, unsourced)
            # Remove from global analyses
            for g in payload.get('global', []):
                if g.get('analysis'):
                    g['analysis'] = remove_failed_claims(g['analysis'], failed_cites, unsourced)

    # ── Save citation audit log ────────────────────────────────────
    if audit_results:
        save_audit_log(audit_results)
        all_passed = all(a.get('passed', True) for a in audit_results)
        total_cites = sum(a.get('total_citations', 0) for a in audit_results)
        total_failed = sum(a.get('failed_count', 0) for a in audit_results)
        total_archived = sum(a.get('archived_count', 0) for a in audit_results)
        status = 'ALL PASSED' if all_passed else 'SOME FAILED (>30% removal — review before publish)'
        print(f"  [Citation Audit] {status}: {total_cites} citations, {total_failed} failed, {total_archived} archived")
        payload['citation_audit'] = {
            'passed': all_passed,
            'total_citations': total_cites,
            'total_failed': total_failed,
            'total_archived': total_archived,
            'calls': [{
                'label': a.get('_label', ''),
                'passed': a.get('passed', True),
                'citations': a.get('total_citations', 0),
                'failed': a.get('failed_count', 0),
                'removal_pct': a.get('removal_pct', 0),
                'archived': a.get('archived_count', 0),
            } for a in audit_results],
        }

    # ── Collect all verified source URLs with archive URLs ──────
    all_sources = []
    for audit in audit_results:
        for vc in audit.get('verified_citations', []):
            if vc.get('url'):
                all_sources.append({
                    'url': vc['url'],
                    'title': vc.get('title', ''),
                    'archive_url': vc.get('archive_url', ''),
                })
    payload['_all_verified_sources'] = all_sources

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
    """Single Sonnet call to generate plain-English context for each national indicator."""
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

def _verify_project_evidence_urls(conn, batch_size=200) -> None:
    """
    Check evidence URLs across projects and mark dead ones.

    Runs HEAD requests against evidence URLs that haven't been checked recently.
    Dead URLs get url_dead=True so the frontend can show 'source unavailable'.
    Checks up to batch_size projects per run.
    """
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    print(f"\n[URL-CHECK] Verifying project evidence URLs...")

    import json as _json
    try:
        rows = conn.execute(
            "SELECT norm_key, evidence FROM projects "
            "WHERE (urls_checked_at IS NULL OR urls_checked_at < ?) LIMIT ?",
            (cutoff, batch_size)
        ).fetchall()
        docs = [dict(r) for r in rows]
    except Exception as e:
        print(f"  [URL-CHECK] Could not query projects: {e}")
        return

    if not docs:
        print("  [URL-CHECK] No projects need URL checking.")
        return

    print(f"  [URL-CHECK] Checking evidence URLs for {len(docs)} projects...")

    # Collect all URLs to check
    url_tasks = []  # (norm_key, evidence_index, url)
    for doc in docs:
        evidence = doc.get('evidence', [])
        if isinstance(evidence, str):
            try:
                evidence = _json.loads(evidence)
            except Exception:
                evidence = []
        for i, ev in enumerate(evidence):
            url = ev.get('url', '')
            if url and url.startswith('http') and not ev.get('url_dead'):
                url_tasks.append((doc['norm_key'], i, url, evidence))

    if not url_tasks:
        today_str = date.today().isoformat()
        for doc in docs:
            try:
                with conn:
                    conn.execute(
                        "UPDATE projects SET urls_checked_at = ? WHERE norm_key = ?",
                        (today_str, doc['norm_key'])
                    )
            except Exception as e:
                print(f"  [WARN] URL check timestamp update failed ({doc.get('norm_key', '?')}): {e}")
        print("  [URL-CHECK] No evidence URLs to verify.")
        return

    # Batch HEAD checks
    urls_only = [t[2] for t in url_tasks]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_check_url, urls_only))

    # Group dead indices by norm_key
    dead_by_key = {}
    dead_count = 0
    for (norm_key, ev_idx, url, ev_list), is_live in zip(url_tasks, results):
        if not is_live:
            dead_count += 1
            dead_by_key.setdefault(norm_key, []).append(ev_idx)

    today_str = date.today().isoformat()
    checked_keys = set()
    for norm_key, dead_indices in dead_by_key.items():
        try:
            row = conn.execute(
                "SELECT evidence FROM projects WHERE norm_key = ?", (norm_key,)
            ).fetchone()
            if row:
                ev_list = _json.loads(row['evidence'] or '[]')
                changed = False
                for idx in dead_indices:
                    if idx < len(ev_list) and not ev_list[idx].get('url_dead'):
                        ev_list[idx]['url_dead'] = True
                        changed = True
                if changed:
                    with conn:
                        conn.execute(
                            "UPDATE projects SET evidence = ?, urls_checked_at = ? WHERE norm_key = ?",
                            (_json.dumps(ev_list, ensure_ascii=False), today_str, norm_key)
                        )
            checked_keys.add(norm_key)
        except Exception as e:
            print(f"  [WARN] Dead URL update failed ({norm_key}): {e}")

    for doc in docs:
        if doc['norm_key'] not in checked_keys:
            try:
                with conn:
                    conn.execute(
                        "UPDATE projects SET urls_checked_at = ? WHERE norm_key = ?",
                        (today_str, doc['norm_key'])
                    )
            except Exception as e:
                print(f"  [WARN] URL check timestamp update failed ({doc.get('norm_key', '?')}): {e}")

    live_count = len(urls_only) - dead_count
    print(f"  [URL-CHECK] {live_count} live, {dead_count} dead across {len(docs)} projects")


def _check_stale_projects(conn) -> None:
    """
    STEP 4b: Mark projects not seen in 4+ weeks as stale.
    Updates SQLite directly. Non-critical — never raises.
    """
    stale_cutoff = (date.today() - timedelta(days=28)).isoformat()
    try:
        rows = conn.execute(
            "SELECT norm_key, name, lastSeen FROM projects WHERE lastSeen < ? LIMIT 50",
            (stale_cutoff,)
        ).fetchall()
        if not rows:
            print("  [Stale check] No projects older than 4 weeks.")
            return
        print(f"  [Stale check] Marking {len(rows)} stale projects...")
        for row in rows:
            name = row['name']
            if not name:
                continue
            try:
                with conn:
                    conn.execute(
                        "UPDATE projects SET stale = 1, statusNote = ? WHERE norm_key = ?",
                        (f"Not seen since {row['lastSeen'] or 'unknown'}", row['norm_key'])
                    )
            except Exception as e:
                print(f"  [WARN] Stale mark failed ({row.get('norm_key', '?')}): {e}")
        print(f"  [Stale check] {len(rows)} projects marked stale")
    except Exception as e:
        print(f"  [Stale check] Error: {e}")


def seed_projects(deep_sweep: bool = False) -> None:
    """
    --seed-projects: Full project seed from all sources.
    1. Government registries (IAAC, BC EAO, NRCan, Infrastructure Canada, BuyAndSell)
    2. Compound Gemini discovery (replaces GDELT+Perplexity)
    3. Municipal + institutional scrapers
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
        upsert_flat_projects(conn,flat)

    # Tier 2: Google News RSS discovery (replaces Gemini grounded search)
    print("\n  [Seed] Google News RSS discovery...")
    try:
        seed_articles = run_google_news_search(gemini_client=gemini_client)
        if seed_articles:
            print(f"  [Seed] {len(seed_articles)} articles from Google News RSS")
    except Exception as e:
        print(f"  [Seed] Google News discovery failed: {e}")

    # Tier 13: Municipal development applications
    try:
        from municipal_dev_apps import scrape_municipal_applications_sync
        print("\n  [Seed] Municipal development applications...")
        muni = scrape_municipal_applications_sync()
        if muni:
            upsert_flat_projects(conn,muni)
    except Exception as e:
        print(f"  [Seed] Municipal scrape failed: {e}")

    # Tier 14: Institutional capital plans
    try:
        from institutional_capital import scrape_institutional_capital
        print("\n  [Seed] Institutional capital plans...")
        inst = scrape_institutional_capital()
        if inst:
            upsert_flat_projects(conn,inst)
    except Exception as e:
        print(f"  [Seed] Institutional scrape failed: {e}")

    # Wayback history backfill for all new projects
    from wayback import backfill_project_history as _bfill
    import json as _json
    print("\n  [Seed] Wayback history backfill...")
    try:
        rows = conn.execute(
            "SELECT norm_key, name, province, statusHistory FROM projects "
            "WHERE (history_backfilled IS NULL OR history_backfilled = 0)"
        ).fetchall()
        bf_count = 0
        for row in rows:
            p = dict(row)
            name = p.get('name', '')
            sh = p.get('statusHistory', '[]')
            if isinstance(sh, str):
                try:
                    sh = _json.loads(sh)
                except Exception:
                    sh = []
            source_url = ''
            for entry in (sh or []):
                src = entry.get('source', {})
                if src.get('url'):
                    source_url = src['url']
                    break
            if not source_url or not name:
                continue
            result = _bfill(
                project_name=name,
                source_url=source_url,
                province=p.get('province', ''),
            )
            if result.get('history_backfilled') and result.get('statusHistory'):
                full_history = result['statusHistory'] + (sh or [])
                with conn:
                    conn.execute(
                        "UPDATE projects SET history_backfilled = 1, "
                        "history_earliest_date = ?, statusHistory = ? WHERE norm_key = ?",
                        (result.get('history_earliest_date', ''),
                         _json.dumps(full_history, ensure_ascii=False),
                         p['norm_key'])
                    )
                bf_count += 1
        print(f"  [Seed] Backfilled {bf_count} projects")
    except Exception as e:
        print(f"  [Seed] Backfill error: {type(e).__name__}: {e}")

    # Quality report
    generate_quality_report(conn=conn)
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
        'discovery_source': 'news_extraction',
        'sources': [{'id': 1, 'title': src.get('title', ''),
                     'url': src.get('url', ''), 'date': src.get('date', '')}],
        'announced':        src.get('date') or date.today().isoformat(),
        'completionDate':   '',
    }


def update_dashboard(deep_sweep: bool = False):
    run_type = "deep_sweep" if deep_sweep else "weekly"
    health = service_health.init()
    run_log = PipelineRunLogger(conn=conn, run_type=run_type)
    run_log.start()
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
            'boc_rate':          boc_data['rate'] or 'N/A',
            'rss_items':         rss_items,
        }
        run_log.log_step("step_1_hard_data")

        # ── STEP 1b: Primary source indicators (consolidated) ────────
        primary_ind  = fetch_primary_indicators()
        national_ind = primary_ind['national']
        prov_ind     = primary_ind['provinces']
        global_ind   = primary_ind['global']
        hard_data['primary_indicators'] = primary_ind

        # Archive to indicator_history for trend analysis
        try:
            _archive_indicators_to_history(primary_ind)
        except Exception as e:
            print(f"  [HISTORY] Archive error (non-critical): {e}")

        # Archive market data (indices, FX, commodities) to indicator_history
        try:
            _archive_market_data_to_history(financial_markets, commodity_data, yield_data)
        except Exception as e:
            print(f"  [HISTORY] Market archive error (non-critical): {e}")

        run_log.log_step("step_1b_indicators")

        # ══════════════════════════════════════════════════════════
        # 5-TIER DISCOVERY PIPELINE
        # ══════════════════════════════════════════════════════════

        # ── TIER 1: Government registries ──────────────────────────
        print("\n[TIER 1] Government registries...")
        registry_projects = fetch_registry_projects(tavily_client=tavily_client)

        run_log.log_step("tier_1_registries")

        # ── TIER 13: Municipal development applications ──────────────
        municipal_projects = []
        try:
            from municipal_dev_apps import scrape_municipal_applications_sync
            print("\n[TIER 13] Municipal development applications...")
            municipal_projects = scrape_municipal_applications_sync()
            print(f"  {len(municipal_projects)} municipal projects found")
        except Exception as e:
            print(f"  [TIER 13] Municipal scrape failed: {type(e).__name__}: {e}")
            run_log.log_error("tier_13_municipal", e)

        # ── TIER 14: Institutional capital plans ─────────────────────
        institutional_projects = []
        try:
            from institutional_capital import scrape_institutional_capital
            print("\n[TIER 14] Institutional capital plans...")
            institutional_projects = scrape_institutional_capital()
            print(f"  {len(institutional_projects)} institutional projects found")
        except Exception as e:
            print(f"  [TIER 14] Institutional scrape failed: {type(e).__name__}: {e}")
            run_log.log_error("tier_14_institutional", e)

        # ── TIER 2: Gemini compound discovery ────────────────────────
        gemini_projects = []

        # Consume follow-up queries from last week via Tavily
        tavily_searches_count = 0
        try:
            from pipeline_store import get_follow_up_queries
            from tavily_search import tavily_search_sync
            pro_follow_ups = get_follow_up_queries(db=None, conn=conn)
            if pro_follow_ups and can_use_tavily():
                print(f"\n[TIER 2] Running {len(pro_follow_ups)} follow-up queries via Tavily...")
                for fq in pro_follow_ups[:30]:  # Cap at 30 Tavily credits
                    if not can_use_tavily():
                        print("  [TAVILY] Budget limit reached — stopping follow-ups")
                        break
                    query_text = fq.get("query", "") if isinstance(fq, dict) else str(fq)
                    results = tavily_search_sync(query_text, max_results=3)
                    tavily_searches_count += 1
                    if results:
                        for r in results:
                            gemini_projects.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "summary": r.get("content", ""),
                                "_discovery_tier": "tavily_followup",
                                "_province": fq.get("province", "") if isinstance(fq, dict) else "",
                                "_sector": fq.get("sector", "") if isinstance(fq, dict) else "",
                            })
                print(f"  [FOLLOWUP] {len(gemini_projects)} results from follow-up queries")
        except Exception as e:
            print(f"  [FOLLOWUP] Failed: {type(e).__name__}: {e}")

        # Google News RSS discovery (replaces Gemini grounded search)
        print("\n[TIER 2] Google News RSS discovery...")
        try:
            news_articles = run_google_news_search(gemini_client=gemini_client)
            if news_articles:
                gemini_projects.extend(news_articles)
        except Exception as e:
            print(f"  [TIER 2] Google News RSS failed: {type(e).__name__}: {e}")
            run_log.log_error("tier_2_google_news", e)

        run_log.log_step("tier_2_google_news")

        # ── TIER 3: Article extraction from RSS ─────────────────────
        # Compound queries + RSS cover all news discovery.
        # Tavily extracts full text from RSS article URLs.
        extracted_articles = []

        # ── TIER 4: RSS feeds (filtered) ───────────────────────────
        # rss_items already fetched above; run filter for project extraction
        rss_filtered = rss_monitor.fetch_and_filter(
            days_back=days_back,
            include_media=True,
            gemini_client=gemini_client,
        )
        # Note: rss_items was already fetched at STEP 1 for context;
        # rss_filtered adds media feeds + three-layer filter for project extraction

        # ── STEP 3: Claude Sonnet analysis ────────────────────────
        final_payload = generate_claude_analysis(hard_data, extracted_articles, rss_items)
        run_log.log_step("step_3_claude_analysis")

        # ── Guard: abort if Claude returned nothing useful ────────
        _REQUIRED_KEYS = {'overview', 'provinces', 'industries'}
        _missing = _REQUIRED_KEYS - set(final_payload or {})
        if not final_payload or _missing:
            msg = f"Claude analysis empty or missing critical keys: {_missing or 'empty dict'}"
            print(f"  [CRITICAL] {msg}")
            run_log.log_error("step_3_claude_analysis", RuntimeError(msg), recovered=False)
            final_payload.setdefault('_analysis_incomplete', True)
            final_payload.setdefault('_analysis_error', msg)

        # ── STEP 4a: Inject authoritative hard data (overrides AI) ─
        final_payload['commodities']      = commodity_data['structured']
        final_payload['financialMarkets'] = financial_markets
        if yield_data:
            final_payload['yieldCurve'] = yield_data['yieldCurve']
            final_payload['charts']     = yield_data['charts']

        # ── STEP 4b: National metrics — API or N/A, never AI ───────
        m = final_payload.setdefault('metrics', {})
        m['bocRate'] = boc_data['rate'] or 'N/A'
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

        # Generate plain-English context lines via Sonnet (non-critical)
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

        # ── POST-EXTRACTION: Deduplicate & upsert all discovered projects ──
        print("\n[POST-EXTRACTION] Collecting all discovered projects...")

        # Claude-analyzed provincial projects (from Claude Call 4)
        if final_payload.get('provinces'):
            upsert_projects(conn, final_payload['provinces'])

        # Collect ALL flat projects from every tier for cross-tier deduplication
        all_flat_projects = []

        # Tier 2: Gemini compound discovery projects
        if gemini_projects:
            for gp in gemini_projects:
                ptype = normalize_project_type(gp.get('project_type', ''))
                all_flat_projects.append({
                    'name':              gp.get('name', ''),
                    'province':          gp.get('province', ''),
                    'cma':               gp.get('cma', ''),
                    'sector':            gp.get('naics_2digit', 'Other'),
                    'naics_code':        gp.get('naics_2digit', ''),
                    'tags':              [],
                    'value':             gp.get('value', 'Not disclosed'),
                    'value_millions':    gp.get('value_numeric'),
                    'status':            gp.get('status', 'Proposed'),
                    'description':       gp.get('description', ''),
                    'discovery_source':  gp.get('discovery_source', 'gemini_compound'),
                    'source_url':        gp.get('source_url', ''),
                    'source_title':      gp.get('source_title', ''),
                    'sources': [{'id': 1, 'title': gp.get('source_title', ''),
                                 'url': gp.get('source_url', '')}],
                    'announced':         date.today().isoformat(),
                    'completionDate':    '',
                    'project_type':      ptype,
                    'is_brownfield':     is_brownfield(ptype),
                    '_source_query_sector': gp.get('_section', ''),
                })

        # Tier 4: RSS project extraction
        rss_projects, rss_failed_articles = extract_projects_from_rss(rss_items)
        if rss_projects:
            for rp in rss_projects:
                rp.setdefault('discovery_source', 'rss_remediated')
            all_flat_projects.extend(rss_projects)

        # Tier 1: Registry projects
        if registry_projects:
            for p in registry_projects:
                all_flat_projects.append({
                    'name':              p.get('name', ''),
                    'province':          p.get('province', ''),
                    'cma':               '',
                    'sector':            p.get('sector', 'Other'),
                    'naics_code':        '',
                    'tags':              [],
                    'value':             p.get('value', ''),
                    'status':            p.get('status', 'Announced'),
                    'description':       p.get('name', ''),
                    'discovery_source':  p.get('discovery_source', 'federal_registry'),
                    'source_url':        p.get('source_url', ''),
                    'sources': [{'id': 1, 'title': p.get('discovery_source', ''),
                                 'url': p.get('source_url', '')}],
                    'announced':         date.today().isoformat(),
                    'completionDate':    '',
                })

        # Tier 13: Municipal development application projects
        if municipal_projects:
            for p in municipal_projects:
                p.setdefault('discovery_source', 'municipal_dev_app')
            all_flat_projects.extend(municipal_projects)

        # Tier 14: Institutional capital plan projects
        if institutional_projects:
            for p in institutional_projects:
                p.setdefault('discovery_source', 'institutional_capital')
            all_flat_projects.extend(institutional_projects)

        # ── Rehash filter (Gemini Flash, free) ────────────────────────
        try:
            from gemini_engine import filter_rehashes_sync
            existing = get_all_projects(conn)
            if rss_items and existing:
                pre_count = len(rss_items)
                rss_items = filter_rehashes_sync(rss_items, existing)
                if pre_count != len(rss_items):
                    print(f"  [REHASH] RSS items: {pre_count} -> {len(rss_items)}")
        except Exception as e:
            print(f"  [REHASH] Filter failed (non-critical): {type(e).__name__}: {e}")

        # ── Selective Claude extraction (top high-signal documents) ───
        try:
            from claude_reasoning import selective_extraction_sync
            # Collect all articles that were classified as relevant this run
            selective_docs = list(rss_items) if rss_items else []
            if 'extracted_articles' in dir() and extracted_articles:
                selective_docs.extend(extracted_articles)
            if selective_docs:
                print("\n[POST-EXTRACTION] Selective Claude extraction (high-signal docs)...")
                selective_projects = selective_extraction_sync(selective_docs)
                if selective_projects:
                    all_flat_projects.extend(selective_projects)
                    print(f"  [SELECTIVE] {len(selective_projects)} projects from selective extraction")
        except Exception as e:
            print(f"  [SELECTIVE] Extraction failed (non-critical): {type(e).__name__}: {e}")

        # ── Cross-tier deduplication ──────────────────────────────────
        if all_flat_projects:
            raw_count = len(all_flat_projects)
            deduped = deduplicate_projects(all_flat_projects)
            dup_count = raw_count - len(deduped)
            # STEP_2F: Hard gate -- reject projects without verifiable source URLs
            verified = [p for p in deduped if p.get("evidence") and len(p["evidence"]) > 0]
            rejected_list = [p for p in deduped if not p.get("evidence") or len(p["evidence"]) == 0]
            rejected = len(rejected_list)
            print(f"\n[DEDUP] {raw_count} raw mentions -> {len(deduped)} unique "
                  f"({dup_count} cross-tier duplicates merged)")
            if rejected:
                print(f"  [URL GATE] {rejected} projects rejected (no verifiable source URL)")
                # Debug: show first 5 rejected with their source info
                for rp in rejected_list[:5]:
                    src = rp.get('discovery_source', '?')
                    name = rp.get('name', '?')[:50]
                    has_ev = bool(rp.get('_evidence'))
                    has_su = bool(rp.get('source_url'))
                    print(f"    REJECTED: [{src}] {name} | _evidence={has_ev} source_url={has_su}")
            sync_result = upsert_flat_projects(conn,verified)
            if sync_result:
                run_log.log_metric("discovery", "projects_added", sync_result.get("new", 0))
                run_log.log_metric("discovery", "projects_updated", sync_result.get("updated", 0))
            run_log.log_metric("discovery", "articles_found", raw_count)
            run_log.log_metric("discovery", "projects_deduped", dup_count)
        else:
            print("\n[DEDUP] No flat projects to upsert")
        run_log.log_step("post_extraction_dedup")

        # Cross-reference logging (legacy gemini_search logger removed)

    except Exception as e:
        import traceback
        print(f"\n[CRITICAL] Core pipeline failed: {e}")
        traceback.print_exc()
        run_log.log_error("core_pipeline", e, recovered=False)
        run_log.finalize("error")
        return

    # ════════════════════════════════════════════════════════════════
    # NON-CRITICAL STEPS — each isolated, failures don't block others
    # ════════════════════════════════════════════════════════════════

    try:
        # ── Cost-finding for valueless projects (runs first) ─────────
        try:
            if can_use_tavily():
                from cost_finder import run_cost_search
                print("\n[POST-EXTRACTION] Cost-finding for valueless projects...")
                cost_results = run_cost_search(conn)
                if cost_results.get("found"):
                    print(f"  [COST] Updated {cost_results['found']} projects with values")
            else:
                print("\n[POST-EXTRACTION] Cost-finding skipped (Tavily budget)")
        except Exception as e:
            print(f"  [COST] Cost-finding failed: {type(e).__name__}: {e}")
            run_log.log_error("cost_finding", e)

        # ── Enrichment queries (Gemini Flash, no grounding) ────────
        if all_flat_projects:
            try:
                from enrichment_queries import run_enrichment_sync
                print("\n[POST-EXTRACTION] Enrichment queries (spare Gemini capacity)...")
                # Projects missing value or status
                needs_enrichment = [p for p in (verified if 'verified' in dir() else all_flat_projects)
                                    if not p.get('value_millions') or not p.get('status')
                                    or p.get('status') == 'Proposed']
                if needs_enrichment:
                    enriched = run_enrichment_sync(needs_enrichment[:55])
                    if enriched:
                        enriched_deduped = deduplicate_projects(enriched)
                        enriched_verified = [p for p in enriched_deduped
                                             if p.get("evidence") and len(p["evidence"]) > 0]
                        if enriched_verified:
                            upsert_flat_projects(conn,enriched_verified)
                            print(f"  [ENRICHMENT] {len(enriched_verified)} projects enriched")
                else:
                    print("  [ENRICHMENT] No projects need enrichment")
            except Exception as e:
                print(f"  [ENRICHMENT] Failed: {type(e).__name__}: {e}")
                run_log.log_error("enrichment", e)

        # ── Wayback history backfill for new projects ──────────────
        try:
            from wayback import backfill_project_history, save_page as wayback_save
        except ImportError:
            backfill_project_history = None
            wayback_save = None
            print("[WARN] wayback module not available, skipping archival")
        if backfill_project_history is not None:
            print("\n[POST-EXTRACTION] Wayback history backfill for new projects...")
            try:
            import json as _json
            rows = conn.execute(
                "SELECT norm_key, name, province, status, statusHistory FROM projects "
                "WHERE (history_backfilled IS NULL OR history_backfilled = 0) LIMIT 20"
            ).fetchall()
            backfill_count = 0
            for row in rows:
                p = dict(row)
                name = p.get('name', '')
                status_history = p.get('statusHistory', '[]')
                if isinstance(status_history, str):
                    try:
                        status_history = _json.loads(status_history)
                    except Exception:
                        status_history = []
                source_url = ''
                for entry in (status_history or []):
                    src = entry.get('source', {})
                    if src.get('url'):
                        source_url = src['url']
                        break
                if not source_url or not name:
                    continue
                print(f"  [Backfill] {name[:50]}...", end=" ", flush=True)
                result = backfill_project_history(
                    project_name=name,
                    source_url=source_url,
                    province=p.get('province', ''),
                    current_status=p.get('status', ''),
                    current_detail='',
                    today=date.today().isoformat(),
                )
                if result.get('history_backfilled'):
                    history = result.get('statusHistory', [])
                    full_history = history + (status_history or [])
                    with conn:
                        conn.execute(
                            "UPDATE projects SET history_backfilled = 1, "
                            "history_earliest_date = ?, statusHistory = ? "
                            "WHERE norm_key = ?",
                            (result.get('history_earliest_date', ''),
                             _json.dumps(full_history, ensure_ascii=False),
                             p['norm_key'])
                        )
                    backfill_count += 1
                    print(f"{result.get('snapshots_processed', 0)} snapshots")
                else:
                    print("skipped")
            if backfill_count:
                print(f"  [Backfill] {backfill_count} projects backfilled")
        except Exception as e:
            print(f"  [Backfill] Error (non-critical): {type(e).__name__}: {e}")

        # ── Deep-sweep: re-attempt backfill for history_backfilled=false ─
        if deep_sweep and backfill_project_history is not None:
            print("\n[DEEP-SWEEP] Re-attempting backfill for unbackfilled projects...")
            try:
                import json as _json
                rows = conn.execute(
                    "SELECT norm_key, name, province, statusHistory FROM projects "
                    "WHERE (history_backfilled IS NULL OR history_backfilled = 0)"
                ).fetchall()
                for row in rows:
                    p = dict(row)
                    name = p.get('name', '')
                    sh = p.get('statusHistory', '[]')
                    if isinstance(sh, str):
                        try:
                            sh = _json.loads(sh)
                        except Exception:
                            sh = []
                    source_url = ''
                    for entry in (sh or []):
                        src = entry.get('source', {})
                        if src.get('url'):
                            source_url = src['url']
                            break
                    if not source_url or not name:
                        continue
                    result = backfill_project_history(
                        project_name=name,
                        source_url=source_url,
                        province=p.get('province', ''),
                    )
                    if result.get('history_backfilled') and result.get('statusHistory'):
                        full_history = result['statusHistory'] + (sh or [])
                        with conn:
                            conn.execute(
                                "UPDATE projects SET history_backfilled = 1, "
                                "history_earliest_date = ?, statusHistory = ? "
                                "WHERE norm_key = ?",
                                (result.get('history_earliest_date', ''),
                                 _json.dumps(full_history, ensure_ascii=False),
                                 p['norm_key'])
                            )
            except Exception as e:
                print(f"  [Deep-sweep backfill] Error: {type(e).__name__}")

        # ── Stale project checks ──────────────────────────────────
        try:
            print("\n[POST-EXTRACTION] Checking stale projects...")
            _check_stale_projects(conn)
        except Exception as e:
            print(f"  [STALE] Stale check failed: {type(e).__name__}: {e}")
            run_log.log_error("stale_check", e)

        # ── Evidence URL verification ──────────────────────────────
        try:
            _verify_project_evidence_urls(conn)
        except Exception as e:
            print(f"  [URL-CHECK] Failed: {type(e).__name__}: {e}")

        # ── Confidence decay ─────────────────────────────────────
        try:
            from confidence_decay import apply_confidence_decay
            decay_result = apply_confidence_decay(conn)
        except Exception as e:
            print(f"  [DECAY] Failed: {type(e).__name__}: {e}")

        # ── Lifecycle monitoring (Gemini status checks) ──────────
        try:
            from lifecycle_monitor import run_lifecycle_search
            monitor_result = run_lifecycle_search(conn)
        except Exception as e:
            print(f"  [MONITOR] Failed: {type(e).__name__}: {e}")

        # ── Cross-project anomaly detection ──────────────────────
        try:
            from anomaly_detection import check_cross_project_anomalies
            all_snap = get_all_projects(conn)
            cross_anomalies = check_cross_project_anomalies(all_snap)
            if cross_anomalies:
                print(f"  [ANOMALY] {len(cross_anomalies)} possible cross-province duplicates")
        except Exception as e:
            print(f"  [ANOMALY] Failed: {type(e).__name__}: {e}")

        # ── Capacity tiers (T1-T6, fills remaining Gemini budget) ──
        cap_result = None
        try:
            from capacity_scheduler import run_capacity_tiers
            cap_result = run_capacity_tiers(conn)
        except Exception as e:
            print(f"  [CAPACITY] Failed: {type(e).__name__}: {e}")

        # ── STEP 2J: Read GitHub Issues submissions ──────────
        try:
            from github_issues_reader import fetch_issue_submissions
            issues_result = fetch_issue_submissions(conn)
            if issues_result.get("skipped"):
                print(f"  [ISSUES] Skipped: {issues_result.get('reason', 'unknown')}")
            elif issues_result.get("processed", 0) > 0:
                print(f"  [ISSUES] {issues_result['processed']} new submissions "
                      f"({issues_result.get('new_projects', 0)} projects, "
                      f"{issues_result.get('corrections', 0)} corrections)")
            else:
                print("  [ISSUES] No new submissions")
        except Exception as e:
            print(f"  [ISSUES] Warning: {e}")

        # ── STEP 2K: Process missed project submissions ──────────
        try:
            from missed_projects import process_pending_submissions
            missed_result = process_pending_submissions(conn, max_queries=20)
            if missed_result.get("processed"):
                print(f"  [MISSED] {missed_result['processed']} submissions, "
                      f"{missed_result['enriched']} enriched")
        except Exception as e:
            print(f"  [MISSED] Failed: {type(e).__name__}: {e}")

        # ── STEP 2K: Apply pipeline learning ─────────────────────
        try:
            from learning_store import apply_pending_improvements
            applied = apply_pending_improvements(conn)
            if applied:
                print(f"  [LEARN] Applied {applied} improvements")
        except Exception as e:
            print(f"  [LEARN] Failed: {type(e).__name__}: {e}")

        # ── STEP 2K: Claude reasoning layer ──────────────────────
        try:
            from pipeline_store import store_follow_up_queries
            from claude_reasoning import (
                analyze_provincial_gaps_sync,
                recover_failed_extractions_sync,
                analyze_dedup_sync, store_dedup_results,
                run_meta_analysis_sync, store_meta_analysis,
            )

            print("\n[CLAUDE] Reasoning layer...")

            # Task 1: Gap analysis on provincial sweep results
            sweep_by_province = {}
            for p in (cap_result or {}).get("_t2_projects", []):
                sweep_by_province.setdefault(p.get("province", "Unknown"), []).append(p)
            if sweep_by_province:
                follow_ups = analyze_provincial_gaps_sync(sweep_by_province)
                if follow_ups:
                    store_follow_up_queries(db=None, queries=follow_ups, conn=conn)

            # Task 2: Recover failed RSS extractions
            rss_failed = rss_failed_articles if 'rss_failed_articles' in locals() else []
            if rss_failed:
                recovered = recover_failed_extractions_sync(rss_failed)
                if recovered:
                    upsert_flat_projects(conn, recovered)
                    print(f"  [CLAUDE] Recovered {len(recovered)} projects from failed extractions")

            # Task 4: Dedup analysis on this week's new projects
            flat_for_dedup = all_flat_projects if 'all_flat_projects' in locals() else []
            if flat_for_dedup and len(flat_for_dedup) > 10:
                dedup_flags = analyze_dedup_sync(flat_for_dedup[:200])
                if dedup_flags:
                    store_dedup_results(conn, dedup_flags)

            # Task 5: Monthly meta-analysis (first week only)
            if datetime.now().day <= 7:
                print("  [CLAUDE] Running monthly meta-analysis...")
                meta = run_meta_analysis_sync(conn)
                if meta:
                    store_meta_analysis(conn, meta)

        except Exception as e:
            print(f"  [CLAUDE] Reasoning failed: {type(e).__name__}: {e}")

        # ── STEP 2M: Sector trend analysis ──────────────────────
        try:
            from sector_trends import compute_project_trends
            from indicator_trends import compute_indicator_trends
            from cross_reference import cross_reference_trends
            from weekly_trend_report import generate_trend_report

            sector_data = compute_project_trends(conn)
            indicator_data = compute_indicator_trends(conn)
            xref_data = cross_reference_trends(indicator_data, sector_data)
            trend_report = generate_trend_report(
                sector_data, indicator_data, xref_data, conn=conn
            )

            # Store trend snapshot in SQLite
            if sector_data and not sector_data.get("error"):
                save_trend_snapshot(conn, {
                    "week_of": datetime.now().strftime("%Y-W%W"),
                    "snapshot": sector_data,
                })

            # Store cross-reference data for frontend
            if xref_data and not xref_data.get("error"):
                save_dashboard_state(conn, "cross_references", {
                    "data": xref_data,
                    "updated_at": datetime.now().isoformat()
                })
                print(f"  [TRENDS] Cross-reference data stored to dashboard_state")

            if trend_report.get("narrative"):
                print(f"  [TRENDS] Report generated ({len(trend_report['narrative'])} chars)")
        except Exception as e:
            print(f"  [TRENDS] Failed: {type(e).__name__}: {e}")
            run_log.log_error("trends_analysis", e)

        run_log.log_step("trends_analysis")

        # ── STEP 2N: Provincial policy monitor ──────────────────
        policy_developments = []
        try:
            from provincial_policy_monitor import process_policy_feeds
            policy_developments = process_policy_feeds(conn, since_days=7)
        except Exception as e:
            print(f"  [POLICY] Failed: {type(e).__name__}: {e}")

        # ── STEP 2N: Canadian commodity indicators ──────────────
        commodity_data = {}
        try:
            from canadian_markets import fetch_and_store_commodities
            commodity_data = fetch_and_store_commodities(conn)
        except Exception as e:
            print(f"  [MARKETS] Failed: {type(e).__name__}: {e}")

        # ── STEP 2N: Economic event calendar ────────────────────
        upcoming_events = []
        try:
            from event_calendar import get_and_store_events
            upcoming_events = get_and_store_events(conn, days_ahead=14)
        except Exception as e:
            print(f"  [CALENDAR] Failed: {type(e).__name__}: {e}")

        # ── STEP 2N: Weekly narrative briefing (Claude Sonnet) ──
        try:
            import asyncio as _aio
            from weekly_briefing import generate_weekly_briefing, store_and_distribute_briefing

            # Gather context from earlier steps
            _sector_data = sector_data if 'sector_data' in locals() else {}
            _indicator_data = indicator_data if 'indicator_data' in locals() else {}
            _xref_data = xref_data if 'xref_data' in locals() else {}

            # Market commentary via Claude Sonnet
            market_commentary_text = None
            try:
                from canadian_markets import generate_market_commentary
                _project_summary = {
                    "total": _sector_data.get("total_projects", 0),
                    "by_sector": _sector_data.get("sectors", {}),
                }
                market_commentary_result = _aio.run(
                    generate_market_commentary(
                        commodity_data, _project_summary, policy_developments
                    )
                )
                if market_commentary_result:
                    market_commentary_text = market_commentary_result.get("text", "")
                    print(f"  [MARKETS] Commentary generated ({len(market_commentary_text)} chars)")
            except Exception as e:
                print(f"  [MARKETS] Commentary failed: {type(e).__name__}: {e}")

            # Pre-event analysis for high-significance events
            pre_event_analyses = []
            for evt in upcoming_events:
                if evt.get("significance") == "high":
                    try:
                        from event_calendar import generate_pre_event_analysis
                        analysis = _aio.run(
                            generate_pre_event_analysis(evt, _indicator_data, [])
                        )
                        if analysis:
                            pre_event_analyses.append({
                                "event": evt.get("name", ""),
                                "date": evt.get("date", ""),
                                "analysis": analysis.get("text", ""),
                            })
                    except Exception as e:
                        print(f"  [WARN] Pre-event analysis failed ({evt.get('name', '?')}): {e}")

            if pre_event_analyses:
                print(f"  [CALENDAR] {len(pre_event_analyses)} pre-event analyses generated")

            # ── STEP 2P: Under the Microscope ──────────────────────
            microscope_text = None
            try:
                from under_the_microscope import (
                    select_microscope_topic, generate_microscope_analysis,
                    store_microscope_history, get_affected_projects,
                )
                # Gather RSS articles for topic selection
                _rss_arts = rss_items if 'rss_items' in dir() and rss_items else []
                topic_context = _aio.run(select_microscope_topic(
                    conn, _rss_arts, _indicator_data, _xref_data
                ))
                if topic_context and topic_context.get("topic"):
                    print(f"  [MICROSCOPE] Topic: {topic_context['topic']}")
                    affected = get_affected_projects(conn, topic_context)
                    microscope_result = _aio.run(generate_microscope_analysis(
                        topic_context, affected, _indicator_data
                    ))
                    if microscope_result:
                        microscope_text = microscope_result.get("text", "")
                        store_microscope_history(conn, topic_context["topic"], microscope_text)
                        # Store current microscope in SQLite dashboard_state
                        save_dashboard_state(conn, "microscope_current", {
                            "topic": topic_context["topic"],
                            "sectors": topic_context.get("sectors", []),
                            "text": microscope_text,
                            "week": datetime.now().strftime("%Y-W%W"),
                            "updated_at": datetime.now().isoformat()
                        })
                        cost = microscope_result.get("cost_usd", 0)
                        print(f"  [MICROSCOPE] Generated: {len(microscope_text)} chars, ${cost:.4f}")
                else:
                    print("  [MICROSCOPE] No dominant topic identified")
            except Exception as e:
                print(f"  [MICROSCOPE] Failed: {type(e).__name__}: {e}")

            # Generate weekly briefing
            print("\n[BRIEFING] Generating weekly intelligence briefing...")
            briefing = _aio.run(generate_weekly_briefing(
                project_trends=_sector_data,
                indicator_trends=_indicator_data,
                cross_insights=_xref_data,
                policy_developments=policy_developments,
                market_commentary=market_commentary_text,
                upcoming_events=upcoming_events,
                pre_event_analyses=pre_event_analyses,
                microscope_text=microscope_text,
            ))

            if briefing:
                _aio.run(store_and_distribute_briefing(conn, briefing))
                cost = briefing.get("cost_usd", 0)
                print(f"  [BRIEFING] Complete: {len(briefing.get('text', ''))} chars, ${cost:.4f}")

                # ── STEP 2P: Briefing export (PDF + DOCX → Firebase Storage) ──
                try:
                    from briefing_export import export_and_upload
                    export_urls = export_and_upload(conn)
                    if export_urls:
                        print(f"  [EXPORT] Briefing exports uploaded: {list(export_urls.keys())}")
                    else:
                        print("  [EXPORT] No exports generated (missing dependencies?)")
                except Exception as e:
                    print(f"  [EXPORT] Briefing export failed: {type(e).__name__}: {e}")
            else:
                print("  [BRIEFING] Skipped (no API key or API error)")

        except Exception as e:
            print(f"  [BRIEFING] Failed: {type(e).__name__}: {e}")
            run_log.log_error("briefing_generation", e)

        run_log.log_step("briefing_generation")

        # ── STEP 2G: Structured data signals ─────────────────────
        try:
            from statcan_permits import detect_permit_anomalies
            from lobbyist_registries import search_lobbyist_registries

            print("\n[2G] Structured data signal detection...")

            permit_anomalies = detect_permit_anomalies(conn)
            if permit_anomalies:
                from pipeline_store import store_follow_up_queries as _store_fq
                _store_fq(db=None, queries=permit_anomalies, conn=conn)
                print(f"  [PERMITS] {len(permit_anomalies)} anomalies → follow-up queries")

            lobby_signals = search_lobbyist_registries()
            if lobby_signals:
                from pipeline_store import store_follow_up_queries as _store_fq2
                _store_fq2(db=None, queries=lobby_signals, conn=conn)
                print(f"  [LOBBY] {len(lobby_signals)} signals → follow-up queries")

        except Exception as e:
            print(f"  [2G signals] Failed: {type(e).__name__}: {e}")

        # ── STEP 5d: StatCan indicators snapshot ───────────────────
        try:
            save_statcan_indicators(conn, statcan_inds)
        except Exception as e:
            print(f"  [WARN] StatCan snapshot save failed: {e}")
            run_log.log_error("statcan_snapshot", e)

        # ── STEP 6: Timeseries ─────────────────────────────────────
        try:
            append_to_timeseries(final_payload, financial_markets, boc_data['rate'] or 'N/A')
        except Exception as e:
            print(f"  [WARN] Timeseries append failed: {e}")
            run_log.log_error("timeseries", e)

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
            final_payload['consumer_sentiment'] = sentiment_result
            try:
                save_dashboard_state(conn, 'latest_sentiment', {
                    'updatedAt': date.today().isoformat(),
                    'consumer_sentiment': sentiment_result,
                })
                print("  [Sentiment] Saved to SQLite")
            except Exception as e:
                print(f"  [Sentiment] SQLite write failed (non-critical): {e}")

        # ── Wayback save for all verified citation URLs ────────────
        all_verified_sources = final_payload.pop('_all_verified_sources', [])
        if all_verified_sources and wayback_save is not None:
            try:
                print(f"\n[POST-EXTRACTION] Archiving {len(all_verified_sources)} verified citation URLs...")
                archived = 0
                for src in all_verified_sources:
                    url = src.get('url', '')
                    if url and not src.get('archive_url'):
                        archive_url = wayback_save(url)
                        if archive_url:
                            src['archive_url'] = archive_url
                            archived += 1
                if archived:
                    print(f"  [Wayback] Archived {archived} citation URLs")
            except Exception as e:
                print(f"  [Wayback] Citation archiving failed: {type(e).__name__}: {e}")
                run_log.log_error("wayback_citations", e)

        # ── STEP 8: Quality Report (non-critical) ────────────────────
        try:
            print("\n[STEP 8] Generating quality report...")
            _discovery_stats = {
                'gemini_projects': len(gemini_projects) if gemini_projects else 0,
                'tavily_extractions': len(extracted_articles) if 'extracted_articles' in dir() else 'N/A',
                'projects_registries': len(registry_projects) if registry_projects else 0,
                'projects_rss': len(rss_projects) if 'rss_projects' in dir() and rss_projects else 0,
                'projects_gemini': len(gemini_projects) if gemini_projects else 0,
            }
            _writing_stats = {}
            _citation_audit = final_payload.get('citation_audit', {})
            if _citation_audit:
                _writing_stats = {
                    'total_citations': _citation_audit.get('total_citations', 0),
                    'verified_citations': _citation_audit.get('total_citations', 0) - _citation_audit.get('total_failed', 0),
                    'removed_citations': _citation_audit.get('total_failed', 0),
                    'audit_pass_rate': 'ALL PASSED' if _citation_audit.get('passed') else 'SOME FAILED',
                    'per_call': _citation_audit.get('calls', []),
                    'officials_referenced': 'N/A',
                    'officials_available': len(_WATCHLIST.get('public_figures_canada', [])) + len(_WATCHLIST.get('provincial_officials', [])),
                }
            _sentiment_stats = {}
            _sentiment_result = hard_data.get('_sentiment_result')
            if _sentiment_result:
                _sentiment_stats = {
                    'reddit_posts': _sentiment_result.get('reddit_posts', 'N/A'),
                    'reddit_comments': _sentiment_result.get('reddit_comments', 'N/A'),
                    'trends_queries': _sentiment_result.get('trends_queries', 'N/A'),
                    'news_comments': _sentiment_result.get('news_comments', 'N/A'),
                    'topics_count': len(_sentiment_result.get('topics', [])),
                    'sentiment_index': _sentiment_result.get('sentiment_index', 'N/A'),
                    'sentiment_label': _sentiment_result.get('sentiment_label', 'N/A'),
                    'categories': _sentiment_result.get('categories', {}),
                }
            generate_quality_report(
                conn=conn,
                discovery_stats=_discovery_stats,
                writing_stats=_writing_stats,
                sentiment_stats=_sentiment_stats,
            )
            run_log.log_step("quality_report")
        except Exception as e:
            print(f"  [QUALITY] Quality report failed: {type(e).__name__}: {e}")
            run_log.log_error("quality_report", e)

    finally:
        # ════════════════════════════════════════════════════════════════
        # CRITICAL — these steps ALWAYS run regardless of earlier failures
        # ════════════════════════════════════════════════════════════════

        # ── STEP 7: Final assembly + push to SQLite ─────────────────
        try:
            print("\n[STEP 7] Final assembly + push to SQLite...")
            final_payload.setdefault('updated_at', date.today().isoformat())
            final_payload.setdefault('consumer_pulse', '')
            final_payload.setdefault('industry_executive_summary', '')
            final_payload.pop('_citation_audit', None)

            # Build sources array with archive URLs
            all_verified_sources = locals().get('all_verified_sources', [])
            sources_with_archives = []
            for src in all_verified_sources:
                sources_with_archives.append({
                    'url': src.get('url', ''),
                    'title': src.get('title', ''),
                    'archive_url': src.get('archive_url', ''),
                })
            if sources_with_archives:
                final_payload['sources'] = sources_with_archives

            toronto_tz = pytz.timezone('America/Toronto')
            today = datetime.now(toronto_tz)
            dated_id = today.strftime('%Y-%m-%d')
            save_dashboard_state(conn, 'newsletter_latest', final_payload)
            save_dashboard_state(conn, f'newsletter_{dated_id}', final_payload)
            if final_payload.get('_analysis_incomplete'):
                print("[WARN] Dashboard updated with INCOMPLETE analysis — Claude calls failed.")
            else:
                print("[OK] Dashboard successfully updated.")
            run_log.log_step("step_7_firestore_push")
        except Exception as e:
            print(f"[ERROR] Step 7 (SQLite export) failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            run_log.log_error("step_7_export", e, recovered=False)

        # ── Log Tavily usage ──────────────────────────────────────────
        try:
            from tavily_search import get_tavily_credits_used
            tavily_credits = get_tavily_credits_used(conn)
            run_log.log_metric("api_usage", "tavily_searches", tavily_searches_count)
            run_log.log_metric("api_usage", "tavily_month_total", tavily_credits.get("used", 0))
        except Exception as e:
            print(f"  [WARN] Tavily usage logging failed: {e}")

        # ── STEP 9: Static JSON export ─────────────────────────────────
        try:
            print("\n[STEP 9] Exporting static JSON files...")
            export_result = export_all(conn=conn)
            print(f"[OK] Exported {export_result['file_count']} files to {export_result['output_dir']}")
            run_log.log_step("step_9_json_export")
        except Exception as e:
            print(f"[ERROR] Static JSON export failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            run_log.log_error("json_export", e, recovered=False)

        # ── Claude API cost summary ──────────────────────────────────
        try:
            print(f"\n[COST SUMMARY] Claude API: {_claude_run_tokens['input']:,} input + {_claude_run_tokens['output']:,} output tokens = ${_claude_run_cost_usd:.4f} (cap: ${CLAUDE_COST_CAP_USD:.2f})")
            run_log.log_metric("api_usage", "claude_input_tokens", _claude_run_tokens["input"])
            run_log.log_metric("api_usage", "claude_output_tokens", _claude_run_tokens["output"])
            run_log.log_metric("api_usage", "claude_cost_usd", round(_claude_run_cost_usd, 4))
        except Exception as e:
            print(f"  [WARN] Cost summary failed: {e}")

        # ── Service health summary ─────────────────────────────────
        health_status = health.get_status()
        if health_status["dead"]:
            print(f"\n[SERVICE HEALTH] Dead services: {health_status['dead']}")
        run_log.log_metric("api_usage", "service_health", health_status)

        # ── Finalize pipeline run log ─────────────────────────────────
        if final_payload.get('_analysis_incomplete'):
            run_log.finalize("partial")
        else:
            run_log.finalize("success")


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
    print("  Checking projects table...")
    for doc in get_all_projects(conn):
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
    print("  Checking newsletter_latest citations...")
    latest = get_dashboard_state(conn, 'newsletter_latest')
    if latest:
        payload = latest
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
        help='Monthly deep NAICS sweep (20 sectors x 13 provinces via Gemini compound queries)'
    )
    parser.add_argument(
        '--test-feeds', action='store_true',
        help='Test all government RSS feed URLs and report which are live/dead. Does not run the pipeline.'
    )
    parser.add_argument(
        '--seed-projects', action='store_true',
        help='Full project seed from all sources: registries + Gemini compound discovery.'
    )
    parser.add_argument(
        '--audit-citations', action='store_true',
        help='Re-verify ALL URLs in DB + newsletter. Flag dead links, attempt Wayback archive.'
    )
    parser.add_argument(
        '--test-sentiment', action='store_true',
        help='Run sentiment collection only (Reddit, Trends, CBC), print results. No pipeline.'
    )
    parser.add_argument(
        '--indicators-only', action='store_true',
        help='Daily mode: fetch hard indicators only (BoC, StatCan, FRED, etc.), skip AI analysis.'
    )
    parser.add_argument(
        '--known-sweep', action='store_true',
        help='One-time comprehensive sweep for ALL active Canadian projects (no time constraint). Seeds 50+ known projects + runs ~200 Gemini queries.'
    )
    parser.add_argument(
        '--audit-archetypes', action='store_true',
        help='Scan rejected articles for emerging archetype patterns (monthly/quarterly).'
    )
    args = parser.parse_args()

    if args.test_sentiment:
        from sentiment import collect_sentiment, compute_sentiment_index
        print("Running sentiment collection (test mode)...")
        result = collect_sentiment()
        if result:
            idx = result.get('sentiment_index', 'N/A')
            topics = result.get('topics', [])
            print(f"\nSentiment index: {idx}")
            print(f"Topics collected: {len(topics)}")
            for t in topics[:10]:
                print(f"  - {t.get('topic', '?')}: {t.get('sentiment', '?')} ({t.get('source', '?')})")
            if len(topics) > 10:
                print(f"  ... and {len(topics) - 10} more")
        else:
            print("No sentiment data collected.")
    elif args.test_feeds:
        rss_monitor.test_feeds()
    elif args.seed_projects:
        seed_projects(deep_sweep=args.deep_sweep)
    elif args.audit_citations:
        audit_all_citations()
    elif args.known_sweep:
        # One-time comprehensive project sweep
        print("\n[KNOWN-SWEEP] Running comprehensive project sweep...")
        from known_project_sweep import seed_known_projects, run_known_project_sweep_sync
        seed_known_projects(conn)
        result = run_known_project_sweep_sync(conn)
        print(f"\n[KNOWN-SWEEP] Complete: {result}")
    elif args.audit_archetypes:
        from archetype_audit import run_archetype_audit
        run_archetype_audit(conn=conn, days=30)
    elif args.indicators_only:
        # Daily mode: hard-data refresh only (no AI calls, no project discovery)
        daily_log = PipelineRunLogger(conn=conn, run_type="daily_indicators")
        daily_log.start()
        print("\n[DAILY MODE] Fetching hard indicators only...")
        try:
            from gov_sources import fetch_primary_indicators
            indicators = fetch_primary_indicators()
            daily_log.log_step("fetch_indicators")
            if indicators:
                dated_id = date.today().strftime("%Y-%m-%d")
                save_dashboard_state(conn, f'timeseries_{dated_id}', indicators)
                print(f"[OK] Indicators stored to dashboard_state/timeseries_{dated_id}")
                daily_log.log_step("store_indicators")
            else:
                print("[WARN] No indicators fetched or no DB connection")

            # Export static JSON so the GitHub Pages site reflects fresh indicator data
            print("\n[DAILY MODE] Exporting static JSON files...")
            try:
                export_result = export_all(conn=conn)
                print(f"[OK] Exported {export_result['file_count']} files to {export_result['output_dir']}")
                daily_log.log_step("step_9_json_export")
            except Exception as e:
                print(f"[WARN] Static JSON export failed (non-fatal): {e}")
                import traceback
                traceback.print_exc()
                daily_log.log_error("json_export", e, recovered=True)

            if indicators:
                daily_log.finalize("success")
            else:
                daily_log.finalize("partial")
        except Exception as e:
            print(f"[ERROR] Daily indicators failed: {e}")
            daily_log.log_error("daily_indicators", e, recovered=False)
            daily_log.finalize("error")
    else:
        update_dashboard(deep_sweep=args.deep_sweep)
