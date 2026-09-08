"""
USGS Realtime Global Earthquake Feed Provider.
Ingests authoritative USGS GeoJSON seismic feeds, assesses magnitude & depth,
and computes scientifically calibrated impact radii.
"""

from datetime import datetime, timezone
import json
import math
import time
import urllib.request
from typing import Any, Dict, List, Optional

from intelligence.core.logging import get_logger
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    GlobalDisasterEvent,
    GlobalHazardZone,
)

logger = get_logger("usgs_provider")


class UsgsEarthquakeProvider:
    PROVIDER_NAME = "USGS"
    ALL_DAY_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    ALL_HOUR_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

    def __init__(self, cache: Optional[ExternalDataCache] = None, timeout_sec: float = 10.0):
        self.cache = cache or ExternalDataCache()
        self.timeout_sec = timeout_sec
        self.cache_ttl_sec = 180.0  # 3 minutes

    def fetch_earthquakes(
        self,
        min_magnitude: float = 2.5,
        force_refresh: bool = False,
        limit: int = 200,
    ) -> List[GlobalDisasterEvent]:
        """
        Fetches authoritative recent seismic events from USGS.
        Filters by minimum magnitude to prevent flooding low-impact micro-tremors.
        """
        cache_key = f"usgs_quakes_min_{min_magnitude}"
        breaker = self.cache.get_breaker("usgs")

        if not force_refresh:
            cached, is_fresh = self.cache.get(cache_key)
            if cached is not None and is_fresh:
                return cached
            if not breaker.can_attempt() and cached is not None:
                return cached

        if not breaker.can_attempt():
            cached, _ = self.cache.get(cache_key)
            return cached or []

        events: List[GlobalDisasterEvent] = []
        try:
            req = urllib.request.Request(
                self.ALL_DAY_URL,
                headers={"User-Agent": "ClimateEyeView/2.0 (Seismic Event Monitoring)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status != 200:
                    raise IOError(f"USGS returned HTTP {resp.status}")
                data = json.loads(resp.read().decode("utf-8"))

            features = data.get("features", [])
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])

                if len(coords) < 2:
                    continue

                lon, lat = coords[0], coords[1]
                depth_km = coords[2] if len(coords) > 2 else 10.0
                mag = props.get("mag")
                if mag is None or mag < min_magnitude:
                    continue

                event_time_ms = props.get("time")
                event_dt = (
                    datetime.fromtimestamp(event_time_ms / 1000.0, tz=timezone.utc)
                    if event_time_ms
                    else datetime.now(timezone.utc)
                )

                # Scientific affected radius formula: R = 10^(0.5*M - 1.5) km
                # M=4.0 -> ~3 km; M=5.0 -> ~10 km; M=6.0 -> ~31 km; M=7.0 -> ~100 km
                calc_radius = max(5.0, 10.0 ** (0.5 * mag - 1.5))

                # Normalize severity between 0.0 and 1.0 based on Richter scale (2.5 -> 0.1, 7.5+ -> 0.95)
                norm_sev = min(1.0, max(0.1, (mag - 2.0) / 6.0))

                # Alert classification
                if mag >= 6.5:
                    alert_level = "RED"
                elif mag >= 5.0:
                    alert_level = "ORANGE"
                elif mag >= 3.5:
                    alert_level = "YELLOW"
                else:
                    alert_level = "GREEN"

                event_id = feat.get("id") or f"USGS-{int(event_dt.timestamp())}"
                title = props.get("title") or f"M {mag:.1f} Earthquake - {props.get('place', 'Global')}"

                events.append(
                    GlobalDisasterEvent(
                        event_id=event_id,
                        event_type="EARTHQUAKE",
                        title=title,
                        severity=round(norm_sev, 2),
                        alert_level=alert_level,
                        confidence=0.98,
                        location=ExternalLocation(
                            lat=round(lat, 4),
                            lon=round(lon, 4),
                            name=props.get("place"),
                        ),
                        affected_radius_km=round(calc_radius, 1),
                        source="USGS",
                        source_url=props.get("url"),
                        timestamp=event_dt,
                        metadata={
                            "magnitude": mag,
                            "depth_km": depth_km,
                            "cdi": props.get("cdi"),
                            "mmi": props.get("mmi"),
                            "tsunami": props.get("tsunami", 0),
                        },
                        simulated=False,
                    )
                )
                if len(events) >= limit:
                    break

            breaker.record_success()
            self.cache.set(cache_key, events, self.cache_ttl_sec)
            return events

        except Exception as exc:
            breaker.record_failure()
            logger.warning(f"USGS Earthquake fetch failed: {exc}")
            cached, _ = self.cache.get(cache_key)
            return cached or []

    def to_hazard_zones(self, events: List[GlobalDisasterEvent]) -> List[GlobalHazardZone]:
        """Converts qualifying significant earthquakes (M >= 4.0) into GlobalHazardZone models."""
        hazard_zones = []
        for ev in events:
            mag = ev.metadata.get("magnitude", 0.0)
            if mag < 4.0:
                continue

            zone_id = f"ZONE-QUAKE-{ev.event_id}"
            hazard_zones.append(
                GlobalHazardZone(
                    zone_id=zone_id,
                    hazard_type="EARTHQUAKE",
                    severity=ev.severity,
                    confidence=ev.confidence,
                    epistemic_status=EpistemicStatus.OBSERVED,
                    geometry={
                        "type": "Point",
                        "coordinates": [ev.location.lon, ev.location.lat],
                    },
                    center=ev.location,
                    radius_km=ev.affected_radius_km,
                    metrics={
                        "magnitude": mag,
                        "depth_km": ev.metadata.get("depth_km"),
                        "tsunami_alert": ev.metadata.get("tsunami") == 1,
                    },
                    drivers=[
                        f"USGS Seismic Network: M {mag:.1f} earthquake",
                        f"Focal depth: {ev.metadata.get('depth_km', 'unknown')} km",
                        f"Epicenter: {ev.location.name or 'Offshore/Remote'}",
                    ],
                    source="USGS",
                    timestamp=ev.timestamp,
                    simulated=False,
                    recommended_action="Inspect regional infrastructure, transport lines, and evaluate aftershock risk.",
                )
            )
        return hazard_zones
