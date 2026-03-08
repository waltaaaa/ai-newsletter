"""
quality_report.py — Post-run quality report for CAN-MACRO dashboard.

Prints and saves to seed_audit_[date].txt after every seed or weekly run.

Sections:
  1. Project Coverage (by province, NAICS, discovery_source, status)
  2. Discovery Stats (GDELT, RSS, registries, Tavily)
  3. Writing Stats (citations, audit, officials)
  4. RSS Health (per-feed status)
  5. Wayback Stats (backfill, save)
  6. Consumer Sentiment Stats
  7. Coverage Gaps
  8. Rejected Items
  9. Annual Cost Summary
"""

import os
from datetime import date
from collections import Counter

from pipeline_config import NAICS_MAP, PROVINCES

TODAY = date.today().isoformat()


def generate_quality_report(
    conn=None,
    discovery_stats: dict | None = None,
    writing_stats: dict | None = None,
    rss_stats: dict | None = None,
    wayback_stats: dict | None = None,
    sentiment_stats: dict | None = None,
    rejected_items: list | None = None,
    filepath: str | None = None,
    db=None,
) -> str:
    """
    Generate a comprehensive quality report.

    Parameters
    ----------
    conn : sqlite3.Connection from db.py (preferred — reads project collection)
    discovery_stats : dict with GDELT/RSS/registry counts
    writing_stats : dict with citation/audit/officials counts
    rss_stats : dict with per-feed health data
    wayback_stats : dict with backfill/save counts
    sentiment_stats : dict with sentiment collection stats
    rejected_items : list of rejected projects/claims with reasons
    filepath : output file path (default: seed_audit_{date}.txt)
    db : deprecated Firestore client; ignored (kept for backward compatibility)

    Returns
    -------
    str — the full report text
    """
    if filepath is None:
        filepath = f'seed_audit_{TODAY}.txt'

    discovery_stats = discovery_stats or {}
    writing_stats = writing_stats or {}
    rss_stats = rss_stats or {}
    wayback_stats = wayback_stats or {}
    sentiment_stats = sentiment_stats or {}
    rejected_items = rejected_items or []

    lines = [
        f"CAN-MACRO Quality Report — {TODAY}",
        "=" * 70,
        "",
    ]

    # ── 1. Project Coverage ──────────────────────────────────────────
    lines.append("1. PROJECT COVERAGE")
    lines.append("-" * 40)

    projects = []
    if conn and hasattr(conn, 'execute'):
        try:
            from db import get_all_projects
            projects = get_all_projects(conn)
        except Exception as e:
            lines.append(f"  [ERROR] Could not read projects: {e}")

    if projects:
        # By province
        prov_counts = Counter(p.get('province', 'Unknown') for p in projects)
        lines.append(f"\n  Total projects: {len(projects)}")
        lines.append("  By province:")
        for prov_cfg in PROVINCES:
            prov_name = prov_cfg['name']
            count = prov_counts.get(prov_name, 0)
            flag = " <-- COVERAGE GAP" if count < 3 else ""
            lines.append(f"    {prov_name:<35} {count:>4}{flag}")

        # By NAICS sector
        naics_counts = Counter(p.get('naics_code', 'Unknown') for p in projects)
        lines.append("\n  By NAICS sector:")
        for code, name in sorted(NAICS_MAP.items()):
            count = naics_counts.get(code, 0)
            flag = " <-- ZERO PROJECTS" if count == 0 else ""
            lines.append(f"    {code:<6} {name:<50} {count:>4}{flag}")

        # By discovery_source
        src_counts = Counter(p.get('discovery_source', 'unknown') for p in projects)
        lines.append("\n  By discovery_source:")
        for src, count in src_counts.most_common():
            lines.append(f"    {src:<35} {count:>4}")

        # By status
        status_counts = Counter(p.get('status', 'Unknown') for p in projects)
        lines.append("\n  By status:")
        for status, count in status_counts.most_common():
            lines.append(f"    {status:<25} {count:>4}")

        # Undisclosed values
        undisclosed = sum(1 for p in projects
                         if (p.get('value') or 'Not disclosed').lower() in
                         ('not disclosed', 'unknown', ''))
        lines.append(f"\n  Value = Not disclosed: {undisclosed}/{len(projects)}")
    else:
        lines.append("  No projects in database (or db not provided)")

    # ── 2. Discovery Stats ───────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("2. DISCOVERY STATS")
    lines.append("-" * 40)
    lines.append(f"  GDELT queries executed:       {discovery_stats.get('gdelt_queries', 'N/A')}")
    lines.append(f"  GDELT unique articles:        {discovery_stats.get('gdelt_unique_articles', 'N/A')}")
    lines.append(f"  Gemini search projects found: {discovery_stats.get('gemini_projects', 'N/A')}")
    lines.append(f"  Company queries hit rate:     {discovery_stats.get('company_hit_rate', 'N/A')}")
    lines.append(f"  RSS feeds working:            {discovery_stats.get('rss_working', 'N/A')}")
    lines.append(f"  RSS feeds failed:             {discovery_stats.get('rss_failed', 'N/A')}")
    lines.append(f"  RSS items matched:            {discovery_stats.get('rss_items_matched', 'N/A')}")
    lines.append(f"  Articles sent to Tavily:      {discovery_stats.get('tavily_extractions', 'N/A')}")
    lines.append(f"  Projects from GDELT:          {discovery_stats.get('projects_gdelt', 'N/A')}")
    lines.append(f"  Projects from RSS:            {discovery_stats.get('projects_rss', 'N/A')}")
    lines.append(f"  Projects from registries:     {discovery_stats.get('projects_registries', 'N/A')}")
    lines.append(f"  Projects from Gemini:         {discovery_stats.get('projects_gemini', 'N/A')}")
    lines.append(f"  Projects from Perplexity:     {discovery_stats.get('projects_perplexity', 'N/A')}")
    lines.append(f"  Projects passing URL verify:  {discovery_stats.get('url_verified', 'N/A')}")
    lines.append(f"  Projects rejected:            {discovery_stats.get('projects_rejected', 'N/A')}")

    # ── 3. Writing Stats ─────────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("3. WRITING STATS")
    lines.append("-" * 40)
    lines.append(f"  Citations generated:          {writing_stats.get('total_citations', 'N/A')}")
    lines.append(f"  Citations verified:           {writing_stats.get('verified_citations', 'N/A')}")
    lines.append(f"  Citations removed:            {writing_stats.get('removed_citations', 'N/A')}")
    lines.append(f"  Audit pass rate:              {writing_stats.get('audit_pass_rate', 'N/A')}")

    per_call = writing_stats.get('per_call', [])
    if per_call:
        lines.append("  Per call:")
        for call in per_call:
            lines.append(
                f"    {call.get('label', '?')}: "
                f"{call.get('citations', 0)} cites, "
                f"{call.get('failed', 0)} failed, "
                f"{call.get('removal_pct', 0):.1f}% removed, "
                f"{'PASSED' if call.get('passed') else 'FAILED'}"
            )

    officials_used = writing_stats.get('officials_referenced', 'N/A')
    officials_total = writing_stats.get('officials_available', 'N/A')
    lines.append(f"  Officials referenced/total:   {officials_used}/{officials_total}")

    # ── 4. RSS Health ────────────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("4. RSS HEALTH")
    lines.append("-" * 40)
    feed_health = rss_stats.get('feeds', [])
    if feed_health:
        working = sum(1 for f in feed_health if f.get('status') == 'working')
        stale = sum(1 for f in feed_health if f.get('status') == 'stale')
        broken = sum(1 for f in feed_health if f.get('status') == 'broken')
        lines.append(f"  Working: {working}, Stale: {stale}, Broken: {broken}")
        for f in feed_health:
            if f.get('status') != 'working':
                lines.append(f"    [{f.get('status', '?').upper()}] {f.get('name', '?')}: "
                             f"{f.get('items', 0)} items, last: {f.get('latest_date', '?')}")
    else:
        lines.append("  No RSS health data available")

    # ── 5. Wayback Stats ─────────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("5. WAYBACK STATS")
    lines.append("-" * 40)
    lines.append(f"  Backfill attempts:            {wayback_stats.get('backfill_attempts', 'N/A')}")
    lines.append(f"  Backfill successes:           {wayback_stats.get('backfill_successes', 'N/A')}")
    lines.append(f"  No CDX results:               {wayback_stats.get('no_cdx_results', 'N/A')}")
    lines.append(f"  Snapshots fetched:            {wayback_stats.get('snapshots_fetched', 'N/A')}")
    lines.append(f"  Snapshots processed:          {wayback_stats.get('snapshots_processed', 'N/A')}")
    lines.append(f"  Avg history depth:            {wayback_stats.get('avg_history_depth', 'N/A')}")
    lines.append(f"  Save Page Now submissions:    {wayback_stats.get('save_submissions', 'N/A')}")
    lines.append(f"  Save Page Now successes:      {wayback_stats.get('save_successes', 'N/A')}")

    # ── 6. Consumer Sentiment Stats ──────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("6. CONSUMER SENTIMENT STATS")
    lines.append("-" * 40)
    lines.append(f"  Reddit posts fetched:         {sentiment_stats.get('reddit_posts', 'N/A')}")
    lines.append(f"  Reddit comments collected:    {sentiment_stats.get('reddit_comments', 'N/A')}")
    lines.append(f"  Google Trends queries:        {sentiment_stats.get('trends_queries', 'N/A')}")
    lines.append(f"  News comments fetched:        {sentiment_stats.get('news_comments', 'N/A')}")
    lines.append(f"  Topics extracted:             {sentiment_stats.get('topics_count', 'N/A')}")
    lines.append(f"  Overall sentiment index:      {sentiment_stats.get('sentiment_index', 'N/A')}")
    lines.append(f"  Overall label:                {sentiment_stats.get('sentiment_label', 'N/A')}")
    categories = sentiment_stats.get('categories', {})
    if categories:
        lines.append("  Category breakdown:")
        for cat, score in categories.items():
            lines.append(f"    {cat:<25} {score}")
    failures = sentiment_stats.get('failures', [])
    if failures:
        lines.append("  Source failures:")
        for f in failures:
            lines.append(f"    - {f}")
    if sentiment_stats.get('skipped'):
        lines.append(f"  SKIPPED: {sentiment_stats.get('skip_reason', 'unknown')}")

    # ── 7. Coverage Gaps ─────────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("7. COVERAGE GAPS")
    lines.append("-" * 40)
    if projects:
        naics_counts = Counter(p.get('naics_code', '') for p in projects)
        for code, name in sorted(NAICS_MAP.items()):
            if naics_counts.get(code, 0) == 0:
                lines.append(f"  COVERAGE GAP: NAICS {code} ({name}) — zero projects across all provinces")

        prov_counts = Counter(p.get('province', '') for p in projects)
        for prov_cfg in PROVINCES:
            prov_name = prov_cfg['name']
            count = prov_counts.get(prov_name, 0)
            if count < 3:
                lines.append(f"  COVERAGE GAP: {prov_name} — only {count} projects. "
                             f"Consider enabling Perplexity gap fill for {prov_name}")

        # Watchlist company hit gaps
        company_gaps = discovery_stats.get('company_zero_hits', [])
        if company_gaps:
            lines.append(f"\n  Watchlist companies with zero GDELT hits ({len(company_gaps)}):")
            for company in company_gaps[:20]:
                lines.append(f"    - {company} (may need query refinement)")
    else:
        lines.append("  No project data available for gap analysis")

    # ── 8. Rejected Items ────────────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("8. REJECTED ITEMS")
    lines.append("-" * 40)
    if rejected_items:
        # Projects
        rejected_projects = [r for r in rejected_items if r.get('type') == 'project']
        rejected_claims = [r for r in rejected_items if r.get('type') == 'claim']
        if rejected_projects:
            lines.append(f"\n  Rejected projects ({len(rejected_projects)}):")
            for rp in rejected_projects[:30]:
                lines.append(f"    - {rp.get('name', '?')[:50]}: {rp.get('reason', '?')}")
        if rejected_claims:
            lines.append(f"\n  Removed writing claims ({len(rejected_claims)}):")
            for rc in rejected_claims[:20]:
                lines.append(f"    - {rc.get('claim', '?')[:80]}: {rc.get('reason', '?')}")
    else:
        lines.append("  No rejected items logged")

    # ── 9. Annual Cost Summary ───────────────────────────────────────
    lines.append(f"\n{'='*70}")
    lines.append("9. ANNUAL COST SUMMARY")
    lines.append("-" * 40)
    lines.append("  Government registries + GDELT + RSS + Wayback CDX + Reddit + Google Trends = Free")
    lines.append("  Google News RSS (Tier 2, 759 queries/week)                     = Free")
    lines.append("  Tavily (targeted enrichment, 1000/mo free tier)                = Free")
    lines.append("  Claude Opus (macro tab: exec + national + global + pulse)      = ~$7/yr")
    lines.append("  Claude Sonnet (all reasoning: briefing + analysis + dedup QA)  = ~$48/yr")
    lines.append("  Gemini 2.5 Flash (extraction + classification, NO grounding)   = Free")
    lines.append("  " + "-" * 60)
    lines.append("  TOTAL                                                          = ~$55/yr")

    lines.append(f"\n{'='*70}")

    report = '\n'.join(lines)

    # Print to console
    print(f"\n{report}")

    # Save to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n  [Quality Report] Saved to {filepath}")
    except Exception as e:
        print(f"\n  [Quality Report] Save failed: {e}")

    return report
