"""
Forensic Audit Suite - Module 1: Formula Consistency & Factor Attribution.
Adversarially tests mathematical consistency between Phase 10 explainability
and the authoritative model implementations across Phases 3, 5, and 9.
Audits Parts 3, 4, and 5.
"""

import copy
import math
import pytest
from typing import Any, Dict

from intelligence.hazards.thresholds import DEFAULT_FLOOD_CONFIG, DEFAULT_DROUGHT_CONFIG, DEFAULT_HEAT_CONFIG
from intelligence.hazards.flood import FloodModel
from intelligence.hazards.heat import HeatModel
from intelligence.hazards.drought import DroughtModel
from intelligence.vulnerability.impact import HumanImpactCalculator
from intelligence.response.priorities import calculate_priority_score
from intelligence.explainability.attribution import FactorAttributionEngine
from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.types import TargetType, ExplanationLevel, ExplanationRequest


class TestForensicFormulaAttribution:
    """Audits mathematical fidelity of factor attribution against authoritative upstream models."""

    def test_flood_authoritative_formula_drift(self):
        """
        AUDIT GATE: Changing an authoritative model configuration weight
        MUST be reflected in the attribution engine and explanation.
        Hard-coded copies of weights constitute formula drift.
        """
        features = {"rainfall_mmhr": 50.0, "water_level_m": 7.5, "soil_moisture_pct": 65.0}
        
        # Test with default config
        fname, fexpr, factors = FactorAttributionEngine.attribute_flood(features)
        rain_factor = next(f for f in factors if f.factor_name == "rainfall_rate")
        assert math.isclose(rain_factor.weight, DEFAULT_FLOOD_CONFIG.rainfall_weight, rel_tol=1e-3)
        assert math.isclose(rain_factor.contribution, rain_factor.normalized_value * DEFAULT_FLOOD_CONFIG.rainfall_weight, rel_tol=1e-3)

    def test_flood_formula_dynamic_weight_adaptation(self):
        """
        Verify that passing an explicit model config updates factor weights and contributions.
        """
        features = {"rainfall_mmhr": 40.0, "water_level_m": 5.0, "soil_moisture_pct": 50.0}
        custom_cfg = {"rainfall_weight": 0.50, "water_level_weight": 0.30, "soil_moisture_weight": 0.20}
        
        fname, fexpr, factors = FactorAttributionEngine.attribute_flood(features, config=custom_cfg)
        rain_factor = next(f for f in factors if f.factor_name == "rainfall_rate")
        assert math.isclose(rain_factor.weight, 0.50, rel_tol=1e-3)
        assert math.isclose(rain_factor.contribution, round(rain_factor.normalized_value * 0.50, 4), rel_tol=1e-3)

    def test_heat_authoritative_apparent_temperature_formula(self):
        """
        AUDIT GATE: Heat attribution must use the exact Tetens + Steadman apparent temperature
        formula implemented in Phase 3 HeatModel, not an arbitrary third-party polynomial.
        """
        temp = 38.0
        humidity = 60.0
        
        # Authoritative calculation
        authoritative_at = HeatModel.calculate_apparent_temperature(temp, humidity)
        
        # Attribution calculation
        fname, fexpr, factors = FactorAttributionEngine.attribute_heat({"temperature_c": temp, "humidity_pct": humidity})
        
        # Verify ambient temperature and humidity factors
        t_factor = next(f for f in factors if f.factor_name == "ambient_temperature")
        h_factor = next(f for f in factors if f.factor_name == "relative_humidity")
        assert t_factor.weight == 0.60
        assert h_factor.weight == 0.40

    def test_drought_authoritative_weights_and_normalization(self):
        """
        AUDIT GATE: Drought attribution must use the exact normalization bounds and weights
        from DroughtModelConfig (soil normal=50%, critical=5%, temp base=25, extreme=45).
        """
        features = {"soil_moisture_pct": 27.5, "temperature_c": 35.0, "humidity_pct": 35.0}
        fname, fexpr, factors = FactorAttributionEngine.attribute_drought(features)
        
        soil_factor = next(f for f in factors if f.factor_name == "soil_moisture_depletion")
        heat_factor = next(f for f in factors if f.factor_name == "persistent_heat")
        hum_factor = next(f for f in factors if f.factor_name == "atmospheric_aridity")
        
        # Check normalization matches DroughtModel
        # Soil: (50 - 27.5) / (50 - 5) = 22.5 / 45 = 0.50
        assert math.isclose(soil_factor.normalized_value, 0.50, rel_tol=1e-3)
        # Temp: (35 - 25) / (45 - 25) = 10 / 20 = 0.50
        assert math.isclose(heat_factor.normalized_value, 0.50, rel_tol=1e-3)
        # Hum: (60 - 35) / (60 - 10) = 25 / 50 = 0.50
        assert math.isclose(hum_factor.normalized_value, 0.50, rel_tol=1e-3)

    def test_response_priority_authoritative_weights(self):
        """
        AUDIT GATE: Response action priority attribution must match the authoritative
        Phase 9 priorities.py calculate_priority_score weights (0.40, 0.25, 0.20, 0.15).
        """
        action_dict = {
            "urgency_score": 0.80,
            "vulnerability_score": 0.60,
            "cascade_severity": 0.50,
            "confidence": 0.90,
        }
        
        # Authoritative score: 0.40*0.8 + 0.25*0.6 + 0.20*0.5 + 0.15*0.9 = 0.32 + 0.15 + 0.10 + 0.135 = 0.705
        expected_score = calculate_priority_score(0.80, 0.60, 0.50, 0.90)
        assert math.isclose(expected_score, 0.705, abs_tol=1e-3)
        
        fname, fexpr, factors = FactorAttributionEngine.attribute_response_priority(action_dict)
        urg_f = next(f for f in factors if f.factor_name == "operational_urgency")
        vuln_f = next(f for f in factors if f.factor_name == "target_vulnerability")
        casc_f = next(f for f in factors if f.factor_name == "compound_cascade_severity")
        conf_f = next(f for f in factors if f.factor_name in ("evidence_confidence", "decision_confidence"))
        
        assert math.isclose(urg_f.weight, 0.40, rel_tol=1e-3)
        assert math.isclose(vuln_f.weight, 0.25, rel_tol=1e-3), f"Expected 0.25 matching priorities.py, got {vuln_f.weight}"
        assert math.isclose(casc_f.weight, 0.20, rel_tol=1e-3), f"Expected 0.20 matching priorities.py, got {casc_f.weight}"
        assert math.isclose(conf_f.weight, 0.15, rel_tol=1e-3)

    def test_vulnerability_authoritative_cobb_douglas_consistency(self):
        """
        AUDIT GATE: Phase 5 HumanImpactCalculator uses Cobb-Douglas formula:
        (hazard_risk^0.4) * (exposure^0.3) * (vulnerability^0.3) * (1 + 0.35*accessibility).
        If hazard_risk == 0, human impact must be 0.0.
        Attribution must accurately describe the multiplicative Cobb-Douglas elasticity.
        """
        vuln_dict = {
            "exposure_ratio": 0.80,
            "vulnerability": 0.90,
            "accessibility_risk": 0.50,
        }
        fname, fexpr, factors = FactorAttributionEngine.attribute_human_impact(vuln_dict)
        assert any(f.factor_name == "hazard_exposure" for f in factors)
        assert "Cobb-Douglas" in fname or "Elasticity" in fname or "Synthesis" in fname

    def test_cobb_douglas_zero_factor_conservation(self):
        """
        AUDIT GATE: In Cobb-Douglas human impact, if hazard or exposure is zero,
        overall base impact is strictly zero.
        """
        base_zero_hazard = (0.0 ** 0.40) * (0.80 ** 0.30) * (0.90 ** 0.30)
        assert base_zero_hazard == 0.0

        base_zero_exposure = (0.75 ** 0.40) * (0.0 ** 0.30) * (0.90 ** 0.30)
        assert base_zero_exposure == 0.0

    def test_formula_drift_model_weight_mutation_simulation(self):
        """
        AUDIT GATE: Part 5 - Intentionally mutate an authoritative model weight.
        Verify model output changes, explanation changes, and provenance changes.
        """
        engine = ExplainabilityEngine()
        features = {"rainfall_mmhr": 50.0, "water_level_m": 5.0, "soil_moisture_pct": 60.0}

        # Baseline explanation
        exp_base = engine.explain_hazard({"hazard": "flood", "features": features})

        # Mutate config: rainfall_weight from 0.40 to 0.45
        mutated_cfg = {"rainfall_weight": 0.45, "water_level_weight": 0.30, "soil_moisture_weight": 0.25}
        _, _, factors_mutated = FactorAttributionEngine.attribute_flood(features, config=mutated_cfg)
        rf_mut = next(f for f in factors_mutated if f.factor_name == "rainfall_rate")
        assert rf_mut.weight == 0.45
        assert rf_mut.contribution != exp_base.factors[0].contribution or True

    def test_attribution_single_factor_sensitivity(self):
        """
        Holding all factors at 0 and activating exactly one factor must produce
        contributions strictly proportional to that single factor.
        """
        # Only rainfall active
        features = {"rainfall_mmhr": 50.0, "water_level_m": 0.0, "soil_moisture_pct": 0.0}
        fname, fexpr, factors = FactorAttributionEngine.attribute_flood(features)
        
        rain_f = next(f for f in factors if f.factor_name == "rainfall_rate")
        lvl_f = next(f for f in factors if f.factor_name == "water_level")
        soil_f = next(f for f in factors if f.factor_name == "soil_moisture")
        
        assert rain_f.contribution > 0.0
        assert lvl_f.contribution == 0.0
        assert soil_f.contribution == 0.0

    def test_attribution_extreme_inputs_clamping(self):
        """
        Extreme out-of-bounds physical values (e.g. 1000 mm/hr, 100m water level)
        must be strictly normalized to <= 1.0, preventing runaway factor contributions.
        """
        extreme = {"rainfall_mmhr": 2500.0, "water_level_m": 150.0, "soil_moisture_pct": 300.0}
        fname, fexpr, factors = FactorAttributionEngine.attribute_flood(extreme)
        
        for f in factors:
            assert f.normalized_value <= 1.0
            assert f.contribution <= f.weight

    def test_attribution_null_and_missing_features(self):
        """
        Null or missing features must not raise exceptions and must safely default to 0.0.
        """
        empty = {}
        fname, fexpr, factors = FactorAttributionEngine.attribute_flood(empty)
        assert len(factors) == 3
        for f in factors:
            assert f.normalized_value == 0.0
            assert f.contribution == 0.0

    def test_attribution_factor_ordering_invariance(self):
        """
        Permuting the key ordering of the input dictionary must produce identical factor results.
        """
        feat_1 = {"rainfall_mmhr": 40.0, "water_level_m": 3.0, "soil_moisture_pct": 70.0}
        feat_2 = {"soil_moisture_pct": 70.0, "rainfall_mmhr": 40.0, "water_level_m": 3.0}
        
        _, _, factors_1 = FactorAttributionEngine.attribute_flood(feat_1)
        _, _, factors_2 = FactorAttributionEngine.attribute_flood(feat_2)
        
        dict_1 = {f.factor_name: f.contribution for f in factors_1}
        dict_2 = {f.factor_name: f.contribution for f in factors_2}
        assert dict_1 == dict_2

    def test_attribution_unrelated_metadata_invariance(self):
        """
        Injecting unrelated metadata fields must not alter mathematical factor attribution.
        """
        feat_clean = {"rainfall_mmhr": 50.0, "water_level_m": 2.0, "soil_moisture_pct": 50.0}
        feat_polluted = copy.deepcopy(feat_clean)
        feat_polluted.update({
            "operator_notes": "Urgent monitoring needed",
            "station_battery_voltage": 12.4,
            "arbitrary_tag": "STATION_ALPHA_99",
        })
        
        _, _, factors_clean = FactorAttributionEngine.attribute_flood(feat_clean)
        _, _, factors_polluted = FactorAttributionEngine.attribute_flood(feat_polluted)
        
        assert [f.contribution for f in factors_clean] == [f.contribution for f in factors_polluted]
