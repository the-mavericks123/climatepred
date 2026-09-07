"""
Unit tests for data drift diagnostics (PSI and KS test) in Phase 10.
"""

import pytest
from intelligence.evaluation.drift import DriftDetector


def test_psi_identical_distributions():
    base = [float(i) for i in range(100)]
    curr = [float(i) for i in range(100)]
    psi, severity, _ = DriftDetector.calculate_psi(base, curr)
    assert psi == 0.0
    assert severity == "NONE"


def test_psi_significant_distribution_shift():
    base = [float(i) for i in range(50)]       # Low values [0..49]
    curr = [float(i + 100) for i in range(50)] # High shifted values [100..149]
    psi, severity, _ = DriftDetector.calculate_psi(base, curr)
    assert psi > 0.20
    assert severity == "SIGNIFICANT"


def test_ks_test_identical_distributions():
    s1 = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    s2 = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    d_stat, crit, is_drift = DriftDetector.calculate_ks_test(s1, s2)
    assert d_stat == 0.0
    assert not is_drift


def test_ks_test_drift_detection():
    s1 = [1.0, 2.0, 3.0] * 20
    s2 = [10.0, 11.0, 12.0] * 20
    d_stat, crit, is_drift = DriftDetector.calculate_ks_test(s1, s2)
    assert d_stat == 1.0
    assert is_drift is True


def test_drift_report_generation():
    base = [float(i) for i in range(100)]
    curr = [float(i + 50) for i in range(100)]
    report = DriftDetector.evaluate_drift("rainfall_mmhr", base, curr, method="PSI")
    assert report.feature_name == "rainfall_mmhr"
    assert report.method == "PSI"
    assert report.drift_detected is True
    assert len(report.provenance_hash) == 64
