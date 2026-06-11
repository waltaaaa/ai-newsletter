"""Phase 5: Analysis — Claude calls 1-4, hard data override, indicator validation."""
import traceback
import json
import os
import re
import time
import threading
import anthropic
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pipeline_config import SONNET_MODEL, OPUS_MODEL, CLAUDE_COST_CAP_USD
from citation_audit import CITATION_RULES, run_citation_audit, save_audit_log, remove_failed_claims
from db import save_checkpoint, get_checkpoint
from nim_client import get_client as get_nim_client
import service_health
import rss_monitor


# ── Exception ────────────────────────────────────────────────────────────────

class CostCapExceeded(Exception):
    """Raised when Claude API cost exceeds the per-run cap."""
    pass


# ── Constants ────────────────────────────────────────────────────────────────

_CLAUDE_SYSTEM = (
    "You are a Senior Canadian Macroeconomist and financial journalist. "
    "Write precise, data-driven analysis with specific figures, dates, and named entities. "
    "Never write generic commentary. Every sentence must reference a real event, figure, or data point. "
    "NEVER invent URLs — only cite URLs that appear in the provided source material. "
    "Output ONLY valid JSON matching the schema exactly. No markdown fences. No explanation before or after the JSON."
)

# Known source URL patterns: match title keywords -> canonical URL
_SOURCE_URL_MAP = [
    ('statistics canada', 'daily', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'gdp', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401'),
    ('statistics canada', 'labour', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'),
    ('statistics canada', 'cpi', 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401'),
    ('statistics canada', 'trade', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'payroll', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'retail', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'housing', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'investment', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'balance', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'manufacturing', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'wholesale', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'permit', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statistics canada', 'population', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('statcan', '', 'https://www150.statcan.gc.ca/n1/daily-quotidien/en'),
    ('bank of canada', 'rate', 'https://www.bankofcanada.ca/rates/interest-rates/'),
    ('bank of canada', 'policy', 'https://www.bankofcanada.ca/rates/interest-rates/'),
    ('bank of canada', 'business outlook', 'https://www.bankofcanada.ca/publications/bos/'),
    ('bank of canada', 'financial', 'https://www.bankofcanada.ca/publications/'),
    ('bank of canada', 'monetary', 'https://www.bankofcanada.ca/publications/mpr/'),
    ('bank of canada', '', 'https://www.bankofcanada.ca/'),
    ('cmhc', 'housing start', 'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research'),
    ('cmhc', '', 'https://www.cmhc-schl.gc.ca/'),
    ('bureau of labor', '', 'https://www.bls.gov/'),
    ('bls', 'employment', 'https://www.bls.gov/news.release/empsit.nr0.htm'),
    ('bls', 'cpi', 'https://www.bls.gov/cpi/'),
    ('federal reserve', '', 'https://www.federalreserve.gov/'),
    ('bureau of economic analysis', '', 'https://www.bea.gov/'),
    ('bea', 'gdp', 'https://www.bea.gov/data/gdp'),
    ('eurostat', '', 'https://ec.europa.eu/eurostat'),
    ('ecb', '', 'https://www.ecb.europa.eu/'),
    ('ons', '', 'https://www.ons.gov.uk/'),
    ('bank of england', '', 'https://www.bankofengland.co.uk/'),
    ('national bureau of statistics', 'china', 'http://www.stats.gov.cn/english/'),
    ('globe and mail', '', 'https://www.theglobeandmail.com/'),
    ('financial post', '', 'https://financialpost.com/'),
    ('reuters', '', 'https://www.reuters.com/'),
    ('bloomberg', '', 'https://www.bloomberg.com/'),
    ('cbc', '', 'https://www.cbc.ca/news'),
    ('iea', '', 'https://www.iea.org/'),
    ('imf', '', 'https://www.imf.org/'),
    ('world bank', '', 'https://www.worldbank.org/'),
    ('oecd', '', 'https://www.oecd.org/'),
    ('infrastructure canada', '', 'https://www.infrastructure.gc.ca/'),
    ('natural resources canada', '', 'https://natural-resources.canada.ca/'),
    ('nrcan', '', 'https://natural-resources.canada.ca/'),
    ('transport canada', '', 'https://tc.canada.ca/en'),
    ('ised', '', 'https://ised-isde.canada.ca/site/ised/en'),
    ('innovation, science and economic development', '', 'https://ised-isde.canada.ca/site/ised/en'),
    ('employment and social development', '', 'https://www.canada.ca/en/employment-social-development.html'),
    ('esdc', '', 'https://www.canada.ca/en/employment-social-development.html'),
    ('immigration, refugees and citizenship', '', 'https://www.canada.ca/en/immigration-refugees-citizenship.html'),
    ('department of finance', '', 'https://www.canada.ca/en/department-finance.html'),
    ('treasury board', '', 'https://www.canada.ca/en/treasury-board-secretariat.html'),
    ('yahoo finance', '', 'https://finance.yahoo.com/'),
]


# ── Helper: format periods and compute changes ──────────────────────────────

def _fmt_period(dt_str: str) -> str:
    """Convert 'YYYY-MM-DD' or 'YYYY-MM' to 'Mon YYYY' for display."""
    if not dt_str:
        return ''
    try:
        from datetime import datetime
        return datetime.strptime(dt_str[:7], '%Y-%m').strftime('%b %Y')
    except Exception:
        return dt_str[:7]


def _calc_change(cur: str | None, prev: str | None) -> str:
    """Compute signed numeric difference between two formatted indicator strings."""
    if not cur or not prev:
        return ''
    try:
        c = float(str(cur).replace('%', '').replace(',', '').replace('+', '').strip())
        p = float(str(prev).replace('%', '').replace(',', '').replace('+', '').strip())
        d = c - p
        unit = 'pp' if '%' in str(cur) else ''
        return f"{d:+.1f}{unit}"
    except Exception:
        return ''


# ── News context helper ──────────────────────────────────────────────────────

def fetch_news_context(rss_items: list | None = None) -> str:
    """
    Format RSS items for use as news context in Claude prompts.
    Prefers federal economic/infrastructure items for macro context.
    Falls back to fetching live if rss_items is None (legacy path).
    """
    if rss_items is None:
        # Legacy path: fetch a small set of feeds directly
        print("Gathering latest economic news feeds...")
        rss_items = rss_monitor.fetch_all_feeds(days_back=7)
    # Federal economic + StatCan/BoC items first, then project-relevant items
    fed_eco  = [i for i in rss_items if i['source_level'] == 'federal'
                and i['category'] in ('economic',)]
    proj_rel = rss_monitor.filter_project_relevant(rss_items)
    # Deduplicate (proj_rel may overlap with fed_eco)
    seen_urls: set[str] = set()
    combined: list[dict] = []
    for item in (fed_eco + proj_rel):
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            combined.append(item)
    return rss_monitor.format_for_context(combined, max_items=40)


# ── Tavily article extraction ────────────────────────────────────────────────

def extract_article_texts(article_urls: list[str], batch_size: int = 5,
                          tavily_client=None) -> list[dict]:
    """
    Use Tavily Extract API to pull full text from article URLs.
    Processes in batches of batch_size URLs per API credit.
    Returns list of {url, title, text} dicts.

    Args:
        article_urls: List of URLs from GDELT or RSS.
        batch_size:   URLs per Tavily Extract call (5 = 1 credit).
        tavily_client: Tavily client instance.
    """
    if not tavily_client:
        print("  [Tavily] No client available — skipping article extraction.")
        return []

    print(f"  [Tavily] Extracting text from {len(article_urls)} URLs "
          f"in batches of {batch_size}...")

    extracted: list[dict] = []
    for i in range(0, len(article_urls), batch_size):
        batch = article_urls[i:i + batch_size]
        try:
            result = tavily_client.extract(urls=batch)
            for r in result.get('results', []):
                url  = r.get('url') or ''
                text = r.get('raw_content') or r.get('content') or ''
                if url and text:
                    extracted.append({
                        'url':   url,
                        'title': r.get('title') or '',
                        'text':  text[:6000],  # cap per article
                    })
        except Exception as e:
            print(f"  [Tavily] Batch {i//batch_size + 1} failed: {e}")
        time.sleep(0.5)

    print(f"  [Tavily] Extracted text from {len(extracted)}/{len(article_urls)} URLs")
    return extracted


# ── Source URL enrichment ────────────────────────────────────────────────────

def _enrich_source_urls(payload: dict):
    """Post-process Claude output: fill in empty source URLs from known title patterns."""
    def _match_url(title: str) -> str:
        t = title.lower()
        for keywords in _SOURCE_URL_MAP:
            *parts, url = keywords
            if all(p in t for p in parts if p):
                return url
        return ''

    def _fix_sources(sources: list):
        fixed = 0
        for s in sources:
            if isinstance(s, dict) and not s.get('url') and s.get('title'):
                matched = _match_url(s['title'])
                if matched:
                    s['url'] = matched
                    fixed += 1
        return fixed

    total_fixed = 0
    # Fix top-level sources
    for key in ('sources', 'industrySources'):
        if isinstance(payload.get(key), list):
            total_fixed += _fix_sources(payload[key])
    # Fix nested sources (national, global, provinces)
    for key in ('national', 'global', 'provinces', 'goodsIndustries', 'servicesIndustries'):
        val = payload.get(key)
        if isinstance(val, dict):
            if isinstance(val.get('sources'), list):
                total_fixed += _fix_sources(val['sources'])
            # Province sub-dicts
            for sub in val.values():
                if isinstance(sub, dict) and isinstance(sub.get('sources'), list):
                    total_fixed += _fix_sources(sub['sources'])
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and isinstance(item.get('sources'), list):
                    total_fixed += _fix_sources(item['sources'])
                    # Also check nested projects
                    for proj in item.get('projects', []):
                        if isinstance(proj, dict) and isinstance(proj.get('sources'), list):
                            total_fixed += _fix_sources(proj['sources'])
    if total_fixed:
        print(f"  [Source URLs] Enriched {total_fixed} empty source URLs from known patterns")


# ── JSON truncation / repair ─────────────────────────────────────────────────

def _is_truncated(text: str) -> bool:
    """Check if JSON response was truncated (doesn't end with valid closure)."""
    stripped = text.rstrip()
    if not stripped:
        return True
    return stripped[-1] not in ('}', ']')


def _repair_json(broken_json: str, label: str,
                 anthropic_client=None, gemini_client=None) -> dict:
    """Try local LLM first, then Groq, then Haiku."""
    if not broken_json:
        return {}

    # Try NIM Nemotron first
    try:
        nim = get_nim_client()
        resp = nim.chat_sync(
            messages=[
                {"role": "system", "content": "The following JSON is truncated or malformed. Complete/fix it and return ONLY valid JSON. No explanation, no markdown fences."},
                {"role": "user", "content": broken_json[-3000:]},
            ],
            max_tokens=4096, temperature=0, thinking=False,
        )
        import json as _json
        result = _json.loads(resp)
        if result is not None:
            print(f"    [NIM REPAIR OK] {label}")
            return result
    except Exception as e:
        print(f"    [NIM REPAIR FAILED] {label}: {e}")

    # Try Groq LLaMA 3.3 70B (free, replaces Gemini)
    try:
        import groq_client
        result = groq_client.repair_json(broken_json, label)
        if result is not None:
            print(f"    [GROQ REPAIR OK] {label}")
            return result
    except ImportError:
        pass
    except Exception as e:
        print(f"    [GROQ REPAIR FAILED] {label}: {e}")

    # Try Claude Code as third fallback (free, subscription)
    from claude_reasoning import REASONING_AGENT_MODE, _call_claude_code_sync
    if REASONING_AGENT_MODE == 'claude_code':
        repair_prompt = (
            "The following JSON is malformed or truncated. Return ONLY the corrected valid JSON. "
            "No markdown. No explanation.\n\n" + broken_json
        )
        raw = _call_claude_code_sync(repair_prompt, f"repair-{label}", model='haiku')
        if raw:
            raw = raw.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                result = json.loads(raw)
                print(f"    [CLAUDE CODE REPAIR OK] {label}")
                return result
            except json.JSONDecodeError:
                print(f"    [CLAUDE CODE REPAIR FAILED] {label}: still invalid JSON")

    print(f"    [REPAIR FAILED] {label}: all repair methods exhausted")
    return {}


# ── Claude API call with cost tracking ───────────────────────────────────────

def _call_claude(prompt: str, label: str, max_tokens: int = 8096, model: str = '',
                 run_id: str = '',
                 anthropic_client=None, cost_state=None, conn=None,
                 gemini_client=None) -> dict:
    """Call Claude with specified model and parse JSON.

    Default: Claude Code subprocess ($0). Fallback: Anthropic API.

    Features:
    - Checkpointing: if run_id is set, checks for cached response before calling
    - Truncation detection: if response hit max_tokens, retries with +4096 (API only)
    - JSON repair: tries Groq, then Gemini fallback

    Args:
        cost_state: mutable dict with keys 'usd', 'input', 'output', 'cap',
                    'input_cost_per_mtok', 'output_cost_per_mtok'.
    """
    if cost_state is None:
        cost_state = {
            'usd': 0.0, 'input': 0, 'output': 0,
            'cap': CLAUDE_COST_CAP_USD,
            'input_cost_per_mtok': 3.0, 'output_cost_per_mtok': 15.0,
        }

    # ── Checkpoint check — return cached response if available ────────────
    if run_id and conn:
        cached = get_checkpoint(conn, run_id, label)
        if cached:
            try:
                result = json.loads(cached["response"])
                print(f"    [CHECKPOINT HIT] {label} — using cached response (saved ${cached['cost_usd']:.4f})")
                return result
            except (json.JSONDecodeError, TypeError):
                pass  # corrupted checkpoint, re-run

    # ── Claude Code mode (default, $0) ───────────────────────────────────
    from claude_reasoning import REASONING_AGENT_MODE, _call_claude_code_sync
    if REASONING_AGENT_MODE == 'claude_code':
        use_model = model or SONNET_MODEL
        cc_model = os.environ.get('REASONING_AGENT_MODEL', 'sonnet')
        if 'opus' in use_model.lower():
            cc_model = 'opus'

        # Prepend system prompt to user prompt for Claude Code
        full_prompt = f"{_CLAUDE_SYSTEM}\n\n{prompt}"
        raw = _call_claude_code_sync(full_prompt, label, model=cc_model)
        if raw:
            # Parse JSON from response
            raw_content = raw.strip()
            if raw_content.startswith("```"):
                parts = raw_content.split("```")
                raw_content = parts[1] if len(parts) > 1 else raw_content
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            try:
                parsed = json.loads(raw_content)
                print(f"    [Claude Code] {label}: OK ($0 — subscription)")
                # Save checkpoint
                if run_id and conn:
                    try:
                        save_checkpoint(conn, run_id, label, json.dumps(parsed, ensure_ascii=False), 0.0)
                    except Exception:
                        pass
                return parsed
            except json.JSONDecodeError:
                print(f"    [Claude Code] {label}: JSON parse failed — trying repair...")
                repaired = _repair_json(raw_content, label,
                                        anthropic_client=anthropic_client,
                                        gemini_client=gemini_client)
                if repaired:
                    if run_id and conn:
                        try:
                            save_checkpoint(conn, run_id, label, json.dumps(repaired, ensure_ascii=False), 0.0)
                        except Exception:
                            pass
                    return repaired
        # If Claude Code failed, fall through to API only if explicitly enabled
        from claude_reasoning import ALLOW_API_FALLBACK
        if not ALLOW_API_FALLBACK:
            print(f"    [Claude Code] {label}: failed; API fallback disabled "
                  "(set CLAUDE_ALLOW_API_FALLBACK=1 to enable)")
            return {}
        if not anthropic_client:
            print(f"    [Claude Code] {label}: failed, no API fallback available")
            return {}
        print(f"    [Claude Code] {label}: failed, falling back to API...")

    # ── API mode (fallback) ──────────────────────────────────────────────
    cap = cost_state.get('cap', CLAUDE_COST_CAP_USD)
    if cost_state['usd'] >= cap:
        print(f"    [COST CAP] ${cost_state['usd']:.4f} >= ${cap:.2f} cap — skipping {label}")
        return {}

    use_model = model or SONNET_MODEL
    raw_content = ""
    current_max_tokens = max_tokens
    from pipeline_config import MODEL_RATES
    rates = MODEL_RATES.get(use_model, {})
    input_cost = rates.get('input', cost_state.get('input_cost_per_mtok', 3.0))
    output_cost = rates.get('output', cost_state.get('output_cost_per_mtok', 15.0))

    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=use_model,
                max_tokens=current_max_tokens,
                system=_CLAUDE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            in_tok = getattr(msg.usage, 'input_tokens', 0)
            out_tok = getattr(msg.usage, 'output_tokens', 0)
            call_cost = (in_tok * input_cost + out_tok * output_cost) / 1_000_000
            lock = cost_state.get('_lock')
            if lock:
                with lock:
                    cost_state['input'] += in_tok
                    cost_state['output'] += out_tok
                    cost_state['usd'] += call_cost
                    total = cost_state['usd']
            else:
                cost_state['input'] += in_tok
                cost_state['output'] += out_tok
                cost_state['usd'] += call_cost
                total = cost_state['usd']
            print(f"    [COST] {label}: {in_tok:,} in + {out_tok:,} out = ${call_cost:.4f} (run total: ${total:.4f}/${cap:.2f})")

            if not msg.content:
                print(f"    [TRUNCATED] {label}: empty API response — retrying")
                time.sleep(2)
                continue
            raw_content = msg.content[0].text.strip()

            if out_tok >= current_max_tokens - 10 and _is_truncated(raw_content):
                current_max_tokens += 4096
                print(f"    [TRUNCATED] {label}: hit {out_tok} tokens — retrying with max_tokens={current_max_tokens}")
                time.sleep(1)
                continue

            if raw_content.startswith("```"):
                parts = raw_content.split("```")
                raw_content = parts[1] if len(parts) > 1 else raw_content
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            parsed = json.loads(raw_content)

            if run_id and conn:
                try:
                    save_checkpoint(conn, run_id, label, json.dumps(parsed, ensure_ascii=False), call_cost)
                except Exception as e:
                    print(f"    [CHECKPOINT SAVE WARN] {label}: {e}")

            return parsed
        except json.JSONDecodeError:
            if attempt == 3:
                print(f"    [CLAUDE JSON ERROR] {label} — trying repair...")
                repaired = _repair_json(raw_content, label,
                                        anthropic_client=anthropic_client,
                                        gemini_client=gemini_client)
                if repaired and run_id and conn:
                    try:
                        save_checkpoint(conn, run_id, label, json.dumps(repaired, ensure_ascii=False), call_cost)
                    except Exception:
                        pass
                return repaired
            time.sleep(1)
        except CostCapExceeded:
            raise
        except Exception as e:
            if attempt == 3:
                print(f"    [CLAUDE ERROR] {label}: {e}")
                return {}
            time.sleep(2 ** attempt)
    return {}


# ── Watchlist context builders ───────────────────────────────────────────────

def _build_canadian_officials_context(watchlist: dict) -> str:
    """Build VERIFIED CANADIAN OFFICIALS block from watchlist.json public_figures_canada."""
    figures = watchlist.get('public_figures_canada', [])
    if not figures:
        return ''
    lines = ['VERIFIED CANADIAN OFFICIALS (use these names and titles exactly):']
    for f in figures:
        name = f.get('name') or f.get('current_holder') or ''
        role = f.get('role') or ''
        entity = f.get('entity_name') or ''
        if name and role:
            lines.append(f'- {name}, {role}')
        elif name and entity:
            lines.append(f'- {name}, {entity}')
    lines.append('')
    lines.append('If an article mentions an official not on this list, use the name and title from the article. Never guess or invent titles.')
    return '\n'.join(lines)


def _build_global_officials_context(watchlist: dict) -> str:
    """Build VERIFIED GLOBAL OFFICIALS block from watchlist.json global_watchlist."""
    entries = watchlist.get('global_watchlist', [])
    if not entries:
        return ''
    # Group by jurisdiction
    by_jur: dict[str, list] = {}
    for e in entries:
        jur = e.get('jurisdiction') or 'Other'
        by_jur.setdefault(jur, []).append(e)
    lines = ['VERIFIED GLOBAL OFFICIALS (use these names and titles exactly):']
    for jur, officials in by_jur.items():
        parts = []
        for o in officials:
            name = o.get('current_holder') or o.get('entity_name') or ''
            role = o.get('role') or ''
            if name and role:
                parts.append(f'{name} ({role})')
        if parts:
            lines.append(f'{jur}: {", ".join(parts)}')
    lines.append('')
    lines.append('If an article mentions an official not on this list, use the name and title from the article.')
    return '\n'.join(lines)


def _build_provincial_officials_context(province: str, watchlist: dict) -> str:
    """Build VERIFIED [PROVINCE] OFFICIALS block from watchlist.json provincial_officials."""
    officials = watchlist.get('provincial_officials', [])
    if not officials:
        return ''
    # Map province names to abbreviations and vice versa
    _abbr_to_name = {
        'BC': 'British Columbia', 'AB': 'Alberta', 'SK': 'Saskatchewan',
        'MB': 'Manitoba', 'ON': 'Ontario', 'QC': 'Quebec',
        'NB': 'New Brunswick', 'NS': 'Nova Scotia', 'PE': 'Prince Edward Island',
        'NL': 'Newfoundland and Labrador', 'YT': 'Yukon',
        'NT': 'Northwest Territories', 'NU': 'Nunavut',
    }
    _name_to_abbr = {v: k for k, v in _abbr_to_name.items()}
    # Filter to this province
    prov_abbr = _name_to_abbr.get(province, province)
    filtered = [o for o in officials if o.get('jurisdiction') in (province, prov_abbr)]
    if not filtered:
        return ''
    lines = [f'VERIFIED {province.upper()} OFFICIALS (use these titles exactly):']
    for o in filtered:
        name = o.get('current_holder') or ''
        role = o.get('role') or ''
        entity = o.get('entity_name') or ''
        if name and role:
            lines.append(f'- {role}: {name}')
        elif name and entity:
            lines.append(f'- {entity}: {name}')
    lines.append('')
    lines.append('If an article names an official not on this list, use the name and title from the article.')
    return '\n'.join(lines)


# ── Hard data summary for prompts ────────────────────────────────────────────

def _hard_data_summary(hard_data: dict, rss_items: list[dict] | None = None) -> str:
    """Format hard data into a concise string for Claude prompts."""
    commodity_lines = "\n".join(
        f"  {name}: {val}"
        for name, val in hard_data['commodities']['summary'].items()
    )
    indices_lines = "\n".join(
        f"  {i['name']}: {i['value']} (day {i['day']}, YoY {i['yy']})"
        for i in hard_data.get('financial_markets', {}).get('indices', [])
    )
    fx_lines = "\n".join(
        f"  {f['name']}: {f['value']} (day {f['day']}, YoY {f['yy']})"
        for f in hard_data.get('financial_markets', {}).get('fx', [])
    )

    # Primary source indicators block — Claude writes ABOUT these but must not change them
    pi = hard_data.get('primary_indicators', {})
    primary_section = ""
    if pi:
        nat_vals = pi.get('national', {}).get('values', {})
        primary_section = (
            "\n\nPRIMARY SOURCE INDICATORS (authoritative — reference these exact values in analysis):\n"
            f"  Real GDP (QoQ ann.): {nat_vals.get('realGdp', 'N/A')} (StatCan)\n"
            f"  CPI (YoY):           {nat_vals.get('cpi', 'N/A')} (StatCan)\n"
            f"  Unemployment:        {nat_vals.get('unemployment', 'N/A')} (StatCan)\n"
            f"  Housing Starts:      {nat_vals.get('housingStarts', 'N/A')} (CMHC/StatCan)\n"
        )
        ind_data = pi.get('industries', {})
        ind_lines = [
            f"    NAICS {code}: M/M={d.get('mm','N/A')}, Y/Y={d.get('yy','N/A')}"
            for code, d in ind_data.items()
            if not code.startswith('_')
        ]
        if ind_lines:
            primary_section += (
                "  Industry GDP — StatCan Table 36-10-0434-01 "
                "(use these M/M and Y/Y values in analysis):\n" +
                "\n".join(ind_lines) + "\n"
            )

    # Build government news context from RSS items (if available)
    rss_items = rss_items or hard_data.get('rss_items', [])
    news_ctx  = fetch_news_context(rss_items) if rss_items else hard_data.get('news_context', '')

    return (
        f"Bank of Canada Policy Rate: {hard_data['boc_rate']}\n\n"
        f"Commodity Prices (Yahoo Finance — authoritative):\n{commodity_lines}\n\n"
        f"Equity Indices (Yahoo Finance — authoritative):\n{indices_lines}\n\n"
        f"FX Rates (Yahoo Finance — authoritative):\n{fx_lines}\n\n"
        f"Government & Economic News (RSS — federal + project-relevant):\n{news_ctx}"
        f"{primary_section}"
    )


# ── Article formatting ───────────────────────────────────────────────────────

def _format_articles_for_prompt(articles: list[dict], max_chars: int = 20000) -> str:
    """Format extracted articles in structured format for Claude prompts.

    Each article formatted as:
      ARTICLE [N]:
      Source type: news_article | government_press_release | canada_gazette
      Headline: "Exact headline"
      URL: https://verified-url
      Text: [full article text]
    """
    if not articles:
        return "(no articles available)"
    lines = []
    total = 0
    for i, a in enumerate(articles, 1):
        url   = a.get('url', '')
        title = a.get('title', '')
        text  = a.get('text', '')[:1500]
        # Determine source type
        src_type = 'news_article'
        if a.get('feed_id') or a.get('feed_name'):
            src_type = 'government_press_release'
        elif 'gazette' in url.lower():
            src_type = 'canada_gazette'
        elif any(d in url for d in ('.gc.ca', 'canada.ca', '.gov.')):
            src_type = 'government_press_release'
        # Include metadata hints if available
        hints = ""
        meta_sectors = a.get('meta_sectors', [])
        meta_provinces = a.get('meta_provinces', [])
        if meta_sectors or meta_provinces:
            hint_parts = []
            if meta_sectors:
                hint_parts.append(f"sector_hints={meta_sectors}")
            if meta_provinces:
                hint_parts.append(f"province_hints={meta_provinces}")
            hints = f"Metadata hints: {', '.join(hint_parts)}\n"

        chunk = (
            f"ARTICLE [{i}]:\n"
            f"Source type: {src_type}\n"
            f"Headline: \"{title}\"\n"
            f"URL: {url}\n"
            f"{hints}"
            f"Text: {text}\n"
        )
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return '\n'.join(lines)


# ── CMA → Province mapping (for job spike province attribution) ──────────────

_CMA_TO_PROVINCE = {
    'Toronto': 'ON', 'Ottawa': 'ON', 'Hamilton': 'ON', 'Kitchener': 'ON',
    'London': 'ON', 'Windsor': 'ON',
    'Montreal': 'QC', 'Quebec City': 'QC',
    'Vancouver': 'BC', 'Victoria': 'BC',
    'Calgary': 'AB', 'Edmonton': 'AB',
    'Winnipeg': 'MB', 'Regina': 'SK', 'Saskatoon': 'SK',
    'Halifax': 'NS', 'St. John\'s': 'NL', 'Saint John': 'NB',
    'Charlottetown': 'PE', 'Fredericton': 'NB', 'Moncton': 'NB',
}


def _cma_to_province(location: str) -> str:
    """Map CMA/city name to 2-letter province code."""
    if not location:
        return ''
    for cma, prov in _CMA_TO_PROVINCE.items():
        if cma.lower() in location.lower():
            return prov
    return ''


# ── Signal context builders (Prompts 11-19 data) ────────────────────────────

def _build_signal_context_blocks(sig: dict) -> dict:
    """Build formatted text blocks from new signal data for Claude prompts.

    Returns dict with keys: call1, sector_signals, province_signals
    """
    blocks = {}

    # ── Call 1: National-level signal summary ────────────────────
    parts = []

    # Policy developments
    policy_summary = sig.get('policy_summary', {})
    policy_items = sig.get('policy_items', [])
    if policy_summary or policy_items:
        p_lines = []
        for item in policy_items[:8]:
            title = item.get('title', '')[:150]
            cats = ', '.join(item.get('policy_categories', [])[:3])
            affected = item.get('affected_projects_total', 0)
            p_lines.append(f"  - [{cats}] {title} ({affected} projects in scope)")
        if p_lines:
            parts.append(
                "POLICY DEVELOPMENTS (legislative/regulatory changes affecting capital investment):\n"
                + '\n'.join(p_lines) + '\n'
                "Report what happened factually. Do not predict outcomes."
            )

    # Hiring spikes
    spikes = sig.get('job_spikes', [])[:10]
    if spikes:
        s_lines = []
        for s in spikes:
            # multiplier is None on a first tracked week (no baseline) —
            # never format None and never assert a fabricated "Nx normal".
            mult = s.get('multiplier')
            mult_str = (f"{mult:.1f}x normal" if mult
                        else "first tracked week — no prior baseline")
            s_lines.append(
                f"  - {s.get('employer', '?')} in {s.get('location', '?')} "
                f"({s.get('sector', '?')}): {s.get('current_count', 0)} postings, "
                f"{mult_str}"
            )
        parts.append(
            "HIRING SIGNALS (employer job posting spikes — possible project mobilization):\n"
            + '\n'.join(s_lines)
        )

    # Procurement highlights (≥$10M)
    contracts = sig.get('procurement_contracts', [])
    # (value can be None on tender-notice rows — `or 0` so the comparison
    # can't TypeError; `.get('value', 0)` returns None when the key exists)
    big_contracts = [c for c in contracts if (c.get('value') or 0) >= 10_000_000][:10]
    if big_contracts:
        c_lines = []
        for c in big_contracts:
            val = c.get('value') or 0
            val_str = f"${val / 1_000_000:.0f}M" if val else 'undisclosed'
            desc = c.get('description', c.get('title', ''))[:150]
            prov = c.get('province', '')
            linked = len(c.get('linked_projects', []))
            link_note = f", linked to {linked} tracked project(s)" if linked else ''
            c_lines.append(f"  - [{prov}] {desc} — {val_str}{link_note}")
        parts.append(
            "GOVERNMENT PROCUREMENT (contract awards/tenders ≥$10M in construction/infrastructure):\n"
            + '\n'.join(c_lines)
        )

    # IAAC status changes
    iaac = sig.get('iaac_status_changes', [])
    if iaac:
        i_lines = []
        for ch in iaac[:8]:
            i_lines.append(
                f"  - {ch.get('project_name', '?')}: "
                f"{ch.get('old_status', '?')} → {ch.get('new_status', '?')} "
                f"({ch.get('province', '')})"
            )
        parts.append(
            "ASSESSMENT STATUS CHANGES (federal IAAC transitions):\n"
            + '\n'.join(i_lines)
        )

    # Extended indicators summary
    ext_tables = sig.get('statcan_extended_tables_ok', 0)
    ext_saved = sig.get('statcan_extended_saved', 0)
    if ext_tables:
        parts.append(
            f"EXTENDED STATCAN DATA: {ext_tables} additional tables fetched, "
            f"{ext_saved} new indicator values saved this cycle."
        )

    blocks['call1'] = '\n\n'.join(parts) if parts else ''

    # ── Call 2: Per-sector signals ────────────────────────────────
    sector_signals = {}
    for item in policy_items:
        for sector in item.get('affected_sectors', []):
            sector_signals.setdefault(sector, {'policy': [], 'hiring': [], 'procurement': []})
            sector_signals[sector]['policy'].append({
                'title': item.get('title', '')[:120],
                'source_type': item.get('source_type', ''),
                'affected_projects_total': item.get('affected_projects_total', 0),
            })
    for spike in spikes:
        sector = spike.get('sector')
        if sector:
            sector_signals.setdefault(sector, {'policy': [], 'hiring': [], 'procurement': []})
            sector_signals[sector]['hiring'].append({
                'employer': spike.get('employer', ''),
                'location': spike.get('location', ''),
                'count': spike.get('current_count', 0),
                'multiplier': spike.get('multiplier') or 0,
            })
    for contract in contracts:
        for proj in contract.get('linked_projects', []):
            sector = proj.get('sector')
            if sector:
                sector_signals.setdefault(sector, {'policy': [], 'hiring': [], 'procurement': []})
                sector_signals[sector]['procurement'].append({
                    'description': contract.get('description', '')[:150],
                    'value': contract.get('value'),
                })

    if sector_signals:
        ss_lines = []
        for sector, data in sorted(sector_signals.items()):
            items_desc = []
            if data['policy']:
                items_desc.append(f"{len(data['policy'])} policy items")
            if data['hiring']:
                items_desc.append(f"{len(data['hiring'])} hiring spikes")
            if data['procurement']:
                items_desc.append(f"{len(data['procurement'])} procurement awards")
            ss_lines.append(f"  {sector}: {', '.join(items_desc)}")
        blocks['sector_signals'] = (
            "SECTOR SIGNALS (from policy tracker, job monitor, procurement monitor):\n"
            + '\n'.join(ss_lines) + '\n'
            "Incorporate these signals where relevant. State facts, not opinions."
        )
    else:
        blocks['sector_signals'] = ''

    # ── Call 3: Per-province signals ──────────────────────────────
    province_signals = {}
    for item in policy_items:
        prov = item.get('province')
        if prov:
            province_signals.setdefault(prov, {'policy': [], 'hiring': [], 'procurement': [], 'iaac_changes': []})
            province_signals[prov]['policy'].append({
                'title': item.get('title', '')[:120],
                'categories': item.get('policy_categories', []),
            })
    for spike in spikes:
        prov = _cma_to_province(spike.get('location', ''))
        if prov:
            province_signals.setdefault(prov, {'policy': [], 'hiring': [], 'procurement': [], 'iaac_changes': []})
            province_signals[prov]['hiring'].append({
                'employer': spike.get('employer', ''),
                'location': spike.get('location', ''),
                'sector': spike.get('sector', ''),
                'count': spike.get('current_count', 0),
            })
    for contract in contracts:
        prov = contract.get('province')
        if prov:
            province_signals.setdefault(prov, {'policy': [], 'hiring': [], 'procurement': [], 'iaac_changes': []})
            province_signals[prov]['procurement'].append({
                'description': contract.get('description', '')[:150],
                'value': contract.get('value'),
            })
    for change in iaac:
        prov = change.get('province')
        if prov:
            province_signals.setdefault(prov, {'policy': [], 'hiring': [], 'procurement': [], 'iaac_changes': []})
            province_signals[prov]['iaac_changes'].append({
                'project': change.get('project_name', ''),
                'old_status': change.get('old_status', ''),
                'new_status': change.get('new_status', ''),
            })

    if province_signals:
        ps_lines = []
        for prov, data in sorted(province_signals.items()):
            items_desc = []
            if data['policy']:
                items_desc.append(f"{len(data['policy'])} policy")
            if data['hiring']:
                items_desc.append(f"{len(data['hiring'])} hiring")
            if data['procurement']:
                items_desc.append(f"{len(data['procurement'])} procurement")
            if data['iaac_changes']:
                items_desc.append(f"{len(data['iaac_changes'])} IAAC changes")
            ps_lines.append(f"  {prov}: {', '.join(items_desc)}")
        blocks['province_signals'] = (
            "PROVINCE SIGNALS (from policy tracker, job monitor, procurement monitor, IAAC):\n"
            + '\n'.join(ps_lines) + '\n'
            "Reference province-specific signals in each province's analysis where relevant."
        )
    else:
        blocks['province_signals'] = ''

    return blocks


# ── Main analysis function ───────────────────────────────────────────────────

def generate_claude_analysis(hard_data: dict, articles: list[dict],
                             rss_items: list[dict] | None = None,
                             anthropic_client=None, gemini_client=None,
                             cost_state=None, conn=None,
                             watchlist=None,
                             signal_context=None,
                             events: list[dict] | None = None,
                             dossier: dict | None = None) -> dict:
    """
    Four-call Claude pipeline with model routing:
      Call 1: Macro — Claude Sonnet (executive_summary, national, global, globalVectors, watchlist)
      Call 2: Industries + Markets — Claude Sonnet (goodsIndustries, servicesIndustries, yieldCurve)
      Call 3: Provincial — Claude Sonnet (all 13 provinces with analysis, indicators, projects)
      Call 4: Project extraction — Claude Sonnet (structured project records)

    Post-writing citation audit runs after each call.
    """
    if watchlist is None:
        watchlist = {}
    if signal_context is None:
        signal_context = {}
    if cost_state is None:
        cost_state = {
            'usd': 0.0, 'input': 0, 'output': 0,
            'cap': CLAUDE_COST_CAP_USD,
            'input_cost_per_mtok': 3.0, 'output_cost_per_mtok': 15.0,
        }

    arts_count = len(articles) or (len(rss_items) if rss_items else 0)
    print(f"\n[STEP 3] Claude analysis (4 calls, {arts_count} articles)...")
    print(f"  Writing agents (macro+industry): Claude Code, Province agents: Claude Code, Call 4 (extraction): Sonnet={SONNET_MODEL}")
    today_str    = date.today().strftime('%B %d, %Y')
    hard_summary = _hard_data_summary(hard_data, rss_items)

    # Build watchlist context blocks
    cdn_officials_ctx = _build_canadian_officials_context(watchlist)
    global_officials_ctx = _build_global_officials_context(watchlist)

    # Consumer sentiment context — DISABLED (2026-03-30)
    # Consumer pulse and word cloud topics are now derived entirely from
    # the news-article corpus already passed to Call 1.  Reddit/Google
    # Trends/CBC comment collection (sentiment.py) has been retired from
    # the active pipeline.  Set SENTIMENT_ENABLED=true in .env to re-enable.
    sentiment_ctx = ''
    _sentiment_future = None
    try:
        from sentiment import SENTIMENT_ENABLED
        if SENTIMENT_ENABLED:
            from sentiment import collect_sentiment
            from concurrent.futures import ThreadPoolExecutor as _SentPool
            _sent_pool = _SentPool(max_workers=1)
            _sentiment_future = _sent_pool.submit(collect_sentiment)
            print("  [Sentiment] Started collection in background...")
        else:
            print("  [Sentiment] Disabled — consumer pulse derived from news articles")
    except ImportError:
        pass
    except Exception as e:
        print(f"  [Sentiment] Setup failed (non-critical): {type(e).__name__}")

    # ── Build signal context blocks from Prompts 11-19 data ────────
    _signal_blocks = _build_signal_context_blocks(signal_context)

    # Split articles by topic for focused prompts — fall back to RSS items
    economy_arts  = [a for a in articles if a.get('topic') == 'economy']
    if not economy_arts and rss_items:
        economy_arts = [
            {
                'title': r.get('title', ''),
                'text': r.get('summary', '') or r.get('snippet', ''),
                'url': r.get('url', ''),
                'topic': 'economy',
                'feed_id': r.get('source_name', ''),
                'meta_sectors': r.get('tags', []),
                'meta_provinces': [r['province']] if r.get('province') else [],
            }
            for r in rss_items
            if r.get('title')
        ]
    project_arts  = [a for a in articles if a.get('topic') == 'project']
    all_arts_text = _format_articles_for_prompt(economy_arts[:50])

    # Collect citation audit results
    audit_results = []

    # ── CALLS 1-4: Run in parallel (all independent) ─────────────
    # cost_state is shared across threads — add lock to protect mutations
    cost_state['_lock'] = threading.Lock()

    # Resolve sentiment future (wait max 60s, then proceed without)
    if _sentiment_future:
        try:
            from concurrent.futures import TimeoutError as _FutTimeout
            sentiment_data = _sentiment_future.result(timeout=60)
            if sentiment_data:
                topics = sentiment_data.get('topics', [])
                s_idx  = sentiment_data.get('sentiment_index', 'N/A')
                top_5  = topics[:5] if topics else []
                topic_lines = '\n'.join(
                    f"  - {t.get('topic', '?')}: {t.get('sentiment', '?')} "
                    f"(mentions: {t.get('mention_count', 0)}, sources: {t.get('source', '?')})"
                    for t in top_5
                )
                sentiment_ctx = (
                    f"\n\nCONSUMER SENTIMENT PULSE (from Reddit, Google Trends, CBC comments):\n"
                    f"  Sentiment Index: {s_idx} (0=very negative, 100=very positive)\n"
                    f"  Top concerns/topics ({len(topics)} total):\n{topic_lines}\n"
                    f"  Use this data to add a 1-2 sentence consumer pulse note in the executive summary.\n"
                )
                hard_data['_sentiment_result'] = sentiment_data
                print(f"  [Sentiment] Collected {len(topics)} topics, index={s_idx}")
        except _FutTimeout:
            print("  [Sentiment] Timed out after 60s — proceeding without")
        except Exception as e:
            print(f"  [Sentiment] Collection failed (non-critical): {type(e).__name__}")

    print(f"  [1-4] Running all calls (Writing Agents + Province Agents + API extraction)...")

    # NOTE: _call1_prompt and _call2_prompt below are VESTIGIAL — they are no longer
    # submitted to _call_claude(). Writing is handled by phases/writing_agents.py
    # (run_all_writing_agents). Kept as documentation of the expected output schema.
    # TODO: Remove once writing_agents.py is stable.

    _call1_prompt = f"""Today: {today_str}

VERIFIED DATA (use exactly, never modify round or reinterpret):
{hard_summary}

{cdn_officials_ctx}

{global_officials_ctx}

RECENT NEWS AND PRESS RELEASES (cite by article number):
{all_arts_text}
{sentiment_ctx}

{_signal_blocks.get('call1', '')}

{CITATION_RULES}

Write:

1. EXECUTIVE SUMMARY (4-6 short paragraphs, 350-450 words)
Format as HTML paragraphs: <p>paragraph text</p>
This is a TL;DR — be concise and direct. Every sentence must carry a specific data point or fact. Cut filler, qualifiers, and scene-setting. No throat-clearing ("This week saw...", "The data revealed...") — lead with the fact.
Each paragraph is 2-3 sentences max. Use brief transitions between paragraphs.
Every paragraph opens with a lead-in sentence wrapped in <span class="lead-sentence">...</span> followed by " — " (space, em-dash, space) and the supporting detail.
NEVER use <strong> or <b> tags — the lead-in is the only bold text (styled by frontend CSS). Numbers stay specific but unbolded.
Structure: Lead paragraph states the week's single biggest national story with its key number. Second paragraph covers the next 2-3 most important national data points. Third paragraph covers notable provincial developments — cite specific provinces, project names, and dollar figures where available (e.g. "Ontario approved a $2.1B transit expansion", "Alberta's oil sands investment reached $X"). Fourth paragraph covers federal or provincial policy actions and project developments. Optional fifth paragraph for a genuinely significant cross-cutting theme connecting national and provincial trends.
Draw from BOTH national indicators AND provincial data/projects when reporting. Provincial stories that carry significant dollar values or affect multiple sectors deserve mention alongside national macro data.
NO forecasting, NO predictions, NO forward-looking language. Every claim backed by <sup>N</sup> citation.

2. NATIONAL ANALYSIS (4-5 short paragraphs, 250-400 words total)
Format as HTML paragraphs: <p>paragraph text</p>
Each paragraph is 2-3 sentences maximum. Write tight — cut qualifiers, scene-setting, and filler. Every sentence must deliver a specific figure or fact.
Structure: Open with the dominant data release and its key figure. Following paragraphs: supporting data with figures inline, policy actions taken, and any notable counterpoints. Do not repeat facts already covered in the executive summary — add depth or different data points.
NEVER forecast. NEVER use "is likely to", "would be expected to", "going forward", "looking ahead", "outlook", "expected to". Only report what HAS happened. Every claim backed by <sup>N</sup> citation. No bullet points.

3. GLOBAL ANALYSIS (4-6 short paragraphs per region, 250-350 words each):
Format each as HTML paragraphs: <p>paragraph text</p>
Each paragraph is 2-3 sentences maximum. Write like a wire service report — state what happened, what data showed, and what the cross-border connection is.
US: Report GDP/employment data, rate/inflation figures, and trade data relevant to Canada.
China: Report growth data, commodity demand figures relevant to Canadian exporters, policy actions taken.
EU: Report fiscal/monetary decisions, defense spending figures, and trade data relevant to Canada.
UK: Report trade figures, rate decisions, and financial data.
Per region: report what happened with embedded data. State factual connections to Canada (e.g. "X% of Canadian exports go to..."). NEVER forecast, predict, or use "looking ahead", "expected to", "is likely to". Every claim backed by <sup>N</sup> citation. No bullet points.

4. INDICATOR CONTEXT LINES: 1 sentence each, under 20 words, plain English for: bocRate, cpi, unemployment, housingStarts, realGdp.

5. WATCHLIST: 15-25 upcoming events with dates, impact rating (high/medium/low), description, source URLs where available.

6. CONSUMER PULSE (2-3 short paragraphs, 120-200 words):
Format as HTML paragraphs: <p>paragraph text</p>
Derive ENTIRELY from the news articles provided above — identify the dominant consumer-facing themes reported in the press this week (cost of living, housing, employment, energy prices, trade/tariff impacts, grocery prices, interest rates, wages, etc.). Lead with the single most-covered consumer story. Each paragraph is 2-3 sentences max covering one theme. Ground in data: cite specific figures, policy actions, or survey results mentioned in the articles. Note divergences between reported consumer conditions only if striking. Use <sup>N</sup> footnote citations referencing the article numbers above. Do NOT reference Reddit, Google Trends, or social media.

7. metrics: Fill ALL fields from articles EXCEPT — leave as "": cpi, shelterCpi, unemployment, participation, realGdp. These are injected from StatCan/BoC primary APIs. bocRate must match "{hard_data['boc_rate']}".

8. WORD CLOUD TOPICS: Extract 40-60 meaningful economic topics/phrases ONLY from the news articles and verified data provided above. These power a word cloud visualization. Each topic should be 1-3 words, e.g. "tariff threat", "rate cut", "housing affordability", "LNG exports", "auto layoffs", "tech hiring freeze", "lumber prices", "fiscal deficit", "immigration policy". Assign each a sentiment_score (-1.0 to +1.0, negative=bad for Canada, positive=good) and frequency (1-10 importance weight, 10=dominant story of the week based on article coverage volume). Prioritize specificity over generality. BAD: "economy", "growth", "markets". GOOD: "tariff retaliation", "BoC rate hold", "Alberta oil sands", "EV battery plant". Frequency should reflect how many articles covered this topic, not social media mentions.

Style: Wire service / Reuters dispatch quality. ALL sections use short prose paragraphs (<p>) — NO bullet points anywhere. Each paragraph 2-3 sentences. Every paragraph opens with a lead-in sentence wrapped in <span class="lead-sentence">...</span> followed by " — " (space, em-dash, space) and the supporting detail. NEVER use <strong> or <b> tags — the lead-in is the only bold text (styled by frontend CSS); numbers stay specific but unbolded. Use transitional phrases between paragraphs for narrative flow. Embed specific figures inline ("grew at an annualized rate of 1.3%", "three straight quarters of businesses cutting back"). REPORT ONLY — no editorializing, no forecasting, no opinions. State what happened, what data showed, what changed. DO NOT use: "is likely to", "would be expected to", "looking ahead", "going forward", "outlook", "expected to", "cautiously optimistic", "remains to be seen", "continues to grow", "markets remain volatile", "positive outlook", "encouraging", "concerning", "worrying", "promising". DO NOT discuss stock market movements, equity index levels, or stock performance (e.g. TSX, S&P 500, Dow, NASDAQ gains/losses). Rate changes, yield changes, FX, and bond markets ARE fair game.

OUTPUT: Valid JSON only. No markdown. No text outside the JSON.

SCHEMA:
{{
    "headline": "8-12 word newspaper-style headline capturing the week's dominant macro story (e.g. 'BoC Holds Rates as February Jobs Report Shows 84,000 Lost')",
    "key_indicators": [
        {{"label": "SHORT LABEL", "value": "latest value with unit", "change": "+/- change vs prior period or empty string"}},
        "Pick 5-7 indicators most relevant to THIS WEEK's story. Always include BoC rate, GDP, CPI, unemployment. Fill remaining slots with whichever indicators are most newsworthy this week (e.g. trade balance, housing starts, employment change, wage growth, oil price, CAD/USD, 10Y yield). Labels should be SHORT (1-2 words, uppercase)."
    ],
    "executive_summary": "<p><span class=\\"lead-sentence\\">Dominant national story with key figure</span> — supporting detail.<sup>1</sup></p><p><span class=\\"lead-sentence\\">Next national data point</span> — supporting national data.<sup>2</sup></p><p><span class=\\"lead-sentence\\">Notable provincial development</span> — specific projects and values.<sup>3</sup></p><p><span class=\\"lead-sentence\\">Policy action</span> — project developments.<sup>4</sup></p><p><span class=\\"lead-sentence\\">Cross-cutting theme</span> — national-provincial connection.<sup>5</sup></p>",
    "metrics": {{
        "realGdp": "", "nomGdp": "", "outputGap": "", "cpi": "", "shelterCpi": "",
        "bocRate": "{hard_data['boc_rate']}", "unemployment": "", "participation": "",
        "wageGrowth": "", "currentAccount": "", "agCrop": "", "farmCash": ""
    }},
    "national": {{
        "analysis": "<p>2-3 sentence paragraph: dominant data release with key figure.<sup>1</sup></p><p>Supporting data point.<sup>2</sup></p><p>Secondary development or counterpoint.<sup>3</sup></p><p>Policy action or project update.<sup>4</sup></p><p>Cross-reference to project database.<sup>5</sup></p>",
        "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://example.com/article"}}]
    }},
    "global": [
        {{"region": "United States", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}}, "indicatorMeta": {{"gdp": {{"change": "", "prev": ""}}, "cpi": {{"change": "", "prev": ""}}, "rate": {{"change": "", "prev": ""}}, "unemployment": {{"change": "", "prev": ""}}, "tradeBalance": {{"change": "", "prev": ""}}, "productivityGrowth": {{"change": "", "prev": ""}}}}, "analysis": "<p>Flowing prose paragraphs with embedded data and <sup>N</sup> citations. 250-350 words.</p>", "sources": [{{"id": 1, "title": "", "url": "https://..."}}]}},
        {{"region": "China", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}}, "indicatorMeta": {{"gdp": {{"change": "", "prev": ""}}, "cpi": {{"change": "", "prev": ""}}, "rate": {{"change": "", "prev": ""}}, "unemployment": {{"change": "", "prev": ""}}, "tradeBalance": {{"change": "", "prev": ""}}, "productivityGrowth": {{"change": "", "prev": ""}}}}, "analysis": "<p>Flowing prose...</p>", "sources": []}},
        {{"region": "European Union", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}}, "indicatorMeta": {{"gdp": {{"change": "", "prev": ""}}, "cpi": {{"change": "", "prev": ""}}, "rate": {{"change": "", "prev": ""}}, "unemployment": {{"change": "", "prev": ""}}, "tradeBalance": {{"change": "", "prev": ""}}, "productivityGrowth": {{"change": "", "prev": ""}}}}, "analysis": "<p>Flowing prose...</p>", "sources": []}},
        {{"region": "United Kingdom", "emoji": "", "indicators": {{"gdp": "", "cpi": "", "rate": "", "unemployment": "", "tradeBalance": "", "productivityGrowth": ""}}, "indicatorMeta": {{"gdp": {{"change": "", "prev": ""}}, "cpi": {{"change": "", "prev": ""}}, "rate": {{"change": "", "prev": ""}}, "unemployment": {{"change": "", "prev": ""}}, "tradeBalance": {{"change": "", "prev": ""}}, "productivityGrowth": {{"change": "", "prev": ""}}}}, "analysis": "<p>Flowing prose...</p>", "sources": []}}
    ],
    "globalVectors": {{"us": "", "china": "", "eu": ""}},
    "consumer_pulse": "<p>Lead paragraph on dominant consumer-facing theme from this week's news coverage.<sup>N</sup></p><p>Secondary consumer theme with transition.<sup>N</sup></p><p>Third theme or divergence in consumer conditions reported.<sup>N</sup></p>",
    "indicatorContextLines": {{"bocRate": "", "cpi": "", "unemployment": "", "housingStarts": "", "realGdp": ""}},
    "watchlist": [
        {{
            "date": "Mar 14",
            "week_label": "This Week",
            "institution": "Statistics Canada",
            "event_name": "Consumer Price Index",
            "description": "One sentence on what to watch and why it matters for Canada.",
            "impact": "high",
            "source_url": "https://www150.statcan.gc.ca/n1/daily-quotidien/en"
        }}
    ],
    "word_cloud_topics": [
        {{"topic": "tariff retaliation", "sentiment_score": -0.7, "frequency": 9}},
        {{"topic": "BoC rate hold", "sentiment_score": 0.2, "frequency": 7}},
        {{"topic": "housing affordability", "sentiment_score": -0.5, "frequency": 6}}
    ]
}}"""

    industry_arts_text = _format_articles_for_prompt(
        [a for a in economy_arts if any(kw in (a.get('title','') + a.get('text','')).lower()
                                        for kw in ('energy','oil','gas','mining','manufactur',
                                                   'agriculture','housing','finance','tech',
                                                   'health','yield','bond','retail','transit',
                                                   'transport','warehouse','wholesale','telecom',
                                                   'real estate','education','university',
                                                   'entertainment','hotel','tourism','waste',
                                                   'military','defense','government'))][:50]
    )

    _call2_prompt = f"""Today: {today_str}

VERIFIED DATA:
{hard_summary}

RECENT ARTICLES (grouped by industry — cite by article number, use URLs exactly as given):
{industry_arts_text}

{_signal_blocks.get('sector_signals', '')}

{CITATION_RULES}

Write:

1. INDUSTRY EXECUTIVE SUMMARY (2-3 short paragraphs, 120-200 words):
Format as HTML paragraphs: <p>paragraph text</p>
Be concise — TL;DR style. Lead with the single biggest sectoral story and its key figure. Second paragraph covers the next 2-3 most notable sector movements. Optional third paragraph only for a genuinely significant cross-sector pattern. Cut filler — every sentence must carry a specific data point. NO forecasting, NO "expected to", NO "looking ahead". Every claim backed by <sup>N</sup> citation.
IMPORTANT: Do NOT repeat developments already covered in the executive summary (Call 1). Focus on sector-specific data points, industry-level trends, and NAICS subsector details not mentioned in the national overview. If a topic was a headline item in the executive summary, reference it briefly and add NEW sector-specific detail rather than restating it.

2. SECTOR ANALYSIS — goodsIndustries: Exactly 5 goods-producing sectors. Per sector: 150 words in bullets. 3-digit NAICS subsector commentary where data supports.
   For each:
   - code: NAICS code string exactly as listed below
   - name: sector display name
   - mm: set to "" — injected from StatCan Table 36-10-0434-01; must not be estimated
   - yy: set to "" — injected from StatCan; must not be estimated
   - analysis: HTML bullets referencing the PRIMARY SOURCE INDICATOR M/M and Y/Y from hard data. Every bullet ends with <sup>N</sup>. Format: <ul class="list-disc list-inside space-y-2 text-slate-600 text-xs"><li>...</li></ul>
   - industrySources: array of {{id, title, url}}
   - isNegative: boolean — set based on the M/M value in PRIMARY SOURCE INDICATORS
   - subsectors: 2-3 subsectors each with code, name, mm set to ""

   The 5 goods sectors: "11" Agriculture, "21" Mining & Energy, "22" Utilities, "23" Construction, "31-33" Manufacturing.

3. servicesIndustries: Exactly 15 services-producing sectors. Same format as goodsIndustries — mm and yy must be "".

   The 15 services sectors: "41" Wholesale Trade, "44-45" Retail Trade, "48-49" Transportation & Warehousing, "51" Information & Culture, "52" Finance & Insurance, "53" Real Estate, "54" Professional Services, "55" Management, "56" Admin & Waste Mgmt, "61" Education, "62" Health Care, "71" Entertainment & Recreation, "72" Accommodation & Food, "81" Other Services, "91" Public Administration.

4. yieldCurve: Full GoC curve 1M through 30Y. highlight: true on 2Y and 10Y only.

5. charts: yieldCurveCurrent (array of float values matching yieldCurve order), yieldCurveLastYear (array of floats for 1-yr prior, or empty []).

DO NOT discuss stock market movements, equity index levels, or stock performance (e.g. TSX, S&P 500, Dow, NASDAQ gains/losses). Rate changes, yield changes, FX, and bond markets ARE fair game.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "industry_executive_summary": "<p>Lead paragraph with dominant sectoral development.<sup>1</sup></p><p>Related industry thread with transition.<sup>2</sup></p><p>Secondary sectors and cross-cutting themes.<sup>3</sup></p>",
    "goodsIndustries": [
        {{
            "code": "11", "name": "Agriculture", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://..."}}],
            "isNegative": false,
            "subsectors": [{{"code": "", "name": "", "mm": ""}}]
        }}
    ],
    "servicesIndustries": [
        {{
            "code": "41", "name": "Wholesale Trade", "mm": "", "yy": "",
            "analysis": "<ul class=\\"list-disc list-inside space-y-2 text-slate-600 text-xs\\"><li>specific bullet <sup>1</sup></li></ul>",
            "industrySources": [{{"id": 1, "title": "", "url": "https://..."}}],
            "isNegative": false,
            "subsectors": [{{"code": "", "name": "", "mm": ""}}]
        }}
    ],
    "yieldCurve": [
        {{"term": "1M", "yield": "", "highlight": false}},
        {{"term": "3M", "yield": "", "highlight": false}},
        {{"term": "6M", "yield": "", "highlight": false}},
        {{"term": "1Y", "yield": "", "highlight": false}},
        {{"term": "2Y", "yield": "", "highlight": true}},
        {{"term": "5Y", "yield": "", "highlight": false}},
        {{"term": "10Y", "yield": "", "highlight": true}},
        {{"term": "30Y", "yield": "", "highlight": false}}
    ],
    "charts": {{
        "yieldCurveCurrent": [],
        "yieldCurveLastYear": []
    }}
}}"""

    # Build provincial article context: matching articles + RSS items per province
    prov_arts_text = _format_articles_for_prompt(economy_arts[:60], max_chars=18000)
    rss_ctx        = rss_monitor.format_for_context(rss_items or [], max_items=60) if rss_items else ''

    # Build provincial officials context from watchlist (all provinces in one block)
    prov_officials_lines = []
    for prov_name in ['Ontario', 'Quebec', 'Alberta', 'British Columbia', 'Saskatchewan',
                      'Manitoba', 'Nova Scotia', 'New Brunswick', 'Newfoundland and Labrador',
                      'Prince Edward Island', 'Yukon', 'Northwest Territories', 'Nunavut']:
        ctx = _build_provincial_officials_context(prov_name, watchlist)
        if ctx:
            prov_officials_lines.append(ctx)
    prov_officials_ctx = '\n'.join(prov_officials_lines)

    _call3_prompt = f"""Today: {today_str}
Bank of Canada Policy Rate: {hard_data['boc_rate']}

NEWS ARTICLES (cite by article number — use URLs exactly as given):
{prov_arts_text}

GOVERNMENT RSS NEWS RELEASES:
{rss_ctx[:8000]}

{prov_officials_ctx}

{_signal_blocks.get('province_signals', '')}

{CITATION_RULES}

INSTRUCTIONS — Generate the 'provinces' array for ALL 13 provinces and territories (in this order):
Ontario, Quebec, Alberta, British Columbia, Saskatchewan, Manitoba, Nova Scotia, New Brunswick, Newfoundland & Labrador, Prince Edward Island, Yukon, Northwest Territories, Nunavut

For EACH:
a) indicators: Set ALL four fields (gdp, unemployment, cpi, housingStarts) to "" — they will be overwritten from primary data APIs (StatCan) and must not be estimated or hallucinated.
b) analysis: 6-8 short prose paragraphs (300-450 words per province, 2-3 sentences each). Format as HTML: <p>paragraph</p>. Write like a wire service dispatch — factual, specific, no editorializing.
   Structure each province's analysis as:
   - Opening paragraph: State the latest GDP/employment data with figures inline ("grew at an annualized rate of 1.3%", "placing it above the national average").
   - Sector paragraphs: Report what happened in 2-3 key sectors with specific figures ("manufacturing sales rose in two of the last three months", "exports to non-US partners were up 20% year-to-date").
   - Policy/fiscal paragraph: Report government spending decisions, capital plans, fiscal position ("The provincial government's capital plan allocated a 16% increase in planned outlays").
   - Project paragraph: Report specific capital projects announced, approved, or advancing.
   NEVER forecast. NEVER use "looking ahead", "expected to", "is likely to", "outlook", "on a positive note", "going forward". Only report what HAS happened. Compare to national average where relevant. Every claim backed by <sup>N</sup> citation. No bullet points.
c) sources: Array matching citation numbers. id, title (Publication — Article Title, Month YYYY), url (direct link — REQUIRED, use homepage if exact URL unknown).
d) projects: 2-4 major capital projects. Each: name, description (1 sentence, max 20 words, names the proponent), sector, value (e.g. "$4.2B"), status (Announced/Approved/Under Construction/Operational/Completed/Cancelled), completionDate (e.g. "2027" or ""), cma (nearest city/CMA), tags (array of 1-3 strings), sources (array with id/title/url).

BAD: "Ontario's economy continues its growth trajectory" / "The sector is expected to see significant investment" / "Looking ahead, conditions should improve"
GOOD: "Statistics Canada revised Ontario's Q3 2025 GDP growth upward to 1.8% annualized from an initial 1.2% estimate. Business capital spending was revised up $1.4B, the largest upward revision since 2019.<sup>1</sup>"

DO NOT discuss stock market movements, equity index levels, or stock performance. Rate changes, yield changes, FX, and bond markets ARE fair game.

OUTPUT: Valid JSON only. No markdown. No text outside JSON.

SCHEMA:
{{
    "provinces": [
        {{
            "name": "Ontario",
            "indicators": {{"gdp": "+X.X%", "unemployment": "X.X%", "cpi": "+X.X%", "housingStarts": "XX,XXX", "participationRate": "XX.X%", "employmentRate": "XX.X%", "buildingPermits": "+X.X%"}},
            "indicatorMeta": {{"gdp": {{"change": "+X.Xpp vs prior period", "prev": "prior value", "period": "e.g. Q3 2025"}}, "unemployment": {{"change": "+X.Xpp", "prev": "", "period": "e.g. Feb 2026"}}, "cpi": {{"change": "+X.Xpp", "prev": "", "period": ""}}, "housingStarts": {{"change": "+/-XXXX", "prev": "", "period": ""}}, "participationRate": {{"change": "", "prev": "", "period": ""}}, "employmentRate": {{"change": "", "prev": "", "period": ""}}, "buildingPermits": {{"change": "", "prev": "", "period": ""}}}},
            "analysis": "<p>2-3 sentences: latest data release with key figure.<sup>1</sup></p><p>Sector data point.<sup>2</sup></p><p>Second sector.<sup>3</sup></p><p>Policy action or fiscal data.<sup>4</sup></p><p>Project update.<sup>5</sup></p>",
            "sources": [{{"id": 1, "title": "StatCan — Labour Force Survey, March 2026", "url": "https://..."}}, {{"id": 2, "title": "Globe and Mail — Article Title, March 2026", "url": "https://..."}}],
            "projects": [
                {{
                    "name": "Project Name",
                    "description": "1-2 sentences describing what the project is, who is building/operating it, and its scope or purpose.",
                    "sector": "Energy",
                    "value": "$X.XB",
                    "status": "Under Construction",
                    "completionDate": "2027",
                    "cma": "Greater Toronto Area",
                    "tags": ["tag1", "tag2"],
                    "sources": [{{"id": 1, "title": "Publication — Title, Month YYYY", "url": "https://example.com/article"}}]
                }}
            ]
        }}
    ]
}}"""
    # Split project articles into 2 batches of 30 to prevent truncation
    proj_batch_1 = project_arts[:30]
    proj_batch_2 = project_arts[30:60]
    proj_arts_text_1 = _format_articles_for_prompt(proj_batch_1, max_chars=12000)
    proj_arts_text_2 = _format_articles_for_prompt(proj_batch_2, max_chars=12000) if proj_batch_2 else ""

    _PROJ_EXTRACT_SCHEMA = """{
  "projects": [
    {
      "project_name": "Full official project name",
      "province": "2-letter province code: ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU",
      "cma": "Census Metropolitan Area or nearest city",
      "sector": "oil_gas | mining | infrastructure | power_energy | manufacturing | transport_logistics | healthcare | education | residential | commercial_mixed | agriculture | forestry | defence | telecom | indigenous | environment | tourism_culture | government",
      "naics_code": "NAICS code string e.g. '21'",
      "tags": ["tag1", "tag2"],
      "estimated_value": "$X.XB or $XXXM or '' if unknown",
      "status": "Proposed | Under Review | Approved | Under Construction | Partially Complete | Complete | Cancelled | On Hold",
      "announcement_date": "YYYY-MM-DD when project was officially announced, or '' if unknown",
      "estimated_start_date": "YYYY-MM-DD estimated construction start, or '' if unknown",
      "estimated_completion_date": "YYYY-MM-DD estimated completion, or '' if unknown",
      "proponent": "Company or organization behind the project",
      "detail": "2-3 sentence description of what the article reports about this project",
      "source": {"title": "article title", "url": "article URL verbatim", "date": "published date"}
    }
  ]
}"""

    _call4_prompt = f"""Today: {today_str}

PROJECT DISCOVERY ARTICLES (extract capital projects — use article URLs verbatim):
{{proj_batch_text}}

INSTRUCTIONS:
For each article that mentions a Canadian capital project worth $5M or more,
extract structured data. Only include real, clearly described projects.
Never fabricate project details not present in the articles.
Some articles include metadata hints (sector_hints, province_hints) derived from source metadata.
Use these as starting points but verify against the article content.
The hints may be empty, incomplete, or occasionally wrong — they are signals, not ground truth.

IMPORTANT:
- Use 2-letter province codes (ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU)
- Use exact canonical statuses (Proposed, Under Review, Approved, Under Construction, Partially Complete, Complete, Cancelled, On Hold)
- Use canonical sector keys (oil_gas, mining, infrastructure, power_energy, manufacturing, etc.)
- Extract ACTUAL dates from the article text — do NOT use today's date
- Include the proponent (company/organization) if mentioned

Output ONLY valid JSON. No markdown. No text outside JSON.

SCHEMA:
{_PROJ_EXTRACT_SCHEMA}

If no projects found, return: {{"projects": []}}"""

    # ── Execute calls ──────────────────────────────────────────────
    # Calls 1+2: writing agents (Claude Code subprocess or API fallback)
    # Call 3: province agents (Claude Code subprocess or API fallback)
    # Call 4: extraction (API — Sonnet)
    _call4a_prompt = _call4_prompt.replace("{proj_batch_text}", proj_arts_text_1)
    _call4b_prompt = _call4_prompt.replace("{proj_batch_text}", proj_arts_text_2) if proj_arts_text_2 else None

    # Call 4 (extraction) runs via API in parallel with agents
    with ThreadPoolExecutor(max_workers=2 if _call4b_prompt else 1) as executor:
        f4a = executor.submit(_call_claude, _call4a_prompt, "call4a-projects",
                              max_tokens=8096, model=SONNET_MODEL,
                              anthropic_client=anthropic_client, cost_state=cost_state,
                              conn=conn, gemini_client=gemini_client)
        if _call4b_prompt:
            f4b = executor.submit(_call_claude, _call4b_prompt, "call4b-projects",
                                  max_tokens=8096, model=SONNET_MODEL,
                                  anthropic_client=anthropic_client, cost_state=cost_state,
                                  conn=conn, gemini_client=gemini_client)

        # ── Writing agents (replaces Calls 1+2) ─────────────────────
        from phases.writing_agents import run_all_writing_agents
        dossier = dossier or {}
        if dossier:
            print(f"  [Writing Agents] Starting with dossier ({len(dossier.get('top_stories',[]))} stories)...")
        else:
            print(f"  [Writing Agents] Starting macro + industry writing agents...")
        writing_payload = run_all_writing_agents(
            hard_data=hard_data,
            articles=articles,
            rss_items=rss_items,
            events=events,
            signal_context=signal_context,
            watchlist=watchlist,
            anthropic_client=anthropic_client,
            cost_state=cost_state,
            conn=conn,
            gemini_client=gemini_client,
            dossier=dossier,
        )

        # ── Province agents (replaces Call 3) ────────────────────────
        from phases.province_agents import run_province_agents
        print(f"  [Province Agents] Starting per-province writing agents...")
        province_events = events or []
        call3_provinces = run_province_agents(
            articles=articles,
            rss_items=rss_items or [],
            events=province_events,
            signal_context=signal_context or {},
            watchlist=watchlist or {},
            hard_data=hard_data,
            anthropic_client=anthropic_client,
            cost_state=cost_state,
            conn=conn,
            gemini_client=gemini_client,
            dossier=dossier,
        )

        # Wait for Call 4 extraction results
        call4a_raw = f4a.result()
        call4b_raw = f4b.result() if _call4b_prompt else {}

    # ── Build call1/call2/call3 from agent outputs ───────────────
    # call1 = writing_payload fields that correspond to the old Call 1 output
    call1 = {
        'headline': writing_payload.get('headline', ''),
        'key_indicators': writing_payload.get('key_indicators', []),
        'executive_summary': writing_payload.get('executive_summary', ''),
        'metrics': writing_payload.get('metrics', {}),
        'national': writing_payload.get('national', {'analysis': '', 'sources': []}),
        'global': writing_payload.get('global', []),
        'globalVectors': writing_payload.get('globalVectors', {}),
        'consumer_pulse': writing_payload.get('consumer_pulse', ''),
        'word_cloud_topics': writing_payload.get('word_cloud_topics', []),
        'indicatorContextLines': writing_payload.get('indicatorContextLines', {}),
        'watchlist': writing_payload.get('watchlist', []),
        'insightChart': writing_payload.get('insightChart', None),
    }
    # call2 = writing_payload fields that correspond to the old Call 2 output
    call2 = {
        'industry_executive_summary': writing_payload.get('industry_executive_summary', ''),
        'goodsIndustries': writing_payload.get('goodsIndustries', []),
        'servicesIndustries': writing_payload.get('servicesIndustries', []),
        'yieldCurve': writing_payload.get('yieldCurve', []),
        'charts': writing_payload.get('charts', {}),
    }
    call3 = {'provinces': call3_provinces}
    print(f"  [1-4] All calls completed (Writing Agents: macro+industry, Province Agents: {len(call3_provinces)} provinces, API: extraction)")

    # ── Citation audits (parallel, after all calls — non-fatal) ────
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            fa1 = executor.submit(run_citation_audit, call1 or {}, 'call1-macro',
                                  anthropic_client=anthropic_client)
            fa2 = executor.submit(run_citation_audit, call2 or {}, 'call2-industries',
                                  anthropic_client=anthropic_client)
            fa3 = executor.submit(run_citation_audit, call3 or {}, 'call3-provinces',
                                  anthropic_client=anthropic_client)

        audit1 = fa1.result()
        audit1['_label'] = 'call1-macro'
        audit_results.append(audit1)
        audit2 = fa2.result()
        audit2['_label'] = 'call2-industries'
        audit_results.append(audit2)
        audit3 = fa3.result()
        audit3['_label'] = 'call3-provinces'
        audit_results.append(audit3)
    except RuntimeError as e:
        print(f"  [Citation audit] Skipped (non-fatal): {e}")

    # Merge Call 4 batch results
    extracted_projects = (call4a_raw or {}).get('projects', []) + (call4b_raw or {}).get('projects', [])
    print(f"  [Call 4] Extracted {len(extracted_projects)} projects from articles")

    # ── Wire Call 4 projects into DB ──────────────────────────────
    if extracted_projects and conn:
        from normalize import normalize_province, normalize_status, parse_value
        from project_schema import build_project_document
        from project_sync import upsert_flat_projects

        # Transform Call 4 schema → pipeline schema
        call4_for_db = []
        for ep in extracted_projects:
            source_url = ""
            if ep.get("source"):
                source_url = ep["source"].get("url", "")
            if not source_url:
                continue  # URL hard gate

            # Normalize province and status at extraction time
            raw_prov = ep.get("province", "")
            prov_code, prov_add = normalize_province(raw_prov)
            if not prov_code:
                continue

            call4_for_db.append({
                "name": ep.get("project_name", ""),
                "province": prov_code,
                "provinces_additional": prov_add,
                "cma": ep.get("cma", ""),
                "sector": ep.get("sector", ""),
                "naics_code": ep.get("naics_code", ""),
                "value": ep.get("estimated_value", ""),
                "parsed_value": parse_value(ep.get("estimated_value", "")),
                "status": normalize_status(ep.get("status", "Proposed")),
                "proponent": ep.get("proponent", ""),
                "description": ep.get("detail", ""),
                "announcement_date": ep.get("announcement_date", ""),
                "start_date": ep.get("estimated_start_date", ""),
                "completionDate": ep.get("estimated_completion_date", ""),
                "tags": ep.get("tags", []),
                "evidence": [{
                    "url": source_url,
                    "source_type": "news_article",
                    "name": ep.get("source", {}).get("title", ""),
                    "date": ep.get("source", {}).get("date", ""),
                }],
                "discovery_source": "call4_extraction",
                "discovery_sources": ["call4_extraction"],
                "confidence": 0.4,
            })

        if call4_for_db:
            try:
                result = upsert_flat_projects(conn, call4_for_db)
                print(f"  [Call 4 → DB] {result.get('new', 0)} new, {result.get('updated', 0)} updated, {result.get('skipped', 0)} skipped")
            except Exception as e:
                print(f"  [Call 4 → DB] Error: {e}")

    # ── Merge all four results ─────────────────────────────────────
    payload = {}
    payload.update(call1 or {})
    payload.update(call2 or {})
    if call3 and 'provinces' in call3:
        payload['provinces'] = call3['provinces']
    elif not payload.get('provinces'):
        payload['provinces'] = []

    # Ensure new fields are present
    if not payload.get('consumer_pulse'):
        payload['consumer_pulse'] = ''
    if not payload.get('industry_executive_summary'):
        payload['industry_executive_summary'] = ''

    # ── Enrich source URLs: map known titles to real URLs ─────────
    _enrich_source_urls(payload)

    # ── Apply citation audit: remove failed claims from text ──────
    for audit in audit_results:
        if not audit.get('passed', True):
            # If audit failed (>30% removal), flag for review
            print(f"  [Citation Audit] {audit.get('_label', '?')}: FAILED — flagging for manual review")
        failed_cites = audit.get('failed_citations', [])
        unsourced = audit.get('unsourced_claims', [])
        if failed_cites or unsourced:
            # Remove failed claims from relevant text fields
            for text_key in ('executive_summary', 'consumer_pulse', 'industry_executive_summary'):
                if payload.get(text_key):
                    payload[text_key] = remove_failed_claims(
                        payload[text_key], failed_cites, unsourced)
            # Remove from national analysis
            if payload.get('national', {}).get('analysis'):
                payload['national']['analysis'] = remove_failed_claims(
                    payload['national']['analysis'], failed_cites, unsourced)
            # Remove from global analyses
            for g in payload.get('global', []):
                if g.get('analysis'):
                    g['analysis'] = remove_failed_claims(g['analysis'], failed_cites, unsourced)

    # ── Save citation audit log ────────────────────────────────────
    if audit_results:
        save_audit_log(audit_results)
        all_passed = all(a.get('passed', True) for a in audit_results)
        total_cites = sum(a.get('total_citations', 0) for a in audit_results)
        total_failed = sum(a.get('failed_count', 0) for a in audit_results)
        total_archived = sum(a.get('archived_count', 0) for a in audit_results)
        status = 'ALL PASSED' if all_passed else 'SOME FAILED (>30% removal — review before publish)'
        print(f"  [Citation Audit] {status}: {total_cites} citations, {total_failed} failed, {total_archived} archived")
        payload['citation_audit'] = {
            'passed': all_passed,
            'total_citations': total_cites,
            'total_failed': total_failed,
            'total_archived': total_archived,
            'calls': [{
                'label': a.get('_label', ''),
                'passed': a.get('passed', True),
                'citations': a.get('total_citations', 0),
                'failed': a.get('failed_count', 0),
                'removal_pct': a.get('removal_pct', 0),
                'archived': a.get('archived_count', 0),
            } for a in audit_results],
        }

    # ── Collect all verified source URLs with archive URLs ──────
    all_sources = []
    for audit in audit_results:
        for vc in audit.get('verified_citations', []):
            if vc.get('url'):
                all_sources.append({
                    'url': vc['url'],
                    'title': vc.get('title', ''),
                    'archive_url': vc.get('archive_url', ''),
                })
    payload['_all_verified_sources'] = all_sources

    print("  Claude analysis complete.")
    return payload


# ── Indicator metadata ───────────────────────────────────────────────────────

def _build_indicator_meta(nat: dict, boc_data: dict) -> dict:
    """Build indicatorMeta dict from primary-source national indicators."""
    meta = {}
    field_defs = {
        'cpi':           ('CPI YoY',        '%'),
        'unemployment':  ('Unemployment',    '%'),
        'bocRate':       ('BoC Rate',        '%'),
        'housingStarts': ('Housing Starts',  ''),
    }
    for field, (_label, _unit) in field_defs.items():
        if field == 'bocRate':
            cur  = boc_data.get('rate', '')
            prev = boc_data.get('prev', '')
            dt   = boc_data.get('date', '')
            src  = 'BoC'
        else:
            cur  = nat.get('values', {}).get(field, '')
            prev = nat.get('prev_values', {}).get(field, '')
            dt   = nat.get('obs_dates', {}).get(field, '')
            src  = nat.get('sources', {}).get(field, '')
        meta[field] = {
            'prev':    prev,
            'change':  _calc_change(cur, prev),
            'period':  _fmt_period(dt),
            'obsDate': dt,
            'source':  src,
            'context': '',
        }
    return meta


def generate_context_lines(ind_meta: dict, national_values: dict,
                           anthropic_client=None) -> dict:
    """Generate plain-English context for each national indicator.

    Default: Claude Code subprocess ($0). Fallback: Anthropic API.
    """
    try:
        items = []
        for field, m in ind_meta.items():
            cur = national_values.get(field, '')
            items.append(
                f"- {field}: value={cur}, prev={m.get('prev','')}, "
                f"change={m.get('change','')}, period={m.get('period','')}"
            )
        prompt = (
            "For each Canadian economic indicator below, write ONE specific sentence (10-15 words) "
            "explaining the key driver or market implication. Use concrete numbers where relevant. "
            "Respond with a JSON object: {\"field\": \"sentence\"}.\n\n"
            + "\n".join(items)
        )

        text = None

        # ── Claude Code mode (default, $0) ──────────────────────────
        from claude_reasoning import (
            REASONING_AGENT_MODE, _call_claude_code_sync, ALLOW_API_FALLBACK,
        )
        if REASONING_AGENT_MODE == 'claude_code':
            text = _call_claude_code_sync(prompt, "context-lines")

        # ── API fallback (gated; non-critical so silent skip is fine) ──
        if not text and ALLOW_API_FALLBACK:
            if anthropic_client is None:
                anthropic_client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip()
                )
            msg = anthropic_client.messages.create(
                model=SONNET_MODEL,
                max_tokens=400,
                messages=[{'role': 'user', 'content': prompt}]
            )
            if msg.content:
                text = msg.content[0].text

        if not text:
            print(f"  [CONTEXT LINES] Empty response (non-critical)")
            return {}
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            lines = json.loads(json_match.group())
            print(f"  [CONTEXT LINES] Generated {len(lines)} context lines.")
            return lines
    except Exception as e:
        print(f"  [CONTEXT LINES] Failed (non-critical): {e}")
    return {}


# ── Indicator validation ─────────────────────────────────────────────────────

def validate_indicators(final_payload: dict, primary: dict) -> None:
    """
    Cross-check every injected indicator in final_payload against primary_indicators.
    Logs a WARNING if the payload value does not match the API value.
    Does NOT modify the payload — the assembly steps have already overwritten everything.
    """
    print("\n[VALIDATION] Cross-checking indicator provenance...")
    mismatches = 0

    # National metrics
    m = final_payload.get('metrics', {})
    for field, api_val in primary.get('national', {}).get('values', {}).items():
        if not api_val:
            continue
        payload_val = m.get(field)
        if payload_val and payload_val not in ('N/A', api_val):
            print(f"  [WARN] national.{field}: payload='{payload_val}', api='{api_val}'")
            mismatches += 1

    # Industry M/M and Y/Y
    ind_data = primary.get('industries', {})
    for list_key in ('goodsIndustries', 'servicesIndustries'):
        for ind_entry in final_payload.get(list_key, []):
            code = (ind_entry.get('code') or '').strip()
            api_ind = ind_data.get(code) or ind_data.get(code.split('/')[0].strip(), {})
            for field in ('mm', 'yy'):
                api_val    = api_ind.get(field)
                payload_val = ind_entry.get(field)
                if (api_val and api_val != 'N/A' and
                        payload_val and payload_val not in ('N/A', api_val)):
                    print(f"  [WARN] industry[{code}].{field}: "
                          f"payload='{payload_val}', api='{api_val}'")
                    mismatches += 1

    if mismatches == 0:
        print("  All injected indicators match primary sources.")
    else:
        print(f"  {mismatches} mismatch(es) logged "
              "(payload already contains the correct API values).")


# ── Source verification helpers ──────────────────────────────────────────────

def _check_url(url: str) -> bool:
    """HEAD request (5 s timeout) to verify a URL is reachable. Returns False on any error."""
    import requests
    if not url or not url.startswith('http'):
        return False
    try:
        r = requests.head(url, timeout=5, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'})
        return r.status_code < 400
    except Exception:
        return False


def _collect_source_dicts(payload: dict) -> list:
    """Return every source dict object (by reference) from known payload locations."""
    srcs = []
    srcs.extend(payload.get('national', {}).get('sources', []))
    for g in payload.get('global', []):
        srcs.extend(g.get('sources', []))
    for ind in payload.get('goodsIndustries', []) + payload.get('servicesIndustries', []):
        srcs.extend(ind.get('industrySources', []))
    for prov in payload.get('provinces', []):
        srcs.extend(prov.get('sources', []))
        for prj in prov.get('projects', []):
            srcs.extend(prj.get('sources', []))
    return srcs


def verify_source_urls(payload: dict) -> dict:
    """
    Walk every source object in the payload and run concurrent HEAD checks.
    Any URL that returns 4xx/5xx or fails is cleared to '' (title is kept).
    """
    import concurrent.futures

    print("\n[SOURCE VERIFICATION] Checking all source URLs...")
    all_srcs   = _collect_source_dicts(payload)
    urls       = [s.get('url', '') for s in all_srcs]
    checkable  = [(i, u) for i, u in enumerate(urls) if u and u.startswith('http')]

    if not checkable:
        print("  No URLs to check.")
        return payload

    print(f"  Checking {len(checkable)} URLs (concurrent HEAD requests)...")
    indices, to_check = zip(*checkable)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_check_url, to_check))

    dead = 0
    for idx, is_live in zip(indices, results):
        if not is_live:
            all_srcs[idx]['url'] = ''
            dead += 1

    print(f"  Live: {len(checkable) - dead}  Dead (cleared): {dead}")
    return payload


def _all_sources(payload):
    """Yield all source dicts from the final payload (any nesting level)."""
    if not payload or not isinstance(payload, dict):
        return
    for key, val in payload.items():
        if key in ('sources', 'industrySources'):
            for src in (val if isinstance(val, list) else []):
                if isinstance(src, dict):
                    yield src
        elif isinstance(val, dict):
            yield from _all_sources(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    yield from _all_sources(item)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(conn, context, logger):
    """Phase 5: Analysis — Claude calls 1-4, hard data override, indicator validation."""
    step_name = "Phase 5: Analysis"
    try:
        anthropic_client = context.get("anthropic_client")
        gemini_client = context.get("gemini_client")  # legacy, unused
        if not anthropic_client:
            print(f"  [ANALYSIS] ERROR: Missing anthropic_client in context — cannot run analysis")
            return {"analysis_error": "missing anthropic_client"}
        cost_state = context.get("claude_cost", {"total_usd": 0.0})
        watchlist = context.get("watchlist", {})
        hard_data = context.get("hard_data", {})
        rss_items = context.get("rss_items", [])
        extracted_articles = context.get("extracted_articles", [])
        primary_ind = context.get("primary_ind", {})
        national_ind = context.get("national_ind", {})
        prov_ind = context.get("prov_ind", {})
        global_ind = context.get("global_ind", {})
        commodity_data = context.get("commodity_data", {})
        financial_markets = context.get("financial_markets", {})
        boc_data = context.get("boc_data", {})
        yield_data = context.get("yield_data", {})

        # Build signal context from Prompts 11-19 data streams
        signal_context = {
            'policy_summary': context.get('policy_summary', {}),
            'policy_items': context.get('policy_items', []),
            'job_spikes': context.get('job_spikes', []),
            'procurement_contracts': context.get('procurement_contracts', []),
            'iaac_status_changes': context.get('iaac_status_changes', []),
            'statcan_extended_tables_ok': context.get('statcan_extended_tables_ok', 0),
            'statcan_extended_saved': context.get('statcan_extended_saved', 0),
        }

        # Load events from database for province agents
        events = []
        try:
            from event_calendar import get_upcoming_events
            events = get_upcoming_events(conn=conn, days_ahead=14) or []
            print(f"  [Events] Loaded {len(events)} events for province agents")
        except Exception as e:
            print(f"  [Events] Could not load events (non-critical): {e}")

        # Call Claude analysis
        final_payload = generate_claude_analysis(
            hard_data, extracted_articles, rss_items,
            anthropic_client=anthropic_client,
            gemini_client=gemini_client,
            cost_state=cost_state,
            conn=conn,
            watchlist=watchlist,
            signal_context=signal_context,
            events=events,
            dossier=context.get('dossier', {}),
        )
        logger.log_step("step_3_claude_analysis")

        # ── Guard: abort if Claude returned nothing useful ────────
        _REQUIRED_KEYS = {'executive_summary', 'provinces'}
        _missing = _REQUIRED_KEYS - set(final_payload or {})
        if not final_payload or _missing:
            msg = f"Claude analysis empty or missing critical keys: {_missing or 'empty dict'}"
            print(f"  [CRITICAL] {msg}")
            logger.log_step("step_3_claude_analysis", "error", msg)
            final_payload.setdefault('_analysis_incomplete', True)
            final_payload.setdefault('_analysis_error', msg)

        # ── STEP 4a: Inject authoritative hard data (overrides AI) ─
        final_payload['commodities']      = commodity_data['structured']
        final_payload['financialMarkets'] = financial_markets
        if yield_data:
            final_payload['yieldCurve'] = yield_data['yieldCurve']
            final_payload['charts']     = yield_data['charts']

        # ── STEP 4b: National metrics — API or N/A, never AI ───────
        m = final_payload.setdefault('metrics', {})
        m['bocRate'] = boc_data['rate'] or 'N/A'
        nat_src = {'bocRate': 'BoC'}
        # Fields that MUST come from a primary API (or N/A — never AI-estimated)
        for field, src_key in [('cpi', 'cpi'), ('unemployment', 'unemployment'),
                                ('housingStarts', 'housingStarts'), ('realGdp', 'realGdp')]:
            api_val = national_ind['values'].get(field)
            if api_val:
                m[field]       = api_val
                nat_src[field] = national_ind['sources'].get(src_key, 'StatCan')
            else:
                m[field]       = 'N/A'
                nat_src[field] = 'N/A'
        # shelterCpi is from the same StatCan release as CPI
        if m.get('cpi') == 'N/A':
            m['shelterCpi'] = 'N/A';  nat_src['shelterCpi'] = 'N/A'
        else:
            nat_src.setdefault('shelterCpi', 'StatCan')
        # Secondary fields — no real-time primary API; values from Claude analysis only
        for field in ('nomGdp', 'outputGap', 'participation',
                      'wageGrowth', 'currentAccount', 'agCrop', 'farmCash'):
            nat_src.setdefault(field, 'N/A')
        final_payload['indicatorSources'] = nat_src

        # ── STEP 4c: Global indicators — API or N/A, never AI ──────
        for entry in final_payload.get('global', []):
            region  = entry.get('region', '')
            real    = global_ind.get(region, {})
            ind     = entry.setdefault('indicators', {})
            ind_src = entry.setdefault('indicatorSources', {})
            for field in ('gdp', 'cpi', 'rate', 'unemployment'):
                api_val = real.get(field)
                if api_val:
                    ind[field]     = api_val
                    ind_src[field] = real.get(f'{field}_src', 'API')
                else:
                    ind[field]     = 'N/A'
                    ind_src[field] = 'N/A'

        # ── STEP 4d: Provincial indicators — API or N/A, never AI ──
        for prov in final_payload.get('provinces', []):
            prov_name = prov.get('name', '')
            ind = prov.setdefault('indicators', {})
            src = prov.setdefault('indicatorSources', {})
            real = prov_ind.get(prov_name, {})
            for field in ('unemployment', 'cpi', 'gdp', 'housingStarts'):
                api_val = real.get(field)
                if api_val:
                    ind[field] = api_val
                    src[field] = real.get(f'{field}_src', 'StatCan')
                else:
                    ind[field] = 'N/A'
                    src[field] = 'N/A'

        # ── STEP 4e: Indicator metadata (prev, change badge, obs date, context) ─
        final_payload['indicatorMeta'] = _build_indicator_meta(national_ind, boc_data)

        # Generate plain-English context lines via Sonnet (non-critical)
        m_vals = final_payload.get('metrics', {})
        ctx = generate_context_lines(final_payload['indicatorMeta'], m_vals,
                                     anthropic_client=anthropic_client)
        for field, sentence in ctx.items():
            if field in final_payload['indicatorMeta']:
                final_payload['indicatorMeta'][field]['context'] = sentence

        # Staleness check — log if any obs date is older than 45 days
        stale_cutoff = (date.today() - timedelta(days=45)).isoformat()
        for field, m_entry in final_payload['indicatorMeta'].items():
            obs_dt = m_entry.get('obsDate', '')
            if obs_dt and obs_dt < stale_cutoff:
                print(f"  [STALE WARNING] {field}: obs date {obs_dt} is older than 45 days")

        # Provincial indicatorMeta — prev value + change badge per province
        for prov in final_payload.get('provinces', []):
            prov_name = prov.get('name', '')
            raw = prov_ind.get(prov_name, {})
            prov['indicatorMeta'] = {
                'unemployment': {
                    'prev':    raw.get('unemployment_prev', ''),
                    'change':  _calc_change(raw.get('unemployment', ''), raw.get('unemployment_prev', '')),
                    'period':  _fmt_period(raw.get('unemployment_date', '')),
                    'obsDate': raw.get('unemployment_date', ''),
                },
                'cpi': {
                    'prev':    raw.get('cpi_prev', ''),
                    'change':  _calc_change(raw.get('cpi', ''), raw.get('cpi_prev', '')),
                    'period':  _fmt_period(raw.get('cpi_date', '')),
                    'obsDate': raw.get('cpi_date', ''),
                },
                'housingStarts': {
                    'prev':    raw.get('housingStarts_prev', ''),
                    'change':  _calc_change(raw.get('housingStarts', ''), raw.get('housingStarts_prev', '')),
                    'period':  raw.get('housingStarts_date', ''),
                    'obsDate': raw.get('housingStarts_date', ''),
                },
                'gdp': {
                    'prev':    '',  # would need n=3 to compute prior-year growth
                    'change':  '',
                    'period':  raw.get('gdp_date', ''),  # e.g. "2024"
                    'obsDate': raw.get('gdp_date', ''),
                },
                # These are already fetched per-province (LFS emp/participation
                # rate, _PROV_EMPRATE_VIDS / _PROV_PARTRATE_VIDS) but were not
                # surfaced into indicatorMeta, so the dashboard showed blank
                # change columns for them.
                'employmentRate': {
                    'prev':    raw.get('employmentRate_prev', ''),
                    'change':  _calc_change(raw.get('employmentRate', ''), raw.get('employmentRate_prev', '')),
                    'period':  _fmt_period(raw.get('employmentRate_date', '')),
                    'obsDate': raw.get('employmentRate_date', ''),
                },
                'participationRate': {
                    'prev':    raw.get('participationRate_prev', ''),
                    'change':  _calc_change(raw.get('participationRate', ''), raw.get('participationRate_prev', '')),
                    'period':  _fmt_period(raw.get('participationRate_date', '')),
                    'obsDate': raw.get('participationRate_date', ''),
                },
                # Fed by _PROV_BUILDING_PERMITS_VIDS / _PROV_WAGE_VIDS in
                # data_collection.py (vectors live-verified 2026-06-09 from
                # Tables 34-10-0292-01 and 14-10-0063-01). raw.get(...) is ''
                # only if the fetch fails, rendering N/A rather than wrong numbers.
                'buildingPermits': {
                    'prev':    raw.get('buildingPermits_prev', ''),
                    'change':  _calc_change(raw.get('buildingPermits', ''), raw.get('buildingPermits_prev', '')),
                    'period':  _fmt_period(raw.get('buildingPermits_date', '')),
                    'obsDate': raw.get('buildingPermits_date', ''),
                },
                'wageGrowth': {
                    'prev':    raw.get('wageGrowth_prev', ''),
                    'change':  _calc_change(raw.get('wageGrowth', ''), raw.get('wageGrowth_prev', '')),
                    'period':  _fmt_period(raw.get('wageGrowth_date', '')),
                    'obsDate': raw.get('wageGrowth_date', ''),
                },
            }

        # ── STEP 4f: Industry indicators — API or N/A, never AI ────
        ind_api = primary_ind['industries']
        for list_key in ('goodsIndustries', 'servicesIndustries'):
            for ind_entry in final_payload.get(list_key, []):
                code = (ind_entry.get('code') or '').strip()
                # Try exact match, then first segment of "21/22"-style codes
                api_data = ind_api.get(code) or ind_api.get(code.split('/')[0].strip())
                if api_data and api_data.get('src') != 'N/A':
                    ind_entry['mm']           = api_data.get('mm', 'N/A')
                    ind_entry['yy']           = api_data.get('yy', 'N/A')
                    ind_entry['isNegative']   = (ind_entry['mm'] or '').startswith('-')
                    ind_entry['indicatorSrc'] = api_data.get('src', 'StatCan')
                else:
                    ind_entry['mm']           = 'N/A'
                    ind_entry['yy']           = 'N/A'
                    ind_entry['isNegative']   = False
                    ind_entry['indicatorSrc'] = 'N/A'
                # Subsectors: no 3-digit StatCan data fetched — set N/A
                for sub in ind_entry.get('subsectors', []):
                    sub['mm'] = 'N/A'

        # ── STEP 4g: Validate indicator provenance ──────────────────
        validate_indicators(final_payload, primary_ind)

        # ── STEP 4e: Verify source URLs ─────────────────────────────
        verify_source_urls(final_payload)

        # ── STEP 4f: Enrich sources with article images ──────────────
        _url_to_image = {}
        for a in extracted_articles:
            img = a.get('image_url', '')
            if img and a.get('url'):
                _url_to_image[a['url']] = img
        for a in (rss_items or []):
            img = a.get('image_url', '')
            if img and a.get('url'):
                _url_to_image[a['url']] = img
        if _url_to_image:
            enriched = 0
            for src in _all_sources(final_payload):
                u = src.get('url', '')
                if u and u in _url_to_image:
                    src['image_url'] = _url_to_image[u]
                    enriched += 1
            if enriched:
                print(f"  [IMAGES] Enriched {enriched} sources with article images")

        logger.log_step(step_name, "success")
        return {"final_payload": final_payload}
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
