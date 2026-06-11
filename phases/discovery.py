"""Phase 2: Discovery — Tiers 1-14 project discovery"""
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date


def _run_tier1(tavily_client):
    """Tier 1: Government registries."""
    from gov_sources import fetch_registry_projects
    return fetch_registry_projects(tavily_client=tavily_client)


def _run_tier13():
    """Tier 13: Municipal development applications."""
    from municipal_dev_apps import scrape_municipal_applications_sync
    return scrape_municipal_applications_sync()


def _run_tier14():
    """Tier 14: Institutional capital plans."""
    from institutional_capital import scrape_institutional_capital
    return scrape_institutional_capital()


def _run_google_news(gemini_client, conn=None):
    """Tier 2: Google News RSS discovery."""
    from google_news_rss_search import run_google_news_search
    return run_google_news_search(gemini_client=gemini_client, conn=conn)


def _run_bing_news(gemini_client=None, conn=None):
    """Tier 2b: Bing News RSS discovery (parallel coverage source).

    Same compound + NAICS queries as Google. Resilient when Google soft-bans
    the IP (12-24h cooldown after bursty pulls); Bing also surfaces Canadian
    outlets (Canadian Mining Journal, BNN Bloomberg, MSN, etc.) that don't
    always appear in Google News.
    """
    from bing_news_rss_search import run_bing_news_search
    return run_bing_news_search(gemini_client=gemini_client, conn=conn)


def run(conn, context, logger):
    """Run all discovery tiers."""
    step_name = "Phase 2: Discovery"
    try:
        tavily_client = context.get("tavily_client")
        gemini_client = context.get("gemini_client")

        # ── Parallel batch: independent tiers (no shared state) ────────
        print("\n[DISCOVERY] Running Tiers 1, 2, 2b, 13, 14 in parallel...")
        registry_projects = []
        municipal_projects = []
        institutional_projects = []
        news_articles = []
        bing_articles = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            # conn is shared with the news threads for the documents cache
            # (L0 skip + classified-doc recording). db.get_db() opens with
            # check_same_thread=False and busy_timeout, and all document
            # writes are wrapped in their own try/except.
            f_tier1  = executor.submit(_run_tier1, tavily_client)
            f_tier13 = executor.submit(_run_tier13)
            f_tier14 = executor.submit(_run_tier14)
            f_news   = executor.submit(_run_google_news, gemini_client, conn)
            f_bing   = executor.submit(_run_bing_news, gemini_client, conn)

            # Collect results inside the with-block (executor waits on exit)
            try:
                registry_projects = f_tier1.result()
            except Exception as e:
                print(f"  [TIER 1] Registry fetch failed: {type(e).__name__}: {e}")
                logger.log_error("tier_1_registries", e, severity="warn")

            try:
                municipal_projects = f_tier13.result()
                print(f"  [TIER 13] {len(municipal_projects)} municipal projects found")
            except Exception as e:
                print(f"  [TIER 13] Municipal scrape failed: {type(e).__name__}: {e}")
                logger.log_error("tier_13_municipal", e, severity="warn")

            try:
                institutional_projects = f_tier14.result()
                print(f"  [TIER 14] {len(institutional_projects)} institutional projects found")
            except Exception as e:
                print(f"  [TIER 14] Institutional scrape failed: {type(e).__name__}: {e}")
                logger.log_error("tier_14_institutional", e, severity="warn")

            try:
                news_articles = f_news.result() or []
            except Exception as e:
                print(f"  [TIER 2] Google News RSS failed: {type(e).__name__}: {e}")
                logger.log_error("tier_2_google_news", e, severity="warn")

            try:
                bing_articles = f_bing.result() or []
                print(f"  [TIER 2b] Bing News RSS: {len(bing_articles)} articles")
            except Exception as e:
                print(f"  [TIER 2b] Bing News RSS failed: {type(e).__name__}: {e}")
                logger.log_error("tier_2b_bing_news", e, severity="warn")

        # Merge Bing into news_articles, deduping by URL. Even though each
        # source dedupes internally, the same article can surface via both
        # Google's and Bing's redirectors with different wrapper URLs — title
        # match catches obvious duplicates.
        if bing_articles:
            seen_urls = {a.get("link") or a.get("url") for a in news_articles}
            seen_titles = {(a.get("title") or "").strip().lower() for a in news_articles}
            added = 0
            for art in bing_articles:
                url = art.get("link") or art.get("url")
                title_key = (art.get("title") or "").strip().lower()
                if url and url not in seen_urls and title_key not in seen_titles:
                    news_articles.append(art)
                    seen_urls.add(url)
                    seen_titles.add(title_key)
                    added += 1
            print(f"  [TIER 2/2b] Merged: {added} unique Bing articles added "
                  f"(news_articles total: {len(news_articles)})")

        # ── R8: per-query yield audit (rolling 8-week history) ─────────
        # Articles carry `_query` (the shortened RSS query). Aggregate counts
        # and append to dashboard_state; queries zero-yield 4+ consecutive
        # weeks get a deprioritization suggestion in pipeline_improvements.
        # Flag only — NOTHING is ever removed from config (additive-only).
        try:
            from query_yield_audit import record_week
            query_counts = {}
            for art in news_articles:
                q = art.get("_query")
                if q:
                    query_counts[q] = query_counts.get(q, 0) + 1
            record_week(conn, query_counts)
        except Exception as e:
            print(f"[WARN] Query yield audit failed: {type(e).__name__}: {e}")
            logger.log_error("query_yield_audit", e, severity="info")

        logger.log_step("tier_1_registries")

        # ── Sequential: conn-dependent tiers (update context) ──────────
        # IAAC status tracker
        try:
            from iaac_status import run_iaac_status
            print("\n[IAAC-STATUS] IAAC assessment status tracking...")
            iaac_results = run_iaac_status(conn)
            context.update(iaac_results)
            status_changes = len(iaac_results.get("iaac_status_changes", []))
            new_disc = len(iaac_results.get("iaac_new_discoveries", []))
            if status_changes or new_disc:
                print(f"  {status_changes} status changes, {new_disc} new discoveries")
        except ImportError:
            print("[WARN] iaac_status not available, skipping IAAC status tracking")
        except Exception as e:
            print(f"[WARN] IAAC status tracking failed: {type(e).__name__}: {e}")
            logger.log_error("iaac_status_tracker", e, severity="warn")

        # Procurement monitor
        try:
            from procurement_monitor import run_procurement_monitor
            print("\n[PROCUREMENT] Government procurement tracking...")
            procurement_results = run_procurement_monitor(conn)
            context.update(procurement_results)
        except ImportError:
            print("[WARN] procurement_monitor not available, skipping procurement tracking")
        except Exception as e:
            print(f"[WARN] Procurement monitor failed: {type(e).__name__}: {e}")
            logger.log_error("procurement_monitor", e, severity="warn")

        # Policy tracker
        try:
            from policy_tracker import run_policy_tracker
            print("\n[POLICY] Policy and legislative tracking...")
            policy_results = run_policy_tracker(conn)
            context.update(policy_results)
            print(f"  {len(policy_results.get('policy_items', []))} relevant items, "
                  f"{len(policy_results.get('policy_new_items', []))} new this week")
        except ImportError:
            print("[WARN] policy_tracker not available, skipping policy monitoring")
        except Exception as e:
            print(f"[WARN] Policy tracker failed: {type(e).__name__}: {e}")
            logger.log_error("policy_tracker", e, severity="warn")

        # ── Project alert tracker (G5: due-based, every weekly run) ───
        # quality-pass-1.4: the first-week-of-month gate is replaced by
        # tier-based due selection inside the tracker (weekly / monthly /
        # quarterly cadences, value-ranked hard cap). The due-set check now
        # runs on EVERY weekly run; an empty due set is a cheap no-op.
        alert_articles = []
        try:
            from project_alert_tracker import run_monthly_alert_check_sync
            print("\n[ALERT-TRACKER] Due-based project alert check (tiered cadence)...")
            alert_result = run_monthly_alert_check_sync(conn)
            alert_articles = alert_result.get("articles", [])
            print(f"  [ALERT-TRACKER] {alert_result.get('alerts_checked', 0)} alerts checked "
                  f"({alert_result.get('due_total', 0)} due, "
                  f"{alert_result.get('overflow', 0)} deferred), "
                  f"{len(alert_articles)} articles found, "
                  f"{alert_result.get('deactivated', 0)} alerts deactivated")
        except ImportError:
            print("[WARN] project_alert_tracker not available")
        except Exception as e:
            print(f"[WARN] Project alert tracker failed: {type(e).__name__}: {e}")
            logger.log_error("project_alert_tracker", e, severity="warn")

        # ── Tavily follow-ups (budget-constrained, must be sequential) ─
        gemini_projects = list(news_articles) + alert_articles
        tavily_searches_count = 0
        try:
            from pipeline_store import get_follow_up_queries
            from tavily_search import tavily_search_sync, can_use_tavily
            pro_follow_ups = get_follow_up_queries(db=None, conn=conn)
            if pro_follow_ups and can_use_tavily():
                queries = pro_follow_ups[:30]
                print(f"\n[TIER 2] Running {len(queries)} follow-up queries via Tavily (3 concurrent)...")

                def _run_followup(fq):
                    if not can_use_tavily():
                        return None, fq
                    query_text = fq.get("query", "") if isinstance(fq, dict) else str(fq)
                    return tavily_search_sync(query_text, max_results=3), fq

                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures = [pool.submit(_run_followup, fq) for fq in queries]
                    for fut in as_completed(futures):
                        results, fq = fut.result()
                        if results is None:
                            break  # budget limit
                        tavily_searches_count += 1
                        if results:
                            for r in results:
                                gemini_projects.append({
                                    "title": r.get("title", ""),
                                    "url": r.get("url", ""),
                                    "summary": r.get("content", ""),
                                    "_discovery_tier": "tavily_followup",
                                    "_province": fq.get("province", "") if isinstance(fq, dict) else "",
                                    "_sector": fq.get("sector", "") if isinstance(fq, dict) else "",
                                })
                print(f"  [FOLLOWUP] {len(gemini_projects) - len(news_articles)} results from follow-up queries")
        except Exception as e:
            print(f"  [FOLLOWUP] Failed: {type(e).__name__}: {e}")

        # ── R3 (2026-06-08 audit): snowball discovery — previously built but
        # never called from anywhere. Multi-pass follow-up discovery is query-
        # heavy (Pass 1 alone is a 421-query sweep), so it runs only in
        # deep-sweep mode and only when SNOWBALL_DISCOVERY_ENABLED.
        if context.get("mode") == "deep-sweep":
            try:
                from pipeline_config import SNOWBALL_DISCOVERY_ENABLED
                if SNOWBALL_DISCOVERY_ENABLED:
                    from snowball_discovery import run_snowball_sweep
                    print("\n[SNOWBALL] Multi-pass snowball discovery (deep-sweep mode)...")
                    snowball_projects = run_snowball_sweep(conn) or []
                    for p in snowball_projects:
                        p.setdefault("discovery_source", "snowball_discovery")
                    registry_projects = list(registry_projects) + snowball_projects
                    print(f"  [SNOWBALL] {len(snowball_projects)} projects from snowball sweep")
                else:
                    print("\n[SNOWBALL] Disabled (SNOWBALL_DISCOVERY_ENABLED=false)")
            except ImportError as e:
                print(f"[WARN] snowball_discovery unavailable: {e}")
            except Exception as e:
                print(f"[WARN] Snowball discovery failed: {type(e).__name__}: {e}")
                logger.log_error("snowball_discovery", e, severity="warn")

        # ── R4 (2026-06-08 audit): known-project sweep cadence. The sweep
        # (~190 instruction-style queries) re-confirms the known-project
        # universe so evidence accrues — it previously ran only when the
        # operator remembered `--known-sweep`. It runs in deep-sweep mode and
        # stamps dashboard_state; weekly runs log loudly once it is overdue
        # (>35 days) instead of silently letting evidence go stale.
        try:
            from datetime import date as _date
            from db import get_dashboard_state, save_dashboard_state
            _stamp = get_dashboard_state(conn, "last_known_sweep_date")
            _days_since = None
            if _stamp:
                try:
                    _days_since = (_date.today() - _date.fromisoformat(str(_stamp)[:10])).days
                except ValueError:
                    _days_since = None
            if context.get("mode") == "deep-sweep":
                from known_project_sweep import run_known_project_sweep_sync
                print("\n[KNOWN-SWEEP] Known-project sweep (deep-sweep mode)...")
                _ks = run_known_project_sweep_sync(conn)
                save_dashboard_state(conn, "last_known_sweep_date", _date.today().isoformat())
                print(f"  [KNOWN-SWEEP] {_ks}")
            elif _days_since is None or _days_since > 35:
                _ago = f"{_days_since} days ago" if _days_since is not None else "never"
                print(f"\n[KNOWN-SWEEP OVERDUE] Last known-project sweep: {_ago}. "
                      f"Run `python update_dashboard.py --deep-sweep` (or --known-sweep) "
                      f"— evidence counts decay without periodic re-confirmation.")
        except Exception as e:
            print(f"[WARN] Known-sweep cadence check failed: {type(e).__name__}: {e}")
            logger.log_error("known_project_sweep", e, severity="warn")

        logger.log_step("tier_2_google_news")

        # ── E7: per-tier yield history (weekly runs only) ──────────────
        # Rolling 8-run per-tier counts in dashboard_state; a tier with 2+
        # consecutive zero-yield runs is logged loudly as DEGRADED.
        if context.get("mode") == "weekly":
            try:
                from db import get_dashboard_state, save_dashboard_state
                from query_yield_audit import update_tier_history
                this_run = {
                    "tier1_registries": len(registry_projects),
                    "tier2_news_search": len(news_articles),
                    "tier2b_bing_news": len(bing_articles),
                    "tier13_municipal": len(municipal_projects),
                    "tier14_institutional": len(institutional_projects),
                    "iaac_status": (len(context.get("iaac_status_changes") or [])
                                    + len(context.get("iaac_new_discoveries") or [])),
                    "procurement": len(context.get("procurement_contracts") or []),
                    "policy": len(context.get("policy_items") or []),
                }
                tier_history = get_dashboard_state(conn, "tier_yield_history") or {}
                tier_history, degraded = update_tier_history(tier_history, this_run)
                save_dashboard_state(conn, "tier_yield_history", tier_history)
                for tier_name, zero_runs in degraded:
                    print(f"  [TIER {tier_name} DEGRADED] zero yield "
                          f"{zero_runs} consecutive runs")
                    logger.log_error(
                        f"tier_yield_{tier_name}",
                        RuntimeError(f"zero yield {zero_runs} consecutive runs"),
                        severity="warn")
            except Exception as e:
                print(f"[WARN] Tier yield history failed: {type(e).__name__}: {e}")
                logger.log_error("tier_yield_history", e, severity="info")

        logger.log_step(step_name)

        return {
            "registry_projects": registry_projects,
            "municipal_projects": municipal_projects,
            "institutional_projects": institutional_projects,
            "gemini_projects": gemini_projects,
            "tavily_searches_count": tavily_searches_count,
            # Red-team F4: these were only context.update()'d in-place and
            # never in the return dict, so a crash-retry run that cache-hits
            # this phase fed the conductor/microscope EMPTY signal lists and
            # the operator summary printed n/a. Returning them makes them
            # part of the cached phase result.
            "policy_items": context.get("policy_items", []),
            "policy_new_items": context.get("policy_new_items", []),
            "policy_summary": context.get("policy_summary", {}),
            "procurement_contracts": context.get("procurement_contracts", []),
            "iaac_status_changes": context.get("iaac_status_changes", []),
            "iaac_new_discoveries": context.get("iaac_new_discoveries", []),
        }
    except Exception as e:
        # Whole-phase exception: discovery is empty, pipeline must continue but
        # downstream phases are starved → critical.
        logger.log_error(step_name, e, severity="critical")
        traceback.print_exc()
        return {}
