"""
Quality Gates and Validation for External Environmental Observations.
"""

from datetime import datetime, timezone
from typing import List, Tuple
from intelligence.external_data.types import ExternalLocation, ExternalMeasurements, ObservationQuality


class ObservationQualityGate:
    """Evaluates physical bounds, geographic validity, and temporal integrity."""

    @staticmethod
    def evaluate(
        location: ExternalLocation,
        measurements: ExternalMeasurements,
        obs_timestamp: datetime,
        received_at: datetime,
    ) -> ObservationQuality:
        flags: List[str] = []
        score = 1.0

        # 1. Coordinate check
        if not (-90.0 <= location.lat <= 90.0) or not (-180.0 <= location.lon <= 180.0):
            flags.append("INVALID_COORDINATES")
            score -= 0.5

        # 2. Temporal checks
        now_utc = datetime.now(timezone.utc)
        diff_future = (obs_timestamp - now_utc).total_seconds()
        if diff_future > 300:
            flags.append("TIMESTAMP_IN_FUTURE")
            score -= 0.4

        diff_age = (now_utc - obs_timestamp).total_seconds()
        if diff_age > 86400:
            flags.append("STALE_OBSERVATION")
            score -= 0.2
        elif diff_age > 3600 * 3:
            flags.append("AGED_OBSERVATION")
            score -= 0.1

        # 3. Physical range checks
        if measurements.temperature is not None:
            if measurements.temperature < -60.0 or measurements.temperature > 65.0:
                flags.append("TEMPERATURE_OUT_OF_BOUNDS")
                score -= 0.3
        else:
            flags.append("MISSING_TEMPERATURE")
            score -= 0.2

        if measurements.humidity is not None:
            if measurements.humidity < 0.0 or measurements.humidity > 100.0:
                flags.append("HUMIDITY_OUT_OF_BOUNDS")
                score -= 0.2

        if measurements.pressure is not None:
            if measurements.pressure < 800.0 or measurements.pressure > 1100.0:
                flags.append("PRESSURE_OUT_OF_BOUNDS")
                score -= 0.2

        if measurements.wind_speed is not None:
            if measurements.wind_speed < 0.0 or measurements.wind_speed > 150.0:
                flags.append("WIND_SPEED_OUT_OF_BOUNDS")
                score -= 0.2

        if measurements.precipitation is not None:
            if measurements.precipitation < 0.0 or measurements.precipitation > 500.0:
                flags.append("PRECIPITATION_OUT_OF_BOUNDS")
                score -= 0.2

        # 4. Water level physical invariant check
        # For weather API feeds, water_level is EXPECTED to be None.
        # It should never be 0.0 when there's no sensor.
        if measurements.water_level is not None:
            if measurements.water_level < 0.0 or measurements.water_level > 50.0:
                flags.append("WATER_LEVEL_OUT_OF_BOUNDS")
                score -= 0.2

        score = max(0.0, min(1.0, round(score, 2)))
        status = "VALID" if score >= 0.7 else ("DEGRADED" if score >= 0.4 else "SUSPECT")

        return ObservationQuality(score=score, status=status, flags=flags)
