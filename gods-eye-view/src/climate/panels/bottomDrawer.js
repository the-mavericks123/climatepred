/**
 * Climate Eye — Bottom Floating Controls Component (Redesigned)
 *
 * Replaces the screen-covering giant drawer with two lightweight, floating HUD controls:
 * 1. Subtle Temporal Prediction Timeline Bar (NOW ── +30m ── +60m ── +6h)
 * 2. Causal Cascade Vector Live Tracker (expandable/collapsible)
 *
 * Preserves public method interface:
 * - setActiveTab(tab)
 * - expand()
 * - collapse()
 *
 * Browser-safe: No Node.js core modules.
 */

export const DRAWER_TABS = Object.freeze({
  SIMULATION: 'SIMULATION',
  PREDICTIONS: 'PREDICTIONS',
  CASCADE: 'CASCADE',
  HUMAN_IMPACT: 'HUMAN_IMPACT',
  EVACUATION: 'EVACUATION',
  EVENT_FEED: 'EVENT_FEED',
});

/**
 * Creates the bottom floating controls component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void, setActiveTab: (tab: string) => void, expand: () => void, collapse: () => void }}
 */
export function createBottomDrawer(store) {
  const container = document.createElement('section');
  container.id = 'climate-bottom-drawer';
  container.className = 'ce-bottom-floating-dock';
  container.setAttribute('aria-label', 'Planetary Temporal & Causal Controls');

  let activeHorizon = 'now';
  let isCascadeExpanded = false;

  container.innerHTML = `
    <!-- Floating Causal Cascade Vector Tracker Strip -->
    <div class="ce-causal-tracker-dock font-mono" id="ce-causal-tracker-strip">
      <div class="ce-causal-dock-header">
        <button type="button" class="ce-causal-toggle-btn" id="ce-causal-toggle-btn" title="Toggle Causal Chain">
          <span class="ce-causal-tree-icon">⑂</span>
          <span class="ce-causal-label">CAUSAL CASCADE CHAIN</span>
          <span class="ce-causal-arrow-icon" id="ce-causal-arrow-icon">▴</span>
        </button>
      </div>

      <div class="ce-causal-nodes-flow" id="ce-causal-nodes-flow">
        <button type="button" class="ce-causal-pill active" id="ce-node-step-1" data-target="rain">
          <span class="ce-pill-pulse">●</span> HEAVY RAIN (45mm/h)
        </button>
        <span class="ce-causal-arrow">→</span>
        <button type="button" class="ce-causal-pill" id="ce-node-step-2" data-target="soil">
          SOIL SATURATION (91%)
        </button>
        <span class="ce-causal-arrow">→</span>
        <button type="button" class="ce-causal-pill amber" id="ce-node-step-3" data-target="flood">
          SURFACE FLASH FLOOD
        </button>
        <span class="ce-causal-arrow">→</span>
        <button type="button" class="ce-causal-pill error" id="ce-node-step-4" data-target="road">
          ROAD FAILURE (NH-44)
        </button>
        <span class="ce-causal-arrow">→</span>
        <button type="button" class="ce-causal-pill error" id="ce-node-step-5" data-target="hospital">
          HOSPITAL ACCESS LOSS
        </button>
        <span class="ce-causal-arrow">→</span>
        <button type="button" class="ce-causal-pill dim" id="ce-node-step-6" data-target="delay">
          EVACUATION DELAY (+45m)
        </button>
      </div>
    </div>

    <!-- Floating Temporal Timeline Control (NOW ── +30m ── +60m ── +6h) -->
    <div class="ce-temporal-timeline-dock font-mono" id="ce-temporal-timeline-dock">
      <div class="ce-timeline-track-wrap">
        <span class="ce-timeline-title">PREDICTION HORIZON:</span>
        <div class="ce-timeline-track">
          <button type="button" class="ce-timeline-step active" data-step="now">
            <span class="ce-step-dot"></span>
            <span class="ce-step-label">NOW</span>
          </button>
          <div class="ce-timeline-line"></div>
          <button type="button" class="ce-timeline-step" data-step="30m">
            <span class="ce-step-dot"></span>
            <span class="ce-step-label">+30m</span>
          </button>
          <div class="ce-timeline-line"></div>
          <button type="button" class="ce-timeline-step" data-step="60m">
            <span class="ce-step-dot"></span>
            <span class="ce-step-label">+60m</span>
          </button>
          <div class="ce-timeline-line"></div>
          <button type="button" class="ce-timeline-step" data-step="6h">
            <span class="ce-step-dot"></span>
            <span class="ce-step-label">+6h</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Hidden compatibility markers for legacy drawer references -->
    <div style="display:none;" aria-hidden="true">
      <div id="ce-dock-tabbar"></div>
      <div id="ce-dock-status-strip"></div>
      <div id="ce-dock-content"></div>
      <span id="ce-dock-global-text">ONLINE</span>
      <span id="ce-dock-rt-text">UNAVAILABLE</span>
      <span id="ce-dock-nodes-text">0</span>
      <span id="ce-dock-api-text">API</span>
      <span id="ce-dock-utc-clock">00:00:00 UTC</span>
    </div>
  `;

  // Timeline step buttons binding
  const timelineSteps = Array.from(container.querySelectorAll('.ce-timeline-step'));
  timelineSteps.forEach((stepBtn) => {
    stepBtn.addEventListener('click', () => {
      const step = stepBtn.getAttribute('data-step');
      activeHorizon = step;
      timelineSteps.forEach((b) => b.classList.toggle('active', b === stepBtn));

      window.dispatchEvent?.(new CustomEvent('climate:prediction-horizon-changed', {
        detail: { horizon: step },
      }));
    });
  });

  // Causal node click triggers camera zoom / highlight
  container.querySelectorAll('.ce-causal-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      container.querySelectorAll('.ce-causal-pill').forEach((p) => p.classList.remove('selected'));
      pill.classList.add('selected');
      const target = pill.getAttribute('data-target');

      window.dispatchEvent?.(new CustomEvent('climate:causal-node-picked', {
        detail: { target },
      }));
    });
  });

  // Causal tracker collapse/expand toggle
  const causalToggleBtn = container.querySelector('#ce-causal-toggle-btn');
  const causalFlow = container.querySelector('#ce-causal-nodes-flow');
  const causalArrowIcon = container.querySelector('#ce-causal-arrow-icon');
  causalToggleBtn?.addEventListener('click', () => {
    isCascadeExpanded = !isCascadeExpanded;
    causalFlow?.classList.toggle('hidden', isCascadeExpanded);
    if (causalArrowIcon) causalArrowIcon.textContent = isCascadeExpanded ? '▾' : '▴';
  });

  return {
    element: container,
    setActiveTab(tab) {
      if (tab === DRAWER_TABS.SIMULATION) {
        window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'simulation' } }));
      } else if (tab === DRAWER_TABS.PREDICTIONS) {
        // focus 60m
        const btn60 = container.querySelector('[data-step="60m"]');
        btn60?.click();
      } else if (tab === DRAWER_TABS.EVACUATION) {
        window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'evacuation' } }));
      }
    },
    expand() {
      // route to right panel expansion
      window.dispatchEvent?.(new CustomEvent('climate:open-workspace', { detail: { mode: 'simulation' } }));
    },
    collapse() {
      // no-op
    },
    destroy() {
      container.remove();
    },
  };
}
