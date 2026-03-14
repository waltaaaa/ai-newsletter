"""Phase 7: Narrative — Trends, market commentary, events, microscope, briefing"""
import traceback
import asyncio as _aio
from datetime import datetime


def run(conn, context, logger):
    """Generate trends, market commentary, microscope, and weekly briefing."""
    step_name = "Phase 7: Narrative"
    try:
        # Sector trend analysis
        sector_data = {}
        indicator_data = {}
        xref_data = {}
        trend_report = {}
        try:
            from sector_trends import compute_project_trends
            from indicator_trends import compute_indicator_trends
            from cross_reference import cross_reference_trends
            from weekly_trend_report import generate_trend_report
            from db import save_trend_snapshot, save_dashboard_state

            sector_data = compute_project_trends(conn)
            indicator_data = compute_indicator_trends(conn)
            xref_data = cross_reference_trends(indicator_data, sector_data)
            trend_report = generate_trend_report(
                sector_data, indicator_data, xref_data, conn=conn
            )

            if sector_data and not sector_data.get("error"):
                save_trend_snapshot(conn, {
                    "week_of": datetime.now().strftime("%Y-W%W"),
                    "snapshot": sector_data,
                })

            if xref_data and not xref_data.get("error"):
                save_dashboard_state(conn, "cross_references", {
                    "data": xref_data,
                    "updated_at": datetime.now().isoformat()
                })
                print(f"  [TRENDS] Cross-reference data stored to dashboard_state")

            if trend_report.get("narrative"):
                print(f"  [TRENDS] Report generated ({len(trend_report['narrative'])} chars)")
        except Exception as e:
            print(f"  [TRENDS] Failed: {type(e).__name__}: {e}")
            logger.log_error("trends_analysis", e)

        logger.log_step("trends_analysis")

        # Provincial policy monitor
        policy_developments = []
        try:
            from provincial_policy_monitor import process_policy_feeds
            policy_developments = process_policy_feeds(conn, since_days=7)
        except Exception as e:
            print(f"  [POLICY] Failed: {type(e).__name__}: {e}")

        # Canadian commodity indicators
        cdn_commodity_data = {}
        try:
            from canadian_markets import fetch_and_store_commodities
            cdn_commodity_data = fetch_and_store_commodities(conn)
        except Exception as e:
            print(f"  [MARKETS] Failed: {type(e).__name__}: {e}")

        # Economic event calendar
        upcoming_events = []
        try:
            from event_calendar import get_and_store_events
            upcoming_events = get_and_store_events(conn, days_ahead=14)
        except Exception as e:
            print(f"  [CALENDAR] Failed: {type(e).__name__}: {e}")

        # Build signal context for downstream modules
        signal_context = {
            'policy_summary': context.get('policy_summary', {}),
            'policy_items': context.get('policy_items', []),
            'job_spikes': context.get('job_spikes', []),
            'procurement_contracts': context.get('procurement_contracts', []),
            'iaac_status_changes': context.get('iaac_status_changes', []),
        }

        # Weekly narrative briefing
        try:
            from weekly_briefing import generate_weekly_briefing, store_and_distribute_briefing

            # Market commentary via Claude Sonnet
            market_commentary_text = None
            try:
                from canadian_markets import generate_market_commentary
                _project_summary = {
                    "total": sector_data.get("total_projects", 0),
                    "by_sector": sector_data.get("sectors", {}),
                }
                # Pass trade policy context to market commentary
                _trade_policy = [
                    p for p in context.get('policy_items', [])
                    if 'trade_policy' in p.get('policy_categories', [])
                ]
                market_commentary_result = _aio.run(
                    generate_market_commentary(
                        cdn_commodity_data, _project_summary, policy_developments,
                        trade_policy=_trade_policy,
                    )
                )
                if market_commentary_result:
                    market_commentary_text = market_commentary_result.get("text", "")
                    print(f"  [MARKETS] Commentary generated ({len(market_commentary_text)} chars)")
            except Exception as e:
                print(f"  [MARKETS] Commentary failed: {type(e).__name__}: {e}")

            # Pre-event analysis for high-significance events
            pre_event_analyses = []
            for evt in upcoming_events:
                if evt.get("significance") == "high":
                    try:
                        from event_calendar import generate_pre_event_analysis
                        analysis = _aio.run(
                            generate_pre_event_analysis(evt, indicator_data, [])
                        )
                        if analysis:
                            pre_event_analyses.append({
                                "event": evt.get("name", ""),
                                "date": evt.get("date", ""),
                                "analysis": analysis.get("text", ""),
                            })
                    except Exception as e:
                        print(f"  [WARN] Pre-event analysis failed ({evt.get('name', '?')}): {e}")

            if pre_event_analyses:
                print(f"  [CALENDAR] {len(pre_event_analyses)} pre-event analyses generated")

            # Under the Microscope
            microscope_text = None
            try:
                from under_the_microscope import (
                    select_microscope_topic, generate_microscope_analysis,
                    store_microscope_history, get_affected_projects,
                )
                from db import save_dashboard_state

                rss_items = context.get("rss_items", [])
                topic_context = _aio.run(select_microscope_topic(
                    conn, rss_items, indicator_data, xref_data,
                    signal_context=signal_context,
                ))
                if topic_context and topic_context.get("topic"):
                    print(f"  [MICROSCOPE] Topic: {topic_context['topic']}")
                    affected = get_affected_projects(conn, topic_context)
                    microscope_result = _aio.run(generate_microscope_analysis(
                        topic_context, affected, indicator_data
                    ))
                    if microscope_result:
                        microscope_text = microscope_result.get("text", "")
                        store_microscope_history(conn, topic_context["topic"], microscope_text)
                        save_dashboard_state(conn, "microscope_current", {
                            "topic": topic_context["topic"],
                            "sectors": topic_context.get("sectors", []),
                            "text": microscope_text,
                            "week": datetime.now().strftime("%Y-W%W"),
                            "updated_at": datetime.now().isoformat()
                        })
                        cost = microscope_result.get("cost_usd", 0)
                        print(f"  [MICROSCOPE] Generated: {len(microscope_text)} chars, ${cost:.4f}")
                else:
                    print("  [MICROSCOPE] No dominant topic identified")
            except Exception as e:
                print(f"  [MICROSCOPE] Failed: {type(e).__name__}: {e}")

            # Generate weekly briefing
            print("\n[BRIEFING] Generating weekly intelligence briefing...")
            briefing = _aio.run(generate_weekly_briefing(
                project_trends=sector_data,
                indicator_trends=indicator_data,
                cross_insights=xref_data,
                policy_developments=policy_developments,
                market_commentary=market_commentary_text,
                upcoming_events=upcoming_events,
                pre_event_analyses=pre_event_analyses,
                microscope_text=microscope_text,
                signal_context=signal_context,
            ))

            if briefing:
                _aio.run(store_and_distribute_briefing(conn, briefing))
                cost = briefing.get("cost_usd", 0)
                print(f"  [BRIEFING] Complete: {len(briefing.get('text', ''))} chars, ${cost:.4f}")

                # Briefing export (PDF + DOCX)
                try:
                    from briefing_export import export_and_upload
                    export_urls = export_and_upload(conn)
                    if export_urls:
                        print(f"  [EXPORT] Briefing exports uploaded: {list(export_urls.keys())}")
                    else:
                        print("  [EXPORT] No exports generated (missing dependencies?)")
                except Exception as e:
                    print(f"  [EXPORT] Briefing export failed: {type(e).__name__}: {e}")
            else:
                print("  [BRIEFING] Skipped (no API key or API error)")
        except Exception as e:
            print(f"  [BRIEFING] Failed: {type(e).__name__}: {e}")
            logger.log_error("briefing_generation", e)

        logger.log_step("briefing_generation")
        logger.log_step(step_name, "success")

        return {
            "sector_data": sector_data,
            "indicator_data": indicator_data,
            "xref_data": xref_data,
            "policy_developments": policy_developments,
            "upcoming_events": upcoming_events,
        }
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
