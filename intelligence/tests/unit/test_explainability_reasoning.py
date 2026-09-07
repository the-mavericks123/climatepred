"""
Unit tests for structured reasoning and uncertainty analyzer in Phase 10.
"""

import pytest
from intelligence.explainability.reasoning import ReasoningEngine


def test_prediction_reasoning_increasing_trend():
    pred_dict = {
        "prediction_id": "PRED-101",
        "forecast_horizon_minutes": 60,
        "severity": 0.85,
        "baseline_severity": 0.40,
        "historical_points_count": 8,
    }
    steps, uncertainties = ReasoningEngine.explain_prediction_reasoning(pred_dict)
    assert len(steps) >= 4
    assert any("increasing" in s.lower() for s in steps)
    assert any(u.source == "forecast_horizon_decay" for u in uncertainties)


def test_prediction_reasoning_horizon_uncertainty():
    # 360 min should yield HIGH uncertainty
    pred_dict_long = {
        "forecast_horizon_minutes": 360,
        "severity": 0.70,
        "baseline_severity": 0.50,
    }
    _, uncertainties = ReasoningEngine.explain_prediction_reasoning(pred_dict_long)
    horizon_unc = next(u for u in uncertainties if u.source == "forecast_horizon_decay")
    assert horizon_unc.level == "HIGH"


def test_compound_reasoning_causal_chain():
    comp_dict = {
        "event_id": "COMP-001",
        "chain": ["heavy_rain", "soil_saturation", "flood", "bridge_failure"],
        "severity": 0.88,
        "drivers": ["Link [heavy_rain -> soil_saturation]: rapid infiltration"],
    }
    steps, uncertainties = ReasoningEngine.explain_compound_reasoning(comp_dict)
    assert len(steps) >= 4
    assert any("heavy_rain -> soil_saturation" in s for s in steps)
    assert len(uncertainties) >= 1


def test_evacuation_reasoning_valid_route():
    evac_dict = {
        "status": "RECOMMENDED",
        "zone_id": "ZONE-C",
        "population_to_evacuate": 4500,
        "destination": {"shelter_name": "East Regional Complex"},
        "route": {"estimated_travel_minutes": 14.5},
        "avoid_edges": ["ROAD-DAMAGED-1"],
    }
    steps, uncertainties = ReasoningEngine.explain_evacuation_reasoning(evac_dict)
    assert len(steps) >= 5
    assert any("East Regional Complex" in s for s in steps)
    assert any("14.5" in s for s in steps)
    assert any("ROAD-DAMAGED-1" in s or "avoidance" in s.lower() for s in steps)


def test_evacuation_reasoning_no_route():
    evac_dict = {
        "status": "NO_ROUTE",
        "zone_id": "ZONE-ISOLATED",
        "population_to_evacuate": 2000,
    }
    steps, uncertainties = ReasoningEngine.explain_evacuation_reasoning(evac_dict)
    assert any("NO_ROUTE" in s or "isolation" in s.lower() for s in steps)
    crit_unc = next(u for u in uncertainties if u.source == "road_network_isolation")
    assert crit_unc.level == "CRITICAL"


def test_response_action_reasoning():
    action_dict = {
        "action": "EVACUATE_ZONE",
        "target": "ZONE-RIVER",
        "priority": 1,
        "urgency": "CRITICAL",
        "requires_human_review": True,
        "review_reason": "Mandatory sign-off for zone evacuation",
        "reason": "Severe flood hazard exposing 5,000 residents.",
    }
    steps, uncertainties = ReasoningEngine.explain_response_reasoning(action_dict)
    assert any("EVACUATE_ZONE" in s for s in steps)
    assert any("Mandatory sign-off" in s for s in steps)
