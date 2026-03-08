> **CLAUDE CODE SETUP — RUN THESE BEFORE STARTING:**
> 1. Type `/clear` to wipe conversation history from any previous step
> 2. Launch with `claude --dangerously-skip-permissions` to auto-approve all file edits and bash commands
> 3. Enter Plan Mode (Shift+Tab twice) and paste this file — review the plan before executing
> 4. If context gets heavy mid-step, run `/compact` to summarize and free space

# STEP_2Q — SEARCH LAYER REPLACEMENT & FRONTEND FIX

**Prerequisites:** Backup at v2.0-stable. Gemini API key disabled/deleted. New Anthropic key set.
**This step replaces Gemini grounded search ($136/day!) with free Google News RSS + Tavily free tier, removes Gemini Pro entirely, and fixes the frontend project display bugs.**

---

## CONTEXT: WHY THIS STEP EXISTS

Gemini grounded search was costing $35 per 1,000 queries via Google Search grounding fees. At 500 queries/day, that's $17.50/day — not $0/year as estimated. The Gemini API key has been disabled and deleted. This step rebuilds the search layer using entirely free sources.

**New model stack (final):**

| Model | Role | Cost |
|---|---|---|
| Gemini Flash (NO grounding) | Classification, extraction, RSS processing | $0 |
| Claude Sonnet | ALL reasoning — briefing, commentary, microscope, gap analysis, dedup QA, extraction recovery, signal investigation, meta-analysis | ~$55/yr |
| Tavily | Targeted enrichment searches (1,000/month free) | $0 |

**Gemini Pro is removed entirely.** All its tasks move to Claude Sonnet. This eliminates Google billing risk and simplifies the model stack to one paid API (Anthropic).

---

## PART 1: GOOGLE NEWS RSS AS PRIMARY SEARCH

### Step 1: Convert compound queries to Google News RSS URLs

Every compound query becomes a Google News RSS feed URL. The existing `compound_queries_final.json` (759 queries) is reused — we just change how they're executed.

```python
"""
google_news_rss_search.py — Replaces Gemini grounded search with
Google News RSS feed polling.

Each compound query is converted to a Google News RSS URL.
feedparser reads the feed and returns articles.
Articles flow through the existing 6-layer RSS filter and
Gemini Flash classification (without grounding).

Cost: $0. Google News RSS is free and unlimited.
"""

import asyncio
import aiohttp
import feedparser
import json
import logging
import re
import urllib.parse
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"


def build_google_news_url(query_text, language="en"):
    """Convert a search query to a Google News RSS URL.
    
    Args:
        query_text: The search query string
        language: "en" for English, "fr" for French
    
    Returns:
        Google News RSS URL string
    """
    params = {
        "q": query_text,
        "hl": "fr-CA" if language == "fr" else "en-CA",
        "gl": "CA",
        "ceid": "CA:fr" if language == "fr" else "CA:en",
    }
    return f"{GOOGLE_NEWS_RSS_BASE}?{urllib.parse.urlencode(params)}"


def load_compound_queries(json_path="compound_queries_final.json"):
    """Load the 759 compound queries from the existing JSON file."""
    with open(json_path, "r") as f:
        queries = json.load(f)
    return queries


def convert_queries_to_rss_urls(queries):
    """Convert all compound queries to Google News RSS URLs.
    
    Returns list of dicts with original query metadata + RSS URL.
    """
    rss_feeds = []
    for q in queries:
        query_text = q.get("query", "")
        language = q.get("language", "en")
        
        # Shorten query for RSS — Google News RSS works best with
        # concise queries (5-15 words), not the long natural language
        # prompts used for Gemini grounded search.
        short_query = _shorten_query(query_text, q)
        
        url = build_google_news_url(short_query, language)
        
        rss_feeds.append({
            "url": url,
            "short_query": short_query,
            "original_query": query_text,
            "province": q.get("province"),
            "sector": q.get("sector"),
            "language": language,
            "geo_tier": q.get("geo_tier"),
            "type": "google_news_rss",
        })
    
    return rss_feeds


def _shorten_query(query_text, query_meta):
    """Shorten a compound query to work well with Google News RSS.
    
    Gemini queries were verbose natural language:
      "Find all major mining projects in Saskatchewan that are currently
       proposed, approved, or under construction..."
    
    Google News RSS needs concise keywords:
      "major mining projects Saskatchewan 2026"
    
    Strategy: extract province/CMA + sector + key terms.
    """
    province = query_meta.get("province", "")
    sector = query_meta.get("sector", "")
    language = query_meta.get("language", "en")
    geo_tier = query_meta.get("geo_tier", "")
    
    # Sector keyword mapping
    SECTOR_KEYWORDS = {
        "oil_gas": "oil gas LNG pipeline",
        "mining": "mining mine mineral",
        "infrastructure": "infrastructure transit highway bridge",
        "power_energy": "power energy solar wind hydro nuclear",
        "manufacturing": "manufacturing factory plant",
        "transport_logistics": "port airport rail terminal",
        "healthcare": "hospital healthcare medical centre",
        "education": "university school campus college",
        "residential": "housing residential condo tower",
        "commercial_mixed": "development mixed-use redevelopment commercial",
        "agriculture": "agriculture greenhouse food processing",
        "forestry": "forestry sawmill pulp mill lumber",
        "defence": "military defence naval shipyard",
        "telecom": "data centre broadband fibre 5G",
        "indigenous": "Indigenous First Nations infrastructure",
        "environment": "remediation cleanup waste recycling",
        "tourism_culture": "museum arena recreation cultural centre",
        "government": "government building courthouse civic",
    }
    
    sector_kw = SECTOR_KEYWORDS.get(sector, sector.replace("_", " "))
    
    # Province name mapping
    PROV_NAMES = {
        "ON": "Ontario", "QC": "Québec", "AB": "Alberta", "BC": "British Columbia",
        "SK": "Saskatchewan", "MB": "Manitoba", "NS": "Nova Scotia",
        "NB": "New Brunswick", "NL": "Newfoundland", "PE": "PEI",
        "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
    }
    
    geo_name = PROV_NAMES.get(province, province)
    
    # CMA queries use the CMA name directly
    if geo_tier == "cma":
        cma = query_meta.get("cma", geo_name)
        geo_name = cma
    
    # Build concise query
    year = datetime.now().year
    
    if language == "fr":
        return f"projet {sector_kw} {geo_name} {year}"
    else:
        return f"{sector_kw} project {geo_name} {year}"


async def fetch_rss_feed(session, feed, semaphore):
    """Fetch a single Google News RSS feed.
    
    Returns list of article dicts.
    """
    async with semaphore:
        try:
            async with session.get(feed["url"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    parsed = feedparser.parse(text)
                    
                    articles = []
                    for entry in parsed.entries[:15]:  # Max 15 per feed
                        articles.append({
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "source": entry.get("source", {}).get("title", ""),
                            "snippet": entry.get("summary", ""),
                            # Attach query metadata for downstream processing
                            "_province": feed.get("province"),
                            "_sector": feed.get("sector"),
                            "_language": feed.get("language"),
                            "_discovery_tier": "google_news_rss",
                            "_query": feed.get("short_query"),
                        })
                    
                    return articles
                else:
                    logger.warning(f"RSS fetch {resp.status}: {feed['short_query']}")
                    return []
        except Exception as e:
            logger.warning(f"RSS fetch error: {feed['short_query']}: {e}")
            return []


async def run_google_news_discovery(json_path="compound_queries_final.json"):
    """Run all 759 compound queries via Google News RSS.
    
    Returns list of article dicts ready for the 6-layer RSS filter
    and Gemini Flash extraction.
    """
    queries = load_compound_queries(json_path)
    rss_feeds = convert_queries_to_rss_urls(queries)
    
    logger.info(f"Google News RSS discovery: {len(rss_feeds)} feeds")
    
    semaphore = asyncio.Semaphore(30)  # 30 concurrent feeds
    all_articles = []
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_rss_feed(session, feed, semaphore) for feed in rss_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)
        elif isinstance(result, Exception):
            continue
    
    # Dedup by URL before processing
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        url = article.get("link", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
    
    logger.info(f"Google News RSS: {len(all_articles)} total → {len(unique_articles)} unique articles")
    
    return unique_articles
```

### Step 2: Process Google News results through existing pipeline

The articles from Google News RSS flow through the SAME pipeline as existing RSS feeds:
1. 6-layer filter (government bypass, dollar bypass, keyword co-occurrence, negative keywords, Gemini Flash classification)
2. Gemini Flash extraction (WITHOUT grounding — just processes the article text)
3. Dedup and Firestore write

```python
# In update_dashboard.py, replace the compound Gemini search tier with:

# ── Tier 2: Google News RSS search (replaces Gemini grounded search) ──
logger.info("Tier 2: Google News RSS search...")
from google_news_rss_search import run_google_news_discovery
news_articles = await run_google_news_discovery()

# Process through existing RSS filter pipeline
for article in news_articles:
    article["_discovery_tier"] = "google_news_rss"
filtered = await process_rss_articles(news_articles)  # existing filter
logger.info(f"  → {len(filtered)} articles passed filter")

# Extract projects from filtered articles using Gemini Flash (no grounding)
for article in filtered:
    projects = await extract_projects_from_article(article)  # existing extraction
    for p in projects:
        p["_discovery_tier"] = "google_news_rss"
    all_projects.extend(projects)
```

---

## PART 2: TAVILY FOR TARGETED SEARCHES

Tavily replaces Gemini grounded search for tasks that need web search (not just news): cost-finding, verification, enrichment, named tracking.

```python
"""
tavily_search.py — Tavily API integration for targeted web searches.

Budget: 1,000 credits/month free tier.
Basic search = 1 credit each.

Used ONLY for:
- Cost-finding for valueless projects (300/month)
- Named project tracking (200/month)
- Deep verification (200/month)
- Enrichment (150/month)
- Signal investigation (100/month)
- Buffer (50/month)
"""

import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(query, max_results=5, search_depth="basic"):
    """Execute a single Tavily search.
    
    Args:
        query: Search query string
        max_results: Number of results (1-10)
        search_depth: "basic" (1 credit) or "advanced" (2 credits)
    
    Returns:
        list of result dicts with title, url, content, score
    """
    if not TAVILY_API_KEY:
        logger.error("TAVILY_API_KEY not set")
        return []
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": False,
        "include_raw_content": False,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(TAVILY_SEARCH_URL, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                logger.info(f"Tavily: '{query[:50]}' → {len(results)} results")
                return results
            else:
                text = await resp.text()
                logger.error(f"Tavily error {resp.status}: {text[:200]}")
                return []


async def tavily_cost_search(project_name, province, city=None):
    """Search for a project's cost/budget/value.
    
    Optimized query for finding dollar figures.
    """
    location = f"{city} {province}" if city else province
    query = f"{project_name} {location} budget cost million billion investment"
    return await tavily_search(query, max_results=5, search_depth="basic")


async def tavily_status_search(project_name, province):
    """Search for a project's current status.
    
    Optimized for finding construction updates, approvals, delays.
    """
    query = f"{project_name} {province} construction update status 2026"
    return await tavily_search(query, max_results=3, search_depth="basic")


async def tavily_verify_project(project_name, province):
    """Search for second-source confirmation of a project.
    
    Used for deep verification of single-source projects.
    """
    query = f'"{project_name}" {province} project'
    return await tavily_search(query, max_results=5, search_depth="basic")
```

### Step 3: Update cost-finding to use Tavily

```python
# In cost_finding.py, replace Gemini grounded search calls with Tavily:

async def find_project_cost(project, db):
    """Find the cost/value for a project missing value_millions."""
    from tavily_search import tavily_cost_search
    
    results = await tavily_cost_search(
        project.get("name", ""),
        project.get("location", {}).get("province", ""),
        project.get("location", {}).get("city"),
    )
    
    # Extract dollar values from results
    for result in results:
        content = result.get("content", "")
        value = extract_dollar_value(content)
        if value:
            return {
                "value_millions": value,
                "source_url": result.get("url"),
                "source_title": result.get("title"),
            }
    
    return None
```

---

## PART 3: REMOVE GEMINI PRO

### Step 1: Delete Gemini Pro module

```python
# Delete or archive gemini_pro_reasoning.py
# Move its 5 tasks to Claude Sonnet
```

### Step 2: Move Pro tasks to Claude Sonnet

In `claude_reasoning.py`, add the 5 tasks that were handled by Gemini Pro:

```python
async def analyze_discovery_gaps(flash_results, discovery_stats):
    """Gap analysis — previously Gemini Pro task.
    
    Reviews what Flash/RSS found and identifies unusual absences.
    """
    system = """You are analyzing the output of a Canadian project discovery pipeline.
Review what was found this week and identify any suspicious gaps:
- Province-sector pairs that usually produce results but didn't this week
- Sectors with unusually low discovery counts
- Geographic areas with no new activity

Be specific. Only flag genuinely unusual absences, not normal variation."""
    
    return await reason_with_claude_tracked(system, str(discovery_stats), 
                                            task_name="gap_analysis", max_tokens=1000)


async def recover_failed_extractions(failed_articles):
    """Re-process articles that produced no projects — previously Gemini Pro.
    
    Takes articles that Gemini Flash failed to extract projects from
    and tries again with Claude Sonnet's stronger reasoning.
    """
    if not failed_articles:
        return []
    
    system = """You are extracting capital project information from news articles 
that a simpler model failed to parse. Look carefully for project names, values, 
locations, proponents, and status information. Return valid JSON."""
    
    return await reason_with_claude_tracked(system, str(failed_articles[:10]),
                                            task_name="extraction_recovery", max_tokens=2000)


async def investigate_signals(permit_anomalies, lobbyist_signals):
    """Investigate signals from permits and lobbyists — previously Gemini Pro."""
    system = """You are analyzing signals from building permit anomalies and 
lobbyist registrations. Determine which signals likely indicate undiscovered 
capital projects and generate specific follow-up search queries."""
    
    context = f"Permit anomalies:\n{permit_anomalies}\n\nLobbyist signals:\n{lobbyist_signals}"
    return await reason_with_claude_tracked(system, context,
                                            task_name="signal_investigation", max_tokens=1000)


async def verify_dedup_quality(recent_merges):
    """Check dedup merge quality — previously Gemini Pro."""
    system = """Review these recent project merges from our deduplication system.
Identify any merges that look incorrect (different projects merged together)
or missed merges (same project not merged). Be specific about which entries."""
    
    return await reason_with_claude_tracked(system, str(recent_merges[:20]),
                                            task_name="dedup_qa", max_tokens=1000)


async def monthly_meta_analysis(monthly_stats):
    """Monthly meta-analysis of pipeline performance — previously Gemini Pro."""
    system = """Analyze this month's pipeline statistics. Identify:
1. Trends in discovery volume by source
2. Sectors or provinces with declining coverage
3. Data quality trends (confidence scores, evidence counts)
4. Recommendations for pipeline improvements"""
    
    return await reason_with_claude_tracked(system, str(monthly_stats),
                                            task_name="meta_analysis", max_tokens=1500)
```

### Step 3: Remove all Gemini Pro references

```python
# In update_dashboard.py:
# - Remove import of gemini_pro_reasoning
# - Replace all gemini_pro_reasoning calls with claude_reasoning calls
# - Remove GEMINI_PRO_MODEL constant
# - Remove any Gemini Pro API key references

# In .env:
# - Ensure no GEMINI_PRO_MODEL or GEMINI_PRO_KEY exists
```

### Step 4: Update environment

Add Tavily key to `.env`:
```
TAVILY_API_KEY=your_tavily_key_here
```

Ensure Gemini key is ONLY used for Flash without grounding:
```
GEMINI_API_KEY=your_new_free_tier_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_SEARCH_ENABLED=false
```

**CRITICAL:** When re-enabling a Gemini key for Flash:
- Create a NEW key on a project with NO billing account
- Verify "Free tier" shows on https://aistudio.google.com/apikey
- Set `GEMINI_SEARCH_ENABLED=false` in .env
- The code must NEVER pass `tools: [{ google_search: {} }]` or `groundingConfig` to the API

---

## PART 4: FRONTEND FIX — PROJECTS NOT APPEARING

### Fix 1: Province Normalization

In `public/index.html`, add after the existing `PROVS` array (~line 494):

```javascript
const NAME_TO_CODE = {};
PROVS.forEach(p => { NAME_TO_CODE[p.name] = p.code; NAME_TO_CODE[p.code] = p.code; });
function normProvince(raw) {
    if (!raw) return '';
    return NAME_TO_CODE[raw.trim()] || raw.substring(0,2).toUpperCase();
}
```

Rewrite `PROV_THRESHOLDS` to use codes:

```javascript
const PROV_THRESHOLDS = {
    'ON':500e6,'QC':250e6,'AB':200e6,'BC':175e6,
    'SK':45e6,'MB':40e6,'NS':25e6,'NB':20e6,
    'NL':17e6,'PE':5e6,'YT':3e6,'NT':3e6,'NU':3e6
};
```

### Fix 2: Update meetsThreshold()

Change from "no value = fail" to "no value = pass (unconfirmed), below threshold = fail":

```javascript
function meetsThreshold(p) {
    const v = parseNumericValue(p.value);
    if (!v) return true;  // no parseable value → show as unconfirmed
    const t = PROV_THRESHOLDS[normProvince(p.province)] || 0;
    return v >= t;
}
```

### Fix 3: Province-Scoped Loading

Rewrite `loadProjects(province)` (~line 583):

```javascript
let _lastLoadedProvince = null;
let _loadSeq = 0;

async function loadProjects(province) {
    const seq = ++_loadSeq;
    _lastLoadedProvince = province;
    
    let query = db.collection('projects');
    
    if (province && province !== 'all') {
        // Load all projects for this province (both code and full name)
        const snap1 = await query.where('location.province', '==', province).get();
        const snap2 = await query.where('location.province', '==', 
            PROVS.find(p => p.code === province)?.name || province).get();
        
        if (seq !== _loadSeq) return; // race guard
        
        const seen = new Set();
        const docs = [];
        snap1.forEach(d => { if (!seen.has(d.id)) { seen.add(d.id); docs.push(d); }});
        snap2.forEach(d => { if (!seen.has(d.id)) { seen.add(d.id); docs.push(d); }});
        
        _allProjects = docs.map(d => ({ id: d.id, ...d.data() }));
    } else {
        // All provinces — load most recent 5000
        const snap = await query.orderBy('lastSeen', 'desc').limit(5000).get();
        if (seq !== _loadSeq) return;
        _allProjects = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    }
    
    filterProjects();
}
```

### Fix 4: Wire Province Filter to Reload

Make `filterProjects()` trigger a reload when province changes (~line 1249):

```javascript
async function filterProjects() {
    const prov = document.getElementById('provinceFilter')?.value || 'all';
    
    // If province changed, reload from Firestore
    if (prov !== _lastLoadedProvince) {
        await loadProjects(prov);
        return; // loadProjects calls filterProjects again
    }
    
    // Apply client-side filters
    let filtered = _allProjects.filter(p => {
        if (!meetsThreshold(p)) return false;
        // ... existing search, sector, status, type filters ...
        // Use normProvince for province matching
        if (prov !== 'all' && normProvince(p.province) !== prov) return false;
        return true;
    });
    
    renderProjectTable(filtered);
}
```

### Fix 5: Province Column Simplification

In `renderProjectTable()`, replace `PROVS.find()` lookup with:

```javascript
const provCode = normProvince(p.province);
```

### Fix 6: Add "showing X of Y" indicator

Add a note when viewing "All" provinces:

```javascript
const countNote = _lastLoadedProvince === 'all' 
    ? `Showing ${filtered.length} of ${_allProjects.length} most recent projects. Select a province for complete results.`
    : `Showing ${filtered.length} of ${_allProjects.length} ${_lastLoadedProvince} projects.`;
document.getElementById('projectCount').textContent = countNote;
```

---

## PART 5: DEDUP AUDIT

With 32,201 projects, duplicates are likely. Run after the frontend fix:

```python
"""
dedup_audit.py — One-time audit to find and merge duplicate projects.
"""

async def audit_duplicates(db):
    """Find projects that are likely duplicates.
    
    Check for:
    1. Exact name + province matches
    2. Similar names (fuzzy) + same province
    3. Same proponent + same city + similar value
    """
    from collections import defaultdict
    
    projects = []
    for doc in db.collection("projects").stream():
        data = doc.to_dict()
        data["_id"] = doc.id
        projects.append(data)
    
    # Group by normalized name + province
    groups = defaultdict(list)
    for p in projects:
        name = p.get("name", "").lower().strip()
        prov = p.get("location", {}).get("province", "").upper()[:2]
        key = f"{prov}:{name}"
        groups[key].append(p)
    
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    
    print(f"Total projects: {len(projects)}")
    print(f"Unique name+province keys: {len(groups)}")
    print(f"Duplicate groups: {len(duplicates)}")
    print(f"Projects in duplicate groups: {sum(len(v) for v in duplicates.values())}")
    
    # Merge duplicates — keep highest value, most evidence, most advanced status
    for key, dupes in duplicates.items():
        if len(dupes) > 1:
            # Sort by evidence count descending, then value descending
            dupes.sort(key=lambda x: (
                x.get("evidence_count", 0),
                x.get("value_millions") or 0,
            ), reverse=True)
            
            primary = dupes[0]
            for secondary in dupes[1:]:
                # Merge evidence arrays
                # Merge discovery sources
                # Keep highest value and most advanced status
                # Delete secondary document
                pass
    
    return duplicates
```

---

## PIPELINE INTEGRATION

Update `update_dashboard.py` orchestrator:

```python
# OLD (remove):
# from compound_discovery import run_compound_discovery
# from gemini_pro_reasoning import analyze_gaps, recover_extractions, ...

# NEW:
from google_news_rss_search import run_google_news_discovery
from tavily_search import tavily_cost_search, tavily_status_search, tavily_verify_project
from claude_reasoning import (
    analyze_discovery_gaps,
    recover_failed_extractions,
    investigate_signals,
    verify_dedup_quality,
    monthly_meta_analysis,
    reason_with_claude_tracked,
)

# Tier 2 becomes:
news_articles = await run_google_news_discovery()
# Process through existing filter + extraction pipeline

# Gemini Pro reasoning section becomes:
# (All calls now go to Claude Sonnet)
gaps = await analyze_discovery_gaps(flash_results, stats)
recovered = await recover_failed_extractions(failed_articles)
signals = await investigate_signals(permit_data, lobbyist_data)
dedup_check = await verify_dedup_quality(recent_merges)
```

---

## ENVIRONMENT VARIABLES (final state)

```env
# Anthropic — the only paid AI service
ANTHROPIC_API_KEY=sk-ant-...your-new-key...

# Gemini — FREE TIER ONLY, NO GROUNDING
GEMINI_API_KEY=...new-free-tier-key-no-billing...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_SEARCH_ENABLED=false

# Tavily — free tier (1,000 credits/month)
TAVILY_API_KEY=tvly-...your-key...

# Firebase
FIREBASE_PROJECT_ID=can-macro-dashboard
```

---

## COST IMPACT

| Component | Before | After |
|---|---|---|
| Gemini grounded search | **$136/day** (!) | $0 (Google News RSS) |
| Gemini Flash (no grounding) | $0 | $0 (unchanged) |
| Gemini Pro | ~$18/year | $0 (removed, tasks moved to Sonnet) |
| Claude Sonnet | ~$40/year | ~$55/year (absorbs Pro tasks) |
| Tavily | — | $0 (free tier) |
| Firebase | ~$5/year | ~$5/year |
| **Total** | **$49,640+/year** | **~$60/year** |

---

## VERIFICATION

### Search layer
- [ ] Google News RSS URLs are generated for all 759 compound queries
- [ ] RSS feeds return articles (test with "mining Saskatchewan 2026")
- [ ] French queries return French articles (test with "projet infrastructure Québec 2026")
- [ ] Articles flow through existing 6-layer filter
- [ ] Gemini Flash processes articles WITHOUT grounding (no `google_search` tool passed)
- [ ] No Gemini grounding fees appear in Google Cloud billing

### Tavily
- [ ] Tavily API key is set and working
- [ ] `tavily_cost_search()` returns results for a known project
- [ ] `tavily_verify_project()` returns results
- [ ] Monthly usage stays within 1,000 credits

### Gemini Pro removal
- [ ] No imports of `gemini_pro_reasoning` anywhere in active code
- [ ] No `GEMINI_PRO_MODEL` in .env or code
- [ ] Gap analysis runs via Claude Sonnet
- [ ] Failed extraction recovery runs via Claude Sonnet
- [ ] Signal investigation runs via Claude Sonnet
- [ ] Dedup QA runs via Claude Sonnet
- [ ] Monthly meta-analysis runs via Claude Sonnet

### Frontend
- [ ] Province normalization handles both "MB" and "Manitoba"
- [ ] Portage Place appears when filtering to Manitoba
- [ ] Projects below threshold with known value are excluded
- [ ] Projects with no value ("Not disclosed", null) appear as unconfirmed
- [ ] Province filter triggers Firestore reload
- [ ] "All" view shows 5,000 most recent with count indicator
- [ ] Evidence URLs still display correctly on project cards
- [ ] Missing project submission form still works

### Safety
- [ ] Gemini API key is on free tier with NO billing account
- [ ] `GEMINI_SEARCH_ENABLED=false` in .env
- [ ] Code NEVER passes grounding config to Gemini API
- [ ] Anthropic spending cap is set ($5-10/month)
- [ ] Tavily is on free tier (1,000 credits/month)
- [ ] Google Cloud budget alert set at $1/day

**STEP_2Q complete.**
