"""
Unit tests for calibration methods (Platt scaling and Isotonic regression) in Phase 10.
"""

import pytest
from intelligence.calibration.methods import IsotonicCalibrator, PlattScaler


def test_isotonic_calibrator_monotonicity():
    scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    labels = [0, 0, 1, 0, 1, 1, 0, 1, 1]

    iso = IsotonicCalibrator().fit(scores, labels)
    preds = iso.predict_proba(scores)

    # Monotonicity invariant: preds[i] <= preds[i+1]
    for i in range(len(preds) - 1):
        assert preds[i] <= preds[i + 1], f"Violated monotonicity at index {i}: {preds[i]} > {preds[i+1]}"


def test_isotonic_calibrator_single_prediction():
    scores = [0.1, 0.3, 0.5, 0.7, 0.9]
    labels = [0, 0, 1, 1, 1]
    iso = IsotonicCalibrator().fit(scores, labels)

    p_low = iso.predict_single(0.2)
    p_high = iso.predict_single(0.8)
    assert p_low <= p_high
    assert 0.0 <= p_low <= 1.0
    assert 0.0 <= p_high <= 1.0


def test_platt_scaler_fitting_and_monotonicity():
    scores = [0.1 * i for i in range(20)]
    labels = [1 if s >= 0.5 else 0 for s in scores]

    scaler = PlattScaler().fit(scores, labels)
    preds = scaler.predict_proba(scores)

    # Monotonicity test
    for i in range(len(preds) - 1):
        assert preds[i] <= preds[i + 1]


def test_platt_scaler_bounds():
    scaler = PlattScaler().fit([0.2, 0.8], [0, 1])
    assert 0.0 <= scaler.predict_single(0.0) <= 1.0
    assert 0.0 <= scaler.predict_single(1.0) <= 1.0
    assert 0.0 <= scaler.predict_single(-10.0) <= 1.0
    assert 0.0 <= scaler.predict_single(100.0) <= 1.0
