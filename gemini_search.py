"""
gemini_search.py — Tier 2 Gemini grounded search for CAN-MACRO pipeline.

Primary discovery engine using Gemini 2.5 Flash with Google Search grounding.
Returns structured project data with source URLs from groundingMetadata.

Sections:
  A  Provincial sweeps (13 queries)
  B  Sector-focused provincial sweeps (39 queries)
  C  CMA-level sweeps (30 queries)
  D  NAICS sector sweeps (20 queries)
  E  Watchlist company sweeps (~21 queries)
  F  Cross-cutting catch-all (10 queries)
  G  DEEP SWEEP — CMA × Sector cross-queries (90 queries)
  H  DEEP SWEEP — Municipal development tracking (30 queries)
  I  DEEP SWEEP — Proponent/developer tracking (26 queries)

Weekly: A-F (~133 base + E varies) = ~279 queries
Monthly deep-sweep adds G-I = +146 queries
"""

import json
import os
import time
from datetime import date

from dotenv import load_dotenv

load_dotenv()

TODAY = date.today().isoformat()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
GEMINI_SEARCH_ENABLED = os.environ.get('GEMINI_SEARCH_ENABLED', 'false').lower() == 'true'

# Rate limiting
_DELAY_SECONDS = 1.0
_last_call = 0.0


def _rate_limit():
    """Enforce delay between Gemini API calls."""
    global _last_call
    now = time.time()
    elapsed = now - _last_call
    if elapsed < _DELAY_SECONDS:
        time.sleep(_DELAY_SECONDS - elapsed)
    _last_call = time.time()


# ══════════════════════════════════════════════════════════════════════════════
# PROVINCE + CMA + THRESHOLD DATA
# ══════════════════════════════════════════════════════════════════════════════

PROVINCES = [
    {'name': 'Ontario',                     'code': 'ON', 'threshold': '$500M', 'threshold_val': 500_000_000},
    {'name': 'Quebec',                      'code': 'QC', 'threshold': '$250M', 'threshold_val': 250_000_000},
    {'name': 'Alberta',                     'code': 'AB', 'threshold': '$200M', 'threshold_val': 200_000_000},
    {'name': 'British Columbia',            'code': 'BC', 'threshold': '$175M', 'threshold_val': 175_000_000},
    {'name': 'Saskatchewan',                'code': 'SK', 'threshold': '$45M',  'threshold_val':  45_000_000},
    {'name': 'Manitoba',                    'code': 'MB', 'threshold': '$40M',  'threshold_val':  40_000_000},
    {'name': 'Nova Scotia',                 'code': 'NS', 'threshold': '$25M',  'threshold_val':  25_000_000},
    {'name': 'New Brunswick',               'code': 'NB', 'threshold': '$20M',  'threshold_val':  20_000_000},
    {'name': 'Newfoundland and Labrador',   'code': 'NL', 'threshold': '$17M',  'threshold_val':  17_000_000},
    {'name': 'Prince Edward Island',        'code': 'PE', 'threshold': '$5M',   'threshold_val':   5_000_000},
    {'name': 'Yukon',                       'code': 'YT', 'threshold': '$3M',   'threshold_val':   3_000_000},
    {'name': 'Northwest Territories',       'code': 'NT', 'threshold': '$3M',   'threshold_val':   3_000_000},
    {'name': 'Nunavut',                     'code': 'NU', 'threshold': '$3M',   'threshold_val':   3_000_000},
]

# CMA list from watchlist — each with its province and a lower threshold
CMAS = [
    {'name': 'Toronto', 'province': 'Ontario', 'threshold': '$200M'},
    {'name': 'Montreal', 'province': 'Quebec', 'threshold': '$100M'},
    {'name': 'Vancouver', 'province': 'British Columbia', 'threshold': '$100M'},
    {'name': 'Calgary', 'province': 'Alberta', 'threshold': '$100M'},
    {'name': 'Edmonton', 'province': 'Alberta', 'threshold': '$75M'},
    {'name': 'Ottawa-Gatineau', 'province': 'Ontario', 'threshold': '$75M'},
    {'name': 'Winnipeg', 'province': 'Manitoba', 'threshold': '$25M'},
    {'name': 'Quebec City', 'province': 'Quebec', 'threshold': '$50M'},
    {'name': 'Hamilton', 'province': 'Ontario', 'threshold': '$50M'},
    {'name': 'Kitchener-Cambridge-Waterloo', 'province': 'Ontario', 'threshold': '$50M'},
    {'name': 'London', 'province': 'Ontario', 'threshold': '$40M'},
    {'name': 'Halifax', 'province': 'Nova Scotia', 'threshold': '$15M'},
    {'name': 'Victoria', 'province': 'British Columbia', 'threshold': '$30M'},
    {'name': 'Windsor', 'province': 'Ontario', 'threshold': '$30M'},
    {'name': 'Oshawa', 'province': 'Ontario', 'threshold': '$30M'},
    {'name': 'Saskatoon', 'province': 'Saskatchewan', 'threshold': '$20M'},
    {'name': 'Regina', 'province': 'Saskatchewan', 'threshold': '$20M'},
    {'name': 'St. Catharines-Niagara', 'province': 'Ontario', 'threshold': '$25M'},
    {'name': 'Barrie', 'province': 'Ontario', 'threshold': '$20M'},
    {'name': 'Kelowna', 'province': 'British Columbia', 'threshold': '$20M'},
    {'name': 'Abbotsford-Mission', 'province': 'British Columbia', 'threshold': '$20M'},
    {'name': 'Sherbrooke', 'province': 'Quebec', 'threshold': '$15M'},
    {'name': 'Guelph', 'province': 'Ontario', 'threshold': '$15M'},
    {'name': 'Moncton', 'province': 'New Brunswick', 'threshold': '$10M'},
    {'name': 'Saint John', 'province': 'New Brunswick', 'threshold': '$10M'},
    {'name': "St. John's", 'province': 'Newfoundland and Labrador', 'threshold': '$10M'},
    {'name': 'Fredericton', 'province': 'New Brunswick', 'threshold': '$10M'},
    {'name': 'Saguenay', 'province': 'Quebec', 'threshold': '$15M'},
    {'name': 'Trois-Rivieres', 'province': 'Quebec', 'threshold': '$15M'},
    {'name': 'Brantford', 'province': 'Ontario', 'threshold': '$15M'},
]

# NAICS sectors for Section D
NAICS_SECTORS = [
    ('11', 'Agriculture, forestry, fishing and hunting'),
    ('21', 'Mining, quarrying, and oil and gas extraction'),
    ('22', 'Utilities'),
    ('23', 'Construction'),
    ('31-33', 'Manufacturing'),
    ('41', 'Wholesale trade'),
    ('44-45', 'Retail trade'),
    ('48-49', 'Transportation and warehousing'),
    ('51', 'Information and cultural industries'),
    ('52', 'Finance and insurance'),
    ('53', 'Real estate and rental and leasing'),
    ('54', 'Professional, scientific and technical services'),
    ('55', 'Management of companies and enterprises'),
    ('56', 'Administrative and support, waste management'),
    ('61', 'Educational services'),
    ('62', 'Health care and social assistance'),
    ('71', 'Arts, entertainment and recreation'),
    ('72', 'Accommodation and food services'),
    ('81', 'Other services'),
    ('91', 'Public administration'),
]


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT + TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM = (
    "You are a research assistant for a Canadian macroeconomic intelligence dashboard. "
    "You search for and identify major capital projects. Return ONLY valid JSON — "
    "no markdown, no preamble, no explanation."
)

_PROVINCE_TEMPLATE = """Find all major capital projects worth over C${threshold} currently proposed, approved, under review, or under construction in {province}, Canada.

Include projects across ALL sectors: energy, mining, manufacturing, transportation, healthcare, education, real estate, mixed-use redevelopment, infrastructure, technology, defense, agriculture, and entertainment/recreation.

Include:
- New construction AND redevelopments/conversions/adaptive reuse
- Private sector investments AND public infrastructure
- Provincial AND municipal AND federal projects located in this province
- Expansions of existing facilities where the expansion value meets the threshold

Exclude:
- Projects already completed or cancelled
- Routine maintenance or operational spending
- Projects below C${threshold}

For EACH project return a JSON object with these fields:
{{
  "name": "project name",
  "value": "dollar value as string (e.g. 'C$650M') or 'Not disclosed'",
  "value_numeric": null,
  "proponent": "company, agency, or developer name",
  "province": "{province}",
  "cma": "city or CMA name",
  "naics_2digit": "best-fit 2-digit NAICS code",
  "status": "Proposed | Under Review | Approved | Under Construction | Paused | Expansion",
  "description": "2-3 sentence summary of project scope and current state",
  "source_url": "URL from search results that describes this project",
  "source_title": "title of the source article or page"
}}

Return a JSON array. If no projects are found, return [].
Search thoroughly — check government announcements, news articles, industry publications, and company press releases."""


# ══════════════════════════════════════════════════════════════════════════════
# QUERY BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_section_a() -> list[tuple[str, str]]:
    """Section A: Provincial sweeps (13 queries)."""
    queries = []
    for prov in PROVINCES:
        prompt = _PROVINCE_TEMPLATE.format(
            threshold=prov['threshold'].replace('$', ''),
            province=prov['name'],
        )
        queries.append((f"A-{prov['code']}", prompt))
    return queries


def _build_section_b() -> list[tuple[str, str]]:
    """Section B: Sector-focused provincial sweeps (13 × 3 = 39 queries)."""
    queries = []
    for prov in PROVINCES:
        t = prov['threshold']
        p = prov['name']

        queries.append((f"B1-{prov['code']}", (
            f"Find all major goods-producing capital projects (mining, energy, oil & gas, "
            f"manufacturing, utilities, agriculture, forestry, construction) worth over C${t} "
            f"in {p}. Include pipelines, processing plants, mines, refineries, power generation, "
            f"transmission, dams, battery plants, LNG terminals, and industrial facilities. "
            f"Return a JSON array of objects with: name, value, proponent, province, cma, "
            f"naics_2digit, status, description, source_url, source_title. Return [] if none found."
        )))

        queries.append((f"B2-{prov['code']}", (
            f"Find all major services-sector and real estate capital projects worth over C${t} "
            f"in {p}. Include mixed-use redevelopments, housing developments, commercial towers, "
            f"transit projects, hospital construction, university expansions, data centers, "
            f"entertainment venues, hotel/resort developments, and adaptive reuse/conversion projects. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))

        queries.append((f"B3-{prov['code']}", (
            f"Find all major infrastructure and public-sector capital projects worth over C${t} "
            f"in {p}. Include highways, bridges, transit (LRT, BRT, subway), ports, airports, "
            f"water/wastewater treatment, military/DND facilities, border crossings, government "
            f"buildings, P3 partnerships, and Indigenous economic development projects. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))

    return queries


def _build_section_c() -> list[tuple[str, str]]:
    """Section C: CMA-level sweeps (30 queries)."""
    queries = []
    for cma in CMAS:
        queries.append((f"C-{cma['name'][:10]}", (
            f"Find all major development and capital projects worth over C{cma['threshold']} "
            f"currently proposed, approved, or under construction in {cma['name']}, {cma['province']}. "
            f"Include private developments, public infrastructure, transit, healthcare, education, "
            f"mixed-use, redevelopments, and expansions. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))
    return queries


def _build_section_d() -> list[tuple[str, str]]:
    """Section D: NAICS sector sweeps (20 queries)."""
    queries = []
    for code, name in NAICS_SECTORS:
        queries.append((f"D-{code}", (
            f"Find the largest capital projects in {name} (NAICS {code}) currently under "
            f"development anywhere in Canada. Focus on projects worth C$100M+ that are "
            f"proposed, approved, or under construction. Include new facilities, major "
            f"expansions, and redevelopments. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))
    return queries


def _build_section_e(watchlist: dict | None = None) -> list[tuple[str, str]]:
    """Section E: Watchlist company sweeps (~21 queries, 5 companies each)."""
    companies = []
    if watchlist:
        for co in watchlist.get('provincial_companies', []):
            name = co.get('name') or co.get('entity', '')
            if name:
                companies.append(name)
        for co in watchlist.get('industry_companies', []):
            name = co.get('name') or co.get('entity', '')
            if name:
                companies.append(name)

    # Deduplicate
    seen = set()
    unique = []
    for c in companies:
        key = c.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    companies = unique

    if not companies:
        return []

    queries = []
    batch_size = 5
    for i in range(0, len(companies), batch_size):
        batch = companies[i:i + batch_size]
        names_str = ', '.join(batch)
        queries.append((f"E-batch{i//batch_size}", (
            f"Search for any major capital projects (C$50M+) being developed by the following "
            f"companies in Canada: {names_str}. Include new facilities, expansions, acquisitions "
            f"with planned redevelopment, and joint ventures. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))
    return queries


def _build_section_f() -> list[tuple[str, str]]:
    """Section F: Cross-cutting catch-all (10 queries)."""
    prompts = [
        "Largest capital projects announced in Canada in the past 3 months, worth C$500M+",
        "Canadian P3 public-private partnership projects currently in procurement or construction",
        "Indigenous-led economic development projects in Canada worth C$25M+",
        "Canadian federal infrastructure projects announced in the 2025-2026 budget",
        "Major Canadian defense and military construction projects by DND",
        "Canadian clean energy and hydrogen projects proposed or under construction",
        "EV battery, critical minerals, and semiconductor plants in Canada",
        "Major Canadian transit projects (LRT, BRT, subway) under construction or proposed",
        "Canadian data center construction and hyperscale projects",
        "Major brownfield redevelopment and urban renewal projects in Canada",
    ]
    queries = []
    for i, p in enumerate(prompts):
        queries.append((f"F-{i+1}", (
            f"{p}. For each project return: name, value (e.g. 'C$1.2B'), proponent, province, "
            f"cma, naics_2digit, status, description, source_url, source_title. "
            f"Return a JSON array. Return [] if none found."
        )))
    return queries


# ── DEEP SWEEP SECTIONS ──────────────────────────────────────────────────────

def _build_section_g() -> list[tuple[str, str]]:
    """Section G: DEEP SWEEP — CMA × Sector cross-queries (90 queries)."""
    sector_prompts = [
        ("real estate, mixed-use, and residential development", "G1"),
        ("infrastructure, transit, and healthcare construction", "G2"),
        ("industrial, manufacturing, energy, and commercial", "G3"),
    ]
    queries = []
    for cma in CMAS:
        t = cma['threshold']
        for sector_desc, label in sector_prompts:
            queries.append((f"{label}-{cma['name'][:10]}", (
                f"Find major {sector_desc} projects over C{t} in {cma['name']}. "
                f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
                f"status, description, source_url, source_title. Return [] if none found."
            )))
    return queries


def _build_section_h() -> list[tuple[str, str]]:
    """Section H: DEEP SWEEP — Municipal development tracking (30 queries)."""
    queries = []
    for cma in CMAS:
        t = cma['threshold']
        queries.append((f"H-{cma['name'][:10]}", (
            f"What major development projects have been approved by the city of {cma['name']} "
            f"in the past 6 months? Include building permits for projects over C{t}, "
            f"rezoning approvals for large developments, and municipal infrastructure spending. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))
    return queries


def _build_section_i() -> list[tuple[str, str]]:
    """Section I: DEEP SWEEP — Proponent/developer tracking (26 queries)."""
    developer_batches = [
        "PCL Construction, EllisDon, Pomerleau, Aecon Group, Bird Construction",
        "Brookfield Asset Management, Oxford Properties, Cadillac Fairview, Ivanhoe Cambridge, Dream Unlimited",
        "Concord Pacific, Westbank Corp, Concert Properties, Bosa Properties, Polygon Homes",
        "Tridel, Menkes, Mattamy Homes, Great Gulf, Daniels Corporation",
        "Devimco, Broccolini, Claridge, Prevel, Fonds immobilier de solidarite FTQ",
        "True North Real Estate Development, Forks North Portage, Artis REIT, Globe General Contractors",
        "Qualico, Daytona Homes, Strategic Group, Anthem Properties, Wall Financial",
        "Cressey Development, Ledcor Group, Graham Construction, Stuart Olson, Chandos Construction",
        "Canderel, Allied Properties REIT, First Capital REIT, Choice Properties REIT, RioCan REIT",
        "CPPIB, PSP Investments, AIMCo, OMERS Infrastructure, CDPQ Infra",
        "Enbridge, TC Energy, Pembina Pipeline, AltaGas, Inter Pipeline",
        "Fortis, TransAlta, Capital Power, Ontario Power Generation, Hydro-Quebec",
        "Cameco, Teck Resources, Nutrien, Lundin Mining, First Quantum Minerals",
        "Stellantis, General Motors Canada, Honda Canada, Toyota Canada, Ford Canada",
        "Northland Power, Innergex, Boralex, EDF Renewables Canada, Capital Power",
        "Samsung C&T, LG Energy Solution, Volkswagen Group, Umicore, BASF",
        "Kinross Gold, Barrick Gold, Agnico Eagle, Pan American Silver, Hudbay Minerals",
        "Loblaws, Metro, Empire Company, Sobeys, Canadian Tire",
        "Shaw Communications, Telus, Rogers, BCE, Cogeco",
        "Maple Leaf Foods, Saputo, Agropur, Richardson International, Viterra",
        "SNC-Lavalin, WSP Global, Stantec, Hatch, Jacobs Engineering",
        "Amazon Canada, Google Canada, Microsoft Canada, Meta Platforms, Apple Canada",
        "Walmart Canada, Costco Canada, IKEA Canada, Home Depot Canada, Lowe's Canada",
        "Minto Group, Killam Apartment REIT, Boardwalk REIT, Canadian Apartment Properties REIT",
        "Irving Group, J.D. Irving, Emera, Fortis Atlantic, Port of Halifax",
        "Kruger Products, Resolute Forest Products, Mercer International, Cascades, Domtar",
    ]

    queries = []
    for i, batch in enumerate(developer_batches):
        queries.append((f"I-{i+1}", (
            f"Major Canadian projects by {batch}. Find capital projects (C$50M+) under "
            f"development, proposed, or recently announced by these companies in Canada. "
            f"Return a JSON array with: name, value, proponent, province, cma, naics_2digit, "
            f"status, description, source_url, source_title. Return [] if none found."
        )))
    return queries


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def _parse_response(response, section_label: str) -> list[dict]:
    """Extract projects from a Gemini grounded search response."""
    try:
        text = response.text.strip()
        # Handle markdown code blocks
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()

        raw = json.loads(text)
        if not isinstance(raw, list):
            raw = [raw] if isinstance(raw, dict) else []
    except (json.JSONDecodeError, IndexError):
        return []

    # Extract grounding URLs
    grounding_urls = set()
    try:
        if hasattr(response, 'candidates') and response.candidates:
            metadata = response.candidates[0].grounding_metadata
            if metadata and hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and hasattr(chunk.web, 'uri'):
                        grounding_urls.add(chunk.web.uri)
    except Exception:
        pass

    projects = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = (item.get('name') or '').strip()
        if not name or len(name) < 3:
            continue

        source_url = (item.get('source_url') or '').strip()
        projects.append({
            'name': name,
            'value': item.get('value') or 'Not disclosed',
            'value_numeric': item.get('value_numeric'),
            'proponent': (item.get('proponent') or 'Unknown').strip(),
            'province': (item.get('province') or '').strip(),
            'cma': (item.get('cma') or '').strip(),
            'naics_2digit': (item.get('naics_2digit') or '').strip(),
            'status': (item.get('status') or 'Proposed').strip(),
            'description': (item.get('description') or '').strip(),
            'source_url': source_url,
            'source_title': (item.get('source_title') or '').strip(),
            'discovery_source': 'gemini_search',
            'confidence': 'verified' if source_url in grounding_urls else 'unverified',
            '_section': section_label,
        })

    return projects


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SEARCH FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_gemini_search(
    deep_sweep: bool = False,
    watchlist: dict | None = None,
    gemini_client=None,
) -> list[dict]:
    """
    Run Gemini grounded search across all sections.

    Args:
        deep_sweep: If True, include Sections G-I (monthly).
        watchlist: Parsed watchlist.json dict for Section E.
        gemini_client: google.genai.Client instance.

    Returns:
        List of project dicts (not yet deduplicated against Firestore).
    """
    if not GEMINI_SEARCH_ENABLED:
        print("  [Gemini Search] Disabled (set GEMINI_SEARCH_ENABLED=true in .env)")
        return []

    if not gemini_client:
        try:
            from google import genai
            api_key = os.environ.get('GEMINI_API_KEY', '').strip()
            if not api_key:
                print("  [Gemini Search] No GEMINI_API_KEY — skipping.")
                return []
            gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"  [Gemini Search] Client init failed: {e}")
            return []

    from google.genai import types

    # Build query plan
    queries = []
    queries.extend(_build_section_a())
    queries.extend(_build_section_b())
    queries.extend(_build_section_c())
    queries.extend(_build_section_d())
    queries.extend(_build_section_e(watchlist))
    queries.extend(_build_section_f())

    if deep_sweep:
        queries.extend(_build_section_g())
        queries.extend(_build_section_h())
        queries.extend(_build_section_i())

    sweep_label = "deep-sweep" if deep_sweep else "weekly"
    print(f"\n[TIER 2] Gemini grounded search ({sweep_label}: {len(queries)} queries)...")

    all_projects = []
    errors = 0

    for i, (label, prompt) in enumerate(queries):
        _rate_limit()
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Content(role='user', parts=[types.Part(text=prompt)])
                ],
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    # tools DISABLED - grounding costs $35/1000 queries,
                    response_mime_type='application/json',
                    max_output_tokens=8192,
                ),
            )
            projects = _parse_response(response, label)
            all_projects.extend(projects)

            if (i + 1) % 25 == 0 or i == len(queries) - 1:
                print(f"  [Gemini Search] {i+1}/{len(queries)} queries done, "
                      f"{len(all_projects)} projects so far")

        except Exception as e:
            errors += 1
            err_name = type(e).__name__
            if errors <= 5:
                print(f"  [Gemini Search] Query {label} failed: {err_name}")
            elif errors == 6:
                print(f"  [Gemini Search] Suppressing further error logs...")
            # For rate limit errors, back off
            if 'rate' in str(e).lower() or '429' in str(e):
                print(f"  [Gemini Search] Rate limited — backing off 30s")
                time.sleep(30)

    # Deduplicate within Gemini results (by name + province)
    seen = set()
    unique = []
    for p in all_projects:
        key = (p['name'].lower().strip(), p.get('province', '').lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"\n  [Gemini Search] Complete: {len(unique)} unique projects "
          f"from {len(queries)} queries ({errors} errors)")

    return unique


def log_gemini_unique(projects: list[dict], existing_names: set[str]):
    """Log projects found by Gemini but not in existing Firestore."""
    unique = [p for p in projects if p.get('name', '').lower().strip() not in existing_names]
    if not unique:
        return
    try:
        path = f'gemini_unique_{TODAY}.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"Gemini-unique projects — {TODAY}\n{'='*60}\n\n")
            for p in unique:
                f.write(f"{p.get('province', '?')}: {p['name']} ({p.get('value', '?')})\n")
                f.write(f"  Status: {p.get('status', '?')} | Source: {p.get('source_url', 'N/A')}\n")
                f.write(f"  Section: {p.get('_section', '?')}\n\n")
        print(f"  [Gemini Search] {len(unique)} unique projects logged to {path}")
    except Exception:
        pass
