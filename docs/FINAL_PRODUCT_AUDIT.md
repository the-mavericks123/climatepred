# Climate Eye View — Final Product Audit & Runtime Architecture

## Date: 2026-09-08
## Phase: Phase 0 — Pre-Implementation Inspection

---

## 1. Executive Summary

This document establishes the authoritative pre-modification audit of the Climate Eye View repository prior to final hackathon implementation. The current system possesses mature, mathematically rigorous S2 Python intelligence engines (Hazards, Predictions, Compound Cascades, Vulnerability, Dynamic Evacuation, Response Planning, Explainability, Scenario Simulation, and Global External Data Feeds) and an operational CesiumJS 3D photorealistic globe frontend.

The objective of the final transformation is to synthesize these functional components into a unified, high-density **Planetary Climate + Disaster Intelligence Command Center** matching the reference UI design.

---

## 2. Existing Working Components

| Subsystem | Location | Runtime Port / Tech | Operational Status |
| :--- | :--- | :--- | :--- |
| **S2 Intelligence Service** | `intelligence/` | `127.0.0.1:8000` (FastAPI / Uvicorn) | **OPERATIONAL** (788/788 pytest pass) |
| **Global External Data** | `intelligence/external_data/` | Python async background scheduler | **ONLINE** (5 providers integrated) |
| **GEV 3D Globe Frontend** | `gods-eye-view/` | `localhost:4173` (Vite / CesiumJS 1.124) | **OPERATIONAL** (440/440 tests pass) |
| **Climate State Store** | `src/climate/state/` | Vanilla JS / Immutable Reducer | **ACTIVE** (13 domains tracked) |
| **Realtime Broadcaster** | `intelligence/core/realtime/` | WebSockets (`/api/v1/events/ws`) & SSE | **READY** |
| **Edge Ingestion / MQTT** | `intelligence/ingestion/` | Paho MQTT / Async TLS client | **STANDBY / OPTIONAL** |
| **Dual Parity Directory** | `Work/gods-eye-view/` | Mirrored codebase | **SYNCHRONIZED** (440/440 tests pass) |

---

## 3. Existing APIs & Endpoints

### 3.1. S2 Intelligence Service (`intelligence/app/main.py`)
- **Health & Readiness**:
  - `GET /api/v1/health`, `GET /health`
  - `GET /api/v1/health/live`, `GET /api/v1/health/ready`
  - `GET /api/v1/metrics`, `GET /metrics`
- **Realtime Streams**:
  - `WS /api/v1/events/ws`, `WS /ws/climate`
  - `GET /api/v1/events/stream`, `GET /api/v1/events/history`
- **Telemetry & Nodes**:
  - `POST /api/v1/telemetry/validate`, `POST /api/v1/telemetry`
  - `GET /api/v1/nodes`, `GET /api/v1/telemetry`
- **Hazards & Predictions**:
  - `POST /api/v1/hazards/evaluate`, `GET /api/v1/hazards/current`
  - `POST /api/v1/predictions/evaluate`, `GET /api/v1/hazards/predictions`
- **Compound Cascade & Vulnerability**:
  - `POST /api/v1/compound/evaluate`, `GET /api/v1/compound-events/current`
  - `POST /api/v1/vulnerability/evaluate`, `GET /api/v1/vulnerability/zones`
- **Evacuation & Response Planning**:
  - `POST /api/v1/evacuation/evaluate`, `GET /api/v1/evacuation/routes`, `GET /api/v1/evacuation/current`
  - `POST /api/v1/response/evaluate`, `GET /api/v1/response/current`
- **Scenario Simulation**:
  - `GET /api/v1/simulation/scenarios`
  - `POST /api/v1/simulation/run` (Accepts `scenario_id`, `changes`, `base_state`)
- **Explainability**:
  - `GET /api/v1/explainability/{target_type}/{target_id}`
  - `POST /api/v1/explainability/generate`
- **Global External Feeds (`intelligence/external_data/router.py`)**:
  - `GET /api/v1/global/sources`
  - `GET /api/v1/global/hazards`
  - `GET /api/v1/global/events`
  - `GET /api/v1/global/weather`
  - `GET /api/v1/global/ai-summary`
  - `POST /api/v1/global/sync`

---

## 4. Existing Data Sources & Invariants

1. **Open-Meteo Weather API**:
   - 36 reference stations globally covering all continents.
   - Temperature, humidity, surface pressure, precipitation rate, wind speed.
   - Invariant: `water_level = null` strictly enforced.
2. **NASA FIRMS Satellite Thermal Anomalies**:
   - VIIRS & MODIS active fire detections.
   - Clustered spatial hazard zones with Fire Radiative Power (FRP, MW).
3. **USGS Earthquake Hazards Program**:
   - Real-time M2.5+ earthquake epicenters, depth, magnitude.
4. **GDACS (Global Disaster Alert and Coordination System)**:
   - UN/EC multi-hazard alerts (Cyclones, Floods, Earthquakes, Volcanoes, Droughts).
5. **Copernicus GloFAS Adapter**:
   - Continental/global river discharge and flood forecasting.
   - Enforces strict honesty: returns `UNAVAILABLE` without `CDS_API_KEY`; zero fabricated hydrographs.
6. **ESP32 Sensor Mesh (Hardware Tier)**:
   - Optional local ground-truth calibration.
   - Disconnected hardware reports `0 NODES`; causes zero degradation to global operational readiness.

---

## 5. Existing Intelligence Engines

1. **Hazard Engine (`intelligence/hazards/`)**:
   - Classifies physical observations into HEAT, WILDFIRE, FLOOD, EARTHQUAKE, CYCLONE, and AIR_POLLUTION.
   - Computes normalized severity, confidence, and epistemic classification (`OBSERVED` vs `INFERRED`).
2. **Prediction Engine (`intelligence/prediction/`)**:
   - Projects deterministic forward hazard trajectories across +30m (nowcasting), +60m (tactical), and +360m (strategic, 6h) horizons.
3. **Compound Disaster Engine (`intelligence/compound/`)**:
   - Evaluates multi-hazard interactions using a directed acyclic dependency graph.
   - Computes compound amplification multipliers ($A_c$).
4. **Human Vulnerability Engine (`intelligence/vulnerability/`)**:
   - Integrates Social Vulnerability Index (SVI), population density, critical infrastructure counts, and evacuation accessibility barriers.
5. **Dynamic Evacuation Engine (`intelligence/evacuation/`)**:
   - Computes safe egress corridors avoiding impassable hazard boundaries (e.g. flooded bridges, active fire fronts) and routes civilians to designated muster shelters.
6. **Response Planner (`intelligence/response/`)**:
   - Emits prioritized tactical action playbooks with evidence tracking.
7. **Explainability Engine (`intelligence/explainability/`)**:
   - Generates feature attribution, counterfactual comparisons, and causal chains.
8. **Digital Twin & Simulation Engine (`intelligence/simulation/`)**:
   - Clones digital twin baseline states, applies parameter perturbations (rainfall multipliers, temperature deltas, drainage failures, road degradation), and propagates state changes through all downstream models with provenance.

---

## 6. Existing Frontend Capabilities

1. **Photorealistic 3D Cesium Client (`gods-eye-view/`)**:
   - CesiumJS 1.124.0 with Google Photorealistic 3D Tilesets.
   - CustomDataSource entity rendering for global hazards (ellipsoids, markers, pulse rings).
   - Screen-space picking click handler projecting tactical HUD popover pinned in screen coordinates.
2. **Top Navigation Bar (`topNav.js`)**:
   - Brand indicator and 7 mode tabs: LIVE, ANALYTICS, RISK, SIMULATION, SENSOR MESH, AI, EMERGENCY.
3. **Left Panel (`leftPanel.js`)**:
   - 9 raw measurement layer toggles, sensor mesh summary, and 4 metric channels.
4. **Right Panel (`rightPanel.js`)**:
   - Selected node details, decoupled operational status summary, 6-source Data Sources telemetry card, and AI Command Center.
5. **Status Bar (`statusBar.js`)**:
   - Bottom status line displaying decoupled operational state (`GLOBAL: ONLINE`, `REALTIME: CONNECTED`, `MESH NODES: 0 NODES`).

---

## 7. Existing Gaps (Target Transformation)

| Gap ID | Area | Current State | Required Final Product State |
| :--- | :--- | :--- | :--- |
| **G1** | **Top Bar Search** | TopNav only has mode tabs and brand title. | Integrated global location search box (Hyderabad, Mumbai, Tokyo, London, New York, California) with fly-to, region selection, live weather fetch, and regional risk cards. |
| **G2** | **Spatial Hazard Zones** | Hazards rendered as points or simple bounding ellipsoids. | Multi-coordinate geographic polygon footprints / bounding corridors with dynamic threat colors: Heat (yellow/orange/red), Flood (light blue/blue/deep blue), Fire (orange/red), Cyclone (purple), Earthquake (rings), Compound (hatched/violet). |
| **G3** | **Bottom Command Panel** | Bottom only has simple status line. | Comprehensive bottom command drawer with tabbed views: Event Feed, Prediction Chart (+30m/+60m/+6h), Compound Causal Chain (interactive graph), Human Impact & SVI, Dynamic Evacuation Plan, and Interactive Simulation Workbench. |
| **G4** | **Tactical HUD Actions** | Popover HUD displays metrics but buttons are static. | Buttons (`VIEW ANALYSIS`, `SIMULATE`, `EVACUATION`, `RESPONSE`) activate UI state and load target intelligence. |
| **G5** | **AI Command Center** | Displays static fallback briefing. | Fully interactive Q&A interface with one-click tactical prompts ("What is happening here?", "Why is this area dangerous?", "Where should people evacuate?", "What happens if rainfall increases by 40%?") grounded strictly in structured backend evidence. |
| **G6** | **Map Layer Toggles** | Left panel has 9 raw measurement layers. | Expanded layer panel with Section 35 toggles: Heat Risk, Flood Risk, Drought, Wildfire, Earthquakes, Cyclones, Disaster Alerts, Population, Vulnerability, Evacuation Routes, Shelters, Critical Infra, Live Zones, Simulated Zones. |
| **G7** | **Interactive Simulation** | Backend simulation engine exists, but frontend lacks live parameter sliders and before/after comparison table. | Full simulation workbench: Sliders (Rainfall, Temperature, Wind, Drainage, Road Access), scenario presets (Rain +20%/+40%/+60%, Temp +3°C/+5°C, Drainage Failure), "RUN SIMULATION" execution, before/after delta table, and visual expansion on Cesium globe. |
| **G8** | **Emergency Mode** | Generic mode intelligence copy. | High-visibility emergency view aggregating Alert Level (Green/Yellow/Orange/Red), Current Threat, Population at risk, Infrastructure affected, Evacuation routes, and Shelters. |
| **G9** | **Deterministic Demo / Replay** | Manual workflow. | 1-click deterministic demonstration script matching Steps 1 to 13 of the Ideal Judge Demonstration. |

---

## 8. Files To Be Modified / Created

### 8.1. Frontend (`gods-eye-view/` & `Work/gods-eye-view/`)
- `src/climate/panels/topNav.js`: Add global location search box, notification badge, and quick system status pill.
- `src/climate/panels/bottomDrawer.js` *(NEW)*: Comprehensive bottom intelligence panel housing Simulation Workbench, Prediction Trend, Compound Causal Chain, Human Impact, Dynamic Evacuation, and Realtime Event Feed.
- `src/climate/panels/leftPanel.js`: Add complete layer toggles matching Section 35 + Data Sources status card.
- `src/climate/panels/rightPanel.js`: Integrate interactive AI Command Center Q&A, Regional Intelligence card, and Response Directives.
- `src/climate/panels/emergencyPanel.js` *(NEW)*: Dedicated Emergency Mode overview card.
- `src/climate/panels/shell.js`: Mount `bottomDrawer` and `emergencyPanel`.
- `src/climate/panels/climateShell.css`: Add styles for bottom drawer, search box, simulation sliders, before/after table, and causal chain graph.
- `src/climate/layers/globalHazardsLayer.js`: Implement multi-coordinate spatial polygon footprints, compound highlighting, and simulation state rendering.
- `src/climate/layers/evacuationLayer.js` *(NEW)*: Cesium entity layer rendering evacuation routes, shelters, and barrier markers.
- `src/climate/state/climateState.js` & `constants.js`: Add state branches for `selectedLocation`, `simulationDeltas`, `bottomDrawerTab`, `searchResults`.
- `src/climate/api/client.js` & `controller.js`: Add methods for running simulations, location lookups, and AI queries.

### 8.2. Backend (`intelligence/`)
- `intelligence/external_data/router.py`: Add `/api/v1/global/region` (regional weather and risk lookup for any geocoded location) and `/api/v1/global/ai-query` (structured prompt responses for Q&A questions).
- `intelligence/app/main.py`: Ensure all proxy and direct routes support regional queries and simulation parameter injection.

---

## 9. Architectural Conflicts & Resolutions

1. **Cesium Canvas Event Interception**:
   - *Conflict*: Large floating UI panels may swallow mouse drag/scroll events needed for rotating the 3D globe.
   - *Resolution*: Set `#climate-eye-root` and panel backdrop containers to `pointer-events: none`. Apply `pointer-events: auto` strictly to interactive UI elements (buttons, inputs, cards, drawers).
2. **Backward Compatibility with Existing Unit Tests**:
   - *Conflict*: 440 frontend unit tests look for specific DOM elements (`#ce-card-status`, `#ce-subsystem-api-val`, etc.).
   - *Resolution*: Preserve all existing element IDs and data attributes as visible or backward-compatible anchor elements.
3. **Decoupled Hardware Independence**:
   - *Conflict*: Physical sensor mesh disconnects must never trigger `SYSTEM STANDBY`.
   - *Resolution*: Top-level status header evaluates global feeds independently of physical node count.

---

## 10. Pre-Implementation Audit Verdict

```text
================================================================================
PRE-IMPLEMENTATION AUDIT VERDICT:
ARCHITECTURE VERIFIED — PROCEED TO IMPLEMENTATION PLAN
================================================================================
```
