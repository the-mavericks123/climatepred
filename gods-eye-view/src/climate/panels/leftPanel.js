/**
 * Climate Eye — Left Climate Panel Component
 *
 * Displays:
 * 1. Climate Layers list (9 real measurement layers + legends)
 * 2. Sensor Mesh status
 * 3. Metric Channels:
 *    - Temperature / Heat
 *    - Rain / Flood
 *    - Soil / Drought
 *    - Air Quality
 *
 * Strict Requirement:
 * Never calculates climate risk or fabricates telemetry.
 * Displays explicit UNAVAILABLE status badges whenever live data is absent.
 * Zero (0) is strictly preserved as a valid measurement.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_LAYERS, CLIMATE_MODES } from '../state/constants.js';
import { LAYER_LEGENDS } from '../layers/legends.js';

export const DISPLAY_LAYERS = Object.freeze([
  { id: CLIMATE_LAYERS.SENSOR_MESH, label: 'Sensor Mesh Nodes' },
  { id: CLIMATE_LAYERS.TEMPERATURE, label: 'Ambient Temperature' },
  { id: CLIMATE_LAYERS.RAINFALL, label: 'Precipitation Rate' },
  { id: CLIMATE_LAYERS.SOIL_MOISTURE, label: 'Soil Moisture' },
  { id: CLIMATE_LAYERS.AIR_QUALITY, label: 'Air Quality (AQI)' },
  { id: CLIMATE_LAYERS.WATER_LEVEL, label: 'Water Level' },
  { id: CLIMATE_LAYERS.FIRES, label: 'Thermal Anomalies (FIRMS)' },
  { id: CLIMATE_LAYERS.DAMS, label: 'Dams & Reservoirs (USACE)' },
  { id: CLIMATE_LAYERS.EARTHQUAKES, label: 'Seismic Activity (USGS)' },
]);

/**
 * Creates the left climate panel component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void }}
 */
export function createLeftPanel(store) {
  const container = document.createElement('aside');
  container.id = 'climate-left-panel';
  container.className = 'ce-panel';
  container.setAttribute('aria-label', 'Climate Observation and Sensors');

  const layersHtml = DISPLAY_LAYERS.map((layer) => `
    <div class="ce-layer-item">
      <div class="ce-layer-info">
        <span class="ce-layer-dot" data-layer-dot="${layer.id}" aria-hidden="true"></span>
        <span>${layer.label}</span>
      </div>
      <button type="button" class="ce-layer-toggle-btn" data-layer="${layer.id}" aria-label="Toggle ${layer.label} Layer" aria-pressed="false">OFF</button>
    </div>
  `).join('');

  container.innerHTML = `
    <!-- 1. CLIMATE LAYERS -->
    <section class="ce-card" id="ce-card-layers">
      <div class="ce-section-header">
        <span class="ce-section-title">CLIMATE LAYERS</span>
        <span class="ce-section-badge" id="ce-active-layers-badge">0 ACTIVE</span>
      </div>
      <div class="ce-layer-list">
        ${layersHtml}
      </div>
      <div class="ce-layer-legend-panel" id="ce-layer-legend-panel">
        <div class="ce-legend-header">ACTIVE LAYER LEGENDS</div>
        <div class="ce-legend-items" id="ce-legend-items"></div>
        <div class="ce-legend-notice">Raw measurement layers only. No risk scores or hazard inferences applied.</div>
      </div>
    </section>

    <!-- 2. SENSORS -->
    <section class="ce-card" id="ce-card-sensors">
      <div class="ce-section-header">
        <span class="ce-section-title">SENSOR MESH</span>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span class="ce-section-badge" id="ce-sensor-count-badge">0 NODES</span>
          <button type="button" class="ce-section-badge ce-mesh-link-btn" id="ce-open-mesh-btn" title="Focus Sensor Mesh Panel">VIEW ALL</button>
        </div>
      </div>
      <div class="ce-metric-grid">
        <div class="ce-metric-card">
          <span class="ce-metric-label">CONNECTED NODES</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-nodes-connected-val">0</span>
            <span class="ce-unavailable-badge" id="ce-nodes-status-badge">NO MESH</span>
          </div>
        </div>
        <div class="ce-metric-card">
          <span class="ce-metric-label">STREAM RATE</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-stream-rate-val">0</span>
            <span class="ce-section-badge">EPS</span>
          </div>
        </div>
      </div>
      <p class="ce-channel-footnote">Awaiting MQTT edge sensor ingestion</p>
    </section>

    <!-- 3. METRIC CHANNELS -->
    <section class="ce-card" id="ce-card-metrics">
      <div class="ce-section-header">
        <span class="ce-section-title">METRIC CHANNELS</span>
        <span class="ce-section-badge">STREAM CHANNELS</span>
      </div>
      <div class="ce-metric-grid">
        <!-- Temperature / Heat -->
        <div class="ce-metric-card" id="ce-metric-temp-card">
          <span class="ce-metric-label">TEMPERATURE / HEAT</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-temp-value">--</span>
            <span class="ce-unavailable-badge" id="ce-temp-badge">UNAVAILABLE</span>
          </div>
        </div>

        <!-- Rain / Flood -->
        <div class="ce-metric-card" id="ce-metric-rain-card">
          <span class="ce-metric-label">RAIN / FLOOD</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-rain-value">--</span>
            <span class="ce-unavailable-badge" id="ce-rain-badge">UNAVAILABLE</span>
          </div>
        </div>

        <!-- Soil / Drought -->
        <div class="ce-metric-card" id="ce-metric-soil-card">
          <span class="ce-metric-label">SOIL / DROUGHT</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-soil-value">--</span>
            <span class="ce-unavailable-badge" id="ce-soil-badge">UNAVAILABLE</span>
          </div>
        </div>

        <!-- Air Quality -->
        <div class="ce-metric-card" id="ce-metric-aqi-card">
          <span class="ce-metric-label">AIR QUALITY</span>
          <div class="ce-metric-value-row">
            <span class="ce-metric-value" id="ce-aqi-value">--</span>
            <span class="ce-unavailable-badge" id="ce-aqi-badge">UNAVAILABLE</span>
          </div>
        </div>
      </div>
      <p class="ce-channel-footnote" id="ce-channel-footnote">Realtime channels display UNAVAILABLE until valid telemetry stream is received.</p>
    </section>
  `;

  const nodeCountBadge = container.querySelector('#ce-sensor-count-badge');
  const nodeCountVal = container.querySelector('#ce-nodes-connected-val');
  const nodeStatusBadge = container.querySelector('#ce-nodes-status-badge');
  const channelFootnote = container.querySelector('#ce-channel-footnote');

  const tempVal = container.querySelector('#ce-temp-value');
  const tempBadge = container.querySelector('#ce-temp-badge');
  const rainVal = container.querySelector('#ce-rain-value');
  const rainBadge = container.querySelector('#ce-rain-badge');
  const soilVal = container.querySelector('#ce-soil-value');
  const soilBadge = container.querySelector('#ce-soil-badge');
  const aqiVal = container.querySelector('#ce-aqi-value');
  const aqiBadge = container.querySelector('#ce-aqi-badge');

  const activeLayersBadge = container.querySelector('#ce-active-layers-badge');
  const legendItemsContainer = container.querySelector('#ce-legend-items');

  function updateFromState(state) {
    if (!state) return;

    // 1. Synchronize Layer Toggles and Legends
    const layers = state.layers || {};
    let activeLayerCount = 0;
    const activeLegendFragments = [];

    for (const layer of DISPLAY_LAYERS) {
      const isVisible = Boolean(layers[layer.id]);
      if (isVisible) activeLayerCount++;

      const btn = container.querySelector(`button[data-layer="${layer.id}"]`);
      const dot = container.querySelector(`span[data-layer-dot="${layer.id}"]`);

      if (btn) {
        btn.classList.toggle('active', isVisible);
        btn.textContent = isVisible ? 'ACTIVE' : 'OFF';
        btn.setAttribute('aria-pressed', String(isVisible));
      }
      if (dot) {
        dot.classList.toggle('active', isVisible);
      }

      if (isVisible) {
        const meta = LAYER_LEGENDS[layer.id];
        if (meta) {
          activeLegendFragments.push(`
            <div class="ce-legend-item">
              <span>${meta.title}</span>
              <span class="ce-legend-unit">${meta.unit}</span>
            </div>
          `);
        }
      }
    }

    if (activeLayersBadge) {
      activeLayersBadge.textContent = `${activeLayerCount} ACTIVE`;
    }

    if (legendItemsContainer) {
      legendItemsContainer.innerHTML = activeLegendFragments.length > 0
        ? activeLegendFragments.join('')
        : '<div class="ce-legend-item"><span>No layers active</span><span class="ce-legend-unit">--</span></div>';
    }

    // 2. Sensor Mesh Count and Status
    const nodeCount = state.nodes?.allIds?.length || 0;
    if (nodeCountBadge) nodeCountBadge.textContent = `${nodeCount} NODES`;
    if (nodeCountVal) nodeCountVal.textContent = String(nodeCount);
    if (nodeStatusBadge) {
      if (nodeCount > 0) {
        nodeStatusBadge.textContent = 'ONLINE';
        nodeStatusBadge.classList.remove('ce-unavailable-badge');
        nodeStatusBadge.style.color = 'var(--ce-emerald)';
      } else {
        nodeStatusBadge.textContent = 'NO MESH';
        nodeStatusBadge.classList.add('ce-unavailable-badge');
        nodeStatusBadge.style.color = '';
      }
    }

    // Resolve active reading (selected node or first node with telemetry)
    let activeReading = null;
    if (state.ui?.selectedNodeId && state.telemetry?.byNodeId?.[state.ui.selectedNodeId]) {
      activeReading = state.telemetry.byNodeId[state.ui.selectedNodeId];
    } else if (state.nodes?.allIds && state.telemetry?.byNodeId) {
      for (const id of state.nodes.allIds) {
        if (state.telemetry.byNodeId[id]) {
          activeReading = state.telemetry.byNodeId[id];
          break;
        }
      }
    }

    // Temperature / Heat
    if (tempVal && tempBadge) {
      if (activeReading && activeReading.temperature !== null && activeReading.temperature !== undefined) {
        tempVal.textContent = `${activeReading.temperature} °C`;
        tempBadge.textContent = 'TELEMETRY';
        tempBadge.classList.remove('ce-unavailable-badge');
        tempBadge.classList.add('ce-section-badge');
      } else {
        tempVal.textContent = '--';
        tempBadge.textContent = 'UNAVAILABLE';
        tempBadge.classList.add('ce-unavailable-badge');
        tempBadge.classList.remove('ce-section-badge');
      }
    }

    // Rain / Flood (preserves numeric zero 0)
    if (rainVal && rainBadge) {
      if (activeReading && activeReading.rainfall !== null && activeReading.rainfall !== undefined) {
        rainVal.textContent = `${activeReading.rainfall} mm/h`;
        rainBadge.textContent = 'TELEMETRY';
        rainBadge.classList.remove('ce-unavailable-badge');
        rainBadge.classList.add('ce-section-badge');
      } else {
        rainVal.textContent = '--';
        rainBadge.textContent = 'UNAVAILABLE';
        rainBadge.classList.add('ce-unavailable-badge');
        rainBadge.classList.remove('ce-section-badge');
      }
    }

    // Soil / Drought (preserves numeric zero 0)
    if (soilVal && soilBadge) {
      if (activeReading && activeReading.soil_moisture !== null && activeReading.soil_moisture !== undefined) {
        soilVal.textContent = `${activeReading.soil_moisture} %`;
        soilBadge.textContent = 'TELEMETRY';
        soilBadge.classList.remove('ce-unavailable-badge');
        soilBadge.classList.add('ce-section-badge');
      } else {
        soilVal.textContent = '--';
        soilBadge.textContent = 'UNAVAILABLE';
        soilBadge.classList.add('ce-unavailable-badge');
        soilBadge.classList.remove('ce-section-badge');
      }
    }

    // Air Quality (preserves numeric zero 0)
    if (aqiVal && aqiBadge) {
      if (activeReading && activeReading.air_quality !== null && activeReading.air_quality !== undefined) {
        aqiVal.textContent = `${activeReading.air_quality} AQI`;
        aqiBadge.textContent = 'TELEMETRY';
        aqiBadge.classList.remove('ce-unavailable-badge');
        aqiBadge.classList.add('ce-section-badge');
      } else {
        aqiVal.textContent = '--';
        aqiBadge.textContent = 'UNAVAILABLE';
        aqiBadge.classList.add('ce-unavailable-badge');
        aqiBadge.classList.remove('ce-section-badge');
      }
    }

    // Channel footnote timestamp
    if (channelFootnote) {
      if (activeReading && activeReading.timestamp) {
        channelFootnote.textContent = `LAST TELEMETRY: ${activeReading.timestamp}`;
      } else if (state.connection?.lastTimestamp) {
        channelFootnote.textContent = `LAST TELEMETRY: ${state.connection.lastTimestamp}`;
      } else {
        channelFootnote.textContent = 'Realtime channels display UNAVAILABLE until valid telemetry stream is received.';
      }
    }
  }

  // Interactive layer toggle buttons bound to store
  const layerButtons = container.querySelectorAll('.ce-layer-toggle-btn');
  layerButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const layerId = btn.dataset.layer;
      if (!layerId) return;

      if (typeof store.toggleLayer === 'function') {
        store.toggleLayer(layerId);
      } else if (typeof store.dispatch === 'function') {
        const current = Boolean(store.getState()?.layers?.[layerId]);
        store.dispatch({
          type: 'LAYER_VISIBILITY_CHANGED',
          payload: { layerId, visible: !current },
        });
      }
    });
  });

  const openMeshBtn = container.querySelector('#ce-open-mesh-btn');
  openMeshBtn?.addEventListener('click', () => {
    if (typeof store.setUiMode === 'function') {
      store.setUiMode(CLIMATE_MODES.SENSOR_MESH);
    } else if (typeof store.dispatch === 'function') {
      store.dispatch({
        type: 'UI_MODE_CHANGED',
        payload: { mode: CLIMATE_MODES.SENSOR_MESH },
      });
    }
  });

  // Sync initial state
  if (store && typeof store.getState === 'function') {
    updateFromState(store.getState());
  }

  // Subscribe to store
  let unsubscribe = null;
  if (store && typeof store.subscribe === 'function') {
    unsubscribe = store.subscribe((state) => {
      updateFromState(state);
    });
  }

  return {
    element: container,
    destroy: () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    },
  };
}
