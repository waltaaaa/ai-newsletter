"""
article_filter.py — Three-layer relevance filter for CAN-MACRO pipeline.

Shared by RSS (Tier 4) and GDELT (Tier 3) to eliminate non-economic content
before spending extraction calls.

Layers:
  1. Compound keyword co-occurrence (A ∩ (B ∪ C)) — with dollar-value bypass
  2. Negative keyword exclusion (title-level reject)
  3. Gemini Flash batch pre-screen (20 per call)

STEP_2B remediation (2026-03-04):
  - Expanded Cat A with brownfield/renovation vocabulary
  - Added dollar-value bypass (≥$1M auto-passes L1)
  - Cleaned L2 negatives to remove false-negative triggers
  - Improved L3 Gemini prompt for brownfield coverage
  - Government source bypass: infra/procurement feeds skip L1+L2
"""

import json
import os
import re
from datetime import date

from dotenv import load_dotenv

load_dotenv()

TODAY = date.today().isoformat()

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — COMPOUND KEYWORD CO-OCCURRENCE
# ══════════════════════════════════════════════════════════════════════════════

# Category A: project signal (greenfield + brownfield)
_CAT_A = frozenset({
    # Greenfield
    'project', 'construction', 'facility', 'plant', 'development',
    'build', 'campus', 'tower', 'terminal', 'warehouse', 'refinery',
    'pipeline', 'mine', 'dam', 'generation', 'turbine', 'reactor',
    'data center', 'data centre', 'housing', 'transit', 'highway',
    'bridge', 'port', 'airport', 'hospital', 'arena', 'stadium',
    'mill', 'smelter', 'upgrader', 'compressor', 'substation',
    'interconnection',
    # Brownfield / renovation
    'redevelopment', 'expansion', 'renovation', 'conversion',
    'remediation', 'retrofit', 'restoration', 'adaptive reuse',
    'modernization', 'modernisation', 'decommission', 'upgrade',
    'overhaul', 'rehabilitation', 'repurpose', 'repurposing',
    'rebuild', 'rebuilding', 'infill', 'densification',
    'revitalization', 'revitalisation', 'reconfiguration',
    'replacement', 'demolition and rebuild', 'seismic upgrade',
    'energy retrofit', 'deep retrofit', 'envelope upgrade',
    # Building types
    'mixed-use', 'mixed use', 'condo', 'condominium', 'townhouse',
    'apartment', 'long-term care', 'ltc', 'seniors residence',
    'assisted living', 'retirement home',
    # Infrastructure types
    'interchange', 'overpass', 'underpass', 'tunnel', 'flyover',
    'rail yard', 'maintenance facility', 'bus rapid transit',
    'light rail', 'lrt', 'brt', 'wastewater', 'water treatment',
    'desalination', 'landfill', 'recycling facility',
    'broadband', 'fibre', 'fiber', 'transmission line',
    'solar farm', 'wind farm', 'battery storage', 'ev charging',
    'hydrogen', 'carbon capture', 'ccs',
})

# Category B: economic signal
_CAT_B = frozenset({
    'million', 'billion', 'investment', 'funding', 'contract',
    'awarded', 'procurement', 'cost', 'budget', 'spend', 'spending',
    'financing', 'capital', 'c$', '$', 'loan', 'bond', 'grant',
    'subsidy', 'allocation', 'appropriation', 'estimate',
    'value', 'worth', 'price tag', 'revenue', 'expenditure',
    'infrastructure bank', 'p3', 'public-private', 'ppp',
})

# Category C: status signal
_CAT_C = frozenset({
    'proposed', 'approved', 'under construction', 'under review',
    'breaking ground', 'announced', 'commissioned', 'tender', 'rfp',
    'permit', 'rezoning', 'rezoned', 'assessment', 'phase',
    'environmental review', 'environmental assessment',
    'public consultation', 'shovels in ground', 'ribbon cutting',
    'completion', 'opening', 'operational', 'inaugurated',
    'site plan', 'building permit', 'demolition permit',
    'heritage designation', 'shovel-ready', 'shovel ready',
    'groundbreaking', 'ground breaking', 'topping off',
    'substantial completion', 'occupancy permit',
    'zoning amendment', 'official plan amendment',
    'notice of commencement', 'record of decision',
    'certificate of authorization', 'underway', 'under way',
})

# Dollar-value bypass regex: matches $X million/billion, C$X M/B,
# and French patterns like "500 millions $"
_DOLLAR_RE = re.compile(
    r'(?:\$\s*[\d,.]+\s*(?:million|billion|m\b|b\b|mil|bil)'
    r'|[\d,.]+\s*(?:million|billion|millions|milliards)\s*\$)',
    re.IGNORECASE,
)


def _has_any(text: str, keywords: frozenset) -> bool:
    """Check if text contains any keyword from the set."""
    for kw in keywords:
        if kw in text:
            return True
    return False


def _has_dollar_value(text: str, min_millions: float = 1.0) -> bool:
    """Check if text mentions a dollar value >= min_millions."""
    for match in _DOLLAR_RE.finditer(text):
        snippet = match.group(0).lower()
        # Extract the numeric part
        num_str = re.search(r'[\d,.]+', snippet)
        if not num_str:
            continue
        try:
            val = float(num_str.group(0).replace(',', ''))
            if 'billion' in snippet or snippet.endswith('b') or 'bil' in snippet:
                val *= 1000
            if val >= min_millions:
                return True
        except ValueError:
            continue
    return False


def layer1_keyword_check(title: str, summary: str = '') -> bool:
    """
    Layer 1: Compound keyword co-occurrence.
    Returns True if:
      (≥1 from A) AND (≥1 from B OR ≥1 from C)
      OR dollar-value bypass (≥$1M mentioned anywhere in title+summary)
    """
    text = (title + ' ' + summary).lower()

    # Dollar-value bypass: any article mentioning ≥$1M is likely project-relevant
    if _has_dollar_value(text):
        return True

    if not _has_any(text, _CAT_A):
        return False
    return _has_any(text, _CAT_B) or _has_any(text, _CAT_C)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — NEGATIVE KEYWORD EXCLUSION
# ══════════════════════════════════════════════════════════════════════════════

# Crime / legal — cleaned to avoid false negatives
# Removed: 'fraud' (procurement fraud is relevant), 'bail' (financial bailout),
#          'arson' (fire-rebuild stories), 'warrant' (could be financial)
_REJECT_CRIME = frozenset({
    'homicide', 'murder', 'assault', 'robbery', 'arrest', 'charged',
    'sentenced', 'verdict', 'guilty', 'plea', 'trafficking', 'shooting',
    'stabbing', 'manslaughter', 'parole', 'inquest', 'sexual assault',
    'embezzlement', 'extradition', 'indicted',
    'convicted', 'crime', 'theft', 'kidnapping', 'missing person',
})

# Sports — cleaned to avoid false negatives
# Removed: 'goal' (project goals), 'draft pick' (kept 'nhl draft'),
#          'scored' (could be in financial context)
_REJECT_SPORTS = frozenset({
    'nhl', 'cfl', 'nba', 'mlb', 'mls', 'chl', 'whl', 'ohl', 'qmjhl',
    'playoff', 'roster', 'free agent', 'trade deadline',
    'tournament', 'championship', 'hat trick', 'shutout',
    'touchdown', 'assists', 'standings', 'preseason', 'grey cup',
    'stanley cup', 'world series', 'all-star',
})

# Entertainment / lifestyle
_REJECT_ENTERTAINMENT = frozenset({
    'concert', 'festival lineup', 'album', 'box office',
    'grammy', 'award show', 'celebrity', 'red carpet', 'recipe',
    'restaurant review', 'fashion', 'travel tips', 'obituary',
})
# Removed: 'film' (film studio construction), 'movie', 'wedding', 'birth',
#          'funeral' (too generic, can appear in infrastructure context)

# Health / medical (non-facility)
_REJECT_HEALTH = frozenset({
    'patient', 'diagnosis', 'outbreak', 'vaccination', 'covid case',
    'overdose', 'opioid death', 'flu season', 'infection rate',
    'drug recall', 'symptom',
})
# Removed: 'clinical trial' (pharma facility construction is relevant)

# Weather / disaster (non-reconstruction)
_REJECT_WEATHER = frozenset({
    'flood warning', 'wildfire evacuation', 'tornado watch', 'blizzard',
    'amber alert', 'weather advisory', 'wind chill', 'heat wave',
    'storm surge',
})
# Removed: 'power outage' (grid infrastructure stories can mention outages)

# General politics (non-spending)
_REJECT_POLITICS = frozenset({
    'polling', 'approval rating', 'caucus', 'leadership race', 'debate',
    'campaign trail', 'endorsement', 'resignation', 'scandal',
    'controversy', 'ethics probe',
})

_ALL_REJECT = (
    _REJECT_CRIME | _REJECT_SPORTS | _REJECT_ENTERTAINMENT
    | _REJECT_HEALTH | _REJECT_WEATHER | _REJECT_POLITICS
)


def layer2_negative_check(title: str) -> bool:
    """
    Layer 2: Negative keyword exclusion on title only.
    Returns True if article should be REJECTED (contains exclusion term).
    """
    title_lower = title.lower()
    for term in _ALL_REJECT:
        if term in title_lower:
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — GEMINI FLASH BATCH PRE-SCREEN
# ══════════════════════════════════════════════════════════════════════════════

GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

_L3_PROMPT = """\
Classify each headline+summary as RELEVANT or NOT_RELEVANT for a Canadian capital projects tracker.

RELEVANT means it describes ANY of these:
- NEW BUILD: new facility, plant, building, infrastructure (greenfield)
- RENOVATION/RETROFIT: major renovation, deep retrofit, energy upgrade, seismic upgrade
- ADAPTIVE REUSE: converting an existing building to a new use (e.g. office -> residential)
- EXPANSION: adding capacity to an existing facility (new wing, new phase, new line)
- REDEVELOPMENT: demolition and rebuild, brownfield remediation, site revitalization
- MODERNIZATION: significant upgrade of existing infrastructure (e.g. transit modernization)
- REAL ESTATE DEVELOPMENT: condo towers, mixed-use projects, housing developments
- GOVERNMENT SPENDING: infrastructure funding announcements, procurement awards, P3 projects
- INDUSTRIAL: mine development, refinery, pipeline, LNG terminal, manufacturing plant
- ENERGY: solar farm, wind farm, battery storage, transmission line, hydrogen facility

NOT_RELEVANT means:
- Crime, court proceedings, sentencing, arrests
- Sports scores, trades, playoffs, team news
- Entertainment, concerts, festivals, celebrity news
- General politics without infrastructure spending
- Weather alerts, disaster warnings (unless about reconstruction funding)
- Health news, outbreaks, clinical results (unless about facility construction)
- Stories where a dollar figure is incidental (lawsuit settlement, fine, salary)
- Opinion/editorial without specific project details

Return ONLY a JSON array of the indices that are RELEVANT. Example: [0, 2, 5]

"""


def layer3_gemini_prescreen(
    articles: list[dict],
    batch_size: int = 20,
    gemini_client=None,
) -> list[int]:
    """
    Layer 3: Gemini Flash batch classification.
    Returns list of indices (from the input list) that are RELEVANT.

    Each article dict should have 'title' and optionally 'summary'.
    """
    if not articles:
        return []
    if not gemini_client:
        # No client — pass everything through (fail open)
        return list(range(len(articles)))

    from google.genai import types

    relevant_indices = []

    for batch_start in range(0, len(articles), batch_size):
        batch = articles[batch_start:batch_start + batch_size]
        items_text = '\n'.join(
            f"[{i}] {a.get('title', '')} — {(a.get('summary', '') or '')[:150]}"
            for i, a in enumerate(batch)
        )

        prompt = _L3_PROMPT + items_text

        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    max_output_tokens=512,
                ),
            )
            raw = response.text.strip()
            indices = json.loads(raw)
            if isinstance(indices, list):
                for idx in indices:
                    if isinstance(idx, int) and 0 <= idx < len(batch):
                        relevant_indices.append(batch_start + idx)
        except Exception as e:
            # On error, pass everything in this batch through
            print(f"  [Filter L3] Gemini pre-screen error: {type(e).__name__}")
            relevant_indices.extend(range(batch_start, batch_start + len(batch)))

    return relevant_indices


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED FILTER
# ══════════════════════════════════════════════════════════════════════════════

def filter_articles(
    articles: list[dict],
    gemini_client=None,
    skip_layer1: bool = False,
    skip_layer2: bool = False,
    log_filtered: bool = True,
) -> list[dict]:
    """
    Run articles through the three-layer filter stack.

    Args:
        articles: list of dicts with 'title' and optionally 'summary'.
        gemini_client: Gemini client for Layer 3. If None, Layer 3 is skipped.
        skip_layer1: If True, skip keyword co-occurrence (for government feeds).
        skip_layer2: If True, skip negative keyword exclusion
                     (for infrastructure/procurement government feeds).
        log_filtered: If True, log rejected articles to filtered_{date}.txt.

    Returns:
        List of articles that passed all layers.
    """
    if not articles:
        return []

    initial_count = len(articles)
    filtered_out = []

    # Layer 1: Keyword co-occurrence (+ dollar-value bypass)
    if not skip_layer1:
        passed_l1 = []
        for art in articles:
            if layer1_keyword_check(art.get('title', ''), art.get('summary', '')):
                passed_l1.append(art)
            else:
                filtered_out.append(('L1', art))
        articles = passed_l1

    # Layer 2: Negative keyword exclusion
    if not skip_layer2:
        passed_l2 = []
        for art in articles:
            if not layer2_negative_check(art.get('title', '')):
                passed_l2.append(art)
            else:
                filtered_out.append(('L2', art))
        articles = passed_l2

    # Layer 3: Gemini batch pre-screen
    if gemini_client and articles:
        relevant_idx = layer3_gemini_prescreen(articles, gemini_client=gemini_client)
        relevant_set = set(relevant_idx)
        passed_l3 = []
        for i, art in enumerate(articles):
            if i in relevant_set:
                passed_l3.append(art)
            else:
                filtered_out.append(('L3', art))
        articles = passed_l3

    l1_cut = sum(1 for layer, _ in filtered_out if layer == 'L1')
    l2_cut = sum(1 for layer, _ in filtered_out if layer == 'L2')
    l3_cut = sum(1 for layer, _ in filtered_out if layer == 'L3')
    print(f"  [Filter] {initial_count} -> {len(articles)} "
          f"(L1: -{l1_cut}, L2: -{l2_cut}, L3: -{l3_cut})")

    # Log filtered articles for review
    if log_filtered and filtered_out:
        try:
            log_path = f'filtered_{TODAY}.txt'
            with open(log_path, 'a', encoding='utf-8') as f:
                for layer, art in filtered_out:
                    f.write(f"[{layer}] {art.get('title', '?')[:120]}\n")
        except Exception:
            pass

    return articles


# ══════════════════════════════════════════════════════════════════════════════
# VERIFICATION TEST HARNESS
# ══════════════════════════════════════════════════════════════════════════════

def run_filter_tests():
    """
    Verify the remediated filter catches brownfield projects and rejects noise.
    Run with: python -c "from article_filter import run_filter_tests; run_filter_tests()"
    """
    # Should PASS Layer 1 (brownfield/renovation vocabulary)
    _SHOULD_PASS = [
        ("$200M hospital renovation announced for Halifax", "Major seismic retrofit"),
        ("City approves $45 million adaptive reuse of heritage warehouse", "Mixed-use conversion"),
        ("Province invests $1.2 billion in transit modernization", "LRT expansion"),
        ("Deep energy retrofit planned for 50 federal buildings", "$800M program"),
        ("Condo tower redevelopment approved at former industrial site", "Brownfield remediation"),
        ("$150M long-term care facility expansion in Sudbury", "Adding 200 beds"),
        ("New $500M hydrogen production facility proposed", "Green hydrogen plant"),
        ("Government announces $3.2 billion infrastructure spending", "Roads and bridges"),
        ("Mixed-use development breaks ground downtown", "$90 million project"),
        ("Battery storage facility approved near Calgary", "$65M investment"),
        ("Highway interchange reconstruction begins", "$180M contract awarded"),
        ("Water treatment plant upgrade underway", "Modernization of filtration systems"),
    ]

    # Should FAIL Layer 1 (no project signal)
    _SHOULD_FAIL_L1 = [
        ("Interest rate announcement expected tomorrow", "BoC policy update"),
        ("Employment figures rise in March", "Statistics Canada release"),
        ("Canadian dollar weakens against USD", "Currency markets"),
    ]

    # Should be REJECTED by Layer 2 (negative keywords)
    _SHOULD_REJECT_L2 = [
        ("Man sentenced for $2M robbery of construction site", ""),
        ("NHL playoff schedule announced for Canadian teams", ""),
        ("Murder charge laid in downtown shooting", ""),
    ]

    # Should NOT be rejected by Layer 2 (cleaned negatives)
    _SHOULD_NOT_REJECT_L2 = [
        ("Fire-damaged arena to be rebuilt with $50M investment", ""),
        ("Project goals met for Phase 2 of LRT", ""),
        ("Bail-out package includes infrastructure funding", ""),
    ]

    print("\n" + "=" * 60)
    print("  ARTICLE FILTER — STEP_2B VERIFICATION")
    print("=" * 60)

    passed = 0
    failed = 0

    print("\n  Layer 1 — Should PASS:")
    for title, summary in _SHOULD_PASS:
        result = layer1_keyword_check(title, summary)
        icon = "PASS" if result else "FAIL"
        if result:
            passed += 1
        else:
            failed += 1
        print(f"    [{icon}] {title[:70]}")

    print("\n  Layer 1 — Should FAIL (not project-relevant):")
    for title, summary in _SHOULD_FAIL_L1:
        result = layer1_keyword_check(title, summary)
        icon = "PASS" if not result else "FAIL"
        if not result:
            passed += 1
        else:
            failed += 1
        print(f"    [{icon}] {title[:70]}")

    print("\n  Layer 2 — Should REJECT:")
    for title, _ in _SHOULD_REJECT_L2:
        result = layer2_negative_check(title)
        icon = "PASS" if result else "FAIL"
        if result:
            passed += 1
        else:
            failed += 1
        print(f"    [{icon}] {title[:70]}")

    print("\n  Layer 2 — Should NOT reject (cleaned negatives):")
    for title, _ in _SHOULD_NOT_REJECT_L2:
        result = layer2_negative_check(title)
        icon = "PASS" if not result else "FAIL"
        if not result:
            passed += 1
        else:
            failed += 1
        print(f"    [{icon}] {title[:70]}")

    print(f"\n  {'=' * 60}")
    print(f"  RESULTS: {passed} passed, {failed} failed out of "
          f"{passed + failed} tests")
    print(f"  {'=' * 60}\n")

    return failed == 0
