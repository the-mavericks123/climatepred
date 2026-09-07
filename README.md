# Climate Eye View S2 — Physical Hardware + System Integration

Climate Eye View S2 is a planetary-scale situational awareness and climate hazard intelligence platform integrating physical IoT sensor telemetry, predictive machine learning models, compound hazard cascade simulation, and dynamic evacuation planning into a 3D Cesium visualization engine (Gods-Eye-View).

## System Architecture

```
Physical Sensors (DHT11, BMP280, Raindrop, Soil, Dust, BH1750, GPS)
    ↓
ESP32 Node Controller (Signal Conditioning & Analog Calibration)
    ↓
LoRa RA-02 Transmitter (SX1278 433 MHz SPI)
    ↓
LoRa Gateway / Receiver (SX1278 + Host / Wi-Fi Bridge)
    ↓
Eclipse Mosquitto MQTT Broker (Authenticated TLS / Port 1883)
    ↓
Climate Eye S2 Ingestion & Calibration Translation Layer
    ↓
Normalized Telemetry Ingestion Pipeline & Quality Gate
    ↓
PostGIS Database / SQLite Persistent Store
    ↓
Climate Intelligence Core (Heat, Flood, Drought, Cascade Risk, A* Routing)
    ↓
Gods-Eye-View (GEV) 3D Cesium Frontend
```

## Hardware Bill of Materials (BOM)

- **Microcontroller:** ESP32 DevKit V1 (Xtensa dual-core 240MHz, 520KB SRAM)
- **Power:** LM2596 DC-DC Buck Converter (12V Input → 5V/3.3V System Rails)
- **GPS:** GY-GPS6MV2P (u-blox NEO-6M, UART2 9600 baud, WGS84 NMEA)
- **Environment:**
  - DHT11 (Ambient Temperature 0–50°C & Relative Humidity 20–90% RH)
  - BMP280 (Calibrated Barometric Pressure 300–1100 hPa & Secondary Temp)
  - BH1750 / GY-302 (Ambient Illuminance 1–65535 lux via I2C)
  - Raindrop Sensor Plate (Conductivity ADC → mm/hr intensity curve)
  - Soil Moisture Sensor (12-bit ADC → 0–100% volumetric saturation)
  - 6-Wire Optical Dust Sensor (GP2Y1010AU0F, 0.28ms pulse sample → PM2.5 AQI)
- **Radio:** LoRa RA-02 (SX1278 433 MHz SPI, 20dBm, +10km LoS range)
- **Water Level:** **NONE** (Hardware BOM contains no water-level sensor. System cleanly handles `water_level = null` with `HazardStatus.UNAVAILABLE` on live telemetry without fabricating zero or synthetic measurements).

## Epistemic Integrity

The platform strictly enforces epistemic badging across all data layers:
- **`LIVE / OBSERVED`**: Real physical telemetry from field nodes (`NODE-001`).
- **`PREDICTED`**: Multi-horizon statistical/machine learning hazard forecasts (1h, 6h, 24h).
- **`SIMULATED`**: Digital-twin scenario stress tests and counterfactual synthetic perturbations (e.g., rainfall +40%).
- **`UNAVAILABLE`**: Missing sensors (such as water-level gauge) explicitly tagged without hidden defaults.
- **`UNVERIFIED`**: Functional physical sensors awaiting lab reference ground-truth colocation.
- **`STALE`**: Telemetry exceeding 30-second freshness window.

## Running Tests

```bash
# Activate virtual environment
.venv\Scripts\activate

# Run full regression test suite (729+ tests)
pytest

# Run dedicated hardware integration tests
pytest tests/integration/test_hardware_integration.py -v

# Build GEV frontend
npm --prefix gods-eye-view run build
```

## Documentation

- **Hardware Audit:** [docs/HARDWARE_INTEGRATION_AUDIT.md](docs/HARDWARE_INTEGRATION_AUDIT.md)
- **Integration Contract:** [docs/contracts/HARDWARE_SOFTWARE_INTEGRATION.md](docs/contracts/HARDWARE_SOFTWARE_INTEGRATION.md)
- **Architectural Decisions (ADRs 001–007):** [docs/contracts/DECISIONS.md](docs/contracts/DECISIONS.md)
- **Hardware Integration Complete:** [docs/HARDWARE_INTEGRATION_COMPLETE.md](docs/HARDWARE_INTEGRATION_COMPLETE.md)
- **Final Integration Report:** [FINAL_HARDWARE_INTEGRATION_REPORT.md](FINAL_HARDWARE_INTEGRATION_REPORT.md)
