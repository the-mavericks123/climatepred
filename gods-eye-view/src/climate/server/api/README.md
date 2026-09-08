# S1 API & Streaming Subsystem

## Responsibilities

* **REST Routes:** Exposes endpoints under:
  * `/api/climate/health`: Backend service status.
  * `/api/climate/summary`: Aggregated microclimate indicators.
  * `/api/nodes`: Active ClimateMesh node list and latest readings.
  * `/api/nodes/:nodeId/history`: Historical sensor time-series windows.
* **Real-time Streaming:** Manages inbound WebSocket / SSE channels on `/api/climate/stream` to push validated telemetry to Software 2 (Cesium UI) in real time.
* **HMR Protection:** Strictly filters HTTP upgrade paths to prevent collision with Vite's Hot Module Replacement (HMR) WebSocket channel.
