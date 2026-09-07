# Climate Eye View — System Architecture

**Document Version:** 1.0.0  
**Phase:** Phase 0 — Baseline & System Boundary Specification  
**Status:** Verified Baseline  

---

## 1. System Overview

Climate Eye View is a planetary-scale climate intelligence and disaster decision-support platform. It pairs high-fidelity geospatial visualization with multi-hazard AI modeling, early warning prediction, compound risk modeling, and automated emergency response planning.

The system is structured as two cleanly decoupled subsystems governed by a strict engineering contract:

1. **Software 1 (GEV Platform & Visualization):** Built on the verified God's Eye View (GEV) foundation, providing photorealistic 3D globe rendering, camera navigation, HUD controls, layer management, MQTT telemetry ingestion, and PostGIS storage.
2. **Software 2 (AI & Intelligence):** A Python-based intelligence engine providing data fusion, physical hazard models (Heat, Flood, Drought), ML predictive forecasting, cascading failure graphs, vulnerability assessment, dynamic evacuation pathfinding, digital twin simulation, and tactical response planning.

---

## 2. Subsystem Ownership & Boundaries

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIMATE EYE VIEW SYSTEM                         │
└────────────────────────────────────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│     SOFTWARE 1 SUBSYSTEM          │       │     SOFTWARE 2 SUBSYSTEM          │
│   (Platform & Visualization)      │       │     (AI & Intelligence)           │
├───────────────────────────────────┤       ├───────────────────────────────────┤
│ • GEV Core & CesiumJS Globe       │       │ • Multi-Source Sensor Fusion      │
│ • Camera, Navigation & Cinematic  │       │ • Data Quality & Provenance       │
│ • UI HUD, Panels & Control Trays  │       │ • Heat Stress (WBGT) Modeling     │
│ • Cesium Layer Renderers:         │       │ • Hydrological Flood Modeling     │
│   - CustomDataSource (3D entities)│       │ • Drought & Moisture Modeling     │
│   - WorldOverlay (screen cards)   │       │ • ML Nowcasting & Forecasting     │
│   - Ground-clamped geometries     │       │ • Cascading Compound Disasters    │
│ • MQTT Broker Ingestion Transport │       │ • Social Vulnerability Indexing   │
│ • PostGIS Spatial Database Storage│       │ • Dynamic Evacuation Routing      │
│ • Realtime WebSocket/SSE Transport│       │ • Digital Twin Simulation Engine  │
│ • API Gateway & Reverse Proxy     │       │ • AI Emergency Response Planner   │
│                                   │       │ • Explainability & Uncertainty    │
│                                   │       │ • Model Validation & Calibration  │
└───────────────────────────────────┘       └───────────────────────────────────┘
         ▲                                                   ▲
         │                                                   │
         └───────────────────┬───────────────────────────────┘
                             │
                  SHARED CONTRACT BOUNDARY
                  • GeoJSON (RFC 7946) & WGS84 (EPSG:4326)
                  • Pydantic / JSON Schemas (/schemas/climate/v1)
                  • REST Endpoints (/api/climate/*)
                  • Streaming Event Channels (climate:alerts, climate:routes)
```

---

## 3. Verified Geospatial & Data Contract

| Contract Element | Specification | Rationale & Verification |
|---|---|---|
| **Datum / CRS** | WGS84 (EPSG:4326) | Verified from CesiumJS native ellipsoid and GEV `locations.js` |
| **Coordinates** | Decimal degrees (`lat`, `lon`) | GeoJSON standard: `[lon, lat, elevation]`. Cesium API: `fromDegrees(lon, lat, height)` |
| **Vertical Reference** | Meters above WGS84 ellipsoid | Conversion from MSL geoid via `egm96-universal` (`src/data/geoid.js`) |
| **Layer Interface** | GEV `DataLayerManager` interface | Required methods: `init()`, `enable()`, `disable()`, `update()`, `destroy()`, `getStats()` |
| **Layer Registration** | Sealed `LAYER_STATE_REGISTRY` | Strict 1-to-1 match required by `DataLayerManager.finalizeRegistrations()` |
| **Screen Overlays** | GEV `worldOverlay` system | 2D canvas/DOM cards and labels with collision resolution and UI occluder avoidance |
| **Selection Context** | `contextStore.js` event bus | `registerEntityContext()`, `selectEntityContext()`, dispatches `gev:entity-selected` |

---

## 4. Intelligence Outputs (S2) to Visualization Layers (S1)

Software 2 produces structured domain entities that map directly into Software 1 layer implementations:

1. **Hazard State Payload:** GeoJSON polygons with hazard classification (`heat`, `flood`, `drought`), severity index `[0.0, 1.0]`, and estimated population exposure.
2. **Predictive Horizon Series:** Forecast state snapshots at canonical initial horizons ($T+30\text{m}$, $T+1\text{h}$, $T+6\text{h}$) including uncertainty envelopes.
3. **Compound Risk Topology:** Directed risk graphs linking cascading failure modes across infrastructure and environmental sectors.
4. **Vulnerability Zones:** Choropleth polygons representing composite Social Vulnerability Indices (SVI) and critical infrastructure dependency trees.
5. **Evacuation Corridors:** Route multilinestrings scored for traversability, congestion delay, and active hazard flood risk.
6. **Tactical Action Plans:** Structured intervention matrices specifying action types, designated locations, resource allocations, and priority weights.
7. **Evidence & Explainability Records:** Sensor attribution graphs and model confidence metrics justifying recommendations.

---

## 5. Software Engineering Governance

- **Phase Isolation:** Phase 0 establishes architectural baselines only. No hazard calculations, ML models, or FastAPI services are deployed in Phase 0.
- **Contract Immobility:** Neither Software 1 nor Software 2 may alter shared schemas or integration endpoints unilaterally.
- **Reproducibility:** All build scripts, doctor scripts, unit tests, and performance benchmarks must run cleanly on supported runtimes.
