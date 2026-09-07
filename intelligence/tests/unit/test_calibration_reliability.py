"""
Unit tests for reliability diagrams and binning in Phase 10 Calibration.
"""

import pytest
from intelligence.calibration.reliability import ReliabilityAnalyzer


def test_reliability_bins_partition():
    # 100 probabilities uniformly distributed
    probs = [i / 100.0 for i in range(100)]
    labels = [1 if p >= 0.5 else 0 for p in probs]

    bins = ReliabilityAnalyzer.compute_reliability_bins(probs, labels, num_bins=10)
    assert len(bins) == 10

    total_samples = sum(b.sample_count for b in bins)
    assert total_samples == 100

    # Upper bins should have higher empirical accuracy
    assert bins[-1].empirical_accuracy >= bins[0].empirical_accuracy


def test_reliability_bins_empty():
    bins = ReliabilityAnalyzer.compute_reliability_bins([], [])
    assert bins == []


def test_calibration_gap_calculation():
    # Perfectly calibrated forecast
    probs = [0.1] * 10
    labels = [1] + [0] * 9  # exactly 10% positive -> acc = 0.1, mean_p = 0.1
    bins = ReliabilityAnalyzer.compute_reliability_bins(probs, labels, num_bins=10)
    b0 = bins[1]  # [0.1, 0.2)
    assert pytest.approx(b0.calibration_gap, 0.01) == 0.0
