# Climate Eye View S2 — Physical Demo Readiness Audit

**Document Version:** 1.0.0  
**Phase:** Release Freeze & Physical Demo Readiness Audit  
**Date:** September 8, 2026  
**Auditor:** Lead System Architect & Integration Specialist  
**Release Rule:** RELEASE FREEZE ACTIVE — NO NEW FEATURES / NO ALGORITHM REDESIGN  

---

## 1. Executive Summary & Git Repository State

An adversarial forensic audit was conducted on the repository to evaluate its readiness for physical hardware demonstration at a hackathon.

### 1.1 Git Working Tree & Branch Telemetry
- **Active Branch:** `main`
- **Head Commit:** `1d7e26d` (*docs: complete Phase 0 GEV understanding and integration boundary*)
- **Status:** Modified tracked files (6): `intelligence/README.md`, `intelligence/app/config.py`, `intelligence/app/dependencies.py`, `intelligence/app/main.py`, `intelligence/ingestion/normalized_adapter.py`, `intelligence/ingestion/source_registry.py`.
- **Untracked Additions:** Canonical documentation, contracts, test suites, and database migration files across Phases 0–12 and Hardware Integration.
- **Diff Statistics:** +3,175 insertions across 6 core intelligence files. Zero breaking changes to existing mathematical models.

---

## 2. Actual Demo Topology & Component Inventory

```
[ PHYSICAL SENSORS ]
  DHT11, BMP280, Raindrop, Soil, Dust, BH1750, GPS
          │ (Electrical jumpers, breadboard/stripboard)
          ▼
   [ ESP32 NODE ]
          │ (SPI Bus)
          ▼
  [ LoRa RA-02 TX ]
          │ (433.0 MHz RF Air Link)
          ▼
  [ LoRa RA-02 RX ]
          │ (SPI / UART)
  [ GATEWAY HOST ] (ESP32 or Python Host Service)
          │ (Wi-Fi / Ethernet / Localhost TCP)
          ▼
  [ MQTT BROKER ] (Eclipse Mosquitto port 1883)
          │ (Internal IPC / Local Network)
          ▼
[ CLIMATE BACKEND ] (FastAPI Python 3.13 / Uvicorn port 8000)
          │
    ┌─────┴─────────────────────┐
    ▼                           ▼
[ SQLITE / POSTGIS ]    [ INTELLIGENCE PIPELINE ]
  Local persistent store   Heat, Flood, Drought, Evac, A*
                                │
                                ▼
                       [ GEV 3D FRONTEND ] (Vite / CesiumJS port 4173)
```

### 2.1 Hardware Component Availability & Verification State

| Subsystem Component | Availability | Verification State | Operational Risk / Missing Prerequisite |
|:---|:---:|:---:|:---|
| **ESP32 Sensor Node (MCU)** | **AVAILABLE** | **PASS (Code Verified)** | Requires physical firmware flashing via PlatformIO / Arduino IDE |
| **DHT11 (Temp/Hum)** | **AVAILABLE** | **UNVERIFIED (Physical)** | 1-wire pin verified; physical calibration against lab reference pending |
| **BMP280 (Press/Temp)** | **AVAILABLE** | **PASS (Factory Calibrated)**| I2C 0x76 digital registers factory trimmed |
| **Raindrop Plate (LM393)** | **AVAILABLE** | **UNVERIFIED (Physical)** | Converted via power curve; tipping bucket colocation pending |
| **Soil Moisture Sensor** | **AVAILABLE** | **UNVERIFIED (Physical)** | 2-point interpolation tested in software; dry/wet immersion pending |
| **Dust Sensor GP2Y1010** | **AVAILABLE** | **UNVERIFIED (Physical)** | 150Ω / 220μF passive filter circuit required for LED pulse |
| **BH1750 (Lux)** | **AVAILABLE** | **PASS (Code Verified)** | Standard I2C illuminance protocol |
| **GY-GPS6MV2P (NEO-6M)** | **AVAILABLE** | **PASS (Code Verified)** | Indoor satellite acquisition requires window/outdoor line-of-sight |
| **LM2596 Buck Regulator** | **AVAILABLE** | **UNVERIFIED (Electrical)**| Multimeter pre-flight verification mandatory before MCU connection |
| **LoRa RA-02 Transmitter** | **AVAILABLE** | **PASS (Packet Verified)**| SPI pin assignments verified; RF air transmission pending antenna |
| **LoRa Gateway (Receiver)**| **PARTIALLY AVAILABLE** | **UNVERIFIED (RF Link)** | Requires second ESP32 + RA-02 or direct UART gateway bridge |
| **Water Level Sensor** | **NOT AVAILABLE** | **NOT AVAILABLE (BOM)** | Handled honestly as `null` / `UNAVAILABLE` in software pipeline |
| **Local MQTT Broker** | **AVAILABLE** | **PASS** | Mosquitto runs natively or via local daemon |
| **Local Backend & DB** | **AVAILABLE** | **PASS (748 Tests Passing)**| Standalone SQLite fallback active; 0 external cloud dependencies |
| **GEV 3D Frontend** | **AVAILABLE** | **PASS (Build Passed)** | Local Vite bundle verified |

---

## 3. Sensor Reality & Calibration Checklist

| Sensor | Raw Domain | Engineering Unit | Calibration Model | Real-World Failure Action |
|:---|:---|:---|:---|:---|
| **DHT11** | 1-wire byte stream | °C, % RH | Range gate (0–50°C, 20–90%) | Fallback to BMP280 temperature; flag `UNVERIFIED` |
| **BMP280** | I2C calibration registers | hPa, °C | Factory trimmed polynomial | Mark pressure `UNAVAILABLE`; flag `FAILED` |
| **Raindrop** | 12-bit ADC (4095–800) | mm/hr rate | Wetness fraction power curve | Clamped to 0.0; flag `rainfall:UNVERIFIED` |
| **Soil Moisture**| 12-bit ADC (3400–1350) | % Volumetric | Inverted 2-point linear interpolation | Clamped [0, 100]; flag `soil:UNVERIFIED` |
| **Dust Sensor** | Analog voltage (0–5V) | $\mu\text{g/m}^3$, AQI | $\frac{V - 0.6}{0.005} \longrightarrow \text{EPA AQI}$ | Value set to `null`; flag `dust:UNVERIFIED` |
| **BH1750** | I2C 16-bit word | lux | Direct optical illuminance | Value set to `null`; isolated from hazard models |
| **GPS** | NMEA `$GPGGA` | WGS84 lat, lon, m | WGS84 bounds; reject `(0,0)` | Fallback to station coordinates; flag `NO_FIX` |
| **Water Level** | **NONE** | m | **None (Absent Transducer)** | **Explicit `null` / `UNAVAILABLE`**; FloodModel produces score `0.0` |

---

## 4. Physical Link & Network Reality

1. **LoRa RA-02 Boundary:** The SX1278 is strictly an RF physical transceiver (SPI). It does not speak TCP/IP or MQTT. If the physical gateway receiver is not powered at the hackathon, the system transitions cleanly to **Level 3 Deterministic Telemetry Replay**.
2. **Offline Resilience:** The entire pipeline runs 100% offline on a local laptop:
   - Backend binds to `127.0.0.1:8000`.
   - GEV frontend runs on `http://localhost:4173` via Vite.
   - Database persists locally via SQLite (`intelligence.db`).
   - Zero internet connectivity required for the golden path demonstration.

---

## 5. Epistemic Invariant Verification

- **Water Level Integrity:** Verified via `tests/integration/test_hardware_integration.py`. Live telemetry reporting `water_level = null` causes `FloodModel` to evaluate to `HazardStatus.UNAVAILABLE` with severity `0.0` and confidence `0.0`. Fake zeros (`0.0`) are strictly forbidden.
- **Simulation Isolation:** Synthetic scenarios (+40% rain) evaluate with `simulated = true` badges and never pollute live telemetry tables.
