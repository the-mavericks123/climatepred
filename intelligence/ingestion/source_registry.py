"""
Source Registry for Climate Eye View S2 Intelligence Ingestion.
Maintains metadata, availability status, quality scoring, and configuration for telemetry sources.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    ESP32 = "ESP32"
    WEATHER_API = "WEATHER_API"
    SATELLITE = "SATELLITE"
    GIS = "GIS"
    HISTORICAL = "HISTORICAL"
    SIMULATION = "SIMULATION"


class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    REGISTERED = "REGISTERED"


class SourceMetadata(BaseModel):
    """Registration metadata for an intelligence ingestion source."""
    source_id: str = Field(..., min_length=1, description="Unique source identifier")
    source_type: SourceType = Field(..., description="Classification of telemetry provider")
    display_name: str = Field(..., description="Human readable name")
    description: Optional[str] = Field(default=None, description="Detailed source purpose")
    status: SourceStatus = Field(default=SourceStatus.REGISTERED, description="Current operational state")
    base_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Baseline confidence multiplier")
    last_heartbeat: Optional[datetime] = Field(default=None, description="Last recorded ingestion heartbeat")
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Registration timestamp",
    )
    metadata: Dict[str, str] = Field(default_factory=dict, description="Arbitrary provider configuration")


class SourceRegistry:
    """Registry maintaining active and registered telemetry sources."""

    def __init__(self) -> None:
        self._sources: Dict[str, SourceMetadata] = {}
        self._initialize_canonical_defaults()

    def _initialize_canonical_defaults(self) -> None:
        """Seeds canonical source archetypes."""
        defaults = [
            SourceMetadata(
                source_id="ESP32_DEFAULT",
                source_type=SourceType.ESP32,
                display_name="Edge IoT Flood & Weather Microstation",
                description="Ground-level ESP32 sensor array measuring water level, rainfall, temp, and soil moisture",
                status=SourceStatus.ACTIVE,
                base_confidence=0.95,
            ),
            SourceMetadata(
                source_id="WEATHER_API_DEFAULT",
                source_type=SourceType.WEATHER_API,
                display_name="Open-Meteo Synoptic Feed",
                description="Global numerical weather prediction and synoptic observations",
                status=SourceStatus.ACTIVE,
                base_confidence=0.90,
            ),
            SourceMetadata(
                source_id="SATELLITE_VIIRS_DEFAULT",
                source_type=SourceType.SATELLITE,
                display_name="NASA FIRMS / VIIRS NRT",
                description="Near-real-time thermal anomaly and fire detection satellite observations",
                status=SourceStatus.ACTIVE,
                base_confidence=0.92,
            ),
            SourceMetadata(
                source_id="GIS_BASE_DEFAULT",
                source_type=SourceType.GIS,
                display_name="Hydrographic Infrastructure GIS",
                description="Dams, drainage basins, elevation profiles, and flood defenses",
                status=SourceStatus.ACTIVE,
                base_confidence=0.98,
            ),
            SourceMetadata(
                source_id="HISTORICAL_ARCHIVE",
                source_type=SourceType.HISTORICAL,
                display_name="Historical Flood & Heat Wave Archive",
                description="Calibrated historical disaster events for benchmark validation",
                status=SourceStatus.ACTIVE,
                base_confidence=0.99,
            ),
            SourceMetadata(
                source_id="SIMULATION_ENGINE",
                source_type=SourceType.SIMULATION,
                display_name="Digital Twin Synthetic Stress Generator",
                description="Counterfactual and forward-looking disaster perturbation generator",
                status=SourceStatus.ACTIVE,
                base_confidence=1.0,
            ),
        ]
        for src in defaults:
            self._sources[src.source_id] = src

    def register(self, source: SourceMetadata) -> SourceMetadata:
        """Register or update a source metadata record."""
        self._sources[source.source_id] = source
        return source

    def get(self, source_id: str) -> Optional[SourceMetadata]:
        """Retrieve source metadata by ID."""
        return self._sources.get(source_id)

    def list_all(self) -> List[SourceMetadata]:
        """List all registered sources."""
        return list(self._sources.values())

    def update_heartbeat(self, source_id: str) -> bool:
        """Updates last seen timestamp for a source."""
        source = self._sources.get(source_id)
        if source:
            source.last_heartbeat = datetime.now(timezone.utc)
            if source.status == SourceStatus.REGISTERED:
                source.status = SourceStatus.ACTIVE
            return True
        return False

    def is_source_available(self, source_id: str) -> bool:
        """Returns True if the source is known and not marked UNAVAILABLE."""
        source = self._sources.get(source_id)
        if not source:
            return False
        return source.status != SourceStatus.UNAVAILABLE
