"""
weekly_trend_report.py -- Generate narrative trend report using Claude Sonnet.

Takes computed trends from sector_trends, indicator_trends, and
cross_reference modules and generates a natural-language summary
suitable for the newsletter.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def _build_trend_prompt(sector_data, indicator_data, xref_data):
    """Build the prompt for Claude Sonnet narrative generation."""

    # Extract key stats
    overall = sector_data.get("overall", {})
    momentum = sector_data.get("sector_momentum", {})
    geo_shifts = sector_data.get("geographic_shifts", {})
    weekly = sector_data.get("period_trends", {}).get("weekly", {})
    monthly = sector_data.get("period_trends", {}).get("monthly", {})

    accel_sectors = [s for s, v in momentum.items() if v.get("label") == "accelerating"]
    decel_sectors = [s for s, v in momentum.items() if v.get("label") == "decelerating"]
    growing_provs = [p for p, v in geo_shifts.items() if v.get("direction") == "growing"]
    shrinking_provs = [p for p, v in geo_shifts.items() if v.get("direction") == "shrinking"]

    # Indicator summaries
    ind_lines = []
    for k, v in (indicator_data or {}).items():
        if k.startswith("_"):
            continue
        d = v.get("direction", "unknown")
        if d in ("rising", "falling"):
            ind_lines.append(f"- {k.replace('_', ' ').title()}: {d} "
                           f"({v.get('pct_change', 0):+.1f}%, streak: {v.get('streak', 0)})")

    # Cross-reference narrative hints
    hints = (xref_data or {}).get("narrative_hints", [])

    prompt = f"""You are an economist writing the weekly trend analysis section for a Canadian
economic intelligence newsletter. Write 3-4 concise paragraphs covering:

1. Pipeline overview: {overall.get('total_projects', 0)} projects tracked,
   ${overall.get('total_value_millions', 0):.0f}M total value,
   {overall.get('active_projects', 0)} active.
   Weekly: {weekly.get('count_change', 0):+d} projects ({weekly.get('count_pct_change', 0):+.1f}%).
   Monthly: {monthly.get('count_change', 0):+d} projects ({monthly.get('count_pct_change', 0):+.1f}%).

2. Sector momentum:
   Accelerating: {', '.join(accel_sectors) if accel_sectors else 'None'}
   Decelerating: {', '.join(decel_sectors) if decel_sectors else 'None'}

3. Geographic shifts:
   Growing share: {', '.join(growing_provs) if growing_provs else 'None'}
   Shrinking share: {', '.join(shrinking_provs) if shrinking_provs else 'None'}

4. Macro indicators:
{chr(10).join(ind_lines) if ind_lines else '- No significant moves'}

5. Cross-reference insights:
{chr(10).join('- ' + h for h in hints[:5]) if hints else '- No clear correlations'}

Guidelines:
- Use precise numbers. Don't speculate beyond the data.
- Mention specific provinces and sectors by name.
- Note any divergences between macro signals and pipeline activity.
- Keep total output under 300 words.
- Use professional, analytical tone. No marketing language.
- Do NOT use bullet points. Write flowing paragraphs.
"""
    return prompt


def generate_trend_report(sector_data, indicator_data, xref_data, db=None):
    """Generate narrative trend report using Claude Sonnet.

    Falls back to a template-based summary if Claude is unavailable.

    Args:
        sector_data: output from sector_trends.compute_project_trends()
        indicator_data: output from indicator_trends.compute_indicator_trends()
        xref_data: output from cross_reference.cross_reference_trends()
        db: optional Firestore client to store the report

    Returns:
        dict with report text and metadata
    """
    print("\n[REPORT] Generating weekly trend report...")

    prompt = _build_trend_prompt(sector_data, indicator_data, xref_data)

    narrative = None

    # Generate narrative via Claude Sonnet
    try:
        from claude_reasoning import reason_sync
        result = reason_sync(
            "You are an economist writing a trend report for a Canadian economic dashboard.",
            prompt,
            task_name="trend_report",
        )
        narrative = result["text"] if result else None
        if narrative:
            print("  [REPORT] Generated via Claude Sonnet")
    except Exception as e:
        logger.warning(f"Claude Sonnet narrative generation failed: {e}")

    # Fallback: template-based summary
    if not narrative:
        narrative = _template_fallback(sector_data, indicator_data, xref_data)
        print("  [REPORT] Using template fallback")

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "narrative": narrative,
        "source": "claude_sonnet" if narrative and "template" not in str(narrative).lower() else "template",
        "data_summary": {
            "total_projects": sector_data.get("total_projects", 0),
            "total_value_millions": sector_data.get("overall", {}).get("total_value_millions", 0),
            "correlations": len((xref_data or {}).get("correlations", [])),
            "divergences": len((xref_data or {}).get("divergences", [])),
        },
    }

    # Optionally store in Firestore
    if db:
        try:
            week_key = datetime.utcnow().strftime("%Y-W%W")
            db.collection("trend_reports").document(week_key).set(report)
            print(f"  [REPORT] Stored as trend_reports/{week_key}")
        except Exception as e:
            logger.warning(f"Failed to store trend report: {e}")

    return report


def _template_fallback(sector_data, indicator_data, xref_data):
    """Generate a basic template-based trend summary."""
    overall = sector_data.get("overall", {})
    momentum = sector_data.get("sector_momentum", {})
    monthly = sector_data.get("period_trends", {}).get("monthly", {})

    accel = [s for s, v in momentum.items() if v.get("label") == "accelerating"]
    decel = [s for s, v in momentum.items() if v.get("label") == "decelerating"]

    lines = []
    lines.append(
        f"The Canadian project pipeline tracks {overall.get('total_projects', 0)} projects "
        f"with a combined value of ${overall.get('total_value_millions', 0):.0f}M. "
        f"Of these, {overall.get('active_projects', 0)} are active."
    )

    m_change = monthly.get("count_change", 0)
    if m_change != 0:
        direction = "up" if m_change > 0 else "down"
        lines.append(
            f"Month-over-month, project announcements are {direction} "
            f"by {abs(m_change)} ({monthly.get('count_pct_change', 0):+.1f}%)."
        )

    if accel:
        lines.append(f"Accelerating sectors: {', '.join(accel[:5])}.")
    if decel:
        lines.append(f"Decelerating sectors: {', '.join(decel[:5])}.")

    hints = (xref_data or {}).get("narrative_hints", [])
    if hints:
        lines.append(hints[0] + ".")

    return " ".join(lines)
