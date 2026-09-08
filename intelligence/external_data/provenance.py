"""
Cryptographic Provenance and Audit Trail for External Data Feeds.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict
from intelligence.external_data.types import ObservationProvenance


class ExternalProvenanceTracker:
    """Computes deterministic cryptographic hashes for ingested external data."""

    @staticmethod
    def compute_record_hash(
        provider: str,
        source_url: str,
        timestamp_iso: str,
        lat: float,
        lon: float,
        measurements: Dict[str, Any],
    ) -> str:
        payload = {
            "provider": provider,
            "source_url": source_url,
            "timestamp": timestamp_iso,
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "measurements": {k: v for k, v in sorted(measurements.items()) if v is not None},
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def create_provenance(
        provider: str,
        source_url: str,
        retrieved_at: datetime,
        source_timestamp: datetime,
        lat: float,
        lon: float,
        measurements: Dict[str, Any],
        version: str = "1.0",
    ) -> ObservationProvenance:
        record_hash = ExternalProvenanceTracker.compute_record_hash(
            provider=provider,
            source_url=source_url,
            timestamp_iso=source_timestamp.isoformat(),
            lat=lat,
            lon=lon,
            measurements=measurements,
        )
        return ObservationProvenance(
            provider=provider,
            source_url=source_url,
            retrieved_at=retrieved_at,
            source_timestamp=source_timestamp,
            version=version,
            record_hash=record_hash,
        )
