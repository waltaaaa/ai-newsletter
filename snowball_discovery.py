"""
snowball_discovery.py — Adaptive multi-pass discovery.

Pass 1: Standard 421-query sweep (nim_deep_search.run_deep_search).
Pass 2+: K2.5 analyzes discovered projects and generates targeted follow-up queries.

Example chain:
  Pass 1: "Alberta energy infrastructure projects 2026"
    -> Discovers: "Pembina Pipeline Expansion, $1.2B"
  Pass 2 (K2.5 generated): "Pembina Pipeline Expansion regulatory approval IAAC"
    -> Discovers: EA details, timeline, connected compressor stations
  Pass 3 (K2.5 generated): "Alberta natural gas compressor station construction 2025 2026"
    -> Discovers: 3 related compressor station projects not in original query list

Stop conditions:
  - max_passes reached (default 3 from SNOWBALL_MAX_PASSES)
  - follow-up queries return < 5 new projects (diminishing returns)
  - NIM circuit breaker trips

Dependencies: Phase 0 (nim_client), Phase 1 (searxng_search), Phase 2 (nim_deep_search).
"""

import json
import logging
import re
from collections import Counter
from difflib import SequenceMatcher

from nim_client import get_client
from nim_deep_search import (
    JSON_INSTRUCTIONS,
    extract_json_array,
    normalize_project,
    dedup_key,
    search_and_extract,
)
from pipeline_config import (
    NIM_THINKING_MODE,
    SNOWBALL_DISCOVERY_ENABLED,
    SNOWBALL_MAX_PASSES,
)
import service_health

logger = logging.getLogger(__name__)

MIN_NEW_PROJECTS = 5        # stop if a pass finds fewer than this
FOLLOWUP_QUERIES_PER_PASS = 50  # max queries K2.5 generates per pass
QUERY_DEDUP_THRESHOLD = 0.75    # fuzzy match threshold for query dedup


# ── Query dedup ───────────────────────────────────────────────────────────

def _is_duplicate_query(query: str, prior_queries: set[str]) -> bool:
    """Check if a query is a fuzzy duplicate of any prior query."""
    query_lower = query.lower().strip()
    for prior in prior_queries:
        if SequenceMatcher(None, query_lower, prior).ratio() >= QUERY_DEDUP_THRESHOLD:
            return True
    return False


# ── Follow-up query generation ────────────────────────────────────────────

def _summarize_projects(projects: list[dict], max_items: int = 80) -> str:
    """Summarize discovered projects for the K2.5 follow-up prompt."""
    lines = []
    for p in projects[:max_items]:
        name = p.get("project_name", "Unknown")
        prov = p.get("province", "")
        sector = p.get("sector", "")
        value = p.get("estimated_value", "")
        status = p.get("status", "")
        line = f"- {name} ({prov}, {sector}, {value}, {status})"
        lines.append(line)
    return "\n".join(lines)


def _coverage_summary(projects: list[dict]) -> str:
    """Generate coverage stats by province and sector."""
    prov_counts = Counter(p.get("province", "Unknown") for p in projects)
    sector_counts = Counter(p.get("sector", "Unknown") for p in projects)

    lines = ["Province coverage:"]
    for prov, count in prov_counts.most_common():
        lines.append(f"  {prov}: {count}")
    lines.append("\nSector coverage:")
    for sec, count in sector_counts.most_common():
        lines.append(f"  {sec}: {count}")
    return "\n".join(lines)


def generate_followup_queries(
    discovered_projects: list[dict],
    pass_number: int,
    prior_queries: set[str],
) -> list[str]:
    """Send discovered projects to K2.5, get targeted follow-up search queries.

    Args:
        discovered_projects: Projects found in prior passes.
        pass_number: Current pass number (2, 3, ...).
        prior_queries: Set of lowercased queries already executed.

    Returns:
        List of new search query strings (deduplicated against prior queries).
    """
    client = get_client()

    if pass_number == 2:
        # Pass 2: follow threads from discovered projects
        summary = _summarize_projects(discovered_projects)
        prompt = (
            "You are a research assistant helping discover Canadian capital projects. "
            "In our initial search, we found these projects:\n\n"
            f"{summary}\n\n"
            "Based on these discoveries, generate targeted web search queries to find:\n"
            "1. Related projects, expansions, or additional phases of these projects\n"
            "2. Connected infrastructure (e.g., if we found a pipeline, search for "
            "compressor stations, processing plants, or export terminals)\n"
            "3. Other projects by the same proponents in the same regions\n"
            "4. Projects mentioned in source articles but not yet captured\n"
            "5. Regulatory filings, environmental assessments, or permit applications "
            "for the largest projects\n\n"
            f"Generate {FOLLOWUP_QUERIES_PER_PASS} short, specific web search queries. "
            "Each query should be concise (5-15 words) and likely to find real Canadian "
            "capital projects on Google/Bing.\n\n"
            "Return a JSON array of query strings: [\"query1\", \"query2\", ...]"
        )
    else:
        # Pass 3+: fill coverage gaps
        coverage = _coverage_summary(discovered_projects)
        prompt = (
            "You are a research assistant helping discover Canadian capital projects. "
            f"After {pass_number - 1} passes of searching, we have found "
            f"{len(discovered_projects)} projects.\n\n"
            f"{coverage}\n\n"
            "Based on our coverage, generate search queries to fill gaps:\n"
            "1. Sectors with fewer than expected projects for their economic importance\n"
            "2. Provinces with thin coverage relative to their economic size\n"
            "3. Project types we may have missed (decommissions, remediations, "
            "conversions, adaptive reuse)\n"
            "4. Recently announced projects or upcoming milestones\n"
            "5. Indigenous-led projects, Crown corporation capital plans, "
            "and defence infrastructure\n\n"
            f"Generate {FOLLOWUP_QUERIES_PER_PASS} short, specific web search queries. "
            "Each should be 5-15 words and target specific gaps.\n\n"
            "Return a JSON array of query strings: [\"query1\", \"query2\", ...]"
        )

    try:
        response = client.chat_sync(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate web search queries for discovering Canadian "
                        "capital projects. Return only a JSON array of query strings."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            thinking=False,  # no thinking needed for query generation
            max_tokens=4096,
            temperature=0.5,
        )
    except Exception as e:
        logger.error(f"K2.5 follow-up query generation failed: {e}")
        return []

    # Parse the response
    raw_queries = _parse_query_list(response)
    if not raw_queries:
        logger.warning("K2.5 returned no follow-up queries")
        return []

    # Dedup against prior queries
    new_queries = []
    for q in raw_queries[:FOLLOWUP_QUERIES_PER_PASS]:
        q = q.strip()
        if not q or len(q) < 10:
            continue
        if _is_duplicate_query(q, prior_queries):
            continue
        new_queries.append(q)
        prior_queries.add(q.lower().strip())

    logger.info(
        f"Pass {pass_number}: K2.5 generated {len(raw_queries)} queries, "
        f"{len(new_queries)} after dedup"
    )
    return new_queries


def _parse_query_list(response: str) -> list[str]:
    """Parse K2.5 response into a list of query strings."""
    if not response:
        return []

    # Try JSON array extraction
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', response)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            if isinstance(result, list):
                return [str(q) for q in result if q]
        except json.JSONDecodeError:
            pass

    bracket_match = re.search(r'\[[\s\S]*\]', response)
    if bracket_match:
        try:
            result = json.loads(bracket_match.group(0))
            if isinstance(result, list):
                return [str(q) for q in result if q]
        except json.JSONDecodeError:
            pass

    # Fallback: split by newlines (numbered or bulleted lists)
    lines = response.strip().split("\n")
    queries = []
    for line in lines:
        line = re.sub(r'^[\d\.\-\*\•]+\s*', '', line).strip()
        line = line.strip('"\'')
        if line and len(line) >= 10:
            queries.append(line)
    return queries


# ── Snowball sweep orchestrator ───────────────────────────────────────────

def run_snowball_sweep(
    conn=None,
    max_passes: int = None,
    thinking: bool = None,
    max_queries_pass1: int = 0,
) -> list[dict]:
    """Multi-pass discovery loop.

    Pass 1: Standard 421-query sweep (nim_deep_search.run_deep_search).
    Pass 2..N: K2.5-generated follow-up queries via search_and_extract.

    Args:
        conn: SQLite connection (reserved for future DB dedup).
        max_passes: Override SNOWBALL_MAX_PASSES config.
        thinking: Override NIM_THINKING_MODE config.
        max_queries_pass1: Limit Pass 1 queries (0 = all, useful for testing).

    Returns:
        List of all normalized project dicts across all passes.
    """
    if max_passes is None:
        max_passes = SNOWBALL_MAX_PASSES
    if thinking is None:
        thinking = NIM_THINKING_MODE

    all_projects: list[dict] = []
    seen_keys: set[str] = set()
    prior_queries: set[str] = set()

    # ── Pass 1: Standard sweep ────────────────────────────────────────
    logger.info(f"Snowball Pass 1: running standard 421-query sweep...")

    from nim_deep_search import run_deep_search, build_all_queries, _to_search_query

    # Collect pass 1 queries for dedup tracking
    pass1_queries = build_all_queries()
    for q in pass1_queries:
        prior_queries.add(_to_search_query(q).lower().strip())

    pass1_projects = run_deep_search(
        conn=conn,
        max_queries=max_queries_pass1,
        thinking=thinking,
    )

    for p in pass1_projects:
        key = dedup_key(p)
        if key not in seen_keys:
            seen_keys.add(key)
            all_projects.append(p)

    logger.info(
        f"Snowball Pass 1 complete: {len(all_projects)} unique projects"
    )

    # ── Pass 2..N: Follow-up queries ──────────────────────────────────
    for pass_num in range(2, max_passes + 1):
        # Check circuit breaker
        health = service_health.get()
        if not health.is_available("nvidia_nim"):
            logger.warning("NIM circuit breaker tripped — stopping snowball")
            break

        logger.info(f"Snowball Pass {pass_num}: generating follow-up queries...")

        followup_queries = generate_followup_queries(
            all_projects, pass_num, prior_queries,
        )

        if not followup_queries:
            logger.info(f"Pass {pass_num}: no follow-up queries generated, stopping")
            break

        logger.info(
            f"Pass {pass_num}: executing {len(followup_queries)} follow-up queries..."
        )

        pass_new = 0
        for i, search_q in enumerate(followup_queries):
            # Build a query_info dict compatible with search_and_extract
            query_info = {
                "search_query": search_q,  # direct SearXNG query (overrides _to_search_query)
                "query": (
                    f"Extract all Canadian capital projects from these search results. "
                    f"The search was: \"{search_q}\"\n\n{JSON_INSTRUCTIONS}"
                ),
                "province": "National",
                "sector": "snowball",
                "type": "snowball",
            }

            try:
                raw_projects = search_and_extract(query_info, thinking=thinking)
            except Exception as e:
                logger.warning(f"Pass {pass_num} query {i+1} failed: {e}")
                continue

            if not raw_projects:
                continue

            for proj in raw_projects:
                normalized = normalize_project(proj, "National", "snowball")
                if not normalized["project_name"]:
                    continue
                key = dedup_key(normalized)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_projects.append(normalized)
                pass_new += 1

        logger.info(
            f"Snowball Pass {pass_num} complete: {pass_new} new projects "
            f"(total: {len(all_projects)})"
        )

        # Stop if diminishing returns
        if pass_new < MIN_NEW_PROJECTS:
            logger.info(
                f"Pass {pass_num} found only {pass_new} new projects "
                f"(< {MIN_NEW_PROJECTS}), stopping snowball"
            )
            break

    logger.info(
        f"Snowball sweep complete: {len(all_projects)} total unique projects "
        f"across {min(max_passes, pass_num) if 'pass_num' in dir() else 1} passes"
    )
    return all_projects
