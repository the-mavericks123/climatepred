# CLIMATE EYE — FULL UI FUNCTIONALITY AUDIT

**Audit Date:** 2026-09-08  
**Scope:** Complete frontend interface, 3D Cesium Earth, S1 API Client, and S2 Python Intelligence Engines  
**Status:** FORENSIC AUDIT COMPLETE

---

## 1. Executive Summary & Architecture Ground Truth

The Climate Eye Command Center architecture requires that every button, tab, control, slider, and layer toggle acts as a direct client of the authoritative S2 Python intelligence and simulation engines (`intelligence.app.main` on port 8000, proxied via Vite on port 5173).

```
                      3D CESIUM GLOBE
                             │
                     USER INTERACTION
                             ▼
                    FRONTEND API CLIENT
                             │
                   REST / WEBSOCKET / SSE
                             ▼
                 S2 INTELLIGENCE ENGINES
    (Simulation, Hazard, Prediction, Cascade, Evac, AI)
                             │
                      SYNTHESIS RESULT
                             ▼
                    FRONTEND STATE STORE
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       CESIUM ENTITIES             PANELS & DIRECTIVES
    (Spatial polygons, routes)    (AI, Causal, Sliders)
```

No synthetic calculations may be fabricated in client JavaScript. All epistemic states must distinguish between `OBSERVED`, `PREDICTED`, and `SIMULATED`.

---

## 2. Complete Inventory of UI Controls and Functional Audit

### A. Top Navigation Bar (`topNav.js`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Location Search Input** (`#ce-location-search-input`) | Accepts string text | Accepts global city/sector query, normalizes location name | `GET /api/v1/global/region?name={q}` | PARTIAL |
| **Search Submit Button** (`#ce-search-submit-btn`) | Dispatches flyTo with known fallback coords | Geocodes, triggers Cesium camera `flyTo`, fetches authoritative regional data, updates store & right panel | `GET /api/v1/global/region?name={q}&lat={lat}&lon={lon}` | PARTIAL |
| **Quick Preset Chips** (`.ce-quick-loc-btn`) | Sets input and dispatches flyTo | Flies camera, requests regional intelligence for city, updates active intelligence context | `GET /api/v1/global/region?name={city}` | PARTIAL |
| **Target Vector Display** (`#ce-coord-chip`) | Displays lat/lon string | Dynamically updates with camera position or selected region coordinates | Browser Camera / Store State | WORKING |
| **Zulu Clock** (`#ce-top-zulu-clock`) | Updates UTC timer | Displays live high-precision UTC military/aviation timestamp | Client System Clock | WORKING |
| **Status Dot & Text** (`#ce-top-status-text`) | Static "OPERATIONAL" | Reflects actual system health from API health check | `GET /api/v1/health` & `/api/v1/global/sources` | PARTIAL |
| **Mode Buttons: LIVE** (`#ce-mode-btn-live`) | Sets store UI mode to LIVE | Sets UI mode, clears simulation overlays, returns to real-time ground truth | S2 / Store State | WORKING |
| **Mode Buttons: ANALYTICS** (`#ce-mode-btn-analytics`) | Sets store UI mode | Displays observational statistics across registered sensors/sources | S2 Telemetry Aggregation | WORKING |
| **Mode Buttons: RISK** (`#ce-mode-btn-risk`) | Sets store UI mode | Displays active hazard vectors, risk indices, and multi-hazard status | `GET /api/v1/hazards/current` | PARTIAL |
| **Mode Buttons: SIMULATION** (`#ce-mode-btn-simulation`) | Sets store UI mode | Switches to Digital Twin workbench, displays sliders and scenarios | `GET /api/v1/simulation/scenarios` | WORKING |
| **Mode Buttons: SENSOR MESH** (`#ce-mode-btn-sensor_mesh`)| Sets store UI mode | Filters view to physical/virtual sensor nodes and ground telemetry | `GET /api/v1/nodes` | WORKING |
| **Mode Buttons: AI** (`#ce-mode-btn-ai`) | Sets store UI mode | Opens AI Command Center directive workspace | `POST /api/v1/global/ai-query` | WORKING |
| **Mode Buttons: EMERGENCY** (`#ce-mode-btn-emergency`) | Sets store UI mode | Focuses on active evacuation corridors, shelters, and response plans | `GET /api/v1/evacuation/current` | WORKING |

---

### B. Left Navigation Accordion Sidebar (`leftPanel.js`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Sidebar Collapse/Expand** (`#ce-left-toggle-btn`) | Collapses sidebar width | Toggles sidebar visibility smoothly without layout jump | Client DOM | WORKING |
| **Section 1: OVERVIEW** Trigger | Expands overview accordion | Expands overview, displays active live metric channels | S1 / S2 Telemetry Stream | WORKING |
| **Overview Metric Channels** (Temp, Rain, Soil, AQI) | Displays `--` or latest node telemetry | Displays ground-truth aggregated metrics from active stream | `GET /api/v1/telemetry` | WORKING |
| **Section 2: HAZARDS** Trigger | Expands hazards accordion | Displays count of active global hazards, opens layer controls | `GET /api/v1/global/hazards` | WORKING |
| **Climate Layer Toggles** (9 channels) | Toggles layer in store | Toggles visibility of respective Cesium entities & legends | Cesium DataSources | WORKING |
| **Section 3: PREDICTIONS: NOW** (`[data-horizon="now"]`) | Dispatches event | Sets prediction timeline to T+0, restores observed hazard zones | `GET /api/v1/hazards/current` | PARTIAL |
| **PREDICTIONS: +30 MIN** (`[data-horizon="30m"]`) | Dispatches event | Queries +30m forecast, scales hazard zones, marks PREDICTED | `GET /api/v1/hazards/predictions?horizon=30m` | PARTIAL |
| **PREDICTIONS: +60 MIN** (`[data-horizon="60m"]`) | Dispatches event | Queries +60m crest forecast, updates globe & contextual HUD | `GET /api/v1/hazards/predictions?horizon=60m` | PARTIAL |
| **PREDICTIONS: +6 HOURS** (`[data-horizon="6h"]`) | Dispatches event | Queries +6h maximum extent forecast, updates globe | `GET /api/v1/hazards/predictions?horizon=360m` | PARTIAL |
| **Section 4: COMPOUND: Cascade Events** (`[data-action="cascade"]`) | Dispatches open workspace | Retrieves compound events, renders causal chain graph in bottom dock | `GET /api/v1/compound` | PARTIAL |
| **COMPOUND: Infrastructure Strain** (`[data-action="infra"]`) | Dispatches open workspace | Highlights strained lifelines (bridges/dams) on Cesium globe | `GET /api/v1/compound` | PARTIAL |
| **COMPOUND: Critical Dependencies** (`[data-action="deps"]`) | Dispatches open workspace | Surfaces dependency matrix in right panel | `GET /api/v1/compound` | PARTIAL |
| **Section 5: HUMAN IMPACT: Population Exposure** (`[data-action="pop"]`) | Dispatches open workspace | Highlights population vulnerability zones on globe, shows counts | `GET /api/v1/vulnerability` | PARTIAL |
| **HUMAN IMPACT: High Vulnerability** (`[data-action="vuln"]`) | Dispatches open workspace | Filters to high-SVI zones, shows demographics breakdown | `GET /api/v1/vulnerability` | PARTIAL |
| **HUMAN IMPACT: Critical Facilities** (`[data-action="facilities"]`) | Dispatches open workspace | Renders critical facility nodes (hospitals, schools) on globe | `GET /api/v1/vulnerability` | PARTIAL |
| **Section 6: EVACUATION: Safe Routes** (`[data-action="routes"]`) | Dispatches open workspace | Fetches and renders green safe evacuation corridors on globe | `GET /api/v1/evacuation` | PARTIAL |
| **EVACUATION: Shelters** (`[data-action="shelters"]`) | Dispatches open workspace | Highlights designated refuge shelters with capacity & readiness | `GET /api/v1/evacuation` | PARTIAL |
| **EVACUATION: Blocked Roads** (`[data-action="blocked"]`) | Dispatches open workspace | Renders red impassable segments (e.g. Bridge B submerged) | `GET /api/v1/evacuation` | PARTIAL |
| **EVACUATION: No-Route Zones** (`[data-action="noroute"]`) | Dispatches open workspace | Displays isolated sectors where evacuation routing failed (`NO_ROUTE`) | `GET /api/v1/evacuation` | PARTIAL |
| **Section 7: SIMULATION: Rain +40%** (`[data-sim="rain40"]`) | Sets local slider state | Sets sliders and executes real Digital Twin simulation | `POST /api/v1/simulation/run` | PARTIAL |
| **SIMULATION: Extreme Heat** (`[data-sim="heat"]`) | Sets local slider state | Executes heatwave simulation on backend | `POST /api/v1/simulation/run` | PARTIAL |
| **SIMULATION: Drainage Failure** (`[data-sim="drain"]`) | Sets local slider state | Executes drainage failure simulation on backend | `POST /api/v1/simulation/run` | PARTIAL |
| **SIMULATION: Road Access -50%** (`[data-sim="road"]`) | Sets local slider state | Executes road degradation simulation on backend | `POST /api/v1/simulation/run` | PARTIAL |
| **SIMULATION: Flood + Heat** (`[data-sim="compound"]`) | Sets local slider state | Executes multi-hazard compound simulation on backend | `POST /api/v1/simulation/run` | PARTIAL |
| **Section 8: DATA SOURCES Status** (6 feeds) | Static DOM text | Live polling of provider status, timestamps, record counts | `GET /api/v1/global/sources` | PARTIAL |
| **Section 9: AI COMMAND: Situation Brief** (`[data-ai="brief"]`) | Dispatches event | Submits "What is the current situation?" to AI endpoint | `POST /api/v1/global/ai-query` | PARTIAL |
| **AI COMMAND: What Happened?** (`[data-ai="cause"]`) | Dispatches event | Submits causal attribution query to AI endpoint | `POST /api/v1/global/ai-query` | PARTIAL |
| **AI COMMAND: What Happens Next?** (`[data-ai="next"]`) | Dispatches event | Submits forecast extrapolation query to AI endpoint | `POST /api/v1/global/ai-query` | PARTIAL |
| **AI COMMAND: Who Is At Risk?** (`[data-ai="risk"]`) | Dispatches event | Submits demographic vulnerability query to AI endpoint | `POST /api/v1/global/ai-query` | PARTIAL |
| **AI COMMAND: Directive** (`[data-ai="action"]`) | Dispatches event | Submits tactical responder directive query to AI endpoint | `POST /api/v1/global/ai-query` | PARTIAL |
| **Section 10: SYSTEM Subsystems Grid** | Hardcoded text pills | Reflects authoritative subsystem state (API, DB, MQTT, Realtime) | Store state / `/api/v1/health` | WORKING |

---

### C. Floating Map Layers Switcher (`#ce-floating-map-layers`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **MAP LAYERS Pill Button** (`#ce-map-layers-toggle-btn`) | Toggles popover menu | Toggles spatial overlay checklist popover | Client DOM | WORKING |
| **Layer Checkbox: Hazards** (`#ce-layer-toggle-hazards`) | Static checkbox | Toggles hazard zones overlay on Cesium globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Heat** (`#ce-layer-toggle-heat`) | Static checkbox | Filters heat thermal ellipses on globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Flood** (`#ce-layer-toggle-flood`) | Static checkbox | Filters flood inundation boundaries on globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Drought** (`#ce-layer-toggle-drought`) | Static checkbox | Filters drought aridity zones on globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Wildfire** (`#ce-layer-toggle-wildfire`) | Static checkbox | Filters NASA FIRMS wildfire clusters on globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Earthquake** (`#ce-layer-toggle-earthquake`) | Static checkbox | Filters USGS earthquake rings on globe | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Predictions** (`#ce-layer-toggle-predictions`)| Static checkbox | Toggles predicted extent outlines | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Compound** (`#ce-layer-toggle-compound`) | Static checkbox | Toggles compound cascade hazard polygons | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Impact** (`#ce-layer-toggle-impact`) | Static checkbox | Toggles human impact demographic heatmaps | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Evacuation** (`#ce-layer-toggle-evacuation`)| Static checkbox | Toggles safe corridors and blocked road segments | Cesium DataSource | PARTIAL |
| **Layer Checkbox: Nodes** (`#ce-layer-toggle-nodes`) | Static checkbox | Toggles IoT sensor node billboards | Cesium DataSource | WORKING |

---

### D. Right Intelligence Workspace (`rightPanel.js`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Right Panel Collapse/Expand** (`#ce-right-expand-btn`) | Toggles collapsed CSS class | Smoothly collapses panel to maximize globe view | Client DOM | WORKING |
| **Tab: PLANETARY** (`#ce-tab-ctx-overview`) | Switches view to overview | Displays planetary overview, active disaster metrics, satellite status | S2 Store State | WORKING |
| **Tab: REGION** (`#ce-tab-ctx-region`) | Switches view to region | Displays active selected region telemetry, brief, causal chain | `GET /api/v1/global/region` | WORKING |
| **Tab: SIMULATION** (`#ce-tab-ctx-simulation`) | Switches view to simulation | Displays Digital Twin slider controls, presets, and runner | `GET /api/v1/simulation/scenarios` | WORKING |
| **Tab: AI DIRECTIVE** (`#ce-tab-ctx-ai`) | Switches view to AI | Displays AI chat/query interface with evidence audit tokens | `POST /api/v1/global/ai-query` | WORKING |
| **View Safe Route on Globe** (`#ce-btn-view-evac-route`) | No action | Flies Cesium camera to focus on evacuation corridor and safe shelter | Cesium Camera FlyTo | PARTIAL |
| **Rainfall Slider** (`#ce-slider-rain`) | Updates local label | Updates simulation perturbation state (-60% to +60%) | State Store | WORKING |
| **Temperature Slider** (`#ce-slider-temp`) | Updates local label | Updates simulation perturbation state (-5°C to +5°C) | State Store | WORKING |
| **Drainage Slider** (`#ce-slider-drain`) | Updates local label | Updates simulation drainage capacity state (0% to 100%) | State Store | WORKING |
| **Road Access Slider** (`#ce-slider-road`) | Updates local label | Updates simulation road accessibility state (0% to 100%) | State Store | WORKING |
| **Simulation Preset Buttons** (`.ce-sim-preset-btn`) | Adjusts sliders locally | Sets sliders to exact values and triggers real simulation run | `POST /api/v1/simulation/run` | PARTIAL |
| **⚡ RUN SIMULATION ENGINE** (`#ce-btn-run-simulation`) | Simulates locally with event | Sends POST request to S2, runs digital twin, updates all models | `POST /api/v1/simulation/run` | PARTIAL |
| **RESET TO BASELINE** (`#ce-btn-reset-sim`) | Clears local flag | Resets store and globe back to live observed baseline | `GET /api/v1/hazards/current` | PARTIAL |
| **AI Query Input & Submit** | Currently static text | User can type or click queries; sends question & context to AI | `POST /api/v1/global/ai-query` | PARTIAL |
| **Node Deselect Button** (`#ce-node-deselect-btn`) | Clears selected node | Clears node selection in store, hides telemetry HUD | Store Dispatch | WORKING |

---

### E. Bottom Floating Dock (`bottomDrawer.js`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Causal Dock Toggle Button** (`#ce-causal-toggle-btn`) | Expands/collapses strip | Minimizes/maximizes horizontal causal flow strip | Client DOM | WORKING |
| **Causal Pill: Heavy Rain** (`#ce-node-step-1`) | Dispatches target event | Zooms camera to atmospheric precipitation hotspot | Cesium Camera | PARTIAL |
| **Causal Pill: Soil Saturation** (`#ce-node-step-2`) | Dispatches target event | Highlights saturated catchment basin on Cesium globe | Cesium Camera | PARTIAL |
| **Causal Pill: Flash Flood** (`#ce-node-step-3`) | Dispatches target event | Highlights surface flood zone on Cesium globe | Cesium Camera | PARTIAL |
| **Causal Pill: Road Failure** (`#ce-node-step-4`) | Dispatches target event | Highlights blocked arterial corridor (Bridge B) in red | Cesium Camera | PARTIAL |
| **Causal Pill: Hospital Access** (`#ce-node-step-5`) | Dispatches target event | Highlights isolated healthcare facility on Cesium globe | Cesium Camera | PARTIAL |
| **Causal Pill: Evacuation Delay** (`#ce-node-step-6`) | Dispatches target event | Displays evacuation delay metrics in contextual HUD | Cesium Camera | PARTIAL |
| **Timeline: NOW** (`[data-step="now"]`) | Dispatches event | Sets prediction timeline to T+0, restores observed state | Store State | WORKING |
| **Timeline: +30m** (`[data-step="30m"]`) | Dispatches event | Updates globe to +30m predicted spread, marks PREDICTED | `GET /api/v1/hazards/predictions` | PARTIAL |
| **Timeline: +60m** (`[data-step="60m"]`) | Dispatches event | Updates globe to +60m predicted crest, marks PREDICTED | `GET /api/v1/hazards/predictions` | PARTIAL |
| **Timeline: +6h** (`[data-step="6h"]`) | Dispatches event | Updates globe to +6h predicted boundary, marks PREDICTED | `GET /api/v1/hazards/predictions` | PARTIAL |

---

### F. Region Focus Card (`regionFocusCard.js`)

| Control | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Close Button** (`#ce-target-close-btn`) | Hides card element | Hides tactical focus card | Client DOM | WORKING |
| **Action: `[ PREDICT ]`** (`#ce-target-btn-pred`) | Dispatches horizon 60m | Requests +60m prediction, updates globe & panel | S2 Prediction Engine | PARTIAL |
| **Action: `[ SIMULATE ]`** (`#ce-target-btn-sim`) | Opens simulation workspace | Switches to simulation tab, pre-populates region parameters | S2 Simulation Engine | WORKING |
| **Action: `[ CASCADE ]`** (`#ce-target-btn-cascade`) | Pulses bottom causal dock | Focuses on causal cascade for selected hazard | S2 Compound Engine | WORKING |
| **Action: `[ EVACUATE ]`** (`#ce-target-btn-evac`) | Dispatches evac highlight | Fetches dynamic evacuation routes, renders safe/blocked paths | S2 Evacuation Engine | PARTIAL |

---

### G. 3D Cesium Globe Interactivity (`globalHazardsLayer.js`)

| Interaction | Current Behavior | Expected Behavior | Backend / API Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Click Hazard Zone Entity** | Opens tactical HUD popover | Opens HUD popover, synchronizes store selection, updates right panel | Store & Right Panel | WORKING |
| **Click Sensor Mesh Node** | Opens sensor telemetry card | Displays ground truth live telemetry in right panel | Store & Right Panel | WORKING |
| **Click Shelter Entity** | Shows shelter properties in HUD | Displays capacity, current demand, status, and recommended ingress | S2 Evacuation Model | PARTIAL |
| **Click Evacuation Route Entity** | Shows route properties in HUD | Displays distance, ETA, safety score, and status | S2 Evacuation Model | PARTIAL |
| **Click Empty Space on Globe** | Dismisses popover | Deselects active hazard, restores planetary overview | Client ScreenSpace | WORKING |

---

## 3. Integration Gap Analysis & Implementation Roadmap

1. **Simulation Engine Integration**:
   - `rightPanel.js` `#ce-btn-run-simulation` must call `POST /api/v1/simulation/run` with `{ scenario_id, base_state: 'current', changes: { rainfall_multiplier, temperature_delta, drainage_failure_severity, road_accessibility_reduction } }`.
   - The returned `simulation` object containing updated hazards, predictions, compound cascade, vulnerability zones, and evacuation routes must be ingested into `store.dispatch` and broadcast to Cesium layers.
   - All values must be stamped with `simulated: true` and the `SIMULATED` epistemic tag.

2. **AI Command Center Integration**:
   - `rightPanel.js` and `leftPanel.js` AI actions must execute `POST /api/v1/global/ai-query` with `{ question, region: store.getState().selectedRegion || { name: 'Hyderabad' } }`.
   - The response (`headline`, `summary`, `actions`, `evidence_ids`, `epistemic_status`) must replace placeholder text with live grounded data.

3. **Prediction Timeline Integration**:
   - Clicking NOW, +30m, +60m, +6h must call `GET /api/v1/hazards/predictions?horizon={h}&region={r}`, update hazard polygons, and mark all values as `PREDICTED`.

4. **Evacuation & Compound Integration**:
   - Evacuation routes must retrieve real route data (`GET /api/v1/evacuation/current`), dynamically rendering green safe corridors, red blocked corridors, and shelter points.
   - Compound risk buttons must retrieve live cascade chains from `GET /api/v1/compound` and render the nodes dynamically.

5. **Live Data Sources Polling**:
   - Data sources section must periodically fetch `GET /api/v1/global/sources` and display live status (ONLINE, STALE, UNAVAILABLE, NOT_CONNECTED) with timestamps.

---

**Audit Sign-off:** Lead Systems Architect, Planetary Disaster Intelligence Command Center
