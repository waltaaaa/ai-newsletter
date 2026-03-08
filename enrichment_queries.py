"""
enrichment_queries.py — Automated project enrichment using spare Gemini capacity.

Post-processing step: after weekly discovery, runs targeted follow-up queries
to fill data gaps in newly found or updated projects.

Uses remaining Gemini free tier capacity (~100 queries/day, leaving 292/day
headroom from the 500/day limit after compound discovery uses ~108/day).

Two enrichment types:
  1. Detail fill — get missing fields (value, proponent, status)
  2. Investigation — follow up on signals from permits, lobbyists, anomalies
"""

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

MAX_ENRICHMENT_QUERIES_PER_DAY = 55  # Budget: 500 - 403 core = 97 spare; shared with missed(20) + policy(1)

ENRICHMENT_SYSTEM_PROMPT = """You are a Canadian infrastructure research assistant.
Given a query about a specific Canadian capital project, provide factual details.
Respond in JSON format:
{
  "projects": [{
    "name": "Project Name",
    "province": "XX",
    "cma": "City",
    "value": "$XXM" or "$X.XB",
    "value_numeric": 123,
    "proponent": "Company Name",
    "status": "Proposed|Approved|Under Construction|Completed|Delayed|Cancelled",
    "description": "One-sentence summary",
    "naics_2digit": "23",
    "source_url": "https://...",
    "source_title": "Source name"
  }]
}
Only include information you can verify. If uncertain, omit the field."""


async def run_enrichment_queries(new_projects: list[dict],
                                 investigation_signals: list[dict] | None = None
                                 ) -> list[dict]:
    """Run enrichment queries using spare Gemini capacity.

    Args:
        new_projects: project dicts from this week's discovery with gaps
        investigation_signals: signal dicts from permit anomalies, lobbyist
                              registries, etc.

    Returns:
        list of enriched project dicts to merge back into Firestore
    """
    from gemini_engine import query_one

    if investigation_signals is None:
        investigation_signals = []

    queries = []

    # ── Type 1: Detail fill for projects with missing fields ──────────────
    for project in new_projects:
        missing = []
        if not project.get("value_millions") and not project.get("value"):
            missing.append("estimated value in Canadian dollars")
        if not project.get("proponent"):
            missing.append("developer or proponent company")
        if not project.get("status") or project.get("status") == "Proposed":
            missing.append("current status (proposed, approved, under construction, completed, delayed)")
        if not project.get("description"):
            missing.append("one-sentence description")

        if not missing:
            continue

        name = project.get("name", "Unknown")
        prov = project.get("province", "")
        cma = project.get("cma", "")
        location = f"{cma}, {prov}" if cma else prov

        queries.append({
            "query": (
                f"What is the current status and details of the {name} project "
                f"in {location}, Canada? Specifically, what is the "
                f"{', '.join(missing)}? "
                f"Provide the source URL for your information."
            ),
            "type": "detail_fill",
            "project_name": name,
            "project_province": prov,
        })

    # ── Type 2: Investigation of signals ──────────────────────────────────
    for signal in investigation_signals:
        suggested = signal.get("suggested_query")
        if suggested:
            queries.append({
                "query": suggested,
                "type": "investigation",
                "signal_source": signal.get("source", "unknown"),
            })

    # ── Cap at daily limit ────────────────────────────────────────────────
    if len(queries) > MAX_ENRICHMENT_QUERIES_PER_DAY:
        investigations = [q for q in queries if q["type"] == "investigation"]
        detail_fills = [q for q in queries if q["type"] == "detail_fill"]
        queries = investigations[:50] + detail_fills[:50]
        logger.info(f"Capped enrichment at {len(queries)} queries "
                    f"(limit: {MAX_ENRICHMENT_QUERIES_PER_DAY})")

    if not queries:
        logger.info("No enrichment queries needed")
        return []

    # ── Run queries ───────────────────────────────────────────────────────
    logger.info(f"Running {len(queries)} enrichment queries")
    semaphore = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        tasks = [
            query_one(session, semaphore, q, ENRICHMENT_SYSTEM_PROMPT)
            for q in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.debug(f"Enrichment query {i} failed: {result}")
            continue
        if result.get("error"):
            continue

        text = result.get("text", "")
        grounding_urls = result.get("grounding_urls", [])
        projects = _parse_enrichment_response(text, queries[i], grounding_urls)
        enriched.extend(projects)

    logger.info(f"Enrichment produced {len(enriched)} project updates")
    return enriched


def _parse_enrichment_response(text: str, query: dict,
                                grounding_urls: list[dict]) -> list[dict]:
    """Parse Gemini enrichment response into project dicts."""
    import json
    import re
    from datetime import date
    from project_schema import normalize_project_type, is_brownfield

    projects = []

    # Try to extract JSON from response
    json_match = re.search(r'\{[\s\S]*"projects"[\s\S]*\}', text)
    if not json_match:
        return []

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return []

    for p in data.get("projects", []):
        name = p.get("name", "").strip()
        if not name:
            continue

        value_str = p.get("value", "")
        value_numeric = p.get("value_numeric")

        # Build evidence from grounding URLs
        evidence = []
        source_url = p.get("source_url", "")
        if source_url:
            evidence.append({
                "url": source_url,
                "name": p.get("source_title", "Enrichment source"),
                "source_type": "enrichment",
                "authority": "media",
            })
        for gu in grounding_urls:
            if gu.get("url") and gu["url"] != source_url:
                evidence.append({
                    "url": gu["url"],
                    "name": gu.get("title", ""),
                    "source_type": "enrichment_grounding",
                    "authority": "media",
                })

        ptype = normalize_project_type(p.get("project_type", ""))

        projects.append({
            "name": name,
            "province": p.get("province", query.get("project_province", "")),
            "cma": p.get("cma", ""),
            "sector": p.get("naics_2digit", "Other"),
            "naics_code": p.get("naics_2digit", ""),
            "tags": [],
            "value": value_str or "Not disclosed",
            "value_millions": value_numeric,
            "status": p.get("status", "Proposed"),
            "description": p.get("description", ""),
            "discovery_source": "gemini_enrichment",
            "source_url": source_url,
            "source_title": p.get("source_title", ""),
            "sources": [{"id": 1, "title": p.get("source_title", ""),
                         "url": source_url}],
            "announced": date.today().isoformat(),
            "completionDate": "",
            "project_type": ptype,
            "is_brownfield": is_brownfield(ptype),
            "_enrichment_type": query.get("type", "detail_fill"),
            "_enrichment_query": query.get("query", ""),
            "_evidence": evidence,
            "confidence": 0.5,
        })

    return projects


def run_enrichment_sync(new_projects: list[dict],
                        investigation_signals: list[dict] | None = None
                        ) -> list[dict]:
    """Synchronous wrapper for pipeline integration."""
    return asyncio.run(run_enrichment_queries(new_projects, investigation_signals))
