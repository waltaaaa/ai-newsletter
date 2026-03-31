"""
province_agents.py — Per-province writing agents for the analysis pipeline.

Replaces the monolithic Call 3 (single prompt for all 13 provinces) with
individual per-province agents that each receive dedicated, enriched context:
  - Province-filtered articles and RSS items
  - Province events and watchlist items (budgets, fiscal releases, policy)
  - Full policy signal text (not just counts)
  - Province-specific projects from the database
  - Province indicators and official names

This solves the context dilution problem where smaller provinces (MB, SK, NB,
PE, territories) received almost no relevant articles because Ontario/Quebec/
Alberta/BC consumed the shared 60-article budget.

Execution modes:
  - claude_code: Spawns Claude Code subprocesses (uses subscription, $0 API cost)
  - api:         Falls back to Anthropic SDK calls (for GitHub Actions / headless)

Default: claude_code.  Set PROVINCE_AGENT_MODE=api in .env to use API mode.
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

AGENT_MODE = os.environ.get('PROVINCE_AGENT_MODE', 'claude_code')  # 'claude_code' or 'api'
CLAUDE_CODE_MODEL = os.environ.get('PROVINCE_AGENT_MODEL', 'sonnet')  # claude code model flag
CLAUDE_CODE_MAX_TURNS = int(os.environ.get('PROVINCE_AGENT_MAX_TURNS', '2'))  # needs 2: read file + respond
PROVINCE_AGENT_WORKERS = int(os.environ.get('PROVINCE_AGENT_WORKERS', '4'))  # parallel agents

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

# ── Province metadata ────────────────────────────────────────────────────────

PROVINCES = [
    'Ontario', 'Quebec', 'Alberta', 'British Columbia', 'Saskatchewan',
    'Manitoba', 'Nova Scotia', 'New Brunswick', 'Newfoundland & Labrador',
    'Prince Edward Island', 'Yukon', 'Northwest Territories', 'Nunavut',
]

_ABBR_MAP = {
    'Ontario': 'ON', 'Quebec': 'QC', 'Alberta': 'AB',
    'British Columbia': 'BC', 'Saskatchewan': 'SK', 'Manitoba': 'MB',
    'Nova Scotia': 'NS', 'New Brunswick': 'NB',
    'Newfoundland & Labrador': 'NL', 'Newfoundland and Labrador': 'NL',
    'Prince Edward Island': 'PE', 'Yukon': 'YT',
    'Northwest Territories': 'NT', 'Nunavut': 'NU',
}

# Province name variants for fuzzy matching in article text/titles
_PROVINCE_KEYWORDS = {
    'ON': ['ontario', 'toronto', 'ottawa', 'hamilton', 'kitchener', 'london ont', 'gta'],
    'QC': ['quebec', 'montreal', 'laval', 'gatineau', 'sherbrooke'],
    'AB': ['alberta', 'calgary', 'edmonton', 'oil sands', 'fort mcmurray'],
    'BC': ['british columbia', 'vancouver', 'victoria bc', 'surrey', 'burnaby', 'kelowna'],
    'SK': ['saskatchewan', 'regina', 'saskatoon', 'potash'],
    'MB': ['manitoba', 'winnipeg', 'brandon mb'],
    'NS': ['nova scotia', 'halifax', 'cape breton'],
    'NB': ['new brunswick', 'moncton', 'fredericton', 'saint john nb'],
    'NL': ['newfoundland', 'labrador', "st. john's nl", "st john's", 'hibernia'],
    'PE': ['prince edward island', 'pei', 'charlottetown'],
    'YT': ['yukon', 'whitehorse'],
    'NT': ['northwest territories', 'yellowknife', 'nwt'],
    'NU': ['nunavut', 'iqaluit'],
}

CITATION_RULES = (
    "CITATION RULES: Every factual claim must end with <sup>N</sup> matching a source in the sources array. "
    "N starts at 1 and increments. Use exact URLs from articles — never fabricate URLs. "
    "If an article has no URL, use the publication homepage."
)

EDITORIAL_RULES = (
    "EDITORIAL RULES: REPORT ONLY — no editorializing. State what happened, "
    "what the data shows, what is connected. Never say 'should', 'must', "
    "'hopefully', 'unfortunately', 'worrying', 'promising', 'encouraging'. "
    "Never recommend policy, investment, or business decisions. Use conditional "
    "language for projections. NEVER forecast or use 'looking ahead', 'expected "
    "to', 'is likely to', 'outlook', 'going forward'."
)

# ── Available timeseries keys for agent-driven charts ────────────────────────
# These are the keys available in timeseries.json. The agent picks which to chart.
_NATIONAL_TIMESERIES_KEYS = [
    'wti', 'brent', 'natural_gas', 'gold', 'copper', 'aluminum', 'nickel',
    'lumber', 'potash_nutrien', 'iron_ore', 'zinc', 'coal', 'uranium_spot',
    'wheat', 'corn', 'soybeans', 'canola', 'silver', 'platinum', 'palladium',
    'cad_usd', 'cadusd', 'boc_rate', 'goc_10y', 'yield_curve_10y2y',
    'tsx_composite', 'sp500', 'nasdaq', 'djia', 'cpi', 'unemployment',
    'housing_starts', 'nat_employment_rate', 'nat_participation_rate',
    'nat_unemployment', 'bitcoin', 'ethereum', 'lng_asia',
    'hy_spread', 'ig_spread', 'dry_bulk_shipping',
]

_PROVINCE_TIMESERIES_KEYS = {
    'ON': ['ON_cpi', 'ON_unemployment', 'ON_on_exports', 'ON_on_imports',
            'ON_on_gdp_goods', 'ON_on_real_capital_investment',
            'ON_on_real_consumption', 'ON_on_real_household'],
    'QC': ['QC_cpi', 'QC_unemployment', 'QC_qc_exports', 'QC_qc_imports',
            'QC_qc_bldg_permits_res', 'QC_qc_bldg_permits_nonres',
            'QC_qc_employment', 'QC_qc_housing_starts',
            'QC_qc_manufacturing_sales', 'QC_qc_real_gdp',
            'QC_qc_retail_sales', 'QC_qc_unemployment_rate',
            'QC_qc_intl_exports', 'QC_qc_intl_imports',
            'QC_qc_business_investment'],
    'AB': ['AB_cpi', 'AB_unemployment'],
    'BC': ['BC_cpi', 'BC_unemployment'],
    'SK': ['SK_cpi', 'SK_unemployment'],
    'MB': ['MB_cpi', 'MB_unemployment'],
    'NS': ['NS_cpi', 'NS_unemployment'],
    'NB': ['NB_cpi', 'NB_unemployment'],
    'NL': ['NL_cpi', 'NL_unemployment'],
    # PE, YT, NT, NU — no province-specific timeseries yet
}

# ── Province commodity & sector exposure (static, no API needed) ────────────

_PROVINCE_COMMODITY_EXPOSURE = {
    'AB': {
        'primary': ['WTI Crude', 'Western Canadian Select', 'Natural Gas (AECO)'],
        'sectors': ['oil_gas', 'mining', 'agriculture'],
        'trade': 'Energy exports (crude, natural gas, petrochemicals) dominate. US is primary market (~90% of oil exports).',
    },
    'SK': {
        'primary': ['Potash', 'Uranium (U3O8)', 'WTI Crude', 'Spring Wheat'],
        'sectors': ['mining', 'agriculture', 'oil_gas'],
        'trade': 'Potash ($7B+/yr), uranium, and canola drive exports. Global fertilizer demand sets price.',
    },
    'BC': {
        'primary': ['Lumber', 'Copper', 'LNG/Natural Gas', 'Metallurgical Coal'],
        'sectors': ['forestry', 'mining', 'transport_logistics'],
        'trade': 'Pacific gateway — Port of Vancouver handles 40%+ of Canada\'s trade. Asia-Pacific exposure through lumber, coal, LNG.',
    },
    'ON': {
        'primary': ['Gold', 'Nickel', 'Auto Parts/Vehicles'],
        'sectors': ['manufacturing', 'mining', 'commercial_mixed'],
        'trade': 'Most diversified province. Auto sector deeply integrated with US (USMCA). Financial services hub.',
    },
    'QC': {
        'primary': ['Aluminum', 'Iron Ore', 'Hydroelectric Power'],
        'sectors': ['power_energy', 'mining', 'manufacturing'],
        'trade': 'Hydro-Québec exports cheap electricity to New England. Aluminum smelting benefits from low energy costs.',
    },
    'NL': {
        'primary': ['Brent Crude (offshore)', 'Iron Ore', 'Nickel'],
        'sectors': ['oil_gas', 'mining', 'infrastructure'],
        'trade': 'Offshore oil (Hibernia, Hebron, Terra Nova) drives provincial revenue. Iron ore from Labrador.',
    },
    'MB': {
        'primary': ['Spring Wheat', 'Canola', 'Nickel (Thompson)'],
        'sectors': ['agriculture', 'mining', 'manufacturing'],
        'trade': 'Agriculture-dependent. Manitoba Hydro exports electricity. CentrePort inland port links to US midwest.',
    },
    'NS': {
        'primary': ['Seafood (Lobster)', 'Natural Gas (Sable)', 'Tidal Energy'],
        'sectors': ['agriculture', 'defence', 'tourism_culture'],
        'trade': 'Atlantic gateway. Halifax port handles container traffic. Defence/shipbuilding (Irving). Seafood exports to US/Asia.',
    },
    'NB': {
        'primary': ['Refined Petroleum (Irving)', 'Potash', 'Seafood'],
        'sectors': ['manufacturing', 'mining', 'power_energy'],
        'trade': 'Irving Oil refinery (largest in Canada) processes imported crude. Potash mining near Sussex. SMR nuclear projects.',
    },
    'PE': {
        'primary': ['Potatoes', 'Seafood (Lobster, Mussels)'],
        'sectors': ['agriculture', 'tourism_culture', 'residential'],
        'trade': 'Agriculture-dominated (potatoes ~25% of Canadian production). Tourism seasonal. Smallest provincial economy.',
    },
    'YT': {
        'primary': ['Gold', 'Silver', 'Zinc'],
        'sectors': ['mining', 'tourism_culture', 'government'],
        'trade': 'Mining drives private sector. Federal transfers significant. Tourism (Klondike) seasonal.',
    },
    'NT': {
        'primary': ['Diamonds', 'Gold', 'Zinc'],
        'sectors': ['mining', 'indigenous', 'government'],
        'trade': 'Diamond mines (Diavik, Ekati winding down). Remediation projects. Indigenous-led resource development.',
    },
    'NU': {
        'primary': ['Gold', 'Iron Ore (Baffinland)', 'Diamonds'],
        'sectors': ['mining', 'indigenous', 'infrastructure'],
        'trade': 'Baffinland Mary River iron ore mine is largest employer. Infrastructure deficit. Federal transfers dominant.',
    },
}

# NAICS sector names for readable labels in prompts
_NAICS_NAMES = {
    '11': 'Agriculture/Forestry', '21': 'Mining/Oil & Gas', '22': 'Utilities',
    '23': 'Construction', '31-33': 'Manufacturing', '41': 'Wholesale Trade',
    '44-45': 'Retail Trade', '48-49': 'Transport/Warehousing',
    '51': 'Information/Culture', '52': 'Finance/Insurance',
    '53': 'Real Estate', '54': 'Professional Services',
    '55': 'Management of Companies', '56': 'Admin/Waste Management',
    '61': 'Education', '62': 'Healthcare/Social Assistance',
    '71': 'Arts/Entertainment', '72': 'Accommodation/Food Services',
    '81': 'Other Services', '91': 'Public Administration',
}


# ── Context enrichment ───────────────────────────────────────────────────────

def _match_province(text: str, abbr: str) -> bool:
    """Check if text mentions this province (fuzzy match on keywords)."""
    text_lower = text.lower()
    for kw in _PROVINCE_KEYWORDS.get(abbr, []):
        if kw in text_lower:
            return True
    return False


def _filter_articles_for_province(articles: list[dict], abbr: str) -> list[dict]:
    """Return articles relevant to a specific province."""
    matched = []
    for a in articles:
        # Check metadata province hints first (most reliable)
        meta_provs = a.get('meta_provinces', [])
        if abbr in meta_provs:
            matched.append(a)
            continue
        # Check title + text for province keywords
        haystack = (a.get('title', '') + ' ' + a.get('text', '')[:800])
        if _match_province(haystack, abbr):
            matched.append(a)
    return matched


def _filter_rss_for_province(rss_items: list[dict], abbr: str, province_name: str) -> list[dict]:
    """Return RSS items relevant to a specific province."""
    matched = []
    for item in (rss_items or []):
        # Check feed_id or feed_name for province
        feed_id = (item.get('feed_id') or '').lower()
        feed_name = (item.get('feed_name') or '').lower()
        title = (item.get('title') or '')
        summary = (item.get('summary') or item.get('text', ''))

        # Government feeds often have province in feed_id
        if abbr.lower() in feed_id or province_name.lower() in feed_id:
            matched.append(item)
            continue
        if abbr.lower() in feed_name or province_name.lower() in feed_name:
            matched.append(item)
            continue
        # Check content
        haystack = title + ' ' + summary[:500]
        if _match_province(haystack, abbr):
            matched.append(item)
    return matched


def _filter_events_for_province(events: list[dict], abbr: str, province_name: str) -> list[dict]:
    """Return events/watchlist items relevant to a specific province."""
    matched = []
    for e in (events or []):
        ev_prov = (e.get('province') or '').upper()
        if ev_prov == abbr or ev_prov == abbr.lower():
            matched.append(e)
            continue
        # Check event name for province keywords
        name = e.get('name', '') + ' ' + e.get('relevance', '')
        if _match_province(name, abbr):
            matched.append(e)
    return matched


def _build_province_signals_text(abbr: str, signal_context: dict) -> str:
    """Build detailed signal text for a province (full text, not just counts)."""
    lines = []
    policy_items = signal_context.get('policy_items', [])
    job_spikes = signal_context.get('job_spikes', [])
    procurement = signal_context.get('procurement_contracts', [])
    iaac = signal_context.get('iaac_status_changes', [])

    # Policy items — include full title + categories
    prov_policy = [p for p in policy_items if (p.get('province') or '').upper() == abbr]
    if prov_policy:
        lines.append("POLICY & LEGISLATIVE DEVELOPMENTS:")
        for p in prov_policy:
            title = p.get('title', '')[:200]
            cats = ', '.join(p.get('policy_categories', []))
            url = p.get('url', '')
            line = f"  - {title}"
            if cats:
                line += f" [{cats}]"
            if url:
                line += f" ({url})"
            lines.append(line)

    # Job spikes — include employer, sector, count
    from phases.analysis import _cma_to_province  # reuse existing mapping
    prov_spikes = [s for s in job_spikes if _cma_to_province(s.get('location', '')) == abbr]
    if prov_spikes:
        lines.append("HIRING SPIKES:")
        for s in prov_spikes:
            lines.append(
                f"  - {s.get('employer', '?')} in {s.get('location', '?')}: "
                f"{s.get('current_count', 0)} postings ({s.get('sector', '')})"
            )

    # Procurement — include description and value
    prov_proc = [c for c in procurement if (c.get('province') or '').upper() == abbr]
    if prov_proc:
        lines.append("PROCUREMENT CONTRACTS:")
        for c in prov_proc:
            val = c.get('value', '')
            desc = c.get('description', '')[:200]
            lines.append(f"  - {desc} (value: {val or 'undisclosed'})")

    # IAAC status changes — include project name, old/new status
    prov_iaac = [i for i in iaac if (i.get('province') or '').upper() == abbr]
    if prov_iaac:
        lines.append("IAAC STATUS CHANGES:")
        for i in prov_iaac:
            lines.append(
                f"  - {i.get('project_name', '?')}: "
                f"{i.get('old_status', '?')} → {i.get('new_status', '?')}"
            )

    return '\n'.join(lines) if lines else ''


def _format_articles_compact(articles: list[dict], max_chars: int = 6000) -> str:
    """Format articles for a single-province prompt (more compact)."""
    if not articles:
        return "(no province-specific articles available)"
    lines = []
    total = 0
    for i, a in enumerate(articles, 1):
        url = a.get('url', '')
        title = a.get('title', '')
        text = a.get('text', '')[:1200]
        src_type = 'news_article'
        if any(d in url for d in ('.gc.ca', 'canada.ca', '.gov.')):
            src_type = 'government_press_release'
        chunk = (
            f"ARTICLE [{i}]:\n"
            f"Source: {src_type}\n"
            f"Headline: \"{title}\"\n"
            f"URL: {url}\n"
            f"Text: {text}\n"
        )
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return '\n'.join(lines)


def _format_events_text(events: list[dict]) -> str:
    """Format events/watchlist items for a province prompt."""
    if not events:
        return ''
    lines = ["RECENT EVENTS & ANNOUNCEMENTS FOR THIS PROVINCE:"]
    for e in events[:10]:
        name = e.get('name', '')
        date_str = e.get('date', '')
        source = e.get('source', '')
        url = e.get('url', '')
        relevance = e.get('relevance', '')
        sig = e.get('significance', '')
        ev_type = e.get('type', '')

        line = f"  - [{date_str}] {name}"
        if source:
            line += f" (source: {source})"
        if url:
            line += f"\n    URL: {url}"
        if relevance:
            line += f"\n    Detail: {relevance[:300]}"
        lines.append(line)
    return '\n'.join(lines)


def _format_rss_compact(rss_items: list[dict], max_items: int = 10) -> str:
    """Format RSS items for a single-province prompt."""
    if not rss_items:
        return ''
    lines = ["GOVERNMENT RSS NEWS RELEASES:"]
    for item in rss_items[:max_items]:
        title = item.get('title', '')
        url = item.get('url', item.get('link', ''))
        summary = (item.get('summary') or item.get('text', ''))[:300]
        lines.append(f"  - {title}\n    URL: {url}\n    {summary}")
    return '\n'.join(lines)


# ── Province context package ─────────────────────────────────────────────────

def build_province_context(province_name: str, articles: list[dict],
                           rss_items: list[dict], events: list[dict],
                           signal_context: dict, officials_ctx: str,
                           boc_rate: str, national_articles: list[dict] = None,
                           hard_data: dict = None, watchlist: dict = None) -> dict:
    """
    Build the complete enriched context package for a single province.

    Returns a dict with all context strings ready for prompt injection.
    """
    abbr = _ABBR_MAP.get(province_name, province_name[:2].upper())

    # Filter data sources to this province
    prov_articles = _filter_articles_for_province(articles, abbr)
    prov_rss = _filter_rss_for_province(rss_items, abbr, province_name)
    prov_events = _filter_events_for_province(events, abbr, province_name)
    prov_signals = _build_province_signals_text(abbr, signal_context)

    # If province has very few articles, include some national articles as fallback
    if len(prov_articles) < 3 and national_articles:
        national_subset = [a for a in national_articles[:10] if a not in prov_articles]
        prov_articles = prov_articles + national_subset[:5]

    # ── Commodity & trade exposure (static) ──────────────────────────
    commodity_data = _PROVINCE_COMMODITY_EXPOSURE.get(abbr, {})
    commodity_text = ''
    if commodity_data:
        primary = ', '.join(commodity_data.get('primary', []))
        trade = commodity_data.get('trade', '')
        commodity_text = f"Key commodities: {primary}\nTrade profile: {trade}"

    # ── National industry GDP context (from hard_data) ───────────────
    industry_gdp_text = ''
    if hard_data:
        pi = hard_data.get('primary_indicators', {})
        industries = pi.get('industries', {})
        if industries:
            # Build sector GDP summary — relevant sectors for this province
            relevant_sectors = commodity_data.get('sectors', [])
            lines = []
            for naics, data in sorted(industries.items()):
                if naics.startswith('_'):
                    continue
                name = _NAICS_NAMES.get(naics, naics)
                mm = data.get('mm', 'N/A')
                yy = data.get('yy', 'N/A')
                lines.append(f"  {name} ({naics}): M/M {mm}, Y/Y {yy}")
            if lines:
                industry_gdp_text = "NATIONAL INDUSTRY GDP (StatCan, all provinces share this macro context):\n" + '\n'.join(lines)

    # ── Provincial indicators (from hard_data) ───────────────────────
    prov_indicators_text = ''
    if hard_data:
        pi = hard_data.get('primary_indicators', {})
        prov_ind = pi.get('provinces', {}).get(province_name, {})
        if prov_ind:
            ind_lines = []
            for field in ('unemployment', 'cpi', 'gdp', 'employmentRate', 'participationRate', 'housingStarts'):
                val = prov_ind.get(field, '')
                if val:
                    src = prov_ind.get(f'{field}_src', 'StatCan')
                    prev = prov_ind.get(f'{field}_prev', '')
                    date_str = prov_ind.get(f'{field}_date', '')
                    prev_str = f" (prev: {prev})" if prev else ''
                    ind_lines.append(f"  {field}: {val}{prev_str} [{src}, {date_str}]")
            if ind_lines:
                prov_indicators_text = f"VERIFIED {province_name.upper()} INDICATORS (primary-source data):\n" + '\n'.join(ind_lines)

    # ── Commodity prices (from hard_data) ────────────────────────────
    commodity_prices_text = ''
    if hard_data and commodity_data.get('primary'):
        commodities = hard_data.get('commodities', {}).get('summary', {})
        if commodities:
            price_lines = []
            for comm_name in commodity_data.get('primary', []):
                # Fuzzy match commodity names
                for key, val in commodities.items():
                    if any(w.lower() in key.lower() for w in comm_name.split()[:2]):
                        price_lines.append(f"  {key}: {val}")
                        break
            if price_lines:
                commodity_prices_text = "COMMODITY PRICES AFFECTING THIS PROVINCE:\n" + '\n'.join(price_lines)

    # ── Watchlist items filtered to province ──────────────────────────
    watchlist_text = ''
    if watchlist:
        events_list = watchlist.get('events', [])
        prov_wl = [e for e in events_list
                    if province_name.lower() in (e.get('description', '') + e.get('event_name', '')).lower()
                    or abbr.lower() in (e.get('tags', '') if isinstance(e.get('tags'), str) else '').lower()]
        if prov_wl:
            wl_lines = [f"  - [{e.get('date', '')}] {e.get('event_name', e.get('name', ''))} ({e.get('institution', '')})"
                        for e in prov_wl[:10]]
            watchlist_text = f"UPCOMING EVENTS AFFECTING {province_name.upper()}:\n" + '\n'.join(wl_lines)

    # ── Financial markets context ────────────────────────────────────
    markets_text = ''
    if hard_data:
        fm = hard_data.get('financial_markets', {})
        fx_items = fm.get('fx', [])
        cad_usd = next((f for f in fx_items if 'CAD' in f.get('name', '') or 'USD/CAD' in f.get('name', '')), None)
        yield_items = fm.get('yield_curve', [])
        y5 = next((y for y in yield_items if '5' in str(y.get('term', ''))), None)
        lines = []
        if cad_usd:
            lines.append(f"  CAD/USD: {cad_usd.get('value', '')} (day: {cad_usd.get('day', '')}, YoY: {cad_usd.get('yy', '')})")
        if y5:
            lines.append(f"  GoC 5Y bond: {y5.get('yield', y5.get('value', ''))}%")
        boc_line = f"  BoC policy rate: {boc_rate}"
        lines.append(boc_line)
        if lines:
            markets_text = "FINANCIAL MARKET CONTEXT:\n" + '\n'.join(lines)

    return {
        'province_name': province_name,
        'abbr': abbr,
        'articles_text': _format_articles_compact(prov_articles),
        'rss_text': _format_rss_compact(prov_rss),
        'events_text': _format_events_text(prov_events),
        'signals_text': prov_signals,
        'officials_ctx': officials_ctx,
        'boc_rate': boc_rate,
        'commodity_text': commodity_text,
        'commodity_prices_text': commodity_prices_text,
        'industry_gdp_text': industry_gdp_text,
        'prov_indicators_text': prov_indicators_text,
        'watchlist_text': watchlist_text,
        'markets_text': markets_text,
        'article_count': len(prov_articles),
        'event_count': len(prov_events),
        'rss_count': len(prov_rss),
    }


# ── Per-province prompt builder ──────────────────────────────────────────────

def _build_province_prompt(ctx: dict, today_str: str) -> str:
    """Build the enriched Claude prompt for a single province's analysis.

    Each province agent now produces 7 output sections (up from 2):
      1. analysis — core weekly analysis (existing, improved)
      2. sectorHighlights — top 2-3 sector developments with NAICS GDP data
      3. labourDeepDive — employment/wage/participation narrative
      4. consumerPulse — cost-of-living/housing/energy themes from news
      5. tradeExposure — commodity prices + export/trade context
      6. marketContext — how yields, CAD, BoC rate affect this province
      7. watchlistItems — filtered upcoming events with impact notes
    """
    province = ctx['province_name']

    events_block = ctx['events_text']
    if events_block:
        events_block = f"\nPROVINCE EVENTS AND ANNOUNCEMENTS:\n{events_block}\n"

    signals_block = ctx['signals_text']
    if signals_block:
        signals_block = f"\nPROVINCE-SPECIFIC SIGNALS:\n{signals_block}\n"

    officials_block = ctx['officials_ctx']
    if officials_block:
        officials_block = f"\n{officials_block}\n"

    # New enrichment blocks
    commodity_block = ctx.get('commodity_text', '')
    if commodity_block:
        commodity_block = f"\nPROVINCE COMMODITY & TRADE PROFILE:\n{commodity_block}\n"

    commodity_prices_block = ctx.get('commodity_prices_text', '')
    if commodity_prices_block:
        commodity_prices_block = f"\n{commodity_prices_block}\n"

    industry_gdp_block = ctx.get('industry_gdp_text', '')
    if industry_gdp_block:
        industry_gdp_block = f"\n{industry_gdp_block}\n"

    prov_indicators_block = ctx.get('prov_indicators_text', '')
    if prov_indicators_block:
        prov_indicators_block = f"\n{prov_indicators_block}\n"

    watchlist_block = ctx.get('watchlist_text', '')
    if watchlist_block:
        watchlist_block = f"\n{watchlist_block}\n"

    markets_block = ctx.get('markets_text', '')
    if markets_block:
        markets_block = f"\n{markets_block}\n"

    # ── Available timeseries keys for chart selection ──────────────────
    abbr = ctx['abbr']
    prov_ts = _PROVINCE_TIMESERIES_KEYS.get(abbr, [])
    all_ts = prov_ts + _NATIONAL_TIMESERIES_KEYS
    ts_block = "AVAILABLE TIMESERIES KEYS (for insightChart — these are plottable 12-month series):\n"
    ts_block += f"  Province-specific: {', '.join(prov_ts) if prov_ts else 'None — use national keys'}\n"
    ts_block += f"  National/commodity: wti, brent, natural_gas, gold, copper, aluminum, nickel, lumber, potash_nutrien, iron_ore, zinc, coal, wheat, corn, soybeans, silver, cad_usd, boc_rate, goc_10y, yield_curve_10y2y, tsx_composite, cpi, unemployment, housing_starts, nat_employment_rate, nat_participation_rate, lng_asia, hy_spread, ig_spread\n"

    return f"""Today: {today_str}
Bank of Canada Policy Rate: {ctx['boc_rate']}

You are writing a comprehensive weekly provincial briefing for **{province}** ({ctx['abbr']}).

PROVINCE-SPECIFIC NEWS ARTICLES (cite by article number — use URLs exactly as given):
{ctx['articles_text']}

{ctx['rss_text']}
{events_block}{signals_block}{officials_block}{prov_indicators_block}{industry_gdp_block}{commodity_block}{commodity_prices_block}{markets_block}{watchlist_block}
{ts_block}
{CITATION_RULES}
{EDITORIAL_RULES}

INSTRUCTIONS — Write a comprehensive provincial briefing for {province} with ALL 8 sections below (7 narrative + 1 chart specification).

a) indicators: Set ALL fields to "" — overwritten from StatCan primary data APIs.
b) indicatorMeta: Set ALL nested fields to "" — overwritten from primary data.

c) analysis: 4-6 short prose paragraphs (300-450 words total, 2-3 sentences each). Format as HTML: <p>paragraph</p>.
   Write like a wire service dispatch — factual, specific, no editorializing.
   Structure:
   - Opening paragraph: State the latest GDP/employment data with figures inline.
   - Sector paragraphs: Report what happened in 2-3 key sectors with specific figures.
   - Policy/fiscal paragraph: Report government spending decisions, capital plans, fiscal position, budget releases. THIS IS CRITICAL — if a provincial budget was released this week, it MUST lead or feature prominently.
   - Project paragraph: Report specific capital projects announced, approved, or advancing.

d) sectorHighlights: 2-3 HTML paragraphs (150-250 words total). Identify the 2-3 most active/changed sectors for {province} this week.
   Use the NATIONAL INDUSTRY GDP data above to contextualize — e.g. "National mining GDP grew +2.1% M/M; {province}'s mining sector saw [specific development]."
   Name specific companies, projects, dollar figures. Every claim cited.

e) labourDeepDive: 2-3 HTML paragraphs (120-200 words). Go beyond the headline unemployment rate.
   Report on: participation rate movements, employment rate, sector-specific hiring/layoffs from news,
   wage trends if mentioned in articles, youth/immigration labour dynamics if available.
   Use the province indicator data above for figures.

f) consumerPulse: 1-2 HTML paragraphs (80-150 words). Extract consumer-facing themes from this week's
   news articles for {province}: housing affordability, energy costs, grocery/food prices, retail trends,
   cost-of-living pressures. Derive ENTIRELY from the articles above — no Reddit, no social media.

g) tradeExposure: 1-2 HTML paragraphs (80-150 words). Connect this province's commodity exposure to
   current commodity prices. Use the COMMODITY PRICES and TRADE PROFILE data above.
   E.g. for Alberta: "WTI at $XX/bbl this week — the database tracks 14 oil sands projects..."
   For PEI: "Potato exports to the US represent..."
   If no relevant commodity data, describe the province's trade dynamics factually.

h) marketContext: 1-2 HTML paragraphs (60-120 words). How do current BoC rate, yield curve, and CAD/USD
   affect {province}'s economy? Focus on capital costs for projects, housing affordability,
   export competitiveness. Use the FINANCIAL MARKET CONTEXT data above.

i) watchlistItems: Array of upcoming events relevant to {province} (3-8 items).
   Each: {{ "date": "YYYY-MM-DD", "event": "Description", "impact": "1 sentence: why this matters for {province}" }}.
   Draw from the events data and watchlist above. Include BoC decisions, StatCan releases, provincial budget dates, regulatory hearings.

j) insightChart: THE MOST IMPORTANT VISUALIZATION FOR THIS PROVINCE THIS WEEK.
   Analyze all the data, articles, indicators, and commodity prices above. Identify the single most impactful
   economic story for {province} this week. Then specify a chart that tells that story visually.
   - "title": A narrative headline for the chart (e.g., "WTI Slides Below $70 — 14 Alberta Oil Projects in Scope")
   - "subtitle": Data source label (e.g., "WTI Crude Oil (USD/bbl) — 12-month trend")
   - "chartType": One of: "line" (time series), "dual_line" (two series, dual y-axis), "bar" (comparison), "diverging_bar" (pos/neg changes)
   - "dataKeys": Array of 1-2 timeseries keys from the AVAILABLE TIMESERIES KEYS above.
     Pick keys that directly relate to the week's biggest story. Prefer province-specific keys when available.
     For dual_line, provide exactly 2 keys. For line, provide 1. For bar/diverging_bar, provide 1-2.
   - "reasoning": 1 sentence explaining why this chart is the week's most important visualization for {province}.
   - "annotations": Optional array of {{ "label": "Event name", "date": "YYYY-MM-DD" }} for key events to mark on the chart.
   RULES: Pick the chart that tells the most compelling data story. If oil prices crashed, chart WTI.
   If unemployment spiked, chart the unemployment series. If housing starts surged, chart that.
   Connect the chart to specific projects or policy developments mentioned in your analysis.

k) sources: Array matching ALL citation numbers across ALL sections. id, title, url (REQUIRED).

l) projects: 2-4 major capital projects. Each: name, description, sector, value, status, completionDate, cma, tags, sources.

EVERY section must be factual. If insufficient data exists for a section, write 1 short sentence noting limited data this week.
NEVER forecast. NEVER editorialize. Every claim backed by <sup>N</sup>.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "name": "{province}",
    "indicators": {{"gdp": "", "unemployment": "", "cpi": "", "housingStarts": "", "participationRate": "", "employmentRate": "", "buildingPermits": ""}},
    "indicatorMeta": {{"gdp": {{"change": "", "prev": "", "period": ""}}, "unemployment": {{"change": "", "prev": "", "period": ""}}, "cpi": {{"change": "", "prev": "", "period": ""}}, "housingStarts": {{"change": "", "prev": "", "period": ""}}, "participationRate": {{"change": "", "prev": "", "period": ""}}, "employmentRate": {{"change": "", "prev": "", "period": ""}}, "buildingPermits": {{"change": "", "prev": "", "period": ""}}}},
    "analysis": "<p>Opening with latest data.<sup>1</sup></p><p>Key sector developments.<sup>2</sup></p><p>Policy/fiscal paragraph.<sup>3</sup></p><p>Project updates.<sup>4</sup></p>",
    "sectorHighlights": "<p>Top sector with national GDP context and province-specific development.<sup>N</sup></p><p>Second sector.<sup>N</sup></p>",
    "labourDeepDive": "<p>Participation rate at XX.X%, employment rate XX.X%. Sector-specific hiring data.<sup>N</sup></p><p>Wage/demographic trends.<sup>N</sup></p>",
    "consumerPulse": "<p>Dominant consumer theme from news — housing, energy, food costs.<sup>N</sup></p>",
    "tradeExposure": "<p>Commodity price impact on province. Export dynamics.<sup>N</sup></p>",
    "marketContext": "<p>BoC rate and yield curve implications for provincial capital costs and housing.<sup>N</sup></p>",
    "watchlistItems": [{{"date": "2026-04-05", "event": "Event name", "impact": "Why it matters for {province}"}}],
    "insightChart": {{
        "title": "Narrative headline connecting data to {province}'s key story this week",
        "subtitle": "Indicator Name (unit) — 12-month trend",
        "chartType": "line",
        "dataKeys": ["AB_unemployment"],
        "reasoning": "Why this is the most important chart for {province} this week.",
        "annotations": [{{"label": "BoC cut", "date": "2026-03-15"}}]
    }},
    "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://..."}}],
    "projects": [
        {{
            "name": "Project Name",
            "description": "1-2 sentences describing the project, its proponent, and scope.",
            "sector": "Energy",
            "value": "$X.XB",
            "status": "Under Construction",
            "completionDate": "2027",
            "cma": "City",
            "tags": ["tag1"],
            "sources": [{{"id": 1, "title": "", "url": ""}}]
        }}
    ]
}}"""


# ── Claude Code subprocess runner ────────────────────────────────────────────

def _call_claude_code(prompt: str, label: str) -> dict | None:
    """
    Call Claude via the Claude Code CLI (uses subscription, $0 API cost).

    Writes the prompt to a temp file and invokes:
      claude -p <prompt> --model <model> --output-format json --max-turns 1

    Returns parsed JSON dict or None on failure.
    """
    # Write prompt to temp file (avoids shell escaping issues with long prompts)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                     encoding='utf-8') as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        if not _CLAUDE_CLI:
            raise FileNotFoundError("claude CLI not resolved")
        cmd = [
            _CLAUDE_CLI, '-p',
            f'Read the file {prompt_file} and follow the instructions exactly. Output ONLY valid JSON.',
            '--model', CLAUDE_CODE_MODEL,
            '--output-format', 'json',
            '--max-turns', str(CLAUDE_CODE_MAX_TURNS),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            encoding='utf-8',
            env=_CLAUDE_ENV,
            errors='replace',
        )

        if result.returncode != 0:
            print(f"    [{label}] Claude Code returned exit code {result.returncode}")
            if result.stderr:
                print(f"    [{label}] stderr: {result.stderr[:300]}")
            return None

        output = result.stdout.strip()
        if not output:
            print(f"    [{label}] Empty output from Claude Code")
            return None

        # Claude Code --output-format json wraps the response
        # Try to parse the outer JSON first
        try:
            outer = json.loads(output)
            # Claude Code JSON format has a 'result' field with the text
            text = outer.get('result', outer.get('text', output))
            if isinstance(text, str):
                # The text itself should be JSON from Claude
                return _extract_json(text, label)
            elif isinstance(text, dict):
                return text
        except (json.JSONDecodeError, TypeError):
            pass

        # Try direct parse
        return _extract_json(output, label)

    except subprocess.TimeoutExpired:
        print(f"    [{label}] Claude Code timed out after 120s")
        return None
    except FileNotFoundError:
        print(f"    [{label}] 'claude' CLI not found — is Claude Code installed?")
        return None
    except Exception as e:
        print(f"    [{label}] Error: {type(e).__name__}: {e}")
        return None
    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


def _extract_json(text: str, label: str) -> dict | None:
    """Extract JSON from Claude's response text, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith('```'):
        lines = text.split('\n')
        # Remove first and last lines if they're fences
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        print(f"    [{label}] Failed to parse JSON from response ({len(text)} chars)")
        return None


# ── Agent orchestrator ───────────────────────────────────────────────────────

def run_province_agents(articles: list[dict], rss_items: list[dict],
                        events: list[dict], signal_context: dict,
                        watchlist: dict, hard_data: dict,
                        anthropic_client=None, cost_state=None,
                        conn=None, gemini_client=None,
                        model: str = '') -> list[dict]:
    """
    Run 13 parallel province writing agents and return a provinces array.

    Each agent:
      1. Gets a dedicated context package (filtered articles, events, signals)
      2. Writes analysis for one province via Claude Code (subscription) or API
      3. Returns structured JSON for that province

    Mode controlled by PROVINCE_AGENT_MODE env var:
      - 'claude_code' (default): uses Claude Code CLI (subscription, $0)
      - 'api': uses Anthropic SDK (_call_claude from analysis.py)

    Falls back to empty analysis on per-province failure (non-fatal).
    """
    from phases.analysis import _build_provincial_officials_context

    mode = AGENT_MODE
    today_str = date.today().strftime('%B %d, %Y')
    boc_rate = hard_data.get('boc_rate', '2.25%')

    # Economy articles for fallback
    economy_arts = [a for a in articles if a.get('topic') == 'economy']

    # Build context packages for all provinces
    print(f"  [Province Agents] Building context packages for {len(PROVINCES)} provinces...")
    contexts = {}
    for prov_name in PROVINCES:
        officials_ctx = _build_provincial_officials_context(prov_name, watchlist)
        ctx = build_province_context(
            province_name=prov_name,
            articles=economy_arts,
            rss_items=rss_items,
            events=events,
            signal_context=signal_context,
            officials_ctx=officials_ctx,
            boc_rate=boc_rate,
            national_articles=economy_arts[:10],
            hard_data=hard_data,
            watchlist=watchlist,
        )
        contexts[prov_name] = ctx
        print(f"    {prov_name}: {ctx['article_count']} articles, "
              f"{ctx['event_count']} events, {ctx['rss_count']} RSS items")

    # Build prompts
    prompts = {}
    for prov_name, ctx in contexts.items():
        prompts[prov_name] = _build_province_prompt(ctx, today_str)

    # Select execution mode
    if mode == 'claude_code':
        print(f"  [Province Agents] Mode: Claude Code (subscription, $0 API cost)")
        print(f"  [Province Agents] Launching {len(PROVINCES)} agents "
              f"({PROVINCE_AGENT_WORKERS} parallel workers)...")
        _run_fn = lambda prompt, label: _call_claude_code(prompt, label)
        workers = PROVINCE_AGENT_WORKERS
    else:
        from phases.analysis import _call_claude, SONNET_MODEL
        if not model:
            model = SONNET_MODEL
        print(f"  [Province Agents] Mode: API ({model})")
        print(f"  [Province Agents] Launching {len(PROVINCES)} parallel API calls...")
        _run_fn = lambda prompt, label: _call_claude(
            prompt, label, max_tokens=3000, model=model,
            anthropic_client=anthropic_client, cost_state=cost_state,
            conn=conn, gemini_client=gemini_client,
        )
        workers = 13

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for prov_name, prompt in prompts.items():
            abbr = _ABBR_MAP.get(prov_name, '??')
            f = executor.submit(_run_fn, prompt, f"prov-{abbr}")
            futures[f] = prov_name

        for future in as_completed(futures):
            prov_name = futures[future]
            try:
                result = future.result()
                if result and isinstance(result, dict):
                    results[prov_name] = result
                    print(f"    [OK] {prov_name}: "
                          f"{len(result.get('analysis', ''))} chars, "
                          f"{len(result.get('projects', []))} projects")
                else:
                    print(f"    [WARN] {prov_name}: empty or invalid response")
                    results[prov_name] = _empty_province(prov_name)
            except Exception as e:
                print(f"    [ERROR] {prov_name}: {type(e).__name__}: {e}")
                results[prov_name] = _empty_province(prov_name)

    # Assemble in canonical order
    provinces = []
    for prov_name in PROVINCES:
        prov_data = results.get(prov_name, _empty_province(prov_name))
        # Ensure name is set correctly
        prov_data['name'] = prov_name
        provinces.append(prov_data)

    ok_count = sum(1 for p in provinces if len(p.get('analysis', '')) > 100)
    print(f"  [Province Agents] Complete: {ok_count}/{len(PROVINCES)} provinces with analysis")

    return provinces


def _empty_province(name: str) -> dict:
    """Return an empty province skeleton for fallback."""
    return {
        'name': name,
        'indicators': {
            'gdp': '', 'unemployment': '', 'cpi': '', 'housingStarts': '',
            'participationRate': '', 'employmentRate': '', 'buildingPermits': '',
        },
        'indicatorMeta': {
            'gdp': {'change': '', 'prev': '', 'period': ''},
            'unemployment': {'change': '', 'prev': '', 'period': ''},
            'cpi': {'change': '', 'prev': '', 'period': ''},
            'housingStarts': {'change': '', 'prev': '', 'period': ''},
            'participationRate': {'change': '', 'prev': '', 'period': ''},
            'employmentRate': {'change': '', 'prev': '', 'period': ''},
            'buildingPermits': {'change': '', 'prev': '', 'period': ''},
        },
        'analysis': f'<p>No province-specific articles or signals were available for {name} this week.</p>',
        'sectorHighlights': '',
        'labourDeepDive': '',
        'consumerPulse': '',
        'tradeExposure': '',
        'marketContext': '',
        'watchlistItems': [],
        'insightChart': None,
        'sources': [],
        'projects': [],
    }
