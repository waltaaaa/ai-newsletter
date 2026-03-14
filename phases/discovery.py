"""Phase 2: Discovery — Tiers 1-14 project discovery"""
import traceback
from datetime import date


def run(conn, context, logger):
    """Run all discovery tiers."""
    step_name = "Phase 2: Discovery"
    try:
        tavily_client = context.get("tavily_client")
        gemini_client = context.get("gemini_client")

        # Tier 1: Government registries
        print("\n[TIER 1] Government registries...")
        from gov_sources import fetch_registry_projects
        registry_projects = fetch_registry_projects(tavily_client=tavily_client)
        logger.log_step("tier_1_registries")

        # Tier 13: Municipal development applications
        municipal_projects = []
        try:
            from municipal_dev_apps import scrape_municipal_applications_sync
            print("\n[TIER 13] Municipal development applications...")
            municipal_projects = scrape_municipal_applications_sync()
            print(f"  {len(municipal_projects)} municipal projects found")
        except Exception as e:
            print(f"  [TIER 13] Municipal scrape failed: {type(e).__name__}: {e}")
            logger.log_error("tier_13_municipal", e)

        # Tier 14: Institutional capital plans
        institutional_projects = []
        try:
            from institutional_capital import scrape_institutional_capital
            print("\n[TIER 14] Institutional capital plans...")
            institutional_projects = scrape_institutional_capital()
            print(f"  {len(institutional_projects)} institutional projects found")
        except Exception as e:
            print(f"  [TIER 14] Institutional scrape failed: {type(e).__name__}: {e}")
            logger.log_error("tier_14_institutional", e)

        # Procurement monitor: federal + provincial contract awards
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

        # Policy tracker: legislative and regulatory monitoring
        try:
            from policy_tracker import run_policy_tracker
            print("\n[POLICY] Policy and legislative tracking...")
            policy_results = run_policy_tracker(conn)
            context.update(policy_results)
            print(f"  {len(policy_results['policy_items'])} relevant items, "
                  f"{len(policy_results['policy_new_items'])} new this week")
        except ImportError:
            print("[WARN] policy_tracker not available, skipping policy monitoring")
        except Exception as e:
            print(f"[WARN] Policy tracker failed: {type(e).__name__}: {e}")
            logger.log_error("policy_tracker", e)

        # Tier 2: Gemini compound discovery
        gemini_projects = []

        # Consume follow-up queries from last week via Tavily
        tavily_searches_count = 0
        try:
            from pipeline_store import get_follow_up_queries
            from tavily_search import tavily_search_sync, can_use_tavily
            pro_follow_ups = get_follow_up_queries(db=None, conn=conn)
            if pro_follow_ups and can_use_tavily():
                print(f"\n[TIER 2] Running {len(pro_follow_ups)} follow-up queries via Tavily...")
                for fq in pro_follow_ups[:30]:  # Cap at 30 Tavily credits
                    if not can_use_tavily():
                        print("  [TAVILY] Budget limit reached — stopping follow-ups")
                        break
                    query_text = fq.get("query", "") if isinstance(fq, dict) else str(fq)
                    results = tavily_search_sync(query_text, max_results=3)
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
                print(f"  [FOLLOWUP] {len(gemini_projects)} results from follow-up queries")
        except Exception as e:
            print(f"  [FOLLOWUP] Failed: {type(e).__name__}: {e}")

        # Google News RSS discovery (replaces Gemini grounded search)
        print("\n[TIER 2] Google News RSS discovery...")
        try:
            from google_news_rss_search import run_google_news_search
            news_articles = run_google_news_search(gemini_client=gemini_client)
            if news_articles:
                gemini_projects.extend(news_articles)
        except Exception as e:
            print(f"  [TIER 2] Google News RSS failed: {type(e).__name__}: {e}")
            logger.log_error("tier_2_google_news", e)

        logger.log_step("tier_2_google_news")
        logger.log_step(step_name, "success")

        return {
            "registry_projects": registry_projects,
            "municipal_projects": municipal_projects,
            "institutional_projects": institutional_projects,
            "gemini_projects": gemini_projects,
            "tavily_searches_count": tavily_searches_count,
        }
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
