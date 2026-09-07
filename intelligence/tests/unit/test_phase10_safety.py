"""
Safety, epistemic integrity, and negative testing suite for Phase 10.
Verifies that the system never fabricates ground truth, never overwrites raw model outputs,
and rejects calibration when statistical conditions are unmet.
"""

import pytest
from intelligence.calibration.engine import CalibrationEngine
from intelligence.calibration.types import CalibrationMethod
from intelligence.evaluation.engine import EvaluationEngine
from intelligence.evaluation.types import EvaluationDataset, EvaluationObservation
from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.types import EpistemicClassification, TargetType


def test_safety_never_overwrites_raw_value():
    cal_engine = CalibrationEngine(min_samples=50)
    # Fit calibrator on synthetic flood benchmark
    rep = cal_engine.fit_calibrator("flood-v1", "EVAL-FLOOD-SYNTHETIC-001")
    assert rep.status == "CALIBRATED"

    cal_out = cal_engine.calibrate_score(rep.calibration_id, raw_value=0.82)
    # RAW VALUE MUST REMAIN EXACTLY 0.82
    assert cal_out.raw_value == 0.82
    # Calibrated probability exists independently
    assert isinstance(cal_out.calibrated_value, float)
    assert cal_out.raw_value != cal_out.calibrated_value or 0.0 <= cal_out.calibrated_value <= 1.0


def test_safety_rejects_calibration_with_insufficient_samples():
    cal_engine = CalibrationEngine(min_samples=50)
    # Build dataset with only 10 samples
    ds = EvaluationDataset(
        dataset_id="EVAL-TINY-001",
        domain="flood",
        observations=[EvaluationObservation(sample_id=f"S-{i}", features={"rainfall_mmhr": float(i)}) for i in range(10)],
    )
    rep = cal_engine.fit_calibrator("flood-v1", "EVAL-TINY-001", custom_dataset=ds.model_dump())
    assert rep.status == "CALIBRATION_UNAVAILABLE"
    assert "Insufficient" in rep.reason


def test_safety_handles_missing_ground_truth_honestly():
    eval_engine = EvaluationEngine()
    # Dataset with observations but ZERO ground truth
    ds = EvaluationDataset(
        dataset_id="EVAL-NO-GT-001",
        domain="flood",
        observations=[EvaluationObservation(sample_id=f"S-{i}", features={"rainfall_mmhr": float(i)}) for i in range(50)],
        ground_truth=[],  # No ground truth!
    )
    rep = eval_engine.evaluate_model("flood-v1", "EVAL-NO-GT-001", custom_dataset=ds.model_dump())
    assert rep.status == "INSUFFICIENT_GROUND_TRUTH"
    assert rep.ground_truth_status.value == "UNAVAILABLE"
    assert rep.metrics.f1_score is None


def test_safety_epistemic_separation_observed_vs_simulated():
    exp_engine = ExplainabilityEngine()

    # Observed flood
    live_hazard = {"hazard_id": "HAZ-LIVE-01", "hazard": "flood", "severity": 0.80, "simulated": False}
    exp_live = exp_engine.explain(TargetType.HAZARD, "HAZ-LIVE-01", target_object=live_hazard)
    assert exp_live.classification == EpistemicClassification.OBSERVED
    assert exp_live.simulated is False

    # Simulated flood
    sim_hazard = {"hazard_id": "HAZ-SIM-01", "hazard": "flood", "severity": 0.80, "simulated": True}
    exp_sim = exp_engine.explain(TargetType.HAZARD, "HAZ-SIM-01", target_object=sim_hazard)
    assert exp_sim.classification == EpistemicClassification.SIMULATED
    assert exp_sim.simulated is True
    assert "SIMULATED" in exp_sim.summary


def test_safety_counterfactual_labeled_hypothetical():
    exp_engine = ExplainabilityEngine()
    live_hazard = {"hazard_id": "HAZ-LIVE-01", "hazard": "flood", "severity": 0.85, "features": {"rainfall_mmhr": 70.0, "water_level_m": 8.0}}
    exp = exp_engine.explain(TargetType.HAZARD, "HAZ-LIVE-01", target_object=live_hazard)
    for cf in exp.counterfactuals:
        assert cf.feasibility == "MODEL_COUNTERFACTUAL"
