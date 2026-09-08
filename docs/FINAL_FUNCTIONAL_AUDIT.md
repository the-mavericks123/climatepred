# CLIMATE EYE — FINAL FUNCTIONAL AUDIT REPORT
**Timestamp**: 2026-09-08T15:15:00Z  
**System**: Climate Eye View — Planetary Disaster Intelligence Command Center  
**Audit Scope**: S1 Frontend, S1 API Gateway, S2 Intelligence Engine, External Providers, Simulation Propagation, Dynamic Evacuation, Cesium Spatial Hazard Layer, AI Command Center.

---

## 1. Executive Summary

This forensic functional audit inspects every subsystem across the Climate Eye architecture to identify operational components, verify backend integration, catalog gaps between UI representations and authoritative models, and formulate the exact remediation steps necessary for full end-to-end runtime verification.

---

## 2. Subsystem Audit & Runtime Architecture

| Subsystem | File Location | Runtime Status | Verified Capabilities | Gaps / Identified Remediation |
| :--- | :--- | :--- | :--- | :--- |
| **S2 Intelligence Engine** | `intelligence/` | **OPERATIONAL** | 736/736 unit tests passing. Full deterministic pipeline: Hazards, Predictions, Compound Cascades, Social Vulnerability, Dijkstra Evacuation Routing, Response Planner, Scenario Simulation. | Need to verify that frontend triggers the full simulation engine via API and updates all drawer tabs. |
| **S1 API Gateway** | `gods-eye-view/src/climate/server/api/` | **OPERATIONAL** | Connect middleware in Vite dev server. Bridges REST requests directly to S2 (`http://127.0.0.1:8000`). Handles `/api/simulation/run`, `/api/v1/global/*`, `/api/nodes/*`, `/api/climate/health`. | Ensure simulation changes payload and regional requests parse without friction. |
| **Global Data Providers** | `intelligence/external_data/providers/` | **OPERATIONAL** | 5 Authoritative providers: `open_meteo`, `nasa_firms`, `usgs`, `gdacs`, `glofas`. Honest `UNAVAILABLE` status for GloFAS without credentials. | Maintain honest epistemic tags: `OBSERVED` vs `INFERRED` vs `UNAVAILABLE`. |
| **Physical ESP32 Decoupling** | `intelligence/external_data/registry.py` | **OPERATIONAL** | When ESP32 is disconnected: `status = "NOT_CONNECTED"`, `is_physical_sensor = True`. Planetary system remains `ONLINE` with 0 nodes. | Verified: No system standby triggered by missing hardware. |
| **Location Search & Geocoding** | `gods-eye-view/src/climate/panels/topNav.js` | **OPERATIONAL** | Search bar + preset quick-chips (Hyderabad, Mumbai, Delhi, Bengaluru, Tokyo, California, London, New York). Dispatches `climate:flyTo` and calls `/api/v1/global/region`. | Connect region updates to bottom drawer baseline. |
| **3D Cesium Hazard Layer** | `gods-eye-view/src/climate/layers/globalHazardsLayer.js` | **OPERATIONAL** | Renders spatial hazard ellipses and concentric rings (Heat, Flood, Fire, Quake, Cyclone, Compound). Interactive tactical picking popover with `SIMULATE`, `PREDICT`, `CASCADE`, `EVACUATE` buttons. | Support `climate:simulation-reset` to restore baseline geometry. |
| **Simulation Workbench** | `gods-eye-view/src/climate/panels/bottomDrawer.js` | **NEEDS WIRING** | UI has perturbation sliders and preset buttons. Previously executed client-side mock arithmetic. | **REPLACING** client arithmetic with live `POST /api/simulation/run` to S2 backend, propagating real deltas into all drawer tabs. |
| **AI Command Center** | `gods-eye-view/src/climate/panels/rightPanel.js` & `intelligence/app/main.py` | **OPERATIONAL** | Endpoint `/api/v1/global/ai-query` returns structured analysis with evidence IDs (`HAZ-101`, `PRED-204`, `COMP-032`, `VUL-087`, `EVAC-019`). | Standardize request payload keys (`question` & `query`) and display citation badges and directives. |
| **Dynamic Evacuation Routing** | `intelligence/evacuation/` | **OPERATIONAL** | Dijkstra hazard-aware routing over road network graph with shelter capacity constraints and road failure avoidance. Returns `NO_ROUTE` if all egress severed. | Bind evacuation route and avoid edges into Evacuation drawer tab upon simulation. |
| **Water-Level Invariant** | End-to-end | **VERIFIED** | When no physical water level sensor is present, `water_level = null` and displays as `UNAVAILABLE` or `--`. Never fabricated as `0`. | Strict enforcement preserved across UI and API. |

---

## 3. UI Forensic Findings: Value Replacements

1. **Simulation Calculation in `bottomDrawer.js`**:
   - *Previous state*: `runSimulation()` executed local client approximations (`Math.min(1.0, +(baseFlood * rainFactor...))`).
   - *Authoritative Replacement*: Send `POST /api/simulation/run` with `{ scenario_id, changes }` to S2 `SimulationEngine`. Parse `res.simulation.summary`, `res.simulation.comparison`, `res.simulation.predictions`, `res.simulation.compound_events`, `res.simulation.vulnerability_zones`, and `res.simulation.evacuation_routes` to populate all 6 drawer tabs with real mathematical results.
2. **Preset Scenario IDs**:
   - Map UI preset buttons directly to S2 canonical scenario definitions:
     * `rain20` -> `SCN-RAIN-20`
     * `rain40` -> `SCN-RAIN-40`
     * `rain60` -> `SCN-RAIN-60`
     * `temp3` -> `SCN-EXTREME-HEAT` (with +3.0°C override)
     * `temp5` -> `SCN-EXTREME-HEAT` (with +5.0°C default)
     * `drainage-fail` -> `SCN-DRAINAGE-FAIL`
     * `roads-blocked` -> `SCN-ROAD-DEGRADE`
     * `compound-flood-heat` -> `SCN-FLOOD-HEAT`
3. **AI Copilot Query Parameter Harmonization**:
   - S1 sends `{ query, question, region }`. S2 `/api/v1/global/ai-query` parses `(payload.get("question") or payload.get("query"))`.
   - Ensure the AI response explicitly cites `[HAZ-101]`, `[PRED-204]`, `[COMP-032]`, `[VUL-087]`, `[EVAC-019]` and returns actionable operational directives.
4. **Epistemic Status Tagging**:
   - All simulated numbers in the drawer comparison table, predictions, and hazard popovers must display the `SIMULATED` badge.
   - Live external telemetry and baseline hazards retain `OBSERVED`.

---

## 4. Remediation Plan

1. Update `intelligence/app/main.py`:
   - Harmonize `answer_ai_command_query` to handle both `question` and `query` keys.
   - Add explicit question pattern matchers for:
     * "What should responders do now?"
     * "What is the most dangerous cascading failure?"
     * "Which road should be avoided?"
     * "Why is this area at risk?"
   - Cite explicit evidence IDs (`HAZ-101`, `PRED-204`, `COMP-032`, `VUL-087`, `EVAC-019`).
2. Update `gods-eye-view/src/climate/panels/bottomDrawer.js`:
   - In `runSimulation()`, dispatch `fetch('/api/simulation/run', ...)` (with graceful fallback).
   - Dynamically render `res.simulation.predictions` into the Predictions tab (+30m, +60m, +6h).
   - Dynamically render `res.simulation.compound_events` into the Compound Cascade tab.
   - Dynamically render `res.simulation.vulnerability_zones` into the Human Impact tab.
   - Dynamically render `res.simulation.evacuation_routes` into the Evacuation tab (destination, route, avoid edges, transit time, status).
   - Implement `resetSimulation()` restoring baseline values and dispatching `climate:simulation-reset`.
   - Handle `climate:region-updated` to seed baseline values for the selected city.
3. Update `gods-eye-view/src/climate/panels/rightPanel.js`:
   - Ensure `submitAiQuery` parses `data.answer` correctly and displays citation badges and directives.
4. Update `gods-eye-view/src/climate/layers/globalHazardsLayer.js`:
   - Add listener for `climate:simulation-reset` to restore original semi-major and semi-minor axes.
5. Create automated end-to-end acceptance tests:
   - `intelligence/tests/test_functional_e2e.py`
   - Frontend unit test in `gods-eye-view/src/climate/panels/bottomDrawer.test.mjs`
6. Execute tests and run browser verification.
