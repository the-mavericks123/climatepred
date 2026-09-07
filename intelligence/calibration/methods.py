"""
Probabilistic calibration algorithms for Phase 10 Calibration.
Implements Platt Scaling (logistic sigmoid) and Isotonic Regression (PAVA)
in pure standard Python without external dependencies.
"""

import math
from typing import List, Tuple


class PlattScaler:
    """
    Parametric logistic calibration fitting: P(Y=1|s) = 1 / (1 + exp(A * s + B)).
    Optimized via Newton-Raphson on negative log-likelihood with Platt's regularized targets.
    """

    def __init__(self, A: float = -1.0, B: float = 0.0):
        self.A = A
        self.B = B
        self.fitted = False

    def fit(self, scores: List[float], labels: List[int], max_iter: int = 100, tol: float = 1e-6) -> "PlattScaler":
        """Fits parameters A and B using Newton-Raphson optimization."""
        if not scores or not labels or len(scores) != len(labels):
            return self

        n = len(scores)
        n_pos = sum(1 for y in labels if y == 1)
        n_neg = n - n_pos

        # Platt regularized targets to avoid over-fitting probabilities to 0 and 1
        t_pos = (n_pos + 1.0) / (n_pos + 2.0)
        t_neg = 1.0 / (n_neg + 2.0)
        targets = [t_pos if y == 1 else t_neg for y in labels]

        # Initial parameters
        A = 0.0
        B = math.log((n_neg + 1.0) / (n_pos + 1.0))

        for _ in range(max_iter):
            # Compute probabilities p_i = 1 / (1 + exp(A * s_i + B))
            grad_A = 0.0
            grad_B = 0.0
            hess_AA = 0.0
            hess_AB = 0.0
            hess_BB = 0.0

            for s, t in zip(scores, targets):
                f_val = A * s + B
                # Numerical clipping for exp
                p = 1.0 / (1.0 + math.exp(max(-50.0, min(50.0, f_val))))
                d = p - t
                w = p * (1.0 - p)

                grad_A += s * d
                grad_B += d
                hess_AA += s * s * w
                hess_AB += s * w
                hess_BB += w

            # Add small regularization to Hessian diagonal
            hess_AA += 1e-4
            hess_BB += 1e-4

            det = hess_AA * hess_BB - hess_AB * hess_AB
            if abs(det) < 1e-12:
                break

            # Newton step: delta = - H^(-1) * grad
            step_A = -(hess_BB * grad_A - hess_AB * grad_B) / det
            step_B = -(hess_AA * grad_B - hess_AB * grad_A) / det

            A += step_A
            B += step_B

            if abs(step_A) < tol and abs(step_B) < tol:
                break

        self.A = round(A, 6)
        self.B = round(B, 6)
        self.fitted = True
        return self

    def predict_proba(self, scores: List[float]) -> List[float]:
        """Maps input scores to calibrated probabilities."""
        calibrated: List[float] = []
        for s in scores:
            f_val = self.A * s + self.B
            p = 1.0 / (1.0 + math.exp(max(-50.0, min(50.0, f_val))))
            calibrated.append(round(max(0.0, min(1.0, p)), 4))
        return calibrated

    def predict_single(self, score: float) -> float:
        """Calibrates a single continuous score."""
        return self.predict_proba([score])[0]


class IsotonicCalibrator:
    """
    Non-parametric monotonic calibration via the Pool Adjacent Violators Algorithm (PAVA).
    Guarantees a non-decreasing piecewise constant probability curve in O(N) time.
    """

    def __init__(self):
        self.cutoffs: List[float] = []
        self.values: List[float] = []
        self.fitted = False

    def fit(self, scores: List[float], labels: List[int]) -> "IsotonicCalibrator":
        """Fits monotonic step function on (scores, labels)."""
        if not scores or not labels or len(scores) != len(labels):
            return self

        # 1. Sort pairs by score ascending
        paired = sorted(zip(scores, labels), key=lambda x: x[0])

        # 2. PAVA implementation
        # Each block: [sum_y, weight, max_score]
        blocks: List[List[float]] = []
        for s, y in paired:
            blocks.append([float(y), 1.0, float(s)])

            # While previous block has higher mean value than current, pool them
            while len(blocks) >= 2:
                prev = blocks[-2]
                curr = blocks[-1]
                mean_prev = prev[0] / prev[1]
                mean_curr = curr[0] / curr[1]

                if mean_prev >= mean_curr:
                    # Merge curr into prev
                    prev[0] += curr[0]
                    prev[1] += curr[1]
                    prev[2] = curr[2]  # update max_score
                    blocks.pop()
                else:
                    break

        # 3. Store step function cutoffs and calibrated values
        self.cutoffs = [b[2] for b in blocks]
        self.values = [round(max(0.0, min(1.0, b[0] / b[1])), 4) for b in blocks]
        self.fitted = True
        return self

    def predict_proba(self, scores: List[float]) -> List[float]:
        """Maps input scores to isotonic calibrated probabilities."""
        if not self.fitted or not self.cutoffs:
            return [max(0.0, min(1.0, round(s, 4))) for s in scores]

        import bisect
        calibrated: List[float] = []
        for s in scores:
            idx = bisect.bisect_left(self.cutoffs, s)
            if idx >= len(self.values):
                p = self.values[-1]
            else:
                p = self.values[idx]
            calibrated.append(round(p, 4))
        return calibrated

    def predict_single(self, score: float) -> float:
        """Calibrates a single score."""
        return self.predict_proba([score])[0]
