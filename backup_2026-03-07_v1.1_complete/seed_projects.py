"""
seed_projects.py — Perplexity Sonar Pro + Claude Sonnet Project Seeder

Two-stage pipeline:
  1. Perplexity Sonar Pro  — web search, NAICS-targeted queries per province
  2. Claude Sonnet         — parse and structure results into project schema

Deduplicates against Firestore and within the current run.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import os
import time
from datetime import date, timedelta

import firebase_admin
from firebase_admin import credentials, firestore
import requests
import anthropic
from dotenv import load_dotenv

from project_sync import normalize_key, fuzzy_match

# ==========================================
# CONFIG & API KEYS
# ==========================================

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()

if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not found in environment or .env")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment or .env")

# Firebase init
if not firebase_admin._apps:
    service_account_info = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if service_account_info:
        cred = credentials.Certificate(json.loads(service_account_info))
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ==========================================
# PROVINCE CONFIG
# ==========================================

PROVINCE_CONFIG = [
    {"name": "Ontario",                 "threshold": "$996M", "tier": "large"},
    {"name": "Quebec",                  "threshold": "$513M", "tier": "large"},
    {"name": "Alberta",                 "threshold": "$394M", "tier": "large"},
    {"name": "British Columbia",        "threshold": "$357M", "tier": "large"},
    {"name": "Saskatchewan",            "threshold": "$94M",  "tier": "medium"},
    {"name": "Manitoba",                "threshold": "$80M",  "tier": "medium"},
    {"name": "Nova Scotia",             "threshold": "$54M",  "tier": "small"},
    {"name": "New Brunswick",           "threshold": "$40M",  "tier": "small"},
    {"name": "Newfoundland & Labrador", "threshold": "$35M",  "tier": "small"},
    {"name": "Prince Edward Island",    "threshold": "$9M",   "tier": "small"},
    {"name": "Yukon",                   "threshold": "$5M",   "tier": "territory"},
    {"name": "Northwest Territories",   "threshold": "$5M",   "tier": "territory"},
    {"name": "Nunavut",                 "threshold": "$5M",   "tier": "territory"},
]

NAICS_BY_TIER = {
    "large": [
        ("11",      "Agriculture & Agri-processing"),
        ("21",      "Mining, Oil & Gas"),
        ("22",      "Utilities & Energy"),
        ("23",      "Construction, Housing & Real Estate"),
        ("31-33",   "Manufacturing"),
        ("48-49",   "Transportation & Logistics"),
        ("54",      "Technology & Data Infrastructure"),
        ("62",      "Healthcare"),
        ("Defence", "Defence & Security"),
    ],
    "medium": [
        ("11",    "Agriculture & Agri-processing"),
        ("21",    "Mining, Oil & Gas"),
        ("22",    "Utilities & Energy"),
        ("23",    "Construction, Housing & Real Estate"),
        ("31-33", "Manufacturing"),
        ("48-49", "Transportation & Logistics"),
        ("62",    "Healthcare"),
    ],
    "small": [
        ("21",    "Mining, Oil & Gas"),
        ("22",    "Utilities & Energy"),
        ("23",    "Construction, Housing & Real Estate"),
        ("31-33", "Manufacturing"),
        ("62",    "Healthcare"),
    ],
    "territory": [
        ("21",    "Mining, Oil & Gas"),
        ("23",    "Construction & Infrastructure"),
        ("22",    "Utilities & Energy"),
    ],
}

# ==========================================
# PROJECT SCHEMA (passed to Claude Sonnet)
# ==========================================

PROJECT_SCHEMA = """\
{
  "projects": [
    {
      "name": "Full official project name",
      "description": "One concise sentence (max 20 words) describing the project and its proponent",
      "province": "Exact province or territory name as provided",
      "cma": "Census Metropolitan Area or nearest city/town",
      "sector": "One of: Energy | Mining | Transit | Housing | Defence | Manufacturing | Technology | Healthcare | Agriculture | Telecommunications | Ports & Logistics | Other",
      "naics_code": "NAICS code string, e.g. '21' or '31-33'",
      "tags": ["tag1", "tag2", "tag3"],
      "value": "$X.XB or $XXXM — use '\\u2014' if unknown",
      "status": "One of: Announced | Approved | Under Construction | Operational | Completed | Cancelled",
      "completionDate": "Expected completion e.g. '2027', 'Q4 2028', 'Late 2026' — use '' if unknown",
      "announced": "YYYY-MM-DD or YYYY-MM if exact day unknown — use today if unknown",
      "sources": [
        {"id": 1, "title": "Publication \\u2014 Article Title, Month YYYY", "url": "direct link or ''"}
      ]
    }
  ]
}"""

# ==========================================
# LEGACY PASS CONFIG
# ==========================================

# Lowered thresholds for the active-legacy pass (catches mid-size ongoing projects)
LEGACY_CONFIG = [
    {"name": "Ontario",                 "threshold": "$500M"},
    {"name": "Quebec",                  "threshold": "$250M"},
    {"name": "Alberta",                 "threshold": "$200M"},
    {"name": "British Columbia",        "threshold": "$175M"},
    {"name": "Saskatchewan",            "threshold": "$45M"},
    {"name": "Manitoba",                "threshold": "$40M"},
    {"name": "Nova Scotia",             "threshold": "$25M"},
    {"name": "New Brunswick",           "threshold": "$20M"},
    {"name": "Newfoundland & Labrador", "threshold": "$17M"},
    {"name": "Prince Edward Island",    "threshold": "$5M"},
    {"name": "Yukon",                   "threshold": "$3M"},
    {"name": "Northwest Territories",   "threshold": "$3M"},
    {"name": "Nunavut",                 "threshold": "$3M"},
]

# 8 varied query templates — each is a callable(province, threshold) -> str
ACTIVE_QUERY_TEMPLATES = [
    # T1: Under construction right now
    lambda prov, thr: (
        f"What major capital projects worth {thr} or more (CAD) are currently under construction "
        f"or in active development in {prov}? Include projects announced before 2024 that are still "
        f"ongoing. List project name, proponent, total value, % complete if known, expected completion "
        f"date, nearest CMA, and a news source citation."
    ),
    # T2: Active resource extraction
    lambda prov, thr: (
        f"What active mining, oil sands, oil and gas, and resource extraction projects worth {thr} "
        f"or more (CAD) are operating, under development, or in construction in {prov}? Include "
        f"legacy projects regardless of announcement date. List project name, operator, value, "
        f"current status, nearest CMA, and news citation."
    ),
    # T3: Infrastructure in progress
    lambda prov, thr: (
        f"What major infrastructure projects (roads, bridges, transit, rail, ports, water treatment, "
        f"power transmission) worth {thr} or more (CAD) are approved or under construction in {prov}? "
        f"Include both recent announcements and long-running projects. List name, proponent or "
        f"government, value, status, completion date, and news source."
    ),
    # T4: Post-FID, proceeding to construction
    lambda prov, thr: (
        f"What large capital investment projects worth {thr} or more (CAD) received regulatory "
        f"approval or a final investment decision (FID) in {prov} in the past 3 years and are now "
        f"proceeding? Focus on energy, mining, manufacturing, and real estate. List project name, "
        f"investor/proponent, value, current phase, and news citation."
    ),
    # T5: Government-funded capital programs
    lambda prov, thr: (
        f"What major government-funded capital projects in {prov} worth {thr} or more (CAD) have "
        f"received federal or provincial funding and are in procurement, construction, or near "
        f"completion? Include hospitals, transit, affordable housing, schools, and military facilities. "
        f"List name, funding source, value, status, and location."
    ),
    # T6: Defence & military
    lambda prov, thr: (
        f"What defence, military, and national security capital projects worth {thr} or more (CAD) "
        f"are planned, approved, or underway in {prov}? Include DND procurements, base upgrades, "
        f"naval facilities, and defence industry plant investments. List project name, "
        f"contractor/proponent, value, status, and news source citation."
    ),
    # T7: Clean energy & energy transition
    lambda prov, thr: (
        f"What clean energy, renewable power, hydrogen, carbon capture (CCS), or energy transition "
        f"projects worth {thr} or more (CAD) are approved or under construction in {prov}? Include "
        f"wind, solar, hydro, nuclear SMR, and emissions-reduction projects. List name, developer, "
        f"value, capacity, status, expected online date, and news source."
    ),
    # T8: Urban redevelopment & large real estate
    lambda prov, thr: (
        f"What major urban redevelopment, mixed-use real estate, commercial or industrial park, or "
        f"special economic zone projects worth {thr} or more (CAD) are planned or underway in "
        f"{prov}? Include downtown revitalization, waterfront developments, transit-oriented "
        f"communities, and large industrial sites. List name, developer, value, status, CMA, "
        f"and news source."
    ),
]


# ==========================================
# PERPLEXITY SEARCH
# ==========================================

def search_perplexity(province: str, threshold: str, naics_code: str, sector_label: str) -> tuple[str, list[str]]:
    """Query Perplexity Sonar Pro for capital projects in a province+sector combo.
    Returns (text_content, citation_urls) where citation_urls are the real verified sources."""
    one_year_ago = (date.today() - timedelta(days=365)).strftime("%B %Y")
    query = (
        f"What major capital projects worth {threshold} or more (in Canadian dollars) were "
        f"announced, approved, began construction, or reached a significant milestone in "
        f"{province} in the {sector_label} sector (NAICS {naics_code}) between {one_year_ago} "
        f"and today? List each project with: full project name, proponent or developer name, "
        f"total project value in CAD, current status (announced/approved/under construction/"
        f"operational/completed/cancelled), expected completion date, nearest city or CMA, "
        f"and a news source citation with publication name and date. "
        f"Only include real, verifiable projects. Do not fabricate."
    )

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Canadian infrastructure and capital markets researcher. "
                    "Provide factual, sourced information about real capital projects in Canada. "
                    "Be specific about project names, dollar values, proponents, and status."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": 2000,
    }

    for attempt in range(4):
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            return content, citations
        except Exception as e:
            if attempt == 3:
                print(f"\n    [PERPLEXITY ERROR] {province}/{naics_code}: {e}")
                return "", []
            time.sleep(2 ** attempt)
    return "", []

def search_perplexity_raw(query: str) -> tuple[str, list[str]]:
    """Query Perplexity Sonar Pro with a free-form query string.
    Returns (text_content, citation_urls)."""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Canadian infrastructure and capital markets researcher. "
                    "Provide factual, sourced information about real capital projects in Canada. "
                    "Be specific about project names, dollar values, proponents, and status. "
                    "Only include real, verifiable projects. Do not fabricate."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": 2000,
    }

    for attempt in range(4):
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            return content, citations
        except Exception as e:
            if attempt == 3:
                print(f"\n    [PERPLEXITY ERROR] raw query: {e}")
                return "", []
            time.sleep(2 ** attempt)
    return "", []


# ==========================================
# CLAUDE SONNET STRUCTURED PARSING
# ==========================================

def parse_with_sonnet(raw_text: str, province: str, threshold: str, naics_code: str, citations: list[str] | None = None) -> list:
    """Use Claude Sonnet to structure Perplexity's raw output into project records."""
    if not raw_text.strip():
        return []

    system_prompt = (
        "You are a data extraction assistant specializing in Canadian capital projects. "
        "Parse the provided text and return a valid JSON object matching the schema exactly. "
        "Only include projects that are real and clearly described in the source text. "
        "Do not fabricate projects or details not present in the source text. "
        "Return only the JSON object — no markdown fences, no explanation."
    )

    citations_block = ""
    if citations:
        numbered = "\n".join(f"[{i+1}] {url}" for i, url in enumerate(citations))
        citations_block = f"""
VERIFIED SOURCE URLs (use these real URLs in project sources — match by relevance to each project):
{numbered}

"""

    user_prompt = f"""Extract all capital projects from the text below.

Province: {province}
Minimum value: {threshold} CAD
NAICS sector context: {naics_code}
{citations_block}
Return only this JSON structure (no markdown, no explanation):
{PROJECT_SCHEMA}

If no valid projects are found, return: {{"projects": []}}

SOURCE TEXT:
{raw_text}"""

    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=os.environ.get("SONNET_MODEL", "claude-sonnet-4-5-20250929"),
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = msg.content[0].text.strip()
            # Strip any accidental markdown fences
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                projects = parsed.get("projects", [])
                if isinstance(projects, list):
                    return projects
            return []
        except json.JSONDecodeError as e:
            if attempt == 3:
                print(f"\n    [SONNET JSON ERROR] {province}/{naics_code}: {e}")
                return []
            time.sleep(1)
        except Exception as e:
            if attempt == 3:
                print(f"\n    [SONNET ERROR] {province}/{naics_code}: {e}")
                return []
            time.sleep(2 ** attempt)
    return []

# ==========================================
# MAIN SEED FUNCTION
# ==========================================

def seed_projects():
    today = date.today().isoformat()
    projects_ref = db.collection('projects')

    # ── Load existing projects from Firestore ──────────────────────
    print("Loading existing projects from Firestore...")
    existing_docs = {}
    existing_names_by_province = {}
    for doc_snap in projects_ref.stream():
        data = doc_snap.to_dict()
        key = normalize_key(data['name'], data['province'])
        existing_docs[key] = (doc_snap.reference, data)
        existing_names_by_province.setdefault(data['province'], []).append(data['name'])
    print(f"  Found {len(existing_docs)} existing projects.\n")

    # ── Run through all provinces + NAICS combos ──────────────────
    added_by_province = {}
    skipped_total = 0
    perplexity_calls = 0
    total_raw = 0

    for prov_cfg in PROVINCE_CONFIG:
        prov_name  = prov_cfg["name"]
        threshold  = prov_cfg["threshold"]
        tier       = prov_cfg["tier"]
        naics_list = NAICS_BY_TIER[tier]

        print(f"\n{'─' * 55}")
        print(f"  {prov_name.upper()}  (threshold: {threshold}+)")
        print(f"{'─' * 55}")

        for naics_code, sector_label in naics_list:
            print(f"  [{naics_code}] {sector_label}... ", end="", flush=True)

            # Step 1: Perplexity search
            raw_text, citations = search_perplexity(prov_name, threshold, naics_code, sector_label)
            perplexity_calls += 1
            time.sleep(2)  # polite delay between API calls

            if not raw_text:
                print("no results")
                continue

            # Step 2: Claude Sonnet structured parsing
            projects = parse_with_sonnet(raw_text, prov_name, threshold, naics_code, citations)
            total_raw += len(projects)
            print(f"→ {len(projects)} found", end="")

            # Step 3: Dedup + insert
            added_here = 0
            for project in projects:
                proj_name = (project.get('name') or '').strip()
                if not proj_name:
                    skipped_total += 1
                    continue

                # Always assign province from outer loop (prevents cross-province bleed)
                proj_prov = prov_name

                # Exact normalized match
                exact_key = normalize_key(proj_name, proj_prov)
                if exact_key in existing_docs:
                    skipped_total += 1
                    continue

                # Fuzzy match within same province
                candidates = existing_names_by_province.get(proj_prov, [])
                fuzzy_name = fuzzy_match(proj_name, candidates)
                if fuzzy_name:
                    skipped_total += 1
                    continue

                # Normalize announced date
                announced = (project.get('announced') or today).strip()
                if len(announced) == 7:    # YYYY-MM
                    announced += '-01'
                elif len(announced) == 4:  # YYYY only
                    announced += '-01-01'
                elif len(announced) < 4:
                    announced = today

                new_doc = {
                    'name':           proj_name,
                    'description':    project.get('description') or '',
                    'province':       proj_prov,
                    'sector':         project.get('sector') or 'Other',
                    'naics_code':     project.get('naics_code') or naics_code,
                    'cma':            project.get('cma') or '',
                    'tags':           project.get('tags') or [],
                    'value':          project.get('value') or '\u2014',
                    'status':         project.get('status') or 'Announced',
                    'completionDate': project.get('completionDate') or '',
                    'sources':        project.get('sources') or [],
                    'source':         '',
                    'firstTracked':   announced,
                    'lastUpdated':    today,
                    'lastSeen':       today,
                    'statusHistory':  [
                        {'status': project.get('status') or 'Announced', 'date': announced}
                    ],
                }

                projects_ref.add(new_doc)
                added_here += 1

                # Update local cache so subsequent entries in this run can match
                existing_names_by_province.setdefault(proj_prov, []).append(proj_name)
                existing_docs[exact_key] = (None, new_doc)

            added_by_province[prov_name] = added_by_province.get(prov_name, 0) + added_here

            if added_here:
                print(f", +{added_here} added")
            else:
                print(", 0 added (all dupes)")

    # ── Final summary ──────────────────────────────────────────────
    total_added = sum(added_by_province.values())

    print(f"\n{'=' * 55}")
    print(f"  SEED COMPLETE (NAICS PASS)")
    print(f"{'=' * 55}")
    print(f"  Perplexity calls:   {perplexity_calls}")
    print(f"  Raw from Sonnet:     {total_raw}")
    print(f"  Added to Firestore: {total_added}")
    print(f"  Skipped (dupes):    {skipped_total}")
    print(f"\n  Breakdown by province:")
    for prov in sorted(added_by_province):
        if added_by_province[prov] > 0:
            print(f"    {prov}: +{added_by_province[prov]}")
    print(f"{'=' * 55}\n")

    return existing_docs, existing_names_by_province


# ==========================================
# ACTIVE LEGACY PASS
# ==========================================

def seed_active_legacy(existing_docs: dict, existing_names_by_province: dict) -> int:
    """
    Second pass: search for active/ongoing projects regardless of announcement date.
    Uses 8 varied query templates × 13 provinces with lowered thresholds.
    Shares the dedup cache populated by seed_projects() to avoid re-inserting
    anything already found in the NAICS pass.

    Returns the total number of new projects added.
    """
    today = date.today().isoformat()
    projects_ref = db.collection('projects')

    n_queries = len(ACTIVE_QUERY_TEMPLATES) * len(LEGACY_CONFIG)
    print(f"\n{'=' * 55}")
    print(f"  ACTIVE LEGACY PASS")
    print(f"  {len(ACTIVE_QUERY_TEMPLATES)} templates × {len(LEGACY_CONFIG)} provinces = {n_queries} queries")
    print(f"{'=' * 55}")

    added_total   = 0
    skipped_total = 0
    perplexity_calls = 0
    raw_total     = 0

    for prov_cfg in LEGACY_CONFIG:
        prov_name = prov_cfg["name"]
        threshold = prov_cfg["threshold"]

        print(f"\n{'─' * 55}")
        print(f"  {prov_name.upper()}  (threshold: {threshold}+)")
        print(f"{'─' * 55}")

        for i, template_fn in enumerate(ACTIVE_QUERY_TEMPLATES, 1):
            query = template_fn(prov_name, threshold)
            print(f"  [T{i}]... ", end="", flush=True)

            raw_text, citations = search_perplexity_raw(query)
            perplexity_calls += 1
            time.sleep(2)

            if not raw_text:
                print("no results")
                continue

            # Reuse parse_with_sonnet — "mixed" naics_code signals multi-sector context
            projects = parse_with_sonnet(raw_text, prov_name, threshold, "mixed", citations)
            raw_total += len(projects)
            print(f"→ {len(projects)} found", end="")

            added_here = 0
            for project in projects:
                proj_name = (project.get('name') or '').strip()
                if not proj_name:
                    skipped_total += 1
                    continue

                # Force province from outer loop (prevents cross-province bleed)
                proj_prov = prov_name

                exact_key = normalize_key(proj_name, proj_prov)
                if exact_key in existing_docs:
                    skipped_total += 1
                    continue

                candidates = existing_names_by_province.get(proj_prov, [])
                fuzzy_name = fuzzy_match(proj_name, candidates)
                if fuzzy_name:
                    skipped_total += 1
                    continue

                # Normalize announced date
                announced = (project.get('announced') or today).strip()
                if len(announced) == 7:
                    announced += '-01'
                elif len(announced) == 4:
                    announced += '-01-01'
                elif len(announced) < 4:
                    announced = today

                # Default status to Under Construction for legacy active-projects pass
                status = project.get('status') or 'Under Construction'

                new_doc = {
                    'name':           proj_name,
                    'description':    project.get('description') or '',
                    'province':       proj_prov,
                    'sector':         project.get('sector') or 'Other',
                    'naics_code':     project.get('naics_code') or '',
                    'cma':            project.get('cma') or '',
                    'tags':           project.get('tags') or [],
                    'value':          project.get('value') or '\u2014',
                    'status':         status,
                    'completionDate': project.get('completionDate') or '',
                    'sources':        project.get('sources') or [],
                    'source':         '',
                    'firstTracked':   announced,
                    'lastUpdated':    today,
                    'lastSeen':       today,
                    'statusHistory':  [{'status': status, 'date': announced}],
                }

                projects_ref.add(new_doc)
                added_here += 1

                existing_names_by_province.setdefault(proj_prov, []).append(proj_name)
                existing_docs[exact_key] = (None, new_doc)

            added_total += added_here

            if added_here:
                print(f", +{added_here} added")
            else:
                print(", 0 added (all dupes)")

    print(f"\n{'=' * 55}")
    print(f"  LEGACY PASS COMPLETE")
    print(f"{'=' * 55}")
    print(f"  Perplexity calls:   {perplexity_calls}")
    print(f"  Raw from Sonnet:     {raw_total}")
    print(f"  Added to Firestore: {added_total}")
    print(f"  Skipped (dupes):    {skipped_total}")
    print(f"{'=' * 55}\n")

    return added_total


if __name__ == "__main__":
    # Run NAICS pass first, then legacy active-projects pass sharing the same dedup cache
    existing_docs, existing_names_by_province = seed_projects()
    seed_active_legacy(existing_docs, existing_names_by_province)
