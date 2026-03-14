"""Phase 6: Reasoning — Gap analysis, dedup QA, extraction recovery, meta-analysis"""
import traceback
from datetime import datetime


def run(conn, context, logger):
    """Run Claude reasoning layer for gap analysis and quality assurance."""
    step_name = "Phase 6: Reasoning"
    try:
        try:
            from pipeline_store import store_follow_up_queries
            from claude_reasoning import (
                analyze_provincial_gaps_sync,
                recover_failed_extractions_sync,
                analyze_dedup_sync, store_dedup_results,
                run_meta_analysis_sync, store_meta_analysis,
            )
            from project_sync import upsert_flat_projects

            print("\n[CLAUDE] Reasoning layer...")

            # Task 1: Gap analysis on provincial sweep results
            cap_result = context.get("cap_result")
            sweep_by_province = {}
            for p in (cap_result or {}).get("_t2_projects", []):
                sweep_by_province.setdefault(p.get("province", "Unknown"), []).append(p)
            if sweep_by_province:
                follow_ups = analyze_provincial_gaps_sync(sweep_by_province)
                if follow_ups:
                    store_follow_up_queries(db=None, queries=follow_ups, conn=conn)

            # Task 2: Recover failed RSS extractions
            rss_failed = context.get("rss_failed_articles", [])
            if rss_failed:
                recovered = recover_failed_extractions_sync(rss_failed)
                if recovered:
                    upsert_flat_projects(conn, recovered)
                    print(f"  [CLAUDE] Recovered {len(recovered)} projects from failed extractions")

            # Task 3: Dedup analysis on this week's new projects
            flat_for_dedup = context.get("all_flat_projects", [])
            if flat_for_dedup and len(flat_for_dedup) > 10:
                dedup_flags = analyze_dedup_sync(flat_for_dedup[:200])
                if dedup_flags:
                    store_dedup_results(conn, dedup_flags)

            # Task 4: Monthly meta-analysis (first week only)
            if datetime.now().day <= 7:
                print("  [CLAUDE] Running monthly meta-analysis...")
                meta = run_meta_analysis_sync(conn)
                if meta:
                    store_meta_analysis(conn, meta)
        except Exception as e:
            print(f"  [CLAUDE] Reasoning failed: {type(e).__name__}: {e}")

        logger.log_step(step_name, "success")
        return {}
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
