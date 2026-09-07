"""
Unit tests for pure standard-library evaluation metrics calculator in Phase 10.
"""

import math
import pytest
from intelligence.evaluation.metrics import MetricsCalculator


def test_classification_perfect_metrics():
    y_true = [1, 1, 0, 0, 1]
    y_pred = [1, 1, 0, 0, 1]
    acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)
    assert acc == 1.0
    assert prec == 1.0
    assert rec == 1.0
    assert f1 == 1.0
    assert cm.true_positives == 3
    assert cm.true_negatives == 2
    assert cm.false_positives == 0
    assert cm.false_negatives == 0


def test_classification_mixed_metrics():
    y_true = [1, 0, 1, 1, 0]
    y_pred = [1, 1, 1, 0, 0]
    # TP = 2 (indices 0, 2), FP = 1 (idx 1), TN = 1 (idx 4), FN = 1 (idx 3)
    acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)
    assert cm.true_positives == 2
    assert cm.false_positives == 1
    assert cm.true_negatives == 1
    assert cm.false_negatives == 1
    assert pytest.approx(prec, 0.01) == 2 / 3
    assert pytest.approx(rec, 0.01) == 2 / 3
    assert pytest.approx(f1, 0.01) == 2 / 3


def test_classification_zero_positives():
    y_true = [0, 0, 0]
    y_pred = [0, 0, 0]
    acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)
    assert acc == 1.0
    assert prec == 0.0
    assert rec == 0.0
    assert f1 == 0.0


def test_continuous_metrics_calculation():
    y_true = [1.0, 2.0, 3.0, 4.0]
    y_pred = [1.1, 1.9, 3.2, 3.8]
    # errors = [+0.1, -0.1, +0.2, -0.2]
    mae, rmse, bias = MetricsCalculator.calculate_continuous_metrics(y_true, y_pred)
    assert pytest.approx(mae, 0.01) == 0.15
    assert rmse > 0.0
    assert pytest.approx(bias, 0.01) == 0.0


def test_brier_score():
    y_true = [1, 0, 1, 1]
    y_prob = [0.9, 0.1, 0.8, 0.2]
    # sq_diffs = (0.1)^2 + (0.1)^2 + (0.2)^2 + (0.8)^2 = 0.01 + 0.01 + 0.04 + 0.64 = 0.70 / 4 = 0.175
    brier = MetricsCalculator.calculate_brier_score(y_true, y_prob)
    assert pytest.approx(brier, 0.01) == 0.175


def test_calibration_error_bins():
    y_true = [1] * 50 + [0] * 50
    # Overconfident incorrect forecasts
    y_prob = [0.95] * 50 + [0.85] * 50
    ece, mce = MetricsCalculator.calculate_calibration_error(y_true, y_prob, num_bins=10)
    assert ece > 0.0
    assert mce > 0.0
