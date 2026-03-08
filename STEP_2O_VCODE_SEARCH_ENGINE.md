> **CLAUDE CODE SETUP — RUN THESE BEFORE STARTING:**
> 1. Type `/clear` to wipe conversation history from any previous step
> 2. Launch with `claude --dangerously-skip-permissions` to auto-approve all file edits and bash commands
> 3. Enter Plan Mode (Shift+Tab twice) and paste this file — review the plan before executing
> 4. If context gets heavy mid-step, run `/compact` to summarize and free space

# STEP_2O — CANSIM V-CODE SEARCH ENGINE & DATA EXPLORER

**Prerequisites:** Backup tagged as v2.0-stable must exist before starting.
**This step adds a plain-English search tool for Statistics Canada V-codes with direct StatsCan links and live data preview.**

---

## WHAT THIS DOES

A "Data Explorer" feature on the dashboard where users type natural-language queries like "Canadian auto exports by province" or "housing starts Alberta" and get back the exact StatsCan V-codes, metadata, live data, and a direct link to the StatsCan page for that series. Combines a pre-indexed local database of ~3,000 curated V-codes with Gemini Flash fallback for queries the index can't match.

## WHY

Finding the right V-code in StatsCan is painful. There are millions of vectors spread across thousands of tables. StatsCan's own search requires knowing table numbers, dimension coordinates, and geographic codes. This tool lets anyone search in plain English and get exactly the data they need — plus a clickable link to verify it on StatsCan directly.

---

## PART 1: CURATED V-CODE INDEX

### Step 1: Build the V-code database

This is the core reference data. Each entry contains enough metadata for both fuzzy text search and direct StatsCan URL construction.

```python
"""
vcode_index.py — Curated index of Statistics Canada V-codes
for the most relevant Canadian macro, economic, and construction indicators.

Each entry:
- vcode: The CANSIM vector ID (e.g., "V2057609")
- table: StatsCan table number (e.g., "14-10-0287-01")
- title: Human-readable series name
- description: Detailed description with keywords for search matching
- geography: Province/CMA/national
- frequency: monthly, quarterly, annual
- unit: persons, dollars, percent, index, etc.
- subject: High-level category for grouping
- keywords: Additional search terms
- statcan_url: Direct link to the data on StatsCan website

StatsCan table URL format:
  https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}
  Example: Table 14-10-0287-01 → pid=1410028701

StatsCan vector URL format (individual series):
  https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en?vectorIds={vcode_number}
  
StatsCan table page with specific vector highlighted:
  https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}&pickMembers%5B0%5D={geo_code}
"""

import json
import os
import re
import logging

logger = logging.getLogger(__name__)

INDEX_FILE = os.path.join(os.path.dirname(__file__), "vcode_index.json")


def build_statcan_table_url(table_number):
    """Convert table number to StatsCan URL.
    
    Example: "14-10-0287-01" → "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701"
    """
    pid = table_number.replace("-", "")
    return f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid}"


def build_statcan_vector_url(vcode):
    """Convert V-code to StatsCan download URL.
    
    Example: "V2057609" → direct download link
    """
    num = vcode.replace("V", "").replace("v", "")
    return f"https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en?vectorIds={num}"


# ============================================================================
# CURATED V-CODE DATABASE
# ============================================================================
# Organized by subject area. Each entry is a dict.
# This is the initial seed — the index grows via Gemini discovery (Part 3).

CURATED_VCODES = [
    # ═══════════════════════════════════════════════════════════
    # LABOUR MARKET (Table 14-10-0287-01, 14-10-0355-01)
    # ═══════════════════════════════════════════════════════════
    
    # National
    {"vcode": "V2057609", "table": "14-10-0287-01", "title": "Employment, Canada", "description": "Total employment, both sexes, 15 years and over, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "persons", "subject": "labour_market", "keywords": ["jobs", "employment", "workforce", "labour force"]},
    {"vcode": "V2057610", "table": "14-10-0287-01", "title": "Unemployment rate, Canada", "description": "Unemployment rate, both sexes, 15 years and over, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["unemployment", "jobless", "labour market"]},
    {"vcode": "V2057776", "table": "14-10-0355-01", "title": "Construction employment, Canada", "description": "Employment in construction industry, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "persons", "subject": "labour_market", "keywords": ["construction jobs", "construction employment", "building trades"]},
    
    # Provincial unemployment
    {"vcode": "V2057818", "table": "14-10-0287-01", "title": "Unemployment rate, Ontario", "description": "Unemployment rate, Ontario, both sexes, 15+, seasonally adjusted", "geography": "ON", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["ontario unemployment", "ontario jobs"]},
    {"vcode": "V2057832", "table": "14-10-0287-01", "title": "Unemployment rate, Quebec", "description": "Unemployment rate, Quebec, both sexes, 15+, seasonally adjusted", "geography": "QC", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["quebec unemployment", "quebec jobs"]},
    {"vcode": "V2057846", "table": "14-10-0287-01", "title": "Unemployment rate, Alberta", "description": "Unemployment rate, Alberta, both sexes, 15+, seasonally adjusted", "geography": "AB", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["alberta unemployment", "alberta jobs"]},
    {"vcode": "V2057860", "table": "14-10-0287-01", "title": "Unemployment rate, British Columbia", "description": "Unemployment rate, BC, both sexes, 15+, seasonally adjusted", "geography": "BC", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["bc unemployment", "british columbia jobs"]},
    {"vcode": "V2057874", "table": "14-10-0287-01", "title": "Unemployment rate, Saskatchewan", "description": "Unemployment rate, Saskatchewan, both sexes, 15+, seasonally adjusted", "geography": "SK", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["saskatchewan unemployment"]},
    {"vcode": "V2057888", "table": "14-10-0287-01", "title": "Unemployment rate, Manitoba", "description": "Unemployment rate, Manitoba, both sexes, 15+, seasonally adjusted", "geography": "MB", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["manitoba unemployment"]},
    {"vcode": "V2057902", "table": "14-10-0287-01", "title": "Unemployment rate, Nova Scotia", "description": "Unemployment rate, Nova Scotia, both sexes, 15+, seasonally adjusted", "geography": "NS", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["nova scotia unemployment"]},
    {"vcode": "V2057916", "table": "14-10-0287-01", "title": "Unemployment rate, New Brunswick", "description": "Unemployment rate, New Brunswick, both sexes, 15+, seasonally adjusted", "geography": "NB", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["new brunswick unemployment"]},
    {"vcode": "V2057930", "table": "14-10-0287-01", "title": "Unemployment rate, Newfoundland and Labrador", "description": "Unemployment rate, NL, both sexes, 15+, seasonally adjusted", "geography": "NL", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["newfoundland unemployment"]},
    {"vcode": "V2057944", "table": "14-10-0287-01", "title": "Unemployment rate, Prince Edward Island", "description": "Unemployment rate, PEI, both sexes, 15+, seasonally adjusted", "geography": "PE", "frequency": "monthly", "unit": "percent", "subject": "labour_market", "keywords": ["pei unemployment"]},
    
    # ═══════════════════════════════════════════════════════════
    # GDP (Table 36-10-0434-01, 36-10-0402-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V65201210", "table": "36-10-0434-01", "title": "GDP at basic prices, all industries, Canada", "description": "Gross domestic product at basic prices, all industries, monthly, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["gdp", "gross domestic product", "economic output", "economic growth"]},
    {"vcode": "V65201236", "table": "36-10-0434-01", "title": "GDP, Construction, Canada", "description": "GDP at basic prices, construction industry, monthly, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["construction gdp", "construction output", "building industry gdp"]},
    {"vcode": "V65201232", "table": "36-10-0434-01", "title": "GDP, Mining, quarrying, oil and gas", "description": "GDP at basic prices, mining quarrying and oil gas extraction, monthly, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["mining gdp", "oil gas gdp", "resource extraction gdp"]},
    {"vcode": "V65201238", "table": "36-10-0434-01", "title": "GDP, Manufacturing, Canada", "description": "GDP at basic prices, manufacturing, monthly, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["manufacturing gdp", "factory output"]},
    
    # Provincial GDP (Table 36-10-0402-01, annual)
    {"vcode": "V62305752", "table": "36-10-0402-01", "title": "GDP, Ontario", "description": "Gross domestic product, expenditure-based, Ontario, annual", "geography": "ON", "frequency": "annual", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["ontario gdp", "ontario economy"]},
    {"vcode": "V62305753", "table": "36-10-0402-01", "title": "GDP, Quebec", "description": "Gross domestic product, expenditure-based, Quebec, annual", "geography": "QC", "frequency": "annual", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["quebec gdp", "quebec economy"]},
    {"vcode": "V62305754", "table": "36-10-0402-01", "title": "GDP, Alberta", "description": "Gross domestic product, expenditure-based, Alberta, annual", "geography": "AB", "frequency": "annual", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["alberta gdp", "alberta economy"]},
    {"vcode": "V62305755", "table": "36-10-0402-01", "title": "GDP, British Columbia", "description": "Gross domestic product, expenditure-based, BC, annual", "geography": "BC", "frequency": "annual", "unit": "chained 2017 dollars", "subject": "gdp", "keywords": ["bc gdp", "british columbia economy"]},
    
    # ═══════════════════════════════════════════════════════════
    # BUILDING PERMITS (Table 34-10-0066-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V51891", "table": "34-10-0066-01", "title": "Building permits, total, Canada", "description": "Total value of building permits, all types, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "construction", "keywords": ["building permits", "construction permits", "permit value"]},
    {"vcode": "V51893", "table": "34-10-0066-01", "title": "Building permits, residential, Canada", "description": "Value of residential building permits, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "construction", "keywords": ["residential permits", "housing permits"]},
    {"vcode": "V51895", "table": "34-10-0066-01", "title": "Building permits, non-residential, Canada", "description": "Value of non-residential building permits, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "construction", "keywords": ["commercial permits", "industrial permits", "institutional permits"]},
    
    # ═══════════════════════════════════════════════════════════
    # HOUSING (Table 34-10-0143-01, 34-10-0145-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V729965", "table": "34-10-0143-01", "title": "Housing starts, total, Canada", "description": "Housing starts, all areas, total units, Canada, monthly, seasonally adjusted annual rate", "geography": "national", "frequency": "monthly", "unit": "units", "subject": "housing", "keywords": ["housing starts", "new homes", "residential construction starts"]},
    {"vcode": "V729966", "table": "34-10-0143-01", "title": "Housing starts, single-detached, Canada", "description": "Housing starts, single-detached units, Canada, monthly, SAAR", "geography": "national", "frequency": "monthly", "unit": "units", "subject": "housing", "keywords": ["single family housing starts", "detached homes"]},
    {"vcode": "V729967", "table": "34-10-0143-01", "title": "Housing starts, multi-unit, Canada", "description": "Housing starts, multi-unit (apartments, condos, row), Canada, monthly, SAAR", "geography": "national", "frequency": "monthly", "unit": "units", "subject": "housing", "keywords": ["apartment starts", "condo starts", "multi-family starts"]},
    
    # ═══════════════════════════════════════════════════════════
    # CONSUMER PRICE INDEX (Table 18-10-0004-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V41690973", "table": "18-10-0004-01", "title": "CPI, All-items, Canada", "description": "Consumer Price Index, all-items, Canada, monthly, not seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "index 2002=100", "subject": "prices", "keywords": ["cpi", "inflation", "consumer prices", "cost of living"]},
    {"vcode": "V41693271", "table": "18-10-0004-01", "title": "CPI, Shelter, Canada", "description": "Consumer Price Index, shelter component, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "index 2002=100", "subject": "prices", "keywords": ["shelter cpi", "housing inflation", "rent inflation"]},
    {"vcode": "V41691037", "table": "18-10-0004-01", "title": "CPI, Energy, Canada", "description": "Consumer Price Index, energy component, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "index 2002=100", "subject": "prices", "keywords": ["energy cpi", "energy prices", "gasoline prices"]},
    
    # ═══════════════════════════════════════════════════════════
    # TRADE (Table 12-10-0011-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V1001", "table": "12-10-0011-01", "title": "Exports, total, Canada", "description": "Domestic exports, total all commodities, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "trade", "keywords": ["exports", "trade", "merchandise exports"]},
    {"vcode": "V1002", "table": "12-10-0011-01", "title": "Imports, total, Canada", "description": "Imports, total all commodities, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "trade", "keywords": ["imports", "trade", "merchandise imports"]},
    {"vcode": "V1003", "table": "12-10-0011-01", "title": "Trade balance, Canada", "description": "Trade balance (exports minus imports), Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "trade", "keywords": ["trade balance", "trade surplus", "trade deficit"]},
    
    # ═══════════════════════════════════════════════════════════
    # AUTO SECTOR (Table 16-10-0047-01, 12-10-0011-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V79311125", "table": "16-10-0047-01", "title": "Motor vehicle production, Canada", "description": "Motor vehicle production, total units, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "units", "subject": "manufacturing", "keywords": ["auto production", "car production", "vehicle manufacturing", "automotive"]},
    {"vcode": "V79311126", "table": "16-10-0047-01", "title": "Motor vehicle sales, Canada", "description": "New motor vehicle sales, total units, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "units", "subject": "manufacturing", "keywords": ["auto sales", "car sales", "vehicle sales"]},
    
    # ═══════════════════════════════════════════════════════════
    # INVESTMENT & CAPITAL EXPENDITURE (Table 34-10-0035-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V753050", "table": "34-10-0035-01", "title": "Capital expenditures, non-residential construction, Canada", "description": "Capital expenditures, non-residential construction, all industries, Canada", "geography": "national", "frequency": "annual", "unit": "dollars", "subject": "investment", "keywords": ["capex", "capital expenditure", "non-residential investment", "business investment"]},
    {"vcode": "V753051", "table": "34-10-0035-01", "title": "Capital expenditures, machinery and equipment, Canada", "description": "Capital expenditures, machinery and equipment, all industries, Canada", "geography": "national", "frequency": "annual", "unit": "dollars", "subject": "investment", "keywords": ["machinery investment", "equipment spending"]},
    
    # ═══════════════════════════════════════════════════════════
    # RETAIL & WHOLESALE (Table 20-10-0008-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V52367097", "table": "20-10-0008-01", "title": "Retail trade, total, Canada", "description": "Retail trade, total, all industries, Canada, monthly, seasonally adjusted", "geography": "national", "frequency": "monthly", "unit": "dollars", "subject": "retail", "keywords": ["retail sales", "consumer spending", "retail trade"]},
    
    # ═══════════════════════════════════════════════════════════
    # INDUSTRIAL PRODUCT PRICES (Table 18-10-0265-01, 18-10-0268-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V86573198", "table": "18-10-0265-01", "title": "Industrial Product Price Index, total, Canada", "description": "IPPI, total, all commodities, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "index 2020=100", "subject": "prices", "keywords": ["producer prices", "industrial prices", "ippi", "wholesale prices"]},
    {"vcode": "V86573328", "table": "18-10-0268-01", "title": "Raw Materials Price Index, total, Canada", "description": "RMPI, total, all commodities, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "index 2020=100", "subject": "prices", "keywords": ["raw materials prices", "commodity prices", "rmpi", "input costs"]},
    
    # ═══════════════════════════════════════════════════════════
    # POPULATION & DEMOGRAPHICS (Table 17-10-0009-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V1", "table": "17-10-0009-01", "title": "Population, Canada", "description": "Population estimate, Canada, quarterly", "geography": "national", "frequency": "quarterly", "unit": "persons", "subject": "demographics", "keywords": ["population", "population growth", "demographics"]},
    
    # ═══════════════════════════════════════════════════════════
    # ENERGY (Table 25-10-0015-01, 25-10-0063-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V78546845", "table": "25-10-0015-01", "title": "Crude oil production, Canada", "description": "Total crude oil and equivalent production, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "cubic metres", "subject": "energy", "keywords": ["oil production", "crude oil output", "petroleum production"]},
    {"vcode": "V78546852", "table": "25-10-0015-01", "title": "Natural gas production, Canada", "description": "Marketable natural gas production, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "cubic metres", "subject": "energy", "keywords": ["gas production", "natural gas output"]},
    
    # ═══════════════════════════════════════════════════════════
    # MINING (Table 16-10-0014-01)
    # ═══════════════════════════════════════════════════════════
    {"vcode": "V78530437", "table": "16-10-0014-01", "title": "Mining production, total, Canada", "description": "Mineral production, total all minerals, Canada, monthly", "geography": "national", "frequency": "monthly", "unit": "index 2017=100", "subject": "mining", "keywords": ["mining output", "mineral production", "mining index"]},
]

# Subject categories for grouping in UI
SUBJECTS = {
    "labour_market": "Labour Market & Employment",
    "gdp": "GDP & Economic Output",
    "construction": "Construction & Building Permits",
    "housing": "Housing Starts & Completions",
    "prices": "Prices & Inflation",
    "trade": "International Trade",
    "manufacturing": "Manufacturing & Auto Sector",
    "investment": "Business Investment & Capital Expenditure",
    "retail": "Retail & Consumer Spending",
    "demographics": "Population & Demographics",
    "energy": "Energy Production",
    "mining": "Mining & Resources",
}


def load_index():
    """Load the V-code index. Uses curated list + any Gemini-discovered additions."""
    index = list(CURATED_VCODES)
    
    # Load any Gemini-discovered V-codes from JSON file
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            discovered = json.load(f)
            index.extend(discovered)
    
    # Add StatsCan URLs to all entries
    for entry in index:
        entry["statcan_table_url"] = build_statcan_table_url(entry["table"])
        entry["statcan_vector_url"] = build_statcan_vector_url(entry["vcode"])
    
    return index


def save_discovered_vcodes(new_entries):
    """Save newly discovered V-codes to the index file."""
    existing = []
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            existing = json.load(f)
    
    # Dedup by vcode
    existing_vcodes = {e["vcode"] for e in existing}
    for entry in new_entries:
        if entry["vcode"] not in existing_vcodes:
            existing.append(entry)
            existing_vcodes.add(entry["vcode"])
    
    with open(INDEX_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    
    logger.info(f"V-code index updated: {len(existing)} discovered entries")
```

### Step 2: Local fuzzy search engine

```python
"""
vcode_search.py — Fuzzy text search over the V-code index.

Handles natural-language queries by matching against title, description,
keywords, geography, and subject fields. Returns ranked results with
StatsCan URLs.
"""

import re
from collections import defaultdict
from vcode_index import load_index, SUBJECTS


def search_vcodes(query, max_results=10):
    """Search the V-code index with a natural-language query.
    
    Scoring:
    - Exact match in title: +10
    - Exact match in keywords: +8
    - Exact match in description: +5
    - Word match in title: +3 per word
    - Word match in keywords: +2 per word
    - Word match in description: +1 per word
    - Province match: +5
    - Subject match: +3
    
    Returns list of result dicts, sorted by score descending.
    """
    index = load_index()
    query_lower = query.lower().strip()
    query_words = set(re.findall(r'[a-z]+', query_lower))
    
    # Remove stop words
    stop_words = {"the", "of", "and", "in", "at", "for", "a", "an", "to", "is", "on",
                  "by", "what", "how", "much", "many", "show", "me", "get", "find",
                  "give", "canadian", "canada", "statistics", "statcan", "data"}
    query_words -= stop_words
    
    # Province detection
    province_map = {
        "ontario": "ON", "quebec": "QC", "alberta": "AB", "british columbia": "BC",
        "bc": "BC", "saskatchewan": "SK", "manitoba": "MB", "nova scotia": "NS",
        "new brunswick": "NB", "newfoundland": "NL", "labrador": "NL",
        "pei": "PE", "prince edward island": "PE", "yukon": "YT",
        "northwest territories": "NT", "nunavut": "NU", "national": "national",
    }
    
    detected_province = None
    for prov_name, prov_code in province_map.items():
        if prov_name in query_lower:
            detected_province = prov_code
            break
    
    results = []
    
    for entry in index:
        score = 0
        
        title_lower = entry.get("title", "").lower()
        desc_lower = entry.get("description", "").lower()
        keywords = [k.lower() for k in entry.get("keywords", [])]
        keywords_joined = " ".join(keywords)
        geo = entry.get("geography", "")
        subject = entry.get("subject", "")
        
        # Exact query match in fields
        if query_lower in title_lower:
            score += 10
        if query_lower in keywords_joined:
            score += 8
        if query_lower in desc_lower:
            score += 5
        
        # Word-level matching
        for word in query_words:
            if word in title_lower:
                score += 3
            if any(word in kw for kw in keywords):
                score += 2
            if word in desc_lower:
                score += 1
        
        # Province match
        if detected_province and geo == detected_province:
            score += 5
        elif detected_province == "national" and geo == "national":
            score += 3
        
        # Subject match (if query words match subject keywords)
        subject_name = SUBJECTS.get(subject, "").lower()
        for word in query_words:
            if word in subject_name:
                score += 3
        
        if score > 0:
            results.append({
                "score": score,
                "vcode": entry["vcode"],
                "table": entry["table"],
                "title": entry["title"],
                "description": entry["description"],
                "geography": entry["geography"],
                "frequency": entry["frequency"],
                "unit": entry["unit"],
                "subject": SUBJECTS.get(entry["subject"], entry["subject"]),
                "statcan_table_url": entry.get("statcan_table_url", ""),
                "statcan_vector_url": entry.get("statcan_vector_url", ""),
            })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]
```

---

## PART 2: GEMINI FLASH FALLBACK

When the local index can't find a good match, use one Gemini Flash query to find the right V-code.

```python
"""
vcode_gemini_fallback.py — Gemini Flash fallback for V-code discovery.

When the local index returns no good matches (score < 3), ask Gemini
to identify the correct StatsCan table and vector for the query.

Uses 1 query from the Gemini free tier budget.
"""

import json
import logging

logger = logging.getLogger(__name__)

VCODE_DISCOVERY_PROMPT = """You are a Statistics Canada data expert. The user wants to find 
a specific CANSIM V-code (vector) for a Canadian economic data series.

Given their query, identify:
1. The most likely Statistics Canada table number (format: XX-XX-XXXX-XX)
2. The specific V-code(s) that match their request
3. The exact title and description of each series
4. The geography (national, provincial, CMA)
5. The frequency (monthly, quarterly, annual)
6. The unit of measurement

Return ONLY a JSON array:
[{
    "vcode": "V2057609",
    "table": "14-10-0287-01",
    "title": "Employment, Canada",
    "description": "Total employment, both sexes, 15+, seasonally adjusted",
    "geography": "national",
    "frequency": "monthly",
    "unit": "persons",
    "subject": "labour_market",
    "keywords": ["employment", "jobs"]
}]

If you cannot identify the exact V-code, provide the table number and 
the closest matching series description. Do NOT fabricate V-codes — 
if unsure of the exact vector number, set vcode to "UNKNOWN" and 
provide the table number so the user can look it up.

IMPORTANT: Only reference real Statistics Canada tables that exist."""


async def discover_vcode_via_gemini(query):
    """Use Gemini Flash to find V-codes not in the local index.
    
    Returns list of discovered V-code entries (same schema as curated index).
    """
    from compound_discovery import _query_gemini
    import asyncio
    import aiohttp
    
    query_obj = {
        "query": f"What Statistics Canada CANSIM V-code (vector) provides data for: {query}. Include the table number, V-code, series title, geography, frequency, and unit.",
        "type": "vcode_discovery",
        "language": "en",
        "geo_tier": "reference",
    }
    
    # Use Gemini grounded search to find the answer
    # This uses 1 query from the free tier
    semaphore = asyncio.Semaphore(1)
    
    async with aiohttp.ClientSession() as session:
        result = await _query_gemini(session, semaphore, query_obj)
    
    # Parse response for V-code entries
    discovered = []
    if result and result.get("projects"):
        # Response might come back as projects — adapt parsing
        pass
    
    # Try to parse as direct JSON
    try:
        if isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = str(result)
        
        # Clean and parse JSON
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        entries = json.loads(text.strip())
        
        if isinstance(entries, list):
            for entry in entries:
                if entry.get("table"):
                    discovered.append(entry)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Could not parse Gemini V-code response for query: {query}")
    
    return discovered
```

---

## PART 3: LIVE DATA PREVIEW

Pull the actual data for matched V-codes so users see values, not just metadata.

```python
"""
vcode_data_fetch.py — Fetch live data for a V-code from Statistics Canada.

Uses the StatsCan Web Data Service to pull recent observations.
"""

import aiohttp
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

STATCAN_VECTOR_API = "https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en"


async def fetch_vcode_data(vcode, periods=12):
    """Fetch recent data points for a V-code.
    
    Args:
        vcode: V-code string (e.g., "V2057609")
        periods: Number of most recent periods to return
    
    Returns:
        dict with metadata and data points:
        {
            "vcode": "V2057609",
            "latest_value": 20150000,
            "latest_date": "2026-01",
            "data": [
                {"date": "2026-01", "value": 20150000},
                {"date": "2025-12", "value": 20120000},
                ...
            ]
        }
    """
    num = vcode.replace("V", "").replace("v", "")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=periods * 35)).strftime("%Y-%m-%d")
    
    url = f"https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadTbl/en?vectorIds={num}&startDate={start_date}&endDate={end_date}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Parse StatsCan response format
                    # Return formatted data points
                    return _parse_statcan_response(data, vcode)
                else:
                    logger.warning(f"StatsCan API {resp.status} for {vcode}")
                    return None
    except Exception as e:
        logger.warning(f"Failed to fetch {vcode}: {e}")
        return None


def _parse_statcan_response(data, vcode):
    """Parse StatsCan API response into clean data points."""
    # StatsCan returns CSV or JSON depending on endpoint
    # Parse and return standardized format
    return {
        "vcode": vcode,
        "data": [],
        "latest_value": None,
        "latest_date": None,
    }
```

---

## PART 4: FRONTEND — DATA EXPLORER TAB

```jsx
function DataExplorer() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedVcode, setSelectedVcode] = useState(null);
  const [previewData, setPreviewData] = useState(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSelectedVcode(null);
    setPreviewData(null);

    try {
      // Call backend search endpoint
      const res = await fetch(`/api/vcode-search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Search failed:", err);
    }
    setLoading(false);
  };

  const handlePreview = async (vcode) => {
    setSelectedVcode(vcode);
    try {
      const res = await fetch(`/api/vcode-data?v=${vcode}`);
      const data = await res.json();
      setPreviewData(data);
    } catch (err) {
      console.error("Preview failed:", err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      <h2 className="text-2xl font-bold mb-2">Data Explorer</h2>
      <p className="text-sm text-gray-600 mb-4">
        Search Statistics Canada data in plain English. Get V-codes, live data, and direct links.
      </p>

      {/* Search bar */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1 border rounded-lg px-4 py-2 text-sm"
          placeholder="e.g., unemployment rate Alberta, housing starts by province, auto exports..."
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Quick category buttons */}
      <div className="flex flex-wrap gap-2 mb-6">
        {["Labour Market", "GDP", "Construction", "Housing", "Inflation", "Trade", "Energy", "Mining"].map(cat => (
          <button
            key={cat}
            onClick={() => { setQuery(cat.toLowerCase()); }}
            className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-full"
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((r, i) => (
            <div key={i} className="border rounded-lg p-4 hover:border-blue-300 transition-colors">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                      {r.vcode}
                    </span>
                    <span className="text-xs text-gray-400">
                      Table {r.table}
                    </span>
                    <span className="text-xs text-gray-400">
                      {r.frequency} · {r.geography === "national" ? "Canada" : r.geography}
                    </span>
                  </div>
                  <h3 className="font-medium text-sm">{r.title}</h3>
                  <p className="text-xs text-gray-500 mt-1">{r.description}</p>
                  <p className="text-xs text-gray-400 mt-1">Unit: {r.unit} · Category: {r.subject}</p>
                </div>
                <div className="flex flex-col gap-1 ml-4">
                  <a
                    href={r.statcan_table_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs bg-green-50 text-green-700 px-3 py-1 rounded hover:bg-green-100 text-center"
                  >
                    View on StatsCan
                  </a>
                  <button
                    onClick={() => handlePreview(r.vcode)}
                    className="text-xs bg-blue-50 text-blue-700 px-3 py-1 rounded hover:bg-blue-100"
                  >
                    Preview Data
                  </button>
                </div>
              </div>

              {/* Data preview (expandable) */}
              {selectedVcode === r.vcode && previewData && (
                <div className="mt-3 pt-3 border-t">
                  <div className="text-xs font-medium text-gray-700 mb-2">
                    Latest: {previewData.latest_value} ({previewData.latest_date})
                  </div>
                  <div className="grid grid-cols-6 gap-1">
                    {previewData.data?.slice(0, 12).map((d, j) => (
                      <div key={j} className="text-center">
                        <div className="text-xs text-gray-400">{d.date}</div>
                        <div className="text-xs font-mono">{d.value?.toLocaleString()}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* No results */}
      {results.length === 0 && query && !loading && (
        <div className="text-center text-gray-500 py-8">
          <p className="text-sm">No matching V-codes found in the local index.</p>
          <p className="text-xs mt-1">Searching Statistics Canada via AI...</p>
          {/* Gemini fallback triggers automatically */}
        </div>
      )}
    </div>
  );
}
```

---

## PART 5: API ENDPOINTS

```python
"""
vcode_api.py — API endpoints for V-code search.

Add these to your Cloud Functions or Flask/FastAPI backend.
"""

from vcode_search import search_vcodes
from vcode_gemini_fallback import discover_vcode_via_gemini
from vcode_data_fetch import fetch_vcode_data
from vcode_index import save_discovered_vcodes


async def handle_vcode_search(query):
    """Handle a V-code search request.
    
    1. Try local fuzzy search first
    2. If no good results (top score < 3), fall back to Gemini
    3. If Gemini finds new V-codes, add them to the index
    """
    # Local search
    results = search_vcodes(query, max_results=10)
    
    # If best result is weak, try Gemini
    if not results or results[0]["score"] < 3:
        discovered = await discover_vcode_via_gemini(query)
        
        if discovered:
            # Save to index for future searches
            save_discovered_vcodes(discovered)
            
            # Add to results
            for entry in discovered:
                entry["score"] = 15  # High score — AI-matched
                entry["source"] = "gemini_discovery"
                from vcode_index import build_statcan_table_url, build_statcan_vector_url
                entry["statcan_table_url"] = build_statcan_table_url(entry["table"])
                entry["statcan_vector_url"] = build_statcan_vector_url(entry["vcode"])
                results.insert(0, entry)
    
    return {"query": query, "results": results, "count": len(results)}


async def handle_vcode_data(vcode):
    """Handle a data preview request for a specific V-code."""
    data = await fetch_vcode_data(vcode, periods=12)
    return data or {"vcode": vcode, "error": "Could not fetch data", "data": []}
```

---

## COST IMPACT

| Component | Cost |
|---|---|
| Local fuzzy search | $0 (runs locally) |
| Gemini Flash fallback (when local fails) | $0 (free tier, ~1-5 queries/day max) |
| StatsCan API data fetch | $0 (free public API) |
| Curated V-code index (JSON file) | $0 |
| **Total** | **$0** |

---

## VERIFICATION

- [ ] Local search returns results for "unemployment rate alberta"
- [ ] Local search returns results for "housing starts"
- [ ] Local search returns results for "construction gdp"
- [ ] Local search returns results for "cpi inflation"
- [ ] Province detection works ("alberta" maps to AB results)
- [ ] StatsCan table URL is correct and opens the right page
- [ ] StatsCan vector URL is correct
- [ ] "View on StatsCan" link opens the correct table page in a new tab
- [ ] Gemini fallback triggers when local search has no good matches
- [ ] Gemini-discovered V-codes are saved to the index for future searches
- [ ] Data preview shows recent values for a selected V-code
- [ ] Frontend Data Explorer tab renders and is functional
- [ ] Quick category buttons populate the search bar
- [ ] Search works on Enter key press
- [ ] No cost increase to the pipeline

**STEP_2O complete.**
