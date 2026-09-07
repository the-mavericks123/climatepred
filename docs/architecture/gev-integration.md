# Climate Eye View — God's Eye View (GEV) Integration Architecture

**Document Version:** 1.0.0  
**Phase:** Phase 0 — GEV Understanding + S2 Integration Boundary  
**Role:** Software Engineer 2 (AI & Intelligence)  
**Date:** September 7, 2026  
**Status:** Verified Baseline  

---

## 1. Executive Summary & Context

Climate Eye View builds a planetary climate intelligence system on top of **God's Eye View (GEV)** as its geospatial and visualization foundation. 

This document defines the verified architectural baseline of GEV (upstream repository: `https://github.com/bilawalsidhu/gods-eye-view`) and establishes the strict engineering boundary between **Software 1 (Platform, 3D Globe, Visualization & Ingestion Transport)** and **Software 2 (AI, Intelligence, Modeling, Prediction, Evacuation & Response)**.

Under the engineering contract, Software 2 does not directly render into Cesium or manipulate GEV DOM/UI structures; instead, Software 2 produces structured intelligence payloads (GeoJSON, risk vectors, graphs, response plans, simulation states) that Software 1 ingests, manages in state, and renders as visual layers.

---

## 2. GEV Baseline & Upstream Environment

The baseline was verified from a fresh clone of upstream GEV without modifications to upstream code.

- **Upstream Repository:** `https://github.com/bilawalsidhu/gods-eye-view`
- **Target Git Commit:** `759652207fd1279ece97f0f19af566feb9a82146`
- **Commit Author & Date:** Bilawal Sidhu, Sat Sep 5 03:30:55 2026 -0500
- **Commit Message:** `fix: improve mapped installations and map-source guidance (#183)`
- **Runtime Environment:** Node.js `v24.15.0` (Node engine constraint in `package.json`: `>=24.14.0 <25 || >=26 <27`)
- **Package Manager:** npm `11.12.1` (`package-lock.json` lockfile version 3)
- **Install Command:** `npm install` (Clean install: 198 packages added, 0 compilation errors)
- **Startup / Development Command:** `npm run dev` (Runs Vite dev server, default port `4173`, HTTP 200 verified at `http://localhost:4173/`)
- **Production Build Command:** `npm run build` (Runs `vite build`, builds 157 modules to `dist/`, verified clean build in 13.4s)
- **Test Suite Command:** `npm test` (Runs `node scripts/run-unit-tests.mjs`, verified: 2,705 tests passed, 0 failed, 2 skipped, 14 memory allocation tests passed)
- **Setup Doctor Command:** `npm run doctor` (Runs `node scripts/setup-doctor.mjs`, verifies Node, npm, dependencies, and configured credentials)

---

## 3. Repository Structure

```
gods-eye-view/
├── .env.example              # Reference configuration and API keys
├── CHANGELOG.md              # Version and feature changelog
├── CONTRIBUTING.md           # Contribution guidelines
├── DATA_SOURCES.md           # Upstream data sources, APIs, licenses & terms
├── LICENSE                   # Upstream MIT License with 3rd-party data notices
├── README.md                 # Project overview and usage
├── SECURITY.md               # Security policy and credential handling
├── TESTING.md                # Test execution and regression tracking guidelines
├── config/                   # Static configuration files (e.g. CCTV source catalogs)
├── docs/                     # Documentation (CURRENT-STATE.md, KNOWN-ISSUES.md, etc.)
├── index.html                # Single-page application HTML entry point
├── package.json              # Project dependencies and npm scripts
├── package-lock.json         # Pinned dependency tree
├── pinokio/                  # Pinokio autonomous launcher scripts & recipes
├── public/                   # Public assets (icons, 3D glTF/GLB models, sample tiles)
├── scripts/                  # Development, QA, doctor, test, and build automation scripts
├── src/                      # Application JavaScript source code
│   ├── main.js               # Primary client-side application entry point
│   ├── camera.js / cameraVerbs.js # Camera control, orbit, waypoint flights
│   ├── contextStore.js       # Selected entities and spatial context store
│   ├── keySetup.js           # In-app credential provider management
│   ├── locations.js          # Preset cities, POIs, landmarks, bounding boxes
│   ├── mapStartup.js         # Photorealistic 3D Tiles vs keyless globe initialization
│   ├── mapStackController.js # Basemap switcher (Google 3D, Esri, OSM, Carto, Bing)
│   ├── renderGovernor.js     # Idle render-loop governor (demands vs requestRenderMode)
│   ├── scopeMask.js          # Lens vignette and military scope viewport shader
│   ├── ui.js                 # HUD management, control panels, styles, share links
│   ├── annotations/          # World-space voice annotation graphics and resolvers
│   ├── data/                 # All data layer modules, feeds, and adaptors
│   │   ├── manager.js        # DataLayerManager: registration, lifecycle, polling loops
│   │   ├── layerState.js     # Canonical layer serialization registry, URL codecs, options
│   │   ├── flights.js / militaryFlights.js # Live ADS-B aircraft tracking
│   │   ├── aisLiveVessels.js # Live AIS vessel positions (WebSocket proxy client)
│   │   ├── earthquakes.js    # USGS earthquake feed
│   │   ├── satellites.js     # CelesTrak TLE orbits & SGP4 propagation
│   │   ├── traffic.js        # TomTom live traffic flow vector tiles & simulation
│   │   ├── cctv.js           # Municipal CCTV traffic cameras & video frames
│   │   ├── firmsHeatmap.js   # NASA FIRMS active fire detection layer
│   │   ├── localGeojson.js   # Local infrastructure GeoJSON loader (dams, datacenters)
│   │   ├── radio.js          # Radio Browser directory & audio streaming
│   │   └── analystEngine.js  # Geospatial query engine for voice/assistant queries
│   ├── overlays/             # Screen-space world overlay subsystem
│   │   ├── worldOverlay.js   # Coordinated canvas/DOM renderer for labels, pins, cards
│   │   ├── worldOverlayDraw.js # Canvas primitive painters & text measurers
│   │   └── worldOverlayTokens.js # Visual styling tokens for overlay entities
│   ├── scenes/               # Automated scene playback and cinematic recordings
│   ├── styles/               # Visual shader styles (Thermal, Surveillance NVG, Noir, etc.)
│   └── voice/                # OpenAI Realtime WebRTC voice agent & tool dispatch
├── style.css                 # Master UI styling and layout stylesheet
├── tools/                    # Headless Cesium rendering and panorama tools
└── vite.config.js            # Build configuration and dev-server backend proxy middlewares
```

---

## 4. Frontend Framework, Build System & Entry Point

1. **Frontend Framework:** Vanilla Modern JavaScript (ESM). No React, Vue, Angular, or Next.js. DOM elements are created and manipulated via native browser APIs and modular controller classes (`ui.js`, `manager.js`, `mapStackController.js`).
2. **Build Tool:** Vite `v6.4.3` configured via `vite.config.js` with `vite-plugin-cesium` to bundle CesiumJS static assets, web workers, and third-party ESM dependencies (`@mapbox/vector-tile`, `satellite.js`, `egm96-universal`, `mgrs`, `pbf`).
3. **Entry Point:**
   - HTML: `index.html` loads `<link rel="stylesheet" href="./style.css">` and `<script type="module" src="./src/main.js"></script>`.
   - JavaScript: `src/main.js` bootstraps `init()`, setting up the Cesium `Viewer`, `StyleManager`, `DataLayerManager`, `MapStackController`, `SceneDirector`, and `initGevVoiceCommands`.

---

## 5. End-to-End Data Flow Architecture

```
[Upstream Data Source]
  (USGS, OpenSky, AISStream, FIRMS, Overpass, Local GeoJSON, Future Climate S2 APIs)
       │
       ▼
[Backend / Proxy Middleware] (vite.config.js / Production API Gateway)
  - CORS handling & API key brokering
  - In-memory rate limiting & TTL caching
  - Protocol translation (e.g. WebSocket upstream -> HTTP snapshot poll)
       │
       ▼
[Client Data Layer Module] (src/data/<layer>.js)
  - Invoked by DataLayerManager update loop
  - Fetch normalized JSON/GeoJSON payload
       │
       ▼
[Data Normalization & Validation]
  - Map external fields into normalized records (lat, lon, altitude, timestamps)
  - Compute feed status (nominal, loading, degraded, stale, fallback, unavailable)
       │
       ▼
[State Registration]
  - DataLayerManager lifecycle state (`enabled`, `lifecycleState`, `refreshEpoch`)
  - contextStore.js (`registerEntityContext`, `selectEntityContext` for selected entity)
       │
       ▼
[Geospatial Rendering]
  ├── 3D Globe Geometry: Cesium.CustomDataSource (Points, Polylines, Polygons, Ellipses, 3D glTF Models)
  └── 2D World-Anchored Screen Overlays: worldOverlay.js (Canvas cards, pins, collision-resolved labels)
       │
       ▼
[Cesium Canvas & HUD UI Viewport]
```

---

## 6. Geographic & Spatial Conventions

- **Coordinate System:** Standard WGS84 Geographic Coordinate System (EPSG:4326).
- **Coordinate Representation:**
  - Latitude: Decimal degrees (`lat`), range `[-90.0, 90.0]`.
  - Longitude: Decimal degrees (`lon` or `lng`), range `[-180.0, 180.0]`.
  - GeoJSON order: `[longitude, latitude, elevation]`.
  - Cesium Cartesian3 order: `Cesium.Cartesian3.fromDegrees(longitude, latitude, height_meters)`.
- **Altitude / Vertical Datum:**
  - Elevation is specified in meters above the WGS84 Reference Ellipsoid.
  - Orthometric / Mean Sea Level (MSL) heights from external datasets are converted to ellipsoidal heights using `egm96-universal` (`src/data/geoid.js`).
  - Ground-level features use `Cesium.HeightReference.CLAMP_TO_GROUND` or sample surface heights dynamically via `src/data/groundFloor.js` and `src/data/terrainHeightsProxy.js`.
- **Bounding Boxes:** Represented either as GeoJSON bounding boxes `[west, south, east, north]` or as nested coordinate bounds `{ southwest: { lat, lng }, northeast: { lat, lng } }`.

---

## 7. Layer Subsystem & Climate Eye View Extension Points

### 7.1 GEV Layer Contract
Every visual layer in GEV implements a standardized interface managed by `DataLayerManager` (`src/data/manager.js`):

```javascript
export const layerInterface = {
  id: 'unique-kebab-layer-id',      // Stable identifier string
  name: 'Human Readable Name',      // Display title for UI toggles
  icon: '🌊',                       // Display icon or emoji
  source: 'Data Provider',          // Attribution string
  updateInterval: 60000,            // Polling interval in ms (0 if static/event-driven)

  init(viewer) {},                  // Allocate Cesium data sources and primitives
  enable(viewer) {},                // Show layer geometry and arm update intervals
  disable(viewer) {},               // Hide layer geometry and clear overlay pins
  update(viewer) {},                // Fetch latest data and update visual primitives
  destroy(viewer) {},               // Teardown primitives and release resources
  getStats() {},                    // Return { count, lastUpdate, error, status }
  getAnalystRecords(maxCount) {},   // Optional: plain JSON-safe records for query engine
};
```

### 7.2 Layer Registration & URL Serialization Rule
- All registered layers **must** be declared in `LAYER_STATE_REGISTRY` (`src/data/layerState.js`).
- `DataLayerManager.finalizeRegistrations(LAYER_STATE_REGISTRY)` asserts a strict 1-to-1 match. Any layer registered in `manager.js` without a corresponding entry in `LAYER_STATE_REGISTRY` will throw an initialization exception and halt application startup.
- Each registry entry requires:
  - `id`: layer identifier
  - `token`: single unique alphanumeric character for URL share state
  - `disposition`: `'enabled-only'`, `'enabled+options'`, or `'enabled+mirrored-options'`

### 7.3 Identified Climate Eye View Layer Injection Points
Software 1 will implement the following layers conforming to the GEV contract, consuming intelligence data produced by Software 2:

| Planned Layer ID | Name | Type | Visualization Primitive | Consumed S2 Intelligence Payload |
|---|---|---|---|---|
| `climate-sensors` | Weather & Flood Sensors | Point Vector | CustomDataSource Billboards + WorldOverlay Cards | Sensor observations, anomaly scores, QA flags |
| `hazard-temperature` | Surface Heat Anomaly | Continuous Field | Cesium ImageryProvider / Dynamic Contours | Heat index, Land Surface Temp anomalies, WBGT |
| `hazard-flood-risk` | Inundation Depth & Extent | Polygon / Mesh | Clamped-to-ground GeoJSON polygons + depth ramp | Flood inundation boundaries, return-period zones |
| `hazard-drought-risk` | Agricultural & Hydro Drought | Polygon / Tile | Regional choropleths & soil moisture deficit tiles | Drought severity indices, soil moisture anomalies |
| `prediction-hazard` | Hazard Nowcast / Forecast | Time Series Geo | Multi-step temporal polygons with time-scrubber | Spatiotemporal hazard projections (+30m, +1h, +6h) |
| `compound-hazards` | Cascading Hazard Cascade | Risk Topology | Intersected polygons with hazard interaction badges | Multi-hazard intersection zones, cascade linkages |
| `vulnerability-zones` | Social & Physical Exposure | Polygon Vector | Extruded polygons (height = vulnerability score) | Social Vulnerability Index, critical facility exposure |
| `evacuation-routes` | Dynamic Evacuation Network | Polyline Graph | Clamped polyline corridors (green=clear, red=blocked) | Optimal route paths, congestion levels, cut-off risks |
| `emergency-resources` | Relief & Shelters | Point Vector | Billboards + WorldOverlay capacity readouts | Shelter capacities, hospital status, resource triage |

---

## 8. State Management Architecture

GEV manages state across five targeted modules rather than a single monolithic Redux/Vuex store:

1. **Layer State & Lifecycle (`src/data/manager.js`):**
   - Authoritative runtime state for every registered layer (`enabled`, `lifecycleState`, `refreshing`, `intervalId`, `toggleChain`).
   - Handles asynchronous toggling races and superseding intent epochs.
2. **Context & Selected Entity Store (`src/data/contextStore.js`):**
   - Global in-memory registry (`window.__gevContextStore`) holding active entity metadata (`id`, `layerId`, `name`, `coordinates`, `properties`).
   - Dispatches browser window custom events: `gev:entity-selected`, `gev:awareness-subject-selected`.
3. **Map Stack & Basemap State (`src/mapStackController.js`):**
   - Current 3D tileset / imagery stack (`photoreal`, `esri-imagery`, `osm-vector`, etc.).
   - Dispatches `gev:map-stack-changed` events.
4. **Visual & UI Preset State (`src/ui.js`):**
   - Active post-processing style (`normal`, `surveillance`, `thermal`, `retro`, `noir`, `anime`).
   - HUD visibility, panel collapse states (stored in `localStorage` under `godsEyeView.*`).
5. **Share Link URL State (`src/data/layerState.js` & `src/sharelink.js`):**
   - Bidirectional serialization between browser query parameters (`?v=2&c=...&l=...`) and application state.

**Climate Eye View State Recommendation:**
Climate intelligence state (selected hazard event, active scenario time-step, simulated interventions) must integrate through a dedicated `climateContextStore` managed by Software 1, matching the event-driven pattern of `contextStore.js` (`gev:climate-hazard-selected`, `gev:scenario-step-changed`) without mutating core GEV data structures.

---

## 9. API & Data Communication Patterns

### 9.1 Existing GEV API Patterns
1. **Dev-Server Middleware Broker (`vite.config.js`):**
   - In development, Vite Connect middlewares intercept `/api/*` requests.
   - Upstream keys (NASA FIRMS, TomTom, OpenSky, OpenAI) are kept server-side and never exposed to the client bundle (except `GOOGLE_MAPS_API_KEY` and `CESIUM_ION_TOKEN` which are required by client WebGL renderers).
   - In-memory caching and request coalescing (e.g. OpenSky OAuth token refresh deduplication, FIRMS 30-minute response cache).
2. **Client-Side Polling:**
   - Data layers execute periodic `fetch()` requests inside an awaited `update()` loop scheduled by `DataLayerManager`.
   - Error handling: HTTP non-200 and parsing failures update `_lastError` and feed state to `'degraded'` or `'unavailable'` without crashing the application.

### 9.2 Realtime Mechanisms in GEV
- **Upstream WebSocket with Polling Bridge:** In `aisLiveProxy()`, the Node backend establishes an upstream WebSocket connection to `AISStream`, buffers incoming position reports in memory, and serves normalized rows to the frontend via `/api/ais-live` HTTP polling.
- **WebRTC DataChannel / Audio:** In `src/voice/gevRealtime.js`, voice intelligence connects directly to OpenAI Realtime via WebRTC after obtaining an ephemeral token from `/api/realtime/token`.

---

## 10. Configuration & Environment Variables

GEV environment configuration is managed via `.env` / process environment variables:

- **Client-Exposed:**
  - `GOOGLE_MAPS_API_KEY`: Direct photorealistic 3D Tiles and Places geocoding.
  - `CESIUM_ION_TOKEN`: Cesium ion assets and Cesium World Terrain.
- **Server-Side Credentials:**
  - `OPENAI_API_KEY`, `OPENAI_REALTIME_MODEL`: Voice intelligence agent.
  - `OPENSKY_CLIENT_ID`, `OPENSKY_CLIENT_SECRET`: ADS-B flight tracking.
  - `AISSTREAM_API_KEY`: Live maritime vessel tracking.
  - `FIRMS_MAP_KEY`: NASA FIRMS active fire detection.
  - `TOMTOM_API_KEY`: TomTom traffic flow vector tiles.
- **Server Host & Port:**
  - `PORT=4173`, `HOST=localhost`.

**Rule:** No API secrets or private credentials may be checked into version control. Future S2 intelligence services will define their configuration in `intelligence/.env.example`.

---

## 11. Upstream Repository, Licenses & Attribution Verification

- **Upstream Repository:** `https://github.com/bilawalsidhu/gods-eye-view`
- **Exact GEV Commit:** `759652207fd1279ece97f0f19af566feb9a82146`
- **License Name:** MIT License (covering source code only) with non-MIT third-party data and 3D asset exceptions
- **License File Path:** [gods-eye-view/LICENSE](file:///c:/Users/yagna/OneDrive/Documents/models/gods-eye-view/LICENSE)
- **Attribution Requirements:**
  - **Google Maps Platform Terms of Service:** Mandates on-screen visible attribution container (`#cesium-credits` rendered via Cesium's `creditContainer`) whenever Google Photorealistic 3D Tiles are loaded. This container is styled subtly but remains active in all modes.
  - **In-App Data Attribution Popover:** Handled by `registerDataCredits(viewer)` (`src/data/dataCredits.js`), surfacing verbatim attribution strings for all active feeds in the expandable bottom-left lightbox.
- **Third-Party Asset & Data Licensing Concerns:**
  - **TeleGeography Submarine Cable Map** (`src/data/local_data/telegeography_submarine_cables/`): Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported (`CC BY-NC-SA 3.0`). **Strictly prohibits commercial use.** If Climate Eye View is deployed in any commercial context, these assets must be excised or a commercial agreement executed with TeleGeography.
  - **OpenStreetMap & Open Infrastructure Map Extracts** (Dams and Datacenters under `src/data/local_data/`): Governed by the Open Database License (`ODbL 1.0`), requiring attribution and share-alike on derivative databases.
  - **NASA FIRMS Active Fires:** U.S. Public Domain / CC0 (citation and attribution requested).
  - **USGS Earthquakes:** U.S. Geological Survey Public Domain.
  - **3D Models** (`public/models/`): Not licensed under MIT. Each glTF/GLB asset carries individual licenses (CC-BY, CC0, etc.) documented with author and modification details in [public/models/README.md](file:///c:/Users/yagna/OneDrive/Documents/models/gods-eye-view/public/models/README.md).
  - **Live External APIs:** Live feeds (OpenSky Network, AISStream, TomTom, Open-Meteo) operate under their respective provider developer terms; some forbid commercial resale or impose daily request quotas.

---

## 12. Software 2 → Software 1 Integration Boundary

Software 2 operates as an independent intelligence subsystem. It produces structured data conforming to strictly versioned JSON / GeoJSON contracts. Software 1 consumes this data, maps it into GEV state, and handles all Cesium rendering and user interactions.

```
┌─────────────────────────────────────────────────────────┐
│              Software 2 (AI & Intelligence)             │
│                                                         │
│  - Multi-hazard physical models (Heat, Flood, Drought)  │
│  - Data fusion & provenance tracking                   │
│  - ML forecasting & nowcasting                         │
│  - Compound disaster cascading failure graph           │
│  - Social & physical vulnerability indexing             │
│  - Evacuation pathfinding & resource optimization       │
│  - Digital twin simulation & counterfactual analysis    │
│  - Explainability & model confidence telemetry         │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼ Structured JSON / GeoJSON
┌─────────────────────────────────────────────────────────┐
│                S2 → S1 Integration Boundary             │
│                                                         │
│  - REST API: /api/climate/* (Snapshots, Scenarios, Plans)│
│  - Streaming: WebSocket / SSE (Alerts, Dynamic Routes)  │
│  - Shared Schemas: /schemas/climate/v1/*                │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│               Software 1 (GEV Platform & UI)            │
│                                                         │
│  - GEV DataLayerManager registration                   │
│  - Cesium CustomDataSource & 3D primitive rendering     │
│  - WorldOverlay screen-space cards & labels             │
│  - Camera focus, flight paths & landmark navigation     │
│  - UI toggle panels, time-scrubbers & HUD displays      │
│  - MQTT sensor ingestion pipeline & PostGIS persistence │
└─────────────────────────────────────────────────────────┘
```

### 12.1 S2 Output Categories & Schemas
1. **Hazard State Payload:** GeoJSON FeatureCollection of active hazard zones, intensities, return periods, and spatial polygons.
2. **Prediction Forecast Series:** Temporal sequences of predicted hazard boundaries at the canonical initial prediction horizons: `$T+30\text{m}$`, `$T+1\text{h}$`, and `$T+6\text{h}$` with probabilistic confidence intervals.
3. **Compound Event Graph:** Directed acyclic graph (DAG) representing cascading failures (e.g. Heatwave $\to$ Grid Failure $\to$ Water Pump Station Shutdown $\to$ Hospital Emergency).
4. **Vulnerability Assessment:** Zonal vulnerability indices combining census social vulnerability, infrastructure critical dependencies, and population demographics.
5. **Evacuation Routes & Road Cut-Offs:** GeoJSON multilinestrings representing optimal evacuation corridors, road closure probabilities, and choke points.
6. **AI Response Plan:** Prioritized intervention matrix (shelter opening, sandbag deployment, cooling center dispatch) with resource requirement estimates.
7. **Digital Twin Simulation Output:** Comparative scenario state matrices representing baseline vs intervened disaster progression.
8. **Explainability & Provenance Metadata:** Per-prediction feature importance rankings, input data quality scores, and model uncertainty bounds.

---

## 13. System Ownership Boundary

```
================================================================================
SOFTWARE 1 OWNS:
  - God's Eye View (GEV) integration and codebase maintenance
  - 3D Globe (CesiumJS) configuration, shaders, atmosphere, tilesets
  - Frontend UI, HUD, control panels, toggle trays, layout responsiveness
  - Visual layer rendering (Cesium DataSources, Primitives, WorldOverlay)
  - Backend API routing and dev-server / production proxies
  - Ingestion transport (MQTT broker, connection pooling, raw sensor ingest)
  - PostGIS spatial database storage, querying, and indexing
  - Realtime transport layer (WebSocket / SSE delivery between server and client)
================================================================================
SOFTWARE 2 OWNS:
  - Intelligence subsystem architecture and execution pipeline
  - Data fusion algorithms, cleansing, and cross-sensor normalization
  - Data quality scoring, validation gates, and provenance tracking
  - Physical & empirical hazard models (Heat stress, Flood hydraulics, Drought)
  - Machine learning prediction, nowcasting, and spatiotemporal forecasting
  - Compound / cascading disaster simulation and graph analysis
  - Human and infrastructure vulnerability modeling
  - Dynamic evacuation routing optimization and capacity modeling
  - Digital twin simulation engine and counterfactual evaluation
  - AI response planner and resource allocation optimization
  - Explainability, evidence synthesis, and model uncertainty quantification
  - Model validation, calibration against historical benchmarks, and evaluation
================================================================================
SHARED CONTRACTS:
  - Data transfer schemas (JSON Schema / Pydantic models / GeoJSON RFC 7946)
  - API endpoint specifications and error formats
  - End-to-end integration tests validating S2 output ingestion in S1 layers
  - Formal change-control process for contract and schema revisions
================================================================================
```

---

## 14. Known Limitations & Pre-existing Issues in GEV

The following pre-existing conditions were identified during repository inspection:
1. **Height-Datum Latency:** As documented in `gods-eye-view/docs/KNOWN-ISSUES.md`, newly visited locations experience cold-start floor latency where grounded features float or sink for 1–2 poll cycles until local terrain heights resolve.
2. **Dense Road Traffic Panning:** Street-level traffic vector loading can experience delayed tile rendering during high-speed camera pans across dense urban cores.
3. **Saved Panel Positions:** CCTV and HUD panels cached in browser `localStorage` can occasionally restore off-screen if display resolution changes.
4. **API Rate Limits / Key Requirements:** NASA FIRMS, TomTom Traffic, OpenSky, and OpenAI Realtime require valid API credentials; without them, corresponding layers switch to keyless fallback or indicate `'KEY REQUIRED'`.
5. **Large Bundle Warning:** Production build generates chunks larger than 1,500 kB (e.g. `egm96-universal`, `regions.js`, `cesium`). This is pre-existing and does not prevent successful production builds.

---

## 15. Conclusion & Verification Verdict

The God's Eye View repository has been thoroughly inspected and verified against the actual code. The integration architecture and boundaries for Climate Eye View have been formally documented.

**Phase 0 Status: COMPLETE / PASS**  
**Recommendation: READY FOR PHASE 1**
