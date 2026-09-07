"""
Preliminary Engineering Heat Model (heat-v1).
Deterministic thermal stress and apparent temperature calculation.

Scientific Reference / Methodology:
Based on Steadman's Apparent Temperature formulation (Steadman, 1984; Bureau of Meteorology adaptation).
Apparent temperature models human thermal sensation by combining dry-bulb ambient temperature
and water vapour pressure derived from relative humidity.

Mathematical Formulation:
1. Water Vapour Pressure (e, hPa):
   e = (RH / 100.0) * 6.105 * exp((17.27 * T) / (237.7 + T))
2. Apparent Temperature (AT, °C) with nominal 1.0 m/s wind speed:
   AT = T + 0.33 * e - 0.70 * 1.0 - 4.00
3. Severity Normalization (S ∈ [0.0, 1.0]):
   - AT < 27.0 °C: Normal band [0.00, 0.19]
   - 27.0 <= AT < 32.0 °C: Low risk (Caution) [0.20, 0.39]
   - 32.0 <= AT < 41.0 °C: Moderate risk (Extreme Caution) [0.40, 0.59]
   - 41.0 <= AT < 54.0 °C: High risk (Danger) [0.60, 0.79]
   - AT >= 54.0 °C: Critical risk (Extreme Danger) [0.80, 1.00]

Classification:
  0.00 - 0.19: NORMAL (Status: NOT_DETECTED)
  0.20 - 0.39: LOW (Status: DETECTED)
  0.40 - 0.59: MODERATE (Status: DETECTED)
  0.60 - 0.79: HIGH (Status: DETECTED)
  0.80 - 1.00: CRITICAL (Status: DETECTED)

Engineering Assumptions & Limitations:
- Initial heuristic parameters calibrated for subtropical and tropical urban environments.
- Assumes light ambient air velocity (1.0 m/s) when anemometer data is unavailable.
- Does not model direct solar radiation / black-globe temperature (WBGT).
"""

import math
from typing import List, Tuple
from intelligence.hazards.base import BaseHazardModel
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict
from intelligence.hazards.thresholds import (
    DEFAULT_CLASSIFICATION_THRESHOLDS,
    DEFAULT_HEAT_CONFIG,
    HeatModelConfig,
)
from intelligence.hazards.types import (
    HazardClassification,
    HazardResult,
    HazardStatus,
    HazardType,
)


class HeatModel(BaseHazardModel):
    """Deterministic Heat Risk Model (heat-v1)."""

    def __init__(self, config: HeatModelConfig = DEFAULT_HEAT_CONFIG) -> None:
        self.config = config

    @property
    def hazard_type(self) -> HazardType:
        return HazardType.HEAT

    @property
    def model_version(self) -> str:
        return self.config.model_version

    @staticmethod
    def calculate_apparent_temperature(temp_c: float, humidity_pct: float, wind_speed_ms: float = 1.0) -> float:
        """Computes Steadman apparent temperature in °C."""
        # Tetens equation for saturated water vapour pressure (hPa)
        vp = (humidity_pct / 100.0) * 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
        # Steadman apparent temperature
        at = temp_c + (0.33 * vp) - (0.70 * wind_speed_ms) - 4.00
        return at

    def calculate_severity(self, at: float) -> Tuple[float, List[str]]:
        """Maps apparent temperature monotonically to normalized severity [0.0, 1.0] and drivers."""
        drivers: List[str] = []

        if at < self.config.at_baseline:
            # Scale 0 to 27 °C into 0.00 to 0.19
            clamped_at = max(0.0, at)
            sev = (clamped_at / self.config.at_baseline) * 0.19
            drivers.append("Thermal conditions within comfortable baseline range")
        elif at < self.config.at_low_threshold:
            # Scale 27 to 32 °C into 0.20 to 0.39
            fraction = (at - self.config.at_baseline) / (self.config.at_low_threshold - self.config.at_baseline)
            sev = 0.20 + (fraction * 0.19)
            drivers.append(f"Elevated apparent temperature ({at:.1f} °C) reaching Caution threshold")
        elif at < self.config.at_moderate_threshold:
            # Scale 32 to 41 °C into 0.40 to 0.59
            fraction = (at - self.config.at_low_threshold) / (self.config.at_moderate_threshold - self.config.at_low_threshold)
            sev = 0.40 + (fraction * 0.19)
            drivers.append(f"High thermal stress: apparent temperature ({at:.1f} °C) in Extreme Caution zone")
        elif at < self.config.at_high_threshold:
            # Scale 41 to 54 °C into 0.60 to 0.79
            fraction = (at - self.config.at_moderate_threshold) / (self.config.at_high_threshold - self.config.at_moderate_threshold)
            sev = 0.60 + (fraction * 0.19)
            drivers.append(f"Dangerous thermal index ({at:.1f} °C): heat exhaustion and heat stroke probable")
        else:
            # Scale >= 54 °C into 0.80 to 1.00
            fraction = min(1.0, (at - self.config.at_high_threshold) / (self.config.at_critical_ceiling - self.config.at_high_threshold))
            sev = 0.80 + (fraction * 0.20)
            drivers.append(f"CRITICAL: Extreme Danger apparent temperature ({at:.1f} °C) exceeding lethal tolerance thresholds")

        return max(0.0, min(1.0, sev)), drivers

    def evaluate(self, features: HazardFeatures, verdict: QualityGateVerdict) -> HazardResult:
        if not verdict.is_admissible or features.temperature_c is None or features.humidity_pct is None:
            return self.build_unavailable_result(features, verdict.reason or "Missing temperature or humidity")

        temp = features.temperature_c
        rh = features.humidity_pct
        at = self.calculate_apparent_temperature(temp, rh)
        severity, drivers = self.calculate_severity(at)

        # Contextual physical drivers
        if temp >= 40.0:
            drivers.append(f"Extreme dry-bulb ambient temperature ({temp:.1f} °C)")
        elif temp >= 32.0:
            drivers.append(f"High ambient dry-bulb temperature ({temp:.1f} °C)")

        if rh >= 70.0 and temp >= 28.0:
            drivers.append(f"High relative humidity ({rh:.1f} %) severely inhibits evaporative cooling")

        classification = DEFAULT_CLASSIFICATION_THRESHOLDS.classify(severity)
        status = HazardStatus.NOT_DETECTED if classification == HazardClassification.NORMAL else HazardStatus.DETECTED

        features_dict = features.as_feature_dict()
        features_dict["apparent_temperature_c"] = round(at, 2)

        return HazardResult(
            hazard_id=f"HAZ-HEAT-{features.node_id}-{int(features.timestamp.timestamp())}",
            hazard=self.hazard_type,
            severity=round(severity, 4),
            confidence=verdict.confidence,
            classification=classification,
            status=status,
            timestamp=features.timestamp,
            forecast_horizon_minutes=0,
            location=features.location,
            features=features_dict,
            drivers=drivers,
            source="model",
            model_version=self.model_version,
            simulated=False,
            provenance_hash=features.provenance_hash,
        )
