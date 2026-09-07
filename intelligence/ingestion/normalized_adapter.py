"""
Normalized Ingestion Adapter for Climate Eye View S2.
Transforms and normalizes incoming telemetry packets into Canonical NormalizedTelemetry format.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from intelligence.core.contracts.telemetry import (
    LocationCoordinate,
    NormalizedTelemetry,
    QualityMetadata,
    SensorMeasurements,
)
from intelligence.core.errors.exceptions import ValidationException
from intelligence.core.validation.validator import TelemetryValidator
from intelligence.ingestion.source_registry import SourceRegistry


class NormalizedAdapter:
    """Ingestion adapter normalizing raw payload maps into canonical telemetry."""

    def __init__(self, registry: Optional[SourceRegistry] = None) -> None:
        self.registry = registry or SourceRegistry()

    def adapt(self, raw_data: Dict[str, Any]) -> NormalizedTelemetry:
        """
        Parses, validates, and normalizes an incoming dictionary into NormalizedTelemetry.
        Raises ValidationException on failure.
        """
        # Ensure quality received_at is stamped if missing
        if "quality" in raw_data and isinstance(raw_data["quality"], dict):
            if "received_at" not in raw_data["quality"] or not raw_data["quality"]["received_at"]:
                raw_data["quality"]["received_at"] = datetime.now(timezone.utc).isoformat()
        elif "quality" not in raw_data:
            source_name = str(raw_data.get("source", "UNKNOWN"))
            raw_data["quality"] = {
                "valid": True,
                "source": source_name,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

        # Run validation
        telemetry = TelemetryValidator.require_valid(raw_data)

        # Update source heartbeat in registry if known
        source_id = telemetry.quality.source
        self.registry.update_heartbeat(source_id)

        return telemetry
