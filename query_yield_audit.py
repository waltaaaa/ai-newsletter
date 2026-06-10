"""
query_yield_audit.py — Rolling yield audits for discovery queries and tiers.

R8 — per-query yield history. The Google/Bing news tiers stamp each article
with `_query` (the shortened RSS query). After each weekly run the discovery
phase aggregates `{short_query: count}` and calls record_week(), which keeps a
rolling 8-week history in dashboard_state (key `query_yield_history` — no new
SQLite table). Queries that yielded at least once historically but have gone
4+ consecutive weeks with zero yield are written to the existing
`pipeline_improvements` table as deprioritization suggestions.

E7 — per-tier yield history. update_tier_history() is a pure helper the
discovery phase uses to keep a rolling per-tier count history in
dashboard_state (key `tier_yield_history`) and surface tiers that have gone
2+ consecutive runs with zero yield.

INVARIANT (ADDITIVE ONLY): this module FLAGS and DEPRIORITIZES only. It never
removes queries, keywords, or feeds from any config file.
"""

from datetime import date

# Rolling history caps
MAX_WEEKS = 8
# A query is flagged after this many consecutive zero-yield weeks
ZERO_YIELD_WEEKS = 4
# A tier is degraded after this many consecutive zero-yield runs
TIER_DEGRADED_RUNS = 2

QUERY_HISTORY_KEY = "query_yield_history"
TIER_HISTORY_KEY = "tier_yield_history"


def record_week(conn, counts, week_of=None):
    """Append one week of per-query yield counts to the rolling history.

    Args:
        conn: SQLite connection (dashboard_state + pipeline_improvements).
        counts: dict {short_query: article_count} for this run. Queries with
            zero yield are simply absent (counts derive from articles).
        week_of: ISO date for this week (default: today). A re-run for the
            same week replaces that week's entry instead of appending.

    Returns:
        list of flagged query strings (zero yield ZERO_YIELD_WEEKS+ weeks).

    Only queries that have appeared in the history with a non-zero count at
    least once (i.e. were issued and yielded) can be flagged. Flagging is a
    suggestion row in pipeline_improvements — NOTHING is removed from config.
    """
    from db import get_dashboard_state, save_dashboard_state, save_pipeline_improvement

    week_of = week_of or date.today().isoformat()
    history = get_dashboard_state(conn, QUERY_HISTORY_KEY) or []
    if not isinstance(history, list):
        history = []

    # Replace any existing entry for the same week, keep chronological order.
    history = [w for w in history if isinstance(w, dict) and w.get("week_of") != week_of]
    history.append({"week_of": week_of, "counts": dict(counts or {})})
    history.sort(key=lambda w: w.get("week_of", ""))
    history = history[-MAX_WEEKS:]
    save_dashboard_state(conn, QUERY_HISTORY_KEY, history)

    flagged = []
    if len(history) >= ZERO_YIELD_WEEKS:
        # Universe: queries that yielded >= 1 article in some recorded week.
        known = set()
        for w in history:
            for q, c in (w.get("counts") or {}).items():
                if c:
                    known.add(q)
        tail = history[-ZERO_YIELD_WEEKS:]
        for q in sorted(known):
            if all((w.get("counts") or {}).get(q, 0) == 0 for w in tail):
                flagged.append(q)

    if flagged:
        print(f"  [QUERY-AUDIT] {len(flagged)} queries zero-yield {ZERO_YIELD_WEEKS}+ weeks")
        for q in flagged:
            try:
                exists = conn.execute(
                    "SELECT 1 FROM pipeline_improvements "
                    "WHERE type = 'query_zero_yield' AND detail = ?",
                    (q,),
                ).fetchone()
                if exists:
                    continue
                save_pipeline_improvement(conn, {
                    "type": "query_zero_yield",
                    "detail": q,
                    "action": "deprioritize",
                    "note": (f"zero yield {ZERO_YIELD_WEEKS} consecutive weeks "
                             "(flag/deprioritize only — ADDITIVE-ONLY invariant, "
                             "never removed from config)"),
                    "week_of": week_of,
                })
            except Exception as e:
                print(f"  [QUERY-AUDIT] improvement write failed for '{q}': "
                      f"{type(e).__name__}: {e}")

    return flagged


def update_tier_history(history, this_run, max_keep=MAX_WEEKS):
    """Pure helper: append this run's per-tier yields to a rolling history.

    Args:
        history: dict {tier_name: [count, ...]} (oldest first). Tolerates
            None / wrong types (treated as empty).
        this_run: dict {tier_name: count} for the run that just finished.
        max_keep: cap on retained runs per tier (default 8).

    Returns:
        (new_history, degraded_tiers) where degraded_tiers is a list of
        (tier_name, consecutive_zero_runs) for tiers whose most recent
        TIER_DEGRADED_RUNS+ runs all yielded zero.
    """
    history = history if isinstance(history, dict) else {}
    this_run = this_run if isinstance(this_run, dict) else {}

    new_history = {}
    degraded = []
    for tier in sorted(set(history) | set(this_run)):
        runs = [int(v or 0) for v in (history.get(tier) or [])
                if isinstance(v, (int, float))]
        if tier in this_run:
            runs.append(int(this_run[tier] or 0))
        runs = runs[-max_keep:]
        new_history[tier] = runs

        zeros = 0
        for v in reversed(runs):
            if v == 0:
                zeros += 1
            else:
                break
        if zeros >= TIER_DEGRADED_RUNS:
            degraded.append((tier, zeros))

    return new_history, degraded
