"""Confidence calculation model for the Phase 3 Prediction Engine.
Computes deterministic, multi-factor forecast confidence scores.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

from intelligence.prediction.features import TemporalTrendSummary
from intelligence.prediction.thresholds import PredictionConfig, DEFAULT_PREDICTION_CONFIG


class PredictionConfidenceCalculator:
    """
    Computes honest, deterministic forecast confidence combining:
      1. Base telemetry data quality
      2. History sample sufficiency
      3. Trend linearity and residual stability
      4. Freshness of the latest observation
      5. Forecast horizon decay
    """

    def __init__(self, config: PredictionConfig = DEFAULT_PREDICTION_CONFIG):
        self.config = config

    def compute_confidence(
        self,
        summaries: List[TemporalTrendSummary],
        horizon_minutes: int,
        base_quality_confidence: float = 1.0,
        staleness_penalty_factor: float = 1.0,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Computes forecast confidence score in [0.0, 1.0] and detailed diagnostic metadata.
        """
        cfg = self.config
        diagnostics: Dict[str, Any] = {
            "base_quality": round(base_quality_confidence, 4),
            "staleness_factor": round(staleness_penalty_factor, 4),
            "horizon_minutes": horizon_minutes,
        }

        # 1. Horizon discount factor
        horizon_factor = cfg.horizon_factors.get(horizon_minutes, 0.70)
        diagnostics["horizon_factor"] = horizon_factor

        if not summaries:
            diagnostics["history_sufficiency"] = 0.0
            diagnostics["trend_stability"] = 0.0
            return 0.0, diagnostics

        # 2. History sufficiency factor
        any_insufficient = any(s.is_insufficient for s in summaries)
        min_samples = min(s.sample_count for s in summaries)
        avg_samples = sum(s.sample_count for s in summaries) / len(summaries)
        diagnostics["sample_count_avg"] = round(avg_samples, 1)
        diagnostics["has_insufficient_history"] = any_insufficient

        if any_insufficient or min_samples < cfg.min_observations:
            history_factor = cfg.insufficient_history_penalty
        else:
            # Scale from 0.70 (at 2 obs) up to 1.00 (at ideal_history_count)
            progress = min(1.0, max(0.0, (avg_samples - 2) / max(1, cfg.ideal_history_count - 2)))
            history_factor = 0.70 + (0.30 * progress)

        diagnostics["history_sufficiency"] = round(history_factor, 4)

        # 3. Trend stability factor (penalize high normalized residual variance)
        avg_variance = sum(s.trend_variance for s in summaries) / len(summaries)
        # Moderate variance penalty: variance > 10.0 starts degrading stability
        variance_penalty = min(0.35, avg_variance / 50.0)
        trend_stability = max(0.65, 1.0 - variance_penalty)
        diagnostics["trend_variance_avg"] = round(avg_variance, 4)
        diagnostics["trend_stability"] = round(trend_stability, 4)

        # 4. Multiplicative combination
        raw_conf = (
            base_quality_confidence
            * staleness_penalty_factor
            * history_factor
            * trend_stability
            * horizon_factor
        )

        final_conf = max(0.05, min(1.0, round(raw_conf, 4)))
        diagnostics["final_confidence"] = final_conf

        return final_conf, diagnostics
