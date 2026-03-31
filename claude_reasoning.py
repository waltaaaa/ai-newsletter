"""
claude_reasoning.py -- Claude reasoning engine (Claude Code agents).

ALL reasoning tasks route through this module:
- Interpreting trends and connecting patterns
- Generating narrative briefings
- Pre-event analysis with historical context
- Policy implication assessment
- Cross-reference insight generation
- Gap analysis
- Extraction recovery
- Dedup QA
- Signal investigation
- Monthly meta-analysis

Default mode: Claude Code subprocess (user subscription, $0 API cost).
Set REASONING_AGENT_MODE=api in .env for Anthropic API fallback.
"""

import os
import asyncio
import logging
import shutil
import tempfile
import subprocess

import aiohttp

from pipeline_config import SONNET_MODEL, OPUS_MODEL, CLAUDE_COST_CAP_USD, MODEL_RATES

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = SONNET_MODEL  # default for extraction/reasoning
OPUS_WRITING_MODEL = OPUS_MODEL  # for all writing calls
CLAUDE_ENDPOINT = "https://api.anthropic.com/v1/messages"

# Agent mode: 'claude_code' (default, $0) or 'api' (Anthropic API)
REASONING_AGENT_MODE = os.environ.get('REASONING_AGENT_MODE', 'claude_code')
REASONING_AGENT_MODEL = os.environ.get('REASONING_AGENT_MODEL', 'sonnet')

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

# Retry config for rate limits (429) and overloaded (529)
CLAUDE_MAX_RETRIES = 4
CLAUDE_RETRY_BASE_DELAY = 30  # seconds — Claude rate limits are longer than Gemini's

# ── Per-run cost tracking (shared across all calls in this module) ────────────
_cumulative_cost_usd = 0.0
_cumulative_tokens = {"input": 0, "output": 0}


def reset_cost_tracker():
    """Reset cumulative cost tracker (call at start of each pipeline run)."""
    global _cumulative_cost_usd, _cumulative_tokens
    _cumulative_cost_usd = 0.0
    _cumulative_tokens = {"input": 0, "output": 0}


def get_cumulative_cost():
    """Return current cumulative cost and token counts."""
    return _cumulative_cost_usd, _cumulative_tokens.copy()


# ── Claude Code subprocess ─────────────────────────────────────────────────────

def _call_claude_code_sync(prompt: str, label: str = "reasoning",
                           model: str = '') -> str | None:
    """Call Claude via Claude Code CLI subprocess. Returns raw text or None.

    Uses the user's Claude subscription — $0 API cost.
    """
    use_model = model or REASONING_AGENT_MODEL
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                     encoding='utf-8') as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        if not _CLAUDE_CLI:
            raise FileNotFoundError("claude CLI not resolved")
        cmd = [_CLAUDE_CLI, '-p', '--output-format', 'text',
               '--model', use_model, '--max-turns', '1']
        logger.info(f"  [Claude Code] [{label}] Calling {use_model}...")
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=180, encoding='utf-8', env=_CLAUDE_ENV,
        )
        if result.returncode != 0:
            stderr = (result.stderr or '')[:500]
            logger.warning(f"  [Claude Code] [{label}] Exit code {result.returncode}: {stderr}")
            return None
        text = (result.stdout or '').strip()
        if not text:
            logger.warning(f"  [Claude Code] [{label}] Empty response")
            return None
        logger.info(f"  [Claude Code] [{label}] OK ({len(text)} chars)")
        return text
    except subprocess.TimeoutExpired:
        logger.warning(f"  [Claude Code] [{label}] Timeout (180s)")
        return None
    except FileNotFoundError:
        logger.warning(f"  [Claude Code] [{label}] 'claude' CLI not found — falling back to API")
        return None
    except Exception as e:
        logger.warning(f"  [Claude Code] [{label}] Error: {e}")
        return None
    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


async def reason_with_claude(system_prompt, user_prompt, max_tokens=4096):
    """Send a reasoning request to Claude.

    Default: Claude Code subprocess ($0). Fallback: Anthropic API.
    No web search, no tools -- pure analysis of provided context.

    Args:
        system_prompt: Role and instructions
        user_prompt: Data and specific question
        max_tokens: Response length limit

    Returns:
        str: Claude's analysis text, or None on failure
    """
    # ── Claude Code mode (default, $0) ──────────────────────────
    if REASONING_AGENT_MODE == 'claude_code':
        combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        text = await asyncio.get_event_loop().run_in_executor(
            None, _call_claude_code_sync, combined, "reason"
        )
        if text:
            return text
        # If Claude Code failed and API key exists, fall through to API
        if not ANTHROPIC_API_KEY:
            return None
        logger.info("  [Claude Code] Falling back to API...")

    # ── API mode (fallback) ─────────────────────────────────────
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set, skipping Claude reasoning")
        return None

    global _cumulative_cost_usd
    if _cumulative_cost_usd >= CLAUDE_COST_CAP_USD:
        logger.warning(f"Cost cap exceeded (${_cumulative_cost_usd:.4f} >= "
                        f"${CLAUDE_COST_CAP_USD:.2f}) — skipping Claude call")
        return None

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

    for attempt in range(CLAUDE_MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    CLAUDE_ENDPOINT, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        usage = data.get("usage", {})
                        in_tok = usage.get("input_tokens", 0)
                        out_tok = usage.get("output_tokens", 0)
                        cost = (in_tok * 3 + out_tok * 15) / 1_000_000
                        _cumulative_cost_usd += cost
                        _cumulative_tokens["input"] += in_tok
                        _cumulative_tokens["output"] += out_tok
                        content = data.get("content")
                        if not content or not isinstance(content, list) or len(content) == 0:
                            logger.warning("Claude API returned empty content array")
                            return None
                        text_val = content[0].get("text") if isinstance(content[0], dict) else None
                        if text_val is None:
                            logger.warning("Claude API response missing 'text' field in content[0]")
                            return None
                        return text_val
                    elif resp.status in (429, 529) and attempt < CLAUDE_MAX_RETRIES:
                        delay = CLAUDE_RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            f"Claude rate limited ({resp.status}), "
                            f"waiting {delay}s (attempt {attempt + 1}/{CLAUDE_MAX_RETRIES})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        text = await resp.text()
                        logger.error(f"Claude API error {resp.status}: {text[:300]}")
                        return None
        except asyncio.TimeoutError:
            if attempt < CLAUDE_MAX_RETRIES:
                delay = CLAUDE_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"Claude API timeout, retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                continue
            logger.warning("Claude API timeout (all retries exhausted)")
            return None
        except Exception as e:
            logger.warning(f"Claude API exception: {e}")
            return None
    return None


async def reason_with_claude_tracked(system_prompt, user_prompt, task_name,
                                     max_tokens=4096, model=None):
    """Reasoning call with token/cost tracking.

    Default: Claude Code subprocess ($0). Fallback: Anthropic API.

    Args:
        model: Override model. Defaults to CLAUDE_MODEL (Sonnet).
               Pass OPUS_WRITING_MODEL for writing tasks.

    Returns:
        dict with text, input_tokens, output_tokens, cost_usd -- or None
    """
    # ── Claude Code mode (default, $0) ──────────────────────────
    if REASONING_AGENT_MODE == 'claude_code':
        # Map API model names to Claude Code model names
        use_model = model or CLAUDE_MODEL
        cc_model = REASONING_AGENT_MODEL  # default: 'sonnet'
        if use_model and 'opus' in use_model.lower():
            cc_model = 'opus'
        elif use_model and 'haiku' in use_model.lower():
            cc_model = 'haiku'

        combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        text = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _call_claude_code_sync(combined, task_name, model=cc_model)
        )
        if text:
            logger.info(f"  [Claude Code] [{task_name}] Complete ($0 — subscription)")
            return {
                "text": text,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        # If Claude Code failed and API key exists, fall through to API
        if not ANTHROPIC_API_KEY:
            return None
        logger.info(f"  [Claude Code] [{task_name}] Falling back to API...")

    # ── API mode (fallback) ─────────────────────────────────────
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set, skipping Claude reasoning")
        return None

    use_model = model or CLAUDE_MODEL

    global _cumulative_cost_usd
    if _cumulative_cost_usd >= CLAUDE_COST_CAP_USD:
        logger.warning(f"Cost cap exceeded (${_cumulative_cost_usd:.4f} >= "
                        f"${CLAUDE_COST_CAP_USD:.2f}) — skipping [{task_name}]")
        return None

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": use_model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    for attempt in range(CLAUDE_MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    CLAUDE_ENDPOINT, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        usage = data.get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)

                        # Cost: use per-model rates
                        rates = MODEL_RATES.get(use_model, {'input': 3.0, 'output': 15.0})
                        cost = (input_tokens * rates['input'] + output_tokens * rates['output']) / 1_000_000
                        _cumulative_cost_usd += cost
                        _cumulative_tokens["input"] += input_tokens
                        _cumulative_tokens["output"] += output_tokens

                        logger.info(
                            f"Claude [{task_name}]: {input_tokens} in / "
                            f"{output_tokens} out = ${cost:.4f}"
                        )

                        content = data.get("content")
                        if not content or not isinstance(content, list) or len(content) == 0:
                            logger.warning(f"Claude API [{task_name}] returned empty content array")
                            return None
                        text_val = content[0].get("text") if isinstance(content[0], dict) else None
                        if text_val is None:
                            logger.warning(f"Claude API [{task_name}] response missing 'text' field")
                            return None
                        return {
                            "text": text_val,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "cost_usd": cost,
                        }
                    elif resp.status in (429, 529) and attempt < CLAUDE_MAX_RETRIES:
                        delay = CLAUDE_RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            f"Claude rate limited ({resp.status}) [{task_name}], "
                            f"waiting {delay}s (attempt {attempt + 1}/{CLAUDE_MAX_RETRIES})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        text = await resp.text()
                        logger.error(f"Claude API error {resp.status}: {text[:300]}")
                        return None
        except asyncio.TimeoutError:
            if attempt < CLAUDE_MAX_RETRIES:
                delay = CLAUDE_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"Claude API timeout [{task_name}], retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                continue
            logger.warning(f"Claude API timeout [{task_name}] (all retries exhausted)")
            return None
        except Exception as e:
            logger.warning(f"Claude API exception [{task_name}]: {e}")
            return None
    return None


def reason_sync(system_prompt, user_prompt, task_name="sync", max_tokens=4096, model=None):
    """Synchronous wrapper for reason_with_claude_tracked."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                reason_with_claude_tracked(system_prompt, user_prompt,
                                           task_name, max_tokens, model=model)
            )
        else:
            return asyncio.run(
                reason_with_claude_tracked(system_prompt, user_prompt,
                                           task_name, max_tokens, model=model)
            )
    except RuntimeError:
        return asyncio.run(
            reason_with_claude_tracked(system_prompt, user_prompt,
                                       task_name, max_tokens, model=model)
        )


# ═══════════════════════════════════════════════════════════════════
# Pipeline reasoning tasks (formerly in pro_*.py, now consolidated)
# ═══════════════════════════════════════════════════════════════════

import json
from datetime import date, datetime

try:
    from pipeline_store import parse_json_response
except ImportError:
    def parse_json_response(text):
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    return None
            return None


# ── Gap Analysis ──────────────────────────────────────────────────

GAP_ANALYSIS_SYSTEM = """You are an expert analyst of the Canadian capital projects landscape.
You have deep knowledge of each province's economic profile, major industries,
and typical project pipeline.

Your task: review the projects found by a web search for a given province and
identify what's MISSING. Major provinces should have projects across most sectors.
If a province with significant mining activity shows no mining projects, that's a gap.
If a province with a housing crisis shows no residential projects, that's suspicious.

For each gap identified, explain why you'd expect projects in that sector and
suggest a specific, targeted search query that would find them.

Return JSON:
{
  "province": "XX",
  "projects_found": 8,
  "sectors_represented": ["infrastructure", "healthcare"],
  "gaps": [
    {
      "sector": "mining",
      "reasoning": "Ontario has the Ring of Fire and significant mining activity in Sudbury/Timmins, but no mining projects appeared",
      "suggested_query": "Ring of Fire mining projects Ontario 2025-2026 chromite development",
      "confidence": "high"
    }
  ],
  "overall_assessment": "Coverage appears incomplete — 3 major sectors missing"
}"""


def analyze_provincial_gaps_sync(sweep_results_by_province):
    """Analyze provincial sweep results for coverage gaps.

    Args:
        sweep_results_by_province: dict of {province_name: [project_dicts]}

    Returns:
        list of follow-up query dicts
    """
    follow_up_queries = []

    for province, projects in sweep_results_by_province.items():
        project_summary = []
        for p in projects:
            val = p.get("value", "Not disclosed")
            project_summary.append(
                f"- {p.get('name', 'Unknown')}: {p.get('naics_2digit') or p.get('sector', 'unknown')} sector, "
                f"{val}, status: {p.get('status', 'unknown')}"
            )

        summary_text = "\n".join(project_summary) if project_summary else "(No projects found)"

        user_prompt = (
            f"Province: {province}\n"
            f"Web search found {len(projects)} projects this week:\n\n"
            f"{summary_text}\n\n"
            f"Analyze this list. What major project types or sectors are missing "
            f"that you would expect for this province? What should we search for next week?"
        )

        result = reason_sync(GAP_ANALYSIS_SYSTEM, user_prompt, task_name="gap_analysis")
        response = result["text"] if result else None
        data = parse_json_response(response)

        if data:
            for gap in data.get("gaps", []):
                if gap.get("suggested_query") and gap.get("confidence") in ("high", "medium"):
                    follow_up_queries.append({
                        "query": gap["suggested_query"],
                        "province": province,
                        "sector": gap.get("sector", "unknown"),
                        "source": "gap_analysis",
                        "reasoning": gap.get("reasoning", ""),
                        "language": "en",
                        "geo_tier": "province",
                    })

            gaps_found = len(data.get("gaps", []))
            high_med = len([g for g in data.get("gaps", [])
                           if g.get("confidence") in ("high", "medium")])
            logger.info(
                f"  {province}: {len(projects)} found, "
                f"{gaps_found} gaps identified, {high_med} follow-up queries"
            )
        else:
            logger.warning(f"  {province}: gap analysis returned no parseable result")

    print(f"  [CLAUDE] Gap analysis: {len(follow_up_queries)} follow-up queries "
          f"from {len(sweep_results_by_province)} provinces")
    return follow_up_queries


# ── Extraction Recovery ───────────────────────────────────────────

RECOVERY_SYSTEM = """You are a Canadian capital projects analyst. You are reading a news article
or government press release that our automated system flagged as likely containing
a capital project, but our extraction model could not identify a specific project.

Read the article carefully. Look for:
1. Explicit project mentions (by name, location, or description)
2. Implied projects (funding announcements that imply construction will happen)
3. Referenced projects (mentioned in passing but not the article's main topic)
4. Future projects (announced plans, feasibility studies, requests for proposals)

For each project found, return JSON:
{
  "projects": [
    {
      "name": "Project name (or best descriptive name if unnamed)",
      "proponent": "Company or organization",
      "province": "Full province name",
      "city": "City name if known",
      "value_millions": null or number,
      "status": "Proposed|Approved|Under Construction|Completed|Delayed|Cancelled",
      "sector": "sector description",
      "description": "1-2 sentences describing what the project is, who is building/operating it, and its scope or purpose",
      "confidence_notes": "Why this was hard to extract",
      "official_ids": {}
    }
  ]
}

If the article references any official project identifiers — such as an IAAC registry number,
a provincial EA reference number, a CER hearing order, a municipal development application ID,
a SEDAR filing number, or a building permit number — extract them into the "official_ids" object
with keys like "iaac", "cer", "provincial_ea", "municipal_app", "sedar", "permit".
If no identifiers are present, return an empty object {}.

If genuinely no capital project exists in this article, return {"projects": [], "reason": "explanation"}.
Be thorough but do not fabricate projects."""


def recover_failed_extractions_sync(failed_articles):
    """Re-process articles that produced no projects.

    Args:
        failed_articles: list of dicts with keys: title, summary, url, source_name, province

    Returns:
        list of flat project dicts ready for upsert_flat_projects()
    """
    if not failed_articles:
        return []

    recovered = []
    today = date.today().isoformat()

    for article in failed_articles:
        title = article.get("title", "")
        summary = article.get("summary", "")
        url = article.get("url", "")
        province = article.get("province", "Canada")

        text_parts = []
        if title:
            text_parts.append(f"Headline: {title}")
        if url:
            text_parts.append(f"Source URL: {url}")
        if summary:
            text_parts.append(f"Summary: {summary[:4000]}")

        if not text_parts:
            continue

        user_prompt = (
            "\n\n".join(text_parts)
            + "\n\nOur basic extraction model found no structured projects in this article. "
            "Please read carefully and identify any capital projects mentioned or implied."
        )

        result = reason_sync(RECOVERY_SYSTEM, user_prompt, task_name="extraction_recovery")
        response = result["text"] if result else None
        data = parse_json_response(response)

        if data and data.get("projects"):
            for project in data["projects"]:
                name = (project.get("name") or "").strip()
                if not name or len(name) < 3:
                    continue

                prov = project.get("province") or province
                if prov == "Canada":
                    prov = ""

                val_m = project.get("value_millions")
                if val_m and isinstance(val_m, (int, float)):
                    if val_m >= 1000:
                        value_str = f"C${val_m/1000:.1f}B"
                    else:
                        value_str = f"C${val_m:.0f}M"
                else:
                    value_str = "Not disclosed"

                flat = {
                    "name": name,
                    "province": prov,
                    "cma": project.get("city", ""),
                    "sector": project.get("sector", "Other"),
                    "value": value_str,
                    "status": project.get("status", "Proposed"),
                    "proponent": project.get("proponent", ""),
                    "description": project.get("description", ""),
                    "discovery_source": "claude_recovered",
                    "discovery_sources": ["claude_recovered"],
                    "confidence": 0.4,
                    "source_url": url,
                    "sources": [{"url": url, "title": title}] if url else [],
                    "evidence": [{
                        "url": url,
                        "name": article.get("source_name", ""),
                        "date": today,
                        "source_type": "claude_recovered",
                    }] if url else [],
                    "evidence_count": 1 if url else 0,
                    "announced": today,
                    "official_ids": project.get("official_ids", {}),
                }
                recovered.append(flat)

            logger.info(
                f"  Recovered {len(data['projects'])} projects from: "
                f"{title[:60]}"
            )

    print(f"  [CLAUDE] Extraction recovery: {len(recovered)} projects "
          f"from {len(failed_articles)} failed articles")
    return recovered


# ── Dedup Analysis ────────────────────────────────────────────────

DEDUP_SYSTEM = """You are a Canadian capital projects data quality analyst. You are reviewing
a list of newly discovered projects to identify duplicates that our automated
name-matching system may have missed.

Look for:
1. Same project, different names (e.g., "Portage Place Redevelopment" and "Downtown Winnipeg Mixed-Use Transformation")
2. Parent-child relationships (e.g., "Ontario Line" and "Ontario Line Pape Station")
3. Cross-province duplicates (e.g., an interprovincial project listed once for each province)
4. Phase duplicates (e.g., "Project X Phase 1" and "Project X" counted separately)
5. Implausible entries (hallucinated or garbled project names)

Return JSON:
{
  "duplicate_groups": [
    {
      "reason": "Same project, different names from different sources",
      "projects": ["Project Name A (index 3)", "Project Name B (index 17)"],
      "recommended_canonical_name": "Best name to use",
      "confidence": "high | medium | low"
    }
  ],
  "parent_child": [
    {
      "parent": "Ontario Line (index 5)",
      "children": ["Ontario Line Pape Station (index 22)"],
      "recommendation": "Keep parent as main record, note children as subcomponents"
    }
  ],
  "suspicious_entries": [
    {
      "project": "Name (index X)",
      "reason": "Name appears garbled / no such project exists / likely hallucinated"
    }
  ],
  "cross_province": [
    {
      "projects": ["Pipeline X - Alberta (index 8)", "Pipeline X - BC (index 14)"],
      "recommendation": "Merge into single interprovincial project"
    }
  ]
}"""


def analyze_dedup_sync(new_projects):
    """Send this week's new projects for intelligent dedup review.

    Args:
        new_projects: list of project dicts discovered this week

    Returns:
        dict with duplicate_groups, parent_child, suspicious_entries, cross_province
    """
    if not new_projects:
        return None

    project_list = []
    for i, p in enumerate(new_projects):
        province = p.get("province", "??")
        city = p.get("cma", "") or p.get("city", "")
        value = p.get("value", "?")
        sector = p.get("sector", "?")
        status = p.get("status", "?")
        project_list.append(
            f"[{i}] {p.get('name', 'Unknown')} | "
            f"{province}, {city} | {value} | {sector} | {status}"
        )

    all_results = {
        "duplicate_groups": [],
        "parent_child": [],
        "suspicious_entries": [],
        "cross_province": [],
    }

    chunk_size = 100
    for start in range(0, len(project_list), chunk_size):
        chunk = project_list[start:start + chunk_size]

        user_prompt = (
            f"This week's newly discovered projects "
            f"({len(chunk)} of {len(project_list)} total):\n\n"
            + "\n".join(chunk)
            + "\n\nIdentify any duplicates, parent-child relationships, "
            "cross-province duplicates, or suspicious entries."
        )

        result = reason_sync(DEDUP_SYSTEM, user_prompt, task_name="dedup_qa")
        response = result["text"] if result else None
        data = parse_json_response(response)

        if data:
            for key in all_results:
                all_results[key].extend(data.get(key, []))

    total_flags = sum(len(v) for v in all_results.values())
    print(f"  [CLAUDE] Dedup analysis: {len(all_results['duplicate_groups'])} duplicate groups, "
          f"{len(all_results['parent_child'])} parent-child, "
          f"{len(all_results['suspicious_entries'])} suspicious, "
          f"{len(all_results['cross_province'])} cross-province")

    return all_results if total_flags > 0 else None


def store_dedup_results(conn, results):
    """Store dedup analysis results in SQLite for review.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)
    """
    if not results:
        return
    try:
        if hasattr(conn, 'execute'):
            from db import save_dashboard_state
            save_dashboard_state(conn, "dedup_analysis", {
                "results": results,
                "analyzed_at": datetime.utcnow().isoformat(),
                "total_flags": sum(len(v) for v in results.values()),
            })
        else:
            # Legacy Firestore path
            conn.collection("pipeline_state").document("dedup_analysis").set({
                "results": results,
                "analyzed_at": datetime.utcnow().isoformat(),
                "total_flags": sum(len(v) for v in results.values()),
            })
    except Exception as e:
        logger.warning(f"Failed to store dedup results: {e}")


# ── Meta-Analysis ─────────────────────────────────────────────────

META_SYSTEM = """You are a strategic analyst reviewing a Canadian capital projects database.
You have deep knowledge of Canada's economy, infrastructure needs, and project landscape.

Analyze the database summary and identify:
1. SECTOR GAPS: sectors with fewer projects than expected given economic activity
2. GEOGRAPHIC GAPS: provinces or cities underrepresented relative to their GDP
3. TYPE GAPS: is greenfield overrepresented vs brownfield or vice versa?
4. STATUS GAPS: are we finding announcements but missing completions? Or vice versa?
5. VALUE GAPS: is the average project value skewed? Are we missing small or large projects?
6. TEMPORAL GAPS: are there periods with suspiciously low discovery rates?
7. SEARCH STRATEGY IMPROVEMENTS: specific new query types, keywords, or sources to add

Be specific and actionable. General advice is not useful. Name specific sectors,
provinces, project types, and suggest exact search queries to close gaps.

Return JSON:
{
  "sector_gaps": [{"sector": "...", "reasoning": "...", "suggested_query": "..."}],
  "geographic_gaps": [{"province": "...", "reasoning": "...", "suggested_query": "..."}],
  "type_gaps": [{"gap": "...", "reasoning": "..."}],
  "status_gaps": [{"gap": "...", "reasoning": "..."}],
  "value_gaps": [{"gap": "...", "reasoning": "..."}],
  "temporal_gaps": [],
  "recommended_new_queries": [{"query": "...", "province": "...", "sector": "..."}],
  "recommended_new_sources": [{"source": "...", "url": "...", "reasoning": "..."}],
  "overall_coverage_grade": "A/B/C/D/F",
  "top_3_priorities": ["...", "...", "..."]
}"""


def run_meta_analysis_sync(conn):
    """Monthly meta-analysis of the full project database.

    Args:
        conn: sqlite3.Connection from db.py (or Firestore client for
              backward compatibility — detected by duck-typing)

    Returns:
        dict with coverage analysis, or None on failure
    """
    stats = {
        "total_projects": 0,
        "by_province": {},
        "by_sector": {},
        "by_status": {},
        "by_discovery_source": {},
        "with_value": 0,
        "without_value": 0,
        "stale_count": 0,
    }

    values = []

    try:
        if hasattr(conn, 'execute'):
            from db import get_all_projects
            all_projects = get_all_projects(conn)
        else:
            all_projects = [doc.to_dict() for doc in conn.collection("projects").stream()]

        for data in all_projects:
            stats["total_projects"] += 1

            prov = data.get("province", "Unknown")
            sector = data.get("sector", "Unknown")
            status = data.get("status", "Unknown")
            source = data.get("discovery_source", "Unknown")

            stats["by_province"][prov] = stats["by_province"].get(prov, 0) + 1
            stats["by_sector"][sector] = stats["by_sector"].get(sector, 0) + 1
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_discovery_source"][source] = stats["by_discovery_source"].get(source, 0) + 1

            val_str = data.get("value", "")
            if val_str and val_str != "Not disclosed":
                stats["with_value"] += 1
                try:
                    if "B" in val_str:
                        v = float(val_str.replace("C$", "").replace("B", "").strip()) * 1000
                    elif "M" in val_str:
                        v = float(val_str.replace("C$", "").replace("M", "").strip())
                    else:
                        v = None
                    if v:
                        values.append(v)
                except (ValueError, TypeError):
                    pass
            else:
                stats["without_value"] += 1

            if data.get("is_stale"):
                stats["stale_count"] += 1
    except Exception as e:
        logger.warning(f"Failed to read projects for meta-analysis: {e}")
        return None

    if stats["total_projects"] == 0:
        return None

    stats["avg_value_millions"] = round(sum(values) / len(values)) if values else 0
    stats["median_value_millions"] = round(sorted(values)[len(values) // 2]) if values else 0
    stats["value_pct_disclosed"] = round(100 * stats["with_value"] / stats["total_projects"], 1)

    user_prompt = (
        f"Database summary as of {datetime.utcnow().strftime('%Y-%m-%d')}:\n\n"
        f"{json.dumps(stats, indent=2)}\n\n"
        f"Analyze this database for coverage gaps and recommend specific improvements "
        f"to our search and tracking strategy."
    )

    result = reason_sync(META_SYSTEM, user_prompt, task_name="meta_analysis")
    response = result["text"] if result else None
    analysis = parse_json_response(response)

    if analysis:
        print(f"  [CLAUDE] Meta-analysis: grade={analysis.get('overall_coverage_grade')}")
        print(f"  [CLAUDE] Top priorities: {analysis.get('top_3_priorities')}")
        print(f"  [CLAUDE] New queries: {len(analysis.get('recommended_new_queries', []))}, "
              f"new sources: {len(analysis.get('recommended_new_sources', []))}")
        return analysis

    logger.warning("Meta-analysis returned no parseable result")
    return None


def store_meta_analysis(conn, analysis):
    """Store meta-analysis results.

    Args:
        conn: sqlite3.Connection from db.py (preferred) or Firestore client
              (backward compatible — detected by duck-typing)
        analysis: parsed meta-analysis dict
    """
    if not analysis:
        return
    try:
        if hasattr(conn, 'execute'):
            from db import save_dashboard_state
            save_dashboard_state(conn, "monthly_meta_analysis", {
                "analysis": analysis,
                "analyzed_at": datetime.utcnow().isoformat(),
                "grade": analysis.get("overall_coverage_grade", "?"),
            })
        else:
            conn.collection("pipeline_state").document("monthly_meta_analysis").set({
                "analysis": analysis,
                "analyzed_at": datetime.utcnow().isoformat(),
                "grade": analysis.get("overall_coverage_grade", "?"),
            })
    except Exception as e:
        logger.warning(f"Failed to store meta-analysis: {e}")


# ── Signal Investigation ──────────────────────────────────────────

SIGNAL_SYSTEM = """You are a Canadian capital projects intelligence analyst. You are reviewing
web search results that were triggered by an investigation signal — either a
lobbyist registration suggesting a company is seeking project approval, or a
building permit anomaly suggesting unusual construction activity in a municipality.

Your job: determine whether this signal represents:
1. A genuinely NEW project not yet in our database
2. An update to an EXISTING project (provide the likely existing project name)
3. A FALSE SIGNAL (the lobbying/permits are unrelated to a capital project)

Return JSON:
{
  "signal_type": "new_project | existing_update | false_signal",
  "confidence": "high | medium | low",
  "reasoning": "Why you reached this conclusion",
  "project": { "name": "...", "province": "...", "sector": "...", "value_millions": null, "status": "..." } or null,
  "existing_project_name": "Name if this is an update to a known project" or null,
  "recommended_action": "add_to_database | merge_with_existing | discard | monitor_next_week"
}"""


def analyze_signals_sync(investigation_results):
    """Analyze signal investigation results.

    Args:
        investigation_results: list of dicts with:
            signal: the original signal (lobbyist reg or permit anomaly)
            flash_results: what Flash found when it searched

    Returns:
        list of actionable findings (new projects, updates, follow-ups)
    """
    if not investigation_results:
        return []

    findings = []

    for investigation in investigation_results:
        signal = investigation.get("signal", {})
        flash_projects = investigation.get("flash_results", {}).get("projects", [])

        flash_summary = json.dumps(flash_projects, indent=2)[:6000]

        user_prompt = (
            f"INVESTIGATION SIGNAL:\n"
            f"Type: {signal.get('type', 'unknown')}\n"
            f"Source: {signal.get('source', '')}\n"
            f"Details: {signal.get('details', '')}\n"
            f"Province: {signal.get('province', '')}\n"
            f"Date: {signal.get('date', '')}\n\n"
            f"SEARCH RESULTS:\n"
            f"{flash_summary}\n\n"
            f"Based on the signal and search results, what is your assessment? "
            f"Is this a new project, an update to an existing one, or a false signal?"
        )

        result = reason_sync(SIGNAL_SYSTEM, user_prompt, task_name="signal_investigation")
        response = result["text"] if result else None
        data = parse_json_response(response)

        if data:
            if data.get("signal_type") == "new_project" and \
               data.get("confidence") in ("high", "medium"):
                project = data.get("project", {})
                if project:
                    project["_discovery_tier"] = "signal_analysis"
                    findings.append({
                        "action": "add_to_database",
                        "project": project,
                        "reasoning": data.get("reasoning", ""),
                    })
            elif data.get("signal_type") == "existing_update":
                findings.append({
                    "action": "merge_with_existing",
                    "existing_name": data.get("existing_project_name"),
                    "update_data": data.get("project"),
                    "reasoning": data.get("reasoning", ""),
                })

            logger.info(
                f"  Signal: {signal.get('type')} -> {data.get('signal_type')} "
                f"({data.get('confidence')}) — {data.get('recommended_action')}"
            )

    logger.info(f"Signal analysis: {len(findings)} actionable from "
                f"{len(investigation_results)} investigations")
    return findings


# ── Selective Extraction ──────────────────────────────────────

SELECTIVE_EXTRACT_SYSTEM = """You are a Canadian capital projects data extractor. You are reading
a high-quality source document (government registry, corporate press release, or procurement award)
that has already been flagged as likely containing a capital project.

Extract ALL capital projects mentioned. For each project return structured data.

Return JSON:
{
  "projects": [
    {
      "name": "Official project name",
      "aliases": ["alternative names if any"],
      "proponent": "Company or organization responsible",
      "proponent_role": "developer | owner | contractor | funder",
      "province": "Full province or territory name",
      "municipality": "City or town",
      "cma": "Census Metropolitan Area if applicable",
      "address": "Street address if available",
      "sector": "sector description",
      "subsector": "more specific description",
      "capex_exact": null,
      "capex_low": null,
      "capex_high": null,
      "capex_currency": "CAD",
      "status": "Proposed|Approved|Under Construction|Completed|Cancelled|Paused",
      "event_type": "announcement|approval|construction_start|completion|cancellation|update",
      "date_announced": "",
      "date_expected_start": "",
      "date_expected_completion": "",
      "official_ids": {},
      "evidence_snippet": "Key quote from source (1-2 sentences)"
    }
  ]
}

If no capital project exists, return {"projects": [], "reason": "explanation"}.
Be thorough but never fabricate. Extract exact dollar values when stated."""


def _select_top_documents(documents, max_docs=40):
    """Select top documents by signal quality for Claude extraction.

    Priority order:
    1. Government registry sources (tier 1/5/8)
    2. Corporate press releases with dollar values
    3. Procurement awards
    4. Documents with high Gemini classification confidence
    """
    scored = []
    for doc in documents:
        score = 0
        url = (doc.get('url') or '').lower()
        title = (doc.get('title') or '').lower()
        text = (doc.get('text') or doc.get('summary') or '').lower()
        combined = title + ' ' + text

        # Government sources get highest priority
        gov_domains = ('.gc.ca', 'canada.ca', '.gov.', 'eao.gov', 'iaac-aeic')
        if any(d in url for d in gov_domains):
            score += 50

        # Dollar values in title/text
        import re
        if re.search(r'\$[\d,.]+\s*[BMK]', combined, re.IGNORECASE):
            score += 30
        elif re.search(r'\$[\d,.]+\s*(billion|million)', combined, re.IGNORECASE):
            score += 30

        # Procurement / award keywords
        if any(kw in combined for kw in ('awarded', 'contract', 'procurement',
                                          'tender', 'rfp', 'bid')):
            score += 20

        # High Gemini confidence
        conf = doc.get('classification_confidence', 0)
        if isinstance(conf, (int, float)) and conf >= 0.85:
            score += 15

        # Press release indicators
        if any(kw in combined for kw in ('press release', 'news release',
                                          'announces', 'announced')):
            score += 10

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return [doc for _, doc in scored[:max_docs]]


def selective_extraction_sync(documents, flash_extractions=None):
    """Run Claude Sonnet extraction on top high-signal documents.

    Call AFTER Gemini Flash bulk extraction, BEFORE project sync.

    Args:
        documents: list of document dicts (url, title, text/summary)
        flash_extractions: optional dict mapping url -> flash extraction result,
                          for comparison

    Returns:
        list of project dicts ready for upsert, with confidence notes
    """
    top_docs = _select_top_documents(documents)
    if not top_docs:
        print("  [CLAUDE] Selective extraction: no high-signal documents found")
        return []

    print(f"  [CLAUDE] Selective extraction: {len(top_docs)} high-signal documents")
    extracted = []
    today = date.today().isoformat()

    for doc_idx, doc in enumerate(top_docs):
        if (doc_idx + 1) % 5 == 0 or doc_idx == 0:
            print(f"  [CLAUDE] Processing {doc_idx + 1}/{len(top_docs)}...")
        title = doc.get('title', '')
        url = doc.get('url', '')
        text = doc.get('text') or doc.get('summary', '')

        # Include metadata hints if available
        hints = ""
        meta_sectors = doc.get('meta_sectors', [])
        meta_provinces = doc.get('meta_provinces', [])
        if meta_sectors or meta_provinces:
            hint_parts = []
            if meta_sectors:
                hint_parts.append(f"Sector hints: {', '.join(meta_sectors)}")
            if meta_provinces:
                hint_parts.append(f"Province hints: {', '.join(meta_provinces)}")
            hints = '\n'.join(hint_parts) + "\n(Hints from source metadata — verify against content)\n\n"

        user_prompt = (
            f"Source URL: {url}\n"
            f"Headline: {title}\n"
            f"{hints}"
            f"Text:\n{text[:4000]}\n\n"
            f"Extract all capital projects mentioned in this document."
        )

        result = reason_sync(SELECTIVE_EXTRACT_SYSTEM, user_prompt,
                             task_name="selective_extraction", max_tokens=4096)
        response = result["text"] if result else None
        data = parse_json_response(response)

        if not data or not data.get("projects"):
            continue

        for project in data["projects"]:
            name = (project.get("name") or "").strip()
            if not name or len(name) < 3:
                continue

            # Build capex string
            capex = project.get("capex_exact")
            if not capex:
                capex = project.get("capex_low")
            if capex and isinstance(capex, (int, float)):
                if capex >= 1_000_000_000:
                    value_str = f"C${capex/1e9:.1f}B"
                elif capex >= 1_000_000:
                    value_str = f"C${capex/1e6:.0f}M"
                else:
                    value_str = f"C${capex/1e3:.0f}K"
            else:
                value_str = "Not disclosed"

            # Compare with Flash extraction if available
            confidence = 0.5
            confidence_note = "claude_selective"
            if flash_extractions and url in flash_extractions:
                flash_proj = flash_extractions[url]
                # If both agree on name/province, higher confidence
                flash_name = (flash_proj.get("name") or "").lower()
                if flash_name and (
                    flash_name in name.lower() or name.lower() in flash_name
                ):
                    confidence = 0.7
                    confidence_note = "claude+flash_agree"
                else:
                    confidence = 0.6
                    confidence_note = "claude_selective_conflict"

            flat = {
                "name": name,
                "province": project.get("province", ""),
                "cma": project.get("cma") or project.get("municipality", ""),
                "sector": project.get("sector", "Other"),
                "value": value_str,
                "status": project.get("status", "Proposed"),
                "proponent": project.get("proponent", ""),
                "description": project.get("evidence_snippet", ""),
                "discovery_source": "claude_selective",
                "discovery_sources": ["claude_selective"],
                "confidence": confidence,
                "confidence_note": confidence_note,
                "source_url": url,
                "sources": [{"url": url, "title": title}] if url else [],
                "evidence": [{
                    "url": url,
                    "name": doc.get("source_name", ""),
                    "date": today,
                    "source_type": "claude_selective",
                }] if url else [],
                "evidence_count": 1 if url else 0,
                "announced": today,
                "official_ids": project.get("official_ids", {}),
            }
            extracted.append(flat)

    print(f"  [CLAUDE] Selective extraction: {len(extracted)} projects "
          f"from {len(top_docs)} documents")
    return extracted
