"""
capacity_scheduler.py -- Orchestrator for STEP_2J capacity tiers.

Runs all 6 new query tiers within the daily Gemini budget.
Single integration point for update_dashboard.py.

Daily budget:
  Compound discovery: ~108 (existing)
  Cost finder:        ~60  (existing)
  Lifecycle monitor:  ~20  (existing)
  T1 Verification:     50  (new)
  T2+T3+T5+T6:       115  (new)
  T4 Named tracking:   50  (new)
  Buffer:             ~97  (safety margin)
  Total:             ~500/day
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TIER_BUDGETS = {
    "T1": 50,   # Deep verification
    "T2": 15,   # Provincial sweeps
    "T3": 50,   # CMA deep dives
    "T4": 50,   # Named project tracking
    "T5": 25,   # Federal/interprovincial
    "T6": 25,   # Emerging sectors
}

TOTAL_NEW_BUDGET = sum(TIER_BUDGETS.values())  # 215


def run_capacity_tiers(db):
    """Run all 6 capacity tiers within budget.

    Called from update_dashboard.py after lifecycle_monitor.

    Args:
        db: Firestore client

    Returns:
        dict with summary stats for each tier
    """
    print(f"\n[CAPACITY] Starting capacity utilization tiers "
          f"({TOTAL_NEW_BUDGET} queries across 6 tiers)...")

    summary = {
        "T1_confirmed": 0, "T1_unconfirmed": 0,
        "T2_T3_T5_T6_projects": 0,
        "T4_updated": 0, "T4_checked": 0,
        "total_queries": 0, "errors": 0,
    }

    # ── T1: Deep Verification (50 queries) ────────────────────────
    try:
        from deep_verification import run_verification
        print("\n[T1] Deep verification of single-source projects...")
        t1_result = run_verification(db, max_queries=TIER_BUDGETS["T1"])
        summary["T1_confirmed"] = t1_result.get("confirmed", 0)
        summary["T1_unconfirmed"] = t1_result.get("unconfirmed", 0)
        summary["total_queries"] += TIER_BUDGETS["T1"]
    except Exception as e:
        print(f"  [T1] Failed: {type(e).__name__}: {e}")
        summary["errors"] += 1

    # ── T2+T3+T5+T6: Capacity Discovery (115 queries) ────────────
    try:
        from capacity_queries import run_capacity_discovery
        from project_sync import upsert_flat_projects

        budgets = {
            "T2": TIER_BUDGETS["T2"],
            "T3": TIER_BUDGETS["T3"],
            "T5": TIER_BUDGETS["T5"],
            "T6": TIER_BUDGETS["T6"],
        }

        projects = run_capacity_discovery(db, budgets)
        # Split T2 provincial sweep results for Pro gap analysis
        t2_projects = [p for p in projects if p.get("geo_tier") == "provincial_sweep"]
        summary["_t2_projects"] = t2_projects
        if projects:
            # Convert to upsert format
            flat = []
            for p in projects:
                flat.append({
                    "name": p.get("name", ""),
                    "description": p.get("description", ""),
                    "province": p.get("province", ""),
                    "sector": p.get("naics_2digit") or p.get("sector", ""),
                    "cma": p.get("cma", ""),
                    "value": p.get("value", "Not disclosed"),
                    "status": p.get("status", "Proposed"),
                    "proponent": p.get("proponent", ""),
                    "project_type": p.get("project_type", ""),
                    "sources": [{"url": p["source_url"], "title": p.get("source_title", "")}]
                             if p.get("source_url") else [],
                    "discovery_source": p.get("discovery_source", "gemini_capacity"),
                    "discovery_sources": [p.get("discovery_source", "gemini_capacity")],
                    "confidence": 0.6 if p.get("confidence") == "verified" else 0.3,
                    "evidence": p.get("_evidence", []),
                    "evidence_count": len(p.get("_evidence", [])),
                    "has_government_source": any(
                        "gov" in (e.get("url", "") or "").lower()
                        for e in p.get("_evidence", [])
                    ),
                    "has_known_source": p.get("confidence") == "verified",
                })

            upsert_flat_projects(db, flat)
            summary["T2_T3_T5_T6_projects"] = len(projects)

        query_count = sum(budgets.values())
        summary["total_queries"] += query_count
    except Exception as e:
        print(f"  [T2-T6] Failed: {type(e).__name__}: {e}")
        summary["errors"] += 1

    # ── T4: Named Project Tracking (50 queries) ──────────────────
    try:
        from named_tracker import run_named_tracking_sync
        print("\n[T4] Named project tracking for top-value projects...")
        t4_result = run_named_tracking_sync(db, max_queries=TIER_BUDGETS["T4"])
        summary["T4_updated"] = t4_result.get("updated", 0)
        summary["T4_checked"] = t4_result.get("checked", 0)
        summary["total_queries"] += TIER_BUDGETS["T4"]
    except Exception as e:
        print(f"  [T4] Failed: {type(e).__name__}: {e}")
        summary["errors"] += 1

    # Print summary
    print(f"\n[CAPACITY] Summary:")
    print(f"  T1 Verification: {summary['T1_confirmed']} confirmed, "
          f"{summary['T1_unconfirmed']} unconfirmed")
    print(f"  T2-T6 Discovery: {summary['T2_T3_T5_T6_projects']} projects")
    print(f"  T4 Tracking: {summary['T4_updated']} updated, "
          f"{summary['T4_checked']} checked")
    print(f"  Total queries: ~{summary['total_queries']}")

    return summary
