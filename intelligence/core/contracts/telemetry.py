"""
Canonical Telemetry Data Contract for Climate Eye View S2.
Defines normalized sensor telemetry schemas and field conventions.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class LocationCoordinate(BaseModel):
    """Geographic location in WGS84 coordinates."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude in decimal degrees")
    elevation: Optional[float] = Field(default=None, description="Meters above WGS84 reference ellipsoid")


class SensorMeasurements(BaseModel):
    """
    Physical sensor measurements.
    Missing sensors MUST be None, never silently coerced to 0.0.
    
    Documented Field Conventions:
      - temperature: °C (valid range: -50.0 to +65.0 °C)
      - humidity: % (valid range: 0.0 to 100.0 %)
      - pressure: hPa (valid range: 800.0 to 1100.0 hPa)
      - rainfall: mm/hr (valid range: 0.0 to 500.0 mm/hr intensity rate)
      - soil_moisture: % (valid range: 0.0 to 100.0 %)
      - water_level: meters (m) relative to sensor mounting baseline / riverbed datum (0.0 to 50.0 m)
      - air_quality: AQI scale (0.0 to 500.0)
      - light_intensity: lux (0.0 to 120000.0 lx from BH1750)
      - battery: % (0.0 to 100.0 %)
      - sensor_status: per-sensor calibration/operational status mapping
    """
    temperature: Optional[float] = Field(default=None, ge=-50.0, le=65.0, description="Ambient temperature in °C")
    humidity: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Relative humidity in %")
    pressure: Optional[float] = Field(default=None, ge=800.0, le=1100.0, description="Atmospheric pressure in hPa")
    rainfall: Optional[float] = Field(default=None, ge=0.0, le=500.0, description="Rainfall intensity rate in mm/hr")
    soil_moisture: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Volumetric soil moisture in %")
    water_level: Optional[float] = Field(default=None, ge=0.0, le=50.0, description="Water level in meters above sensor baseline")
    air_quality: Optional[float] = Field(default=None, ge=0.0, le=500.0, description="Air quality index (AQI 0-500)")
    light_intensity: Optional[float] = Field(default=None, ge=0.0, le=120000.0, description="Ambient light intensity in lux (BH1750)")
    battery: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Node battery percentage (0-100%)")
    sensor_status: Optional[Dict[str, str]] = Field(default=None, description="Per-sensor operational and calibration status dictionary")


class QualityMetadata(BaseModel):
    """Data quality and provenance metadata."""
    valid: bool = Field(default=True, description="Whether the packet passed quality gates")
    source: str = Field(..., min_length=1, description="Originating source type (e.g. ESP32, WEATHER_API)")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the packet reached the S2 boundary",
    )
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Quality confidence score (0.0 to 1.0)")
    anomaly_score: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Detected sensor anomaly score")
    flags: List[str] = Field(default_factory=list, description="Quality inspection flags")


class NormalizedTelemetry(BaseModel):
    """
    Canonical internal data contract for Climate Eye View S2.
    Every external source (ESP32, weather API, GIS, simulation) normalizes to this schema.
    """
    schema_version: str = Field(default="1.0", description="Contract schema version")
    node_id: str = Field(..., min_length=1, description="Unique telemetry node or station identifier")
    timestamp: datetime = Field(..., description="Observation capture UTC timestamp (ISO-8601)")
    location: LocationCoordinate = Field(..., description="Observation WGS84 location")
    measurements: SensorMeasurements = Field(..., description="Physical sensor measurements")
    quality: QualityMetadata = Field(..., description="Quality and provenance metadata")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError(f"Unsupported schema_version: '{v}'. Expected '1.0'")
        return v

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("node_id cannot be empty or whitespace only")
        return trimmed

    @model_validator(mode="after")
    def validate_temporal_ordering(self) -> "NormalizedTelemetry":
        # Check that timestamp is not in the distant future (> 5 minutes ahead of received_at)
        time_diff = (self.timestamp - self.quality.received_at).total_seconds()
        if time_diff > 300:
            raise ValueError(f"Observation timestamp {self.timestamp} is more than 300s ahead of received_at")
        return self
