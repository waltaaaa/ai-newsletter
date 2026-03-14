#!/usr/bin/env python3
"""Backfill missing dashboard_state documents for new frontend sections.

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time/occasional utility script.

Creates:
  - dashboard_state/microscope_current  (from microscope_history + latest_briefing)
  - dashboard_state/cross_references    (re-compute from existing data)
  - policy_developments/2026-W10        (re-run policy monitor for last week)

Run: python backfill_frontend_data.py
"""
import os, sys, re, asyncio
from datetime import datetime, timedelta

from db import init_db, get_dashboard_state, save_dashboard_state


def backfill_microscope_current(conn):
    """Create microscope_current from microscope_history + latest_briefing."""
    print("\n[1/4] Backfilling dashboard_state/microscope_current...")

    # Check if already exists
    existing = get_dashboard_state(conn, "microscope_current")
    if existing:
        print("  Already exists, skipping.")
        return

    # Get microscope history
    hist_doc = get_dashboard_state(conn, "microscope_history")
    if not hist_doc:
        print("  No microscope_history found, skipping.")
        return

    topics = hist_doc.get("topics", [])
    if not topics:
        print("  microscope_history is empty, skipping.")
        return

    latest_topic = topics[-1]
    topic_name = latest_topic.get("topic", "")
    topic_date = latest_topic.get("date", "")
    print(f"  Latest topic: '{topic_name}' ({topic_date})")

    # Try to extract microscope text from latest_briefing
    briefing_doc = get_dashboard_state(conn, "latest_briefing")
    microscope_text = ""
    if briefing_doc:
        content = briefing_doc.get("content", "")
        # Extract section 3 (Under the Microscope) from briefing
        patterns = [
            r'(?:#{2,3}\s*(?:\d+[\.\)]\s*)?Under the Microscope.*?\n)(.*?)(?=\n#{2,3}\s|\Z)',
            r'(?:Under the Microscope[:\s]*\n)(.*?)(?=\n#{2,3}\s|\Z)',
            r'(?:\*\*Under the Microscope\*\*.*?\n)(.*?)(?=\n\*\*|\Z)',
        ]
        for pat in patterns:
            m = re.search(pat, content, re.DOTALL | re.IGNORECASE)
            if m:
                microscope_text = m.group(1).strip()
                break

    if not microscope_text:
        microscope_text = f"Analysis on '{topic_name}' — see the weekly briefing for full details."

    # Guess sectors from topic name
    sector_keywords = {
        'oil': 'oil_gas', 'gas': 'oil_gas', 'energy': 'power_energy', 'pipeline': 'oil_gas',
        'mining': 'mining', 'mineral': 'mining', 'lithium': 'mining', 'uranium': 'mining',
        'housing': 'residential', 'residential': 'residential', 'condo': 'residential',
        'infrastructure': 'infrastructure', 'transit': 'transport_logistics', 'rail': 'transport_logistics',
        'healthcare': 'healthcare', 'hospital': 'healthcare', 'education': 'education',
        'manufacturing': 'manufacturing', 'defence': 'defence', 'military': 'defence',
        'telecom': 'telecom', 'agriculture': 'agriculture', 'forestry': 'forestry',
    }
    sectors = []
    topic_lower = topic_name.lower()
    for kw, sector in sector_keywords.items():
        if kw in topic_lower and sector not in sectors:
            sectors.append(sector)

    week_num = latest_topic.get("week_number", datetime.utcnow().isocalendar()[1])

    save_dashboard_state(conn, "microscope_current", {
        "topic": topic_name,
        "sectors": sectors,
        "text": microscope_text,
        "week": f"2026-W{week_num:02d}",
        "updated_at": topic_date or datetime.utcnow().isoformat(),
    })
    print(f"  Created microscope_current: {len(microscope_text)} chars, {len(sectors)} sectors")


def backfill_cross_references(conn):
    """Re-compute cross-reference data from existing trends."""
    print("\n[2/4] Backfilling dashboard_state/cross_references...")

    existing = get_dashboard_state(conn, "cross_references")
    if existing:
        print("  Already exists, skipping.")
        return

    try:
        from cross_reference import cross_reference_trends
        from sector_trends import compute_project_trends
        from indicator_trends import compute_indicator_trends

        print("  Computing sector trends...")
        sector_data = compute_project_trends(conn)
        print("  Computing indicator trends...")
        indicator_data = compute_indicator_trends(conn)
        print("  Computing cross-references...")
        xref_data = cross_reference_trends(indicator_data, sector_data)

        if xref_data and not xref_data.get("error"):
            save_dashboard_state(conn, "cross_references", {
                "data": xref_data,
                "updated_at": datetime.utcnow().isoformat(),
            })
            print(f"  Created cross_references document")
        else:
            print(f"  Cross-reference computation returned error or empty, skipping.")
    except ImportError as e:
        print(f"  Could not import required modules: {e}")
        print("  Skipping cross-references (will be populated on next pipeline run).")
    except Exception as e:
        print(f"  Error computing cross-references: {e}")


def backfill_policy_developments(conn):
    """Run policy monitor and store results for this week."""
    print("\n[3/4] Backfilling policy_developments...")

    week_key = datetime.utcnow().strftime("%Y-W%W")
    existing = get_dashboard_state(conn, f"policy_{week_key}")
    if existing:
        print(f"  {week_key} already exists, skipping.")
        return

    try:
        from provincial_policy_monitor import process_policy_feeds

        print("  Running policy monitor (last 7 days)...")
        articles = asyncio.run(process_policy_feeds(conn, since_days=7))

        if articles:
            save_dashboard_state(conn, f"policy_{week_key}", {
                "articles": [
                    {
                        "headline": a.get("headline", ""),
                        "snippet": a.get("snippet", ""),
                        "url": a.get("url", ""),
                        "published": a.get("published", ""),
                        "source": a.get("source", ""),
                        "scope": a.get("scope", ""),
                        "category": a.get("category", ""),
                    }
                    for a in articles
                ],
                "count": len(articles),
                "week": week_key,
                "updated_at": datetime.utcnow().isoformat(),
            })
            print(f"  Stored {len(articles)} policy articles for {week_key}")
        else:
            print("  No policy articles found.")
    except ImportError as e:
        print(f"  Could not import policy monitor: {e}")
        print("  Skipping (will be populated on next pipeline run).")
    except Exception as e:
        print(f"  Error running policy monitor: {e}")


def verify_existing_data(conn):
    """Check which documents already exist."""
    print("\n[4/4] Verifying existing SQLite data for frontend sections...")

    checks = [
        "microscope_history",
        "microscope_current",
        "cross_references",
        "latest_briefing",
        "tavily_credits",
    ]

    for key in checks:
        try:
            doc = get_dashboard_state(conn, key)
            if doc:
                updated = doc.get("updated_at", doc.get("date", "?"))
                print(f"  {key}: EXISTS (updated: {updated})")
            else:
                print(f"  {key}: MISSING")
        except Exception as e:
            print(f"  {key}: ERROR - {e}")

    # Check policy_developments
    try:
        week_key = datetime.utcnow().strftime("%Y-W%W")
        doc = get_dashboard_state(conn, f"policy_{week_key}")
        if doc:
            count = doc.get("count", "?")
            print(f"  policy_{week_key}: EXISTS ({count} articles)")
        else:
            print(f"  policy_{week_key}: MISSING")
    except Exception as e:
        print(f"  policy_developments: ERROR - {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Backfilling frontend data for new dashboard sections")
    print("=" * 60)

    conn = init_db()

    backfill_microscope_current(conn)
    backfill_cross_references(conn)
    backfill_policy_developments(conn)
    verify_existing_data(conn)

    conn.close()

    print("\n" + "=" * 60)
    print("Done! Refresh the dashboard to see data.")
    print("=" * 60)
