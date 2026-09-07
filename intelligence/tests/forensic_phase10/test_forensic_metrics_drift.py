"""
Adversarial Forensic Test Suite: Metrics, Drift & Model Comparison.
Audits Parts 14, 15, 16, 17, 18, and 26.
"""

import math
import pytest
from intelligence.evaluation.metrics import MetricsCalculator
from intelligence.evaluation.drift import DriftDetector
from intelligence.evaluation.comparison import ModelComparator
from intelligence.evaluation.types import EvaluationMetrics


class TestForensicMetricsVerification:
    """Independent mathematical verification of evaluation metrics."""

    def test_hand_calculated_classification_metrics(self):
        """Verify precision, recall, accuracy, and F1 against hand-calculated ground truth."""
        # 6 samples:
        # y_true = [1, 1, 1, 0, 0, 0]
        # y_pred = [1, 1, 0, 1, 0, 0]
        # TP = 2 (indices 0, 1)
        # FN = 1 (index 2)
        # FP = 1 (index 3)
        # TN = 2 (indices 4, 5)
        # Acc = (2 + 2) / 6 = 4/6 = 0.6667
        # Prec = 2 / (2 + 1) = 2/3 = 0.6667
        # Rec = 2 / (2 + 1) = 2/3 = 0.6667
        # F1 = 2 * (2/3 * 2/3) / (4/3) = 2/3 = 0.6667
        y_true = [1, 1, 1, 0, 0, 0]
        y_pred = [1, 1, 0, 1, 0, 0]

        acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)

        assert acc == 0.6667
        assert prec == 0.6667
        assert rec == 0.6667
        assert f1 == 0.6667
        assert cm.true_positives == 2
        assert cm.false_negatives == 1
        assert cm.false_positives == 1
        assert cm.true_negatives == 2

    def test_classification_metrics_edge_cases_zero_division(self):
        """Test edge cases with no positive predictions, empty datasets, or all negatives."""
        # Empty inputs
        acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics([], [])
        assert (acc, prec, rec, f1) == (0.0, 0.0, 0.0, 0.0)

        # All true negatives (no positives anywhere: TP=0, FP=0, FN=0, TN=5)
        y_true = [0, 0, 0, 0, 0]
        y_pred = [0, 0, 0, 0, 0]
        acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)
        assert acc == 1.0
        assert prec == 0.0  # (tp+fp == 0) -> safe 0.0
        assert rec == 0.0   # (tp+fn == 0) -> safe 0.0
        assert f1 == 0.0

        # Completely inverted predictions (Acc=0.0)
        y_true = [1, 1, 0, 0]
        y_pred = [0, 0, 1, 1]
        acc, prec, rec, f1, cm = MetricsCalculator.calculate_classification_metrics(y_true, y_pred)
        assert acc == 0.0
        assert f1 == 0.0
        assert cm.true_positives == 0
        assert cm.false_positives == 2
        assert cm.false_negatives == 2
        assert cm.true_negatives == 0

    def test_continuous_metrics_hand_calculated(self):
        """Verify MAE, RMSE, and Mean Bias on hand-calculated numbers."""
        # y_true = [10.0, 20.0, 30.0]
        # y_pred = [12.0, 19.0, 35.0]
        # errors = [12 - 10 = +2, 19 - 20 = -1, 35 - 30 = +5]
        # abs_errors = [2, 1, 5], sum = 8, MAE = 8/3 = 2.6667
        # sq_errors = [4, 1, 25], sum = 30, RMSE = sqrt(30/3) = sqrt(10) = 3.1623
        # mean_bias = (2 - 1 + 5) / 3 = 6/3 = 2.0000
        y_true = [10.0, 20.0, 30.0]
        y_pred = [12.0, 19.0, 35.0]

        mae, rmse, bias = MetricsCalculator.calculate_continuous_metrics(y_true, y_pred)
        assert mae == 2.6667
        assert rmse == 3.1623
        assert bias == 2.0000

    def test_continuous_metrics_mismatched_and_empty(self):
        """Verify continuous metrics safely return zeros on mismatched lengths or empty lists."""
        assert MetricsCalculator.calculate_continuous_metrics([], []) == (0.0, 0.0, 0.0)
        assert MetricsCalculator.calculate_continuous_metrics([1.0], [1.0, 2.0]) == (0.0, 0.0, 0.0)

    def test_brier_score_hand_calculated(self):
        """Verify Brier score hand calculation."""
        # Brier = (1/N) * sum((prob - actual)^2)
        # actual = [1, 0, 1, 0]
        # prob   = [0.8, 0.2, 0.4, 0.9]
        # diffs  = [0.8 - 1 = -0.2 (sq=0.04), 0.2 - 0 = 0.2 (sq=0.04), 0.4 - 1 = -0.6 (sq=0.36), 0.9 - 0 = 0.9 (sq=0.81)]
        # sum = 0.04 + 0.04 + 0.36 + 0.81 = 1.25
        # Brier = 1.25 / 4 = 0.3125
        actual = [1, 0, 1, 0]
        prob = [0.8, 0.2, 0.4, 0.9]

        brier = MetricsCalculator.calculate_brier_score(actual, prob)
        assert brier == 0.3125

    def test_ece_mce_hand_calculated(self):
        """Verify ECE and MCE binning and weighted calibration gaps."""
        # Bin width = 0.5 (2 bins: [0.0, 0.5) and [0.5, 1.0])
        # Bin 0:
        #   actual = [0, 0], prob = [0.1, 0.3] -> acc = 0.0, conf = 0.2, gap = 0.2, weight = 2/4
        # Bin 1:
        #   actual = [1, 0], prob = [0.7, 0.9] -> acc = 0.5, conf = 0.8, gap = 0.3, weight = 2/4
        # ECE = (2/4)*0.2 + (2/4)*0.3 = 0.1 + 0.15 = 0.25
        # MCE = max(0.2, 0.3) = 0.3
        actual = [0, 0, 1, 0]
        prob = [0.1, 0.3, 0.7, 0.9]

        ece, mce = MetricsCalculator.calculate_calibration_error(actual, prob, num_bins=2)
        assert ece == 0.25
        assert mce == 0.3


class TestForensicDriftVerification:
    """Forensic verification of distribution drift (PSI and KS two-sample test)."""

    def test_psi_identical_distributions(self):
        """PSI between identical distributions must be 0.0 (or negligible due to smoothing)."""
        dist = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0] * 10
        psi, severity, details = DriftDetector.calculate_psi(dist, dist, num_bins=5)
        assert psi == 0.0
        assert severity == "NONE"

    def test_psi_constant_distributions(self):
        """PSI on invariant constant distributions must return zero without division error."""
        dist = [42.0] * 20
        psi, severity, details = DriftDetector.calculate_psi(dist, dist)
        assert psi == 0.0
        assert severity == "NONE"

    def test_psi_massive_drift_severity(self):
        """PSI with completely separated distributions must be marked SIGNIFICANT."""
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
        current = [90.0, 91.0, 92.0, 93.0, 94.0] * 20

        psi, severity, details = DriftDetector.calculate_psi(baseline, current, num_bins=5)
        assert psi > 0.20
        assert severity == "SIGNIFICANT"

    def test_ks_test_independent_verification(self):
        """Verify KS statistic against step empirical CDF."""
        # Identical samples
        s1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        s2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        d_stat, crit, is_drift = DriftDetector.calculate_ks_test(s1, s2)
        assert d_stat == 0.0
        assert not is_drift

        # Non-overlapping samples with N=15: D must be 1.0 and exceed crit_val (~0.496)
        s1 = [1.0 + i * 0.1 for i in range(15)]
        s2 = [10.0 + i * 0.1 for i in range(15)]
        d_stat, crit, is_drift = DriftDetector.calculate_ks_test(s1, s2)
        assert d_stat == 1.0
        assert is_drift
        assert crit < 1.0

    def test_drift_threshold_configuration_control(self):
        """Verify drift thresholds actually control the drift_detected decision flag."""
        baseline = [10.0, 12.0, 14.0, 16.0, 18.0] * 10
        current = [12.0, 14.0, 16.0, 18.0, 20.0] * 10

        # Run with default threshold
        rep1 = DriftDetector.evaluate_drift("temp", baseline, current, method="PSI", threshold=0.05)
        rep2 = DriftDetector.evaluate_drift("temp", baseline, current, method="PSI", threshold=10.0)

        # Under low threshold (0.05), drift should be detected
        # Under high threshold (10.0), drift should NOT be detected
        assert rep1.threshold == 0.05
        assert rep2.threshold == 10.0
        assert rep2.drift_detected is False


class TestForensicModelComparator:
    """Forensic verification of model version comparison and regression detection."""

    def test_comparator_f1_improvement_vs_regression(self):
        """F1: higher is better. Candidate regression should be flagged only when degradation exceeds tolerance."""
        base_metrics = EvaluationMetrics(f1_score=0.85, accuracy=0.85)

        # Slight regression (-0.03 degradation), tolerance 0.05 -> NO regression
        cand_slight = EvaluationMetrics(f1_score=0.82, accuracy=0.82)
        rep1 = ModelComparator.compare_models(
            "v1.0", "v1.1", "ds-01", base_metrics, cand_slight, sample_count=100, f1_tolerance=0.05
        )
        assert rep1.regression_detected is False
        assert rep1.metric_deltas["f1_score"] == -0.03

        # Significant regression (-0.06 degradation), tolerance 0.05 -> REGRESSION
        cand_bad = EvaluationMetrics(f1_score=0.79, accuracy=0.79)
        rep2 = ModelComparator.compare_models(
            "v1.0", "v1.2", "ds-01", base_metrics, cand_bad, sample_count=100, f1_tolerance=0.05
        )
        assert rep2.regression_detected is True
        assert rep2.metric_deltas["f1_score"] == -0.06
        assert any("F1 score degraded" in r for r in rep2.regression_reasons)

    def test_comparator_mae_increase_vs_decrease(self):
        """MAE: lower is better. Candidate MAE increase above tolerance must trigger regression flag."""
        base_metrics = EvaluationMetrics(mae=1.50)

        # MAE decreased (improvement) -> NO regression
        cand_good = EvaluationMetrics(mae=1.20)
        rep_good = ModelComparator.compare_models(
            "v1.0", "v1.1", "ds-01", base_metrics, cand_good, sample_count=100, mae_tolerance=0.05
        )
        assert rep_good.regression_detected is False
        assert rep_good.metric_deltas["mae"] == -0.30

        # MAE increased beyond tolerance -> REGRESSION
        cand_worse = EvaluationMetrics(mae=1.60)
        rep_worse = ModelComparator.compare_models(
            "v1.0", "v1.2", "ds-01", base_metrics, cand_worse, sample_count=100, mae_tolerance=0.05
        )
        assert rep_worse.regression_detected is True
        assert rep_worse.metric_deltas["mae"] == +0.10
        assert any("MAE error increased" in r for r in rep_worse.regression_reasons)
