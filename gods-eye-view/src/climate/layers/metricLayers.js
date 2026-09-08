/**
 * Climate Eye — Telemetry Metric Visualization Layers (Step F4.5)
 *
 * Renders real measurement layers onto the Cesium globe:
 * - Temperature (°C)
 * - Rainfall (mm/h)
 * - Soil Moisture (%)
 * - Air Quality (AQI)
 * - Water Level (m)
 *
 * Strict Requirements:
 * - Real measurements only; no risk calculation, no hazard thresholds, no predictions.
 * - Numeric zero (0) is preserved as a valid reading (e.g. "0.0 mm/h", "0%").
 * - Null / missing is preserved as "--" without false substitution.
 * - Uses existing GEV Cesium viewer and terrain clamping.
 * - Clean lifecycle: idempotent initialization, leak-free destruction.
 *
 * Browser-safe: No Node.js core modules.
 */

import * as CesiumDefault from 'cesium';
import { governorRequestRender } from '../../renderGovernor.js';
import { CLIMATE_LAYERS } from '../state/constants.js';
import { LAYER_LEGENDS } from './legends.js';

export const CLIMATE_METRICS_DATA_SOURCE_NAME = 'climate-eye-metrics';
export const CLIMATE_METRIC_ENTITY_PREFIX = 'climate-metric:';

// Canonical telemetry field mapping
export const METRIC_LAYER_CONFIGS = Object.freeze({
  [CLIMATE_LAYERS.TEMPERATURE]: {
    field: 'temperature',
    unit: '°C',
    decimals: 1,
    badgeColor: '#fb923c', // Warm Amber (physical property, not risk)
    yOffset: 16,
  },
  [CLIMATE_LAYERS.RAINFALL]: {
    field: 'rainfall',
    unit: 'mm/h',
    decimals: 1,
    badgeColor: '#38bdf8', // Sky Blue (physical precipitation)
    yOffset: 28,
  },
  [CLIMATE_LAYERS.SOIL_MOISTURE]: {
    field: 'soil_moisture',
    unit: '%',
    decimals: 1,
    badgeColor: '#34d399', // Emerald/Teal (physical moisture)
    yOffset: 40,
  },
  [CLIMATE_LAYERS.AIR_QUALITY]: {
    field: 'air_quality',
    unit: 'AQI',
    decimals: 0,
    badgeColor: '#a78bfa', // Lavender/Purple (particulate matter)
    yOffset: 52,
  },
  [CLIMATE_LAYERS.WATER_LEVEL]: {
    field: 'water_level',
    unit: 'm',
    decimals: 2,
    badgeColor: '#60a5fa', // Blue (physical water depth)
    yOffset: 64,
  },
});

/**
 * Formats a measurement strictly preserving 0 and null.
 *
 * @param {number|null|undefined} value
 * @param {string} unit
 * @param {number} decimals
 * @returns {string}
 */
export function formatMeasurementBadge(value, unit, decimals = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return `-- ${unit}`;
  }
  const num = Number(value);
  return `${num.toFixed(decimals)} ${unit}`;
}

/**
 * Creates the Climate Eye telemetry metric layers manager.
 *
 * @param {object} options
 * @param {object} options.viewer - Cesium Viewer instance
 * @param {object} options.store - Authoritative Climate Eye store
 * @param {object} [options.Cesium] - Optional Cesium module override
 * @returns {object} Metric layers controller
 */
export function createMetricLayers({
  viewer,
  store,
  Cesium = CesiumDefault,
} = {}) {
  if (!viewer) {
    throw new TypeError('createMetricLayers requires a valid Cesium viewer instance');
  }
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createMetricLayers requires an authoritative Climate Eye store');
  }

  let dataSource = null;
  let storeUnsubscribe = null;
  let isDestroyed = false;

  // Map of entityKey -> Cesium.Entity
  const entityMap = new Map();

  /**
   * Synchronizes metric badge entities from the store.
   */
  function syncEntitiesFromState() {
    if (isDestroyed || !dataSource) return;

    const state = store.getState();
    const nodes = state?.nodes?.byId || {};
    const allNodeIds = state?.nodes?.allIds || [];
    const telemetryByNode = state?.telemetry?.byNodeId || {};
    const layers = state?.layers || {};

    const activeEntityKeys = new Set();

    // Iterate across active metric layers
    for (const [layerId, config] of Object.entries(METRIC_LAYER_CONFIGS)) {
      const isLayerActive = Boolean(layers[layerId]);
      if (!isLayerActive) continue;

      for (const nodeId of allNodeIds) {
        const node = nodes[nodeId] || {};
        const telemetry = telemetryByNode[nodeId] || null;

        const lat = typeof node.latitude === 'number' ? node.latitude : (telemetry && typeof telemetry.latitude === 'number' ? telemetry.latitude : null);
        const lon = typeof node.longitude === 'number' ? node.longitude : (telemetry && typeof telemetry.longitude === 'number' ? telemetry.longitude : null);

        if (lat === null || lon === null || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          continue;
        }

        const rawValue = telemetry ? telemetry[config.field] : null;
        const badgeText = formatMeasurementBadge(rawValue, config.unit, config.decimals);
        const entityKey = `${CLIMATE_METRIC_ENTITY_PREFIX}${layerId}:${nodeId}`;
        activeEntityKeys.add(entityKey);

        const targetPosition = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
        let entity = entityMap.get(entityKey);

        if (!entity) {
          entity = dataSource.entities.add({
            id: entityKey,
            name: `${nodeId} - ${config.field}`,
            position: targetPosition,
            label: {
              text: badgeText,
              font: '10px "JetBrains Mono", monospace',
              style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
              fillColor: Cesium.Color ? Cesium.Color.fromCssColorString(config.badgeColor) : undefined,
              outlineColor: Cesium.Color ? Cesium.Color.BLACK : undefined,
              outlineWidth: 2,
              pixelOffset: new Cesium.Cartesian2(0, config.yOffset),
              heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            properties: {
              layerId,
              nodeId,
              metric: config.field,
              value: rawValue,
            },
          });
          entityMap.set(entityKey, entity);
        } else {
          // In-place update (flicker-free)
          if (entity.position && typeof entity.position.setValue === 'function') {
            entity.position.setValue(targetPosition);
          } else {
            entity.position = targetPosition;
          }

          if (entity.label) {
            if (typeof entity.label.text?.setValue === 'function') {
              entity.label.text.setValue(badgeText);
            } else {
              entity.label.text = badgeText;
            }
          }

          if (entity.properties) {
            entity.properties.value = rawValue;
          }
        }
      }
    }

    // Remove entities for deactivated layers or removed nodes
    for (const [key, entity] of entityMap.entries()) {
      if (!activeEntityKeys.has(key)) {
        dataSource.entities.remove(entity);
        entityMap.delete(key);
      }
    }

    try {
      governorRequestRender('climate-metrics-update');
    } catch (_) {}
  }

  function init() {
    if (isDestroyed) return;

    dataSource = new Cesium.CustomDataSource(CLIMATE_METRICS_DATA_SOURCE_NAME);
    viewer.dataSources.add(dataSource);

    storeUnsubscribe = store.subscribe(() => {
      syncEntitiesFromState();
    });

    syncEntitiesFromState();
  }

  function setVisible(visible) {
    if (dataSource) {
      dataSource.show = Boolean(visible);
      try {
        governorRequestRender('climate-metrics-visibility');
      } catch (_) {}
    }
  }

  function destroy() {
    if (isDestroyed) return;
    isDestroyed = true;

    if (typeof storeUnsubscribe === 'function') {
      storeUnsubscribe();
      storeUnsubscribe = null;
    }

    if (dataSource && viewer.dataSources) {
      try {
        dataSource.entities.removeAll();
        viewer.dataSources.remove(dataSource, true);
      } catch (_) {}
      dataSource = null;
    }

    entityMap.clear();

    try {
      governorRequestRender('climate-metrics-destroyed');
    } catch (_) {}
  }

  return {
    init,
    update: syncEntitiesFromState,
    setVisible,
    destroy,
    getDataSource: () => dataSource,
    getEntityMap: () => entityMap,
  };
}
