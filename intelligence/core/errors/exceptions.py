"""
Standardized error exceptions and response models for Climate Eye View S2.
Conforms strictly to the project's structured error contract.
"""

from typing import Any, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    STALE_DATA = "STALE_DATA"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    success: bool = Field(default=False)
    error: ErrorDetail
    request_id: Optional[str] = Field(default=None)


class IntelligenceServiceException(Exception):
    """Base application exception for Climate Eye View S2."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class InvalidRequestException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.INVALID_REQUEST, message, status_code=400, details=details)


class ValidationException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, status_code=422, details=details)


class ResourceNotFoundException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404, details=details)


class StaleDataException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.STALE_DATA, message, status_code=409, details=details)


class ModelUnavailableException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.MODEL_UNAVAILABLE, message, status_code=503, details=details)


class ServiceUnavailableException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, message, status_code=503, details=details)


class SimulationException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.SIMULATION_ERROR, message, status_code=500, details=details)


class InternalServerException(IntelligenceServiceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, status_code=500, details=details)
