"""
Reliability analysis and diagram calculation for Phase 10 Calibration.
Partitions probability predictions into standardized bins and calculates calibration gaps.
"""

from typing import List, Tuple
from intelligence.calibration.types import ReliabilityBin


class ReliabilityAnalyzer:
    """
    Computes reliability diagram bins and empirical accuracy distributions.
    """

    @classmethod
    def compute_reliability_bins(
        cls,
        probabilities: List[float],
        labels: List[int],
        num_bins: int = 10,
    ) -> List[ReliabilityBin]:
        """
        Partitions probabilities into 10 bins [0.0, 0.1), [0.1, 0.2), ...
        and computes empirical accuracy, mean forecast probability, sample count, and calibration gap.
        """
        if not probabilities or not labels or len(probabilities) != len(labels):
            return []

        bin_width = 1.0 / num_bins
        bins: List[ReliabilityBin] = []

        for b in range(num_bins):
            b_low = round(b * bin_width, 2)
            b_high = round((b + 1) * bin_width, 2)

            pairs = [
                (p, y) for p, y in zip(probabilities, labels)
                if (b_low <= p < b_high) or (b == num_bins - 1 and p >= b_high)
            ]

            count = len(pairs)
            if count > 0:
                mean_p = round(sum(p for p, _ in pairs) / count, 4)
                acc = round(sum(y for _, y in pairs) / count, 4)
                gap = round(abs(acc - mean_p), 4)
            else:
                mean_p = round((b_low + b_high) / 2.0, 4)
                acc = 0.0
                gap = 0.0

            bins.append(ReliabilityBin(
                bin_index=b,
                lower_bound=b_low,
                upper_bound=b_high,
                mean_predicted_prob=mean_p,
                empirical_accuracy=acc,
                sample_count=count,
                calibration_gap=gap,
            ))

        return bins
