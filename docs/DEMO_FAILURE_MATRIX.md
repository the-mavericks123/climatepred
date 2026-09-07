# Climate Eye View — Demo Failure Matrix & Degradation Runbook

**Document Version:** 1.0.0  
**Phase:** Physical Demo Readiness  
**Target:** Hackathon Live Demonstration Stability  

---

## 1. Physical Failure Degradation Matrix

| Subsystem / Component Failure | Immediate Symptom | System Reaction | Rapid Operator Fallback (< 2 min) |
|:---|:---|:---|:---|
| **DHT11 Sensor Hardware Fault** | CRC errors / Timeout on GPIO 4 | Ingestion sets `temperature = null`, status `FAILED` | BMP280 secondary temperature used automatically; Heat model functions with reduced confidence. |
| **BMP280 I2C Disconnect** | Missing ACK on `0x76` | Ingestion sets `pressure = null`, status `FAILED` | Fallback to nominal atmospheric baseline (1013.25 hPa) with `UNVERIFIED` flag. |
| **GPS Indoors (No Satellite Fix)** | `$GPGGA` sentences report fix quality `0` | `HardwareSensorCalibrator` rejects coordinates; marks `UNAVAILABLE` | Automatically falls back to station ground coordinates (Hyderabad: 17.3850° N, 78.4867° E). Node renders on globe. |
| **Raindrop Plate Dry / Detached** | ADC floating or stuck at 4095 | Ingestion sets `rainfall = 0.0 mm/hr`, status `UNVERIFIED` | Normal operation. Demonstrator can moisten plate with a damp paper towel to trigger live rainfall response. |
| **Soil Moisture Uncalibrated** | ADC reading outside calibrated curve | Software clamps reading to [0, 100]%, status `UNVERIFIED` | Switch to Level 2/3 fixture replay if physical probe reading is noisy. |
| **Optical Dust Transistor Inactive**| Pulse pin disconnected; ADC reads 0V | Ingestion sets `air_quality = null`, status `UNAVAILABLE` | System continues without AQI; other layers unaffected. |
| **LoRa RA-02 Link Failure / Distance**| Packet counter freezes; RSSI drops below -120 dBm | Backend flags node `STALE` after 30 seconds; GEV globe dims node billboard | **Switch to Level 3 (Deterministic Telemetry Replay)** via one CLI command: `.venv\Scripts\python.exe -m intelligence.scripts.run_phase11_golden_production_path`. |
| **MQTT Broker Down / Crash** | Connection refused on port 1883 | Ingestion client engages exponential backoff retries (1s to 30s) | Restart local Mosquitto service or trigger direct REST ingestion endpoint `/api/v1/telemetry`. |
| **PostGIS / Database Unavailable** | Storage write exception | Fallback to embedded SQLite database (`intelligence.db`) or in-memory persistence | Seamless in-memory fallback preserves full API query capability. |
| **Venue Wi-Fi / Internet Failure** | DNS failures for external weather tiles | Zero impact on physical telemetry and GEV local layers | Golden path runs 100% locally on `localhost`. Basemap falls back to offline raster / vector cache. |
| **Laptop Resource Exhaustion** | Vite dev server slow / high memory | GEV Cesium render loop throttles | Run `npm --prefix gods-eye-view run preview` (production bundle) for 4x lower CPU/RAM usage. |

---

## 2. Fast Recovery Command Reference

### Level 3 Fallback: Instant Deterministic Telemetry Ingestion
If hardware power or LoRa radio link fails on stage:
```bash
# Injects clean, verified, calibrated telemetry into the local backend
.venv\Scripts\python.exe -c "
import urllib.request, json
req = urllib.request.Request(
    'http://localhost:8000/api/v1/telemetry',
    data=json.dumps({
        'node_id': 'NODE-001',
        'location': {'lat': 17.3850, 'lon': 78.4867},
        'measurements': {
            'temperature': 31.4, 'humidity': 68.5, 'pressure': 1008.2,
            'rainfall': 12.6, 'soil_moisture': 68.3, 'water_level': None,
            'air_quality': 42.0, 'light_intensity': 532.4
        }
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
print(urllib.request.urlopen(req).read().decode('utf-8'))
"
```
**Result:** GEV 3D globe immediately lights up with active node status, rendering live hazard vectors and evacuation routes.
