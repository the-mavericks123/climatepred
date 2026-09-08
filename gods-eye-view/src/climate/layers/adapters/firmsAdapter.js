/**
 * Climate Eye — NASA FIRMS Thermal Anomalies Adapter (Step F4.5)
 *
 * Provides a clean adapter boundary wrapping the existing GEV `local-firms` layer.
 * Strictly preserves source data without calculating or inferring wildfire risk.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_LAYERS } from '../../state/constants.js';
import { getLayerLegend } from '../legends.js';

export const GEV_FIRMS_LAYER_ID = 'local-firms';

/**
 * Creates an adapter for NASA FIRMS data via GEV DataManager.
 *
 * @param {object} [options]
 * @param {object} [options.dataManager] - GEV DataLayerManager instance
 * @param {object} [options.viewer] - Cesium viewer instance
 * @returns {object} Adapter interface
 */
export function createFirmsAdapter({ dataManager = null, viewer = null } = {}) {
  let dm = dataManager;
  let isDestroyed = false;

  function resolveDataManager() {
    if (dm) return dm;
    if (typeof window !== 'undefined' && window.__godsEyeView?.dataManager) {
      dm = window.__godsEyeView.dataManager;
    }
    return dm;
  }

  return {
    id: CLIMATE_LAYERS.FIRES,
    gevLayerId: GEV_FIRMS_LAYER_ID,
    legend: getLayerLegend(CLIMATE_LAYERS.FIRES),

    async setVisible(visible) {
      if (isDestroyed) return false;
      const manager = resolveDataManager();
      if (!manager) return false;

      const currentlyEnabled = Boolean(manager.isEnabled(GEV_FIRMS_LAYER_ID));
      const targetVisible = Boolean(visible);

      if (currentlyEnabled !== targetVisible) {
        if (typeof manager.setEnabled === 'function') {
          return await manager.setEnabled(GEV_FIRMS_LAYER_ID, targetVisible, { origin: 'user' });
        } else if (typeof manager.toggle === 'function') {
          return await manager.toggle(GEV_FIRMS_LAYER_ID, { origin: 'user' });
        }
      }
      return targetVisible;
    },

    isVisible() {
      if (isDestroyed) return false;
      const manager = resolveDataManager();
      return Boolean(manager && manager.isEnabled(GEV_FIRMS_LAYER_ID));
    },

    getStats() {
      const manager = resolveDataManager();
      if (!manager) return null;
      const entry = manager.layers?.get?.(GEV_FIRMS_LAYER_ID);
      return entry?.module?.getStats?.() || null;
    },

    destroy() {
      isDestroyed = true;
      dm = null;
    },
  };
}
