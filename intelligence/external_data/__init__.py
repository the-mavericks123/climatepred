"""
Climate Eye View — External Data Ingestion and Multi-Source Fusion Layer.
Connects authoritative global meteorological, fire, seismic, and hydrological feeds
to the deterministic S2 intelligence pipeline.
"""

from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalObservation,
    ExternalMeasurements,
    GlobalHazardZone,
    GlobalDisasterEvent,
    DataSourceStatus,
)
from intelligence.external_data.service import ExternalDataService, get_external_data_service

__all__ = [
    "EpistemicStatus",
    "ExternalObservation",
    "ExternalMeasurements",
    "GlobalHazardZone",
    "GlobalDisasterEvent",
    "DataSourceStatus",
    "ExternalDataService",
    "get_external_data_service",
]
