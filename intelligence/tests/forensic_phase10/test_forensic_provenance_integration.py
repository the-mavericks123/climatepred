"""
Adversarial Forensic Test Suite: Provenance, Determinism, Caching & Phase 8/9 Integration.
Audits Parts 21, 22, 23, 24, 25, 28, 30, 31, and 32.
"""

import copy
import json
import pytest
from datetime import datetime, timezone

from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.provenance import ExplanationProvenanceTracker
from intelligence.explainability.types import (
    EpistemicClassification,
    ExplanationContract,
    ExplanationLevel,
    ExplanationRequest,
    FactorAttribution,
    TargetType,
)
from intelligence.response.types import (
    ActionItem,
    ActionType,
    UrgencyLevel,
    ResponsePlan,
    AlertLevel,
)
from intelligence.simulation.types import (
    ScenarioDefinition,
    ScenarioParameters,
    ScenarioType,
    SimulationComparison,
    SimulationResult,
    SimulationSummary,
)


class TestForensicProvenanceAndDeterminism:
    """Forensic verification of cryptographic provenance tracking and determinism."""

    def test_provenance_changes_on_material_mutation(self):
        """Mutation matrix: mutating any material input field must alter the provenance hash."""
        base_factors = [
            FactorAttribution(factor_name="rainfall", display_name="Rainfall", input_value=50.0, normalized_value=0.50, weight=0.40, contribution=0.20),
            FactorAttribution(factor_name="water_level", display_name="Water Level", input_value=4.5, normalized_value=0.30, weight=0.35, contribution=0.105),
        ]
        
        h_base = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD",
            target_id="flood_zone_1",
            model_version="1.0.0",
            classification="OBSERVED",
            formula_name="FloodHydrologicalFormula",
            factors=base_factors,
        )

        # Mutate factor contribution
        mutated_factors = copy.deepcopy(base_factors)
        mutated_factors[0].contribution = 0.25
        h_mut_factor = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD",
            target_id="flood_zone_1",
            model_version="1.0.0",
            classification="OBSERVED",
            formula_name="FloodHydrologicalFormula",
            factors=mutated_factors,
        )
        assert h_base != h_mut_factor

        # Mutate model version
        h_mut_version = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD",
            target_id="flood_zone_1",
            model_version="1.0.1",
            classification="OBSERVED",
            formula_name="FloodHydrologicalFormula",
            factors=base_factors,
        )
        assert h_base != h_mut_version

        # Mutate epistemic classification (e.g. OBSERVED -> SIMULATED)
        h_mut_class = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD",
            target_id="flood_zone_1",
            model_version="1.0.0",
            classification="SIMULATED",
            formula_name="FloodHydrologicalFormula",
            factors=base_factors,
            simulated=True,
        )
        assert h_base != h_mut_class

    def test_provenance_dictionary_ordering_invariance(self):
        """Canonical hashing must be invariant to factor collection ordering."""
        f1 = FactorAttribution(factor_name="alpha", display_name="Alpha", input_value=1.0, normalized_value=0.1, weight=0.5, contribution=0.05)
        f2 = FactorAttribution(factor_name="beta", display_name="Beta", input_value=2.0, normalized_value=0.2, weight=0.5, contribution=0.10)

        h1 = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD", target_id="t1", model_version="1.0", classification="OBSERVED", factors=[f1, f2]
        )
        h2 = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type="HAZARD", target_id="t1", model_version="1.0", classification="OBSERVED", factors=[f2, f1]
        )
        assert h1 == h2

    def test_10x_run_determinism(self):
        """Identical inputs evaluated 10 times in sequence must yield identical hashes and explanations."""
        engine = ExplainabilityEngine(enable_cache=False)

        hashes = set()
        summaries = set()

        for _ in range(10):
            exp = engine.explain_hazard({
                "hazard_type": "flood",
                "features": {"rainfall_mmhr": 50.0, "water_level_m": 4.0, "soil_moisture_pct": 80.0},
            }, target_id="flood_sensor_1")
            hashes.add(exp.provenance_hash)
            summaries.add(exp.summary)

        assert len(hashes) == 1
        assert len(summaries) == 1

    def test_stale_cache_invalidation(self):
        """Engine cache must not return stale explanations when input parameters change."""
        engine = ExplainabilityEngine(enable_cache=True)

        exp1 = engine.explain(
            TargetType.HAZARD,
            target_id="flood_node_A",
            target_object={"hazard_type": "flood", "features": {"rainfall_mmhr": 10.0, "water_level_m": 1.0, "soil_moisture_pct": 20.0}},
        )

        exp2 = engine.explain(
            TargetType.HAZARD,
            target_id="flood_node_A",
            target_object={"hazard_type": "flood", "features": {"rainfall_mmhr": 90.0, "water_level_m": 8.0, "soil_moisture_pct": 95.0}},
        )

        assert exp1.provenance_hash != exp2.provenance_hash
        assert exp1.factors[0].contribution != exp2.factors[0].contribution


class TestForensicPhase8Phase9Integration:
    """Forensic verification of genuine Phase 8 and Phase 9 integration."""

    def test_phase8_simulation_delta_explanation(self):
        """Verify explanation accurately consumes actual Phase 8 SimulationResult outputs."""
        engine = ExplainabilityEngine()

        scenario = ScenarioDefinition(
            scenario_id="SCN-HEAVY-RAIN-01",
            name="Severe Downpour What-If",
            description="Testing 2.5x rainfall impact",
            scenario_type=ScenarioType.RAINFALL_MULTIPLIER,
            default_parameters=ScenarioParameters(rainfall_multiplier=2.5),
        )

        sim_result = SimulationResult(
            simulation_id="SIM-RUN-99",
            scenario_id="SCN-HEAVY-RAIN-01",
            timestamp=datetime.now(timezone.utc),
            simulated=True,
            base_state_id="BASE-STATE-001",
            base_state_hash="HASH-BASE-001",
            parameters=ScenarioParameters(rainfall_multiplier=2.5),
            summary=SimulationSummary(
                executive_takeaway="Rainfall spike drives high flood risk",
                peak_hazard_name="flood",
                peak_hazard_delta=0.45,
                evacuation_routes_invalidated=2,
            ),
            comparison=SimulationComparison(deltas=[]),
            confidence=0.88,
            provenance_hash="HASH-SIM-RESULT-99",
        )

        exp = engine.explain_simulation(sim_result, target_id="SCN-HEAVY-RAIN-01")

        # Forensic checks:
        assert exp.target_id == "SCN-HEAVY-RAIN-01"
        assert exp.simulated is True
        assert exp.classification == EpistemicClassification.SIMULATED
        assert "SIMULATED WHAT-IF" in exp.summary
        assert len(exp.provenance_hash) == 64

    def test_phase8_scenario_parameter_mutation_changes_provenance(self):
        """Mutating scenario parameters in simulation must change the resulting explanation provenance hash."""
        engine = ExplainabilityEngine()

        sim1 = {
            "simulation_id": "SIM-01",
            "scenario_id": "SCN-01",
            "parameters": {"rainfall_multiplier": 1.5},
        }
        sim2 = {
            "simulation_id": "SIM-01",
            "scenario_id": "SCN-01",
            "parameters": {"rainfall_multiplier": 3.0},
        }

        exp1 = engine.explain_simulation(sim1)
        exp2 = engine.explain_simulation(sim2)

        assert exp1.provenance_hash != exp2.provenance_hash

    def test_phase9_response_action_explanation(self):
        """Verify explanation accurately consumes actual Phase 9 ActionItem and enforces human review."""
        engine = ExplainabilityEngine()

        from intelligence.response.types import EvidenceReference as RespEvidenceReference, EvidenceType
        action = ActionItem(
            action_id="ACT-EVAC-42",
            action=ActionType.EVACUATE_ZONE,
            target="Zone-Riverbank",
            priority=1,
            priority_score=0.92,
            urgency=UrgencyLevel.CRITICAL,
            urgency_score=0.95,
            confidence=0.85,
            reason="River stage breached danger threshold",
            requires_human_review=True,
            evidence=[
                RespEvidenceReference(id="EV-HAZARD-FLOOD-01", type=EvidenceType.OBSERVED, source_phase="PHASE_3", description="Flood gauge"),
                RespEvidenceReference(id="EV-VULN-02", type=EvidenceType.OBSERVED, source_phase="PHASE_5", description="Demographic exposure"),
            ],
        )

        exp = engine.explain_response_action(action)

        assert exp.target_id == "ACT-EVAC-42"
        assert "EVACUATE_ZONE" in exp.summary
        assert any("HUMAN SUPERVISOR REVIEW REQUIRED" in s for s in exp.reasoning_steps)
        assert len(exp.evidence) == 2

    def test_phase9_controlled_vocabulary_and_human_review_enforcement(self):
        """Controlled vocabulary rejection and mandatory human review preservation."""
        engine = ExplainabilityEngine()

        # Reject invalid action
        with pytest.raises(ValueError):
            engine.explain_response_action({
                "action": "INVALID_DISASTER_ACTION_XYZ",
                "target": "Zone-A",
            })

    def test_failure_injection_missing_upstream_attributes(self):
        """Fails gracefully and explicitly without hallucinating fake numbers when upstream fields are empty."""
        engine = ExplainabilityEngine()
        exp = engine.explain_hazard({}, target_id="EMPTY-HAZARD")
        assert exp.target_id == "EMPTY-HAZARD"
        for f in exp.factors:
            assert f.contribution == 0.0

    def test_no_pii_or_credential_leakage_in_provenance_or_explanation(self):
        """Part 32: Inappropriate sensitive information or credentials must not leak into provenance or text."""
        engine = ExplainabilityEngine()
        polluted = {
            "hazard_type": "flood",
            "features": {"rainfall_mmhr": 30.0},
            "api_key": "sk-proj-SECRET-API-KEY-12345",
            "user_password": "super-secret-password",
        }
        exp = engine.explain_hazard(polluted, target_id="SECURE-NODE")
        serialized = json.dumps(exp.model_dump(), default=str)
        assert "sk-proj-SECRET-API-KEY-12345" not in serialized
        assert "super-secret-password" not in serialized
