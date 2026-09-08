/**
 * Climate Eye — Layer Legends and Provenance (Step F4.5)
 *
 * Provides metadata, units, and attribution for all Climate Eye layers.
 * Strict boundary: Distinguishes raw measurements from authoritative multi-feed hazard intelligence.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_LAYERS } from '../state/constants.js';

export const LAYER_LEGENDS = Object.freeze({
  [CLIMATE_LAYERS.SENSOR_MESH]: Object.freeze({
    id: CLIMATE_LAYERS.SENSOR_MESH,
    title: 'Sensor Mesh Network',
    metric: 'Hardware Nodes',
    unit: 'Node ID',
    source: 'Climate Eye Mesh Infrastructure',
    type: 'infrastructure',
    isRiskLayer: false,
    notice: 'Physical hardware sensor nodes and network status.',
  }),
  [CLIMATE_LAYERS.TEMPERATURE]: Object.freeze({
    id: CLIMATE_LAYERS.TEMPERATURE,
    title: 'Ambient Temperature',
    metric: 'temperature',
    unit: '°C',
    source: 'Climate Eye Telemetry',
    type: 'telemetry',
    isRiskLayer: false,
    notice: 'Raw ambient temperature measurement. No heatwave risk inference applied.',
  }),
  [CLIMATE_LAYERS.RAINFALL]: Object.freeze({
    id: CLIMATE_LAYERS.RAINFALL,
    title: 'Precipitation Rate',
    metric: 'rainfall',
    unit: 'mm/h',
    source: 'Climate Eye Telemetry',
    type: 'telemetry',
    isRiskLayer: false,
    notice: 'Direct precipitation intensity. 0 mm/h is preserved. No flood severity inference applied.',
  }),
  [CLIMATE_LAYERS.SOIL_MOISTURE]: Object.freeze({
    id: CLIMATE_LAYERS.SOIL_MOISTURE,
    title: 'Soil Moisture',
    metric: 'soil_moisture',
    unit: '%',
    source: 'Climate Eye Telemetry',
    type: 'telemetry',
    isRiskLayer: false,
    notice: 'Volumetric soil moisture percentage. No drought risk calculation applied.',
  }),
  [CLIMATE_LAYERS.AIR_QUALITY]: Object.freeze({
    id: CLIMATE_LAYERS.AIR_QUALITY,
    title: 'Air Quality Index',
    metric: 'air_quality',
    unit: 'AQI',
    source: 'Climate Eye Telemetry',
    type: 'telemetry',
    isRiskLayer: false,
    notice: 'Direct sensor particulate measurement. No health risk prediction applied.',
  }),
  [CLIMATE_LAYERS.WATER_LEVEL]: Object.freeze({
    id: CLIMATE_LAYERS.WATER_LEVEL,
    title: 'Water Level',
    metric: 'water_level',
    unit: 'm',
    source: 'Climate Eye Telemetry',
    type: 'telemetry',
    isRiskLayer: false,
    notice: 'Gauge water level relative to baseline. Preserves missing data as unmeasured.',
  }),
  [CLIMATE_LAYERS.FIRES]: Object.freeze({
    id: CLIMATE_LAYERS.FIRES,
    title: 'Thermal Anomalies',
    metric: 'brightness',
    unit: 'VIIRS FRP',
    source: 'NASA FIRMS (GEV Adapter)',
    type: 'external_adapter',
    isRiskLayer: false,
    notice: 'Satellite thermal detection points. Unaltered NASA FIRMS data.',
  }),
  [CLIMATE_LAYERS.DAMS]: Object.freeze({
    id: CLIMATE_LAYERS.DAMS,
    title: 'Dams & Reservoirs',
    metric: 'storage',
    unit: 'USACE Registry',
    source: 'USACE / Local Dams (GEV Adapter)',
    type: 'external_adapter',
    isRiskLayer: false,
    notice: 'Infrastructure point registry. Raw location and capacity data.',
  }),
  [CLIMATE_LAYERS.EARTHQUAKES]: Object.freeze({
    id: CLIMATE_LAYERS.EARTHQUAKES,
    title: 'Seismic Events',
    metric: 'magnitude',
    unit: 'M2.5+ USGS',
    source: 'USGS Earthquake Hazards Program (GEV Adapter)',
    type: 'external_adapter',
    isRiskLayer: false,
    notice: 'Recorded seismic hypocenters. No aftershock prediction model applied.',
  }),
  [CLIMATE_LAYERS.GLOBAL_HAZARDS]: Object.freeze({
    id: CLIMATE_LAYERS.GLOBAL_HAZARDS,
    title: 'Global Hazard Zones',
    metric: 'hazard_zones',
    unit: 'Multi-Source',
    source: 'Authoritative Multi-Feed Fusion (GDACS, FIRMS, USGS, Open-Meteo)',
    type: 'global_hazard',
    isRiskLayer: false,
    notice: 'Fused authoritative global hazard boundaries and active disaster zones.',
  }),
  [CLIMATE_LAYERS.HEAT_ZONES]: Object.freeze({
    id: CLIMATE_LAYERS.HEAT_ZONES,
    title: 'Thermal & Heatwave Zones',
    metric: 'heat_index',
    unit: '°C / Severity',
    source: 'Open-Meteo & Ground Fusion',
    type: 'global_hazard',
    isRiskLayer: false,
    notice: 'Spatial thermal anomalies and extreme temperature hazard zones.',
  }),
  [CLIMATE_LAYERS.FLOOD_ZONES]: Object.freeze({
    id: CLIMATE_LAYERS.FLOOD_ZONES,
    title: 'Hydrological & Flood Zones',
    metric: 'inundation',
    unit: 'GloFAS / GDACS',
    source: 'GloFAS & GDACS Flood Feeds',
    type: 'global_hazard',
    isRiskLayer: false,
    notice: 'Hydrological inundation extents and severe precipitation flood buffers.',
  }),
  [CLIMATE_LAYERS.COMPOUND_ZONES]: Object.freeze({
    id: CLIMATE_LAYERS.COMPOUND_ZONES,
    title: 'Compound Disaster Zones',
    metric: 'cascade_risk',
    unit: 'Multi-Hazard',
    source: 'S2 Compound Disaster Engine',
    type: 'global_hazard',
    isRiskLayer: false,
    notice: 'Overlapping concurrent hazards creating cascading systemic vulnerabilities.',
  }),
  [CLIMATE_LAYERS.CYCLONE_ZONES]: Object.freeze({
    id: CLIMATE_LAYERS.CYCLONE_ZONES,
    title: 'Cyclone & Severe Storm Tracks',
    metric: 'wind_speed',
    unit: 'km/h / GDACS',
    source: 'GDACS Tropical Cyclone Feeds',
    type: 'global_hazard',
    isRiskLayer: false,
    notice: 'Authoritative tropical storm tracks and radius of gale-force winds.',
  }),
});


/**
 * Returns the non-risk legend specification for a given layer ID.
 *
 * @param {string} layerId
 * @returns {object|null}
 */
export function getLayerLegend(layerId) {
  return LAYER_LEGENDS[layerId] || null;
}
