"""
Contract tests for the Climate Eye View Canonical Telemetry Contract.
Verifies strict adherence to data contract specifications without mocking.
"""

import pytest
from pydantic import ValidationError
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)
from intelligence.core.errors.exceptions import ErrorCode, ErrorDetail, ErrorResponse


def test_contract_required_top_level_fields():
    """Verify that all required top-level fields are enforced by the contract."""
    with pytest.raises(ValidationError) as exc:
        NormalizedTelemetry.model_validate({})
    errors = exc.value.errors()
    missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}
    expected_required = {"node_id", "timestamp", "location", "measurements", "quality"}
    assert expected_required.issubset(missing_fields)


def test_contract_coordinate_order_and_types():
    """Verify WGS84 coordinate contract."""
    loc = LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0)
    assert isinstance(loc.lat, float)
    assert isinstance(loc.lon, float)
    assert isinstance(loc.elevation, float)
    assert -90.0 <= loc.lat <= 90.0
    assert -180.0 <= loc.lon <= 180.0


def test_contract_physical_units_and_ranges():
    """
    Verify documented physical measurement contract:
      - temperature: °C (-50 to +65)
      - humidity: % (0 to 100)
      - pressure: hPa (800 to 1100)
      - rainfall: mm/hr (0 to 500)
      - soil_moisture: % (0 to 100)
      - water_level: m (0 to 50)
      - air_quality: AQI (0 to 500)
    """
    measurements = SensorMeasurements(
        temperature=31.42,
        humidity=74.20,
        pressure=1008.43,
        rainfall=12.60,
        soil_moisture=68.30,
        water_level=14.70,
        air_quality=82.0,
    )
    dumped = measurements.model_dump()
    assert dumped["temperature"] == 31.42
    assert dumped["rainfall"] == 12.60
    assert dumped["water_level"] == 14.70

    # Test boundary limits
    with pytest.raises(ValidationError):
        SensorMeasurements(temperature=-55.0)  # below -50 °C

    with pytest.raises(ValidationError):
        SensorMeasurements(humidity=105.0)  # above 100 %

    with pytest.raises(ValidationError):
        SensorMeasurements(rainfall=-1.0)  # negative rainfall rate

    with pytest.raises(ValidationError):
        SensorMeasurements(water_level=55.0)  # above 50 m


def test_contract_structured_error_schema():
    """Verify the error payload contract matches project requirements."""
    error_detail = ErrorDetail(
        code=ErrorCode.VALIDATION_ERROR,
        message="Measurement out of physical range",
        details={"field": "measurements.temperature", "value": 150.0},
    )
    response = ErrorResponse(
        success=False,
        error=error_detail,
        request_id="REQ-TEST-12345",
    )
    payload = response.model_dump()
    assert payload["success"] is False
    assert payload["request_id"] == "REQ-TEST-12345"
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "field" in payload["error"]["details"]
