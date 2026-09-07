"""
Provenance verification and mutation matrix for Phase 10.
Proves deterministic hashing, volatile metadata decoupling, and single-input sensitivity.
"""

import pytest
from intelligence.calibration.provenance import CalibrationProvenanceTracker
from intelligence.calibration.types import CalibrationMethod
from intelligence.evaluation.provenance import EvaluationProvenanceTracker
from intelligence.evaluation.types import EvaluationMetrics
from intelligence.explainability.provenance import ExplanationProvenanceTracker
from intelligence.explainability.types import EvidenceReference, FactorAttribution


def test_explanation_provenance_determinism():
    factors = [
        FactorAttribution(factor_name="rain", display_name="Rain", input_value=40.0, normalized_value=0.4, weight=0.4, contribution=0.16),
        FactorAttribution(factor_name="water", display_name="Water", input_value=5.0, normalized_value=0.33, weight=0.35, contribution=0.115),
    ]
    evidence = [EvidenceReference(type="telemetry", id="TEL-1")]

    h1 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", factors=factors, evidence=evidence)
    h2 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", factors=factors, evidence=evidence)
    assert h1 == h2


def test_explanation_provenance_factor_mutation():
    factors1 = [FactorAttribution(factor_name="rain", display_name="Rain", input_value=40.0, normalized_value=0.4, weight=0.4, contribution=0.16)]
    factors2 = [FactorAttribution(factor_name="rain", display_name="Rain", input_value=55.0, normalized_value=0.55, weight=0.4, contribution=0.22)]

    h1 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", factors=factors1)
    h2 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", factors=factors2)
    assert h1 != h2, "Mutating factor input value must change explanation provenance"


def test_explanation_provenance_model_version_mutation():
    h1 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED")
    h2 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v2", "OBSERVED")
    assert h1 != h2, "Mutating model version must change explanation provenance"


def test_explanation_provenance_evidence_mutation():
    ev1 = [EvidenceReference(type="telemetry", id="TEL-A")]
    ev2 = [EvidenceReference(type="telemetry", id="TEL-B")]
    h1 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", evidence=ev1)
    h2 = ExplanationProvenanceTracker.compute_provenance_hash("hazard", "HAZ-1", "flood-v1", "OBSERVED", evidence=ev2)
    assert h1 != h2, "Mutating evidence ID must change explanation provenance"


def test_evaluation_provenance_determinism():
    m = EvaluationMetrics(f1_score=0.92, mae=0.03)
    h1 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "EVAL-01", "1.0", "COMPLETED", 100, m)
    h2 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "EVAL-01", "1.0", "COMPLETED", 100, m)
    assert h1 == h2


def test_evaluation_provenance_dataset_mutation():
    m = EvaluationMetrics(f1_score=0.92)
    h1 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "DATA-A", "1.0", "COMPLETED", 100, m)
    h2 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "DATA-B", "1.0", "COMPLETED", 100, m)
    assert h1 != h2, "Mutating dataset ID must change evaluation provenance"


def test_evaluation_provenance_metric_mutation():
    m1 = EvaluationMetrics(f1_score=0.92)
    m2 = EvaluationMetrics(f1_score=0.88)
    h1 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "DATA-A", "1.0", "COMPLETED", 100, m1)
    h2 = EvaluationProvenanceTracker.compute_provenance_hash("flood-v1", "DATA-A", "1.0", "COMPLETED", 100, m2)
    assert h1 != h2, "Mutating metric score must change evaluation provenance"


def test_calibration_provenance_determinism():
    h1 = CalibrationProvenanceTracker.compute_calibration_hash("flood-v1", CalibrationMethod.ISOTONIC, "DATA-CAL-01", 100, 0.08, 0.03)
    h2 = CalibrationProvenanceTracker.compute_calibration_hash("flood-v1", CalibrationMethod.ISOTONIC, "DATA-CAL-01", 100, 0.08, 0.03)
    assert h1 == h2


def test_calibration_provenance_method_mutation():
    h1 = CalibrationProvenanceTracker.compute_calibration_hash("flood-v1", CalibrationMethod.ISOTONIC, "DATA-CAL-01", 100, 0.08, 0.03)
    h2 = CalibrationProvenanceTracker.compute_calibration_hash("flood-v1", CalibrationMethod.PLATT_SCALING, "DATA-CAL-01", 100, 0.08, 0.03)
    assert h1 != h2, "Mutating calibration method must change calibration provenance"


def test_calibration_output_hash_raw_value_mutation():
    h1 = CalibrationProvenanceTracker.compute_output_hash("CAL-1", "flood-v1", 0.80, 0.75)
    h2 = CalibrationProvenanceTracker.compute_output_hash("CAL-1", "flood-v1", 0.85, 0.75)
    assert h1 != h2, "Mutating raw value must change output hash"
