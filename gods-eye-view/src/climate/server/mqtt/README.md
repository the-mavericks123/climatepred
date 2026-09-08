# S1 MQTT Ingestion Subsystem

## Responsibilities

* **Broker Connectivity:** Maintains connection to the ClimateMesh MQTT broker.
* **Topic Subscriptions:** Subscribes to:
  * `climate/nodes/+/telemetry` (Sensor measurements)
  * `climate/nodes/+/status` (LWT & online/offline state)
  * `climate/nodes/+/heartbeat` (Diagnostic vitals)
* **Lifecycle Management:** Automatically triggers teardown on server shutdown (`server.httpServer.on('close')`) to prevent connection leaks across dev server reloads.
* **Handoff:** Routes raw messages to `../telemetry/` for validation and normalization before database persistence.
