# CLIMATE EYE — STITCH UI/UX INTEGRATION AUDIT
**Planetary Climate + 3D Disaster Intelligence Command Center**  
**Audit Date**: September 8, 2026  
**Status**: COMPLETE — READY FOR PRODUCTION IMPLEMENTATION

---

## 1. Executive Summary

This forensic integration audit examines the existing Climate Eye View application and the newly supplied Stitch design reference located in `stitch_climate_eye_command_center/` (specifically `orbital_precision_hud/DESIGN.md` and `climate_eye_planetary_intelligence_command_center/code.html`).

The core architectural imperative is:
* **The Stitch project is the VISUAL DESIGN TARGET.**
* **The existing Climate Eye backend/intelligence is the AUTHORITATIVE SOURCE OF TRUTH.**
* **70–80% visual dominance is reserved for the 3D Cesium Earth.**
* **The UI uses progressive disclosure (compact floating HUDs, contextual cards, single-tab bottom command drawer) rather than crowded dashboard walls.**
* **All existing APIs, intelligence engines, global feeds, simulation math, Dijkstra evacuation routing, epistemic honesty tags, and hardware support are preserved intact.**

---

## 2. Existing UI Architecture Analysis

### Current Structure (`gods-eye-view/src/climate/`)
* **State Management (`src/climate/state/`)**: Authoritative unified store with 13 functional sections (nodes, telemetry, connection, system, hazards, predictions, compound, vulnerability, evacuation, response, simulation, ai, ui). Strict adherence to numeric zero preservation and null unmonitored values.
* **Component Layer (`src/climate/panels/`)**:
  * `topNav.js`: Fixed top header with mode buttons, location search input, and quick city shortcut chips.
  * `leftPanel.js`: Left rail with 9 measurement layers list and connected sensor mesh stats. Currently permanently docked.
  * `sensorMeshPanel.js`: Dedicated overlay modal for inspecting ESP32 mesh nodes.
  * `rightPanel.js`: Right rail displaying system subsystems, live data feeds, selected regional conditions, risk scores, and AI command copilot.
  * `bottomDrawer.js`: Multi-tab bottom drawer (Simulation, Predictions, Cascade, Human Impact, Evacuation, Event Feed) connected to `/api/v1/simulation/run` with mathematical delta propagation.
  * `statusBar.js`: Bottom telemetry status bar tracking realtime status, mesh nodes, latest timestamp, and UTC clock.
  * `climateShell.css`: Monolithic stylesheet (~1,848 lines) providing dark theme variables and layout rules.
* **Geospatial Cesium Layer (`src/climate/layers/`)**:
  * `globalHazardsLayer.js`: Renders spatial hazard polygon envelopes (Flood, Heat, Drought, Wildfire, Seismic, Compound) with translucent fills, pulsed boundaries, and click-to-focus event dispatching.
  * `nodesLayer.js`, `metricLayers.js`, `layersController.js`: Render edge sensor beacons, raster weather overlays, and legend keys.

---

## 3. Stitch Design Architecture Analysis

### Stitch Reference Files (`stitch_climate_eye_command_center/`)
1. `orbital_precision_hud/DESIGN.md`:
   * **Design Identity**: "Technical Glassmorphism with Futuristic Telemetry Minimalism".
   * **Palette Tokens**:
     * Canvas/Deep Void: `#080e1a` (`surface-container-lowest`), `#0e131f` (`surface`), `#161c28` (`surface-container-low`), `#242a36` (`surface-container-high`).
     * Atmospheric Cyan (Primary): `#4cd7f6` / `#06b6d4`
     * Orbital Sky (Secondary): `#7bd0ff` / `#38bdf8`
     * Compound Threat (Tertiary): `#ddb7ff` / `#a855f7`
     * Tactical Severity: Nominal `#10b981`, Warning `#f59e0b`, Severe `#f97316`, Critical `#ef4444`.
     * Razor Glass Borders: `1px solid rgba(76, 215, 246, 0.2)` / `1px solid rgba(56, 189, 248, 0.15)`.
     * Micro-Crosshairs & Corner Ticks (Chamfered brackets `[ ]`, coordinate reticles).
   * **Typography**:
     * Display: Space Grotesk (headers, sector titles, tactical badges).
     * UI & Narrative: Inter (telemetry notes, AI situational directives).
     * Telemetry & Monospace: JetBrains Mono (GPS coordinates, timestamps, confidence, epistemic badges).
2. `climate_eye_planetary_intelligence_command_center/code.html`:
   * **Viewport Scaffolding**:
     * Fixed Top Navigation (80px): Brand insignia + radar pulse, search bar with coordinate readout (`LAT 17.3850° N / LON 78.4867° E`) and quick vector links (`[Hyderabad]`, `[Mumbai]`, `[Delhi]`, `[Tokyo]`, `[California]`, `[London]`), live stream pill (`OBSERVED | LIVE STREAM`), UTC clock (`ZULU`), mode navigation (`Live`, `Analytics`, `Risk`, `Simulation`, `AI Command`, `Emergency`), and sub-bar displaying live provider health.
     * Collapsible Floating Left HUD: Compact instrument drawer (`ORBITAL INSTRUMENTS / TACTICAL LAYERS`) categorized into: 1.0 Climate Telemetry, 2.0 Active Hazard Vectors, 3.0 Infrastructure & Corridors, 4.0 Intelligence.
     * Floating Region Focus HUD Card (Pinned near reticle): Locked Target Sector card displaying real city metrics (Temp, Rain, Humid, Conf), threat severity meters, exposed population, vulnerability, and tactical trigger buttons (`[SIMULATE]`, `[PREDICT]`, `[CASCADE]`, `EVACUATE`).
     * Contextual Right Intelligence HUD: Single unified panel displaying Epistemic Validation Tag, Risk Assessment breakdown with Compound Synergy, Human Impact Telemetry, and AI Command Directive with priority interventions and evidence audit tokens.
     * Bottom Causal Chain Dock & Global Status Bar: Live causal cascade vector pipeline (`HEAVY RAIN -> SOIL SATURATION -> FLASH FLOOD -> ROAD FAILURE -> HOSPITAL ACCESS LOSS -> EVACUATION DELAY`) plus operational readiness metrics, with progressive disclosure tabs.

---

## 4. Component Adaptation & Preservation Matrix

| Component | Existing Implementation | Stitch Design Target | Action Plan |
| :--- | :--- | :--- | :--- |
| **Top Navigation** (`topNav.js`) | Fixed 48px bar with basic tabs and search box. | Fixed 80px orbital command bar with sub-bar provider health, coordinate indicator, live stream badge, and vectors. | **Adapt**: Restyle into Stitch top bar + sub-bar; connect search and vector chips directly to existing geocoding and `climate:flyTo`. |
| **Left Rail** (`leftPanel.js`) | Large permanent 280px docked panel showing all layers and sensor counts. | Compact collapsible floating HUD (`TACTICAL LAYERS`) toggled via button, expanding on demand. | **Adapt**: Convert from permanent dock to floating collapsible HUD with Stitch 4-tier category structure; wire toggles to existing Cesium layers. |
| **3D Earth / Cesium** | Interactive CesiumJS globe with polygon entities. | 70–80% viewport dominance, atmospheric glow, and holographic reticle targeting active location. | **Preserve & Enhance**: Keep full CesiumJS globe active underneath; add holographic reticle overlay and target sector pin on active city. |
| **Region / Hazard HUD** | Rendered inside right panel or bottom drawer. | Floating contextual HUD card pinned in viewport displaying locked sector, metrics, threat meters, and action buttons. | **Adapt / Create**: Implement floating contextual HUD card driven by active region/hazard state; wire action buttons to bottom drawer tabs. |
| **Right Intelligence Panel** (`rightPanel.js`) | Multi-card scrollable rail with separate sensor, subsystem, sources, and AI cards. | Single contextual glass HUD with epistemic tag, risk breakdown, human impact, and AI directive. | **Adapt**: Consolidate into Stitch single-flow layout; connect directly to existing store, regional conditions, and `/api/v1/ai/query`. |
| **Bottom Command Dock** (`bottomDrawer.js`) | Multi-tab bottom drawer with comparison table and controls. | Floating bottom dock with causal cascade pipeline summary when collapsed, expanding only one tab at a time. | **Adapt**: Style with Stitch tokens; add causal chain vector tracker row; ensure strict single-panel progressive disclosure. |
| **Status Bar** (`statusBar.js`) | Fixed bottom bar with status pills and UTC clock. | Integrated into bottom dock header and top sub-bar. | **Preserve & Integrate**: Synchronize telemetry and freshness counters with Stitch sub-bar indicators. |
| **Emergency Mode** | Generic mode state change. | High-priority focused command HUD, minimizing background UI, highlighting critical hazards and evacuation directives. | **Enhance**: Implement clean emergency focus state in shell coordinator. |

---

## 5. Dual Directory Strategy (`gods-eye-view/` vs. `Work/gods-eye-view/`)

* **Audit Finding**: `gods-eye-view/` is the active, tracked git development repository where all recent architectural enhancements, simulation wiring, and test suites reside. `Work/gods-eye-view/` is an earlier snapshot copy.
* **Authoritative Source**: `gods-eye-view/` is designated as the primary, authoritative frontend source.
* **Synchronization Plan**: All changes will be implemented and validated first in `gods-eye-view/`. Upon passing all unit and build tests, the modified panel and style files will be synchronized to `Work/gods-eye-view/` so both directories remain 100% buildable and passing.

---

## 6. Implementation Steps

1. **Design System & CSS Tokens**:
   * Update `gods-eye-view/src/climate/panels/climateShell.css` with the complete Stitch palette, typography (`Space Grotesk`, `Inter`, `JetBrains Mono`), glassmorphic panels, razor borders, and chamfered HUD cards.
2. **Top Navigation & Sub-Bar**:
   * Update `topNav.js` with the Stitch 2-tier header: main cockpit bar (brand, coordinate readout, vector chips, live stream pill, mode navigation) + sub-bar (provider status indicators: Open-Meteo, FIRMS, USGS, GDACS, GLOFAS, ESP32).
3. **Collapsible Left Tactical Layers HUD**:
   * Refactor `leftPanel.js` into a floating, collapsible HUD with categories: 1.0 Climate Telemetry, 2.0 Active Hazards, 3.0 Infrastructure, 4.0 Intelligence, wired to existing layer toggles.
4. **Contextual Region Focus HUD Card**:
   * Add the floating `LOCKED TARGET SECTOR` HUD card showing live regional telemetry, threat bars, exposed population, and direct action triggers (`[SIMULATE]`, `[PREDICT]`, `[CASCADE]`, `EVACUATE`).
5. **Contextual Right Intelligence Panel**:
   * Refactor `rightPanel.js` to match the Stitch Situational Matrix: epistemic badge, risk breakdown, human impact summary, and AI command directives grounded in evidence IDs.
6. **Bottom Command Dock & Progressive Disclosure**:
   * Refactor `bottomDrawer.js` into the Stitch bottom dock featuring the live causal cascade vector pipeline, operational summary, and single-tab progressive disclosure drawers.
7. **Cesium 3D Globe Visual Dominance**:
   * Ensure the central 70–80% viewport remains transparent and fully interactive, with Cesium spatial hazard polygons clearly visible.
8. **Testing & Synchronization**:
   * Run frontend tests (`node:test`), backend tests (`pytest`), production builds for both directories, and autonomous browser verification.
