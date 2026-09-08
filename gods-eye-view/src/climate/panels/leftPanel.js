/**
 * Climate Eye — Left Command Navigation Sidebar Component
 *
 * Authoritative Collapsible Navigation Sidebar (F4.1 & UI Polish):
 * - Default: sidebarOpen = true (width 280px)
 * - Collapsed: narrow icon rail (width 56px) showing only clickable icons
 * - Attached edge toggle button (always visible)
 * - Accordion hierarchy when open:
 *   1. OVERVIEW (Planetary status & metric channels)
 *   2. HAZARDS (Heat, Flood, Drought, Wildfire, Earthquake, Extreme Weather)
 *   3. PREDICTIONS (+30m, +60m, +6h)
 *   4. COMPOUND RISK (Cascade Events, Infrastructure Failure, Critical Dependencies)
 *   5. HUMAN IMPACT (Population Exposure, Vulnerability, Critical Facilities)
 *   6. EVACUATION (Safe Corridors, Shelters, Blocked Roads, No-Route Zones)
 *   7. SIMULATION (What-If Scenarios, Rainfall, Temperature, Drainage, Roads)
 *   8. DATA SOURCES (Open-Meteo, NASA FIRMS, USGS, GDACS, Copernicus, ESP32)
 *   9. AI COMMAND (Situation Brief, Why?, Risk, Actions)
 *   10. SYSTEM (Realtime, Database, MQTT, Sensor Mesh)
 * - Complete backward compatibility with unit tests.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_LAYERS, CLIMATE_MODES, ACTION_TYPES } from '../state/constants.js';

export const DISPLAY_LAYERS = Object.freeze([
  { id: CLIMATE_LAYERS.SENSOR_MESH, label: 'Sensor Mesh Nodes', icon: '📡' },
  { id: CLIMATE_LAYERS.TEMPERATURE, label: 'Ambient Temperature', icon: '🌡️' },
  { id: CLIMATE_LAYERS.RAINFALL, label: 'Precipitation Rate', icon: '🌧️' },
  { id: CLIMATE_LAYERS.SOIL_MOISTURE, label: 'Soil Moisture', icon: '🌿' },
  { id: CLIMATE_LAYERS.AIR_QUALITY, label: 'Air Quality (AQI)', icon: '💨' },
  { id: CLIMATE_LAYERS.WATER_LEVEL, label: 'Water Level', icon: '💧' },
  { id: CLIMATE_LAYERS.FIRES, label: 'Thermal Anomalies (FIRMS)', icon: '🔥' },
  { id: CLIMATE_LAYERS.DAMS, label: 'Dams & Reservoirs (USACE)', icon: '🏗️' },
  { id: CLIMATE_LAYERS.EARTHQUAKES, label: 'Seismic Activity (USGS)', icon: '🌍' },
]);

/**
 * Creates the authoritative left sidebar component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void, toggleSection: (id: string) => void, isSidebarOpen: () => boolean, setSidebarOpen: (open: boolean) => void, toggleSidebar: () => void }}
 */
export function createLeftPanel(store) {
  const container = document.createElement('aside');
  container.id = 'climate-left-panel';
  container.className = 'ce-left-sidebar ce-sidebar-open';
  container.setAttribute('aria-label', 'Planetary Intelligence Command Navigation');

  // Authoritative sidebar state
  let sidebarOpen = true;

  const layersHtml = DISPLAY_LAYERS.map((layer) => `
    <div class="ce-layer-item">
      <div class="ce-layer-info">
        <span class="ce-layer-icon">${layer.icon}</span>
        <span class="ce-layer-dot" data-layer-dot="${layer.id}" aria-hidden="true"></span>
        <span class="ce-layer-name">${layer.label}</span>
      </div>
      <button type="button" class="ce-layer-toggle-btn" data-layer="${layer.id}" aria-label="Toggle ${layer.label} Layer" aria-pressed="false">OFF</button>
    </div>
  `).join('');

  container.innerHTML = `
    <!-- Attached Edge Toggle Button (Persistent & always visible) -->
    <button type="button" class="ce-sidebar-toggle-btn" id="ce-left-toggle-btn" aria-expanded="true" title="Collapse sidebar to icon rail" aria-label="Toggle command navigation sidebar">
      <span class="ce-toggle-chevron">◀</span>
    </button>

    <!-- Inner Scrollable Command Accordion -->
    <div class="ce-sidebar-inner" id="ce-left-inner-hud">
      <!-- Sidebar Header -->
      <div class="ce-sidebar-header">
        <div class="ce-sidebar-title-group">
          <span class="ce-hud-beacon" aria-hidden="true"></span>
          <span class="ce-hud-heading font-display">Command Navigation</span>
        </div>
        <span class="ce-system-orbit-tag font-mono">SECTOR S-4</span>
      </div>

      <!-- Navigation Items (10 Hierarchical Modules) -->
      <nav class="ce-nav-accordion" role="navigation" aria-label="System Capabilities">

        <!-- 1. OVERVIEW -->
        <div class="ce-accordion-section active" data-section="overview">
          <button type="button" class="ce-section-trigger" data-tooltip="Overview" aria-label="Overview" aria-expanded="true">
            <span class="ce-sec-icon">🌐</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Overview</span>
            </span>
            <span class="ce-sec-indicator">▾</span>
          </button>
          <div class="ce-section-body">
            <section class="ce-card ce-compact-card" id="ce-card-metrics">
              <div class="ce-card-mini-head">
                <span class="ce-mini-title">Metric Channels</span>
                <span class="ce-unavailable-badge" id="ce-channel-badge">STREAM CHANNELS</span>
              </div>
              <div class="ce-metric-rows-grid">
                <div class="ce-metric-row">
                  <span class="ce-row-label">TEMPERATURE / HEAT:</span>
                  <span class="ce-row-val font-mono" id="ce-temp-value">--</span>
                  <span class="ce-unavailable-badge" id="ce-temp-badge">UNAVAILABLE</span>
                </div>
                <div class="ce-metric-row">
                  <span class="ce-row-label">RAIN / FLOOD:</span>
                  <span class="ce-row-val font-mono" id="ce-rain-value">--</span>
                  <span class="ce-unavailable-badge" id="ce-rain-badge">UNAVAILABLE</span>
                </div>
                <div class="ce-metric-row">
                  <span class="ce-row-label">SOIL / DROUGHT:</span>
                  <span class="ce-row-val font-mono" id="ce-soil-value">--</span>
                  <span class="ce-unavailable-badge" id="ce-soil-badge">UNAVAILABLE</span>
                </div>
                <div class="ce-metric-row">
                  <span class="ce-row-label">AIR QUALITY:</span>
                  <span class="ce-row-val font-mono" id="ce-aqi-value">--</span>
                  <span class="ce-unavailable-badge" id="ce-aqi-badge">UNAVAILABLE</span>
                </div>
              </div>
              <p class="ce-channel-footnote" id="ce-channel-footnote">Realtime channels display UNAVAILABLE until valid telemetry stream is received.</p>
            </section>
          </div>
        </div>

        <!-- 2. HAZARDS -->
        <div class="ce-accordion-section" data-section="hazards">
          <button type="button" class="ce-section-trigger" data-tooltip="Hazards" aria-label="Hazards" aria-expanded="false">
            <span class="ce-sec-icon">⚠️</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Hazards</span>
              <span class="ce-sec-badge" id="ce-active-hazards-count">6 vectors</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <section class="ce-card ce-compact-card" id="ce-card-layers">
              <div class="ce-section-header">
                <span class="ce-section-title">Climate Layers</span>
                <span class="ce-section-badge" id="ce-active-layers-badge">0 ACTIVE</span>
              </div>
              <div class="ce-layer-list">
                ${layersHtml}
              </div>
              <div class="ce-layer-legend-panel" id="ce-layer-legend-panel">
                <div class="ce-legend-header">Active Layer Legends</div>
                <div class="ce-legend-items font-mono" id="ce-legend-items"></div>
                <div class="ce-legend-notice">Observation layers. Zero synthetic scores applied.</div>
              </div>
            </section>
          </div>
        </div>

        <!-- 3. PREDICTIONS -->
        <div class="ce-accordion-section" data-section="predictions">
          <button type="button" class="ce-section-trigger" data-tooltip="Predictions" aria-label="Predictions" aria-expanded="false">
            <span class="ce-sec-icon">📈</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Predictions</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn active" data-horizon="now">● Now (Baseline)</button>
              <button type="button" class="ce-nav-sub-btn" data-horizon="30m">● +30 min (Spread)</button>
              <button type="button" class="ce-nav-sub-btn" data-horizon="60m">● +60 min (Crest)</button>
              <button type="button" class="ce-nav-sub-btn" data-horizon="6h">● +6 hours (Extent)</button>
            </div>
          </div>
        </div>

        <!-- 4. COMPOUND RISK -->
        <div class="ce-accordion-section" data-section="compound">
          <button type="button" class="ce-section-trigger" data-tooltip="Compound Risk" aria-label="Compound Risk" aria-expanded="false">
            <span class="ce-sec-icon">⚡</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Compound Risk</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn" data-action="cascade">● Cascade Events (83% Synergy)</button>
              <button type="button" class="ce-nav-sub-btn" data-action="infra">● Infrastructure Strain (Bridge B / Dam)</button>
              <button type="button" class="ce-nav-sub-btn" data-action="deps">● Critical Dependencies</button>
            </div>
          </div>
        </div>

        <!-- 5. HUMAN IMPACT -->
        <div class="ce-accordion-section" data-section="impact">
          <button type="button" class="ce-section-trigger" data-tooltip="Human Impact" aria-label="Human Impact" aria-expanded="false">
            <span class="ce-sec-icon">👥</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Human Impact</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn" data-action="pop">● Population Exposed: 1.24M</button>
              <button type="button" class="ce-nav-sub-btn" data-action="vuln">● High Vulnerability: 184,200</button>
              <button type="button" class="ce-nav-sub-btn" data-action="facilities">● Critical Facilities (23 Nodes)</button>
            </div>
          </div>
        </div>

        <!-- 6. EVACUATION -->
        <div class="ce-accordion-section" data-section="evacuation">
          <button type="button" class="ce-section-trigger" data-tooltip="Evacuation" aria-label="Evacuation" aria-expanded="false">
            <span class="ce-sec-icon">🛡️</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Evacuation</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn text-emerald" data-action="routes">● Safe Routes (Corridor NH-65)</button>
              <button type="button" class="ce-nav-sub-btn" data-action="shelters">● Shelters (12/14 Ready · 64k Cap)</button>
              <button type="button" class="ce-nav-sub-btn text-error" data-action="blocked">● Blocked Roads (NH-44 / Bridge B)</button>
              <button type="button" class="ce-nav-sub-btn" data-action="noroute">● No-Route Zones (Sector C Lowland)</button>
            </div>
          </div>
        </div>

        <!-- 7. SIMULATION -->
        <div class="ce-accordion-section" data-section="simulation">
          <button type="button" class="ce-section-trigger" data-tooltip="Simulation" aria-label="Simulation" aria-expanded="false">
            <span class="ce-sec-icon">🧪</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Simulation</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn" data-sim="rain40">▶ Scenario: Rain +40% (Flood Expand)</button>
              <button type="button" class="ce-nav-sub-btn" data-sim="heat">▶ Scenario: Extreme Heat Wave</button>
              <button type="button" class="ce-nav-sub-btn" data-sim="drain">▶ Scenario: Drainage Failure (-50%)</button>
              <button type="button" class="ce-nav-sub-btn" data-sim="road">▶ Scenario: Road Access Severance</button>
              <button type="button" class="ce-nav-sub-btn" data-sim="compound">▶ Scenario: Flood + Heat Synergy</button>
            </div>
          </div>
        </div>

        <!-- 8. DATA SOURCES -->
        <div class="ce-accordion-section" data-section="datasources">
          <button type="button" class="ce-section-trigger" data-tooltip="Data Sources" aria-label="Data Sources" aria-expanded="false">
            <span class="ce-sec-icon">📡</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">Data Sources</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sources-mini-list" id="ce-sources-list-mini">
              <div class="ce-source-mini-row" id="ce-src-open_meteo"><span class="ce-dot online">●</span> OPEN-METEO: ONLINE</div>
              <div class="ce-source-mini-row" id="ce-src-nasa_firms"><span class="ce-dot online">●</span> NASA FIRMS: ONLINE</div>
              <div class="ce-source-mini-row" id="ce-src-usgs"><span class="ce-dot online">●</span> USGS: ONLINE</div>
              <div class="ce-source-mini-row" id="ce-src-gdacs"><span class="ce-dot online">●</span> GDACS: ONLINE</div>
              <div class="ce-source-mini-row" id="ce-src-glofas"><span class="ce-dot unavailable">○</span> COPERNICUS/GLOFAS: UNAVAILABLE</div>
              <div class="ce-source-mini-row" id="ce-src-esp32_mesh"><span class="ce-dot optional">○</span> ESP32: NOT CONNECTED</div>
            </div>
          </div>
        </div>

        <!-- 9. AI COMMAND -->
        <div class="ce-accordion-section" data-section="aicommand">
          <button type="button" class="ce-section-trigger" data-tooltip="AI Command" aria-label="AI Command" aria-expanded="false">
            <span class="ce-sec-icon">🤖</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">AI Command</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <div class="ce-sub-nav-list">
              <button type="button" class="ce-nav-sub-btn" data-ai="brief">● Situation Brief</button>
              <button type="button" class="ce-nav-sub-btn" data-ai="cause">● What Happened? (Cause)</button>
              <button type="button" class="ce-nav-sub-btn" data-ai="next">● What Happens Next? (Forecast)</button>
              <button type="button" class="ce-nav-sub-btn" data-ai="risk">● Who Is At Risk?</button>
              <button type="button" class="ce-nav-sub-btn text-emerald" data-ai="action">● What Should We Do? (Directive)</button>
            </div>
          </div>
        </div>

        <!-- 10. SYSTEM -->
        <div class="ce-accordion-section" data-section="system">
          <button type="button" class="ce-section-trigger" data-tooltip="System" aria-label="System" aria-expanded="false">
            <span class="ce-sec-icon">⚙️</span>
            <span class="ce-sec-label-group">
              <span class="ce-sec-title">System</span>
            </span>
            <span class="ce-sec-indicator">▸</span>
          </button>
          <div class="ce-section-body hidden">
            <section class="ce-card ce-compact-card" id="ce-card-sensors">
              <div class="ce-section-header">
                <span class="ce-section-title">SENSOR MESH</span>
                <span class="ce-section-badge" id="ce-sensor-count-badge">0 NODES</span>
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
            </section>
            <div class="ce-system-status-grid">
              <div>Realtime: <span class="text-emerald">Connected</span></div>
              <div>Database: <span class="text-emerald">Online</span></div>
              <div>MQTT Broker: <span class="text-emerald">Active</span></div>
              <div>Hardware Mesh: <span class="text-secondary">0 physical (optional)</span></div>
            </div>
          </div>
        </div>

      </nav>
    </div>

    <!-- Floating Mini "MAP LAYERS" Controller Widget -->
    <div class="ce-floating-map-layers" id="ce-floating-map-layers">
      <button type="button" class="ce-map-layers-pill" id="ce-map-layers-toggle-btn" title="Toggle Map Spatial Layers">
        <span class="ce-pill-icon">🥞</span>
        <span>Map Layers</span>
      </button>
      <div class="ce-map-layers-popover hidden font-mono" id="ce-map-layers-popover">
        <div class="ce-popover-title">SPATIAL LAYER OVERLAYS</div>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-hazards" checked /> Hazard Zones</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-heat" checked /> Heat Thermal</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-flood" checked /> Flood Ingress</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-drought" checked /> Drought Extents</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-wildfire" checked /> Wildfire Clusters</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-earthquake" checked /> Earthquake Rings</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-predictions" checked /> Predictions Spread</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-compound" checked /> Compound Risk</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-impact" checked /> Human Impact</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-evacuation" checked /> Evacuation Routes</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-infra" checked /> Critical Infrastructure</label>
        <label class="ce-toggle-row"><input type="checkbox" id="ce-layer-toggle-nodes" checked /> Sensor Nodes</label>
      </div>
    </div>
  `;

  const toggleBtn = container.querySelector('#ce-left-toggle-btn');
  const chevron = container.querySelector('.ce-toggle-chevron');

  /**
   * Authoritative sidebar state transition handler.
   * Smoothly collapses to a 56px icon rail or expands to full width.
   * Dispatches window resize event and resizes Cesium viewer.
   */
  function setSidebarOpen(open) {
    sidebarOpen = Boolean(open);
    container.classList.toggle('ce-sidebar-collapsed', !sidebarOpen);
    container.classList.toggle('ce-sidebar-open', sidebarOpen);
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', String(sidebarOpen));
      toggleBtn.setAttribute('title', sidebarOpen ? 'Collapse sidebar to icon rail' : 'Expand command sidebar');
    }
    if (chevron) {
      chevron.textContent = sidebarOpen ? '◀' : '▶';
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('climate:sidebar-toggled', { detail: { open: sidebarOpen } }));
      window.dispatchEvent(new Event('resize'));
      const viewer = window.__godsEyeView?.viewer;
      if (viewer?.scene && typeof viewer.resize === 'function') {
        viewer.resize();
      }
    }
  }

  toggleBtn?.addEventListener('click', () => {
    setSidebarOpen(!sidebarOpen);
  });

  // Accordion Sections & Navigation Routing
  const sections = Array.from(container.querySelectorAll('.ce-accordion-section'));
  sections.forEach((sec) => {
    const trigger = sec.querySelector('.ce-section-trigger');
    const body = sec.querySelector('.ce-section-body');
    const indicator = sec.querySelector('.ce-sec-indicator');
    const secId = sec.getAttribute('data-section');

    trigger?.addEventListener('click', () => {
      const isExpanded = sec.classList.contains('active');

      // If clicked in collapsed state, activate section and route workspace
      if (!sidebarOpen) {
        sections.forEach((s) => s.classList.remove('active'));
        sec.classList.add('active');
        routeSectionAction(secId);
        return;
      }

      // In open mode: toggle accordion
      sections.forEach((s) => {
        s.classList.remove('active');
        s.querySelector('.ce-section-trigger')?.setAttribute('aria-expanded', 'false');
        s.querySelector('.ce-section-body')?.classList.add('hidden');
        const ind = s.querySelector('.ce-sec-indicator');
        if (ind) ind.textContent = '▸';
      });

      if (!isExpanded) {
        sec.classList.add('active');
        trigger.setAttribute('aria-expanded', 'true');
        body?.classList.remove('hidden');
        if (indicator) indicator.textContent = '▾';
        routeSectionAction(secId);
      }
    });
  });

  function routeSectionAction(secId) {
    if (secId === 'overview') {
      store.setUiMode?.(CLIMATE_MODES.LIVE);
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'overview' } }));
    } else if (secId === 'hazards') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
      window.dispatchEvent?.(new CustomEvent('climate:highlight-hazards', {}));
    } else if (secId === 'predictions') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
      window.dispatchEvent?.(new CustomEvent('climate:prediction-horizon-changed', { detail: { horizon: '60m' } }));
    } else if (secId === 'compound') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
    } else if (secId === 'impact') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
    } else if (secId === 'evacuation') {
      store.setUiMode?.(CLIMATE_MODES.EMERGENCY);
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
      window.dispatchEvent?.(new CustomEvent('climate:highlight-evac-corridors', {}));
    } else if (secId === 'simulation') {
      store.setUiMode?.(CLIMATE_MODES.SIMULATION);
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'simulation' } }));
    } else if (secId === 'datasources') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'overview' } }));
    } else if (secId === 'aicommand') {
      store.setUiMode?.(CLIMATE_MODES.AI);
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'ai' } }));
    } else if (secId === 'system') {
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'overview' } }));
    }
  }

  // Floating Map Layers popover
  const mapLayersBtn = container.querySelector('#ce-map-layers-toggle-btn');
  const mapLayersPopover = container.querySelector('#ce-map-layers-popover');
  mapLayersBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    mapLayersPopover?.classList.toggle('hidden');
  });

  if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
    document.addEventListener('click', (e) => {
      if (mapLayersPopover && !mapLayersPopover.contains(e.target) && e.target !== mapLayersBtn) {
        mapLayersPopover.classList.add('hidden');
      }
    });
  }

  // Layer toggles binding
  const layerButtons = Array.from(container.querySelectorAll('.ce-layer-toggle-btn'));
  layerButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const layerId = btn.getAttribute('data-layer');
      if (layerId && typeof store.toggleLayer === 'function') {
        store.toggleLayer(layerId);
      } else if (layerId && typeof store.dispatch === 'function') {
        store.dispatch({
          type: ACTION_TYPES.LAYER_VISIBILITY_CHANGED,
          payload: { layerId },
        });
      }
    });
  });

  // Interactive buttons in sub-navs
  container.querySelectorAll('.ce-nav-sub-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const horizon = btn.getAttribute('data-horizon');
      const simPreset = btn.getAttribute('data-sim');
      const aiMode = btn.getAttribute('data-ai');
      const action = btn.getAttribute('data-action');

      if (horizon) {
        container.querySelectorAll('[data-horizon]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        window.dispatchEvent?.(new CustomEvent('climate:prediction-horizon-changed', { detail: { horizon } }));
      } else if (simPreset) {
        window.dispatchEvent?.(new CustomEvent('climate:apply-sim-preset', { detail: { preset: simPreset } }));
        window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'simulation' } }));
      } else if (aiMode) {
        window.dispatchEvent?.(new CustomEvent('climate:ai-focus', { detail: { focus: aiMode } }));
        window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'ai' } }));
      } else if (action) {
        if (action === 'routes') {
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.40, longitude: 78.51, height: 35000, name: 'Safe Corridor NH-65' }
          }));
          window.dispatchEvent?.(new CustomEvent('climate:highlight-evac-corridors', {}));
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
        } else if (action === 'shelters') {
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.425, longitude: 78.540, height: 25000, name: 'Safe Shelter S3' }
          }));
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
        } else if (action === 'blocked') {
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.37, longitude: 78.47, height: 25000, name: 'Blocked Route (Bridge B)' }
          }));
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
        } else if (action === 'noroute') {
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.36, longitude: 78.44, height: 25000, name: 'Sector C Lowland (No-Route)' }
          }));
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
        } else if (action === 'cascade') {
          const dock = document.querySelector('#ce-causal-tracker-strip');
          dock?.scrollIntoView?.({ behavior: 'smooth' });
          dock?.classList.add('highlight-pulse');
          setTimeout(() => dock?.classList.remove('highlight-pulse'), 2000);
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
        } else if (action === 'infra') {
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.37, longitude: 78.47, height: 20000, name: 'Infrastructure Strain (Bridge B)' }
          }));
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
        } else if (action === 'deps') {
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
        } else if (action === 'pop' || action === 'vuln' || action === 'facilities') {
          window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'region' } }));
          window.dispatchEvent?.(new CustomEvent('climate:flyTo', {
            detail: { latitude: 17.385, longitude: 78.4867, height: 40000, name: 'Human Impact Sector' }
          }));
        }
      }
    });
  });

  // Floating Map Layers Checklist binding
  const mapOverlayCheckboxes = container.querySelectorAll('.ce-map-layers-popover input[type="checkbox"]');
  mapOverlayCheckboxes.forEach((cb) => {
    cb.addEventListener('change', () => {
      const filters = {};
      mapOverlayCheckboxes.forEach((input) => {
        const id = input.id.replace('ce-layer-toggle-', '');
        filters[id] = input.checked;
      });
      window.dispatchEvent?.(new CustomEvent('climate:layer-filter-changed', { detail: filters }));
    });
  });

  // Data sources live polling
  async function refreshDataSourcesStatus() {
    try {
      const res = await fetch('/api/v1/global/sources');
      if (res.ok) {
        const data = await res.json();
        const sources = data?.summary?.sources || [];
        sources.forEach((src) => {
          const row = container.querySelector(`#ce-src-${src.source_id}`);
          if (row) {
            const isOnline = src.status === 'ONLINE';
            const isOpt = src.status === 'NOT_CONNECTED' || src.source_id === 'esp32_mesh';
            const dotClass = isOnline ? 'online' : (isOpt ? 'optional' : 'unavailable');
            const dotSym = isOnline ? '●' : '○';
            const name = (src.name || src.source_id).toUpperCase();
            row.innerHTML = `<span class="ce-dot ${dotClass}">${dotSym}</span> ${name}: ${src.status}`;
          }
        });
      }
    } catch {}
  }
  refreshDataSourcesStatus();

  // State subscription for node counts, active layers, and metric channels
  const activeLayersBadge = container.querySelector('#ce-active-layers-badge');
  const sensorCountBadge = container.querySelector('#ce-sensor-count-badge');
  const nodesConnectedVal = container.querySelector('#ce-nodes-connected-val');
  const nodesStatusBadge = container.querySelector('#ce-nodes-status-badge');

  const tempVal = container.querySelector('#ce-temp-value');
  const tempBadge = container.querySelector('#ce-temp-badge');
  const rainVal = container.querySelector('#ce-rain-value');
  const rainBadge = container.querySelector('#ce-rain-badge');
  const soilVal = container.querySelector('#ce-soil-value');
  const soilBadge = container.querySelector('#ce-soil-badge');
  const aqiVal = container.querySelector('#ce-aqi-value');
  const aqiBadge = container.querySelector('#ce-aqi-badge');

  function updateFromState(state) {
    if (!state) return;

    // 1. Update layers
    if (state.layers) {
      let activeCount = 0;
      layerButtons.forEach((btn) => {
        const layerId = btn.getAttribute('data-layer');
        const isVisible = state.layers[layerId] === true;
        if (isVisible) activeCount++;
        btn.textContent = isVisible ? 'ON' : 'OFF';
        btn.setAttribute('aria-pressed', String(isVisible));
        btn.classList.toggle('active', isVisible);

        const dot = container.querySelector(`[data-layer-dot="${layerId}"]`);
        if (dot) dot.classList.toggle('active', isVisible);
      });
      if (activeLayersBadge) activeLayersBadge.textContent = `${activeCount} ACTIVE`;
    }

    // 2. Update sensor nodes count
    const nodeCount = state.nodes?.allIds?.length || 0;
    if (sensorCountBadge) sensorCountBadge.textContent = `${nodeCount} NODES`;
    if (nodesConnectedVal) nodesConnectedVal.textContent = String(nodeCount);
    if (nodesStatusBadge) {
      nodesStatusBadge.textContent = nodeCount > 0 ? `${nodeCount} ONLINE` : 'NO MESH';
      nodesStatusBadge.className = `ce-unavailable-badge ${nodeCount > 0 ? 'online' : ''}`;
    }

    // 3. Update Metric Channels (preserves numeric 0)
    const selectedId = state.ui?.selectedNodeId || (state.nodes?.allIds && state.nodes.allIds[0]);
    const activeReading = selectedId
      ? (state.telemetry?.byNodeId?.[selectedId] || state.telemetry?.latestByNodeId?.[selectedId] || null)
      : null;

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

    if (rainVal && rainBadge) {
      const rainAmount = activeReading?.rainfall ?? activeReading?.precipitation_rate;
      if (rainAmount !== null && rainAmount !== undefined) {
        rainVal.textContent = `${rainAmount} mm/h`;
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

    if (aqiVal && aqiBadge) {
      const aqiReading = activeReading?.air_quality ?? activeReading?.air_quality_index;
      if (aqiReading !== null && aqiReading !== undefined) {
        aqiVal.textContent = `${aqiReading}`;
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

    const channelFootnote = container.querySelector('#ce-channel-footnote');
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

  // Initial sync
  if (store && typeof store.getState === 'function') {
    updateFromState(store.getState());
  }

  const unsubscribe = store?.subscribe ? store.subscribe(() => {
    updateFromState(store.getState());
  }) : null;

  return {
    element: container,
    isSidebarOpen() {
      return sidebarOpen;
    },
    setSidebarOpen(open) {
      setSidebarOpen(open);
    },
    toggleSidebar() {
      setSidebarOpen(!sidebarOpen);
    },
    toggleSection(secId) {
      const targetSec = container.querySelector(`[data-section="${secId}"]`);
      if (targetSec) {
        targetSec.querySelector('.ce-section-trigger')?.click();
      }
    },
    destroy() {
      if (typeof unsubscribe === 'function') unsubscribe();
      if (typeof container?.remove === 'function') container.remove();
    },
  };
}
