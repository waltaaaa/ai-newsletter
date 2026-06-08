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


def _run_google_news(gemini_client):
    """Tier 2: Google News RSS discovery."""
    from google_news_rss_search import run_google_news_search
    return run_google_news_search(gemini_client=gemini_client)


def _run_bing_news():
    """Tier 2b: Bing News RSS discovery (parallel coverage source).

    Same compound + NAICS queries as Google. Resilient when Google soft-bans
    the IP (12-24h cooldown after bursty pulls); Bing also surfaces Canadian
    outlets (Canadian Mining Journal, BNN Bloomberg, MSN, etc.) that don't
    always appear in Google News.
    """
    from bing_news_rss_search import run_bing_news_search
    return run_bing_news_search()


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
            f_tier1  = executor.submit(_run_tier1, tavily_client)
            f_tier13 = executor.submit(_run_tier13)
            f_tier14 = executor.submit(_run_tier14)
            f_news   = executor.submit(_run_google_news, gemini_client)
            f_bing   = executor.submit(_run_bing_news)

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

        # ── Project alert tracker (monthly — first week only) ─────────
        alert_articles = []
        try:
            from project_alert_tracker import is_first_week_of_month, run_monthly_alert_check_sync
            if is_first_week_of_month():
                print("\n[ALERT-TRACKER] Monthly project alert check (first week of month)...")
                alert_result = run_monthly_alert_check_sync(conn)
                alert_articles = alert_result.get("articles", [])
                print(f"  [ALERT-TRACKER] {alert_result.get('alerts_checked', 0)} alerts checked, "
                      f"{len(alert_articles)} articles found, "
                      f"{alert_result.get('deactivated', 0)} alerts deactivated")
            else:
                print("\n[ALERT-TRACKER] Skipped (not first week of month)")
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

        logger.log_step("tier_2_google_news")
        logger.log_step(step_name)

        return {
            "registry_projects": registry_projects,
            "municipal_projects": municipal_projects,
            "institutional_projects": institutional_projects,
            "gemini_projects": gemini_projects,
            "tavily_searches_count": tavily_searches_count,
        }
    except Exception as e:
        # Whole-phase exception: discovery is empty, pipeline must continue but
        # downstream phases are starved → critical.
        logger.log_error(step_name, e, severity="critical")
        traceback.print_exc()
        return {}
