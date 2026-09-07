"""
Distribution drift diagnostics for Phase 10 Evaluation.
Implements Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) two-sample test
in pure standard Python without external statistical libraries.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
from intelligence.evaluation.types import DriftReport


class DriftDetector:
    """
    Evaluates input distribution drift between reference baseline and operational telemetry.
    """

    @classmethod
    def calculate_psi(
        cls,
        baseline: List[float],
        current: List[float],
        num_bins: int = 10,
        epsilon: float = 1e-4,
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Computes the Population Stability Index (PSI) between two numeric sample distributions.
        PSI = sum((P_i - Q_i) * ln(P_i / Q_i))
        """
        if not baseline or not current:
            return 0.0, "NONE", {"error": "Empty distribution provided"}

        min_val = min(min(baseline), min(current))
        max_val = max(max(baseline), max(current))

        if math.isclose(min_val, max_val):
            return 0.0, "NONE", {"note": "Identical constant distributions"}

        bin_width = (max_val - min_val) / num_bins
        b_count = len(baseline)
        c_count = len(current)

        psi_total = 0.0
        bin_details = []

        for b in range(num_bins):
            b_low = min_val + b * bin_width
            b_high = min_val + (b + 1) * bin_width

            # Count samples
            b_samples = sum(1 for x in baseline if (b_low <= x < b_high) or (b == num_bins - 1 and x >= b_high))
            c_samples = sum(1 for x in current if (b_low <= x < b_high) or (b == num_bins - 1 and x >= b_high))

            # Proportions with Laplace smoothing
            p = (b_samples / b_count) + epsilon
            q = (c_samples / c_count) + epsilon

            bin_psi = (p - q) * math.log(p / q)
            psi_total += bin_psi
            bin_details.append({
                "bin": b,
                "range": [round(b_low, 3), round(b_high, 3)],
                "baseline_prop": round(p - epsilon, 4),
                "current_prop": round(q - epsilon, 4),
                "bin_psi": round(bin_psi, 4),
            })

        psi_val = max(0.0, round(psi_total, 4))
        if psi_val < 0.10:
            severity = "NONE"
        elif psi_val < 0.20:
            severity = "MODERATE"
        else:
            severity = "SIGNIFICANT"

        return psi_val, severity, {"bins": bin_details}

    @classmethod
    def calculate_ks_test(
        cls,
        sample1: List[float],
        sample2: List[float],
        alpha: float = 0.05,
    ) -> Tuple[float, float, bool]:
        """
        Computes the Kolmogorov-Smirnov (KS) two-sample test statistic:
        D = sup_x |F1(x) - F2(x)|
        Returns (D_statistic, critical_value, is_drift).
        """
        if not sample1 or not sample2:
            return 0.0, 1.0, False

        n1 = len(sample1)
        n2 = len(sample2)

        # Critical value approximation for alpha = 0.05 (c = 1.36)
        c_alpha = 1.36
        crit_val = c_alpha * math.sqrt((n1 + n2) / (n1 * n2))

        # Merge and sort unique evaluation points
        s1_sorted = sorted(sample1)
        s2_sorted = sorted(sample2)
        all_vals = sorted(list(set(s1_sorted + s2_sorted)))

        import bisect
        max_d = 0.0
        for val in all_vals:
            # Empirical CDF at val: count(x <= val) / n
            f1 = bisect.bisect_right(s1_sorted, val) / n1
            f2 = bisect.bisect_right(s2_sorted, val) / n2
            d = abs(f1 - f2)
            if d > max_d:
                max_d = d

        is_drift = max_d > crit_val
        return round(max_d, 4), round(crit_val, 4), is_drift

    @classmethod
    def evaluate_drift(
        cls,
        feature_name: str,
        baseline: List[float],
        current: List[float],
        method: str = "PSI",
        threshold: Optional[float] = None,
    ) -> DriftReport:
        """Evaluates drift and returns a structured DriftReport."""
        import uuid
        method_clean = method.upper()

        if method_clean == "KS_TEST":
            d_stat, crit, drift_detected = cls.calculate_ks_test(baseline, current)
            metric_val = d_stat
            effective_thresh = threshold if threshold is not None else crit
            drift_detected = metric_val > effective_thresh
            severity = "SIGNIFICANT" if drift_detected else "NONE"
            details = {"critical_value": crit}
        else:
            # Default PSI
            effective_thresh = threshold if threshold is not None else 0.20
            psi_val, severity, details = cls.calculate_psi(baseline, current)
            metric_val = psi_val
            drift_detected = metric_val >= effective_thresh

        import hashlib
        import json
        payload = {
            "feature_name": feature_name,
            "method": method_clean,
            "metric_value": metric_val,
            "threshold": effective_thresh,
            "baseline_count": len(baseline),
            "current_count": len(current),
            "drift_detected": drift_detected,
        }
        prov_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

        return DriftReport(
            report_id=f"DRIFT-{uuid.uuid4().hex[:8].upper()}",
            feature_name=feature_name,
            method=method_clean,
            drift_detected=drift_detected,
            metric_value=metric_val,
            threshold=effective_thresh,
            baseline_sample_count=len(baseline),
            current_sample_count=len(current),
            severity=severity,
            details=details,
            provenance_hash=prov_hash,
        )
