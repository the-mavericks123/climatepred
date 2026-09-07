"""
Climate Eye View — Phase 10 Evaluation Data Contracts.
Defines schemas for evaluation datasets, ground-truth records, evaluation metrics,
reports, model comparisons, and data drift diagnostics.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetType(str, Enum):
    """Categorization of evaluation datasets."""
    REAL = "REAL"
    SYNTHETIC = "SYNTHETIC"
    HISTORICAL = "HISTORICAL"
    REPLAY = "REPLAY"
    BENCHMARK = "BENCHMARK"


class GroundTruthStatus(str, Enum):
    """Availability of authoritative target labels."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_GROUND_TRUTH = "INSUFFICIENT_GROUND_TRUTH"


class EvaluationObservation(BaseModel):
    """Single input sample for model evaluation."""
    sample_id: str = Field(..., description="Unique sample identifier")
    features: Dict[str, Any] = Field(..., description="Input telemetry/features dictionary")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual sample metadata")


class GroundTruthRecord(BaseModel):
    """Authoritative reference outcome for an observation."""
    sample_id: str = Field(..., description="Corresponding sample identifier")
    binary_label: Optional[int] = Field(default=None, ge=0, le=1, description="Binary event occurrence (0 or 1)")
    continuous_target: Optional[float] = Field(default=None, description="Continuous ground truth measurement")
    categorical_class: Optional[str] = Field(default=None, description="Ground truth categorical classification")
    causal_chain: Optional[List[str]] = Field(default=None, description="Ground truth verified causal cascade chain")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    """
    Versioned container of inputs and ground truth for model benchmarking.
    """
    dataset_id: str = Field(..., description="Unique dataset identifier")
    version: str = Field(default="1.0", description="Semantic dataset version")
    dataset_type: DatasetType = Field(default=DatasetType.BENCHMARK, description="Dataset provenance category")
    description: str = Field(default="", description="Description of dataset domain and coverage")
    domain: str = Field(..., description="Target domain: 'flood', 'heat', 'prediction', 'evacuation', 'response', etc.")
    observations: List[EvaluationObservation] = Field(default_factory=list)
    ground_truth: List[GroundTruthRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_hash: Optional[str] = Field(default=None, description="Cryptographic SHA-256 fingerprint")


class ConfusionMatrix(BaseModel):
    """Standard binary classification confusion matrix."""
    true_positives: int = Field(default=0, ge=0)
    false_positives: int = Field(default=0, ge=0)
    true_negatives: int = Field(default=0, ge=0)
    false_negatives: int = Field(default=0, ge=0)


class EvaluationMetrics(BaseModel):
    """Standard quantitative evaluation metrics across domains."""
    # Binary / Classification metrics
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confusion_matrix: Optional[ConfusionMatrix] = Field(default=None)

    # Continuous / Regression metrics
    mae: Optional[float] = Field(default=None, ge=0.0, description="Mean Absolute Error")
    rmse: Optional[float] = Field(default=None, ge=0.0, description="Root Mean Squared Error")
    mean_bias: Optional[float] = Field(default=None, description="Mean error (predicted - ground_truth)")

    # Horizon-specific metrics for prediction
    horizon_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Metrics broken down by forecast horizon (+30m, +60m, +360m)")

    # Probabilistic / Calibration metrics
    brier_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    expected_calibration_error: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    maximum_calibration_error: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # System quality metrics for response planning & evacuation
    unsupported_action_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    contradiction_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    unsafe_shelter_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    human_review_compliance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    causal_chain_accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class EvaluationReport(BaseModel):
    """
    Standardized, auditable report summarizing model performance on an evaluation dataset.
    """
    evaluation_id: str = Field(..., description="Unique evaluation run identifier")
    model_version: str = Field(..., description="Target model version evaluated")
    dataset_id: str = Field(..., description="Benchmark dataset evaluated against")
    dataset_version: str = Field(default="1.0")
    dataset_type: DatasetType = Field(default=DatasetType.BENCHMARK)
    status: str = Field(default="COMPLETED", description="Status: 'COMPLETED', 'INSUFFICIENT_GROUND_TRUTH', 'FAILED'")
    ground_truth_status: GroundTruthStatus = Field(default=GroundTruthStatus.AVAILABLE)
    sample_count: int = Field(default=0, ge=0)
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_hash: str = Field(..., description="Deterministic SHA-256 fingerprint of evaluation inputs and results")


class ModelComparisonReport(BaseModel):
    """Comparative evaluation report contrasting two model versions on the same dataset."""
    comparison_id: str = Field(...)
    baseline_model_version: str = Field(...)
    candidate_model_version: str = Field(...)
    dataset_id: str = Field(...)
    sample_count: int = Field(default=0)
    baseline_metrics: EvaluationMetrics = Field(...)
    candidate_metrics: EvaluationMetrics = Field(...)
    metric_deltas: Dict[str, float] = Field(default_factory=dict, description="candidate_metric - baseline_metric")
    regression_detected: bool = Field(default=False)
    regression_reasons: List[str] = Field(default_factory=list)
    provenance_hash: str = Field(...)


class DriftReport(BaseModel):
    """Distribution drift diagnostic comparing baseline vs operational feature distributions."""
    report_id: str = Field(...)
    feature_name: str = Field(...)
    method: str = Field(..., description="'PSI' or 'KS_TEST'")
    drift_detected: bool = Field(...)
    metric_value: float = Field(...)
    threshold: float = Field(...)
    baseline_sample_count: int = Field(...)
    current_sample_count: int = Field(...)
    severity: str = Field(default="NONE", description="'NONE', 'MODERATE', 'SIGNIFICANT'")
    details: Dict[str, Any] = Field(default_factory=dict)
    provenance_hash: str = Field(...)


class EvaluationRunRequest(BaseModel):
    """Request payload for POST /api/v1/evaluation/run."""
    model_version: str = Field(...)
    dataset_id: str = Field(...)
    custom_dataset: Optional[Dict[str, Any]] = Field(default=None)


class ModelCompareRequest(BaseModel):
    """Request payload for POST /api/v1/models/compare."""
    baseline_model_version: str = Field(...)
    candidate_model_version: str = Field(...)
    dataset_id: str = Field(...)


class DriftEvaluateRequest(BaseModel):
    """Request payload for POST /api/v1/drift/evaluate."""
    feature_name: str = Field(...)
    baseline_samples: List[float] = Field(...)
    current_samples: List[float] = Field(...)
    method: Optional[str] = Field(default="PSI")
    threshold: Optional[float] = Field(default=None)
