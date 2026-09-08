"""
Canonical Data Contracts and Types for External Data Ingestion & Fusion.
Strictly adheres to Epistemic Separation and physical invariants.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EpistemicStatus(str, Enum):
    """Rigorous epistemic categorization of all operational data."""
    OBSERVED = "OBSERVED"      # Direct physical or satellite observation
    PREDICTED = "PREDICTED"    # Statistical, numerical, or physical forecast
    INFERRED = "INFERRED"      # Derived via deterministic model logic
    SIMULATED = "SIMULATED"    # Synthetic digital twin scenario runs
    STALE = "STALE"            # Valid observation whose freshness window elapsed
    UNAVAILABLE = "UNAVAILABLE" # Metric cannot be measured or source offline


class SourceType(str, Enum):
    WEATHER_API = "WEATHER_API"
    SATELLITE_HOTSPOT = "SATELLITE_HOTSPOT"
    SEISMIC_FEED = "SEISMIC_FEED"
    DISASTER_ALERT = "DISASTER_ALERT"
    HYDROLOGICAL = "HYDROLOGICAL"
    PHYSICAL_MESH = "PHYSICAL_MESH"


class ExternalLocation(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    elevation_m: Optional[float] = Field(default=None, description="Elevation in meters")
    name: Optional[str] = Field(default=None, description="Station or region name")


class ExternalMeasurements(BaseModel):
    """
    Normalized physical meteorological and environmental measurements.
    Physical invariant: water_level is strictly None (null) for weather-only feeds.
    Never coerce missing sensors or water_level to 0.0!
    """
    temperature: Optional[float] = Field(default=None, ge=-60.0, le=65.0, description="Temperature in °C")
    apparent_temperature: Optional[float] = Field(default=None, ge=-60.0, le=75.0, description="Apparent / heat index in °C")
    humidity: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Relative humidity in %")
    pressure: Optional[float] = Field(default=None, ge=800.0, le=1100.0, description="Surface pressure in hPa")
    precipitation: Optional[float] = Field(default=None, ge=0.0, le=500.0, description="Current precipitation rate in mm/h")
    wind_speed: Optional[float] = Field(default=None, ge=0.0, le=150.0, description="Wind speed in m/s")
    wind_direction: Optional[float] = Field(default=None, ge=0.0, le=360.0, description="Wind direction in degrees")
    soil_moisture: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Soil moisture in %")
    air_quality: Optional[float] = Field(default=None, ge=0.0, le=500.0, description="Air quality AQI")
    water_level: Optional[float] = Field(default=None, ge=0.0, le=50.0, description="Water level in meters (None for weather-only)")


class ObservationQuality(BaseModel):
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Quality confidence score")
    status: str = Field(default="VALID", description="Validation status (VALID, DEGRADED, SUSPECT)")
    flags: List[str] = Field(default_factory=list, description="Quality anomaly flags")


class ObservationProvenance(BaseModel):
    provider: str = Field(..., description="Authoritative data provider name")
    source_url: str = Field(..., description="API endpoint or feed URI")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time when data was fetched by S2",
    )
    source_timestamp: Optional[datetime] = Field(default=None, description="Original observation time claimed by provider")
    version: Optional[str] = Field(default=None, description="Feed or model version")
    record_hash: Optional[str] = Field(default=None, description="SHA-256 cryptographic provenance hash")


class ExternalObservation(BaseModel):
    """
    Canonical External Observation Contract.
    Conforms to project requirements.
    """
    observation_id: str = Field(..., description="Unique observation ID (OBS-...)")
    source: str = Field(..., description="Origin source identifier (e.g. open_meteo, nasa_firms)")
    source_type: SourceType = Field(..., description="Classification of the data source")
    timestamp: datetime = Field(..., description="Observation capture UTC timestamp")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Ingestion UTC timestamp",
    )
    location: ExternalLocation = Field(..., description="WGS84 geographic location")
    measurements: ExternalMeasurements = Field(..., description="Normalized sensor readings")
    quality: ObservationQuality = Field(default_factory=ObservationQuality, description="Validation metrics")
    epistemic_status: EpistemicStatus = Field(default=EpistemicStatus.OBSERVED, description="Epistemic classification")
    simulated: bool = Field(default=False, description="Strictly false for live data")
    provenance: ObservationProvenance = Field(..., description="Full origin provenance tracking")

    @field_validator("simulated")
    @classmethod
    def validate_not_simulated(cls, v: bool) -> bool:
        return v


class GlobalHazardZone(BaseModel):
    """
    Geographic hazard zone representation for 3D Globe visualization & Intelligence.
    """
    zone_id: str = Field(..., description="Unique hazard zone identifier")
    hazard_type: str = Field(..., description="HEAT, FLOOD, WILDFIRE, EARTHQUAKE, DROUGHT, CYCLONE, COMPOUND")
    severity: float = Field(..., ge=0.0, le=1.0, description="Normalized severity (0.0 to 1.0)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model or detection confidence (0.0 to 1.0)")
    epistemic_status: EpistemicStatus = Field(..., description="OBSERVED, INFERRED, PREDICTED, or SIMULATED")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry or bounding footprint")
    center: ExternalLocation = Field(..., description="Center coordinate of the hazard")
    radius_km: float = Field(default=10.0, ge=0.1, description="Approximate hazard impact radius in kilometers")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Underlying physical metrics")
    drivers: List[str] = Field(default_factory=list, description="Primary causal drivers")
    source: str = Field(..., description="Authoritative origin source(s)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(default=None)
    simulated: bool = Field(default=False, description="Strictly false for real hazard zones")
    affected_population: Optional[int] = Field(default=None, description="Estimated exposed population")
    vulnerability_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Social vulnerability index")
    recommended_action: Optional[str] = Field(default=None, description="Recommended response directive")


class GlobalDisasterEvent(BaseModel):
    """
    Authoritative point event from USGS, GDACS, or FIRMS.
    """
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="EARTHQUAKE, CYCLONE, FLOOD, WILDFIRE, VOLCANO, DROUGHT")
    title: str = Field(..., description="Human-readable event summary")
    severity: float = Field(..., ge=0.0, le=1.0, description="Normalized severity (0.0 to 1.0)")
    alert_level: str = Field(default="GREEN", description="GREEN, YELLOW, ORANGE, RED")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    location: ExternalLocation = Field(...)
    affected_radius_km: float = Field(default=10.0)
    source: str = Field(...)
    source_url: Optional[str] = Field(default=None)
    timestamp: datetime = Field(...)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    simulated: bool = Field(default=False)


class DataSourceStatus(BaseModel):
    """
    Health and freshness status for an external provider or physical mesh.
    """
    source_id: str = Field(..., description="Unique identifier (e.g. open_meteo, nasa_firms, esp32)")
    name: str = Field(..., description="Human-readable name")
    status: str = Field(..., description="ONLINE, STALE, UNAVAILABLE, NOT_CONNECTED")
    last_update: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    record_count: int = Field(default=0)
    is_physical_sensor: bool = Field(default=False)
    endpoint: Optional[str] = Field(default=None)
