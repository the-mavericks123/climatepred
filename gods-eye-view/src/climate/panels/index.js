/**
 * Climate Eye — Panels Module Entry Point
 *
 * Exposes the modular Climate Eye UI layer (F4.1).
 *
 * Browser-safe: No Node.js core modules.
 */

import { createClimateStore } from '../state/index.js';
import { syncClimateStateFromRest } from '../api/index.js';
import { startRealtimeBridge, stopRealtimeBridge } from '../realtime/index.js';
import {
  initNodesLayer,
  destroyNodesLayer,
  initClimateLayers,
  destroyClimateLayers,
  getClimateLayers,
} from '../layers/index.js';
import { mountClimateShell, ensureClimateStyles } from './shell.js';

export { mountClimateShell, ensureClimateStyles } from './shell.js';
export { createTopNav } from './topNav.js';
export { createLeftPanel } from './leftPanel.js';
export { createSensorMeshPanel } from './sensorMeshPanel.js';
export { createRightPanel, resolveSubsystemStatus } from './rightPanel.js';
export { createStatusBar, computeNodeFreshnessSummary } from './statusBar.js';
export {
  initNodesLayer,
  destroyNodesLayer,
  initClimateLayers,
  destroyClimateLayers,
  getClimateLayers,
} from '../layers/index.js';

let activeShell = null;
let sharedStore = null;

/**
 * Returns or creates a singleton Climate Eye state store for UI components.
 *
 * @returns {object} Authoritative store instance.
 */
export function getSharedClimateStore() {
  if (!sharedStore) {
    sharedStore = createClimateStore();
  }
  return sharedStore;
}

/**
 * Sets or resets the shared Climate Eye store instance.
 * Useful in testing or when orchestrating with an external store.
 *
 * @param {object|null} store
 */
export function setSharedClimateStore(store) {
  sharedStore = store;
}

/**
 * Initializes and mounts the Climate Eye command-center shell.
 *
 * @param {object} [options]
 * @param {HTMLElement} [options.container]
 * @param {object} [options.store]
 * @param {object} [options.client] - REST client override.
 * @param {boolean} [options.syncRest=true]
 * @param {boolean} [options.connectRealtime=true]
 * @param {object} [options.realtimeClient] - Realtime client override.
 * @param {object} [options.realtimeOptions] - Options for realtime client.
 * @param {typeof WebSocket} [options.WebSocketClass]
 * @returns {object} Mounted shell instance.
 */
export function initClimateShell(options = {}) {
  if (activeShell) {
    return activeShell;
  }

  const store = options.store || getSharedClimateStore();
  if (typeof window !== 'undefined') {
    window.__climateStore = store;
    window.__syncClimateState = () => syncClimateStateFromRest({
      store,
      client: options.client,
      syncIntelligence: options.syncIntelligence !== false,
    });
  }

  const container = options.container || (typeof document !== 'undefined' ? document.getElementById('cesiumContainer') || document.body : null);
  activeShell = mountClimateShell(container, { store, ...options });

  // In F4.2 & S1-S2 Integration: trigger initial REST state & intelligence synchronization
  if (options.syncRest !== false) {
    const doSync = () => syncClimateStateFromRest({
      store,
      client: options.client,
      syncIntelligence: options.syncIntelligence !== false,
      fetchTelemetry: true,
    });

    doSync().catch((err) => {
      console.warn('[ClimateEye] Initial REST sync warning:', err);
    });

    const syncInterval = setInterval(() => {
      doSync().catch(() => {});
    }, 10000);
    if (typeof syncInterval?.unref === 'function') syncInterval.unref();
  }

  // In F4.3: connect realtime WebSocket stream (separate responsibility from REST sync)
  if (
    options.connectRealtime !== false &&
    (typeof globalThis.WebSocket === 'function' || options.WebSocketClass || options.realtimeClient)
  ) {
    try {
      startRealtimeBridge({
        store,
        client: options.realtimeClient,
        clientOptions: options.realtimeOptions,
        WebSocketClass: options.WebSocketClass,
      });
    } catch (err) {
      console.warn('[ClimateEye] Realtime bridge start warning:', err);
    }
  }

  // In F4.4 & F4.5: initialize Cesium visualization layers if viewer is available
  const viewer = options.viewer || (typeof window !== 'undefined' ? window.__godsEyeView?.viewer : null);
  const dataManager = options.dataManager || (typeof window !== 'undefined' ? window.__godsEyeView?.dataManager : null);
  if (viewer && options.initNodesLayer !== false && options.initClimateLayers !== false) {
    try {
      initClimateLayers({
        viewer,
        store,
        dataManager,
        Cesium: options.Cesium,
      });
    } catch (err) {
      console.warn('[ClimateEye] Climate layers initialization warning:', err);
    }
  }

  return activeShell;
}

/**
 * Returns the currently mounted shell instance, if any.
 *
 * @returns {object|null}
 */
export function getClimateShell() {
  return activeShell;
}

/**
 * Destroys the active Climate Eye shell instance and unmounts DOM nodes.
 */
export function destroyClimateShell() {
  if (activeShell) {
    activeShell.destroy();
    activeShell = null;
  }
  stopRealtimeBridge();
  destroyClimateLayers();
  destroyNodesLayer();
}
