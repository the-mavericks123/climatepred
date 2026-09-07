"""
Security, correlation, and error containment middlewares for Climate Eye View S2 service.
Ensures security headers, body size limits, correlation IDs, and sanitized error responses.
"""

import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from intelligence.app.config import settings
from intelligence.core.logging import get_logger

logger = get_logger("security_middleware")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects defensive HTTP security headers into all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Baseline defensive security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"

        if settings.environment.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Extracts or generates an immutable X-Request-ID header for end-to-end tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        request.state.request_id = req_id

        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforces upper boundary on incoming HTTP request body payload sizes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_bytes = int(content_length)
                if length_bytes > settings.max_request_body_bytes:
                    req_id = getattr(request.state, "request_id", f"REQ-{uuid.uuid4().hex[:8].upper()}")
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "success": False,
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body size ({length_bytes} bytes) exceeds limit of {settings.max_request_body_bytes} bytes.",
                                "details": {"max_bytes": settings.max_request_body_bytes, "actual_bytes": length_bytes},
                            },
                            "request_id": req_id,
                        },
                        headers={"X-Request-ID": req_id},
                    )
            except ValueError:
                pass

        return await call_next(request)
