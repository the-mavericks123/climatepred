"""
Feature extraction pipeline for Climate Eye View S2 hazard intelligence.
Extracts model features from canonical NormalizedTelemetry preserving units, metadata, and coordinates.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from intelligence.core.contracts.telemetry import LocationCoordinate, NormalizedTelemetry


class HazardFeatures(BaseModel):
    """
    Standardized feature container passed to individual hazard models.
    Preserves exact observation units, raw values, and provenance metadata.
    """
    node_id: str
    timestamp: datetime
    location: LocationCoordinate
    source: str
    valid: bool
    confidence_base: float
    anomaly_score: float
    flags: List[str]

    # Raw physical measurements (preserves None if unobserved)
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    rainfall_mmhr: Optional[float] = None
    soil_moisture_pct: Optional[float] = None
    water_level_m: Optional[float] = None
    air_quality_aqi: Optional[float] = None

    # Raw telemetry provenance hash
    provenance_hash: Optional[str] = None

    def as_feature_dict(self) -> Dict[str, Any]:
        """Returns non-null physical features with explicit unit keys."""
        d: Dict[str, Any] = {}
        if self.temperature_c is not None:
            d["temperature_c"] = self.temperature_c
        if self.humidity_pct is not None:
            d["humidity_pct"] = self.humidity_pct
        if self.pressure_hpa is not None:
            d["pressure_hpa"] = self.pressure_hpa
        if self.rainfall_mmhr is not None:
            d["rainfall_mmhr"] = self.rainfall_mmhr
        if self.soil_moisture_pct is not None:
            d["soil_moisture_pct"] = self.soil_moisture_pct
        if self.water_level_m is not None:
            d["water_level_m"] = self.water_level_m
        if self.air_quality_aqi is not None:
            d["air_quality_aqi"] = self.air_quality_aqi
        return d


class FeatureExtractor:
    """Extracts HazardFeatures from canonical NormalizedTelemetry."""

    @staticmethod
    def extract(telemetry: NormalizedTelemetry, provenance_hash: Optional[str] = None) -> HazardFeatures:
        m = telemetry.measurements
        q = telemetry.quality

        return HazardFeatures(
            node_id=telemetry.node_id,
            timestamp=telemetry.timestamp,
            location=telemetry.location,
            source=q.source,
            valid=q.valid,
            confidence_base=q.confidence if q.confidence is not None else 1.0,
            anomaly_score=q.anomaly_score if q.anomaly_score is not None else 0.0,
            flags=list(q.flags),
            temperature_c=m.temperature,
            humidity_pct=m.humidity,
            pressure_hpa=m.pressure,
            rainfall_mmhr=m.rainfall,
            soil_moisture_pct=m.soil_moisture,
            water_level_m=m.water_level,
            air_quality_aqi=m.air_quality,
            provenance_hash=provenance_hash,
        )
