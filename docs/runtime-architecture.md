# Climate Eye View — Real Runtime Topology & Architecture

**Document Version:** 1.0.0  
**Phase:** Phase 12 — Full S2 Integration + Acceptance  
**Status:** Verified Operational Baseline  
**Date:** September 8, 2026  

---

## 1. System Overview

Climate Eye View integrates an edge sensor telemetry layer (ESP32/MQTT), a real-time message broker, a high-performance Python FastAPI intelligence microservice (Software 2), an authoritative PostGIS spatial persistence tier, and a 3D browser-based geospatial digital twin (Software 1 / God's Eye View).

The system architecture enforces strict epistemic segregation across:
- **`OBSERVED`**: Real-time physical sensor readings, current-state hazard evaluations, and detected field measurements.
- **`PREDICTED`**: Machine learning and statistical trend nowcasts across strictly defined horizons (+30m, +60m, +360m).
- **`INFERRED`**: Compound cascade graphs, human vulnerability indices, and calculated evacuation routes.
- **`SIMULATED`**: Counterfactual digital-twin scenarios (`simulated=true`), strictly segregated from live authoritative operational state.

---

## 2. Component Topology Matrix

The following table documents the real runtime components, their network bindings, protocols, data flows, and failure postures:

| Component | Purpose | Port | Protocol | Input | Output | Dependencies | Failure Behavior |
|---|---|---|---|---|---|---|---|
| **Frontend UI (GEV)** | 3D Cesium globe visualizer, HUD telemetry display, layer manager, evacuation corridor rendering | `4173` | HTTP / ESM (Vite Dev / Static CDN) | User interactions, S2 GeoJSON/JSON responses, WebSocket events | Cesium WebGL graphics, DOM HUD cards, layer toggles | Modern browser (WebGL 2.0), S2 API | **Graceful degradation**: Globe and cached basemaps remain interactive. Missing feeds display `'UNAVAILABLE'` / `'KEY REQUIRED'` without crashing the renderer. |
| **Backend / S2 Intelligence API** | Core computational microservice: validation, provenance hashing, multi-hazard modeling, prediction, compound DAGs, vulnerability, evacuation routing, response planning, explainability | `8000` | HTTP / REST & WebSocket / SSE | Normalized telemetry, spatial graphs, demographic profiles, scenario changes | GeoJSON FeatureCollections, risk vectors, response action plans, explanations | Python 3.11+, SourceRegistry, FastAPI, Pydantic | **Bounded resilience**: Returns standardized error envelopes (`ErrorResponse`) with HTTP 4xx/5xx status codes; does not expose internal stack traces or corrupt active state. |
| **MQTT Broker (Mosquitto)** | Message broker ingesting asynchronous hardware telemetry packets published by edge sensing units | `1883` | MQTT v3.1.1 / v5.0 (TCP) | Raw telemetry JSON packets published to `climate/nodes/{node_id}/telemetry` | Fanout delivery to subscribed `ClimateMqttClient` instances | TCP network, local or containerized Mosquitto daemon | **Disconnection tolerance**: Clients back off with exponential retry (1.0s to 30.0s). Ingestion marks nodes as `STALE` if heartbeat expires. HTTP API continues unaffected. |
| **Edge Hardware (ESP32 Nodes)** | Physical / simulated IoT sensing nodes sampling ambient conditions (temperature, humidity, pressure, rainfall, soil moisture, water level, air quality, battery) | N/A (Client) | MQTT over Wi-Fi (QoS 1) | Microcontroller sensor ADC/I2C/SPI readings | Formatted JSON packets published to `climate/nodes/{node_id}/telemetry` | Wi-Fi Access Point, Mosquitto Broker | **Self-healing retry**: Reconnects to Wi-Fi/broker on link drop. Preserves sensor readings in local RTC buffer or drops unacknowledged frames safely. |
| **Authoritative Database (PostGIS)** | Spatial database holding source-controlled tables for nodes, telemetry time-series, hazard events, predictions, compound disasters, vulnerability zones, shelters, routes, and response plans | `5432` | TCP (PostgreSQL wire protocol) | SQL DDL / DML commands conforming to `database/migrations/001_initial_schema.sql` | Relational query results, spatial indexes (GiST), time-ordered slices | PostGIS extension, storage volume | **Circuit breaking**: If database connection is unavailable, in-memory repository caches operational state while reporting `DATABASE_UNAVAILABLE` in health checks. |
| **Realtime Event Transport** | Event distribution broker broadcasting push notifications to connected frontend clients | `8000` (`/api/v1/events/ws`, `/api/v1/events/stream`) | WebSocket (`ws://`) & Server-Sent Events (`text/event-stream`) | Internal domain events (`telemetry.updated`, `hazard.updated`, `prediction.updated`, etc.) | JSON event frames: `{"event_id", "event_type", "timestamp", "data"}` | S2 FastAPI process, ASGI event loop | **Non-blocking fallback**: If client disconnects or buffer fills, connection is dropped without interrupting analytical processing loops. GEV falls back to polling. |
| **External Data Providers** | Third-party auxiliary feeds (Open-Meteo weather, USGS earthquakes, NASA FIRMS fire detections, TomTom traffic) | `443` (Outbound) | HTTPS / REST | Geocoordinates, bounding boxes | External JSON / CSV payloads | External provider networks and API quotas | **Explicit provenance penalty**: Unavailable APIs do NOT halt pipeline; source marked `'UNAVAILABLE'`, external confidence set to 0.0, and sensor-only evaluation continues. |
| **Digital Twin Simulation Engine** | In-process counterfactual engine running hypothetical hazard perturbations (+20%, +40%, +60% rainfall, extreme heat, drainage failure) | In-Process (S2) | Synchronous / Async Python function calls | Baseline state + parameter overrides (`ScenarioParameters`) | `SimulationResult` with `simulated=true` | S2 Core Engines (Hazards, Predictions, Compound, Vulnerability, Evacuation, Response) | **Epistemic Isolation**: Simulation outputs cannot mutate authoritative live database records or active operational alerts. |

---

## 3. End-to-End Runtime Pipeline

```
[ ESP32 Sensor Node / Real Publisher ]
                 │
                 │ WiFi / MQTT (QoS 1, Topic: climate/nodes/{node_id}/telemetry)
                 ▼
        [ Mosquitto Broker:1883 ]
                 │
                 │ TCP Stream
                 ▼
    [ ClimateMqttClient (Thread-safe Paho Subscriber) ]
                 │
                 ├─► Deduplication (SHA-256 / sliding window cache)
                 ├─► TelemetryValidator (Pydantic contract + physical bounds)
                 ├─► NormalizedAdapter (Canonical schema + SourceRegistry heartbeat)
                 │
                 ├──► [ Database Repository / PostGIS ] (sensor_readings)
                 │
                 └──► [ RealtimeBroadcaster ] ──► WebSocket / SSE (telemetry.updated)
                             │
                             ▼
                 [ Core Intelligence Pipeline ]
                 ├── 1. HazardEngine (Heat, Flood, Drought - Current State)
                 │         └──► Broadcast: hazard.updated
                 ├── 2. PredictionEngine (+30m, +60m, +360m horizons)
                 │         └──► Broadcast: prediction.updated
                 ├── 3. CompoundEngine (DAG multi-hazard cascade)
                 │         └──► Broadcast: compound.updated
                 ├── 4. VulnerabilityEngine (Hazard × Exposure × Vulnerability × Access)
                 │         └──► Broadcast: vulnerability.updated
                 ├── 5. EvacuationEngine (Dynamic Dijkstra rerouting on road cut-off)
                 │         └──► Broadcast: evacuation.updated
                 ├── 6. ResponseEngine (Action synthesis, priority, HITL requirements)
                 │         └──► Broadcast: response.updated
                 └── 7. ExplainabilityEngine (Attribution, drivers, counterfactuals)
                             │
                             ▼
                 [ GEV 3D Globe Frontend:4173 ]
                 ├── Sensors Layer (CustomDataSource Billboards + WorldOverlay)
                 ├── Hazard Contours & Polygons (Clamped GeoJSON)
                 ├── Prediction Vectors (+30m, +1h, +6h scrubber)
                 ├── Compound Cascade Links
                 ├── Vulnerability Extruded Polygons
                 ├── Dynamic Evacuation Corridors (Green/Red cut-offs)
                 └── Emergency Response Action HUD
```

---

## 4. Port and Process Configuration

| Process | Working Directory | Launch Command | Target Port |
|---|---|---|---|
| **S2 Intelligence Service** | `.` | `.venv/bin/uvicorn intelligence.app.main:app --host 0.0.0.0 --port 8000` | `8000` |
| **S1 GEV Frontend** | `gods-eye-view` | `npm run dev` (or `npm run preview` on `dist/`) | `4173` |
| **MQTT Broker** | Root / Docker | `mosquitto -c config/mosquitto/mosquitto.conf` | `1883` |
| **PostgreSQL / PostGIS** | Root / Docker | `docker compose up postgis` | `5432` |

---

## 5. Security & Authentication Boundaries

1. **Edge-to-Broker**: Username/Password authentication over MQTT; strict topic access enforcement (`climate/nodes/+/telemetry`).
2. **Client-to-API**: Bearer JWT / API Key tokens validated through `Role` hierarchy (`ADMIN`, `OPERATOR`, `ANALYST`, `VIEWER`).
3. **Rate Limiting**: Sliding-window rate limiting enforcing per-client quotas (e.g. 10 requests / 1-second burst window with `Retry-After` headers).
4. **Input Sanitization**: Request bodies restricted to 10 MB maximum payload size, hardened with Content-Security-Policy, HSTS, X-Frame-Options, and X-Content-Type-Options headers.
