"""
research_agents.py — Opus research agents for discovery and gap-filling.

Layer 2 of the 4-layer agent pipeline. Runs AFTER the pipeline sweep
(RSS, registries, Google News) to:
  1. Find projects/announcements the sweep missed (per-province + federal)
  2. Fill gaps in thin coverage areas
  3. Add context and detail to key discoveries

Each agent uses Claude's built-in web search via `claude -p` with
multiple turns, running on the user's subscription ($0 API cost).

Agents:
  - 13 province discovery agents (one per province/territory)
  - 1 federal/national discovery agent
  - Gap-filling agents triggered by thin sweep coverage
"""

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

MAX_WORKERS = int(os.environ.get('RESEARCH_AGENT_WORKERS', '2'))
CLAUDE_CODE_MODEL = os.environ.get('RESEARCH_AGENT_MODEL', 'opus')
MAX_TURNS = int(os.environ.get('RESEARCH_AGENT_MAX_TURNS', '10'))
AGENT_TIMEOUT = int(os.environ.get('RESEARCH_AGENT_TIMEOUT', '420'))

PROVINCES = [
    'Ontario', 'Quebec', 'Alberta', 'British Columbia', 'Saskatchewan',
    'Manitoba', 'Nova Scotia', 'New Brunswick', 'Newfoundland and Labrador',
    'Prince Edward Island', 'Yukon', 'Northwest Territories', 'Nunavut',
]

SECTORS = [
    'oil & gas', 'mining', 'infrastructure', 'power & energy',
    'manufacturing', 'transport & logistics', 'healthcare', 'education',
    'residential', 'commercial & mixed-use', 'agriculture', 'forestry',
    'defence', 'telecom', 'Indigenous', 'environment', 'tourism & culture',
    'government',
]

# Resolve claude CLI
_CLAUDE_CLI = shutil.which('claude')
if not _CLAUDE_CLI:
    _npm_dir = os.path.join(os.environ.get('APPDATA', ''), 'npm')
    _candidate = os.path.join(_npm_dir, 'claude.cmd')
    if os.path.isfile(_candidate):
        _CLAUDE_CLI = _candidate

_CLAUDE_ENV = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}


# ── Agent runner ────────────────────────────────────────────────────────────

def _call_research_agent(prompt: str, label: str) -> dict | None:
    """Call Opus research agent with multi-turn web search enabled."""
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
            '--max-turns', str(MAX_TURNS),
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
    """Extract JSON from Claude Code response."""
    text = output.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        text = '\n'.join(lines).strip()
    # Try parsing as Claude Code JSON wrapper
    try:
        outer = json.loads(text)
        inner = outer.get('result', outer.get('text', text))
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, str):
            text = inner
    except (json.JSONDecodeError, TypeError):
        pass
    # Try direct parse
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


# ── Prompt builders ─────────────────────────────────────────────────────────

def _build_province_research_prompt(province: str, today_str: str,
                                     sweep_summary: str) -> str:
    return f"""You are a Canadian economic research analyst. Today is {today_str}.

TASK: Search for new capital project announcements, infrastructure developments, and major economic news in {province}, Canada from the past 7 days.

CONTEXT FROM PIPELINE SWEEP (what we already found):
{sweep_summary}

SEARCH FOR:
- New capital projects announced (construction, infrastructure, energy, mining, manufacturing, healthcare, education, residential, commercial)
- Government funding announcements for {province}
- Major private sector investments or facility expansions
- Project status updates (approvals, groundbreakings, completions, cancellations)
- Regulatory decisions affecting projects (environmental assessments, permits)
- Municipal development applications for projects over $10M

For each finding, verify it with a source URL. Do not fabricate projects.

OUTPUT: Valid JSON only.
{{
  "province": "{province}",
  "findings": [
    {{
      "name": "Project or announcement name",
      "description": "1-2 sentence description of what was announced",
      "value": "Dollar value if mentioned, otherwise 'Not disclosed'",
      "status": "Proposed|Announced|Approved|Under Construction|Completed|Cancelled",
      "sector": "One of: oil_gas, mining, infrastructure, power_energy, manufacturing, transport_logistics, healthcare, education, residential, commercial_mixed, agriculture, forestry, defence, telecom, indigenous, environment, tourism_culture, government",
      "source_url": "URL where this was found",
      "source_title": "Title of the source article/page",
      "date_announced": "YYYY-MM-DD if known"
    }}
  ],
  "context": "2-3 sentences summarizing the overall investment climate in {province} this week"
}}"""


def _build_federal_research_prompt(today_str: str, sweep_summary: str) -> str:
    return f"""You are a Canadian economic research analyst. Today is {today_str}.

TASK: Search for new federal government capital project announcements, national infrastructure programs, defence procurement, and major policy developments from the past 7 days that affect capital investment across Canada.

CONTEXT FROM PIPELINE SWEEP (what we already found):
{sweep_summary}

SEARCH FOR:
- Federal infrastructure funding announcements (new programs, project approvals, contribution agreements)
- Defence procurement and military infrastructure
- Crown corporation capital plans and project announcements
- Federal regulatory decisions (IAAC, CER, CRTC) affecting major projects
- National housing, transit, or climate infrastructure programs
- Trade policy changes affecting capital investment
- Bank of Canada communications relevant to investment

For each finding, verify it with a source URL. Do not fabricate.

OUTPUT: Valid JSON only.
{{
  "scope": "federal",
  "findings": [
    {{
      "name": "Project or announcement name",
      "description": "1-2 sentence description",
      "value": "Dollar value if mentioned, otherwise 'Not disclosed'",
      "status": "Proposed|Announced|Approved|Under Construction|Completed|Cancelled",
      "sector": "sector code",
      "province": "Province if location-specific, otherwise 'National'",
      "source_url": "URL",
      "source_title": "Source title",
      "date_announced": "YYYY-MM-DD if known"
    }}
  ],
  "policy_developments": [
    {{
      "title": "Policy or regulatory development",
      "description": "What changed and why it matters for capital investment",
      "affected_sectors": ["sector codes"],
      "affected_provinces": ["province names or 'All'"],
      "source_url": "URL",
      "date": "YYYY-MM-DD"
    }}
  ],
  "context": "3-4 sentences summarizing federal investment and policy activity this week"
}}"""


def _build_gap_prompt(gap_description: str, today_str: str) -> str:
    return f"""You are a Canadian economic research analyst. Today is {today_str}.

TASK: Our weekly pipeline sweep found thin coverage in the following area. Search for what we may have missed.

GAP IDENTIFIED:
{gap_description}

Search for recent announcements, projects, or developments in this area from the past 7 days. Verify each finding with a source URL. Do not fabricate.

OUTPUT: Valid JSON only.
{{
  "gap_area": "description of the gap",
  "findings": [
    {{
      "name": "Project or announcement name",
      "description": "1-2 sentence description",
      "value": "Dollar value if mentioned, otherwise 'Not disclosed'",
      "status": "Proposed|Announced|Approved|Under Construction|Completed|Cancelled",
      "sector": "sector code",
      "province": "Province",
      "source_url": "URL",
      "source_title": "Source title",
      "date_announced": "YYYY-MM-DD if known"
    }}
  ]
}}"""


# ── Sweep summary builder ──────────────────────────────────────────────────

def _build_sweep_summary(rss_items: list, province: str = None) -> str:
    """Summarize what the pipeline sweep already found for a province or nationally."""
    if not rss_items:
        return "(No articles found in pipeline sweep)"

    if province:
        prov_lower = province.lower()
        relevant = [r for r in rss_items
                    if prov_lower in (r.get('title', '') + r.get('summary', '')).lower()
                    or (r.get('province', '') or '').lower() == prov_lower]
    else:
        relevant = rss_items

    if not relevant:
        return f"(No articles found for {province or 'this scope'} in pipeline sweep — this is a gap)"

    lines = []
    for r in relevant[:20]:
        title = r.get('title', '')[:80]
        source = r.get('source_name', '')[:30]
        lines.append(f"  - [{source}] {title}")
    summary = '\n'.join(lines)
    total = len(relevant)
    if total > 20:
        summary += f"\n  ... and {total - 20} more articles"
    return f"{total} articles found:\n{summary}"


# ── Gap detection ───────────────────────────────────────────────────────────

def _detect_gaps(rss_items: list, conn=None) -> list[str]:
    """Identify coverage gaps that need research agent attention."""
    gaps = []

    # Check per-province coverage
    prov_counts = {}
    for r in rss_items:
        prov = r.get('province', '')
        if prov:
            prov_counts[prov] = prov_counts.get(prov, 0) + 1

    for prov in PROVINCES:
        count = prov_counts.get(prov, 0)
        if count < 3:
            gaps.append(
                f"{prov} had only {count} articles in the pipeline sweep. "
                f"Search for new capital projects, infrastructure announcements, "
                f"and economic developments in {prov} from the past 7 days."
            )

    # Check sector coverage if we have DB access
    if conn:
        try:
            recent = conn.execute("""
                SELECT sector, COUNT(*) as cnt
                FROM projects
                WHERE announced >= date('now', '-30 days')
                GROUP BY sector
            """).fetchall()
            sector_counts = {r[0]: r[1] for r in recent}
            thin_sectors = [s for s in SECTORS
                           if sector_counts.get(s, 0) < 2]
            if thin_sectors:
                gaps.append(
                    f"These sectors had fewer than 2 new projects in 30 days: "
                    f"{', '.join(thin_sectors[:5])}. Search for recent project "
                    f"announcements in these sectors across Canada."
                )
        except Exception:
            pass

    return gaps[:5]  # Cap at 5 gap-fill agents


# ── Main orchestrator ───────────────────────────────────────────────────────

def run_research_agents(rss_items: list = None, conn=None,
                        skip_provinces: list = None) -> dict:
    """
    Run all research agents and return merged findings.

    Returns:
        {
            'findings': [...],           # All discovered projects/announcements
            'policy_developments': [...], # Federal policy items
            'province_context': {...},    # Per-province context summaries
            'federal_context': str,       # Federal context summary
            'gaps_investigated': int,
        }
    """
    rss_items = rss_items or []
    skip_provinces = skip_provinces or []
    today_str = date.today().strftime('%B %d, %Y')

    all_findings = []
    all_policy = []
    province_context = {}
    federal_context = ''

    # Build task list
    tasks = {}

    # Province discovery agents
    for prov in PROVINCES:
        if prov in skip_provinces:
            continue
        sweep_summary = _build_sweep_summary(rss_items, prov)
        prompt = _build_province_research_prompt(prov, today_str, sweep_summary)
        tasks[f'research_{prov}'] = {
            'prompt': prompt,
            'label': f'research-{prov[:2].lower()}',
            'type': 'province',
            'province': prov,
        }

    # Federal/national agent
    sweep_summary = _build_sweep_summary(rss_items)
    prompt = _build_federal_research_prompt(today_str, sweep_summary)
    tasks['research_federal'] = {
        'prompt': prompt,
        'label': 'research-federal',
        'type': 'federal',
    }

    # Gap-filling agents
    gaps = _detect_gaps(rss_items, conn)
    for i, gap_desc in enumerate(gaps):
        prompt = _build_gap_prompt(gap_desc, today_str)
        tasks[f'gap_{i}'] = {
            'prompt': prompt,
            'label': f'research-gap-{i}',
            'type': 'gap',
        }

    total = len(tasks)
    print(f"  [Research Agents] Launching {total} agents "
          f"({MAX_WORKERS} parallel, Opus, {MAX_TURNS} max turns)...")

    # Execute agents
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for key, task in tasks.items():
            f = executor.submit(_call_research_agent, task['prompt'], task['label'])
            futures[f] = (key, task)

        completed = 0
        for future in as_completed(futures):
            key, task = futures[future]
            completed += 1
            try:
                result = future.result()
                if result and isinstance(result, dict):
                    results[key] = result
                    findings = result.get('findings', [])
                    print(f"    [{completed}/{total}] [OK] {key}: "
                          f"{len(findings)} findings")
                else:
                    print(f"    [{completed}/{total}] [WARN] {key}: empty response")
            except Exception as e:
                print(f"    [{completed}/{total}] [ERROR] {key}: {e}")

    # Merge results
    for key, result in results.items():
        task = tasks[key]
        findings = result.get('findings', [])

        # Tag each finding with discovery source
        for f in findings:
            f['discovery_source'] = 'research_agent'
            f.setdefault('province', task.get('province', ''))

        all_findings.extend(findings)

        if task['type'] == 'province':
            province_context[task['province']] = result.get('context', '')
        elif task['type'] == 'federal':
            federal_context = result.get('context', '')
            all_policy.extend(result.get('policy_developments', []))

    ok_count = sum(1 for v in results.values() if v)
    print(f"  [Research Agents] Complete: {ok_count}/{total} agents returned data, "
          f"{len(all_findings)} total findings, {len(all_policy)} policy items")

    return {
        'research_findings': all_findings,
        'research_policy': all_policy,
        'province_context': province_context,
        'federal_context': federal_context,
        'gaps_investigated': len(gaps),
    }


# ── Pipeline phase entry point ──────────────────────────────────────────────

def run(conn, context: dict, run_log) -> dict:
    """Pipeline phase entry point for research agents."""
    step_name = "research_agents"
    try:
        rss_items = context.get('rss_items', [])

        result = run_research_agents(
            rss_items=rss_items,
            conn=conn,
        )

        # Ingest findings into project database
        if result.get('research_findings'):
            try:
                from project_sync import upsert_flat_projects
                from project_dedup import deduplicate_projects
                from project_schema import normalize_project_type, is_brownfield

                flat_projects = []
                for f in result['research_findings']:
                    if not f.get('source_url'):
                        continue
                    ptype = normalize_project_type(f.get('project_type', ''))
                    flat_projects.append({
                        'name': f.get('name', ''),
                        'province': f.get('province', ''),
                        'sector': f.get('sector', 'infrastructure'),
                        'value': f.get('value', 'Not disclosed'),
                        'status': f.get('status', 'Proposed'),
                        'description': f.get('description', ''),
                        'discovery_source': 'research_agent',
                        'source_url': f.get('source_url', ''),
                        'source_title': f.get('source_title', ''),
                        'sources': [{'id': 1, 'title': f.get('source_title', ''),
                                     'url': f.get('source_url', '')}],
                        'announced': f.get('date_announced', date.today().isoformat()),
                        'project_type': ptype,
                        'is_brownfield': is_brownfield(ptype),
                    })

                if flat_projects:
                    deduped = deduplicate_projects(flat_projects)
                    verified = [p for p in deduped if p.get('evidence') and len(p['evidence']) > 0]
                    if verified:
                        sync_result = upsert_flat_projects(conn, verified)
                        new = sync_result.get('new', 0) if sync_result else 0
                        updated = sync_result.get('updated', 0) if sync_result else 0
                        print(f"  [Research DB] {new} new projects, {updated} updated")
                    else:
                        print(f"  [Research DB] {len(flat_projects)} findings, "
                              f"none passed URL gate after dedup")
            except Exception as e:
                print(f"  [Research DB] Ingest failed (non-critical): {e}")

        run_log.log_step(step_name)
        return result

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Research agents failed: {e}")
        traceback.print_exc()
        run_log.log_error(step_name, e, recovered=True)
        return {}
