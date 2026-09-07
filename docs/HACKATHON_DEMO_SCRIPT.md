# Climate Eye View — Judge Q&A Technical Defense Guide

**Document Version:** 1.0.0  
**Target:** Hackathon Presentation & Jury Question Preparation  

---

### Q1: What makes Climate Eye View different from a standard weather dashboard?
**Answer:**  
*"A weather dashboard displays isolated, passive sensor numbers. Climate Eye View is an end-to-end, safety-critical decision engine. It takes physical multi-sensor IoT telemetry over LoRa, feeds it through calibrated multi-hazard algorithms (Heat, Flood, Drought), models future trajectories via predictive machine learning, runs cascading compound risk analysis, calculates social vulnerability, and dynamically computes obstacle-avoiding evacuation routes using real road networks in an interactive 3D geospatial twin."*

---

### Q2: What exactly is "AI" in this system versus traditional deterministic rules?
**Answer:**  
*"We use a rigorous hybrid architecture where each layer uses the right tool for safety-critical operations:*
1. *Hazard evaluation and evacuation routing are **deterministic mathematical algorithms** (hydrological formulas, A* over road topology) because emergency life-safety decisions must be 100% reproducible and verifiable.*
2. *Prediction utilizes **statistical time-series models (ARIMA & Gradient Boosted Regression)** across 1h, 6h, and 24h forecast horizons.*
3. *Our Explainability and Response modules employ **natural language AI models** to translate complex compound risk matrices into actionable, human-readable evacuation orders for emergency responders. Crucially, **AI never invents numerical hazard values**."*

---

### Q3: What happens if a sensor fails or produces physically impossible readings?
**Answer:**  
*"Every incoming measurement passes through an adversarial `TelemetryValidator` and calibration layer before entering the intelligence core. If a DHT11 temperature reading exceeds terrestrial limits (-50°C to +65°C), or if an analog voltage shorts to ground, the validator strips that individual measurement to `null`, flags the sensor as `FAILED`, and allows all other healthy sensors on that node to continue operating. The system degrades gracefully rather than crashing."*

---

### Q4: Why does the system report Flood Risk as "UNAVAILABLE" on your physical hardware?
**Answer:**  
*"Because our physical bill of materials does not contain a water-level sensor. Many naive IoT projects inject a fake `0.0` or pretend to measure depth from a raindrop sensor. In Climate Eye View, that is an absolute safety violation. If evidence is absent, the flood model honestly returns `HazardStatus.UNAVAILABLE` with confidence `0.0`. Simulated water levels exist exclusively in our digital twin with explicit `simulated = true` badges."*

---

### Q5: How does the LoRa communication connect to the MQTT broker?
**Answer:**  
*"The Semtech SX1278 (RA-02) is purely an RF physical layer transceiver communicating at 433 MHz over the SPI bus. It does not run TCP/IP. We decouple the radio link from the network: the node transmits a packed binary RF packet; a gateway receiver (ESP32 or host bridge) captures the radio packet, attaches RSSI and SNR link telemetry, and forwards the normalized JSON payload over Wi-Fi/Ethernet to the Eclipse Mosquitto MQTT broker."*

---

### Q6: Can this architecture scale to hundreds of field nodes?
**Answer:**  
*"Yes. Node identity is entirely data-driven (`NODE-001`, `NODE-002`, `NODE-003`). The backend database and ingestion pipelines operate without hardcoded station logic. The MQTT topic hierarchy (`climate/nodes/{node_id}/telemetry`) and spatial queries in PostGIS index nodes dynamically."*

---

### Q7: Does the system depend on cloud internet connectivity?
**Answer:**  
*"No. The entire stack—from the LoRa RF receiver to the MQTT broker, FastAPI backend, SQLite/PostGIS database, and Vite/CesiumJS 3D frontend—runs 100% locally on a single workstation. External satellite APIs are strictly optional enhancements."*
