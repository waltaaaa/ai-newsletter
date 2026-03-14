"""Phase 4: Signals — Permits, lobbyists (runs before analysis)"""
import traceback


def run(conn, context, logger):
    """Detect structured data signals from permits and lobbyist registries."""
    step_name = "Phase 4: Signals"
    try:
        permit_anomalies = []
        lobby_signals = []

        try:
            from statcan_permits import detect_permit_anomalies
            from lobbyist_registries import search_lobbyist_registries

            print("\n[SIGNALS] Structured data signal detection...")

            permit_anomalies = detect_permit_anomalies(conn)
            if permit_anomalies:
                from pipeline_store import store_follow_up_queries
                store_follow_up_queries(db=None, queries=permit_anomalies, conn=conn)
                print(f"  [PERMITS] {len(permit_anomalies)} anomalies → follow-up queries")

            lobby_signals = search_lobbyist_registries()
            if lobby_signals:
                from pipeline_store import store_follow_up_queries as _store_fq2
                _store_fq2(db=None, queries=lobby_signals, conn=conn)
                print(f"  [LOBBY] {len(lobby_signals)} signals → follow-up queries")
        except Exception as e:
            print(f"  [SIGNALS] Failed: {type(e).__name__}: {e}")

        # Job posting monitor — hiring spikes as leading indicator
        job_results = {}
        try:
            from job_monitor import run_job_monitor
            job_results = run_job_monitor(conn)
            print(f"  [JOBS] {job_results['job_postings_total']} postings, "
                  f"{len(job_results['job_spikes'])} spikes")
        except ImportError:
            print("  [WARN] job_monitor not available, skipping job posting analysis")
        except Exception as e:
            print(f"  [WARN] Job monitor failed: {e}")

        logger.log_step(step_name, "success")
        return {
            "permit_anomalies": permit_anomalies,
            "lobby_signals": lobby_signals,
            **job_results,
        }
    except Exception as e:
        logger.log_step(step_name, "error", str(e))
        traceback.print_exc()
        return {}
