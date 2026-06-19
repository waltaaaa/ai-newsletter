"""
synthesis_agent.py — Opus synthesis agent: the editor's desk.

Layer 4 of the 4-layer agent pipeline. Takes ALL collected data —
pipeline sweep, research findings, analysis briefs — and produces
a structured dossier that the writing agents consume.

The dossier is the single source of truth for the writing layer.
It tells writers: "Here are the stories, here's the data, here's
what connects to what. Write about THIS."

One agent, one pass, comprehensive output.
"""

import json
import os
import shutil
import subprocess
from datetime import date

CLAUDE_CODE_MODEL = os.environ.get('SYNTHESIS_AGENT_MODEL', 'opus')
AGENT_TIMEOUT = int(os.environ.get('SYNTHESIS_AGENT_TIMEOUT', '600'))

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
    "Never recommend policy, investment, or business decisions. "
    "PROSE STYLE: Every narrative paragraph opens with a lead-in sentence wrapped in "
    "<span class=\"lead-sentence\">...</span> followed by ' — ' (space, em-dash, space) "
    "and the supporting detail. NEVER use <strong> or <b> tags — the lead-in is the only "
    "bold text (styled by frontend CSS); numbers stay specific but unbolded."
)


# ── Agent runner ────────────────────────────────────────────────────────────

def _call_synthesis_agent(prompt: str) -> dict | None:
    """Call the synthesis agent — single Opus pass with extended timeout."""
    prompt_file = None
    try:
        if not _CLAUDE_CLI:
            raise FileNotFoundError("claude CLI not resolved")
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write(prompt)
            prompt_file = f.name
        prompt_arg = f'Read the file {prompt_file} and follow the instructions exactly. Output ONLY valid JSON.'
        cmd = [
            _CLAUDE_CLI, '-p', prompt_arg,
            '--model', CLAUDE_CODE_MODEL,
            '--output-format', 'json',
            '--max-turns', '2',
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=AGENT_TIMEOUT,
            encoding='utf-8', errors='replace', env=_CLAUDE_ENV,
        )
        if result.returncode != 0:
            print(f"    [synthesis] exit code {result.returncode}")
            return None
        output = result.stdout.strip()
        if not output:
            return None
        return _extract_json(output)
    except subprocess.TimeoutExpired:
        print(f"    [synthesis] Timed out after {AGENT_TIMEOUT}s")
        return None
    except FileNotFoundError:
        print("    [synthesis] 'claude' CLI not found")
        return None
    except Exception as e:
        print(f"    [synthesis] Error: {type(e).__name__}: {e}")
        return None
    finally:
        if prompt_file:
            try:
                os.unlink(prompt_file)
            except OSError:
                pass


def _extract_json(output: str) -> dict | None:
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
    print(f"    [synthesis] JSON parse failed ({len(text)} chars)")
    return None


# ── Dossier builder ─────────────────────────────────────────────────────────

def _format_briefs(briefs: dict) -> str:
    """Format analysis briefs for the synthesis prompt."""
    if not briefs:
        return "(No analysis briefs available)"

    sections = []
    for key, brief in briefs.items():
        brief_type = brief.get('brief_type', key)
        sections.append(f"=== ANALYSIS BRIEF: {brief_type.upper()} ===")
        sections.append(json.dumps(brief, indent=2, ensure_ascii=False)[:3000])
        sections.append("")

    return '\n'.join(sections)


def _format_indicators_compact(hard_data: dict) -> str:
    """Compact indicator summary for synthesis."""
    pi = hard_data.get('primary_indicators', {})
    nat = pi.get('national', {}).get('values', {})
    boc = hard_data.get('boc_rate', 'N/A')

    lines = [f"BoC Rate: {boc}"]
    for k, v in nat.items():
        lines.append(f"{k}: {v}")

    comms = hard_data.get('commodities', {}).get('summary', {})
    for name, val in list(comms.items())[:5]:
        lines.append(f"{name}: {val}")

    return ', '.join(lines)


def _build_synthesis_prompt(today_str: str, indicators: str,
                             briefs_text: str, research_summary: str,
                             article_count: int, project_stats: str,
                             federal_context: str,
                             province_highlights: str) -> str:
    return f"""You are the editor-in-chief of "The Lagging Indicator," a weekly Canadian economic intelligence briefing. Today is {today_str}.
{EDITORIAL_RULES}

Your job: synthesize ALL of this week's research into a structured DOSSIER that your writing team will use to draft the briefing. The dossier must be comprehensive, prioritized, and actionable for writers.

The writing team should NOT need to do any additional research — everything they need is in the dossier.

INDICATORS THIS WEEK:
{indicators}

RESEARCH AGENT SUMMARY:
{research_summary}

FEDERAL CONTEXT:
{federal_context}

PROVINCIAL HIGHLIGHTS:
{province_highlights}

{project_stats}

Pipeline collected {article_count} articles this week.

ANALYSIS BRIEFS FROM SPECIALIST AGENTS:
{briefs_text}

Now produce the dossier. Prioritize by significance — lead with what matters most.

OUTPUT: Valid JSON only.
{{
  "edition_headline": "8-12 word newspaper-style headline for this week's edition",

  "top_stories": [
    {{
      "rank": 1,
      "headline": "Story headline",
      "summary": "3-5 sentences explaining what happened, why it matters, with specific data points. Include exact figures, percentages, dollar values.",
      "data_points": ["Each specific number or fact the writer should cite"],
      "source_urls": ["URLs to cite"],
      "connected_to": ["Other stories or themes this links to"],
      "affected_sectors": ["sector codes"],
      "affected_provinces": ["province names"]
    }}
  ],

  "national_context": {{
    "macro_narrative": "4-6 sentences telling the national economic story this week. What moved, what it means in context, how indicators relate to each other.",
    "boc_context": "1-2 sentences on monetary policy stance",
    "key_indicators": [
      {{"label": "Indicator name", "value": "Current value", "change": "Period-over-period change", "context": "Why this number matters this week"}}
    ]
  }},

  "provincial_highlights": [
    {{
      "province": "Province name",
      "headline": "Key development",
      "details": "2-3 sentences with specifics",
      "projects_mentioned": ["Project names if applicable"],
      "data_points": ["Specific figures"]
    }}
  ],

  "sector_signals": [
    {{
      "sector": "Sector name",
      "activity": "high|moderate|low|declining",
      "headline": "What's happening in this sector",
      "data_points": ["GDP figures, project counts, values"],
      "connections": ["What's driving this — policy, rates, commodities?"]
    }}
  ],

  "policy_brief": [
    {{
      "title": "Policy action or development",
      "description": "What it does and what it affects",
      "impact_on_pipeline": "Which projects or project types are affected",
      "timeline": "When this takes effect",
      "source_url": "URL"
    }}
  ],

  "cross_cutting_themes": [
    {{
      "theme": "Theme name",
      "description": "How this theme manifests across multiple data streams",
      "evidence": ["Specific data points from different sources that support this theme"]
    }}
  ],

  "writer_notes": {{
    "tone_guidance": "Any specific tone considerations for this week's edition",
    "data_warnings": ["Any data points that need caveats or context"],
    "source_quality": "Assessment of source coverage this week"
  }}
}}"""


# ── Main entry point ────────────────────────────────────────────────────────

def run_synthesis(hard_data: dict = None, rss_items: list = None,
                   analysis_briefs: dict = None,
                   research_findings: list = None,
                   research_policy: list = None,
                   province_context: dict = None,
                   federal_context: str = '',
                   conn=None) -> dict:
    """Run the synthesis agent and return the dossier."""
    hard_data = hard_data or {}
    rss_items = rss_items or []
    analysis_briefs = analysis_briefs or {}
    research_findings = research_findings or []
    province_context = province_context or {}

    today_str = date.today().strftime('%B %d, %Y')
    indicators = _format_indicators_compact(hard_data)
    briefs_text = _format_briefs(analysis_briefs)

    # Research summary
    research_lines = []
    for f in research_findings[:25]:
        research_lines.append(
            f"  - [{f.get('province','')}] {f.get('name','')}: "
            f"{f.get('description','')[:100]} ({f.get('value','N/A')})"
        )
    research_summary = '\n'.join(research_lines) if research_lines else "(No research findings)"

    # Province highlights from research
    prov_lines = []
    for prov, ctx in province_context.items():
        if ctx:
            prov_lines.append(f"  {prov}: {ctx}")
    province_highlights = '\n'.join(prov_lines) if prov_lines else "(No provincial context)"

    # Project stats
    project_stats = ""
    if conn:
        try:
            total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            recent = conn.execute("""
                SELECT COUNT(*) FROM projects
                WHERE announced >= date('now', '-7 days')
            """).fetchone()[0]
            project_stats = f"PROJECT DATABASE: {total} projects tracked, {recent} new this week"
        except Exception:
            pass

    prompt = _build_synthesis_prompt(
        today_str, indicators, briefs_text, research_summary,
        len(rss_items), project_stats, federal_context,
        province_highlights,
    )

    print(f"  [Synthesis Agent] Running dossier synthesis (Opus, {AGENT_TIMEOUT}s timeout)...")
    dossier = _call_synthesis_agent(prompt)

    if dossier:
        stories = len(dossier.get('top_stories', []))
        provs = len(dossier.get('provincial_highlights', []))
        sectors = len(dossier.get('sector_signals', []))
        print(f"  [Synthesis Agent] Dossier complete: {stories} top stories, "
              f"{provs} provincial highlights, {sectors} sector signals")
    else:
        print("  [Synthesis Agent] WARNING: Dossier synthesis failed — "
              "writing agents will use raw data")
        dossier = {}

    return {'dossier': dossier}


# ── Pipeline phase entry point ──────────────────────────────────────────────

def run(conn, context: dict, run_log) -> dict:
    """Pipeline phase entry point for synthesis agent."""
    step_name = "synthesis_agent"
    try:
        result = run_synthesis(
            hard_data=context.get('hard_data', {}),
            rss_items=context.get('rss_items', []),
            analysis_briefs=context.get('analysis_briefs', {}),
            research_findings=context.get('research_findings', []),
            research_policy=context.get('research_policy', []),
            province_context=context.get('province_context', {}),
            federal_context=context.get('federal_context', ''),
            conn=conn,
        )
        run_log.log_step(step_name)
        return result
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Synthesis agent failed: {e}")
        traceback.print_exc()
        run_log.log_error(step_name, e, recovered=True)
        return {}
