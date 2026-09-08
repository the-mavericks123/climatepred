# Climate Eye Global Data Integration Architecture

## 1. Executive Summary

Climate Eye View decouples the physical telemetry mesh from system-wide operational readiness. The intelligence pipeline and 3D geospatial operations are driven primarily by authoritative, high-cadence global satellite feeds, numerical weather prediction systems, and seismic monitoring networks. 

Physical hardware (such as ESP32 mesh nodes or LoRa edge stations) serves as an optional, high-resolution ground-truth augmentation tier. When zero physical nodes are connected, the top-level operational status remains:

```text
SYSTEM: OPERATIONAL
GLOBAL DATA: ONLINE
INTELLIGENCE: ACTIVE
REALTIME: CONNECTED
PHYSICAL SENSOR MESH: 0 NODES
ESP32 HARDWARE: NOT CONNECTED (OPTIONAL)
```

The system ingests, normalizes, spatially indexes, and fuses multi-modal hazard feeds across Earth's surface, streaming deterministic hazard zones, compound cascades, and tactical evacuation plans to the photorealistic 3D Cesium globe.

---

## 2. End-to-End Pipeline Architecture

The deterministic intelligence pipeline operates on an unyielding unidirectional flow:

```mermaid
flowchart TD
    subgraph S1_GLOBAL_FEEDS [Authoritative Global Live Feeds]
        OM[Open-Meteo API\n36 Reference Ground Stations]
        FIRMS[NASA FIRMS Satellite\nVIIRS / MODIS Active Fires]
        USGS[USGS Earthquake Hazards\nM2.5+ Global Feeds]
        GDACS[GDACS GeoRSS Alerts\nUN/EC Multi-Hazard]
        GLOFAS[Copernicus GloFAS Adapter\nRiver Discharge & Flood]
        ESP32[Physical Sensor Mesh (Optional)\nESP32 / LoRa Environmental]
    end

    subgraph S2_FUSION_ENGINE [Data Ingestion, Normalization & Spatial Fusion Layer]
        SCHED[ExternalDataScheduler\nAsync Poller & Background Refresh]
        VAL[Payload Normalizer\nField Boundary & Null Guard]
        CACHE[TTL Cache & Circuit Breakers\nFallback Graceful Degradation]
        SPATIAL[Spatial Indexer & Grid Clusterer\nGeoJSON Feature Generation]
    end

    subgraph S3_HAZARD_INTELLIGENCE [Deterministic Hazard & Risk Engine]
        HE[Hazard Engine\nThermal, Fire, Flood, Seismic]
        PRED[Prediction Engine\n+30m / +60m / +360m Projections]
        CASCADE[Compound Cascade Generator\nMulti-Hazard Dependency Graph]
        VULN[Human Vulnerability & SVI Index\nHigh-Density Risk Aggregation]
        EVAC[Dynamic Evacuation Router\nSafe Egress & Tactical Corridors]
        RESP[Response Directive Generator\nActionable Emergency Playbooks]
    end

    subgraph S4_EXPLAINABILITY [Explainability & Reasoning Layer]
        AI[AI Command Center\nDeterministic Evidence Mode]
    end

    subgraph S5_VISUALIZATION [Photorealistic 3D Cesium Client]
        GLOBE[Cesium 3D Globe Viewer\nCustomDataSource Entity Hierarchy]
        HUD[Tactical Hazard Popover HUD\nTelemetry & Non-Risk Attribution]
        PANEL[Telemetry & Operations Cards\nDual Right Panel & Status Bar]
    end

    OM --> SCHED
    FIRMS --> SCHED
    USGS --> SCHED
    GDACS --> SCHED
    GLOFAS --> SCHED
    ESP32 -. Optional Ground Truth .-> VAL

    SCHED --> VAL
    VAL --> CACHE
    CACHE --> SPATIAL
    SPATIAL --> HE

    HE --> PRED
    PRED --> CASCADE
    CASCADE --> VULN
    VULN --> EVAC
    EVAC --> RESP

    RESP --> AI
    HE --> GLOBE
    CASCADE --> GLOBE
    EVAC --> GLOBE
    AI --> PANEL
    GLOBE --> HUD
```

---

## 3. Subsystem Components & Responsibilities

### 3.1. External Data Acquisition Layer (`intelligence/external_data/`)

1. **`providers.py`**:
   - Implements provider clients with asynchronous HTTP (`httpx.AsyncClient`) with connection pooling and timeouts (10.0s).
   - **`OpenMeteoProvider`**: Polls 36 strategic reference stations covering all continents, polar regions, and microclimates. Extracts 2-meter air temperature, relative humidity, surface pressure, 1-hour precipitation, and 10-meter wind speed.
   - **`NASAFIRMSProvider`**: Ingests active thermal anomalies from VIIRS and MODIS satellites. Performs spatial clustering to collapse individual fire points into cohesive hazard zones with cumulative radiative power (FRP in Megawatts).
   - **`USGSProvider`**: Ingests real-time GeoJSON earthquake data (`all_day.geojson`, `2.5_day.geojson`), filtering for significant ground acceleration and depth.
   - **`GDACSProvider`**: Ingests UN/EC Global Disaster Alert and Coordination System multi-hazard GeoRSS feeds (Tropical Cyclones, Floods, Earthquakes, Volcanoes, Droughts).
   - **`GloFASProvider`**: Adapter interface for European Copernicus Global Flood Awareness System. Enforces strict honesty: if `CDS_API_KEY` is not present, reports status as `UNAVAILABLE` without synthetic mock data.

2. **`scheduler.py`**:
   - Manages asynchronous background polling loops with individual provider cadences.
   - Implements exponential backoff and circuit breaker state tracking to prevent cascade failures on upstream rate limiting.
   - Houses an in-memory thread-safe cache with configurable TTLs.

3. **`router.py`**:
   - Exposes RESTful endpoints under `/api/v1/global`:
     - `GET /sources`: Status, health, provider latency, and last-updated timestamps for all 5 providers.
     - `GET /hazards`: Unified GeoJSON collection of all currently active global hazard zones.
     - `GET /events`: Active humanitarian and disaster alerts with severity scoring and affected areas.
     - `GET /weather`: Aggregated weather measurements across global reference coordinates.
     - `GET /ai-summary`: Deterministic AI Command Center executive briefings.
     - `POST /sync`: Force synchronization of all live feeds.

### 3.2. Data Normalization & Invariant Preservation

- **Value Preservation Invariant (`water_level = null`)**:
  Weather stations and atmospheric models do not possess hydrometric riverbed/coastal gauge sensors. Coercing missing hydrometric data to `0.0` or `0` creates false negative flood risk assessments. The normalization engine enforces `water_level = null` for all pure meteorological observations.
- **Epistemic Classification**:
  Every emitted entity contains an explicit `epistemic_status`:
  - `OBSERVED`: Direct instrument measurement (satellite radiometer, seismograph, weather station).
  - `INFERRED`: Derived via spatial interpolation, compound cascade matrices, or physical propagation formulas.
  - `PREDICTED`: Time-series projection (+30m, +60m, +360m) with lower-bound confidence intervals.
  - `SIMULATED`: Strictly assigned during synthetic tabletop exercises.

---

## 4. Frontend Data Layer & State Management (`gods-eye-view/src/climate/`)

1. **`climateStore.js`**:
   - Centralized immutability-focused reactive state tree.
   - Tracks global feed status, active hazard zones, spatial grids, AI reasoning outputs, and physical sensor nodes.
   - Implements subscriber lifecycle allowing reactive DOM and Cesium rendering without polling loops.

2. **`globalHazardsLayer.js`**:
   - Cesium `CustomDataSource` managing dynamic 3D rendering of:
     - **Heat Zones**: Thermal pulsing ellipsoids colored by peak temperature gradient.
     - **Wildfire Clusters**: Fire Radiative Power (FRP) billboard markers with dynamic ember particle rings.
     - **Flood Zones**: Hydrometric polygons with water inundation depth vectors.
     - **Earthquake Rings**: Concentric seismic P/S wave shockwave wavefronts with Richter magnitude scaling.
     - **Cyclone Tracks**: Storm trajectory paths with wind radius cones.
     - **Compound Cascades**: Connecting geodesic splines illustrating inter-hazard cascading triggers.
   - Implements Cesium `ScreenSpaceEventHandler` for click picking, rendering tactical popover HUDs directly over target coordinates.

3. **`rightPanel.js` & `statusBar.js`**:
   - Top-level status header displaying decoupled operational readiness.
   - Dedicated "Global Data Sources" telemetry card detailing Open-Meteo, NASA FIRMS, USGS, GDACS, Copernicus GloFAS, and physical ESP32 status.
   - Dedicated AI Command Center running in `ACTIVE — DETERMINISTIC EVIDENCE MODE`.

---

## 5. Circuit Breakers & Failure Handling

| Provider | Failure Mode | Circuit Action | UI Representation |
| :--- | :--- | :--- | :--- |
| **Open-Meteo** | HTTP 429 Rate Limit / Timeout | Trips circuit breaker for 60s; serves cached weather data with `stale: true` | `GLOBAL: ONLINE (DEGRADED)` |
| **NASA FIRMS** | 503 Gateway / Upstream Outage | Holds last valid 24h satellite orbital swath; marks timestamp | `NASA FIRMS: CACHED` |
| **USGS** | Network unreachable | Retries after 30s exponential ladder; maintains active seismic zones | `USGS: RECONNECTING` |
| **GloFAS** | Missing `CDS_API_KEY` | Zero fabricated river discharge; reports honest epistemic unavailable | `GLOFAS: UNAVAILABLE (REQUIRES KEY)` |
| **ESP32 Mesh** | Physical hardware disconnected | Physical mesh count set to 0; operational status remains healthy | `PHYSICAL SENSOR MESH: 0 NODES (OPTIONAL)` |

---

## 6. Real-Time Streaming & Event Bus

The platform provides a dual-channel real-time architecture:
1. **WebSocket Telemetry Stream (`/ws/telemetry`)**: Streams high-frequency sensor packets when physical nodes are connected, maintaining 500ms latency.
2. **WebSocket Global Hazard Stream (`/ws/global-hazards`)**: Pushes newly detected global hazard zones, updated predictions, and compound cascade alerts instantly to connected 3D globes.
