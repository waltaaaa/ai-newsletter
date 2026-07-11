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
from db import save_indicator, format_indicator_change
from gov_sources import fetch_statcan_indicators
from pipeline_store import cache as _cache


# ─────────────────────────────────────────────────────────────────────────────
# yfinance helper
# ─────────────────────────────────────────────────────────────────────────────

def _yf_close(obj):
    """Coerce a yfinance 'Close' slice into a flat numeric Series.

    yfinance >=1.x returns MultiIndex columns even for single-ticker
    downloads, so df['Close'] is a 1-column DataFrame and float(x.iloc[-1])
    raises "not 'Series'". Squeeze 1-col frames to a Series (multi-col → first
    column); pass real Series through. Returns a NaN-dropped float Series, or
    None if unusable.
    """
    try:
        import pandas as pd
        if obj is None:
            return None
        if isinstance(obj, pd.DataFrame):
            if obj.shape[1] == 0:
                return None
            obj = obj.iloc[:, 0]
        s = pd.to_numeric(obj, errors="coerce").dropna()
        return s if len(s) else None
    except Exception:
        return None


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
        ("ALI=F", "Base Metals",                "Aluminum",          "t",       lambda x: f"${x:,.0f}"),
        # Building Materials — LBR=F is the active Yahoo lumber future (the old
        # LB=F/LBS=F symbols delisted, which froze `lumber` at 2023-05-12).
        ("LBR=F", "Building Materials",          "Lumber",            "mbf",     lambda x: f"${x:,.0f}"),
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
        "Building Materials":         "text-amber-700",
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
                raw = data[ticker] if len(all_tickers) > 1 else data
                col = _yf_close(raw)
                if col is not None and len(col) >= 2:
                    return col
            except (KeyError, TypeError):
                pass
        # Individual fallback for tickers that failed in batch
        try:
            ind = _yf_close(yf.download(ticker, period="1y", progress=False)['Close'])
            if ind is not None and len(ind) >= 2:
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
            prev_close = float(col.iloc[-2])
            year_ago = float(col.iloc[0])

            # Contract rollover / bad data detection: if day change > 50%,
            # use previous close as current (the latest point is likely a
            # rolled contract with a different price scale)
            if prev_close and abs((current - prev_close) / prev_close) > 0.50:
                print(f"  [WARN] {name} ({ticker}): day change "
                      f"{((current - prev_close) / prev_close) * 100:.0f}% "
                      f"exceeds 50% — likely contract rollover. "
                      f"Using previous close ${prev_close:.2f}")
                current = prev_close

            yy_pct = ((current - year_ago) / year_ago) * 100 if year_ago else 0
            yy_str = f"{'+' if yy_pct >= 0 else ''}{yy_pct:.1f}%"
            day_str = ''
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
            col = _yf_close(data[ticker] if len(all_tickers) > 1 else data)
            if col is None or len(col) < 2:
                # Individual fallback — a ticker absent/NaN in the batch
                # (partial Yahoo response / rate-limit) otherwise silently
                # drops that index or FX pair from the briefing.
                try:
                    col = _yf_close(yf.download(ticker, period="1y", progress=False)['Close'])
                except Exception:
                    col = None
            if col is None or len(col) < 2:
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

def _cmhc_housing_starts() -> tuple[float, str] | None:
    """
    Fetch the latest monthly SAAR of total housing starts for all of Canada
    directly from the CMHC monthly news release page.
    Tries the most recent 4 months to account for publication lag (~11 business days).

    Returns (value, reference_period 'YYYY-MM-01') — the release month IS the
    reference month the SAAR covers (audit D5: the archiver needs the true
    reference period, never the fetch date).
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
                    return val, target.strftime('%Y-%m-01')
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
# Verified against StatCan WDS on 2026-04-18:
#   v2062811 returns total employment count (thousands), NOT the rate.
#   v2062803 is terminated (returns no data).
#   v2062817 = Canada employment rate (60.6% Mar 2026, rate format).
#   v2062816 = Canada participation rate (64.9% Mar 2026, rate format).
# Unemployment stays on v2062815. Emp/part rate = unemp + 2/+1 offset
# matches the provincial _PROV_EMPRATE_VIDS / _PROV_PARTRATE_VIDS pattern.
_EMPRATE_VECTOR   = 2062817   # Table 14-10-0287-01, Employment rate Canada SA
_PARTRATE_VECTOR  = 2062816   # Table 14-10-0287-01, Participation rate Canada SA

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
    starts_obs = _cmhc_housing_starts()
    if starts_obs is not None:
        values['housingStarts']    = f"{starts_obs[0]:,.0f}"
        sources['housingStarts']   = 'CMHC'
        obs_dates['housingStarts'] = starts_obs[1]

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

# Provincial building permits — StatCan Table 34-10-0292-01 (PID 34100292),
# the ACTIVE successor cube (34-10-0066 ended 2023-10; 34-10-0285 ended
# 2025-03 — both archived). Coordinate: Total residential and non-residential /
# Types of work, total / Value of permits / Seasonally adjusted, current.
# Values are thousands of dollars, monthly.
# Vectors resolved + validated live 2026-06-09 via getSeriesInfoFromCubePidCoord
# (latest refPer 2026-03; ON $4.87B, QC $2.58B, BC $3.05B — plausible).
_PROV_BUILDING_PERMITS_VIDS: dict[str, int] = {
    "Newfoundland and Labrador": 1675119653,
    "Prince Edward Island":      1675119661,
    "Nova Scotia":               1675119669,
    "New Brunswick":             1675119677,
    "Quebec":                    1675119685,
    "Ontario":                   1675119693,
    "Manitoba":                  1675119701,
    "Saskatchewan":              1675119709,
    "Alberta":                   1675119717,
    "British Columbia":          1675119725,
}

# Provincial average hourly wage — StatCan Table 14-10-0063-01 (PID 14100063),
# active (end 2026-05). Coordinate: Average hourly wage rate / Both full- and
# part-time employees / Total employees, all industries / Total - Gender /
# 15 years and over. Dollars per hour, monthly, unadjusted.
# Vectors resolved + validated live 2026-06-09 (latest refPer 2026-05;
# ON $38.22/h, AB $38.53/h — plausible). Surfaced as wageGrowth = YoY %.
_PROV_WAGE_VIDS: dict[str, int] = {
    "Newfoundland and Labrador": 2135999,
    "Prince Edward Island":      2139419,
    "Nova Scotia":               2142839,
    "New Brunswick":             2146259,
    "Quebec":                    2149679,
    "Ontario":                   2153099,
    "Manitoba":                  2156519,
    "Saskatchewan":              2159939,
    "Alberta":                   2163359,
    "British Columbia":          2166779,
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

# Territorial labour force — StatCan WDS vector IDs
# Table 14-10-0292-01 (PID 14100292): three-month moving average, SA, 15+, both sexes
# Table 14-10-0287 excludes territories, so territories live in a separate cube
# with independent vector IDs. Kept as separate dicts so the provincial loops
# above don't need to learn the "three territories, 3MMA" semantics.
_TERR_UNEMP_VIDS = {
    "Yukon":                 46438777,
    "Northwest Territories": 46438879,
    "Nunavut":               99443852,
}
_TERR_PARTRATE_VIDS = {
    "Yukon":                 46438789,
    "Northwest Territories": 46438891,
    "Nunavut":               99443858,
}
_TERR_EMPRATE_VIDS = {
    "Yukon":                 46438801,
    "Northwest Territories": 46438903,
    "Nunavut":               99443864,
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
    # Plus territorial labour force from Table 14-10-0292 (9 vectors: 3 territories × 3 rates, 3MMA)
    all_vids = (list(_PROV_UNEMP_VIDS.values()) + list(_PROV_CPI_VIDS.values())
                + list(_PROV_EMPRATE_VIDS.values()) + list(_PROV_PARTRATE_VIDS.values())
                + list(_TERR_UNEMP_VIDS.values()) + list(_TERR_PARTRATE_VIDS.values())
                + list(_TERR_EMPRATE_VIDS.values())
                + list(_PROV_BUILDING_PERMITS_VIDS.values())
                + list(_PROV_WAGE_VIDS.values()))
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

    # Building permits — monthly total value, SA (Table 34-10-0292-01).
    # Vector values are thousands of dollars; rendered as $M / $B.
    def _fmt_permits(thousands: float) -> str:
        dollars = thousands * 1_000
        if dollars >= 1_000_000_000:
            return f"${dollars / 1_000_000_000:.2f}B"
        return f"${dollars / 1_000_000:.0f}M"

    for prov, vid in _PROV_BUILDING_PERMITS_VIDS.items():
        obs = data.get(vid, [])
        if obs:
            try:
                val = float(obs[-1]['value'])
                # sanity: monthly provincial totals between $1M and $20B
                if 1_000 <= val <= 20_000_000:
                    updates = {
                        'buildingPermits':      _fmt_permits(val),
                        'buildingPermits_src':  'StatCan',
                        'buildingPermits_date': obs[-1].get('refPer', ''),
                    }
                    if len(obs) >= 2:
                        prev_val = float(obs[-2]['value'])
                        if 1_000 <= prev_val <= 20_000_000:
                            updates['buildingPermits_prev'] = _fmt_permits(prev_val)
                    result.setdefault(prov, {}).update(updates)
            except Exception as e:
                print(f"  [WARN] Provincial building permits ({prov}): {e}")

    # Wage growth — YoY % from average hourly wage levels (Table 14-10-0063-01),
    # obs[-1] vs obs[-13] = 12 months apart (same construction as CPI above).
    for prov, vid in _PROV_WAGE_VIDS.items():
        obs = data.get(vid, [])
        if len(obs) >= 13:
            try:
                latest   = float(obs[-1]['value'])
                year_ago = float(obs[-13]['value'])
                # sanity: hourly wages between $15 and $80
                if 15.0 <= latest <= 80.0 and 15.0 <= year_ago <= 80.0:
                    yoy = ((latest - year_ago) / year_ago) * 100
                    updates = {
                        'wageGrowth':      f"+{yoy:.1f}%" if yoy >= 0 else f"{yoy:.1f}%",
                        'wageGrowth_src':  'StatCan',
                        'wageGrowth_date': obs[-1].get('refPer', ''),
                    }
                    if len(obs) >= 14:
                        prev_latest   = float(obs[-2]['value'])
                        prev_year_ago = float(obs[-14]['value'])
                        if 15.0 <= prev_latest <= 80.0 and 15.0 <= prev_year_ago <= 80.0:
                            prev_yoy = ((prev_latest - prev_year_ago) / prev_year_ago) * 100
                            updates['wageGrowth_prev'] = f"+{prev_yoy:.1f}%" if prev_yoy >= 0 else f"{prev_yoy:.1f}%"
                    result.setdefault(prov, {}).update(updates)
            except Exception as e:
                print(f"  [WARN] Provincial wage growth ({prov}): {e}")

    # Territorial labour force (YT / NT / NU) — 3-month moving average from
    # Table 14-10-0292-01. Same downstream shape as provincial rows, different
    # source table. CPI is not published monthly for the territories and is
    # intentionally skipped; provincial StatCan housing-starts feed handles
    # territorial starts via CMHC where available.
    def _save_terr_rate(vids: dict, out_key: str, prev_key: str, sanity: tuple):
        lo, hi = sanity
        for prov, vid in vids.items():
            obs = data.get(vid, [])
            if not obs:
                continue
            try:
                val = float(obs[-1]['value'])
                if not (lo <= val <= hi):
                    continue
                updates = {
                    out_key:            f"{val:.1f}%",
                    f"{out_key}_src":   'StatCan',
                    f"{out_key}_date":  obs[-1].get('refPer', ''),
                }
                if len(obs) >= 2:
                    prev_val = float(obs[-2]['value'])
                    if lo <= prev_val <= hi:
                        updates[prev_key] = f"{prev_val:.1f}%"
                result.setdefault(prov, {}).update(updates)
            except Exception as e:
                print(f"  [WARN] Territorial {out_key} ({prov}): {e}")
    _save_terr_rate(_TERR_UNEMP_VIDS,    'unemployment',      'unemployment_prev',      (1.0, 30.0))
    _save_terr_rate(_TERR_EMPRATE_VIDS,  'employmentRate',    'employmentRate_prev',    (30.0, 80.0))
    _save_terr_rate(_TERR_PARTRATE_VIDS, 'participationRate', 'participationRate_prev', (40.0, 85.0))

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

def _fred_latest_obs(series_id: str) -> tuple[float, str | None] | None:
    """Latest observation from FRED public CSV endpoint (no API key required).

    Returns (value, observation_date 'YYYY-MM-DD') or None. The observation
    date is the REFERENCE period the value covers — required so indicator
    history is never stamped with the fetch date (audit D5).
    """
    try:
        url  = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        for line in reversed(resp.text.strip().split('\n')):
            if line.startswith('DATE') or line.startswith('observation'):
                continue
            parts = [p.strip() for p in line.split(',')]
            val = parts[-1]
            if val and val != '.':
                obs_date = parts[0][:10] if parts and re.match(r'^\d{4}-\d{2}-\d{2}', parts[0]) else None
                return float(val), obs_date
        return None
    except Exception:
        return None


def _fred_latest(series_id: str) -> float | None:
    """Back-compat wrapper around _fred_latest_obs (value only)."""
    r = _fred_latest_obs(series_id)
    return r[0] if r else None


def _fred_yoy_obs(series_id: str) -> tuple[float, str | None] | None:
    """
    Fetch 14 months from FRED and return (YoY % change, latest obs date).
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
            parts = [p.strip() for p in line.split(',')]
            val = parts[-1]
            if val and val != '.':
                try:
                    rows.append((parts[0][:10], float(val)))
                except ValueError:
                    pass
        if len(rows) < 13:
            return None
        (latest_date, latest), (_, year_ago) = rows[-1], rows[-13]
        if year_ago == 0:
            return None
        obs_date = latest_date if re.match(r'^\d{4}-\d{2}-\d{2}$', latest_date) else None
        return ((latest - year_ago) / year_ago) * 100, obs_date
    except Exception:
        return None


def _ecb_last_obs(dataflow: str, key: str) -> tuple[float, str | None] | None:
    """Latest observation from ECB Statistical Data Warehouse REST API.

    Returns (value, time_period) — the SDMX TIME_PERIOD id ('YYYY-MM' or
    'YYYY-MM-DD') of the observation, or None when unavailable.
    """
    try:
        url  = (f"https://data-api.ecb.europa.eu/service/data/{dataflow}/{key}"
                f"?format=jsondata&lastNObservations=1")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        series = list(data['dataSets'][0]['series'].values())[0]
        obs_key, obs = sorted(series['observations'].items(),
                              key=lambda kv: int(kv[0]))[-1]
        ref = None
        try:
            time_vals = data['structure']['dimensions']['observation'][0]['values']
            ref = str(time_vals[int(obs_key)].get('id') or '') or None
        except Exception:
            ref = None
        return float(obs[0]), ref
    except Exception:
        return None


def _boe_bank_rate_obs() -> tuple[float, str | None] | None:
    """Latest Bank of England Bank Rate from BoE public IADB CSV download.

    Returns (value, observation_date or None). Falls back to FRED series
    (BOEBRBA) if BoE endpoint returns HTML instead of CSV (the BoE changed
    their endpoint format periodically). The UK rate is also available via
    FRED, so this is non-critical — all UK data is covered by FRED with the
    45s timeout.
    """
    def _parse_boe_date(raw: str) -> str | None:
        raw = (raw or '').strip()
        for fmt in ('%d %b %Y', '%d %B %Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
        return None

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
                        return float(val), _parse_boe_date(parts[0])
                    except ValueError:
                        pass
        return None
    except Exception:
        pass

    # Fallback: BoE Bank Rate via FRED (series BOEBRBA)
    try:
        return _fred_latest_obs('BOEBRBA')
    except Exception:
        return None


def _fred_qoq_obs(series_id: str) -> tuple[float, str | None] | None:
    """
    Fetch a quarterly level index from FRED and return
    (most recent QoQ % change, latest quarter's observation date).
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
            parts = [p.strip() for p in line.split(',')]
            val = parts[-1]
            if val and val != '.':
                try:
                    rows.append((parts[0][:10], float(val)))
                except ValueError:
                    pass
        if len(rows) < 2:
            return None
        (latest_date, latest), (_, prev) = rows[-1], rows[-2]
        if not prev:
            return None
        obs_date = latest_date if re.match(r'^\d{4}-\d{2}-\d{2}$', latest_date) else None
        return ((latest / prev) - 1) * 100, obs_date
    except Exception:
        return None


def _world_bank_latest_obs(iso3: str, indicator: str) -> tuple[float, str | None] | None:
    """
    Most recent non-null (value, reference_date) from the World Bank Open Data
    API (annual frequency — the 'date' field is the reference YEAR, normalized
    here to 'YYYY-01-01'). Free, no key required.
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
                ref_year = str(entry.get('date') or '').strip()
                ref = f"{ref_year}-01-01" if re.match(r'^\d{4}$', ref_year) else None
                return float(entry['value']), ref
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
    Returns {region: {field: 'X.X%', field_src: 'SOURCE', field_date: 'YYYY-MM-DD'}}.

    The <field>_date companion is the source's REFERENCE period for the
    observation (audit D5). _archive_indicators_to_history uses it to stamp
    indicator_history — rows without it are SKIPPED, never stamped with the
    fetch date.
    """
    # Check cache first (24hr TTL — these indicators change slowly).
    # Key is versioned (v2) because pre-D5 cached payloads lack the
    # <field>_date companions the archiver now requires.
    if _cache:
        cached = _cache.get("global_indicators_v2")
        if cached:
            print("Fetching global indicators from cache (24hr TTL)...")
            return cached
    print("Fetching global indicators from primary APIs...")
    result = {}

    # Value formatters
    def _pct2(v):    return f"{v:.2f}%"
    def _pct1(v):    return f"{v:.1f}%"
    def _signed1(v): return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

    def _set(d: dict, field: str, obs, fmt, src: str) -> bool:
        """Assign value + _src + _date companions from a (value, ref_date)
        observation tuple. Returns True when the value was set."""
        if not obs or obs[0] is None:
            return False
        d[field] = fmt(obs[0])
        d[f'{field}_src'] = src
        if obs[1]:
            d[f'{field}_date'] = obs[1]
        return True

    # ── United States (FRED — BLS/BEA) ────────────────────────────
    print("  US (FRED/BLS/BEA)...", end=" ", flush=True)
    us = {}
    _set(us, 'rate', _fred_latest_obs('DFF'), _pct2, 'FRED')                       # Fed Funds effective rate (daily)
    _set(us, 'unemployment', _fred_latest_obs('UNRATE'), _pct1, 'FRED/BLS')        # Unemployment rate (BLS, monthly SA)
    _set(us, 'cpi', _fred_yoy_obs('CPIAUCSL'), _signed1, 'FRED/BLS')               # CPI all urban, YoY (BLS)
    _set(us, 'gdp', _fred_latest_obs('A191RL1Q225SBEA'), _signed1, 'FRED/BEA')     # Real GDP growth annualised QoQ (BEA)
    result['United States'] = us
    print(f"rate={us.get('rate','—')} unemp={us.get('unemployment','—')} "
          f"cpi={us.get('cpi','—')} gdp={us.get('gdp','—')}")

    # ── European Union (ECB SDW + FRED for GDP) ────────────────────
    print("  EU (ECB SDW + FRED)...", end=" ", flush=True)
    eu = {}
    _set(eu, 'rate', _ecb_last_obs('FM', 'B.U2.EUR.4F.KR.DFR.LEV'), _pct2, 'ECB')          # ECB deposit facility rate
    _set(eu, 'cpi', _ecb_last_obs('ICP', 'M.U2.N.000000.4.ANR'), _signed1, 'ECB/Eurostat')  # HICP 12-month % change
    if not _set(eu, 'unemployment', _ecb_last_obs('LFSI', 'M.I8.S.UNEHRT.TOTAL0.15_74.T'),
                _pct1, 'ECB/Eurostat'):                                                      # Euro Area unemployment
        if not _set(eu, 'unemployment', _fred_latest_obs('LRHUTTTTEUM156S'),
                    _pct1, 'FRED/OECD'):                                                     # OECD harmonised via FRED
            _set(eu, 'unemployment', _world_bank_latest_obs('EUU', 'SL.UEM.TOTL.ZS'),
                 _pct1, 'World Bank')                                                        # World Bank fallback
    # EA19 real GDP QoQ — FRED OECD Quarterly National Accounts series
    if not _set(eu, 'gdp', _fred_qoq_obs('CLVMNACSCAB1GQEA19'), _signed1, 'FRED/Eurostat'):
        _set(eu, 'gdp', _world_bank_latest_obs('EUU', 'NY.GDP.MKTP.KD.ZG'),
             _signed1, 'World Bank')                                                         # World Bank fallback
    result['European Union'] = eu
    print(f"rate={eu.get('rate','—')} cpi={eu.get('cpi','—')} "
          f"unemp={eu.get('unemployment','—')} gdp={eu.get('gdp','—')}")

    # ── United Kingdom (BoE + FRED/OECD + World Bank fallbacks) ────
    print("  UK (BoE + FRED/ONS + World Bank)...", end=" ", flush=True)
    uk = {}
    # Rate: BoE IADB → FRED → FRED/OECD 3-month interbank
    if not _set(uk, 'rate', _boe_bank_rate_obs(), _pct2, 'BoE'):
        _set(uk, 'rate', _fred_latest_obs('IR3TIB01GBM156N'), _pct2, 'FRED/OECD')
    # CPI: FRED/OECD → World Bank
    if not _set(uk, 'cpi', _fred_yoy_obs('GBRCPIALLMINMEI'), _signed1, 'FRED/ONS'):
        _set(uk, 'cpi', _world_bank_latest_obs('GBR', 'FP.CPI.TOTL.ZG'), _signed1, 'World Bank')
    # Unemployment: FRED/OECD → World Bank
    if not _set(uk, 'unemployment', _fred_latest_obs('LRHUTTTTGBM156S'), _pct1, 'FRED/ONS'):
        _set(uk, 'unemployment', _world_bank_latest_obs('GBR', 'SL.UEM.TOTL.ZS'),
             _pct1, 'World Bank')
    # GDP: FRED/OECD QoQ → FRED/OECD YoY → World Bank
    if not _set(uk, 'gdp', _fred_qoq_obs('CLVMNACSCAB1GQGB'), _signed1, 'FRED/ONS'):
        if not _set(uk, 'gdp', _fred_latest_obs('NAEXKP01GBQ657S'), _signed1, 'FRED/OECD'):
            _set(uk, 'gdp', _world_bank_latest_obs('GBR', 'NY.GDP.MKTP.KD.ZG'),
                 _signed1, 'World Bank')
    result['United Kingdom'] = uk
    print(f"rate={uk.get('rate','—')} cpi={uk.get('cpi','—')} "
          f"unemp={uk.get('unemployment','—')} gdp={uk.get('gdp','—')}")

    # ── China (World Bank Open Data + FRED/OECD) ──
    print("  China (World Bank + FRED/OECD)...", end=" ", flush=True)
    cn = {}
    _set(cn, 'gdp', _world_bank_latest_obs('CHN', 'NY.GDP.MKTP.KD.ZG'), _signed1, 'World Bank')      # GDP growth annual %
    _set(cn, 'cpi', _world_bank_latest_obs('CHN', 'FP.CPI.TOTL.ZG'), _signed1, 'World Bank')         # CPI inflation annual %
    _set(cn, 'unemployment', _world_bank_latest_obs('CHN', 'SL.UEM.TOTL.ZS'), _pct1, 'World Bank/ILO')  # ILO modelled estimate
    _set(cn, 'rate', _fred_latest_obs('INTDSRCNM193N'), _pct2, 'FRED/IMF')                            # PBoC LPR not on free APIs
    result['China'] = cn
    print(f"gdp={cn.get('gdp','—')} cpi={cn.get('cpi','—')} "
          f"unemp={cn.get('unemployment','—')} rate={cn.get('rate','—')}")

    # Cache for 24 hours
    if _cache:
        _cache.set("global_indicators_v2", result, ttl_hours=24)
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
            naics_code: {'mm': '+X.X%', 'yy': '+X.X%', 'src': 'StatCan',
                         'ref': 'YYYY-MM-DD'},  # WDS refPer of latest obs (D5)
            '_gdp_quarterly': '+X.X%',       # QoQ annualised real GDP
            '_gdp_quarterly_src': 'StatCan',
            '_gdp_quarterly_ref': 'YYYY-MM-DD',
        }
    """
    print("  Fetching industry GDP from StatCan WDS...")
    all_vectors = list(_INDUSTRY_VECTORS.values()) + [_GDP_QUARTERLY_VECTOR]
    data = _statcan_wds(all_vectors, n=14)
    result = {}

    # Industry M/M and Y/Y. 'ref' carries the WDS refPer of the latest
    # observation — the REFERENCE period the M/M and Y/Y changes describe
    # (audit D5). The archiver stamps indicator_history with it and skips
    # the row when it is missing, never falling back to the fetch date.
    for naics_code, vector_id in _INDUSTRY_VECTORS.items():
        obs = data.get(vector_id, [])
        mm, yy = _compute_mm_yy(obs)
        result[naics_code] = {
            'mm':  (f"+{mm:.1f}%" if mm >= 0 else f"{mm:.1f}%") if mm is not None else 'N/A',
            'yy':  (f"+{yy:.1f}%" if yy >= 0 else f"{yy:.1f}%") if yy is not None else 'N/A',
            'src': 'StatCan' if (mm is not None or yy is not None) else 'N/A',
            'ref': (obs[-1].get('refPer') or '')[:10] if obs else None,
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
                result['_gdp_quarterly_ref'] = (gdp_obs[-1].get('refPer') or '')[:10]
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
        if ind.get('_gdp_quarterly_ref'):
            nat['obs_dates']['realGdp'] = ind['_gdp_quarterly_ref']

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

def _norm_ref_period(raw: str | None) -> str | None:
    """Normalize a reference period ('YYYY-MM-DD', 'YYYY-MM', or bare 'YYYY'
    for annual series like provincial GDP) to YYYY-MM-DD.

    Returns None when the string is missing/unparseable. Callers must SKIP
    the row (with a logged warning) in that case — never stamp the fetch
    date (audit D14; pipeline invariant: stamp the REFERENCE period).
    """
    s = str(raw or '').strip()[:10]
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    if re.match(r'^\d{4}-\d{2}$', s):
        return f"{s}-01"
    if re.match(r'^\d{4}$', s):
        return f"{s}-01-01"
    return None


def _fmt_indicator_change(cur, prev, unit: str = '',
                          indicator_name: str = '') -> str | None:
    """Period-over-period change string. Delegates to the shared UNIT-aware
    helper in db.py (audit D11): %-natured series get pp differences, level
    series get relative % change — never decided by value magnitude."""
    return format_indicator_change(cur, prev, unit=unit,
                                   indicator_name=indicator_name)


def _archive_indicators_to_history(conn, primary_ind: dict) -> None:
    """Write each indicator value to the indicator_history table for trend tracking.

    Schema per record: {indicator_name, province, period, value, unit, source, frequency, backfilled}

    Periods are stamped with the StatCan REFERENCE period (obs_dates national,
    <field>_date provincial/global, 'ref' industry) — not the fetch date.
    Before 2026-06-11 every row was stamped with the run date, so a May LFS
    print fetched in June landed in a 2026-06 history bucket, daily runs
    created one bogus row per run date, and previous_value/change never
    reached the export. Rows whose reference period cannot be determined are
    SKIPPED with a logged warning (audit D5/D14) — never stamped with today.
    """
    count = 0
    skipped = 0

    # National indicators
    nat = primary_ind.get('national', {})
    nat_vals = nat.get('values', {})
    nat_srcs = nat.get('sources', {})
    nat_prevs = nat.get('prev_values', {})
    nat_dates = nat.get('obs_dates', {})
    for field, value in nat_vals.items():
        if not value or value == 'N/A':
            continue
        source_label = nat_srcs.get(field, '')
        ref_period = _norm_ref_period(nat_dates.get(field))
        if ref_period is None:
            print(f"  [HISTORY][SKIP] national '{field}': no parseable reference "
                  f"period (obs_date={nat_dates.get(field)!r}) — row NOT archived "
                  f"(never stamp the fetch date)")
            skipped += 1
            continue
        prev_value = nat_prevs.get(field)
        unit = '%' if any(k in field.lower() for k in ['rate', 'cpi', 'gdp', 'unemployment']) else ''
        save_indicator(conn, {
            'indicator': field,
            'province': 'national',
            'date': ref_period,
            'value': str(value),
            'previous_value': str(prev_value) if prev_value not in (None, '', 'N/A') else None,
            'change': _fmt_indicator_change(value, prev_value, unit, field),
            'unit': unit,
            'source': source_label,
            'frequency': 'monthly',
            'backfilled': False,
            'source_meta': {
                'authority': source_label or 'StatCan',
                'reference_period': ref_period,
            },
        })
        count += 1

    # Provincial indicators. <field>_src/_date/_prev companions are metadata —
    # they feed period/previous_value here and must NOT be saved as indicators
    # (they used to leak in as fake series; see _SKIP_INDICATORS in the export).
    _META_SUFFIXES = ('_src', '_date', '_prev')
    for province, prov_data in primary_ind.get('provinces', {}).items():
        for field, value in prov_data.items():
            if field.endswith(_META_SUFFIXES) or not value or value == 'N/A':
                continue
            source_label = prov_data.get(f'{field}_src', '')
            ref_period = _norm_ref_period(prov_data.get(f'{field}_date'))
            if ref_period is None:
                print(f"  [HISTORY][SKIP] {province} '{field}': no parseable "
                      f"reference period (obs_date={prov_data.get(f'{field}_date')!r}) "
                      f"— row NOT archived (never stamp the fetch date)")
                skipped += 1
                continue
            prev_value = prov_data.get(f'{field}_prev')
            unit = '%' if any(k in field.lower() for k in ['rate', 'cpi', 'unemployment']) else ''
            save_indicator(conn, {
                'indicator': field,
                'province': province,
                'date': ref_period,
                'value': str(value),
                'previous_value': str(prev_value) if prev_value not in (None, '', 'N/A') else None,
                'change': _fmt_indicator_change(value, prev_value, unit, field),
                'unit': unit,
                'source': source_label,
                'frequency': 'monthly',
                'backfilled': False,
                'source_meta': {
                    'authority': source_label or 'StatCan',
                    'reference_period': ref_period,
                },
            })
            count += 1

    # Global indicators (US, EU, UK, China)
    _GLOBAL_AUTHORITIES = {
        'United States': 'BLS/BEA/Fed',
        'US': 'BLS/BEA/Fed',
        'China': 'NBS/PBoC',
        'European Union': 'Eurostat/ECB',
        'EU': 'Eurostat/ECB',
        'United Kingdom': 'ONS/BoE',
        'UK': 'ONS/BoE',
    }
    _CANONICAL_URLS = {
        'United States': 'https://www.federalreserve.gov/monetarypolicy/openmarket.htm',
        'US': 'https://www.federalreserve.gov/monetarypolicy/openmarket.htm',
        'China': 'http://www.stats.gov.cn/english/',
        'European Union': 'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html',
        'EU': 'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html',
        'United Kingdom': 'https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes',
        'UK': 'https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes',
    }
    # D5: stamp the source's reference period from the <field>_date companion
    # (FRED/ECB/BoE/World Bank observation dates). Cached pre-D5 payloads and
    # sources without a machine-readable refPer have no companion — those
    # rows are SKIPPED loudly, never stamped with the fetch date.
    for region, region_data in primary_ind.get('global', {}).items():
        for field, value in region_data.items():
            if field.endswith(('_src', '_date')) or not value or value == 'N/A':
                continue
            source_label = region_data.get(f'{field}_src', '')
            ref_period = _norm_ref_period(region_data.get(f'{field}_date'))
            if ref_period is None:
                print(f"  [HISTORY][SKIP] global {region} '{field}': source gave no "
                      f"machine-readable reference period "
                      f"(date={region_data.get(f'{field}_date')!r}) — row NOT archived")
                skipped += 1
                continue
            save_indicator(conn, {
                'indicator': f'global_{field}',
                'province': region,
                'date': ref_period,
                'value': str(value),
                'unit': '%' if any(k in field.lower() for k in ['rate', 'cpi', 'gdp', 'unemployment']) else '',
                'source': source_label,
                'frequency': 'monthly',
                'category': 'Global',
                'backfilled': False,
                'source_meta': {
                    'authority': _GLOBAL_AUTHORITIES.get(region, source_label),
                    'reference_period': ref_period,
                    'source_url': _CANONICAL_URLS.get(region, ''),
                },
            })
            count += 1

    # Industry GDP (per-NAICS M/M and Y/Y from StatCan WDS).
    # D5: 'ref' is the WDS refPer of the latest observation — the month the
    # M/M and Y/Y changes describe. Missing refPer → loud skip, never today.
    for naics_code, ind_data in primary_ind.get('industries', {}).items():
        if naics_code.startswith('_'):
            continue
        mm = ind_data.get('mm', 'N/A')
        yy = ind_data.get('yy', 'N/A')
        src = ind_data.get('src', 'StatCan')
        ref_period = _norm_ref_period(ind_data.get('ref'))
        if ref_period is None:
            if (mm and mm != 'N/A') or (yy and yy != 'N/A'):
                print(f"  [HISTORY][SKIP] industry_gdp NAICS {naics_code}: no WDS "
                      f"refPer (ref={ind_data.get('ref')!r}) — rows NOT archived")
                skipped += 1
            continue
        if mm and mm != 'N/A':
            save_indicator(conn, {
                'indicator': f'industry_gdp_mm_{naics_code}',
                'province': 'national',
                'date': ref_period,
                'value': str(mm),
                'unit': '%',
                'source': src,
                'frequency': 'monthly',
                'backfilled': False,
                'source_meta': {
                    'authority': 'Statistics Canada',
                    'reference_period': ref_period,
                    'table_id': '36-10-0434',
                },
            })
            count += 1
        if yy and yy != 'N/A':
            save_indicator(conn, {
                'indicator': f'industry_gdp_yy_{naics_code}',
                'province': 'national',
                'date': ref_period,
                'value': str(yy),
                'unit': '%',
                'source': src,
                'frequency': 'monthly',
                'backfilled': False,
                'source_meta': {
                    'authority': 'Statistics Canada',
                    'reference_period': ref_period,
                    'table_id': '36-10-0434',
                },
            })
            count += 1

    print(f"  [HISTORY] Archived {count} indicator values to indicator_history"
          + (f" ({skipped} skipped: no reference period)" if skipped else ""))


# ─────────────────────────────────────────────────────────────────────────────
# D-6: commodity poison filter (module-level so it's testable)
# ─────────────────────────────────────────────────────────────────────────────

# Plausibility bounds per indicator. These are looser than the validator's
# RANGE rules because they're a poison filter, not a validation — the goal
# is to catch yfinance batch-download column scrambles (e.g., wti=1079.5,
# platinum=67, soybean_oil=4761.9) before they land in indicator_history
# and get picked as "latest" by the exporter. Any value outside these
# bounds is almost certainly a yfinance DataFrame column swap.
_POISON_BOUNDS = {
    'wti':          (10.0, 200.0),   'brent':        (10.0, 220.0),
    'natural_gas':  (0.5, 20.0),     'coal':         (20.0, 500.0),
    'gold':         (800.0, 8000.0), 'silver':       (5.0, 150.0),
    'platinum':     (300.0, 3000.0), 'palladium':    (200.0, 4000.0),
    'copper':       (1.0, 10.0),     'aluminum':     (800.0, 6000.0),
    'wheat':        (200.0, 1500.0), 'corn':         (150.0, 1200.0),
    'rice':         (5.0, 50.0),     'soybeans':     (500.0, 2500.0),
    'coffee':       (50.0, 600.0),   'cocoa':        (500.0, 15000.0),
    'sugar':        (5.0, 50.0),     'cotton':       (40.0, 250.0),
    'soybean_oil':  (10.0, 120.0),   'soybean_meal': (150.0, 700.0),
    'lumber':       (100.0, 2500.0), 'propane':      (0.2, 5.0),
    'canola':       (400.0, 1500.0),
}

# Indicator name → yfinance ticker, for the one-shot individual retry after a
# poison trip. Mirrors TICKER_MAP in get_live_commodities(); names without a
# yfinance ticker (lumber, propane, canola — non-yfinance sources) can't be
# retried and go straight to skip + service_health failure.
_POISON_RETRY_TICKERS = {
    'wti': 'CL=F', 'brent': 'BZ=F', 'natural_gas': 'NG=F', 'coal': 'MTF=F',
    'gold': 'GC=F', 'silver': 'SI=F', 'platinum': 'PL=F', 'palladium': 'PA=F',
    'copper': 'HG=F', 'aluminum': 'ALI=F',
    'wheat': 'ZW=F', 'corn': 'ZC=F', 'rice': 'ZR=F', 'soybeans': 'ZS=F',
    'coffee': 'KC=F', 'cocoa': 'CC=F', 'sugar': 'SB=F', 'cotton': 'CT=F',
    'soybean_oil': 'ZL=F', 'soybean_meal': 'ZM=F',
    'lumber': 'LBR=F',  # 2026-06-15: active lumber future (old LB=F delisted)
}


def _within_poison_bounds(name, value) -> bool:
    """True when value is plausible for the named indicator.

    Names without bounds always pass (the poison filter only covers
    commodities with known plausible ranges). Unparseable values fail.
    """
    bounds = _POISON_BOUNDS.get(name)
    if not bounds:
        return True
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return bounds[0] <= v <= bounds[1]


def _poison_retry_value(name, fetcher=None):
    """D-6: retry ONE individual download after a poison trip.

    Mirrors the individual-fallback pattern in get_live_commodities()._get_ticker_series:
    a single-ticker yf.download avoids the batch DataFrame column scramble that
    poisons values in the first place.

    Args:
        name: indicator name (e.g. 'wti')
        fetcher: optional callable(ticker) -> float|None, injectable for tests.

    Returns:
        An in-bounds float, or None when no ticker is known, the fetch fails,
        or the retried value is still out of bounds.
    """
    ticker = _POISON_RETRY_TICKERS.get(name)
    if not ticker:
        return None

    if fetcher is None:
        def fetcher(tkr):
            import yfinance as yf
            col = _yf_close(yf.download(tkr, period="5d", progress=False)['Close'])
            if col is None or len(col) == 0:
                return None
            return float(col.iloc[-1])

    try:
        val = fetcher(ticker)
    except Exception:
        return None
    if val is None or not _within_poison_bounds(name, val):
        return None
    return float(val)


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
            fnum = float(val)
        except (ValueError, TypeError):
            return
        if name in _POISON_BOUNDS and not _within_poison_bounds(name, fnum):
            print(f"  [POISON-FILTER] {name}={fnum} outside "
                  f"{_POISON_BOUNDS.get(name)} — retrying individual download")
            # D-6: one individual-ticker retry before giving up.
            retry = _poison_retry_value(name)
            if retry is None:
                # Skip the write — the previous good indicator_history row
                # holds over as "latest" for the exporter.
                print(f"  [POISON-FILTER] Skipping {name} (retry failed or "
                      f"still out of bounds)")
                try:
                    import service_health
                    service_health.get().record_failure(
                        'yfinance', f'poison:{name}')
                except Exception:
                    pass  # health bookkeeping must never block the archive
                return
            print(f"  [POISON-FILTER] Retry recovered {name}={retry}")
            fnum = retry
            val = str(retry)
        save_indicator(conn, {
            'indicator': name,
            'province': 'national',
            'date': today_str,
            'value': val,
            'unit': unit,
            'source': source,
            'frequency': 'daily',
            'backfilled': False,
            'source_meta': {
                'authority': source,
                'reference_period': today_str,
            },
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

        # Audit M2: the old all-or-nothing condition dropped the ENTIRE
        # 1-year-ago comparison line whenever a single term had no
        # observation in the 10-day window. Yield curves are smooth —
        # interpolate isolated gaps from neighbouring terms, and only give
        # up when fewer than half the terms have history.
        n_known = sum(1 for v in historical_vals if v is not None)
        if historical_vals and n_known >= max(2, len(current_vals) // 2):
            filled = list(historical_vals)
            # Pad to current length if the loop appended fewer entries
            while len(filled) < len(current_vals):
                filled.append(None)
            known_idx = [i for i, v in enumerate(filled) if v is not None]
            for i, v in enumerate(filled):
                if v is not None:
                    continue
                lo = max((k for k in known_idx if k < i), default=None)
                hi = min((k for k in known_idx if k > i), default=None)
                if lo is not None and hi is not None:
                    frac = (i - lo) / (hi - lo)
                    filled[i] = filled[lo] + (filled[hi] - filled[lo]) * frac
                else:
                    filled[i] = filled[lo if lo is not None else hi]
            hist_line = [round(v, 2) for v in filled]
        else:
            hist_line = []
        charts = {
            "yieldCurveCurrent":  current_vals,
            "yieldCurveLastYear": hist_line,
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

        # Warehouse instrumentation (RC-6): record Phase 1 connection outcomes
        # (yfinance batches, BoC Valet, LFS/CPI primary, global indicators) so
        # a dark source is visible beyond stdout. record_run never raises and
        # this block never alters Phase 1 output.
        try:
            from data_warehouse import record_run

            def _wh(dct):
                try:
                    n = len(dct) if dct else 0
                except TypeError:
                    n = 1 if dct else 0
                return ("ok" if n else "failed"), n

            _st, _n = _wh(commodity_data)
            record_run("yf_commodities", _st, items_fetched=_n, items_saved=_n,
                       error="" if _n else "empty commodities payload", conn=conn)
            _mk_n = (len(financial_markets.get("indices") or [])
                     + len(financial_markets.get("fx") or [])) if financial_markets else 0
            record_run("yf_markets", "ok" if _mk_n else "failed",
                       items_fetched=_mk_n, items_saved=_mk_n,
                       error="" if _mk_n else "empty indices/fx payload", conn=conn)
            _boc_ok = bool(boc_data and boc_data.get("rate"))
            record_run("boc_valet", "ok" if _boc_ok else "failed",
                       items_fetched=1 if _boc_ok else 0,
                       items_saved=1 if _boc_ok else 0,
                       error="" if _boc_ok else "BoC Valet returned no policy rate", conn=conn)
            _lfs_n = (len(national_ind or {})
                      + sum(len(v or {}) for v in (prov_ind or {}).values()))
            record_run("statcan_lfs_primary", "ok" if _lfs_n else "failed",
                       items_fetched=_lfs_n, items_saved=_lfs_n,
                       error="" if _lfs_n else "no national/provincial LFS-CPI values", conn=conn)
            _gl_n = len(global_ind or {})
            record_run("global_indicators", "ok" if _gl_n else "failed",
                       items_fetched=_gl_n, items_saved=_gl_n,
                       error="" if _gl_n else "empty global indicators payload", conn=conn)
        except Exception as _wh_e:
            print(f"  [WAREHOUSE] Phase 1 recording failed (non-critical): {_wh_e}")

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
