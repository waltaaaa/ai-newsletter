"""Phase 1: Data Collection — Hard data from APIs.

Fetches all primary-source data (Yahoo Finance, BoC Valet, StatCan WDS,
CMHC, FRED, ECB, BoE, World Bank) and archives to indicator_history.
"""

import traceback
import re
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta

import rss_monitor
from db import save_indicator
from gov_sources import fetch_statcan_indicators
from pipeline_store import cache as _cache


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Yahoo Finance — Commodities
# ─────────────────────────────────────────────────────────────────────────────

def get_live_commodities():
    print("Fetching live commodity data from Yahoo Finance...")

    TICKER_MAP = [
        # Energy
        ("CL=F",  "Energy",                     "Crude Oil (WTI)",   "bbl",     lambda x: f"${x:.2f}"),
        ("BZ=F",  "Energy",                     "Crude Oil (Brent)", "bbl",     lambda x: f"${x:.2f}"),
        ("NG=F",  "Energy",                     "Natural Gas",       "MMBtu",   lambda x: f"${x:.3f}"),
        ("MTF=F", "Energy",                     "Coal (Newcastle)",  "t",       lambda x: f"${x:.2f}"),
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
        # Crypto
        ("BTC-USD", "Crypto",                   "Bitcoin",           "USD",     lambda x: f"${x:,.0f}"),
        ("ETH-USD", "Crypto",                   "Ethereum",          "USD",     lambda x: f"${x:,.0f}"),
        # Shipping
        ("BDRY",  "Shipping",                   "Dry Bulk (BDI proxy)", "USD",  lambda x: f"${x:.2f}"),
    ]

    CATEGORY_COLORS = {
        "Energy":                     "text-orange-500",
        "Precious Metals":            "text-yellow-500",
        "Base Metals":                "text-slate-500",
        "Agriculture - Grains":       "text-lime-600",
        "Agriculture - Softs":        "text-emerald-600",
        "Agriculture - Oils & Meals": "text-green-600",
        "Crypto":                     "text-violet-500",
        "Shipping":                   "text-blue-600",
        "Fertilizers":                "text-teal-600",
        "Livestock":                  "text-rose-500",
    }

    all_tickers = [t[0] for t in TICKER_MAP]

    # Check cache first (12-hour TTL — commodities update daily)
    cached = _cache.get("yfinance:commodities")
    if cached is not None:
        print(f"  Using cached commodity data ({len(cached.get('structured', []))} categories)")
        return cached

    import yfinance as yf
    try:
        data = yf.download(all_tickers, period="1y", progress=False)['Close']
    except Exception as e:
        print(f"  Batch download failed: {e}")
        data = None

    categories = {}
    summary = {}

    def _get_ticker_series(ticker):
        """Get price series for a ticker from batch data, falling back to individual download."""
        if data is not None:
            try:
                col = data[ticker] if len(all_tickers) > 1 else data
                col = col.dropna()
                if len(col) >= 2:
                    return col
            except (KeyError, TypeError):
                pass
        # Individual fallback for tickers that failed in batch
        try:
            ind = yf.download(ticker, period="1y", progress=False)['Close']
            if hasattr(ind, 'dropna'):
                ind = ind.dropna()
            if len(ind) >= 2:
                return ind
        except Exception:
            pass
        return None

    for ticker, category, name, unit, fmt in TICKER_MAP:
        try:
            col = _get_ticker_series(ticker)
            if col is None or len(col) < 2:
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


# ─────────────────────────────────────────────────────────────────────────────
# Yahoo Finance — Financial Markets
# ─────────────────────────────────────────────────────────────────────────────

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
    import yfinance as yf
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


# ─────────────────────────────────────────────────────────────────────────────
# Bank of Canada
# ─────────────────────────────────────────────────────────────────────────────

def get_boc_rate() -> dict:
    """Return {'rate': '2.75%', 'prev': '3.00%', 'date': 'YYYY-MM-DD'}."""
    print("Fetching live BoC Policy Rate...")
    try:
        url = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=2"
        response = requests.get(url, timeout=15).json()
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


# ─────────────────────────────────────────────────────────────────────────────
# CMHC Housing Starts
# ─────────────────────────────────────────────────────────────────────────────

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
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
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
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
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


# ─────────────────────────────────────────────────────────────────────────────
# StatCan WDS
# ─────────────────────────────────────────────────────────────────────────────

# StatCan WDS endpoint (POST, JSON, public — no API key required)
_STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

# National CPI, unemployment — fetched directly from StatCan WDS
_CPI_VECTOR           = 41690973  # Table 18-10-0004-01, CPI All-items Canada
_UNEMP_VECTOR         = 2062815   # Table 14-10-0287-01, LFS unemployment rate Canada SA
_HOUSING_STARTS_VECTOR = 44176028  # NOTE: actually Table 18-10-0049-01 (NHPI) — not used; national housing starts fetched via _cmhc_housing_starts() instead

# National employment and participation — StatCan WDS vector IDs
# NOTE: v2062809 returns total employment (thousands), NOT the rate.
# Canada employment rate = v2062811 (unemp v2062815 minus 4, matching
# the provincial pattern where emprate = unemp_vector + 2).
# v2062803 (participation rate) is TERMINATED — returns no data.
# For now, national emp/part rates come from the pipeline's provincial
# aggregation path, not from direct WDS fetch. These vectors are kept
# as documentation only.
_EMPRATE_VECTOR   = 2062811   # Table 14-10-0287-01, Employment rate Canada SA (needs verification when StatCan is available)
_PARTRATE_VECTOR  = 2062803   # Table 14-10-0287-01, Participation rate Canada SA (TERMINATED — returns no data)

# StatCan WDS vector IDs for Table 36-10-0434-01
# Real GDP at basic prices (2012=100), monthly, seasonally adjusted
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


# ─────────────────────────────────────────────────────────────────────────────
# National Indicators
# ─────────────────────────────────────────────────────────────────────────────

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

    # Employment rate — latest observation (sanity-checked like provincial rates)
    emprate_obs = wds_data.get(_EMPRATE_VECTOR, [])
    if emprate_obs:
        try:
            val = float(emprate_obs[-1]['value'])
            if 30.0 <= val <= 80.0:
                values['employmentRate']    = f"{val:.1f}%"
                sources['employmentRate']   = 'StatCan'
                obs_dates['employmentRate'] = emprate_obs[-1].get('refPer', '')
            else:
                print(f"  [WARN] National employment rate out of range: {val}, skipping")
        except Exception as e:
            print(f"  [WARN] Employment rate parsing failed: {e}")
    if len(emprate_obs) >= 2:
        try:
            prev_val = float(emprate_obs[-2]['value'])
            if 30.0 <= prev_val <= 80.0:
                prev_values['employmentRate'] = f"{prev_val:.1f}%"
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


# ─────────────────────────────────────────────────────────────────────────────
# Provincial Indicators
# ─────────────────────────────────────────────────────────────────────────────

# Provincial unemployment — StatCan WDS vector IDs
# Table 14-10-0287-01 (PID 14100287): Unemployment rate, both sexes, 15 years+, SA
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

# Provincial CPI — StatCan WDS vector IDs
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

# Provincial real GDP — StatCan WDS vector IDs
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

# Provincial employment rate — StatCan WDS vector IDs
# Table 14-10-0287-01 (PID 14100287): Employment rate, both sexes, 15 years+, SA
# Offset: unemployment_rate_vector + 2
_PROV_EMPRATE_VIDS = {
    "Newfoundland and Labrador": 2063006,
    "Prince Edward Island":      2063195,
    "Nova Scotia":               2063384,
    "New Brunswick":             2063573,
    "Quebec":                    2063762,
    "Ontario":                   2063951,
    "Manitoba":                  2064140,
    "Saskatchewan":              2064329,
    "Alberta":                   2064518,
    "British Columbia":          2064707,
}

# Provincial participation rate — StatCan WDS vector IDs
# Table 14-10-0287-01 (PID 14100287): Participation rate, both sexes, 15 years+, SA
# Offset: unemployment_rate_vector + 1
_PROV_PARTRATE_VIDS = {
    "Newfoundland and Labrador": 2063005,
    "Prince Edward Island":      2063194,
    "Nova Scotia":               2063383,
    "New Brunswick":             2063572,
    "Quebec":                    2063761,
    "Ontario":                   2063950,
    "Manitoba":                  2064139,
    "Saskatchewan":              2064328,
    "Alberta":                   2064517,
    "British Columbia":          2064706,
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


# ─────────────────────────────────────────────────────────────────────────────
# Global Indicator Fetchers
# (US: FRED public CSV · EU: ECB SDW API · UK: BoE IADB)
# ─────────────────────────────────────────────────────────────────────────────

def _fred_latest(series_id: str) -> float | None:
    """Latest observation from FRED public CSV endpoint (no API key required)."""
    try:
        url  = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        for line in reversed(resp.text.strip().split('\n')):
            if line.startswith('DATE') or line.startswith('observation'):
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
        resp  = requests.get(url, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().split('\n'):
            if line.startswith('DATE') or line.startswith('observation'):
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
    """Latest Bank of England Bank Rate from BoE public IADB CSV download.

    Falls back to FRED series (BOEBRBA) if BoE endpoint returns HTML instead
    of CSV (the BoE changed their endpoint format periodically). The UK rate
    is also available via FRED, so this is non-critical — all UK data is
    covered by FRED with the 45s timeout.
    """
    # Try BoE IADB first
    try:
        url  = ("https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
                "?Travel=NIxSUx&SeriesCodes=IUMABEDR&UsingCodes=Y&CSVF=TT&html.x=1&html.y=1")
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        # Detect HTML response (BoE sometimes returns a web page instead of CSV)
        if '</html>' in resp.text.lower() or '<html' in resp.text.lower()[:500]:
            print("  [WARN] BoE IADB returned HTML instead of CSV — trying FRED fallback")
            raise ValueError("BoE returned HTML")
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
        pass

    # Fallback: BoE Bank Rate via FRED (series BOEBRBA)
    try:
        return _fred_latest('BOEBRBA')
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
        resp  = requests.get(url, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().split('\n'):
            if line.startswith('DATE') or line.startswith('observation'):
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
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
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
    if 'unemployment' not in eu:
        v = _fred_latest('LRHUTTTTEUM156S')  # OECD harmonised EU unemployment via FRED
        if v is not None:
            eu['unemployment'] = f"{v:.1f}%";  eu['unemployment_src'] = 'FRED/OECD'
    if 'unemployment' not in eu:
        v = _world_bank_latest('EUU', 'SL.UEM.TOTL.ZS')  # World Bank fallback
        if v is not None:
            eu['unemployment'] = f"{v:.1f}%";  eu['unemployment_src'] = 'World Bank'
    # EA19 real GDP QoQ — FRED OECD Quarterly National Accounts series
    v = _fred_qoq('CLVMNACSCAB1GQEA19')
    if v is not None:
        eu['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  eu['gdp_src'] = 'FRED/Eurostat'
    if 'gdp' not in eu:
        v = _world_bank_latest('EUU', 'NY.GDP.MKTP.KD.ZG')  # World Bank fallback
        if v is not None:
            eu['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  eu['gdp_src'] = 'World Bank'
    result['European Union'] = eu
    print(f"rate={eu.get('rate','—')} cpi={eu.get('cpi','—')} "
          f"unemp={eu.get('unemployment','—')} gdp={eu.get('gdp','—')}")

    # ── United Kingdom (BoE + FRED/OECD + World Bank fallbacks) ────
    print("  UK (BoE + FRED/ONS + World Bank)...", end=" ", flush=True)
    uk = {}
    # Rate: BoE IADB → FRED → FRED/OECD 3-month interbank
    v = _boe_bank_rate()
    if v is not None:
        uk['rate'] = f"{v:.2f}%";  uk['rate_src'] = 'BoE'
    if 'rate' not in uk:
        v = _fred_latest('IR3TIB01GBM156N')  # UK 3-month interbank rate (OECD via FRED)
        if v is not None:
            uk['rate'] = f"{v:.2f}%";  uk['rate_src'] = 'FRED/OECD'
    # CPI: FRED/OECD → World Bank
    v = _fred_yoy('GBRCPIALLMINMEI')
    if v is not None:
        uk['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['cpi_src'] = 'FRED/ONS'
    if 'cpi' not in uk:
        v = _world_bank_latest('GBR', 'FP.CPI.TOTL.ZG')
        if v is not None:
            uk['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['cpi_src'] = 'World Bank'
    # Unemployment: FRED/OECD → World Bank
    v = _fred_latest('LRHUTTTTGBM156S')
    if v is not None:
        uk['unemployment'] = f"{v:.1f}%";  uk['unemployment_src'] = 'FRED/ONS'
    if 'unemployment' not in uk:
        v = _world_bank_latest('GBR', 'SL.UEM.TOTL.ZS')
        if v is not None:
            uk['unemployment'] = f"{v:.1f}%";  uk['unemployment_src'] = 'World Bank'
    # GDP: FRED/OECD QoQ → FRED/OECD YoY → World Bank
    v = _fred_qoq('CLVMNACSCAB1GQGB')
    if v is not None:
        uk['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['gdp_src'] = 'FRED/ONS'
    if 'gdp' not in uk:
        v = _fred_latest('NAEXKP01GBQ657S')  # UK GDP growth rate QoQ (OECD via FRED)
        if v is not None:
            uk['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['gdp_src'] = 'FRED/OECD'
    if 'gdp' not in uk:
        v = _world_bank_latest('GBR', 'NY.GDP.MKTP.KD.ZG')
        if v is not None:
            uk['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  uk['gdp_src'] = 'World Bank'
    result['United Kingdom'] = uk
    print(f"rate={uk.get('rate','—')} cpi={uk.get('cpi','—')} "
          f"unemp={uk.get('unemployment','—')} gdp={uk.get('gdp','—')}")

    # ── China (World Bank Open Data + FRED/OECD) ──
    print("  China (World Bank + FRED/OECD)...", end=" ", flush=True)
    cn = {}
    v = _world_bank_latest('CHN', 'NY.GDP.MKTP.KD.ZG')  # GDP growth annual %
    if v is not None:
        cn['gdp'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  cn['gdp_src'] = 'World Bank'
    v = _world_bank_latest('CHN', 'FP.CPI.TOTL.ZG')     # CPI inflation annual %
    if v is not None:
        cn['cpi'] = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%";  cn['cpi_src'] = 'World Bank'
    # Unemployment: World Bank ILO modelled estimate
    v = _world_bank_latest('CHN', 'SL.UEM.TOTL.ZS')
    if v is not None:
        cn['unemployment'] = f"{v:.1f}%";  cn['unemployment_src'] = 'World Bank/ILO'
    # Rate: PBoC 1-year LPR not on free APIs — try FRED
    v = _fred_latest('INTDSRCNM193N')  # China interest rate (IMF via FRED)
    if v is not None:
        cn['rate'] = f"{v:.2f}%";  cn['rate_src'] = 'FRED/IMF'
    result['China'] = cn
    print(f"gdp={cn.get('gdp','—')} cpi={cn.get('cpi','—')} "
          f"unemp={cn.get('unemployment','—')} rate={cn.get('rate','—')}")

    # Cache for 24 hours
    if _cache:
        _cache.set("global_indicators", result, ttl_hours=24)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Industry GDP (StatCan WDS)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Primary Indicators (master fetcher)
# ─────────────────────────────────────────────────────────────────────────────

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
    print("\n[STEP 1b] Fetching ALL primary source indicators (parallel)...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_nat  = executor.submit(get_national_indicators)
        f_prov = executor.submit(get_provincial_indicators)
        f_glob = executor.submit(get_global_indicators)
        f_ind  = executor.submit(fetch_industry_indicators)
    nat  = f_nat.result()
    prov = f_prov.result()
    glob = f_glob.result()
    ind  = f_ind.result()

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


# ─────────────────────────────────────────────────────────────────────────────
# Archive to indicator_history
# ─────────────────────────────────────────────────────────────────────────────

def _archive_indicators_to_history(conn, primary_ind: dict) -> None:
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

    # Global indicators (US, EU, UK, China)
    for region, region_data in primary_ind.get('global', {}).items():
        for field, value in region_data.items():
            if field.endswith('_src') or not value or value == 'N/A':
                continue
            save_indicator(conn, {
                'indicator': f'global_{field}',
                'province': region,
                'date': today_str,
                'value': str(value),
                'unit': '%' if any(k in field.lower() for k in ['rate', 'cpi', 'gdp', 'unemployment']) else '',
                'source': region_data.get(f'{field}_src', ''),
                'frequency': 'monthly',
                'category': 'Global',
                'backfilled': False,
            })
            count += 1

    # Industry GDP (per-NAICS M/M and Y/Y from StatCan WDS)
    for naics_code, ind_data in primary_ind.get('industries', {}).items():
        if naics_code.startswith('_'):
            continue
        mm = ind_data.get('mm', 'N/A')
        yy = ind_data.get('yy', 'N/A')
        src = ind_data.get('src', 'StatCan')
        if mm and mm != 'N/A':
            save_indicator(conn, {
                'indicator': f'industry_gdp_mm_{naics_code}',
                'province': 'national',
                'date': today_str,
                'value': str(mm),
                'unit': '%',
                'source': src,
                'frequency': 'monthly',
                'backfilled': False,
            })
            count += 1
        if yy and yy != 'N/A':
            save_indicator(conn, {
                'indicator': f'industry_gdp_yy_{naics_code}',
                'province': 'national',
                'date': today_str,
                'value': str(yy),
                'unit': '%',
                'source': src,
                'frequency': 'monthly',
                'backfilled': False,
            })
            count += 1

    print(f"  [HISTORY] Archived {count} indicator values to indicator_history")


def _archive_market_data_to_history(conn, financial_markets: dict, commodity_data: dict, yield_data: dict) -> None:
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
        'Canola': 'canola',
        'Bitcoin': 'bitcoin', 'Ethereum': 'ethereum',
        'Dry Bulk (BDI proxy)': 'dry_bulk_shipping',
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

    # FRED commodity prices and bond spreads (IMF monthly + daily)
    FRED_COMMODITY_SERIES = {
        'iron_ore': ('PIORECRUSDM', 'USD/t'),
        'nickel': ('PNICKUSDM', 'USD/t'),
        'zinc': ('PZINCUSDM', 'USD/t'),
        'tin': ('PTINUSDM', 'USD/t'),
        'lead': ('PLEADUSDM', 'USD/t'),
        'lng_asia': ('PNGASJPUSDM', 'USD/MMBtu'),
        'ig_spread': ('BAMLC0A0CM', '%'),
        'hy_spread': ('BAMLH0A0HYM2', '%'),
        'yield_curve_10y2y': ('T10Y2Y', '%'),
    }
    for ind_name, (series_id, unit) in FRED_COMMODITY_SERIES.items():
        val = _fred_latest(series_id)
        if val is not None:
            _save(ind_name, str(val), unit, 'FRED')

    print(f"  [HISTORY] Archived {count} market data points to indicator_history")


# ─────────────────────────────────────────────────────────────────────────────
# GoC Yield Curve
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# News Context
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Phase entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(conn, context, logger):
    """Fetch all hard data from primary APIs."""
    step_name = "Phase 1: Data Collection"
    try:
        deep_sweep = context.get("mode") == "deep-sweep"

        # STEP 1: Hard Data (parallel fetch — all sources independent)
        print("\n[STEP 1] Fetching hard data (parallel)...")
        days_back = 30 if deep_sweep else 7

        results = {}
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(get_live_commodities): 'commodities',
                executor.submit(get_financial_markets): 'markets',
                executor.submit(get_boc_rate): 'boc',
                executor.submit(get_goc_yields): 'yields',
                executor.submit(rss_monitor.fetch_all_feeds, days_back): 'rss',
                executor.submit(fetch_statcan_indicators): 'statcan',
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"  [STEP 1] {key} fetch failed: {type(e).__name__}: {e}")
                    results[key] = {} if key not in ('rss',) else []

        commodity_data    = results.get('commodities', {})
        financial_markets = results.get('markets', {})
        boc_data          = results.get('boc', {})
        yield_data        = results.get('yields', {})
        rss_items         = results.get('rss', [])
        statcan_inds      = results.get('statcan', {})

        hard_data = {
            'commodities':       commodity_data,
            'financial_markets': financial_markets,
            'boc_rate':          boc_data['rate'] or 'N/A',
            'rss_items':         rss_items,
        }
        logger.log_step("step_1_hard_data")

        # STEP 1b: Primary indicators
        primary_ind  = fetch_primary_indicators()
        national_ind = primary_ind['national']
        prov_ind     = primary_ind['provinces']
        global_ind   = primary_ind['global']
        hard_data['primary_indicators'] = primary_ind

        try:
            _archive_indicators_to_history(conn, primary_ind)
        except Exception as e:
            print(f"  [HISTORY] Archive error (non-critical): {e}")

        try:
            _archive_market_data_to_history(conn, financial_markets, commodity_data, yield_data)
        except Exception as e:
            print(f"  [HISTORY] Market archive error (non-critical): {e}")

        # STEP 1c: Extended StatCan indicators (investment, employment, trade, housing)
        statcan_ext = {}
        try:
            from statcan_extended import run_extended_statcan
            pipeline_mode = context.get("mode", "weekly")
            statcan_ext = run_extended_statcan(conn, mode=pipeline_mode)
        except ImportError:
            print("  [WARN] statcan_extended not available — skipping")
        except Exception as e:
            print(f"  [WARN] Extended StatCan fetch failed (non-critical): {e}")

        logger.log_step("step_1b_indicators")

        return {
            "commodity_data": commodity_data,
            "financial_markets": financial_markets,
            "boc_data": boc_data,
            "yield_data": yield_data,
            "rss_items": rss_items,
            "statcan_inds": statcan_inds,
            "hard_data": hard_data,
            "primary_ind": primary_ind,
            "national_ind": national_ind,
            "prov_ind": prov_ind,
            "global_ind": global_ind,
            **statcan_ext,
        }
    except Exception as e:
        logger.log_error(step_name, e, recovered=False)
        traceback.print_exc()
        return {}
