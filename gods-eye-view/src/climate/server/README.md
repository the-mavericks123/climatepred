# Climate Eye Software 1 (S1) Backend

This directory houses the Software 1 (S1) backend integration foundation for Climate Eye.

## Architecture

The S1 backend is implemented as a decoupled, modular Node.js subsystem conforming to `DECISION-005`. It can be mounted directly into Vite's dev server connect middlewares or extracted into a standalone production server without rewriting application code.

### Directory Structure

* **`mqtt/`**: MQTT client connection, topic subscription management (`climate/nodes/+/...`), and connection lifecycle/LWT tracking.
* **`api/`**: REST and streaming endpoint handlers (`/api/climate/*`, `/api/nodes/*`, `/api/climate/stream`).
* **`db/`**: Database repository layer for node registry and historical sensor time-series persistence (PostgreSQL / PostGIS).
* **`telemetry/`**: Telemetry parsing, schema validation against Canonical Envelope v1.0.0 (`DECISION-003`), and unit normalization.
* **`index.js`**: Unified entry point exposing `createClimateServer()` and `climateServerPlugin()`.
