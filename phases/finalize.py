"""Phase 9: Finalize — Timeseries append, assembly, quality report, export, deploy"""
import traceback
import json
import pytz
from datetime import date, datetime, timedelta


def _sync_weekly_briefings(conn, final_payload: dict) -> None:
    """M-2 — keep `weekly_briefings` table in lock-step with on-disk briefings.

    Per audit: `weekly_briefings.week_of` last updated 2026-03-30 but on-disk
    briefings exist through 2026-05-19. The dashboard pointer
    (`dashboard_state.newsletter_latest`) is updated; the weekly_briefings
    archive is not. Anything downstream that reads "most recent briefing" from
    the table (cohort comparisons, sector_trends WoW deltas) sees stale data.

    This function upserts a row keyed on week_of using INSERT OR REPLACE. The
    full briefing JSON is stored in a `briefing_json` TEXT column (added via
    ALTER TABLE if missing — defensive). Idempotent.

    Schema (see migrations/002_weekly_briefings_schema.sql):
        weekly_briefings(
            id INTEGER PK,
            week_of TEXT UNIQUE NOT NULL,
            headline TEXT,
            edition TEXT,
            briefing_json TEXT,
            generated_at TEXT,
            ... (legacy columns kept for backward compat)
        )
    """
    try:
        # Defensive: ensure the table exists (db.py creates it on init_db, but
        # this lets the function work even if called from a script that didn't
        # init the full schema).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_briefings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                week_of      TEXT NOT NULL,
                headline     TEXT DEFAULT '',
                sections     TEXT DEFAULT '{}',
                word_count   INTEGER DEFAULT 0,
                generated_at TEXT DEFAULT '',
                pdf_url      TEXT DEFAULT '',
                docx_url     TEXT DEFAULT ''
            )
        """)

        # Defensive: add new columns if missing (ALTER TABLE ADD COLUMN is
        # idempotent only via try/except in SQLite).
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(weekly_briefings)").fetchall()}
        if 'briefing_json' not in existing_cols:
            try:
                conn.execute("ALTER TABLE weekly_briefings ADD COLUMN briefing_json TEXT DEFAULT ''")
            except Exception:
                pass
        if 'edition' not in existing_cols:
            try:
                conn.execute("ALTER TABLE weekly_briefings ADD COLUMN edition TEXT DEFAULT ''")
            except Exception:
                pass
        # week_of unique index so INSERT OR REPLACE works as upsert
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_briefings_week_of ON weekly_briefings(week_of)")
        except Exception:
            pass

        week_of = (final_payload.get('week_of') or final_payload.get('updated_at')
                   or date.today().isoformat())
        headline = final_payload.get('headline', '') or ''
        edition = final_payload.get('edition', '') or ''
        generated_at = (final_payload.get('generated_at')
                        or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        try:
            briefing_json = json.dumps(final_payload, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            print(f"  [FINALIZE] weekly_briefings JSON serialize failed: {e}")
            return

        sections = final_payload.get('sections', {}) or {}
        try:
            sections_json = json.dumps(sections, ensure_ascii=False)
        except (TypeError, ValueError):
            sections_json = '{}'

        word_count = 0
        try:
            exec_summary = final_payload.get('executive_summary', '') or ''
            word_count = len(exec_summary.split())
        except Exception:
            pass

        # INSERT OR REPLACE keyed on week_of (idempotent upsert)
        with conn:
            conn.execute(
                """INSERT INTO weekly_briefings
                       (week_of, headline, edition, sections, word_count,
                        generated_at, briefing_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(week_of) DO UPDATE SET
                       headline      = excluded.headline,
                       edition       = excluded.edition,
                       sections      = excluded.sections,
                       word_count    = excluded.word_count,
                       generated_at  = excluded.generated_at,
                       briefing_json = excluded.briefing_json
                """,
                (week_of, headline, edition, sections_json, word_count,
                 generated_at, briefing_json),
            )
        print(f"  [FINALIZE] weekly_briefings synced for week_of={week_of}")
    except Exception as e:
        # Non-critical — the on-disk briefing is still produced; this is just
        # an archive sync.
        print(f"  [FINALIZE] weekly_briefings sync failed (non-critical): "
              f"{type(e).__name__}: {e}")


def append_to_timeseries(conn, payload: dict, financial_markets: dict, boc_rate: str):
    """
    Append one data point per tracked variable to the timeseries table in SQLite.
    Skips duplicate dates (ON CONFLICT DO NOTHING).
    Variables tracked: BoC rate, CPI, unemployment, GoC yields, CAD/USD, TSX Composite.
    """
    from db import save_timeseries_point

    print("\n[TIMESERIES] Appending data points...")
    today_str = date.today().isoformat()

    def _upsert(series_name: str, unit: str, raw_value):
        """Parse raw_value to float and upsert into the timeseries table."""
        if raw_value is None:
            return
        try:
            val_f = float(str(raw_value).replace('%', '').replace('$', '').replace(',', '').strip())
        except Exception:
            return
        # Red-team F8: tag briefing-derived points so exporters/fact-checkers
        # can distinguish them from independently-fetched data (a writer's
        # own print must never become next week's verification baseline).
        save_timeseries_point(conn, series_name, today_str, val_f, unit=unit,
                              source='briefing_print')

    # BoC Rate
    _upsert('boc_rate', '%', boc_rate.replace('%', ''))

    # National metrics
    m = payload.get('metrics', {})
    _upsert('canada_cpi',         '%', (m.get('cpi') or '').replace('%', '').replace('+', ''))
    _upsert('canada_unemployment', '%', (m.get('unemployment') or '').replace('%', ''))

    # Yield curve terms
    for yc in payload.get('yieldCurve', []):
        term = yc.get('term', '')
        yval = yc.get('yield', '')
        if term and yval:
            _upsert(f'yield_{term.lower()}', '%', yval.replace('%', ''))

    def _vv(d):
        """Market item value: conductor briefings write 'val', legacy 'value'."""
        return str(d.get('value') or d.get('val') or '').replace(',', '')

    # CAD/USD
    for fx in financial_markets.get('fx', []):
        if 'CAD/USD' in fx.get('name', '') or 'CADUSD' in fx.get('name', ''):
            _upsert('cadusd', 'USD', _vv(fx))

    # TSX Composite
    for idx in financial_markets.get('indices', []):
        if 'TSX' in idx.get('name', ''):
            _upsert('tsx_composite', 'pts', _vv(idx))

    # Commodities — use canonical keys that match the yfinance backfill
    # (idx_*/comm_* prefixed variants were stale duplicates of the same data
    # under `wti`, `gold`, etc. — removed from the timeseries in 3.8.)
    COMM_ID_MAP = {
        'Crude Oil (WTI)': 'wti', 'Crude Oil (Brent)': 'brent',
        'Natural Gas': 'natural_gas', 'Gold': 'gold', 'Silver': 'silver',
        'Platinum': 'platinum', 'Palladium': 'palladium',
        'Copper': 'copper', 'Aluminum': 'aluminum',
        'Wheat': 'wheat', 'Corn': 'corn', 'Rice': 'rice',
        'Soybeans': 'soybeans', 'Coffee': 'coffee', 'Cocoa': 'cocoa',
        'Sugar #11': 'sugar', 'Cotton': 'cotton',
        'Soybean Oil': 'soybean_oil', 'Soybean Meal': 'soybean_meal',
        'Coal (Newcastle)': 'coal', 'Propane': 'propane',
        'Lumber': 'lumber',
        # Red-team F8/2.5 (2026-06-11): do NOT add the thin proxy series
        # (Uranium/Canola/Nickel/Potash) here. Appending writer-emitted
        # prints into a thin series makes the briefing its own fact-check
        # baseline next week (circular), and the Sprott/NTR proxies are in
        # different units than the prints. Those series need independent
        # fetchers (canola: StatCan vector — chip spawned 2026-06-11).
    }
    # The conductor-era briefing carries a FLAT commodities list
    # ([{name, val, unit, ...}]); the legacy shape was categorized
    # ([{items: [...]}]). Handle both — the categorized iteration silently
    # appended nothing for every conductor briefing (audit H9).
    _comm_items = []
    for cat in payload.get('commodities', []):
        if isinstance(cat, dict) and isinstance(cat.get('items'), list):
            _comm_items.extend(cat['items'])
        elif isinstance(cat, dict) and cat.get('name'):
            _comm_items.append(cat)
    for item in _comm_items:
        name = item.get('name', '')
        series_id = COMM_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, item.get('unit', ''),
                    str(item.get('val', '') or '').replace('$', '').replace(',', ''))

    # Other equity indices — canonical keys (sp500/djia/nasdaq/ftse100/dax/
    # nikkei225). Hang Seng and Shanghai have no non-prefixed canonical in the
    # backfill, so they keep their idx_ names.
    IDX_ID_MAP = {
        'S&P 500': 'sp500', 'Dow Jones': 'djia', 'NASDAQ': 'nasdaq',
        'FTSE 100': 'ftse100', 'DAX': 'dax', 'Nikkei 225': 'nikkei225',
        'Hang Seng': 'idx_hangseng', 'Shanghai': 'idx_shanghai',
    }
    for idx in financial_markets.get('indices', []):
        name = idx.get('name', '')
        series_id = IDX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, 'pts', _vv(idx))

    # Other FX pairs
    FX_ID_MAP = {
        'EUR/USD': 'fx_eurusd', 'GBP/USD': 'fx_gbpusd', 'USD/JPY': 'fx_usdjpy',
        'USD/CNY': 'fx_usdcny', 'AUD/USD': 'fx_audusd',
    }
    for fx_item in financial_markets.get('fx', []):
        name = fx_item.get('name', '')
        series_id = FX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, '', _vv(fx_item))

    print("  Timeseries update complete.")


def run(conn, context, logger):
    """Final assembly, timeseries, quality report, and static JSON export."""
    step_name = "Phase 6: Finalize"
    try:
        final_payload = context.get("final_payload", {})
        financial_markets = context.get("financial_markets", {})
        boc_data = context.get("boc_data", {})
        commodity_data = context.get("commodity_data", {})
        hard_data = context.get("hard_data", {})
        statcan_inds = context.get("statcan_inds")

        # If conductor produced the briefing, sources are inside the payload
        all_verified_sources = context.get("all_verified_sources",
                                            final_payload.get("_all_verified_sources",
                                            final_payload.get("sources", [])))

        # M-4 — apply confidence decay BEFORE the export. Per audit, 2,398
        # projects (31%) have not been re-seen in 30+ days but no project in
        # the DB has is_stale=1 or needs_review=1. confidence_decay.py exists
        # but was never wired into any phase.
        try:
            from confidence_decay import apply_confidence_decay
            decayed = apply_confidence_decay(conn) or {}
            print(f"  [DECAY] {decayed.get('decayed', 0)} projects decayed, "
                  f"{decayed.get('stale', 0)} flagged stale, "
                  f"{decayed.get('needs_review', 0)} need review")
            logger.log_metric("decay", "decayed_count", decayed.get('decayed', 0))
            logger.log_metric("decay", "stale_count",   decayed.get('stale', 0))
            logger.log_metric("decay", "review_count",  decayed.get('needs_review', 0))
        except Exception as e:
            print(f"  [DECAY] Decay step failed (non-critical): {e}")
            try:
                logger.log_error("confidence_decay", e)
            except Exception:
                pass

        # C2 (2026-06-08 audit) — weekly fuzzy-dedup REPORT pass. Dry-run only:
        # finds residual duplicate clusters (the live C1 fuzzy upsert prevents
        # new ones; this surfaces the backlog) and writes dedup_report_weekly.md
        # for operator review. Merging stays operator-gated via
        #   python tools/dedup_projects_fuzzy.py --merge
        # — never auto-applied here.
        try:
            import subprocess
            import sys as _sys
            from pathlib import Path as _Path
            _root = _Path(__file__).resolve().parent.parent
            _tool = _root / "tools" / "dedup_projects_fuzzy.py"
            if _tool.exists():
                r = subprocess.run(
                    [_sys.executable, str(_tool), "--report",
                     str(_root / "dedup_report_weekly.md")],
                    capture_output=True, text=True, timeout=600, cwd=str(_root),
                )
                tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-4:]
                for ln in tail:
                    print(f"  [DEDUP-REPORT] {ln}")
                if r.returncode != 0:
                    print(f"  [DEDUP-REPORT] tool exited {r.returncode} (non-critical)")
        except Exception as e:
            print(f"  [DEDUP-REPORT] weekly dedup report failed (non-critical): {e}")
            try:
                logger.log_error("dedup_report", e)
            except Exception:
                pass

        # Recall instruments — benchmark coverage audit + typed miss
        # classification. This existed as an operator tool only; the 2026-06-10
        # miss diagnosis (Portage Place sat on the benchmark list while
        # miss_audit_results stayed empty) showed it must run every pipeline
        # run so recall failures are loud, not latent.
        try:
            from tools.coverage_audit import run_coverage_audit, run_miss_classification
            from db import get_all_projects as _get_all_projects
            _cov = run_coverage_audit(_get_all_projects(conn))
            logger.log_metric("coverage", "benchmark_found", _cov.get("found", 0))
            logger.log_metric("coverage", "benchmark_total", _cov.get("total", 0))
            logger.log_metric("coverage", "benchmark_missing", len(_cov.get("missing", [])))
            if _cov.get("missing"):
                run_miss_classification(conn)
        except Exception as e:
            print(f"  [COVERAGE] benchmark audit failed (non-critical): {e}")
            try:
                logger.log_error("coverage_audit", e)
            except Exception:
                pass

        # M-3 — every weekly run, ensure Under Construction projects carry
        # an alert. The existing monthly check (project_alert_tracker.is_
        # first_week_of_month gate) only fires on day 1-7 of the month —
        # this priority sweep runs unconditionally because UC milestones
        # don't wait for the calendar.
        try:
            from project_alert_tracker import prioritize_alerts
            alert_stats = prioritize_alerts(conn) or {}
            logger.log_metric("alerts", "under_constr_total",
                              alert_stats.get("under_constr_total", 0))
            logger.log_metric("alerts", "under_constr_with_alerts",
                              alert_stats.get("under_constr_with_alerts", 0))
            logger.log_metric("alerts", "alerts_created",
                              alert_stats.get("alerts_created", 0))
            logger.log_metric("alerts", "alerts_reactivated",
                              alert_stats.get("alerts_reactivated", 0))
        except Exception as e:
            print(f"  [ALERTS] prioritize_alerts failed (non-critical): {e}")
            try:
                logger.log_error("prioritize_alerts", e)
            except Exception:
                pass

        # StatCan indicators snapshot
        try:
            from gov_sources import save_statcan_indicators
            save_statcan_indicators(conn, statcan_inds)
        except Exception as e:
            print(f"  [WARN] StatCan snapshot save failed: {e}")
            logger.log_error("statcan_snapshot", e)

        # Timeseries append
        try:
            append_to_timeseries(conn, final_payload, financial_markets, boc_data.get('rate') or 'N/A')
        except Exception as e:
            print(f"  [WARN] Timeseries append failed: {e}")
            logger.log_error("timeseries", e)

        # Edition string
        toronto_tz = pytz.timezone('America/Toronto')
        today = datetime.now(toronto_tz)
        last_week = today - timedelta(days=7)
        final_payload["edition"] = (
            f"EDITION: {last_week.strftime('%b %d').upper()} – "
            f"{today.strftime('%b %d').upper()} // STATUS: AI-SYNTHESIZED"
        )

        # Audit M3: top-level aliases. The assembler emits bocRate /
        # pipeline_value / project_count as literal null; the frontend uses
        # them as fallbacks (app.js reads D.bocRate, D.pipeline_value,
        # D.project_count). Backfill from metrics + the projects table so the
        # validator aliases are real values, not nulls.
        try:
            _m = final_payload.get('metrics') or {}
            if not final_payload.get('bocRate'):
                final_payload['bocRate'] = (_m.get('bocRate')
                                            or boc_data.get('rate') or '')
            if (not final_payload.get('pipeline_value')
                    or not final_payload.get('project_count')):
                _row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(value_millions), 0) "
                    "FROM projects WHERE status NOT IN "
                    "('Cancelled', 'Complete', 'Completed')").fetchone()
                if not final_payload.get('project_count'):
                    final_payload['project_count'] = int(_row[0] or 0)
                if not final_payload.get('pipeline_value'):
                    final_payload['pipeline_value'] = (
                        f"${(_row[1] or 0) / 1000:.1f}B")
        except Exception as e:
            print(f"  [WARN] Top-level alias backfill failed (non-critical): {e}")

        # Consumer sentiment to DB
        sentiment_result = hard_data.get('_sentiment_result')
        if sentiment_result:
            final_payload['consumer_sentiment'] = sentiment_result
            try:
                from db import save_dashboard_state
                save_dashboard_state(conn, 'latest_sentiment', {
                    'updatedAt': date.today().isoformat(),
                    'consumer_sentiment': sentiment_result,
                })
                print("  [Sentiment] Saved to SQLite")
            except Exception as e:
                print(f"  [Sentiment] SQLite write failed (non-critical): {e}")

        # Quality Report
        try:
            from tools.quality_report import generate_quality_report
            from db import get_all_projects
            print("\n[STEP 8] Generating quality report...")
            gemini_projects = context.get("gemini_projects", [])
            registry_projects = context.get("registry_projects", [])
            rss_projects = context.get("rss_projects", [])
            extracted_articles = context.get("extracted_articles", [])
            _discovery_stats = {
                'gemini_projects': len(gemini_projects) if gemini_projects else 0,
                'tavily_extractions': len(extracted_articles) if extracted_articles else 'N/A',
                'projects_registries': len(registry_projects) if registry_projects else 0,
                'projects_rss': len(rss_projects) if rss_projects else 0,
                'projects_gemini': len(gemini_projects) if gemini_projects else 0,
            }
            _writing_stats = {}
            _citation_audit = final_payload.get('citation_audit', {})
            if _citation_audit:
                watchlist = context.get("watchlist", {})
                _writing_stats = {
                    'total_citations': _citation_audit.get('total_citations', 0),
                    'verified_citations': _citation_audit.get('total_citations', 0) - _citation_audit.get('total_failed', 0),
                    'removed_citations': _citation_audit.get('total_failed', 0),
                    'audit_pass_rate': 'ALL PASSED' if _citation_audit.get('passed') else 'SOME FAILED',
                    'per_call': _citation_audit.get('calls', []),
                    'officials_referenced': 'N/A',
                    'officials_available': len(watchlist.get('public_figures_canada', [])) + len(watchlist.get('provincial_officials', [])),
                }
            _sentiment_stats = {}
            if sentiment_result:
                _sentiment_stats = {
                    'reddit_posts': sentiment_result.get('reddit_posts', 'N/A'),
                    'reddit_comments': sentiment_result.get('reddit_comments', 'N/A'),
                    'trends_queries': sentiment_result.get('trends_queries', 'N/A'),
                    'news_comments': sentiment_result.get('news_comments', 'N/A'),
                    'topics_count': len(sentiment_result.get('topics', [])),
                    'sentiment_index': sentiment_result.get('sentiment_index', 'N/A'),
                    'sentiment_label': sentiment_result.get('sentiment_label', 'N/A'),
                    'categories': sentiment_result.get('categories', {}),
                }
            generate_quality_report(
                conn=conn,
                discovery_stats=_discovery_stats,
                writing_stats=_writing_stats,
                sentiment_stats=_sentiment_stats,
            )
            logger.log_step("quality_report")
        except Exception as e:
            print(f"  [QUALITY] Quality report failed: {type(e).__name__}: {e}")
            logger.log_error("quality_report", e)

        # Final assembly + push to SQLite
        try:
            from db import save_dashboard_state
            print("\n[STEP 7] Final assembly + push to SQLite...")
            final_payload.setdefault('updated_at', date.today().isoformat())
            final_payload.setdefault('consumer_pulse', '')
            final_payload.setdefault('industry_executive_summary', '')
            final_payload.pop('_citation_audit', None)

            sources_with_archives = []
            for src in all_verified_sources:
                sources_with_archives.append({
                    'url': src.get('url', ''),
                    'title': src.get('title', ''),
                    'archive_url': src.get('archive_url', ''),
                })
            if sources_with_archives:
                final_payload['sources'] = sources_with_archives

            # Unsplash image disabled — stock photos don't fit the editorial style

            toronto_tz2 = pytz.timezone('America/Toronto')
            today2 = datetime.now(toronto_tz2)
            dated_id = today2.strftime('%Y-%m-%d')

            # Snapshot the PREVIOUS edition before newsletter_latest is
            # overwritten below. The stale-briefing gate (Check 5) must compare
            # against the prior week; reading newsletter_latest AFTER this write
            # compared the new briefing against itself and reported ~100%
            # overlap on every run (chronic false positive).
            _prev_headline, _prev_exec_summary = "", ""
            try:
                from db import get_dashboard_state as _gds_prev
                _prev_nl = _gds_prev(conn, 'newsletter_latest')
                if isinstance(_prev_nl, dict):
                    _prev_headline = (_prev_nl.get("headline", "") or "").strip()
                    _prev_exec_summary = _prev_nl.get("executive_summary", "") or ""
            except Exception:
                pass

            # NEW-4 (2026-06-08 audit): never overwrite a good edition with an
            # empty/soft-failed payload. A conductor soft-failure can leave
            # final_payload effectively empty; writing it blanked newsletter_latest
            # (and the entire live site) until the next successful run. Preserve the
            # prior edition and demote the run to critical instead.
            _payload_ok = bool(
                final_payload.get('executive_summary')
                or final_payload.get('sections')
                or final_payload.get('headline')
            )
            if _payload_ok:
                save_dashboard_state(conn, 'newsletter_latest', final_payload)
                save_dashboard_state(conn, f'newsletter_{dated_id}', final_payload)
            else:
                print("[ERROR] final_payload is empty/incomplete — PRESERVING prior "
                      "newsletter_latest (NEW-4 guard); not overwriting with a blank edition.")
                logger.log_error(
                    "finalize_empty_payload",
                    RuntimeError("empty final_payload; prior edition preserved"),
                    recovered=True, severity="critical")

            # M-2 — sync weekly_briefings archive table. Pointer-only
            # (newsletter_latest) wasn't enough: the table fell 3+ weeks behind
            # the on-disk briefings.
            try:
                _sync_weekly_briefings(conn, final_payload)
            except Exception as _e:
                print(f"  [FINALIZE] weekly_briefings sync raised: {_e}")

            if final_payload.get('_analysis_incomplete'):
                print("[WARN] Dashboard updated with INCOMPLETE analysis — Claude calls failed.")
            else:
                print("[OK] Dashboard successfully updated.")
            logger.log_step("step_7_firestore_push")
        except Exception as e:
            print(f"[ERROR] Step 7 (SQLite export) failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            # M-1/NEW-7: a failed final SQLite push means no briefing was persisted —
            # this is run-halting, not a recoverable scraper warning.
            logger.log_error("step_7_export", e, recovered=False, severity="critical")

        # Tavily usage logging
        try:
            from tavily_search import get_tavily_credits_used
            tavily_searches_count = context.get("tavily_searches_count", 0)
            tavily_credits = get_tavily_credits_used(conn)
            logger.log_metric("api_usage", "tavily_searches", tavily_searches_count)
            logger.log_metric("api_usage", "tavily_month_total", tavily_credits.get("used", 0))
        except Exception as e:
            print(f"  [WARN] Tavily usage logging failed: {e}")

        # ── Quality gate — block deploy if critical checks fail ────────
        gate_passed = True
        gate_failures = []

        # Check 1: briefing is non-empty
        exec_summary = final_payload.get("executive_summary", "")
        if not exec_summary or len(exec_summary) < 100:
            gate_failures.append("Briefing executive_summary is empty or too short")
            gate_passed = False

        # Check 2: minimum project count
        try:
            from db import get_projects
            all_projects = get_projects(conn, limit=10000)
            if len(all_projects) < 100:
                gate_failures.append(f"Only {len(all_projects)} projects in DB (minimum: 100)")
                gate_passed = False
            # Check 3: province representation
            provinces_found = set(p.get("province", "") for p in all_projects)
            if len(provinces_found) < 10:
                gate_failures.append(f"Only {len(provinces_found)} provinces represented (minimum: 10)")
                gate_passed = False
        except Exception as e:
            gate_failures.append(f"Could not check projects: {e}")

        # Check 4: editorial word scan
        FORBIDDEN_WORDS = {"should", "must", "worrying", "promising", "encouraging",
                          "welcome", "bullish", "bearish", "unfortunately", "hopefully"}
        editorial_violations = []
        for text_key in ("executive_summary", "consumer_pulse", "industry_executive_summary"):
            text = final_payload.get(text_key, "")
            if text:
                words = text.lower().split()
                for fw in FORBIDDEN_WORDS:
                    if fw in words:
                        editorial_violations.append(f"{text_key}: contains '{fw}'")
        # Check provinces' analysis text too
        for prov in final_payload.get("provinces", []):
            analysis = prov.get("analysis", "")
            if analysis:
                words = analysis.lower().split()
                for fw in FORBIDDEN_WORDS:
                    if fw in words:
                        editorial_violations.append(f"province {prov.get('name', '?')}: contains '{fw}'")
        if editorial_violations:
            print(f"\n[EDITORIAL SCAN] {len(editorial_violations)} violations found:")
            for v in editorial_violations[:10]:
                print(f"  - {v}")
            # Editorial violations are warnings, not gate blockers

        # Check 5: stale briefing detection. The real failure mode is the
        # pipeline republishing the PREVIOUS edition (conductor stale-fallback).
        # Compare against the prior edition snapshotted before the overwrite
        # above — and flag only on a (near-)identical republish, not on the
        # shared macro vocabulary that any two distinct weeks naturally have
        # (the old shared-words/0.90 ratio fired on every genuine new edition).
        try:
            new_headline = (final_payload.get("headline", "") or "").strip()
            if _prev_exec_summary and exec_summary:
                if _prev_headline and new_headline and _prev_headline == new_headline:
                    print(f"\n[STALE WARNING] Headline identical to previous edition: {new_headline!r}")
                    gate_failures.append("Stale briefing: headline identical to previous edition")
                    gate_passed = False
                else:
                    prev_words = set(_prev_exec_summary.lower().split())
                    new_words = set(exec_summary.lower().split())
                    if prev_words and new_words:
                        overlap = len(prev_words & new_words) / max(len(prev_words), len(new_words))
                        # >=0.98 = effectively the same text, not just same topic
                        if overlap >= 0.98:
                            print(f"\n[STALE WARNING] Briefing {overlap:.0%} identical to previous week")
                            gate_failures.append(f"Stale briefing: {overlap:.0%} identical to previous week")
                            gate_passed = False
        except Exception:
            pass

        if gate_passed:
            print("\n[QUALITY GATE] PASSED — proceeding to export")
        else:
            print(f"\n[QUALITY GATE] FAILED — {len(gate_failures)} issues:")
            for f in gate_failures:
                print(f"  - {f}")
            print("  Export will proceed but issues are logged.")
            logger.log_error("quality_gate", Exception("; ".join(gate_failures)))

        # Static JSON export
        try:
            from tools.export_dashboard import export_all
            print("\n[STEP 9] Exporting static JSON files...")
            export_result = export_all(conn=conn)
            print(f"[OK] Exported {export_result['file_count']} files to {export_result['output_dir']}")
            logger.log_step("step_9_json_export")
        except Exception as e:
            print(f"[ERROR] Static JSON export failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            logger.log_error("json_export", e, recovered=False)

        # Claude API cost summary
        try:
            cost_state = context.get("claude_cost", {})
            input_tok = cost_state.get("input", 0)
            output_tok = cost_state.get("output", 0)
            cost_usd = cost_state.get("usd", 0)
            cap = cost_state.get("cap", 0)
            print(f"\n[COST SUMMARY] Claude API: {input_tok:,} input + {output_tok:,} output tokens = ${cost_usd:.4f} (cap: ${cap:.2f})")
            logger.log_metric("api_usage", "claude_input_tokens", input_tok)
            logger.log_metric("api_usage", "claude_output_tokens", output_tok)
            logger.log_metric("api_usage", "claude_cost_usd", round(cost_usd, 4))
        except Exception as e:
            print(f"  [WARN] Cost summary failed: {e}")

        # Service health summary
        health = context.get("health")
        if health:
            health_status = health.get_status()
            if health_status.get("dead"):
                print(f"\n[SERVICE HEALTH] Dead services: {health_status['dead']}")
            logger.log_metric("api_usage", "service_health", health_status)

        logger.log_step(step_name, "success")
        return {"status": "completed" if not final_payload.get('_analysis_incomplete') else "partial"}
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {"status": "error"}
