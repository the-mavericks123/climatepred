"""
Data provenance tracking foundation for Climate Eye View S2.
Ensures every piece of normalized telemetry maintains verifiable origin and chain of custody.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from intelligence.core.contracts.telemetry import NormalizedTelemetry


class ProvenanceRecord(BaseModel):
    """Verifiable provenance record for an observation."""
    record_hash: str = Field(..., description="SHA-256 fingerprint of the normalized packet")
    source: str = Field(..., description="Origin source system identifier")
    source_type: str = Field(..., description="Type of source (e.g. IOT_STATION, SATELLITE, SYNTHETIC)")
    node_id: str = Field(..., description="Identifier of the node within the source system")
    observed_at: datetime = Field(..., description="Time of physical observation")
    received_at: datetime = Field(..., description="Time packet was ingested at S2 boundary")
    schema_version: str = Field(..., description="Schema version of ingested data")
    quality_valid: bool = Field(..., description="Initial quality gate result")
    ingestion_agent: str = Field(default="S2_INGESTION_ADAPTER_V1", description="Ingestion pipeline handler")


class ProvenanceTracker:
    """Manages creation and verification of telemetry provenance fingerprints."""

    @staticmethod
    def compute_record_hash(telemetry: NormalizedTelemetry) -> str:
        """Computes deterministic SHA-256 fingerprint of normalized telemetry."""
        canonical_dict = {
            "schema_version": telemetry.schema_version,
            "node_id": telemetry.node_id,
            "timestamp": telemetry.timestamp.isoformat(),
            "location": {
                "lat": round(telemetry.location.lat, 6),
                "lon": round(telemetry.location.lon, 6),
            },
            "measurements": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in sorted(telemetry.measurements.model_dump().items())
            },
            "source": telemetry.quality.source,
        }
        serialized = json.dumps(canonical_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def generate_record(cls, telemetry: NormalizedTelemetry, source_type: str = "IOT_STATION") -> ProvenanceRecord:
        """Generates an immutable ProvenanceRecord for the given telemetry packet."""
        record_hash = cls.compute_record_hash(telemetry)
        return ProvenanceRecord(
            record_hash=record_hash,
            source=telemetry.quality.source,
            source_type=source_type,
            node_id=telemetry.node_id,
            observed_at=telemetry.timestamp,
            received_at=telemetry.quality.received_at,
            schema_version=telemetry.schema_version,
            quality_valid=telemetry.quality.valid,
        )

    @classmethod
    def verify_fingerprint(cls, telemetry: NormalizedTelemetry, expected_hash: str) -> bool:
        """Verifies if the telemetry contents match the expected fingerprint."""
        return cls.compute_record_hash(telemetry) == expected_hash
