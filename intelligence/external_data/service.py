"""
Climate Eye View — External Data Service.
Master orchestrator for multi-source global data ingestion, validation,
fusion with deterministic intelligence engines, caching, persistence, and realtime broadcasts.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from intelligence.core.logging import get_logger
from intelligence.core.realtime.broadcaster import realtime_broadcaster
from intelligence.database.repository import get_repository
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.fusion.hazard_fusion import GlobalHazardFusionEngine
from intelligence.external_data.fusion.spatial_fusion import GlobalSpatialGrid
from intelligence.external_data.fusion.weather_fusion import WeatherFusionEngine
from intelligence.external_data.providers.gdacs import GdacsProvider
from intelligence.external_data.providers.glofas import GlofasProvider
from intelligence.external_data.providers.nasa_firms import NasaFirmsProvider
from intelligence.external_data.providers.open_meteo import OpenMeteoProvider
from intelligence.external_data.providers.usgs import UsgsEarthquakeProvider
from intelligence.external_data.registry import ExternalSourceRegistry
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    ExternalObservation,
    GlobalDisasterEvent,
    GlobalHazardZone,
)

logger = get_logger("external_data_service")

_service_instance: Optional["ExternalDataService"] = None
_service_lock = threading.Lock()


class ExternalDataService:
    """
    Unified global live data service powering Climate Eye View.
    """

    def __init__(self):
        self.cache = ExternalDataCache()
        self.registry = ExternalSourceRegistry()
        self.open_meteo = OpenMeteoProvider(cache=self.cache)
        self.nasa_firms = NasaFirmsProvider(cache=self.cache)
        self.usgs = UsgsEarthquakeProvider(cache=self.cache)
        self.gdacs = GdacsProvider(cache=self.cache)
        self.glofas = GlofasProvider(cache=self.cache)
        self.hazard_fusion = GlobalHazardFusionEngine()

        self._observations: List[ExternalObservation] = []
        self._hazard_zones: List[GlobalHazardZone] = []
        self._disaster_events: List[GlobalDisasterEvent] = []
        self._predictions: List[Dict[str, Any]] = []
        self._compound_events: List[Any] = []
        self._lock = threading.Lock()

    def sync_all_feeds(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Ingests all live external feeds, evaluates deterministic models,
        persists to database, and broadcasts updates via WebSockets.
        """
        logger.info("Executing global external data synchronization...")
        repo = get_repository()
        now_utc = datetime.now(timezone.utc)

        # 1. Open-Meteo Global Weather Grid (36 stations)
        obs_list: List[ExternalObservation] = []
        ref_stations = GlobalSpatialGrid.get_reference_stations()
        for stn in ref_stations:
            try:
                obs = self.open_meteo.fetch_point_weather(
                    lat=stn["lat"],
                    lon=stn["lon"],
                    station_name=stn["name"],
                    force_refresh=force_refresh,
                )
                if obs:
                    obs_list.append(obs)
            except Exception as e:
                logger.debug(f"Open-Meteo station {stn['name']} note: {e}")

        if obs_list:
            self.registry.update_source_status(
                "open_meteo", "ONLINE", record_count=len(obs_list)
            )
        else:
            self.registry.update_source_status(
                "open_meteo", "STALE", record_count=0, error_message="No stations responded"
            )

        # 2. NASA FIRMS Active Fires
        fire_points = self.nasa_firms.fetch_active_fires(force_refresh=force_refresh)
        fire_zones = self.nasa_firms.cluster_fires(fire_points)
        if fire_points:
            self.registry.update_source_status(
                "nasa_firms", "ONLINE", record_count=len(fire_points)
            )
        else:
            self.registry.update_source_status(
                "nasa_firms", "ONLINE", record_count=0
            )

        # 3. USGS Earthquakes
        quake_events = self.usgs.fetch_earthquakes(min_magnitude=2.5, force_refresh=force_refresh)
        quake_zones = self.usgs.to_hazard_zones(quake_events)
        if quake_events:
            self.registry.update_source_status(
                "usgs", "ONLINE", record_count=len(quake_events)
            )
        else:
            self.registry.update_source_status(
                "usgs", "ONLINE", record_count=0
            )

        # 4. GDACS Multi-Hazard Alerts
        gdacs_events = self.gdacs.fetch_disasters(force_refresh=force_refresh)
        gdacs_zones = self.gdacs.to_hazard_zones(gdacs_events)
        if gdacs_events:
            self.registry.update_source_status(
                "gdacs", "ONLINE", record_count=len(gdacs_events)
            )
        else:
            self.registry.update_source_status(
                "gdacs", "ONLINE", record_count=0
            )

        # 5. GloFAS Status
        glofas_status = self.glofas.get_status()
        self.registry.update_source_status(
            "glofas",
            glofas_status.status,
            record_count=glofas_status.record_count,
            error_message=glofas_status.error_message,
        )

        # 6. Run Deterministic Intelligence Pipeline on External Weather Observations
        weather_zones, predictions, compound_events = self.hazard_fusion.evaluate_weather_hazards(obs_list)

        # 7. Multi-Hazard Spatial Fusion & Compound Detection
        all_hazards = self.hazard_fusion.fuse_all_global_hazards(
            weather_zones=weather_zones,
            fire_zones=fire_zones,
            quake_zones=quake_zones,
            disaster_zones=gdacs_zones,
        )

        # Aggregate all point disaster events
        all_events = list(quake_events) + list(gdacs_events)

        with self._lock:
            self._observations = obs_list
            self._hazard_zones = all_hazards
            self._disaster_events = all_events
            self._predictions = predictions
            self._compound_events = compound_events

        # 8. Persist to Database Repository
        try:
            for obs in obs_list:
                repo.save_external_observation(
                    obs_id=obs.observation_id,
                    source=obs.source,
                    station_id=obs.location.name or obs.observation_id,
                    lat=obs.location.lat,
                    lon=obs.location.lon,
                    measurements=obs.measurements.model_dump(),
                    quality_score=obs.quality.score,
                    timestamp=obs.timestamp.isoformat(),
                    received_at=obs.received_at.isoformat(),
                )
            for z in all_hazards:
                repo.save_global_hazard(
                    zone_id=z.zone_id,
                    hazard_type=z.hazard_type,
                    severity=z.severity,
                    confidence=z.confidence,
                    geometry=z.geometry,
                    center={"lat": z.center.lat, "lon": z.center.lon},
                    radius_km=z.radius_km,
                    drivers=z.drivers,
                    timestamp=z.timestamp.isoformat(),
                )
            for ev in all_events:
                repo.save_external_event(
                    event_id=ev.event_id,
                    event_type=ev.event_type,
                    title=ev.title,
                    severity=ev.severity,
                    alert_level=ev.alert_level,
                    lat=ev.location.lat,
                    lon=ev.location.lon,
                    source=ev.source,
                    timestamp=ev.timestamp.isoformat(),
                )
        except Exception as persist_err:
            logger.debug(f"Global persistence note: {persist_err}")

        # 9. Broadcast Realtime S1 Events via WebSockets
        try:
            realtime_broadcaster.broadcast_sync(
                "global.sources.updated",
                self.registry.get_system_summary(),
            )
            realtime_broadcaster.broadcast_sync(
                "global.hazard.updated",
                {
                    "hazard_count": len(all_hazards),
                    "hazards": [z.model_dump() for z in all_hazards[:50]],
                    "timestamp": now_utc.isoformat(),
                },
            )
            if quake_events:
                top_q = quake_events[0]
                realtime_broadcaster.broadcast_sync(
                    "global.earthquake.detected",
                    top_q.model_dump(),
                )
            if fire_zones:
                top_f = fire_zones[0]
                realtime_broadcaster.broadcast_sync(
                    "global.fire.detected",
                    top_f.model_dump(),
                )
        except Exception as bc_err:
            logger.debug(f"Global broadcast note: {bc_err}")

        logger.info(
            f"Global sync complete: {len(obs_list)} weather stations, {len(fire_zones)} fire zones, "
            f"{len(quake_events)} earthquakes, {len(gdacs_events)} GDACS alerts, {len(all_hazards)} total hazard zones."
        )

        return {
            "success": True,
            "observations_count": len(obs_list),
            "hazard_zones_count": len(all_hazards),
            "disaster_events_count": len(all_events),
            "timestamp": now_utc.isoformat(),
        }

    # Query APIs
    def get_observations(self) -> List[ExternalObservation]:
        with self._lock:
            return list(self._observations)

    def get_hazard_zones(self, hazard_type: Optional[str] = None) -> List[GlobalHazardZone]:
        with self._lock:
            if not hazard_type:
                return list(self._hazard_zones)
            h_upper = hazard_type.upper()
            return [z for z in self._hazard_zones if z.hazard_type == h_upper]

    def get_disaster_events(self, event_type: Optional[str] = None) -> List[GlobalDisasterEvent]:
        with self._lock:
            if not event_type:
                return list(self._disaster_events)
            e_upper = event_type.upper()
            return [e for e in self._disaster_events if e.event_type == e_upper]

    def get_sources_status(self) -> Dict[str, Any]:
        return self.registry.get_system_summary()

    def get_ai_summary(self) -> Dict[str, Any]:
        """
        Returns structured grounded evidence for AI Command Center.
        Strictly deterministic — ZERO hallucinated metrics!
        """
        with self._lock:
            hazards = list(self._hazard_zones)
            events = list(self._disaster_events)

        active_count = len(hazards)
        high_risk = [h for h in hazards if h.severity >= 0.70]
        compound = [h for h in hazards if h.hazard_type == "COMPOUND"]

        top_event = None
        if high_risk:
            top_h = sorted(high_risk, key=lambda x: x.severity, reverse=True)[0]
            top_event = {
                "title": f"{top_h.center.name or 'Global Region'}: {top_h.hazard_type}",
                "hazard": top_h.hazard_type,
                "severity": top_h.severity,
                "confidence": top_h.confidence,
                "observed_at": top_h.timestamp.isoformat(),
                "location": {"lat": top_h.center.lat, "lon": top_h.center.lon},
                "drivers": top_h.drivers,
                "recommended_action": top_h.recommended_action or "Maintain heightened surveillance.",
                "sources": [top_h.source],
            }
        elif hazards:
            top_h = sorted(hazards, key=lambda x: x.severity, reverse=True)[0]
            top_event = {
                "title": f"{top_h.center.name or 'Global Region'}: {top_h.hazard_type}",
                "hazard": top_h.hazard_type,
                "severity": top_h.severity,
                "confidence": top_h.confidence,
                "observed_at": top_h.timestamp.isoformat(),
                "location": {"lat": top_h.center.lat, "lon": top_h.center.lon},
                "drivers": top_h.drivers,
                "recommended_action": top_h.recommended_action or "Nominal conditions.",
                "sources": [top_h.source],
            }

        return {
            "mode": "ACTIVE — DETERMINISTIC EVIDENCE MODE",
            "active_events_count": active_count,
            "high_risk_zones_count": len(high_risk),
            "compound_events_count": len(compound),
            "top_event": top_event,
            "provenance": {
                "sources": ["Open-Meteo", "NASA FIRMS", "USGS", "GDACS"],
                "epistemic_status": "OBSERVED / INFERRED",
                "simulated": False,
            },
        }


def get_external_data_service() -> ExternalDataService:
    """Returns singleton ExternalDataService instance."""
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            _service_instance = ExternalDataService()
        return _service_instance
