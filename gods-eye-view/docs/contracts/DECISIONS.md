# Climate Eye Architectural & Hardware Decisions

This document records the foundational architectural decisions, sensor specifications, and hardware contracts for Climate Eye and the ClimateMesh node network.

---

## DECISION-001: ClimateMesh Hardware Sensor Scope Freeze

* **Date:** 2026-09-07
* **Status:** APPROVED / FROZEN
* **Scope:** Physical node deployment and telemetry contract boundaries.

### 1. Hardware Inventory & Capabilities

The sensor suite for the primary ClimateMesh ground monitoring station is frozen to the following components:

| Hardware Component | Sensor Role & Measured Parameters | Protocol / Interface |
| :--- | :--- | :--- |
| **ESP32** | Central node controller, sensor polling, WiFi/mesh network transmission | SPI / I2C / ADC / UART |
| **BME280** | Ambient air temperature (°C), relative humidity (%RH), barometric pressure (hPa) | I2C |
| **Rain Sensor** | Precipitation detection and rainfall rate sensing | Digital GPIO / Analog ADC |
| **Capacitive Soil-Moisture Sensor** | Volumetric soil water content (% VWC) without electrode oxidation | Analog ADC |
| **PMS5003** | Particulate matter laser particle counter: PM1.0, PM2.5, PM10 concentrations (µg/m³) | Serial UART (TX/RX) |
| **BH1750** | Ambient illuminance / solar irradiance proxy (lux) | I2C |
| **Power & Wiring** | Regulated DC power, wiring harnesses, decoupling capacitors, and weatherized bus lines | Core Infrastructure |

### 2. Explicitly Excluded Hardware

* **Optical Sensor / Camera:** **NOT REQUIRED.**
  * No physical camera, lens module, or optical sensor is included in the ground station build.
  * Application software, backend endpoints, and data contracts MUST NOT require, wait for, or create dependencies on video frames, camera snapshots, or optical imagery from ground nodes.

### 3. Software Contract & Architecture Implications

1. **Telemetry Payload Contract:**
   * Telemetry ingestion schemas must strictly bind to the physical parameters produced by the verified sensors:
     * Atmospheric: `temperature`, `humidity`, `pressure`
     * Precipitation: `rain_detected`, `rain_intensity`
     * Soil/Ground: `soil_moisture`
     * Air Quality: `pm1_0`, `pm2_5`, `pm10`
     * Light/Solar: `lux`
     * System: `battery_voltage`, `rssi`, `uptime`
2. **ClimateMesh Scalability:**
   * Telemetry envelopes must include a distinct `node_id`, geographic `location` (latitude, longitude, altitude), and RFC3339 `timestamp`.
   * The schema is node-agnostic, ensuring additional ClimateMesh nodes can join the network without schema migration or breaking changes to the 3D globe visualization.

---

## DECISION-002: ClimateMesh Logical Node Identities & Sensor Allocations

* **Date:** 2026-09-07
* **Status:** APPROVED / FROZEN
* **Scope:** ClimateMesh ground node profiles, telemetry semantics, and sensor mapping.

### 1. Logical Node Architecture Overview

ClimateMesh utilizes data-driven logical node profiles mapped to physical sensor allocations. Each node identity corresponds to a specialized environmental monitoring purpose using subsets of the frozen hardware inventory (ESP32, BME280, Rain Sensor, Capacitive Soil-Moisture Sensor, PMS5003, BH1750).

**Critical Constraint:** Optical sensors and cameras are strictly **NOT REQUIRED** and have no software dependencies across all node profiles.

### 2. Node Allocation Table

| Node ID | Identity / Profile | Primary Purpose | Allocated Sensors | Primary Measurements |
| :--- | :--- | :--- | :--- | :--- |
| **`NODE-001`** | **Weather** | Baseline meteorological observation & microclimate ground truth | ESP32, BME280, BH1750 | Ambient temperature (°C), relative humidity (%RH), barometric pressure (hPa), illuminance / solar proxy (lux) |
| **`NODE-002`** | **Rain / Flood** | Precipitation event onset, rainfall intensity, and flash flood risk indexing | ESP32, Rain Sensor, BME280 | Precipitation status (binary detected/clear), rain rate / analog accumulation index, barometric pressure trend (hPa), ambient temp/humidity |
| **`NODE-003`** | **Agriculture** | Soil hydrology, drought risk detection, and crop microclimate monitoring | ESP32, Capacitive Soil-Moisture Sensor, BME280, BH1750 | Volumetric soil moisture (% VWC), ground-level air temperature (°C), relative humidity (%RH), solar exposure (lux) |
| **`NODE-004`** | **Air Quality** | Particulate pollution tracking, wildfire smoke / aerosol detection, and AQI computation | ESP32, PMS5003, BME280 | Particulate matter PM1.0, PM2.5, PM10 mass concentrations (µg/m³), air temperature (°C), relative humidity (%RH for hygroscopic compensation) |
| **`NODE-005`** | **Urban Heat** | Urban heat island (UHI) thermal mapping, microclimate hot-spot tracking, and radiant heat exposure | ESP32, BME280, BH1750 | Ambient surface/air temperature (°C), relative humidity (%RH), ambient illuminance / solar exposure (lux), derived heat index |

### 3. Data-Driven Node Telemetry Contract

All ClimateMesh nodes emit telemetry envelopes matching this canonical structure:

```json
{
  "node_id": "NODE-001",
  "profile": "weather",
  "timestamp": "2026-09-07T22:45:00Z",
  "location": {
    "latitude": 30.2672,
    "longitude": -97.7431,
    "altitude_m": 149.0
  },
  "telemetry": {
    "temperature_c": 26.4,
    "humidity_rh": 58.2,
    "pressure_hpa": 1013.25,
    "lux": 12500,
    "rain_detected": false,
    "rain_rate_raw": 0,
    "soil_moisture_pct": null,
    "pm1_0_ug_m3": null,
    "pm2_5_ug_m3": null,
    "pm10_ug_m3": null
  },
  "diagnostics": {
    "battery_v": 3.92,
    "rssi_dbm": -64,
    "uptime_s": 84210
  }
}
```

* Unused sensor attributes for a given node profile evaluate to `null` or are omitted per profile schema.
* Future physical node instances (`NODE-006`+) inherit one of the above profiles or define a combined profile without schema migration.

---

## DECISION-003: Canonical Climate Eye MQTT Telemetry Envelope (v1.0.0)

* **Date:** 2026-09-07
* **Status:** APPROVED / FROZEN
* **Scope:** MQTT message payload contract across all ClimateMesh nodes and ingest ingestion pipelines.

### 1. Telemetry Specification & Field Definitions

The canonical MQTT telemetry payload is a flat JSON object designed for low-overhead transmission, high reliability, and clear sensor attribution.

| Field Name | Data Type | Unit / Semantic Meaning | Envelope Status |
| :--- | :--- | :--- | :--- |
| **`schema_version`** | String | Envelope semantic version string (`"1.0.0"`) | **Required** |
| **`node_id`** | String | Unique data-driven node identifier (e.g. `"NODE-001"`, `"NODE-002"`) | **Required** |
| **`timestamp`** | String | Observation time in UTC ISO-8601 format (`YYYY-MM-DDTHH:MM:SSZ`) | **Required** |
| **`latitude`** | Number | Node latitude in WGS84 decimal degrees (`-90.0` to `+90.0`) | **Required** |
| **`longitude`** | Number | Node longitude in WGS84 decimal degrees (`-180.0` to `+180.0`) | **Required** |
| **`temperature`** | Number \| null | Ambient air temperature in degrees Celsius (°C) via BME280 | Optional / Nullable |
| **`humidity`** | Number \| null | Relative humidity percentage (%RH) via BME280 (`0.0` to `100.0`) | Optional / Nullable |
| **`pressure`** | Number \| null | Barometric surface pressure in hectopascals (hPa) via BME280 | Optional / Nullable |
| **`rainfall`** | Number \| null | Incremental rain accumulation in millimeters (mm) over the node reporting window | Optional / Nullable |
| **`soil_moisture`** | Number \| null | Volumetric soil moisture content percentage (% VWC) via capacitive sensor | Optional / Nullable |
| **`water_level`** | Number \| null | Surface/flood water level in centimeters (cm) relative to the dry ground baseline datum | Optional / Nullable |
| **`air_quality`** | Number \| null | PM2.5 particulate mass concentration in micrograms per cubic meter (µg/m³) via PMS5003 | Optional / Nullable |
| **`battery`** | Number \| null | Node power supply / battery voltage in Volts (V) | Optional / Nullable |

*Explicit Exclusion:* Optical sensor, camera image, or video stream fields **MUST NOT EXIST** in this envelope.

---

### 2. Canonical JSON Example

#### Fully Populated Node (e.g. Composite Station)
```json
{
  "schema_version": "1.0.0",
  "node_id": "NODE-001",
  "timestamp": "2026-09-07T22:45:00Z",
  "latitude": 30.2672,
  "longitude": -97.7431,
  "temperature": 26.4,
  "humidity": 58.2,
  "pressure": 1013.25,
  "rainfall": 0.0,
  "soil_moisture": null,
  "water_level": null,
  "air_quality": null,
  "battery": 3.92
}
```

#### Specialized Air Quality Node (e.g. NODE-004)
```json
{
  "schema_version": "1.0.0",
  "node_id": "NODE-004",
  "timestamp": "2026-09-07T22:45:00Z",
  "latitude": 30.2747,
  "longitude": -97.7404,
  "temperature": 27.1,
  "humidity": 55.0,
  "pressure": 1012.80,
  "rainfall": null,
  "soil_moisture": null,
  "water_level": null,
  "air_quality": 14.8,
  "battery": 4.05
}
```

#### Specialized Flood Node (e.g. NODE-002)
```json
{
  "schema_version": "1.0.0",
  "node_id": "NODE-002",
  "timestamp": "2026-09-07T22:45:00Z",
  "latitude": 30.2621,
  "longitude": -97.7510,
  "temperature": 24.8,
  "humidity": 88.5,
  "pressure": 1009.40,
  "rainfall": 12.4,
  "soil_moisture": null,
  "water_level": 18.5,
  "air_quality": null,
  "battery": 3.84
}
```

---

### 3. Validation Rules

1. **Header Validation:**
   * `schema_version` must match `^1\.[0-9]+\.[0-9]+$`. Payloads with major versions other than `1` must be routed to migration handlers.
   * `node_id` must match grammar `^[A-Za-z0-9_-]{3,32}$`. Node IDs must be data-driven and never hard-coded in visualization components.
   * `timestamp` must be a valid UTC ISO-8601 string terminating with `Z` (RFC3339). Reject timestamps drifting more than 24 hours into the future.
2. **Coordinate Range:**
   * `latitude` must be a float where `-90.0 <= latitude <= 90.0`.
   * `longitude` must be a float where `-180.0 <= longitude <= 180.0`.
3. **Physical Value Limits:**
   * `temperature`: `-40.0 <= temperature <= 85.0`
   * `humidity`: `0.0 <= humidity <= 100.0`
   * `pressure`: `300.0 <= pressure <= 1100.0`
   * `rainfall`: `rainfall >= 0.0` (indicates non-negative incremental accumulation)
   * `soil_moisture`: `0.0 <= soil_moisture <= 100.0`
   * `water_level`: `water_level >= 0.0`
   * `air_quality`: `0.0 <= air_quality <= 1000.0` (PM2.5 concentration scale)
   * `battery`: `0.0 <= battery <= 6.0`

---

### 4. Missing-Value Rules

* **Explicit Null Rule:** If a physical sensor is not installed on the node profile (e.g. `air_quality` on a weather-only node) or is temporarily reporting an error/disconnected state, the corresponding field value **MUST be `null`**.
* **No Fabricated Zeroes:** Systems must NEVER substitute `0` or `0.0` for missing or unmeasured data:
  * A `rainfall` value of `0.0` means precipitation was actively monitored and zero rain fell.
  * A `rainfall` value of `null` means rainfall is not monitored by this node.
  * A `water_level` value of `0.0` means the water level is at baseline / dry.
  * A `water_level` value of `null` means water level is not measured by this node.
* **Non-Blocking Ingest:** Ingestion pipelines and 3D globe visualizations must gracefully ingest envelopes where one or more optional fields are `null`.

---

### 5. Future Node Compatibility (NODE-006+)

1. **Profile Independence:** The schema is decoupled from any hardcoded node count or specific profile list. Nodes `NODE-001` through `NODE-005` use the exact same envelope structure, varying only in which optional metrics evaluate to numbers vs. `null`.
2. **Forward Compatibility:** Any future station (`NODE-006`, `NODE-007`, etc.) or community-contributed sensor cluster can publish to the telemetry broker using this schema without requiring database alterations, broker schema migrations, or frontend redeployments.
3. **Permissive Ingest:** Consumers must ignore any unknown supplementary keys (e.g. `"firmware_version"` or `"rssi"`) present in the envelope, ensuring forward compatibility as telemetry diagnostics evolve.

---

## DECISION-004: ClimateMesh MQTT Topic Hierarchy & Ownership Contract

* **Date:** 2026-09-07
* **Status:** APPROVED / FROZEN
* **Scope:** MQTT topic taxonomy, publisher/subscriber boundaries, and connection lifecycle management across ClimateMesh and Climate Eye.

### 1. Architectural Roles & Ownership Rules

* **Hardware (ESP32 Nodes):**
  * Publishes raw physical sensor telemetry on `/telemetry`.
  * Publishes lifecycle connectivity and LWT state on `/status`.
  * Publishes diagnostic liveness pings on `/heartbeat`.
* **Software 1 (Backend Ingest, Normalizer & State Broker):**
  * Subscribes to all three node topics (`climate/nodes/+/telemetry`, `climate/nodes/+/status`, `climate/nodes/+/heartbeat`).
  * Ingests, validates, and normalizes telemetry against the Canonical Telemetry Envelope (v1.0.0 per DECISION-003).
  * Manages node lifecycle state, watchdog timeouts, and historical persistence.
* **Software 2 (Frontend / 3D Visualization Console):**
  * **Does NOT consume raw MQTT directly.**
  * Consumes normalized, validated geospatial streams provided by Software 1 via WebSocket / SSE / REST APIs.

---

### 2. Topic Specifications

#### Topic 1: `climate/nodes/{node_id}/telemetry`
1. **Topic Pattern:** `climate/nodes/{node_id}/telemetry`
2. **Direction:** Node → MQTT Broker → Software 1 (Ingest)
3. **Publisher:** Hardware (ESP32 node)
4. **Subscriber:** Software 1 (Backend Ingestion & Normalizer)
5. **Payload Type:** JSON — Canonical Telemetry Envelope (v1.0.0, per DECISION-003)
6. **Purpose:** Periodic delivery of physical environmental sensor measurements (temperature, humidity, pressure, rainfall, soil moisture, water level, air quality, battery).
7. **Recommended Interval:** 30s to 60s (nominal); dynamic drop to 10s upon detection of rapid threshold anomalies (e.g. flash flood rainfall trigger).
8. **Expected Behavior on Disconnect:** Publications cease. Software 1 preserves last known valid telemetry but marks the readings as stale once the status topic or heartbeat watchdog expires.
9. **QoS & Retained Recommendation:**
   * **QoS:** QoS 1 (At least once delivery to prevent lost weather/hazard events).
   * **Retained:** `false` (Telemetry represents real-time time-series streams; stale telemetry should not be retained on the broker).
   * *Status:* Recommendation noted; final broker QoS profile marked for deployment finalization.
10. **Example Topic for NODE-001:**
    `climate/nodes/NODE-001/telemetry`

---

#### Topic 2: `climate/nodes/{node_id}/status`
1. **Topic Pattern:** `climate/nodes/{node_id}/status`
2. **Direction:** Node / Broker → Software 1
3. **Publisher:** Hardware (ESP32 node upon boot/shutdown) & MQTT Broker (via Last Will and Testament)
4. **Subscriber:** Software 1 (Node Registry & Connectivity Monitor)
5. **Payload Type:** JSON:
   ```json
   {
     "node_id": "NODE-001",
     "status": "online",
     "reason": "boot_complete",
     "timestamp": "2026-09-07T22:45:00Z"
   }
   ```
6. **Purpose:** Tracks node availability, graceful shutdowns, and unexpected ungraceful connection drops.
7. **Recommended Interval:** Event-driven (published on connect/disconnect) and via broker LWT.
8. **Expected Behavior on Disconnect:**
   * **Graceful:** Node publishes `{"status": "offline", "reason": "maintenance_shutdown"}` prior to disconnecting.
   * **Ungraceful (Power loss, radio drop):** The MQTT Broker detects TCP timeout and automatically dispatches the pre-configured Last Will and Testament (LWT) payload: `{"node_id": "NODE-001", "status": "offline", "reason": "lwt_timeout"}`.
9. **QoS & Retained Recommendation:**
   * **QoS:** QoS 1.
   * **Retained:** `true` (Ensures any newly connecting subscriber immediately receives the current connectivity status of the node).
   * *Status:* Recommendation noted; final broker retention setting marked for deployment finalization.
10. **Example Topic for NODE-001:**
    `climate/nodes/NODE-001/status`

---

#### Topic 3: `climate/nodes/{node_id}/heartbeat`
1. **Topic Pattern:** `climate/nodes/{node_id}/heartbeat`
2. **Direction:** Node → MQTT Broker → Software 1
3. **Publisher:** Hardware (ESP32 node)
4. **Subscriber:** Software 1 (Watchdog & Health Monitor)
5. **Payload Type:** JSON:
   ```json
   {
     "node_id": "NODE-001",
     "timestamp": "2026-09-07T22:45:15Z",
     "uptime_s": 84210,
     "battery_v": 3.92,
     "rssi_dbm": -64,
     "heap_free_bytes": 142080
   }
   ```
6. **Purpose:** Lightweight, high-frequency liveness signal and hardware vitals monitoring independent of heavy sensor polling cycles.
7. **Recommended Interval:** 10s to 15s.
8. **Expected Behavior on Disconnect:** Heartbeat messages cease arriving. Software 1 watchdog transitions node health state to `unresponsive` if no heartbeat is received within 3 missed intervals (e.g., 45s).
9. **QoS & Retained Recommendation:**
   * **QoS:** QoS 0 (At most once delivery; occasional dropped heartbeats are acceptable).
   * **Retained:** `false`.
   * *Status:* Recommendation noted; final broker QoS profile marked for deployment finalization.
10. **Example Topic for NODE-001:**
    `climate/nodes/NODE-001/heartbeat`

---

### 3. Decisions to be Finalized at Deployment

1. **Broker Authentication & Encryption:** Final selection between TLS client certificates (mTLS) vs. pre-shared tokens per node.
2. **Broker Keep-Alive Interval:** Formalization of the MQTT `keep_alive` timer (recommendation: 30 seconds, allowing broker LWT to trigger within 45 seconds of ungraceful disconnect).
3. **Multi-Node Wildcard Subscriptions:** Software 1 implementation will subscribe to `climate/nodes/+/telemetry` to capture all active and future node IDs (`NODE-001` through `NODE-006`+) dynamically without configuration updates.

---

## DECISION-005: Climate Eye S1 Backend Integration Architecture & Middleware Boundary

* **Date:** 2026-09-07
* **Status:** APPROVED / FROZEN
* **Scope:** Software 1 (S1) backend runtime, API routing, MQTT ingestion, and database boundary definition.

### 1. Architectural Decision
Use the existing God's Eye View (GEV) **Vite Connect Middleware** architecture as the initial Software 1 (S1) Climate Eye backend integration boundary, rather than introducing an independent, separate backend server process immediately.

### 2. Existing GEV Backend Foundation
* **Server Framework:** Vite 6 Connect Middleware engine (`server.middlewares.use(...)`).
* **Configuration & Wiring:** [vite.config.js](file:///C:/Users/inbox/OneDrive/Desktop/Hackathon/Work/gods-eye-view/vite.config.js) (~7,800 lines of hardened proxies, rate limiters, and SSRF guards).
* **Runtime:** Node.js (v24.x LTS / ESM).

### 3. Planned Climate Eye S1 Additions
The embedded S1 backend layer will introduce:
1. **API Endpoints:**
   * `/api/climate/*`: Environmental endpoints for wildfire (FIRMS), atmospheric weather (Open-Meteo), and aggregated hazard indicators.
   * `/api/nodes/*`: ClimateMesh node registry, live sensor states, historical window queries, and station health.
2. **Telemetry Ingestion & Processing:**
   * Local MQTT subscriber listening to `climate/nodes/+/...`.
   * Real-time validation against the Canonical Telemetry Envelope (v1.0.0 per DECISION-003).
   * Telemetry normalization and unit harmonization.
3. **Persistence:**
   * PostgreSQL / PostGIS geospatial storage adapter for node coordinates and historical sensor time-series.
4. **Real-time Client Broadcast:**
   * Inbound WebSocket / SSE streaming capability on `/api/climate/stream` to push validated telemetry to Software 2 (Cesium UI) without polling.

### 4. Replaceability & Decoupling Mandate
The S1 backend architecture must strictly remain **decoupled and replaceable**:
* All S1 backend capabilities must be contained inside dedicated modules (e.g., `src/climate/server/`).
* Business logic, MQTT handlers, and database queries must not be intertwined with Vite-specific build code.
* If production scale, distributed deployment, or multi-process reliability requires it, this entire S1 middleware block can be extracted into a standalone service (e.g. Express, Fastify, or FastAPI) with zero refactoring of the Climate Eye data contracts or frontend UI.

### 5. Known Architectural Risks
1. **Port 4173 Collision:** Running an external server alongside GEV creates port conflicts or requires cross-origin multi-terminal orchestration.
2. **MQTT Client Duplication:** Vite restarts the development server in-process whenever configuration changes occur. Naive client instantiations can leak open sockets and spawn duplicate MQTT listeners.
3. **Inbound WebSocket / HMR Collision:** Intercepting HTTP `upgrade` requests indiscriminately can break Vite's internal Hot Module Replacement (HMR) WebSocket channel.
4. **PostgreSQL Driver Compatibility:** Ensuring PostgreSQL / PostGIS drivers (`pg`) run smoothly under Node 24+ without disrupting GEV's existing locked devDependencies.

### 6. Chosen Mitigation Strategy
* **Reuse Existing Vite Connect Engine:** Avoid multi-process orchestration complexity during development by registering modular connect middleware plugins directly with Vite.
* **Modularize S1 Backend Code:** Place all S1 route handlers, validation schemas, and database access logic in a modular folder structure outside `vite.config.js` (e.g. `src/climate/server/`), mounting via a clean entry point.
* **Guaranteed Lifecycle Cleanup:** Hook MQTT client disconnects and database pool shutdowns into `server.httpServer.on('close', ...)` to guarantee zero zombie connections across Vite reloads.
* **Isolated WebSocket Upgrade Guard:** Strictly filter HTTP `upgrade` events by pathname (e.g., exclusively matching `/api/climate/stream`) and pass all other upgrades through to Vite's internal HMR handler.
* **Encapsulated Service Boundary:** Isolate PostGIS database operations behind an abstract repository interface so storage can run mock in-memory, SQLite/Spatialite, or full PostgreSQL without altering API consumers.

---
