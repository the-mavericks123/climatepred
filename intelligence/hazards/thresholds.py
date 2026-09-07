"""Configurable threshold definitions for Climate Eye View S2 hazard intelligence.
Controls classification tiers, model weights, and physical trigger limits.
"""

from pydantic import BaseModel, Field
from intelligence.hazards.types import HazardClassification


class ClassificationThresholds(BaseModel):
    """
    Standard severity-to-classification boundary configuration.
    Severity values must be in [0.0, 1.0].
    """
    normal_max: float = Field(default=0.19, description="0.00 - 0.19 is NORMAL")
    low_max: float = Field(default=0.39, description="0.20 - 0.39 is LOW")
    moderate_max: float = Field(default=0.59, description="0.40 - 0.59 is MODERATE")
    high_max: float = Field(default=0.79, description="0.60 - 0.79 is HIGH")
    # >= 0.80 is CRITICAL

    def classify(self, severity: float) -> HazardClassification:
        """Deterministic mapping of severity [0.0, 1.0] to HazardClassification."""
        s = max(0.0, min(1.0, severity))
        if s <= self.normal_max:
            return HazardClassification.NORMAL
        elif s <= self.low_max:
            return HazardClassification.LOW
        elif s <= self.moderate_max:
            return HazardClassification.MODERATE
        elif s <= self.high_max:
            return HazardClassification.HIGH
        else:
            return HazardClassification.CRITICAL


class HeatModelConfig(BaseModel):
    """
    Parameters for Preliminary Engineering Heat Model (heat-v1).
    Based on Steadman's Apparent Temperature formulation.
    """
    model_version: str = "heat-v1"
    # Apparent Temperature (AT) thresholds in °C
    at_baseline: float = 27.0     # Below 27°C is NORMAL
    at_low_threshold: float = 32.0 # 27-32°C is LOW (Caution)
    at_moderate_threshold: float = 41.0 # 32-41°C is MODERATE (Extreme Caution)
    at_high_threshold: float = 54.0     # 41-54°C is HIGH (Danger)
    at_critical_ceiling: float = 65.0   # >= 54°C is CRITICAL, 65°C reaches 1.00


class FloodModelConfig(BaseModel):
    """
    Parameters and weights for Preliminary Engineering Flood Model (flood-v1).
    Combines rainfall intensity rate, river/water level, and soil moisture saturation.
    Weights are Initial Engineering Weights.
    """
    model_version: str = "flood-v1"
    # Weights summing to 1.0
    rainfall_weight: float = Field(default=0.40, description="Weight for rainfall intensity rate")
    water_level_weight: float = Field(default=0.35, description="Weight for water/river stage level")
    soil_moisture_weight: float = Field(default=0.25, description="Weight for volumetric soil saturation")

    # Normalization baselines
    rainfall_min_mmhr: float = 0.0
    rainfall_max_mmhr: float = 100.0     # 100 mm/hr reaches 1.0 component score

    water_level_min_m: float = 0.0
    water_level_max_m: float = 15.0       # 15.0 m reaches 1.0 component score

    soil_saturation_min_pct: float = 30.0 # Soil moisture below 30% produces 0.0 flood component
    soil_saturation_max_pct: float = 100.0 # 100% soil saturation produces 1.0 flood component

    # Driver trigger thresholds
    driver_rainfall_threshold_mmhr: float = 50.0
    driver_water_level_threshold_m: float = 8.0
    driver_soil_saturation_threshold_pct: float = 80.0


class DroughtModelConfig(BaseModel):
    """
    Parameters and weights for Preliminary Engineering Drought Model (drought-v1).
    Combines soil dryness, persistent thermal factor, and atmospheric humidity deficit.
    Weights are Initial Engineering Weights.
    """
    model_version: str = "drought-v1"
    # Weights summing to 1.0
    soil_dryness_weight: float = Field(default=0.50, description="Weight for depleted soil moisture")
    heat_factor_weight: float = Field(default=0.30, description="Weight for elevated ambient temperature")
    humidity_deficit_weight: float = Field(default=0.20, description="Weight for atmospheric dryness")

    # Normalization baselines
    soil_moisture_normal_pct: float = 50.0    # Above 50% gives 0.0 dryness component
    soil_moisture_critical_pct: float = 5.0   # Below 5% gives 1.0 dryness component

    temp_baseline_c: float = 25.0             # Temperature below 25°C gives 0.0 heat component
    temp_extreme_c: float = 45.0              # Temperature >= 45°C gives 1.0 heat component

    humidity_normal_pct: float = 60.0         # RH above 60% gives 0.0 humidity deficit
    humidity_critical_pct: float = 10.0       # RH <= 10% gives 1.0 humidity deficit

    # Driver trigger thresholds
    driver_dry_soil_threshold_pct: float = 15.0
    driver_high_temp_threshold_c: float = 40.0
    driver_low_humidity_threshold_pct: float = 20.0


# Default singleton configurations
DEFAULT_CLASSIFICATION_THRESHOLDS = ClassificationThresholds()
DEFAULT_HEAT_CONFIG = HeatModelConfig()
DEFAULT_FLOOD_CONFIG = FloodModelConfig()
DEFAULT_DROUGHT_CONFIG = DroughtModelConfig()
