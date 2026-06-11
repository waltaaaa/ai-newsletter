"""
under_the_microscope.py — Deep-dive topic selection and analysis for weekly briefing.

Automatically selects the dominant story of the week and generates a 200-300 word
analysis focused on Canadian economic and project impacts. Inserted as section 3
of the weekly briefing between MACRO PULSE and PROVINCIAL SPOTLIGHT.

Cost: 1 Gemini Flash query (topic selection) + 1 Claude Sonnet call (~$0.20/week).
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Topic selection ────────────────────────────────────────────────────────

TOPIC_SELECTION_PROMPT = """Analyze these article headlines from Canadian news this week.
Identify the single most dominant global or national story that would most
significantly affect Canadian capital investment, infrastructure, or economic conditions.

Consider:
- Stories appearing across multiple publications and multiple days
- Stories that caused significant commodity price or interest rate movements
- Stories that could affect the largest number of active Canadian capital projects
- Both domestic (e.g., federal budget, policy change) and international (e.g., trade war, conflict) stories

Headlines:
{headlines}

Return ONLY a JSON object:
{{
    "topic": "Short topic name (5-10 words)",
    "description": "One sentence describing the story and why it matters for Canadian investment",
    "estimated_article_count": <number of headlines related to this topic>,
    "affected_sectors": ["list", "of", "affected", "NAICS", "sectors"],
    "affected_provinces": ["list", "of", "province", "codes"]
}}"""


async def select_microscope_topic(conn, rss_articles, indicator_trends, cross_insights,
                                  signal_context=None):
    """Select this week's Under the Microscope topic.

    Selection criteria (weighted):
    1. Manual override from dashboard_state/microscope_override
    2. Highest-volume news story in RSS feeds this week
    3. Story with largest indicator/commodity moves
    4. Story affecting the most tracked projects
    5. Multi-signal convergence boost (policy + hiring + procurement + IAAC)

    Args:
        conn: sqlite3.Connection from db.py
        rss_articles: list of article dicts from RSS feeds
        indicator_trends: dict from compute_indicator_trends()
        cross_insights: dict from cross_reference_trends()
        signal_context: dict with policy_items, job_spikes, procurement_contracts,
                        iaac_status_changes from Prompts 11-19

    Returns: dict with topic, description, related_articles, weeks_running, history
    """
    from db import get_dashboard_state, save_dashboard_state

    # Check for manual override first
    try:
        override = get_dashboard_state(conn, "microscope_override")
        if override and isinstance(override, dict):
            if override.get("active") and override.get("topic"):
                topic = override["topic"]
                logger.info(f"Microscope override: {topic}")
                # Deactivate override after use
                override["active"] = False
                save_dashboard_state(conn, "microscope_override", override)
                return await _build_topic_context(
                    conn, topic,
                    override.get("description", ""),
                    override.get("affected_sectors", []),
                    override.get("affected_provinces", []),
                    rss_articles,
                )
    except Exception as e:
        logger.warning(f"Microscope override check failed: {e}")

    # Automated selection via Groq LLaMA 3.3 70B
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_headlines = []
    for article in (rss_articles or []):
        title = article.get("title", "")
        if title:
            recent_headlines.append(title)

    if not recent_headlines:
        logger.warning("No headlines for microscope topic selection")
        return None

    # Use Groq for topic identification (free tier)
    try:
        import groq_client

        # Build signal summary for topic selection
        _sig_lines = _format_signal_summary_for_topic(signal_context or {})

        prompt = TOPIC_SELECTION_PROMPT.format(
            headlines="\n".join(f"- {h}" for h in recent_headlines[:200])
        )
        if _sig_lines:
            prompt += f"\n\nAdditional signal data (consider when selecting topic):\n{_sig_lines}"
        text = groq_client.generate(
            "You are a Canadian economic analyst. Return only valid JSON.",
            prompt,
            max_tokens=2048,
        )
        if not text:
            logger.warning("Groq returned empty response for microscope topic selection")
            return None
        text = text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        # Parse JSON response
        topic_data = json.loads(text)
        topic = topic_data.get("topic", "")
        description = topic_data.get("description", "")
        affected_sectors = topic_data.get("affected_sectors", [])
        affected_provinces = topic_data.get("affected_provinces", [])

        if not topic:
            logger.warning("Groq returned empty topic")
            return None

        # Calculate signal convergence boost
        sig_boost = calculate_signal_boost(affected_sectors, signal_context or {})
        if sig_boost:
            logger.info(f"Microscope topic signal boost: +{sig_boost}")

        logger.info(f"Microscope topic selected: {topic}")
        return await _build_topic_context(
            conn, topic, description, affected_sectors, affected_provinces, rss_articles
        )

    except json.JSONDecodeError:
        # Try to extract topic from non-JSON response
        logger.warning(f"Groq returned non-JSON for microscope topic: {text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Microscope topic selection failed: {e}")
        return None


async def _build_topic_context(conn, topic, description, affected_sectors,
                                affected_provinces, rss_articles):
    """Build comprehensive context for the selected topic."""
    from db import get_dashboard_state

    # Find related articles by checking if topic words appear in titles
    topic_words = set(topic.lower().split())
    # Remove common words
    topic_words -= {"the", "and", "of", "in", "on", "for", "to", "a", "an", "is", "are"}

    related_articles = []
    for article in (rss_articles or []):
        title = article.get("title", "").lower()
        if any(w in title for w in topic_words if len(w) > 3):
            related_articles.append(article)

    # Check microscope_history for continuity
    weeks_running = 0
    history = []
    try:
        history_data = get_dashboard_state(conn, "microscope_history")
        if history_data and isinstance(history_data, dict):
            history = history_data.get("topics", [])
            # Check how many consecutive weeks this topic has run
            for entry in reversed(history):
                if _topics_match(entry.get("topic", ""), topic):
                    weeks_running += 1
                else:
                    break
    except Exception:
        pass

    return {
        "topic": topic,
        "description": description,
        "affected_sectors": affected_sectors,
        "affected_provinces": affected_provinces,
        "related_articles": related_articles[:10],
        "weeks_running": weeks_running,
        "history": history[-12:],  # last 12 weeks
    }


def _topics_match(topic_a, topic_b):
    """Check if two topic strings refer to the same story."""
    a = set(topic_a.lower().split()) - {"the", "and", "of", "in", "on", "for"}
    b = set(topic_b.lower().split()) - {"the", "and", "of", "in", "on", "for"}
    if not a or not b:
        return False
    overlap = len(a & b) / min(len(a), len(b))
    return overlap >= 0.5


# ── Signal helpers for topic selection ─────────────────────────────────────


def _format_signal_summary_for_topic(signal_context):
    """Format signal data as a concise summary for topic selection."""
    if not signal_context:
        return ''
    parts = []
    spikes = signal_context.get('job_spikes', [])
    if spikes:
        sectors = {}
        for s in spikes:
            sec = s.get('sector', 'unknown')
            sectors[sec] = sectors.get(sec, 0) + 1
        parts.append("Hiring spikes: " + ", ".join(f"{v} in {k}" for k, v in sectors.items()))
    contracts = signal_context.get('procurement_contracts', [])
    # (value can be None on tender-notice rows — `or 0` so the comparison
    # can't TypeError; `.get('value', 0)` returns None when the key exists)
    big = [c for c in contracts if (c.get('value') or 0) >= 10_000_000]
    if big:
        parts.append(f"Procurement: {len(big)} contracts ≥$10M awarded")
    iaac = signal_context.get('iaac_status_changes', [])
    if iaac:
        parts.append(f"IAAC: {len(iaac)} assessment status changes")
    policy = signal_context.get('policy_items', [])
    if policy:
        cats = {}
        for p in policy:
            for c in p.get('policy_categories', []):
                cats[c] = cats.get(c, 0) + 1
        parts.append("Policy: " + ", ".join(f"{v} {k}" for k, v in cats.items()))
    return "\n".join(f"- {p}" for p in parts) if parts else ''


def calculate_signal_boost(affected_sectors, signal_context):
    """Calculate a scoring boost for topics with multi-signal convergence.

    A sector with simultaneous policy changes, hiring spikes, and procurement
    awards is a stronger microscope candidate.

    Returns: int boost score
    """
    if not signal_context or not affected_sectors:
        return 0

    boost = 0
    for sector in affected_sectors:
        # Policy convergence
        policy_items = [
            p for p in signal_context.get('policy_items', [])
            if sector in p.get('affected_sectors', [])
        ]
        boost += len(policy_items) * 2

        # Hiring activity
        hiring_spikes = [
            s for s in signal_context.get('job_spikes', [])
            if s.get('sector') == sector
        ]
        boost += len(hiring_spikes) * 3

        # Procurement activity
        procurement = [
            c for c in signal_context.get('procurement_contracts', [])
            if any(p.get('sector') == sector for p in c.get('linked_projects', []))
        ]
        boost += len(procurement) * 2

        # IAAC status changes
        iaac_changes = [
            c for c in signal_context.get('iaac_status_changes', [])
            if c.get('sector') == sector
        ]
        boost += len(iaac_changes) * 4

    return boost


# ── Analysis generation ────────────────────────────────────────────────────

MICROSCOPE_SYSTEM = """You are a senior Canadian economic analyst writing the "Under the Microscope" \
section of a weekly intelligence briefing. This section provides a deep-dive on the single \
most significant story of the week, analyzed specifically through Canadian economic impact.

Structure your analysis as:
1. WHAT HAPPENED / WHAT CHANGED — factual summary (2-3 sentences)
2. NEW DEVELOPMENTS THIS WEEK — what specifically changed in the past 7 days
3. CANADIAN IMPACT — broken down by:
   - Affected sectors (with project counts and values from database)
   - Affected provinces (which regions are most exposed)
   - Commodity/indicator implications (with current data)
4. PROJECTS IN THE CROSSHAIRS — name 2-5 specific tracked projects that are directly \
affected, with brief explanation of how (e.g., "LNG Canada Phase 1 ($40B) faces potential \
export headwinds" or "Irving CSC program ($77B) may see acceleration")
5. WHAT TO WATCH NEXT WEEK — one forward-looking signal for readers

Total length: 200-300 words. Be specific. Use numbers. Name projects. No filler phrases."""


async def generate_microscope_analysis(topic_context, project_data, indicator_data):
    """Generate the Under the Microscope deep-dive using Claude Sonnet.

    Args:
        topic_context: dict from select_microscope_topic()
        project_data: list of project dicts that may be affected
        indicator_data: dict of relevant indicator movements

    Returns: dict with text, input_tokens, output_tokens, cost_usd or None
    """
    if not topic_context or not topic_context.get("topic"):
        return None

    from claude_reasoning import reason_with_claude_tracked

    continuity_note = ""
    weeks = topic_context.get("weeks_running", 0)
    if weeks > 0:
        continuity_note = (
            f"\n\nNOTE: This is week {weeks + 1} covering this topic. "
            f"Reference that this story continues from prior weeks and focus "
            f"ONLY on genuinely new developments. Do not repeat earlier analysis."
        )

    # Red-team F3 (2026-06-11): this prompt is sent through `claude -p`, which
    # on this host fails (exit 1, empty stderr) on prompts over ~4KB. The old
    # build (15 full project dicts + indicators, both indent=2) ran 4-7KB and
    # silently no-op'd the whole microscope step. Compact every block, keep
    # only the project fields the analysis cites, and shrink until under budget.
    def _slim_project(p):
        return {k: p.get(k) for k in
                ("name", "province", "value", "status", "sector") if p.get(k)}

    def _build_prompt(n_projects, n_titles, title_len, desc_len, ind_len):
        projects_block = (
            json.dumps([_slim_project(p) for p in project_data[:n_projects]],
                       separators=(",", ":"))
            if project_data else "No matching projects identified.")
        indicators_block = (
            json.dumps(indicator_data, separators=(",", ":"))[:ind_len]
            if indicator_data else "No significant indicator changes.")
        titles_block = json.dumps(
            [a.get('title', '')[:title_len]
             for a in topic_context.get('related_articles', [])[:n_titles]],
            separators=(",", ":"))
        return f"""TOPIC: {topic_context.get('topic', '')[:200]}
DESCRIPTION: {topic_context.get('description', '')[:desc_len]}

RECENT ARTICLES ON THIS TOPIC:
{titles_block}

AFFECTED SECTORS: {', '.join(topic_context.get('affected_sectors', []))}
AFFECTED PROVINCES: {', '.join(topic_context.get('affected_provinces', []))}

PROJECTS IN OUR DATABASE THAT MAY BE AFFECTED (name/province/value/status/sector):
{projects_block}

RELEVANT INDICATOR MOVEMENTS:
{indicators_block}
{continuity_note}

Generate the Under the Microscope analysis (200-300 words)."""

    # MICROSCOPE_SYSTEM is ~1.4KB; keep the user prompt under ~2.4KB so the
    # combined claude -p payload stays clear of the ~4KB failure threshold.
    # Every block scales down per attempt — shrinking only the project list
    # was not enough when titles/indicators were themselves bloated.
    user_prompt = None
    for params in ((8, 8, 120, 500, 1200),
                   (5, 6, 100, 400, 700),
                   (3, 4, 80, 250, 400),
                   (1, 2, 60, 150, 200)):
        user_prompt = _build_prompt(*params)
        if len(user_prompt) <= 2400:
            break
    if len(user_prompt) > 2400:
        logger.warning(f"Microscope prompt still {len(user_prompt)} chars after "
                       f"trimming — claude -p may fail on the ~4KB host limit")

    try:
        from claude_reasoning import OPUS_WRITING_MODEL
        result = await reason_with_claude_tracked(
            MICROSCOPE_SYSTEM,
            user_prompt,
            task_name="under_the_microscope",
            max_tokens=1500,
            model=OPUS_WRITING_MODEL,
        )
        logger.info(f"Microscope analysis generated: {len(result.get('text', ''))} chars")
        return result
    except Exception as e:
        logger.warning(f"Microscope analysis failed: {e}")
        return None


# ── History tracking ───────────────────────────────────────────────────────

def store_microscope_history(conn, topic, analysis_text):
    """Record this week's microscope topic for continuity tracking.

    Stores in dashboard_state/microscope_history (keeps last 52 weeks).

    Args:
        conn: sqlite3.Connection from db.py
        topic: topic string
        analysis_text: generated analysis text
    """
    from db import get_dashboard_state, save_dashboard_state

    try:
        history_data = get_dashboard_state(conn, "microscope_history")
        history = []
        if history_data and isinstance(history_data, dict):
            history = history_data.get("topics", [])

        history.append({
            "topic": topic,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "week_number": datetime.utcnow().isocalendar()[1],
            "analysis_length": len(analysis_text) if analysis_text else 0,
        })

        # Keep last 52 weeks
        history = history[-52:]

        save_dashboard_state(conn, "microscope_history", {"topics": history})
        logger.info(f"Microscope history updated: {topic}")
    except Exception as e:
        logger.warning(f"Failed to store microscope history: {e}")


def get_affected_projects(conn, topic_context):
    """Query SQLite for projects that may be affected by the microscope topic.

    Uses affected_sectors and affected_provinces to filter the project database.

    Args:
        conn: sqlite3.Connection from db.py
        topic_context: dict from select_microscope_topic()

    Returns: list of simplified project dicts (name, province, value, status, sector)
    """
    from db import get_projects

    affected_sectors = topic_context.get("affected_sectors", [])
    affected_provinces = topic_context.get("affected_provinces", [])

    if not affected_sectors and not affected_provinces:
        return []

    try:
        projects = []
        # Query by sector (most targeted)
        for sector in affected_sectors[:3]:
            rows = get_projects(conn, sector=sector, limit=20)
            for d in rows:
                projects.append({
                    "name": d.get("name", ""),
                    "province": d.get("province", ""),
                    "value_millions": d.get("value_millions"),
                    "status": d.get("status", ""),
                    "sector": d.get("sector", ""),
                })

        # Dedup by name
        seen = set()
        unique = []
        for p in projects:
            if p["name"] not in seen:
                seen.add(p["name"])
                unique.append(p)

        # Sort by value (highest first)
        unique.sort(key=lambda x: x.get("value_millions") or 0, reverse=True)
        return unique[:15]

    except Exception as e:
        logger.warning(f"Failed to get affected projects: {e}")
        return []
