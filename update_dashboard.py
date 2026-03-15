"""
update_dashboard.py — CAN-MACRO Strategic Dashboard Pipeline (Orchestrator)

Thin orchestrator that runs 9 phases in sequence:
  1. Data Collection  — Hard data from APIs (BoC, StatCan, FRED, ECB, BoE, Yahoo)
  2. Discovery        — Tiers 1-14 project discovery
  3. Filtering        — RSS filter, project extraction, dedup, URL hard gate
  4. Signals          — Permits, lobbyists (runs BEFORE analysis)
  5. Analysis         — Claude Sonnet 4-call pipeline + hard data override
  6. Reasoning        — Gap analysis, dedup QA, extraction recovery, meta-analysis
  7. Narrative        — Trends, market commentary, microscope, briefing
  8. Verification     — Source URL checks, Wayback, cost-finding, enrichment, stale
  9. Finalize         — Timeseries, assembly, quality report, export, deploy

Flags:
  python update_dashboard.py               — normal weekly run
  python update_dashboard.py --deep-sweep  — monthly full sweep
  python update_dashboard.py --indicators-only — daily hard-data refresh only
  python update_dashboard.py --test-feeds  — test all RSS feed URLs
  python update_dashboard.py --seed-projects — full project seed
  python update_dashboard.py --audit-citations — link rot audit
  python update_dashboard.py --test-sentiment — sentiment test
  python update_dashboard.py --known-sweep — one-time project sweep
  python update_dashboard.py --audit-archetypes — archetype pattern scan
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

import json
import os
import anthropic
from google import genai
from datetime import date
from dotenv import load_dotenv

from db import init_db, save_dashboard_state, get_all_projects
from pipeline_logging import PipelineRunLogger
from pipeline_config import CLAUDE_COST_CAP_USD
from tools.export_dashboard import export_all
import rss_monitor
import service_health

from phases import (
    data_collection,
    discovery,
    filtering,
    signals,
    analysis,
    reasoning,
    narrative,
    verification,
    finalize,
)

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & AUTH
# ══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set in .env")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in .env")
if not TAVILY_API_KEY:
    print("[WARN] TAVILY_API_KEY not set — article extraction will be skipped")

# API clients
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

tavily_client = None
try:
    from tavily import TavilyClient as _TavilyClient
    if TAVILY_API_KEY:
        tavily_client = _TavilyClient(api_key=TAVILY_API_KEY)
except ImportError:
    print("[WARN] tavily-python not installed — Tavily Extract will be skipped")

# SQLite
try:
    conn = init_db()
except Exception as e:
    print(f"[FATAL] Database initialization failed: {e}")
    import sys
    sys.exit(1)

# Tavily credit tracking
from tavily_search import set_tracking_db, can_use_tavily
set_tracking_db(conn)

# Watchlist for official context injection
_WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), 'config', 'watchlist.json')
_WATCHLIST = {}
if os.path.exists(_WATCHLIST_PATH):
    try:
        with open(_WATCHLIST_PATH, 'r', encoding='utf-8') as _wf:
            _WATCHLIST = json.load(_wf)
    except Exception as e:
        print(f"[WARN] Failed to load watchlist: {e}")
        _WATCHLIST = {}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def update_dashboard(deep_sweep: bool = False):
    """Run the full 9-phase pipeline."""
    run_type = "deep_sweep" if deep_sweep else "weekly"
    health = service_health.init()
    run_log = PipelineRunLogger(conn=conn, run_type=run_type)
    run_log.start()

    # Shared context dict — replaces local variable passing
    context = {
        "anthropic_client": anthropic_client,
        "gemini_client": gemini_client,
        "tavily_client": tavily_client,
        "watchlist": _WATCHLIST,
        "mode": "deep-sweep" if deep_sweep else "weekly",
        "claude_cost": {
            "usd": 0.0,
            "input": 0,
            "output": 0,
            "cap": CLAUDE_COST_CAP_USD,
            "input_cost_per_mtok": 3.0,
            "output_cost_per_mtok": 15.0,
        },
    }

    # Phase pipeline — order matters
    phases = [
        ("Phase 1: Data Collection", data_collection),
        ("Phase 2: Discovery",       discovery),
        ("Phase 3: Filtering",       filtering),
        ("Phase 4: Signals",         signals),
        ("Phase 5: Analysis",        analysis),
        ("Phase 6: Reasoning",       reasoning),
        ("Phase 7: Narrative",       narrative),
        ("Phase 8: Verification",    verification),
        ("Phase 9: Finalize",        finalize),
    ]

    # Per-phase timeout limits (seconds). Generous defaults.
    PHASE_TIMEOUTS = {
        "Phase 1: Data Collection": 600,
        "Phase 2: Discovery": 300,
        "Phase 3: Filtering": 120,
        "Phase 4: Signals": 180,
        "Phase 5: Analysis": 300,
        "Phase 6: Reasoning": 120,
        "Phase 7: Narrative": 120,
        "Phase 8: Verification": 120,
        "Phase 9: Finalize": 120,
    }

    # Phase-level caching: check for run_id-based cache key
    run_date = date.today().isoformat()
    cache_prefix = f"phase_cache_{run_date}"

    for phase_name, phase_module in phases:
        print(f"\n{'='*60}")
        print(f"  {phase_name}")
        print(f"{'='*60}")

        # Check phase cache for crash recovery
        cache_key = f"{cache_prefix}_{phase_name.replace(' ', '_')}"
        try:
            from db import get_dashboard_state
            cached = get_dashboard_state(conn, cache_key)
            if cached and isinstance(cached, dict) and cached.get("_completed"):
                print(f"  [CACHE HIT] Skipping — completed earlier today")
                context.update({k: v for k, v in cached.items() if not k.startswith("_")})
                continue
        except Exception:
            pass

        timeout = PHASE_TIMEOUTS.get(phase_name, 300)
        try:
            import signal as _signal
            import threading

            # Use threading timeout (cross-platform)
            result_container = [None]
            error_container = [None]

            def _run_phase():
                try:
                    result_container[0] = phase_module.run(conn, context, run_log)
                except Exception as e:
                    error_container[0] = e

            t = threading.Thread(target=_run_phase)
            t.start()
            t.join(timeout=timeout)

            if t.is_alive():
                print(f"\n[TIMEOUT] {phase_name} exceeded {timeout}s — continuing with partial results")
                run_log.log_error(phase_name, Exception(f"Timeout after {timeout}s"), recovered=True)
            elif error_container[0]:
                raise error_container[0]
            else:
                result = result_container[0]
                # Merge phase outputs into shared context
                if result:
                    context.update(result)
                    # Cache phase results for crash recovery
                    try:
                        from db import save_dashboard_state
                        cache_data = {k: v for k, v in result.items()
                                      if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
                        cache_data["_completed"] = True
                        save_dashboard_state(conn, cache_key, cache_data)
                    except Exception:
                        pass  # caching is best-effort

        except Exception as e:
            import traceback
            print(f"\n[CRITICAL] {phase_name} failed: {e}")
            traceback.print_exc()
            run_log.log_error(phase_name, e, recovered=False)
            # Analysis failure is critical — skip remaining phases
            if phase_module is analysis:
                run_log.finalize("error")
                return

    # ── Service health summary ─────────────────────────────────────
    health_status = health.get_status()
    if health_status["dead"]:
        print(f"\n[SERVICE HEALTH] Dead services: {health_status['dead']}")
    run_log.log_metric("api_usage", "service_health", health_status)

    # ── Finalize pipeline run log ─────────────────────────────────
    final_payload = context.get("final_payload", {})
    if final_payload.get('_analysis_incomplete'):
        run_log.finalize("partial")
    else:
        run_log.finalize("success")


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE CLI MODES
# ══════════════════════════════════════════════════════════════════════════════

def seed_projects(deep_sweep: bool = False) -> None:
    """--seed-projects: Full project seed from all sources."""
    from project_sync import upsert_flat_projects
    from google_news_rss_search import run_google_news_search
    from gov_sources import fetch_registry_projects

    print("\n[SEED PROJECTS] Running full project seed...")

    # Tier 1: Government registries
    registry_projects = fetch_registry_projects(tavily_client=tavily_client)
    if registry_projects:
        flat = []
        for p in registry_projects:
            flat.append({
                'name':             p.get('name', ''),
                'province':         p.get('province', ''),
                'cma':              p.get('cma', ''),
                'sector':           p.get('sector', 'Other'),
                'value':            p.get('value', ''),
                'status':           p.get('status', 'Announced'),
                'description':      p.get('name', ''),
                'discovery_source': p.get('discovery_source', 'federal_registry'),
                'sources': [{'id': 1, 'title': p.get('discovery_source', ''),
                             'url': p.get('source_url', '')}],
                'announced':        date.today().isoformat(),
                'naics_code':       '',
                'tags':             [],
                'completionDate':   '',
            })
        upsert_flat_projects(conn, flat)

    # Tier 2: Google News RSS discovery
    print("\n  [Seed] Google News RSS discovery...")
    try:
        seed_articles = run_google_news_search(gemini_client=gemini_client)
        if seed_articles:
            print(f"  [Seed] {len(seed_articles)} articles from Google News RSS")
    except Exception as e:
        print(f"  [Seed] Google News discovery failed: {e}")

    # Tier 13: Municipal development applications
    try:
        from municipal_dev_apps import scrape_municipal_applications_sync
        print("\n  [Seed] Municipal development applications...")
        muni = scrape_municipal_applications_sync()
        if muni:
            upsert_flat_projects(conn, muni)
    except Exception as e:
        print(f"  [Seed] Municipal scrape failed: {e}")

    # Tier 14: Institutional capital plans
    try:
        from institutional_capital import scrape_institutional_capital
        print("\n  [Seed] Institutional capital plans...")
        inst = scrape_institutional_capital()
        if inst:
            upsert_flat_projects(conn, inst)
    except Exception as e:
        print(f"  [Seed] Institutional scrape failed: {e}")

    # Wayback history backfill
    from tools.wayback import backfill_project_history as _bfill
    print("\n  [Seed] Wayback history backfill...")
    try:
        rows = conn.execute(
            "SELECT norm_key, name, province, statusHistory FROM projects "
            "WHERE (history_backfilled IS NULL OR history_backfilled = 0)"
        ).fetchall()
        bf_count = 0
        for row in rows:
            p = dict(row)
            name = p.get('name', '')
            sh = p.get('statusHistory', '[]')
            if isinstance(sh, str):
                try:
                    sh = json.loads(sh)
                except Exception:
                    sh = []
            source_url = ''
            for entry in (sh or []):
                src = entry.get('source', {})
                if src.get('url'):
                    source_url = src['url']
                    break
            if not source_url or not name:
                continue
            result = _bfill(
                project_name=name,
                source_url=source_url,
                province=p.get('province', ''),
            )
            if result.get('history_backfilled') and result.get('statusHistory'):
                full_history = result['statusHistory'] + (sh or [])
                with conn:
                    conn.execute(
                        "UPDATE projects SET history_backfilled = 1, "
                        "history_earliest_date = ?, statusHistory = ? WHERE norm_key = ?",
                        (result.get('history_earliest_date', ''),
                         json.dumps(full_history, ensure_ascii=False),
                         p['norm_key'])
                    )
                bf_count += 1
        if bf_count:
            print(f"  [Seed] {bf_count} projects backfilled")
    except Exception as e:
        print(f"  [Seed] Backfill error: {e}")


def audit_all_citations():
    """--audit-citations: Link rot audit — re-verify ALL URLs in DB."""
    from tools.url_verify import verify_url as _vurl, quick_reject as _qr
    from tools.wayback import save_page as _wsave
    from db import get_dashboard_state

    print(f"\n{'='*70}")
    print(f"  --audit-citations: Link Rot Audit")
    print(f"{'='*70}\n")

    total = 0
    passed = 0
    dead_archived = 0
    dead_unarchived = 0
    failures = []

    print("  Checking projects table...")
    for doc in get_all_projects(conn):
        name = doc.get('name', '(unnamed)')
        for entry in (doc.get('statusHistory') or []):
            src = entry.get('source', {})
            url = src.get('url', '')
            if not url:
                continue
            total += 1
            if _qr(url):
                continue
            result = _vurl(url, name)
            if result.get('accepted'):
                passed += 1
            else:
                archive_url = src.get('archive_url', '')
                if archive_url:
                    entry['link_status'] = 'link_rotted_archived'
                    dead_archived += 1
                else:
                    saved = _wsave(url)
                    if saved:
                        entry['link_status'] = 'link_rotted_archived'
                        entry.setdefault('source', {})['archive_url'] = saved
                        dead_archived += 1
                    else:
                        entry['link_status'] = 'link_rotted_unarchived'
                        dead_unarchived += 1
                failures.append({
                    'name': name,
                    'url': url,
                    'reason': result.get('reason', 'dead'),
                    'has_archive': bool(archive_url or (saved if 'saved' in dir() else False)),
                })

    print("  Checking newsletter_latest citations...")
    latest = get_dashboard_state(conn, 'newsletter_latest')
    if latest:
        for section_key in ('national', 'global', 'provinces', 'goodsIndustries', 'servicesIndustries'):
            _audit_section_urls(latest, section_key, failures, _vurl, _qr)

    print(f"\n  Total URLs checked: {total}")
    print(f"  Passed:             {passed}")
    print(f"  Dead (archived):    {dead_archived}")
    print(f"  Dead (unarchived):  {dead_unarchived}")

    if failures:
        audit_file = f'link_audit_{date.today().isoformat()}.txt'
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write(f"Link Rot Audit — {date.today().isoformat()}\n{'='*60}\n\n")
            for fl in failures:
                archive_note = ' (has archive)' if fl.get('has_archive') else ' (NO archive)'
                f.write(f"Project: {fl['name']}\n  URL: {fl['url']}\n  "
                        f"Reason: {fl['reason']}{archive_note}\n\n")
            f.write(f"\nSummary: {passed} OK, {dead_archived} dead+archived, "
                    f"{dead_unarchived} dead+unarchived out of {total}\n")
        print(f"  Report saved to {audit_file}")


def _audit_section_urls(payload, section_key, failures, _vurl, _qr):
    """Helper: check source URLs in a payload section."""
    data = payload.get(section_key)
    if not data:
        return
    items = data if isinstance(data, list) else [data]
    for item in items:
        for src in (item.get('sources') or []) + (item.get('industrySources') or []):
            url = src.get('url', '')
            if url and not _qr(url):
                result = _vurl(url, src.get('title', ''))
                if not result.get('accepted'):
                    failures.append({
                        'name': section_key,
                        'url': url,
                        'reason': result.get('reason', 'dead'),
                        'has_archive': False,
                    })


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CAN-MACRO Dashboard Pipeline")
    parser.add_argument(
        '--deep-sweep', action='store_true',
        help='Monthly deep NAICS sweep (20 sectors x 13 provinces via Gemini compound queries)'
    )
    parser.add_argument(
        '--test-feeds', action='store_true',
        help='Test all government RSS feed URLs and report which are live/dead.'
    )
    parser.add_argument(
        '--seed-projects', action='store_true',
        help='Full project seed from all sources: registries + Google News RSS.'
    )
    parser.add_argument(
        '--audit-citations', action='store_true',
        help='Re-verify ALL URLs in DB + newsletter. Flag dead links, attempt Wayback archive.'
    )
    parser.add_argument(
        '--test-sentiment', action='store_true',
        help='Run sentiment collection only (Reddit, Trends, CBC), print results.'
    )
    parser.add_argument(
        '--indicators-only', action='store_true',
        help='Daily mode: fetch hard indicators only (BoC, StatCan, FRED, etc.), skip AI.'
    )
    parser.add_argument(
        '--known-sweep', action='store_true',
        help='One-time comprehensive sweep for ALL active Canadian projects.'
    )
    parser.add_argument(
        '--audit-archetypes', action='store_true',
        help='Scan rejected articles for emerging archetype patterns.'
    )
    args = parser.parse_args()

    if args.test_sentiment:
        from sentiment import collect_sentiment
        print("Running sentiment collection (test mode)...")
        result = collect_sentiment()
        if result:
            idx = result.get('sentiment_index', 'N/A')
            topics = result.get('topics', [])
            print(f"\nSentiment index: {idx}")
            print(f"Topics collected: {len(topics)}")
            for t in topics[:10]:
                print(f"  - {t.get('topic', '?')}: {t.get('sentiment', '?')} ({t.get('source', '?')})")
            if len(topics) > 10:
                print(f"  ... and {len(topics) - 10} more")
        else:
            print("No sentiment data collected.")
    elif args.test_feeds:
        rss_monitor.test_feeds()
    elif args.seed_projects:
        seed_projects(deep_sweep=args.deep_sweep)
    elif args.audit_citations:
        audit_all_citations()
    elif args.known_sweep:
        print("\n[KNOWN-SWEEP] Running comprehensive project sweep...")
        from known_project_sweep import seed_known_projects, run_known_project_sweep_sync
        seed_known_projects(conn)
        result = run_known_project_sweep_sync(conn)
        print(f"\n[KNOWN-SWEEP] Complete: {result}")
    elif args.audit_archetypes:
        from archetype_audit import run_archetype_audit
        run_archetype_audit(conn=conn, days=30)
    elif args.indicators_only:
        daily_log = PipelineRunLogger(conn=conn, run_type="daily_indicators")
        daily_log.start()
        print("\n[DAILY MODE] Fetching hard indicators only...")
        try:
            from phases.data_collection import fetch_primary_indicators
            indicators = fetch_primary_indicators()
            daily_log.log_step("fetch_indicators")
            if indicators:
                dated_id = date.today().strftime("%Y-%m-%d")
                save_dashboard_state(conn, f'timeseries_{dated_id}', indicators)
                print(f"[OK] Indicators stored to dashboard_state/timeseries_{dated_id}")
                daily_log.log_step("store_indicators")
            else:
                print("[WARN] No indicators fetched or no DB connection")

            print("\n[DAILY MODE] Exporting static JSON files...")
            try:
                export_result = export_all(conn=conn)
                print(f"[OK] Exported {export_result['file_count']} files to {export_result['output_dir']}")
                daily_log.log_step("step_9_json_export")
            except Exception as e:
                print(f"[WARN] Static JSON export failed (non-fatal): {e}")
                import traceback
                traceback.print_exc()
                daily_log.log_error("json_export", e, recovered=True)

            if indicators:
                daily_log.finalize("success")
            else:
                daily_log.finalize("partial")
        except Exception as e:
            print(f"[ERROR] Daily indicators failed: {e}")
            daily_log.log_error("daily_indicators", e, recovered=False)
            daily_log.finalize("error")
    else:
        update_dashboard(deep_sweep=args.deep_sweep)
