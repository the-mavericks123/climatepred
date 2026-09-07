"""
EvaluationEngine orchestrator for Phase 10.
Executes benchmarks against versioned datasets, coordinates model comparisons,
and evaluates distribution drift.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from intelligence.evaluation.benchmarks import (
    HazardBenchmarkEvaluator,
    PredictionBenchmarkEvaluator,
    ResponsePlanBenchmarkEvaluator,
)
from intelligence.evaluation.comparison import ModelComparator
from intelligence.evaluation.datasets import DatasetRegistry
from intelligence.evaluation.drift import DriftDetector
from intelligence.evaluation.provenance import EvaluationProvenanceTracker
from intelligence.evaluation.types import (
    DriftReport,
    EvaluationDataset,
    EvaluationReport,
    GroundTruthStatus,
    ModelComparisonReport,
)


class EvaluationEngine:
    """
    Central evaluation engine managing benchmarking, comparisons, and drift analysis.
    """

    def __init__(self):
        self._reports: Dict[str, EvaluationReport] = {}
        self._comparisons: Dict[str, ModelComparisonReport] = {}

    def evaluate_model(
        self,
        model_version: str,
        dataset_id: str,
        custom_dataset: Optional[Dict[str, Any]] = None,
    ) -> EvaluationReport:
        """
        Runs model evaluation against a registered or supplied dataset.
        """
        if custom_dataset:
            dataset = EvaluationDataset(**custom_dataset)
        else:
            dataset = DatasetRegistry.get_dataset(dataset_id)
            if not dataset:
                raise ValueError(f"Dataset '{dataset_id}' not found in registry.")

        gt_status = GroundTruthStatus.AVAILABLE if dataset.ground_truth else GroundTruthStatus.UNAVAILABLE

        # Dispatch based on domain/model
        if "prediction" in dataset.domain or "prediction" in model_version:
            metrics, warnings = PredictionBenchmarkEvaluator.evaluate(model_version, dataset)
        elif "response" in dataset.domain:
            # Response plan benchmark
            metrics, warnings = ResponsePlanBenchmarkEvaluator.evaluate(dataset.observations)
        else:
            # Default hazard models (flood, heat, drought)
            metrics, warnings = HazardBenchmarkEvaluator.evaluate(model_version, dataset)

        status = "COMPLETED" if gt_status == GroundTruthStatus.AVAILABLE else "INSUFFICIENT_GROUND_TRUTH"

        prov_hash = EvaluationProvenanceTracker.compute_provenance_hash(
            model_version=model_version,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            status=status,
            sample_count=len(dataset.observations),
            metrics=metrics,
        )

        report = EvaluationReport(
            evaluation_id=f"EVAL-{uuid.uuid4().hex[:8].upper()}",
            model_version=model_version,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            dataset_type=dataset.dataset_type,
            status=status,
            ground_truth_status=gt_status,
            sample_count=len(dataset.observations),
            metrics=metrics,
            warnings=warnings,
            limitations=[
                "Synthetic datasets provide regression testing and engineering benchmarks, NOT real-world validation.",
                "Metrics depend strictly on the distribution of input scenarios evaluated.",
            ],
            provenance_hash=prov_hash,
        )

        self._reports[report.evaluation_id] = report
        return report

    def get_evaluation(self, evaluation_id: str) -> Optional[EvaluationReport]:
        """Retrieves a cached evaluation report by ID."""
        return self._reports.get(evaluation_id)

    run_evaluation = evaluate_model

    def compare_models(
        self,
        baseline_version: Optional[str] = None,
        candidate_version: Optional[str] = None,
        dataset_id: str = "",
        baseline_model_version: Optional[str] = None,
        candidate_model_version: Optional[str] = None,
    ) -> ModelComparisonReport:
        """Compares two model versions on the same dataset."""
        b_ver = baseline_version or baseline_model_version or ""
        c_ver = candidate_version or candidate_model_version or ""

        rep_baseline = self.evaluate_model(b_ver, dataset_id)
        rep_candidate = self.evaluate_model(c_ver, dataset_id)

        comp = ModelComparator.compare_models(
            baseline_version=b_ver,
            candidate_version=c_ver,
            dataset_id=dataset_id,
            baseline_metrics=rep_baseline.metrics,
            candidate_metrics=rep_candidate.metrics,
            sample_count=rep_baseline.sample_count,
        )
        self._comparisons[comp.comparison_id] = comp
        return comp

    def evaluate_drift(
        self,
        feature_name: str,
        baseline_samples: Optional[List[float]] = None,
        operational_samples: Optional[List[float]] = None,
        method: str = "PSI",
        threshold: Optional[float] = None,
        baseline_values: Optional[List[float]] = None,
        operational_values: Optional[List[float]] = None,
        current_samples: Optional[List[float]] = None,
    ) -> DriftReport:
        """Evaluates numerical feature drift between baseline and production telemetry."""
        b_s = baseline_samples if baseline_samples is not None else (baseline_values or [])
        o_s = operational_samples if operational_samples is not None else (current_samples if current_samples is not None else (operational_values or []))
        return DriftDetector.evaluate_drift(
            feature_name=feature_name,
            baseline=b_s,
            current=o_s,
            method=method,
            threshold=threshold,
        )
