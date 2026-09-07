"""Drought hazard detection model (drought-v1).

STATUS: Preliminary Engineering Model (not operationally/climatologically calibrated).
Provides deterministic preliminary drought risk score from current telemetry indicators.
"""

from typing import List
from intelligence.hazards.base import BaseHazardModel
from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardResult,
    HazardClassification,
)
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict
from intelligence.hazards.thresholds import (
    DroughtModelConfig,
    ClassificationThresholds,
    DEFAULT_DROUGHT_CONFIG,
    DEFAULT_CLASSIFICATION_THRESHOLDS,
)


class DroughtModel(BaseHazardModel):
    """Deterministic preliminary drought risk model (drought-v1).

    Combines current atmospheric and pedospheric indicators:
      - Soil moisture deficit (%)
      - Elevated temperature (°C)
      - Atmospheric humidity deficit (%)

    Formula:
      drought_score = (soil_dryness_score * w_soil) + (heat_factor_score * w_temp) + (humidity_deficit_score * w_hum)
      where weights sum to 1.0.

    Monotonicity behavior:
      - Decreasing soil moisture -> non-decreasing drought severity.
      - Increasing temperature -> non-decreasing drought severity.
      - Decreasing humidity -> non-decreasing drought severity.

    Limitations:
      - This is a short-term instantaneous indicator of dry, hot, low-moisture stress conditions.
      - It is NOT a standard meteorological drought index (such as SPI, SPEI, or Palmer PDSI) which requires multi-week or multi-month historical precipitation deficit records.
    """

    def __init__(
        self,
        config: DroughtModelConfig = DEFAULT_DROUGHT_CONFIG,
        classification_thresholds: ClassificationThresholds = DEFAULT_CLASSIFICATION_THRESHOLDS,
    ):
        self.config = config
        self.classification_thresholds = classification_thresholds

    @property
    def hazard_type(self) -> HazardType:
        return HazardType.DROUGHT

    @property
    def model_version(self) -> str:
        return self.config.model_version

    def _calculate_soil_dryness_score(self, soil_moisture: float) -> float:
        """Normalized soil dryness score in [0, 1].

        Lower soil moisture produces higher dryness score.
        """
        cfg = self.config
        if soil_moisture >= cfg.soil_moisture_normal_pct:
            return 0.0
        if soil_moisture <= cfg.soil_moisture_critical_pct:
            return 1.0
        return (cfg.soil_moisture_normal_pct - soil_moisture) / (
            cfg.soil_moisture_normal_pct - cfg.soil_moisture_critical_pct
        )

    def _calculate_heat_factor_score(self, temperature: float) -> float:
        """Normalized heat stress factor in [0, 1]."""
        cfg = self.config
        if temperature <= cfg.temp_baseline_c:
            return 0.0
        if temperature >= cfg.temp_extreme_c:
            return 1.0
        return (temperature - cfg.temp_baseline_c) / (cfg.temp_extreme_c - cfg.temp_baseline_c)

    def _calculate_humidity_deficit_score(self, humidity: float) -> float:
        """Normalized humidity deficit score in [0, 1]."""
        cfg = self.config
        if humidity >= cfg.humidity_normal_pct:
            return 0.0
        if humidity <= cfg.humidity_critical_pct:
            return 1.0
        return (cfg.humidity_normal_pct - humidity) / (
            cfg.humidity_normal_pct - cfg.humidity_critical_pct
        )

    def evaluate(
        self,
        features: HazardFeatures,
        verdict: QualityGateVerdict,
    ) -> HazardResult:
        """Evaluate drought hazard deterministically."""
        if (
            not verdict.is_admissible
            or features.soil_moisture_pct is None
            or features.temperature_c is None
            or features.humidity_pct is None
        ):
            return self.build_unavailable_result(
                features,
                verdict.reason or "Missing required drought sensor measurements",
            )

        soil_moisture = features.soil_moisture_pct
        temperature = features.temperature_c
        humidity = features.humidity_pct

        # Component scores
        soil_dryness_score = self._calculate_soil_dryness_score(soil_moisture)
        heat_factor_score = self._calculate_heat_factor_score(temperature)
        humidity_deficit_score = self._calculate_humidity_deficit_score(humidity)

        # Weighted combination
        cfg = self.config
        raw_severity = (
            soil_dryness_score * cfg.soil_dryness_weight
            + heat_factor_score * cfg.heat_factor_weight
            + humidity_deficit_score * cfg.humidity_deficit_weight
        )
        severity = max(0.0, min(1.0, round(raw_severity, 4)))

        # Classification
        classification = self.classification_thresholds.classify(severity)
        status = HazardStatus.NOT_DETECTED if classification == HazardClassification.NORMAL else HazardStatus.DETECTED

        # Deterministic drivers
        drivers = self._generate_drivers(
            soil_moisture=soil_moisture,
            temperature=temperature,
            humidity=humidity,
            soil_dryness_score=soil_dryness_score,
            heat_factor_score=heat_factor_score,
            humidity_deficit_score=humidity_deficit_score,
        )

        features_dict = features.as_feature_dict()
        features_dict.update({
            "soil_dryness_score": round(soil_dryness_score, 4),
            "heat_factor_score": round(heat_factor_score, 4),
            "humidity_deficit_score": round(humidity_deficit_score, 4),
        })

        return HazardResult(
            hazard_id=f"HAZ-DROUGHT-{features.node_id}-{int(features.timestamp.timestamp())}",
            hazard=HazardType.DROUGHT,
            severity=severity,
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

    def _generate_drivers(
        self,
        soil_moisture: float,
        temperature: float,
        humidity: float,
        soil_dryness_score: float,
        heat_factor_score: float,
        humidity_deficit_score: float,
    ) -> List[str]:
        """Generate explicit deterministic driver statements without LLMs."""
        drivers: List[str] = []
        cfg = self.config

        if soil_moisture <= cfg.driver_dry_soil_threshold_pct:
            drivers.append(f"severe soil moisture deficit ({soil_moisture:.1f}%)")
        elif soil_dryness_score >= 0.4:
            drivers.append(f"depleted soil moisture ({soil_moisture:.1f}%)")

        if temperature >= cfg.driver_high_temp_threshold_c:
            drivers.append(f"elevated ambient temperature ({temperature:.1f}°C)")
        elif heat_factor_score >= 0.4:
            drivers.append(f"above-baseline temperature ({temperature:.1f}°C)")

        if humidity <= cfg.driver_low_humidity_threshold_pct:
            drivers.append(f"critically low relative humidity ({humidity:.1f}%)")
        elif humidity_deficit_score >= 0.4:
            drivers.append(f"low atmospheric humidity ({humidity:.1f}%)")

        if not drivers:
            drivers.append("soil and atmospheric moisture indicators within normal limits")

        return drivers
