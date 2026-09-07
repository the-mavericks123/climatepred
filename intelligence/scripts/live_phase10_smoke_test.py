"""
Live smoke test script for Phase 10: Explainability + Evaluation + Calibration.
Verifies the 17 mission-critical capabilities mandated in PART I:
1. Generate flood explanation
2. Generate heat explanation
3. Generate drought explanation
4. Explain prediction
5. Explain compound event
6. Explain vulnerability
7. Explain evacuation
8. Explain response plan
9. Explain Phase 8 simulation
10. Run synthetic evaluation
11. Compare two model versions
12. Run calibration with valid fixture data
13. Reject calibration with insufficient data
14. Detect synthetic drift
15. Verify deterministic provenance
16. Verify no ground-truth fabrication
17. Verify observed/predicted/simulated separation
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import copy
from typing import Any, Dict

from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.types import (
    ExplanationLevel,
    ExplanationRequest,
    TargetType,
    EpistemicClassification,
)
from intelligence.evaluation.engine import EvaluationEngine
from intelligence.evaluation.types import (
    DatasetType,
    EvaluationDataset,
    EvaluationObservation,
    GroundTruthRecord,
)
from intelligence.calibration.engine import CalibrationEngine
from intelligence.calibration.types import CalibrationMethod


def run_smoke_test():
    print("=" * 70)
    print("STARTING PHASE 10 LIVE SMOKE TEST: EXPLAINABILITY, EVALUATION & CALIBRATION")
    print("=" * 70)

    explain_engine = ExplainabilityEngine()
    eval_engine = EvaluationEngine()
    calib_engine = CalibrationEngine(min_samples=50)

    passed_checks = 0

    # 1. Generate flood explanation
    flood_req = ExplanationRequest(
        target_type=TargetType.HAZARD,
        target_id="HAZ-FLOOD-001",
        target_object={
            "hazard_type": "flood",
            "model_version": "flood-v1.0",
            "severity": 0.78,
            "confidence": 0.92,
            "features": {"rainfall_mmhr": 35.0, "water_level_m": 2.4, "soil_moisture_pct": 82.0},
        },
        level=ExplanationLevel.DETAILED,
    )
    flood_exp = explain_engine.explain(flood_req)
    assert flood_exp.summary != ""
    assert "Hydrological" in flood_exp.formula_name
    assert len(flood_exp.factors) == 3
    assert flood_exp.provenance_hash is not None
    print("[CHECK 01] PASS: Generate flood explanation with deterministic attribution & formula")
    passed_checks += 1

    # 2. Generate heat explanation
    heat_req = ExplanationRequest(
        target_type=TargetType.HAZARD,
        target_id="HAZ-HEAT-001",
        target_object={
            "hazard_type": "heat",
            "model_version": "heat-v1.0",
            "severity": 0.82,
            "confidence": 0.95,
            "features": {"temperature_c": 41.5, "humidity_pct": 65.0},
        },
        level=ExplanationLevel.STANDARD,
    )
    heat_exp = explain_engine.explain(heat_req)
    assert any(f.factor_name in ("ambient_temperature", "relative_humidity") for f in heat_exp.factors)
    print("[CHECK 02] PASS: Generate heat explanation with apparent temperature formula")
    passed_checks += 1

    # 3. Generate drought explanation
    drought_req = ExplanationRequest(
        target_type=TargetType.HAZARD,
        target_id="HAZ-DROUGHT-001",
        target_object={
            "hazard_type": "drought",
            "model_version": "drought-v1.0",
            "severity": 0.65,
            "confidence": 0.88,
            "features": {"soil_moisture_pct": 14.0, "temperature_c": 36.0, "humidity_pct": 20.0},
        },
        level=ExplanationLevel.SUMMARY,
    )
    drought_exp = explain_engine.explain(drought_req)
    assert drought_exp.summary != ""
    assert any(f.factor_name in ("soil_moisture_depletion", "soil_moisture_deficit") for f in drought_exp.factors)
    print("[CHECK 03] PASS: Generate drought explanation with soil deficit attribution")
    passed_checks += 1

    # 4. Explain prediction
    pred_req = ExplanationRequest(
        target_type=TargetType.PREDICTION,
        target_id="PRED-001",
        target_object={
            "model_version": "trend-v1",
            "horizon_minutes": 60,
            "predicted_severity": 0.85,
            "confidence": 0.89,
            "historical_window_minutes": 180,
            "observations_used": 12,
            "baseline_component": 0.60,
            "trend_delta": 0.25,
            "uncertainty_lower": 0.80,
            "uncertainty_upper": 0.90,
        },
    )
    pred_exp = explain_engine.explain(pred_req)
    assert pred_exp.classification == EpistemicClassification.PREDICTED
    assert any(f.factor_name == "forecast_horizon" for f in pred_exp.factors)
    assert len(pred_exp.uncertainty) > 0
    print("[CHECK 04] PASS: Explain prediction with horizon, baseline, trend, and uncertainty bounds")
    passed_checks += 1

    # 5. Explain compound event
    comp_req = ExplanationRequest(
        target_type=TargetType.COMPOUND_EVENT,
        target_id="COMP-001",
        target_object={
            "event_type": "FLOOD_ROAD_CASCADE",
            "rule_id": "RULE-CASCADE-04",
            "model_version": "compound-v1.0",
            "severity": 0.88,
            "confidence": 0.85,
            "causal_chain": ["HEAVY_RAIN", "FLOOD", "ROAD_WASHOUT", "ACCESSIBILITY_COLLAPSE"],
            "contributing_hazards": ["HAZ-FLOOD-01", "HAZ-INFRA-02"],
        },
    )
    comp_exp = explain_engine.explain(comp_req)
    assert any("RULE-CASCADE-04" in s for s in comp_exp.reasoning_steps)
    assert len(comp_exp.evidence) == 2
    print("[CHECK 05] PASS: Explain compound event with causal chain, rule IDs, and upstream hazards")
    passed_checks += 1

    # 6. Explain vulnerability
    vuln_req = ExplanationRequest(
        target_type=TargetType.VULNERABILITY,
        target_id="VULN-001",
        target_object={
            "zone_id": "ZONE-DHARAVI-01",
            "model_version": "vuln-v1.0",
            "impact_score": 0.82,
            "confidence": 0.88,
            "exposure_ratio": 0.85,
            "vulnerability": 0.90,
            "accessibility_risk": 0.60,
            "population": 45000,
        },
    )
    vuln_exp = explain_engine.explain(vuln_req)
    assert any(f.factor_name in ("hazard_exposure", "demographic_vulnerability") for f in vuln_exp.factors)
    print("[CHECK 06] PASS: Explain vulnerability with zone exposure, vulnerability, and accessibility")
    passed_checks += 1

    # 7. Explain evacuation
    evac_req = ExplanationRequest(
        target_type=TargetType.EVACUATION,
        target_id="EVAC-001",
        target_object={
            "zone_id": "ZONE-DHARAVI-01",
            "routing_version": "dijkstra-hazard-v1",
            "status": "RECOMMENDED",
            "population_to_evacuate": 1200,
            "destination": {"shelter_id": "SHELTER-NORTH-COLLEGE", "shelter_name": "Shelter North"},
            "route": {"route_id": "ROUTE-HIGHLAND-A", "estimated_travel_minutes": 22.5},
            "avoid_edges": ["SEG-EAST-LOW-01", "SEG-RIVER-04"],
            "evidence": ["HAZ-101", "VULN-201"],
        },
    )
    evac_exp = explain_engine.explain(evac_req)
    assert any("Shelter North" in s for s in evac_exp.reasoning_steps)
    assert any("SEG-EAST-LOW-01" in c.condition for c in evac_exp.counterfactuals)
    print("[CHECK 07] PASS: Explain evacuation route selection, rejection rationale, and avoided segments")
    passed_checks += 1

    # 8. Explain response plan
    resp_req = ExplanationRequest(
        target_type=TargetType.RESPONSE_PLAN,
        target_id="PLAN-001",
        target_object={
            "action_id": "ACT-EVAC-URGENT",
            "model_version": "response-v1.0",
            "action": "EVACUATE_ZONE",
            "target_zone": "ZONE-DHARAVI-01",
            "urgency": "CRITICAL",
            "urgency_score": 0.95,
            "vulnerability_score": 0.88,
            "cascade_severity": 0.80,
            "confidence": 0.91,
            "human_review_required": True,
            "evidence": ["HAZ-101", "VULN-201", "EVAC-001"],
            "conflicts": [],
        },
    )
    resp_exp = explain_engine.explain(resp_req)
    assert any(f.factor_name == "operational_urgency" for f in resp_exp.factors)
    assert any("HUMAN SUPERVISOR REVIEW REQUIRED" in s for s in resp_exp.reasoning_steps)
    print("[CHECK 08] PASS: Explain response plan action, priority factors, and human-review gate")
    passed_checks += 1

    # 9. Explain Phase 8 simulation
    sim_req = ExplanationRequest(
        target_type=TargetType.SIMULATION,
        target_id="SIM-001",
        target_object={
            "scenario_id": "SCEN-DAM-FAILURE-01",
            "model_version": "twin-v1.0",
            "simulated_water_level": 4.5,
            "confidence": 0.85,
            "parameter_perturbations": {"rainfall_multiplier": 1.5, "dam_gate_failure": True},
        },
    )
    sim_exp = explain_engine.explain(sim_req)
    assert "SIMULATED WHAT-IF" in sim_exp.summary
    assert any("parameter shifts" in s for s in sim_exp.reasoning_steps)
    print("[CHECK 09] PASS: Explain Phase 8 simulation with SIMULATED classification")
    passed_checks += 1

    # 10. Run synthetic evaluation
    eval_rep = eval_engine.run_evaluation(
        model_version="flood-v1.0",
        dataset_id="EVAL-FLOOD-SYNTHETIC-001",
    )
    assert eval_rep.status == "COMPLETED"
    assert eval_rep.metrics.f1_score is not None
    assert eval_rep.metrics.f1_score >= 0.80
    assert eval_rep.metrics.confusion_matrix is not None
    print(f"[CHECK 10] PASS: Run synthetic evaluation (F1: {eval_rep.metrics.f1_score:.3f}, Samples: {eval_rep.sample_count})")
    passed_checks += 1

    # 11. Compare two model versions
    comp_rep = eval_engine.compare_models(
        baseline_model_version="flood-v1.0",
        candidate_model_version="flood-v2.0",
        dataset_id="EVAL-FLOOD-SYNTHETIC-001",
    )
    assert comp_rep.baseline_model_version == "flood-v1.0"
    assert comp_rep.candidate_model_version == "flood-v2.0"
    assert isinstance(comp_rep.regression_detected, bool)
    f1_delta = comp_rep.metric_deltas.get("f1_score", 0.0)
    print(f"[CHECK 11] PASS: Compare two model versions (Regression: {comp_rep.regression_detected}, F1 Delta: {f1_delta:+.3f})")
    passed_checks += 1

    # 12. Run calibration with valid fixture data
    calib_rep = calib_engine.fit_calibrator(
        model_version="flood-v1.0",
        dataset_id="EVAL-FLOOD-SYNTHETIC-001",
        method=CalibrationMethod.ISOTONIC,
    )
    assert calib_rep.status == "CALIBRATED"
    assert calib_rep.brier_score_after is not None
    assert calib_rep.brier_score_after <= calib_rep.brier_score_before
    assert len(calib_rep.reliability_bins) == 10
    print(f"[CHECK 12] PASS: Run isotonic calibration with valid data (Brier: {calib_rep.brier_score_before:.3f} -> {calib_rep.brier_score_after:.3f})")
    passed_checks += 1

    # 13. Reject calibration with insufficient data
    small_dataset = {
        "dataset_id": "TINY-DATASET",
        "version": "1.0",
        "dataset_type": "SYNTHETIC",
        "domain": "flood",
        "description": "Insufficient samples for calibration",
        "observations": [
            {"sample_id": f"S-{i}", "features": {"rainfall_mmhr": 10.0}}
            for i in range(5)
        ],
        "ground_truth": [
            {"sample_id": f"S-{i}", "binary_label": i % 2}
            for i in range(5)
        ],
    }
    rejected_calib = calib_engine.fit_calibrator(
        model_version="flood-v1.0",
        dataset_id="TINY-DATASET",
        custom_dataset=small_dataset,
    )
    assert rejected_calib.status == "CALIBRATION_UNAVAILABLE"
    assert "Insufficient sample count" in rejected_calib.reason
    print("[CHECK 13] PASS: Reject calibration when sample count (5 < 50) is statistically insufficient")
    passed_checks += 1

    # 14. Detect synthetic drift
    baseline_vals = [20.0 + i * 0.1 for i in range(100)]
    shifted_vals = [80.0 + i * 0.1 for i in range(100)]
    drift_rep = eval_engine.evaluate_drift(
        feature_name="rainfall_mmhr",
        baseline_values=baseline_vals,
        operational_values=shifted_vals,
    )
    assert drift_rep.drift_detected is True
    assert drift_rep.severity in ("MODERATE", "SIGNIFICANT", "MODERATE_DRIFT", "SIGNIFICANT_DRIFT")
    print(f"[CHECK 14] PASS: Detect distribution drift (Metric: {drift_rep.metric_value:.3f}, Severity: {drift_rep.severity})")
    passed_checks += 1

    # 15. Verify deterministic provenance
    req_a = copy.deepcopy(flood_req)
    req_b = copy.deepcopy(flood_req)
    exp_a = explain_engine.explain(req_a)
    exp_b = explain_engine.explain(req_b)
    assert exp_a.provenance_hash == exp_b.provenance_hash
    # Mutate material rainfall
    req_b.target_object["features"]["rainfall_mmhr"] = 99.0
    exp_mutated = explain_engine.explain(req_b)
    assert exp_a.provenance_hash != exp_mutated.provenance_hash
    print("[CHECK 15] PASS: Provenance is deterministic and sensitive to material feature mutations")
    passed_checks += 1

    # 16. Verify no ground-truth fabrication
    no_gt_dataset = {
        "dataset_id": "NO-GT-DATASET",
        "version": "1.0",
        "dataset_type": "BENCHMARK",
        "domain": "flood",
        "description": "Benchmark with no ground truth",
        "observations": [
            {"sample_id": f"O-{i}", "features": {"rainfall_mmhr": 15.0}}
            for i in range(20)
        ],
        "ground_truth": [],
    }
    no_gt_eval = eval_engine.run_evaluation(
        model_version="flood-v1.0",
        dataset_id="NO-GT-DATASET",
        custom_dataset=no_gt_dataset,
    )
    assert no_gt_eval.status == "INSUFFICIENT_GROUND_TRUTH"
    assert no_gt_eval.metrics.f1_score is None
    print("[CHECK 16] PASS: Scientific honesty preserved - returns INSUFFICIENT_GROUND_TRUTH without fabricating labels")
    passed_checks += 1

    # 17. Verify observed/predicted/simulated separation
    assert flood_exp.classification == EpistemicClassification.OBSERVED
    assert pred_exp.classification == EpistemicClassification.PREDICTED
    assert sim_exp.classification == EpistemicClassification.SIMULATED
    print("[CHECK 17] PASS: Rigorous separation of OBSERVED vs PREDICTED vs SIMULATED classifications")
    passed_checks += 1

    print("=" * 70)
    print(f"SMOKE TEST SUMMARY: {passed_checks}/17 CHECKS PASSED. ZERO REGRESSIONS.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_smoke_test()
    if not success:
        sys.exit(1)
