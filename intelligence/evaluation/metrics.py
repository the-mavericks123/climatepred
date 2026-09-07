"""
Pure standard-library mathematical evaluation metrics for Phase 10.
Implements precision, recall, F1, accuracy, MAE, RMSE, mean bias, Brier score,
Expected Calibration Error (ECE), and Maximum Calibration Error (MCE) with zero external dependencies.
"""

import math
from typing import List, Optional, Tuple
from intelligence.evaluation.types import ConfusionMatrix, EvaluationMetrics


class MetricsCalculator:
    """
    Statistically rigorous metric calculations implemented in pure Python.
    """

    @classmethod
    def calculate_classification_metrics(
        cls,
        y_true: List[int],
        y_pred: List[int],
    ) -> Tuple[float, float, float, float, ConfusionMatrix]:
        """
        Calculates Accuracy, Precision, Recall, F1 score, and Confusion Matrix for binary labels.
        """
        if not y_true or not y_pred or len(y_true) != len(y_pred):
            return 0.0, 0.0, 0.0, 0.0, ConfusionMatrix()

        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
        tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

        total = len(y_true)
        acc = (tp + tn) / total if total > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        cm = ConfusionMatrix(true_positives=tp, false_positives=fp, true_negatives=tn, false_negatives=fn)
        return round(acc, 4), round(prec, 4), round(rec, 4), round(f1, 4), cm

    @classmethod
    def calculate_continuous_metrics(
        cls,
        y_true: List[float],
        y_pred: List[float],
    ) -> Tuple[float, float, float]:
        """
        Calculates Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and Mean Bias.
        """
        if not y_true or not y_pred or len(y_true) != len(y_pred):
            return 0.0, 0.0, 0.0

        n = len(y_true)
        errors = [p - t for t, p in zip(y_true, y_pred)]
        abs_errors = [abs(e) for e in errors]
        sq_errors = [e * e for e in errors]

        mae = sum(abs_errors) / n
        rmse = math.sqrt(sum(sq_errors) / n)
        mean_bias = sum(errors) / n

        return round(mae, 4), round(rmse, 4), round(mean_bias, 4)

    @classmethod
    def calculate_brier_score(
        cls,
        y_true: List[int],
        y_prob: List[float],
    ) -> float:
        """
        Calculates the Brier score: (1/N) * sum((prob - actual)^2).
        Strictly measures accuracy of probabilistic predictions in [0.0, 1.0]. Lower is better.
        """
        if not y_true or not y_prob or len(y_true) != len(y_prob):
            return 0.0

        n = len(y_true)
        total_sq_diff = sum((p - y) ** 2 for y, p in zip(y_true, y_prob))
        return round(total_sq_diff / n, 4)

    @classmethod
    def calculate_calibration_error(
        cls,
        y_true: List[int],
        y_prob: List[float],
        num_bins: int = 10,
    ) -> Tuple[float, float]:
        """
        Calculates Expected Calibration Error (ECE) and Maximum Calibration Error (MCE)
        by partitioning probability forecasts into equal-width bins.
        ECE = sum((|bin| / N) * |acc(bin) - conf(bin)|)
        MCE = max(|acc(bin) - conf(bin)|)
        """
        if not y_true or not y_prob or len(y_true) != len(y_prob):
            return 0.0, 0.0

        n = len(y_true)
        bin_width = 1.0 / num_bins
        ece = 0.0
        mce = 0.0

        for b in range(num_bins):
            bin_lower = b * bin_width
            bin_upper = (b + 1) * bin_width

            # Collect samples falling in bin [bin_lower, bin_upper) or upper closed on 1.0
            bin_samples = [
                (y, p) for y, p in zip(y_true, y_prob)
                if (bin_lower <= p < bin_upper) or (b == num_bins - 1 and p >= bin_upper)
            ]

            bin_count = len(bin_samples)
            if bin_count > 0:
                bin_acc = sum(y for y, _ in bin_samples) / bin_count
                bin_conf = sum(p for _, p in bin_samples) / bin_count
                gap = abs(bin_acc - bin_conf)

                ece += (bin_count / n) * gap
                if gap > mce:
                    mce = gap

        return round(ece, 4), round(mce, 4)
