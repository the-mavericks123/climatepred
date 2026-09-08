/**
 * Climate Eye — Unified Layers Controller (Step F4.5)
 *
 * Coordinates all 9 Climate Eye data layers:
 * 1. SENSOR_MESH (Infrastructure Nodes)
 * 2. TEMPERATURE (Raw °C)
 * 3. RAINFALL (Raw mm/h)
 * 4. SOIL_MOISTURE (Raw %)
 * 5. AIR_QUALITY (Raw AQI)
 * 6. WATER_LEVEL (Raw m)
 * 7. FIRES (NASA FIRMS via GEV local-firms adapter)
 * 8. DAMS (USACE Dams via GEV local-dams adapter)
 * 9. EARTHQUAKES (USGS Earthquakes via GEV earthquakes adapter)
 *
 * Requirements:
 * - Real measurements only. No risk calculations, models, or predictions.
 * - Idempotent initialization and leak-free destruction.
 * - Single Cesium globe integration.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_LAYERS } from '../state/constants.js';
import { initNodesLayer, destroyNodesLayer, getNodesLayer } from './nodesLayer.js';
import { createMetricLayers } from './metricLayers.js';
import { createFirmsAdapter } from './adapters/firmsAdapter.js';
import { createDamsAdapter } from './adapters/damsAdapter.js';
import { createEarthquakesAdapter } from './adapters/earthquakesAdapter.js';
import { initGlobalHazardsLayer, destroyGlobalHazardsLayer, getGlobalHazardsLayer } from './globalHazardsLayer.js';
import { LAYER_LEGENDS, getLayerLegend } from './legends.js';


let activeController = null;

/**
 * Creates the unified Climate Eye layers controller.
 *
 * @param {object} options
 * @param {object} options.viewer - Cesium Viewer instance
 * @param {object} options.store - Authoritative Climate Eye store
 * @param {object} [options.dataManager] - GEV DataLayerManager instance
 * @param {object} [options.Cesium] - Optional Cesium module override
 * @returns {object} Layers controller instance
 */
export function createLayersController({
  viewer,
  store,
  dataManager = null,
  Cesium,
} = {}) {
  if (!viewer) {
    throw new TypeError('createLayersController requires a valid Cesium viewer instance');
  }
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createLayersController requires an authoritative Climate Eye store');
  }

  let nodesLayer = null;
  let metricLayers = null;
  let firmsAdapter = null;
  let damsAdapter = null;
  let earthquakesAdapter = null;
  let globalHazardsLayer = null;
  let storeUnsubscribe = null;
  let isDestroyed = false;
  let lastLayerState = {};

  function syncLayersWithState() {
    if (isDestroyed) return;
    const state = store.getState();
    const currentLayers = state?.layers || {};

    // 1. SENSOR_MESH
    const meshVisible = Boolean(currentLayers[CLIMATE_LAYERS.SENSOR_MESH]);
    if (nodesLayer && typeof nodesLayer.setVisible === 'function') {
      nodesLayer.setVisible(meshVisible);
    }

    // 2. Metrics (handled in metricLayers sync)
    if (metricLayers && typeof metricLayers.update === 'function') {
      metricLayers.update();
    }

    // 3. Adapters (GEV layers)
    const firesVisible = Boolean(currentLayers[CLIMATE_LAYERS.FIRES]);
    if (lastLayerState[CLIMATE_LAYERS.FIRES] !== firesVisible && firmsAdapter) {
      firmsAdapter.setVisible(firesVisible);
    }

    const damsVisible = Boolean(currentLayers[CLIMATE_LAYERS.DAMS]);
    if (lastLayerState[CLIMATE_LAYERS.DAMS] !== damsVisible && damsAdapter) {
      damsAdapter.setVisible(damsVisible);
    }

    const quakesVisible = Boolean(currentLayers[CLIMATE_LAYERS.EARTHQUAKES]);
    if (lastLayerState[CLIMATE_LAYERS.EARTHQUAKES] !== quakesVisible && earthquakesAdapter) {
      earthquakesAdapter.setVisible(quakesVisible);
    }

    // 4. Global Hazards Layer
    const globalVisible = currentLayers[CLIMATE_LAYERS.GLOBAL_HAZARDS] !== false;
    if (globalHazardsLayer && typeof globalHazardsLayer.setVisible === 'function') {
      globalHazardsLayer.setVisible(globalVisible);
    }
    if (globalHazardsLayer && typeof globalHazardsLayer.update === 'function') {
      globalHazardsLayer.update();
    }

    lastLayerState = { ...currentLayers };
  }

  function init() {
    if (isDestroyed) return;

    // Initialize node marker layer
    nodesLayer = initNodesLayer({ viewer, store, Cesium });

    // Initialize metric badge layer
    metricLayers = createMetricLayers({ viewer, store, Cesium });
    metricLayers.init();

    // Initialize global hazards & disaster event layer
    globalHazardsLayer = initGlobalHazardsLayer({ viewer, store, Cesium });

    // Initialize GEV adapters
    firmsAdapter = createFirmsAdapter({ viewer, dataManager });
    damsAdapter = createDamsAdapter({ viewer, dataManager });
    earthquakesAdapter = createEarthquakesAdapter({ viewer, dataManager });

    // Subscribe to store for layer toggles
    storeUnsubscribe = store.subscribe(() => {
      syncLayersWithState();
    });

    // Initial synchronization
    syncLayersWithState();
  }


  function setLayerVisibility(layerId, visible) {
    if (typeof store.setLayerVisibility === 'function') {
      store.setLayerVisibility(layerId, visible);
    } else {
      store.dispatch({
        type: 'LAYER_VISIBILITY_CHANGED',
        payload: { layerId, visible: Boolean(visible) },
      });
    }
  }

  function toggleLayer(layerId) {
    if (typeof store.toggleLayer === 'function') {
      store.toggleLayer(layerId);
    } else {
      const current = Boolean(store.getState()?.layers?.[layerId]);
      setLayerVisibility(layerId, !current);
    }
  }

  function isLayerVisible(layerId) {
    return Boolean(store.getState()?.layers?.[layerId]);
  }

  function destroy() {
    if (isDestroyed) return;
    isDestroyed = true;

    if (typeof storeUnsubscribe === 'function') {
      storeUnsubscribe();
      storeUnsubscribe = null;
    }

    if (metricLayers) {
      metricLayers.destroy();
      metricLayers = null;
    }

    if (nodesLayer) {
      destroyNodesLayer();
      nodesLayer = null;
    }

    if (firmsAdapter) {
      firmsAdapter.destroy();
      firmsAdapter = null;
    }

    if (damsAdapter) {
      damsAdapter.destroy();
      damsAdapter = null;
    }

    if (earthquakesAdapter) {
      earthquakesAdapter.destroy();
      earthquakesAdapter = null;
    }

    if (globalHazardsLayer) {
      destroyGlobalHazardsLayer();
      globalHazardsLayer = null;
    }

    lastLayerState = {};
  }

  return {
    init,
    destroy,
    setLayerVisibility,
    toggleLayer,
    isLayerVisible,
    getLayerLegend,
    getAllLegends: () => LAYER_LEGENDS,
    getNodesLayer: () => nodesLayer || getNodesLayer(),
    getMetricLayers: () => metricLayers,
    getGlobalHazardsLayer: () => globalHazardsLayer || getGlobalHazardsLayer(),
    getAdapters: () => ({
      firms: firmsAdapter,
      dams: damsAdapter,
      earthquakes: earthquakesAdapter,
    }),
  };
}

/**
 * Initializes or returns the singleton Climate Eye layers controller.
 *
 * @param {object} options
 * @returns {object} Controller instance
 */
export function initClimateLayers(options = {}) {
  if (activeController) {
    return activeController;
  }
  activeController = createLayersController(options);
  activeController.init();
  return activeController;
}

/**
 * Returns the currently active layers controller, if any.
 *
 * @returns {object|null}
 */
export function getClimateLayers() {
  return activeController;
}

/**
 * Destroys the active layers controller.
 */
export function destroyClimateLayers() {
  if (activeController) {
    activeController.destroy();
    activeController = null;
  }
}
