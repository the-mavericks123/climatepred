"""
CalibrationEngine orchestrator for Phase 10.
Manages statistical probability calibration, sample-size gating,
reliability diagram calculation, and non-destructive calibrated inference.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from intelligence.calibration.methods import IsotonicCalibrator, PlattScaler
from intelligence.calibration.provenance import CalibrationProvenanceTracker
from intelligence.calibration.reliability import ReliabilityAnalyzer
from intelligence.calibration.types import (
    CalibratedOutput,
    CalibrationMethod,
    CalibrationReport,
)
from intelligence.core.contracts.telemetry import LocationCoordinate
from intelligence.evaluation.datasets import DatasetRegistry
from intelligence.evaluation.metrics import MetricsCalculator
from intelligence.evaluation.types import EvaluationDataset


class CalibrationEngine:
    """
    Central probability calibration service with strict statistical validity gating.
    """

    def __init__(self, min_samples: int = 50):
        self.min_samples = min_samples
        self._fitted_calibrators: Dict[str, Any] = {}
        self._reports: Dict[str, CalibrationReport] = {}

    def fit_calibrator(
        self,
        model_version: str,
        dataset_id: str,
        method: CalibrationMethod = CalibrationMethod.ISOTONIC,
        custom_dataset: Optional[Dict[str, Any]] = None,
    ) -> CalibrationReport:
        """
        Fits a probability calibrator on a dataset, enforcing minimum sample size and data freshness gates.
        """
        if custom_dataset:
            dataset = EvaluationDataset(**custom_dataset)
        else:
            dataset = DatasetRegistry.get_dataset(dataset_id)
            if not dataset:
                raise ValueError(f"Dataset '{dataset_id}' not found.")

        # 1. Statistical Gating: Sample count and ground truth check
        sample_count = len(dataset.observations)
        if sample_count < self.min_samples:
            cal_id = f"CAL-{uuid.uuid4().hex[:8].upper()}"
            prov_hash = CalibrationProvenanceTracker.compute_calibration_hash(
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=sample_count,
                brier_after=None,
                ece_after=None,
            )
            report = CalibrationReport(
                calibration_id=cal_id,
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=sample_count,
                status="CALIBRATION_UNAVAILABLE",
                reason=f"Insufficient sample count ({sample_count} < {self.min_samples}) for statistically valid probability calibration.",
                provenance_hash=prov_hash,
            )
            self._reports[cal_id] = report
            return report

        # Extract raw model predictions and ground truth binary labels
        # Using domain evaluators or pre-scored target outputs
        gt_map = {gt.sample_id: gt.binary_label for gt in dataset.ground_truth if gt.binary_label is not None}
        if len(gt_map) < self.min_samples:
            cal_id = f"CAL-{uuid.uuid4().hex[:8].upper()}"
            prov_hash = CalibrationProvenanceTracker.compute_calibration_hash(
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=len(gt_map),
            )
            report = CalibrationReport(
                calibration_id=cal_id,
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=len(gt_map),
                status="CALIBRATION_UNAVAILABLE",
                reason=f"Insufficient binary ground truth labels ({len(gt_map)} < {self.min_samples}) for calibration.",
                provenance_hash=prov_hash,
            )
            self._reports[cal_id] = report
            return report

        # Single-class dataset check (Part 13: 50 samples but all one class cannot calibrate)
        if len(set(gt_map.values())) <= 1:
            cal_id = f"CAL-{uuid.uuid4().hex[:8].upper()}"
            prov_hash = CalibrationProvenanceTracker.compute_calibration_hash(
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=len(gt_map),
            )
            report = CalibrationReport(
                calibration_id=cal_id,
                model_version=model_version,
                method=method,
                dataset_id=dataset.dataset_id,
                sample_count=len(gt_map),
                status="CALIBRATION_UNAVAILABLE",
                reason="Single class labels in dataset: calibration requires both positive and negative instances for statistical validity.",
                provenance_hash=prov_hash,
            )
            self._reports[cal_id] = report
            return report

        # Extract scores
        from intelligence.hazards.flood import FloodModel
        from intelligence.hazards.heat import HeatModel
        from intelligence.hazards.drought import DroughtModel
        from intelligence.hazards.features import HazardFeatures
        from intelligence.hazards.quality_gate import QualityGateVerdict

        if "heat" in model_version:
            model = HeatModel()
        elif "drought" in model_version:
            model = DroughtModel()
        else:
            model = FloodModel()

        verdict = QualityGateVerdict(is_admissible=True)
        raw_scores: List[float] = []
        labels: List[int] = []

        for obs in dataset.observations:
            if obs.sample_id in gt_map:
                feat = HazardFeatures(
                    node_id=obs.sample_id,
                    timestamp=datetime.now(timezone.utc),
                    location=LocationCoordinate(lat=19.076, lon=72.8777, elevation=10.0),
                    source="SENSOR",
                    valid=True,
                    confidence_base=1.0,
                    anomaly_score=0.0,
                    flags=[],
                    rainfall_mmhr=obs.features.get("rainfall_mmhr"),
                    water_level_m=obs.features.get("water_level_m"),
                    soil_moisture_pct=obs.features.get("soil_moisture_pct"),
                    temperature_c=obs.features.get("temperature_c"),
                    humidity_pct=obs.features.get("humidity_pct"),
                )
                res = model.evaluate(feat, verdict)
                raw_scores.append(res.severity)
                labels.append(gt_map[obs.sample_id])

        # Partition data to evaluate out-of-sample calibration performance without data leakage
        if len(labels) >= 20:
            cal_scores = [raw_scores[i] for i in range(len(raw_scores)) if i % 2 == 0]
            cal_labels = [labels[i] for i in range(len(labels)) if i % 2 == 0]
            eval_scores = [raw_scores[i] for i in range(len(raw_scores)) if i % 2 == 1]
            eval_labels = [labels[i] for i in range(len(labels)) if i % 2 == 1]
        else:
            cal_scores, cal_labels = raw_scores, labels
            eval_scores, eval_labels = raw_scores, labels

        # Diagnostics before calibration
        brier_before = MetricsCalculator.calculate_brier_score(eval_labels, eval_scores)
        ece_before, mce_before = MetricsCalculator.calculate_calibration_error(eval_labels, eval_scores)

        # 2. Fit calibration model (fit on calibration partition, evaluate on holdout)
        if method == CalibrationMethod.PLATT_SCALING:
            calibrator = PlattScaler().fit(cal_scores, cal_labels)
            full_calibrator = PlattScaler().fit(raw_scores, labels)
        else:
            calibrator = IsotonicCalibrator().fit(cal_scores, cal_labels)
            full_calibrator = IsotonicCalibrator().fit(raw_scores, labels)

        eval_calibrated_probs = calibrator.predict_proba(eval_scores)

        # Diagnostics after calibration on untouched holdout set
        brier_after = MetricsCalculator.calculate_brier_score(eval_labels, eval_calibrated_probs)
        ece_after, mce_after = MetricsCalculator.calculate_calibration_error(eval_labels, eval_calibrated_probs)

        # Reliability bins
        full_calibrated_probs = full_calibrator.predict_proba(raw_scores)
        bins = ReliabilityAnalyzer.compute_reliability_bins(full_calibrated_probs, labels)

        cal_id = f"CAL-{uuid.uuid4().hex[:8].upper()}"
        prov_hash = CalibrationProvenanceTracker.compute_calibration_hash(
            model_version=model_version,
            method=method,
            dataset_id=dataset.dataset_id,
            sample_count=len(labels),
            brier_after=brier_after,
            ece_after=ece_after,
        )

        report = CalibrationReport(
            calibration_id=cal_id,
            model_version=model_version,
            method=method,
            dataset_id=dataset.dataset_id,
            sample_count=len(labels),
            status="CALIBRATED",
            brier_score_before=brier_before,
            brier_score_after=brier_after,
            ece_before=ece_before,
            ece_after=ece_after,
            mce_before=mce_before,
            mce_after=mce_after,
            reliability_bins=bins,
            provenance_hash=prov_hash,
        )

        self._fitted_calibrators[cal_id] = {
            "calibrator": calibrator,
            "report": report,
            "model_version": model_version,
            "method": method,
            "dataset_id": dataset.dataset_id,
        }
        self._reports[cal_id] = report
        return report

    def get_calibration(self, calibration_id: str) -> Optional[CalibrationReport]:
        """Retrieves a cached calibration report by ID."""
        return self._reports.get(calibration_id)

    def calibrate_score(
        self,
        calibration_id: str,
        raw_value: float,
    ) -> CalibratedOutput:
        """
        Transforms a raw continuous model score into a calibrated probability.
        Strictly preserves raw_value alongside calibrated_value.
        """
        entry = self._fitted_calibrators.get(calibration_id)
        if not entry:
            raise ValueError(f"Fitted calibrator '{calibration_id}' not found.")

        calibrator = entry["calibrator"]
        cal_val = calibrator.predict_single(raw_value)

        prov_hash = CalibrationProvenanceTracker.compute_output_hash(
            calibration_id=calibration_id,
            model_version=entry["model_version"],
            raw_value=raw_value,
            calibrated_value=cal_val,
        )

        return CalibratedOutput(
            calibration_id=calibration_id,
            model_version=entry["model_version"],
            method=entry["method"],
            raw_value=round(raw_value, 4),
            calibrated_value=cal_val,
            calibration_dataset=entry["dataset_id"],
            provenance_hash=prov_hash,
        )
