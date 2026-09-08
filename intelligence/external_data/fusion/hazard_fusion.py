"""
Global Multi-Hazard Fusion Engine.
Integrates weather-derived hazards (Heat, Flood, Drought from existing HazardEngine),
active wildfires (NASA FIRMS), earthquakes (USGS), and multi-hazard alerts (GDACS)
into unified global hazard zones and identifies compound hazard interactions.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from intelligence.core.contracts.telemetry import (
    LocationCoordinate,
    NormalizedTelemetry,
    QualityMetadata,
    SensorMeasurements,
)
from intelligence.external_data.fusion.spatial_fusion import GlobalSpatialGrid
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    ExternalObservation,
    GlobalDisasterEvent,
    GlobalHazardZone,
)
from intelligence.hazards.engine import HazardEngine
from intelligence.hazards.types import HazardType
from intelligence.prediction.engine import PredictionEngine
from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.compound.types import CompoundEvent
from intelligence.vulnerability.engine import VulnerabilityEngine
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.response.engine import ResponsePlannerEngine
from intelligence.core.logging import get_logger

logger = get_logger("hazard_fusion")


class GlobalHazardFusionEngine:
    """
    Coordinates multi-source hazard fusion and drives existing Phase 2-10 engines.
    """

    def __init__(
        self,
        hazard_engine: Optional[HazardEngine] = None,
        prediction_engine: Optional[PredictionEngine] = None,
        compound_engine: Optional[CompoundDisasterEngine] = None,
        vulnerability_engine: Optional[VulnerabilityEngine] = None,
        evacuation_engine: Optional[EvacuationEngine] = None,
        response_engine: Optional[ResponsePlannerEngine] = None,
    ):
        self.hazard_engine = hazard_engine or HazardEngine()
        self.prediction_engine = prediction_engine or PredictionEngine()
        self.compound_engine = compound_engine or CompoundDisasterEngine()
        self.vulnerability_engine = vulnerability_engine or VulnerabilityEngine()
        self.evacuation_engine = evacuation_engine or EvacuationEngine()
        self.response_engine = response_engine or ResponsePlannerEngine()

    @staticmethod
    def observation_to_telemetry(obs: ExternalObservation, station_id: str) -> NormalizedTelemetry:
        """
        Transforms an ExternalObservation into a NormalizedTelemetry packet
        so existing Phase 2-10 intelligence engines can execute natively without modification.
        Strictly preserves water_level = None (never coerced to 0.0).
        """
        loc = LocationCoordinate(
            lat=obs.location.lat,
            lon=obs.location.lon,
            elevation=obs.location.elevation_m or 0.0,
        )
        measurements = SensorMeasurements(
            temperature=obs.measurements.temperature,
            humidity=obs.measurements.humidity,
            pressure=obs.measurements.pressure,
            rainfall=obs.measurements.precipitation,
            soil_moisture=obs.measurements.soil_moisture,
            water_level=obs.measurements.water_level,  # Strictly None for weather-only
            air_quality=obs.measurements.air_quality,
            light_intensity=None,
            battery=100.0,
            sensor_status={"weather_api": "ONLINE"},
        )
        quality = QualityMetadata(
            valid=obs.quality.status != "SUSPECT",
            source=obs.source.upper(),
            received_at=obs.received_at,
            confidence=obs.quality.score,
            flags=obs.quality.flags,
        )
        return NormalizedTelemetry(
            schema_version="1.0",
            node_id=station_id,
            timestamp=obs.timestamp,
            location=loc,
            measurements=measurements,
            quality=quality,
        )

    def evaluate_weather_hazards(
        self, observations: List[ExternalObservation]
    ) -> Tuple[List[GlobalHazardZone], List[Dict[str, Any]], List[CompoundEvent]]:
        """
        Runs existing deterministic HazardEngine, PredictionEngine, and CompoundDisasterEngine
        over all global meteorological observations.
        """
        hazard_zones: List[GlobalHazardZone] = []
        predictions: List[Dict[str, Any]] = []
        compound_events: List[CompoundEvent] = []

        now_utc = datetime.now(timezone.utc)

        for obs in observations:
            station_id = obs.location.name or f"EXT-STN-{obs.observation_id[-6:]}"
            try:
                telem = self.observation_to_telemetry(obs, station_id)
            except Exception as e:
                logger.warning(f"Telemetry contract conversion note: {e}")
                continue

            # 1. Deterministic Phase 2 Hazard Evaluation
            try:
                eval_results = self.hazard_engine.evaluate_telemetry(telem)
                for res in eval_results:
                    # Filter out nominal/background results with 0 severity or unavailable
                    if res.severity <= 0.15:
                        continue

                    h_type = res.hazard.value.upper()
                    zone_id = f"ZONE-WEATHER-{h_type}-{abs(hash(f'{obs.location.lat}_{obs.location.lon}')) % 100000:05d}"
                    radius_km = 45.0 if h_type == "HEAT" else (30.0 if h_type == "FLOOD" else 60.0)

                    # Determine action directive
                    if h_type == "HEAT":
                        action = "Open municipal cooling shelters; issue thermal stress advisories."
                    elif h_type == "FLOOD":
                        action = "Inspect storm runoff channels; prepare flood defenses in low-lying sectors."
                    elif h_type == "DROUGHT":
                        action = "Enforce water conservation quotas; activate drought assistance."
                    else:
                        action = "Maintain continuous environmental surveillance."

                    hazard_zones.append(
                        GlobalHazardZone(
                            zone_id=zone_id,
                            hazard_type=h_type,
                            severity=res.severity,
                            confidence=res.confidence,
                            epistemic_status=EpistemicStatus.INFERRED,
                            geometry={
                                "type": "Point",
                                "coordinates": [obs.location.lon, obs.location.lat],
                            },
                            center=obs.location,
                            radius_km=radius_km,
                            metrics={
                                "temperature": obs.measurements.temperature,
                                "humidity": obs.measurements.humidity,
                                "rainfall": obs.measurements.precipitation,
                                "apparent_temp": obs.measurements.apparent_temperature,
                            },
                            drivers=res.drivers,
                            source="Open-Meteo + Deterministic Hazard Engine",
                            timestamp=now_utc,
                            simulated=False,
                            recommended_action=action,
                        )
                    )
            except Exception as hz_err:
                logger.debug(f"Hazard evaluation note: {hz_err}")

            # 2. Deterministic Phase 3 Predictions (+30m, +60m, +360m)
            try:
                for horizon in [30, 60, 360]:
                    pred_res = self.prediction_engine.predict(
                        current=telem,
                        history=[],
                        horizon_minutes=horizon,
                    )
                    predictions.append(pred_res.model_dump())
            except Exception as pred_err:
                logger.debug(f"Prediction evaluation note: {pred_err}")

        # 3. Deterministic Compound Event Analysis
        try:
            # Check for multi-hazard convergence
            compound_results = self.compound_engine.evaluate_active_hazards(
                hazards=[
                    {
                        "hazard": z.hazard_type.lower(),
                        "severity": z.severity,
                        "confidence": z.confidence,
                        "node_id": z.zone_id,
                        "timestamp": z.timestamp.isoformat(),
                        "drivers": z.drivers,
                    }
                    for z in hazard_zones
                ]
            )
            compound_events.extend(compound_results)
        except Exception as comp_err:
            logger.debug(f"Compound evaluation note: {comp_err}")

        return hazard_zones, predictions, compound_events

    def fuse_all_global_hazards(
        self,
        weather_zones: List[GlobalHazardZone],
        fire_zones: List[GlobalHazardZone],
        quake_zones: List[GlobalHazardZone],
        disaster_zones: List[GlobalHazardZone],
    ) -> List[GlobalHazardZone]:
        """
        Merges all hazard zones into a unified collection and generates COMPOUND hazard zones
        where spatial proximity thresholds overlap.
        """
        all_zones = list(weather_zones) + list(fire_zones) + list(quake_zones) + list(disaster_zones)
        compound_zones: List[GlobalHazardZone] = []
        now_utc = datetime.now(timezone.utc)

        # Spatial overlap check for compound hazard formation (distance < 75 km)
        for i in range(len(all_zones)):
            for j in range(i + 1, len(all_zones)):
                z1 = all_zones[i]
                z2 = all_zones[j]
                if z1.hazard_type == z2.hazard_type or z1.hazard_type == "COMPOUND" or z2.hazard_type == "COMPOUND":
                    continue

                dist = GlobalSpatialGrid.haversine_distance_km(
                    z1.center.lat, z1.center.lon, z2.center.lat, z2.center.lon
                )

                # If overlapping within combined radius
                if dist <= (z1.radius_km + z2.radius_km):
                    # Compound cascade detected!
                    avg_lat = round((z1.center.lat + z2.center.lat) / 2.0, 4)
                    avg_lon = round((z1.center.lon + z2.center.lon) / 2.0, 4)
                    combined_sev = round(min(0.99, max(z1.severity, z2.severity) * 1.15), 2)
                    comp_id = f"ZONE-COMPOUND-{abs(hash(f'{avg_lat}_{avg_lon}')) % 100000:05d}"

                    compound_zones.append(
                        GlobalHazardZone(
                            zone_id=comp_id,
                            hazard_type="COMPOUND",
                            severity=combined_sev,
                            confidence=round(min(z1.confidence, z2.confidence), 2),
                            epistemic_status=EpistemicStatus.INFERRED,
                            geometry={
                                "type": "Point",
                                "coordinates": [avg_lon, avg_lat],
                            },
                            center=ExternalLocation(
                                lat=avg_lat,
                                lon=avg_lon,
                                name=f"Compound Cascade ({z1.hazard_type} + {z2.hazard_type})",
                            ),
                            radius_km=round(max(z1.radius_km, z2.radius_km) * 1.2, 1),
                            metrics={
                                "primary_hazard": z1.hazard_type,
                                "secondary_hazard": z2.hazard_type,
                                "separation_km": round(dist, 1),
                            },
                            drivers=[
                                f"Compound Interaction: {z1.hazard_type} ({z1.severity}) overlapping with {z2.hazard_type} ({z2.severity})",
                                f"Amplified cascading impact across {dist:.1f} km convergence zone",
                            ],
                            source="Climate Eye Compound Disaster Engine",
                            timestamp=now_utc,
                            simulated=False,
                            recommended_action=f"Activate unified incident command; coordinate joint {z1.hazard_type} and {z2.hazard_type} multi-hazard response.",
                        )
                    )

        return all_zones + compound_zones
