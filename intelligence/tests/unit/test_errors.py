"""
Unit tests for structured error handling.
"""

from intelligence.core.errors.exceptions import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    InvalidRequestException,
    ValidationException,
    ResourceNotFoundException,
    StaleDataException,
    ServiceUnavailableException,
)


def test_error_response_model():
    err = ErrorDetail(
        code=ErrorCode.VALIDATION_ERROR,
        message="Test validation failure",
        details={"field": "lat"},
    )
    resp = ErrorResponse(
        success=False,
        error=err,
        request_id="REQ-TEST-001",
    )
    dumped = resp.model_dump()
    assert dumped["success"] is False
    assert dumped["request_id"] == "REQ-TEST-001"
    assert dumped["error"]["code"] == "VALIDATION_ERROR"
    assert dumped["error"]["details"]["field"] == "lat"


def test_custom_exception_properties():
    exc = ValidationException("Invalid coordinate", details={"lat": 150})
    assert exc.code == ErrorCode.VALIDATION_ERROR
    assert exc.status_code == 422
    assert exc.details["lat"] == 150

    stale = StaleDataException("Telemetry is too old")
    assert stale.code == ErrorCode.STALE_DATA
    assert stale.status_code == 409
