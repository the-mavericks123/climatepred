"""Unit tests for prediction confidence model (Phase 3).

Tests:
  - History sufficiency (sample count and duration scaling)
  - Insufficient history penalty
  - Horizon decay (30m > 60m > 360m)
  - Trend noise / variance degradation
  - Staleness penalty
  - Bounded strictly in [0.0, 1.0]
"""

import pytest

from intelligence.prediction.confidence import PredictionConfidenceCalculator
from intelligence.prediction.features import TemporalTrendSummary
from intelligence.prediction.thresholds import PredictionConfig


def _make_summary(var: str = "temp", n: int = 6, variance: float = 0.05, is_insufficient: bool = False):
    return TemporalTrendSummary(
        variable_name=var,
        current_value=30.0,
        sample_count=n,
        history_span_minutes=50.0,
        rate_of_change_per_minute=0.1,
        trend_variance=variance,
        is_insufficient=is_insufficient,
        direction="RISING",
    )


class TestPredictionConfidence:
    def setup_method(self):
        self.calc = PredictionConfidenceCalculator()

    def test_horizon_decay(self):
        """Longer forecast horizons must have lower confidence."""
        summaries = [_make_summary("temp"), _make_summary("humidity")]

        c30, _ = self.calc.compute_confidence(summaries, horizon_minutes=30)
        c60, _ = self.calc.compute_confidence(summaries, horizon_minutes=60)
        c360, _ = self.calc.compute_confidence(summaries, horizon_minutes=360)

        assert 0.0 <= c360 < c60 < c30 <= 1.0

    def test_insufficient_history_penalty(self):
        """Insufficient history (< 2 samples) must apply penalty."""
        summaries_good = [_make_summary(n=6, is_insufficient=False)]
        summaries_bad = [_make_summary(n=1, is_insufficient=True)]

        c_good, diag_good = self.calc.compute_confidence(summaries_good, horizon_minutes=30)
        c_bad, diag_bad = self.calc.compute_confidence(summaries_bad, horizon_minutes=30)

        assert c_bad < c_good
        assert diag_bad["has_insufficient_history"] is True
        assert diag_bad["history_sufficiency"] == 0.50

    def test_noisy_trend_variance_penalty(self):
        """High residual variance (noise) in history must degrade confidence."""
        summaries_clean = [_make_summary(variance=0.01)]
        summaries_noisy = [_make_summary(variance=25.0)]

        c_clean, _ = self.calc.compute_confidence(summaries_clean, horizon_minutes=60)
        c_noisy, _ = self.calc.compute_confidence(summaries_noisy, horizon_minutes=60)

        assert c_noisy < c_clean

    def test_staleness_penalty(self):
        """Stale input observation must reduce prediction confidence."""
        summaries = [_make_summary()]
        c_fresh, _ = self.calc.compute_confidence(summaries, horizon_minutes=30, staleness_penalty_factor=1.0)
        c_stale, _ = self.calc.compute_confidence(summaries, horizon_minutes=30, staleness_penalty_factor=0.60)

        assert c_stale < c_fresh
        assert c_stale == pytest.approx(c_fresh * 0.60, 0.01)
