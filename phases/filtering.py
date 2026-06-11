"""Phase 3: Filtering — RSS filter, dedup, URL hard gate"""
import os
import traceback
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import rss_monitor

# Parallel workers for the per-province chunked extraction loop. Canada alone
# can produce 60+ chunks (one claude subprocess per chunk); sequential runs
# blew the 2400s Phase 3 budget.
# E-5: bumped default 3 → 6 — Phase 3 does not run the conductor in parallel
# so we can use the full subscription rate without contending for stdin
# pressure. Re-cap to 3 in any phase that runs the conductor concurrently.
RSS_EXTRACT_WORKERS = int(os.environ.get('RSS_EXTRACT_WORKERS', '6'))
from pipeline_config import SONNET_MODEL
from project_dedup import deduplicate_projects
from project_schema import normalize_project_type, is_brownfield
from project_sync import upsert_flat_projects, upsert_projects
from db import get_all_projects


# ── Constants ────────────────────────────────────────────────────────────────

_PROJECT_SYSTEM_PROMPT = (
    "You are a Canadian infrastructure and capital markets researcher. "
    "Provide factual, sourced information about real capital projects in Canada. "
    "Be specific about project names, dollar values, proponents, and status. "
    "Only include real, verifiable projects. Do not fabricate."
)

_PROJECT_SCHEMA = """\
{
  "projects": [
    {
      "name": "Full official project name",
      "description": "1-2 sentences describing what the project is, who is building/operating it, and its scope or purpose",
      "province": "Exact Canadian province or territory name",
      "cma": "Census Metropolitan Area or nearest city/town",
      "sector": "One of: Energy | Mining | Transit | Housing | Defence | Manufacturing | Technology | Healthcare | Agriculture | Telecommunications | Ports & Logistics | Other",
      "naics_code": "NAICS code string, e.g. '21' or '31-33'",
      "tags": ["tag1", "tag2"],
      "value": "$X.XB or $XXXM — use '\\u2014' if unknown",
      "status": "One of: Announced | Approved | Under Construction | Operational | Completed | Cancelled",
      "completionDate": "Expected completion e.g. '2027' — use '' if unknown",
      "announced": "YYYY-MM-DD — use today if unknown",
      "sources": [
        {"id": 1, "title": "Publication \\u2014 Article Title, Month YYYY", "url": "direct link or ''"}
      ]
    }
  ]
}"""

WEEKLY_PROJECT_SECTORS = [
    ("Energy (Oil & Gas)",
     "New oil, gas, pipeline, or LNG capital projects announced in Canada this week — "
     "named proponents, CAD investment values, provinces, and current status."),
    ("Clean Energy",
     "New renewable energy, wind, solar, hydro, nuclear, hydrogen, or carbon capture projects "
     "announced in Canada this week — developer, value, province, status."),
    ("Mining",
     "New mining, potash, critical minerals, gold, copper, or mineral processing projects "
     "announced in Canada this week — operator, value, province, status."),
    ("Infrastructure",
     "New road, bridge, highway, tunnel, or civil infrastructure projects announced or approved "
     "in Canada this week — government funder, value, province."),
    ("Transit & Rail",
     "New urban transit, light rail, subway, GO train, or commuter rail projects announced in "
     "Canada this week — proponent, value, province, status."),
    ("Housing",
     "New large-scale housing developments, affordable housing, or mixed-use projects announced "
     "in Canada this week — developer, unit count or value, province."),
    ("Defence",
     "New defence procurement, military base construction, or national security capital projects "
     "announced in Canada this week — DND, contractor, value."),
    ("Healthcare",
     "New hospital, long-term care, cancer centre, or health facility construction announced in "
     "Canada this week — government funder, value, province, status."),
    ("Technology & Data",
     "New data centre, AI facility, semiconductor plant, or tech infrastructure projects "
     "announced in Canada this week — proponent, value, province."),
    ("Ports & Logistics",
     "New port expansion, intermodal terminal, warehouse, or logistics facility projects "
     "announced in Canada this week — operator, value, province."),
    ("Agriculture",
     "New agri-food processing plant, grain terminal, or agricultural infrastructure project "
     "announced in Canada this week — proponent, value, province."),
    ("Manufacturing",
     "New automotive, steel, chemicals, pulp, or advanced manufacturing investment announced "
     "in Canada this week — company, value, province, jobs created."),
    ("Telecommunications",
     "New telecom network expansion, 5G infrastructure, or rural broadband project announced "
     "in Canada this week — carrier, value, province."),
    ("Water & Wastewater",
     "New water treatment, wastewater, or flood mitigation infrastructure project announced "
     "in Canada this week — municipality, value, province."),
    ("Education",
     "New university building, college campus expansion, or major school construction announced "
     "in Canada this week — institution, value, province."),
    ("Tourism & Hospitality",
     "New resort, hotel, convention centre, or cultural infrastructure project announced in "
     "Canada this week — developer, value, province, status."),
]

DEEP_SWEEP_NAICS = [
    ("11",  "Agriculture & Agri-processing"),
    ("21",  "Mining, Oil & Gas Extraction"),
    ("22",  "Utilities & Energy"),
    ("23",  "Construction & Civil Infrastructure"),
    ("31",  "Food & Beverage Manufacturing"),
    ("32",  "Chemical & Plastics Manufacturing"),
    ("33",  "Primary & Fabricated Metal"),
    ("48",  "Air, Rail & Truck Transportation"),
    ("49",  "Pipeline & Water Transportation"),
    ("51",  "Information & Cultural Industries"),
    ("52",  "Finance & Insurance"),
    ("53",  "Real Estate"),
    ("54",  "Professional, Scientific & Tech Services"),
    ("56",  "Administrative & Support Services"),
    ("61",  "Education"),
    ("62",  "Healthcare & Social Assistance"),
    ("71",  "Arts, Entertainment & Recreation"),
    ("72",  "Accommodation & Food Services"),
    ("81",  "Other Services"),
    ("91",  "Defence & Public Administration"),
]

_WEEKLY_PROVINCES = [
    "Ontario", "Quebec", "Alberta", "British Columbia",
    "Saskatchewan", "Manitoba", "Nova Scotia", "New Brunswick",
    "Newfoundland and Labrador", "Prince Edward Island",
    "Yukon", "Northwest Territories", "Nunavut",
]

_PROV_WEEKLY_THRESHOLDS = {
    "Ontario": "$100M", "Quebec": "$50M", "Alberta": "$50M",
    "British Columbia": "$50M", "Saskatchewan": "$20M", "Manitoba": "$20M",
    "Nova Scotia": "$15M", "New Brunswick": "$15M",
    "Newfoundland and Labrador": "$15M", "Prince Edward Island": "$5M",
    "Yukon": "$3M", "Northwest Territories": "$3M", "Nunavut": "$3M",
}

_PROV_DEEP_THRESHOLDS = {
    "Ontario": "$200M", "Quebec": "$100M", "Alberta": "$100M",
    "British Columbia": "$100M", "Saskatchewan": "$30M", "Manitoba": "$25M",
    "Nova Scotia": "$15M", "New Brunswick": "$15M",
    "Newfoundland and Labrador": "$15M", "Prince Edward Island": "$5M",
    "Yukon": "$3M", "Northwest Territories": "$3M", "Nunavut": "$3M",
}


# ── Helper functions ─────────────────────────────────────────────────────────

def _parse_projects_with_sonnet(raw_text, province, context_label="",
                                anthropic_client=None, claude_model=None, cost_state=None):
    """
    Use Claude Sonnet to parse a Perplexity result into structured project records.
    If province is a specific province name, forces all extracted projects to that province.
    If province is 'Canada', lets Sonnet determine the province from context.
    """
    if not raw_text.strip():
        return []

    system_prompt = (
        "You are a data extraction assistant specializing in Canadian capital projects. "
        "Parse the provided text and return a valid JSON object matching the schema exactly. "
        "Only include projects that are real and clearly described in the source text. "
        "Do not fabricate projects or details not present in the source text. "
        "Return only the JSON object — no markdown fences, no explanation."
    )

    if province and province != "Canada":
        prov_instruction = f"Province: {province} (force all extracted projects to this province)"
    else:
        prov_instruction = (
            "Province: Determine from project context "
            "(set the exact Canadian province or territory name for each project)"
        )

    user_prompt = f"""Extract all capital projects from the text below.

{prov_instruction}
Context: {context_label}

Return only this JSON structure (no markdown, no explanation):
{_PROJECT_SCHEMA}

If no valid projects are found, return: {{"projects": []}}

SOURCE TEXT:
{raw_text}"""

    if cost_state is None:
        cost_state = {"usd": 0.0, "input": 0, "output": 0, "cap": 1.0,
                      "input_cost_per_mtok": 3.0, "output_cost_per_mtok": 15.0}

    if claude_model is None:
        claude_model = SONNET_MODEL

    if cost_state["usd"] >= cost_state["cap"]:
        print(f"    [COST CAP] ${cost_state['usd']:.4f} >= ${cost_state['cap']:.2f} cap — skipping {context_label}")
        return []

    # ── Claude Code mode (default, $0) ──────────────────────────
    from claude_reasoning import (
        REASONING_AGENT_MODE, _call_claude_code_sync, ALLOW_API_FALLBACK,
        _ClaudeCodeTimeout,
    )
    if REASONING_AGENT_MODE == 'claude_code':
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        # D-13: retry once on Claude Code timeout. First attempt: 180s.
        # On TimeoutExpired, retry with a 300s budget. If the retry also
        # times out, log [CHUNK FAIL] and continue — don't crash the phase.
        # Per-chunk budget after retry is 480s, still well within the Phase 3
        # 2400s cap.
        raw = None
        try:
            raw = _call_claude_code_sync(
                full_prompt, f"filter-{context_label}",
                timeout=180, raise_on_timeout=True,
            )
        except _ClaudeCodeTimeout:
            print(f"    [Claude Code] {context_label}: 180s timeout — retrying with 300s budget...")
            try:
                raw = _call_claude_code_sync(
                    full_prompt, f"filter-{context_label}-retry",
                    timeout=300, raise_on_timeout=True,
                )
            except _ClaudeCodeTimeout:
                # context_label already contains "{province} [n/m]"
                # Count items in prompt body for a best-effort article count.
                n_articles = max(
                    user_prompt.count('\n- '),
                    user_prompt.count('\n* '),
                    user_prompt.count('\nURL:'),
                    user_prompt.count('\nTitle:'),
                )
                print(f"    [CHUNK FAIL] {context_label} after 2 attempts ({n_articles} articles)")
                raw = None
        if raw:
            content = raw.strip()
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    projects = parsed.get("projects", [])
                    if isinstance(projects, list):
                        if province and province != "Canada":
                            for p in projects:
                                p['province'] = province
                        print(f"    [Claude Code] {context_label}: {len(projects)} projects ($0)")
                        return projects
            except json.JSONDecodeError:
                print(f"    [Claude Code] {context_label}: JSON parse failed")
        # Fall through to API only if explicitly enabled
        if not ALLOW_API_FALLBACK:
            print(f"    [Claude Code] {context_label}: failed; API fallback disabled "
                  "(set CLAUDE_ALLOW_API_FALLBACK=1 to enable)")
            return []
        if not anthropic_client:
            return []
        print(f"    [Claude Code] {context_label}: falling back to API...")

    # ── API mode (fallback) ─────────────────────────────────────
    for attempt in range(4):
        try:
            msg = anthropic_client.messages.create(
                model=claude_model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            in_tok = getattr(msg.usage, 'input_tokens', 0)
            out_tok = getattr(msg.usage, 'output_tokens', 0)
            cost_state["input"] += in_tok
            cost_state["output"] += out_tok
            call_cost = (in_tok * cost_state["input_cost_per_mtok"] + out_tok * cost_state["output_cost_per_mtok"]) / 1_000_000
            cost_state["usd"] += call_cost
            print(f"    [COST] {context_label}: {in_tok:,} in + {out_tok:,} out = ${call_cost:.4f} (run total: ${cost_state['usd']:.4f}/${cost_state['cap']:.2f})")

            if not msg.content:
                print(f"\n    [SONNET] Empty content from API for {context_label}")
                return []
            content = msg.content[0].text.strip()
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                projects = parsed.get("projects", [])
                if isinstance(projects, list):
                    if province and province != "Canada":
                        for p in projects:
                            p['province'] = province
                    return projects
            return []
        except json.JSONDecodeError as e:
            if attempt == 3:
                print(f"\n    [SONNET JSON ERROR] {context_label}: {e}")
                return []
            time.sleep(1)
        except Exception as e:
            if attempt == 3:
                print(f"\n    [SONNET ERROR] {context_label}: {e}")
                return []
            time.sleep(2 ** attempt)
    return []


# ── Extraction backlog (carryover across runs) ──────────────────────────────
# Phase 3 has a hard wall-clock budget; when it fires, whatever hasn't been
# extracted yet used to vanish silently — including marquee stories that
# happened to sit late in the queue. The backlog persists the unprocessed
# tail in dashboard_state so the next run picks it up first.
EXTRACTION_BACKLOG_KEY = 'extraction_backlog'
EXTRACTION_BACKLOG_CAP = int(os.environ.get('EXTRACTION_BACKLOG_CAP', '400'))
EXTRACTION_BACKLOG_MAX_ATTEMPTS = 3


def _item_priority(item) -> float:
    """Extraction priority: carryover first, then rerank relevance, then rest."""
    if item.get('_carryover'):
        return 100.0
    logit = item.get('_rerank_logit')
    return float(logit) if logit is not None else 0.0


def _item_lite(item) -> dict:
    """Slim, JSON-safe snapshot of an article for the persisted backlog."""
    return {
        'title': item.get('title', ''),
        'summary': (item.get('summary', '') or '')[:500],
        'url': item.get('url') or item.get('link') or '',
        'source_name': item.get('source_name', ''),
        'source_level': item.get('source_level', ''),
        'province': item.get('province', ''),
        'published': item.get('published', ''),
        '_rerank_logit': item.get('_rerank_logit'),
        'attempts': int(item.get('attempts', 0)),
    }


def merge_extraction_backlog(conn, items):
    """Prepend last run's unprocessed articles (deduped by URL, attempt-capped)."""
    try:
        from db import get_dashboard_state
        backlog = get_dashboard_state(conn, EXTRACTION_BACKLOG_KEY) or []
    except Exception:
        backlog = []
    if not backlog:
        return list(items)
    current_urls = {(i.get('url') or i.get('link') or '') for i in items}
    carried, expired = [], 0
    for b in backlog:
        u = b.get('url') or ''
        if not u or u in current_urls:
            continue
        b['attempts'] = int(b.get('attempts', 0)) + 1
        if b['attempts'] >= EXTRACTION_BACKLOG_MAX_ATTEMPTS:
            expired += 1
            continue
        b['_carryover'] = True
        carried.append(b)
    if carried or expired:
        print(f"  [BACKLOG] {len(carried)} unprocessed articles carried over from "
              f"previous run ({expired} expired after {EXTRACTION_BACKLOG_MAX_ATTEMPTS} attempts)")
    return carried + list(items)


def _flush_backlog(remaining_by_url: dict):
    """Persist the not-yet-extracted articles. Opens its own connection — runs
    from extraction worker context, possibly after the phase deadline."""
    try:
        from db import get_db, save_dashboard_state
        items = sorted(remaining_by_url.values(),
                       key=lambda b: (b.get('_rerank_logit') or 0.0), reverse=True)
        conn = get_db()
        try:
            save_dashboard_state(conn, EXTRACTION_BACKLOG_KEY,
                                 items[:EXTRACTION_BACKLOG_CAP])
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"  [BACKLOG] flush failed (non-fatal): {type(e).__name__}: {e}")


def extract_projects_from_rss(rss_items, anthropic_client=None, claude_model=None, cost_state=None):
    """
    Extract structured capital project data directly from RSS news items
    using Claude Sonnet — extracts directly from RSS text.

    Filters project-relevant items, groups by province, then calls
    _parse_projects_with_sonnet() on each group.  Returns a tuple of
    (flat project list, failed article list for Pro recovery).
    """
    # Items that already cleared the 6-layer remediated filter (stamped
    # '_l6_passed' in run()) skip the crude keyword cut — the L1/L2 bypasses
    # (government source, dollar value) exist precisely because keyword
    # matching misses them.
    pre_filtered = [i for i in rss_items if i.get('_l6_passed') or i.get('_carryover')]
    rest = [i for i in rss_items if not (i.get('_l6_passed') or i.get('_carryover'))]
    proj_items = pre_filtered + rss_monitor.filter_project_relevant(rest)
    if not proj_items:
        print("  [RSS PROJECTS] No project-relevant items found in RSS feeds.")
        return [], []

    # Highest-relevance first: a phase timeout must only ever cost us the
    # low-signal tail, never the week's marquee story.
    proj_items.sort(key=_item_priority, reverse=True)

    print(f"\n  [RSS PROJECTS] Extracting from {len(proj_items)} relevant RSS items...")

    # Group by province (federal items go under 'Canada')
    by_province: dict[str, list] = {}
    for item in proj_items:
        prov = item.get('province') or 'Canada'
        by_province.setdefault(prov, []).append(item)

    all_projects: list = []
    failed_articles: list = []
    # Canada (federal) often has far more items than any single province because it
    # collects every federal feed. A single large batch overflows the claude -p stdin
    # budget and exits 1 → API fallback → $0 balance error. Chunk any batch with
    # >BATCH_ITEM_CAP items into sub-batches. Applies to every province for safety,
    # but in practice only Canada hits the cap.
    BATCH_ITEM_CAP = 20

    def _process_chunk(province, chunk_idx, chunk_count, chunk):
        """Run one (province, chunk) extraction. Returns (projects, failed_items)."""
        text = rss_monitor.format_for_context(chunk, max_items=BATCH_ITEM_CAP)
        if not text.strip():
            return [], []
        label_suffix = f" [{chunk_idx+1}/{chunk_count}]" if chunk_count > 1 else ""
        projects = _parse_projects_with_sonnet(
            f"Government news releases from {province}{label_suffix}:\n\n{text}",
            province if province != 'Canada' else 'Canada',
            f"RSS/{province[:15]}{label_suffix}",
            anthropic_client=anthropic_client,
            claude_model=claude_model,
            cost_state=cost_state,
        )
        if projects:
            rss_urls = [{"url": i.get('url') or i.get('link') or '',
                         "name": i.get('source_name', ''),
                         "date": (i.get('published') or '')[:10],
                         "source_type": "rss_government" if i.get('source_level') != 'media' else "rss_news"}
                        for i in chunk if (i.get('url') or i.get('link'))]
            for p in projects:
                p.setdefault('_evidence', [])
                existing = {e.get('url') for e in p['_evidence']}
                for ru in rss_urls:
                    if ru['url'] not in existing:
                        p['_evidence'].append(ru)
                        existing.add(ru['url'])
                if not p.get('source_url') and rss_urls:
                    p['source_url'] = rss_urls[0]['url']
            return projects, []
        # Sonnet found no projects — collect articles for Pro recovery
        failed = [{
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("url") or item.get("link", ""),
            "source_name": item.get("source_name", ""),
            "province": province,
        } for item in chunk]
        return [], failed

    # Build the full work list across all provinces, then run in parallel.
    # Provinces with one chunk are still fine — they just run alongside others.
    work = []
    chunk_counts = {}
    for province, items in sorted(by_province.items()):
        chunks = [items[i:i + BATCH_ITEM_CAP] for i in range(0, len(items), BATCH_ITEM_CAP)] or [[]]
        chunks = [c for c in chunks if c]
        chunk_counts[province] = len(chunks)
        for chunk_idx, chunk in enumerate(chunks):
            work.append((province, chunk_idx, len(chunks), chunk))

    # Dispatch highest-priority chunks first — worker submission order is the
    # processing order, so a phase timeout drops only the low-relevance tail.
    work.sort(key=lambda w: max((_item_priority(i) for i in w[3]), default=0.0),
              reverse=True)

    # Persist the full queue up front, then peel off completed chunks. If the
    # phase deadline abandons this thread mid-flight, whatever wasn't flushed
    # as done is still in dashboard_state for the next run to carry over.
    remaining_by_url = {}
    for _, _, _, chunk in work:
        for it in chunk:
            u = it.get('url') or it.get('link') or ''
            if u:
                remaining_by_url[u] = _item_lite(it)
    _flush_backlog(remaining_by_url)

    province_projects: dict[str, list] = {p: [] for p in by_province}
    if work:
        completed_since_flush = 0
        with ThreadPoolExecutor(max_workers=RSS_EXTRACT_WORKERS) as ex:
            futs = {ex.submit(_process_chunk, *w): w for w in work}
            for fut in as_completed(futs):
                province = futs[fut][0]
                chunk = futs[fut][3]
                try:
                    projects, failed = fut.result()
                except Exception as e:
                    # Chunk raised (subprocess crash, etc.) — leave its articles
                    # in remaining_by_url so the backlog carries them to the
                    # next run instead of silently dropping them (audit C2).
                    print(f"    [RSS PROJECTS] {province} chunk failed: {type(e).__name__}: {e} "
                          f"— {len(chunk)} articles kept in backlog")
                    completed_since_flush += 1
                    if completed_since_flush >= 5:
                        _flush_backlog(remaining_by_url)
                        completed_since_flush = 0
                    continue
                # Only a chunk that actually returned is removed from the backlog.
                for it in chunk:
                    remaining_by_url.pop(it.get('url') or it.get('link') or '', None)
                completed_since_flush += 1
                if completed_since_flush >= 5:
                    _flush_backlog(remaining_by_url)
                    completed_since_flush = 0
                province_projects[province].extend(projects)
                failed_articles.extend(failed)
        _flush_backlog(remaining_by_url)

    for province, projs in province_projects.items():
        if projs:
            cnt = chunk_counts.get(province, 0)
            print(f"    {province}: {len(projs)} projects from RSS ({cnt} chunk{'s' if cnt != 1 else ''})")
        all_projects.extend(projs)

    print(f"  [RSS PROJECTS] {len(all_projects)} extracted, "
          f"{len(failed_articles)} articles queued for Pro recovery")
    return all_projects, failed_articles


def _normalize_extracted_project(p):
    """Convert a Call 4 project extract to the flat project format."""
    name = p.get('project_name') or p.get('name') or ''
    if not name or len(name) < 5:
        return None
    src = p.get('source') or {}
    return {
        'name':             name,
        'province':         p.get('province', ''),
        'cma':              p.get('cma', ''),
        'sector':           p.get('sector', 'Other'),
        'naics_code':       p.get('naics_code', ''),
        'tags':             p.get('tags', []),
        'value':            p.get('estimated_value', ''),
        'status':           p.get('status', 'Announced'),
        'description':      p.get('detail', '')[:200],
        'discovery_source': 'news_extraction',
        'sources': [{'id': 1, 'title': src.get('title', ''),
                     'url': src.get('url', ''), 'date': src.get('date', '')}],
        'announced':        src.get('date') or date.today().isoformat(),
        'completionDate':   '',
    }


# ── Main phase entry point ───────────────────────────────────────────────────

def run(conn, context, logger):
    """Run RSS filtering, project extraction, dedup, and URL hard gate."""
    step_name = "Phase 3: Filtering"
    try:
        gemini_client = context.get("gemini_client")
        anthropic_client = context.get("anthropic_client")
        deep_sweep = context.get("mode") == "deep-sweep"
        days_back = 30 if deep_sweep else 7
        rss_items = context.get("rss_items", [])

        # Get Claude cost tracking state
        cost_state = context.get("claude_cost", {
            "usd": 0.0, "input": 0, "output": 0, "cap": 1.0,
            "input_cost_per_mtok": 3.0, "output_cost_per_mtok": 15.0,
        })
        claude_model = SONNET_MODEL

        # Get discovery results from Phase 2 (keys set directly in context)
        registry_projects = context.get("registry_projects", [])
        municipal_projects = context.get("municipal_projects", [])
        institutional_projects = context.get("institutional_projects", [])
        gemini_projects = context.get("gemini_projects", [])

        # ── Pre-step: Metadata tagging (zero API cost) ────────────────
        try:
            from metadata_tagger import tag_batch
            if rss_items:
                rss_items = tag_batch(rss_items)
        except ImportError:
            print("[WARN] metadata_tagger not available, skipping metadata tagging")
        except Exception as e:
            print(f"[WARN] Metadata tagging failed, continuing without tags: {e}")

        # ── TIER 3: Article extraction from RSS ─────────────────────
        # Compound queries + RSS cover all news discovery.
        # Tavily extracts full text from RSS article URLs.
        extracted_articles = []

        # ── TIER 4: RSS feeds (filtered) ───────────────────────────
        # Reuse Phase 1 RSS items instead of re-fetching from all feeds
        rss_filtered = rss_monitor.fetch_and_filter(
            days_back=days_back,
            include_media=True,
            gemini_client=gemini_client,
            prefetched_items=rss_items if rss_items else None,
            conn=conn,  # E-7: enables page-text + embedding caches
        )

        # The remediated 6-layer set (gov bypass + dollar bypass + L6 LLM
        # classification + L7 rerank) IS the extraction queue. It used to be
        # computed and then dropped on the floor while extraction re-cut the
        # raw items with a crude keyword filter — missing every article that
        # only survived via a bypass, and ignoring the rerank relevance
        # signal entirely. Stamp items so extract_projects_from_rss() trusts
        # them, and prepend last run's unprocessed backlog.
        if rss_filtered:
            for _it in rss_filtered:
                _it['_l6_passed'] = True
            extraction_items = rss_filtered
        else:
            extraction_items = rss_items
        extraction_items = merge_extraction_backlog(conn, extraction_items)

        # ── POST-EXTRACTION: Deduplicate & upsert all discovered projects ──
        print("\n[POST-EXTRACTION] Collecting all discovered projects...")

        # Collect ALL flat projects from every tier for cross-tier deduplication
        all_flat_projects = []

        # Tier 2: Gemini compound discovery projects
        if gemini_projects:
            for gp in gemini_projects:
                ptype = normalize_project_type(gp.get('project_type', ''))
                all_flat_projects.append({
                    'name':              gp.get('name', ''),
                    'province':          gp.get('province', ''),
                    'cma':               gp.get('cma', ''),
                    'sector':            gp.get('naics_2digit', 'Other'),
                    'naics_code':        gp.get('naics_2digit', ''),
                    'tags':              [],
                    'value':             gp.get('value', 'Not disclosed'),
                    'value_millions':    gp.get('value_numeric'),
                    'status':            gp.get('status', 'Proposed'),
                    'description':       gp.get('description', ''),
                    'discovery_source':  gp.get('discovery_source', 'gemini_compound'),
                    'source_url':        gp.get('source_url', ''),
                    'source_title':      gp.get('source_title', ''),
                    'sources': [{'id': 1, 'title': gp.get('source_title', ''),
                                 'url': gp.get('source_url', '')}],
                    'announced':         date.today().isoformat(),
                    'completionDate':    '',
                    'project_type':      ptype,
                    'is_brownfield':     is_brownfield(ptype),
                    '_source_query_sector': gp.get('_section', ''),
                })

        # Tier 4: RSS project extraction (remediated filter output + backlog,
        # highest rerank relevance first)
        rss_projects, rss_failed_articles = extract_projects_from_rss(
            extraction_items,
            anthropic_client=anthropic_client,
            claude_model=claude_model,
            cost_state=cost_state,
        )
        if rss_projects:
            for rp in rss_projects:
                rp.setdefault('discovery_source', 'rss_remediated')
            all_flat_projects.extend(rss_projects)

        # Tier 1: Registry projects
        if registry_projects:
            for p in registry_projects:
                all_flat_projects.append({
                    'name':              p.get('name', ''),
                    'province':          p.get('province', ''),
                    'cma':               '',
                    'sector':            p.get('sector', 'Other'),
                    'naics_code':        '',
                    'tags':              [],
                    'value':             p.get('value', ''),
                    'status':            p.get('status', 'Announced'),
                    'description':       p.get('name', ''),
                    'discovery_source':  p.get('discovery_source', 'federal_registry'),
                    'source_url':        p.get('source_url', ''),
                    'sources': [{'id': 1, 'title': p.get('discovery_source', ''),
                                 'url': p.get('source_url', '')}],
                    'announced':         date.today().isoformat(),
                    'completionDate':    '',
                })

        # Tier 13: Municipal development application projects
        if municipal_projects:
            for p in municipal_projects:
                p.setdefault('discovery_source', 'municipal_dev_app')
            all_flat_projects.extend(municipal_projects)

        # Tier 14: Institutional capital plan projects
        if institutional_projects:
            for p in institutional_projects:
                p.setdefault('discovery_source', 'institutional_capital')
            all_flat_projects.extend(institutional_projects)

        # ── Rehash filter (Gemini Flash, free) ────────────────────────
        try:
            from gemini_engine import filter_rehashes_sync
            existing = get_all_projects(conn)
            if rss_items and existing:
                pre_count = len(rss_items)
                rss_items = filter_rehashes_sync(rss_items, existing)
                if pre_count != len(rss_items):
                    print(f"  [REHASH] RSS items: {pre_count} -> {len(rss_items)}")
        except Exception as e:
            print(f"  [REHASH] Filter failed (non-critical): {type(e).__name__}: {e}")

        # ── Selective Claude extraction (top high-signal documents) ───
        try:
            from claude_reasoning import selective_extraction_sync
            # Collect all articles that were classified as relevant this run
            selective_docs = list(rss_items) if rss_items else []
            if extracted_articles:
                selective_docs.extend(extracted_articles)
            if selective_docs:
                print("\n[POST-EXTRACTION] Selective Claude extraction (high-signal docs)...")
                selective_projects = selective_extraction_sync(selective_docs)
                if selective_projects:
                    all_flat_projects.extend(selective_projects)
                    print(f"  [SELECTIVE] {len(selective_projects)} projects from selective extraction")
        except Exception as e:
            print(f"  [SELECTIVE] Extraction failed (non-critical): {type(e).__name__}: {e}")

        # ── Cross-tier deduplication ──────────────────────────────────
        verified = []
        if all_flat_projects:
            raw_count = len(all_flat_projects)
            deduped = deduplicate_projects(all_flat_projects)
            dup_count = raw_count - len(deduped)
            # STEP_2F: Hard gate -- reject projects without verifiable source URLs
            verified = [p for p in deduped if p.get("evidence") and len(p["evidence"]) > 0]
            rejected_list = [p for p in deduped if not p.get("evidence") or len(p["evidence"]) == 0]
            rejected = len(rejected_list)
            print(f"\n[DEDUP] {raw_count} raw mentions -> {len(deduped)} unique "
                  f"({dup_count} cross-tier duplicates merged)")
            if rejected:
                print(f"  [URL GATE] {rejected} projects rejected (no verifiable source URL)")
                # Debug: show first 5 rejected with their source info
                for rp in rejected_list[:5]:
                    src = rp.get('discovery_source', '?')
                    name = rp.get('name', '?')[:50]
                    has_ev = bool(rp.get('_evidence'))
                    has_su = bool(rp.get('source_url'))
                    print(f"    REJECTED: [{src}] {name} | _evidence={has_ev} source_url={has_su}")
            sync_result = upsert_flat_projects(conn, verified)
            if sync_result:
                logger.log_metric("discovery", "projects_added", sync_result.get("new", 0))
                logger.log_metric("discovery", "projects_updated", sync_result.get("updated", 0))
                logger.log_metric("discovery", "fuzzy_merges", sync_result.get("fuzzy_merged", 0))
                # Register newly discovered projects for alert tracking
                try:
                    from project_alert_tracker import register_batch
                    new_norm_keys = sync_result.get("new_keys", [])
                    if new_norm_keys:
                        registered = register_batch(conn, new_norm_keys)
                        if registered:
                            print(f"  [ALERTS] {registered} new projects registered for alert tracking")
                except Exception as e:
                    print(f"  [ALERTS] Registration failed (non-critical): {e}")
            logger.log_metric("discovery", "articles_found", raw_count)
            logger.log_metric("discovery", "projects_deduped", dup_count)
        else:
            print("\n[DEDUP] No flat projects to upsert")
        logger.log_step("post_extraction_dedup")

        logger.log_step(step_name, "success")

        return {
            "rss_projects": rss_projects,
            "rss_failed_articles": rss_failed_articles,
            "all_flat_projects": all_flat_projects,
            "verified_projects": verified,
            "extracted_articles": extracted_articles,
        }
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
