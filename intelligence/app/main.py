"""
Climate Eye View S2 Intelligence Service — Main Application Entry Point.
Production-grade FastAPI service providing health, validation, and contract endpoints.
"""

import asyncio
from contextlib import asynccontextmanager
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from intelligence.app.config import Settings, settings
from intelligence.core.metrics.collector import metrics
from intelligence.core.security.middleware import (
    PayloadSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from intelligence.core.security.auth import Role, require_role, authenticate_client
from intelligence.core.security.rate_limiter import limit_rate
from intelligence.app.dependencies import (
    get_settings,
    get_source_registry,
    get_provenance_tracker,
    get_hazard_engine,
    get_prediction_engine,
    get_compound_engine,
    get_vulnerability_engine,
    get_evacuation_engine,
    get_simulation_engine,
    get_response_engine,
    get_explainability_engine,
    get_evaluation_engine,
    get_calibration_engine,
)
from intelligence.response.types import (
    ResponseEvaluateRequest,
    ResponseSimulateRequest,
    ResponsePlanResponse,
)
from intelligence.explainability.types import (
    ExplanationRequest,
    TargetType,
    ExplanationLevel,
)
from intelligence.evaluation.types import (
    EvaluationRunRequest,
    ModelCompareRequest,
    DriftEvaluateRequest,
)
from intelligence.calibration.types import (
    CalibrationRunRequest,
    CalibrationMethod,
)
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.errors.exceptions import (
    ErrorCode,
    ErrorDetail,

    ErrorResponse,
    IntelligenceServiceException,
    ResourceNotFoundException,
    SimulationException,
    StaleDataException,
    ValidationException,
)
from intelligence.core.logging import get_logger, setup_logging
from intelligence.core.provenance.tracker import ProvenanceTracker
from intelligence.core.realtime.broadcaster import realtime_broadcaster
from intelligence.core.validation.validator import TelemetryValidator
from intelligence.database.repository import get_repository
from intelligence.ingestion.mqtt_client import ClimateMqttClient
from intelligence.ingestion.source_registry import SourceRegistry

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for service startup and shutdown."""
    setup_logging(log_level=settings.log_level)
    settings.validate_production_security()
    logger.info(
        "Climate Eye View S2 Intelligence Service starting up...",
        extra={"extra_data": {"environment": settings.environment, "port": settings.port}},
    )

    try:
        realtime_broadcaster.set_event_loop(asyncio.get_running_loop())
    except Exception as exc:
        logger.debug(f"Event loop binding note: {exc}")

    # Wire and start background MQTT client
    repo = get_repository()

    def on_mqtt_telemetry(telemetry: NormalizedTelemetry) -> None:
        try:
            repo.save_telemetry(telemetry)
            realtime_broadcaster.broadcast_sync(
                "telemetry.updated",
                {"telemetry": telemetry.model_dump(), "source": "MQTT", "status": "LIVE"},
            )
        except Exception as err:
            logger.error(f"Error handling MQTT telemetry: {err}")

    mqtt_client = ClimateMqttClient(
        on_telemetry_callback=on_mqtt_telemetry,
    )
    app.state.mqtt_client = mqtt_client

    # Connect non-blocking (gracefully handles broker unavailable without halting server)
    try:
        mqtt_client.start(non_blocking=True)
    except Exception as e:
        logger.warning(f"MQTT auto-start note: {e}")

    yield

    logger.info("Climate Eye View S2 Intelligence Service shutting down...")
    try:
        mqtt_client.stop()
    except Exception as e:
        logger.warning(f"MQTT stop note: {e}")


app = FastAPI(
    title="Climate Eye View — Intelligence Subsystem (S2)",
    version="1.0.0",
    description="S2 Intelligence microservice managing data fusion, hazard modeling, prediction, and response planning.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enforce payload body size limit
app.add_middleware(PayloadSizeLimitMiddleware)

# Security headers (CSP, X-Frame-Options, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS for S1 frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    """Assigns unique request ID, logs request processing latency, and records metrics."""
    request_id = request.headers.get("X-Request-ID") or f"REQ-{uuid.uuid4().hex[:12].upper()}"
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_sec = time.perf_counter() - start_time
    duration_ms = duration_sec * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
    
    # Record operational metrics
    metrics.record_request(request.url.path, response.status_code, duration_sec)
    return response


# ---------------------------------------------------------------------------
# Centralized Error Handlers (Conforming to Project Error Contract)
# ---------------------------------------------------------------------------

@app.exception_handler(IntelligenceServiceException)
async def handle_intelligence_exception(request: Request, exc: IntelligenceServiceException):
    """Handles domain-specific service exceptions."""
    request_id = getattr(request.state, "request_id", None)
    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """Handles FastAPI/Pydantic request payload validation errors."""
    request_id = getattr(request.state, "request_id", None)
    formatted_errors = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", []))
        formatted_errors.append({
            "field": loc,
            "message": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        })

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Request validation failed with {len(formatted_errors)} error(s)",
            details={"errors": formatted_errors},
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response.model_dump(),
    )


from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: Any):
    """Converts HTTP exceptions into standard Climate Eye View error contract."""
    request_id = getattr(request.state, "request_id", None)
    # Map HTTP status codes to canonical ErrorCode enum
    status_code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.INVALID_REQUEST,
        403: ErrorCode.INVALID_REQUEST,
        404: ErrorCode.NOT_FOUND,
        413: ErrorCode.INVALID_REQUEST,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.INVALID_REQUEST,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    default_code = status_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    if isinstance(exc.detail, dict):
        raw_code = exc.detail.get("code")
        try:
            code = ErrorCode(raw_code) if raw_code else default_code
        except ValueError:
            code = default_code
        message = exc.detail.get("message", str(exc.detail))
        details = dict(exc.detail.get("details", {}))
        if raw_code and raw_code != code.value:
            details["sub_code"] = raw_code
    else:
        code = default_code
        message = str(exc.detail)
        details = {}

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
        ),
        request_id=request_id,
    )
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
        headers=headers,
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    """Catches unhandled errors without leaking stack traces or internal secrets."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception(f"Unhandled exception during request {request_id}: {exc}")

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal server error occurred while processing the request.",
            details={},
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------

@app.get(f"{settings.api_prefix}/health", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    """Service liveness probe."""
    return {
        "status": "healthy",
        "service": "climate-intelligence",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(f"{settings.api_prefix}/health/live", tags=["Health"])
async def liveness_check():
    """Service process liveness probe."""
    return {
        "status": "ALIVE",
        "live": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(f"{settings.api_prefix}/health/ready", tags=["Health"])
@app.get(f"{settings.api_prefix}/ready", tags=["Health"])
@app.get("/ready", tags=["Health"])
async def readiness_check(
    registry: SourceRegistry = Depends(get_source_registry),
):
    """Service readiness probe checking availability of core internal modules."""
    sources = registry.list_all()
    if not sources:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "UNAVAILABLE",
                "ready": False,
                "reason": "No telemetry sources registered in source registry",
            },
        )

    return {
        "status": "READY",
        "ready": True,
        "registered_sources_count": len(sources),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(f"{settings.api_prefix}/metrics", tags=["Observability"])
@app.get("/metrics", tags=["Observability"])
async def get_metrics():
    """Returns operational metrics snapshot."""
    return metrics.get_snapshot()


# ---------------------------------------------------------------------------
# Realtime Intelligence Event Streaming Endpoints (WebSockets & SSE)
# ---------------------------------------------------------------------------

@app.websocket("/api/v1/events/ws")
@app.websocket("/ws/climate")
async def websocket_events_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint streaming live intelligence events to God's Eye View (GEV).
    Emits canonical events: telemetry.updated, hazard.updated, prediction.updated,
    compound.updated, vulnerability.updated, evacuation.updated, response.updated,
    simulation.completed.
    """
    await realtime_broadcaster.register_websocket(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await realtime_broadcaster.unregister_websocket(websocket)
    except Exception:
        await realtime_broadcaster.unregister_websocket(websocket)


@app.get("/api/v1/events/stream", tags=["Realtime"])
async def sse_events_endpoint():
    """
    Server-Sent Events (SSE) endpoint streaming live intelligence events to HTTP consumers.
    """
    return StreamingResponse(
        realtime_broadcaster.subscribe_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/events/history", tags=["Realtime"])
async def get_events_history(limit: int = 50, event_type: Optional[str] = None):
    """
    Returns recent broadcast events history for state catch-up and audit verification.
    """
    return {
        "success": True,
        "events": realtime_broadcaster.get_history(limit=limit, event_type=event_type),
    }


# ---------------------------------------------------------------------------
# Telemetry Ingestion & Validation Endpoints
# ---------------------------------------------------------------------------

@app.get(f"{settings.api_prefix}/sources", tags=["Sources"])
async def list_sources(
    registry: SourceRegistry = Depends(get_source_registry),
):
    """List all registered telemetry data sources and their statuses."""
    return {
        "success": True,
        "sources": [source.model_dump() for source in registry.list_all()],
    }


@app.post(f"{settings.api_prefix}/telemetry/validate", tags=["Telemetry"])
async def validate_telemetry_packet(
    payload: Dict[str, Any],
    request: Request,
    tracker: ProvenanceTracker = Depends(get_provenance_tracker),
):
    """
    Validates an incoming telemetry packet against the Canonical Data Contract.
    Computes cryptographic provenance hash on valid records.
    """
    is_valid, telemetry, error = TelemetryValidator.validate_dict(payload)
    request_id = getattr(request.state, "request_id", None)

    if not is_valid or telemetry is None:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=error,
                request_id=request_id,
            ).model_dump(),
        )

    provenance_record = tracker.generate_record(telemetry)
    try:
        repo = get_repository()
        repo.save_telemetry(telemetry, provenance_hash=provenance_record.record_hash)
        realtime_broadcaster.broadcast_sync(
            "telemetry.updated",
            {
                "telemetry": telemetry.model_dump(),
                "provenance": provenance_record.model_dump(),
                "source": "REST",
                "status": "LIVE",
            },
        )
    except Exception as persist_exc:
        logger.warning(f"Telemetry persistence/broadcast note: {persist_exc}")

    return {
        "success": True,
        "valid": True,
        "telemetry": telemetry.model_dump(),
        "provenance": provenance_record.model_dump(),
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Hazard Evaluation Endpoint (Phase 2 Deterministic Risk Engine)
# ---------------------------------------------------------------------------

@app.post(f"{settings.api_prefix}/hazards/evaluate", tags=["Hazards"])
async def evaluate_hazards(
    payload: Dict[str, Any],
    request: Request,
    engine = Depends(get_hazard_engine),
):
    """
    Evaluates current-state hazard risk (Heat, Flood, Drought) from normalized telemetry.
    Strictly deterministic current-state evaluation:
      - forecast_horizon_minutes = 0
      - simulated = false
      - client cannot supply or dictate severity, confidence, or classification
    """
    request_id = getattr(request.state, "request_id", None)

    # 1. Extract telemetry payload
    telemetry_raw = payload.get("telemetry")
    if telemetry_raw is None:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Missing required 'telemetry' field in request payload",
                    details={"field": "telemetry"},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    # 2. Validate telemetry contract
    is_valid, telemetry, error = TelemetryValidator.validate_dict(telemetry_raw)
    if not is_valid or telemetry is None:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=error,
                request_id=request_id,
            ).model_dump(),
        )

    # 3. Optional hazard types filter
    requested_hazards = None
    if "hazards" in payload and payload["hazards"] is not None:
        from intelligence.hazards.types import HazardType
        try:
            requested_hazards = [HazardType(h) for h in payload["hazards"]]
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid hazard type in requested filter: {e}",
                        details={"hazards": payload.get("hazards")},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 4. Deterministic evaluation through HazardEngine
    results = engine.evaluate_telemetry(
        telemetry=telemetry,
        hazard_types=requested_hazards,
    )

    try:
        repo = get_repository()
        for res in results:
            repo.save_hazard_event(
                event_id=res.hazard_id,
                hazard_type=res.hazard.value,
                severity=res.severity,
                confidence=res.confidence,
                detected_at=res.timestamp,
                node_id=telemetry.node_id,
                evidence={"drivers": res.drivers, "features": res.features},
            )
        realtime_broadcaster.broadcast_sync(
            "hazard.updated",
            {
                "node_id": telemetry.node_id,
                "hazards": [result.model_dump() for result in results],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as bc_exc:
        logger.warning(f"Hazard broadcast/persist note: {bc_exc}")

    return {
        "success": True,
        "hazards": [result.model_dump() for result in results],
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Hazard Prediction Endpoint (Phase 3 Deterministic Prediction Engine)
# ---------------------------------------------------------------------------

@app.post(f"{settings.api_prefix}/predictions/evaluate", tags=["Predictions"])
async def evaluate_predictions(
    payload: Dict[str, Any],
    request: Request,
    engine = Depends(get_prediction_engine),
):
    """
    Evaluates future-state hazard predictions (Heat, Flood, Drought) across strictly
    30-minute, 1-hour, and 6-hour horizons from normalized telemetry and history.
    Strictly deterministic forecasting:
      - forecast_horizon_minutes in {30, 60, 360}
      - simulated = false
      - client cannot dictate severity, confidence, or classification
    """
    request_id = getattr(request.state, "request_id", None)

    # 1. Validate current telemetry payload
    telemetry_raw = payload.get("telemetry")
    if telemetry_raw is None:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Missing required 'telemetry' field in prediction payload",
                    details={"field": "telemetry"},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    is_valid, current_telemetry, error = TelemetryValidator.validate_dict(telemetry_raw)
    if not is_valid or current_telemetry is None:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=error,
                request_id=request_id,
            ).model_dump(),
        )

    # 2. Validate historical telemetry packets
    history_raw = payload.get("history", [])
    if not isinstance(history_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'history' must be a list of telemetry packets",
                    details={"field": "history"},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    valid_history: List[NormalizedTelemetry] = []
    for idx, h_item in enumerate(history_raw):
        h_valid, h_telemetry, h_err = TelemetryValidator.validate_dict(h_item)
        if not h_valid or h_telemetry is None:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"History record at index {idx} failed validation: {h_err.message if h_err else 'Invalid'}",
                        details={"history_index": idx, "error": h_err.model_dump() if h_err else None},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )
        valid_history.append(h_telemetry)

    # 3. Validate requested horizons (strictly {30, 60, 360})
    from intelligence.prediction.thresholds import VALID_HORIZONS
    from intelligence.hazards.types import HazardType

    requested_horizons = None
    if "horizons_minutes" in payload and payload["horizons_minutes"] is not None:
        horizons_raw = payload["horizons_minutes"]
        if not isinstance(horizons_raw, list):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Field 'horizons_minutes' must be a list of integers",
                        details={"horizons_minutes": horizons_raw},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

        unsupported = [h for h in horizons_raw if h not in VALID_HORIZONS]
        if unsupported:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Unsupported forecast horizon(s): {unsupported}. Valid horizons are: {sorted(list(VALID_HORIZONS))}",
                        details={"unsupported_horizons": unsupported, "valid_horizons": sorted(list(VALID_HORIZONS))},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )
        requested_horizons = horizons_raw

    # 4. Validate requested hazards
    requested_hazards = None
    if "hazards" in payload and payload["hazards"] is not None:
        try:
            requested_hazards = [HazardType(h) for h in payload["hazards"]]
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid hazard type in requested filter: {e}",
                        details={"hazards": payload.get("hazards")},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 5. Execute predictions
    predictions = engine.evaluate_predictions(
        current_telemetry=current_telemetry,
        history=valid_history,
        requested_hazards=requested_hazards,
        requested_horizons=requested_horizons,
    )

    try:
        repo = get_repository()
        for p in predictions:
            repo.save_prediction(
                prediction_id=p.prediction_id,
                node_id=current_telemetry.node_id,
                target_hazard=p.hazard.value if hasattr(p.hazard, 'value') else str(p.hazard),
                horizon_minutes=p.forecast_horizon_minutes,
                predicted_severity=p.severity,
                confidence=p.confidence,
                trend=str(getattr(p, 'trend', 'EXTRAPOLATED')),
                model_version=p.model_version,
                predicted_at=p.prediction_time,
            )
        realtime_broadcaster.broadcast_sync(
            "prediction.updated",
            {
                "node_id": current_telemetry.node_id,
                "predictions": [p.model_dump() for p in predictions],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as pred_exc:
        logger.warning(f"Prediction broadcast/persist note: {pred_exc}")

    return {
        "success": True,
        "predictions": [p.model_dump() for p in predictions],
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Phase 4: Compound & Cascading Disaster Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/compound/evaluate", tags=["Compound Intelligence"])
async def evaluate_compound_hazards(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    compound_engine=Depends(get_compound_engine),
):
    """
    Evaluates observed Phase 2 hazard results, Phase 3 predictions, and environmental states
    to discover active compound events, cascading chains, and infrastructure consequences.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    from intelligence.hazards.types import HazardResult
    from intelligence.prediction.types import PredictionResult
    from intelligence.compound.types import CompoundEvaluationResponse

    # 1. Parse and validate HazardResults
    parsed_hazards: List[HazardResult] = []
    hazards_raw = payload.get("hazards", [])
    if not isinstance(hazards_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'hazards' must be a list of HazardResult objects",
                    details={"hazards": hazards_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    for idx, h_raw in enumerate(hazards_raw):
        try:
            parsed_hazards.append(HazardResult(**h_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Hazard result at index {idx} failed contract validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 2. Parse and validate PredictionResults
    parsed_predictions: List[PredictionResult] = []
    preds_raw = payload.get("predictions", [])
    if not isinstance(preds_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'predictions' must be a list of PredictionResult objects",
                    details={"predictions": preds_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    for idx, p_raw in enumerate(preds_raw):
        try:
            parsed_predictions.append(PredictionResult(**p_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Prediction result at index {idx} failed contract validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 3. Optional environmental states
    env_states = payload.get("environmental_states")

    # 4. Optional baseline timestamp
    now_ts = None
    if "timestamp" in payload and payload["timestamp"]:
        try:
            now_ts = datetime.fromisoformat(payload["timestamp"])
        except ValueError:
            now_ts = None

    # 5. Evaluate compound events
    events = compound_engine.evaluate(
        hazards=parsed_hazards,
        predictions=parsed_predictions,
        environmental_states=env_states,
        now=now_ts,
    )

    try:
        realtime_broadcaster.broadcast_sync(
            "compound.updated",
            {
                "events": [e.model_dump() for e in events],
                "event_count": len(events),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as comp_exc:
        logger.warning(f"Compound broadcast note: {comp_exc}")

    response = CompoundEvaluationResponse(
        success=True,
        events=events,
        event_count=len(events),
        request_id=request_id,
    )
    return response.model_dump()


@app.get("/api/v1/compound-events/current", tags=["Compound Intelligence"])
async def get_current_compound_events(
    request: Request,
    compound_engine=Depends(get_compound_engine),
):
    """
    Returns the most recently evaluated active compound and cascading disaster events.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    from intelligence.compound.types import CompoundEvaluationResponse

    events = compound_engine.get_latest_events()
    return CompoundEvaluationResponse(
        success=True,
        events=events,
        event_count=len(events),
        request_id=request_id,
    ).model_dump()


# ---------------------------------------------------------------------------
# Phase 5: Human Vulnerability & Exposure Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/vulnerability/evaluate", tags=["Vulnerability Intelligence"])
async def evaluate_vulnerability(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    vulnerability_engine=Depends(get_vulnerability_engine),
):
    """
    Evaluates human vulnerability, geographic exposure, accessibility, and human impact
    across supplied population zones.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    from intelligence.vulnerability.types import (
        PopulationZone,
        VulnerabilityEvaluationResponse,
    )
    from intelligence.hazards.types import HazardResult
    from intelligence.prediction.types import PredictionResult
    from intelligence.compound.types import CompoundEvent

    # 1. Parse and validate PopulationZones (Required field)
    zones_raw = payload.get("zones")
    if not zones_raw or not isinstance(zones_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'zones' must be a non-empty list of PopulationZone objects",
                    details={"zones": zones_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    parsed_zones: List[PopulationZone] = []
    for idx, z_raw in enumerate(zones_raw):
        try:
            parsed_zones.append(PopulationZone(**z_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"PopulationZone at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 2. Parse optional HazardResults
    parsed_hazards: List[HazardResult] = []
    hazards_raw = payload.get("hazards", [])
    if isinstance(hazards_raw, list):
        for idx, h_raw in enumerate(hazards_raw):
            try:
                parsed_hazards.append(HazardResult(**h_raw))
            except Exception as e:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content=ErrorResponse(
                        success=False,
                        error=ErrorDetail(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"HazardResult at index {idx} failed validation: {e}",
                            details={"index": idx, "error": str(e)},
                        ),
                        request_id=request_id,
                    ).model_dump(),
                )

    # 3. Parse optional PredictionResults
    parsed_predictions: List[PredictionResult] = []
    preds_raw = payload.get("predictions", [])
    if isinstance(preds_raw, list):
        for idx, p_raw in enumerate(preds_raw):
            try:
                parsed_predictions.append(PredictionResult(**p_raw))
            except Exception as e:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content=ErrorResponse(
                        success=False,
                        error=ErrorDetail(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"PredictionResult at index {idx} failed validation: {e}",
                            details={"index": idx, "error": str(e)},
                        ),
                        request_id=request_id,
                    ).model_dump(),
                )

    # 4. Parse optional CompoundEvents
    parsed_compound: List[CompoundEvent] = []
    compound_raw = payload.get("compound_events", [])
    if isinstance(compound_raw, list):
        for idx, ce_raw in enumerate(compound_raw):
            try:
                parsed_compound.append(CompoundEvent(**ce_raw))
            except Exception as e:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content=ErrorResponse(
                        success=False,
                        error=ErrorDetail(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"CompoundEvent at index {idx} failed validation: {e}",
                            details={"index": idx, "error": str(e)},
                        ),
                        request_id=request_id,
                    ).model_dump(),
                )

    # 5. Optional timestamp
    now_ts = None
    if "timestamp" in payload and payload["timestamp"]:
        try:
            now_ts = datetime.fromisoformat(payload["timestamp"])
        except ValueError:
            now_ts = None

    # 6. Evaluate human vulnerability and impact
    assessments = vulnerability_engine.evaluate(
        zones=parsed_zones,
        hazards=parsed_hazards,
        predictions=parsed_predictions,
        compound_events=parsed_compound,
        now=now_ts,
    )

    try:
        realtime_broadcaster.broadcast_sync(
            "vulnerability.updated",
            {
                "assessments": [a.model_dump() for a in assessments],
                "assessment_count": len(assessments),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as vuln_exc:
        logger.warning(f"Vulnerability broadcast note: {vuln_exc}")

    response = VulnerabilityEvaluationResponse(
        success=True,
        assessments=assessments,
        assessment_count=len(assessments),
        request_id=request_id,
    )
    return response.model_dump()


@app.get("/api/v1/vulnerability/zones", tags=["Vulnerability Intelligence"])
async def get_vulnerability_zones(
    request: Request,
    vulnerability_engine=Depends(get_vulnerability_engine),
):
    """
    Returns the most recently evaluated human vulnerability and impact zone assessments.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    from intelligence.vulnerability.types import VulnerabilityEvaluationResponse

    assessments = vulnerability_engine.get_latest_assessments()
    return VulnerabilityEvaluationResponse(
        success=True,
        assessments=assessments,
        assessment_count=len(assessments),
        request_id=request_id,
    ).model_dump()


# ---------------------------------------------------------------------------
# Phase 6: Dynamic Evacuation & Adaptive Routing Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/evacuation/evaluate", tags=["Evacuation Intelligence"])
async def evaluate_evacuation(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    evacuation_engine=Depends(get_evacuation_engine),
):
    """
    Evaluates evacuation demand, identifies optimal safe shelters, checks capacity constraints,
    and computes deterministic hazard-aware routes.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    from intelligence.evacuation.types import (
        EvacuationEvaluationResponse,
        PopulationZone,
        RoadNetwork,
        Shelter,
    )
    from intelligence.vulnerability.types import VulnerabilityZoneAssessment
    from intelligence.hazards.types import HazardResult
    from intelligence.prediction.types import PredictionResult
    from intelligence.compound.types import CompoundEvent

    # 1. Parse and validate PopulationZones
    zones_raw = payload.get("zones")
    if not zones_raw or not isinstance(zones_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'zones' must be a non-empty list of PopulationZone objects",
                    details={"zones": zones_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    parsed_zones: List[PopulationZone] = []
    for idx, z_raw in enumerate(zones_raw):
        try:
            parsed_zones.append(PopulationZone(**z_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"PopulationZone at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 2. Parse and validate Shelters
    shelters_raw = payload.get("shelters")
    if not shelters_raw or not isinstance(shelters_raw, list):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'shelters' must be a non-empty list of Shelter objects",
                    details={"shelters": shelters_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    parsed_shelters: List[Shelter] = []
    for idx, s_raw in enumerate(shelters_raw):
        try:
            parsed_shelters.append(Shelter(**s_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Shelter at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 3. Parse and validate RoadNetwork
    network_raw = payload.get("road_network")
    if not network_raw or not isinstance(network_raw, dict):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'road_network' must be a valid RoadNetwork object",
                    details={"road_network": network_raw},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    try:
        parsed_network = RoadNetwork(**network_raw)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"RoadNetwork failed validation: {e}",
                    details={"error": str(e)},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    # 4. Parse optional VulnerabilityZoneAssessments
    parsed_vulns: List[VulnerabilityZoneAssessment] = []
    vulns_raw = payload.get("vulnerabilities", [])
    if isinstance(vulns_raw, list):
        for idx, v_raw in enumerate(vulns_raw):
            try:
                parsed_vulns.append(VulnerabilityZoneAssessment(**v_raw))
            except Exception as e:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content=ErrorResponse(
                        success=False,
                        error=ErrorDetail(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"VulnerabilityZoneAssessment at index {idx} failed validation: {e}",
                            details={"index": idx, "error": str(e)},
                        ),
                        request_id=request_id,
                    ).model_dump(),
                )

    # 5. Parse optional Hazards, Predictions, Compound events
    parsed_hazards: List[HazardResult] = []
    for idx, h_raw in enumerate(payload.get("hazards", [])):
        try:
            parsed_hazards.append(HazardResult(**h_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"HazardResult at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    parsed_predictions: List[PredictionResult] = []
    for idx, p_raw in enumerate(payload.get("predictions", [])):
        try:
            parsed_predictions.append(PredictionResult(**p_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"PredictionResult at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    parsed_compound: List[CompoundEvent] = []
    for idx, ce_raw in enumerate(payload.get("compound_events", [])):
        try:
            parsed_compound.append(CompoundEvent(**ce_raw))
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"CompoundEvent at index {idx} failed validation: {e}",
                        details={"index": idx, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 6. Optional timestamp
    now_ts = None
    if "timestamp" in payload and payload["timestamp"]:
        try:
            now_ts = datetime.fromisoformat(payload["timestamp"])
        except ValueError:
            now_ts = None

    # 7. Evaluate evacuation directives
    recommendations = evacuation_engine.evaluate(
        zones=parsed_zones,
        shelters=parsed_shelters,
        road_network=parsed_network,
        vulnerabilities=parsed_vulns if parsed_vulns else None,
        hazards=parsed_hazards if parsed_hazards else None,
        predictions=parsed_predictions if parsed_predictions else None,
        compound_events=parsed_compound if parsed_compound else None,
        accessibility_threshold=payload.get("edge_accessibility_threshold"),
        now=now_ts,
    )

    total_evac = sum(
        r.destination.assigned_population
        for r in recommendations
        if r.destination is not None
    )
    unassigned = sum(
        r.population_to_evacuate - (r.destination.assigned_population if r.destination else 0)
        for r in recommendations
    )

    try:
        realtime_broadcaster.broadcast_sync(
            "evacuation.updated",
            {
                "recommendations": [r.model_dump() for r in recommendations],
                "total_evacuated_population": total_evac,
                "unassigned_demand_population": max(0, unassigned),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as evac_exc:
        logger.warning(f"Evacuation broadcast note: {evac_exc}")

    response = EvacuationEvaluationResponse(
        success=True,
        recommendations=recommendations,
        recommendation_count=len(recommendations),
        total_evacuated_population=total_evac,
        unassigned_demand_population=max(0, unassigned),
        request_id=request_id,
    )
    return response.model_dump()


@app.get("/api/v1/evacuation/routes", tags=["Evacuation Intelligence"])
async def get_evacuation_routes(
    request: Request,
    evacuation_engine=Depends(get_evacuation_engine),
):
    """
    Returns the most recently evaluated evacuation directives and routes.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    from intelligence.evacuation.types import EvacuationEvaluationResponse

    recommendations = evacuation_engine.get_latest_recommendations()
    total_evac = sum(
        r.destination.assigned_population
        for r in recommendations
        if r.destination is not None
    )
    unassigned = sum(
        r.population_to_evacuate - (r.destination.assigned_population if r.destination else 0)
        for r in recommendations
    )

    return EvacuationEvaluationResponse(
        success=True,
        recommendations=recommendations,
        recommendation_count=len(recommendations),
        total_evacuated_population=total_evac,
        unassigned_demand_population=max(0, unassigned),
        request_id=request_id,
    ).model_dump()


@app.get("/api/v1/evacuation/current", tags=["Evacuation Intelligence"])
async def get_evacuation_current(
    request: Request,
    evacuation_engine=Depends(get_evacuation_engine),
):
    """
    Alias endpoint for retrieving current active evacuation recommendations.
    """
    return await get_evacuation_routes(request, evacuation_engine)


# ---------------------------------------------------------------------------
# Phase 7: Digital Twin + Scenario Simulation Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/simulation/scenarios", tags=["Scenario Simulation"])
async def list_simulation_scenarios(
    request: Request,
    simulation_engine=Depends(get_simulation_engine),
):
    """
    Returns the catalog of formally supported base simulation scenarios.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    scenarios = simulation_engine.get_supported_scenarios()
    return {
        "success": True,
        "count": len(scenarios),
        "scenarios": [s.model_dump() for s in scenarios],
        "request_id": request_id,
    }


@app.post(
    "/api/v1/simulation/run",
    tags=["Scenario Simulation"],
    dependencies=[Depends(require_role(Role.OPERATOR)), Depends(limit_rate(cost=1.0))],
)
async def run_scenario_simulation(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    simulation_engine=Depends(get_simulation_engine),
):
    """
    Executes a deterministic hypothetical scenario simulation on a digital twin state.
    Strictly isolated from live operational state; propagates through Phase 2-6 models.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if not settings.enable_scenario_simulation:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message="Scenario simulation engine is disabled by configuration.",
                ),
                request_id=request_id,
            ).model_dump(),
        )

    # 1. Validate scenario_id
    scenario_id = payload.get("scenario_id")
    if not scenario_id or not isinstance(scenario_id, str):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Field 'scenario_id' must be a non-empty string",
                    details={"scenario_id": scenario_id},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    # 2. Parse changes/parameters if provided
    from intelligence.simulation.types import (
        DigitalTwinState,
        ScenarioParameters,
        SimulationRunResponse,
    )
    from intelligence.simulation.scenarios import ScenarioCatalog

    parsed_changes = None
    changes_raw = payload.get("changes")
    if changes_raw is not None:
        if not isinstance(changes_raw, dict):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Field 'changes' must be an object of scenario parameters",
                        details={"changes": changes_raw},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )
        try:
            parsed_changes = ScenarioParameters(**changes_raw)
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scenario parameter values: {e}",
                        details={"changes": changes_raw, "error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 3. Parse base_state if provided
    parsed_base_state = None
    base_state_raw = payload.get("base_state")
    if base_state_raw is not None and base_state_raw != "current":
        if not isinstance(base_state_raw, dict):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Field 'base_state' must be 'current' or a valid DigitalTwinState object",
                        details={"base_state": type(base_state_raw).__name__},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )
        try:
            parsed_base_state = DigitalTwinState(**base_state_raw)
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ErrorResponse(
                    success=False,
                    error=ErrorDetail(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Provided base_state failed validation: {e}",
                        details={"error": str(e)},
                    ),
                    request_id=request_id,
                ).model_dump(),
            )

    # 4. Execute simulation through engine
    try:
        result = simulation_engine.run_simulation(
            scenario_id=scenario_id,
            base_state=parsed_base_state,
            changes=parsed_changes,
        )
        try:
            realtime_broadcaster.broadcast_sync(
                "simulation.completed",
                {
                    "simulation_id": result.simulation_id,
                    "scenario_id": result.scenario_id,
                    "simulated": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as sim_exc:
            logger.warning(f"Simulation broadcast note: {sim_exc}")

        return SimulationRunResponse(
            success=True,
            simulation=result,
            request_id=request_id,
        ).model_dump()

    except StaleDataException as sde:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.STALE_DATA,
                    message=sde.message,
                    details=sde.details,
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except ResourceNotFoundException as rnfe:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.NOT_FOUND,
                    message=rnfe.message,
                    details=rnfe.details,
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except (ValidationException, ValueError) as ve:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=str(ve),
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Unexpected error running scenario simulation: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.SIMULATION_ERROR,
                    message=f"Simulation calculation failed: {exc}",
                ),
                request_id=request_id,
            ).model_dump(),
        )


@app.get(
    "/api/v1/simulation/{simulation_id}",
    tags=["Scenario Simulation"],
    dependencies=[Depends(require_role(Role.OPERATOR))],
)
async def get_simulation_result(
    simulation_id: str,
    request: Request,
    simulation_engine=Depends(get_simulation_engine),
):
    """
    Retrieves a cached scenario simulation result by simulation_id.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    cached = simulation_engine.get_cached_simulation(simulation_id)
    if cached is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.NOT_FOUND,
                    message=f"Simulation result '{simulation_id}' not found or expired.",
                    details={"simulation_id": simulation_id},
                ),
                request_id=request_id,
            ).model_dump(),
        )

    return {
        "success": True,
        "simulation": cached.model_dump(),
        "request_id": request_id,
    }


# ---------------------------------------------------------------------------
# Phase 9: AI Response Planner Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/response/current", tags=["Emergency Response Planning"])
async def get_current_response_plan(
    request: Request,
    response_engine=Depends(get_response_engine),
):
    """
    Retrieves the latest authoritative emergency response plan.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        plan = response_engine.get_current_plan()
        return ResponsePlanResponse(
            success=True,
            plan=plan,
            request_id=request_id,
        ).model_dump()
    except Exception as exc:
        logger.error(f"Failed to retrieve current response plan: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to retrieve current response plan: {exc}",
                ),
                request_id=request_id,
            ).model_dump(),
        )


@app.post(
    "/api/v1/response/evaluate",
    tags=["Emergency Response Planning"],
    dependencies=[Depends(require_role(Role.OPERATOR))],
)
async def evaluate_response_plan_endpoint(
    request: Request,
    payload: Optional[ResponseEvaluateRequest] = Body(default=None),
    response_engine=Depends(get_response_engine),
):
    """
    Evaluates current or supplied environmental conditions and demographic assets
    to synthesize an evidence-backed, prioritized emergency response plan.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        req_dict = payload.model_dump(exclude_none=True) if payload else {}
        plan = response_engine.evaluate_response_plan(
            telemetry=req_dict.get("telemetry"),
            history=req_dict.get("history"),
            population_zones=req_dict.get("population_zones"),
            road_network=req_dict.get("road_network"),
            shelters=req_dict.get("shelters"),
            include_predictions=req_dict.get("include_predictions", True),
        )
        try:
            repo = get_repository()
            primary_haz = "flood"
            if plan.situation and plan.situation.observed_hazards:
                h0 = plan.situation.observed_hazards[0]
                primary_haz = str(h0.get("hazard", "flood") if isinstance(h0, dict) else getattr(h0, "hazard", "flood"))
            repo.save_response_plan(
                plan_id=plan.plan_id,
                alert_level=plan.alert_level.value if hasattr(plan.alert_level, "value") else str(plan.alert_level),
                primary_hazard=primary_haz,
                actions=[a.model_dump() for a in plan.actions],
                resource_allocations={},
                evaluated_at=plan.generated_at,
            )
            realtime_broadcaster.broadcast_sync(
                "response.updated",
                {
                    "plan_id": plan.plan_id,
                    "alert_level": plan.alert_level.value if hasattr(plan.alert_level, "value") else str(plan.alert_level),
                    "primary_hazard": primary_haz,
                    "action_count": len(plan.actions),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as resp_exc:
            logger.warning(f"Response broadcast/persist note: {resp_exc}")

        return ResponsePlanResponse(
            success=True,
            plan=plan,
            request_id=request_id,
        ).model_dump()
    except (ValidationException, ValueError) as ve:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=str(ve),
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Error evaluating response plan: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Response planning calculation failed: {exc}",
                ),
                request_id=request_id,
            ).model_dump(),
        )


@app.post(
    "/api/v1/response/simulate",
    tags=["Emergency Response Planning"],
    dependencies=[Depends(require_role(Role.OPERATOR)), Depends(limit_rate(cost=1.0))],
)
async def simulate_response_plan_endpoint(
    request: Request,
    payload: ResponseSimulateRequest = Body(...),
    response_engine=Depends(get_response_engine),
):
    """
    Synthesizes a response plan against a Phase 8 digital twin what-if simulation scenario.
    Labels all actions with simulated=True and SIMULATED epistemic groundings.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        plan = response_engine.simulate_scenario_response(
            scenario_id=payload.scenario_id,
            changes=payload.changes,
            base_state=payload.base_state,
        )
        return ResponsePlanResponse(
            success=True,
            plan=plan,
            request_id=request_id,
        ).model_dump()
    except ResourceNotFoundException as rnfe:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.NOT_FOUND,
                    message=rnfe.message,
                    details=rnfe.details,
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except (ValidationException, ValueError) as ve:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=str(ve),
                ),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Error simulating response plan: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Simulation response planning failed: {exc}",
                ),
                request_id=request_id,
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# Phase 10: Explainability, Evaluation & Calibration Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/explainability/{target_type}/{target_id}", tags=["Explainability"])
async def get_explanation_endpoint(
    target_type: str,
    target_id: str,
    request: Request,
    level: Optional[str] = "STANDARD",
    explainability_engine=Depends(get_explainability_engine),
):
    """
    Retrieves an explainability contract for a specified target model artifact.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        t_type = TargetType(target_type.lower())
        exp_level = ExplanationLevel(level.upper()) if level else ExplanationLevel.STANDARD
        explanation = explainability_engine.explain(
            target_type=t_type,
            target_id=target_id,
            level=exp_level,
        )
        return {
            "success": True,
            "explanation": explanation.model_dump(),
            "request_id": request_id,
        }
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.VALIDATION_ERROR, message=str(ve)),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Error generating explanation: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=f"Explanation generation failed: {exc}"),
                request_id=request_id,
            ).model_dump(),
        )


@app.post("/api/v1/explainability/generate", tags=["Explainability"])
async def generate_explanation_endpoint(
    request: Request,
    payload: ExplanationRequest = Body(...),
    explainability_engine=Depends(get_explainability_engine),
):
    """
    Generates a structured explanation contract from inline target output or context.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        explanation = explainability_engine.explain(
            target_type=payload.target_type,
            target_id=payload.target_id,
            level=payload.level,
            target_object=payload.target_object,
            upstream_context=payload.upstream_context,
        )
        return {
            "success": True,
            "explanation": explanation.model_dump(),
            "request_id": request_id,
        }
    except Exception as exc:
        logger.error(f"Error in explainability generate: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to generate explanation: {exc}"),
                request_id=request_id,
            ).model_dump(),
        )


@app.post(
    "/api/v1/evaluation/run",
    tags=["Evaluation Engine"],
    dependencies=[Depends(require_role(Role.ADMIN)), Depends(limit_rate(cost=1.0))],
)
async def run_evaluation_endpoint(
    request: Request,
    payload: EvaluationRunRequest = Body(...),
    evaluation_engine=Depends(get_evaluation_engine),
):
    """
    Executes an empirical model evaluation against a benchmark dataset.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        report = evaluation_engine.evaluate_model(
            model_version=payload.model_version,
            dataset_id=payload.dataset_id,
            custom_dataset=payload.custom_dataset,
        )
        return {
            "success": True,
            "report": report.model_dump(),
            "request_id": request_id,
        }
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.NOT_FOUND, message=str(ve)),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Error running evaluation: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=f"Evaluation failed: {exc}"),
                request_id=request_id,
            ).model_dump(),
        )


@app.get(
    "/api/v1/evaluation/{evaluation_id}",
    tags=["Evaluation Engine"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def get_evaluation_endpoint(
    evaluation_id: str,
    request: Request,
    evaluation_engine=Depends(get_evaluation_engine),
):
    """
    Retrieves a cached evaluation report by ID.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    report = evaluation_engine.get_evaluation(evaluation_id)
    if not report:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.NOT_FOUND, message=f"Evaluation report '{evaluation_id}' not found."),
                request_id=request_id,
            ).model_dump(),
        )
    return {
        "success": True,
        "report": report.model_dump(),
        "request_id": request_id,
    }


@app.post(
    "/api/v1/calibration/run",
    tags=["Calibration Engine"],
    dependencies=[Depends(require_role(Role.ADMIN)), Depends(limit_rate(cost=1.0))],
)
async def run_calibration_endpoint(
    request: Request,
    payload: CalibrationRunRequest = Body(...),
    calibration_engine=Depends(get_calibration_engine),
):
    """
    Fits a probability calibrator on a dataset with statistical sample-size gating.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        report = calibration_engine.fit_calibrator(
            model_version=payload.model_version,
            dataset_id=payload.dataset_id,
            method=payload.method or CalibrationMethod.ISOTONIC,
        )
        return {
            "success": True,
            "report": report.model_dump(),
            "request_id": request_id,
        }
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.NOT_FOUND, message=str(ve)),
                request_id=request_id,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error(f"Error running calibration: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=f"Calibration failed: {exc}"),
                request_id=request_id,
            ).model_dump(),
        )


@app.get(
    "/api/v1/calibration/{calibration_id}",
    tags=["Calibration Engine"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def get_calibration_endpoint(
    calibration_id: str,
    request: Request,
    calibration_engine=Depends(get_calibration_engine),
):
    """
    Retrieves a cached calibration report by ID.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    report = calibration_engine.get_calibration(calibration_id)
    if not report:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.NOT_FOUND, message=f"Calibration report '{calibration_id}' not found."),
                request_id=request_id,
            ).model_dump(),
        )
    return {
        "success": True,
        "report": report.model_dump(),
        "request_id": request_id,
    }


@app.get(
    "/api/v1/models/{model_version}/evaluation",
    tags=["Evaluation Engine"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def get_model_evaluation_endpoint(
    model_version: str,
    request: Request,
    evaluation_engine=Depends(get_evaluation_engine),
):
    """
    Retrieves default benchmark evaluation for a model version.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        # Default benchmark mapping
        dataset_id = "EVAL-FLOOD-SYNTHETIC-001" if "flood" in model_version else (
            "EVAL-HEAT-SYNTHETIC-001" if "heat" in model_version else "EVAL-PRED-SYNTHETIC-001"
        )
        report = evaluation_engine.evaluate_model(model_version=model_version, dataset_id=dataset_id)
        return {
            "success": True,
            "report": report.model_dump(),
            "request_id": request_id,
        }
    except Exception as exc:
        logger.error(f"Error fetching model evaluation: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc)),
                request_id=request_id,
            ).model_dump(),
        )


@app.post(
    "/api/v1/models/compare",
    tags=["Evaluation Engine"],
    dependencies=[Depends(require_role(Role.ADMIN)), Depends(limit_rate(cost=1.0))],
)
async def compare_models_endpoint(
    request: Request,
    payload: ModelCompareRequest = Body(...),
    evaluation_engine=Depends(get_evaluation_engine),
):
    """
    Contrasts two model versions on a shared benchmark dataset and detects regression.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        comparison = evaluation_engine.compare_models(
            baseline_version=payload.baseline_model_version,
            candidate_version=payload.candidate_model_version,
            dataset_id=payload.dataset_id,
        )
        return {
            "success": True,
            "comparison": comparison.model_dump(),
            "request_id": request_id,
        }
    except Exception as exc:
        logger.error(f"Error comparing models: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc)),
                request_id=request_id,
            ).model_dump(),
        )


@app.post(
    "/api/v1/drift/evaluate",
    tags=["Evaluation Engine"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def evaluate_drift_endpoint(
    request: Request,
    payload: DriftEvaluateRequest = Body(...),
    evaluation_engine=Depends(get_evaluation_engine),
):
    """
    Evaluates distribution drift (PSI or KS test) between baseline and operational samples.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        report = evaluation_engine.evaluate_drift(
            feature_name=payload.feature_name,
            baseline_samples=payload.baseline_samples,
            current_samples=payload.current_samples,
            method=payload.method or "PSI",
            threshold=payload.threshold,
        )
        return {
            "success": True,
            "report": report.model_dump(),
            "request_id": request_id,
        }
    except Exception as exc:
        logger.error(f"Error evaluating drift: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc)),
                request_id=request_id,
            ).model_dump(),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("intelligence.app.main:app", host=settings.host, port=settings.port, reload=True)





