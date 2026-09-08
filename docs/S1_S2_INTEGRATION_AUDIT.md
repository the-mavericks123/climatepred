# Climate Eye View — S1 + S2 Complete Integration Audit

**Author:** Antigravity Integration Agent  
**Date:** September 8, 2026  
**Status:** Authoritative Pre-Integration Audit Baseline  
**Authority:** Root S2 Repository & `Work/gods-eye-view` (S1 Implementation)  

---

## 1. Executive Summary

This audit establishes the comprehensive, verified architectural inventory of Software 1 (S1: God's Eye View platform, Cesium 3D globe visualization, frontend UI, client state, and transport gateway) and Software 2 (S2: Climate Intelligence, sensor fusion, 9 hazard/evacuation/response engines, PostGIS/relational database, and physical hardware validation).

No code or algorithm was assumed to work merely because documentation existed. Both codebases have been directly inspected, compiled, and tested:
- **S2 Python Baseline:** 748 pytest tests passing in 9.45s (0 failures, 0 skipped).
- **S1 Frontend Baseline:** Production Vite build succeeding in 5.99s (`dist/` generated cleanly).
- **S1 Climate Test Baseline:** 422 Node.js unit tests passing across all `src/climate` modules.

The primary architectural gap is the **501 Not Implemented boundary** in S1's API router (`Work/gods-eye-view/src/climate/server/api/router.js` lines 97–114) where intelligence routes were previously stubbed out, and the event bridge between S2's realtime broadcaster and S1's WebSocket transport.

---

## 2. Component Audit Matrix

| S1 Component | S2 Component | Current Interface | Conflict | Required Integration | Owner | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend Entry Point** (`src/main.js`, `src/ui.js`) | *None* (Headless backend) | Mounts `initClimateShell()`, initializes Cesium globe | None. S1 owns UI; S2 owns intelligence. | Maintain S1 entry point; trigger intelligence state sync. | S1 | **Verified** |
| **Cesium 3D Globe & Layers** (`src/climate/layers/`) | GeoJSON / Polygon outputs in S2 models | `initClimateLayers` renders node billboards & measurement heat | Hazard polygons, compound cascades, evacuation paths not yet drawn on 3D globe | Connect S2 GeoJSON/WKT outputs (zones, routes, hazards) to Cesium entity primitives | S1 | **Needs Layer Wiring** |
| **Frontend State Store** (`src/climate/state/climateState.js`) | Relational DB & in-memory engine state | Store has actions for hazards, predictions, compound, vulnerability, evacuation, response, simulation | S1 store reducers are fully implemented but rest controller only populated nodes/telemetry | Expand `syncClimateStateFromRest` to load intelligence results and subscribe to S2 events | S1 | **Store Ready / Needs Fetching** |
| **REST API Client** (`src/climate/api/client.js`) | FastAPI endpoints (`/api/v1/...`) | Relative paths: `/api/hazards/current`, `/api/compound`, etc. | S1 client expected `/api/...`; S2 serves `/api/v1/...` | S1 API Router acts as local adapter/proxy translating `/api/*` to S2 `/api/v1/*` | S1 | **Needs Adapter Routing** |
| **API Router & Handlers** (`src/climate/server/api/router.js`) | FastAPI app (`intelligence/app/main.py`) | Intercepts `/api/*`; returns HTTP 501 for intelligence & simulation routes | 501 Stubs block frontend from consuming actual S2 intelligence | Replace 501 handlers with proxy adapters calling S2 (`http://127.0.0.1:8000/api/v1/...`) | S1 Gateway | **Primary Integration Point** |
| **Realtime Transport** (`src/climate/server/realtime/server.js`) | Realtime Broadcaster (`intelligence/core/realtime/broadcaster.py`) | S1 serves WS on `/api/climate/stream`; S2 serves WS on `/api/v1/events/ws` and SSE on `/api/v1/events/stream` | S1 realtime server was isolated from S2 broadcast events | Connect S1 server to S2 event stream or bridge S2 events to S1 client websockets | S1 / S2 Bridge | **Primary Transport Point** |
| **MQTT Ingestion Client** (`src/climate/server/mqtt/adapter.js`) | S2 MQTT Client (`intelligence/ingestion/mqtt_client.py`) | Both subscribe to `climate/nodes/+/telemetry` | Potential duplicate subscription or split state if uncoordinated | S2 MQTT client is authoritative for normalization & provenance; S1 gateway can forward or share stream | S2 Ingestion | **Unified Telemetry Path** |
| **Database & Persistence** (`src/climate/server/db/`) | Intelligence Repository (`intelligence/database/repository.py`) | S1 stores nodes/readings in memory or PG; S2 stores all 9 entities | Two separate database repositories | S2 `IntelligenceRepository` is authoritative for all 9 entities; S1 reads via S2 API | S2 DB | **S2 Authoritative** |
| **Hazard Engine (Heat/Flood/Drought)** | S2 Hazard Models (`intelligence/hazards/`) | S1 stubs `/api/hazards/current` with 501; S2 provides `POST /api/v1/hazards/evaluate` | S1 cannot see evaluated hazards | S1 router maps `GET /api/hazards/current` to S2 hazard engine evaluation | S2 Engine | **Needs S1 Route Adapter** |
| **Prediction Engine (+30/+60/+360m)** | S2 Prediction Models (`intelligence/predictions/`) | S1 stubs `/api/hazards/predictions` with 501; S2 provides `POST /api/v1/predictions/evaluate` | S1 cannot see multi-horizon predictions | S1 router maps `GET /api/hazards/predictions` to S2 prediction evaluation | S2 Engine | **Needs S1 Route Adapter** |
| **Compound Disaster Engine** | S2 Cascade Engine (`intelligence/compound/`) | S1 stubs `/api/compound` with 501; S2 provides `POST /api/v1/compound/evaluate` and `GET /api/v1/compound-events/current` | S1 cannot see causal chains | S1 router maps `GET /api/compound` to S2 compound events; UI renders causal chain | S2 Engine | **Needs S1 Route Adapter** |
| **Human Vulnerability Engine** | S2 SVI Engine (`intelligence/vulnerability/`) | S1 stubs `/api/vulnerability` with 501; S2 provides `GET /api/v1/vulnerability/zones` | S1 cannot answer "Who is affected?" | S1 router maps `GET /api/vulnerability` to S2 vulnerability zones | S2 Engine | **Needs S1 Route Adapter** |
| **Dynamic Evacuation Engine** | S2 A* Routing (`intelligence/evacuation/`) | S1 stubs `/api/evacuation` with 501; S2 provides `GET /api/v1/evacuation/current` and `GET /api/v1/evacuation/routes` | S1 cannot display safe routes | S1 router maps `GET /api/evacuation` to S2 evacuation routes; preserves `NO_ROUTE` | S2 Engine | **Needs S1 Route Adapter** |
| **Response Planner Engine** | S2 Decision Engine (`intelligence/response/`) | S1 stubs `/api/response` with 501; S2 provides `GET /api/v1/response/current` | S1 cannot show alert level & prioritized action list | S1 router maps `GET /api/response` to S2 response plan; renders actionable cards | S2 Engine | **Needs S1 Route Adapter** |
| **Digital Twin Simulation** (`src/climate/panels/`) | S2 Simulation Engine (`intelligence/simulation/`) | S1 stubs `/api/simulation/scenarios` and `/api/simulation/run` with 501; S2 provides both endpoints | S1 simulation UI cannot execute what-if runs | S1 router proxies scenarios & runs to S2; tags output `SIMULATED: true` | S1 UI / S2 Sim | **Needs S1 Route Adapter** |
| **Explainability Engine** | S2 Factor Attribution (`intelligence/explainability/`) | S2 exposes `/api/v1/explainability/...`; S1 had no route | S1 lacks inspection route for "Why did the system say this?" | Add S1 route `/api/explainability/:type/:id` forwarding to S2 | S2 Engine | **Needs S1 Route Adapter** |
| **Security & RBAC** | S2 Auth Guard (`intelligence/core/security/auth.py`) | S2 enforces OPERATOR role for simulation/run and response/eval; rate limits | Missing credentials from S1 client could trigger HTTP 401 | S1 gateway propagates operator token / API key for privileged actions | S2 Security | **Preserve RBAC** |
| **Epistemic Semantics** | Ingestion & Telemetry Contracts | S1 and S2 both define status badges | Inadvertent mock data or fake zero water level | Strictly enforce `water_level = null` on live telemetry, `UNAVAILABLE` status, and badges | S1 / S2 | **Enforce Invariants** |

---

## 3. Telemetry & Ingestion Architecture

### Verified Physical Hardware BOM
1. ESP32 MCU (Espressif Systems)
2. GY-GPS6MV2P GPS Module
3. LM2596 Step-Down Power Converter (Power regulator only — not a telemetry metric)
4. Raindrop Module (LM393 analog comparator — unverified empirical conversion)
5. GP2Y1010AU0F Optical Dust Sensor (Pulsed LED, PM2.5 calculation — unverified)
6. BH1750 Ambient Light Sensor (I2C lux reading)
7. BMP280 Barometric Pressure Sensor (I2C calibrated sensor)
8. LoRa RA-02 RF Transceiver (SX1278 SPI communication module — not telemetry)
9. DHT11 Temperature & Humidity Sensor (1-Wire low-precision)
10. Soil Moisture Sensor (Analog resistive probe — two-point calibration required)

### The Water-Level Invariant
The physical hardware contains **no water-level sensor**.
- Live physical telemetry MUST report: `water_level = null` and `sensor_status.water_level = "UNAVAILABLE"`.
- Under no circumstances will the system inject `water_level = 0.0`.
- If the live flood model requires water level, it returns `HazardStatus.UNAVAILABLE`, `severity = 0.0`, `confidence = 0.0`.
- Synthetic water level is admissible **ONLY** in digital twin simulation runs and fixtures explicitly flagged with `simulated = true`.

---

## 4. Architectural Ownership & Boundaries

```
+-------------------------------------------------------------------------+
|                        SOFTWARE 1 (S1) PLATFORM                         |
|  Location: Work/gods-eye-view (also mirrored in root gods-eye-view)     |
|                                                                         |
|  Responsibilities:                                                      |
|   - God's Eye View 3D Globe (CesiumJS) & Camera Controls                |
|   - UI Shell: TopNav, LeftPanel, RightPanel, StatusBar, MeshPanel       |
|   - Visualization Layers: Sensor Nodes, Metric Contours, GeoJSON        |
|   - Frontend Store: Pure deterministic Redux-style store (climateState) |
|   - Client Transport: WebSocket client with backoff & snapshot recovery |
|   - API Gateway / Adapter: Connect middleware proxying /api/* to S2     |
+-------------------------------------------------------------------------+
                                    │
                                    │ REST (HTTP) / WebSocket / SSE
                                    ▼
+-------------------------------------------------------------------------+
|                     SOFTWARE 2 (S2) INTELLIGENCE                        |
|  Location: intelligence/                                                |
|                                                                         |
|  Responsibilities:                                                      |
|   - Canonical Telemetry Normalization & Physical Range Validation       |
|   - Cryptographic Provenance Tracking (SHA-256 state hashing)           |
|   - Authoritative Hazard Engines: Heat, Flood, Drought                  |
|   - Multi-Horizon Hazard Prediction (+30m, +60m, +360m)                  |
|   - Compound & Cascading Disaster Graph Reasoner                        |
|   - Social Vulnerability Index (SVI) & Human Impact Evaluation          |
|   - Dynamic Evacuation Route Optimization (A* & Capacity)              |
|   - Digital Twin Scenario Simulator (Isolated hypothetical runs)        |
|   - Automated Emergency Response Planner (Alerts & HITL Actions)        |
|   - Explainability & Counterfactual Analysis Engine                     |
|   - Unified Relational Persistence (SQLite / PostGIS 9-table schema)    |
|   - Realtime Broadcaster (WebSocket & SSE multi-subscriber hub)         |
+-------------------------------------------------------------------------+
```

---

## 5. Implementation Roadmap

1. **S1 Backend Adapter (`router.js` & `handlers.js`):**
   Implement HTTP proxying to S2 FastAPI endpoints with standard JSON envelope normalization and error mapping.
2. **Realtime Event Bridge:**
   Bridge S2 WebSocket/SSE events into S1's `ClimateRealtimeServer` so browser clients receive live intelligence broadcasts.
3. **Frontend Intelligence Synchronization:**
   Enhance `syncClimateStateFromRest` to query current hazards, predictions, compound cascades, vulnerability zones, evacuation routes, and response plans on startup.
4. **UI Intelligence Binding:**
   Bind the Right Panel Threat Card ("Current Conditions") and AI Agent Card to authoritative `climateState` values rather than static placeholder strings.
5. **Cesium 3D Layer Integration:**
   Render hazard impact zones and evacuation routes on the Cesium globe.
6. **End-to-End Golden Verification:**
   Verify full pipeline from Telemetry -> MQTT -> Ingestion -> Normalization -> Database -> Hazards -> Predictions -> Compound -> Vulnerability -> Evacuation -> Response -> Explainability -> Realtime -> Frontend/GEV.
