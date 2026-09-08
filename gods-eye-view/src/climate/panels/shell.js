/**
 * Climate Eye — Command Center Shell Coordinator
 *
 * Coordinates the mounting of:
 * - Top Navigation
 * - Left Climate Panel
 * - Right Intelligence Panel
 * - Bottom Status Bar
 *
 * Maintains central transparency and non-blocking pointer events so the
 * underlying GEV Cesium globe remains fully interactive.
 *
 * Browser-safe: No Node.js core modules.
 */

import { createTopNav } from './topNav.js';
import { createLeftPanel } from './leftPanel.js';
import { createRightPanel } from './rightPanel.js';
import { createStatusBar } from './statusBar.js';
import { createSensorMeshPanel } from './sensorMeshPanel.js';
import { createBottomDrawer } from './bottomDrawer.js';
import { createRegionFocusCard } from './regionFocusCard.js';

const STYLE_ID = 'climate-eye-shell-css';
const CSS_HREF = '/src/climate/panels/climateShell.css';

/**
 * Injects the Climate Eye stylesheet if running in a browser environment
 * and not already present in document.head.
 */
export function ensureClimateStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;

  const link = document.createElement('link');
  link.id = STYLE_ID;
  link.rel = 'stylesheet';
  link.href = CSS_HREF;
  document.head.appendChild(link);
}

/**
 * Mounts the Climate Eye command-center shell into a host container.
 *
 * @param {HTMLElement} [container] - Host element (defaults to document.body).
 * @param {object} options
 * @param {object} options.store - Authoritative Climate Eye state store instance.
 * @returns {{ root: HTMLElement, destroy: () => void }}
 */
export function mountClimateShell(container = (typeof document !== 'undefined' ? document.body : null), options = {}) {
  if (!container) {
    throw new Error('mountClimateShell requires a valid container or browser document.body');
  }

  ensureClimateStyles();

  // Check if an existing shell root is present to avoid duplicates
  let root = container.querySelector('#climate-eye-root');
  if (!root) {
    root = document.createElement('div');
    root.id = 'climate-eye-root';
    container.appendChild(root);
  }

  const { store } = options;

  // Mount components
  const topNav = createTopNav(store);
  const leftPanel = createLeftPanel(store);
  const sensorMeshPanel = createSensorMeshPanel(store);
  const rightPanel = createRightPanel(store);
  const bottomDrawer = createBottomDrawer(store);
  const regionFocusCard = createRegionFocusCard(store, bottomDrawer);
  const statusBar = createStatusBar(store);

  root.appendChild(topNav.element);
  root.appendChild(leftPanel.element);
  root.appendChild(sensorMeshPanel.element);
  root.appendChild(regionFocusCard.element);
  root.appendChild(rightPanel.element);
  root.appendChild(bottomDrawer.element);
  root.appendChild(statusBar.element);

  return {
    root,
    components: {
      topNav,
      leftPanel,
      sensorMeshPanel,
      regionFocusCard,
      rightPanel,
      bottomDrawer,
      statusBar,
    },
    destroy: () => {
      topNav.destroy();
      leftPanel.destroy();
      sensorMeshPanel.destroy();
      regionFocusCard.destroy();
      rightPanel.destroy();
      bottomDrawer.destroy();
      statusBar.destroy();
      root.remove();
    },
  };
}
