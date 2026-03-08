> **CLAUDE CODE SETUP — RUN THESE BEFORE STARTING:**
> 1. Type `/clear` to wipe conversation history from any previous step
> 2. Launch with `claude --dangerously-skip-permissions` to auto-approve all file edits and bash commands
> 3. Enter Plan Mode (Shift+Tab twice) and paste this file — review the plan before executing
> 4. If context gets heavy mid-step, run `/compact` to summarize and free space

# STEP_2N — PROVINCIAL POLICY MONITOR, ENHANCED MARKETS, EVENT CALENDAR & NARRATIVE SYNTHESIS

**Prerequisites:** STEP_2M (Historical Backfill & Trend Analysis) should be complete.
**This step upgrades four newsletter dimensions using Claude Sonnet 4.5 as the reasoning engine.**
**Complements STEP_2K (Gemini Pro reasoning layer). Pro handles structured analytical tasks; Sonnet handles narrative intelligence. Both stay in the pipeline.**

---

## REASONING ENGINE: CLAUDE SONNET 4.5

All higher-order analysis in the pipeline now uses Claude Sonnet via the Anthropic API. Gemini Flash still handles all web searching (free tier). Claude Sonnet handles all thinking — trend narratives, cross-reference insights, policy implications, pre-event analysis, and the weekly briefing synthesis.

```python
"""
claude_reasoning.py — Claude Sonnet 4.5 reasoning engine.

Used for all analysis that requires genuine intelligence:
- Interpreting trends and connecting patterns
- Generating narrative briefings
- Pre-event analysis with historical context
- Policy implication assessment
- Cross-reference insight generation

Gemini Flash: searches the web (free)
Claude Sonnet: thinks about what Flash found (~$15-30/year)
"""

import os
import json
import logging
import aiohttp

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_ENDPOINT = "https://api.anthropic.com/v1/messages"


async def reason_with_claude(system_prompt, user_prompt, max_tokens=4096):
    """Send a reasoning request to Claude Sonnet.
    
    No web search, no tools — pure analysis of provided context.
    
    Args:
        system_prompt: Role and instructions
        user_prompt: Data and specific question
        max_tokens: Response length limit
    
    Returns:
        str: Claude's analysis text
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(CLAUDE_ENDPOINT, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["content"][0]["text"]
            else:
                text = await resp.text()
                logger.error(f"Claude API error {resp.status}: {text[:300]}")
                return None


# Token cost tracking
async def reason_with_claude_tracked(system_prompt, user_prompt, task_name, max_tokens=4096):
    """Same as reason_with_claude but tracks token usage for cost monitoring."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(CLAUDE_ENDPOINT, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                
                # Cost: Sonnet = $3/M input + $15/M output
                cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
                
                logger.info(
                    f"Claude [{task_name}]: {input_tokens} in / {output_tokens} out "
                    f"= ${cost:.4f}"
                )
                
                return {
                    "text": data["content"][0]["text"],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                }
            else:
                text = await resp.text()
                logger.error(f"Claude API error {resp.status}: {text[:300]}")
                return None
```

---

## PART 1: PROVINCIAL POLICY MONITOR

Track policy changes across all 13 provinces and the federal government that affect capital investment.

### 1A: Policy RSS feeds and sources

```python
"""
provincial_policy_monitor.py — Track provincial and federal policy changes
affecting capital investment.

Sources:
- Provincial legislature Hansard / proceedings RSS
- Provincial finance ministry news releases
- Federal Parliament news (budget, economic statements)
- Regulatory body announcements (CER, provincial energy boards, etc.)
- Provincial Gazette notices (regulatory changes)

Processes through a policy-specific Gemini Flash classification prompt,
then Claude Sonnet assesses economic implications.
"""

POLICY_FEEDS = {
    # Federal
    "federal_finance": {
        "name": "Department of Finance Canada",
        "url": "https://www.canada.ca/en/department-finance.atom.xml",
        "scope": "federal",
    },
    "federal_parliament": {
        "name": "Parliament of Canada News",
        "url": "https://www.parl.ca/rss/en/news",
        "scope": "federal",
    },
    "federal_budget": {
        "name": "Budget / Fall Economic Statement",
        "url": "https://budget.canada.ca/rss",
        "scope": "federal",
    },
    
    # Provincial finance / treasury (one per province)
    "on_finance": {
        "name": "Ontario Ministry of Finance",
        "url": "https://news.ontario.ca/en/newsroom/treasury-board-secretariat",
        "scope": "ON",
    },
    "qc_finance": {
        "name": "Ministère des Finances du Québec",
        "url": "https://www.quebec.ca/en/government/news/rss",
        "scope": "QC",
    },
    "ab_finance": {
        "name": "Alberta Treasury Board and Finance",
        "url": "https://www.alberta.ca/treasury-board-and-finance-news-rss",
        "scope": "AB",
    },
    "bc_finance": {
        "name": "BC Ministry of Finance",
        "url": "https://news.gov.bc.ca/ministries/finance/feed",
        "scope": "BC",
    },
    # ... add remaining provinces
    
    # Energy regulators
    "cer": {
        "name": "Canada Energy Regulator",
        "url": "https://www.cer-rec.gc.ca/en/about/news-room/rss.html",
        "scope": "federal",
        "topic": "energy_regulation",
    },
    "aer": {
        "name": "Alberta Energy Regulator",
        "url": "https://www.aer.ca/news/feed",
        "scope": "AB",
        "topic": "energy_regulation",
    },
    "bcuc": {
        "name": "BC Utilities Commission",
        "url": "https://www.bcuc.com/news/feed",
        "scope": "BC",
        "topic": "energy_regulation",
    },
}

# Policy categories that affect capital investment
POLICY_CATEGORIES = [
    "budget_capital_spending",       # Provincial/federal budget capital allocations
    "tax_incentive",                 # Investment tax credits, accelerated depreciation
    "regulatory_change",             # EA process changes, permitting reform
    "housing_policy",                # Housing accelerator, zoning reform, rent control
    "energy_policy",                 # Clean energy mandates, carbon pricing changes
    "mining_royalty",                # Royalty rate changes, exploration incentives
    "infrastructure_funding",        # Federal/provincial infrastructure program announcements
    "trade_policy",                  # Tariffs, trade agreements affecting investment
    "indigenous_policy",             # Duty to consult changes, reconciliation frameworks
    "environmental_regulation",      # Emissions standards, water quality, land use
    "immigration_workforce",         # Workforce programs affecting construction labour
    "procurement_policy",            # Buy Canadian, P3 framework changes
]
```

### 1B: Policy classification prompt (Gemini Flash)

```python
POLICY_CLASSIFICATION_PROMPT = """You are classifying government news releases and policy announcements 
for a Canadian economic intelligence tracker.

An article is POLICY_RELEVANT if it describes:
- Budget or fiscal update with capital spending allocations
- Tax incentives or credits affecting business investment
- Regulatory changes to environmental assessment, permitting, or approvals
- Housing policy changes (zoning reform, accelerator programs, rent policy)
- Energy policy (clean energy mandates, carbon pricing, electricity market rules)
- Mining or resource royalty changes
- Infrastructure funding program announcements or modifications
- Trade policy changes affecting construction materials or investment
- Indigenous consultation or reconciliation policy changes
- Environmental regulation changes affecting project development
- Immigration or workforce policy affecting construction labour
- Procurement policy (P3 frameworks, buy-Canadian requirements)

An article is NOT_RELEVANT if it is:
- General political news without policy specifics
- Personnel appointments
- Routine administrative notices
- Public health or social services (unless involving facility construction)

Classify as POLICY_RELEVANT or NOT_RELEVANT.
If POLICY_RELEVANT, also identify the category from:
budget_capital_spending, tax_incentive, regulatory_change, housing_policy,
energy_policy, mining_royalty, infrastructure_funding, trade_policy,
indigenous_policy, environmental_regulation, immigration_workforce, procurement_policy

Articles:
{articles}

Return JSON array:
[{{"index": 0, "classification": "POLICY_RELEVANT", "category": "housing_policy"}}, ...]"""
```

### 1C: Policy impact assessment (Claude Sonnet)

When a policy article is classified as relevant, Claude Sonnet assesses its economic implications and links it to affected projects.

```python
POLICY_ASSESSMENT_SYSTEM = """You are a factual reporter covering Canadian economic policy. 
Your job is to describe how government policy changes connect to capital investment 
and construction activity across Canada. Report facts, not opinions.

You have access to the dashboard's project database. When assessing a policy 
change, identify:
1. Which sectors are directly affected
2. Which provinces are affected
3. Whether the policy accelerates or decelerates investment
4. Specific projects in the database that would be impacted
5. The likely magnitude of impact (high/medium/low)
6. The timeline of impact (immediate, 3-6 months, 1-2 years)

Be specific and grounded. Cite the policy mechanism (e.g., "the 30% ITC 
reduces the effective cost of clean energy projects, making marginal projects 
viable at current power prices"). Do not speculate beyond what the policy 
text supports."""


async def assess_policy_impact(policy_article, affected_projects, indicator_context):
    """Use Claude Sonnet to assess a policy change's impact on capital investment."""
    
    user_prompt = f"""POLICY ANNOUNCEMENT:
{policy_article['headline']}
{policy_article['snippet']}
Source: {policy_article.get('url', 'unknown')}
Province/scope: {policy_article.get('scope', 'unknown')}
Category: {policy_article.get('category', 'unknown')}

POTENTIALLY AFFECTED PROJECTS IN OUR DATABASE:
{json.dumps([{
    'name': p.get('name'),
    'province': p.get('location', {}).get('province'),
    'sector': p.get('sector'),
    'value_millions': p.get('value_millions'),
    'status': p.get('status'),
} for p in affected_projects[:20]], indent=2)}

CURRENT ECONOMIC CONTEXT:
{json.dumps(indicator_context, indent=2)}

Assess the economic impact of this policy change on capital investment in Canada.
Structure your response as:
1. SUMMARY (2-3 sentences)
2. AFFECTED SECTORS AND MECHANISM
3. SPECIFIC PROJECTS IMPACTED (from the list above)
4. MAGNITUDE AND TIMELINE
5. RISKS OR UNCERTAINTIES"""

    result = await reason_with_claude_tracked(
        POLICY_ASSESSMENT_SYSTEM,
        user_prompt,
        task_name="policy_assessment",
        max_tokens=2000,
    )
    
    return result
```

---

## PART 2: ENHANCED MARKETS & COMMODITIES

Add Canadian-specific commodity benchmarks and connect price movements to the project database.

### 2A: Canadian-specific market indicators

```python
"""
canadian_markets.py — Canadian-specific commodity and market indicators
beyond standard Yahoo Finance tickers.
"""

CANADIAN_COMMODITY_INDICATORS = {
    # Oil — Canadian-specific
    "wcs_discount": {
        "description": "Western Canadian Select discount to WTI",
        "relevance": "Determines Alberta oil sands project profitability. A wide discount (>$15) makes heavy oil projects uneconomic. Narrow discount (<$10) signals strong pipeline capacity.",
        "affected_sectors": ["oil_gas"],
        "affected_provinces": ["AB", "SK"],
        "source": "yahoo_finance",  # Can proxy via WCS ticker or calculate WTI - WCS
        "ticker": "WCS-WTI spread",
        "threshold_note": "Alert when spread widens beyond $15 or narrows below $8",
    },
    "aeco_gas": {
        "description": "AECO natural gas hub price (Alberta)",
        "relevance": "Western Canada gas benchmark. Discount to Henry Hub reflects pipeline constraints. Directly affects BC LNG project economics.",
        "affected_sectors": ["oil_gas", "power_energy"],
        "affected_provinces": ["AB", "BC"],
        "source": "manual_or_api",
        "threshold_note": "Alert when AECO-HH spread exceeds $1.50",
    },
    
    # Mining — critical minerals
    "lithium_carbonate": {
        "description": "Lithium carbonate spot price",
        "relevance": "Drives EV battery plant and lithium mine economics in ON and QC.",
        "affected_sectors": ["mining", "manufacturing"],
        "affected_provinces": ["ON", "QC", "AB", "MB"],
        "source": "yahoo_finance_or_manual",
        "ticker": "LTHM",  # proxy via lithium ETF/miner
    },
    "uranium_spot": {
        "description": "Uranium spot price (U3O8)",
        "relevance": "Determines Saskatchewan uranium mine expansion viability and SMR project economics nationally.",
        "affected_sectors": ["mining", "power_energy"],
        "affected_provinces": ["SK", "ON", "NB"],
        "source": "yahoo_finance",
        "ticker": "URA",  # proxy via uranium ETF
    },
    "nickel": {
        "description": "Nickel spot price",
        "relevance": "Affects Ontario and Quebec nickel mine projects and EV battery supply chain.",
        "affected_sectors": ["mining"],
        "affected_provinces": ["ON", "QC", "NL", "MB"],
        "source": "yahoo_finance",
        "ticker": "^NIKL",
    },
    "potash": {
        "description": "Potash price (MOP granular)",
        "relevance": "Directly determines BHP Jansen and other Saskatchewan potash project economics.",
        "affected_sectors": ["mining"],
        "affected_provinces": ["SK", "NB"],
        "source": "manual_or_api",
    },
    
    # Construction inputs
    "steel_rebar": {
        "description": "Steel rebar price index",
        "relevance": "Major input cost for infrastructure and building construction. Rising prices signal cost pressure on all projects.",
        "affected_sectors": ["infrastructure", "residential", "commercial_mixed"],
        "source": "yahoo_finance",
        "ticker": "SLX",  # steel ETF proxy
    },
    "cement": {
        "description": "Cement/concrete price indicator",
        "relevance": "Critical construction input. Price increases directly affect project viability.",
        "affected_sectors": ["infrastructure", "residential", "commercial_mixed"],
        "source": "statcan",
        "table": "18-10-0268-01",  # Industrial product price index
    },
    
    # Real estate & housing
    "cmhc_housing_starts": {
        "description": "CMHC housing starts (seasonally adjusted annual rate)",
        "relevance": "Leading indicator of residential construction activity.",
        "affected_sectors": ["residential"],
        "source": "cmhc_api",
    },
    "teranet_hpi": {
        "description": "Teranet-National Bank House Price Index",
        "relevance": "Housing price trends affect residential project economics and land values.",
        "affected_sectors": ["residential", "commercial_mixed"],
        "source": "manual_or_api",
    },
    
    # Capital markets
    "tsx_infrastructure": {
        "description": "S&P/TSX Infrastructure Index (custom basket)",
        "relevance": "Market valuation of Canadian infrastructure companies signals investment appetite.",
        "source": "yahoo_finance",
        "tickers": ["BIP-UN.TO", "AQN.TO", "BEPC.TO", "TRP.TO", "ENB.TO"],
    },
    "baa_spread": {
        "description": "Corporate credit spread (proxy for project financing conditions)",
        "relevance": "Wider spreads make project financing more expensive, potentially delaying marginal projects.",
        "source": "yahoo_finance",
        "ticker": "^BAML",
    },
}
```

### 2B: Market commentary generation (Claude Sonnet)

```python
MARKET_COMMENTARY_SYSTEM = """You are a factual reporter covering Canadian commodity 
and market data as it connects to capital projects and construction activity.

Report price changes and state which tracked projects they connect to:
- Oil prices → Alberta/Saskatchewan energy sector projects in the database
- Commodity prices → mining projects by province
- Interest rates → residential and commercial projects with rate sensitivity
- Construction input costs → projects with reported budget pressure
- Exchange rates → projects with significant import components

Be specific about thresholds: "WTI closed at $72, above the $65 breakeven 
reported for most oil sands operations" not "oil prices remain elevated."
Reference specific projects from the database by name and value.
Do not predict outcomes or characterize movements as positive/negative."""


async def generate_market_commentary(market_data, project_data, policy_context):
    """Generate weekly market commentary connecting prices to projects."""
    
    user_prompt = f"""MARKET DATA (current vs 1 week / 1 month / 1 year ago):
{json.dumps(market_data, indent=2)}

ACTIVE PROJECT PIPELINE SUMMARY:
- Total projects: {project_data['total']}
- Energy sector: {project_data['by_sector'].get('oil_gas', {}).get('count', 0)} projects, ${project_data['by_sector'].get('oil_gas', {}).get('value_millions', 0):.0f}M
- Mining sector: {project_data['by_sector'].get('mining', {}).get('count', 0)} projects, ${project_data['by_sector'].get('mining', {}).get('value_millions', 0):.0f}M  
- Residential: {project_data['by_sector'].get('residential', {}).get('count', 0)} projects, ${project_data['by_sector'].get('residential', {}).get('value_millions', 0):.0f}M
- Infrastructure: {project_data['by_sector'].get('infrastructure', {}).get('count', 0)} projects, ${project_data['by_sector'].get('infrastructure', {}).get('value_millions', 0):.0f}M

RECENT POLICY CONTEXT:
{json.dumps(policy_context, indent=2) if policy_context else 'No significant policy changes this week.'}

Write a concise market commentary (200-300 words) for a Canadian economic 
intelligence briefing. Focus on what matters for capital investment decisions. 
Lead with the most significant market development this week."""

    result = await reason_with_claude_tracked(
        MARKET_COMMENTARY_SYSTEM,
        user_prompt,
        task_name="market_commentary",
        max_tokens=1500,
    )
    
    return result
```

---

## PART 3: ECONOMIC EVENT CALENDAR WITH PRE-EVENT ANALYSIS

### 3A: Event source compilation

```python
"""
event_calendar.py — Economic event calendar with forward-looking analysis.

Sources:
- Bank of Canada: rate decision dates (published annually)
- Statistics Canada: release calendar (published monthly)
- Federal budget / fall economic statement dates
- Provincial budget dates (announced weeks in advance)
- IAAC hearing and decision dates for major projects
- CER hearing dates
- CMHC quarterly report dates
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Bank of Canada fixed announcement dates (published annually)
# Update this list each January from https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/
BOC_RATE_DECISIONS_2026 = [
    "2026-01-29", "2026-03-12", "2026-04-16", "2026-06-04",
    "2026-07-09", "2026-09-17", "2026-10-22", "2026-12-10",
]

# StatsCan major releases (recurring monthly — dates shift slightly)
STATCAN_RECURRING = [
    {"name": "Labour Force Survey", "frequency": "monthly", "typical_day": "first_friday",
     "indicator": "employment", "relevance": "Employment and unemployment by province. Affects infrastructure spending pressure and construction labour availability."},
    {"name": "Consumer Price Index", "frequency": "monthly", "typical_day": "third_tuesday",
     "indicator": "cpi_total", "relevance": "Inflation reading. Directly influences BoC rate path and therefore project financing costs."},
    {"name": "GDP by Industry", "frequency": "monthly", "typical_day": "last_friday",
     "indicator": "gdp_monthly", "relevance": "Economic growth breakdown. Construction and mining sectors are directly reported."},
    {"name": "Building Permits", "frequency": "monthly", "typical_day": "around_8th",
     "indicator": "building_permits", "relevance": "6-12 month leading indicator of construction activity by province."},
    {"name": "Housing Starts", "frequency": "monthly", "typical_day": "around_15th",
     "indicator": "housing_starts", "relevance": "Current residential construction activity level."},
    {"name": "Investment in Building Construction", "frequency": "monthly",
     "indicator": "investment_nonresidential", "relevance": "Directly measures capital spending on non-residential construction."},
]

# Provincial budget season (typically Feb-April)
PROVINCIAL_BUDGETS_2026 = [
    # Update as dates are announced
    {"province": "ON", "expected": "March 2026", "confirmed_date": None},
    {"province": "QC", "expected": "March 2026", "confirmed_date": None},
    {"province": "AB", "expected": "February 2026", "confirmed_date": None},
    {"province": "BC", "expected": "February 2026", "confirmed_date": None},
    {"province": "federal", "expected": "April 2026", "confirmed_date": None},
    # ... other provinces
]


def get_upcoming_events(db, days_ahead=14):
    """Get economic events in the next N days.
    
    Returns list of event dicts with pre-analysis context.
    """
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=days_ahead)
    
    events = []
    
    # BoC rate decisions
    for date_str in BOC_RATE_DECISIONS_2026:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if today <= event_date <= cutoff:
            events.append({
                "date": date_str,
                "name": "Bank of Canada Rate Decision",
                "source": "Bank of Canada",
                "type": "rate_decision",
                "significance": "high",
                "indicators_affected": ["policy_rate", "mortgage_5y_fixed", "prime_rate"],
                "sectors_affected": ["residential", "commercial_mixed", "infrastructure"],
            })
    
    # StatsCan releases — check the release calendar
    # (In production, scrape https://www.statcan.gc.ca/en/release-calendar)
    for release in STATCAN_RECURRING:
        events.append({
            "name": release["name"],
            "source": "Statistics Canada",
            "type": "data_release",
            "frequency": release["frequency"],
            "significance": "medium",
            "indicator": release["indicator"],
            "relevance": release["relevance"],
        })
    
    # Provincial budgets
    for budget in PROVINCIAL_BUDGETS_2026:
        if budget.get("confirmed_date"):
            event_date = datetime.strptime(budget["confirmed_date"], "%Y-%m-%d").date()
            if today <= event_date <= cutoff:
                events.append({
                    "date": budget["confirmed_date"],
                    "name": f"{budget['province']} Provincial Budget",
                    "source": f"{budget['province']} Finance Ministry",
                    "type": "budget",
                    "significance": "high",
                    "province": budget["province"],
                })
    
    # IAAC decision dates for tracked projects
    # (Query Firestore for projects with upcoming regulatory milestones)
    
    events.sort(key=lambda x: x.get("date", "9999"))
    return events
```

### 3B: Pre-event analysis (Claude Sonnet)

```python
PRE_EVENT_SYSTEM = """You are a factual reporter preparing a data briefing 
ahead of a major Canadian economic event.

Your report must:
1. State what the event is and when it occurs
2. State current market pricing/consensus for the outcome (if available)
3. For each possible outcome, state which tracked projects and sectors it connects to — using conditional language ("if X, then Y projects would...")
4. Identify specific projects in the database that are in scope
5. State relevant historical data points for context
6. Be concise (150-250 words per event)

Do not predict which outcome is more likely. Do not characterize outcomes as 
good or bad. Do not recommend actions. Use the historical data provided to 
show factual context, not to argue for a position."""


async def generate_pre_event_analysis(event, indicator_history, project_data):
    """Generate forward-looking analysis for an upcoming economic event."""
    
    user_prompt = f"""UPCOMING EVENT:
{json.dumps(event, indent=2)}

HISTORICAL CONTEXT FOR THIS INDICATOR:
{json.dumps(indicator_history, indent=2)}

PROJECTS IN AFFECTED SECTORS:
{json.dumps([{
    'name': p.get('name'),
    'province': p.get('location', {}).get('province'),
    'sector': p.get('sector'),
    'value_millions': p.get('value_millions'),
    'status': p.get('status'),
} for p in project_data[:15]], indent=2)}

Generate a pre-event data briefing. State the event, the possible outcomes, 
which tracked projects connect to each outcome, and relevant historical data points."""

    result = await reason_with_claude_tracked(
        PRE_EVENT_SYSTEM,
        user_prompt,
        task_name=f"pre_event_{event.get('type', 'unknown')}",
        max_tokens=1500,
    )
    
    return result
```

---

## PART 4: WEEKLY NARRATIVE SYNTHESIS

The crown jewel — combines all dimensions into a single coherent weekly briefing.

### 4A: Narrative synthesis prompt (Claude Sonnet)

```python
WEEKLY_SYNTHESIS_SYSTEM = """You are a factual reporter producing a weekly Canadian 
economic data briefing. Your readers are senior decision-makers: government 
analysts, investment managers, infrastructure developers, and policy advisors.

CRITICAL RULE: Report facts. Do not editorialize. Never characterize events as 
good, bad, worrying, promising, welcome, or concerning. Never recommend actions. 
Never predict outcomes. State what happened, what the data shows, and what 
connects to what. Let readers draw their own conclusions.

Your briefing must be:
- Factual (state what happened, what changed, what the numbers show)
- Specific (cite project names, dollar values, provinces, percentages)
- Connected (show which indicators link to which projects — but do not predict causation)
- Balanced (cover all regions, not just Toronto/Vancouver)
- Concise (1000-1500 words total)
- Sourced (every claim traces to data in the provided context)
- Conditional for projections ("If rates hold at X, Y projects would..." not "Y projects will benefit")

Structure:
1. HEADLINE — single most important data point or development (1-2 sentences)
2. MACRO PULSE — national economic indicators and what changed this week (150-200 words)
3. UNDER THE MICROSCOPE — deep-dive on dominant story with Canadian data context (200-300 words)
4. PROVINCIAL SPOTLIGHT — one province with notable data this week (100-150 words)
5. SECTOR WATCH — sectors with accelerating or decelerating discovery rates (150-200 words)
6. PROJECT TRACKER — new projects discovered, status changes, completions (150-200 words)
7. MARKETS & COMMODITIES — price movements and which tracked projects they connect to (100-150 words)
8. LOOKING AHEAD — upcoming data releases and scheduled events (100-150 words)

Tone: Reuters wire service. Not opinion column, not consultant report, not editorial.
Do NOT use: "unfortunately," "hopefully," "worrying," "promising," "encouraging," 
"welcome step," "should," "must," "in conclusion," "it remains to be seen."
Every sentence must contain a specific fact, number, or data connection."""


async def generate_weekly_briefing(
    project_trends,
    indicator_trends, 
    cross_insights,
    policy_developments,
    market_commentary,
    upcoming_events,
    pre_event_analyses,
):
    """Generate the full weekly intelligence briefing.
    
    This is the single most important Claude Sonnet call of the week.
    Budget: ~100K input tokens, ~2K output tokens = ~$0.33 per briefing.
    Annual cost: ~$17 for this call alone.
    """
    
    user_prompt = f"""Generate this week's Canadian Macro Strategic Dashboard briefing.

=== PROJECT PIPELINE TRENDS ===
Total tracked: {project_trends['total_projects']} projects (${project_trends['total_value_billions']:.1f}B)
New this week: {project_trends['new_this_week']['count']} (${project_trends['new_this_week']['value_millions']:.0f}M)
Week-over-week: {project_trends['trends']['week']['direction']} ({project_trends['trends']['week']['count_change_pct']:+.0f}%)
Month-over-month: {project_trends['trends']['month']['direction']} ({project_trends['trends']['month']['count_change_pct']:+.0f}%)
Quarter-over-quarter: {project_trends['trends']['quarter']['direction']} ({project_trends['trends']['quarter']['count_change_pct']:+.0f}%)

Sector momentum (30-day):
{_format_list(project_trends.get('sector_momentum', [])[:10])}

Geographic shifts (90-day):
{_format_list(project_trends.get('geographic_shifts', [])[:8])}

Pipeline health:
{json.dumps(project_trends.get('pipeline_health', {}), indent=2)}

Greenfield/brownfield mix: {json.dumps(project_trends.get('by_type', {}), indent=2)}

=== ECONOMIC INDICATORS ===
{json.dumps(indicator_trends, indent=2)}

=== CROSS-REFERENCE INSIGHTS ===
{json.dumps(cross_insights, indent=2)}

=== POLICY DEVELOPMENTS THIS WEEK ===
{json.dumps(policy_developments, indent=2) if policy_developments else "No major policy developments this week."}

=== MARKET COMMENTARY ===
{market_commentary or "No significant market movements this week."}

=== UPCOMING EVENTS (next 14 days) ===
{json.dumps(upcoming_events, indent=2)}

=== PRE-EVENT ANALYSES ===
{json.dumps(pre_event_analyses, indent=2) if pre_event_analyses else "No high-significance events in the next 14 days."}

Generate the weekly briefing following the structure specified in your system instructions."""

    result = await reason_with_claude_tracked(
        WEEKLY_SYNTHESIS_SYSTEM,
        user_prompt,
        task_name="weekly_briefing",
        max_tokens=3000,
    )
    
    return result


def _format_list(items):
    lines = []
    for item in items:
        lines.append(f"  - {json.dumps(item)}")
    return "
".join(lines) if lines else "  (no data)"
```

### 4B: Briefing storage and distribution

```python
"""
briefing_store.py — Store and distribute weekly briefings.
"""


async def store_and_distribute_briefing(db, briefing_text, metadata):
    """Store briefing in Firestore and prepare for distribution."""
    
    doc = {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "week_number": datetime.utcnow().isocalendar()[1],
        "year": datetime.utcnow().year,
        "content": briefing_text,
        "metadata": metadata,  # token usage, cost, generation time
        "created_at": datetime.utcnow().isoformat(),
    }
    
    db.collection("weekly_briefings").add(doc)
    
    # Make available to frontend
    # The dashboard can display the latest briefing as the "Weekly Intelligence" tab
    db.collection("dashboard_state").document("latest_briefing").set({
        "content": briefing_text,
        "date": doc["date"],
        "week_number": doc["week_number"],
    })
    
    logger.info(f"Weekly briefing stored: week {doc['week_number']}, {len(briefing_text)} chars")
```

---

## PIPELINE INTEGRATION

```python
# In weekly pipeline orchestrator, as the FINAL step after all discovery,
# enrichment, intelligence, and trend analysis:

# ── Provincial policy monitoring ──
logger.info("Processing policy feeds...")
from provincial_policy_monitor import process_policy_feeds
policy_developments = await process_policy_feeds(db)

# If significant policies found, assess impact with Claude Sonnet
policy_assessments = []
for policy in policy_developments:
    if policy.get("significance") in ("high", "medium"):
        assessment = await assess_policy_impact(policy, affected_projects, indicator_context)
        policy_assessments.append(assessment)

# ── Market commentary ──
logger.info("Generating market commentary...")
from canadian_markets import generate_market_commentary
market_commentary = await generate_market_commentary(market_data, project_summary, policy_developments)

# ── Event calendar and pre-event analysis ──
logger.info("Building event calendar...")
from event_calendar import get_upcoming_events, generate_pre_event_analysis
upcoming = get_upcoming_events(db, days_ahead=14)
pre_event = []
for event in upcoming:
    if event.get("significance") == "high":
        analysis = await generate_pre_event_analysis(event, indicator_history, affected_projects)
        pre_event.append({"event": event, "analysis": analysis})

# ── Weekly narrative synthesis ──
logger.info("Generating weekly briefing...")
from claude_reasoning import generate_weekly_briefing
briefing = await generate_weekly_briefing(
    project_trends=project_trends,
    indicator_trends=indicator_trends,
    cross_insights=cross_insights,
    policy_developments=policy_assessments,
    market_commentary=market_commentary,
    upcoming_events=upcoming,
    pre_event_analyses=pre_event,
)

# ── Store and distribute ──
from briefing_store import store_and_distribute_briefing
await store_and_distribute_briefing(db, briefing["text"], {
    "total_cost_usd": briefing["cost_usd"],
    "input_tokens": briefing["input_tokens"],
    "output_tokens": briefing["output_tokens"],
})

logger.info(f"Weekly briefing complete: ${briefing['cost_usd']:.4f}")
```

---

## ANNUAL COST ESTIMATE

```
Claude Sonnet calls per week:
  Weekly briefing synthesis:        1 call  (~$0.33)
  Market commentary:                1 call  (~$0.10)
  Pre-event analyses (0-3/week):    ~1.5 avg (~$0.10)
  Policy impact assessments (0-5):  ~2 avg   (~$0.15)
  ─────────────────────────────────────────────────
  Weekly total:                     ~5.5 calls (~$0.68/week)
  Annual total:                     ~$35/year

  Gemini Pro (STEP_2K):             ~$18/year (complements Sonnet)

  Full annual total:
    Gemini Flash (500/day):         $0
    Gemini Pro (structured):        ~$18
    Claude Sonnet (narrative):      ~$35
    Firestore:                      ~$5
    ─────────────────────────────────
    Total:                          ~$58/year
```

---

## VERIFICATION

- [ ] Claude Sonnet API calls succeed and return quality analysis
- [ ] Token usage tracking reports accurate costs per call
- [ ] Provincial policy feeds are polled and classified
- [ ] Policy impact assessments correctly link policies to affected projects
- [ ] Canadian-specific commodity indicators are tracked (WCS, AECO, lithium, uranium, potash)
- [ ] Market commentary connects price movements to specific Canadian projects
- [ ] BoC rate decision dates are loaded for 2026
- [ ] StatsCan release calendar events are tracked
- [ ] Provincial budget dates are tracked
- [ ] Pre-event analyses generate for high-significance upcoming events
- [ ] Weekly narrative synthesis produces a coherent 800-1200 word briefing
- [ ] Briefing is stored in Firestore and available to frontend
- [ ] All Claude Sonnet calls stay within ~$35/year budget
- [ ] Briefing quality is noticeably better than a template-filled report

**STEP_2N complete.**

---

## FULL PIPELINE ANNUAL COST — FINAL STATE

| Component | Annual Cost |
|---|---|
| Gemini 2.5 Flash (500 queries/day, grounded search) | $0 |
| RSS feeds (~200), Google Alerts (~25) | $0 |
| Government registries, SEDAR+, CER, municipal APIs | $0 |
| StatsCan API, Bank of Canada Valet API | $0 |
| Yahoo Finance (yfinance) | $0 |
| Gemini 2.5 Pro (structured reasoning, ~5 calls/week) | ~$18 |
| Claude Sonnet 4.5 (narrative reasoning + briefing) | ~$35 |
| Firebase/Firestore (storage + functions) | ~$5 |
| **Total** | **~$58/year** |
