"""
weekly_briefing.py -- Weekly narrative synthesis and storage.

The crown jewel: combines all data dimensions into a single coherent
weekly intelligence briefing via Claude Sonnet.

Structure (8 sections, 1000-1500 words):
1. HEADLINE -- single most important development
2. MACRO PULSE -- national economic conditions
3. UNDER THE MICROSCOPE -- deep-dive on dominant story (pre-generated)
4. PROVINCIAL SPOTLIGHT -- one province with notable activity
5. SECTOR WATCH -- accelerating and decelerating sectors
6. PROJECT TRACKER -- new projects, status changes, completions
7. MARKETS & COMMODITIES -- price movements and project implications
8. LOOKING AHEAD -- upcoming events and what to watch
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Synthesis prompt ─────────────────────────────────────────────────

WEEKLY_SYNTHESIS_SYSTEM = """You are the editor-in-chief of Canada's premier \
economic intelligence briefing. Your readers are senior decision-makers: \
government analysts, investment managers, infrastructure developers, and \
policy advisors.

Your briefing must be:
- Insightful, not just informative (connect dots between data points)
- Specific (cite project names, dollar values, provinces, percentages)
- Analytical (what does this week's data tell us about current conditions?)
- Balanced (cover all regions, not just Toronto/Vancouver)
- Concise (1000-1500 words total)
- Sourced (every factual claim traces to data in the provided context)

Structure:
1. HEADLINE -- single most important development (1-2 sentences)
2. MACRO PULSE -- national economic conditions and what they mean for investment (150-200 words)
3. UNDER THE MICROSCOPE -- deep-dive on the dominant story of the week (200-300 words, pre-generated analysis provided below — incorporate it into the briefing flow, editing lightly for tone consistency)
4. PROVINCIAL SPOTLIGHT -- one province with notable activity this week (100-150 words)
5. SECTOR WATCH -- accelerating and decelerating sectors with context (150-200 words)
6. PROJECT TRACKER -- new projects, status changes, completions (150-200 words)
7. MARKETS & COMMODITIES -- what price movements mean for Canadian projects (100-150 words)
8. LOOKING AHEAD -- upcoming events and what to watch (100-150 words)

Do NOT use generic filler phrases like "in conclusion" or "it remains to be seen."
Every sentence should contain specific information or contextual insight."""


def _format_list(items):
    """Format a list of dicts for the prompt."""
    if not items:
        return "  (no data)"
    lines = []
    for item in items:
        lines.append(f"  - {json.dumps(item)}")
    return "\n".join(lines)


async def generate_weekly_briefing(
    project_trends,
    indicator_trends,
    cross_insights,
    policy_developments,
    market_commentary,
    upcoming_events,
    pre_event_analyses,
    microscope_text=None,
):
    """Generate the full weekly intelligence briefing via Claude Sonnet.

    This is the single most important Claude call of the week.
    Budget: ~100K input tokens, ~2K output tokens = ~$0.33 per briefing.
    """
    from claude_reasoning import reason_with_claude_tracked

    # Extract key stats safely
    overall = project_trends.get("overall", {}) if project_trends else {}
    period_trends = project_trends.get("period_trends", {}) if project_trends else {}
    weekly = period_trends.get("weekly", {})
    monthly = period_trends.get("monthly", {})
    quarterly = period_trends.get("quarterly", {})

    momentum = project_trends.get("sector_momentum", {}) if project_trends else {}
    geo_shifts = project_trends.get("geographic_shifts", {}) if project_trends else {}

    accel = [f"{s}: {v.get('current_count', 0)} projects (+{v.get('change', 0)})"
             for s, v in momentum.items() if v.get("label") == "accelerating"]
    decel = [f"{s}: {v.get('current_count', 0)} projects ({v.get('change', 0)})"
             for s, v in momentum.items() if v.get("label") == "decelerating"]
    growing = [f"{p}: {v.get('current_share', 0):.1%} share ({v.get('shift', 0):+.1%})"
               for p, v in geo_shifts.items() if v.get("direction") == "growing"]

    # Format indicator trends
    ind_lines = []
    for k, v in (indicator_trends or {}).items():
        if k.startswith("_"):
            continue
        d = v.get("direction", "unknown")
        if d in ("rising", "falling"):
            ind_lines.append(
                f"- {k.replace('_', ' ').title()}: {d} "
                f"({v.get('pct_change', 0):+.1f}%, streak: {v.get('streak', 0)})"
            )

    # Cross-reference hints
    hints = (cross_insights or {}).get("narrative_hints", [])

    # Policy developments summary
    policy_text = "No major policy developments this week."
    if policy_developments:
        policy_items = []
        for p in policy_developments[:5]:
            if isinstance(p, dict):
                headline = p.get("headline", p.get("text", ""))[:200]
                cat = p.get("category", "unknown")
                scope = p.get("scope", "unknown")
                policy_items.append(f"[{scope}/{cat}] {headline}")
        if policy_items:
            policy_text = "\n".join(policy_items)

    user_prompt = f"""Generate this week's Canadian Macro Strategic Dashboard briefing.

=== PROJECT PIPELINE TRENDS ===
Total tracked: {overall.get('total_projects', 0)} projects (${overall.get('total_value_millions', 0) / 1000:.1f}B)
Week-over-week: {weekly.get('count_change', 0):+d} projects ({weekly.get('count_pct_change', 0):+.1f}%)
Month-over-month: {monthly.get('count_change', 0):+d} projects ({monthly.get('count_pct_change', 0):+.1f}%)
Quarter-over-quarter: {quarterly.get('count_change', 0):+d} projects ({quarterly.get('count_pct_change', 0):+.1f}%)

Sector momentum (accelerating):
{chr(10).join('  - ' + s for s in accel) if accel else '  None'}

Sector momentum (decelerating):
{chr(10).join('  - ' + s for s in decel) if decel else '  None'}

Geographic shifts (growing share):
{chr(10).join('  - ' + g for g in growing) if growing else '  None'}

Pipeline health:
  Active: {overall.get('active_projects', 0)}, Completed: {overall.get('completed', 0)}, Cancelled: {overall.get('cancelled', 0)}
  Value coverage: {overall.get('value_coverage', 0):.0%}

=== ECONOMIC INDICATORS ===
{chr(10).join(ind_lines) if ind_lines else '- No significant indicator moves'}

=== CROSS-REFERENCE INSIGHTS ===
{chr(10).join('- ' + h for h in hints[:5]) if hints else '- No clear correlations identified'}

=== POLICY DEVELOPMENTS ===
{policy_text}

=== MARKET COMMENTARY ===
{market_commentary if isinstance(market_commentary, str) else (market_commentary or {}).get('text', 'No market commentary available.')}

=== UPCOMING EVENTS (next 14 days) ===
{json.dumps(upcoming_events[:8], indent=2) if upcoming_events else 'No high-significance events.'}

=== PRE-EVENT ANALYSES ===
{json.dumps(pre_event_analyses[:3], indent=2) if pre_event_analyses else 'None generated.'}

=== UNDER THE MICROSCOPE (pre-generated deep-dive — incorporate as section 3) ===
{microscope_text if microscope_text else 'No microscope analysis available this week. Skip section 3 and proceed with sections 1-2, 4-8.'}

Generate the weekly briefing following the 8-section structure in your system instructions."""

    return await reason_with_claude_tracked(
        WEEKLY_SYNTHESIS_SYSTEM,
        user_prompt,
        task_name="weekly_briefing",
        max_tokens=3000,
    )


async def store_and_distribute_briefing(conn, briefing_result):
    """Store briefing in SQLite and make available to frontend.

    Args:
        conn: sqlite3.Connection from db.py
        briefing_result: dict from reason_with_claude_tracked (text, tokens, cost)
    """
    from db import save_briefing, save_dashboard_state

    if not briefing_result:
        logger.warning("No briefing to store")
        return

    text = briefing_result.get("text", "")
    now = datetime.utcnow()

    doc = {
        "date": now.strftime("%Y-%m-%d"),
        "week_number": now.isocalendar()[1],
        "year": now.year,
        "content": text,
        "input_tokens": briefing_result.get("input_tokens", 0),
        "output_tokens": briefing_result.get("output_tokens", 0),
        "cost_usd": briefing_result.get("cost_usd", 0),
        "created_at": now.isoformat(),
    }

    try:
        # Permanent record in weekly_briefings table
        save_briefing(conn, doc)

        # Latest for frontend in dashboard_state
        save_dashboard_state(conn, "latest_briefing", {
            "content": text,
            "date": doc["date"],
            "week_number": doc["week_number"],
            "cost_usd": doc["cost_usd"],
        })

        logger.info(f"Weekly briefing stored: week {doc['week_number']}, "
                     f"{len(text)} chars, ${doc['cost_usd']:.4f}")
    except Exception as e:
        logger.warning(f"Failed to store briefing: {e}")
