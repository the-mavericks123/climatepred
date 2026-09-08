"""
Weather Data Fusion: Blends Global Macro-Weather with Local Physical ESP32 Sensor Nodes.
Handles spatial interpolation, distance-weighted fusion, and variance analysis.
"""

import math
from typing import Any, Dict, Optional, Tuple
from intelligence.external_data.fusion.spatial_fusion import GlobalSpatialGrid
from intelligence.external_data.types import ExternalObservation


class WeatherFusionEngine:
    """
    Fuses external global meteorological observations with local physical ESP32 sensor telemetry.
    Produces fused observational records with transparent attribution and confidence scores.
    """

    @staticmethod
    def fuse_weather_readings(
        global_obs: Optional[ExternalObservation],
        local_telemetry: Optional[Dict[str, Any]],
        distance_km: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Fuses a global observation with a nearby local sensor packet.
        Weighting formula: Local hardware sensor has high weight if within 15km;
        variance and agreement factors modulate the final confidence.
        """
        if global_obs is None and local_telemetry is None:
            return {
                "fused": None,
                "confidence": 0.0,
                "status": "UNAVAILABLE",
                "breakdown": {},
            }

        if global_obs is None:
            # Only local sensor available
            measurements = local_telemetry.get("measurements", {})
            return {
                "temperature": measurements.get("temperature"),
                "humidity": measurements.get("humidity"),
                "pressure": measurements.get("pressure"),
                "rainfall": measurements.get("rainfall"),
                "water_level": measurements.get("water_level"),
                "confidence": local_telemetry.get("quality", {}).get("confidence", 0.9),
                "mode": "LOCAL_ONLY",
                "breakdown": {
                    "local": measurements.get("temperature"),
                    "global": None,
                    "fused": measurements.get("temperature"),
                },
            }

        if local_telemetry is None:
            # Only global external feed available
            m = global_obs.measurements
            return {
                "temperature": m.temperature,
                "apparent_temperature": m.apparent_temperature,
                "humidity": m.humidity,
                "pressure": m.pressure,
                "rainfall": m.precipitation,
                "water_level": None,  # Strictly None for weather-only
                "confidence": global_obs.quality.score,
                "mode": "GLOBAL_ONLY",
                "breakdown": {
                    "local": None,
                    "global": m.temperature,
                    "fused": m.temperature,
                },
            }

        # Both Global and Local are available -> Multi-source Fusion
        local_m = local_telemetry.get("measurements", {})
        global_m = global_obs.measurements

        # Weighting: local sensor weight decays exponentially with distance from station
        # w_local = 0.75 * exp(-distance / 20km)
        decay = math.exp(-distance_km / 20.0)
        w_local = 0.75 * decay
        w_global = 1.0 - w_local

        # 1. Temperature fusion
        t_local = local_m.get("temperature")
        t_global = global_m.temperature
        if t_local is not None and t_global is not None:
            fused_temp = round(w_local * t_local + w_global * t_global, 2)
            temp_diff = abs(t_local - t_global)
            agreement = max(0.5, 1.0 - min(1.0, temp_diff / 10.0))
        elif t_local is not None:
            fused_temp = t_local
            agreement = 0.85
        else:
            fused_temp = t_global
            agreement = 0.80

        # 2. Humidity fusion
        h_local = local_m.get("humidity")
        h_global = global_m.humidity
        if h_local is not None and h_global is not None:
            fused_humidity = round(w_local * h_local + w_global * h_global, 1)
        else:
            fused_humidity = h_local if h_local is not None else h_global

        # 3. Pressure fusion
        p_local = local_m.get("pressure")
        p_global = global_m.pressure
        if p_local is not None and p_global is not None:
            fused_pressure = round(w_local * p_local + w_global * p_global, 1)
        else:
            fused_pressure = p_local if p_local is not None else p_global

        # 4. Rainfall fusion
        r_local = local_m.get("rainfall")
        r_global = global_m.precipitation
        if r_local is not None and r_global is not None:
            fused_rain = round(max(r_local, r_global), 2)  # Conservative hazard envelope
        else:
            fused_rain = r_local if r_local is not None else r_global

        # 5. Water level: comes ONLY from local hydrological sensor if present!
        # Global weather never synthesizes water level!
        fused_water_level = local_m.get("water_level", None)

        overall_conf = round(min(0.98, agreement * 0.95), 2)

        return {
            "temperature": fused_temp,
            "humidity": fused_humidity,
            "pressure": fused_pressure,
            "rainfall": fused_rain,
            "water_level": fused_water_level,
            "confidence": overall_conf,
            "mode": "FUSED_GLOBAL_LOCAL",
            "breakdown": {
                "global_model": t_global,
                "local_sensor": t_local,
                "fused": fused_temp,
                "distance_km": round(distance_km, 1),
                "weights": {"global": round(w_global, 2), "local": round(w_local, 2)},
            },
        }
