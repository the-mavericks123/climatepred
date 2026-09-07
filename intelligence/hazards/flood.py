"""Flood hazard detection model (flood-v1).

STATUS: Preliminary Engineering Model (not operationally/hydrologically calibrated).
Provides deterministic multi-factor flood risk evaluation from telemetry.
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
    FloodModelConfig,
    ClassificationThresholds,
    DEFAULT_FLOOD_CONFIG,
    DEFAULT_CLASSIFICATION_THRESHOLDS,
)


class FloodModel(BaseHazardModel):
    """Deterministic multi-factor flood risk model (flood-v1).

    Combines:
      - Rainfall intensity (mm/hr)
      - Water level (meters)
      - Soil moisture saturation (%)

    Formula:
      flood_score = (rainfall_score * w_rain) + (water_level_score * w_level) + (soil_score * w_soil)
      where weights sum to 1.0.

    Limitations:
      - Uses initial engineering thresholds, not calibrated to a specific hydrological watershed.
      - Does not account for terrain topography, drainage network capacity, or upstream catchment dynamics.
    """

    def __init__(
        self,
        config: FloodModelConfig = DEFAULT_FLOOD_CONFIG,
        classification_thresholds: ClassificationThresholds = DEFAULT_CLASSIFICATION_THRESHOLDS,
    ):
        self.config = config
        self.classification_thresholds = classification_thresholds

    @property
    def hazard_type(self) -> HazardType:
        return HazardType.FLOOD

    @property
    def model_version(self) -> str:
        return self.config.model_version

    def _calculate_rainfall_score(self, rainfall: float) -> float:
        """Normalized rainfall score in [0, 1]."""
        cfg = self.config
        if rainfall <= cfg.rainfall_min_mmhr:
            return 0.0
        if rainfall >= cfg.rainfall_max_mmhr:
            return 1.0
        return (rainfall - cfg.rainfall_min_mmhr) / (cfg.rainfall_max_mmhr - cfg.rainfall_min_mmhr)

    def _calculate_water_level_score(self, water_level: float) -> float:
        """Normalized water level score in [0, 1]."""
        cfg = self.config
        if water_level <= cfg.water_level_min_m:
            return 0.0
        if water_level >= cfg.water_level_max_m:
            return 1.0
        return (water_level - cfg.water_level_min_m) / (cfg.water_level_max_m - cfg.water_level_min_m)

    def _calculate_soil_moisture_score(self, soil_moisture: float) -> float:
        """Normalized soil moisture saturation score in [0, 1]."""
        cfg = self.config
        if soil_moisture <= cfg.soil_saturation_min_pct:
            return 0.0
        if soil_moisture >= cfg.soil_saturation_max_pct:
            return 1.0
        return (soil_moisture - cfg.soil_saturation_min_pct) / (cfg.soil_saturation_max_pct - cfg.soil_saturation_min_pct)

    def evaluate(
        self,
        features: HazardFeatures,
        verdict: QualityGateVerdict,
    ) -> HazardResult:
        """Evaluate flood hazard deterministically."""
        if (
            not verdict.is_admissible
            or features.rainfall_mmhr is None
            or features.water_level_m is None
            or features.soil_moisture_pct is None
        ):
            return self.build_unavailable_result(
                features,
                verdict.reason or "Missing required flood sensor measurements",
            )

        rainfall = features.rainfall_mmhr
        water_level = features.water_level_m
        soil_moisture = features.soil_moisture_pct

        # Component scores
        rainfall_score = self._calculate_rainfall_score(rainfall)
        water_level_score = self._calculate_water_level_score(water_level)
        soil_score = self._calculate_soil_moisture_score(soil_moisture)

        # Weighted combination
        cfg = self.config
        raw_severity = (
            rainfall_score * cfg.rainfall_weight
            + water_level_score * cfg.water_level_weight
            + soil_score * cfg.soil_moisture_weight
        )
        severity = max(0.0, min(1.0, round(raw_severity, 4)))

        # Classification
        classification = self.classification_thresholds.classify(severity)
        status = HazardStatus.NOT_DETECTED if classification == HazardClassification.NORMAL else HazardStatus.DETECTED

        # Deterministic drivers
        drivers = self._generate_drivers(
            rainfall=rainfall,
            water_level=water_level,
            soil_moisture=soil_moisture,
            rainfall_score=rainfall_score,
            water_level_score=water_level_score,
            soil_score=soil_score,
        )

        features_dict = features.as_feature_dict()
        features_dict.update({
            "rainfall_score": round(rainfall_score, 4),
            "water_level_score": round(water_level_score, 4),
            "soil_moisture_score": round(soil_score, 4),
        })

        return HazardResult(
            hazard_id=f"HAZ-FLOOD-{features.node_id}-{int(features.timestamp.timestamp())}",
            hazard=HazardType.FLOOD,
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
        rainfall: float,
        water_level: float,
        soil_moisture: float,
        rainfall_score: float,
        water_level_score: float,
        soil_score: float,
    ) -> List[str]:
        """Generate explicit deterministic driver statements without LLMs."""
        drivers: List[str] = []
        cfg = self.config

        if rainfall >= cfg.driver_rainfall_threshold_mmhr:
            drivers.append(f"heavy rainfall ({rainfall:.1f} mm/hr)")
        elif rainfall_score >= 0.3:
            drivers.append(f"moderate rainfall ({rainfall:.1f} mm/hr)")

        if water_level >= cfg.driver_water_level_threshold_m:
            drivers.append(f"critical water level ({water_level:.2f} m)")
        elif water_level_score >= 0.3:
            drivers.append(f"elevated water level ({water_level:.2f} m)")

        if soil_moisture >= cfg.driver_soil_saturation_threshold_pct:
            drivers.append(f"high soil saturation ({soil_moisture:.1f}%)")
        elif soil_score >= 0.4:
            drivers.append(f"saturated soil ({soil_moisture:.1f}%)")

        if not drivers:
            drivers.append("hydrological indicators within normal limits")

        return drivers
