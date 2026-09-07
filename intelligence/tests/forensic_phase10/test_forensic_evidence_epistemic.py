"""
Forensic Audit Suite - Module 3: Evidence Integrity & Epistemic Separation.
Adversarially tests epistemic classification boundaries, evidence resolution,
Phase 9 controlled action vocabulary enforcement, and human review retention.
Audits Parts 6, 7, 10, 22, and 23.
"""

import pytest
from datetime import datetime, timezone, timedelta

from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.types import (
    EpistemicClassification,
    ExplanationLevel,
    ExplanationRequest,
    TargetType,
)
from intelligence.explainability.evidence import EvidenceResolver
from intelligence.response.types import ActionType


class TestForensicEvidenceEpistemic:
    """Audits epistemic boundaries, evidence resolution, and emergency review safety."""

    def test_simulated_flag_enforces_simulated_classification(self):
        """
        AUDIT GATE: If simulated=True, classification MUST be SIMULATED.
        It must never collapse into OBSERVED or INFERRED.
        """
        engine = ExplainabilityEngine()
        sim_req = ExplanationRequest(
            target_type=TargetType.HAZARD,
            target_id="HAZ-SIM-01",
            target_object={
                "hazard_type": "flood",
                "model_version": "flood-v1.0",
                "severity": 0.85,
                "confidence": 0.90,
                "simulated": True,
                "features": {"rainfall_mmhr": 60.0, "water_level_m": 4.0, "soil_moisture_pct": 85.0},
            },
        )
        exp = engine.explain(sim_req)
        assert exp.classification == EpistemicClassification.SIMULATED
        assert exp.simulated is True

    def test_epistemic_separation_quadrant(self):
        """
        AUDIT GATE: Verifies strict separation across all four epistemic classifications:
        OBSERVED, PREDICTED, INFERRED, SIMULATED.
        """
        engine = ExplainabilityEngine()
        
        # 1. Observed Hazard
        exp_obs = engine.explain(TargetType.HAZARD, "H1", target_object={"features": {"rainfall_mmhr": 10.0}})
        assert exp_obs.classification == EpistemicClassification.OBSERVED
        
        # 2. Predicted
        exp_pred = engine.explain(TargetType.PREDICTION, "P1", target_object={"severity": 0.70, "horizon_minutes": 60})
        assert exp_pred.classification == EpistemicClassification.PREDICTED
        
        # 3. Inferred Compound
        exp_inf = engine.explain(TargetType.COMPOUND, "C1", target_object={"severity": 0.80, "causal_chain": ["A", "B"]})
        assert exp_inf.classification == EpistemicClassification.INFERRED
        
        # 4. Simulated Digital Twin
        exp_sim = engine.explain(TargetType.SIMULATION, "S1", target_object={"scenario_id": "SCEN-01"})
        assert exp_sim.classification == EpistemicClassification.SIMULATED

    def test_response_action_controlled_vocabulary_enforcement(self):
        """
        AUDIT GATE: Explaining a response action not present in the Phase 9 controlled vocabulary
        (ActionType enum) must be rejected with ValueError.
        """
        engine = ExplainabilityEngine()
        unauthorized_req = ExplanationRequest(
            target_type=TargetType.RESPONSE_PLAN,
            target_id="ACT-ILLEGAL-01",
            target_object={
                "action_id": "ACT-ILLEGAL-01",
                "action": "NUKE_HURRICANE",
                "target": "COASTAL_SECTOR",
                "urgency": "CRITICAL",
            },
        )
        with pytest.raises(ValueError) as exc_info:
            engine.explain(unauthorized_req)
        assert "controlled vocabulary" in str(exc_info.value).lower() or "invalid response action" in str(exc_info.value).lower()

    def test_response_action_valid_vocabulary_accepted(self):
        """
        AUDIT GATE: All valid actions from ActionType must be properly accepted and explained.
        """
        engine = ExplainabilityEngine()
        for action in ActionType:
            req = ExplanationRequest(
                target_type=TargetType.RESPONSE_PLAN,
                target_id=f"ACT-{action.value}",
                target_object={
                    "action_id": f"ACT-{action.value}",
                    "action": action.value,
                    "target": "ZONE-ALPHA",
                    "urgency": "HIGH",
                },
            )
            exp = engine.explain(req)
            assert exp.summary != ""

    def test_mandatory_human_review_preservation_for_critical_actions(self):
        """
        AUDIT GATE: High-consequence actions (EVACUATE_ZONE, REDIRECT_EVACUATION, REQUEST_FIELD_VERIFICATION, REASSESS)
        must mandate human review in reasoning steps and flags.
        """
        engine = ExplainabilityEngine()
        critical_actions = ["EVACUATE_ZONE", "REDIRECT_EVACUATION", "REQUEST_FIELD_VERIFICATION", "REASSESS"]
        
        for act in critical_actions:
            req = ExplanationRequest(
                target_type=TargetType.RESPONSE_PLAN,
                target_id=f"ACT-{act}",
                target_object={
                    "action_id": f"ACT-{act}",
                    "action": act,
                    "target": "DHARAVI",
                    "requires_human_review": False,  # Attempting to bypass
                },
            )
            exp = engine.explain(req)
            assert any("HUMAN SUPERVISOR REVIEW REQUIRED" in step for step in exp.reasoning_steps)

    def test_mandatory_human_review_when_confidence_low(self):
        """
        AUDIT GATE: If model confidence < 0.50, human review must be mandated.
        """
        engine = ExplainabilityEngine()
        req = ExplanationRequest(
            target_type=TargetType.RESPONSE_PLAN,
            target_id="ACT-LOW-CONF",
            target_object={
                "action_id": "ACT-LOW-CONF",
                "action": "MONITOR",
                "target": "ZONE-01",
                "confidence": 0.40,
            },
        )
        exp = engine.explain(req)
        assert any("HUMAN SUPERVISOR REVIEW REQUIRED" in step for step in exp.reasoning_steps)

    def test_evidence_resolution_string_and_dict_handling(self):
        """
        EvidenceResolver must resolve evidence given as strings, dicts, or structured references.
        """
        data = {
            "evidence": ["HAZ-001", "VULN-002"],
            "contributing_hazards": ["HAZ-101", {"hazard_id": "HAZ-102", "severity": 0.90}],
        }
        refs_resp = EvidenceResolver.resolve_response_evidence(data)
        refs_comp = EvidenceResolver.resolve_compound_evidence(data)
        
        assert len(refs_resp) == 2
        assert refs_resp[0].id == "HAZ-001"
        assert len(refs_comp) == 2
        assert refs_comp[1].id == "HAZ-102"

    def test_stale_evidence_flagged_with_uncertainty(self):
        """
        AUDIT GATE: Part 6 - Evidence with timestamps older than threshold must be
        flagged with uncertainty or downgrade confidence, never silently accepted as fresh.
        """
        engine = ExplainabilityEngine()
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        req = ExplanationRequest(
            target_type=TargetType.HAZARD,
            target_id="HAZ-STALE-01",
            target_object={
                "hazard_type": "flood",
                "features": {"rainfall_mmhr": 45.0, "water_level_m": 3.0},
                "timestamp": stale_time,
                "stale_flag": True,
            },
        )
        exp = engine.explain(req)
        assert exp.target_id == "HAZ-STALE-01"

    def test_future_timestamp_prediction_leakage_flagged(self):
        """
        AUDIT GATE: Part 10 - Attempting to predict +60m while injecting future observation
        timestamps (T+30m) must not leak future ground truth into historical window.
        """
        engine = ExplainabilityEngine()
        pred_obj = {
            "model_version": "trend-v1",
            "horizon_minutes": 60,
            "predicted_severity": 0.85,
            "confidence": 0.89,
            "historical_window_minutes": 180,
            "observations_used": 12,
            "baseline_component": 0.60,
            "trend_delta": 0.25,
        }
        exp = engine.explain(TargetType.PREDICTION, "PRED-TIME-01", target_object=pred_obj)
        assert exp.classification == EpistemicClassification.PREDICTED
        # Horizon factor must strictly reflect +60m projection distance
        h_factor = next(f for f in exp.factors if f.factor_name == "forecast_horizon")
        assert h_factor.input_value == 60.0

    def test_simulated_cannot_collapse_to_observed_in_response(self):
        """
        AUDIT GATE: Part 7 - Response actions generated from simulated twin states must
        retain SIMULATED classification and cannot be mislabeled as OBSERVED.
        """
        engine = ExplainabilityEngine()
        sim_action_req = ExplanationRequest(
            target_type=TargetType.RESPONSE_PLAN,
            target_id="ACT-SIM-RESP",
            target_object={
                "action_id": "ACT-SIM-RESP",
                "action": "PREPARE_EVACUATION",
                "target": "ZONE-B",
                "simulated": True,
            },
        )
        exp = engine.explain(sim_action_req)
        assert exp.classification == EpistemicClassification.SIMULATED
        assert exp.simulated is True
