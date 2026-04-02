"""
writing_agents.py — Claude Code writing agents for all briefing sections.

Replaces the monolithic Call 1 (macro) and Call 2 (industries) with
individual focused agents, each receiving dedicated context. Combined
with province_agents.py (13 province agents), this converts the entire
writing pipeline from API calls to Claude Code subprocesses ($0 cost).

Agent groups:
  Group 1 — Macro (replaces Call 1):
    - executive_summary: 350-450 words, TL;DR of the week
    - national_analysis: 250-400 words, deep national macro dive
    - consumer_pulse: 120-200 words, consumer-facing themes from news
    - global_us, global_china, global_eu, global_uk: 250-350 words each
    - watchlist: 15-25 upcoming events
    - metrics + indicator_context + word_cloud: data extraction
  Group 2 — Industries (replaces Call 2):
    - industry_executive_summary: 120-200 words
    - 5 goods sectors + 15 services sectors: 150 words each
    - yield_curve + charts: data extraction

Execution: Claude Code subprocess (subscription) or API fallback.
Default: claude_code. Set WRITING_AGENT_MODE=api in .env for API mode.
"""

import json
import os
import shutil
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

AGENT_MODE = os.environ.get('WRITING_AGENT_MODE', 'claude_code')
CLAUDE_CODE_MODEL = os.environ.get('WRITING_AGENT_MODEL', 'opus')
MAX_WORKERS = int(os.environ.get('WRITING_AGENT_WORKERS', '2'))

# Resolve claude CLI path — npm installs to AppData/Roaming/npm which may not
# be on the PATH that Python's subprocess inherits on Windows.
_CLAUDE_CLI = shutil.which('claude')
if not _CLAUDE_CLI:
    _npm_dir = os.path.join(os.environ.get('APPDATA', ''), 'npm')
    _candidate = os.path.join(_npm_dir, 'claude.cmd')
    if os.path.isfile(_candidate):
        _CLAUDE_CLI = _candidate

# Strip ANTHROPIC_API_KEY from subprocess env so claude CLI uses the
# subscription instead of the API (which may have no credits).
_CLAUDE_ENV = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}

CITATION_RULES = (
    "CITATION RULES: Every factual claim must end with <sup>N</sup> matching "
    "a source in the sources array. N starts at 1 and increments. Use exact "
    "URLs from articles — never fabricate URLs."
)

EDITORIAL_RULES = (
    "EDITORIAL RULES: REPORT ONLY — no editorializing. State what happened, "
    "what the data shows, what is connected. Never say 'should', 'must', "
    "'hopefully', 'unfortunately', 'worrying', 'promising', 'encouraging'. "
    "Never recommend policy, investment, or business decisions. Use conditional "
    "language for projections. NEVER forecast or use 'looking ahead', 'expected "
    "to', 'is likely to', 'outlook', 'going forward'."
)


# ── Claude Code execution (shared with province_agents.py) ───────────────────

def _call_claude_code(prompt: str, label: str, max_turns: int = 1) -> dict | None:
    """Call Claude via Claude Code CLI with direct prompt. Returns parsed JSON dict or None."""
    prompt_file = None
    try:
        if not _CLAUDE_CLI:
            raise FileNotFoundError("claude CLI not resolved")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write(prompt)
            prompt_file = f.name
        prompt_arg = f'Read the file {prompt_file} and follow the instructions exactly. Output ONLY valid JSON.'
        cmd = [
            _CLAUDE_CLI, '-p', prompt_arg,
            '--model', CLAUDE_CODE_MODEL,
            '--output-format', 'json',
            '--max-turns', str(max(max_turns, 2)),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=420,
                                encoding='utf-8', errors='replace', env=_CLAUDE_ENV)
        if result.returncode != 0:
            print(f"    [{label}] Claude Code exit code {result.returncode}")
            return None
        output = result.stdout.strip()
        if not output:
            return None
        # Parse response
        try:
            outer = json.loads(output)
            text = outer.get('result', outer.get('text', output))
            if isinstance(text, dict):
                return text
            if isinstance(text, str):
                return _extract_json(text, label)
        except (json.JSONDecodeError, TypeError):
            pass
        return _extract_json(output, label)
    except subprocess.TimeoutExpired:
        print(f"    [{label}] Timed out after 420s")
        return None
    except FileNotFoundError:
        print(f"    [{label}] 'claude' CLI not found")
        return None
    except Exception as e:
        print(f"    [{label}] Error: {type(e).__name__}: {e}")
        return None
    finally:
        if prompt_file:
            try:
                os.unlink(prompt_file)
            except OSError:
                pass


def _extract_json(text: str, label: str) -> dict | None:
    """Extract JSON from response text."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        print(f"    [{label}] JSON parse failed ({len(text)} chars)")
        return None


def _run_agent(prompt: str, label: str, anthropic_client=None, cost_state=None,
               conn=None, gemini_client=None, model: str = '', max_tokens: int = 4000):
    """Run a single agent — Claude Code or API depending on mode."""
    if AGENT_MODE == 'claude_code':
        return _call_claude_code(prompt, label)
    else:
        from phases.analysis import _call_claude, SONNET_MODEL
        return _call_claude(prompt, label, max_tokens=max_tokens,
                            model=model or SONNET_MODEL,
                            anthropic_client=anthropic_client,
                            cost_state=cost_state, conn=conn,
                            gemini_client=gemini_client)


# ── Prompt builders ──────────────────────────────────────────────────────────

def _build_exec_summary_prompt(today_str, hard_summary, arts_text, signal_block,
                                officials_ctx, sentiment_ctx):
    return f"""Today: {today_str}

VERIFIED DATA (use exactly, never modify or reinterpret):
{hard_summary}

{officials_ctx}

RECENT NEWS AND PRESS RELEASES (cite by article number):
{arts_text}
{sentiment_ctx}

{signal_block}

{CITATION_RULES}
{EDITORIAL_RULES}

Write an EXECUTIVE SUMMARY (4-6 short paragraphs, 350-450 words).
Format as HTML paragraphs: <p>paragraph text</p>
This is a TL;DR — be concise and direct. Every sentence must carry a specific data point.
No throat-clearing ("This week saw...") — lead with the fact.
Each paragraph is 2-3 sentences max. Use <strong> on key figures. Use <sup>N</sup> citations.
Structure: Lead with week's biggest story. Second paragraph: next 2-3 data points.
Third: notable provincial developments with project names and values.
Fourth: federal/provincial policy actions. Fifth (optional): cross-cutting theme.
Draw from BOTH national indicators AND provincial data/projects.
NO forecasting, NO predictions. Every claim backed by <sup>N</sup>.

Also extract:
- headline: 8-12 word newspaper-style headline
- key_indicators: 5-7 most relevant this week (label, value, change, direction, period, source)
- metrics: fill from articles EXCEPT leave blank: cpi, shelterCpi, unemployment, participation, realGdp

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "headline": "8-12 word headline",
    "key_indicators": [{{"label": "SHORT LABEL", "value": "", "change": "", "direction": "up|down|hold", "period": "", "source": ""}}],
    "executive_summary": "<p>...</p>",
    "metrics": {{"realGdp": "", "nomGdp": "", "outputGap": "", "cpi": "", "shelterCpi": "", "bocRate": "", "unemployment": "", "participation": "", "wageGrowth": "", "currentAccount": "", "agCrop": "", "farmCash": "", "housingStarts": "", "employmentRate": "", "participationRate": ""}}
}}"""


def _build_national_prompt(today_str, hard_summary, arts_text, signal_block, officials_ctx):
    return f"""Today: {today_str}

VERIFIED DATA:
{hard_summary}

{officials_ctx}

RECENT NEWS (cite by article number):
{arts_text}

{signal_block}

AVAILABLE TIMESERIES KEYS (for insightChart — these are plottable 12-month series):
  National: wti, brent, natural_gas, gold, copper, aluminum, nickel, lumber, potash_nutrien, iron_ore, zinc, coal, wheat, corn, soybeans, silver, cad_usd, cadusd, boc_rate, goc_10y, yield_curve_10y2y, tsx_composite, sp500, nasdaq, djia, cpi, unemployment, housing_starts, nat_employment_rate, nat_participation_rate, lng_asia, hy_spread, ig_spread, dry_bulk_shipping, bitcoin, ethereum

{CITATION_RULES}
{EDITORIAL_RULES}

Write NATIONAL ANALYSIS (4-5 short paragraphs, 250-400 words total).
Format as HTML: <p>paragraph text</p>. Each paragraph 2-3 sentences max.
Open with the dominant data release. Following paragraphs: supporting data,
policy actions, notable counterpoints. Do NOT repeat the executive summary — add depth.
NEVER forecast. Every claim backed by <sup>N</sup>. No bullet points.

ALSO produce an insightChart — the single most important visualization for Canada this week.
Analyze the data, articles, and indicators above. Identify the dominant economic story and specify
a chart that tells it visually.
- "title": Narrative headline (e.g., "BoC Holds at 4.5% — Housing Starts Stall for Third Month")
- "subtitle": Data source label (e.g., "BoC Overnight Rate (%) — 12-month trend")
- "chartType": One of: "line", "dual_line" (two series, dual y-axis), "bar", "diverging_bar"
- "dataKeys": Array of 1-2 timeseries keys from the AVAILABLE TIMESERIES KEYS above.
  For dual_line, provide exactly 2 keys. For line, provide 1.
- "reasoning": 1 sentence — why this chart is the week's most important national visualization.
- "annotations": Optional array of {{"label": "Event", "date": "YYYY-MM-DD"}} to mark on chart.

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "national": {{
        "analysis": "<p>...</p>",
        "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://..."}}]
    }},
    "insightChart": {{
        "title": "Narrative headline connecting data to Canada's key story this week",
        "subtitle": "Indicator Name (unit) — 12-month trend",
        "chartType": "line",
        "dataKeys": ["boc_rate"],
        "reasoning": "Why this is the most important chart for Canada this week.",
        "annotations": [{{"label": "BoC decision", "date": "2026-03-15"}}]
    }}
}}"""


def _build_consumer_pulse_prompt(today_str, arts_text):
    return f"""Today: {today_str}

NEWS ARTICLES (cite by article number):
{arts_text}

{CITATION_RULES}
{EDITORIAL_RULES}

Write TWO sections:

1. CONSUMER PULSE (2-3 short paragraphs, 120-200 words):
Format as HTML: <p>paragraph text</p>
Derive ENTIRELY from the news articles — identify dominant consumer-facing themes
(cost of living, housing, employment, energy prices, trade/tariffs, grocery, rates, wages).
Lead with the single most-covered consumer story. Each paragraph 2-3 sentences max.
Use <sup>N</sup> footnote citations. Do NOT reference Reddit, Google Trends, or social media.

2. WORD CLOUD TOPICS: Extract 40-60 meaningful economic topics/phrases from the articles.
Each: 1-3 words, sentiment_score (-1.0 to +1.0), frequency (1-10 based on article coverage).
Prioritize specificity: "tariff retaliation" not "economy".

3. INDICATOR CONTEXT LINES: 1 sentence each, under 20 words, for: bocRate, cpi, unemployment, housingStarts, realGdp.

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "consumer_pulse": "<p>...</p>",
    "word_cloud_topics": [{{"topic": "term", "sentiment_score": 0.0, "frequency": 5}}],
    "indicatorContextLines": {{"bocRate": "", "cpi": "", "unemployment": "", "housingStarts": "", "realGdp": ""}}
}}"""


def _build_global_prompt(today_str, region, emoji, hard_summary, arts_text, officials_ctx):
    return f"""Today: {today_str}

VERIFIED DATA:
{hard_summary}

{officials_ctx}

RECENT NEWS (cite by article number):
{arts_text}

{CITATION_RULES}
{EDITORIAL_RULES}

Write GLOBAL ANALYSIS for **{region}** {emoji} (4-6 short paragraphs, 250-350 words).
Format as HTML: <p>paragraph text</p>. Each paragraph 2-3 sentences max.
Report GDP/employment, rate/inflation, trade data relevant to Canada.
State factual connections to Canada (e.g. "X% of Canadian exports go to...").
NEVER forecast. Every claim backed by <sup>N</sup>. No bullet points.
DO NOT discuss stock market movements.

Also extract indicators and their changes vs prior period.

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "region": "{region}",
    "emoji": "{emoji}",
    "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}},
    "indicatorMeta": {{"gdp": {{"change": "", "prev": ""}}, "cpi": {{"change": "", "prev": ""}}, "rate": {{"change": "", "prev": ""}}, "unemployment": {{"change": "", "prev": ""}}, "tradeBalance": {{"change": "", "prev": ""}}, "productivityGrowth": {{"change": "", "prev": ""}}}},
    "analysis": "<p>...</p>",
    "sources": [{{"id": 1, "title": "", "url": ""}}],
    "indicatorSources": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}}
}}"""


def _build_watchlist_prompt(today_str, arts_text, events_text):
    return f"""Today: {today_str}

NEWS ARTICLES:
{arts_text}

KNOWN UPCOMING EVENTS:
{events_text}

Generate a WATCHLIST of 15-25 upcoming economic events for Canada.
Include: BoC rate decisions, StatsCan releases (CPI, GDP, labour force, trade),
provincial budgets, federal budget, major conferences, regulatory deadlines.
For each, provide date, event name, institution, description, impact rating, and source URL.

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "watchlist": [
        {{
            "date": "Apr 1",
            "week_label": "This Week",
            "institution": "Statistics Canada",
            "event_name": "International Merchandise Trade",
            "description": "One sentence on what to watch.",
            "impact": "high",
            "source_url": "https://..."
        }}
    ]
}}"""


def _build_industry_summary_prompt(today_str, hard_summary, arts_text, signal_block):
    return f"""Today: {today_str}

VERIFIED DATA:
{hard_summary}

RECENT ARTICLES:
{arts_text}

{signal_block}

{CITATION_RULES}
{EDITORIAL_RULES}

Write INDUSTRY EXECUTIVE SUMMARY (2-3 short paragraphs, 120-200 words):
Format as HTML: <p>paragraph text</p>
Lead with the single biggest sectoral story and its key figure.
Second paragraph: next 2-3 notable sector movements.
Every sentence must carry a specific data point. <sup>N</sup> citations.
DO NOT discuss stock market movements.

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "industry_executive_summary": "<p>...</p>"
}}"""


def _build_sector_prompt(today_str, code, name, arts_text, signal_block, is_goods: bool):
    sector_type = "goods-producing" if is_goods else "services-producing"
    return f"""Today: {today_str}

You are writing the analysis for the {sector_type} sector: **{name}** (NAICS {code}).

RECENT ARTICLES RELEVANT TO THIS SECTOR (cite by article number):
{arts_text}

{signal_block}

{CITATION_RULES}
{EDITORIAL_RULES}

Write sector analysis as narrative prose (3-4 sentences, 150-200 words):
Format: <p><span class="lead-sentence">{{sector name}} — {{key fact with data}}</span> — {{supporting detail connecting indicator to project database impacts, with specific numbers}}<sup>N</sup></p>
Use em dash lead sentences: open each paragraph with the sector name, an em dash, and the most important data point, then flow into supporting detail.
Write 1-2 short paragraphs. NO bullet points, NO <ul>/<li> tags.
Each claim ends with <sup>N</sup>. Reference M/M and Y/Y GDP changes if available.
Include commodity prices, trade data, or policy actions relevant to this sector.
DO NOT discuss stock market movements.

BEFORE (wrong — bullets):
<ul class="list-disc list-inside space-y-2 text-slate-600 text-xs"><li>Mining & Energy GDP declined 1.2% month-over-month<sup>1</sup></li><li>WTI crude traded below $70/bbl for the third week<sup>2</sup></li></ul>

AFTER (correct — narrative prose with em dash lead):
<p><span class="lead-sentence">Mining & Energy — GDP contracted 1.2% month-over-month as WTI crude traded below $70/bbl for the third consecutive week</span>, affecting 12 Alberta oil sands projects ($18.2B) with breakeven costs above the current price.<sup>1,2</sup> Gold rose 1.8% to $3,042/oz, supporting 23 mining projects in BC and Ontario ($6.4B) linked to precious metal prices.<sup>3</sup></p>

Also provide: sources, subsectors (2-3 with code/name), isNegative (based on M/M).

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "code": "{code}",
    "name": "{name}",
    "mm": "",
    "yy": "",
    "analysis": "<p><span class=\\"lead-sentence\\">{{sector}} — {{key fact}}</span> — {{detail with data}}<sup>N</sup></p>",
    "industrySources": [{{"id": 1, "title": "", "url": ""}}],
    "isNegative": false,
    "subsectors": [{{"code": "", "name": "", "mm": ""}}],
    "indicatorSrc": "StatCan"
}}"""


def _build_yield_curve_prompt(today_str, hard_summary):
    return f"""Today: {today_str}

VERIFIED DATA:
{hard_summary}

Extract the Government of Canada yield curve and charts data.
Include terms: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 30Y. Highlight 2Y and 10Y only.
Also provide yieldCurveCurrent (array of float values) and yieldCurveLastYear (array or empty).

OUTPUT: Valid JSON only.
SCHEMA:
{{
    "yieldCurve": [{{"term": "2Y", "yield": "X.XX%", "highlight": true}}],
    "charts": {{"yieldCurveCurrent": [], "yieldCurveLastYear": []}}
}}"""


# ── Sector definitions ───────────────────────────────────────────────────────

GOODS_SECTORS = [
    ("11", "Agriculture"),
    ("21", "Mining & Energy"),
    ("22", "Utilities"),
    ("23", "Construction"),
    ("31-33", "Manufacturing"),
]

SERVICES_SECTORS = [
    ("41", "Wholesale Trade"),
    ("44-45", "Retail Trade"),
    ("48-49", "Transportation & Warehousing"),
    ("51", "Information & Culture"),
    ("52", "Finance & Insurance"),
    ("53", "Real Estate"),
    ("54", "Professional Services"),
    ("55", "Management"),
    ("56", "Admin & Waste Mgmt"),
    ("61", "Education"),
    ("62", "Health Care"),
    ("71", "Entertainment & Recreation"),
    ("72", "Accommodation & Food"),
    ("81", "Other Services"),
    ("91", "Public Administration"),
]

# Keywords for filtering articles to sectors
_SECTOR_KEYWORDS = {
    "11": ['agriculture', 'farm', 'crop', 'livestock', 'dairy', 'grain', 'wheat', 'canola'],
    "21": ['mining', 'oil', 'gas', 'energy', 'petroleum', 'crude', 'extraction', 'quarry'],
    "22": ['utilities', 'electricity', 'power', 'hydro', 'natural gas distribution', 'water system'],
    "23": ['construction', 'housing', 'building', 'residential', 'condo', 'infrastructure'],
    "31-33": ['manufacturing', 'factory', 'auto', 'vehicle', 'assembly', 'plant', 'production'],
    "41": ['wholesale', 'distribution', 'supply chain'],
    "44-45": ['retail', 'store', 'consumer', 'shopping', 'grocery', 'sales'],
    "48-49": ['transport', 'logistics', 'rail', 'shipping', 'freight', 'port', 'airline', 'trucking'],
    "51": ['telecom', 'media', 'broadcast', 'publishing', 'tech', 'software', 'data centre'],
    "52": ['bank', 'finance', 'insurance', 'credit', 'mortgage', 'lending'],
    "53": ['real estate', 'property', 'commercial real', 'office space', 'lease'],
    "54": ['professional services', 'consulting', 'engineering', 'legal', 'accounting', 'R&D'],
    "55": ['management', 'holding company', 'corporate'],
    "56": ['admin', 'waste', 'remediation', 'security services', 'staffing'],
    "61": ['education', 'university', 'college', 'school', 'training'],
    "62": ['health', 'hospital', 'medical', 'pharmaceutical', 'clinic', 'long-term care'],
    "71": ['entertainment', 'recreation', 'arts', 'culture', 'sport', 'museum', 'tourism'],
    "72": ['hotel', 'restaurant', 'accommodation', 'food service', 'hospitality'],
    "81": ['repair', 'personal services', 'laundry', 'religious'],
    "91": ['government', 'public admin', 'federal', 'provincial', 'municipal', 'defence', 'military'],
}


def _filter_articles_for_sector(articles: list[dict], code: str) -> list[dict]:
    """Filter articles relevant to a specific NAICS sector."""
    keywords = _SECTOR_KEYWORDS.get(code, [])
    if not keywords:
        return articles[:5]
    matched = []
    for a in articles:
        haystack = (a.get('title', '') + ' ' + a.get('text', '')[:600]).lower()
        if any(kw in haystack for kw in keywords):
            matched.append(a)
    return matched[:12]


def _format_articles_compact(articles: list[dict], max_chars: int = 6000) -> str:
    """Format articles compactly for a focused agent prompt."""
    if not articles:
        return "(no relevant articles available)"
    lines = []
    total = 0
    for i, a in enumerate(articles, 1):
        url = a.get('url', '')
        title = a.get('title', '')
        text = a.get('text', '')[:1000]
        src_type = 'government' if any(d in url for d in ('.gc.ca', 'canada.ca', '.gov.')) else 'news'
        chunk = f"ARTICLE [{i}]: [{src_type}] \"{title}\"\nURL: {url}\nText: {text}\n"
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return '\n'.join(lines)


# ── Master orchestrator ──────────────────────────────────────────────────────

def run_all_writing_agents(hard_data: dict, articles: list[dict],
                           rss_items: list[dict] | None = None,
                           events: list[dict] | None = None,
                           signal_context: dict | None = None,
                           watchlist: dict | None = None,
                           anthropic_client=None, cost_state=None,
                           conn=None, gemini_client=None,
                           dossier: dict | None = None) -> dict:
    """
    Run all writing agents and return a merged payload (replaces Calls 1+2).

    When a dossier is provided (from synthesis agent), writing agents receive
    focused, pre-analyzed context instead of raw data dumps.

    Returns dict with: headline, key_indicators, executive_summary, metrics,
    national, global, globalVectors, consumer_pulse, word_cloud_topics,
    indicatorContextLines, watchlist, industry_executive_summary,
    goodsIndustries, servicesIndustries, yieldCurve, charts.
    """
    from phases.analysis import (_hard_data_summary, _format_articles_for_prompt,
                                 _build_canadian_officials_context,
                                 _build_global_officials_context,
                                 _build_signal_context_blocks)

    today_str = date.today().strftime('%B %d, %Y')
    hard_summary = _hard_data_summary(hard_data, rss_items)
    signal_blocks = _build_signal_context_blocks(signal_context or {})

    # Build dossier context block if available
    dossier_context = ''
    if dossier and isinstance(dossier, dict) and dossier.get('top_stories'):
        dossier_lines = ["\nEDITOR'S DOSSIER (pre-analyzed — use this as your primary guide):\n"]
        dossier_lines.append(f"Edition headline: {dossier.get('edition_headline', '')}\n")

        nat_ctx = dossier.get('national_context', {})
        if nat_ctx:
            dossier_lines.append(f"MACRO NARRATIVE: {nat_ctx.get('macro_narrative', '')}")
            dossier_lines.append(f"BOC CONTEXT: {nat_ctx.get('boc_context', '')}\n")

        for story in dossier.get('top_stories', [])[:7]:
            dossier_lines.append(f"TOP STORY #{story.get('rank', '?')}: {story.get('headline', '')}")
            dossier_lines.append(f"  {story.get('summary', '')}")
            for dp in story.get('data_points', [])[:5]:
                dossier_lines.append(f"  • {dp}")
            dossier_lines.append(f"  Sources: {', '.join(story.get('source_urls', [])[:3])}")
            dossier_lines.append("")

        for theme in dossier.get('cross_cutting_themes', [])[:3]:
            dossier_lines.append(f"THEME: {theme.get('theme', '')}: {theme.get('description', '')}")

        notes = dossier.get('writer_notes', {})
        if notes.get('data_warnings'):
            dossier_lines.append(f"\nDATA WARNINGS: {'; '.join(notes['data_warnings'])}")

        dossier_context = '\n'.join(dossier_lines)

    # When dossier is available, it's the primary context — skip raw article dump
    # to keep prompts within context window limits
    economy_arts = []
    if dossier_context:
        hard_summary = hard_summary + '\n\n' + dossier_context
        all_arts_text = '(Articles already analyzed in dossier above — cite sources from dossier)'
        industry_arts_text = '(Industry articles already analyzed in dossier above)'
    else:
        # Fallback: use extracted articles or RSS items
        economy_arts = [a for a in articles if a.get('topic') == 'economy']
        if not economy_arts and rss_items:
            economy_arts = [
                {
                    'title': r.get('title', ''),
                    'text': r.get('summary', '') or r.get('snippet', ''),
                    'url': r.get('url', ''),
                    'topic': 'economy',
                    'feed_id': r.get('source_name', ''),
                    'meta_sectors': r.get('tags', []),
                    'meta_provinces': [r['province']] if r.get('province') else [],
                }
                for r in rss_items
                if r.get('title')
            ]
        all_arts_text = _format_articles_for_prompt(economy_arts[:50])
        industry_arts = [a for a in economy_arts if any(
            kw in (a.get('title', '') + a.get('text', '')).lower()
            for kw in ('energy', 'oil', 'mining', 'manufactur', 'housing', 'finance',
                        'health', 'retail', 'transit', 'transport', 'education',
                        'agriculture', 'defence', 'telecom', 'real estate')
        )]
        industry_arts_text = _format_articles_for_prompt(industry_arts[:50])

    cdn_officials = _build_canadian_officials_context(watchlist or {})
    global_officials = _build_global_officials_context(watchlist or {})

    # Events text for watchlist agent
    events_text = ""
    if events:
        events_lines = [f"  - [{e.get('date','')}] {e.get('name','')} ({e.get('source','')})"
                        for e in (events or [])[:25]]
        events_text = '\n'.join(events_lines)

    # ── Define all agent tasks ────────────────────────────────────
    tasks = {}

    # Group 1: Macro
    tasks['exec_summary'] = {
        'prompt': _build_exec_summary_prompt(
            today_str, hard_summary, all_arts_text,
            signal_blocks.get('call1', ''), cdn_officials, ''),
        'label': 'agent-exec-summary',
    }
    tasks['national'] = {
        'prompt': _build_national_prompt(
            today_str, hard_summary, all_arts_text,
            signal_blocks.get('call1', ''), cdn_officials),
        'label': 'agent-national',
    }
    tasks['consumer_pulse'] = {
        'prompt': _build_consumer_pulse_prompt(today_str, all_arts_text),
        'label': 'agent-consumer-pulse',
    }
    tasks['watchlist'] = {
        'prompt': _build_watchlist_prompt(today_str, all_arts_text, events_text),
        'label': 'agent-watchlist',
    }

    # Global regions
    for region, emoji in [('United States', ''), ('China', ''), ('European Union', ''), ('United Kingdom', '')]:
        key = f"global_{region.lower().replace(' ', '_')}"
        tasks[key] = {
            'prompt': _build_global_prompt(
                today_str, region, emoji, hard_summary,
                all_arts_text, global_officials),
            'label': f'agent-global-{region[:2].lower()}',
        }

    # Group 2: Industries
    tasks['industry_summary'] = {
        'prompt': _build_industry_summary_prompt(
            today_str, hard_summary, industry_arts_text,
            signal_blocks.get('sector_signals', '')),
        'label': 'agent-industry-summary',
    }

    # Individual sectors
    for code, name in GOODS_SECTORS + SERVICES_SECTORS:
        sector_arts = _filter_articles_for_sector(economy_arts, code)
        sector_arts_text = _format_articles_compact(sector_arts)
        is_goods = code in [c for c, _ in GOODS_SECTORS]
        key = f"sector_{code}"
        tasks[key] = {
            'prompt': _build_sector_prompt(
                today_str, code, name, sector_arts_text,
                signal_blocks.get('sector_signals', ''), is_goods),
            'label': f'agent-sector-{code}',
        }

    # Yield curve
    tasks['yield_curve'] = {
        'prompt': _build_yield_curve_prompt(today_str, hard_summary),
        'label': 'agent-yield-curve',
    }

    # ── Execute all agents ────────────────────────────────────────
    total = len(tasks)
    print(f"  [Writing Agents] Launching {total} agents ({MAX_WORKERS} parallel workers)...")

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for key, task in tasks.items():
            f = executor.submit(
                _run_agent, task['prompt'], task['label'],
                anthropic_client=anthropic_client, cost_state=cost_state,
                conn=conn, gemini_client=gemini_client,
            )
            futures[f] = key

        completed = 0
        for future in as_completed(futures):
            key = futures[future]
            completed += 1
            try:
                result = future.result()
                if result and isinstance(result, dict):
                    results[key] = result
                    print(f"    [{completed}/{total}] [OK] {key}")
                else:
                    print(f"    [{completed}/{total}] [WARN] {key}: empty response")
                    results[key] = {}
            except Exception as e:
                print(f"    [{completed}/{total}] [ERROR] {key}: {e}")
                results[key] = {}

    ok_count = sum(1 for v in results.values() if v)
    print(f"  [Writing Agents] Complete: {ok_count}/{total} agents returned data")

    # ── Merge results into unified payload ────────────────────────
    payload = {}

    # Executive summary
    es = results.get('exec_summary', {})
    payload['headline'] = es.get('headline', '')
    payload['key_indicators'] = es.get('key_indicators', [])
    payload['executive_summary'] = es.get('executive_summary', '')
    payload['metrics'] = es.get('metrics', {})

    # National
    nat = results.get('national', {})
    payload['national'] = nat.get('national', {'analysis': '', 'sources': []})
    # National insight chart (agent-driven)
    payload['insightChart'] = nat.get('insightChart', None)

    # Consumer pulse + word cloud + indicator context
    cp = results.get('consumer_pulse', {})
    payload['consumer_pulse'] = cp.get('consumer_pulse', '')
    payload['word_cloud_topics'] = cp.get('word_cloud_topics', [])
    payload['indicatorContextLines'] = cp.get('indicatorContextLines', {})

    # Watchlist
    wl = results.get('watchlist', {})
    payload['watchlist'] = wl.get('watchlist', [])

    # Global
    global_list = []
    global_vectors = {}
    for region_key, region_name in [('global_united_states', 'us'),
                                     ('global_china', 'china'),
                                     ('global_european_union', 'eu'),
                                     ('global_united_kingdom', 'uk')]:
        g = results.get(region_key, {})
        if g:
            global_list.append(g)
            analysis = g.get('analysis', '')
            global_vectors[region_name] = analysis[:150] if analysis else ''
    payload['global'] = global_list
    payload['globalVectors'] = global_vectors

    # Industry summary
    ind_sum = results.get('industry_summary', {})
    payload['industry_executive_summary'] = ind_sum.get('industry_executive_summary', '')

    # Sectors
    goods = []
    services = []
    for code, name in GOODS_SECTORS:
        s = results.get(f'sector_{code}', {})
        if s:
            s.setdefault('code', code)
            s.setdefault('name', name)
            goods.append(s)
        else:
            goods.append({'code': code, 'name': name, 'mm': '', 'yy': '',
                          'analysis': '', 'industrySources': [], 'isNegative': False,
                          'subsectors': [], 'indicatorSrc': 'StatCan'})
    for code, name in SERVICES_SECTORS:
        s = results.get(f'sector_{code}', {})
        if s:
            s.setdefault('code', code)
            s.setdefault('name', name)
            services.append(s)
        else:
            services.append({'code': code, 'name': name, 'mm': '', 'yy': '',
                             'analysis': '', 'industrySources': [], 'isNegative': False,
                             'subsectors': [], 'indicatorSrc': 'StatCan'})
    payload['goodsIndustries'] = goods
    payload['servicesIndustries'] = services

    # Yield curve
    yc = results.get('yield_curve', {})
    payload['yieldCurve'] = yc.get('yieldCurve', [])
    payload['charts'] = yc.get('charts', {})

    return payload