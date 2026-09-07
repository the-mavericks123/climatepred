# Climate Eye View — Hardware Integration Audit
**Audit Date:** September 8, 2026  
**Document Status:** Complete Forensic Baseline  
**Scope:** Post-Phase-12 Physical Hardware to S2 Intelligence Integration  

---

## 1. Executive Summary

This forensic audit evaluates the Phase 12 verified baseline of Climate Eye View S2 against the actual physical sensing hardware bill of materials (BOM). The purpose is to map real physical transducers (ESP32, GY-GPS6MV2P, LM2596, Raindrop module, 6-wire Optical Dust Sensor, BH1750, BMP280, LoRa RA-02, DHT11, Soil Moisture sensor) into the canonical software schemas, quantify physical sensor capabilities and limitations, define missing evidence behavior, and establish the exact integration adapters required without altering existing intelligence mathematics.

---

## 2. Existing Software Infrastructure Audit

### 2.1 Existing Telemetry Contract (`intelligence/core/contracts/telemetry.py`)
- **Root Schema:** `NormalizedTelemetry`
  - `schema_version`: String, strictly `"1.0"`.
  - `node_id`: String, non-empty (e.g. `"NODE-001"`).
  - `timestamp`: UTC datetime (ISO-8601).
  - `location`: `LocationCoordinate` (`lat`, `lon`, optional `elevation`).
  - `measurements`: `SensorMeasurements`:
    - `temperature`: Optional float [-50.0, 65.0] °C
    - `humidity`: Optional float [0.0, 100.0] %
    - `pressure`: Optional float [800.0, 1100.0] hPa
    - `rainfall`: Optional float [0.0, 500.0] mm/hr
    - `soil_moisture`: Optional float [0.0, 100.0] %
    - `water_level`: Optional float [0.0, 50.0] meters
    - `air_quality`: Optional float [0.0, 500.0] AQI
  - `quality`: `QualityMetadata` (`valid`, `source`, `received_at`, `confidence`, `anomaly_score`, `flags`).
- **Audit Finding:** Missing physical fields for light intensity (`light_intensity` in lux from BH1750) and per-sensor calibration/operational status flags (`sensor_status`). Neither field currently exists in `SensorMeasurements`.

### 2.2 Existing MQTT Implementation (`intelligence/ingestion/mqtt_client.py`)
- Subscribes to `climate/nodes/+/telemetry` and `climate/nodes/+/status`.
- Enforces topic regex: `^climate/nodes/([^/]+)/telemetry$`.
- Implements L1 deduplication cache (`TelemetryDeduplicator`).
- Validates canonical fields and ranges via `TelemetryValidator.validate_dict()`.
- **Audit Finding:** Telemetry topic matches single nodes dynamically (`+`), but does not distinguish raw LoRa gateway forwarder packets from direct Wi-Fi clients. Clock skew validation requires `received_at` to strictly reflect UTC server ingestion time.

### 2.3 Existing Node Registration & Identity
- Nodes are auto-discovered upon first telemetry packet via `IntelligenceRepository.upsert_node()`.
- Supports dynamic `node_id` strings (`NODE-001`, `NODE-002`, `NODE-003`).
- **Audit Finding:** Software supports multi-node scaling with zero hardcoded node branches.

### 2.4 Existing Database Representation (`database/migrations/001_initial_schema.sql` & `repository.py`)
- `nodes`: `node_id`, `name`, `status`, `latitude`, `longitude`, `elevation_m`, `hardware_version`, `firmware_version`.
- `sensor_readings`: `reading_id`, `node_id`, `timestamp`, `received_at`, `latitude`, `longitude`, `temperature`, `humidity`, `pressure`, `rainfall`, `soil_moisture`, `water_level`, `air_quality`, `battery`, `provenance_hash`.
- **Audit Finding:** Database schema already accommodates `battery` and standard telemetry. Needs column or metadata storage for `light_intensity` and `sensor_status`.

### 2.5 Existing Realtime Pipeline (`intelligence/core/realtime/broadcaster.py`)
- Dispatches `telemetry.updated`, `hazard.updated`, `prediction.updated`, `compound.updated`, `vulnerability.updated`, `evacuation.updated`, `response.updated`.
- Transports: WebSocket (`/api/v1/events/ws`, `/ws/climate`) and Server-Sent Events (`/api/v1/events/stream`).
- Preserves 1000-event in-memory ring buffer for HTTP catch-up.

### 2.6 Existing Frontend Representation (`gods-eye-view`)
- 3D globe powered by CesiumJS.
- Renders layers: Sensors, Temperature, Rainfall, Flood Risk, Heat Risk, Drought Risk, Forecasts, Cascades, Vulnerability, Evacuation Routes, Shelters.
- **Audit Finding:** Visualizes sensor markers; needs distinct status badges (`LIVE`, `STALE`, `UNAVAILABLE`, `UNVERIFIED`).

### 2.7 Existing Intelligence Dependencies (`intelligence/hazards/`)
- **Heat Model:** Requires `temperature_c`, `humidity_pct`.
- **Flood Model:** Requires `rainfall_mmhr`, `soil_moisture_pct`, `water_level_m`.
- **Drought Model:** Requires `soil_moisture_pct`, `temperature_c`, `humidity_pct`.
- **Critical Finding:** The physical hardware BOM **DOES NOT CONTAIN** a water level sensor.

---

## 3. Physical Hardware Sensor Mapping & Analysis

| Physical Sensor Component | Transducer / Interface | Target Physical Metric | Unit | Calibration Requirement | Hardware Status |
|---|---|---|---|---|---|
| **ESP32 Microcontroller** | MCU / Dual Core 240MHz | System Telemetry, Battery ADC | %, V | ADC reference attenuation (11dB) | Present |
| **GY-GPS6MV2P** | UART (NMEA 9600 baud) | Latitude, Longitude, Elev | WGS84 deg | Check GPS fix & HDOP bounds | Present |
| **LM2596 Step-Down** | Switching Regulator | Power Supply (5.0V / 3.3V) | Volts (V) | Multimeter output trim (5.05V) | Present |
| **Raindrop Module** | Resistive Plate + LM393 ADC | Precipitation Intensity | mm/hr | ADC curve to mm/hr conversion | Present (Unverified) |
| **6-Wire Optical Dust Sensor** | GP2Y1010AU0F / Analog Pulse | Particle Concentration | $\mu\text{g/m}^3$ / AQI | Pulse timing (0.32ms) & V-to-dust | Present (Unverified) |
| **BH1750 (GY-302)** | I2C (`0x23`) Digital Lux | Ambient Light Intensity | Lux (lx) | Factory calibrated digital direct | Present |
| **BMP280** | I2C (`0x76` or `0x77`) | Barometric Pressure, Temp | hPa, °C | Factory trimmed I2C registers | Present |
| **LoRa RA-02 (SX1278)** | SPI Transceiver (433 MHz) | RF Packet Transport | dBm / RSSI | Not a sensor; RF packet link | Present |
| **DHT11** | 1-Wire Digital Transducer | Ambient Temp, Relative Hum | °C, % RH | Low precision (±2°C, ±5% RH) | Present |
| **Soil Moisture Sensor** | Resistive/Capacitive ADC | Volumetric Moisture | % (0–100) | Dry air vs saturated wet points | Present (Unverified) |
| **Water Level Sensor** | **NONE** | Surface Water Level | meters | **NOT PRESENT IN HARDWARE** | **ABSENT** |

---

## 4. Discrepancies & Required Integration Changes

### 4.1 Missing Physical Sensor: Water Level
- **Problem:** The physical BOM contains no submersible pressure transducer, ultrasonic ranger, or radar gauge for water level.
- **Rule:** Never generate `water_level = 0.0`. Never fabricate live measurements.
- **Solution:** Physical telemetry will explicitly report `"water_level": null` with sensor status `"water_level": "UNAVAILABLE"`.
- **Model Impact:** `FloodModel` quality gate requires `water_level_m`. When absent on live telemetry, the quality gate reports `is_admissible = False` and returns `HazardStatus.UNAVAILABLE` with reason `"Missing required inputs for flood: water_level_m"`.
- **Demo / What-If Impact:** In simulated scenarios (e.g. `shared/fixtures/golden_demo/`), synthetic water level carries `simulated = True`.

### 4.2 Raw ADC vs Physical Units (Raindrop & Soil Moisture)
- **Raindrop Sensor:** Raw ADC voltage drops when water bridges the traces. It measures surface conductivity, NOT volumetric accumulation. Sending raw ADC as mm/hr is strictly prohibited. An engineering conversion curve with calibration status `UNVERIFIED` must be introduced.
- **Soil Moisture:** Raw 12-bit ADC (0–4095) must be converted via 2-point calibration ($V_{\text{dry}}, V_{\text{wet}}$) into $0.0 - 100.0\%$.

### 4.3 Optical Dust Sensor Identification (GP2Y1010AU0F)
- The 6-wire optical dust sensor uses an infrared diode and phototransistor.
- Interface: Pin 1 (V-LED), Pin 2 (LED-GND), Pin 3 (LED pulse trigger), Pin 4 (S-GND), Pin 5 (Vo analog out), Pin 6 (Vcc 5V).
- Measurement: Analog voltage proportional to dust density.
- Physical conversion:
  $$\text{Dust Density } (\mu\text{g/m}^3) = \max\left(0, \frac{V_o - V_{\text{no\_dust}}}{K}\right)$$
  where $V_{\text{no\_dust}} \approx 0.6\text{V}$ and $K \approx 0.5\text{V} / (100\mu\text{g/m}^3)$.
- AQI conversion follows US EPA standard breakpoints. If uncalibrated against reference particulate monitor, status is marked `UNVERIFIED`.

### 4.4 Temperature Disambiguation (DHT11 vs BMP280)
- Both DHT11 and BMP280 provide temperature readings.
- DHT11 is slower and less precise ($0–50^\circ\text{C} \pm 2^\circ\text{C}$).
- BMP280 is high-precision ($-40–85^\circ\text{C} \pm 0.5^\circ\text{C}$).
- **Policy:** DHT11 temperature supplies primary ambient `temperature` to preserve Phase 1–11 baseline; BMP280 pressure supplies `pressure`; secondary temperature is preserved in `sensor_status` or auxiliary features.

### 4.5 LoRa RA-02 Network Topology
- RA-02 is an SX1278 SPI RF module operating at 433 MHz. It has no TCP/IP stack.
- Real Architecture:
  $$\text{ESP32 (Transmitter)} \xrightarrow{\text{LoRa 433MHz}} \text{LoRa Gateway (ESP32 / Serial Host)} \xrightarrow{\text{Wi-Fi / Ethernet}} \text{MQTT Broker (1883)} \xrightarrow{} \text{S2 Backend}$$
- Direct transmission from RA-02 to MQTT broker without an intermediary gateway is physically impossible and will not be claimed.

---

## 5. Summary of Required Modifications

1. **Schema Extension:** Add `light_intensity: Optional[float]` and `sensor_status: Optional[Dict[str, str]]` to `SensorMeasurements`.
2. **Hardware Calibration Module:** Implement [intelligence/calibration/hardware.py](file:///c:/Users/yagna/OneDrive/Documents/models/intelligence/calibration/hardware.py) for ADC conversion, calibration limits, and status tracking.
3. **Gateway Specification & Bridge:** Create [intelligence/ingestion/lora_gateway.py](file:///c:/Users/yagna/OneDrive/Documents/models/intelligence/ingestion/lora_gateway.py) simulating or executing the LoRa-to-MQTT bridge.
4. **Architectural Decision Record:** Create [docs/contracts/DECISIONS.md](file:///c:/Users/yagna/OneDrive/Documents/models/docs/contracts/DECISIONS.md).
5. **Hardware Integration Specification:** Create [docs/contracts/HARDWARE_SOFTWARE_INTEGRATION.md](file:///c:/Users/yagna/OneDrive/Documents/models/docs/contracts/HARDWARE_SOFTWARE_INTEGRATION.md).
6. **Hardware Test Suite:** Implement [tests/integration/test_hardware_integration.py](file:///c:/Users/yagna/OneDrive/Documents/models/tests/integration/test_hardware_integration.py).
