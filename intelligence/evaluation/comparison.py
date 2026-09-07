"""
Model version comparator and regression detector for Phase 10 Evaluation.
Compares performance between baseline and candidate model versions, computing
metric deltas and alerting on statistically meaningful model regression.
"""

import hashlib
import json
import uuid
from typing import Dict, List, Optional
from intelligence.evaluation.types import (
    EvaluationMetrics,
    ModelComparisonReport,
)


class ModelComparator:
    """
    Compares two model evaluation results and flags performance regression.
    """

    @classmethod
    def compare_models(
        cls,
        baseline_version: str,
        candidate_version: str,
        dataset_id: str,
        baseline_metrics: EvaluationMetrics,
        candidate_metrics: EvaluationMetrics,
        sample_count: int,
        f1_tolerance: float = 0.05,
        mae_tolerance: float = 0.05,
    ) -> ModelComparisonReport:
        """
        Contrasts baseline and candidate metrics, computing deltas and regression flags.
        Delta = candidate - baseline (positive F1 delta is improvement, positive MAE delta is regression).
        """
        deltas: Dict[str, float] = {}
        reg_reasons: List[str] = []

        # F1 Score comparison
        if baseline_metrics.f1_score is not None and candidate_metrics.f1_score is not None:
            f1_delta = round(candidate_metrics.f1_score - baseline_metrics.f1_score, 4)
            deltas["f1_score"] = f1_delta
            if f1_delta < -f1_tolerance:
                reg_reasons.append(f"F1 score degraded by {abs(f1_delta):.4f} (exceeds tolerance {f1_tolerance})")

        # Precision comparison
        if baseline_metrics.precision is not None and candidate_metrics.precision is not None:
            deltas["precision"] = round(candidate_metrics.precision - baseline_metrics.precision, 4)

        # Recall comparison
        if baseline_metrics.recall is not None and candidate_metrics.recall is not None:
            deltas["recall"] = round(candidate_metrics.recall - baseline_metrics.recall, 4)

        # MAE comparison
        if baseline_metrics.mae is not None and candidate_metrics.mae is not None:
            mae_delta = round(candidate_metrics.mae - baseline_metrics.mae, 4)
            deltas["mae"] = mae_delta
            if mae_delta > mae_tolerance:
                reg_reasons.append(f"MAE error increased by {mae_delta:.4f} (exceeds tolerance {mae_tolerance})")

        # Brier Score comparison
        if baseline_metrics.brier_score is not None and candidate_metrics.brier_score is not None:
            deltas["brier_score"] = round(candidate_metrics.brier_score - baseline_metrics.brier_score, 4)

        regression_detected = len(reg_reasons) > 0

        # Provenance
        payload = {
            "baseline_version": baseline_version,
            "candidate_version": candidate_version,
            "dataset_id": dataset_id,
            "deltas": deltas,
            "sample_count": sample_count,
            "regression_detected": regression_detected,
        }
        prov_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

        return ModelComparisonReport(
            comparison_id=f"COMPARE-{uuid.uuid4().hex[:8].upper()}",
            baseline_model_version=baseline_version,
            candidate_model_version=candidate_version,
            dataset_id=dataset_id,
            sample_count=sample_count,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            metric_deltas=deltas,
            regression_detected=regression_detected,
            regression_reasons=reg_reasons,
            provenance_hash=prov_hash,
        )
