"""Phase 8: Verification — Source verification, Wayback archival, project maintenance"""
import traceback
import json
import concurrent.futures
import requests
from datetime import date, timedelta


def _check_url(url: str) -> bool:
    """HEAD request (5 s timeout) to verify a URL is reachable. Returns False on any error."""
    if not url or not url.startswith('http'):
        return False
    try:
        r = requests.head(url, timeout=5, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; CAN-MACRO/1.0)'})
        return r.status_code < 400
    except Exception:
        return False


def _verify_project_evidence_urls(conn, batch_size=200) -> None:
    """
    Check evidence URLs across projects and mark dead ones.

    Runs HEAD requests against evidence URLs that haven't been checked recently.
    Dead URLs get url_dead=True so the frontend can show 'source unavailable'.
    Checks up to batch_size projects per run.
    """
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    print(f"\n[URL-CHECK] Verifying project evidence URLs...")

    try:
        rows = conn.execute(
            "SELECT norm_key, evidence FROM projects "
            "WHERE (urls_checked_at IS NULL OR urls_checked_at < ?) LIMIT ?",
            (cutoff, batch_size)
        ).fetchall()
        docs = [dict(r) for r in rows]
    except Exception as e:
        print(f"  [URL-CHECK] Could not query projects: {e}")
        return

    if not docs:
        print("  [URL-CHECK] No projects need URL checking.")
        return

    print(f"  [URL-CHECK] Checking evidence URLs for {len(docs)} projects...")

    # Collect all URLs to check
    url_tasks = []  # (norm_key, evidence_index, url)
    for doc in docs:
        evidence = doc.get('evidence', [])
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except Exception:
                evidence = []
        for i, ev in enumerate(evidence):
            url = ev.get('url', '')
            if url and url.startswith('http') and not ev.get('url_dead'):
                url_tasks.append((doc['norm_key'], i, url, evidence))

    if not url_tasks:
        today_str = date.today().isoformat()
        for doc in docs:
            try:
                with conn:
                    conn.execute(
                        "UPDATE projects SET urls_checked_at = ? WHERE norm_key = ?",
                        (today_str, doc['norm_key'])
                    )
            except Exception as e:
                print(f"  [WARN] URL check timestamp update failed ({doc.get('norm_key', '?')}): {e}")
        print("  [URL-CHECK] No evidence URLs to verify.")
        return

    # Batch HEAD checks
    urls_only = [t[2] for t in url_tasks]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_check_url, urls_only))

    # Group dead indices by norm_key, using already-fetched evidence
    dead_by_key = {}   # norm_key -> (dead_indices, evidence_list)
    dead_count = 0
    for (norm_key, ev_idx, url, ev_list), is_live in zip(url_tasks, results):
        if not is_live:
            dead_count += 1
            if norm_key not in dead_by_key:
                dead_by_key[norm_key] = ([], ev_list)
            dead_by_key[norm_key][0].append(ev_idx)

    today_str = date.today().isoformat()
    checked_keys = set()

    # Batch update: mark dead URLs using already-fetched evidence (no re-query)
    for norm_key, (dead_indices, ev_list) in dead_by_key.items():
        try:
            changed = False
            for idx in dead_indices:
                if idx < len(ev_list) and not ev_list[idx].get('url_dead'):
                    ev_list[idx]['url_dead'] = True
                    changed = True
            if changed:
                with conn:
                    conn.execute(
                        "UPDATE projects SET evidence = ?, urls_checked_at = ? WHERE norm_key = ?",
                        (json.dumps(ev_list, ensure_ascii=False), today_str, norm_key)
                    )
            checked_keys.add(norm_key)
        except Exception as e:
            print(f"  [WARN] Dead URL update failed ({norm_key}): {e}")

    # Batch update timestamp for projects with no dead URLs
    no_dead_keys = [doc['norm_key'] for doc in docs if doc['norm_key'] not in checked_keys]
    if no_dead_keys:
        try:
            with conn:
                conn.executemany(
                    "UPDATE projects SET urls_checked_at = ? WHERE norm_key = ?",
                    [(today_str, nk) for nk in no_dead_keys]
                )
        except Exception as e:
            print(f"  [WARN] Batch URL check timestamp update failed: {e}")

    live_count = len(urls_only) - dead_count
    print(f"  [URL-CHECK] {live_count} live, {dead_count} dead across {len(docs)} projects")


def _check_stale_projects(conn) -> None:
    """
    STEP 4b: Mark projects not seen in 4+ weeks as stale.
    Updates SQLite directly. Non-critical — never raises.
    """
    stale_cutoff = (date.today() - timedelta(days=28)).isoformat()
    try:
        rows = conn.execute(
            "SELECT norm_key, name, lastSeen FROM projects WHERE lastSeen < ? LIMIT 50",
            (stale_cutoff,)
        ).fetchall()
        if not rows:
            print("  [Stale check] No projects older than 4 weeks.")
            return
        print(f"  [Stale check] Marking {len(rows)} stale projects...")
        for row in rows:
            name = row['name']
            if not name:
                continue
            try:
                with conn:
                    conn.execute(
                        "UPDATE projects SET stale = 1, statusNote = ? WHERE norm_key = ?",
                        (f"Not seen since {row['lastSeen'] or 'unknown'}", row['norm_key'])
                    )
            except Exception as e:
                print(f"  [WARN] Stale mark failed ({row.get('norm_key', '?')}): {e}")
        print(f"  [Stale check] {len(rows)} projects marked stale")
    except Exception as e:
        print(f"  [Stale check] Error: {e}")


def run(conn, context, logger):
    """Run source verification, stale checks, Wayback backfill, and maintenance tasks."""
    step_name = "Phase 8: Verification"
    try:
        final_payload = context.get("final_payload", {})
        deep_sweep = context.get("mode") == "deep-sweep"
        all_flat_projects = context.get("all_flat_projects", [])
        verified_projects = context.get("verified_projects", [])

        # Cost-finding for valueless projects
        try:
            from tavily_search import can_use_tavily
            if can_use_tavily():
                from cost_finder import run_cost_search
                print("\n[POST-EXTRACTION] Cost-finding for valueless projects...")
                cost_results = run_cost_search(conn)
                if cost_results.get("found"):
                    print(f"  [COST] Updated {cost_results['found']} projects with values")
            else:
                print("\n[POST-EXTRACTION] Cost-finding skipped (Tavily budget)")
        except Exception as e:
            print(f"  [COST] Cost-finding failed: {type(e).__name__}: {e}")
            logger.log_error("cost_finding", e)

        # Enrichment queries (Gemini Flash, no grounding)
        if all_flat_projects:
            try:
                from enrichment_queries import run_enrichment_sync
                from project_dedup import deduplicate_projects
                from project_sync import upsert_flat_projects
                print("\n[POST-EXTRACTION] Enrichment queries (spare Gemini capacity)...")
                needs_enrichment = [p for p in (verified_projects or all_flat_projects)
                                    if not p.get('value_millions') or not p.get('status')
                                    or p.get('status') == 'Proposed']
                if needs_enrichment:
                    enriched = run_enrichment_sync(needs_enrichment[:55])
                    if enriched:
                        enriched_deduped = deduplicate_projects(enriched)
                        enriched_verified = [p for p in enriched_deduped
                                             if p.get("evidence") and len(p["evidence"]) > 0]
                        if enriched_verified:
                            upsert_flat_projects(conn, enriched_verified)
                            print(f"  [ENRICHMENT] {len(enriched_verified)} projects enriched")
                else:
                    print("  [ENRICHMENT] No projects need enrichment")
            except Exception as e:
                print(f"  [ENRICHMENT] Failed: {type(e).__name__}: {e}")
                logger.log_error("enrichment", e)

        # Wayback history backfill
        try:
            from tools.wayback import backfill_project_history, save_page as wayback_save
        except ImportError:
            backfill_project_history = None
            wayback_save = None
            print("[WARN] wayback module not available, skipping archival")

        if backfill_project_history is not None:
            print("\n[POST-EXTRACTION] Wayback history backfill for new projects...")
            try:
                rows = conn.execute(
                    "SELECT norm_key, name, province, status, statusHistory FROM projects "
                    "WHERE (history_backfilled IS NULL OR history_backfilled = 0) LIMIT 20"
                ).fetchall()
                backfill_count = 0
                for row in rows:
                    p = dict(row)
                    name = p.get('name', '')
                    status_history = p.get('statusHistory', '[]')
                    if isinstance(status_history, str):
                        try:
                            status_history = json.loads(status_history)
                        except Exception:
                            status_history = []
                    source_url = ''
                    for entry in (status_history or []):
                        src = entry.get('source', {})
                        if src.get('url'):
                            source_url = src['url']
                            break
                    if not source_url or not name:
                        continue
                    print(f"  [Backfill] {name[:50]}...", end=" ", flush=True)
                    result = backfill_project_history(
                        project_name=name,
                        source_url=source_url,
                        province=p.get('province', ''),
                        current_status=p.get('status', ''),
                        current_detail='',
                        today=date.today().isoformat(),
                    )
                    if result.get('history_backfilled'):
                        history = result.get('statusHistory', [])
                        full_history = history + (status_history or [])
                        with conn:
                            conn.execute(
                                "UPDATE projects SET history_backfilled = 1, "
                                "history_earliest_date = ?, statusHistory = ? "
                                "WHERE norm_key = ?",
                                (result.get('history_earliest_date', ''),
                                 json.dumps(full_history, ensure_ascii=False),
                                 p['norm_key'])
                            )
                        backfill_count += 1
                        print(f"{result.get('snapshots_processed', 0)} snapshots")
                    else:
                        print("skipped")
                if backfill_count:
                    print(f"  [Backfill] {backfill_count} projects backfilled")
            except Exception as e:
                print(f"  [Backfill] Error (non-critical): {type(e).__name__}: {e}")

            # Deep-sweep: re-attempt backfill for history_backfilled=false
            if deep_sweep:
                print("\n[DEEP-SWEEP] Re-attempting backfill for unbackfilled projects...")
                try:
                    rows = conn.execute(
                        "SELECT norm_key, name, province, statusHistory FROM projects "
                        "WHERE (history_backfilled IS NULL OR history_backfilled = 0)"
                    ).fetchall()
                    for row in rows:
                        p = dict(row)
                        name = p.get('name', '')
                        sh = p.get('statusHistory', '[]')
                        if isinstance(sh, str):
                            try:
                                sh = json.loads(sh)
                            except Exception:
                                sh = []
                        source_url = ''
                        for entry in (sh or []):
                            src = entry.get('source', {})
                            if src.get('url'):
                                source_url = src['url']
                                break
                        if not source_url or not name:
                            continue
                        result = backfill_project_history(
                            project_name=name,
                            source_url=source_url,
                            province=p.get('province', ''),
                        )
                        if result.get('history_backfilled') and result.get('statusHistory'):
                            full_history = result['statusHistory'] + (sh or [])
                            with conn:
                                conn.execute(
                                    "UPDATE projects SET history_backfilled = 1, "
                                    "history_earliest_date = ?, statusHistory = ? "
                                    "WHERE norm_key = ?",
                                    (result.get('history_earliest_date', ''),
                                     json.dumps(full_history, ensure_ascii=False),
                                     p['norm_key'])
                                )
                except Exception as e:
                    print(f"  [Deep-sweep backfill] Error: {type(e).__name__}")

        # Stale project checks
        try:
            print("\n[POST-EXTRACTION] Checking stale projects...")
            _check_stale_projects(conn)
        except Exception as e:
            print(f"  [STALE] Stale check failed: {type(e).__name__}: {e}")
            logger.log_error("stale_check", e)

        # Evidence URL verification
        try:
            _verify_project_evidence_urls(conn)
        except Exception as e:
            print(f"  [URL-CHECK] Failed: {type(e).__name__}: {e}")

        # Confidence decay
        try:
            from confidence_decay import apply_confidence_decay
            apply_confidence_decay(conn)
        except Exception as e:
            print(f"  [DECAY] Failed: {type(e).__name__}: {e}")

        # Lifecycle monitoring
        try:
            from lifecycle_monitor import run_lifecycle_search
            run_lifecycle_search(conn)
        except Exception as e:
            print(f"  [MONITOR] Failed: {type(e).__name__}: {e}")

        # Deactivate alerts for terminal projects
        try:
            from project_alert_tracker import deactivate_terminal_projects
            deactivated = deactivate_terminal_projects(conn)
            if deactivated:
                print(f"  [ALERTS] Deactivated {deactivated} alerts for terminal projects")
        except Exception as e:
            print(f"  [ALERTS] Deactivation check failed: {type(e).__name__}: {e}")

        # Cross-project anomaly detection
        try:
            from anomaly_detection import check_cross_project_anomalies
            from db import get_all_projects
            all_snap = get_all_projects(conn) or []
            cross_anomalies = check_cross_project_anomalies(all_snap)
            if cross_anomalies:
                print(f"  [ANOMALY] {len(cross_anomalies)} possible cross-province duplicates")
        except Exception as e:
            print(f"  [ANOMALY] Failed: {type(e).__name__}: {e}")

        # Capacity tiers
        cap_result = None
        try:
            from capacity_scheduler import run_capacity_tiers
            cap_result = run_capacity_tiers(conn)
        except Exception as e:
            print(f"  [CAPACITY] Failed: {type(e).__name__}: {e}")

        # GitHub Issues submissions
        try:
            from github_issues_reader import fetch_issue_submissions
            issues_result = fetch_issue_submissions(conn)
            if issues_result.get("skipped"):
                print(f"  [ISSUES] Skipped: {issues_result.get('reason', 'unknown')}")
            elif issues_result.get("processed", 0) > 0:
                print(f"  [ISSUES] {issues_result['processed']} new submissions "
                      f"({issues_result.get('new_projects', 0)} projects, "
                      f"{issues_result.get('corrections', 0)} corrections)")
            else:
                print("  [ISSUES] No new submissions")
        except Exception as e:
            print(f"  [ISSUES] Warning: {e}")

        # Missed project submissions
        try:
            from missed_projects import process_pending_submissions
            missed_result = process_pending_submissions(conn, max_queries=20)
            if missed_result.get("processed"):
                print(f"  [MISSED] {missed_result['processed']} submissions, "
                      f"{missed_result['enriched']} enriched")
        except Exception as e:
            print(f"  [MISSED] Failed: {type(e).__name__}: {e}")

        # Pipeline learning
        try:
            from learning_store import apply_pending_improvements
            applied = apply_pending_improvements(conn)
            if applied:
                print(f"  [LEARN] Applied {applied} improvements")
        except Exception as e:
            print(f"  [LEARN] Failed: {type(e).__name__}: {e}")

        # Wayback save for verified citation URLs
        all_verified_sources = context.get("final_payload", {}).pop('_all_verified_sources', [])
        if all_verified_sources and wayback_save is not None:
            try:
                print(f"\n[POST-EXTRACTION] Archiving {len(all_verified_sources)} verified citation URLs...")
                archived = 0
                for src in all_verified_sources:
                    url = src.get('url', '')
                    if url and not src.get('archive_url'):
                        archive_url = wayback_save(url)
                        if archive_url:
                            src['archive_url'] = archive_url
                            archived += 1
                if archived:
                    print(f"  [Wayback] Archived {archived} citation URLs")
            except Exception as e:
                print(f"  [Wayback] Citation archiving failed: {type(e).__name__}: {e}")
                logger.log_error("wayback_citations", e)

        logger.log_step(step_name, "success")
        return {
            "cap_result": cap_result,
            "all_verified_sources": all_verified_sources,
        }
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
