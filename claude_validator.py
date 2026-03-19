"""
claude_validator.py — Claude validation gate for high-value extracted projects.

K2.5 handles bulk extraction. Claude Sonnet reviews the top N new or updated
projects for accuracy before they reach the database.

This is NOT re-extraction. Claude receives the extracted project record alongside
source text and answers specific validation questions:
  1. Is the project name accurate and specific?
  2. Is the capital cost correct? (total vs. phase, CAD vs. USD, estimate vs. committed)
  3. Is the status classification correct?
  4. Is this actually a Canadian project? (not a Canadian company's foreign project)
  5. Is the sector classification correct?
  6. Are there red flags? (stale data, contradictory sources, speculative language)

Batched: 5 projects per Claude call. 30 projects = 6 API calls (~$0.06-0.12/week).

Usage:
    from claude_validator import validate_batch
    validated = await validate_batch(projects, source_texts, top_n=30)
"""

import asyncio
import json
import logging
import re
import threading

from claude_reasoning import reason_with_claude_tracked, CLAUDE_MODEL
from pipeline_config import CLAUDE_VALIDATION_ENABLED, CLAUDE_VALIDATION_TOP_N

logger = logging.getLogger(__name__)

BATCH_SIZE = 5  # projects per Claude call


# ── Priority ranking ──────────────────────────────────────────────────────

def _priority_score(project: dict) -> float:
    """Score a project for validation priority (higher = validate first).

    Priority:
      1. New projects not previously in database
      2. Projects with significant field changes
      3. Projects with highest capital cost
      4. Projects from lower-confidence sources
    """
    score = 0.0

    # New projects get highest priority
    if project.get("_is_new", True):
        score += 1000

    # Field changes
    if project.get("_has_changes"):
        score += 500

    # Capital cost (higher value = higher priority for validation)
    value = project.get("estimated_value") or project.get("value") or ""
    value_str = str(value).upper().replace(",", "").replace("$", "").replace("C", "")
    try:
        m = re.match(r'(\d+(?:\.\d+)?)\s*(B|M|K)?', value_str)
        if m:
            n = float(m.group(1))
            unit = m.group(2) or "M"
            if unit == "B":
                n *= 1000
            elif unit == "K":
                n /= 1000
            score += min(n, 5000)  # cap at $5B equivalent
    except (ValueError, AttributeError):
        pass

    # Lower confidence = higher validation priority
    conf = project.get("confidence", 0.5)
    score += (1.0 - conf) * 200

    return score


# ── Validation prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a data quality reviewer for a Canadian capital projects database. "
    "You validate extracted project records against their source text. "
    "Be precise and factual. Only flag issues you can verify from the provided text. "
    "Return valid JSON."
)


def _build_validation_prompt(batch: list[dict], source_texts: dict) -> str:
    """Build a validation prompt for a batch of projects."""
    projects_text = []
    for i, proj in enumerate(batch):
        proj_id = proj.get("project_name", f"Project_{i}")
        source = source_texts.get(proj_id, "")
        if not source:
            source = source_texts.get(i, "No source text available.")

        projects_text.append(
            f"### Project {i+1}: {proj.get('project_name', 'Unknown')}\n"
            f"Province: {proj.get('province', 'Unknown')}\n"
            f"City: {proj.get('city', '')}\n"
            f"Sector: {proj.get('sector', '')}\n"
            f"Estimated Value: {proj.get('estimated_value', 'Not disclosed')}\n"
            f"Status: {proj.get('status', 'Proposed')}\n"
            f"Proponent: {proj.get('proponent', '')}\n"
            f"Description: {proj.get('description', '')}\n"
            f"Source URL: {proj.get('source_url', '')}\n\n"
            f"Source text:\n{str(source)[:2000]}\n"
        )

    prompt = (
        "Validate these extracted project records against their source texts.\n\n"
        "For EACH project, check:\n"
        "1. Is the project name accurate and specific?\n"
        "2. Is the capital cost figure correct and attributed properly? "
        "(total vs. phase, CAD vs. USD, estimate vs. committed)\n"
        "3. Is the status classification correct? "
        "(Proposed / Approved / Under Construction / Completed / Paused / Cancelled)\n"
        "4. Is this actually a Canadian project? "
        "(not a Canadian company's foreign project)\n"
        "5. Is the sector classification correct?\n"
        "6. Are there red flags? "
        "(stale data, contradictory sources, speculative language)\n\n"
        + "\n---\n".join(projects_text) +
        "\n\nReturn a JSON array with one object per project:\n"
        "[\n"
        '  {\n'
        '    "project_index": 1,\n'
        '    "project_name": "...",\n'
        '    "validation_status": "confirmed" | "corrected" | "flagged",\n'
        '    "corrections": {"field_name": "corrected_value", ...} or {},\n'
        '    "notes": "Brief explanation of any issues found",\n'
        '    "confidence": 0.0-1.0\n'
        "  }\n"
        "]\n\n"
        "Use \"confirmed\" if the record is accurate. "
        "Use \"corrected\" if you found errors and can fix them. "
        "Use \"flagged\" if the project has serious issues (not Canadian, fabricated, etc.)."
    )
    return prompt


# ── Response parsing ──────────────────────────────────────────────────────

def _parse_validation_response(response: str) -> list[dict]:
    """Parse Claude's validation response into a list of validation results."""
    if not response:
        return []

    # Try JSON extraction
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    bracket_match = re.search(r'\[[\s\S]*\]', response)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except json.JSONDecodeError:
            pass

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    logger.warning(f"Could not parse validation response ({len(response)} chars)")
    return []


def _apply_validation(project: dict, validation: dict) -> dict:
    """Apply validation results to a project dict."""
    project["_validation_status"] = validation.get("validation_status", "confirmed")
    project["_validation_notes"] = validation.get("notes", "")
    project["_validation_confidence"] = validation.get("confidence", 0.5)

    corrections = validation.get("corrections", {})
    if corrections and isinstance(corrections, dict):
        project["_validation_corrections"] = corrections
        # Apply corrections to the project
        field_map = {
            "project_name": "project_name",
            "province": "province",
            "city": "city",
            "sector": "sector",
            "estimated_value": "estimated_value",
            "status": "status",
            "proponent": "proponent",
            "description": "description",
        }
        for field, value in corrections.items():
            if field in field_map and value:
                project[field_map[field]] = value
    else:
        project["_validation_corrections"] = {}

    return project


# ── Core validation ───────────────────────────────────────────────────────

async def validate_project(project: dict, source_text: str) -> dict:
    """Validate a single project. Wraps validate_batch for one project."""
    results = await validate_batch(
        [project],
        {project.get("project_name", ""): source_text},
        top_n=1,
    )
    return results[0] if results else project


async def validate_batch(
    projects: list[dict],
    source_texts: dict,
    top_n: int = None,
) -> list[dict]:
    """Validate top N projects by priority. Batches 5 projects per Claude call.

    Args:
        projects: List of extracted project dicts.
        source_texts: Dict mapping project_name (or index) -> source text.
        top_n: Number of projects to validate (default from config).

    Returns:
        All projects (validated ones have _validation_* fields added).
    """
    if not CLAUDE_VALIDATION_ENABLED:
        logger.info("Claude validation disabled")
        return projects

    if top_n is None:
        top_n = CLAUDE_VALIDATION_TOP_N

    if not projects:
        return projects

    # Rank by priority and select top N
    ranked = sorted(projects, key=_priority_score, reverse=True)
    to_validate = ranked[:top_n]
    skip_set = set(id(p) for p in projects) - set(id(p) for p in to_validate)

    logger.info(
        f"Claude validation: {len(to_validate)} projects selected "
        f"(of {len(projects)} total), {len(to_validate) // BATCH_SIZE + 1} API calls"
    )

    # Process in batches of BATCH_SIZE
    validated_count = 0
    for batch_start in range(0, len(to_validate), BATCH_SIZE):
        batch = to_validate[batch_start:batch_start + BATCH_SIZE]

        prompt = _build_validation_prompt(batch, source_texts)

        result = await reason_with_claude_tracked(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            task_name=f"validation_batch_{batch_start // BATCH_SIZE + 1}",
            max_tokens=4096,
        )

        if result is None:
            logger.warning(f"Validation batch {batch_start // BATCH_SIZE + 1} failed")
            # Mark as unvalidated
            for proj in batch:
                proj["_validation_status"] = "skipped"
            continue

        response_text = result.get("text", "") if isinstance(result, dict) else result
        validations = _parse_validation_response(response_text)

        # Apply validations to projects
        for val in validations:
            idx = val.get("project_index", 0) - 1  # 1-indexed in prompt
            if 0 <= idx < len(batch):
                _apply_validation(batch[idx], val)
                validated_count += 1

        # Mark any unmatched projects in batch
        for i, proj in enumerate(batch):
            if "_validation_status" not in proj:
                proj["_validation_status"] = "skipped"

    # Mark non-validated projects
    for proj in projects:
        if "_validation_status" not in proj:
            proj["_validation_status"] = "not_selected"

    confirmed = sum(1 for p in projects if p.get("_validation_status") == "confirmed")
    corrected = sum(1 for p in projects if p.get("_validation_status") == "corrected")
    flagged = sum(1 for p in projects if p.get("_validation_status") == "flagged")

    logger.info(
        f"Claude validation complete: {validated_count} validated "
        f"({confirmed} confirmed, {corrected} corrected, {flagged} flagged)"
    )

    return projects


# ── Sync wrapper ──────────────────────────────────────────────────────────

_sync_loop = None


def validate_batch_sync(
    projects: list[dict],
    source_texts: dict,
    top_n: int = None,
) -> list[dict]:
    """Synchronous wrapper for validate_batch."""
    global _sync_loop

    if _sync_loop is None or _sync_loop.is_closed():
        _sync_loop = asyncio.new_event_loop()
        t = threading.Thread(target=_sync_loop.run_forever, daemon=True)
        t.start()

    future = asyncio.run_coroutine_threadsafe(
        validate_batch(projects, source_texts, top_n), _sync_loop,
    )
    return future.result(timeout=300)
