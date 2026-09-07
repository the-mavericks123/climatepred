"""
Contract tests for Phase 10 Evaluation schemas.
"""

import pytest
from intelligence.evaluation.types import (
    ConfusionMatrix,
    DatasetType,
    EvaluationDataset,
    EvaluationMetrics,
    EvaluationObservation,
    EvaluationReport,
    GroundTruthRecord,
    GroundTruthStatus,
    ModelComparisonReport,
)


def test_confusion_matrix_schema():
    cm = ConfusionMatrix(true_positives=15, false_positives=3, true_negatives=70, false_negatives=2)
    assert cm.true_positives == 15
    assert cm.false_negatives == 2
    dump = cm.model_dump()
    assert dump["true_positives"] == 15


def test_evaluation_metrics_defaults():
    m = EvaluationMetrics(f1_score=0.88, mae=0.04)
    assert m.f1_score == 0.88
    assert m.mae == 0.04
    assert m.precision is None
    assert m.brier_score is None


def test_dataset_types_enum():
    assert DatasetType.REAL.value == "REAL"
    assert DatasetType.SYNTHETIC.value == "SYNTHETIC"
    assert DatasetType.HISTORICAL.value == "HISTORICAL"
    assert DatasetType.BENCHMARK.value == "BENCHMARK"


def test_ground_truth_status_enum():
    assert GroundTruthStatus.AVAILABLE.value == "AVAILABLE"
    assert GroundTruthStatus.UNAVAILABLE.value == "UNAVAILABLE"
    assert GroundTruthStatus.INSUFFICIENT_GROUND_TRUTH.value == "INSUFFICIENT_GROUND_TRUTH"


def test_evaluation_dataset_valid():
    ds = EvaluationDataset(
        dataset_id="DATA-001",
        version="1.0",
        dataset_type=DatasetType.BENCHMARK,
        domain="flood",
        observations=[
            EvaluationObservation(sample_id="S-1", features={"rain": 20.0})
        ],
        ground_truth=[
            GroundTruthRecord(sample_id="S-1", binary_label=0)
        ],
    )
    assert len(ds.observations) == 1
    assert len(ds.ground_truth) == 1


def test_evaluation_report_schema():
    rep = EvaluationReport(
        evaluation_id="EVAL-001",
        model_version="flood-v1",
        dataset_id="DATA-001",
        sample_count=100,
        metrics=EvaluationMetrics(f1_score=0.92),
        provenance_hash="b" * 64,
    )
    assert rep.status == "COMPLETED"
    assert rep.metrics.f1_score == 0.92


def test_model_comparison_report_schema():
    rep = ModelComparisonReport(
        comparison_id="COMP-001",
        baseline_model_version="flood-v1",
        candidate_model_version="flood-v2",
        dataset_id="DATA-001",
        sample_count=50,
        baseline_metrics=EvaluationMetrics(f1_score=0.85),
        candidate_metrics=EvaluationMetrics(f1_score=0.90),
        metric_deltas={"f1_score": 0.05},
        regression_detected=False,
        provenance_hash="c" * 64,
    )
    assert rep.metric_deltas["f1_score"] == 0.05
    assert rep.regression_detected is False
