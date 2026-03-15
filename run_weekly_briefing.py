"""
run_weekly_briefing.py — Standalone runner for weekly briefing generation.

Pulls latest data from SQLite, generates the briefing via Claude Sonnet,
and stores it back in SQLite under dashboard_state/latest_briefing and
weekly_briefings table.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from db import init_db, get_all_projects, get_latest_indicators, get_dashboard_state

conn = init_db()


def _get_latest_newsletter():
    """Fetch the most recent newsletter from SQLite dashboard_state."""
    try:
        data = get_dashboard_state(conn, 'newsletter_latest')
        if data:
            return data
    except Exception as e:
        print(f"  [WARN] Newsletter fetch failed: {e}")
    return {}


def _build_market_commentary(newsletter):
    """Extract market commentary from the newsletter."""
    if not newsletter:
        return "No market commentary available."

    commodities = newsletter.get('commodities', {})
    if not commodities:
        return "No commodity data available."

    lines = []
    for name, data in list(commodities.items())[:10]:
        if isinstance(data, dict):
            price = data.get('price', data.get('value', 'N/A'))
            change = data.get('change_pct', data.get('pct_change', ''))
            if change:
                lines.append(f"{name}: ${price} ({change}%)")
            else:
                lines.append(f"{name}: ${price}")

    return "\n".join(lines) if lines else "Market data collected but no significant moves."


async def main():
    print("=" * 60)
    print("WEEKLY BRIEFING GENERATION")
    print("=" * 60)

    # 1. Gather data
    print("\n[1/4] Gathering data from SQLite...")

    newsletter = _get_latest_newsletter()
    print(f"  Newsletter: {newsletter.get('updated_at', 'unknown')}")

    # Project trends — full pipeline computation
    from sector_trends import compute_project_trends
    project_trends = compute_project_trends(conn)
    total = project_trends.get('total_projects', 0)
    total_val = project_trends.get('overall', {}).get('total_value_millions', 0)
    print(f"  Project stats: {total} projects, ${total_val:,.0f}M total value")

    # Indicator trends — full computation
    from indicator_trends import compute_indicator_trends
    indicator_trends = compute_indicator_trends(conn)
    print(f"  Indicator trends: {len(indicator_trends)} indicators")

    # Cross-reference insights — compute inline
    from cross_reference import cross_reference_trends
    cross_insights = cross_reference_trends(indicator_trends, project_trends)
    n_corr = len(cross_insights.get('correlations', []))
    n_div = len(cross_insights.get('divergences', []))
    print(f"  Cross-reference: {n_corr} correlations, {n_div} divergences")

    market_commentary = _build_market_commentary(newsletter)

    # 2. Generate briefing
    print("\n[2/4] Generating weekly briefing via Claude Sonnet...")
    from weekly_briefing import generate_weekly_briefing, store_and_distribute_briefing

    briefing_result = await generate_weekly_briefing(
        project_trends=project_trends,
        indicator_trends=indicator_trends,
        cross_insights=cross_insights,
        policy_developments=[],
        market_commentary=market_commentary,
        upcoming_events=[],
        pre_event_analyses=[],
    )

    if briefing_result:
        text = briefing_result.get('text', '')
        cost = briefing_result.get('cost_usd', 0)
        print(f"  Briefing generated: {len(text)} chars, ${cost:.4f}")
        print(f"\n--- BRIEFING PREVIEW (first 500 chars) ---")
        print(text[:500])
        print("--- END PREVIEW ---")
    else:
        print("  ERROR: No briefing generated")
        return

    # 3. Generate infographic directives
    print("\n[3/5] Generating infographic directives via Claude Sonnet...")
    from weekly_briefing import generate_infographic_directives
    exec_summary = newsletter.get('executive_summary', '') if newsletter else ''
    infographic_directives = await generate_infographic_directives(
        executive_summary=exec_summary,
        indicator_trends=indicator_trends,
        project_trends=project_trends,
        market_commentary=market_commentary,
    )
    if infographic_directives:
        from db import save_dashboard_state
        save_dashboard_state(conn, 'infographic_directives', infographic_directives)
        print(f"  Generated {len(infographic_directives)} infographic directives")
    else:
        print("  No infographic directives generated (will use defaults)")

    # 4. Store in SQLite
    print("\n[4/5] Storing briefing in SQLite...")
    await store_and_distribute_briefing(conn, briefing_result)
    print("  Stored in weekly_briefings table and dashboard_state/latest_briefing")

    # 5. Summary
    now = datetime.now(timezone.utc)
    print(f"\n[5/5] Done!")
    print(f"  Briefing date: {now.strftime('%Y-%m-%d')}")
    print(f"  Week number: {now.isocalendar()[1]}")
    print(f"  Cost: ${cost:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
