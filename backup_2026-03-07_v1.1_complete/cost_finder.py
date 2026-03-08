"""
cost_finder.py — Targeted Gemini queries to find dollar values for projects
discovered without a cost estimate.

Reuses the async Gemini grounded search pattern from compound_discovery.py.
Runs after project upsert in update_dashboard.py.

Priority within enrichment budget: cost-finding runs FIRST because value is
the single most important missing field for analysis.
"""

import asyncio
import aiohttp
import json
import re
import os
import sys
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
MAX_CONCURRENT = 10          # slightly lower than compound discovery
RETRY_DELAY = 60
MAX_COST_QUERIES_PER_RUN = 60
COST_SEARCH_COOLDOWN_DAYS = 14
MAX_ATTEMPTS_BEFORE_UNFINDABLE = 3

# Values that mean "no value"
_NO_VALUE = {'', '—', 'not disclosed', 'unknown', 'n/a', 'c$0m', 'tbd',
             'not available', 'undisclosed'}

COST_SYSTEM_PROMPT = """You are a financial research assistant specializing in Canadian infrastructure and capital projects. For the project described in the query, find its estimated cost, budget, or investment value.

Search government budget documents, procurement awards, news articles, environmental assessment filings, corporate filings, securities disclosures, and municipal development applications.

Respond with ONLY a JSON object (no markdown fences) in this format:
{
  "value_millions": 650,
  "currency": "CAD",
  "value_type": "estimate",
  "source_description": "Government of Alberta press release, March 2026",
  "notes": "Phase 1 of 2; total project estimated at $1.2B"
}

Rules:
- value_millions: the total project value in millions of Canadian dollars (e.g. 650 for $650M, 1200 for $1.2B)
- value_type: one of "estimate", "approved_budget", "contract_award", "actual_cost", "funding_announcement"
- If a range is given, use the midpoint and note the range in "notes"
- If multiple phases, sum all phases for value_millions and note the breakdown
- If the value is in USD, convert roughly to CAD (multiply by 1.37)
- If NO cost information is findable, respond: {"value_millions": null, "notes": "No cost information found"}
"""


# ── Candidate Selection ───────────────────────────────────────────────────────

def select_projects_needing_cost(db, max_candidates=MAX_COST_QUERIES_PER_RUN):
    """Select projects from Firestore that have no dollar value.

    Priority:
    1. New projects (discovered this week) — highest urgency
    2. Projects with government sources — likely findable
    3. Projects with multiple evidence sources — well-confirmed
    4. Older projects — lower priority

    Returns list of (doc_id, project_dict) tuples, sorted by priority.
    """
    candidates = []
    now = datetime.utcnow()

    for doc in db.collection("projects").stream():
        data = doc.to_dict()
        doc_id = doc.id

        # Skip if already has a value
        val = (data.get("value") or "").strip().lower()
        if val and val not in _NO_VALUE:
            continue

        # Skip cancelled
        if (data.get("status") or "").lower() in ("cancelled", "canceled"):
            continue

        # Skip if marked unfindable
        if data.get("cost_unfindable"):
            continue

        # Skip if cost-searched recently
        last_search = data.get("last_cost_search")
        if last_search:
            if isinstance(last_search, str):
                try:
                    last_search = datetime.fromisoformat(
                        last_search.replace("Z", "+00:00").replace("+00:00", "")
                    )
                except ValueError:
                    last_search = None
            if last_search and (now - last_search).days < COST_SEARCH_COOLDOWN_DAYS:
                continue

        # Priority scoring
        priority = 100
        attempts = data.get("cost_search_attempts", 0)
        evidence_count = len(data.get("evidence", []))
        has_gov = data.get("has_government_source", False)

        # New projects get highest priority
        first_tracked = data.get("firstTracked") or data.get("announced") or ""
        if first_tracked:
            try:
                ft = datetime.fromisoformat(str(first_tracked)[:10])
                if (now - ft).days <= 7:
                    priority = 1000
            except ValueError:
                pass

        if has_gov:
            priority = max(priority, 500)
        if evidence_count >= 2:
            priority = max(priority, 300)

        # Penalize repeated failures
        priority -= attempts * 50

        if priority > 0:
            candidates.append((doc_id, data, priority))

    candidates.sort(key=lambda x: x[2], reverse=True)
    result = [(doc_id, data) for doc_id, data, _ in candidates[:max_candidates]]
    return result


# ── Query Builders ────────────────────────────────────────────────────────────

def build_cost_query(doc_id, project):
    """Build a Gemini grounded search query to find a project's dollar value."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    proponent = project.get("proponent", "")
    sector = project.get("sector", "")
    # Sector may be a NAICS code like "23" — only use if it's a readable name
    if sector and len(sector) <= 5 and sector.replace('-', '').isdigit():
        sector = ""

    location = f"{cma}, {province}" if cma else province
    proponent_str = f" by {proponent}" if proponent else ""
    sector_str = f" ({sector})" if sector else ""

    query_text = (
        f"What is the estimated cost, budget, or investment value of the "
        f"{name} project{proponent_str} in {location}, Canada{sector_str}? "
        f"Search for: total project cost, estimated construction value, "
        f"approved budget, capital expenditure, contract value, government "
        f"funding amount. The cost may appear in news articles, government "
        f"budget documents, procurement awards, environmental assessment "
        f"filings, corporate announcements, or municipal development "
        f"applications."
    )
    return {
        "query": query_text,
        "type": "cost_finding",
        "doc_id": doc_id,
        "project_name": name,
        "province": province,
        "city": cma or None,
        "language": "en",
    }


def build_cost_query_french(doc_id, project):
    """French-language cost query for QC and NB projects."""
    name = project.get("name", "Unknown")
    province = project.get("province", "")
    cma = project.get("cma", "")
    proponent = project.get("proponent", "")

    location = f"{cma}, {province}" if cma else province
    proponent_str = f" par {proponent}" if proponent else ""

    query_text = (
        f"Quel est le coût estimé, le budget ou la valeur du projet "
        f"{name}{proponent_str} à {location}, Canada ? "
        f"Recherchez : coût total du projet, valeur estimée de la construction, "
        f"budget approuvé, dépenses en capital, valeur du contrat, montant du "
        f"financement gouvernemental."
    )
    return {
        "query": query_text,
        "type": "cost_finding",
        "doc_id": doc_id,
        "project_name": name,
        "province": province,
        "city": cma or None,
        "language": "fr",
    }


# ── Cost Extraction ──────────────────────────────────────────────────────────

def extract_cost_from_response(response_text, grounding_urls=None):
    """Parse cost information from a Gemini response.

    Returns dict with:
        value_millions, value_low, value_high, value_notes,
        source_urls, found (bool)
    """
    result = {
        "value_millions": None,
        "value_low": None,
        "value_high": None,
        "value_notes": "",
        "source_urls": grounding_urls or [],
        "found": False,
    }

    if not response_text:
        return result

    # Try JSON parse first
    text = response_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)

    # Find JSON object
    obj_start = text.find('{')
    if obj_start >= 0:
        # Find matching close brace
        depth = 0
        for i in range(obj_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    json_str = text[obj_start:i + 1]
                    try:
                        data = json.loads(json_str)
                        val = data.get("value_millions")
                        if val is not None and val != 0:
                            result["value_millions"] = float(val)
                            result["found"] = True
                            result["value_notes"] = data.get("notes", "")
                            return result
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
                    break

    # Fall back to regex extraction from natural language
    values_found = []

    # "$X billion" / "C$X billion" / "$XB"
    for m in re.finditer(
        r'(?:C?\$|CAD\s*)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:billion|B\b)',
        text, re.IGNORECASE
    ):
        val = float(m.group(1).replace(',', '')) * 1000
        values_found.append(val)

    # "$X million" / "C$X million" / "$XM"
    for m in re.finditer(
        r'(?:C?\$|CAD\s*)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:million|M\b)',
        text, re.IGNORECASE
    ):
        val = float(m.group(1).replace(',', ''))
        values_found.append(val)

    if not values_found:
        return result

    # Use the largest value (total project cost is usually the biggest)
    values_found.sort(reverse=True)
    result["value_millions"] = values_found[0]
    result["found"] = True

    # Check for range language
    range_match = re.search(
        r'between\s+(?:C?\$)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:million|billion|M|B)'
        r'\s+and\s+(?:C?\$)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:million|billion|M|B)',
        text, re.IGNORECASE
    )
    if range_match:
        low = float(range_match.group(1).replace(',', ''))
        high = float(range_match.group(2).replace(',', ''))
        if 'billion' in range_match.group(0).lower():
            low *= 1000
            high *= 1000
        result["value_low"] = low
        result["value_high"] = high
        result["value_millions"] = (low + high) / 2
        result["value_notes"] = f"Range: C${low:.0f}M–C${high:.0f}M"

    # Check for revision language
    if re.search(r'revis|updat|increas|escal|overrun|now estimat', text, re.I):
        result["value_notes"] += " (revised estimate)" if result["value_notes"] else "Revised estimate"

    return result


def _format_value(millions):
    """Convert millions float to display string matching existing format."""
    if millions is None or millions <= 0:
        return "Not disclosed"
    if millions >= 1000:
        return f"C${millions / 1000:.1f}B"
    return f"C${millions:.0f}M"


# ── Async Gemini Queries ─────────────────────────────────────────────────────

async def _query_tavily_cost(semaphore, query_obj):
    """Send one cost-finding query to Tavily search."""
    from tavily_search import tavily_cost_search

    async with semaphore:
        name = query_obj.get("project_name", "")
        province = query_obj.get("province", "")
        city = query_obj.get("city")

        # Build a concise search query from the verbose Gemini-style query
        if not name:
            # Fallback: extract key terms from the query text
            name = query_obj.get("query", "")[:80]

        try:
            results = await tavily_cost_search(name, province, city)
        except Exception as e:
            return {"error": str(e), "query": query_obj}

        if not results:
            cost = extract_cost_from_response("", [])
            return {"cost": cost, "query": query_obj, "raw_text": ""}

        # Combine all result content for cost extraction
        combined_text = "\n\n".join(
            r.get("content", "") for r in results if r.get("content")
        )
        source_urls = [
            r.get("url") for r in results if r.get("url")
        ]

        cost = extract_cost_from_response(combined_text, source_urls)
        return {
            "cost": cost,
            "query": query_obj,
            "raw_text": combined_text[:500],
        }


# ── Main Orchestrator ────────────────────────────────────────────────────────

async def run_cost_finding(db):
    """Run cost-finding queries for valueless projects.

    Returns dict with counts: {found, not_found, unfindable, errors}.
    """
    from tavily_search import TAVILY_API_KEY as _tav_key
    if not _tav_key:
        print("  [COST] No TAVILY_API_KEY — skipping cost-finding.")
        return {"found": 0, "not_found": 0, "unfindable": 0, "errors": 0}

    candidates = select_projects_needing_cost(db)
    if not candidates:
        print("  [COST] No valueless projects to search.")
        return {"found": 0, "not_found": 0, "unfindable": 0, "errors": 0}

    # Build queries
    queries = []
    for doc_id, project in candidates:
        province = (project.get("province") or "").lower()
        queries.append(build_cost_query(doc_id, project))
        # Add French query for QC/NB projects
        if province in ("quebec", "qc", "new brunswick", "nb"):
            queries.append(build_cost_query_french(doc_id, project))

    # Cap total queries
    if len(queries) > MAX_COST_QUERIES_PER_RUN:
        queries = queries[:MAX_COST_QUERIES_PER_RUN]

    print(f"  [COST] Running {len(queries)} cost-finding queries "
          f"for {min(len(candidates), MAX_COST_QUERIES_PER_RUN)} projects...")

    # Run async via Tavily
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_query_tavily_cost(semaphore, q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Group results by doc_id (QC/NB projects may have 2 results)
    by_doc = {}
    errors = 0
    for r in results:
        if isinstance(r, Exception):
            errors += 1
            continue
        if r.get("error"):
            errors += 1
            if errors <= 3:
                logger.warning(f"  [COST] Error: {r['error'][:100]}")
            continue

        doc_id = r["query"]["doc_id"]
        cost = r["cost"]
        # Keep the result with value (or the last one if none found)
        if doc_id not in by_doc or (cost["found"] and not by_doc[doc_id]["found"]):
            by_doc[doc_id] = cost

    # Apply results to Firestore
    found = 0
    not_found = 0
    unfindable = 0
    now_iso = datetime.utcnow().isoformat()

    for doc_id, project in candidates:
        cost = by_doc.get(doc_id)
        if cost is None:
            continue

        doc_ref = db.collection("projects").document(doc_id)

        if cost["found"] and cost["value_millions"] and cost["value_millions"] > 0:
            # Value found — update project
            value_str = _format_value(cost["value_millions"])
            updates = {
                "value": value_str,
                "value_millions": cost["value_millions"],
                "last_cost_search": now_iso,
                "cost_search_attempts": 0,
                "lastUpdated": now_iso,
            }
            if cost.get("value_low"):
                updates["value_low_millions"] = cost["value_low"]
            if cost.get("value_high"):
                updates["value_high_millions"] = cost["value_high"]
            if cost.get("value_notes"):
                updates["value_notes"] = cost["value_notes"]

            # Add grounding URLs as evidence
            try:
                existing = doc_ref.get().to_dict() or {}
                evidence = existing.get("evidence", [])
                existing_urls = {e.get("url") for e in evidence if e.get("url")}
                for url in cost.get("source_urls", []):
                    if url and url.startswith("http") and url not in existing_urls:
                        evidence.append({
                            "url": url,
                            "name": "",
                            "date": now_iso[:10],
                            "source_type": "cost_finding",
                        })
                        existing_urls.add(url)
                updates["evidence"] = evidence
                updates["evidence_count"] = len(evidence)

                # Recalculate confidence (having a value boosts it)
                try:
                    from project_dedup import calculate_confidence
                    temp = {**existing, **updates}
                    updates["confidence"] = calculate_confidence(temp)
                except Exception:
                    pass
            except Exception:
                pass

            doc_ref.update(updates)
            found += 1
            print(f"    Found: {project.get('name', '?')[:45]} -> {value_str}")
        else:
            # Not found — increment attempts
            attempts = project.get("cost_search_attempts", 0) + 1
            updates = {
                "last_cost_search": now_iso,
                "cost_search_attempts": attempts,
            }
            if attempts >= MAX_ATTEMPTS_BEFORE_UNFINDABLE:
                updates["cost_unfindable"] = True
                updates["value_notes"] = "Cost not found after 3 search attempts"
                unfindable += 1
            else:
                not_found += 1
            doc_ref.update(updates)

    print(f"  [COST] Results: {found} found, {not_found} pending, "
          f"{unfindable} unfindable, {errors} errors")

    return {"found": found, "not_found": not_found,
            "unfindable": unfindable, "errors": errors}


# ── Synchronous Wrapper ──────────────────────────────────────────────────────

def run_cost_search(db):
    """Synchronous wrapper for run_cost_finding(). Handles event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context (e.g., Jupyter)
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            print("  [COST] Cannot run in existing event loop (install nest_asyncio)")
            return {"found": 0, "not_found": 0, "unfindable": 0, "errors": 0}
        return loop.run_until_complete(run_cost_finding(db))
    else:
        return asyncio.run(run_cost_finding(db))
