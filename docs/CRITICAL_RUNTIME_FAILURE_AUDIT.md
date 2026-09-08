# Climate Eye — Critical Runtime Failure Forensic Audit

**Date**: September 9, 2026  
**Investigator**: Antigravity Autonomous Coding Agent  
**Target Systems**: Software 1 (S1 — Vite / Node.js Connect Dev Server) & Software 2 (S2 — FastAPI Python 3.13 Intelligence Microservice)  
**Status**: Root causes identified, verified via network and process telemetry.

---

## 1. Executive Summary of Root Causes

Forensic investigation of the live runtime environment revealed three compounding root causes:

1. **S2 FastAPI Intelligence Microservice Was Inactive**:
   - The Vite frontend server (S1) runs on port `5173`.
   - All REST requests to `/api/simulation/run`, `/api/v1/global/ai-query`, `/api/v1/global/region`, `/api/hazards/current`, etc., are intercepted by S1's API router (`vite-plugin-climate-server` -> `createClimateApiRouter`) and forwarded via `forwardToS2` to `http://127.0.0.1:8000`.
   - However, **no background process was listening on port `8000`**.
   - Every request to simulation and AI failed with `HTTP 503 Service Unavailable`:
     ```json
     {"ok":false,"error":"S2 Intelligence service unavailable at http://127.0.0.1:8000: fetch failed","code":"MODEL_UNAVAILABLE","details":{"targetUrl":"http://127.0.0.1:8000/api/v1/simulation/run"}}
     ```
   - In the frontend UI, `controller.runSimulationScenario()` caught this 503 error and rendered `SIMULATION FAILED`. In AI Command, `queryAiDirective()` failed silently or showed fallback without live reasoning.

2. **Geographic Globe Picking & Selection Missing**:
   - In `src/climate/layers/globalHazardsLayer.js`, the Cesium `LEFT_CLICK` event handler only checked `viewer.scene.pick(movement.position)` for hazard polygons. When the user clicked anywhere on the globe surface, it executed `hidePopover()` and completely ignored the clicked Cartesian coordinates.
   - In `src/climate/panels/topNav.js`, `navigateToLocation` fell back to hardcoded Hyderabad coordinates whenever an unlisted location was searched.
   - There was no bidirectional binding between Cesium globe clicks, geocoding, application store `selectedRegion`, and backend regional telemetry queries.

3. **Simulation & AI Region Decoupling**:
   - `runSimulationScenario` was passing a fallback string `'Hyderabad'` instead of dynamically reading the active `store.getState().selectedRegion`.
   - S2's `/api/v1/simulation/run` and `/api/v1/global/ai-query` require dynamic regional context (coordinates, name, observed weather) to ground hypothetical perturbations and answers in the user's selected location.

---

## 2. Actual Runtime Topology

```
┌──────────────────────────────────────────────────────────────┐
│                    BROWSER RUNTIME (S1)                      │
│   Cesium 3D Earth  ·  TopNav  ·  Left Rail  ·  Right Panel   │
│                 http://localhost:5173                        │
└──────────────────────────────┬───────────────────────────────┘
                               │ Fetch /api/* & WS
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    S1 DEV GATEWAY (Node)                     │
│               Vite Dev Server (Port 5173)                    │
│        - `vite-plugin-climate-server` (server/index.js)       │
│        - `createClimateApiRouter` (router.js)                │
│        - `forwardToS2` (handlers.js)                         │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP Proxy (http://127.0.0.1:8000)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                 S2 INTELLIGENCE ENGINE (Python)              │
│               FastAPI / Uvicorn (Port 8000)                  │
│        - `/api/v1/simulation/run` (Phase 2-9 Models)         │
│        - `/api/v1/global/ai-query` (Grounded Reasoning)      │
│        - `/api/v1/global/region` (Open-Meteo Telemetry)      │
│        - `/api/v1/events/ws` (WebSocket Realtime)            │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Network Endpoint Audit & Payloads

| Function | Frontend Endpoint | S2 Upstream Path | S2 Status (Pre-Fix) | S2 Status (Running) |
|---|---|---|:---:|:---:|
| **Health Check** | `GET /api/climate/health` | Served by S1 | HTTP 200 | HTTP 200 |
| **Run Simulation** | `POST /api/simulation/run` | `POST /api/v1/simulation/run` | HTTP 503 (ECONNREFUSED) | HTTP 200 |
| **AI Query** | `POST /api/v1/global/ai-query` | `POST /api/v1/global/ai-query` | HTTP 503 (ECONNREFUSED) | HTTP 200 |
| **Region Telemetry** | `GET /api/v1/global/region` | `GET /api/v1/global/region` | HTTP 503 (ECONNREFUSED) | HTTP 200 |
| **Realtime Stream** | `ws://localhost:5173/api/climate/stream` | `ws://127.0.0.1:8000/api/v1/events/ws` | S1 Inactive | Connected |

### Detailed Payload Traces

#### A. Simulation Endpoint (`POST /api/simulation/run`)
- **Request Payload**:
  ```json
  {
    "scenario_id": "SCN-RAIN-40",
    "base_state": "current",
    "region": "Hyderabad",
    "changes": {
      "rainfall_multiplier": 1.4,
      "temperature_delta": 2.0,
      "drainage_failure_severity": 0.5,
      "road_accessibility_reduction": 0.5
    }
  }
  ```
- **Observed Failure (Before S2 Startup)**:
  `HTTP 503 Service Unavailable`
  `{"ok":false,"error":"S2 Intelligence service unavailable at http://127.0.0.1:8000: fetch failed"}`
- **Verified Success (With S2 Running)**:
  `HTTP 200 OK`
  ```json
  {
    "success": true,
    "simulation": {
      "simulation_id": "SIM-SCN-RAIN-40-0A409092",
      "scenario_id": "SCN-RAIN-40",
      "scenario_version": "1.0",
      "timestamp": "2026-09-08T19:12:27.653311+00:00",
      "simulated": true,
      "base_state_id": "STATE-HYDERA-BASELINE",
      "hazards": [ ... ],
      "predictions": [ ... ],
      "compound": { ... },
      "human_impact": { ... },
      "evacuation": { ... }
    }
  }
  ```

#### B. AI Query Endpoint (`POST /api/v1/global/ai-query`)
- **Request Payload**:
  ```json
  {
    "question": "What is happening in this region?",
    "region": {
      "name": "Hyderabad",
      "latitude": 17.385,
      "longitude": 78.4867
    }
  }
  ```
- **Observed Failure (Before S2 Startup)**:
  `HTTP 503 Service Unavailable`
- **Verified Success (With S2 Running)**:
  `HTTP 200 OK`
  ```json
  {
    "success": true,
    "answer": {
      "headline": "OPERATIONAL ASSESSMENT: HEAT IMPACT IN HYDERABAD",
      "summary": "Active telemetry indicates an elevated HEAT condition at 65% severity. Approximately 1.2M citizens are exposed in the affected sector with 68% Social Vulnerability Index. Forward projections anticipate risk escalation over the next 6 hours.",
      "primary_hazard": "HEAT",
      "severity": 0.65,
      "exposed_population": "1.2M",
      "actions": [
        "1. Issue advisory broadcast across Hyderabad municipal notification channels.",
        "2. Pre-position civil response units along Arterial Corridor 4.",
        "3. Verify readiness of Designated Safe Shelter.",
        "4. Enforce avoidance perimeter around Lowland Causeway."
      ],
      "evidence_ids": ["HAZ-101", "PRED-204", "COMP-032", "VUL-087", "EVAC-019"],
      "epistemic_status": "DETERMINISTIC_EVALUATION"
    }
  }
  ```

---

## 4. Remediation Plan

1. **Process Supervision**:
   - Ensure S2 FastAPI is started and maintained (`.venv\Scripts\python.exe -m uvicorn intelligence.app.main:app --host 127.0.0.1 --port 8000`).
2. **Geographic Globe Interaction**:
   - Implement Cesium screen space event handler for globe clicking on `Cesium.ScreenSpaceEventType.LEFT_CLICK`.
   - Convert pick Cartesian to Cartographic (lat/lon).
   - Implement reverse geocoding to resolve city/locality/subdivision/country.
   - Implement dynamic forward geocoding for the search bar (supporting any global location, e.g. Paris, Tokyo, Mumbai, London, New York).
3. **Selected Region State Management**:
   - Dispatch `store.dispatch({ type: 'SELECTED_REGION_UPDATED', payload: region })`.
   - Render a prominent, persistent `SELECTED REGION` HUD component.
   - Pass the selected region's coordinates and metadata directly into:
     - Regional intelligence API (`GET /api/v1/global/region`)
     - Simulation engine (`POST /api/simulation/run`)
     - AI query engine (`POST /api/v1/global/ai-query`)
4. **Spatial Hazard Zone Rendering**:
   - Dynamically render hazard zones, disaster perimeters, and evacuation corridors around the selected location.
   - Visibly scale and mark entities with `SIMULATED` when a simulation is applied.
5. **Browser Verification**:
   - Test all 10 AI queries, location search, globe clicks, and simulation execution via real browser runtime interaction.
