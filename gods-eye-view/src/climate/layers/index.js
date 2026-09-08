/**
 * Climate Eye — Layers Entry Point (Steps F4.4 & F4.5)
 *
 * Exposes the modular visualization layers for the Cesium globe:
 * - Sensor nodes layer
 * - Telemetry metric layers (Temperature, Rainfall, Soil Moisture, Air Quality, Water Level)
 * - GEV adapters (NASA FIRMS, Dams, USGS Earthquakes)
 * - Layer legends & non-risk attribution
 * - Unified layers controller
 *
 * Browser-safe: No Node.js core modules.
 */

export {
  CLIMATE_NODES_DATA_SOURCE_NAME,
  CLIMATE_NODE_ENTITY_PREFIX,
  CLIMATE_NODES_LAYER_ID,
  createNodesLayer,
  initNodesLayer,
  getNodesLayer,
  destroyNodesLayer,
} from './nodesLayer.js';

export {
  CLIMATE_METRICS_DATA_SOURCE_NAME,
  CLIMATE_METRIC_ENTITY_PREFIX,
  METRIC_LAYER_CONFIGS,
  formatMeasurementBadge,
  createMetricLayers,
} from './metricLayers.js';

export {
  LAYER_LEGENDS,
  getLayerLegend,
} from './legends.js';

export {
  GEV_FIRMS_LAYER_ID,
  createFirmsAdapter,
} from './adapters/firmsAdapter.js';

export {
  GEV_DAMS_LAYER_ID,
  createDamsAdapter,
} from './adapters/damsAdapter.js';

export {
  GEV_EARTHQUAKES_LAYER_ID,
  createEarthquakesAdapter,
} from './adapters/earthquakesAdapter.js';

export {
  CLIMATE_GLOBAL_HAZARDS_DATA_SOURCE_NAME,
  GLOBAL_HAZARD_ENTITY_PREFIX,
  GLOBAL_EVENT_ENTITY_PREFIX,
  CLIMATE_GLOBAL_HAZARDS_LAYER_ID,
  createGlobalHazardsLayer,
  initGlobalHazardsLayer,
  getGlobalHazardsLayer,
  destroyGlobalHazardsLayer,
} from './globalHazardsLayer.js';

export {
  createLayersController,
  initClimateLayers,
  getClimateLayers,
  destroyClimateLayers,
} from './layersController.js';

