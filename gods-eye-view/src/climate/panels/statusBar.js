/**
 * Climate Eye — Bottom Status Bar Component (F4.7)
 *
 * Displays operational system status:
 * 1. Realtime stream state (UNAVAILABLE / LIVE / STALE / SIMULATED)
 * 2. Node summary (TOTAL, LIVE/AVAILABLE, STALE, UNAVAILABLE)
 * 3. Latest real telemetry timestamp (or honest '-- (UNAVAILABLE)')
 * 4. Telemetry connection status (CONNECTED / DISCONNECTED)
 * 5. Backend/API health status (READY / STANDBY / DEGRADED / UNAVAILABLE)
 * 6. Live UTC clock
 *
 * Browser-safe: No Node.js core modules.
 */

import { REALTIME_STATES } from '../state/constants.js';

/**
 * Computes authoritative node freshness counts and the latest telemetry timestamp.
 *
 * @param {object} nodes - state.nodes
 * @param {object} telemetryMap - state.telemetry.byNodeId
 * @param {object} connection - state.connection
 * @param {number} [now] - Current epoch ms
 * @returns {{ total: number, available: number, stale: number, unavailable: number, newestTimestamp: string|null }}
 */
export function computeNodeFreshnessSummary(nodes, telemetryMap, connection, now = Date.now()) {
  const allIds = nodes?.allIds || [];
  const nodesMap = nodes?.byId || {};
  const tMap = telemetryMap || {};
  const rtState = connection?.realtimeState || REALTIME_STATES.UNAVAILABLE;

  let available = 0;
  let stale = 0;
  let unavailable = 0;
  let newestTimestamp = null;
  let newestMs = -Infinity;

  for (const id of allIds) {
    const node = nodesMap[id] || { node_id: id };
    const t = tMap[id];

    if (t?.timestamp) {
      const ms = new Date(t.timestamp).getTime();
      if (!isNaN(ms) && ms > newestMs) {
        newestMs = ms;
        newestTimestamp = t.timestamp;
      }
    }

    if (rtState === REALTIME_STATES.UNAVAILABLE || node.status === 'offline') {
      unavailable++;
    } else if (rtState === REALTIME_STATES.STALE || node.status === 'stale') {
      stale++;
    } else if (rtState === REALTIME_STATES.LIVE && t?.timestamp) {
      const ageMs = t?.timestamp ? now - new Date(t.timestamp).getTime() : Infinity;
      if (ageMs <= 15000) {
        available++;
      } else if (ageMs <= 60000) {
        stale++;
      } else {
        unavailable++;
      }
    } else {
      unavailable++;
    }
  }

  // Also consider connection.lastTimestamp if valid
  if (connection?.lastTimestamp) {
    const connMs = new Date(connection.lastTimestamp).getTime();
    if (!isNaN(connMs) && connMs > newestMs) {
      newestMs = connMs;
      newestTimestamp = connection.lastTimestamp;
    }
  }

  return {
    total: allIds.length,
    available,
    stale,
    unavailable,
    newestTimestamp,
  };
}

/**
 * Creates the bottom status bar component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void }}
 */
export function createStatusBar(store) {
  const container = document.createElement('footer');
  container.id = 'climate-bottom-bar';
  container.setAttribute('role', 'contentinfo');
  container.setAttribute('aria-label', 'Climate Eye Operational Status Bar');

  container.innerHTML = `
    <div class="ce-status-cluster">
      <!-- 0. Global External Data Feeds -->
      <div class="ce-status-item">
        <span>GLOBAL:</span>
        <span class="ce-status-pill live" id="ce-global-pill">
          <span class="ce-pill-dot"></span>
          <span id="ce-global-text">ONLINE</span>
        </span>
      </div>

      <!-- 1. Realtime State -->
      <div class="ce-status-item">
        <span>REALTIME:</span>
        <span class="ce-status-pill unavailable" id="ce-realtime-pill">
          <span class="ce-pill-dot"></span>
          <span id="ce-realtime-text">UNAVAILABLE</span>
        </span>
      </div>

      <!-- 2. Node Count & Breakdown -->
      <div class="ce-status-item ce-status-nodes-summary" id="ce-status-nodes-summary">
        <span>MESH NODES:</span>
        <strong id="ce-node-count-text" title="Physical Sensor Nodes">0</strong>
        <span class="ce-sub-counts" id="ce-node-sub-counts">
          (<span class="live" id="ce-node-live-count" title="Available / Live">0</span>L ·
           <span class="stale" id="ce-node-stale-count" title="Stale">0</span>S ·
           <span class="unavailable" id="ce-node-unavail-count" title="Unavailable">0</span>U)
        </span>
      </div>

      <!-- 3. Latest Telemetry -->
      <div class="ce-status-item ce-status-telemetry-ts" id="ce-status-telemetry-ts">
        <span>LATEST:</span>
        <span class="ce-status-val mono" id="ce-status-last-telemetry-val">--</span>
        <span class="ce-unavailable-badge" id="ce-status-last-telemetry-badge">UNAVAILABLE</span>
      </div>

      <!-- 4. Telemetry Connection -->
      <div class="ce-status-item">
        <span>STREAM:</span>
        <span class="ce-status-pill disconnected" id="ce-telemetry-pill">
          <span id="ce-telemetry-text">DISCONNECTED</span>
        </span>
      </div>

      <!-- 5. Backend / API Status -->
      <div class="ce-status-item">
        <span>API:</span>
        <span class="ce-status-pill healthy" id="ce-api-pill">
          <span id="ce-api-text">STANDBY</span>
        </span>
      </div>
    </div>

    <div class="ce-status-cluster">
      <div class="ce-clock" id="ce-utc-clock">00:00:00 UTC</div>
    </div>
  `;

  const realtimePill = container.querySelector('#ce-realtime-pill');
  const realtimeText = container.querySelector('#ce-realtime-text');
  const globalPill = container.querySelector('#ce-global-pill');
  const globalText = container.querySelector('#ce-global-text');
  const nodeCountText = container.querySelector('#ce-node-count-text');
  const nodeLiveCount = container.querySelector('#ce-node-live-count');
  const nodeStaleCount = container.querySelector('#ce-node-stale-count');
  const nodeUnavailCount = container.querySelector('#ce-node-unavail-count');

  const latestTsVal = container.querySelector('#ce-status-last-telemetry-val');
  const latestTsBadge = container.querySelector('#ce-status-last-telemetry-badge');

  const telemetryPill = container.querySelector('#ce-telemetry-pill');
  const telemetryText = container.querySelector('#ce-telemetry-text');
  const apiPill = container.querySelector('#ce-api-pill');
  const apiText = container.querySelector('#ce-api-text');
  const utcClock = container.querySelector('#ce-utc-clock');

  function updateClock() {
    if (!utcClock) return;
    const now = new Date();
    const h = String(now.getUTCHours()).padStart(2, '0');
    const m = String(now.getUTCMinutes()).padStart(2, '0');
    const s = String(now.getUTCSeconds()).padStart(2, '0');
    utcClock.textContent = `${h}:${m}:${s} UTC`;
  }

  const clockInterval = setInterval(updateClock, 1000);
  if (typeof clockInterval?.unref === 'function') {
    clockInterval.unref();
  }
  updateClock();

  function updateFromState(state) {
    if (!state) return;

    // 0. Global Data Status
    const gStatus = state.global?.status || 'ONLINE';
    if (globalText) globalText.textContent = gStatus;
    if (globalPill) {
      globalPill.className = `ce-status-pill ${gStatus === 'ONLINE' ? 'live' : 'standby'}`;
    }

    // 1. Realtime state
    const rtState = state.connection?.realtimeState || REALTIME_STATES.UNAVAILABLE;
    if (realtimeText) realtimeText.textContent = rtState;
    if (realtimePill) {
      realtimePill.classList.remove('live', 'stale', 'simulated', 'unavailable');
      if (rtState === REALTIME_STATES.LIVE) {
        realtimePill.classList.add('live');
      } else if (rtState === REALTIME_STATES.STALE) {
        realtimePill.classList.add('stale');
      } else if (rtState === REALTIME_STATES.SIMULATED) {
        realtimePill.classList.add('simulated');
      } else {
        realtimePill.classList.add('unavailable');
      }
    }

    // 2. Node counts & Freshness
    const summary = computeNodeFreshnessSummary(state.nodes, state.telemetry?.byNodeId, state.connection);
    if (nodeCountText) nodeCountText.textContent = String(summary.total);
    if (nodeLiveCount) nodeLiveCount.textContent = String(summary.available);
    if (nodeStaleCount) nodeStaleCount.textContent = String(summary.stale);
    if (nodeUnavailCount) nodeUnavailCount.textContent = String(summary.unavailable);

    // 3. Latest Telemetry Timestamp
    if (latestTsVal && latestTsBadge) {
      if (summary.newestTimestamp) {
        latestTsVal.textContent = summary.newestTimestamp;
        latestTsBadge.textContent = rtState === REALTIME_STATES.LIVE ? 'LIVE' : 'RECORDED';
        latestTsBadge.className = 'ce-section-badge';
      } else {
        latestTsVal.textContent = '--';
        latestTsBadge.textContent = 'UNAVAILABLE';
        latestTsBadge.className = 'ce-unavailable-badge';
      }
    }

    // 4. Telemetry Stream Connection
    const connected = !!state.connection?.connected;
    if (telemetryText) telemetryText.textContent = connected ? 'CONNECTED' : 'DISCONNECTED';
    if (telemetryPill) {
      telemetryPill.classList.toggle('live', connected);
      telemetryPill.classList.toggle('disconnected', !connected);
    }

    // 5. API / System Status
    const sysStatus = state.system?.status || 'standby';
    if (apiText) apiText.textContent = sysStatus.toUpperCase();
    if (apiPill) {
      const isHealthy = sysStatus === 'healthy' || sysStatus === 'ready';
      const isLoading = sysStatus === 'loading';
      apiPill.classList.toggle('healthy', isHealthy);
      apiPill.classList.toggle('unavailable', isLoading || sysStatus === 'degraded');
      apiPill.classList.toggle('disconnected', !isHealthy && !isLoading && sysStatus !== 'degraded');
    }
  }

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
      clearInterval(clockInterval);
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    },
  };
}
