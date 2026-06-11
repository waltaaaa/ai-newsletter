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

from nim_client import get_client as get_nim_client
from pipeline_config import NIM_CLASSIFY_MODEL

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
    # Phase 1 additions — generic facility terms
    'installation', 'complex', 'centre', 'center',
    'hub', 'park', 'depot', 'station', 'works',
    'building', 'structure',
    # Generic action terms
    'construct', 'develop', 'expand',
    'modernize', 'renovate', 'demolish',
    'commission',
    # Generic scale terms
    'mega', 'major', 'significant', 'largest', 'massive',
    'world-class', 'state-of-the-art', 'first-of-its-kind',
    # Milestone terms
    'sod turning', 'financial close', 'fid', 'final investment decision',
    # Data centres and digital
    'hyperscale', 'colocation',
    # Clean energy
    'battery plant', 'gigafactory', 'ev factory', 'hydrogen plant',
    'clean fuel', 'ccus', 'smr', 'small modular reactor',
    # Defence
    'shipbuilding', 'naval', 'military base', 'defence procurement',
    # Tourism/culture
    'convention centre', 'convention center',
    'hotel development', 'resort',
    # Agriculture/food
    'food processing', 'grain terminal', 'canola crushing',
    'fertilizer plant', 'agri-food', 'greenhouse',
    # Phase 3 additions — redevelopment and real estate
    'urban renewal', 'master plan', 'master-planned',
    'condo tower', 'residential tower', 'office tower',
    'commercial development', 'transit-oriented', 'rezoning', 'brownfield',
    # Phase 3 — digital
    'fibre optic', 'fiber optic', '5g tower',
    # Phase 3 — milestone terms (also in Cat A for co-occurrence)
    'groundbreaking', 'ribbon cutting',
    'topping off', 'substantial completion',
    # Phase 3 — French Cat A
    'projet', 'investissement', 'agrandissement',
    'usine', 'installation', 'infrastructure', 'développement',
    'aménagement', 'réaménagement', 'mise en chantier',
    'milliard', 'million de dollars',
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

# quality-pass-1.4 G9: French Category B (economic signal) — ADDITIVE.
# Cat A and Cat C already carry French vocabulary (Phase 3) but Cat B was
# anglo-only, so French articles with a clear economic signal failed the
# A ∩ (B ∪ C) co-occurrence unless a Cat C status word happened to appear.
# Both apostrophe variants (' and ') are included for "appel d'offres" /
# "étude de faisabilité"-style phrases copied from different encodings.
_CAT_B_FR = frozenset({
    'financement', 'contrat', 'coût', 'cout', 'budget', 'subvention',
    "appel d'offres", 'appel d’offres', 'milliards', 'millions',
    'investissement', 'retombées', 'retombees', 'chantier', 'travaux',
    'mise en service', 'étude de faisabilité', 'etude de faisabilite',
    'étude de faisabilité', 'dépenses', 'depenses',
    'immobilisations', 'enveloppe budgétaire', 'enveloppe budgetaire',
    'octroi', 'adjudication', 'soumission', 'devis',
})

# Combined Cat B used everywhere Cat B is checked (additive only — the
# original _CAT_B is never reduced).
_CAT_B_ALL = _CAT_B | _CAT_B_FR

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
    # Phase 1 additions
    'broke ground', 'shovels in ground', 'green light',
    'given the go-ahead', 'received approval', 'regulatory approval',
    'environmental assessment complete', 'building permit issued',
    'construction permit', 'zoning approved', 'rezoning approved',
    'fid reached', 'reached financial close', 'secured financing',
    'awarded contract', 'contract awarded to',
    # Phase 3 — French Cat C
    'approuvé', 'approbation', 'autorisé', 'permis de construire',
    'début des travaux', 'achèvement', 'inauguration',
    'annulé', 'reporté', 'retardé',
})

# Dollar-value bypass regex: matches $X million/billion, C$X M/B,
# and French patterns like "500 millions $"
_DOLLAR_RE = re.compile(
    r'(?:\$\s*[\d,.]+\s*(?:million|billion|m\b|b\b|mil|bil)'
    r'|[\d,.]+\s*(?:million|billion|millions|milliards)\s*\$)',
    re.IGNORECASE,
)


# ── L2b bypass: Canadian location + any dollar mention ──

_CANADIAN_PROVINCES = frozenset({
    'ontario', 'quebec', 'québec', 'alberta', 'british columbia',
    'saskatchewan', 'manitoba', 'nova scotia', 'new brunswick',
    'newfoundland', 'labrador', 'prince edward island', 'pei',
    'yukon', 'northwest territories', 'nunavut',
    'canada', 'canadian',
})

_CANADIAN_CMAS = frozenset({
    'toronto', 'montreal', 'montréal', 'vancouver', 'calgary',
    'edmonton', 'ottawa', 'winnipeg', 'quebec city', 'hamilton',
    'kitchener', 'waterloo', 'london', 'halifax', 'victoria',
    'windsor', 'oshawa', 'saskatoon', 'regina', 'barrie',
    'kelowna', 'abbotsford', 'sherbrooke', 'guelph', 'moncton',
    'saint john', 'fredericton', 'sudbury', 'thunder bay',
    'trois-rivières', 'brantford', 'peterborough', 'lethbridge',
    'red deer', 'kamloops', "st. john's", 'charlottetown',
    'gatineau', 'niagara', 'st. catharines',
})

_ALL_CANADIAN_LOCATIONS = _CANADIAN_PROVINCES | _CANADIAN_CMAS


_CANADIAN_LOCATION_RE = re.compile(
    '|'.join(re.escape(loc) for loc in sorted(_ALL_CANADIAN_LOCATIONS, key=len, reverse=True)),
    re.IGNORECASE,
)


def _mentions_canadian_location(text: str) -> bool:
    """Check if text mentions any Canadian province or CMA."""
    return bool(_CANADIAN_LOCATION_RE.search(text))


_ANY_DOLLAR_RE = re.compile(
    r'\$\s*[\d,.]+|\d+\s*(?:million|billion|mil|bil|milliard)',
    re.IGNORECASE,
)


def _has_any_dollar_mention(text: str) -> bool:
    """Check if text contains any dollar figure (no minimum threshold)."""
    return bool(_ANY_DOLLAR_RE.search(text))


def _compile_keyword_re(keywords: frozenset) -> re.Pattern:
    """Compile a frozenset of keywords into a single regex for fast substring search."""
    # Sort by length descending so longer matches take priority
    sorted_kws = sorted(keywords, key=len, reverse=True)
    return re.compile('|'.join(re.escape(kw) for kw in sorted_kws))


# Pre-compiled keyword patterns (built once at import time)
# G9: Cat B compiles the combined EN+FR set.
_CAT_A_RE = _compile_keyword_re(_CAT_A)
_CAT_B_RE = _compile_keyword_re(_CAT_B_ALL)
_CAT_C_RE = _compile_keyword_re(_CAT_C)


def _has_any(text: str, keywords: frozenset, compiled_re: re.Pattern = None) -> bool:
    """Check if text contains any keyword from the set.

    When compiled_re is provided (pre-compiled at module load), uses fast
    single-pass regex. Falls back to linear scan for ad-hoc keyword sets.
    """
    if compiled_re is not None:
        return bool(compiled_re.search(text))
    return any(kw in text for kw in keywords)


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

    # L2: Dollar-value bypass: any article mentioning ≥$1M is likely project-relevant
    if _has_dollar_value(text):
        return True

    # L2b: Any dollar mention + Canadian location → pass to L6 Gemini classification
    if _has_any_dollar_mention(text) and _mentions_canadian_location(text):
        return True

    # L4: Keyword co-occurrence (Cat B includes the French additions, G9)
    if not _has_any(text, _CAT_A, _CAT_A_RE):
        return False
    return _has_any(text, _CAT_B_ALL, _CAT_B_RE) or _has_any(text, _CAT_C, _CAT_C_RE)


def layer1_strength(title: str, summary: str = '') -> str:
    """Return L1 match strength: 'strong', 'bypass', or 'none'.

    'strong' = Cat A + (Cat B or Cat C) all matched via keywords.
    'bypass' = passed only via dollar-value bypass or location+dollar bypass.
    'none'   = did not pass L1.
    """
    text = (title + ' ' + summary).lower()
    has_a = _has_any(text, _CAT_A, _CAT_A_RE)
    has_bc = _has_any(text, _CAT_B_ALL, _CAT_B_RE) or _has_any(text, _CAT_C, _CAT_C_RE)
    if has_a and has_bc:
        return "strong"
    if _has_dollar_value(text):
        return "bypass"
    if _has_any_dollar_mention(text) and _mentions_canadian_location(text):
        return "bypass"
    return "none"


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


_ALL_REJECT_RE = _compile_keyword_re(_ALL_REJECT)


def layer2_negative_check(title: str) -> bool:
    """
    Layer 2: Negative keyword exclusion on title only.
    Returns True if article should be REJECTED (contains exclusion term).
    """
    return bool(_ALL_REJECT_RE.search(title.lower()))


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
- DATA CENTRES: hyperscale, colocation, cloud infrastructure facilities
- CLEAN ENERGY TRANSITION: carbon capture, CCUS, EV charging, biofuels, hydrogen
- DEFENCE AND MILITARY: base construction, shipbuilding, military facility upgrades
- WATER AND WASTEWATER: treatment plants, stormwater, flood protection
- INSTITUTIONAL: museums, libraries, community centres, government buildings

Be INCLUSIVE. If the article describes spending money to build or improve something physical in Canada, it is relevant. If uncertain, classify as RELEVANT.

Do NOT reject articles because they describe a project type you haven't seen before. A "vertical farm," "quantum computing lab," "space launch facility," "modular housing factory," or "AI training data centre" are all relevant if they involve construction or capital investment in Canada.

NOT_RELEVANT means:
- Crime, court proceedings, sentencing, arrests
- Sports scores, trades, playoffs, team news
- Entertainment, concerts, festivals, celebrity news
- General politics without infrastructure spending
- Weather alerts, disaster warnings (unless about reconstruction funding)
- Health news, outbreaks, clinical results (unless about facility construction)
- Stories where a dollar figure is incidental (lawsuit settlement, fine, salary)
- Opinion/editorial without specific project details

Return a JSON array with one object per input article (same order as input). Each object must have:
{
  "index": <int>,
  "is_relevant": <bool>,
  "is_canadian": <bool>,
  "is_project_related": <bool>,
  "likely_province": "<two-letter code or null>",
  "likely_sector": "<sector name or null>",
  "likely_event_type": "<announcement|approval|construction_start|completion|funding|cancellation|null>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one sentence>",
  "has_dollar_value": <bool>,
  "estimated_value_range": "<e.g. '100M-500M' or null>",
  "likely_source_type": "<gov_newsroom|trade_publication|business_media|local_news|aggregator>"
}

"""


_NIM_CLASSIFY_PROMPT = """\
Classify each numbered headline for a Canadian capital projects and economic development tracker.

R = RELEVANT. Includes: construction, renovation, retrofit, expansion, infrastructure, \
housing development, condo towers, mixed-use, transit, highway, bridge, energy (solar, wind, \
LNG, pipeline, nuclear, hydrogen, battery), mining, data centres, defence, water/wastewater, \
institutional (hospital, school, arena), government capital spending, P3, funding announcements, \
building permits, housing starts, industrial facilities, environmental remediation, adaptive reuse.

I = IRRELEVANT. Only: sports scores/trades/playoffs, crime/court/sentencing, entertainment/concerts, \
weather alerts, health outbreaks, opinion/editorial without project details, dollar figures that are \
lawsuits/salaries/fines.

If uncertain, output R.

Output format: one line per headline — number, period, R or I. Nothing else.

Example:
1.R
2.I
3.R"""


def _degraded_keyword_pass(article: dict) -> bool:
    """quality-pass-1.4 G6: tightened keyword bar for full-chain L6 failure.

    When BOTH free classifier tiers (NIM and Groq) are down, instead of
    passing every borderline article we keep only those that clear a
    tightened bar:
      - a dollar-value regex match (reuses _DOLLAR_RE), OR
      - triple keyword co-occurrence: Cat A AND Cat B AND Cat C.

    Government-bypass articles never reach L6 (skip_layer1 feeds leave them
    with no _l1_strength, which defaults to 'strong' and skips L6 entirely),
    and dollar-bypass articles satisfy the dollar-regex arm by construction —
    so everything that arrived via a bypass invariant still passes.
    """
    text = (f"{article.get('title', '')} "
            f"{article.get('summary', '') or ''}").lower()
    if _DOLLAR_RE.search(text):
        return True
    return (_has_any(text, _CAT_A, _CAT_A_RE)
            and _has_any(text, _CAT_B_ALL, _CAT_B_RE)
            and _has_any(text, _CAT_C, _CAT_C_RE))


def _record_l6_fail_open(reason: str):
    """Record a fail-open event on the l6_classifier service (best-effort)."""
    try:
        import service_health
        service_health.get().record_failure('l6_classifier', reason)
    except Exception:
        pass


# Fail-open passes exceeding this fraction of L6 input triggers a WARN.
_L6_FAIL_OPEN_WARN_FRAC = 0.10


def layer3_gemini_prescreen(
    articles: list[dict],
    batch_size: int = 20,
    gemini_client=None,
    conn=None,
) -> list[int]:
    """
    Layer 6: LLM batch classification.
    Fallback chain: NIM Nemotron Super 120B → Groq LLaMA 3.3 70B →
    degraded keyword-only mode (G6: tightened bar, NOT pass-everything).
    Returns list of indices (from the input list) that are RELEVANT.
    """
    if not articles:
        return []

    # Try NIM Nemotron Super 120B first
    try:
        nim = get_nim_client()
        relevant_indices = []
        fail_open_passes = 0  # G6: missing-verdict passes
        for batch_start in range(0, len(articles), batch_size):
            batch = articles[batch_start:batch_start + batch_size]
            batch_text = "\n".join(
                f"{j+1}. {a.get('title', '')} — {(a.get('summary', '') or '')[:150]}"
                for j, a in enumerate(batch)
            )
            resp = nim.chat_sync(
                model=NIM_CLASSIFY_MODEL,
                messages=[
                    {"role": "system", "content": _NIM_CLASSIFY_PROMPT},
                    {"role": "user", "content": batch_text},
                ],
                max_tokens=len(batch) * 5 + 20,
                temperature=0.1,
                thinking=False,
            )
            verdicts = re.findall(r'(\d+)\.([RI])', resp, re.IGNORECASE)
            result_map = {int(num): v.upper() for num, v in verdicts}
            for j in range(len(batch)):
                if (j + 1) not in result_map:
                    fail_open_passes += 1  # fail-open: missing verdict = R
                v = result_map.get(j + 1, "R")  # fail-open if missing
                if v == "R":
                    relevant_indices.append(batch_start + j)
        print(f"  [Filter L6] NIM Nemotron: {len(relevant_indices)}/{len(articles)} relevant")
        # G6: fail-open rate alerting (normal per-verdict fail-open stays
        # untouched — this only surfaces an abnormal rate).
        if fail_open_passes > _L6_FAIL_OPEN_WARN_FRAC * len(articles):
            print(f"  [Filter L6 WARN] fail-open passes {fail_open_passes}/"
                  f"{len(articles)} exceed {_L6_FAIL_OPEN_WARN_FRAC:.0%} of L6 input "
                  f"(missing verdicts defaulted to RELEVANT)")
            _record_l6_fail_open(
                f"missing-verdict fail-open {fail_open_passes}/{len(articles)}")
        return relevant_indices
    except Exception as e:
        print(f"  [Filter L6] NIM failed, falling back to Groq: {e}")

    # Try Groq LLaMA 3.3 70B
    try:
        import groq_client
        if groq_client.can_use_groq():
            relevant_indices = groq_client.batch_classify(articles, _L3_PROMPT, batch_size=batch_size)
            print(f"  [Filter L6] Groq: {len(relevant_indices)}/{len(articles)} relevant")
            return relevant_indices
    except ImportError:
        pass
    except Exception as e:
        print(f"  [Filter L6] Groq failed: {type(e).__name__}: {e}")

    # G6 DEGRADED MODE: both free tiers are down. Previously this branch
    # passed ALL articles through; now only articles clearing the tightened
    # keyword bar (dollar regex OR Cat A+B+C triple co-occurrence) survive.
    # Everything kept here is a fail-open pass — counted and alerted.
    kept = [i for i, art in enumerate(articles) if _degraded_keyword_pass(art)]
    print(f"  [Filter L6 DEGRADED] keyword-only mode: kept {len(kept)} of "
          f"{len(articles)} (NIM and Groq both unavailable)")
    if len(kept) > _L6_FAIL_OPEN_WARN_FRAC * len(articles):
        print(f"  [Filter L6 WARN] fail-open passes {len(kept)}/{len(articles)} "
              f"exceed {_L6_FAIL_OPEN_WARN_FRAC:.0%} of L6 input "
              f"(full classifier-chain failure)")
    _record_l6_fail_open(
        f"full-chain failure: keyword-only kept {len(kept)}/{len(articles)}")
    return kept


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED FILTER
# ══════════════════════════════════════════════════════════════════════════════

def _article_language(art: dict) -> str:
    """quality-pass-1.4 G9: best-effort language hint for an article.

    Sources of truth, in priority order:
      1. `_language` (Google/Bing News RSS search articles)
      2. `language` (some feed dicts)
      3. feed-category metadata (rss_monitor items carry `category`,
         e.g. 'regional_media_fr' → French)
    Defaults to 'en'.
    """
    lang = art.get('_language') or art.get('language')
    if lang:
        return 'fr' if str(lang).lower().startswith('fr') else 'en'
    cat = str(art.get('category') or art.get('_feed_category') or '').lower()
    if cat.endswith('_fr') or cat == 'fr':
        return 'fr'
    return 'en'


def filter_articles(
    articles: list[dict],
    gemini_client=None,
    skip_layer1: bool = False,
    skip_layer2: bool = False,
    log_filtered: bool = True,
    conn=None,
    record_documents: bool = False,
    doc_source_type: str = 'news',
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
        conn: Optional SQLite connection for document dedup check.
        record_documents: If True (and conn given), record documents for every
            article that COMPLETED L6/L7 classification — both survivors and
            L6/L7 rejects. Deterministic L1/L2 cuts are intentionally NOT
            recorded so a keyword added next week can still rescue them.
        doc_source_type: source_type stamped on recorded documents
            (e.g. 'google_news', 'bing_news').

    Returns:
        List of articles that passed all layers.
    """
    if not articles:
        return []

    # Layer 0: Skip articles already processed in documents table
    if conn:
        try:
            from db import is_already_processed
            pre_count = len(articles)
            articles = [
                a for a in articles
                if not is_already_processed(conn, a.get('url', a.get('link', '')))[0]
            ]
            skipped = pre_count - len(articles)
            if skipped:
                print(f"  [Filter L0] {skipped} already-processed URLs skipped")
        except Exception:
            pass

    initial_count = len(articles)
    filtered_out = []

    # Layer 1: Keyword co-occurrence (+ dollar-value bypass + metadata boost)
    # Also track L1 strength to skip L3 for strong keyword matches.
    if not skip_layer1:
        passed_l1 = []
        meta_boost_passed = 0
        for art in articles:
            # Metadata boost: articles pre-tagged with sector by domain or feed
            # bypass L1 keyword check (still go through L2 negative + L3 LLM)
            if art.get('meta_sectors'):
                art['_l1_strength'] = 'meta'
                meta_boost_passed += 1
                passed_l1.append(art)
            elif layer1_keyword_check(art.get('title', ''), art.get('summary', '')):
                art['_l1_strength'] = layer1_strength(
                    art.get('title', ''), art.get('summary', ''))
                passed_l1.append(art)
            else:
                filtered_out.append(('L1', art))
        articles = passed_l1
        if meta_boost_passed:
            print(f"  [Filter L1] metadata-boost passed {meta_boost_passed}")

    # Layer 2: Negative keyword exclusion
    if not skip_layer2:
        passed_l2 = []
        for art in articles:
            if not layer2_negative_check(art.get('title', '')):
                passed_l2.append(art)
            else:
                filtered_out.append(('L2', art))
        articles = passed_l2

    # Layer 6: LLM batch pre-screen (local LLM → Groq → fail-open).
    # Skip L6 for articles with strong L1 keyword matches — they already have
    # Cat A + (Cat B or Cat C), so the LLM call adds little value. Only send
    # borderline articles (dollar-bypass, metadata-boost) for LLM verification.
    if articles:
        strong_articles = []
        borderline_articles = []
        borderline_indices = []
        for i, art in enumerate(articles):
            strength = art.pop('_l1_strength', 'strong')
            if strength == 'strong':
                strong_articles.append(art)
            else:
                borderline_articles.append(art)
                borderline_indices.append(i)

        if borderline_articles:
            l6_skipped = len(strong_articles)
            relevant_idx = layer3_gemini_prescreen(
                borderline_articles, gemini_client=gemini_client, conn=conn)
            relevant_set = set(relevant_idx)
            passed_l6 = list(strong_articles)
            for i, art in enumerate(borderline_articles):
                if i in relevant_set:
                    passed_l6.append(art)
                else:
                    filtered_out.append(('L6', art))
            if l6_skipped:
                print(f"  [Filter L6] {l6_skipped} strong-match articles skipped L6")
            articles = passed_l6
        else:
            # All articles are strong matches — skip L6 entirely
            articles = strong_articles
            print(f"  [Filter L6] All {len(articles)} articles are strong matches, L6 skipped")
    else:
        # Clean up _l1_strength if L3 was skipped
        for art in articles:
            art.pop('_l1_strength', None)

    # Layer 7: NIM Rerank — relevance FILTER, not a top-N cap.
    #
    # D-11 fix (2026-06-08 audit): the previous implementation passed
    # top_n=min(50, N) and nim_client truncated to the first 512 passages, so a
    # 25k-article discovery batch was scored only for its first 512 entries and
    # then capped to the top 50 — dropping ~99% of articles as "L7" and starving
    # extraction. Rerank must DROP clearly-irrelevant articles, never impose a
    # fixed survivor count. We now:
    #   1. Score EVERY article, chunked in <=RERANK_MAX_PASSAGES batches.
    #   2. Keep everything at/above RERANK_MIN_LOGIT (unscored => fail-open keep).
    #   3. Apply a SANITY GUARD: if rerank would keep < RERANK_SANITY_KEEP_FRAC of
    #      the L6 set, distrust it (API fault / wrong threshold) and keep L6 whole.
    RERANK_MIN_LOGIT = float(os.environ.get('RERANK_MIN_LOGIT', '-2.0'))
    RERANK_CHUNK = int(os.environ.get('RERANK_MAX_PASSAGES', '512'))
    RERANK_MIN_BATCH = int(os.environ.get('RERANK_MIN_BATCH', '50'))   # don't bother below this
    RERANK_SANITY_KEEP_FRAC = float(os.environ.get('RERANK_SANITY_KEEP_FRAC', '0.2'))
    nim_rerank_enabled = os.environ.get('NIM_RERANK_ENABLED', 'true').lower() == 'true'
    passed_l6_count = len(articles)
    if nim_rerank_enabled and len(articles) > RERANK_MIN_BATCH:
        try:
            nim = get_nim_client()
            rerank_query = (
                "Canadian infrastructure capital project construction development "
                "investment funding announcement approval"
            )
            passages = [
                f"{a.get('title', '')} — {(a.get('summary', '') or '')[:200]}"
                for a in articles
            ]
            # Score every article (chunked). logits[i] stays None if the API never
            # returned a score for it (then it is kept, fail-open).
            logits = [None] * len(articles)
            n_chunks = (len(passages) + RERANK_CHUNK - 1) // RERANK_CHUNK
            for ci in range(n_chunks):
                lo = ci * RERANK_CHUNK
                hi = min(lo + RERANK_CHUNK, len(passages))
                chunk = passages[lo:hi]
                ranked = nim.rerank_sync(query=rerank_query, passages=chunk, top_n=len(chunk))
                for r in (ranked or []):
                    idx = r.get("index", -1)
                    if 0 <= idx < len(chunk):
                        logits[lo + idx] = r.get("logit", None)
                if n_chunks > 1:
                    print(f"  [Filter L7] reranked chunk {ci + 1}/{n_chunks} ({hi}/{len(passages)})")
            # Stamp the relevance score on each article — Phase 3 uses it to
            # order the extraction queue so the highest-signal stories extract
            # first and a phase timeout only ever drops the low-relevance tail.
            for _i, _art in enumerate(articles):
                if logits[_i] is not None:
                    _art['_rerank_logit'] = logits[_i]
            scored = [v for v in logits if v is not None]
            if scored:
                srt = sorted(scored)
                def _pct(p):
                    return srt[min(len(srt) - 1, int(p * len(srt)))]
                print(f"  [Filter L7] logit dist min/p25/p50/p75/max = "
                      f"{srt[0]:.2f}/{_pct(.25):.2f}/{_pct(.5):.2f}/{_pct(.75):.2f}/{srt[-1]:.2f} "
                      f"(scored {len(scored)}/{len(articles)})")
            keep_indices = {i for i, v in enumerate(logits)
                            if v is None or v >= RERANK_MIN_LOGIT}
            kept_n = len(keep_indices)
            sanity_floor = max(1, int(RERANK_SANITY_KEEP_FRAC * passed_l6_count))
            if scored and kept_n < sanity_floor:
                # Rerank is almost certainly faulty (silent empty/zero scores or a
                # mis-tuned threshold). Keep the L6 set rather than ship ~nothing.
                print(f"  [Filter L7 DEGRADED] rerank kept {kept_n}/{passed_l6_count} "
                      f"(< {RERANK_SANITY_KEEP_FRAC:.0%} floor {sanity_floor}); "
                      f"distrusting rerank, keeping full L6 set")
            else:
                rerank_cut = len(articles) - kept_n
                if rerank_cut > 0:
                    for i, art in enumerate(articles):
                        if i not in keep_indices:
                            filtered_out.append(('L7', art))
                    articles = [articles[i] for i in sorted(keep_indices)]
                print(f"  [Filter L7] NIM Rerank: kept {len(articles)}, dropped {rerank_cut}")
        except Exception as e:
            print(f"  [Filter L7] NIM Rerank failed (non-fatal): {type(e).__name__}: {e}")

    l1_cut = sum(1 for layer, _ in filtered_out if layer == 'L1')
    l2_cut = sum(1 for layer, _ in filtered_out if layer == 'L2')
    l6_cut = sum(1 for layer, _ in filtered_out if layer == 'L6')
    l7_cut = sum(1 for layer, _ in filtered_out if layer == 'L7')
    print(f"  [Filter] {initial_count} -> {len(articles)} "
          f"(L1: -{l1_cut}, L2: -{l2_cut}, L6: -{l6_cut}, L7: -{l7_cut})")

    # G9: per-language pass/reject counts in the run summary. French
    # articles failing at an outsized rate is the signal this surfaces.
    lang_stats: dict[str, list[int]] = {}
    for art in articles:
        lang = _article_language(art)
        lang_stats.setdefault(lang, [0, 0])[0] += 1
    for _layer, art in filtered_out:
        lang = _article_language(art)
        lang_stats.setdefault(lang, [0, 0])[1] += 1
    if lang_stats:
        summary = "; ".join(
            f"{lang}: {p} passed / {r} rejected"
            for lang, (p, r) in sorted(lang_stats.items()))
        print(f"  [Filter lang] {summary}")

    # Doc-cache recording (E-4/E-9): persist every article that COMPLETED
    # L6/L7 classification — survivors AND L6/L7 rejects — so re-fetches are
    # skipped at L0 next run. Deterministic L1/L2 cuts are NOT recorded: a
    # keyword added next week must still be able to rescue them.
    if conn is not None and record_documents:
        try:
            from db import insert_document, update_document_classification
            recorded = 0
            for art, relevant in (
                [(a, True) for a in articles]
                + [(a, False) for layer, a in filtered_out if layer in ('L6', 'L7')]
            ):
                url = art.get('url') or art.get('link', '')
                if not url:
                    continue
                insert_document(conn, url,
                                title=art.get('title', ''),
                                source_tier='tier_2',
                                source_type=doc_source_type,
                                published_date=art.get('published', ''))
                update_document_classification(conn, url, relevant)
                recorded += 1
            if recorded:
                print(f"  [Filter] recorded {recorded} classified documents (doc cache)")
        except Exception as e:
            print(f"  [Filter] document recording failed (non-fatal): {type(e).__name__}: {e}")

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

# ══════════════════════════════════════════════════════════════════════════════
# REGULATORY FEED PRE-FILTER (CanLII / tribunal decisions)
# ══════════════════════════════════════════════════════════════════════════════

REGULATORY_KEYWORDS = [
    # Project types
    "construction", "development", "building permit", "site plan",
    "zoning", "official plan", "subdivision", "rezoning",
    "environmental assessment", "environmental approval",
    "compliance order", "remediation order", "stop work",
    # Infrastructure
    "pipeline", "transmission line", "generating station", "wind farm",
    "solar", "refinery", "mine", "quarry", "port", "terminal",
    "highway", "bridge", "water treatment", "wastewater",
    # Regulatory actions
    "approved", "denied", "dismissed", "granted", "suspended",
    "variance", "amendment", "certificate of approval",
    "licence", "license", "permit",
    # Parties (project proponents)
    "proponent", "applicant", "developer", "operator",
]


def is_regulatory_relevant(article: dict) -> bool:
    """Filter CanLII/regulatory feed items for project relevance.

    Requires at least 2 keyword matches in title+summary to pass.
    Intentionally loose — better to let some irrelevant legal decisions
    through to the LLM filter than to miss a pipeline approval.
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    matches = sum(1 for kw in REGULATORY_KEYWORDS if kw in text)
    return matches >= 2


# ══════════════════════════════════════════════════════════════════════════════
# REGULATORY STATUS SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

REGULATORY_STATUS_SIGNALS = {
    # Positive progression
    "approved": "Approved",
    "granted": "Approved",
    "certificate of approval": "Approved",
    "licence issued": "Approved",
    "permit issued": "Approved",
    # Negative / blocking
    "denied": "On Hold",
    "dismissed": None,  # Appeal dismissed — status unchanged
    "suspended": "Suspended",
    "stop work order": "On Hold",
    "compliance order": "Under Construction",  # Confirms active construction
    "remediation order": "Under Construction",  # Confirms site activity
    # Cancelled
    "revoked": "Cancelled",
    "withdrawn": "Cancelled",
}


def extract_regulatory_signal(article: dict) -> dict | None:
    """Extract project status signal from a regulatory decision.

    Returns a dict with signal, implied_status, source, and title,
    or None if no status signal is detected.
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    for keyword, status in REGULATORY_STATUS_SIGNALS.items():
        if keyword in text:
            return {
                "signal": keyword,
                "implied_status": status,
                "source": article.get("url", ""),
                "title": article.get("title", ""),
            }
    return None


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
