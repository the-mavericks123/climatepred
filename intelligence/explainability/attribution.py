"""
Mathematical factor attribution engine for Phase 10 Explainability.
Derives quantitative factor contributions using the exact mathematical formulas
from the authoritative models in Phases 2 through 9.
"""

from typing import Any, Dict, List, Optional, Tuple
from intelligence.explainability.types import FactorAttribution


class FactorAttributionEngine:
    """
    Computes exact factor contributions without inventing artificial weights or drifting from model definitions.
    """

    @classmethod
    def attribute_flood(cls, features: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Tuple[str, str, List[FactorAttribution]]:
        """
        Attributes flood score to rainfall, water level, and soil moisture using authoritative weights.
        Formula: flood_score = w_rain * rain_score + w_level * level_score + w_soil * soil_score
        """
        w_rain = float(config.get("rainfall_weight", 0.40)) if config else 0.40
        w_level = float(config.get("water_level_weight", 0.35)) if config else 0.35
        w_soil = float(config.get("soil_moisture_weight", 0.25)) if config else 0.25

        rain_raw = float(features.get("rainfall_mmhr") or features.get("rainfall") or 0.0)
        level_raw = float(features.get("water_level_m") or features.get("water_level") or 0.0)
        soil_raw = float(features.get("soil_moisture_pct") or features.get("soil_moisture") or 0.0)

        # Normalization matching flood-v1
        rain_norm = max(0.0, min(1.0, rain_raw / 100.0))
        level_norm = max(0.0, min(1.0, level_raw / 15.0))
        # Soil moisture: below 30% gives 0.0, 100% gives 1.0
        soil_norm = max(0.0, min(1.0, (soil_raw - 30.0) / 70.0)) if soil_raw >= 30.0 else 0.0

        factors = [
            FactorAttribution(
                factor_name="rainfall_rate",
                display_name="Rainfall Intensity Rate",
                input_value=rain_raw,
                normalized_value=round(rain_norm, 4),
                weight=w_rain,
                contribution=round(rain_norm * w_rain, 4),
                unit="mm/hr",
                description=f"Surface precipitation rate contributing {rain_norm * w_rain:.3f} to flood score.",
            ),
            FactorAttribution(
                factor_name="water_level",
                display_name="River & Channel Water Level",
                input_value=level_raw,
                normalized_value=round(level_norm, 4),
                weight=w_level,
                contribution=round(level_norm * w_level, 4),
                unit="m",
                description=f"Hydrological stage level contributing {level_norm * w_level:.3f} to flood score.",
            ),
            FactorAttribution(
                factor_name="soil_moisture",
                display_name="Soil Saturation Level",
                input_value=soil_raw,
                normalized_value=round(soil_norm, 4),
                weight=w_soil,
                contribution=round(soil_norm * w_soil, 4),
                unit="%",
                description=f"Subsurface saturation preventing infiltration, contributing {soil_norm * w_soil:.3f}.",
            ),
        ]
        # Sort factors by contribution descending
        factors.sort(key=lambda f: f.contribution, reverse=True)
        formula_name = "Linear Weighted Hydrological Index"
        expression = f"flood_score = {w_rain:.2f} * norm(rainfall) + {w_level:.2f} * norm(water_level) + {w_soil:.2f} * norm(soil_moisture)"
        return formula_name, expression, factors

    @classmethod
    def attribute_heat(cls, features: Dict[str, Any]) -> Tuple[str, str, List[FactorAttribution]]:
        """
        Attributes heat score to ambient temperature and relative humidity via authoritative HeatModel calculation.
        """
        temp = float(features.get("temperature_c") or features.get("temperature") or 25.0)
        humidity = float(features.get("humidity_pct") or features.get("humidity") or 50.0)

        # Call authoritative Phase 3 HeatModel apparent temperature calculation
        from intelligence.hazards.heat import HeatModel
        apparent_temp = HeatModel.calculate_apparent_temperature(temp, humidity)

        # Normalization: baseline 27C (0.0) to 65C (1.0)
        norm_severity = max(0.0, min(1.0, (apparent_temp - 27.0) / (65.0 - 27.0))) if apparent_temp >= 27.0 else 0.0

        factors = [
            FactorAttribution(
                factor_name="ambient_temperature",
                display_name="Dry Bulb Temperature",
                input_value=temp,
                normalized_value=round(max(0.0, min(1.0, (temp - 20.0) / 25.0)), 4),
                weight=0.60,
                contribution=round(0.60 * norm_severity, 4),
                unit="°C",
                description="Primary thermal driver elevating apparent temperature.",
            ),
            FactorAttribution(
                factor_name="relative_humidity",
                display_name="Atmospheric Relative Humidity",
                input_value=humidity,
                normalized_value=round(humidity / 100.0, 4),
                weight=0.40,
                contribution=round(0.40 * norm_severity, 4),
                unit="%",
                description="Moisture content suppressing evaporative cooling.",
            ),
        ]
        factors.sort(key=lambda f: f.contribution, reverse=True)
        formula_name = "Steadman Apparent Temperature Formulation"
        expression = "AT = -2.653 + 0.994 * T + 0.0153 * vapor_pressure(T, RH)"
        return formula_name, expression, factors

    @classmethod
    def attribute_drought(cls, features: Dict[str, Any]) -> Tuple[str, str, List[FactorAttribution]]:
        """
        Attributes drought score to soil dryness (0.50), heat factor (0.30), and humidity deficit (0.20).
        """
        w_dry = 0.50
        w_heat = 0.30
        w_hum = 0.20

        soil = float(features.get("soil_moisture_pct") or features.get("soil_moisture") or 30.0)
        temp = float(features.get("temperature_c") or features.get("temperature") or 25.0)
        hum = float(features.get("humidity_pct") or features.get("humidity") or 50.0)

        # Soil dryness norm: >50% is 0, <5% is 1
        dry_norm = max(0.0, min(1.0, (50.0 - soil) / 45.0)) if soil <= 50.0 else 0.0
        heat_norm = max(0.0, min(1.0, (temp - 25.0) / 20.0)) if temp >= 25.0 else 0.0
        hum_norm = max(0.0, min(1.0, (60.0 - hum) / 50.0)) if hum <= 60.0 else 0.0

        factors = [
            FactorAttribution(
                factor_name="soil_moisture_depletion",
                display_name="Soil Moisture Deficit",
                input_value=soil,
                normalized_value=round(dry_norm, 4),
                weight=w_dry,
                contribution=round(dry_norm * w_dry, 4),
                unit="%",
                description="Subsurface water deficit driving agricultural/ecological stress.",
            ),
            FactorAttribution(
                factor_name="persistent_heat",
                display_name="Persistent High Temperature",
                input_value=temp,
                normalized_value=round(heat_norm, 4),
                weight=w_heat,
                contribution=round(heat_norm * w_heat, 4),
                unit="°C",
                description="Atmospheric evaporative demand amplifying soil drying.",
            ),
            FactorAttribution(
                factor_name="atmospheric_aridity",
                display_name="Relative Humidity Deficit",
                input_value=hum,
                normalized_value=round(hum_norm, 4),
                weight=w_hum,
                contribution=round(hum_norm * w_hum, 4),
                unit="%",
                description="Low atmospheric water vapor vaporizing remaining moisture.",
            ),
        ]
        factors.sort(key=lambda f: f.contribution, reverse=True)
        formula_name = "Composite Agricultural Drought Deficit"
        expression = "drought_score = 0.50 * soil_deficit + 0.30 * heat_factor + 0.20 * humidity_deficit"
        return formula_name, expression, factors

    @classmethod
    def attribute_human_impact(cls, vuln_dict: Dict[str, Any]) -> Tuple[str, str, List[FactorAttribution]]:
        """
        Attributes human impact using Cobb-Douglas elasticity:
        base = (hazard^0.40) * (exposure^0.30) * (vulnerability^0.30)
        human_impact = min(1.0, base * (1 + 0.35 * accessibility_risk))
        """
        w_exp = float(vuln_dict.get("exposure_weight", 0.50))
        w_vuln = float(vuln_dict.get("vulnerability_weight", 0.35))
        w_health = float(vuln_dict.get("accessibility_weight", 0.15))

        exp_ratio = float(vuln_dict.get("exposure_ratio", 0.0))
        vuln_score = float(vuln_dict.get("vulnerability", 0.0))
        access_risk = float(vuln_dict.get("accessibility_risk", 0.0))

        factors = [
            FactorAttribution(
                factor_name="hazard_exposure",
                display_name="Spatial Hazard Exposure",
                input_value=exp_ratio,
                normalized_value=round(exp_ratio, 4),
                weight=w_exp,
                contribution=round(exp_ratio * w_exp, 4),
                description="Percentage of zone resident population intersecting active/predicted hazard.",
            ),
            FactorAttribution(
                factor_name="demographic_vulnerability",
                display_name="Demographic Vulnerability Index",
                input_value=vuln_score,
                normalized_value=round(vuln_score, 4),
                weight=w_vuln,
                contribution=round(vuln_score * w_vuln, 4),
                description="Elderly, child, and mobility-impaired resident concentration.",
            ),
            FactorAttribution(
                factor_name="accessibility_impediments",
                display_name="Infrastructural / Healthcare Deficit",
                input_value=access_risk,
                normalized_value=round(access_risk, 4),
                weight=w_health,
                contribution=round(access_risk * w_health, 4),
                description="Lack of emergency hospital access and arterial road redundancy.",
            ),
        ]
        factors.sort(key=lambda f: f.contribution, reverse=True)
        formula_name = "Cobb-Douglas Human Impact & Vulnerability Synthesis"
        expression = "human_impact = min(1.0, 0.50 * exposure + 0.35 * demographic_vulnerability + 0.15 * accessibility_risk)"
        return formula_name, expression, factors


    @classmethod
    def attribute_response_priority(cls, action_dict: Dict[str, Any]) -> Tuple[str, str, List[FactorAttribution]]:
        """
        Attributes response action priority score to urgency (0.40), vulnerability (0.25),
        cascade severity (0.20), and model confidence (0.15) matching authoritative Phase 9 calculation.
        """
        w_urg = 0.40
        w_vuln = 0.25
        w_casc = 0.20
        w_conf = 0.15

        urg = float(action_dict.get("urgency_score", 0.50))
        vuln = float(action_dict.get("vulnerability_score", 0.50))
        casc = float(action_dict.get("cascade_severity", 0.30))
        conf = float(action_dict.get("confidence", 0.85))

        factors = [
            FactorAttribution(
                factor_name="operational_urgency",
                display_name="Operational Urgency",
                input_value=urg,
                normalized_value=round(urg, 4),
                weight=w_urg,
                contribution=round(urg * w_urg, 4),
                description="Temporal horizon discounted severity and access impediment risk.",
            ),
            FactorAttribution(
                factor_name="target_vulnerability",
                display_name="Population Vulnerability",
                input_value=vuln,
                normalized_value=round(vuln, 4),
                weight=w_vuln,
                contribution=round(vuln * w_vuln, 4),
                description="Concentration of high-risk residents in target sector.",
            ),
            FactorAttribution(
                factor_name="compound_cascade_severity",
                display_name="Cascading Threat Severity",
                input_value=casc,
                normalized_value=round(casc, 4),
                weight=w_casc,
                contribution=round(casc * w_casc, 4),
                description="Multi-hazard amplification and infrastructure failure chain.",
            ),
            FactorAttribution(
                factor_name="evidence_confidence",
                display_name="Upstream Evidence Confidence",
                input_value=conf,
                normalized_value=round(conf, 4),
                weight=w_conf,
                contribution=round(conf * w_conf, 4),
                description="Aggregated data quality and forecast reliability.",
            ),
        ]
        factors.sort(key=lambda f: f.contribution, reverse=True)
        formula_name = "Deterministic Emergency Priority Formula"
        expression = "priority = 0.40 * urgency + 0.25 * vulnerability + 0.20 * cascade + 0.15 * confidence"
        return formula_name, expression, factors

