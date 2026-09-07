"""
Unit tests for deterministic counterfactual generator in Phase 10.
"""

import pytest
from intelligence.explainability.counterfactual import CounterfactualEngine


def test_flood_counterfactual_precipitation_reduction():
    features = {"rainfall_mmhr": 80.0, "water_level_m": 8.0}
    cfs = CounterfactualEngine.generate_flood_counterfactuals(features, current_severity=0.75)
    assert len(cfs) >= 1
    rain_cf = next(c for c in cfs if c.altered_parameter == "rainfall_mmhr")
    assert rain_cf.original_value == 80.0
    assert rain_cf.counterfactual_value == 40.0
    assert "decrease" in rain_cf.condition.lower()


def test_flood_counterfactual_channel_drainage():
    features = {"rainfall_mmhr": 20.0, "water_level_m": 12.0}
    cfs = CounterfactualEngine.generate_flood_counterfactuals(features, current_severity=0.60)
    level_cf = next((c for c in cfs if c.altered_parameter == "water_level_m"), None)
    assert level_cf is not None
    assert level_cf.original_value == 12.0
    assert level_cf.counterfactual_value == 8.0


def test_evacuation_counterfactual_no_route_restoration():
    evac_dict = {"status": "NO_ROUTE", "zone_id": "ZONE-A"}
    cfs = CounterfactualEngine.generate_evacuation_counterfactuals(evac_dict)
    assert len(cfs) >= 1
    assert "bridge" in cfs[0].condition.lower() or "accessibility" in cfs[0].condition.lower()
    assert cfs[0].counterfactual_value >= 0.50


def test_evacuation_counterfactual_clearing_avoided_edge():
    evac_dict = {"status": "RECOMMENDED", "avoid_edges": ["ROAD-BLOCKED-1"]}
    cfs = CounterfactualEngine.generate_evacuation_counterfactuals(evac_dict)
    assert len(cfs) >= 1
    assert "ROAD-BLOCKED-1" in cfs[0].condition


def test_response_counterfactual_de_escalate_evacuation():
    action_dict = {"action": "EVACUATE_ZONE", "urgency": "CRITICAL"}
    cfs = CounterfactualEngine.generate_response_counterfactuals(action_dict)
    assert len(cfs) >= 1
    assert any("EVACUATE_ZONE to PREPARE_EVACUATION" in c.counterfactual_outcome for c in cfs)
