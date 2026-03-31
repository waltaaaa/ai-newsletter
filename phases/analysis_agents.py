"""
analysis_agents.py — Opus analysis agents for deep interpretation.

Layer 3 of the 4-layer agent pipeline. Runs AFTER research agents,
taking the full collected data (pipeline sweep + research findings)
and producing structured research briefs.

5 focused analysis agents:
  1. Macro/National   — indicator movements, BoC context, national trends
  2. Provincial       — regional trends, clusters, provincial developments
  3. Sector/Industry  — sector performance, project pipeline shifts
  4. Policy/Regulatory — legislation implications, regulatory decisions
  5. Cross-Reference   — connections between indicators, projects, policy

Each agent receives focused data and produces a research brief as JSON.
"""

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

MAX_WORKERS = int(os.environ.get('ANALYSIS_AGENT_WORKERS', '2'))
CLAUDE_CODE_MODEL = os.environ.get('ANALYSIS_AGENT_MODEL', 'opus')
AGENT_TIMEOUT = int(os.environ.get('ANALYSIS_AGENT_TIMEOUT', '420'))

_CLAUDE_CLI = shutil.which('claude')
if not _CLAUDE_CLI:
    _npm_dir = os.path.join(os.environ.get('APPDATA', ''), 'npm')
    _candidate = os.path.join(_npm_dir, 'claude.cmd')
    if os.path.isfile(_candidate):
        _CLAUDE_CLI = _candidate

_CLAUDE_ENV = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}

EDITORIAL_RULES = (
    "EDITORIAL RULES: REPORT ONLY — no editorializing. State what happened, "
    "what the data shows, what is connected. Never say 'should', 'must', "
    "'hopefully', 'unfortunately', 'worrying', 'promising', 'encouraging'. "
    "Never recommend policy, investment, or business decisions."
)


# ── Agent runner ────────────────────────────────────────────────────────────

def _call_analysis_agent(prompt: str, label: str) -> dict | None:
    """Call Opus analysis agent — single turn, deep analytical output."""
    prompt_file = None
    try:
        if not _CLAUDE_CLI:
            raise FileNotFoundError("claude CLI not resolved")
        if len(prompt) > 30000:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                             encoding='utf-8') as f:
                f.write(prompt)
                prompt_file = f.name
            prompt_arg = f'Read the file {prompt_file} and follow the instructions exactly. Output ONLY valid JSON.'
            turns = 2
        else:
            prompt_arg = prompt
            turns = 1
        cmd = [
            _CLAUDE_CLI, '-p', prompt_arg,
            '--model', CLAUDE_CODE_MODEL,
            '--output-format', 'json',
            '--max-turns', str(turns),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=AGENT_TIMEOUT,
            encoding='utf-8', errors='replace', env=_CLAUDE_ENV,
        )
        if result.returncode != 0:
            print(f"    [{label}] exit code {result.returncode}")
            return None
        output = result.stdout.strip()
        if not output:
            return None
        return _extract_json(output, label)
    except subprocess.TimeoutExpired:
        print(f"    [{label}] Timed out after {AGENT_TIMEOUT}s")
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


def _extract_json(output: str, label: str) -> dict | None:
    text = output.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        text = '\n'.join(lines).strip()
    try:
        outer = json.loads(text)
        inner = outer.get('result', outer.get('text', text))
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, str):
            text = inner
    except (json.JSONDecodeError, TypeError):
        pass
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


# ── Data formatters ─────────────────────────────────────────────────────────

def _format_indicators(hard_data: dict) -> str:
    """Format indicator data for analysis prompts."""
    lines = []
    pi = hard_data.get('primary_indicators', {})
    nat = pi.get('national', {}).get('values', {})
    if nat:
        lines.append("NATIONAL INDICATORS:")
        for k, v in nat.items():
            lines.append(f"  {k}: {v}")

    boc = hard_data.get('boc_rate', 'N/A')
    lines.append(f"\nBank of Canada Policy Rate: {boc}")

    comms = hard_data.get('commodities', {}).get('summary', {})
    if comms:
        lines.append("\nCOMMODITY PRICES:")
        for name, val in list(comms.items())[:10]:
            lines.append(f"  {name}: {val}")

    fm = hard_data.get('financial_markets', {})
    indices = fm.get('indices', [])
    if indices:
        lines.append("\nEQUITY INDICES:")
        for idx in indices[:5]:
            lines.append(f"  {idx.get('name','')}: {idx.get('value','')} "
                        f"(day {idx.get('day','')}, YoY {idx.get('yy','')})")

    # Industry GDP
    ind = pi.get('industries', {})
    if ind:
        lines.append("\nINDUSTRY GDP (StatCan 36-10-0434-01):")
        for code, d in ind.items():
            if not code.startswith('_'):
                lines.append(f"  NAICS {code}: M/M={d.get('mm','N/A')}, "
                           f"Y/Y={d.get('yy','N/A')}")

    return '\n'.join(lines) if lines else "(No indicator data available)"


def _format_articles(rss_items: list, limit: int = 30,
                     province: str = None, sector: str = None) -> str:
    """Format RSS items for analysis prompts."""
    items = rss_items or []
    if province:
        prov_lower = province.lower()
        items = [r for r in items
                 if prov_lower in (r.get('title', '') + r.get('summary', '')).lower()
                 or (r.get('province', '') or '').lower() == prov_lower]
    if sector:
        sec_lower = sector.lower()
        items = [r for r in items
                 if sec_lower in (r.get('title', '') + r.get('summary', '')).lower()
                 or sec_lower in str(r.get('tags', '')).lower()]

    if not items:
        return "(No articles available for this scope)"

    lines = []
    for i, r in enumerate(items[:limit], 1):
        title = r.get('title', '')
        summary = r.get('summary', '')[:200]
        url = r.get('url', '')
        source = r.get('source_name', '')
        lines.append(f"[{i}] {title}\n    Source: {source}\n    URL: {url}\n    {summary}")

    return '\n'.join(lines)


def _format_research_findings(findings: list, limit: int = 20) -> str:
    """Format research agent findings for analysis prompts."""
    if not findings:
        return "(No additional findings from research agents)"
    lines = []
    for f in findings[:limit]:
        lines.append(f"  - {f.get('name','')}: {f.get('description','')} "
                    f"[{f.get('province','')}, {f.get('sector','')}, "
                    f"{f.get('value','Not disclosed')}]")
    return '\n'.join(lines)


def _format_policy_items(policy_items: list) -> str:
    """Format policy items for analysis."""
    if not policy_items:
        return "(No policy items tracked this week)"
    lines = []
    for p in policy_items[:15]:
        lines.append(f"  - {p.get('title','')}: {p.get('description', p.get('summary',''))[:150]}")
        if p.get('affected_sectors'):
            lines.append(f"    Sectors: {', '.join(p['affected_sectors'][:3])}")
        if p.get('source_url'):
            lines.append(f"    URL: {p['source_url']}")
    return '\n'.join(lines)


def _format_project_stats(conn) -> str:
    """Get project database statistics for analysis context."""
    if not conn:
        return "(No database connection)"
    try:
        total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        by_status = conn.execute("""
            SELECT status, COUNT(*) FROM projects GROUP BY status
            ORDER BY COUNT(*) DESC
        """).fetchall()
        by_sector = conn.execute("""
            SELECT sector, COUNT(*), SUM(CASE WHEN value_millions IS NOT NULL
                THEN value_millions ELSE 0 END) as total_val
            FROM projects GROUP BY sector ORDER BY total_val DESC LIMIT 10
        """).fetchall()
        recent = conn.execute("""
            SELECT COUNT(*) FROM projects
            WHERE announced >= date('now', '-7 days')
        """).fetchone()[0]

        lines = [f"PROJECT DATABASE: {total} total projects, {recent} new this week"]
        lines.append("By status: " + ', '.join(
            f"{s[0]}={s[1]}" for s in by_status))
        lines.append("Top sectors by value:")
        for s in by_sector[:8]:
            val = f"${s[2]/1e6:.0f}M" if s[2] else "N/A"
            lines.append(f"  {s[0]}: {s[1]} projects, {val}")
        return '\n'.join(lines)
    except Exception as e:
        return f"(Database query failed: {e})"


# ── Prompt builders ─────────────────────────────────────────────────────────

def _build_macro_prompt(today_str: str, indicators: str, articles: str,
                        research_ctx: str, project_stats: str) -> str:
    return f"""You are a senior Canadian economic analyst. Today is {today_str}.
{EDITORIAL_RULES}

Analyze this week's macroeconomic data and produce a research brief that a writing team will use to draft the weekly briefing.

{indicators}

TOP NEWS ARTICLES:
{articles}

RESEARCH AGENT FINDINGS:
{research_ctx}

{project_stats}

Produce a structured research brief. Focus on what matters most — the 3-5 developments that should lead the briefing. For each, explain what happened, provide the exact data points, and note what it connects to.

OUTPUT: Valid JSON only.
{{
  "brief_type": "macro_national",
  "key_developments": [
    {{
      "headline": "Short headline",
      "significance": "Why this matters — 2-3 sentences with specific data",
      "data_points": ["Specific numbers and sources to cite"],
      "connections": ["How this links to other developments or projects"]
    }}
  ],
  "indicator_narrative": "3-4 sentences interpreting this week's indicator movements in context — what changed, by how much, and what it means relative to recent trends",
  "boc_context": "1-2 sentences on current monetary policy stance and next decision date",
  "risks_and_signals": ["Emerging signals or divergences worth monitoring"]
}}"""


def _build_provincial_prompt(today_str: str, articles: str,
                              research_ctx: str, province_context: dict,
                              project_stats: str) -> str:
    prov_lines = []
    for prov, ctx in (province_context or {}).items():
        if ctx:
            prov_lines.append(f"  {prov}: {ctx}")
    prov_summary = '\n'.join(prov_lines) if prov_lines else "(No provincial context)"

    return f"""You are a senior Canadian economic analyst. Today is {today_str}.
{EDITORIAL_RULES}

Analyze provincial developments across Canada and produce a research brief highlighting regional trends and noteworthy activity.

PROVINCIAL CONTEXT (from research agents):
{prov_summary}

TOP NEWS ARTICLES:
{articles}

RESEARCH AGENT FINDINGS:
{research_ctx}

{project_stats}

Identify the most significant provincial developments. Look for: provinces with unusual activity, clusters of related projects, regional policy impacts, and inter-provincial patterns.

OUTPUT: Valid JSON only.
{{
  "brief_type": "provincial",
  "spotlight_province": {{
    "name": "Province with the most significant activity",
    "rationale": "Why this province stands out this week — specific data",
    "key_developments": ["List of specific developments with data"]
  }},
  "provincial_highlights": [
    {{
      "province": "Province name",
      "headline": "Key development",
      "details": "1-2 sentences with specifics"
    }}
  ],
  "regional_patterns": ["Cross-province patterns or trends observed"],
  "data_gaps": ["Provinces or regions with thin coverage that may need attention"]
}}"""


def _build_sector_prompt(today_str: str, indicators: str, articles: str,
                          research_ctx: str, project_stats: str) -> str:
    return f"""You are a senior Canadian economic analyst specializing in sector analysis. Today is {today_str}.
{EDITORIAL_RULES}

Analyze sector-level activity across Canada's capital project pipeline and produce a research brief on industry trends.

{indicators}

TOP NEWS ARTICLES (industry-focused):
{articles}

RESEARCH AGENT FINDINGS:
{research_ctx}

{project_stats}

Identify which sectors are most active, which are shifting, and what's driving changes. Connect industry GDP data to project pipeline activity.

OUTPUT: Valid JSON only.
{{
  "brief_type": "sector_industry",
  "top_sectors": [
    {{
      "sector": "Sector name",
      "activity_level": "high|moderate|low",
      "headline": "Key development in this sector",
      "data_points": ["Specific GDP, project count, or value data"],
      "outlook_signals": ["What the data suggests about near-term activity"]
    }}
  ],
  "sector_shifts": ["Notable changes in sector activity compared to recent weeks"],
  "cross_sector_themes": ["Themes affecting multiple sectors — e.g., supply chain, labour, rates"]
}}"""


def _build_policy_prompt(today_str: str, policy_items: str,
                          research_policy: str, articles: str,
                          project_stats: str) -> str:
    return f"""You are a senior Canadian policy analyst specializing in investment and infrastructure policy. Today is {today_str}.
{EDITORIAL_RULES}

Analyze this week's policy and regulatory developments and produce a research brief on their implications for capital investment.

POLICY ITEMS FROM PIPELINE:
{policy_items}

POLICY FINDINGS FROM RESEARCH AGENTS:
{research_policy}

RELEVANT NEWS ARTICLES:
{articles}

{project_stats}

For each significant policy development, analyze what it means for the capital project pipeline. Which projects are affected? What sectors? What timelines?

OUTPUT: Valid JSON only.
{{
  "brief_type": "policy_regulatory",
  "significant_developments": [
    {{
      "title": "Policy or regulatory action",
      "description": "What happened — factual description",
      "affected_sectors": ["sector codes"],
      "affected_provinces": ["provinces"],
      "project_impact": "How this affects the capital project pipeline — specific projects or categories",
      "timeline": "When this takes effect or next steps",
      "source_url": "URL"
    }}
  ],
  "regulatory_signals": ["Upcoming regulatory actions or consultations to watch"],
  "legislative_status": ["Status of key bills or regulatory processes in progress"]
}}"""


def _build_crossref_prompt(today_str: str, indicators: str, articles: str,
                            research_ctx: str, project_stats: str,
                            policy_items: str) -> str:
    return f"""You are a senior Canadian economic analyst specializing in connecting economic signals to real-world outcomes. Today is {today_str}.
{EDITORIAL_RULES}

Your job: find connections that aren't obvious. Link indicator movements to project pipeline activity, policy changes to sector impacts, and identify divergences where data points contradict each other.

{indicators}

TOP NEWS:
{articles}

RESEARCH FINDINGS:
{research_ctx}

POLICY DEVELOPMENTS:
{policy_items}

{project_stats}

Look for:
1. Indicator-project connections (e.g., rate change → affected project types)
2. Policy-sector linkages (e.g., new regulation → which projects are impacted)
3. Divergences (e.g., strong GDP but weak project starts in a sector)
4. Leading signals (e.g., procurement awards that signal future construction)
5. Cross-cutting themes that span multiple data streams

OUTPUT: Valid JSON only.
{{
  "brief_type": "cross_reference",
  "connections": [
    {{
      "theme": "Short theme title",
      "description": "What connects to what and why it matters — 2-3 sentences",
      "data_streams": ["Which data sources this connection draws from"],
      "affected_projects_estimate": "Approximate count or value of affected projects"
    }}
  ],
  "divergences": [
    {{
      "observation": "What doesn't line up",
      "possible_explanations": ["Hypotheses for the divergence"]
    }}
  ],
  "microscope_candidate": {{
    "topic": "Suggested Under the Microscope topic for this week",
    "rationale": "Why this deserves a deep dive — what makes it the biggest story"
  }}
}}"""


# ── Main orchestrator ───────────────────────────────────────────────────────

def run_analysis_agents(hard_data: dict = None, rss_items: list = None,
                         research_findings: list = None,
                         research_policy: list = None,
                         province_context: dict = None,
                         policy_items: list = None,
                         signal_context: dict = None,
                         conn=None) -> dict:
    """Run all 5 analysis agents and return their research briefs."""
    hard_data = hard_data or {}
    rss_items = rss_items or []
    research_findings = research_findings or []
    research_policy = research_policy or []
    province_context = province_context or {}
    policy_items = policy_items or []

    today_str = date.today().strftime('%B %d, %Y')
    indicators = _format_indicators(hard_data)
    articles = _format_articles(rss_items, limit=30)
    research_ctx = _format_research_findings(research_findings)
    project_stats = _format_project_stats(conn)
    policy_text = _format_policy_items(policy_items + research_policy)

    # Industry-focused articles for sector agent
    industry_kw = ['energy', 'oil', 'mining', 'manufactur', 'housing', 'finance',
                   'health', 'retail', 'transit', 'transport', 'construction',
                   'agriculture', 'defence', 'telecom', 'real estate']
    industry_items = [r for r in rss_items if any(
        kw in (r.get('title', '') + r.get('summary', '')).lower()
        for kw in industry_kw
    )]
    industry_articles = _format_articles(industry_items, limit=30)

    # Policy-focused articles
    policy_kw = ['bill', 'legislation', 'regulation', 'policy', 'budget',
                 'minister', 'government', 'federal', 'provincial', 'act',
                 'gazette', 'consultation', 'assessment', 'tribunal']
    policy_items_rss = [r for r in rss_items if any(
        kw in (r.get('title', '') + r.get('summary', '')).lower()
        for kw in policy_kw
    )]
    policy_articles = _format_articles(policy_items_rss, limit=20)

    tasks = {
        'macro': {
            'prompt': _build_macro_prompt(today_str, indicators, articles,
                                          research_ctx, project_stats),
            'label': 'analysis-macro',
        },
        'provincial': {
            'prompt': _build_provincial_prompt(today_str, articles, research_ctx,
                                               province_context, project_stats),
            'label': 'analysis-provincial',
        },
        'sector': {
            'prompt': _build_sector_prompt(today_str, indicators,
                                           industry_articles, research_ctx,
                                           project_stats),
            'label': 'analysis-sector',
        },
        'policy': {
            'prompt': _build_policy_prompt(today_str, policy_text,
                                           _format_research_findings(research_policy),
                                           policy_articles, project_stats),
            'label': 'analysis-policy',
        },
        'crossref': {
            'prompt': _build_crossref_prompt(today_str, indicators, articles,
                                              research_ctx, project_stats,
                                              policy_text),
            'label': 'analysis-crossref',
        },
    }

    total = len(tasks)
    print(f"  [Analysis Agents] Launching {total} agents "
          f"({MAX_WORKERS} parallel, Opus)...")

    briefs = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for key, task in tasks.items():
            f = executor.submit(_call_analysis_agent, task['prompt'], task['label'])
            futures[f] = key

        completed = 0
        for future in as_completed(futures):
            key = futures[future]
            completed += 1
            try:
                result = future.result()
                if result and isinstance(result, dict):
                    briefs[key] = result
                    print(f"    [{completed}/{total}] [OK] {key}")
                else:
                    print(f"    [{completed}/{total}] [WARN] {key}: empty response")
            except Exception as e:
                print(f"    [{completed}/{total}] [ERROR] {key}: {e}")

    ok_count = len(briefs)
    print(f"  [Analysis Agents] Complete: {ok_count}/{total} briefs produced")

    return {
        'analysis_briefs': briefs,
    }


# ── Pipeline phase entry point ──────────────────────────────────────────────

def run(conn, context: dict, run_log) -> dict:
    """Pipeline phase entry point for analysis agents."""
    step_name = "analysis_agents"
    try:
        result = run_analysis_agents(
            hard_data=context.get('hard_data', {}),
            rss_items=context.get('rss_items', []),
            research_findings=context.get('research_findings', []),
            research_policy=context.get('research_policy', []),
            province_context=context.get('province_context', {}),
            policy_items=context.get('policy_items', []),
            signal_context=context.get('signal_context', {}),
            conn=conn,
        )
        run_log.log_step(step_name)
        return result
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Analysis agents failed: {e}")
        traceback.print_exc()
        run_log.log_error(step_name, e, recovered=True)
        return {}
