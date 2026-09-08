/**
 * Climate Eye — Sensor Mesh Panel Component (Step F4.6)
 *
 * Dedicated command-center panel displaying all dynamically known sensor nodes
 * from the authoritative Climate Eye state store:
 * - Dynamic rendering for NODE-001 through future NODE-006+ (no hardcoded IDs)
 * - Exact value preservation: 0 is preserved as a valid measurement, null as "--"
 * - Exact backend timestamp preservation
 * - Realtime freshness states: LIVE/AVAILABLE, STALE, UNAVAILABLE
 * - Summary counts derived purely from authoritative state
 * - Newest telemetry indicator
 * - Two-way selection synchronization with the Cesium globe node layer
 * - Full keyboard accessibility and clean lifecycle
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_MODES, REALTIME_STATES } from '../state/constants.js';

/**
 * Formats a measurement strictly preserving 0 and null.
 *
 * @param {number|null|undefined} value
 * @param {string} unit
 * @param {number} [decimals=1]
 * @returns {string}
 */
export function formatNodeMetric(value, unit, decimals = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return `-- ${unit}`.trim();
  }
  const num = Number(value);
  return `${num.toFixed(decimals)} ${unit}`.trim();
}

/**
 * Calculates freshness state for a given node.
 *
 * @param {object} [node]
 * @param {object} [telemetry]
 * @param {string} [rtState]
 * @returns {'AVAILABLE'|'STALE'|'UNAVAILABLE'}
 */
export function getNodeFreshness(node, telemetry, rtState) {
  if (rtState === REALTIME_STATES.UNAVAILABLE || node?.status === 'offline') {
    return 'UNAVAILABLE';
  }
  if (rtState === REALTIME_STATES.STALE || node?.status === 'stale') {
    return 'STALE';
  }
  if (rtState === REALTIME_STATES.LIVE || (telemetry && telemetry.timestamp)) {
    return 'AVAILABLE';
  }
  return 'STALE';
}

/**
 * Formats relative time from an ISO timestamp.
 *
 * @param {string|null} timestamp
 * @param {number} [nowMs]
 * @returns {string}
 */
export function formatTimeAgo(timestamp, nowMs = Date.now()) {
  if (!timestamp) return 'NEVER';
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) return String(timestamp);

  const diffSec = Math.max(0, Math.floor((nowMs - then) / 1000));
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  return `${diffHours}h ago`;
}

/**
 * Creates the Sensor Mesh Panel component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, update: () => void, destroy: () => void }}
 */
export function createSensorMeshPanel(store) {
  const container = document.createElement('aside');
  container.id = 'climate-sensor-mesh-panel';
  container.className = 'ce-panel';
  container.setAttribute('aria-label', 'Sensor Mesh Network');

  container.innerHTML = `
    <!-- 1. HEADER & ACTIONS -->
    <div class="ce-mesh-header">
      <div class="ce-section-header" style="margin-bottom: 0; width: 100%;">
        <span class="ce-section-title">
          <span class="ce-pill-dot" style="background: var(--ce-emerald);"></span>
          SENSOR MESH
        </span>
        <div class="ce-mesh-actions">
          <button
            type="button"
            class="ce-mesh-deselect-btn hidden"
            id="ce-mesh-deselect-btn"
            title="Deselect Node"
            aria-label="Deselect active node"
          >
            DESELECT
          </button>
          <span class="ce-section-badge" id="ce-mesh-mode-indicator">LIVE</span>
        </div>
      </div>
    </div>

    <!-- 2. SUMMARY COUNTS -->
    <section class="ce-card" id="ce-mesh-summary-card">
      <div class="ce-mesh-summary-grid" id="ce-mesh-summary-grid">
        <div class="ce-mesh-stat">
          <span class="ce-mesh-stat-val" id="ce-mesh-total-val">0</span>
          <span class="ce-mesh-stat-lbl">TOTAL</span>
        </div>
        <div class="ce-mesh-stat">
          <span class="ce-mesh-stat-val" style="color: var(--ce-emerald);" id="ce-mesh-available-val">0</span>
          <span class="ce-mesh-stat-lbl">AVAILABLE</span>
        </div>
        <div class="ce-mesh-stat">
          <span class="ce-mesh-stat-val" style="color: var(--ce-amber);" id="ce-mesh-stale-val">0</span>
          <span class="ce-mesh-stat-lbl">STALE</span>
        </div>
        <div class="ce-mesh-stat">
          <span class="ce-mesh-stat-val" style="color: var(--ce-text-muted);" id="ce-mesh-unavailable-val">0</span>
          <span class="ce-mesh-stat-lbl">OFFLINE</span>
        </div>
      </div>
      <div class="ce-mesh-telemetry-status">
        <span class="ce-mesh-latest-lbl">LAST TELEMETRY:</span>
        <strong class="ce-mesh-latest-val" id="ce-mesh-latest-telemetry-val">UNAVAILABLE</strong>
      </div>
    </section>

    <!-- 3. DYNAMIC NODE LIST -->
    <section class="ce-card" id="ce-mesh-list-card">
      <div class="ce-section-header">
        <span class="ce-section-title" style="font-size: 10px;">CONNECTED HARDWARE</span>
        <span class="ce-section-badge" id="ce-mesh-node-count-badge">0 NODES</span>
      </div>
      <div class="ce-mesh-node-list" id="ce-mesh-node-list" role="list">
        <!-- Dynamically rendered rows -->
      </div>
    </section>
  `;

  // DOM Elements
  const deselectBtn = container.querySelector('#ce-mesh-deselect-btn');
  const modeIndicator = container.querySelector('#ce-mesh-mode-indicator');
  const totalVal = container.querySelector('#ce-mesh-total-val');
  const availableVal = container.querySelector('#ce-mesh-available-val');
  const staleVal = container.querySelector('#ce-mesh-stale-val');
  const unavailableVal = container.querySelector('#ce-mesh-unavailable-val');
  const latestTelemetryVal = container.querySelector('#ce-mesh-latest-telemetry-val');
  const nodeCountBadge = container.querySelector('#ce-mesh-node-count-badge');
  const nodeListContainer = container.querySelector('#ce-mesh-node-list');

  // Wire deselect button
  deselectBtn?.addEventListener('click', () => {
    if (typeof store.selectNode === 'function') {
      store.selectNode(null);
    } else {
      store.dispatch({
        type: 'NODE_SELECTED',
        payload: { nodeId: null },
      });
    }
  });

  /**
   * Updates the panel from state.
   *
   * @param {object} state
   */
  function updateFromState(state) {
    if (!state) return;

    const allNodeIds = state.nodes?.allIds || [];
    const nodesById = state.nodes?.byId || {};
    const telemetryByNode = state.telemetry?.byNodeId || {};
    const selectedNodeId = state.ui?.selectedNodeId || null;
    const currentMode = state.ui?.mode || CLIMATE_MODES.LIVE;
    const rtState = state.connection?.realtimeState || REALTIME_STATES.UNAVAILABLE;

    // 1. Deselect button visibility
    if (deselectBtn) {
      if (selectedNodeId) {
        deselectBtn.classList.remove('hidden');
      } else {
        deselectBtn.classList.add('hidden');
      }
    }

    // 2. Mode indicator
    if (modeIndicator) {
      modeIndicator.textContent = currentMode;
    }

    // 3. Panel visibility / mode styling
    const isMeshMode = currentMode === CLIMATE_MODES.SENSOR_MESH;
    container.classList.toggle('ce-mesh-mode-active', isMeshMode);

    // 4. Derive summary counts
    let countAvailable = 0;
    let countStale = 0;
    let countUnavailable = 0;
    let newestTimestampMs = null;
    let newestTimestampStr = null;

    for (const nodeId of allNodeIds) {
      const node = nodesById[nodeId];
      const telemetry = telemetryByNode[nodeId];
      const freshness = getNodeFreshness(node, telemetry, rtState);

      if (freshness === 'AVAILABLE') countAvailable++;
      else if (freshness === 'STALE') countStale++;
      else countUnavailable++;

      const ts = telemetry?.timestamp || node?.lastSeen;
      if (ts) {
        const timeMs = new Date(ts).getTime();
        if (Number.isFinite(timeMs) && (newestTimestampMs === null || timeMs > newestTimestampMs)) {
          newestTimestampMs = timeMs;
          newestTimestampStr = ts;
        }
      }
    }

    if (totalVal) totalVal.textContent = String(allNodeIds.length);
    if (availableVal) availableVal.textContent = String(countAvailable);
    if (staleVal) staleVal.textContent = String(countStale);
    if (unavailableVal) unavailableVal.textContent = String(countUnavailable);
    if (nodeCountBadge) nodeCountBadge.textContent = `${allNodeIds.length} NODES`;

    if (latestTelemetryVal) {
      if (newestTimestampStr) {
        latestTelemetryVal.textContent = formatTimeAgo(newestTimestampStr);
        latestTelemetryVal.title = newestTimestampStr;
      } else {
        latestTelemetryVal.textContent = 'UNAVAILABLE';
        latestTelemetryVal.title = '';
      }
    }

    // 5. Render Node List
    if (!nodeListContainer) return;

    if (allNodeIds.length === 0) {
      nodeListContainer.innerHTML = `
        <div class="ce-mesh-empty-state">
          <div class="ce-mesh-empty-icon">⛯</div>
          <p class="ce-mesh-empty-text">NO SENSOR NODES DETECTED</p>
          <span class="ce-mesh-empty-sub">Awaiting edge sensor telemetry ingestion</span>
        </div>
      `;
      return;
    }

    // Render nodes dynamically
    const rowsHtml = allNodeIds.map((nodeId) => {
      const node = nodesById[nodeId] || {};
      const telemetry = telemetryByNode[nodeId] || null;
      const isSelected = selectedNodeId === nodeId;
      const freshness = getNodeFreshness(node, telemetry, rtState);

      let dotColor = 'var(--ce-text-muted)';
      if (freshness === 'AVAILABLE') dotColor = 'var(--ce-emerald)';
      else if (freshness === 'STALE') dotColor = 'var(--ce-amber)';

      const tempStr = telemetry ? formatNodeMetric(telemetry.temperature, '°C', 1) : '--';
      const rainStr = telemetry ? formatNodeMetric(telemetry.rainfall, 'mm/h', 1) : '--';
      const humidityStr = telemetry ? formatNodeMetric(telemetry.humidity, '%', 0) : null;
      const soilStr = telemetry ? formatNodeMetric(telemetry.soil_moisture, '%', 1) : null;
      const aqiStr = telemetry ? formatNodeMetric(telemetry.air_quality, 'AQI', 0) : null;
      const waterStr = telemetry ? formatNodeMetric(telemetry.water_level, 'm', 2) : null;
      const batteryStr = telemetry ? formatNodeMetric(telemetry.battery, 'V', 2) : null;

      const ts = telemetry?.timestamp || node?.lastSeen;
      const timeAgo = formatTimeAgo(ts);

      return `
        <div
          class="ce-mesh-node-row ${isSelected ? 'selected' : ''}"
          role="button"
          tabindex="0"
          data-node-id="${nodeId}"
          aria-label="Sensor Node ${nodeId} - ${freshness}"
          aria-pressed="${isSelected ? 'true' : 'false'}"
        >
          <div class="ce-mesh-node-header">
            <div class="ce-mesh-node-title">
              <span class="ce-mesh-dot" style="background: ${dotColor};" aria-hidden="true"></span>
              <strong class="ce-mesh-id">${nodeId}</strong>
            </div>
            <span class="ce-mesh-badge ${freshness.toLowerCase()}">${freshness}</span>
          </div>

          <div class="ce-mesh-node-metrics">
            <div class="ce-mesh-metric-item">
              <span class="ce-mesh-metric-lbl">TEMP</span>
              <strong class="ce-mesh-metric-val">${tempStr}</strong>
            </div>
            <div class="ce-mesh-metric-item">
              <span class="ce-mesh-metric-lbl">RAIN</span>
              <strong class="ce-mesh-metric-val">${rainStr}</strong>
            </div>
            ${humidityStr ? `
              <div class="ce-mesh-metric-item">
                <span class="ce-mesh-metric-lbl">HUM</span>
                <span class="ce-mesh-metric-val">${humidityStr}</span>
              </div>
            ` : ''}
            ${soilStr ? `
              <div class="ce-mesh-metric-item">
                <span class="ce-mesh-metric-lbl">SOIL</span>
                <span class="ce-mesh-metric-val">${soilStr}</span>
              </div>
            ` : ''}
            ${aqiStr ? `
              <div class="ce-mesh-metric-item">
                <span class="ce-mesh-metric-lbl">AQI</span>
                <span class="ce-mesh-metric-val">${aqiStr}</span>
              </div>
            ` : ''}
            ${waterStr ? `
              <div class="ce-mesh-metric-item">
                <span class="ce-mesh-metric-lbl">WATER</span>
                <span class="ce-mesh-metric-val">${waterStr}</span>
              </div>
            ` : ''}
            ${batteryStr ? `
              <div class="ce-mesh-metric-item">
                <span class="ce-mesh-metric-lbl">BAT</span>
                <span class="ce-mesh-metric-val">${batteryStr}</span>
              </div>
            ` : ''}
          </div>

          <div class="ce-mesh-node-footer">
            <span class="ce-mesh-ts-label">LAST: ${timeAgo}</span>
            ${ts ? `<span class="ce-mesh-ts-exact" title="${ts}">${ts.slice(11, 19)}Z</span>` : ''}
          </div>
        </div>
      `;
    }).join('');

    nodeListContainer.innerHTML = rowsHtml;

    // Attach click and keyboard listeners to rows
    const rows = nodeListContainer.querySelectorAll('.ce-mesh-node-row');
    rows.forEach((row) => {
      const nodeId = row.dataset.nodeId;
      if (!nodeId) return;

      const handleSelectionToggle = () => {
        const currentSelectedId = store.getState?.()?.ui?.selectedNodeId ?? state.ui?.selectedNodeId;
        if (currentSelectedId === nodeId) {
          if (typeof store.selectNode === 'function') {
            store.selectNode(null);
          } else {
            store.dispatch({
              type: 'NODE_SELECTED',
              payload: { nodeId: null },
            });
          }
        } else {
          if (typeof store.selectNode === 'function') {
            store.selectNode(nodeId);
          } else {
            store.dispatch({
              type: 'NODE_SELECTED',
              payload: { nodeId },
            });
          }
        }
      };

      row.addEventListener('click', handleSelectionToggle);
      row.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          handleSelectionToggle();
        }
      });
    });
  }

  // Initial update
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
    update: () => {
      if (store && typeof store.getState === 'function') {
        updateFromState(store.getState());
      }
    },
    destroy: () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe();
        unsubscribe = null;
      }
      container.remove();
    },
  };
}
