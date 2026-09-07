# Production Readiness Checklist: Climate Eye View

**Milestone:** Phase 11 — Production Hardening  
**Status:** Verification Gate  

---

## 1. Core Production Readiness Matrix

- [x] **Secrets Externalized**: Zero hard-coded passwords, API keys, or private tokens in source code or fixtures.
- [x] **Configuration Validated**: Fail-fast startup checks reject insecure keys and wildcard CORS in production mode.
- [x] **CORS Hardened**: Wildcard origins (`*`) disallowed in production; allowed origins strictly configurable.
- [x] **API Validation Hardened**: Pydantic schema validation on all inputs and responses; unknown fields rejected or isolated.
- [x] **Authentication Boundary Documented**: Public vs. protected vs. admin access tiers explicitly established.
- [x] **Authorization Enforced**: Role-Based Access Control (`Public`, `Operator`, `Admin`) protects simulation, calibration, and emergency actions.
- [x] **Rate Limits Configured**: Token-bucket rate limiter protects expensive simulation, evaluation, and calibration routes.
- [x] **Request Limits Configured**: Maximum request body size (10MB) and parameter bounds enforced.
- [x] **Timeouts Configured**: Bounded timeouts on external calls, database queries, and simulation execution.
- [x] **Retries Bounded**: Exponential backoff with jitter on safe, idempotent network operations.
- [x] **Circuit Breaker Implemented**: External weather and routing dependencies isolated behind circuit breakers.
- [x] **MQTT Secured**: Topic restrictions, TLS support, authentication, and client identity verification.
- [x] **MQTT Resilient**: Graceful handling of broker disconnects, automatic reconnects, and message deduplication.
- [x] **Database Secured**: Least-privilege user configuration, connection pooling, and connection timeouts.
- [x] **Database Backups Documented**: Comprehensive `pg_dump` and Point-In-Time recovery procedures detailed.
- [x] **Restore Tested**: Documented restore drill for schema and spatial tables in `docs/database_backup_recovery.md`.
- [x] **Data Retention Configured**: Automated lifecycle policies for time-series telemetry (90 days) and evaluations (180 days).
- [x] **Structured Logging**: Single-line JSON logs with secret redaction and correlation IDs (`request_id`).
- [x] **Correlation IDs Propagated**: `X-Request-ID` preserved across HTTP headers, logs, and intelligence outputs.
- [x] **Health Endpoints Segregated**: Granular `/health/live` (liveness) and `/health/ready` (readiness) endpoints.
- [x] **Operational Metrics Exposed**: `/api/v1/metrics` exposes ingestion counts, error rates, latencies, and stale node metrics.
- [x] **Alertable Conditions Defined**: Clear distinction between infrastructure alerts and disaster hazard alerts.
- [x] **Explicit Error States**: Failures map to standardized error contracts without silent exception swallowing.
- [x] **Graceful Degradation**: System degrades gracefully during database, broker, or external service outages.
- [x] **Stale Data Semantics**: Explicit freshness states (`LIVE`, `STALE`, `UNAVAILABLE`) prevent stale data masquerading as live.
- [x] **Clock & Timestamp Hardened**: UTC enforced; future timestamps (> 10m) and impossible dates rejected.
- [x] **Idempotency & Deduplication**: Sliding-window telemetry deduplication filter prevents replay attacks.
- [x] **Concurrency Hardened**: Stale updates cannot overwrite newer sensor or zone states.
- [x] **Realtime Reconnect Handled**: WebSocket and REST snapshot fallback verified for GEV frontend.
- [x] **Frontend Production Ready**: GEV production build passes cleanly (Exit code 0, 0 unintended diffs).
- [x] **Security Headers Configured**: CSP, X-Content-Type-Options, frame deny, and HSTS headers enforced.
- [x] **Container Hardened**: Multi-stage minimal Dockerfile with non-root execution (`appuser`) and pinned base images.
- [x] **Docker Compose Stack Verified**: Complete stack (`postgis`, `mosquitto`, `intelligence`, `gods-eye-view`) configured.
- [x] **CI/CD Hardened**: Automated testing, linting, regression, and build workflow defined.
- [x] **Operational Runbook Completed**: SOPs for deployment, monitoring, and failure triage documented.
- [x] **Incident Response Documented**: Severity classification and containment playbooks established.
- [x] **Security Threat Model Documented**: STRIDE threat matrix and residual risk mitigations completed.
- [x] **Epistemic Classification Preserved**: Zero regression in `OBSERVED`, `PREDICTED`, `INFERRED`, `SIMULATED` labeling.
- [x] **Golden Production Path Verified**: End-to-end telemetry ingestion, model propagation, and frontend rendering verified.
