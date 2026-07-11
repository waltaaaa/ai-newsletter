"""
update_dashboard.py — CAN-MACRO Strategic Dashboard Pipeline (Orchestrator)

Thin orchestrator that runs 6 phases in sequence:
  1. Data Collection    — Hard data from APIs (BoC, StatCan, FRED, ECB, BoE, Yahoo)
  2. Discovery          — Tiers 1-14 project discovery
  3. Filtering          — RSS filter, project extraction, dedup, URL hard gate
  4. Signals            — Permits, lobbyists (runs BEFORE analysis)
  5. Conductor          — Dispatches subagent pipeline via tldr-conductor skill:
                          data enrichment, research (3 agents), analysis (3 agents),
                          writing (4 agents), assembly, charts, audit, fix
  6. Finalize           — Timeseries, assembly, quality report, export, deploy

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
    conductor,
    finalize,
)

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & AUTH
# ══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

# Anthropic API key is only required when any agent runs in 'api' mode.
# Default mode is 'claude_code' (subscription via `claude -p` CLI), which costs $0.
_api_mode_active = any(
    os.environ.get(var, "").strip().lower() == "api"
    for var in ("REASONING_AGENT_MODE", "WRITING_AGENT_MODE", "PROVINCE_AGENT_MODE")
)
if _api_mode_active and not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY required when REASONING/WRITING/PROVINCE_AGENT_MODE=api. "
        "Either set the key or switch the mode to 'claude_code' (default)."
    )
if not TAVILY_API_KEY:
    print("[WARN] TAVILY_API_KEY not set — article extraction will be skipped")

# API clients — only instantiate Anthropic client if a key is present.
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

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

# Idempotent dedup of weekly_briefings on startup — guards against future
# INSERT-without-upsert drift and cleans any pre-existing duplicates.
try:
    from db import cleanup_duplicate_briefings
    _removed = cleanup_duplicate_briefings(conn)
    if _removed:
        print(f"[DB] Removed {_removed} duplicate weekly_briefings row(s) on startup")
except Exception as _e:
    print(f"[WARN] weekly_briefings dedup skipped: {_e}")

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

def _rotate_weekly_db_backups(keep: int = 4):
    """Audit M5: enforce the weekly-task backup-rotation rule in code.

    The weekly scheduled task creates dashboard.db.pre-weekly-* before each
    run; the SKILL.md rule says keep the 4 most recent, but it was never
    automated and copies accumulated (~110MB each). Only pre-weekly-*
    backups are rotated — operator-created repair/dedup backups are not
    touched.
    """
    import glob as _glob
    here = os.path.dirname(os.path.abspath(__file__))
    # Red-team F7: sort by FILENAME (the date is in the name), not mtime —
    # PowerShell Copy-Item preserves the source LastWriteTime, so after a
    # restore-from-older-backup the newest copy can sort oldest and be deleted.
    backups = sorted(_glob.glob(os.path.join(here, "dashboard.db.pre-weekly-*")),
                     reverse=True)
    for old in backups[keep:]:
        try:
            os.unlink(old)
            print(f"  [BACKUP ROTATE] removed {os.path.basename(old)}")
        except OSError as e:
            print(f"  [BACKUP ROTATE] could not remove {os.path.basename(old)}: {e}")


def update_dashboard(deep_sweep: bool = False):
    """Run the full 6-phase pipeline."""
    run_type = "deep_sweep" if deep_sweep else "weekly"
    health = service_health.init()
    run_log = PipelineRunLogger(conn=conn, run_type=run_type)
    run_log.start()
    _rotate_weekly_db_backups()

    # Shared context dict — replaces local variable passing
    context = {
        "anthropic_client": anthropic_client,
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
    # Layers: Sweep (1-4) → Conductor (5) → Finalize (6)
    phases = [
        ("Phase 1: Data Collection",   data_collection),
        ("Phase 2: Discovery",         discovery),
        ("Phase 3: Filtering",         filtering),
        ("Phase 4: Signals",           signals),
        ("Phase 5: Conductor",         conductor),
        ("Phase 6: Finalize",          finalize),
    ]

    # Per-phase timeout limits (seconds). Generous defaults.
    PHASE_TIMEOUTS = {
        "Phase 1: Data Collection": 600,
        "Phase 2: Discovery": 1200,
        # Audit C2 (2026-06-11): 2400s was below the measured extraction need
        # (60 chunks x 180-300s / 6 workers ~= 1800-2500s before L6/L7/dedup
        # overhead) — the 2026-06-08 run timed out with 331 articles unprocessed.
        "Phase 3: Filtering": 4200,
        "Phase 4: Signals": 600,
        # Red-team F2: the phase join must exceed CONDUCTOR_TIMEOUT (7200s
        # subprocess budget) PLUS the pre-steps (trends, export,
        # ~10-20 min) — when join == subprocess timeout, a full-budget
        # conductor is abandoned mid-flight and its claude child runs on as
        # an orphan racing the deploy.
        "Phase 5: Conductor": 9000,
        # Red-team F9: finalize internally runs the fuzzy-dedup report with a
        # 600s subprocess timeout — a 300s phase join abandoned the phase
        # while its own subprocess kept running.
        "Phase 6: Finalize": 900,
    }

    # Phase-level caching (E-2): stable per-phase keys + TTL freshness check.
    # The key no longer embeds the run date — a next-day retry reuses any
    # phase completed within PHASE_CACHE_TTL_HOURS (default 24h).
    from pipeline_cache import phase_cache_key, phase_cache_fresh, phase_cache_ttl_hours
    _phase_ttl_hours = phase_cache_ttl_hours()

    import time as _time

    for phase_name, phase_module in phases:
        # M-8: machine-readable phase boundary marker (BEGIN). Pairs with
        # PHASE_END below. Lets log greppers find "what crashed at 47min"
        # without staring at the human-readable header.
        _phase_start = _time.time()
        print(f"[PHASE_BEGIN {phase_name} t={int(_phase_start)}]")

        print(f"\n{'='*60}")
        print(f"  {phase_name}")
        print(f"{'='*60}")

        # Check phase cache for crash recovery.
        # Phase 6 Finalize is INTENTIONALLY non-cacheable — its job is to publish
        # whatever `final_payload` Phase 5 produced this run. Caching it caused
        # a critical bug where a fresh conductor briefing was orphaned because
        # a morning run had already cached Phase 6 with the previous payload.
        cache_key = phase_cache_key(phase_name)
        if phase_name == "Phase 6: Finalize":
            cached = None
        else:
            try:
                from db import get_dashboard_state
                cached = get_dashboard_state(conn, cache_key)
                if phase_cache_fresh(cached, _phase_ttl_hours):
                    print(f"  [CACHE HIT] Skipping — completed within the "
                          f"last {_phase_ttl_hours:g}h")
                    context.update({k: v for k, v in cached.items() if not k.startswith("_")})
                    _phase_end = _time.time()
                    print(f"[PHASE_END {phase_name} t={int(_phase_end)} "
                          f"dt={int(_phase_end - _phase_start)} status=cached]")
                    continue
            except Exception:
                pass

        timeout = PHASE_TIMEOUTS.get(phase_name, 300)
        _phase_status = "ok"
        try:
            import threading

            # Use threading timeout (cross-platform). daemon=True (E-10) so a
            # hung phase thread can never keep the process alive after main exits.
            result_container = [None]
            error_container = [None]

            def _run_phase():
                try:
                    result_container[0] = phase_module.run(conn, context, run_log)
                except Exception as e:
                    error_container[0] = e

            t = threading.Thread(target=_run_phase, daemon=True)
            t.start()
            t.join(timeout=timeout)

            if t.is_alive():
                print(f"\n[TIMEOUT] {phase_name} exceeded {timeout}s — continuing with partial results")
                run_log.log_error(phase_name, Exception(f"Timeout after {timeout}s"), recovered=True)
                _phase_status = "timeout"
            elif error_container[0]:
                _phase_status = "error"
                raise error_container[0]
            else:
                result = result_container[0]
                # C3 (reliability audit 2026-06-15): the conductor returns {} on
                # failure WITHOUT raising (phases/conductor.py), so the except-
                # clause hard-halt below never fires — the loop would fall through
                # and Phase 6 would silently re-publish LAST week's edition under
                # this week's date (exit 0, green CI, no retry). An empty conductor
                # result means no fresh briefing was produced → hard-fail so the
                # CI failure-issue + retry fire instead of shipping a stale edition.
                if phase_module is conductor and not result:
                    print("\n[CRITICAL] Conductor produced no briefing — halting "
                          "to avoid a silent stale republish")
                    run_log.log_error(phase_name,
                                      Exception("Conductor produced empty result"),
                                      recovered=False, severity="critical")
                    run_log.finalize("error")
                    sys.exit(1)
                # Merge phase outputs into shared context
                if result:
                    context.update(result)
                    # Cache phase results for crash recovery.
                    # Skip Phase 6 — it's non-cacheable by design (see cache-check above).
                    if phase_name != "Phase 6: Finalize":
                        try:
                            from datetime import datetime, timezone
                            from db import save_dashboard_state
                            cache_data = {k: v for k, v in result.items()
                                          if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
                            cache_data["_completed"] = True
                            # E-2: UTC ISO completion stamp — phase_cache_fresh()
                            # rejects entries older than PHASE_CACHE_TTL_HOURS.
                            cache_data["_completed_at"] = datetime.now(timezone.utc).isoformat()
                            save_dashboard_state(conn, cache_key, cache_data)
                        except Exception:
                            pass  # caching is best-effort

        except Exception as e:
            import traceback
            print(f"\n[CRITICAL] {phase_name} failed: {e}")
            traceback.print_exc()
            # M-1/NEW-7: a phase that raised (recovered=False) is run-halting, not a
            # warn-level scraper flake — tag critical so the run is demoted honestly.
            run_log.log_error(phase_name, e, recovered=False, severity="critical")
            _phase_status = "error"
            # M-8: emit PHASE_END before bailing on conductor failure
            _phase_end = _time.time()
            print(f"[PHASE_END {phase_name} t={int(_phase_end)} "
                  f"dt={int(_phase_end - _phase_start)} status={_phase_status}]")
            # Conductor failure is critical — the run cannot ship a briefing.
            # Exit non-zero (not bare return, which exited 0 and let CI go green)
            # so the workflow failure-issue + retry fire (reliability audit C3).
            if phase_module is conductor:
                run_log.finalize("error")
                sys.exit(1)
            continue

        # M-8: emit PHASE_END marker on the happy / timeout paths
        _phase_end = _time.time()
        print(f"[PHASE_END {phase_name} t={int(_phase_end)} "
              f"dt={int(_phase_end - _phase_start)} status={_phase_status}]")

    # ── Service health summary ─────────────────────────────────────
    # M-5: persist the run's service-health snapshot BEFORE the get_status
    # print so the operator dashboard has the row even if logging fails.
    try:
        health.persist(conn, getattr(run_log, '_run_id', None))
    except Exception as _e:
        print(f"[SERVICE HEALTH] persist raised (non-critical): {_e}")

    health_status = health.get_status()
    if health_status["dead"]:
        print(f"\n[SERVICE HEALTH] Dead services: {health_status['dead']}")
    run_log.log_metric("api_usage", "service_health", health_status)

    # ── Status-change counter (audit H7; red-team F1/F8) ──────────
    # Real status changes are written to project_events with
    # event_type='status_change' (project_sync.py) — NOT project_changes,
    # whose only writer (change_detector) is orphaned. Use the LOCAL date:
    # event rows carry local dates, and a UTC date from an evening run would
    # exclude same-evening changes.
    try:
        from datetime import date as _ld
        _since = _ld.today().isoformat()
        _sc = conn.execute(
            "SELECT COUNT(*) FROM project_events "
            "WHERE event_type = 'status_change' "
            "AND COALESCE(NULLIF(event_date, ''), detected_date) >= ?",
            (_since,)).fetchone()
        run_log.log_metric("discovery", "status_changes", int(_sc[0] if _sc else 0))
    except Exception as _e:
        print(f"[WARN] status-change counter failed (non-critical): {_e}")

    # ── Operator health summary (audit H1) ────────────────────────
    # One block that makes a dead tier look different from a quiet week.
    _print_operator_summary(conn, run_log, health_status, context)

    # ── Data warehouse connection health (RC-6, 2026-07-11) ───────
    # Central per-connection retrieval health: last-success age vs cadence,
    # consecutive failures, and series-accrual gaps. Writes
    # docs/data/warehouse_status.json (+ public/data mirror) and prints loud
    # [WAREHOUSE] lines for failed/overdue connections. Must NEVER crash the
    # pipeline — everything is wrapped.
    try:
        from data_warehouse import check_health, write_status_json, log_health_summary
        _wh_health = check_health(conn=conn)
        log_health_summary(_wh_health)
        for _p in write_status_json(health=_wh_health):
            print(f"[WAREHOUSE] wrote {_p}")
    except Exception as _wh_e:
        print(f"[WAREHOUSE] health check failed (non-critical): "
              f"{type(_wh_e).__name__}: {_wh_e}")

    # ── Finalize pipeline run log ─────────────────────────────────
    final_payload = context.get("final_payload", {})
    if final_payload.get('_analysis_incomplete'):
        run_log.finalize("partial")
    else:
        run_log.finalize("success")


def _print_operator_summary(conn, run_log, health_status, context):
    """End-of-run operator summary: tier yields, dead feeds, dead services,
    signal-tier output, and error counts — in one block in the run log.

    A discovery tier or signal feed that is 100% dead must be visually
    distinct from one that simply had a quiet news week (audit finding H1:
    jobs + procurement returned zero for 3 months unnoticed).
    """
    print("\n" + "=" * 62)
    print("OPERATOR RUN SUMMARY")
    print("=" * 62)
    try:
        d = run_log._discovery
        print(f"  Discovery: {d.get('articles_found', 0)} articles | "
              f"{d.get('projects_added', 0)} new projects | "
              f"{d.get('projects_updated', 0)} updated | "
              f"{d.get('fuzzy_merges', 0)} fuzzy-merged | "
              f"{d.get('status_changes', 0)} status changes")
    except Exception:
        pass

    # Per-tier yields this run (zero-yield tiers flagged inline)
    try:
        from db import get_dashboard_state
        hist = get_dashboard_state(conn, "tier_yield_history") or {}
        parts, zeros = [], []
        for tier, runs in sorted(hist.items()):
            if isinstance(runs, list) and runs:
                last = runs[-1]
                n = last.get("count", last) if isinstance(last, dict) else last
                (zeros if not n else parts).append(f"{tier}={n}")
        if parts:
            print(f"  Tier yields: {', '.join(parts)}")
        if zeros:
            print(f"  [!] ZERO-YIELD TIERS: {', '.join(zeros)} — dead source or quiet week; "
                  f"check per-source FAILED lines above")
        if not parts and not zeros:
            # Red-team F10: silent absence reads as "nothing to report" —
            # say explicitly that the instrument has no data yet.
            print("  Tier yields: no history yet (tier_yield_history empty — "
                  "first run, or query_yield_audit did not record this run)")
    except Exception as e:
        print(f"  Tier yields: unavailable ({e})")

    # Signal tiers: jobs / procurement / policy — chronic-empty alarms
    try:
        jobs = context.get("job_spikes")
        proc = context.get("procurement_contracts")
        pol = context.get("policy_items")
        print(f"  Signals: jobs={'n/a' if jobs is None else len(jobs)} spikes | "
              f"procurement={'n/a' if proc is None else len(proc)} contracts | "
              f"policy={'n/a' if pol is None else len(pol)} items")
        # Jobs: a post-filter zero is still a meaningful chronic-empty alarm.
        if jobs is not None and len(jobs) == 0:
            print("  [!] JOBS returned 0 — verify source health "
                  "(this tier was dead for 3 months before 2026-06-11 audit)")
        # Procurement (2026-06-19): the sources fetch a ROLLING WINDOW every
        # run, so ~100% of fetched contracts are repeats and procurement_contracts
        # is empty MOST weeks BY DESIGN. A post-dedup zero is therefore NOT an
        # alarm. Gate on whether ANY source returned raw rows pre-dedup this run
        # (procurement_sources_had_rows from run_procurement_monitor): if sources
        # returned rows but everything deduped → benign info line; if NO source
        # returned rows → the sources are dark, raise the alarm.
        if proc is not None and len(proc) == 0:
            had_rows = context.get("procurement_sources_had_rows")
            if had_rows:
                print("  Procurement: sources healthy, 0 new (all fetched "
                      "contracts already seen — rolling-window dedup, expected)")
            else:
                print("  [!] PROCUREMENT returned 0 raw rows from every source — "
                      "verify source health (dead endpoints; see per-source "
                      "FAILED/DARK lines above)")
    except Exception:
        pass

    # RSS feed health (rolling, from rss_feed_health table)
    try:
        from rss_feed_health import get_health_summary
        fh = get_health_summary(conn)
        if fh.get("total_feeds"):
            print(f"  RSS feeds: {fh['active']}/{fh['total_feeds']} active, "
                  f"{fh['dormant']} dormant (1-7 empty wks), "
                  f"{fh['dead_candidate']} dead candidates (>=8 empty wks)")
            if fh["dead_candidate"]:
                print(f"  [!] {fh['dead_candidate']} feeds look dead — "
                      f"review rss_feed_health table (additive-only: flag, don't remove)")
    except Exception:
        pass

    # Service health
    try:
        if health_status.get("dead"):
            print(f"  [!] DEAD SERVICES: {health_status['dead']}")
        if health_status.get("degraded"):
            print(f"  [!] Degraded services: {health_status['degraded']}")
    except Exception:
        pass

    # Error rollup
    try:
        nc, nw = len(run_log._errors_critical), len(run_log._errors)
        if nc or nw:
            print(f"  Errors: {nc} critical, {nw} warn — see [LOG] lines above")
            for e in run_log._errors_critical[:5]:
                print(f"    CRITICAL {e.get('step')}: {e.get('message', '')[:120]}")
    except Exception:
        pass
    print("=" * 62)


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
        seed_articles = run_google_news_search()
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


def _run_post_export_validator_gate():
    """Post-export validator gate — HARD FAIL on schema FAIL.

    Runs `tools/validate_briefing_schema.py` against `docs/data/briefing_latest.json`
    immediately after the daily or weekly pipeline exports. Exit codes:
        0 = PASS  → return, proceed to deploy
        2 = WARN  → return, proceed to deploy (known B.4 producer-regen gaps)
        1 = FAIL  → print the validator output and `sys.exit(1)` so the
                    GitHub Actions workflow fails loudly. This is the
                    regression guard that catches a daily or weekly export
                    that silently clobbered required fields. See CLAUDE.md
                    "Validator is a deploy gate" invariant and
                    HANDOFF_NEXT_SESSION.md Phase B.5.

    No override flag. No silent ship. If the briefing file is missing the
    gate also fails — the daily export is supposed to have written it.
    """
    import subprocess
    import sys as _sys

    briefing_path = os.path.join(
        os.path.dirname(__file__), "docs", "data", "briefing_latest.json"
    )
    if not os.path.exists(briefing_path):
        print(f"\n[VALIDATOR GATE] FAIL — briefing_latest.json missing at {briefing_path}")
        _sys.exit(1)

    validator_path = os.path.join(
        os.path.dirname(__file__), "tools", "validate_briefing_schema.py"
    )
    print("\n[VALIDATOR GATE] Re-validating briefing_latest.json post-export...")
    proc = subprocess.run(
        [_sys.executable, validator_path, briefing_path],
        capture_output=True,
        text=True,
    )
    # Always echo the validator's own report for CI log visibility.
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)

    rc = proc.returncode
    if rc == 0:
        print("[VALIDATOR GATE] PASS — briefing_latest.json is schema-clean.")
        return
    if rc == 2:
        print(
            "[VALIDATOR GATE] WARN — briefing_latest.json has non-critical "
            "warnings (known producer-regen gaps). Proceeding to deploy."
        )
        return
    # rc == 1 (FAIL) or any other non-zero — abort the run.
    print(
        f"\n[VALIDATOR GATE] FAIL — validator returned exit code {rc}. "
        "The daily/weekly run must not clobber required fields. "
        "Deploy blocked. Fix the briefing and re-run."
    )
    _sys.exit(1)


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
        # R4: stamp the sweep date so the weekly overdue check resets
        from datetime import date as _date
        from db import save_dashboard_state
        save_dashboard_state(conn, "last_known_sweep_date", _date.today().isoformat())
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

            # Policy tracker runs in daily mode too (added 2026-04-19).
            # Just RSS parsing — lightweight. Freshens policy_snapshots so the
            # weekly run does not miss items that surfaced mid-week.
            print("\n[DAILY MODE] Running policy tracker (RSS only, no researcher merge)...")
            try:
                from policy_tracker import run_policy_tracker
                policy_result = run_policy_tracker(conn, research_paths=None)
                print(
                    f"[OK] Policy tracker: {len(policy_result.get('policy_items', []))} items, "
                    f"{len(policy_result.get('policy_new_items', []))} new"
                )
                daily_log.log_step("policy_tracker_daily")
            except Exception as e:
                print(f"[WARN] Policy tracker failed (non-fatal): {e}")
                import traceback
                traceback.print_exc()
                daily_log.log_error("policy_tracker_daily", e, recovered=True)

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

        # Post-daily-run validator gate — see HANDOFF_NEXT_SESSION.md Phase B.5.
        # Fails the workflow (sys.exit 1) if the daily export clobbered a
        # required briefing_latest.json field. WARN-tier does not block.
        _run_post_export_validator_gate()
    else:
        update_dashboard(deep_sweep=args.deep_sweep)
        # Post-weekly-run validator gate — same guarantee as daily. If Phase 6
        # (Finalize) wrote a briefing_latest.json that fails the schema
        # contract, the workflow fails before the Deploy/commit step runs.
        _run_post_export_validator_gate()
