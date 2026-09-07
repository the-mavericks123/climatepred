"""Configurable thresholds and physical bounds for the Phase 3 Prediction Engine.
Defines supported forecast horizons, lookback windows, physical sensor clamping limits,
and horizon confidence discount factors.
"""

from typing import Set
from pydantic import BaseModel, Field

# Strictly supported forecast horizons in minutes
VALID_HORIZONS: Set[int] = {30, 60, 360}

# Minimum history observations required to calculate rate of change / trend
MIN_HISTORY_OBSERVATIONS: int = 2

# Maximum history lookback window in hours (ignore observations older than this)
MAX_LOOKBACK_HOURS: float = 24.0


class PhysicalSensorBounds(BaseModel):
    """
    Physical sensor measurement limits adhering strictly to Canonical Data Contract.
    Extrapolated/predicted values are clamped to these ranges to prevent physical absurdities.
    """
    temp_min_c: float = -50.0
    temp_max_c: float = 65.0

    humidity_min_pct: float = 0.0
    humidity_max_pct: float = 100.0

    pressure_min_hpa: float = 800.0
    pressure_max_hpa: float = 1100.0

    rainfall_min_mmhr: float = 0.0
    rainfall_max_mmhr: float = 500.0

    soil_moisture_min_pct: float = 0.0
    soil_moisture_max_pct: float = 100.0

    water_level_min_m: float = 0.0
    water_level_max_m: float = 50.0

    air_quality_min_aqi: float = 0.0
    air_quality_max_aqi: float = 500.0


class PredictionConfig(BaseModel):
    """Configuration parameters for the deterministic prediction engine."""
    model_version_prefix: str = "pred-v1"
    min_observations: int = Field(default=MIN_HISTORY_OBSERVATIONS)
    max_lookback_hours: float = Field(default=MAX_LOOKBACK_HOURS)

    # Horizon confidence multiplier (longer horizons decay confidence)
    horizon_factors: dict[int, float] = Field(
        default_factory=lambda: {
            30: 0.95,
            60: 0.90,
            360: 0.75,
        }
    )

    # History sufficiency factors
    # ratio of available observations to ideal baseline (e.g. 6 observations)
    ideal_history_count: int = 6

    # Penalty factor when resorting to persistence fallback due to sample_count < 2
    insufficient_history_penalty: float = 0.50

    # Physical clamping bounds
    bounds: PhysicalSensorBounds = Field(default_factory=PhysicalSensorBounds)


DEFAULT_PHYSICAL_BOUNDS = PhysicalSensorBounds()
DEFAULT_PREDICTION_CONFIG = PredictionConfig()
