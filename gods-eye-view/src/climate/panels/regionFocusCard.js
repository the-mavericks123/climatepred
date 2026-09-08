/**
 * Climate Eye — Compact Region Focus Intelligence Card (Redesigned)
 *
 * Implements the compact floating intelligence card pinned near selected
 * hazard zones on the 3D globe:
 * - Title: FLOOD RISK / HYDERABAD REGION
 * - Severity: 82% | Confidence: 94%
 * - Status: OBSERVED vs SIMULATED
 * - Environmental Telemetry: Rain rate 45 mm/h | Soil Saturation 91%
 * - Human Impact: 1.2M Exposed | Forecast +60 MIN
 * - Tactical Action Triggers: [PREDICT], [SIMULATE], [CASCADE], [EVACUATE]
 *
 * Browser-safe: No Node.js core modules.
 */

export function createRegionFocusCard(store, bottomDrawer) {
  const container = document.createElement('aside');
  container.id = 'ce-locked-target-card';
  container.className = 'ce-compact-target-card hidden';
  container.setAttribute('aria-label', 'Selected Hazard Intelligence Card');

  container.innerHTML = `
    <button type="button" class="ce-popover-close-btn" id="ce-target-close-btn" title="Close Intelligence Card">✕</button>

    <!-- Card Header -->
    <div class="ce-target-card-header">
      <div class="ce-target-type-badge font-mono" id="ce-target-type-badge">
        <span class="ce-badge-pulse">●</span>
        <span id="ce-target-hazard-type">FLOOD RISK</span>
      </div>
      <div class="ce-target-epistemic-status font-mono" id="ce-target-epistemic-status">OBSERVED</div>
    </div>

    <h3 class="ce-target-region-name font-display" id="ce-target-city-name">HYDERABAD REGION</h3>
    <div class="ce-target-coords font-mono" id="ce-target-coords-text">17.3850° N, 78.4867° E</div>

    <!-- Core Risk Matrix Grid -->
    <div class="ce-target-metrics-matrix font-mono">
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">SEVERITY</span>
        <span class="ce-cell-val text-cyan font-bold" id="ce-target-flood-pct">82%</span>
      </div>
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">CONFIDENCE</span>
        <span class="ce-cell-val text-emerald font-bold" id="ce-target-conf">94%</span>
      </div>
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">RAIN RATE</span>
        <span class="ce-cell-val text-cyan" id="ce-target-rain">45 mm/h</span>
      </div>
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">SOIL SAT</span>
        <span class="ce-cell-val text-amber" id="ce-target-soil-pct">91%</span>
      </div>
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">POPULATION</span>
        <span class="ce-cell-val" id="ce-target-pop-val">1.2M EXPOSED</span>
      </div>
      <div class="ce-matrix-cell">
        <span class="ce-cell-label">FORECAST</span>
        <span class="ce-cell-val text-cyan" id="ce-target-forecast-horizon">+60 MIN</span>
      </div>
    </div>

    <!-- Tactical Action Triggers Strip -->
    <div class="ce-target-actions-strip font-mono">
      <button type="button" class="ce-tactical-btn pred" id="ce-target-btn-pred">[ PREDICT ]</button>
      <button type="button" class="ce-tactical-btn sim" id="ce-target-btn-sim">[ SIMULATE ]</button>
      <button type="button" class="ce-tactical-btn cascade" id="ce-target-btn-cascade">[ CASCADE ]</button>
      <button type="button" class="ce-tactical-btn evac" id="ce-target-btn-evac">[ EVACUATE ]</button>
    </div>

    <!-- Hidden compatibility markers -->
    <div style="display:none;" aria-hidden="true">
      <span id="ce-target-temp">28.4°C</span>
      <span id="ce-target-humid">82%</span>
      <span id="ce-target-heat-pct">64%</span>
      <span id="ce-target-vuln-val">72%</span>
      <span id="ce-target-action-badge">PREPARE EVACUATION</span>
      <span id="ce-target-severity-level">TIER-1</span>
      <div id="ce-target-flood-fill"></div>
      <div id="ce-target-heat-fill"></div>
    </div>
  `;

  const closeBtn = container.querySelector('#ce-target-close-btn');
  closeBtn?.addEventListener('click', () => {
    container.classList.add('hidden');
  });

  const predBtn = container.querySelector('#ce-target-btn-pred');
  const simBtn = container.querySelector('#ce-target-btn-sim');
  const cascadeBtn = container.querySelector('#ce-target-btn-cascade');
  const evacBtn = container.querySelector('#ce-target-btn-evac');

  predBtn?.addEventListener('click', () => {
    window.dispatchEvent?.(new CustomEvent('climate:prediction-horizon-changed', { detail: { horizon: '60m' } }));
  });

  simBtn?.addEventListener('click', () => {
    window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'simulation' } }));
  });

  cascadeBtn?.addEventListener('click', () => {
    const dock = document.querySelector('#ce-causal-tracker-strip');
    dock?.scrollIntoView?.({ behavior: 'smooth' });
    dock?.classList.add('highlight-pulse');
    setTimeout(() => dock?.classList.remove('highlight-pulse'), 2000);
  });

  evacBtn?.addEventListener('click', () => {
    window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
    window.dispatchEvent?.(new CustomEvent('climate:highlight-evac-corridors', {}));
  });

  // Listen to hazard selection events from Cesium globe picking
  const onHazardSelected = (e) => {
    const data = e.detail || {};
    const type = (data.hazard_type || data.event_type || 'FLOOD').toUpperCase();
    const typeBadge = container.querySelector('#ce-target-hazard-type');
    const regionName = container.querySelector('#ce-target-city-name');
    const coords = container.querySelector('#ce-target-coords-text');
    const floodPct = container.querySelector('#ce-target-flood-pct');
    const conf = container.querySelector('#ce-target-conf');
    const epistemic = container.querySelector('#ce-target-epistemic-status');
    const rain = container.querySelector('#ce-target-rain');

    if (typeBadge) typeBadge.textContent = `${type} RISK`;
    if (regionName) regionName.textContent = data.title || (data.name ? `${data.name} REGION` : 'HYDERABAD REGION');
    if (coords && data.center) {
      coords.textContent = `${Math.abs(data.center.latitude).toFixed(4)}° N, ${Math.abs(data.center.longitude).toFixed(4)}° E`;
    }
    if (floodPct && data.severity != null) {
      floodPct.textContent = `${(data.severity * 100).toFixed(0)}%`;
    }
    if (conf && data.confidence != null) {
      conf.textContent = `${(data.confidence * 100).toFixed(0)}%`;
    }
    if (epistemic) {
      epistemic.textContent = (data.epistemic_status || (data.simulated ? 'SIMULATED' : 'OBSERVED')).toUpperCase();
      epistemic.className = `ce-target-epistemic-status font-mono ${data.simulated ? 'simulated' : ''}`;
    }
    if (rain && data.precipitation_rate != null) {
      rain.textContent = `${data.precipitation_rate} mm/h`;
    }

    container.classList.remove('hidden');
  };

  const onSimulationApplied = (e) => {
    const epistemic = container.querySelector('#ce-target-epistemic-status');
    const floodPct = container.querySelector('#ce-target-flood-pct');
    const rain = container.querySelector('#ce-target-rain');

    if (epistemic) {
      epistemic.textContent = 'SIMULATED';
      epistemic.className = 'ce-target-epistemic-status font-mono simulated';
    }
    if (floodPct) floodPct.textContent = '94%';
    if (rain && e.detail?.rainMultiplier) {
      rain.textContent = `${(45 * e.detail.rainMultiplier).toFixed(0)} mm/h`;
    }
  };

  const onSimulationReset = () => {
    const epistemic = container.querySelector('#ce-target-epistemic-status');
    const floodPct = container.querySelector('#ce-target-flood-pct');
    const rain = container.querySelector('#ce-target-rain');

    if (epistemic) {
      epistemic.textContent = 'OBSERVED';
      epistemic.className = 'ce-target-epistemic-status font-mono';
    }
    if (floodPct) floodPct.textContent = '82%';
    if (rain) rain.textContent = '45 mm/h';
  };

  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('climate:hazard-selected', onHazardSelected);
    window.addEventListener('climate:simulation-applied', onSimulationApplied);
    window.addEventListener('climate:simulation-reset', onSimulationReset);
  }

  return {
    element: container,
    destroy() {
      if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
        window.removeEventListener('climate:hazard-selected', onHazardSelected);
        window.removeEventListener('climate:simulation-applied', onSimulationApplied);
        window.removeEventListener('climate:simulation-reset', onSimulationReset);
      }
      container.remove();
    },
  };
}
