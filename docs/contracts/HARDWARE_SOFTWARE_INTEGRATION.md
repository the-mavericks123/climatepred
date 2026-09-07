# Climate Eye View — Hardware-to-Software Integration Contract

**Document Version:** 1.0.0  
**Phase:** Post-Phase-12 Final Hardware + System Integration  
**Date:** September 8, 2026  
**Status:** Authoritative Physical Interface Contract  

---

## 1. Physical Hardware Bill of Materials (BOM)

| Component | Function | Exact Model / Spec | Bus Interface | Pin Connections (ESP32) | Operating Voltage |
|---|---|---|---|---|---|
| **MCU** | Core Controller & Processing | ESP32-WROOM-32D | Dual Core 240MHz | N/A | 3.3V DC |
| **Power Regulator** | Step-Down Buck Converter | LM2596 DC-DC | Analog Power Bus | IN: 7–24V DC, OUT: 5.0V | 5.0V / 3.3V |
| **GPS Receiver** | Geolocation & Elevation | GY-GPS6MV2P (u-blox NEO-6M) | Hardware UART (UART2) | TX -> GPIO 16 (RX2), RX -> GPIO 17 (TX2) | 3.3V / 5.0V |
| **Temp & Humidity** | Ambient Weather | DHT11 Digital Sensor | 1-Wire GPIO | DATA -> GPIO 4 (10k pullup) | 3.3V |
| **Barometric Pressure** | Atmospheric Pressure & Temp | Bosch BMP280 | I2C (Address `0x76`) | SDA -> GPIO 21, SCL -> GPIO 22 | 3.3V |
| **Raindrop Sensor** | Surface Water Conduction | LM393 Comparator + Plate | ADC1 (12-bit) | AO -> GPIO 34 (Analog Input Only) | 3.3V / 5.0V |
| **Soil Moisture** | Volumetric Soil Moisture | Analog Resistive/Capacitive | ADC1 (12-bit) | AO -> GPIO 35 (Analog Input Only) | 3.3V |
| **Optical Dust Sensor** | Particulate Matter PM2.5 | Sharp GP2Y1010AU0F (6-pin) | Analog ADC + Digital Pulse | ILED -> GPIO 18, Vo -> GPIO 36 (ADC1_0) | 5.0V (Vcc), 3.3V ADC |
| **Ambient Light** | Illuminance (Lux) | ROHM BH1750 (GY-302) | I2C (Address `0x23`) | SDA -> GPIO 21, SCL -> GPIO 22 | 3.3V |
| **LoRa Transceiver** | RF Telemetry Transmission | Ai-Thinker RA-02 (SX1278) | SPI Bus (VSPI) | MOSI: 23, MISO: 19, SCK: 18, NSS: 5, RST: 14, DIO0: 2 | 3.3V (Max 3.6V) |
| **Water Level** | **NONE** | **ABSENT FROM BOM** | **N/A** | **N/A** | **N/A** |

---

## 2. Power Architecture & Voltage Rails

```
[External Battery / Solar (7.4V - 12V)]
                 ↓
      [LM2596 Buck Regulator]
                 ↓
            +5.0V Rail -----------------------------> GP2Y1010AU0F Vcc (Pin 6)
                 ↓                                    Raindrop Board Vcc
          [AMS1117-3.3V / ESP32 Onboard LDO]
                 ↓
            +3.3V Rail -----------------------------> ESP32 VDD
                                                      BMP280 Vcc
                                                      BH1750 Vcc
                                                      DHT11 Vcc
                                                      RA-02 LoRa Vcc (Strictly <= 3.3V)
                                                      NEO-6M GPS Vcc
                                                      Soil Moisture Vcc
```

---

## 3. LoRa RA-02 RF Configuration

- **Carrier Frequency:** 433.0 MHz (ISM Band)
- **Modulation:** LoRa Chirp Spread Spectrum (CSS)
- **Bandwidth (BW):** 125 kHz
- **Spreading Factor (SF):** 7 (Optimal balance of airtime ~45 ms and link budget)
- **Coding Rate (CR):** 4/5
- **Preamble Length:** 8 symbols
- **Transmit Power:** +17 dBm (PA_BOOST pin)
- **Sync Word:** `0x12` (Private Climate Network sync word)
- **Packet Structure:**
  - Standard Binary: 28 bytes packed struct (Little/Big-Endian aligned)
  - Text Fallback: Compact JSON string

---

## 4. Network Topology & Gateway Decoupling

```
+--------------------------+
|  PHYSICAL SENSOR NODE    |
|  - ESP32 Microcontroller |
|  - Transducers 1 to 9    |
|  - RA-02 SPI Transmitter |
+--------------------------+
             |
             | 433 MHz LoRa RF Packet (~45 ms airtime, 10s interval)
             v
+-----------------------------------------------------------+
|  LORA GATEWAY (Port 1883 Gateway)                         |
|  - RA-02 SPI Receiver (433 MHz)                           |
|  - Gateway ESP32 / Embedded Linux Host                    |
|  - HardwarePayloadProcessor (Conversion & Verification)   |
|  - Wi-Fi / WPA2 or Ethernet Interface                     |
|  - Paho MQTT Client v2.0                                  |
+-----------------------------------------------------------+
             |
             | MQTT Publish (QoS 1)
             v
+-----------------------------------------------------------+
|  MQTT BROKER (Eclipse Mosquitto, Port 1883)               |
|  Topic: climate/nodes/{node_id}/telemetry                 |
+-----------------------------------------------------------+
             |
             | MQTT Subscribe
             v
+-----------------------------------------------------------+
|  CLIMATE EYE S2 BACKEND MICROSERVICE                      |
+-----------------------------------------------------------+
```

---

## 5. MQTT Topics & Message Contracts

### 5.1 Topics
- `climate/nodes/{node_id}/telemetry` — Primary 10-second sensor observations
- `climate/nodes/{node_id}/status` — Operational status & hardware diagnostics
- `climate/nodes/{node_id}/heartbeat` — 30-second watchdog heartbeat
- `climate/alerts` — Outbound emergency directives from Response Planner
- `climate/commands/{node_id}` — Inbound configuration / calibration parameter updates

### 5.2 Canonical Hardware Telemetry JSON Schema
```json
{
  "schema_version": "1.0",
  "node_id": "NODE-001",
  "timestamp": "2026-09-08T10:30:15Z",
  "location": {
    "lat": 17.385044,
    "lon": 78.486671,
    "elevation": 505.0
  },
  "measurements": {
    "temperature": 28.4,
    "humidity": 65.0,
    "pressure": 1011.25,
    "rainfall": 0.0,
    "soil_moisture": 48.5,
    "water_level": null,
    "air_quality": 64.0,
    "light_intensity": 850.0,
    "battery": 94.0,
    "sensor_status": {
      "gps": "CALIBRATED",
      "dht11": "UNVERIFIED",
      "bmp280": "CALIBRATED",
      "rainfall": "UNVERIFIED",
      "soil_moisture": "UNVERIFIED",
      "optical_dust": "UNVERIFIED",
      "bh1750": "CALIBRATED",
      "water_level": "UNAVAILABLE",
      "bmp280_secondary_temp_c": "28.75"
    }
  },
  "quality": {
    "valid": true,
    "source": "ESP32_LORA",
    "received_at": "2026-09-08T10:30:16Z",
    "confidence": 1.0,
    "flags": [
      "dht11:UNVERIFIED",
      "rainfall:UNVERIFIED",
      "soil_moisture:UNVERIFIED",
      "optical_dust:UNVERIFIED",
      "water_level:UNAVAILABLE"
    ]
  }
}
```

---

## 6. Physical Sensor Calibration & Engineering Ranges

| Measurement | Raw Input | Engineering Formula | Valid Operating Range | Calibration Status | Failure Action |
|---|---|---|---|---|---|
| **Temperature** | DHT11 1-wire bitstream | $T_{\text{ambient}}$ direct °C | $-50.0\text{ to }+65.0^\circ\text{C}$ | `UNVERIFIED` | Value set to `null`; flag `dht11:FAILED` |
| **Humidity** | DHT11 1-wire bitstream | $RH$ direct % | $0.0\text{ to }100.0\%$ | `UNVERIFIED` | Value set to `null`; flag `dht11:FAILED` |
| **Pressure** | BMP280 registers | Factory trimmed math | $800.0\text{ to }1100.0\text{ hPa}$ | `CALIBRATED` | Value set to `null`; flag `bmp280:FAILED` |
| **Rainfall** | Raindrop 12-bit ADC | $(\text{wetness})^{1.8} \times 120.0$ | $0.0\text{ to }500.0\text{ mm/hr}$ | `UNVERIFIED` | Clamped to $0.0$; flag `rainfall:FAILED` |
| **Soil Moisture** | Resistive 12-bit ADC | $100 \cdot \frac{ADC_{\text{dry}} - ADC}{ADC_{\text{dry}} - ADC_{\text{wet}}}$ | $0.0\text{ to }100.0\%$ | `UNVERIFIED` | Clamped $[0, 100]$; flag `soil:FAILED` |
| **Dust / AQI** | GP2Y1010AU0F analog V | $\frac{V - 0.6}{0.005} \longrightarrow \text{EPA AQI}$ | $0.0\text{ to }500.0\text{ AQI}$ | `UNVERIFIED` | Value set to `null`; flag `dust:FAILED` |
| **Light** | BH1750 I2C word | Direct illuminance | $0.0\text{ to }120000.0\text{ lx}$ | `CALIBRATED` | Value set to `null`; flag `bh1750:FAILED` |
| **Water Level** | **None** | **None** | $0.0\text{ to }50.0\text{ m}$ | `UNAVAILABLE` | **Strictly `null`**; never 0.0 |
| **GPS Fix** | NMEA `$GPGGA` sentences | WGS84 dec. degrees | Lat: $[-90, 90]$, Lon: $[-180, 180]$ | `CALIBRATED` | Reject $(0,0)$; fallback to station config |

---

## 7. Missing Value & Staleness Semantics

1. **Missing Transducer:** When a sensor is not present (e.g. water level), the field must be `null` in JSON (never `0.0`).
2. **Failed Sensor:** When a sensor shorts or produces out-of-range values (e.g. DHT11 reporting $125^\circ\text{C}$), the field is coerced to `null`, recorded in `quality.flags`, and its status is set to `FAILED`.
3. **Staleness Threshold:** Telemetry older than 300 seconds (5 minutes) is categorized as `STALE`. The GEV frontend renders a yellow warning ring around stale nodes.
4. **Clock Skew:** Observations with timestamps more than 300 seconds ahead of the server clock are rejected with HTTP 422 (`VALIDATION_ERROR`).

---

## 8. Failure Modes & Mitigation

| Failure Mode | Impact | Mitigation / System Response |
|---|---|---|
| **ESP32 Power Loss** | Node stops transmitting | Gateway heartbeats detect silence after 30s; node flagged `STALE` |
| **LoRa Link Blockage** | Packet loss across RF | LoRa Gateway retains last known good packet; no fabrication |
| **Gateway Wi-Fi Loss** | MQTT unreachable | Gateway queues up to 256 packets in flash; bursts on reconnect |
| **MQTT Broker Down** | Ingestion pipeline paused | Paho client auto-reconnects with exponential backoff (1s to 30s) |
| **Uncalibrated Rainfall** | Approximate mm/hr | UI displays `UNVERIFIED` status badge alongside rainfall rate |
| **Missing Water Level** | Flood model missing input | Flood quality gate returns `HazardStatus.UNAVAILABLE` |
