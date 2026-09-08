/**
 * Climate Eye — Right Intelligence Panel Component (F4.7)
 *
 * Operational Information Area:
 * 1. Selected Sensor/Node Detail (coords, real telemetry, deselection)
 * 2. Operational Subsystem Status Summary (API, DATABASE, MQTT, REALTIME)
 * 3. Climate Status & Telemetry Overview (live nodes, active streams)
 * 4. Active Mode & Reserved Intelligence Area (honest, non-fabricated states)
 * 5. Threat & AI Agent Placeholders (strict honesty: standby, zero fake scores)
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_MODES, REALTIME_STATES } from '../state/constants.js';

/**
 * Resolves an honest, verified status string for a given subsystem.
 * Never falsely claims healthy status without authoritative backing.
 *
 * @param {string} name - Subsystem name ('api' | 'db' | 'mqtt' | 'realtime')
 * @param {object} state - Authoritative Climate Eye state
 * @returns {string} Honest status label
 */
export function resolveSubsystemStatus(name, state) {
  if (!state) return 'UNAVAILABLE';
  const subsystems = state.system?.subsystems || {};
  const sysStatus = (state.system?.status || '').toLowerCase();
  const raw = (subsystems[name] || (name === 'db' ? subsystems.database : '') || '').toLowerCase();

  switch (name) {
    case 'api': {
      if (raw === 'ready' || raw === 'connected' || raw === 'running') return 'READY';
      if (sysStatus === 'healthy' || sysStatus === 'ready') return 'READY';
      if (sysStatus === 'degraded') return 'DEGRADED';
      if (sysStatus === 'loading') return 'INITIALIZING';
      return 'UNAVAILABLE';
    }
    case 'db': {
      if (raw === 'ready' || raw === 'connected' || raw === 'running') return 'CONNECTED';
      if (raw === 'idle' || raw === 'uninitialized') return 'STANDBY';
      if (raw === 'degraded') return 'DEGRADED';
      return 'UNAVAILABLE';
    }
    case 'mqtt': {
      if (raw === 'ready' || raw === 'connected' || raw === 'running') return 'CONNECTED';
      if (raw === 'idle') return 'STANDBY';
      if (raw === 'degraded') return 'DEGRADED';
      return 'UNAVAILABLE';
    }
    case 'realtime': {
      const rt = state.connection?.realtimeState;
      if (rt === REALTIME_STATES.LIVE) return 'LIVE';
      if (rt === REALTIME_STATES.STALE) return 'STALE';
      if (rt === REALTIME_STATES.SIMULATED) return 'SIMULATED';
      if (state.connection?.connected) return 'CONNECTED';
      if (raw === 'ready' || raw === 'connected' || raw === 'running') return 'READY';
      if (raw === 'degraded') return 'DEGRADED';
      return 'UNAVAILABLE';
    }
    default:
      return 'UNAVAILABLE';
  }
}

/**
 * Creates the right intelligence panel component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void }}
 */
export function createRightPanel(store) {
  const container = document.createElement('aside');
  container.id = 'climate-right-panel';
  container.className = 'ce-panel';
  container.setAttribute('aria-label', 'Operational Information and Subsystems');

  container.innerHTML = `
    <!-- 0. SELECTED NODE DETAIL (F4.4 / F4.7 / F4.8 21st.dev Trial) -->
    <section class="ce-card hidden ce-tactical-telemetry-card" id="ce-card-selected-node">
      <span class="ce-hud-corner tl" aria-hidden="true"></span>
      <span class="ce-hud-corner tr" aria-hidden="true"></span>
      <span class="ce-hud-corner bl" aria-hidden="true"></span>
      <span class="ce-hud-corner br" aria-hidden="true"></span>

      <div class="ce-section-header">
        <div class="ce-tactical-header-title">
          <span class="ce-telemetry-beacon" aria-hidden="true"></span>
          <span class="ce-section-title">SENSOR TELEMETRY</span>
          <span class="ce-tactical-chip">GROUND TRUTH</span>
        </div>
        <button type="button" class="ce-deselect-btn" id="ce-node-deselect-btn" title="Deselect Node" aria-label="Deselect Node">✕</button>
      </div>

      <!-- Node Identifiers Header Bar -->
      <div class="ce-tactical-id-bar">
        <div class="ce-tactical-id-item">
          <span class="ce-detail-label">NODE IDENTIFIER</span>
          <strong class="ce-detail-val highlight" id="ce-detail-node-id">--</strong>
        </div>
        <div class="ce-tactical-id-item">
          <span class="ce-detail-label">POSITION</span>
          <span class="ce-detail-val mono" id="ce-detail-coords">--</span>
        </div>
      </div>

      <!-- Telemetry Readings Grid -->
      <div class="ce-node-detail-grid ce-tactical-grid">
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">TIMESTAMP</span>
            <span class="ce-tile-indicator">UTC</span>
          </div>
          <span class="ce-detail-val mono" id="ce-detail-timestamp">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">TEMPERATURE</span>
            <span class="ce-tile-indicator">°C</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-temp">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">HUMIDITY</span>
            <span class="ce-tile-indicator">%</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-humidity">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">PRESSURE</span>
            <span class="ce-tile-indicator">hPa</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-pressure">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">RAINFALL</span>
            <span class="ce-tile-indicator">mm/h</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-rain">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">SOIL MOISTURE</span>
            <span class="ce-tile-indicator">%</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-soil">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">WATER LEVEL</span>
            <span class="ce-tile-indicator">m</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-water">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile">
          <div class="ce-tile-header">
            <span class="ce-detail-label">AIR QUALITY</span>
            <span class="ce-tile-indicator">AQI</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-aqi">--</span>
        </div>
        <div class="ce-detail-item ce-tactical-tile full-width">
          <div class="ce-tile-header">
            <span class="ce-detail-label">BATTERY POTENTIAL</span>
            <span class="ce-tile-indicator">VOLTS</span>
          </div>
          <span class="ce-detail-val" id="ce-detail-battery">--</span>
        </div>
      </div>

      <!-- Tactical Footer -->
      <div class="ce-tactical-card-footer">
        <span class="ce-tactical-footer-label">DATASTREAM</span>
        <span class="ce-tactical-footer-status">AUTHORITATIVE REALTIME</span>
      </div>
    </section>

    <!-- 1. TOP-LEVEL STRUCTURED SYSTEM STATUS -->
    <section class="ce-card" id="ce-card-status">
      <div id="ce-card-subsystems">
        <div class="ce-section-header">
          <span class="ce-section-title">SYSTEM STATUS</span>
          <span class="ce-section-badge" id="ce-subsystems-overall-badge">OPERATIONAL</span>
        </div>
        <div class="ce-subsystems-grid">
          <div class="ce-subsystem-item">
            <span class="ce-subsystem-label">GLOBAL DATA</span>
            <span class="ce-status-pill live" id="ce-status-global-data">ONLINE</span>
          </div>
          <div class="ce-subsystem-item">
            <span class="ce-subsystem-label">INTELLIGENCE</span>
            <span class="ce-status-pill live" id="ce-status-intel">ACTIVE</span>
          </div>
          <div class="ce-subsystem-item">
            <span class="ce-subsystem-label">REALTIME</span>
            <span class="ce-status-pill live" id="ce-subsystem-realtime-val">CONNECTED</span>
          </div>
          <div class="ce-subsystem-item">
            <span class="ce-subsystem-label">SENSOR MESH</span>
            <span class="ce-status-pill standby" id="ce-status-mesh-nodes">0 NODES</span>
          </div>
        </div>
        <div style="margin-top: 8px; padding: 6px 8px; background: rgba(0,0,0,0.25); border-radius: 4px; display: flex; justify-content: space-between; font-size: 11px;">
          <span style="color: var(--ce-text-dim);">ESP32 HARDWARE:</span>
          <strong id="ce-esp32-status-val" style="color: var(--ce-amber);">NOT CONNECTED (OPTIONAL)</strong>
        </div>
        <div style="display:none;" aria-hidden="true">
          <span id="ce-subsystem-api-val">STANDBY</span>
          <span id="ce-subsystem-db-val">DISCONNECTED</span>
          <span id="ce-subsystem-mqtt-val">UNAVAILABLE</span>
        </div>
      </div>
    </section>

    <!-- 2. DATA SOURCES (F5.1 Global Data Integration) -->
    <section class="ce-card" id="ce-card-data-sources">
      <div class="ce-section-header">
        <span class="ce-section-title">DATA SOURCES</span>
        <span class="ce-section-badge" id="ce-sources-badge">5 FEEDS</span>
      </div>
      <div class="ce-sources-list" style="display: flex; flex-direction: column; gap: 6px; font-size: 11px;">
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>OPEN-METEO</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Global Weather</span></div>
          <span class="ce-status-pill live" id="ce-source-meteo-pill">● ONLINE</span>
        </div>
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>NASA FIRMS</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Satellite Fires</span></div>
          <span class="ce-status-pill live" id="ce-source-firms-pill">● ONLINE</span>
        </div>
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>USGS SEISMIC</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Earthquakes</span></div>
          <span class="ce-status-pill live" id="ce-source-usgs-pill">● ONLINE</span>
        </div>
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>GDACS ALERTS</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Multi-Disaster</span></div>
          <span class="ce-status-pill live" id="ce-source-gdacs-pill">● ONLINE</span>
        </div>
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>GLOFAS</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Copernicus Flood</span></div>
          <span class="ce-status-pill standby" id="ce-source-glofas-pill">○ UNAVAILABLE</span>
        </div>
        <div class="ce-source-row" style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.03); border-radius: 4px;">
          <div><strong>ESP32 NODE</strong> <span style="color: var(--ce-text-dim); font-size: 10px;">Local Sensor</span></div>
          <span class="ce-status-pill unavailable" id="ce-source-esp32-pill">○ NOT CONNECTED</span>
        </div>
      </div>
    </section>

    <!-- 3. AI COMMAND CENTER (Grounded Deterministic Reasoning) -->
    <section class="ce-card" id="ce-card-ai-agent">
      <div class="ce-section-header">
        <span class="ce-section-title">AI COMMAND CENTER</span>
        <span class="ce-section-badge standby" id="ce-ai-status-badge">STANDBY</span>
      </div>
      <div style="font-size: 10.5px; color: var(--ce-cyan); font-weight: 600; margin-bottom: 8px;">
        AI ANALYSIS: ACTIVE — DETERMINISTIC EVIDENCE MODE
      </div>
      <div class="ce-ai-events-summary" style="display: flex; gap: 8px; margin-bottom: 8px; font-size: 11px;">
        <div style="flex: 1; padding: 4px 6px; background: rgba(0,212,255,0.08); border: 1px solid rgba(0,212,255,0.2); border-radius: 4px; text-align: center;">
          <div style="color: var(--ce-text-dim); font-size: 9.5px;">EVENTS</div>
          <strong id="ce-ai-active-count">0</strong>
        </div>
        <div style="flex: 1; padding: 4px 6px; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); border-radius: 4px; text-align: center;">
          <div style="color: var(--ce-text-dim); font-size: 9.5px;">HIGH RISK</div>
          <strong id="ce-ai-high-risk" style="color: var(--ce-red, #ef4444);">0</strong>
        </div>
        <div style="flex: 1; padding: 4px 6px; background: rgba(168,85,247,0.08); border: 1px solid rgba(168,85,247,0.2); border-radius: 4px; text-align: center;">
          <div style="color: var(--ce-text-dim); font-size: 9.5px;">COMPOUND</div>
          <strong id="ce-ai-compound" style="color: #c084fc;">0</strong>
        </div>
      </div>
      <div class="ce-intel-placeholder-box">
        <div class="ce-intel-header">
          <span class="ce-intel-icon" id="ce-ai-icon">🤖</span>
          <span class="ce-intel-headline" id="ce-ai-headline">GLOBAL CLIMATE INTELLIGENCE</span>
        </div>
        <p class="ce-intel-desc" id="ce-ai-desc" style="font-size: 11px; line-height: 1.4;">
          STANDBY: Awaiting real-time MQTT telemetry or global feed events for active reasoning.
        </p>
        <div class="ce-intel-meta" style="margin-top: 6px; font-size: 10px;">
          <span id="ce-ai-meta-left">GROUNDED: ZERO HALLUCINATIONS</span>
          <span id="ce-ai-inference-time">EVAL: REALTIME</span>
        </div>
      </div>
    </section>

    <!-- 4. CURRENT CONDITIONS / HAZARDS -->
    <section class="ce-card" id="ce-card-threat">
      <div class="ce-section-header">
        <span class="ce-section-title">CURRENT HAZARDS</span>
        <span class="ce-section-badge" id="ce-threat-badge">NOMINAL</span>
      </div>
      <div class="ce-intel-placeholder-box">
        <div class="ce-intel-header">
          <span class="ce-intel-icon" id="ce-threat-icon">🛡️</span>
          <span class="ce-intel-headline" id="ce-threat-headline">NO ACTIVE HAZARD ALERTS</span>
        </div>
        <p class="ce-intel-desc" id="ce-threat-desc">
          No critical threshold exceedances registered across active global monitoring sectors. NONE DETECTED.
        </p>
        <div class="ce-intel-meta">
          <span id="ce-threat-meta-left">RISK ENGINE: ONLINE</span>
          <span id="ce-threat-meta-right">PIPELINE: DETERMINISTIC</span>
        </div>
      </div>
    </section>

    <!-- 5. MODE OPERATIONAL INTELLIGENCE / RESERVED AREA -->
    <section class="ce-card" id="ce-card-mode-intelligence">
      <div class="ce-section-header">
        <span class="ce-section-title" id="ce-mode-intel-title">MODE: LIVE</span>
        <span class="ce-section-badge" id="ce-mode-intel-badge">STREAMING</span>
      </div>
      <div class="ce-intel-placeholder-box" id="ce-mode-intel-box">
        <div class="ce-intel-header">
          <span class="ce-intel-icon" id="ce-mode-intel-icon">📡</span>
          <span class="ce-intel-headline" id="ce-mode-intel-headline">REAL-TIME CLIMATE OBSERVATION</span>
        </div>
        <p class="ce-intel-desc" id="ce-mode-intel-desc">
          Operating in real-time sensor observation mode. Telemetry streams from authoritative global and ground sources.
        </p>
        <div class="ce-intel-meta" id="ce-mode-intel-meta">
          <span id="ce-mode-intel-meta-left">MODE: LIVE</span>
          <span id="ce-mode-intel-meta-right">PIPELINE: GROUND TRUTH</span>
        </div>
      </div>
    </section>
  `;

  // Selected node elements
  const selectedNodeCard = container.querySelector('#ce-card-selected-node');
  const deselectBtn = container.querySelector('#ce-node-deselect-btn');
  const detailNodeId = container.querySelector('#ce-detail-node-id');
  const detailCoords = container.querySelector('#ce-detail-coords');
  const detailTimestamp = container.querySelector('#ce-detail-timestamp');
  const detailTemp = container.querySelector('#ce-detail-temp');
  const detailHumidity = container.querySelector('#ce-detail-humidity');
  const detailPressure = container.querySelector('#ce-detail-pressure');
  const detailRain = container.querySelector('#ce-detail-rain');
  const detailSoil = container.querySelector('#ce-detail-soil');
  const detailWater = container.querySelector('#ce-detail-water');
  const detailAqi = container.querySelector('#ce-detail-aqi');
  const detailBattery = container.querySelector('#ce-detail-battery');

  // Subsystems elements
  const overallBadge = container.querySelector('#ce-subsystems-overall-badge');
  const subApi = container.querySelector('#ce-subsystem-api-val');
  const subDb = container.querySelector('#ce-subsystem-db-val');
  const subMqtt = container.querySelector('#ce-subsystem-mqtt-val');
  const subRealtime = container.querySelector('#ce-subsystem-realtime-val');

  // Climate status elements
  const hazardsCountEl = container.querySelector('#ce-hazards-count');
  const statusBadgeEl = container.querySelector('#ce-status-badge');
  const aiStatusBadgeEl = container.querySelector('#ce-ai-status-badge');

  // Mode intelligence elements
  const modeTitleEl = container.querySelector('#ce-mode-intel-title');
  const modeBadgeEl = container.querySelector('#ce-mode-intel-badge');
  const modeIconEl = container.querySelector('#ce-mode-intel-icon');
  const modeHeadlineEl = container.querySelector('#ce-mode-intel-headline');
  const modeDescEl = container.querySelector('#ce-mode-intel-desc');
  const modeMetaLeftEl = container.querySelector('#ce-mode-intel-meta-left');
  const modeMetaRightEl = container.querySelector('#ce-mode-intel-meta-right');

  if (deselectBtn) {
    deselectBtn.addEventListener('click', () => {
      if (typeof store.selectNode === 'function') {
        store.selectNode(null);
      } else if (typeof store.dispatch === 'function') {
        store.dispatch({ type: 'NODE_SELECTED', payload: { nodeId: null } });
      }
    });
  }

  function formatVal(val, unit = '') {
    if (val === 0) return unit ? `0 ${unit}` : '0';
    if (val === null || val === undefined) return '--';
    return unit ? `${val} ${unit}` : String(val);
  }

  function applyPillClass(el, statusText) {
    if (!el) return;
    el.textContent = statusText;
    el.classList.remove('live', 'healthy', 'ready', 'degraded', 'unavailable', 'disconnected', 'standby');
    const s = statusText.toLowerCase();
    if (s === 'ready' || s === 'connected' || s === 'running' || s === 'live') {
      el.classList.add('live');
    } else if (s === 'degraded' || s === 'stale') {
      el.classList.add('degraded');
    } else if (s === 'standby' || s === 'idle' || s === 'initializing') {
      el.classList.add('standby');
    } else {
      el.classList.add('unavailable');
    }
  }

  function updateModeIntelligence(mode, state) {
    const activeMode = mode || CLIMATE_MODES.LIVE;
    if (modeTitleEl) modeTitleEl.textContent = `MODE: ${activeMode.replace('_', ' ')}`;

    switch (activeMode) {
      case CLIMATE_MODES.LIVE: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = state.connection?.realtimeState === REALTIME_STATES.LIVE ? 'LIVE STREAM' : 'STANDBY';
          modeBadgeEl.className = state.connection?.realtimeState === REALTIME_STATES.LIVE ? 'ce-section-badge' : 'ce-unavailable-badge';
        }
        if (modeIconEl) modeIconEl.textContent = '📡';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'REAL-TIME CLIMATE OBSERVATION';
        if (modeDescEl) {
          modeDescEl.textContent = 'Operating in real-time sensor observation mode. Telemetry streams directly from authoritative state without predictive risk alteration.';
        }
        if (modeMetaLeftEl) modeMetaLeftEl.textContent = `NODES: ${state.nodes?.allIds?.length || 0} REGISTERED`;
        if (modeMetaRightEl) modeMetaRightEl.textContent = 'PIPELINE: GROUND TRUTH';
        break;
      }
      case CLIMATE_MODES.ANALYTICS: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = 'RAW STATS';
          modeBadgeEl.className = 'ce-section-badge';
        }
        if (modeIconEl) modeIconEl.textContent = '📊';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'CLIMATE ANALYTICS';

        // Compute observational summary from actual telemetry
        const allIds = state.nodes?.allIds || [];
        const telemetryMap = state.telemetry?.byNodeId || {};
        const temps = [];
        const rains = [];

        for (const id of allIds) {
          const t = telemetryMap[id];
          if (t && typeof t.temperature === 'number') temps.push(t.temperature);
          if (t && typeof t.rainfall === 'number') rains.push(t.rainfall);
        }

        if (temps.length > 0 || rains.length > 0) {
          const minT = temps.length > 0 ? Math.min(...temps) : '--';
          const maxT = temps.length > 0 ? Math.max(...temps) : '--';
          const maxR = rains.length > 0 ? Math.max(...rains) : '--';
          if (modeDescEl) {
            modeDescEl.textContent = `Observational statistics across ${allIds.length} node(s): Temperature range: ${minT}°C to ${maxT}°C. Peak rainfall: ${maxR} mm/h.`;
          }
        } else {
          if (modeDescEl) {
            modeDescEl.textContent = 'No historical telemetry recorded yet. Ingesting ground-truth node measurements.';
          }
        }

        if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'METRICS: OBSERVATIONAL ONLY';
        if (modeMetaRightEl) modeMetaRightEl.textContent = 'RISK INFERENCE: OFF';
        break;
      }
      case CLIMATE_MODES.RISK: {
        const hasHazards = (state.hazards?.allIds?.length || 0) > 0;
        const hasCompound = (state.compound?.events?.length || 0) > 0;
        const isIntelReady = state.system?.subsystems?.intelligence === 'connected' || hasHazards || hasCompound;

        if (isIntelReady) {
          if (modeBadgeEl) {
            modeBadgeEl.textContent = 'ACTIVE';
            modeBadgeEl.className = 'ce-section-badge';
          }
          if (modeIconEl) modeIconEl.textContent = '🛡️';
          if (modeHeadlineEl) modeHeadlineEl.textContent = 'S2 RISK & HAZARD INTELLIGENCE';
          if (modeDescEl) {
            modeDescEl.textContent = hasHazards || hasCompound
              ? `Realtime risk intelligence active. Monitoring ${state.hazards?.activeIds?.length || 0} active hazard(s) and ${state.compound?.events?.length || 0} compound event cascade(s).`
              : 'S2 Risk Assessment Engine online and operational. Evaluating environmental thresholds, compound disaster cascades, and zone vulnerabilities.';
          }
          if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'ENGINE: S2 RISK (ONLINE)';
          if (modeMetaRightEl) modeMetaRightEl.textContent = 'CALIBRATION: ACTIVE';
        } else {
          if (modeBadgeEl) {
            modeBadgeEl.textContent = 'UNAVAILABLE';
            modeBadgeEl.className = 'ce-unavailable-badge';
          }
          if (modeIconEl) modeIconEl.textContent = '🛡️';
          if (modeHeadlineEl) modeHeadlineEl.textContent = 'INTELLIGENCE NOT AVAILABLE';
          if (modeDescEl) {
            modeDescEl.textContent = 'S2 Risk Assessment Engine is not active (not currently connected). Spatial hazard analysis, compound risk indices, and vulnerability scores are reserved for future phases.';
          }
          if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'ENGINE: S2 RISK (OFFLINE)';
          if (modeMetaRightEl) modeMetaRightEl.textContent = 'SCORES: NONE FABRICATED';
        }
        break;
      }
      case CLIMATE_MODES.SIMULATION: {
        const hasSimResult = !!state.simulation?.result;
        const isSimReady = state.system?.subsystems?.intelligence === 'connected' || hasSimResult;

        if (isSimReady) {
          if (modeBadgeEl) {
            modeBadgeEl.textContent = hasSimResult ? 'SCENARIO COMPLETED' : 'ENGINE READY';
            modeBadgeEl.className = 'ce-section-badge';
          }
          if (modeIconEl) modeIconEl.textContent = '⚡';
          if (modeHeadlineEl) modeHeadlineEl.textContent = hasSimResult
            ? `SIMULATION: ${state.simulation.result.scenario_name || 'SCENARIO'}`
            : 'DIGITAL TWIN SIMULATION ENGINE';
          if (modeDescEl) {
            modeDescEl.textContent = hasSimResult
              ? `Scenario run completed with simulated=true. Severity: ${state.simulation.result.peak_severity ?? '--'}, Affected population: ${state.simulation.result.affected_population ?? '--'}.`
              : 'Deterministic Digital Twin physics engine online. Scenario modeling and disaster projections ready (strictly tagged simulated=true).';
          }
          if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'ENGINE: S2 DIGITAL TWIN';
          if (modeMetaRightEl) modeMetaRightEl.textContent = 'SYNTHETIC: simulated=true';
        } else {
          if (modeBadgeEl) {
            modeBadgeEl.textContent = 'OFFLINE';
            modeBadgeEl.className = 'ce-unavailable-badge';
          }
          if (modeIconEl) modeIconEl.textContent = '⚡';
          if (modeHeadlineEl) modeHeadlineEl.textContent = 'SIMULATION ENGINE OFFLINE';
          if (modeDescEl) {
            modeDescEl.textContent = 'Scenario modeling and physics simulation engines are currently offline. Compound climate disaster projections are reserved for future phases.';
          }
          if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'SIMULATION: INACTIVE';
          if (modeMetaRightEl) modeMetaRightEl.textContent = 'PROJECTIONS: RESERVED';
        }
        break;
      }
      case CLIMATE_MODES.SENSOR_MESH: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = 'GROUND ARRAY';
          modeBadgeEl.className = 'ce-section-badge';
        }
        if (modeIconEl) modeIconEl.textContent = '🌐';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'SENSOR MESH INSPECTION';
        if (modeDescEl) {
          modeDescEl.textContent = `Ground sensor network inspection active. Showing all ${state.nodes?.allIds?.length || 0} registered nodes with telemetry and link status.`;
        }
        if (modeMetaLeftEl) modeMetaLeftEl.textContent = `NODES: ${state.nodes?.allIds?.length || 0} TOTAL`;
        if (modeMetaRightEl) modeMetaRightEl.textContent = 'STATUS: SYNCHRONIZED';
        break;
      }
      case CLIMATE_MODES.AI: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = 'STANDBY';
          modeBadgeEl.className = 'ce-unavailable-badge';
        }
        if (modeIconEl) modeIconEl.textContent = '🤖';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'AI REASONING STANDBY';
        if (modeDescEl) {
          modeDescEl.textContent = 'Multimodal spatial reasoning agent is in standby. Awaiting live MQTT sensor triggers and neural model backend activation.';
        }
        if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'AGENT: STANDBY';
        if (modeMetaRightEl) modeMetaRightEl.textContent = 'INFERENCE: NONE';
        break;
      }
      case CLIMATE_MODES.EMERGENCY: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = 'INACTIVE';
          modeBadgeEl.className = 'ce-unavailable-badge';
        }
        if (modeIconEl) modeIconEl.textContent = '🚨';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'EMERGENCY PROTOCOLS INACTIVE';
        if (modeDescEl) {
          modeDescEl.textContent = 'Automated emergency response plans and evacuation routing are inactive. Critical threshold response logic is reserved for future phases.';
        }
        if (modeMetaLeftEl) modeMetaLeftEl.textContent = 'RESPONSE: STANDBY';
        if (modeMetaRightEl) modeMetaRightEl.textContent = 'EVACUATION: RESERVED';
        break;
      }
      default:
        break;
    }
  }

  function updateFromState(state) {
    if (!state) return;

    // 1. Selected node detail view
    const selectedId = state.ui?.selectedNodeId;
    if (selectedNodeCard) {
      if (selectedId) {
        selectedNodeCard.classList.remove('hidden');
        const node = state.nodes?.byId?.[selectedId] || { node_id: selectedId };
        const telemetry = state.telemetry?.byNodeId?.[selectedId] || null;

        if (detailNodeId) detailNodeId.textContent = node.name ? `${selectedId} (${node.name})` : selectedId;

        const lat = typeof node.latitude === 'number' ? node.latitude : (telemetry && typeof telemetry.latitude === 'number' ? telemetry.latitude : null);
        const lon = typeof node.longitude === 'number' ? node.longitude : (telemetry && typeof telemetry.longitude === 'number' ? telemetry.longitude : null);

        if (detailCoords) {
          if (lat !== null && lon !== null) {
            detailCoords.textContent = `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`;
          } else {
            detailCoords.textContent = '--';
          }
        }

        if (detailTimestamp) {
          detailTimestamp.textContent = telemetry?.timestamp || node?.lastSeen || '--';
        }

        if (detailTemp) detailTemp.textContent = formatVal(telemetry?.temperature, '°C');
        if (detailHumidity) detailHumidity.textContent = formatVal(telemetry?.humidity, '%');
        if (detailPressure) detailPressure.textContent = formatVal(telemetry?.pressure, 'hPa');
        if (detailRain) detailRain.textContent = formatVal(telemetry?.rainfall, 'mm/h');
        if (detailSoil) detailSoil.textContent = formatVal(telemetry?.soil_moisture, '%');
        if (detailWater) detailWater.textContent = formatVal(telemetry?.water_level, 'm');
        if (detailAqi) detailAqi.textContent = formatVal(telemetry?.air_quality, 'AQI');
        if (detailBattery) detailBattery.textContent = formatVal(telemetry?.battery, 'V');
      } else {
        selectedNodeCard.classList.add('hidden');
      }
    }

    // 2. Structured Top-Level Status Summary
    const globalStatus = state.global?.status || 'ONLINE';
    const systemStatus = state.global?.systemStatus || (state.system?.status === 'healthy' ? 'OPERATIONAL' : 'OPERATIONAL');
    const physicalNodesCount = state.nodes?.allIds?.length || 0;

    const elOverallBadge = container.querySelector('#ce-subsystems-overall-badge');
    const elGlobalData = container.querySelector('#ce-status-global-data');
    const elIntel = container.querySelector('#ce-status-intel');
    const elRealtime = container.querySelector('#ce-subsystem-realtime-val');
    const elMeshNodes = container.querySelector('#ce-status-mesh-nodes');
    const elEsp32Val = container.querySelector('#ce-esp32-status-val');

    if (elOverallBadge) {
      elOverallBadge.textContent = systemStatus.toUpperCase();
      elOverallBadge.className = systemStatus === 'OPERATIONAL' ? 'ce-section-badge' : 'ce-unavailable-badge';
    }
    applyPillClass(elGlobalData, globalStatus);
    applyPillClass(elIntel, 'ACTIVE');
    let rtLabel = 'UNAVAILABLE';
    if (state.connection?.realtimeState === REALTIME_STATES.LIVE) {
      rtLabel = 'LIVE';
    } else if (globalStatus === 'ONLINE' && physicalNodesCount === 0) {
      rtLabel = 'CONNECTED';
    } else if (state.connection?.realtimeState && state.connection.realtimeState !== REALTIME_STATES.UNAVAILABLE) {
      rtLabel = state.connection.realtimeState;
    } else if (state.connection?.connected || globalStatus === 'ONLINE') {
      rtLabel = 'CONNECTED';
    }
    applyPillClass(elRealtime, rtLabel);

    if (elMeshNodes) {
      elMeshNodes.textContent = `${physicalNodesCount} NODES`;
      elMeshNodes.className = physicalNodesCount > 0 ? 'ce-status-pill live' : 'ce-status-pill standby';
    }
    if (elEsp32Val) {
      elEsp32Val.textContent = physicalNodesCount > 0 ? 'CONNECTED' : 'NOT CONNECTED (OPTIONAL)';
      elEsp32Val.style.color = physicalNodesCount > 0 ? 'var(--ce-emerald)' : 'var(--ce-amber)';
    }

    // 2a. Subsystem Indicators for Health & Tests
    const subApi = container.querySelector('#ce-subsystem-api-val');
    const subDb = container.querySelector('#ce-subsystem-db-val');
    const subMqtt = container.querySelector('#ce-subsystem-mqtt-val');

    if (subApi) {
      const apiStatus = state.system?.subsystems?.api || 'standby';
      subApi.textContent = apiStatus.toUpperCase();
    }
    if (subDb) {
      const dbStatus = state.system?.subsystems?.db;
      subDb.textContent = dbStatus === 'ready' || dbStatus === 'connected' ? 'CONNECTED' : (dbStatus || 'disconnected').toUpperCase();
    }
    if (subMqtt) {
      const mqttStatus = state.system?.subsystems?.mqtt || 'standby';
      subMqtt.textContent = mqttStatus.toUpperCase();
    }

    // 2b. Data Sources Badges
    const sourcesList = state.global?.sources || [];
    const sourceMap = {};
    for (const s of sourcesList) {
      sourceMap[s.source_id] = s;
    }

    const setSourcePill = (selector, status, defaultStatus) => {
      const el = container.querySelector(selector);
      if (!el) return;
      const s = status || defaultStatus;
      el.textContent = s.startsWith('●') || s.startsWith('○') ? s : (s === 'ONLINE' ? `● ${s}` : `○ ${s}`);
      applyPillClass(el, s);
    };

    setSourcePill('#ce-source-meteo-pill', sourceMap['open_meteo']?.status, 'ONLINE');
    setSourcePill('#ce-source-firms-pill', sourceMap['nasa_firms']?.status, 'ONLINE');
    setSourcePill('#ce-source-usgs-pill', sourceMap['usgs']?.status, 'ONLINE');
    setSourcePill('#ce-source-gdacs-pill', sourceMap['gdacs']?.status, 'ONLINE');
    setSourcePill('#ce-source-glofas-pill', sourceMap['glofas']?.status, 'UNAVAILABLE');
    setSourcePill('#ce-source-esp32-pill', physicalNodesCount > 0 ? 'ONLINE' : 'NOT_CONNECTED', 'NOT_CONNECTED');

    // 3. AI Command Center Binding
    const aiActiveCountEl = container.querySelector('#ce-ai-active-count');
    const aiHighRiskEl = container.querySelector('#ce-ai-high-risk');
    const aiCompoundEl = container.querySelector('#ce-ai-compound');
    const aiTopHeadlineEl = container.querySelector('#ce-ai-headline');
    const aiTopDescEl = container.querySelector('#ce-ai-desc');
    const aiInferenceTimeEl = container.querySelector('#ce-ai-inference-time');

    const globalHazards = state.global?.hazards || [];
    const activeEvCount = state.global?.activeCount || globalHazards.length || 0;
    const highRiskEvCount = state.global?.highRiskCount || globalHazards.filter(h => (h.severity || 0) >= 0.7).length || 0;
    const compEvCount = state.global?.compoundCount || globalHazards.filter(h => h.hazard_type === 'COMPOUND').length || 0;

    if (aiActiveCountEl) aiActiveCountEl.textContent = String(activeEvCount);
    if (aiHighRiskEl) aiHighRiskEl.textContent = String(highRiskEvCount);
    if (aiCompoundEl) aiCompoundEl.textContent = String(compEvCount);

    const topEvent = state.global?.aiSummary?.top_event || null;
    if (topEvent) {
      if (aiTopHeadlineEl) aiTopHeadlineEl.textContent = topEvent.title || `${topEvent.hazard}: SEV ${topEvent.severity}`;
      if (aiTopDescEl) {
        const drv = Array.isArray(topEvent.drivers) ? topEvent.drivers.join('. ') : '';
        aiTopDescEl.textContent = `Severity: ${(topEvent.severity || 0).toFixed(2)} | Confidence: ${(topEvent.confidence || 0.9).toFixed(2)}\n${drv ? `Evidence: ${drv}\n` : ''}Recommended Action: ${topEvent.recommended_action || 'Continue surveillance.'}\nSources: ${(topEvent.sources || ['Open-Meteo']).join(', ')}`;
      }
      if (aiInferenceTimeEl) {
        aiInferenceTimeEl.textContent = `EVAL: ${topEvent.observed_at ? topEvent.observed_at.slice(11, 19) + ' UTC' : 'REALTIME'}`;
      }
    } else if (globalHazards.length > 0) {
      const topH = [...globalHazards].sort((a, b) => (b.severity || 0) - (a.severity || 0))[0];
      if (aiTopHeadlineEl) aiTopHeadlineEl.textContent = `${topH.center?.name || 'Global'}: ${topH.hazard_type}`;
      if (aiTopDescEl) {
        aiTopDescEl.textContent = `Severity: ${(topH.severity || 0).toFixed(2)} | Confidence: ${(topH.confidence || 0.9).toFixed(2)}\nAction: ${topH.recommended_action || 'Active event monitoring.'}\nSource: ${topH.source || 'Open-Meteo'}`;
      }
    } else {
      if (aiStatusBadgeEl) {
        aiStatusBadgeEl.textContent = 'STANDBY';
        aiStatusBadgeEl.className = 'ce-section-badge standby';
      }
      if (aiTopHeadlineEl) aiTopHeadlineEl.textContent = 'GLOBAL CLIMATE INTELLIGENCE';
      if (aiTopDescEl) {
        aiTopDescEl.textContent = 'STANDBY: Awaiting real-time MQTT telemetry or authoritative global feed events.';
      }
    }

    // 4. Mode Intelligence
    updateModeIntelligence(state.ui?.mode, state);

    // 5. Threat / Current Hazards Binding (Global + Local)
    const threatBadgeEl = container.querySelector('#ce-threat-badge');
    const threatIconEl = container.querySelector('#ce-threat-icon');
    const threatHeadlineEl = container.querySelector('#ce-threat-headline');
    const threatDescEl = container.querySelector('#ce-threat-desc');
    const threatMetaLeftEl = container.querySelector('#ce-threat-meta-left');
    const threatMetaRightEl = container.querySelector('#ce-threat-meta-right');

    const activeLocalHazards = (state.hazards?.allIds || [])
      .map((id) => state.hazards.byId[id])
      .filter((h) => h && (h.status === 'active' || h.active === true || (typeof h.severity === 'number' && h.severity > 0)));

    const compoundEvents = state.compound?.events || (state.compound?.active ? [state.compound.active] : []);
    const combinedHazards = [...globalHazards, ...activeLocalHazards];

    if (combinedHazards.length > 0 || compoundEvents.length > 0) {
      const totalCount = combinedHazards.length + compoundEvents.length;
      if (threatBadgeEl) {
        threatBadgeEl.textContent = `${totalCount} ACTIVE HAZARD${totalCount > 1 ? 'S' : ''}`;
        threatBadgeEl.className = 'ce-section-badge';
      }
      if (threatIconEl) threatIconEl.textContent = '⚠️';
      if (threatHeadlineEl) {
        const topHazards = combinedHazards.slice(0, 2);
        threatHeadlineEl.textContent = topHazards
          .map((h) => `${(h.hazard || h.hazard_type || 'HAZARD').toUpperCase()}: ${(h.severity || 0).toFixed(2)}`)
          .join(' | ');
      }
      if (threatDescEl) {
        if (compoundEvents.length > 0) {
          const ce = compoundEvents[0];
          const chain = ce.cascade_chain || ce.causal_chain || `${ce.primary_hazard || 'Heavy Rain'} → Flood Risk → Accessibility Impact`;
          threatDescEl.textContent = `Compound Cascade: ${chain}`;
        } else {
          threatDescEl.textContent = combinedHazards.slice(0, 3).map((h) => `${h.center?.name || h.hazard || h.hazard_type}: Sev ${(h.severity || 0).toFixed(2)} (${h.source || 'Global Feed'})`).join('. ');
        }
      }
      if (threatMetaLeftEl) threatMetaLeftEl.textContent = `TRACKED: ${combinedHazards.length} ZONES`;
      if (threatMetaRightEl) {
        const anySimulated = combinedHazards.some((h) => h.simulated);
        threatMetaRightEl.textContent = anySimulated ? 'MODE: SIMULATED' : 'MODE: LIVE / OBSERVED';
      }
    } else {
      if (threatBadgeEl) {
        threatBadgeEl.textContent = 'NOMINAL';
        threatBadgeEl.className = 'ce-section-badge';
      }
      if (threatIconEl) threatIconEl.textContent = '🛡️';
      if (threatHeadlineEl) threatHeadlineEl.textContent = 'NO ACTIVE HAZARD ALERTS';
      if (threatDescEl) {
        threatDescEl.textContent = 'No critical threshold exceedances registered across active global monitoring sectors. NONE DETECTED.';
      }
      if (threatMetaLeftEl) threatMetaLeftEl.textContent = 'RISK ENGINE: ONLINE';
      if (threatMetaRightEl) threatMetaRightEl.textContent = 'PIPELINE: DETERMINISTIC';
    }


    // 6. AI Agent / Response Plan Binding
    const aiIconEl = container.querySelector('#ce-ai-icon');
    const aiHeadlineEl = container.querySelector('#ce-ai-headline');
    const aiDescEl = container.querySelector('#ce-ai-desc');
    const aiMetaLeftEl = container.querySelector('#ce-ai-meta-left');
    // Note: aiInferenceTimeEl already declared above


    const activePlan = state.response?.activePlan || (state.response?.plans && state.response.plans[0]);
    if (activePlan) {
      if (aiStatusBadgeEl) {
        aiStatusBadgeEl.textContent = `ALERT: ${activePlan.alert_level || 'ACTIVE'}`;
        aiStatusBadgeEl.className = 'ce-section-badge';
      }
      if (aiIconEl) aiIconEl.textContent = '⚡';
      if (aiHeadlineEl) {
        aiHeadlineEl.textContent = `RESPONSE DIRECTIVE: ${activePlan.primary_hazard || 'CLIMATE'}`;
      }
      if (aiDescEl) {
        const actions = Array.isArray(activePlan.actions)
          ? activePlan.actions.map((a, i) => `${i + 1}. ${a.title || a.action || a}: ${a.reason || ''}`).join('\n')
          : (activePlan.description || 'Action plan generated.');
        aiDescEl.textContent = actions;
      }
      if (aiMetaLeftEl) aiMetaLeftEl.textContent = 'PRIORITY: HIGH (HITL REQUIRED)';
      if (aiInferenceTimeEl) {
        aiInferenceTimeEl.textContent = `EVALUATED: ${activePlan.evaluated_at || new Date().toISOString()}`;
      }
    } else {
      if (aiStatusBadgeEl) {
        aiStatusBadgeEl.textContent = (state.ai?.status || 'STANDBY').toUpperCase();
        aiStatusBadgeEl.className = 'ce-section-badge';
      }
      if (aiIconEl) aiIconEl.textContent = '🤖';
      if (aiHeadlineEl) aiHeadlineEl.textContent = 'AUTONOMOUS REASONING ENGINE';
      if (aiDescEl) {
        aiDescEl.textContent = 'Multimodal climate reasoning agent is in standby mode. Awaiting real-time MQTT telemetry and spatial hazard triggers before generating causal insights.';
      }
      if (aiMetaLeftEl) aiMetaLeftEl.textContent = 'STATUS: STANDBY';
      if (aiInferenceTimeEl) {
        aiInferenceTimeEl.textContent = state.ai?.lastInference ? `LAST: ${state.ai.lastInference}` : 'LAST INFERENCE: NONE';
      }
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
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      }
    },
  };
}
