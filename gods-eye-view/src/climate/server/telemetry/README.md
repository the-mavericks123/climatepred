# S1 Telemetry & Validation Subsystem

## Responsibilities

* **Schema Validation:** Strictly validates incoming raw MQTT payloads against the Canonical Telemetry Envelope (v1.0.0 per `DECISION-003`).
* **Boundary Checks:** Verifies numeric bounds for physical metrics (temperature, humidity, pressure, rainfall, soil moisture, water level, air quality, battery).
* **Missing-Value Enforcement:** Ensures unequipped or faulted sensor metrics evaluate to `null` and prevents fabricated zeroes.
* **Unit Normalization:** Harmonizes sensor timestamps into UTC ISO-8601 (RFC3339) and standardizes metric units before persistence.
