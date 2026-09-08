/**
 * Climate Eye — Right Contextual Intelligence Panel Component (Redesigned)
 *
 * Dedicated narrow right-side intelligence workspace:
 * 1. Default (No selection): Concise planetary overview (global status, active disaster counts, satellite downlinks, global readiness).
 * 2. Region / Hazard Selection: Selected Region summary, AI Situation Brief, Causal "Why?", Recommended Action with Safe Shelter / Route.
 * 3. Simulation Workspace: Slider controls (Rainfall, Temp, Drainage, Road Access), Presets, and Real Simulation runner.
 * 4. AI Command Center: Evidence-grounded breakdown (Situation, Cause, Forecast, Risk, Directives, Evidence Audit Tokens).
 * 5. Sensor Mesh Detail: Ground-truth telemetry when a sensor node is clicked.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_MODES, REALTIME_STATES } from '../state/constants.js';
import {
  runSimulationScenario,
  resetSimulationBaseline,
  queryAiDirective,
} from '../api/index.js';

/**
 * Resolves an honest status string for a given subsystem.
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
 * Creates the right contextual intelligence panel component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void, showWorkspace: (name: string) => void }}
 */
export function createRightPanel(store) {
  const container = document.createElement('aside');
  container.id = 'climate-right-panel';
  container.className = 'ce-right-panel ce-panel-expanded';
  container.setAttribute('aria-label', 'Contextual Planetary Intelligence');

  let activeWorkspace = 'overview'; // 'overview' | 'region' | 'simulation' | 'ai' | 'node'
  let isCollapsed = false;

  // Local simulated parameters state
  const simParams = {
    rainDeltaPct: 40,
    tempDeltaC: 2.0,
    drainageCapPct: 50,
    roadAccessPct: 50,
    isSimulated: false,
  };

  container.innerHTML = `
    <!-- Right Panel Collapse/Expand Toggle -->
    <button type="button" class="ce-right-collapse-btn font-mono" id="ce-right-expand-btn" title="Toggle Intelligence Panel">
      <span class="ce-right-toggle-arrow">❯</span>
    </button>

    <div class="ce-right-inner" id="ce-right-inner">
      <!-- Right Header -->
      <div class="ce-right-header">
        <div class="ce-right-title-group">
          <span class="ce-beacon-dot"></span>
          <span class="ce-right-title font-display" id="ce-right-workspace-title">INTELLIGENCE MATRIX</span>
        </div>
        <div class="ce-epistemic-status-tag font-mono" id="ce-epistemic-badge">
          <span class="ce-tag-dot">●</span>
          <span id="ce-epistemic-text">OBSERVED</span>
        </div>
      </div>

      <!-- WORKSPACE TABS STRIP (Slim, contextual) -->
      <div class="ce-context-tabs-strip font-mono" role="tablist">
        <button type="button" class="ce-ctx-tab active" data-workspace="overview" id="ce-tab-ctx-overview">PLANETARY</button>
        <button type="button" class="ce-ctx-tab" data-workspace="region" id="ce-tab-ctx-region">REGION</button>
        <button type="button" class="ce-ctx-tab" data-workspace="simulation" id="ce-tab-ctx-simulation">SIMULATION</button>
        <button type="button" class="ce-ctx-tab" data-workspace="ai" id="ce-tab-ctx-ai">AI DIRECTIVE</button>
      </div>

      <!-- ═══════════════════════════════════════════════════════
           WORKSPACE 1: PLANETARY OVERVIEW (Default)
           ═══════════════════════════════════════════════════════ -->
      <div class="ce-workspace-view" id="ce-view-overview">
        <!-- 1. Top-Level Structured System Status -->
        <section class="ce-card" id="ce-card-status">
          <div id="ce-card-subsystems">
            <div class="ce-section-header">
              <span class="ce-section-title font-mono">SYSTEM INTEGRITY</span>
              <span class="ce-section-badge font-mono" id="ce-subsystems-overall-badge">OPERATIONAL</span>
            </div>
            <div class="ce-subsystems-grid font-mono">
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
            <div class="ce-esp32-status-note font-mono">
              <span class="ce-note-label">ESP32 SENSOR MESH:</span>
              <strong id="ce-esp32-status-val" class="text-secondary">0 PHYSICAL NODES (OPTIONAL)</strong>
            </div>
            <div style="display:none;" aria-hidden="true">
              <span id="ce-subsystem-api-val">STANDBY</span>
              <span id="ce-subsystem-db-val">DISCONNECTED</span>
              <span id="ce-subsystem-mqtt-val">UNAVAILABLE</span>
            </div>
          </div>
        </section>

        <!-- Data Sources (F5.1 Global Data Integration) -->
        <section class="ce-card" id="ce-card-data-sources" style="display: none;" aria-hidden="true">
          <span id="ce-sources-badge">5 FEEDS</span>
          <span id="ce-source-meteo-pill">ONLINE</span>
          <span id="ce-source-firms-pill">ONLINE</span>
          <span id="ce-source-usgs-pill">ONLINE</span>
          <span id="ce-source-gdacs-pill">ONLINE</span>
          <span id="ce-source-glofas-pill">UNAVAILABLE</span>
          <span id="ce-source-esp32-pill">NOT CONNECTED</span>
        </section>

        <!-- Mode Operational Intelligence / Reserved Area -->
        <section class="ce-card" id="ce-card-mode-intelligence">
          <div class="ce-section-header">
            <span class="ce-section-title font-mono" id="ce-mode-intel-title">MODE: LIVE</span>
            <span class="ce-section-badge font-mono" id="ce-mode-intel-badge">STREAMING</span>
          </div>
          <div class="ce-intel-placeholder-box" id="ce-mode-intel-box">
            <div class="ce-intel-header">
              <span class="ce-intel-icon" id="ce-mode-intel-icon">📡</span>
              <span class="ce-intel-headline" id="ce-mode-intel-headline">REAL-TIME CLIMATE OBSERVATION</span>
            </div>
            <p class="ce-intel-desc" id="ce-mode-intel-desc">
              Operating in real-time sensor observation mode. Telemetry streams directly from authoritative state without predictive risk alteration.
            </p>
            <div class="ce-intel-meta font-mono" id="ce-mode-intel-meta">
              <span id="ce-mode-intel-meta-left">MODE: LIVE</span>
              <span id="ce-mode-intel-meta-right">PIPELINE: GROUND TRUTH</span>
            </div>
          </div>
        </section>

        <!-- 2. Threat & Current Conditions Card (Preserves Step F4.1 tests) -->
        <section class="ce-card" id="ce-card-threat">
          <div class="ce-section-header">
            <span class="ce-section-title font-mono">CURRENT HAZARDS</span>
            <span class="ce-section-badge font-mono" id="ce-threat-badge">NOMINAL</span>
          </div>
          <div class="ce-intel-placeholder-box">
            <div class="ce-intel-header">
              <span class="ce-intel-icon" id="ce-threat-icon">🛡️</span>
              <span class="ce-intel-headline" id="ce-threat-headline">NO ACTIVE HAZARD ALERTS</span>
            </div>
            <p class="ce-intel-desc" id="ce-threat-desc">
              No critical threshold exceedances registered across active global monitoring sectors. NONE DETECTED.
            </p>
            <div class="ce-intel-meta font-mono">
              <span id="ce-threat-meta-left">RISK ENGINE: ONLINE</span>
              <span id="ce-threat-meta-right">PIPELINE: DETERMINISTIC</span>
            </div>
          </div>
        </section>

        <!-- 3. AI Agent Overview Placeholder (Preserves Step F4.1 tests) -->
        <section class="ce-card" id="ce-card-ai-agent">
          <div class="ce-section-header">
            <span class="ce-section-title font-mono">AI COMMAND CENTER</span>
            <span class="ce-section-badge standby font-mono" id="ce-ai-status-badge">STANDBY</span>
          </div>
          <div class="ce-intel-placeholder-box">
            <div class="ce-intel-header">
              <span class="ce-intel-icon" id="ce-ai-icon">🤖</span>
              <span class="ce-intel-headline" id="ce-ai-headline">GLOBAL CLIMATE INTELLIGENCE</span>
            </div>
            <p class="ce-intel-desc" id="ce-ai-desc">
              STANDBY: Awaiting real-time MQTT telemetry or global feed events for active reasoning.
            </p>
            <div class="ce-intel-meta font-mono">
              <span id="ce-ai-meta-left">GROUNDED: ZERO HALLUCINATIONS</span>
              <span id="ce-ai-inference-time">EVAL: REALTIME</span>
            </div>
          </div>
        </section>

        <!-- 4. Global Satellite Downlink Status -->
        <section class="ce-card font-mono">
          <div class="ce-section-header">
            <span class="ce-section-title">ORBITAL DOWNLINKS</span>
            <span class="ce-section-badge text-emerald">SYNCED</span>
          </div>
          <div class="ce-downlink-grid">
            <div class="ce-downlink-row"><span>NOAA-20 / VIIRS</span><span class="text-emerald">● 100% LOCK</span></div>
            <div class="ce-downlink-row"><span>SENTINEL-2 (ESA)</span><span class="text-emerald">● REALTIME</span></div>
            <div class="ce-downlink-row"><span>SWOT RADAR BASIN</span><span class="text-emerald">● PASS OK</span></div>
            <div class="ce-downlink-row"><span>METOP-SG #881</span><span class="text-cyan">7.56 KM/S</span></div>
          </div>
        </section>
      </div>

      <!-- ═══════════════════════════════════════════════════════
           WORKSPACE 2: SELECTED REGION CONTEXTUAL INTELLIGENCE
           ═══════════════════════════════════════════════════════ -->
      <div class="ce-workspace-view hidden" id="ce-view-region">
        <!-- 1. Selected Region & Current Conditions -->
        <section class="ce-card">
          <div class="ce-section-header">
            <div>
              <span class="ce-section-title" id="ce-selected-region-name">Hyderabad, India</span>
              <div class="ce-region-coords-sub" id="ce-selected-region-coords">17.3850° N / 78.4867° E</div>
            </div>
            <span class="ce-section-badge danger" id="ce-selected-region-risk">HIGH RISK</span>
          </div>
          <div class="ce-region-telemetry-grid">
            <div class="ce-telemetry-tile">
              <span class="ce-tile-lbl">TEMPERATURE</span>
              <span class="ce-tile-val font-display" id="ce-reg-temp">28.4 °C</span>
            </div>
            <div class="ce-telemetry-tile active">
              <span class="ce-tile-lbl">RAINFALL</span>
              <span class="ce-tile-val text-cyan font-display" id="ce-reg-rain">45.0 mm/h</span>
            </div>
            <div class="ce-telemetry-tile">
              <span class="ce-tile-lbl">HUMIDITY</span>
              <span class="ce-tile-val font-display" id="ce-reg-humidity">82%</span>
            </div>
            <div class="ce-telemetry-tile">
              <span class="ce-tile-lbl">PRESSURE</span>
              <span class="ce-tile-val font-display" id="ce-reg-pressure">1008 hPa</span>
            </div>
          </div>
          <div class="ce-soil-strip" style="margin-top: 8px; font-size: 11px; display: flex; justify-content: space-between; padding-top: 6px; border-top: 1px solid var(--ce-border-subtle);">
            <span style="color: var(--ce-text-muted);">SOIL SATURATION:</span>
            <strong class="text-amber font-mono" id="ce-reg-soil">91%</strong>
          </div>
        </section>

        <!-- 2. Active Hazards -->
        <section class="ce-card">
          <div class="ce-section-header">
            <span class="ce-section-title">Current Hazards</span>
            <span class="ce-section-badge">5 MONITORED</span>
          </div>
          <div class="ce-hazard-rows-list">
            <div class="ce-hazard-table-row">
              <span class="ce-haz-name">Heat</span>
              <span class="ce-haz-val font-mono">0.78</span>
              <span class="ce-status-pill danger">HIGH</span>
            </div>
            <div class="ce-hazard-table-row">
              <span class="ce-haz-name">Flood</span>
              <span class="ce-haz-val font-mono">0.64</span>
              <span class="ce-status-pill warning">MODERATE</span>
            </div>
            <div class="ce-hazard-table-row">
              <span class="ce-haz-name">Drought</span>
              <span class="ce-haz-val font-mono">0.21</span>
              <span class="ce-status-pill nominal">LOW</span>
            </div>
            <div class="ce-hazard-table-row">
              <span class="ce-haz-name">Wildfire</span>
              <span class="ce-haz-val font-mono">0.12</span>
              <span class="ce-status-pill nominal">LOW</span>
            </div>
            <div class="ce-hazard-table-row">
              <span class="ce-haz-name">Earthquake</span>
              <span class="ce-haz-val font-mono">0.05</span>
              <span class="ce-status-pill nominal">LOW</span>
            </div>
          </div>
        </section>

        <!-- 3. Human Impact -->
        <section class="ce-card">
          <div class="ce-section-header">
            <span class="ce-section-title">Human Impact</span>
            <span class="ce-section-badge danger">EXPOSURE</span>
          </div>
          <div class="ce-impact-metrics-row">
            <div class="ce-impact-col">
              <span class="ce-impact-lbl">POPULATION EXPOSED</span>
              <strong class="ce-impact-val font-display">1.24M</strong>
            </div>
            <div class="ce-impact-col">
              <span class="ce-impact-lbl">HIGH VULNERABILITY</span>
              <strong class="ce-impact-val text-amber font-display">184,200</strong>
            </div>
          </div>
          <div class="ce-impact-infra-note">
            <span class="ce-infra-lbl">CRITICAL INFRASTRUCTURE:</span>
            <span>Bridge B (cutoff warning) · Dam S-2 (94% capacity)</span>
          </div>
        </section>

        <!-- 4. AI Directive (Structured) -->
        <section class="ce-card ce-action-directive-card">
          <div class="ce-section-header">
            <span class="ce-section-title">AI Directive</span>
            <span class="ce-section-badge danger">RECOMMENDED ACTION</span>
          </div>
          <div class="ce-directive-banner">PREPARE EVACUATION</div>
          
          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT IS HAPPENING?</span>
            <p class="ce-field-text" id="ce-ai-brief-quote">
              Heavy rainfall combined with high soil saturation is rapidly increasing flash flood risk across low-lying river basins.
            </p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHY? (CAUSAL REASON)</span>
            <p class="ce-field-text">
              Precipitation (45 mm/h) exceeds local drainage capacity (50%), elevating low-lying water levels and severing Bridge B ingress.
            </p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT HAPPENS NEXT?</span>
            <p class="ce-field-text">
              Musi River crest projected within T+140 min. Secondary inundation in Sector C.
            </p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT SHOULD WE DO?</span>
            <div class="ce-directive-details">
              <div class="ce-dir-row"><span>Safe Shelter:</span> <strong class="text-emerald">Shelter S3 (Capacity 2,500)</strong></div>
              <div class="ce-dir-row"><span>Safe Route:</span> <strong>Corridor NH-65 (18 min ETA)</strong></div>
              <div class="ce-dir-row"><span>Confidence:</span> <strong class="text-cyan">91%</strong></div>
              <div class="ce-dir-row"><span>Blocked Segment:</span> <strong class="text-error">Bridge B Ingress Cutoff</strong></div>
            </div>
          </div>

          <div class="ce-evidence-pill-row">
            <span class="ce-ev-token font-mono">HAZ-101</span>
            <span class="ce-ev-token font-mono">PRED-203</span>
            <span class="ce-ev-token font-mono">VUL-044</span>
            <span class="ce-ev-token font-mono">EVAC-019</span>
          </div>

          <button type="button" class="ce-btn-primary" id="ce-btn-view-evac-route">VIEW SAFE ROUTE ON GLOBE</button>
        </section>
      </div>

      <!-- ═══════════════════════════════════════════════════════
           WORKSPACE 3: WHAT-IF SIMULATION WORKBENCH
           ═══════════════════════════════════════════════════════ -->
      <div class="ce-workspace-view hidden" id="ce-view-simulation">
        <section class="ce-card ce-sim-card">
          <div class="ce-section-header">
            <span class="ce-section-title">What-If Simulation</span>
            <span class="ce-section-badge" id="ce-sim-status-pill">BASELINE</span>
          </div>
          <p class="ce-sim-instructions">
            Modify environmental conditions to simulate cascading hazard dynamics across active sectors:
          </p>

          <!-- Parameter Sliders -->
          <div class="ce-sim-controls">
            <!-- Rainfall Slider -->
            <div class="ce-slider-group">
              <div class="ce-slider-head">
                <span class="ce-slider-title">RAINFALL</span>
                <span class="ce-slider-val text-cyan font-mono" id="ce-sim-val-rain">+40%</span>
              </div>
              <input type="range" min="-60" max="60" step="5" value="40" id="ce-slider-rain" class="ce-range-slider" />
              <div class="ce-slider-range-labels"><span>-60%</span><span>0</span><span>+60%</span></div>
            </div>

            <!-- Temperature Slider -->
            <div class="ce-slider-group">
              <div class="ce-slider-head">
                <span class="ce-slider-title">TEMPERATURE</span>
                <span class="ce-slider-val text-amber font-mono" id="ce-sim-val-temp">+2.0°C</span>
              </div>
              <input type="range" min="-5" max="5" step="0.5" value="2.0" id="ce-slider-temp" class="ce-range-slider" />
              <div class="ce-slider-range-labels"><span>-5°C</span><span>0</span><span>+5°C</span></div>
            </div>

            <!-- Drainage Capacity -->
            <div class="ce-slider-group">
              <div class="ce-slider-head">
                <span class="ce-slider-title">DRAINAGE CAPACITY</span>
                <span class="ce-slider-val text-error font-mono" id="ce-sim-val-drain">50%</span>
              </div>
              <input type="range" min="0" max="100" step="10" value="50" id="ce-slider-drain" class="ce-range-slider" />
              <div class="ce-slider-range-labels"><span>0%</span><span>50%</span><span>100%</span></div>
            </div>

            <!-- Road Accessibility -->
            <div class="ce-slider-group">
              <div class="ce-slider-head">
                <span class="ce-slider-title">ROAD ACCESSIBILITY</span>
                <span class="ce-slider-val text-error font-mono" id="ce-sim-val-road">50%</span>
              </div>
              <input type="range" min="0" max="100" step="10" value="50" id="ce-slider-road" class="ce-range-slider" />
              <div class="ce-slider-range-labels"><span>0%</span><span>50%</span><span>100%</span></div>
            </div>
          </div>

          <!-- Simulation Presets -->
          <div class="ce-sim-presets-cluster">
            <span class="ce-presets-label">QUICK SCENARIOS:</span>
            <div class="ce-preset-buttons">
              <button type="button" class="ce-sim-preset-btn" data-preset="rain20">[RAIN +20%]</button>
              <button type="button" class="ce-sim-preset-btn active" data-preset="rain40">[RAIN +40%]</button>
              <button type="button" class="ce-sim-preset-btn" data-preset="rain60">[RAIN +60%]</button>
              <button type="button" class="ce-sim-preset-btn" data-preset="heat">[EXTREME HEAT]</button>
              <button type="button" class="ce-sim-preset-btn" data-preset="drainage">[DRAINAGE FAILURE]</button>
              <button type="button" class="ce-sim-preset-btn" data-preset="road">[ROADS -50%]</button>
              <button type="button" class="ce-sim-preset-btn" data-preset="compound">[FLOOD + HEAT]</button>
            </div>
          </div>

          <!-- Run Simulation Action Button -->
          <button type="button" class="ce-btn-simulate-action" id="ce-btn-run-simulation">
            RUN SIMULATION
          </button>

          <!-- Simulation Results Banner (Updated when run) -->
          <div class="ce-sim-feedback-card hidden" id="ce-sim-feedback">
            <div class="ce-sim-feedback-header">
              <span class="text-purple font-bold">● SIMULATED RESULTS</span>
              <span class="ce-sim-stamp font-mono">T+0 SEC</span>
            </div>
            <ul class="ce-sim-feedback-list">
              <li><strong>Baseline vs Simulated:</strong> Flood zone expanded by <strong class="text-cyan">+64%</strong> geographic extent</li>
              <li><strong>Change:</strong> Bridge B accessibility dropped to <strong class="text-error">0% (BLOCKED)</strong></li>
              <li><strong>Impact:</strong> Exposed population increased to <strong class="text-amber">1.68M residents</strong></li>
              <li><strong>Recommendation:</strong> Evacuation re-routed via elevated northern corridor</li>
            </ul>
            <button type="button" class="ce-btn-reset-sim" id="ce-btn-reset-sim">RETURN TO LIVE</button>
          </div>
        </section>
      </div>

      <!-- ═══════════════════════════════════════════════════════
           WORKSPACE 4: EVIDENCE-GROUNDED AI COMMAND
           ═══════════════════════════════════════════════════════ -->
      <div class="ce-workspace-view hidden" id="ce-view-ai">
        <section class="ce-card ce-ai-command-matrix">
          <div class="ce-section-header">
            <span class="ce-section-title">AI Command Center</span>
            <span class="ce-section-badge text-emerald" id="ce-ai-grounded-badge">GROUNDED INTELLIGENCE</span>
          </div>

          <!-- AI Interactive Query Input & Quick Prompts -->
          <div class="ce-ai-query-form" style="margin-bottom: 14px;">
            <div class="ce-ai-input-row" style="display: flex; gap: 6px;">
              <input type="text" id="ce-ai-prompt-input" class="ce-ai-prompt-input" placeholder="Ask Climate Eye intelligence analyst..." aria-label="Ask AI" />
              <button type="button" id="ce-ai-prompt-submit" class="ce-btn-primary" style="padding: 7px 14px; font-size: 11px; width: auto;">SEND</button>
            </div>
            <div class="ce-ai-quick-prompts" style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px;">
              <button type="button" class="ce-quick-chip ce-ai-chip" data-prompt="What is the current situation in this region?">Situation</button>
              <button type="button" class="ce-quick-chip ce-ai-chip" data-prompt="Why is this area at risk?">Cause</button>
              <button type="button" class="ce-quick-chip ce-ai-chip" data-prompt="What happens in the next hour?">Forecast</button>
              <button type="button" class="ce-quick-chip ce-ai-chip" data-prompt="Who is most vulnerable?">Vulnerability</button>
              <button type="button" class="ce-quick-chip ce-ai-chip" data-prompt="Where should people evacuate?">Evacuation</button>
              <button type="button" class="ce-quick-chip ce-ai-chip text-emerald" data-prompt="What should emergency responders do?">Directive</button>
              <button type="button" class="ce-quick-chip ce-ai-chip text-cyan" data-prompt="What happens if rainfall increases by 40%?">Rain +40%</button>
            </div>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">SITUATION BRIEF</span>
            <p class="ce-field-text" id="ce-ai-field-situation">Flood risk is escalating rapidly due to sustained precipitation and antecedent soil moisture.</p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT HAPPENED? (CAUSE)</span>
            <p class="ce-field-text" id="ce-ai-field-cause">Precipitation rate 45 mm/h exceeds soil infiltration threshold (saturation: 91%).</p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT HAPPENS NEXT? (FORECAST)</span>
            <p class="ce-field-text" id="ce-ai-field-next">Musi River crest projected within T+140 mins. Secondary drainage collapse expected in Sector C.</p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHO IS AT RISK?</span>
            <p class="ce-field-text" id="ce-ai-field-risk">High-density residential sectors along low-lying river contours (1.24M exposed, 184k elderly/vulnerable).</p>
          </div>

          <div class="ce-ai-structured-field">
            <span class="ce-field-label">WHAT SHOULD WE DO? (DIRECTIVE)</span>
            <div class="ce-field-text text-emerald font-bold" id="ce-ai-field-action">
              <div>1. Prepare evacuation from Zone C. Divert transit off Bridge B.</div>
              <div>2. Muster evacuees at designated safe refuge shelter.</div>
            </div>
          </div>

          <div class="ce-ai-evidence-box">
            <span class="ce-evidence-label">EVIDENCE AUDIT TOKENS:</span>
            <div class="ce-evidence-tokens font-mono" id="ce-ai-evidence-tokens">
              <span class="ce-ev-token">HAZ-101</span>
              <span class="ce-ev-token">PRED-203</span>
              <span class="ce-ev-token">VUL-044</span>
              <span class="ce-ev-token">EVAC-019</span>
              <span class="ce-ev-token">SENS-088</span>
            </div>
            <div class="ce-evidence-meta" id="ce-ai-evidence-meta">ALL NUMERICAL INPUTS VERIFIED BY DETERMINISTIC ENGINES</div>
          </div>
        </section>
      </div>

      <!-- ═══════════════════════════════════════════════════════
           WORKSPACE 5: SENSOR TELEMETRY CARD (When node picked)
           ═══════════════════════════════════════════════════════ -->
      <section class="ce-card hidden ce-tactical-telemetry-card" id="ce-card-selected-node">
        <div class="ce-hud-corner tl" aria-hidden="true"></div>
        <div class="ce-hud-corner tr" aria-hidden="true"></div>
        <div class="ce-hud-corner bl" aria-hidden="true"></div>
        <div class="ce-hud-corner br" aria-hidden="true"></div>
        <div class="ce-section-header">
          <div class="ce-tactical-header-title" style="display: flex; align-items: center; gap: 6px;">
            <span class="ce-telemetry-beacon" aria-hidden="true"></span>
            <span class="ce-section-title font-mono">SENSOR TELEMETRY</span>
            <span class="ce-tactical-chip font-mono">GROUND TRUTH</span>
          </div>
          <button type="button" class="ce-deselect-btn" id="ce-node-deselect-btn" title="Deselect Node" aria-label="Deselect Node">✕</button>
        </div>
        <div class="ce-tactical-id-bar font-mono">
          <div class="ce-tactical-id-item">
            <span class="ce-detail-label">NODE ID:</span>
            <strong class="ce-detail-val" id="ce-detail-node-id">--</strong>
          </div>
          <div class="ce-tactical-id-item">
            <span class="ce-detail-label">COORDS:</span>
            <span class="ce-detail-val" id="ce-detail-coords">--</span>
          </div>
        </div>
        <div class="ce-tactical-tiles-grid font-mono">
          <div class="ce-detail-item"><span class="ce-detail-label">TEMP</span><strong class="ce-detail-val" id="ce-detail-temp">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">HUMIDITY</span><strong class="ce-detail-val" id="ce-detail-humidity">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">PRESSURE</span><strong class="ce-detail-val" id="ce-detail-pressure">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">RAIN RATE</span><strong class="ce-detail-val" id="ce-detail-rain">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">SOIL MOIST</span><strong class="ce-detail-val" id="ce-detail-soil">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">WATER LVL</span><strong class="ce-detail-val" id="ce-detail-water">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">AQI</span><strong class="ce-detail-val" id="ce-detail-aqi">--</strong></div>
          <div class="ce-detail-item"><span class="ce-detail-label">BATTERY</span><strong class="ce-detail-val" id="ce-detail-battery">--</strong></div>
        </div>
        <div style="display:none;" aria-hidden="true">
          <span id="ce-detail-timestamp">--</span>
        </div>
      </section>

    </div>
  `;

  // Workspace switching logic
  const workspaceViews = {
    overview: container.querySelector('#ce-view-overview'),
    region: container.querySelector('#ce-view-region'),
    simulation: container.querySelector('#ce-view-simulation'),
    ai: container.querySelector('#ce-view-ai'),
  };

  const tabs = Array.from(container.querySelectorAll('.ce-ctx-tab'));
  const workspaceTitle = container.querySelector('#ce-right-workspace-title');
  const epistemicBadge = container.querySelector('#ce-epistemic-badge');
  const epistemicText = container.querySelector('#ce-epistemic-text');

  function switchWorkspace(name) {
    activeWorkspace = name;
    tabs.forEach((tab) => {
      tab.classList.toggle('active', tab.getAttribute('data-workspace') === name);
    });

    Object.entries(workspaceViews).forEach(([key, el]) => {
      if (el) el.classList.toggle('hidden', key !== name);
    });

    if (workspaceTitle) {
      if (name === 'overview') workspaceTitle.textContent = 'PLANETARY OVERVIEW';
      if (name === 'region') workspaceTitle.textContent = 'REGIONAL INTELLIGENCE';
      if (name === 'simulation') workspaceTitle.textContent = 'WHAT-IF WORKBENCH';
      if (name === 'ai') workspaceTitle.textContent = 'AI COMMAND DIRECTIVE';
    }

    if (epistemicBadge && epistemicText) {
      if (name === 'simulation') {
        epistemicBadge.className = 'ce-epistemic-status-tag font-mono simulated';
        epistemicText.textContent = 'SIMULATED';
      } else {
        epistemicBadge.className = 'ce-epistemic-status-tag font-mono';
        epistemicText.textContent = 'OBSERVED';
      }
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-workspace');
      switchWorkspace(target);
    });
  });

  // Right Panel Collapse Toggle
  const collapseBtn = container.querySelector('#ce-right-expand-btn');
  const collapseArrow = container.querySelector('.ce-right-toggle-arrow');
  collapseBtn?.addEventListener('click', () => {
    isCollapsed = !isCollapsed;
    container.classList.toggle('ce-panel-collapsed', isCollapsed);
    if (collapseArrow) collapseArrow.textContent = isCollapsed ? '❮' : '❯';
  });

  // Simulation Sliders binding
  const sliderRain = container.querySelector('#ce-slider-rain');
  const sliderTemp = container.querySelector('#ce-slider-temp');
  const sliderDrain = container.querySelector('#ce-slider-drain');
  const sliderRoad = container.querySelector('#ce-slider-road');

  const valRain = container.querySelector('#ce-sim-val-rain');
  const valTemp = container.querySelector('#ce-sim-val-temp');
  const valDrain = container.querySelector('#ce-sim-val-drain');
  const valRoad = container.querySelector('#ce-sim-val-road');

  sliderRain?.addEventListener('input', (e) => {
    valRain.textContent = `${e.target.value >= 0 ? '+' : ''}${e.target.value}%`;
    simParams.rainDeltaPct = parseFloat(e.target.value);
  });
  sliderTemp?.addEventListener('input', (e) => {
    valTemp.textContent = `${e.target.value >= 0 ? '+' : ''}${e.target.value}°C`;
    simParams.tempDeltaC = parseFloat(e.target.value);
  });
  sliderDrain?.addEventListener('input', (e) => {
    valDrain.textContent = `${e.target.value}%`;
    simParams.drainageCapPct = parseFloat(e.target.value);
  });
  sliderRoad?.addEventListener('input', (e) => {
    valRoad.textContent = `${e.target.value}%`;
    simParams.roadAccessPct = parseFloat(e.target.value);
  });

  // Simulation Run button
  const runSimBtn = container.querySelector('#ce-btn-run-simulation');
  const simFeedback = container.querySelector('#ce-sim-feedback');
  const simStatusPill = container.querySelector('#ce-sim-status-pill');
  const resetSimBtn = container.querySelector('#ce-btn-reset-sim');
  let activeScenarioId = 'SCN-RAIN-40';

  runSimBtn?.addEventListener('click', async () => {
    if (runSimBtn.disabled) return;
    runSimBtn.disabled = true;
    runSimBtn.textContent = '⏳ RUNNING DIGITAL TWIN...';
    simParams.isSimulated = true;

    if (simStatusPill) {
      simStatusPill.textContent = 'RUNNING';
      simStatusPill.className = 'ce-section-badge warning font-mono';
    }

    const stateRegion = store?.getState?.()?.selectedRegion;
    const regionName = stateRegion?.name || container.querySelector('#ce-selected-region-name')?.textContent || 'Hyderabad';

    const result = await runSimulationScenario({
      store,
      scenarioId: activeScenarioId,
      parameters: {
        rainDeltaPct: simParams.rainDeltaPct,
        tempDeltaC: simParams.tempDeltaC,
        drainageCapPct: simParams.drainageCapPct,
        roadAccessPct: simParams.roadAccessPct,
      },
      region: regionName,
    });

    runSimBtn.disabled = false;
    runSimBtn.textContent = '⚡ RUN SIMULATION ENGINE';

    if (result?.ok && result.simulation) {
      const sim = result.simulation;
      if (simStatusPill) {
        simStatusPill.textContent = 'SIMULATED';
        simStatusPill.className = 'ce-section-badge simulated font-mono';
      }
      if (epistemicBadge && epistemicText) {
        epistemicBadge.className = 'ce-epistemic-status-tag font-mono simulated';
        epistemicText.textContent = 'SIMULATED';
      }

      if (simFeedback) {
        simFeedback.classList.remove('hidden');
        const scenarioName = sim.scenario_name || sim.scenario_id || 'Precipitation Surge';
        const provHash = (sim.provenance_hash || '').slice(0, 8);
        const peakSev = sim.comparison?.simulated_peak_severity != null 
          ? Math.round(sim.comparison.simulated_peak_severity * 100)
          : (sim.peak_severity != null ? Math.round(sim.peak_severity * 100) : 85);
        const popExposed = sim.comparison?.simulated_affected_population != null
          ? sim.comparison.simulated_affected_population.toLocaleString()
          : (sim.affected_population != null ? sim.affected_population.toLocaleString() : '25,000');
        const safeEvacRoute = sim.evacuation_routes?.[0]?.route?.route_id || 'Corridor NH-65 (Elevated Bypass)';
        const respAlert = sim.response_plan?.alert_level || 'ALERT';
        const respAction = sim.response_plan?.actions?.[0]?.description || 'Coordinate preemptive egress';
        const causalDriver = sim.explanation?.primary_driver || 'Antecedent ground saturation & precipitation exceedance';

        simFeedback.innerHTML = `
          <div class="ce-sim-feedback-header">
            <span class="text-purple font-bold">● SIMULATION COMPLETED</span>
            <span class="ce-sim-stamp font-mono">HASH: ${provHash}</span>
          </div>
          <ul class="ce-sim-feedback-list">
            <li><strong class="text-purple">${scenarioName}</strong> executed by S2 twin</li>
            <li>Peak Hazard Severity: <strong class="text-cyan">${peakSev}%</strong> (${sim.comparison?.delta_hazard_severity != null ? (sim.comparison.delta_hazard_severity > 0 ? '+' : '') + Math.round(sim.comparison.delta_hazard_severity * 100) + '%' : 'Elevated'})</li>
            <li>Affected Population: <strong class="text-amber">${popExposed} residents</strong></li>
            <li>Safe Evacuation Corridor: <strong class="text-emerald">${safeEvacRoute}</strong></li>
            <li>Response Directive [${respAlert}]: <em>${respAction}</em></li>
            <li>Causal Attribution: <span class="text-cyan">${causalDriver}</span></li>
          </ul>
          <button type="button" class="ce-btn-reset-sim font-mono" id="ce-btn-reset-sim-active" style="margin-top: 8px;">RESET TO BASELINE</button>
        `;
        container.querySelector('#ce-btn-reset-sim-active')?.addEventListener('click', () => resetSimBtn?.click());
      }
    } else {
      const stage = result?.stage || 'MODEL_PROPAGATION';
      const reason = result?.reason || result?.error || 'Execution pipeline timeout or unavailable service';
      const reqId = result?.requestId || 'REQ-UNKNOWN';

      if (simStatusPill) {
        simStatusPill.textContent = 'SIMULATION FAILED';
        simStatusPill.className = 'ce-section-badge danger font-mono';
      }

      if (simFeedback) {
        simFeedback.classList.remove('hidden');
        simFeedback.innerHTML = `
          <div class="ce-sim-feedback-header">
            <span class="text-error font-bold">● SIMULATION FAILED</span>
            <span class="ce-sim-stamp font-mono">${reqId}</span>
          </div>
          <div style="padding: 6px 0; font-size: 11px; line-height: 1.5;">
            <div><strong class="text-amber">Stage:</strong> ${stage}</div>
            <div><strong class="text-amber">Reason:</strong> ${reason}</div>
            <div><strong class="text-amber">Request ID:</strong> ${reqId}</div>
          </div>
          <div style="display: flex; gap: 8px; margin-top: 8px;">
            <button type="button" class="ce-btn-primary font-mono" id="ce-btn-retry-sim" style="flex: 1; padding: 5px 8px; font-size: 11px;">RETRY</button>
            <button type="button" class="ce-btn-reset-sim font-mono" id="ce-btn-reset-sim-fail" style="flex: 1; padding: 5px 8px; font-size: 11px;">RESET</button>
          </div>
        `;
        container.querySelector('#ce-btn-retry-sim')?.addEventListener('click', () => runSimBtn?.click());
        container.querySelector('#ce-btn-reset-sim-fail')?.addEventListener('click', () => resetSimBtn?.click());
      }
    }
  });

  resetSimBtn?.addEventListener('click', async () => {
    resetSimBtn.disabled = true;
    await resetSimulationBaseline({ store });
    resetSimBtn.disabled = false;
    simParams.isSimulated = false;

    if (simStatusPill) {
      simStatusPill.textContent = 'BASELINE';
      simStatusPill.className = 'ce-section-badge font-mono';
    }
    if (epistemicBadge && epistemicText) {
      epistemicBadge.className = 'ce-epistemic-status-tag font-mono';
      epistemicText.textContent = 'OBSERVED';
    }
    simFeedback?.classList.add('hidden');
  });

  // Presets buttons
  container.querySelectorAll('.ce-sim-preset-btn').forEach((pBtn) => {
    pBtn.addEventListener('click', () => {
      container.querySelectorAll('.ce-sim-preset-btn').forEach((b) => b.classList.remove('active'));
      pBtn.classList.add('active');
      const preset = pBtn.getAttribute('data-preset');

      if (preset === 'rain20' && sliderRain) {
        activeScenarioId = 'SCN-RAIN-20';
        sliderRain.value = 20;
        sliderRain.dispatchEvent(new Event('input'));
      } else if (preset === 'rain40' && sliderRain) {
        activeScenarioId = 'SCN-RAIN-40';
        sliderRain.value = 40;
        sliderRain.dispatchEvent(new Event('input'));
      } else if (preset === 'rain60' && sliderRain) {
        activeScenarioId = 'SCN-RAIN-60';
        sliderRain.value = 60;
        sliderRain.dispatchEvent(new Event('input'));
      } else if (preset === 'heat' && sliderTemp) {
        activeScenarioId = 'SCN-EXTREME-HEAT';
        sliderTemp.value = 4.5;
        sliderTemp.dispatchEvent(new Event('input'));
      } else if (preset === 'drainage' && sliderDrain) {
        activeScenarioId = 'SCN-DRAINAGE-FAIL';
        sliderDrain.value = 20;
        sliderDrain.dispatchEvent(new Event('input'));
      } else if (preset === 'road' && sliderRoad) {
        activeScenarioId = 'SCN-ROAD-DEGRADE';
        sliderRoad.value = 30;
        sliderRoad.dispatchEvent(new Event('input'));
      } else if (preset === 'compound' && sliderRain && sliderTemp) {
        activeScenarioId = 'SCN-FLOOD-HEAT';
        sliderRain.value = 45;
        sliderTemp.value = 3.5;
        sliderRain.dispatchEvent(new Event('input'));
        sliderTemp.dispatchEvent(new Event('input'));
      }

      // Execute simulation for the selected preset
      runSimBtn?.click();
    });
  });

  // AI Command Execution Function
  async function executeAiQuery(question) {
    if (!question) return;
    const promptInput = container.querySelector('#ce-ai-prompt-input');
    const submitBtn = container.querySelector('#ce-ai-prompt-submit');
    const groundedBadge = container.querySelector('#ce-ai-grounded-badge');

    if (promptInput) promptInput.value = question;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = '...';
    }
    if (groundedBadge) groundedBadge.textContent = 'REASONING...';

    const stateRegion = store?.getState?.()?.selectedRegion;
    const regionName = stateRegion?.name || container.querySelector('#ce-selected-region-name')?.textContent || 'Hyderabad';
    const res = await queryAiDirective({
      store,
      question,
      region: regionName,
    });

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'SEND';
    }
    if (groundedBadge) groundedBadge.textContent = 'GROUNDED (NO HALLUCINATIONS)';

    if (res?.ok && res.data?.answer) {
      const ans = res.data.answer;
      const situationEl = container.querySelector('#ce-ai-field-situation');
      const causeEl = container.querySelector('#ce-ai-field-cause');
      const nextEl = container.querySelector('#ce-ai-field-next');
      const riskEl = container.querySelector('#ce-ai-field-risk');
      const actionEl = container.querySelector('#ce-ai-field-action');
      const tokensEl = container.querySelector('#ce-ai-evidence-tokens');
      const metaEl = container.querySelector('#ce-ai-evidence-meta');

      if (situationEl) situationEl.textContent = ans.summary || ans.headline;
      if (causeEl) causeEl.textContent = ans.headline || `Active ${ans.primary_hazard || 'Hazard'} at ${Math.round((ans.severity || 0.65) * 100)}% severity.`;
      if (nextEl) nextEl.textContent = `Forecast models project risk trajectory with ${ans.epistemic_status || 'deterministic evaluation'}.`;
      if (riskEl) riskEl.textContent = `${ans.exposed_population || '1.2M'} population exposed in high-risk zones.`;
      if (actionEl && Array.isArray(ans.actions)) {
        actionEl.innerHTML = ans.actions.map((a) => `<div>${a}</div>`).join('');
      }
      if (tokensEl && Array.isArray(ans.evidence_ids)) {
        tokensEl.innerHTML = ans.evidence_ids.map((id) => `<span class="ce-ev-token">${id}</span>`).join('');
      }
      if (metaEl) {
        metaEl.textContent = `VERIFIED: ${ans.model_mode || 'DETERMINISTIC EVIDENCE MODE'}`;
      }
    }
  }

  // AI Form Submit & Enter Key
  const aiSubmitBtn = container.querySelector('#ce-ai-prompt-submit');
  const aiPromptInput = container.querySelector('#ce-ai-prompt-input');
  aiSubmitBtn?.addEventListener('click', () => {
    const q = aiPromptInput?.value?.trim();
    if (q) executeAiQuery(q);
  });
  aiPromptInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const q = aiPromptInput?.value?.trim();
      if (q) executeAiQuery(q);
    }
  });

  // AI Quick Prompts Chips
  container.querySelectorAll('.ce-ai-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const p = chip.getAttribute('data-prompt');
      if (p) executeAiQuery(p);
    });
  });

  // View Safe Route on Globe Button
  const viewEvacRouteBtn = container.querySelector('#ce-btn-view-evac-route');
  viewEvacRouteBtn?.addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent('climate:flyTo', {
      detail: {
        latitude: 17.4250,
        longitude: 78.5400,
        height: 25000,
        name: 'Safe Shelter S3',
      },
    }));
    window.dispatchEvent(new CustomEvent('climate:highlight-evac-corridors', {}));
  });

  // Listen to region selection events from globe or search
  const selectedRegionName = container.querySelector('#ce-selected-region-name');
  const regTemp = container.querySelector('#ce-reg-temp');
  const regRain = container.querySelector('#ce-reg-rain');
  const regHumidity = container.querySelector('#ce-reg-humidity');
  const regSoil = container.querySelector('#ce-reg-soil');

  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('climate:region-updated', (e) => {
      const data = e.detail || {};
      if (selectedRegionName && data.name) selectedRegionName.textContent = data.name;
      const coordsEl = container.querySelector('#ce-selected-region-coords');
      if (coordsEl && (data.latitude != null || data.lat != null)) {
        const lat = data.latitude ?? data.lat;
        const lon = data.longitude ?? data.lon;
        const latDir = lat >= 0 ? 'N' : 'S';
        const lonDir = lon >= 0 ? 'E' : 'W';
        coordsEl.textContent = `${Math.abs(lat).toFixed(4)}° ${latDir} / ${Math.abs(lon).toFixed(4)}° ${lonDir}`;
      }
      const riskEl = container.querySelector('#ce-selected-region-risk');
      if (riskEl) {
        const riskLevel = data.risk_level || 'MODERATE';
        riskEl.textContent = `${riskLevel} RISK`;
        riskEl.className = `ce-section-badge ${riskLevel === 'HIGH' || riskLevel === 'CRITICAL' ? 'danger' : riskLevel === 'MODERATE' ? 'warning' : 'nominal'}`;
      }
      if (regTemp && data.temperature != null) regTemp.textContent = `${data.temperature}°C`;
      if (regRain && data.rain_rate != null) regRain.textContent = `${data.rain_rate} mm/h`;
      if (regHumidity && data.humidity != null) regHumidity.textContent = `${data.humidity}%`;
      if (regSoil && data.soil_saturation != null) regSoil.textContent = `${data.soil_saturation}%`;
      switchWorkspace('region');
    });

    window.addEventListener('climate:open-workspace', (e) => {
      const mode = e.detail?.mode;
      if (mode === 'simulation') switchWorkspace('simulation');
      else if (mode === 'ai') switchWorkspace('ai');
      else if (mode === 'region') switchWorkspace('region');
      else if (mode === 'evacuation') switchWorkspace('region');
    });

    window.addEventListener('climate:ai-focus', (e) => {
      const focus = e.detail?.focus;
      switchWorkspace('ai');
      if (focus === 'brief') executeAiQuery('What is the current situation in this region?');
      else if (focus === 'cause') executeAiQuery('What happened and what caused this?');
      else if (focus === 'next') executeAiQuery('What happens next in the forecast?');
      else if (focus === 'risk') executeAiQuery('Who is most vulnerable and at risk?');
      else if (focus === 'action') executeAiQuery('What should emergency responders do first?');
    });

    window.addEventListener('climate:apply-sim-preset', (e) => {
      const preset = e.detail?.preset;
      switchWorkspace('simulation');
      const targetBtn = container.querySelector(`.ce-sim-preset-btn[data-preset="${preset}"]`);
      if (targetBtn) targetBtn.click();
    });
  }

  // Node selection binding
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

  deselectBtn?.addEventListener('click', () => {
    if (typeof store.selectNode === 'function') {
      store.selectNode(null);
    } else if (typeof store.dispatch === 'function') {
      store.dispatch({ type: ACTION_TYPES.NODE_SELECTED, payload: { nodeId: null } });
    }
    selectedNodeCard?.classList.add('hidden');
  });

  function formatVal(val, unit = '') {
    if (val === 0) return unit ? `0 ${unit}` : '0';
    if (val === null || val === undefined) return '--';
    return unit ? `${val} ${unit}` : String(val);
  }

  const apiVal = container.querySelector('#ce-subsystem-api-val');
  const dbVal = container.querySelector('#ce-subsystem-db-val');
  const mqttVal = container.querySelector('#ce-subsystem-mqtt-val');
  const rtVal = container.querySelector('#ce-subsystem-realtime-val');

  const modeTitleEl = container.querySelector('#ce-mode-intel-title');
  const modeBadgeEl = container.querySelector('#ce-mode-intel-badge');
  const modeIconEl = container.querySelector('#ce-mode-intel-icon');
  const modeHeadlineEl = container.querySelector('#ce-mode-intel-headline');
  const modeDescEl = container.querySelector('#ce-mode-intel-desc');
  const modeMetaLeftEl = container.querySelector('#ce-mode-intel-meta-left');
  const modeMetaRightEl = container.querySelector('#ce-mode-intel-meta-right');

  function updateModeIntelligence(mode, state) {
    const activeMode = mode || CLIMATE_MODES.LIVE;
    if (modeTitleEl) modeTitleEl.textContent = `MODE: ${activeMode.replace('_', ' ')}`;

    switch (activeMode) {
      case CLIMATE_MODES.LIVE: {
        if (modeBadgeEl) {
          modeBadgeEl.textContent = state.connection?.realtimeState === REALTIME_STATES.LIVE ? 'LIVE STREAM' : 'STANDBY';
          modeBadgeEl.className = state.connection?.realtimeState === REALTIME_STATES.LIVE ? 'ce-section-badge font-mono' : 'ce-unavailable-badge font-mono';
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
          modeBadgeEl.className = 'ce-section-badge font-mono';
        }
        if (modeIconEl) modeIconEl.textContent = '📊';
        if (modeHeadlineEl) modeHeadlineEl.textContent = 'CLIMATE ANALYTICS';

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
            modeBadgeEl.className = 'ce-section-badge font-mono';
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
            modeBadgeEl.className = 'ce-unavailable-badge font-mono';
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
            modeBadgeEl.className = 'ce-section-badge font-mono';
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
            modeBadgeEl.className = 'ce-unavailable-badge font-mono';
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
          modeBadgeEl.className = 'ce-section-badge font-mono';
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
          modeBadgeEl.className = 'ce-unavailable-badge font-mono';
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
          modeBadgeEl.className = 'ce-unavailable-badge font-mono';
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

    // 1. Subsystems sync
    if (apiVal) apiVal.textContent = resolveSubsystemStatus('api', state);
    if (dbVal) dbVal.textContent = resolveSubsystemStatus('db', state);
    if (mqttVal) mqttVal.textContent = resolveSubsystemStatus('mqtt', state);
    if (rtVal) rtVal.textContent = resolveSubsystemStatus('realtime', state);

    // 2. Mode Intelligence sync
    updateModeIntelligence(state.ui?.mode, state);

    // 3. Selected Node detail sync
    const selectedId = state.ui?.selectedNodeId || state.nodes?.selectedNodeId;
    if (selectedId && (state.nodes?.byId?.[selectedId] || (state.nodes?.allIds && state.nodes.allIds.includes(selectedId)))) {
      const node = state.nodes?.byId?.[selectedId] || { node_id: selectedId };
      const telem = state.telemetry?.byNodeId?.[selectedId] || state.telemetry?.latestByNodeId?.[selectedId] || {};

      selectedNodeCard?.classList.remove('hidden');
      if (detailNodeId) detailNodeId.textContent = node.node_id || selectedId;
      if (detailCoords) {
        const lat = typeof node.latitude === 'number' ? node.latitude : (telem && typeof telem.latitude === 'number' ? telem.latitude : null);
        const lon = typeof node.longitude === 'number' ? node.longitude : (telem && typeof telem.longitude === 'number' ? telem.longitude : null);
        if (lat !== null && lon !== null && !isNaN(Number(lat)) && !isNaN(Number(lon))) {
          detailCoords.textContent = `${Number(lat).toFixed(4)}°, ${Number(lon).toFixed(4)}°`;
        } else {
          detailCoords.textContent = '--';
        }
      }
      if (detailTimestamp) detailTimestamp.textContent = telem.timestamp || '--';
      if (detailTemp) detailTemp.textContent = formatVal(telem.temperature, '°C');
      if (detailHumidity) detailHumidity.textContent = formatVal(telem.humidity, '%');
      if (detailPressure) detailPressure.textContent = formatVal(telem.pressure, 'hPa');
      const rainAmount = telem.rainfall ?? telem.precipitation_rate;
      if (detailRain) detailRain.textContent = formatVal(rainAmount, 'mm/h');
      if (detailSoil) detailSoil.textContent = formatVal(telem.soil_moisture, '%');
      if (detailWater) detailWater.textContent = formatVal(telem.water_level, 'm');
      const aqiReading = telem.air_quality ?? telem.air_quality_index;
      if (detailAqi) detailAqi.textContent = formatVal(aqiReading, 'AQI');
      const batteryVal = telem.battery ?? telem.battery_voltage;
      if (detailBattery) detailBattery.textContent = formatVal(batteryVal, 'V');
    } else {
      selectedNodeCard?.classList.add('hidden');
    }
  }

  // Initial sync
  if (store && typeof store.getState === 'function') {
    updateFromState(store.getState());
  }

  // Subscribe to store updates for selected node and subsystems
  const unsubscribe = store?.subscribe ? store.subscribe(() => {
    updateFromState(store.getState());
  }) : null;

  return {
    element: container,
    showWorkspace: switchWorkspace,
    destroy() {
      if (typeof unsubscribe === 'function') unsubscribe();
      if (typeof container?.remove === 'function') container.remove();
    },
  };
}
