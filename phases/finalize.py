"""Phase 9: Finalize — Timeseries append, assembly, quality report, export, deploy"""
import traceback
import json
import pytz
from datetime import date, datetime, timedelta


def append_to_timeseries(conn, payload: dict, financial_markets: dict, boc_rate: str):
    """
    Append one data point per tracked variable to the timeseries table in SQLite.
    Skips duplicate dates (ON CONFLICT DO NOTHING).
    Variables tracked: BoC rate, CPI, unemployment, GoC yields, CAD/USD, TSX Composite.
    """
    from db import save_timeseries_point

    print("\n[TIMESERIES] Appending data points...")
    today_str = date.today().isoformat()

    def _upsert(series_name: str, unit: str, raw_value):
        """Parse raw_value to float and upsert into the timeseries table."""
        if raw_value is None:
            return
        try:
            val_f = float(str(raw_value).replace('%', '').replace('$', '').replace(',', '').strip())
        except Exception:
            return
        save_timeseries_point(conn, series_name, today_str, val_f, unit=unit)

    # BoC Rate
    _upsert('boc_rate', '%', boc_rate.replace('%', ''))

    # National metrics
    m = payload.get('metrics', {})
    _upsert('canada_cpi',         '%', (m.get('cpi') or '').replace('%', '').replace('+', ''))
    _upsert('canada_unemployment', '%', (m.get('unemployment') or '').replace('%', ''))

    # Yield curve terms
    for yc in payload.get('yieldCurve', []):
        term = yc.get('term', '')
        yval = yc.get('yield', '')
        if term and yval:
            _upsert(f'yield_{term.lower()}', '%', yval.replace('%', ''))

    # CAD/USD
    for fx in financial_markets.get('fx', []):
        if 'CAD/USD' in fx.get('name', '') or 'CADUSD' in fx.get('name', ''):
            _upsert('cadusd', 'USD', fx.get('value', '').replace(',', ''))

    # TSX Composite
    for idx in financial_markets.get('indices', []):
        if 'TSX' in idx.get('name', ''):
            _upsert('tsx_composite', 'pts', idx.get('value', '').replace(',', ''))

    # Commodities
    COMM_ID_MAP = {
        'Crude Oil (WTI)': 'comm_wti', 'Crude Oil (Brent)': 'comm_brent',
        'Natural Gas': 'comm_natgas', 'Gold': 'comm_gold', 'Silver': 'comm_silver',
        'Platinum': 'comm_platinum', 'Palladium': 'comm_palladium',
        'Copper': 'comm_copper', 'Aluminum': 'comm_aluminum',
        'Wheat': 'comm_wheat', 'Corn': 'comm_corn', 'Rice': 'comm_rice',
        'Soybeans': 'comm_soybeans', 'Coffee': 'comm_coffee', 'Cocoa': 'comm_cocoa',
        'Sugar #11': 'comm_sugar', 'Cotton': 'comm_cotton',
        'Soybean Oil': 'comm_soyoil', 'Soybean Meal': 'comm_soymeal',
        'Coal (Newcastle)': 'comm_coal', 'Propane': 'comm_propane',
    }
    for cat in payload.get('commodities', []):
        for item in (cat.get('items', []) if isinstance(cat, dict) else []):
            name = item.get('name', '')
            series_id = COMM_ID_MAP.get(name)
            if series_id:
                _upsert(series_id, item.get('unit', ''),
                        item.get('val', '').replace('$', '').replace(',', ''))

    # Other equity indices
    IDX_ID_MAP = {
        'S&P 500': 'idx_sp500', 'Dow Jones': 'idx_djia', 'NASDAQ': 'idx_nasdaq',
        'FTSE 100': 'idx_ftse', 'DAX': 'idx_dax', 'Nikkei 225': 'idx_nikkei',
        'Hang Seng': 'idx_hangseng', 'Shanghai': 'idx_shanghai',
    }
    for idx in financial_markets.get('indices', []):
        name = idx.get('name', '')
        series_id = IDX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, 'pts', idx.get('value', '').replace(',', ''))

    # Other FX pairs
    FX_ID_MAP = {
        'EUR/USD': 'fx_eurusd', 'GBP/USD': 'fx_gbpusd', 'USD/JPY': 'fx_usdjpy',
        'USD/CNY': 'fx_usdcny', 'AUD/USD': 'fx_audusd',
    }
    for fx_item in financial_markets.get('fx', []):
        name = fx_item.get('name', '')
        series_id = FX_ID_MAP.get(name)
        if series_id:
            _upsert(series_id, '', fx_item.get('value', '').replace(',', ''))

    print("  Timeseries update complete.")


def run(conn, context, logger):
    """Final assembly, timeseries, quality report, and static JSON export."""
    step_name = "Phase 9: Finalize"
    try:
        final_payload = context.get("final_payload", {})
        financial_markets = context.get("financial_markets", {})
        boc_data = context.get("boc_data", {})
        commodity_data = context.get("commodity_data", {})
        hard_data = context.get("hard_data", {})
        statcan_inds = context.get("statcan_inds")
        all_verified_sources = context.get("all_verified_sources", [])

        # StatCan indicators snapshot
        try:
            from gov_sources import save_statcan_indicators
            save_statcan_indicators(conn, statcan_inds)
        except Exception as e:
            print(f"  [WARN] StatCan snapshot save failed: {e}")
            logger.log_error("statcan_snapshot", e)

        # Timeseries append
        try:
            append_to_timeseries(conn, final_payload, financial_markets, boc_data.get('rate') or 'N/A')
        except Exception as e:
            print(f"  [WARN] Timeseries append failed: {e}")
            logger.log_error("timeseries", e)

        # Edition string
        toronto_tz = pytz.timezone('America/Toronto')
        today = datetime.now(toronto_tz)
        last_week = today - timedelta(days=7)
        final_payload["edition"] = (
            f"EDITION: {last_week.strftime('%b %d').upper()} – "
            f"{today.strftime('%b %d').upper()} // STATUS: AI-SYNTHESIZED"
        )

        # Consumer sentiment to DB
        sentiment_result = hard_data.get('_sentiment_result')
        if sentiment_result:
            final_payload['consumer_sentiment'] = sentiment_result
            try:
                from db import save_dashboard_state
                save_dashboard_state(conn, 'latest_sentiment', {
                    'updatedAt': date.today().isoformat(),
                    'consumer_sentiment': sentiment_result,
                })
                print("  [Sentiment] Saved to SQLite")
            except Exception as e:
                print(f"  [Sentiment] SQLite write failed (non-critical): {e}")

        # Quality Report
        try:
            from quality_report import generate_quality_report
            from db import get_all_projects
            print("\n[STEP 8] Generating quality report...")
            gemini_projects = context.get("gemini_projects", [])
            registry_projects = context.get("registry_projects", [])
            rss_projects = context.get("rss_projects", [])
            extracted_articles = context.get("extracted_articles", [])
            _discovery_stats = {
                'gemini_projects': len(gemini_projects) if gemini_projects else 0,
                'tavily_extractions': len(extracted_articles) if extracted_articles else 'N/A',
                'projects_registries': len(registry_projects) if registry_projects else 0,
                'projects_rss': len(rss_projects) if rss_projects else 0,
                'projects_gemini': len(gemini_projects) if gemini_projects else 0,
            }
            _writing_stats = {}
            _citation_audit = final_payload.get('citation_audit', {})
            if _citation_audit:
                watchlist = context.get("watchlist", {})
                _writing_stats = {
                    'total_citations': _citation_audit.get('total_citations', 0),
                    'verified_citations': _citation_audit.get('total_citations', 0) - _citation_audit.get('total_failed', 0),
                    'removed_citations': _citation_audit.get('total_failed', 0),
                    'audit_pass_rate': 'ALL PASSED' if _citation_audit.get('passed') else 'SOME FAILED',
                    'per_call': _citation_audit.get('calls', []),
                    'officials_referenced': 'N/A',
                    'officials_available': len(watchlist.get('public_figures_canada', [])) + len(watchlist.get('provincial_officials', [])),
                }
            _sentiment_stats = {}
            if sentiment_result:
                _sentiment_stats = {
                    'reddit_posts': sentiment_result.get('reddit_posts', 'N/A'),
                    'reddit_comments': sentiment_result.get('reddit_comments', 'N/A'),
                    'trends_queries': sentiment_result.get('trends_queries', 'N/A'),
                    'news_comments': sentiment_result.get('news_comments', 'N/A'),
                    'topics_count': len(sentiment_result.get('topics', [])),
                    'sentiment_index': sentiment_result.get('sentiment_index', 'N/A'),
                    'sentiment_label': sentiment_result.get('sentiment_label', 'N/A'),
                    'categories': sentiment_result.get('categories', {}),
                }
            generate_quality_report(
                conn=conn,
                discovery_stats=_discovery_stats,
                writing_stats=_writing_stats,
                sentiment_stats=_sentiment_stats,
            )
            logger.log_step("quality_report")
        except Exception as e:
            print(f"  [QUALITY] Quality report failed: {type(e).__name__}: {e}")
            logger.log_error("quality_report", e)

        # Final assembly + push to SQLite
        try:
            from db import save_dashboard_state
            print("\n[STEP 7] Final assembly + push to SQLite...")
            final_payload.setdefault('updated_at', date.today().isoformat())
            final_payload.setdefault('consumer_pulse', '')
            final_payload.setdefault('industry_executive_summary', '')
            final_payload.pop('_citation_audit', None)

            sources_with_archives = []
            for src in all_verified_sources:
                sources_with_archives.append({
                    'url': src.get('url', ''),
                    'title': src.get('title', ''),
                    'archive_url': src.get('archive_url', ''),
                })
            if sources_with_archives:
                final_payload['sources'] = sources_with_archives

            toronto_tz2 = pytz.timezone('America/Toronto')
            today2 = datetime.now(toronto_tz2)
            dated_id = today2.strftime('%Y-%m-%d')
            save_dashboard_state(conn, 'newsletter_latest', final_payload)
            save_dashboard_state(conn, f'newsletter_{dated_id}', final_payload)
            if final_payload.get('_analysis_incomplete'):
                print("[WARN] Dashboard updated with INCOMPLETE analysis — Claude calls failed.")
            else:
                print("[OK] Dashboard successfully updated.")
            logger.log_step("step_7_firestore_push")
        except Exception as e:
            print(f"[ERROR] Step 7 (SQLite export) failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            logger.log_error("step_7_export", e, recovered=False)

        # Tavily usage logging
        try:
            from tavily_search import get_tavily_credits_used
            tavily_searches_count = context.get("tavily_searches_count", 0)
            tavily_credits = get_tavily_credits_used(conn)
            logger.log_metric("api_usage", "tavily_searches", tavily_searches_count)
            logger.log_metric("api_usage", "tavily_month_total", tavily_credits.get("used", 0))
        except Exception as e:
            print(f"  [WARN] Tavily usage logging failed: {e}")

        # Static JSON export
        try:
            from export_dashboard import export_all
            print("\n[STEP 9] Exporting static JSON files...")
            export_result = export_all(conn=conn)
            print(f"[OK] Exported {export_result['file_count']} files to {export_result['output_dir']}")
            logger.log_step("step_9_json_export")
        except Exception as e:
            print(f"[ERROR] Static JSON export failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            logger.log_error("json_export", e, recovered=False)

        # Claude API cost summary
        try:
            cost_state = context.get("claude_cost", {})
            input_tok = cost_state.get("input", 0)
            output_tok = cost_state.get("output", 0)
            cost_usd = cost_state.get("usd", 0)
            cap = cost_state.get("cap", 0)
            print(f"\n[COST SUMMARY] Claude API: {input_tok:,} input + {output_tok:,} output tokens = ${cost_usd:.4f} (cap: ${cap:.2f})")
            logger.log_metric("api_usage", "claude_input_tokens", input_tok)
            logger.log_metric("api_usage", "claude_output_tokens", output_tok)
            logger.log_metric("api_usage", "claude_cost_usd", round(cost_usd, 4))
        except Exception as e:
            print(f"  [WARN] Cost summary failed: {e}")

        # Service health summary
        health = context.get("health")
        if health:
            health_status = health.get_status()
            if health_status.get("dead"):
                print(f"\n[SERVICE HEALTH] Dead services: {health_status['dead']}")
            logger.log_metric("api_usage", "service_health", health_status)

        logger.log_step(step_name, "success")
        return {"status": "completed" if not final_payload.get('_analysis_incomplete') else "partial"}
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {"status": "error"}
