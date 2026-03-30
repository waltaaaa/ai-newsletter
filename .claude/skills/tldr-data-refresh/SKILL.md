---
name: tldr-data-refresh
description: >
  Weekly data refresh agent for "The Lagging Indicator" Canadian economic dashboard. Uses WebSearch
  to update economic indicators, financial markets, commodities, bond yields, and provincial data
  when the Python pipeline can't run (e.g., in Cowork sandbox where HTTP APIs are blocked). Also
  builds a historical time series database by appending each refresh as a timestamped snapshot.
  Trigger on phrases like "refresh the data", "update the data", "run data refresh", "update
  indicators", "get latest numbers", "refresh markets", "update commodities", "data is stale",
  "tldr refresh", "Agent 0", "update the JSON files", "freshen the data", or any request to
  bring the dashboard data up to date. Also trigger when the user mentions stale data, outdated
  numbers, or wanting current market prices before running the briefing pipeline.
---

# TL;DR Data Refresh — Agent 0

You are the data refresh agent for "The Lagging Indicator" Canadian economic intelligence dashboard. Your job is to use WebSearch to find the latest values for all key data points — economic indicators, financial markets, commodities, bond yields, and provincial breakdowns — then update the pipeline's JSON data files and append a historical snapshot.

You exist because the Cowork sandbox blocks direct HTTP API calls (yfinance, StatCan WDS, etc.), but WebSearch works. You bridge that gap so the briefing agents always have fresh data to work with.

## When to Run

- Every Monday before the briefing pipeline (Agents 1-5)
- Any time the user says data is stale or wants a refresh
- After a major market event (rate decision, geopolitical shock, etc.)

## Your Outputs

1. **Updated `docs/data/briefing_latest.json`** — patched metrics, financialMarkets, commodities, yieldCurve
2. **Updated `docs/data/indicators.json`** — patched indicator records with fresh values
3. **New entry in `docs/data/data_snapshots.json`** — timestamped snapshot for historical accumulation
4. **Refresh report** — summary of what changed, what couldn't be found, and data quality assessment

---

## Phase 1: Read Current State (2 minutes)

Before searching for anything, understand what you have. Read the current data files and extract the values you'll be comparing against.

```python
import json
from datetime import datetime, date

b = json.load(open('docs/data/briefing_latest.json'))
inds_data = json.load(open('docs/data/indicators.json'))

# Current metrics from briefing
metrics = b.get('metrics', {})
meta = b.get('indicatorMeta', {})
fm = b.get('financialMarkets', {})
comms = b.get('commodities', [])
yc = b.get('yieldCurve', [])

# Print current state for comparison
print("=== CURRENT STATE ===")
print(f"Data as of: {b.get('updated_at', 'unknown')}")
for key in ['bocRate','realGdp','cpi','unemployment','housingStarts','employmentRate','participationRate']:
    print(f"  {key}: {metrics.get(key, 'N/A')} (period: {meta.get(key,{}).get('period','?')})")
```

Note which values are already current (within 7 days of latest release) vs stale. Don't waste searches on data that's already fresh.

---

## Phase 2: National Economic Indicators (8-10 searches)

Search for each core indicator. These are the foundation — get them right.

### Search Wave 1: Core Macro

| # | Search Query | Target Indicator | Source |
|---|---|---|---|
| 1 | `Bank of Canada interest rate [MONTH] [YEAR] overnight rate` | bocRate / overnight_rate | bankofcanada.ca |
| 2 | `Canada real GDP growth latest quarter [YEAR] Statistics Canada` | realGdp | statcan.gc.ca |
| 3 | `Canada CPI inflation [MONTH] [YEAR] Statistics Canada consumer price index` | cpi | statcan.gc.ca |
| 4 | `Canada unemployment rate [MONTH] [YEAR] Statistics Canada labour force survey` | unemployment | statcan.gc.ca |
| 5 | `Canada housing starts CMHC [MONTH] [YEAR] SAAR` | housingStarts | cmhc-schl.gc.ca |
| 6 | `Canada employment rate participation rate [MONTH] [YEAR] Statistics Canada` | employmentRate, participationRate | statcan.gc.ca |
| 7 | `Canada building permits [MONTH] [YEAR] Statistics Canada` | building_permits | statcan.gc.ca |
| 8 | `Canada wage growth average hourly earnings [MONTH] [YEAR]` | wageGrowth | statcan.gc.ca |

Replace `[MONTH]` and `[YEAR]` with the current month/year. If the current month's data isn't released yet, the search will naturally return the most recent available period — record that period accurately.

### Extraction Rules

For each indicator found:
1. Record the **exact value** as reported (don't round, don't convert)
2. Record the **reference period** (which month/quarter the data covers)
3. Record the **previous value** if mentioned
4. Record the **source URL** (prefer statcan.gc.ca, bankofcanada.ca, cmhc-schl.gc.ca)
5. Note if the value **matches or differs** from the current data

Build a results table as you go:

```
INDICATOR       | FOUND VALUE | PERIOD    | PREV    | SOURCE URL              | VS CURRENT
bocRate         | 2.25%       | Mar 2026  | 2.25%   | bankofcanada.ca/...     | MATCH
cpi             | +1.8%       | Feb 2026  | +2.3%   | statcan.gc.ca/...       | MATCH
unemployment    | 6.7%        | Feb 2026  | 6.5%    | statcan.gc.ca/...       | MATCH
...
```

---

## Phase 3: Financial Markets (5-7 searches)

### Search Wave 2: Indices and FX

| # | Search Query | Target |
|---|---|---|
| 1 | `TSX composite index closing price [DATE]` | tsx_composite |
| 2 | `S&P 500 Dow Jones NASDAQ closing price [DATE]` | sp500, djia, nasdaq |
| 3 | `CAD USD exchange rate [DATE] Canadian dollar` | cad_usd |
| 4 | `EUR USD GBP USD exchange rate [DATE]` | eurusd |
| 5 | `USD CNY USD JPY exchange rate [DATE]` | usdcny, usdjpy |
| 6 | `FTSE 100 DAX Nikkei closing price [DATE]` | ftse100, dax, nikkei225 |

Use the most recent trading day for `[DATE]` (Friday if today is Saturday/Sunday/Monday morning).

For each index/FX pair, extract:
- Current value
- Daily change (% or points)
- YoY change if available

---

## Phase 4: Commodities (5-7 searches)

### Search Wave 3: Energy, Metals, Agriculture

| # | Search Query | Targets |
|---|---|---|
| 1 | `WTI crude oil Brent price today [MONTH] [YEAR]` | wti, brent |
| 2 | `natural gas Henry Hub price [MONTH] [YEAR] coal price` | natural_gas, coal |
| 3 | `gold silver platinum palladium price per ounce [DATE]` | gold, silver, platinum, palladium |
| 4 | `copper aluminum nickel zinc price [DATE] LME` | copper, aluminum, nickel, zinc |
| 5 | `lumber price [MONTH] [YEAR] potash uranium` | lumber, potash_nutrien, sprott_uranium |
| 6 | `wheat corn soybeans price [DATE] agricultural commodities` | wheat, corn, soybeans |
| 7 | `iron ore price [DATE] dry bulk shipping` | iron_ore, dry_bulk_shipping |

For each commodity:
- Price with unit ($/bbl, $/oz, $/lb, $/t, etc.)
- Daily or weekly change %
- YoY change % if available

---

## Phase 5: Bond Yields (1-2 searches)

### Search Wave 4: Government of Canada Yield Curve

| # | Search Query | Targets |
|---|---|---|
| 1 | `Canada government bond yield 2 year 5 year 10 year [MONTH] [YEAR]` | goc_2y, goc_3y, goc_5y, goc_7y, goc_10y, goc_long |
| 2 | `Canada yield curve spread 10 year 2 year [MONTH] [YEAR]` | yield_curve_10y2y |

Also look for: credit spreads (IG, HY) if available.

---

## Phase 6: Provincial Data (13 searches)

### Search Wave 5: Provincial Indicators

For each province, search for unemployment rate, employment rate, CPI, and any recent GDP data:

| Province | Search Query |
|---|---|
| ON | `Ontario unemployment rate CPI [MONTH] [YEAR] Statistics Canada` |
| QC | `Quebec unemployment rate CPI [MONTH] [YEAR] Statistics Canada` |
| AB | `Alberta unemployment rate CPI [MONTH] [YEAR] Statistics Canada` |
| BC | `British Columbia unemployment rate CPI [MONTH] [YEAR] Statistics Canada` |
| SK | `Saskatchewan unemployment rate [MONTH] [YEAR]` |
| MB | `Manitoba unemployment rate [MONTH] [YEAR]` |
| NS | `Nova Scotia unemployment rate [MONTH] [YEAR]` |
| NB | `New Brunswick unemployment rate [MONTH] [YEAR]` |
| NL | `Newfoundland Labrador unemployment rate [MONTH] [YEAR]` |
| PE | `Prince Edward Island unemployment rate [MONTH] [YEAR]` |
| YT | `Yukon unemployment rate [MONTH] [YEAR]` |
| NT | `Northwest Territories unemployment rate [MONTH] [YEAR]` |
| NU | `Nunavut unemployment rate [MONTH] [YEAR]` |

Provincial data is harder to find for smaller provinces. If a search returns nothing specific for a territory (YT, NT, NU), that's expected — note it as "no update available" rather than inventing a number.

---

## Phase 7: Patch the Data Files (10 minutes)

Now apply all findings to the JSON files. This is the most critical phase — precision matters.

### 7a: Patch `briefing_latest.json`

```python
import json
from datetime import datetime, date

b = json.load(open('docs/data/briefing_latest.json'))

# ── METRICS ──
# Only update values where WebSearch found a NEWER or CORRECTED value.
# If the current value matches what WebSearch found, leave it alone.
# Example updates (replace with actual findings):

updates = {
    # key: (new_value, period, previous, change, source_url)
    # Only include keys where you found updated data
}

for key, (val, period, prev, change, url) in updates.items():
    b['metrics'][key] = val
    if key in b.get('indicatorMeta', {}):
        b['indicatorMeta'][key]['period'] = period
        if prev: b['indicatorMeta'][key]['prev'] = prev
        if change: b['indicatorMeta'][key]['change'] = change
    if key in b.get('indicatorSources', {}):
        b['indicatorSources'][key] = url

# ── FINANCIAL MARKETS ──
# Update or add indices
# The structure is: financialMarkets.indices = [{name, value, day, yy, region}]
# and financialMarkets.fx = [{name, value, day, yy}]

# ── COMMODITIES ──
# Structure: commodities = [{category, color, items: [{name, unit, val, yy, day}]}]
# Update item values within their categories

# ── YIELD CURVE ──
# Structure: yieldCurve = [{term, yield, highlight}]

# ── TIMESTAMPS ──
b['updated_at'] = date.today().isoformat()

with open('docs/data/briefing_latest.json', 'w') as f:
    json.dump(b, f, indent=2, ensure_ascii=False)
```

### 7b: Patch `indicators.json`

For each indicator that changed, find the matching record(s) in `indicators.json` and update:

```python
inds_data = json.load(open('docs/data/indicators.json'))
indicators = inds_data.get('indicators', [])

def update_indicator(indicators, name, province, new_value, new_period, source):
    """Update an indicator record. Matches on indicator_name + province."""
    for ind in indicators:
        if ind.get('indicator_name') == name and ind.get('province') == province:
            ind['previous_value'] = ind.get('value')
            ind['value'] = new_value
            ind['period'] = new_period
            ind['source'] = source
            ind['fetched_at'] = datetime.utcnow().isoformat() + 'Z'
            return True
    return False

# Apply updates...
# If an indicator doesn't exist yet, append a new record

with open('docs/data/indicators.json', 'w') as f:
    json.dump(inds_data, f, indent=2, ensure_ascii=False)
```

### 7c: Important Patch Rules

1. **Never overwrite a value with an older one.** Check the period — if the current data is from February 2026 and your search only found January 2026 data, don't downgrade.

2. **Preserve the exact format.** If the current BoC rate is stored as `"2.25%"` (string with percent), don't change it to `2.25` (number without percent). Match the existing format.

3. **Handle missing gracefully.** If you couldn't find a value, leave the current one in place. Don't null it out.

4. **Update timestamps.** Set `fetched_at` to now and `updated_at` on the briefing to today.

5. **Keep province codes consistent.** The data uses both full names ("Ontario") and codes ("ON") — match whichever the existing record uses.

---

## Phase 8: Append Historical Snapshot

This is what builds the time series database over weeks. Each run appends one snapshot.

```python
import json, os
from datetime import datetime, date

snapshot_path = 'docs/data/data_snapshots.json'

# Load existing snapshots
if os.path.exists(snapshot_path):
    with open(snapshot_path) as f:
        snapshots = json.load(f)
else:
    snapshots = []

# Build this week's snapshot
snapshot = {
    "date": date.today().isoformat(),
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "source": "websearch_refresh",

    "national": {
        "boc_rate": None,       # fill from findings
        "real_gdp": None,
        "cpi_yoy": None,
        "unemployment": None,
        "employment_rate": None,
        "participation_rate": None,
        "housing_starts_saar": None,
        "building_permits": None,
        "wage_growth": None
    },

    "markets": {
        "tsx": None,
        "sp500": None,
        "djia": None,
        "nasdaq": None,
        "ftse100": None,
        "dax": None,
        "nikkei225": None,
        "cad_usd": None,
        "eur_usd": None,
        "usd_cny": None,
        "usd_jpy": None
    },

    "commodities": {
        "wti": None,
        "brent": None,
        "natural_gas": None,
        "gold": None,
        "silver": None,
        "copper": None,
        "aluminum": None,
        "lumber": None,
        "potash": None,
        "wheat": None,
        "iron_ore": None
    },

    "yields": {
        "goc_2y": None,
        "goc_5y": None,
        "goc_10y": None,
        "goc_long": None,
        "spread_10y2y": None
    },

    "provincial_unemployment": {
        "ON": None, "QC": None, "AB": None, "BC": None,
        "SK": None, "MB": None, "NS": None, "NB": None,
        "NL": None, "PE": None, "YT": None, "NT": None, "NU": None
    },

    "data_quality": {
        "searches_run": 0,
        "values_updated": 0,
        "values_unchanged": 0,
        "values_not_found": 0,
        "coverage_pct": 0.0
    }
}

# Fill in values from your research...

# Deduplicate (don't add two snapshots for the same date)
snapshots = [s for s in snapshots if s.get('date') != snapshot['date']]
snapshots.append(snapshot)

# Sort by date (most recent last)
snapshots.sort(key=lambda s: s.get('date', ''))

with open(snapshot_path, 'w') as f:
    json.dump(snapshots, f, indent=2, ensure_ascii=False)

print(f"Snapshot saved. Total snapshots in database: {len(snapshots)}")
```

Over time, `data_snapshots.json` becomes a rich time series:
- Week 1: 1 snapshot
- Week 10: 10 snapshots — enough to see trends
- Week 52: 52 snapshots — a full year of weekly data

The frontend or analysis agents can read this file to compute week-over-week changes, moving averages, and trend detection without needing the full indicators.json history.

---

## Phase 9: Generate Refresh Report

Print a summary for the user:

```
Data Refresh Complete — [DATE]
Searches run: [N]

=== NATIONAL INDICATORS ===
| Indicator        | Previous  | Updated   | Period   | Status    |
|-----------------|-----------|-----------|----------|-----------|
| BoC Rate        | 2.25%     | 2.25%     | Mar 2026 | UNCHANGED |
| CPI             | +1.8%     | +1.8%     | Feb 2026 | UNCHANGED |
| Unemployment    | 6.7%      | 6.7%      | Feb 2026 | UNCHANGED |
| WTI Crude       | $87.84    | $101.01   | Mar 30   | UPDATED !!|
| TSX Composite   | (missing) | 31,961    | Mar 27   | NEW       |
...

=== COVERAGE ===
Values updated: [N] / Values unchanged: [N] / Not found: [N]
Provincial coverage: [N]/13 provinces

=== SNAPSHOT DATABASE ===
Total weekly snapshots: [N]
Date range: [earliest] to [latest]

=== DATA QUALITY FLAGS ===
- [Any values that seem suspicious or contradictory]
- [Any searches that returned conflicting information]
- [Any provinces/indicators with no data available]
```

---

## Important Rules

1. **WebSearch is your only data source.** Don't use curl, wget, or Python HTTP libraries — they're blocked in the sandbox. WebSearch is the way.

2. **Authoritative sources first.** Prefer bankofcanada.ca, statcan.gc.ca, cmhc-schl.gc.ca over news articles. News articles are acceptable for market prices (tradingeconomics.com, yahoo finance).

3. **Never fabricate data.** If you can't find a value, leave the current one in place. An old value is better than a fake one.

4. **Record the reference period, not the search date.** If you search on March 30 and find February CPI data, the period is "Feb 2026", not "Mar 2026".

5. **Be careful with units.** WTI in $/bbl, gold in $/oz, copper in $/lb, lumber in $/MBF. Match what the existing data uses.

6. **Handle conflicting sources.** If two sources report different values, use the more authoritative one (government > financial data provider > news article). Note the discrepancy in the report.

7. **Don't update what's already current.** If the BoC rate was updated 5 days ago and hasn't changed, don't re-search for it. Focus your searches on genuinely stale or missing data.

8. **The snapshot database is append-only.** Never modify past snapshots. Only add new ones or replace the current date's snapshot (for re-runs on the same day).

9. **Provincial data for territories will often be unavailable.** YT, NT, and NU have limited statistical coverage. Record what you can find and note gaps — don't treat missing territory data as a failure.

10. **This agent runs BEFORE the briefing agents.** Its output is the foundation they build on. Accuracy over speed.
