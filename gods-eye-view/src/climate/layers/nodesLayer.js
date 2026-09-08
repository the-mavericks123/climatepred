/**
 * Climate Eye — Sensor Nodes Globe Visualization Layer (Step F4.4)
 *
 * Renders authoritative Climate Eye sensor nodes onto the existing GEV Cesium globe
 * using WGS84 coordinates and terrain clamping.
 *
 * Responsibilities:
 * - Data-driven: renders any node ID dynamically (NODE-001, NODE-006, etc.).
 * - Positions markers using real backend coordinates without fabricating positions.
 * - Visual state reflects freshness (AVAILABLE, STALE, UNAVAILABLE) without risk colors.
 * - Manages picking and selection via Cesium ScreenSpaceEventHandler and pickRegistry.
 * - Single globe: hooks directly into the existing Cesium viewer without creating a second globe.
 * - Clean lifecycle: idempotent initialization and leak-free destruction.
 *
 * Browser-safe: No Node.js core modules.
 */

import * as CesiumDefault from 'cesium';
import {
  registerPickOwner,
  unregisterPickOwner,
  resolvePickId,
} from '../../data/pickRegistry.js';
import { governorRequestRender } from '../../renderGovernor.js';
import { REALTIME_STATES, CLIMATE_LAYERS } from '../state/constants.js';

export const CLIMATE_NODES_DATA_SOURCE_NAME = 'climate-eye-nodes';
export const CLIMATE_NODE_ENTITY_PREFIX = 'climate-node:';
export const CLIMATE_NODES_LAYER_ID = 'climate-nodes';

let activeNodesLayer = null;

/**
 * Creates the Climate Eye sensor nodes layer instance.
 *
 * @param {object} options
 * @param {object} options.viewer - Cesium Viewer instance.
 * @param {object} options.store - Authoritative Climate Eye store.
 * @param {object} [options.Cesium] - Optional Cesium module override (for unit testing).
 * @returns {object} Layer controller with init, update, selectNode, destroy.
 */
export function createNodesLayer({
  viewer,
  store,
  Cesium = CesiumDefault,
} = {}) {
  if (!viewer) {
    throw new TypeError('createNodesLayer requires a valid Cesium viewer instance');
  }
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createNodesLayer requires an authoritative Climate Eye store');
  }

  let dataSource = null;
  let clickHandler = null;
  let storeUnsubscribe = null;
  let isDestroyed = false;

  // Track known entity IDs to prevent unnecessary recreation
  const entityMap = new Map(); // nodeId -> Cesium.Entity

  // Color constants (honestly distinguishing freshness, no risk colors yet)
  const COLOR_AVAILABLE = Cesium.Color ? Cesium.Color.fromCssColorString('#00f5a0') : null; // Emerald
  const COLOR_STALE = Cesium.Color ? Cesium.Color.fromCssColorString('#f59e0b') : null;     // Amber
  const COLOR_UNAVAILABLE = Cesium.Color ? Cesium.Color.fromCssColorString('#94a3b8') : null; // Slate
  const COLOR_OUTLINE_NORMAL = Cesium.Color ? Cesium.Color.fromCssColorString('#060b13') : null; // Dark
  const COLOR_OUTLINE_SELECTED = Cesium.Color ? Cesium.Color.fromCssColorString('#00d4ff') : null; // Cyan glow

  function getNodeColor(node, telemetry, rtState) {
    if (!Cesium.Color) return null;
    if (rtState === REALTIME_STATES.UNAVAILABLE || node?.status === 'offline') {
      return COLOR_UNAVAILABLE;
    }
    if (rtState === REALTIME_STATES.STALE || node?.status === 'stale') {
      return COLOR_STALE;
    }
    // Live/Available if we have active telemetry or live connection
    if (rtState === REALTIME_STATES.LIVE || (telemetry && telemetry.timestamp)) {
      return COLOR_AVAILABLE;
    }
    return COLOR_STALE;
  }

  /**
   * Synchronizes Cesium entities with the current state of nodes and telemetry.
   */
  function syncEntitiesFromState() {
    if (isDestroyed || !dataSource) return;

    const state = store.getState();
    if (state?.layers && state.layers[CLIMATE_LAYERS.SENSOR_MESH] !== undefined) {
      dataSource.show = Boolean(state.layers[CLIMATE_LAYERS.SENSOR_MESH]);
    }
    const nodes = state?.nodes?.byId || {};
    const allNodeIds = state?.nodes?.allIds || [];
    const telemetryByNode = state?.telemetry?.byNodeId || {};
    const selectedNodeId = state?.ui?.selectedNodeId || null;
    const rtState = state?.connection?.realtimeState || REALTIME_STATES.UNAVAILABLE;

    const currentIds = new Set();

    for (const nodeId of allNodeIds) {
      const node = nodes[nodeId] || {};
      const telemetry = telemetryByNode[nodeId] || null;

      // Extract coordinates (node latitude/longitude take precedence, then telemetry)
      const lat = typeof node.latitude === 'number' ? node.latitude : (telemetry && typeof telemetry.latitude === 'number' ? telemetry.latitude : null);
      const lon = typeof node.longitude === 'number' ? node.longitude : (telemetry && typeof telemetry.longitude === 'number' ? telemetry.longitude : null);

      if (lat === null || lon === null || !Number.isFinite(lat) || !Number.isFinite(lon)) {
        continue;
      }

      currentIds.add(nodeId);
      const isSelected = selectedNodeId === nodeId;
      const markerColor = getNodeColor(node, telemetry, rtState);
      const entityId = `${CLIMATE_NODE_ENTITY_PREFIX}${nodeId}`;

      let entity = entityMap.get(nodeId);

      const targetPosition = Cesium.Cartesian3.fromDegrees(lon, lat, 0);

      if (!entity) {
        // Create new marker entity
        entity = dataSource.entities.add({
          id: entityId,
          name: node.name || nodeId,
          position: targetPosition,
          point: {
            pixelSize: isSelected ? 18 : 12,
            color: markerColor || Cesium.Color.WHITE,
            outlineColor: isSelected ? COLOR_OUTLINE_SELECTED : COLOR_OUTLINE_NORMAL,
            outlineWidth: isSelected ? 3 : 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: nodeId,
            font: '10px "JetBrains Mono", monospace',
            style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            pixelOffset: new Cesium.Cartesian2(0, -14),
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: {
            nodeId,
            climateType: 'sensor_node',
          },
        });
        entityMap.set(nodeId, entity);
      } else {
        // Update existing entity in place (prevents flickering or duplicate objects)
        if (entity.position && typeof entity.position.setValue === 'function') {
          entity.position.setValue(targetPosition);
        } else {
          entity.position = targetPosition;
        }

        if (entity.point) {
          entity.point.pixelSize = isSelected ? 18 : 12;
          if (markerColor) entity.point.color = markerColor;
          entity.point.outlineColor = isSelected ? COLOR_OUTLINE_SELECTED : COLOR_OUTLINE_NORMAL;
          entity.point.outlineWidth = isSelected ? 3 : 2;
        }
      }
    }

    // Remove any entities that are no longer in authoritative state
    for (const [nodeId, entity] of entityMap.entries()) {
      if (!currentIds.has(nodeId)) {
        dataSource.entities.remove(entity);
        entityMap.delete(nodeId);
      }
    }

    // Request governor render pass
    try {
      governorRequestRender('climate-nodes-update');
    } catch (_) {}
  }

  /**
   * Initializes the layer, registers pick owner, and sets up interaction handlers.
   */
  function init() {
    if (isDestroyed) return;

    // Create and add CustomDataSource to viewer
    dataSource = new Cesium.CustomDataSource(CLIMATE_NODES_DATA_SOURCE_NAME);
    viewer.dataSources.add(dataSource);

    // Register with GEV pick ownership registry to prevent conflicts with other layers
    registerPickOwner(CLIMATE_NODES_LAYER_ID, (pickedId) => {
      return typeof pickedId === 'string' && pickedId.startsWith(CLIMATE_NODE_ENTITY_PREFIX);
    });

    // Screen-space click handler for node selection on canvas
    if (viewer.scene?.canvas && Cesium.ScreenSpaceEventHandler) {
      clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      clickHandler.setInputAction((movement) => {
        if (!movement?.position || !viewer.scene) return;
        const picked = viewer.scene.pick(movement.position);
        const pickId = resolvePickId(picked);

        if (pickId && pickId.startsWith(CLIMATE_NODE_ENTITY_PREFIX)) {
          const nodeId = pickId.slice(CLIMATE_NODE_ENTITY_PREFIX.length);
          if (typeof store.selectNode === 'function') {
            store.selectNode(nodeId);
          } else {
            store.dispatch({
              type: 'NODE_SELECTED',
              payload: { nodeId },
            });
          }
          try {
            governorRequestRender('climate-node-picked');
          } catch (_) {}
        }
      }, Cesium.ScreenSpaceEventType?.LEFT_CLICK ?? 0);
    }

    // Subscribe to state store changes
    storeUnsubscribe = store.subscribe(() => {
      syncEntitiesFromState();
    });

    // Initial sync
    syncEntitiesFromState();
  }

  /**
   * Programmatically selects a node or clears selection.
   *
   * @param {string|null} nodeId
   */
  function selectNode(nodeId) {
    if (typeof store.selectNode === 'function') {
      store.selectNode(nodeId);
    }
  }

  /**
   * Completely destroys and cleans up the layer.
   */
  function destroy() {
    if (isDestroyed) return;
    isDestroyed = true;

    // Unsubscribe from store
    if (typeof storeUnsubscribe === 'function') {
      storeUnsubscribe();
      storeUnsubscribe = null;
    }

    // Remove ScreenSpaceEventHandler
    if (clickHandler) {
      clickHandler.destroy();
      clickHandler = null;
    }

    // Unregister pick ownership
    unregisterPickOwner(CLIMATE_NODES_LAYER_ID);

    // Remove dataSource and entities
    if (dataSource && viewer.dataSources) {
      try {
        dataSource.entities.removeAll();
        viewer.dataSources.remove(dataSource, true);
      } catch (_) {}
      dataSource = null;
    }

    entityMap.clear();

    try {
      governorRequestRender('climate-nodes-destroyed');
    } catch (_) {}
  }

  function setVisible(visible) {
    if (dataSource) {
      dataSource.show = Boolean(visible);
      try {
        governorRequestRender('climate-nodes-visibility');
      } catch (_) {}
    }
  }

  return {
    init,
    update: syncEntitiesFromState,
    selectNode,
    setVisible,
    destroy,
    getDataSource: () => dataSource,
    getEntityMap: () => entityMap,
  };
}

/**
 * Initializes or returns the singleton Climate Eye nodes layer.
 *
 * @param {object} options
 * @param {object} options.viewer - Cesium Viewer.
 * @param {object} options.store - Climate Eye store.
 * @param {object} [options.Cesium]
 * @returns {object} Layer instance.
 */
export function initNodesLayer(options = {}) {
  if (activeNodesLayer) {
    return activeNodesLayer;
  }

  activeNodesLayer = createNodesLayer(options);
  activeNodesLayer.init();
  return activeNodesLayer;
}

/**
 * Returns the currently active nodes layer, if any.
 *
 * @returns {object|null}
 */
export function getNodesLayer() {
  return activeNodesLayer;
}

/**
 * Destroys the active nodes layer.
 */
export function destroyNodesLayer() {
  if (activeNodesLayer) {
    activeNodesLayer.destroy();
    activeNodesLayer = null;
  }
}
