"""
Contract tests for Phase 10 Explainability schemas.
Verifies Pydantic boundaries, required fields, and serialization integrity.
"""

import pytest
from datetime import datetime, timezone
from intelligence.explainability.types import (
    CounterfactualItem,
    EpistemicClassification,
    EvidenceReference,
    ExplanationContract,
    ExplanationLevel,
    ExplanationRequest,
    FactorAttribution,
    TargetType,
    UncertaintyItem,
)


def test_factor_attribution_valid():
    fa = FactorAttribution(
        factor_name="rainfall",
        display_name="Rainfall Rate",
        input_value=45.0,
        normalized_value=0.45,
        weight=0.40,
        contribution=0.18,
        unit="mm/hr",
        description="Rainfall contribution",
    )
    assert fa.factor_name == "rainfall"
    assert fa.contribution == 0.18
    assert fa.normalized_value == 0.45


def test_factor_attribution_bounds():
    with pytest.raises(ValueError):
        FactorAttribution(
            factor_name="rainfall",
            display_name="Rainfall",
            input_value=12.0,
            normalized_value=1.5,  # > 1.0 invalid
            weight=0.40,
            contribution=0.6,
        )


def test_evidence_reference_serialization():
    er = EvidenceReference(
        type="hazard",
        id="HAZ-101",
        severity=0.85,
        confidence=0.90,
    )
    dump = er.model_dump()
    assert dump["type"] == "hazard"
    assert dump["id"] == "HAZ-101"
    assert dump["severity"] == 0.85


def test_uncertainty_and_counterfactual_items():
    unc = UncertaintyItem(
        source="sensor_drift",
        level="MODERATE",
        description="Sensor calibration overdue",
        impact_on_decision="Slight confidence reduction",
    )
    assert unc.level == "MODERATE"

    cf = CounterfactualItem(
        condition="rainfall drops by 30%",
        altered_parameter="rainfall",
        original_value=60.0,
        counterfactual_value=42.0,
        counterfactual_outcome="de-escalates from RED to ORANGE",
    )
    assert cf.original_value == 60.0
    assert cf.counterfactual_value == 42.0


def test_explanation_contract_valid():
    contract = ExplanationContract(
        explanation_id="EXP-001",
        target_type=TargetType.HAZARD,
        target_id="HAZ-FLOOD-01",
        model_version="flood-v1",
        classification=EpistemicClassification.OBSERVED,
        summary="Flood risk elevated due to high rainfall.",
        explanation_level=ExplanationLevel.STANDARD,
        provenance_hash="a" * 64,
        simulated=False,
    )
    assert contract.explanation_id == "EXP-001"
    assert contract.classification == EpistemicClassification.OBSERVED
    assert contract.simulated is False


def test_explanation_request_defaults():
    req = ExplanationRequest(
        target_type=TargetType.PREDICTION,
        target_id="PRED-101",
    )
    assert req.level == ExplanationLevel.STANDARD
    assert req.target_object is None


def test_epistemic_classification_values():
    assert EpistemicClassification.OBSERVED.value == "OBSERVED"
    assert EpistemicClassification.PREDICTED.value == "PREDICTED"
    assert EpistemicClassification.INFERRED.value == "INFERRED"
    assert EpistemicClassification.SIMULATED.value == "SIMULATED"
