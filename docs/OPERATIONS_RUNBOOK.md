# Climate Eye View: Operational Runbook

**Audience:** System Operators, DevOps Engineers, and Emergency Coordinators  
**Milestone:** Phase 11 — Production Hardening  

---

## 1. Service Management & Lifecycle

### Starting the Stack
```bash
# Start all microservices in detached mode
docker compose up -d

# Verify container health status
docker compose ps
```

### Stopping the Stack
```bash
# Graceful shutdown with 30s timeout
docker compose down --timeout 30
```

### Service Health Verification
- **Liveness Probe**: `GET http://localhost:8000/api/v1/health/live`  
  *Expectation*: HTTP 200 `{"status": "ALIVE"}` (indicates process is responsive).
- **Readiness Probe**: `GET http://localhost:8000/api/v1/health/ready`  
  *Expectation*: HTTP 200 `{"status": "READY", "database": "CONNECTED", "mqtt": "CONNECTED"}`.
- **Operational Metrics**: `GET http://localhost:8000/api/v1/metrics`  
  *Exposes*: Ingestion rates, latency histograms, error counts, stale node metrics.

---

## 2. Common Failure Modes & Remediation

### 2.1 Stale Telemetry Alarm
- **Symptoms**: GEV displays yellow/amber badges on nodes; alert log reports `STALE_TELEMETRY (age > 300s)`.
- **Diagnostic Steps**:
  1. Inspect MQTT ingestion logs: `docker compose logs --tail=100 mosquitto`
  2. Verify edge node network connectivity (cellular/LoRaWAN gateway status).
  3. Query latest sensor observation timestamp:
     ```bash
     curl -s http://localhost:8000/api/v1/telemetry/nodes | jq '.[] | {id: .node_id, age: .freshness_age_seconds}'
     ```
- **Remediation**:
  - If a physical sensor battery or transmitter failed, dispatch field technicians. The intelligence engine automatically flags the node as `STALE` and penalizes forecast confidence.

### 2.2 Database Connection Outage
- **Symptoms**: Readiness probe reports `database: DISCONNECTED`; write operations fail with `DATABASE_UNAVAILABLE`.
- **Diagnostic Steps**:
  1. Check PostGIS container: `docker compose ps postgis`
  2. Inspect PostgreSQL log files for disk full or connection exhaustion:
     `docker compose logs --tail=50 postgis`
- **Remediation**:
  1. Restart PostGIS container: `docker compose restart postgis`
  2. The S2 intelligence service connection pool will automatically reconnect with exponential backoff.
  3. GEV will continue serving cached snapshots until database recovery is complete.

### 2.3 MQTT Ingestion Crash / Broker Disconnect
- **Symptoms**: Incoming telemetry drops to zero; intelligence service reports `MQTT_DISCONNECTED`.
- **Diagnostic Steps**:
  1. Verify broker process: `docker compose ps mosquitto`
  2. Test local MQTT loopback publish:
     ```bash
     mosquitto_pub -h localhost -p 1883 -t "telemetry/test_node" -m '{"test": true}'
     ```
- **Remediation**:
  1. Restart broker: `docker compose restart mosquitto`
  2. S2 client will automatically re-subscribe to all telemetry topics within 10 seconds.

### 2.4 High Error Rate / Rate Limiting Spike
- **Symptoms**: HTTP 429 errors returned to clients; metrics report high `rate_limit_exceeded_count`.
- **Remediation**:
  - Identify abusive IP or client token from structured logs:
    ```bash
    docker compose logs intelligence | grep "RATE_LIMIT_EXCEEDED"
    ```
  - Adjust rate limits in `config/app.yaml` or `.env` if operational demand has legitimately escalated during a disaster drill.

---

## 3. Log Analysis & Observability

All production logs are formatted as single-line structured JSON records. To inspect operational traces:
```bash
# Filter errors only
docker compose logs -f intelligence | jq 'select(.level == "ERROR")'

# Trace specific request by correlation ID
docker compose logs -f intelligence | jq 'select(.request_id == "REQ-12345678")'

# Check model execution versions
docker compose logs -f intelligence | jq '{timestamp, endpoint, model_version, duration_ms}'
```

---

## 4. Configuration Changes & Hot Reloading

- Environmental updates (`.env`) require a graceful container restart:
  ```bash
  docker compose up -d --no-deps intelligence
  ```
- Startup validator will immediately abort launch if invalid configurations (e.g. wildcard CORS in production) are detected.
