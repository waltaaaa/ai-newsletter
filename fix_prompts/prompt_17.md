Run this with: `claude -p "$(cat fix_prompts/prompt_17.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to expand the StatCan indicators collected in Phase 1 (Data Collection). The pipeline already has a StatCan table registry script and WDS API access, but only pulls building permit data for Tier 9. Several other tables provide direct signals about capital investment, construction activity, and economic conditions that should feed into the indicator history and cross-reference engine. Read the relevant files before making changes.

## Context

StatCan publishes structured time series that are directly relevant to economic forecasting and project tracking. These aren't RSS articles that need filtering — they're hard data: actual dollar amounts, physical volumes, employment counts. They go straight into `indicator_history` and feed the cross-reference engine, Claude analysis calls, and the weekly briefing.

## Part 1: Add new StatCan table pulls to data collection

File: `phases/data_collection.py`

Add the following StatCan tables to the data collection phase. Use the WDS API (`https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en`) or the JSON endpoint format the pipeline already uses. Each table has a product ID (PID) that maps to a specific dataset.

### Investment and Capital Expenditure
```python
STATCAN_INVESTMENT_TABLES = {
    # Capital expenditure intentions by sector and province
    "34-10-0035": {
        "name": "Capital and repair expenditures, by industry and province",
        "frequency": "annual",
        "indicators": ["total_capex", "construction_capex", "machinery_capex"],
        "sectors": ["all"],
        "notes": "Annual survey of capex intentions — leading indicator of construction"
    },
    # Investment in building construction
    "34-10-0175": {
        "name": "Investment in building construction",
        "frequency": "quarterly",
        "indicators": ["residential_investment", "non_residential_investment",
                       "industrial_investment", "commercial_investment",
                       "institutional_investment"],
        "sectors": ["residential", "commercial_mixed", "infrastructure"],
        "notes": "Quarterly actual investment in buildings by type"
    },
    # Non-residential building construction price index
    "18-10-0135": {
        "name": "Non-residential building construction price index",
        "frequency": "quarterly",
        "indicators": ["construction_price_index"],
        "sectors": ["infrastructure", "commercial_mixed"],
        "notes": "Cost escalation indicator — affects project viability"
    },
}

# Employment (leading indicator of activity)
STATCAN_EMPLOYMENT_TABLES = {
    # Employment by industry
    "14-10-0022": {
        "name": "Employment by industry, monthly",
        "frequency": "monthly",
        "indicators": ["construction_employment", "mining_employment",
                       "manufacturing_employment"],
        "sectors": ["infrastructure", "mining", "manufacturing"],
        "notes": "Monthly LFS — construction employment is a real-time activity indicator"
    },
    # Job vacancies by industry
    "14-10-0326": {
        "name": "Job vacancies by industry sector",
        "frequency": "quarterly",
        "indicators": ["construction_vacancies", "mining_vacancies"],
        "sectors": ["infrastructure", "mining"],
        "notes": "Complements the job_monitor module — official vacancy data"
    },
}

# Trade (for resource sectors)
STATCAN_TRADE_TABLES = {
    # International trade by commodity
    "12-10-0129": {
        "name": "Merchandise exports by commodity",
        "frequency": "monthly",
        "indicators": ["energy_exports", "mineral_exports", "forestry_exports",
                       "agri_exports"],
        "sectors": ["oil_gas", "mining", "forestry", "agriculture"],
        "notes": "Export volumes by sector — demand signal for resource projects"
    },
}

# Housing-specific
STATCAN_HOUSING_TABLES = {
    # Housing starts and completions (supplements CMHC data)
    "34-10-0143": {
        "name": "Housing starts, by type and province",
        "frequency": "monthly",
        "indicators": ["housing_starts_single", "housing_starts_multi",
                       "housing_starts_total"],
        "sectors": ["residential"],
        "notes": "CMHC housing starts — leading indicator for residential sector"
    },
    # New housing price index
    "18-10-0205": {
        "name": "New housing price index",
        "frequency": "monthly",
        "indicators": ["new_housing_price_index"],
        "sectors": ["residential"],
        "notes": "Price trends in new construction"
    },
}
```

## Part 2: Create `statcan_extended.py`

Create a new module that handles fetching these additional tables:

```python
"""
Extended StatCan data collection — investment, employment, trade, and housing
indicators beyond the base permit data.

Uses the StatCan WDS API (free, no key required).
Outputs go to indicator_history table for cross-referencing and trend analysis.
"""
import requests
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

WDS_BASE = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action"
WDS_JSON = "https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en"

# Combine all table configs
ALL_TABLES = {}
# Import from data_collection or define here — merge all dicts above

def fetch_statcan_table(pid, periods=4):
    """
    Fetch the most recent N periods from a StatCan table.
    
    Args:
        pid: StatCan product ID (e.g., "34-10-0035")
        periods: number of most recent periods to fetch
    
    Returns:
        list of dicts with date, value, and metadata
    """
    try:
        url = f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid.replace('-', '')}"
        
        # Try the JSON API first
        api_url = f"https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en?pid={pid.replace('-', '')}&latestN={periods}&startDate=&endDate=&csvLocale=en&selectedMembers="
        
        resp = requests.get(api_url, timeout=20)
        if resp.status_code != 200:
            print(f"[STATCAN] Table {pid} returned {resp.status_code}")
            return []
        
        # Parse the response (CSV or JSON depending on endpoint)
        # The exact parsing depends on which WDS endpoint works — 
        # check the existing statcan code in the pipeline for the pattern used
        
        return _parse_statcan_response(resp, pid)
        
    except Exception as e:
        print(f"[WARN] StatCan table {pid} fetch failed: {e}")
        return []


def _parse_statcan_response(resp, pid):
    """Parse StatCan API response into indicator records."""
    records = []
    # Implementation depends on the response format used by the existing
    # StatCan code in the pipeline — match that pattern exactly.
    # The key fields to extract are: date, value, geo (province), indicator name
    return records


def save_indicators(conn, records, source_table):
    """Save fetched indicators to the indicator_history table."""
    cursor = conn.cursor()
    saved = 0
    
    for record in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO indicator_history 
                (indicator, value, date, source, province)
                VALUES (?, ?, ?, ?, ?)
            """, (
                record["indicator"],
                record["value"],
                record["date"],
                f"statcan_{source_table}",
                record.get("province"),
            ))
            saved += 1
        except Exception as e:
            logger.debug(f"[STATCAN] Failed to save indicator: {e}")
    
    conn.commit()
    return saved


def run_extended_statcan(conn):
    """
    Fetch all extended StatCan tables and save to indicator_history.
    
    Returns dict with fetch results for pipeline context.
    """
    total_fetched = 0
    total_saved = 0
    tables_succeeded = 0
    tables_failed = 0
    
    tables_to_fetch = {
        "34-10-0035": "Capital expenditures by industry",
        "34-10-0175": "Investment in building construction",
        "18-10-0135": "Construction price index",
        "14-10-0022": "Employment by industry",
        "14-10-0326": "Job vacancies by industry",
        "12-10-0129": "Merchandise exports by commodity",
        "34-10-0143": "Housing starts by province",
        "18-10-0205": "New housing price index",
    }
    
    for pid, name in tables_to_fetch.items():
        try:
            records = fetch_statcan_table(pid)
            if records:
                saved = save_indicators(conn, records, pid)
                total_fetched += len(records)
                total_saved += saved
                tables_succeeded += 1
                print(f"[STATCAN] {pid} ({name}): {len(records)} records, {saved} saved")
            else:
                tables_failed += 1
                print(f"[STATCAN] {pid} ({name}): no data returned")
        except Exception as e:
            tables_failed += 1
            print(f"[WARN] StatCan {pid} ({name}) failed: {e}")
    
    print(f"[STATCAN] Extended: {tables_succeeded} tables succeeded, "
          f"{tables_failed} failed, {total_saved} indicators saved")
    
    return {
        "statcan_extended_fetched": total_fetched,
        "statcan_extended_saved": total_saved,
        "statcan_extended_tables": tables_succeeded,
    }
```

**IMPORTANT:** Before writing the parsing code, read the existing StatCan code in `phases/data_collection.py`, `statcan_permits.py`, or wherever the pipeline currently fetches StatCan data. Match the exact same API endpoint format, parsing logic, and error handling pattern. Do NOT invent a new StatCan API integration — extend the one that already works.

## Part 3: Integrate into data collection phase

File: `phases/data_collection.py`

Add after the existing StatCan/indicator fetches:

```python
try:
    from statcan_extended import run_extended_statcan
    statcan_ext = run_extended_statcan(conn)
    context.update(statcan_ext)
except ImportError:
    print("[WARN] statcan_extended not available")
except Exception as e:
    print(f"[WARN] Extended StatCan fetch failed: {e}")
```

## Part 4: Update cross-reference engine

File: `cross_reference.py`

The new indicators (construction employment, capex intentions, housing starts, export volumes) should be available to the cross-reference engine for linking to projects. No code change needed if `cross_reference.py` already reads from `indicator_history` — the new indicators will appear automatically. But verify that the sector mapping in the cross-reference engine includes mappings for the new indicator names.

## Part 5: Update CLAUDE.md

Add to Repository Layout:
```
├── statcan_extended.py         # Extended StatCan indicators (investment, employment, trade, housing)
```

Update the Data Collection section to note the additional tables:
```
StatCan Extended: 8 additional tables covering capital expenditure intentions, 
building investment, construction costs, employment by industry, job vacancies, 
merchandise exports, housing starts, and housing prices. All fetched via WDS API. 
Zero cost, no API key.
```

## Important constraints

- Zero cost — StatCan WDS API is free, no registration
- Match the existing StatCan fetching pattern exactly — do not introduce a new API client
- Annual tables (capex intentions) only update once per year — don't fetch them on daily runs. Check the `mode` in context: if `indicators-only`, skip annual and quarterly tables, only fetch monthly ones.
- StatCan rate limits are generous but do exist. Add 1-second delays between table fetches.
- These are HARD DATA indicators — they go into `indicator_history` and are treated as ground truth, never overridden by LLM output. This is consistent with the existing "hard data always wins" rule.
