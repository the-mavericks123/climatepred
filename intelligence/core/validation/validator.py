"""
Validation engine for telemetry packets and intelligence requests.
"""

from typing import Any, Dict, Tuple, Optional
from pydantic import ValidationError
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.errors.exceptions import ErrorCode, ErrorDetail, ValidationException


class TelemetryValidator:
    """Reusable validation engine for normalized telemetry payloads."""

    @staticmethod
    def _adapt_flat_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility adapter mapping flat incoming hardware telemetry into canonical schema."""
        from datetime import datetime, timezone
        data = dict(raw)
        # Adapt schema_version
        if "schema_version" in data and str(data["schema_version"]).startswith("1."):
            data["schema_version"] = "1.0"
        elif "schema_version" not in data:
            data["schema_version"] = "1.0"

        # Adapt location
        if "location" not in data and ("latitude" in data or "lat" in data):
            data["location"] = {
                "lat": data.get("latitude", data.get("lat")),
                "lon": data.get("longitude", data.get("lon")),
                "elevation": data.get("elevation", data.get("elevation_m")),
            }
        elif "location" in data and isinstance(data["location"], dict):
            loc = dict(data["location"])
            if "latitude" in loc and "lat" not in loc:
                loc["lat"] = loc["latitude"]
            if "longitude" in loc and "lon" not in loc:
                loc["lon"] = loc["longitude"]
            if "elevation_m" in loc and "elevation" not in loc:
                loc["elevation"] = loc["elevation_m"]
            data["location"] = loc

        # Adapt measurements
        if "measurements" not in data and "readings" in data and isinstance(data["readings"], dict):
            data["measurements"] = dict(data["readings"])
        elif "measurements" not in data:
            measurement_keys = [
                "temperature", "humidity", "pressure", "rainfall",
                "soil_moisture", "water_level", "air_quality",
                "light_intensity", "battery", "sensor_status"
            ]
            meas = {}
            for k in measurement_keys:
                if k in data and data[k] is not None:
                    meas[k] = data[k]
            if meas:
                data["measurements"] = meas

        # Adapt quality
        if "quality" not in data:
            data["quality"] = {
                "valid": True,
                "source": data.get("source", "ESP32"),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        elif isinstance(data["quality"], dict):
            q = dict(data["quality"])
            if "received_at" not in q or not q["received_at"]:
                q["received_at"] = datetime.now(timezone.utc).isoformat()
            data["quality"] = q

        return data

    @staticmethod
    def validate_dict(data: Dict[str, Any]) -> Tuple[bool, Optional[NormalizedTelemetry], Optional[ErrorDetail]]:
        """
        Validates raw dictionary data against Canonical NormalizedTelemetry schema.
        Returns (is_valid, telemetry_instance_or_none, error_detail_or_none).
        """
        if not isinstance(data, dict):
            error = ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message="Expected payload to be a JSON object",
                details={"received_type": type(data).__name__},
            )
            return False, None, error

        adapted = TelemetryValidator._adapt_flat_dict(data)

        try:
            telemetry = NormalizedTelemetry.model_validate(adapted)
            return True, telemetry, None
        except ValidationError as e:
            formatted_errors = []
            for err in e.errors():
                loc = ".".join(str(item) for item in err.get("loc", []))
                formatted_errors.append({
                    "field": loc,
                    "message": err.get("msg", "Invalid value"),
                    "type": err.get("type", "value_error"),
                })
            error = ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Telemetry payload validation failed with {len(formatted_errors)} error(s)",
                details={"errors": formatted_errors},
            )
            return False, None, error

    @staticmethod
    def require_valid(data: Dict[str, Any]) -> NormalizedTelemetry:
        """Validates dictionary and raises ValidationException if invalid."""
        is_valid, telemetry, error = TelemetryValidator.validate_dict(data)
        if not is_valid or telemetry is None:
            raise ValidationException(
                message=error.message if error else "Telemetry validation failed",
                details=error.details if error else {},
            )
        return telemetry
