# Climate Eye View — Architectural & Hardware Decision Records (ADRs)

**Document Version:** 1.0.0  
**Status:** Authoritative Architectural Baseline  
**Date:** September 8, 2026  

---

## ADR-001: Absence of Physical Water-Level Transducer

### Context
The Climate Eye View S2 Flood Detection Model (`FloodModel`, Phase 2) was mathematically formulated to synthesize three environmental features:
1. Rainfall intensity rate ($R$ in mm/hr)
2. Soil moisture saturation ($S$ in %)
3. Surface water level ($W$ in meters above baseline)

The actual physical hardware bill of materials (BOM) deployed on the field node consists of:
- ESP32 MCU
- GY-GPS6MV2P GPS
- LM2596 Power Converter
- Raindrop Module (resistive analog)
- 6-Wire Optical Dust Sensor (GP2Y1010AU0F)
- BH1750 Light Sensor (I2C)
- BMP280 Barometric Pressure/Temp Sensor (I2C)
- LoRa RA-02 RF Transceiver (SX1278 SPI)
- DHT11 Temp/Humidity Sensor (1-wire)
- Soil Moisture Sensor (resistive/capacitive analog)

**The physical hardware contains NO water-level sensor** (no submersible hydrostatic pressure transducer, ultrasonic ranger, or FMCW radar gauge).

### Decision
1. **Zero Fabrication:** The ingestion system and firmware shall **NEVER** output `water_level = 0.0` or any synthetic numerical default for live node readings. Generating fake zeros implies a dry riverbed, which is false evidence.
2. **Explicit Null Representation:** On physical hardware telemetry packets, `water_level` shall be strictly `null` (None in Python).
3. **Sensor Status Flag:** The `sensor_status` metadata dictionary shall explicitly report `"water_level": "UNAVAILABLE"`.
4. **Hazard Intelligence Response:** In accordance with the Phase 2 `HazardQualityGate.verify()` contract, when `water_level_m` is `None` on live observed telemetry, the quality gate reports `is_admissible = False` with reason:
   `"Missing required inputs for flood: water_level_m"`.
   The `FloodModel` returns `HazardStatus.UNAVAILABLE` with `severity = 0.0` and `confidence = 0.0`.
5. **No Mathematical Alteration:** The authoritative flood formula:
   $$\text{Flood Severity} = w_r \cdot R + w_w \cdot W + w_s \cdot S$$
   remains untouched and unweakened.
6. **Simulation / Demo Isolation:** When water level is required to demonstrate flood propagation, compound disaster cascades, or bridge collapse, synthetic water level is injected **ONLY** in dedicated simulation/demo fixtures, and **MUST** carry `simulated = true`.

---

## ADR-002: Temperature Arbitration (DHT11 vs BMP280)

### Context
Both the DHT11 and the BMP280 measure temperature. The DHT11 is an uncalibrated polymer capacitor/thermistor with low precision ($0–50^\circ\text{C} \pm 2.0^\circ\text{C}$). The BMP280 is a factory-calibrated silicon bandgap transducer ($ -40–85^\circ\text{C} \pm 0.5^\circ\text{C}$).

### Decision
1. **Primary Ambient Temperature:** The DHT11 temperature output maps to canonical `measurements.temperature` to maintain backward compatibility with Phase 1–11 baseline expectations.
2. **Barometric Pressure:** The BMP280 output maps directly to canonical `measurements.pressure` (in hPa).
3. **Provenance & Secondary Tracking:** The BMP280 temperature reading is preserved in the raw sensor status block as `temperature_bmp280` to allow analytical comparison without silently blending or fusing two divergent physical sensors.

---

## ADR-003: Raindrop Module Calibration Semantics

### Context
The raindrop sensor consists of nickel-plated interleaved PCB traces functioning as a variable resistor connected to an LM393 comparator with analog output (AO). The raw ADC value is an inverse function of surface water droplet coverage (dry $\approx 4095$, fully submerged $\approx 1000$). It does **NOT** measure volumetric accumulation or rainfall intensity (mm/hr).

### Decision
1. **Prohibition of Raw ADC as mm/hr:** Firmware and ingestion pipelines must not assign raw ADC integers directly to the `rainfall` field.
2. **Calibration Function:** The hardware integration layer provides an inverse piecewise logarithmic conversion model:
   $$\text{Rainfall Rate (mm/hr)} = f(\text{ADC})$$
3. **Calibration Status:** Because this calibration is empirical and unverified in a certified rain-tunnel or tipping-bucket colocation, the status of this measurement shall be marked:
   `"rainfall": "UNVERIFIED"`.

---

## ADR-004: Soil Moisture Sensor Two-Point Calibration

### Context
Soil moisture sensors output raw analog voltages dependent on soil electrical conductivity. An uncalibrated ADC output cannot be reported as percentage moisture.

### Decision
1. **Two-Point Calibration:** Calibration parameters $ADC_{\text{dry}}$ (in air) and $ADC_{\text{wet}}$ (submerged in water) must be configured per node:
   $$\text{Soil Moisture (\%)} = \text{clamp}\left(100 \cdot \frac{ADC_{\text{dry}} - ADC_{\text{raw}}}{ADC_{\text{dry}} - ADC_{\text{wet}}}, 0.0, 100.0\right)$$
2. **Status Tracking:** When running with default parameters rather than physical soil samples, the status shall be:
   `"soil_moisture": "UNVERIFIED"`.

---

## ADR-005: Optical Dust Sensor (GP2Y1010AU0F) Processing

### Context
The 6-wire optical dust sensor pulses an internal IR LED for $0.32\text{ ms}$ and samples the phototransistor output voltage at $0.28\text{ ms}$. The voltage is proportional to dust density ($\text{mg/m}^3$).

### Decision
1. **Physical Metric:** The sensor reading is converted to Dust Density in $\mu\text{g/m}^3$.
2. **AQI Calculation:** Dust density is mapped to PM2.5 AQI according to US EPA standardized breakpoints.
3. **Status:** Until colocated with an optical particle counter (e.g. BAM-1020), status is marked `"air_quality": "UNVERIFIED"`.

---

## ADR-006: BH1750 Ambient Light Decoupling

### Context
The BH1750 provides digital ambient illuminance in lux ($0 - 65,535\text{ lx}$). None of the Phase 2–10 models (Heat, Flood, Drought, Prediction, Cascades, Evacuation) depend on light intensity.

### Decision
1. **Schema Extension:** `light_intensity` is added as an optional field in `SensorMeasurements`.
2. **Model Isolation:** Light intensity is stored and rendered on GEV dashboards, but does **NOT** alter the mathematical behavior of Heat, Flood, or Drought algorithms.

---

## ADR-007: LoRa RA-02 Network Transport Architecture

### Context
The LoRa RA-02 module is an SX1278-based SPI transceiver operating at 433 MHz. It broadcasts raw RF packets over the physical air interface. It possesses no IP stack, Wi-Fi hardware, or MQTT client.

### Decision
1. **Two-Tier Topology:** The physical field node transmits compact LoRa packets to a LoRa Gateway (a second ESP32 or serial host). The gateway decodes the radio packet and publishes standard JSON over Wi-Fi/Ethernet to the Mosquitto MQTT broker at `climate/nodes/{node_id}/telemetry`.
2. **Truthful System Description:** Documentation shall never claim direct MQTT connectivity from the sensor ESP32 over LoRa RA-02.
