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


def run(conn, context, logger):
    """Run all discovery tiers."""
    step_name = "Phase 2: Discovery"
    try:
        tavily_client = context.get("tavily_client")
        gemini_client = context.get("gemini_client")

        # ── Parallel batch: independent tiers (no shared state) ────────
        print("\n[DISCOVERY] Running Tiers 1, 2, 13, 14 in parallel...")
        registry_projects = []
        municipal_projects = []
        institutional_projects = []
        news_articles = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            f_tier1  = executor.submit(_run_tier1, tavily_client)
            f_tier13 = executor.submit(_run_tier13)
            f_tier14 = executor.submit(_run_tier14)
            f_news   = executor.submit(_run_google_news, gemini_client)

            # Collect results inside the with-block (executor waits on exit)
            try:
                registry_projects = f_tier1.result()
            except Exception as e:
                print(f"  [TIER 1] Registry fetch failed: {type(e).__name__}: {e}")
                logger.log_error("tier_1_registries", e)

            try:
                municipal_projects = f_tier13.result()
                print(f"  [TIER 13] {len(municipal_projects)} municipal projects found")
            except Exception as e:
                print(f"  [TIER 13] Municipal scrape failed: {type(e).__name__}: {e}")
                logger.log_error("tier_13_municipal", e)

            try:
                institutional_projects = f_tier14.result()
                print(f"  [TIER 14] {len(institutional_projects)} institutional projects found")
            except Exception as e:
                print(f"  [TIER 14] Institutional scrape failed: {type(e).__name__}: {e}")
                logger.log_error("tier_14_institutional", e)

            try:
                news_articles = f_news.result() or []
            except Exception as e:
                print(f"  [TIER 2] Google News RSS failed: {type(e).__name__}: {e}")
                logger.log_error("tier_2_google_news", e)

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
            logger.log_error("iaac_status_tracker", e)

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
            logger.log_error("procurement_monitor", e)

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
            logger.log_error("policy_tracker", e)

        # ── Tavily follow-ups (budget-constrained, must be sequential) ─
        gemini_projects = list(news_articles)
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
        logger.log_error(step_name, e)
        traceback.print_exc()
        return {}
