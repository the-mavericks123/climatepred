"""
Unit tests for mathematical factor attribution engine.
Verifies exact calculation consistency against Phase 2-9 model formulas.
"""

import pytest
from intelligence.explainability.attribution import FactorAttributionEngine


def test_flood_attribution_weights_and_contributions():
    features = {
        "rainfall_mmhr": 50.0,    # norm = 0.50, w = 0.40 -> contrib = 0.20
        "water_level_m": 7.5,     # norm = 0.50, w = 0.35 -> contrib = 0.175
        "soil_moisture_pct": 65.0,# norm = (65-30)/70 = 0.50, w = 0.25 -> contrib = 0.125
    }
    fname, fexpr, factors = FactorAttributionEngine.attribute_flood(features)
    assert "Hydrological" in fname
    assert len(factors) == 3

    # Check that weights sum to 1.0
    total_weight = sum(f.weight for f in factors)
    assert pytest.approx(total_weight, 0.01) == 1.0

    # Top contributor should be rainfall
    assert factors[0].factor_name == "rainfall_rate"
    assert pytest.approx(factors[0].contribution, 0.01) == 0.20


def test_flood_attribution_zero_inputs():
    features = {"rainfall_mmhr": 0.0, "water_level_m": 0.0, "soil_moisture_pct": 20.0}
    _, _, factors = FactorAttributionEngine.attribute_flood(features)
    for f in factors:
        assert f.normalized_value == 0.0
        assert f.contribution == 0.0


def test_flood_attribution_max_inputs():
    features = {"rainfall_mmhr": 150.0, "water_level_m": 20.0, "soil_moisture_pct": 100.0}
    _, _, factors = FactorAttributionEngine.attribute_flood(features)
    for f in factors:
        assert f.normalized_value == 1.0
    total_contrib = sum(f.contribution for f in factors)
    assert pytest.approx(total_contrib, 0.01) == 1.0


def test_heat_attribution_steadman():
    features = {"temperature_c": 35.0, "humidity_pct": 70.0}
    fname, fexpr, factors = FactorAttributionEngine.attribute_heat(features)
    assert "Steadman" in fname
    assert len(factors) == 2
    temp_factor = next(f for f in factors if f.factor_name == "ambient_temperature")
    assert temp_factor.input_value == 35.0
    assert temp_factor.contribution > 0.0


def test_drought_attribution_deficit():
    features = {"soil_moisture_pct": 10.0, "temperature_c": 38.0, "humidity_pct": 20.0}
    fname, fexpr, factors = FactorAttributionEngine.attribute_drought(features)
    assert "Drought" in fname
    assert len(factors) == 3
    soil_factor = next(f for f in factors if f.factor_name == "soil_moisture_depletion")
    assert soil_factor.weight == 0.50
    assert soil_factor.contribution > 0.0


def test_human_impact_attribution():
    vuln_dict = {
        "exposure_ratio": 0.80,
        "vulnerability": 0.60,
        "accessibility_risk": 0.40,
    }
    fname, fexpr, factors = FactorAttributionEngine.attribute_human_impact(vuln_dict)
    assert len(factors) == 3
    exp_f = next(f for f in factors if f.factor_name == "hazard_exposure")
    assert exp_f.weight == 0.50
    assert pytest.approx(exp_f.contribution, 0.01) == 0.40


def test_response_priority_attribution():
    action_dict = {
        "urgency_score": 0.90,
        "vulnerability_score": 0.70,
        "cascade_severity": 0.50,
        "confidence": 0.80,
    }
    fname, fexpr, factors = FactorAttributionEngine.attribute_response_priority(action_dict)
    assert len(factors) == 4
    urg_f = next(f for f in factors if f.factor_name == "operational_urgency")
    assert urg_f.weight == 0.40
    assert pytest.approx(urg_f.contribution, 0.01) == 0.36
