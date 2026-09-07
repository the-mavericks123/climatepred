# Climate Eye View S2 — Physical Hardware Integration Complete

**Status:** COMPLETE & VERIFIED  
**Phase:** Post-Phase-12 Final Physical Hardware + System Integration  
**Date:** 2026-09-08  
**Integration Boundary:** ESP32 Sensor Node → LoRa RA-02 Transmitter (433MHz) → LoRa Gateway → MQTT Broker → Climate Eye S2 Backend → Database → Intelligence Pipeline → Gods-Eye-View (GEV) 3D Frontend  

---

## 1. Final Runtime Architecture

```
[ PHYSICAL SENSORS ]
  - DHT11 (Temp/Hum) [1-Wire]
  - BMP280 (Press/Secondary Temp) [I2C 0x76]
  - Raindrop Module (Conductivity) [Analog ADC1_CH4]
  - Soil Moisture (Resistive) [Analog ADC1_CH5]
  - Optical Dust GP2Y1010AU0F [Analog ADC1_CH6 + Pulse]
  - BH1750 GY-302 (Ambient Lux) [I2C 0x23]
  - GY-GPS6MV2P NEO-6M (WGS84) [UART2]
  - LM2596 DC-DC Step-Down (12V -> 5V/3.3V)
           │
           ▼
[ ESP32 PHYSICAL NODE ]
  - Hardware Pin Multiplexing & Signal Conditioning
  - Inverted Two-Point Soil Moisture Conversion
  - Sharp GP2Y1010 0.28ms Precision Microsecond Sampling
  - SX1278 SPI LoRa Driver (433.0 MHz, SF7, BW 125 kHz)
           │ (LoRa RF Packet, 36-byte packed binary or JSON)
           ▼
[ LORA RA-02 GATEWAY / RECEIVER ]
  - SX1278 433 MHz Receiver Module
  - Gateway Controller (ESP32 or Python Host Service)
  - Radio link metadata: RSSI (dBm), SNR (dB)
  - Network Interface: Ethernet / 802.11 b/g/n Wi-Fi
           │ (TCP/IP / TLS)
           ▼
[ ECLIPSE MOSQUITTO MQTT BROKER ]
  - Authenticated Topics: `climate/nodes/{node_id}/telemetry`
  - Heartbeat & Status Topics: `climate/nodes/{node_id}/heartbeat`
           │
           ▼
[ CLIMATE EYE S2 BACKEND INGESTION ]
  - MQTT Ingestion Engine (`intelligence/ingestion/mqtt_client.py`)
  - Calibration Translation Layer (`intelligence/calibration/hardware.py`)
  - Canonical Telemetry Validator (`intelligence/core/contracts/telemetry.py`)
  - Provenance & Deduplication Engine (`intelligence/core/provenance/`)
           │
     ┌─────┴─────────────────────────┐
     ▼                               ▼
[ PERSISTENCE ]            [ INTELLIGENCE PIPELINE ]
  - PostGIS / SQLite         - Quality Gate & Anomaly Filter
  - `nodes`                  - Hazard Models (Heat, Flood, Drought)
  - `sensor_readings`        - Prediction (1h, 6h, 24h ARIMA/GBM)
  - `hazard_events`          - Compound/Cascade Risk Evaluator
  - `evacuation_routes`      - Human Vulnerability & SVI
  - `response_plans`         - Dynamic Evacuation Routing (A*)
                             - Digital Twin / What-If Engine
                             - Explainability & Counterfactuals
                                     │
                                     ▼
                      [ GEV 3D FRONTEND (CesiumJS) ]
                        - Live Sensor Billboards & Badging
                        - Epistemic Status Tags (LIVE, PREDICTED, SIMULATED, UNAVAILABLE, UNVERIFIED)
                        - Realtime WebSocket Updates
```

---

## 2. Hardware Bill of Materials (BOM) & Sensor Mappings

| Component | Physical Interface | Pin / Port | Measured Quantity | Unit | Range / Constraints |
|:---|:---|:---|:---|:---|:---|
| **ESP32 DevKit V1** | MCU Core | 3.3V / GND | Dual-core Xtensa 240MHz, 520KB SRAM | — | System Coordinator |
| **LM2596** | Buck Converter | VIN 7-24V → VOUT 5V/3.3V | DC System Bus Power | V | 3A max, thermal dissipation checked |
| **DHT11** | 1-Wire Digital | GPIO 4 | Ambient Temperature, Humidity | °C, % RH | Temp: 0–50°C, Hum: 20–90% RH |
| **BMP280** | I2C (Address 0x76) | SDA (GPIO 21), SCL (GPIO 22) | Barometric Pressure, Temp | hPa, °C | Press: 700–1200 hPa, Temp: -40 to +85°C |
| **Raindrop Plate** | Analog Voltage (LM393) | ADC1_CH4 (GPIO 32) | Conductivity Wetness Fraction | mm/hr rate | ADC 4095 (dry) → 800 (submerged) |
| **Soil Moisture** | Resistive Probe | ADC1_CH5 (GPIO 33) | Soil Moisture Content | % Volumetric | 2-point calibrated: Dry 3400 → Wet 1350 |
| **Optical Dust Sensor** | 6-Wire GP2Y1010AU0F | LED (GPIO 14), Vo (ADC1_CH6 / GPIO 34) | Analog Dust Voltage → PM2.5 Density | $\mu\text{g/m}^3$, AQI | LED 0.32ms pulse, sample at 0.28ms |
| **BH1750 (GY-302)** | I2C (Address 0x23) | SDA (GPIO 21), SCL (GPIO 22) | Ambient Light Illuminance | lux | 0 to 120,000 lux (1 lux res) |
| **GY-GPS6MV2P** | UART2 NMEA | TX2 (GPIO 17), RX2 (GPIO 16) | Latitude, Longitude, Altitude | WGS84 deg, m | Rejects Null Island (0,0) and No-Fix |
| **LoRa RA-02** | SPI (SX1278 433MHz) | NSS (GPIO 5), SCK (18), MISO (19), MOSI (23), DIO0 (GPIO 2) | RF Telemetry Packet Link | dBm, dB | 433.0 MHz, SF7, BW 125kHz, CR 4/5 |

---

## 3. Epistemic Separation & Sensor Calibration Status

| Sensor Field | Physical Status | Software State | Epistemic Badge | Fallback / Model Behavior |
|:---|:---|:---|:---|:---|
| **temperature** | DHT11 Present | Ingested (°C) | `UNVERIFIED` | Passed to Heat & Drought hazard models |
| **humidity** | DHT11 Present | Ingested (% RH) | `UNVERIFIED` | Passed to Heat index evaluation |
| **pressure** | BMP280 Present | Ingested (hPa) | `CALIBRATED` | Factory-trimmed I2C calibration registers |
| **rainfall** | Raindrop Module | Converted (mm/hr) | `UNVERIFIED` | Empirical power curve; uncalibrated against tipping bucket gauge |
| **soil_moisture**| Resistive Probe | Converted (0-100%) | `UNVERIFIED` | 2-point linear interpolation; unverified against lab gravimetric oven tests |
| **air_quality** | GP2Y1010AU0F | Converted (AQI) | `UNVERIFIED` | Converted via US EPA PM2.5 piecewise linear breakpoints |
| **light_intensity** | BH1750 Present | Ingested (lux) | `CALIBRATED` | Stored in DB & GEV UI; excluded from hazard mathematics |
| **water_level** | **ABSENT FROM BOM** | **`null` / None** | **`UNAVAILABLE`** | **Flood model evaluates to `HazardStatus.UNAVAILABLE`. No fake zeros.** |

---

## 4. Architectural Rules Upheld

1. **No Fabricated Sensor Data:** All raw readings undergo strict range boundary validation; missing physical transducers (`water_level`) are explicitly `null`.
2. **No Fake `water_level = 0.0`:** Physical node lacks water-level transducer. When ingested, `water_level` is `None`. `FloodModel` line 91 validates prerequisite presence and cleanly produces `status = UNAVAILABLE` with score `0.0` and confidence `0.0`.
3. **No Raw ADC Passed as Engineering Units:** Raindrop module raw ADC is converted to estimated mm/hr via non-linear power curve; soil moisture raw ADC is calibrated between dry/wet bounds.
4. **LoRa Decoupling:** RA-02 is recognized as an RF transceiver. Decoupled gateway topology forwards packets via MQTT.
5. **Multi-Node Ready:** Node identity is configurable via EEPROM/NVS and payload headers (`NODE-001`, `NODE-002`), requiring zero code branching in intelligence models.
6. **Zero Math Modifications:** Existing flood, heat, drought, cascade, evacuation, and prediction mathematical models remain intact and unmodified.

---

## 5. Verification Summary

- **Hardware Integration Tests:** 19/19 PASSED (`tests/integration/test_hardware_integration.py`)
- **Full Regression Test Suite:** 729/729 PASSED (`pytest`)
- **GEV Frontend Production Build:** 0 errors, built in 5.73s (`npm --prefix gods-eye-view run build`)
