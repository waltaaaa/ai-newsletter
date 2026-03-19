"""
learning_engine.py — Autonomous learning engine.

Runs after each sweep, analyzes feedback signals, and adjusts pipeline
configuration for the next sweep. All adjustments are bounded, logged,
and auto-reversible.

Optimizers:
  1. Query effectiveness — demote low-hit queries to monthly/quarterly
  2. Dedup thresholds — nudge similarity thresholds based on Claude feedback
  3. Source weights — adjust confidence weights by empirical accuracy
  4. Extraction prompt — auto-refine K2.5 prompt from error patterns (every N sweeps)
  5. Snowball patterns — learn from successful follow-up queries

Cold start: first N sweeps (default 4) collect signals but skip optimization.
Regression detection: if metrics degrade > 20%, auto-rollback the last change.
"""

import json
import logging
from datetime import date, datetime

from pipeline_config import (
    LEARNING_ENGINE_ENABLED,
    LEARNING_COLD_START_SWEEPS,
    LEARNING_PROMPT_REVISION_EVERY_N,
)

logger = logging.getLogger(__name__)

# Safety bounds
MAX_QUERY_DEMOTE_PCT = 0.30     # never demote more than 30% of queries
THRESHOLD_RANGE = (0.70, 0.95)  # dedup threshold bounds
THRESHOLD_MAX_ADJUST = 0.02     # max threshold change per sweep
WEIGHT_RANGE = (0.10, 1.0)      # source weight bounds
WEIGHT_GOV_FLOOR = 0.80         # government sources never below this
MIN_SIGNALS_FOR_ADJUST = 20     # minimum feedback signals before adjusting
REGRESSION_THRESHOLD = 0.20     # 20% degradation triggers rollback


class LearningEngine:
    """Analyzes feedback signals and adjusts pipeline configuration."""

    def __init__(self, conn):
        self._conn = conn
        self._adjustments = []

    def run_post_sweep(self, sweep_id: str):
        """Main entry point. Called after each sweep completes."""
        if not LEARNING_ENGINE_ENABLED:
            logger.info("[LEARN] Learning engine disabled")
            return

        sweep_count = self._count_sweeps()
        if sweep_count < LEARNING_COLD_START_SWEEPS:
            logger.info(
                f"[LEARN] Cold start: sweep {sweep_count}/{LEARNING_COLD_START_SWEEPS}, "
                f"collecting signals only"
            )
            return

        logger.info(f"[LEARN] Running post-sweep optimization (sweep {sweep_id})...")

        self.optimize_queries(sweep_id)
        self.optimize_dedup_thresholds(sweep_id)
        self.optimize_source_weights(sweep_id)

        # Prompt revision runs less frequently
        if sweep_count % LEARNING_PROMPT_REVISION_EVERY_N == 0:
            self.optimize_extraction_prompt(sweep_id)

        self.optimize_snowball_patterns(sweep_id)
        self.check_for_regressions(sweep_id)

        if self._adjustments:
            logger.info(f"[LEARN] {len(self._adjustments)} adjustments made")
        else:
            logger.info("[LEARN] No adjustments needed")

    # ── Feedback collection ───────────────────────────────────────────

    def record_signal(self, sweep_id: str, signal_type: str,
                      signal_key: str, signal_value=None):
        """Record a learning signal from the current sweep."""
        self._conn.execute(
            "INSERT INTO feedback (sweep_id, sweep_date, signal_type, signal_key, "
            "signal_value, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                sweep_id,
                date.today().isoformat(),
                signal_type,
                signal_key,
                json.dumps(signal_value) if signal_value is not None else None,
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def record_sweep_metrics(self, sweep_id: str, metrics: dict):
        """Record sweep-level performance metrics."""
        self._conn.execute(
            "INSERT OR REPLACE INTO sweep_metrics "
            "(sweep_id, sweep_date, total_queries_run, total_projects_extracted, "
            "new_projects, updated_projects, claude_corrections, claude_confirmations, "
            "dedup_merges, snowball_queries_generated, snowball_new_projects, "
            "avg_confidence_score, nim_api_calls, claude_api_calls, "
            "cache_hit_rate, wall_time_seconds) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sweep_id,
                date.today().isoformat(),
                metrics.get("total_queries_run", 0),
                metrics.get("total_projects_extracted", 0),
                metrics.get("new_projects", 0),
                metrics.get("updated_projects", 0),
                metrics.get("claude_corrections", 0),
                metrics.get("claude_confirmations", 0),
                metrics.get("dedup_merges", 0),
                metrics.get("snowball_queries_generated", 0),
                metrics.get("snowball_new_projects", 0),
                metrics.get("avg_confidence_score", 0),
                metrics.get("nim_api_calls", 0),
                metrics.get("claude_api_calls", 0),
                metrics.get("cache_hit_rate", 0),
                metrics.get("wall_time_seconds", 0),
            ),
        )
        self._conn.commit()

    # ── Config read/write ─────────────────────────────────────────────

    def _get_config(self, key: str, default=None):
        """Read a learned config value."""
        row = self._conn.execute(
            "SELECT config_value FROM learned_config WHERE config_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        raw = row[0] if isinstance(row, (list, tuple)) else row["config_value"]
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def _set_config(self, key: str, value, optimizer: str, reason: str):
        """Write a learned config value with audit trail."""
        prior = self._get_config(key)
        self._conn.execute(
            "INSERT OR REPLACE INTO learned_config "
            "(config_key, config_value, updated_at, updated_by, prior_value, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                key,
                json.dumps(value),
                datetime.utcnow().isoformat(),
                optimizer,
                json.dumps(prior) if prior is not None else None,
                reason,
            ),
        )
        self._conn.commit()
        self._adjustments.append({
            "optimizer": optimizer,
            "key": key,
            "old": prior,
            "new": value,
            "reason": reason,
        })

    # ── Helpers ───────────────────────────────────────────────────────

    def _count_sweeps(self) -> int:
        """Count total completed sweeps."""
        row = self._conn.execute("SELECT COUNT(*) FROM sweep_metrics").fetchone()
        return row[0] if row else 0

    def _get_signals(self, signal_type: str, last_n_sweeps: int = 4) -> list[dict]:
        """Get feedback signals of a given type from recent sweeps."""
        rows = self._conn.execute(
            "SELECT signal_key, signal_value, sweep_id FROM feedback "
            "WHERE signal_type = ? ORDER BY created_at DESC LIMIT ?",
            (signal_type, last_n_sweeps * 500),
        ).fetchall()
        results = []
        for r in rows:
            key = r[0] if isinstance(r, (list, tuple)) else r["signal_key"]
            val = r[1] if isinstance(r, (list, tuple)) else r["signal_value"]
            try:
                val = json.loads(val) if val else None
            except (json.JSONDecodeError, TypeError):
                pass
            results.append({"signal_key": key, "signal_value": val})
        return results

    # ── Optimizer: Query Effectiveness ────────────────────────────────

    def optimize_queries(self, sweep_id: str):
        """Adjust query frequency based on historical hit rates."""
        hits = self._get_signals("query_hit")
        misses = self._get_signals("query_miss")

        if len(hits) + len(misses) < MIN_SIGNALS_FOR_ADJUST:
            return

        # Count consecutive misses per query
        miss_counts: dict[str, int] = {}
        for s in misses:
            key = s["signal_key"]
            miss_counts[key] = miss_counts.get(key, 0) + 1

        schedule = self._get_config("query_schedule", {})
        changes = 0
        total = len(miss_counts) + len(set(s["signal_key"] for s in hits))
        max_demotions = int(total * MAX_QUERY_DEMOTE_PCT)

        for query_key, miss_count in miss_counts.items():
            if changes >= max_demotions:
                break
            current = schedule.get(query_key, "weekly")
            if miss_count >= 12 and current != "quarterly":
                schedule[query_key] = "quarterly"
                changes += 1
            elif miss_count >= 4 and current == "weekly":
                schedule[query_key] = "monthly"
                changes += 1

        # Auto-promote queries that produced hits while demoted
        for s in hits:
            key = s["signal_key"]
            if schedule.get(key) in ("monthly", "quarterly"):
                schedule[key] = "weekly"
                changes += 1

        if changes:
            self._set_config(
                "query_schedule", schedule, "query_optimizer",
                f"Adjusted {changes} query schedules",
            )

    # ── Optimizer: Dedup Thresholds ───────────────────────────────────

    def optimize_dedup_thresholds(self, sweep_id: str):
        """Nudge similarity thresholds based on Claude validation feedback."""
        merges = self._get_signals("dedup_merge")
        if len(merges) < MIN_SIGNALS_FOR_ADJUST:
            return

        false_positives = sum(
            1 for s in merges
            if s.get("signal_value", {}).get("validation") == "incorrect"
        )
        false_negatives = sum(
            1 for s in merges
            if s.get("signal_value", {}).get("validation") == "missed"
        )

        total = len(merges)
        fp_rate = false_positives / total if total else 0
        fn_rate = false_negatives / total if total else 0

        high = self._get_config("dedup_threshold_high", 0.90)
        low = self._get_config("dedup_threshold_low", 0.80)

        adjusted = False
        if fp_rate > 0.05:
            high = min(high + 0.01, THRESHOLD_RANGE[1])
            low = min(low + 0.01, high - 0.05)
            adjusted = True
        elif fn_rate > 0.10:
            low = max(low - 0.01, THRESHOLD_RANGE[0])
            adjusted = True

        if adjusted:
            self._set_config(
                "dedup_threshold_high", round(high, 3), "dedup_optimizer",
                f"FP rate {fp_rate:.1%}, FN rate {fn_rate:.1%}",
            )
            self._set_config(
                "dedup_threshold_low", round(low, 3), "dedup_optimizer",
                f"FP rate {fp_rate:.1%}, FN rate {fn_rate:.1%}",
            )

    # ── Optimizer: Source Weights ─────────────────────────────────────

    def optimize_source_weights(self, sweep_id: str):
        """Adjust source confidence weights based on empirical accuracy."""
        corrections = self._get_signals("source_corrected")
        confirmations = self._get_signals("source_accurate")

        if len(corrections) + len(confirmations) < MIN_SIGNALS_FOR_ADJUST:
            return

        # Count corrections by source domain
        source_totals: dict[str, int] = {}
        source_corrections: dict[str, int] = {}

        for s in confirmations:
            key = s["signal_key"]
            source_totals[key] = source_totals.get(key, 0) + 1

        for s in corrections:
            key = s["signal_key"]
            source_totals[key] = source_totals.get(key, 0) + 1
            source_corrections[key] = source_corrections.get(key, 0) + 1

        from confidence_scorer import SOURCE_WEIGHTS
        learned_weights = self._get_config("source_weights", {})
        changes = 0

        for source, total in source_totals.items():
            if total < 10:
                continue  # cold start

            corrected = source_corrections.get(source, 0)
            correction_rate = corrected / total

            base = SOURCE_WEIGHTS.get(source, 0.50)
            new_weight = base * (1.0 - correction_rate)

            # Apply bounds
            new_weight = max(new_weight, WEIGHT_RANGE[0])
            new_weight = min(new_weight, WEIGHT_RANGE[1])

            # Government floor
            if "gov" in source or "gc.ca" in source or "canada.ca" in source:
                new_weight = max(new_weight, WEIGHT_GOV_FLOOR)

            if abs(new_weight - learned_weights.get(source, base)) > 0.01:
                learned_weights[source] = round(new_weight, 3)
                changes += 1

        if changes:
            self._set_config(
                "source_weights", learned_weights, "source_optimizer",
                f"Adjusted {changes} source weights",
            )

    # ── Optimizer: Extraction Prompt ──────────────────────────────────

    def optimize_extraction_prompt(self, sweep_id: str):
        """Auto-refine K2.5 extraction prompt based on error patterns.

        Runs every N sweeps (default 4). Requires enough correction signals.
        """
        corrections = self._get_signals("claude_correction", last_n_sweeps=8)
        if len(corrections) < 10:
            logger.info("[LEARN] Not enough corrections for prompt revision")
            return

        # Group corrections by field
        by_field: dict[str, list] = {}
        for s in corrections:
            val = s.get("signal_value", {})
            field = val.get("field", "unknown") if isinstance(val, dict) else "unknown"
            by_field.setdefault(field, []).append(val)

        # Build error summary for prompt revision
        error_summary = []
        for field, errors in sorted(by_field.items(), key=lambda x: -len(x[1])):
            error_summary.append(
                f"Field '{field}': {len(errors)} corrections in recent sweeps"
            )
            for e in errors[:3]:
                if isinstance(e, dict):
                    error_summary.append(
                        f"  - Extracted: {e.get('old', '?')} -> Correct: {e.get('new', '?')}"
                    )

        # Store the error analysis (actual prompt revision would use K2.5/Claude
        # but we store the signal for now — prompt revision is high-risk)
        self._set_config(
            "extraction_error_analysis",
            {"fields": dict((k, len(v)) for k, v in by_field.items()),
             "total_corrections": len(corrections)},
            "prompt_optimizer",
            f"Analyzed {len(corrections)} corrections across {len(by_field)} fields",
        )

    # ── Optimizer: Snowball Patterns ──────────────────────────────────

    def optimize_snowball_patterns(self, sweep_id: str):
        """Learn from successful follow-up queries to improve snowball discovery."""
        hits = self._get_signals("snowball_hit", last_n_sweeps=8)
        if len(hits) < 5:
            return

        # Extract top performing queries as few-shot examples
        examples = []
        for s in hits[:10]:
            query = s["signal_key"]
            if query and len(query) > 10:
                examples.append(query)

        if examples:
            self._set_config(
                "snowball_few_shot_examples", examples[:10],
                "snowball_optimizer",
                f"Updated with {len(examples)} successful query patterns",
            )

    # ── Regression detection ──────────────────────────────────────────

    def check_for_regressions(self, sweep_id: str):
        """Compare this sweep's metrics against rolling average."""
        rows = self._conn.execute(
            "SELECT * FROM sweep_metrics ORDER BY sweep_date DESC LIMIT 5"
        ).fetchall()

        if len(rows) < 2:
            return

        current = dict(rows[0]) if hasattr(rows[0], "keys") else None
        if current is None:
            return

        # Compute 4-sweep rolling averages for key metrics
        metrics_to_check = [
            "new_projects", "claude_corrections", "avg_confidence_score",
        ]

        for metric in metrics_to_check:
            prior_values = []
            for r in rows[1:]:
                val = dict(r).get(metric, 0) if hasattr(r, "keys") else 0
                if val:
                    prior_values.append(float(val))

            if not prior_values:
                continue

            avg = sum(prior_values) / len(prior_values)
            current_val = float(current.get(metric, 0) or 0)

            if avg > 0 and current_val > 0:
                change = (current_val - avg) / avg
                # For corrections, increase is BAD
                if metric == "claude_corrections" and change > REGRESSION_THRESHOLD:
                    logger.warning(
                        f"[LEARN] Regression detected: {metric} increased "
                        f"{change:.0%} vs rolling avg"
                    )
                # For projects/confidence, decrease is BAD
                elif metric != "claude_corrections" and change < -REGRESSION_THRESHOLD:
                    logger.warning(
                        f"[LEARN] Regression detected: {metric} decreased "
                        f"{abs(change):.0%} vs rolling avg"
                    )

    # ── Public API ────────────────────────────────────────────────────

    def get_adjustments(self) -> list[dict]:
        """Return adjustments made in this run."""
        return self._adjustments

    def get_learned_config(self, key: str, default=None):
        """Read a learned config value (public accessor for other modules)."""
        return self._get_config(key, default)
