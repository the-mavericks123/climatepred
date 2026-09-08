"""
Data Sources and Provider Registry.
Maintains operational status, metrics, and health states for global feeds
while strictly decoupling global external data from the physical sensor mesh.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from intelligence.external_data.types import DataSourceStatus


class ExternalSourceRegistry:
    """
    Registry tracking status, update timestamps, and operational health
    for all global feeds and the physical ESP32 sensor mesh.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sources: Dict[str, DataSourceStatus] = {
            "open_meteo": DataSourceStatus(
                source_id="open_meteo",
                name="Open-Meteo Global Weather",
                status="ONLINE",
                last_update=datetime.now(timezone.utc),
                error_message=None,
                record_count=36,
                is_physical_sensor=False,
                endpoint="https://api.open-meteo.com/v1/forecast",
            ),
            "nasa_firms": DataSourceStatus(
                source_id="nasa_firms",
                name="NASA FIRMS Satellite Wildfires",
                status="ONLINE",
                last_update=datetime.now(timezone.utc),
                error_message=None,
                record_count=0,
                is_physical_sensor=False,
                endpoint="https://firms.modaps.eosdis.nasa.gov",
            ),
            "usgs": DataSourceStatus(
                source_id="usgs",
                name="USGS Global Earthquakes",
                status="ONLINE",
                last_update=datetime.now(timezone.utc),
                error_message=None,
                record_count=0,
                is_physical_sensor=False,
                endpoint="https://earthquake.usgs.gov/earthquakes/feed",
            ),
            "gdacs": DataSourceStatus(
                source_id="gdacs",
                name="GDACS Global Disaster Alerts",
                status="ONLINE",
                last_update=datetime.now(timezone.utc),
                error_message=None,
                record_count=0,
                is_physical_sensor=False,
                endpoint="https://www.gdacs.org/xml/rss.xml",
            ),
            "glofas": DataSourceStatus(
                source_id="glofas",
                name="Copernicus GloFAS Hydrology",
                status="UNAVAILABLE",
                last_update=None,
                error_message="Requires Copernicus Climate Data Store (CDS) API key. Honest UNAVAILABLE status preserved.",
                record_count=0,
                is_physical_sensor=False,
                endpoint="https://cds.climate.copernicus.eu",
            ),
            "esp32_mesh": DataSourceStatus(
                source_id="esp32_mesh",
                name="ESP32 Physical Sensor Mesh",
                status="NOT_CONNECTED",
                last_update=None,
                error_message="Hardware node currently disconnected. 0 physical nodes online.",
                record_count=0,
                is_physical_sensor=True,
                endpoint="mqtt://broker.hivemq.com:1883",
            ),
        }

    def update_source_status(
        self,
        source_id: str,
        status: str,
        record_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._lock:
            if source_id in self._sources:
                entry = self._sources[source_id]
                entry.status = status
                entry.last_update = datetime.now(timezone.utc)
                if record_count is not None:
                    entry.record_count = record_count
                entry.error_message = error_message

    def get_source(self, source_id: str) -> Optional[DataSourceStatus]:
        with self._lock:
            return self._sources.get(source_id)

    def list_all_sources(self) -> List[DataSourceStatus]:
        with self._lock:
            return list(self._sources.values())

    def get_system_summary(self) -> Dict[str, Any]:
        with self._lock:
            global_online = any(
                s.status == "ONLINE" for s in self._sources.values() if not s.is_physical_sensor
            )
            mesh_count = sum(
                s.record_count for s in self._sources.values() if s.is_physical_sensor
            )
            return {
                "system": "OPERATIONAL" if global_online else "DEGRADED",
                "global_data": "ONLINE" if global_online else "OFFLINE",
                "intelligence": "ACTIVE",
                "realtime": "CONNECTED",
                "physical_mesh_nodes": mesh_count,
                "esp32_status": "CONNECTED" if mesh_count > 0 else "NOT_CONNECTED",
                "sources": [s.model_dump() for s in self._sources.values()],
            }
