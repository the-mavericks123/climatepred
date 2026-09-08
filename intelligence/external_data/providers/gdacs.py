"""
GDACS (Global Disaster Alert and Coordination System) Feed Provider.
Ingests international multi-hazard emergency alerts (Cyclones, Floods, Drought, Volcanoes, Earthquakes).
"""

from datetime import datetime, timezone
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from intelligence.core.logging import get_logger
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    GlobalDisasterEvent,
    GlobalHazardZone,
)

logger = get_logger("gdacs_provider")


class GdacsProvider:
    PROVIDER_NAME = "GDACS"
    FEED_URL = "https://www.gdacs.org/xml/rss.xml"

    # GDACS XML namespaces
    NAMESPACES = {
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "gdacs": "http://www.gdacs.org",
    }

    def __init__(self, cache: Optional[ExternalDataCache] = None, timeout_sec: float = 12.0):
        self.cache = cache or ExternalDataCache()
        self.timeout_sec = timeout_sec
        self.cache_ttl_sec = 600.0  # 10 minutes

    def fetch_disasters(self, force_refresh: bool = False, limit: int = 150) -> List[GlobalDisasterEvent]:
        """Fetches live multi-hazard alerts from GDACS."""
        cache_key = "gdacs_disasters"
        breaker = self.cache.get_breaker("gdacs")

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
                self.FEED_URL,
                headers={"User-Agent": "ClimateEyeView/2.0 (GDACS Multi-Hazard Ingestion)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status != 200:
                    raise IOError(f"GDACS returned HTTP {resp.status}")
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                return []

            items = channel.findall("item")
            for item in items:
                title = item.findtext("title") or "GDACS Alert"
                link = item.findtext("link") or "https://www.gdacs.org"
                pub_date_str = item.findtext("pubDate")

                lat_el = item.find("geo:lat", self.NAMESPACES)
                lon_el = item.find("geo:long", self.NAMESPACES)
                if lat_el is None or lon_el is None or not lat_el.text or not lon_el.text:
                    continue

                try:
                    lat = float(lat_el.text)
                    lon = float(lon_el.text)
                except ValueError:
                    continue

                event_type_raw = item.findtext("gdacs:eventtype", default="DISASTER", namespaces=self.NAMESPACES)
                alert_level = (item.findtext("gdacs:alertlevel", default="GREEN", namespaces=self.NAMESPACES) or "GREEN").upper()
                episode_id = item.findtext("gdacs:episodeid", default=None, namespaces=self.NAMESPACES)
                event_id_raw = item.findtext("gdacs:eventid", default=None, namespaces=self.NAMESPACES) or str(abs(hash(f"{lat}_{lon}_{title}")) % 100000)
                event_id = f"GDACS-{event_type_raw}-{event_id_raw}"

                # Severity mapping based on GDACS alertlevel
                if alert_level == "RED":
                    severity = 0.90
                    radius_km = 80.0
                elif alert_level == "ORANGE":
                    severity = 0.65
                    radius_km = 45.0
                else:
                    severity = 0.35
                    radius_km = 20.0

                event_dt = datetime.now(timezone.utc)
                if pub_date_str:
                    try:
                        # RFC 822 format (e.g. "Tue, 08 Sep 2026 06:00:00 GMT")
                        event_dt = datetime.strptime(pub_date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                # Map event types to canonical hazard types
                type_map = {
                    "TC": "CYCLONE",
                    "FL": "FLOOD",
                    "EQ": "EARTHQUAKE",
                    "DR": "DROUGHT",
                    "VO": "VOLCANO",
                    "WF": "WILDFIRE",
                }
                canonical_type = type_map.get(event_type_raw.upper(), event_type_raw.upper())

                events.append(
                    GlobalDisasterEvent(
                        event_id=event_id,
                        event_type=canonical_type,
                        title=title,
                        severity=severity,
                        alert_level=alert_level,
                        confidence=0.92,
                        location=ExternalLocation(lat=round(lat, 4), lon=round(lon, 4), name=title),
                        affected_radius_km=radius_km,
                        source="GDACS",
                        source_url=link,
                        timestamp=event_dt,
                        metadata={
                            "gdacs_event_type": event_type_raw,
                            "episode_id": episode_id,
                            "raw_alert_level": alert_level,
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
            logger.warning(f"GDACS alert fetch failed: {exc}")
            cached, _ = self.cache.get(cache_key)
            return cached or []

    def to_hazard_zones(self, events: List[GlobalDisasterEvent]) -> List[GlobalHazardZone]:
        """Converts GDACS alerts into GlobalHazardZone models."""
        zones = []
        for ev in events:
            # Map canonical type to hazard zone type
            hazard_type = ev.event_type
            zone_id = f"ZONE-GDACS-{ev.event_id}"
            action_map = {
                "CYCLONE": "Issue storm surge and wind damage warnings; activate emergency shelters.",
                "FLOOD": "Monitor river basins, prepare flood barriers and pre-position evacuation resources.",
                "DROUGHT": "Enforce water conservation quotas; evaluate agricultural stress.",
                "VOLCANO": "Establish exclusion perimeter; distribute particulate masks for ashfall.",
                "EARTHQUAKE": "Deploy urban search and rescue; survey critical lifelines.",
                "WILDFIRE": "Establish firebreaks; issue air quality warnings.",
            }
            action = action_map.get(hazard_type, "Maintain situational monitoring.")

            zones.append(
                GlobalHazardZone(
                    zone_id=zone_id,
                    hazard_type=hazard_type,
                    severity=ev.severity,
                    confidence=ev.confidence,
                    epistemic_status=EpistemicStatus.OBSERVED,
                    geometry={
                        "type": "Point",
                        "coordinates": [ev.location.lon, ev.location.lat],
                    },
                    center=ev.location,
                    radius_km=ev.affected_radius_km,
                    metrics={"alert_level": ev.alert_level, "source_feed": "GDACS_RSS"},
                    drivers=[
                        f"GDACS multi-hazard alert: {ev.alert_level} {ev.event_type}",
                        f"{ev.title}",
                    ],
                    source="GDACS",
                    timestamp=ev.timestamp,
                    simulated=False,
                    recommended_action=action,
                )
            )
        return zones
