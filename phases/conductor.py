"""
phases/conductor.py — Conductor phase: orchestrates subagent briefing pipeline.

Replaces the old monolithic agent phases (research_agents, analysis_agents,
synthesis_agent, analysis/writing, reasoning, narrative, verification) with
a single conductor invocation that dispatches focused subagents for research,
analysis, writing, charting, and quality assurance via Claude Code skills.

The Python pipeline handles:
  - Phases 1-4: Data collection, discovery, filtering, signals
  - This phase: Data enrichment + conductor dispatch
  - Finalize: Timeseries, quality report, export, deploy
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime

# ── Claude CLI resolution ─────────────────────────────────────────────────────

_CLAUDE_CLI = shutil.which('claude')
if not _CLAUDE_CLI:
    _npm_dir = os.path.join(os.environ.get('APPDATA', ''), 'npm')
    _candidate = os.path.join(_npm_dir, 'claude.cmd')
    if os.path.isfile(_candidate):
        _CLAUDE_CLI = _candidate

_CLAUDE_ENV = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'docs', 'data')

CONDUCTOR_TIMEOUT = int(os.environ.get('CONDUCTOR_TIMEOUT', '7200'))  # 2 hours
CONDUCTOR_MAX_TURNS = int(os.environ.get('CONDUCTOR_MAX_TURNS', '200'))
# NEW-5: pin the conductor to the concrete Opus model id from pipeline_config
# instead of the floating 'opus' CLI alias — a freshly-installed CLI resolving
# 'opus' to a newer model caused run-to-run prose/quality drift + cost mismatch.
from pipeline_config import OPUS_MODEL as _PINNED_OPUS_MODEL
CONDUCTOR_MODEL = os.environ.get('CONDUCTOR_MODEL') or _PINNED_OPUS_MODEL


# ── Pre-conductor: Python data enrichment ─────────────────────────────────────

def _run_trend_computation(conn):
    """Run Python-based trend computation (moved from old narrative phase).

    Produces sector trends, indicator trends, cross-references, and stores
    snapshots to SQLite. This data feeds into docs/data/ exports that the
    conductor's agents read.
    """
    results = {}
    try:
        from sector_trends import compute_project_trends
        from indicator_trends import compute_indicator_trends
        from cross_reference import cross_reference_trends
        from weekly_trend_report import generate_trend_report
        from db import save_trend_snapshot, save_dashboard_state

        sector_data = compute_project_trends(conn)
        indicator_data = compute_indicator_trends(conn)
        xref_data = cross_reference_trends(indicator_data, sector_data)
        trend_report = generate_trend_report(
            sector_data, indicator_data, xref_data, conn=conn
        )

        if sector_data and not sector_data.get("error"):
            save_trend_snapshot(conn, {
                "week_of": datetime.now().strftime("%Y-W%W"),
                "snapshot": sector_data,
            })

        if xref_data and not xref_data.get("error"):
            save_dashboard_state(conn, "cross_references", {
                "data": xref_data,
                "updated_at": datetime.now().isoformat(),
            })
            print("    Cross-reference data stored")

        results['sector_data'] = sector_data
        results['indicator_data'] = indicator_data
        results['xref_data'] = xref_data
        results['trend_report'] = trend_report
        print("    Trend computation complete")
    except Exception as e:
        print(f"    Trend computation failed (non-critical): {e}")
    return results


def _run_policy_and_events(conn, context):
    """Run policy monitor and event calendar (moved from old narrative phase)."""
    results = {}

    # Provincial policy monitor
    try:
        from provincial_policy_monitor import process_policy_feeds
        policy_devs = process_policy_feeds(conn, since_days=7)
        results['policy_developments'] = policy_devs
        if policy_devs:
            print(f"    {len(policy_devs)} policy developments processed")
    except Exception as e:
        print(f"    Policy monitor failed (non-critical): {e}")

    # Canadian commodity indicators
    try:
        from canadian_markets import fetch_and_store_commodities
        cdn_comms = fetch_and_store_commodities(conn)
        results['cdn_commodity_data'] = cdn_comms
    except Exception as e:
        print(f"    Commodity indicators failed (non-critical): {e}")

    # Province event search (cached 7 days)
    try:
        from event_calendar import get_cached_province_events, search_province_events
        cached = get_cached_province_events(conn)
        if not cached:
            print("    Searching province events via Tavily...")
            search_province_events(conn, days_ahead=30)
    except Exception as e:
        print(f"    Province event search failed (non-critical): {e}")

    # Economic event calendar
    try:
        from event_calendar import get_and_store_events
        upcoming = get_and_store_events(conn, days_ahead=14)
        results['upcoming_events'] = upcoming
    except Exception as e:
        print(f"    Event calendar failed (non-critical): {e}")

    return results


def _export_data_files(conn, context):
    """Export current data to docs/data/ for conductor agents to read."""
    import json as _json

    from tools.export_dashboard import export_all
    result = export_all(conn=conn)
    print(f"    Exported {result['file_count']} data files to {result['output_dir']}")

    # Write industry GDP data as a standalone file for analyst/writer agents
    primary_ind = context.get('primary_ind', context.get('hard_data', {}).get('primary_indicators', {}))
    industries = primary_ind.get('industries', {})
    if industries:
        industry_gdp = {k: v for k, v in industries.items() if not k.startswith('_')}
        gdp_path = os.path.join(DATA_DIR, 'industry_gdp.json')
        with open(gdp_path, 'w', encoding='utf-8') as f:
            _json.dump(industry_gdp, f, ensure_ascii=False, indent=2)
        n_valid = sum(1 for v in industry_gdp.values() if v.get('mm', 'N/A') != 'N/A')
        print(f"    Industry GDP: {n_valid}/{len(industry_gdp)} NAICS codes with M/M data")


# ── Conductor invocation ──────────────────────────────────────────────────────

def _summarize_accuracy_files() -> str:
    """One factual DATA STATUS line for province_counts.json and
    discovery_summary.json (quality-pass-1.4), or '' if neither exists."""
    parts = []
    try:
        pc_path = os.path.join(DATA_DIR, 'province_counts.json')
        if os.path.exists(pc_path):
            with open(pc_path, encoding='utf-8') as f:
                provs = (json.load(f) or {}).get('provinces', {}) or {}
            qualifying = sum(v.get('qualifying', 0) for v in provs.values())
            unpriced = sum(v.get('tracked_unpriced', 0) for v in provs.values())
            stale = sum(v.get('stale', 0) for v in provs.values())
            parts.append(
                f"province_counts.json — {qualifying} qualifying, "
                f"{unpriced} tracked-unpriced, {stale} stale projects "
                f"across {len(provs)} provinces")
    except Exception:
        pass
    try:
        ds_path = os.path.join(DATA_DIR, 'discovery_summary.json')
        if os.path.exists(ds_path):
            with open(ds_path, encoding='utf-8') as f:
                ds = json.load(f) or {}
            parts.append(
                f"discovery_summary.json — week of {ds.get('week_of', '?')}: "
                f"{ds.get('new', 0)} new, {ds.get('rediscovered', 0)} rediscovered, "
                f"{ds.get('status_changes', 0)} status changes")
    except Exception:
        pass
    if not parts:
        return ""
    return "\n- " + "; ".join(parts)


def _build_conductor_prompt(today_str: str) -> str:
    """Build the prompt that triggers the conductor's briefing track."""
    return f"""Run the briefing track for "The Lagging Indicator" weekly briefing.

TODAY: {today_str}

DATA STATUS: The Python pipeline has already completed all data collection:
- indicators.json, projects_all.json, timeseries.json, policy.json, commodities.json, events.json are all current in docs/data/
- industry_gdp.json — per-NAICS M/M and Y/Y GDP changes from StatCan WDS (20 industries)
- jobs.json — hiring spike data by CMA and sector (from job_monitor)
- procurement.json — government contract awards >=5M (from procurement_monitor)
- iaac.json — federal impact assessment projects with status history
- signals.json — combined signal summary (jobs, procurement, IAAC counts){_summarize_accuracy_files()}
- dashboard.db is up to date with this week's discoveries, filtering, and signals
- Trend computation and cross-references are stored in SQLite

SKIP Phase 0 (Data Refresh) — all data files are already current.

Run these phases in order:
1. Phase 0.5: Data Gap Audit
2. Phase 1: Research (3 parallel agents)
3. Phase 2: Analysis (3 parallel agents)
4. Phase 3: Writing (4 parallel agents)
5. Phase 3.5: Assembly
6. Phase 4: Charts
7. Phase 5: Audit + Discovery (parallel)
8. Phase 6: Fix (if audit is not PASS)

AUTOMATION MODE — proceed without asking for user input:
- Data gap audit: proceed regardless of gap count
- Agent failures: log and continue with remaining agents
- Auditor verdict: run fixer if not PASS, then proceed
- Do NOT run Deploy (git commit/push) — the Python pipeline handles that

After all phases, write the final briefing to docs/data/briefing_{today_str}.json.
Do NOT overwrite briefing_latest.json — the Python pipeline promotes it during deploy.
"""


def _invoke_conductor(prompt: str) -> bool:
    """Invoke the conductor via claude -p. Returns True on success."""
    if not _CLAUDE_CLI:
        print("    ERROR: claude CLI not found — cannot run conductor")
        print("    Install: npm install -g @anthropic-ai/claude-code")
        return False

    prompt_file = None
    try:
        # Write the prompt file INSIDE PROJECT_ROOT (not the system %TEMP%).
        # The conductor runs `claude -p` with cwd=PROJECT_ROOT and its tool
        # sandbox only permits reads within the working dir; a %TEMP% path is
        # denied, leaving the conductor with no instructions (stale briefing).
        with tempfile.NamedTemporaryFile(mode='w', prefix='conductor_prompt_',
                                         suffix='.txt', delete=False,
                                         encoding='utf-8', dir=PROJECT_ROOT) as f:
            f.write(prompt)
            prompt_file = f.name

        prompt_arg = (
            f'Read the file {prompt_file} and follow the instructions exactly. '
            f'You are the conductor — dispatch subagents for each phase as '
            f'described in the tldr-conductor skill.'
        )
        cmd = [
            _CLAUDE_CLI, '-p', prompt_arg,
            '--model', CONDUCTOR_MODEL,
            '--max-turns', str(CONDUCTOR_MAX_TURNS),
            # Headless `-p` has no interactive approval path. The conductor must
            # Write/Edit briefing JSON and run `python tools/*.py` within its own
            # project dir (cwd=PROJECT_ROOT); without this every mutating tool is
            # auto-denied and the pipeline falls back to a stale briefing.
            '--permission-mode', 'bypassPermissions',
        ]

        print(f"    Invoking conductor ({CONDUCTOR_MODEL}, "
              f"max {CONDUCTOR_MAX_TURNS} turns, "
              f"{CONDUCTOR_TIMEOUT // 60} min timeout)...")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=CONDUCTOR_TIMEOUT,
            encoding='utf-8', errors='replace', env=_CLAUDE_ENV,
            cwd=PROJECT_ROOT,
        )

        if result.returncode != 0:
            print(f"    Conductor exit code {result.returncode}")
            if result.stderr:
                stderr_tail = result.stderr.strip().split('\n')[-5:]
                print(f"    stderr: {chr(10).join(stderr_tail)}")
            return False

        # Print conductor output summary (last 30 lines)
        output = result.stdout.strip()
        if output:
            lines = output.split('\n')
            summary_lines = lines[-30:] if len(lines) > 30 else lines
            print(f"    Conductor output ({len(lines)} lines, showing last {len(summary_lines)}):")
            for line in summary_lines:
                print(f"      {line}")

        return True

    except subprocess.TimeoutExpired:
        print(f"    Conductor timed out after {CONDUCTOR_TIMEOUT // 60} minutes")
        return False
    except Exception as e:
        print(f"    Conductor error: {type(e).__name__}: {e}")
        return False
    finally:
        if prompt_file:
            try:
                os.unlink(prompt_file)
            except OSError:
                pass


# ── Output reading ────────────────────────────────────────────────────────────

def _read_conductor_output() -> dict:
    """Read the briefing JSON produced by the conductor.

    Looks for docs/data/briefing_YYYY-MM-DD.json first, then
    falls back to briefing_latest.json.
    """
    today_str = date.today().isoformat()
    briefing_file = os.path.join(DATA_DIR, f'briefing_{today_str}.json')

    if not os.path.exists(briefing_file):
        print(f"    No briefing_{today_str}.json found, checking briefing_latest.json")
        briefing_file = os.path.join(DATA_DIR, 'briefing_latest.json')

    if os.path.exists(briefing_file):
        try:
            with open(briefing_file, 'r', encoding='utf-8') as f:
                briefing = json.load(f)
            headline = briefing.get('headline', 'N/A')
            provinces = len(briefing.get('provinces', []))
            goods = len(briefing.get('goodsIndustries', []))
            services = len(briefing.get('servicesIndustries', []))
            print(f"    Briefing loaded: \"{headline}\"")
            print(f"    {provinces} provinces, {goods} goods, {services} services industries")
            return briefing
        except Exception as e:
            print(f"    Failed to read briefing JSON: {e}")

    return {}


# ── Pipeline phase entry point ────────────────────────────────────────────────

def run(conn, context: dict, run_log) -> dict:
    """Pipeline phase entry point — orchestrate the conductor briefing track."""
    step_name = "conductor"
    try:
        today_str = date.today().isoformat()

        # Step 1: Python data enrichment (trends, policy, events)
        print("\n  [Step 1] Trend computation & data enrichment...")
        trend_results = _run_trend_computation(conn)
        extra_results = _run_policy_and_events(conn, context)

        # Step 2: Export all data to docs/data/ for conductor agents
        print("  [Step 2] Exporting data files for conductor agents...")
        _export_data_files(conn, context)

        # Step 3: Invoke the conductor
        print("  [Step 3] Running conductor briefing track...")
        prompt = _build_conductor_prompt(today_str)
        success = _invoke_conductor(prompt)

        if not success:
            print("\n  [WARN] Conductor failed — briefing may be incomplete")
            # Conductor produces the briefing; its failure means the run cannot
            # ship a complete edition → critical (M-1).
            run_log.log_error(step_name, Exception("Conductor invocation failed"),
                              recovered=True, severity="critical")

        # Step 4: Read conductor output
        print("  [Step 4] Reading conductor output...")
        briefing = _read_conductor_output()

        if not briefing:
            print("  [WARN] No briefing output — finalize will run with empty payload")

        run_log.log_step(step_name)

        return {
            'final_payload': briefing,
            **trend_results,
            **extra_results,
        }

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Conductor phase failed: {e}")
        traceback.print_exc()
        # Whole conductor phase exception → pipeline cannot produce a briefing.
        run_log.log_error(step_name, e, recovered=True, severity="critical")
        return {}
