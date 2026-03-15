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


def _format_signal_context(signal_context):
    """Format Prompts 11-19 signal data for the briefing prompt."""
    if not signal_context:
        return ""

    parts = []

    # Policy summary
    policy_summary = signal_context.get('policy_summary', {})
    policy_items = signal_context.get('policy_items', [])
    if policy_summary or policy_items:
        p_lines = []
        for item in policy_items[:5]:
            title = item.get('title', '')[:150]
            cats = ', '.join(item.get('policy_categories', [])[:3])
            affected = item.get('affected_projects_total', 0)
            prov = item.get('province', '')
            prov_note = f" [{prov}]" if prov else ''
            p_lines.append(f"  - [{cats}]{prov_note} {title} ({affected} projects in scope)")
        if p_lines:
            parts.append(
                "=== POLICY TRACKER ===\n"
                "Include significant policy developments in the relevant briefing sections:\n"
                "- New legislation affecting housing → Section 1 (Headline) if major, or Section 5 (Sector Watch)\n"
                "- Federal budget items → Section 2 (Macro Pulse)\n"
                "- Provincial policy → Section 4 (Provincial Spotlight) if the featured province is affected\n"
                "- Trade policy → Section 7 (Markets & Commodities) if it affects commodity trade\n"
                "- Upcoming regulatory deadlines → Section 8 (Looking Ahead)\n"
                "Report what happened and how many projects are in scope. No predictions.\n"
                + '\n'.join(p_lines)
            )

    # Hiring spikes
    spikes = signal_context.get('job_spikes', [])[:5]
    if spikes:
        s_lines = [
            f"  - {s.get('employer', '?')} in {s.get('location', '?')} "
            f"({s.get('sector', '?')}): {s.get('current_count', 0)} postings, "
            f"{s.get('multiplier', 0):.1f}x normal"
            for s in spikes
        ]
        parts.append(
            "=== HIRING SIGNALS ===\n"
            "Hiring spikes indicate project mobilization. Include in:\n"
            "- Section 6 (Project Tracker) — \"Hiring spike at [employer] in [location] suggests [project] is mobilizing\"\n"
            "- Section 4 (Provincial Spotlight) if concentrated in the featured province\n"
            + '\n'.join(s_lines)
        )

    # Procurement awards ≥$10M
    contracts = [
        c for c in signal_context.get('procurement_contracts', [])
        if c.get('value', 0) >= 10_000_000
    ][:5]
    if contracts:
        c_lines = []
        for c in contracts:
            val = c.get('value', 0)
            val_str = f"${val / 1_000_000:.0f}M" if val else 'undisclosed'
            desc = c.get('description', c.get('title', ''))[:150]
            prov = c.get('province', '')
            prov_note = f" [{prov}]" if prov else ''
            c_lines.append(f"  -{prov_note} {desc} — {val_str}")
        parts.append(
            "=== PROCUREMENT AWARDS ===\n"
            "Government contract awards confirm project advancement. Include in:\n"
            "- Section 6 (Project Tracker) — \"[Department] awarded $[value] to [vendor] for [description]\"\n"
            "- Section 5 (Sector Watch) if concentrated in a specific sector\n"
            + '\n'.join(c_lines)
        )

    # IAAC status changes
    iaac = signal_context.get('iaac_status_changes', [])
    if iaac:
        i_lines = [
            f"  - {ch.get('project_name', '?')}: "
            f"{ch.get('old_status', '?')} → {ch.get('new_status', '?')}"
            f" ({ch.get('province', '')})"
            for ch in iaac[:5]
        ]
        parts.append(
            "=== ASSESSMENT STATUS CHANGES ===\n"
            "Federal IAAC transitions. Include in:\n"
            "- Section 6 (Project Tracker) — \"[Project] advanced from [old] to [new] in IAAC assessment\"\n"
            + '\n'.join(i_lines)
        )

    # Regulatory signals
    reg_signals = signal_context.get('regulatory_signals', [])
    if reg_signals:
        r_lines = [
            f"  - {r.get('title', '?')[:150]} — {r.get('regulatory_signal', {}).get('action', '?')}"
            for r in reg_signals[:5]
        ]
        parts.append(
            "=== REGULATORY DECISIONS ===\n"
            "Tribunal and court decisions. Include in:\n"
            "- Section 6 (Project Tracker) — \"[Tribunal] [approved/denied] [project]\"\n"
            + '\n'.join(r_lines)
        )

    if not parts:
        return ""

    return (
        "\n\n" + '\n\n'.join(parts) + "\n\n"
        "IMPORTANT: All new data sources follow the same editorial rules. "
        "State what happened, cite the source, reference specific numbers and project names. "
        "No predictions, no 'good news/bad news' framing, no recommendations."
    )


async def generate_weekly_briefing(
    project_trends,
    indicator_trends,
    cross_insights,
    policy_developments,
    market_commentary,
    upcoming_events,
    pre_event_analyses,
    microscope_text=None,
    signal_context=None,
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

{_format_signal_context(signal_context)}

Generate the weekly briefing following the 8-section structure in your system instructions."""

    from claude_reasoning import OPUS_WRITING_MODEL
    return await reason_with_claude_tracked(
        WEEKLY_SYNTHESIS_SYSTEM,
        user_prompt,
        task_name="weekly_briefing",
        max_tokens=3000,
        model=OPUS_WRITING_MODEL,
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


async def generate_infographic_directives(
    executive_summary: str,
    indicator_trends: dict,
    project_trends: dict,
    market_commentary,
):
    """Generate 3-4 infographic specs tied to this week's key stories.

    Uses Claude Sonnet (~$0.01 per call) to read the executive summary
    and produce chart configurations that visualize the week's main points.
    The frontend renders these dynamically instead of static default charts.
    """
    from claude_reasoning import reason_with_claude_tracked, SONNET_REASONING_MODEL

    overall = project_trends.get("overall", {}) if project_trends else {}
    momentum = project_trends.get("sector_momentum", {}) if project_trends else {}

    # Build indicator summary
    ind_lines = []
    for k, v in (indicator_trends or {}).items():
        if k.startswith("_"):
            continue
        val = v.get("latest_value", v.get("value"))
        prev = v.get("previous_value", v.get("prev"))
        d = v.get("direction", "")
        if val is not None:
            ind_lines.append(f"{k}: {val} (prev: {prev}, {d})")

    # Sector momentum
    sector_lines = []
    for s, v in momentum.items():
        label = v.get("label", "")
        count = v.get("current_count", 0)
        change = v.get("change", 0)
        sector_lines.append(f"{s}: {count} projects ({change:+d}, {label})")

    market_text = market_commentary if isinstance(market_commentary, str) else (
        market_commentary or {}
    ).get("text", "")

    prompt = f"""You are a data visualization editor for a Canadian economic intelligence newsletter.

Based on this week's executive summary and data, generate exactly 4 infographic directives.
Each infographic should visualize a key point from this week's briefing to drive the story home.

EXECUTIVE SUMMARY:
{executive_summary[:2000] if executive_summary else 'No summary available.'}

KEY INDICATORS:
{chr(10).join(ind_lines[:20]) if ind_lines else 'No indicator data.'}

SECTOR MOMENTUM:
{chr(10).join(sector_lines[:15]) if sector_lines else 'No momentum data.'}

MARKET COMMENTARY:
{market_text[:500] if market_text else 'No market commentary.'}

PROJECT STATS:
Total: {overall.get('total_projects', 0)}, Active: {overall.get('active_projects', 0)}, Value: ${overall.get('total_value_millions', 0)/1000:.1f}B

Return a JSON array of exactly 4 objects. Each object must have:
- "type": one of "bar", "horizontal_bar", "doughnut", "line"
- "title": short chart title (3-6 words)
- "subtitle": one sentence connecting the chart to this week's story
- "data_source": one of "indicators", "commodities", "projects", "sectors"
- "metric": what to measure — "value", "count", "pct_change", "price"
- "filter": object with optional keys: "names" (array of indicator/commodity names to include), "statuses" (array), "sectors" (array), "provinces" (array), "top_n" (number)
- "group_by": one of "name", "status", "sector", "province", "category"
- "sort": "desc" or "asc"
- "insight": one sentence insight to display below the chart

Rules:
- Each chart should visualize a DIFFERENT aspect (don't repeat topics)
- At least one must be about indicators/macro data
- At least one must be about commodities or markets
- Subtitles must reference specific numbers from the data
- Keep it factual — no editorializing

Return ONLY the JSON array, no other text."""

    try:
        result = await reason_with_claude_tracked(
            "You are a data visualization editor. Return only valid JSON.",
            prompt,
            task_name="infographic_directives",
            max_tokens=1000,
            model=SONNET_REASONING_MODEL,
        )
        text = (result or {}).get("text", "").strip()
        # Extract JSON from response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            directives = json.loads(text[start:end])
            if isinstance(directives, list) and len(directives) >= 2:
                logger.info(f"Generated {len(directives)} infographic directives")
                return directives
        logger.warning(f"Invalid infographic directives format: {text[:200]}")
        return []
    except Exception as e:
        logger.warning(f"Infographic directives generation failed: {e}")
        return []
