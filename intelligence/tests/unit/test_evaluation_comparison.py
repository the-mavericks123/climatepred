"""
Unit tests for model version comparison and regression detection in Phase 10.
"""

import pytest
from intelligence.evaluation.comparison import ModelComparator
from intelligence.evaluation.types import EvaluationMetrics


def test_model_comparison_improvement():
    m_base = EvaluationMetrics(f1_score=0.80, precision=0.80, recall=0.80, mae=0.10)
    m_cand = EvaluationMetrics(f1_score=0.88, precision=0.89, recall=0.87, mae=0.06)

    comp = ModelComparator.compare_models(
        baseline_version="flood-v1",
        candidate_version="flood-v2",
        dataset_id="EVAL-FLOOD-001",
        baseline_metrics=m_base,
        candidate_metrics=m_cand,
        sample_count=100,
    )
    assert comp.metric_deltas["f1_score"] == 0.08
    assert comp.metric_deltas["mae"] == -0.04
    assert comp.regression_detected is False
    assert len(comp.regression_reasons) == 0


def test_model_comparison_regression_detected():
    m_base = EvaluationMetrics(f1_score=0.90, mae=0.05)
    m_cand = EvaluationMetrics(f1_score=0.78, mae=0.12)  # Severe degradation

    comp = ModelComparator.compare_models(
        baseline_version="flood-v1",
        candidate_version="flood-v2",
        dataset_id="EVAL-FLOOD-001",
        baseline_metrics=m_base,
        candidate_metrics=m_cand,
        sample_count=100,
        f1_tolerance=0.05,
        mae_tolerance=0.05,
    )
    assert comp.regression_detected is True
    assert len(comp.regression_reasons) >= 1
    assert any("F1 score degraded" in r for r in comp.regression_reasons)


def test_model_comparison_provenance_determinism():
    m_base = EvaluationMetrics(f1_score=0.85)
    m_cand = EvaluationMetrics(f1_score=0.89)

    c1 = ModelComparator.compare_models("v1", "v2", "d1", m_base, m_cand, 50)
    c2 = ModelComparator.compare_models("v1", "v2", "d1", m_base, m_cand, 50)
    assert c1.provenance_hash == c2.provenance_hash
