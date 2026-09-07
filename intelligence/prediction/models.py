"""Deterministic trend forecasting model for environmental variables.
Extrapolates physical values for future horizons and enforces strict physical bounding.
"""

from typing import Dict, List, Optional, Tuple
from intelligence.prediction.features import TemporalTrendSummary
from intelligence.prediction.thresholds import PhysicalSensorBounds, DEFAULT_PHYSICAL_BOUNDS


class DeterministicTrendForecaster:
    """
    Projects physical environmental variables forward in time using linear trend or persistence fallback.
    Clamps all projected values strictly to physically valid measurement boundaries.
    """

    def __init__(self, bounds: PhysicalSensorBounds = DEFAULT_PHYSICAL_BOUNDS):
        self.bounds = bounds

    def get_bounds_for_variable(self, variable_name: str) -> Tuple[float, float]:
        """Returns (min_val, max_val) for a given sensor variable."""
        b = self.bounds
        if variable_name == "temperature":
            return (b.temp_min_c, b.temp_max_c)
        elif variable_name == "humidity":
            return (b.humidity_min_pct, b.humidity_max_pct)
        elif variable_name == "rainfall":
            return (b.rainfall_min_mmhr, b.rainfall_max_mmhr)
        elif variable_name == "soil_moisture":
            return (b.soil_moisture_min_pct, b.soil_moisture_max_pct)
        elif variable_name == "water_level":
            return (b.water_level_min_m, b.water_level_max_m)
        elif variable_name == "pressure":
            return (b.pressure_min_hpa, b.pressure_max_hpa)
        elif variable_name == "air_quality":
            return (b.air_quality_min_aqi, b.air_quality_max_aqi)
        else:
            return (0.0, 1000.0)

    def forecast_variable(
        self,
        summary: TemporalTrendSummary,
        horizon_minutes: int,
    ) -> Tuple[Optional[float], List[str]]:
        """
        Extrapolates variable to horizon_minutes.
        Returns: (predicted_value, driver_notes).
        """
        drivers: List[str] = []

        if summary.current_value is None:
            drivers.append(f"{summary.variable_name} measurement unobserved / null")
            return None, drivers

        curr = summary.current_value
        var = summary.variable_name
        min_bound, max_bound = self.get_bounds_for_variable(var)

        # 1. Fallback if insufficient history
        if summary.is_insufficient:
            drivers.append(f"{var} persistence fallback ({curr:.1f}): insufficient history to project trend")
            clamped_val = max(min_bound, min(max_bound, curr))
            return clamped_val, drivers

        # 2. Linear projection: future = current + slope * horizon_minutes
        slope = summary.rate_of_change_per_minute
        delta = slope * float(horizon_minutes)
        projected = curr + delta

        # 3. Physical bounding clamping
        if projected < min_bound:
            drivers.append(f"{var} projection clamped to physical floor ({min_bound:.1f})")
            final_val = min_bound
        elif projected > max_bound:
            drivers.append(f"{var} projection clamped to physical ceiling ({max_bound:.1f})")
            final_val = max_bound
        else:
            final_val = projected

        # 4. Trajectory driver note
        if abs(delta) >= 0.2:
            sign = "+" if delta > 0 else ""
            drivers.append(f"{var} trend: {sign}{delta:.1f} over +{horizon_minutes}m (rate: {slope*60.0:+.2f}/hr)")
        else:
            drivers.append(f"{var} trend: stable (projected {final_val:.1f} at +{horizon_minutes}m)")

        return round(final_val, 4), drivers
