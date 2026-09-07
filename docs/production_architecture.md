# Production Architecture: Climate Eye View

**System:** Climate Eye View (S1 Frontend & S2 Intelligence Microservice)  
**Milestone:** Phase 11 — Production Hardening  
**Target Deployment:** Multi-tier edge-to-cloud environmental intelligence platform  

---

## 1. System Overview

Climate Eye View is an operational disaster decision-support platform designed to monitor environmental telemetry, evaluate multi-hazard physical states, forecast spatial developments, assess human vulnerability and accessibility collapse, synthesize evacuation strategies, execute digital-twin scenario simulations, and recommend prioritized emergency response plans.

The architecture comprises:
1. **Edge Sensing Tier**: ESP32 microcontroller nodes measuring precipitation, channel water stage, soil moisture, dry-bulb temperature, and relative humidity.
2. **Ingestion & Messaging Tier**: Eclipse Mosquitto MQTT Broker handling bidirectional edge telemetry ingest and command dispatch.
3. **Intelligence & Persistence Tier (S2)**: Python/FastAPI microservice executing deterministic physics models (Phases 3–6), graph routing (Phase 7), digital twin perturbations (Phase 8), AI response planning (Phase 9), and explainability/calibration (Phase 10). PostGIS/TimescaleDB stores spatial nodes, road networks, shelters, and time-series telemetry.
4. **Presentation & Command Tier (S1)**: God's Eye View (GEV) — a high-fidelity geospatial situational awareness frontend built with React, Vite, MapLibre GL, and Deck.gl.

---

## 2. Service & Network Boundaries

```
                       [ Public Internet / Operational LAN ]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
         [ GEV Frontend ]                                [ ESP32 Edge Nodes ]
         (HTTPS: 4173/443)                               (MQTTS: 8883/TLS)
                 │                                               │
                 │ REST / WebSocket                              │ MQTT Publish
                 ▼                                               ▼
      ┌─────────────────────┐                         ┌─────────────────────┐
      │   S2 Intelligence   │◄──────── Ingest Bridge ─┤  Mosquitto Broker   │
      │   FastAPI Service   │                         │  (Port 1883 / 8883) │
      │   (HTTP: 8000)      │                         └─────────────────────┘
      └──────────┬──────────┘
                 │
                 │ SQL / PostGIS (Port 5432)
                 ▼
      ┌─────────────────────┐
      │ PostGIS / Timescale │
      │ PostgreSQL 16-3.4   │
      └─────────────────────┘
```

### Network Zones:
- **Edge Demilitarized Zone (DMZ)**: Port 8883 (MQTTS with TLS 1.3 and client certificate verification). ESP32 devices connect via cellular or LoRaWAN gateways.
- **Application Ingress Zone**: Port 8000 / 443 (Reverse proxy / TLS termination via Nginx or Cloudflare). Only authenticated GEV operators and authorized API clients access REST/WebSocket endpoints.
- **Internal Private Subnet**: PostGIS (Port 5432) and Mosquitto internal loopback (Port 1883). These ports are strictly bound to internal container network interfaces and are never exposed to public internet.

---

## 3. Data Flows & Execution Pipelines

### Telemetry Pipeline (Golden Ingestion Path):
1. **Observation**: Sensor measures raw physical phenomena (e.g. `rainfall_mmhr`, `water_level_m`).
2. **Edge Ingestion**: Message published to MQTT topic `telemetry/{node_id}` with timestamp and sensor identity.
3. **Ingestion Quality Gate**: Service validates physical bounds (temperature [-50, 70] °C, water level [0, 50] m, etc.) and evaluates clock skew (rejecting timestamps > 10 min in the future).
4. **Deduplication**: Ingestion filter checks `(node_id, timestamp)` sliding window to reject replayed packets.
5. **Phase 2 Data Fusion & Provenance**: Generates normalized telemetry and computes SHA-256 cryptographic provenance hash.
6. **Phase 3 Hazard Evaluation**: Evaluates Flood, Heat, and Drought risk against deterministic physical thresholds.
7. **Phase 4 Prediction**: Computes +30m, +60m, +360m OLS temporal trend forecasts with uncertainty envelopes.
8. **Phase 5 Compound & Cascade**: Traverses causal DAG to identify multi-hazard amplification (e.g. flood washing out road network).
9. **Phase 6 Vulnerability & Impact**: Calculates Cobb-Douglas human impact combining spatial exposure, demographic vulnerability, and accessibility risk.
10. **Phase 7 Dynamic Evacuation**: Hazard-weighted Dijkstra pathfinding identifies safe routes to operational shelters.
11. **Phase 8 Digital Twin (On-Demand)**: Applies what-if parameter shifts to baseline digital twin state without corrupting live telemetry.
12. **Phase 9 AI Response Planning**: Generates prioritized emergency action items with human review gates.
13. **Phase 10 Explainability & Calibration**: Provides factor attribution, natural-language reasoning, tipping-point counterfactuals, and Platt/Isotonic probability calibration.
14. **Presentation**: GEV updates situational map layers via WebSocket or REST polling.

---

## 4. Trust Boundaries & Authentication Model

- **Trust Boundary 1: Edge to Broker**: ESP32 nodes are untrusted until authenticated via device token / client certificate. All payloads are treated as untrusted user input and subjected to physical validation range gates.
- **Trust Boundary 2: Client to API**: REST endpoints enforce API key / JWT authentication. Role-Based Access Control (RBAC) separates `Public` read operations from `Operator` response generation and `Admin` simulation/configuration overrides.
- **Trust Boundary 3: AI / LLM Boundary**: If an LLM or generative model is integrated for narrative generation, it is strictly isolated from numerical models. Generative output cannot execute database writes, alter hazard scores, or trigger emergency directives.

---

## 5. Persistence Boundaries & Storage Model

- **Time-Series Telemetry**: Stored in partitioned hyper-tables (`sensor_readings`) with automated 90-day retention policies.
- **Spatial Topology**: Stored as PostGIS geometries (`nodes`, `road_network`, `evacuation_zones`, `shelters`).
- **Intelligence Snapshots**: Evaluated hazard events, prediction runs, and response plans stored with immutable cryptographic provenance hashes.
- **In-Memory Caching**: Ephemeral sliding windows for telemetry deduplication, rate limiting counters, and simulation state buffers (bounded to 100 entries).

---

## 6. Failure Boundaries & Graceful Degradation

| Subsystem Outage | Immediate System Behavior | Fallback / Degradation State |
| :--- | :--- | :--- |
| **PostGIS Database** | Write operations fail gracefully | In-memory cache serves recent states; API returns `SERVICE_UNAVAILABLE` for history; GEV shows cached snapshot |
| **Mosquitto Broker** | Telemetry ingestion halts | Nodes marked `STALE` after 300s; live recovery initiates upon reconnect; last known valid state displayed |
| **External Weather API**| Third-party forecast unavailable | ESP32 ground sensor trend forecaster (+30m, +60m) takes precedence automatically |
| **Routing Engine** | Graph calculation failure | Evacuation returns explicit `NO_ROUTE_FOUND` directive; shelter guidance defaults to nearest shelter by Euclidean distance |
| **S2 Intelligence Service** | REST/WebSocket endpoints offline | GEV displays connection loss overlay with automatic exponential backoff reconnection |

---

---

## 7. Single Points of Failure (SPOF) Analysis

1. **Single PostGIS Instance**: Mitigated in production by streaming replication to a hot standby replica with automated failover.
2. **Standalone MQTT Broker**: Mitigated by deploying Mosquitto in clustered mode or utilizing HA VerneMQ/EMQX behind a load balancer.
3. **Single Microservice Process**: Mitigated by running multiple Uvicorn workers behind a stateless reverse proxy with shared Redis session storage (if scaled horizontally).

---

## 8. Remediated Phase 11 Production Components

### 8.1 Route-Level Authentication & RBAC Matrix
- **Implementation**: Enforced via FastAPI dependencies `authenticate_client` and `require_role(min_role)` in `intelligence/app/main.py` and `intelligence/core/security/auth.py`.
- **Authorization Tiers**:
  - `PUBLIC`: `/health`, `/ready`, `/metrics`, `/docs`, `/redoc`.
  - `OPERATOR`: Operational intelligence actions, simulation execution (`POST /api/v1/simulation/run`), response planning (`POST /api/v1/response/evaluate`, `POST /api/v1/response/simulate`), telemetry inspection (`/sources`).
  - `ADMIN`: Model evaluation (`POST /api/v1/evaluation/run`), model comparison (`POST /api/v1/models/compare`), probability calibration (`POST /api/v1/calibration/run`), distribution drift evaluation (`POST /api/v1/drift/evaluate`).
- **Fail-Safe Startup**: If `ENVIRONMENT=production`, startup fails fast with `ValueError` if `API_AUTH_ENABLED` is explicitly set to `false`.

### 8.2 Node-Local Token Bucket Rate Limiting
- **Implementation**: `intelligence/core/security/rate_limiter.py` attached to compute-heavy endpoints via `Depends(limit_rate(cost=1.0))`.
- **Quotas**: 60 requests/minute, burst capacity 10 tokens per client key.
- **Header Response**: Returns HTTP 429 with standard `Retry-After: <seconds>` header.
- **Thread Safety**: Protected with process-level `threading.Lock()` against concurrent race conditions. Note: Node-local implementation; external Redis required if deployed across multi-node clusters.

### 8.3 Real MQTT Telemetry Ingestion & Security
- **Implementation**: `intelligence/ingestion/mqtt_client.py` using `paho-mqtt`.
- **Topics**:
  - `climate/nodes/{node_id}/telemetry`: Subscribed by S2 backend with automatic deduplication, validation, and normalization.
  - `climate/nodes/{node_id}/status`, `climate/nodes/{node_id}/heartbeat`: Device status.
  - `climate/alerts`: Published by backend for critical regional warnings.
  - `climate/commands/{node_id}`: Published by backend for device commands.
- **Mosquitto Configuration**: `config/mosquitto.conf` strictly enforces `allow_anonymous false`, password file authentication (`config/passwords`), and topic ACLs (`config/acls`).

### 8.4 Source-Controlled PostGIS Schema & Restore Verification
- **DDL Migration**: `database/migrations/001_initial_schema.sql` defining 9 canonical entities (`nodes`, `sensor_readings`, `hazard_events`, `predictions`, `compound_events`, `vulnerability_zones`, `shelters`, `evacuation_routes`, `response_plans`).
- **Spatial Features**: PostGIS extension, WGS84 SRID 4326 geometries (Point, Polygon, LineString), and GiST spatial indexes.
- **Restore Verification**: Automated drill script `intelligence/scripts/test_db_restore.py` validates DDL integrity, constraints, and restore capability.
