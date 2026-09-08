# Authoritative Global Data Sources Specification

## 1. Overview & Operational Principles

Climate Eye integrates five external planetary-scale data sources to deliver continuous situational awareness. The system adheres strictly to the **Principle of Epistemic Honesty**:
- Zero fabrication of synthetic data in production feeds.
- If upstream credentials or services are missing, the system reports `UNAVAILABLE` rather than generating mock values.
- Weather observations never fabricate hydrometric values (`water_level = null` strictly enforced).
- Every data point carries explicit source attribution, sensor type, and epistemic classification.

---

## 2. External Provider Specifications

### 2.1. Open-Meteo Global Weather API

- **Service Purpose**: Near-real-time meteorological observations and short-range numerical weather predictions.
- **Provider URL**: `https://api.open-meteo.com/v1/forecast`
- **Authentication**: None required for standard open tier.
- **Polling Cadence**: 15 minutes (900 seconds) background poll.
- **Geographic Coverage**: 36 distributed reference stations spanning all continents and critical climatic zones:
  - North America: New York, Los Angeles, Chicago, Miami, Vancouver, Mexico City.
  - South America: São Paulo, Buenos Aires, Bogota, Lima, Manaus (Amazon).
  - Europe: London, Paris, Berlin, Madrid, Rome, Athens, Kyiv.
  - Africa: Cairo, Lagos, Nairobi, Johannesburg, Casablanca.
  - Asia: Tokyo, Beijing, Mumbai, New Delhi, Singapore, Bangkok, Dubai, Riyadh.
  - Oceania: Sydney, Melbourne, Auckland.
  - Polar & Arctic: Svalbard, McMurdo Station (Antarctica).
- **Extracted Fields**:
  - `temperature_2m` (°C)
  - `relative_humidity_2m` (%)
  - `surface_pressure` (hPa)
  - `precipitation` (mm/h)
  - `wind_speed_10m` (km/h)
- **Physical Invariant**:
  `water_level = null` (Open-Meteo atmospheric models do not sample riverbed or tidal gauges).
- **Epistemic Classification**: `OBSERVED` (for current hour telemetry) / `PREDICTED` (for +1h to +6h models).
- **Hazard Trigger Rules**:
  - Extreme Heat: `temperature_2m > 38.0°C` → Severity `0.70 + (temp - 38) * 0.03`
  - Torrential Rain: `precipitation > 25.0 mm/h` → Severity `0.65 + (rain - 25) * 0.02`
  - Gale-Force Wind: `wind_speed_10m > 60.0 km/h` → Severity `0.60 + (wind - 60) * 0.01`

---

### 2.2. NASA FIRMS (Fire Information for Resource Management System)

- **Service Purpose**: Global near-real-time satellite active fire and thermal anomaly detection.
- **Provider URL**: `https://firms.modaps.eosdis.nasa.gov/api/area/` / Public Area Feeds.
- **Sensors / Constellations**:
  - VIIRS (Visible Infrared Imaging Radiometer Suite) on Suomi NPP and NOAA-20 (375m resolution).
  - MODIS (Moderate Resolution Imaging Spectroradiometer) on Terra and Aqua (1km resolution).
- **Authentication**: MAP_KEY required for custom bounding box queries; public regional CSV/GeoJSON feeds utilized for open tier.
- **Polling Cadence**: 1 hour (3600 seconds) background refresh.
- **Payload Normalization & Spatial Clustering**:
  - Individual thermal anomaly detections within 25 km of each other are clustered into contiguous **Wildfire Threat Clusters**.
  - Radiative intensity is aggregated as total Fire Radiative Power (FRP, in MW).
  - Confidence metric: Extracted directly from satellite detection quality flags (0–100%).
- **Epistemic Classification**: `OBSERVED`.
- **Hazard Trigger Rules**:
  - Cluster Severity: `min(1.0, 0.50 + (cluster_frp / 2500.0) * 0.50)`.
  - Radius Calculation: `base_radius (5km) + sqrt(cluster_frp) * 0.2km`.

---

### 2.3. USGS Earthquake Hazards Program

- **Service Purpose**: Real-time global seismic monitoring and earthquake epicenters.
- **Provider URL**: `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson`
- **Authentication**: None required (Public Open Data).
- **Polling Cadence**: 5 minutes (300 seconds) background poll.
- **Filtering Criteria**:
  - Magnitude `M >= 2.5` for global events.
  - Depth: Ingested in kilometers below sea level.
  - Tsunami Potential: Evaluated when `magnitude >= 6.5` with coastal epicenter.
- **Epistemic Classification**: `OBSERVED`.
- **Hazard Trigger Rules**:
  - Magnitude `< 4.5`: Minor advisory (Severity 0.30–0.49).
  - Magnitude `4.5 <= M < 6.0`: Moderate seismic hazard (Severity 0.50–0.69).
  - Magnitude `6.0 <= M < 7.5`: Severe earthquake zone (Severity 0.70–0.89).
  - Magnitude `>= 7.5`: Catastrophic seismic event (Severity 0.90–1.00).
- **Secondary Cascade Trigger**:
  - If seismic epicenter is located in mountainous topography with recent precipitation (`>10mm`), triggers `LANDSLIDE_RISK` compound cascade.

---

### 2.4. GDACS (Global Disaster Alert and Coordination System)

- **Service Purpose**: Multi-hazard early warning and disaster impact assessments administered by the United Nations and the European Commission.
- **Provider URL**: `https://www.gdacs.org/xml/rss.xml`
- **Authentication**: None required (Public RSS/XML feed).
- **Polling Cadence**: 15 minutes (900 seconds) background poll.
- **Hazard Types Ingested**:
  - Tropical Cyclones (`TC`)
  - Floods (`FL`)
  - Earthquakes (`EQ`)
  - Volcano Eruptions (`VO`)
  - Droughts (`DR`)
- **Extracted Metadata**:
  - Alert Level: `Green`, `Orange`, `Red`.
  - Affected Population Estimates.
  - Vulnerability Multipliers.
- **Epistemic Classification**: `OBSERVED` (for reported impacts) / `INFERRED` (for population exposure models).
- **Hazard Trigger Rules**:
  - GDACS `Red`: Severity 0.90–1.00 (Immediate international disaster response protocol).
  - GDACS `Orange`: Severity 0.65–0.89 (National emergency alert).
  - GDACS `Green`: Severity 0.30–0.64 (Advisory monitoring).

---

### 2.5. Copernicus GloFAS (Global Flood Awareness System)

- **Service Purpose**: Continental and global hydrological forecasting and river discharge monitoring.
- **Provider URL**: ECMWF Climate Data Store (`https://cds.climate.copernicus.eu/api/v2`)
- **Authentication**: Requires valid `CDS_API_KEY` and User ID.
- **Polling Cadence**: 6 hours (21600 seconds) background batch.
- **Strict Honesty & Absence Policy**:
  - When `CDS_API_KEY` is not present in the runtime environment:
    - The provider returns status `UNAVAILABLE`.
    - No mock discharge hydrographs or fabricated flood zones are injected.
    - The UI card displays `COPERNICUS GLOFAS: UNAVAILABLE (REQUIRES CDS_API_KEY)`.
  - When credentials are present:
    - Queries GloFAS river discharge forecast layers (return periods 2-year, 5-year, 20-year).
    - Hydrometric fields (`water_level`, `river_discharge_m3s`) are marked `OBSERVED` / `PREDICTED`.

---

## 3. Physical Hardware Mesh (ESP32 Edge Nodes - Optional)

- **Protocol**: MQTT over TLS (`mqtts://`) and WebSocket (`ws://`).
- **Telemetry Frequency**: 1.0 second bursts / 5.0 second steady-state.
- **Sensors Supported**:
  - BME280 / BMP280 (Temperature, Humidity, Barometric Pressure).
  - Capacitive Soil Moisture Sensor.
  - Optical Tipping Bucket / Ultrasonic Rain Gauge.
  - Ultrasonic Water Depth Sensor (Direct riverbed gauge).
  - MQ-135 / PMS5003 Air Quality Particulate Sensor.
- **Decoupling Guarantee**:
  - When physical ESP32 nodes are powered on, they provide local ground-truth calibration.
  - When physical ESP32 nodes are absent (0 nodes connected), the entire global intelligence platform operates at full capacity without degradation of global situational awareness.

---

## 4. Summary Matrix of Data Feeds

| Feed Source | Primary Hazard Types | Polling Cadence | Authentication | Epistemic Status | Null Invariant Enforced |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo** | Heatwaves, Freezes, Severe Storms | 15 min | None (Open) | `OBSERVED` | `water_level = null` |
| **NASA FIRMS** | Wildfires, Biomass Burns | 60 min | None / Open Area | `OBSERVED` | `water_level = null` |
| **USGS** | Earthquakes, Seismic Waves | 5 min | None (Open) | `OBSERVED` | `water_level = null` |
| **GDACS** | Cyclones, Floods, Tsunamis | 15 min | None (Open) | `OBSERVED` | Context-dependent |
| **GloFAS** | River Inundation, Flash Floods | 6 hours | `CDS_API_KEY` | `UNAVAILABLE` without key | River gauge validated |
| **ESP32 Mesh** | Microclimate Local Ground Truth | Real-time | Token / MQTT | `OBSERVED` | Real sensor readings |
