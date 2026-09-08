/**
 * Climate Eye — Top Navigation Bar Component (F4.7)
 *
 * Renders the top navigation command-center bar:
 * - Brand indicator and title
 * - Mode navigation tabs: LIVE, ANALYTICS, RISK, SIMULATION, SENSOR MESH, AI, EMERGENCY
 * - WAI-ARIA tablist accessibility with keyboard arrow navigation
 * - Dispatches UI_MODE_CHANGED actions to the Climate Eye state store.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_MODES, ACTION_TYPES } from '../state/constants.js';

/**
 * Creates the top navigation component.
 *
 * @param {object} store - Authoritative Climate Eye store instance.
 * @returns {{ element: HTMLElement, destroy: () => void }}
 */
export function createTopNav(store) {
  const container = document.createElement('header');
  container.id = 'climate-top-nav';
  container.setAttribute('role', 'banner');
  container.setAttribute('aria-label', 'Climate Eye Command Navigation');

  const navModes = [
    { mode: CLIMATE_MODES.LIVE, label: 'LIVE' },
    { mode: CLIMATE_MODES.ANALYTICS, label: 'ANALYTICS' },
    { mode: CLIMATE_MODES.RISK, label: 'RISK' },
    { mode: CLIMATE_MODES.SIMULATION, label: 'SIMULATION' },
    { mode: CLIMATE_MODES.SENSOR_MESH, label: 'SENSOR MESH' },
    { mode: CLIMATE_MODES.AI, label: 'AI' },
    { mode: CLIMATE_MODES.EMERGENCY, label: 'EMERGENCY' },
  ];

  container.innerHTML = `
    <div class="ce-brand-group">
      <div class="ce-brand-radar" aria-hidden="true"></div>
      <span class="ce-brand-title">CLIMATIC EYE</span>
      <span class="ce-brand-badge">COMMAND CENTER</span>
    </div>
    <nav class="ce-nav-modes" role="tablist" aria-label="Command center operating modes">
      ${navModes
        .map(
          ({ mode, label }) => `
        <button
          type="button"
          class="ce-mode-btn"
          role="tab"
          data-mode="${mode}"
          aria-selected="false"
          tabindex="-1"
          id="ce-mode-btn-${mode.toLowerCase()}"
          aria-label="Mode: ${label}"
        >
          ${label}
        </button>
      `
        )
        .join('')}
    </nav>
    <div class="ce-top-right">
      <div class="ce-quick-chip">
        <span class="ce-quick-dot online" id="ce-top-status-dot"></span>
        <span id="ce-top-status-text">OPERATIONAL</span>
      </div>
    </div>
  `;

  const buttons = Array.from(container.querySelectorAll('.ce-mode-btn'));

  function updateActiveMode(currentMode) {
    buttons.forEach((btn) => {
      const btnMode = btn.getAttribute('data-mode');
      const isActive = btnMode === currentMode;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', String(isActive));
      btn.setAttribute('tabindex', isActive ? '0' : '-1');
    });
  }

  function activateMode(mode) {
    if (!mode || !store) return;
    if (typeof store.setUiMode === 'function') {
      store.setUiMode(mode);
    } else if (typeof store.dispatch === 'function') {
      store.dispatch({
        type: ACTION_TYPES.UI_MODE_CHANGED,
        payload: { mode },
      });
    }
  }

  // Click handlers
  buttons.forEach((btn, index) => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      activateMode(mode);
    });

    // Keyboard navigation (ArrowLeft, ArrowRight, Home, End)
    btn.addEventListener('keydown', (e) => {
      let targetIndex = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        targetIndex = (index + 1) % buttons.length;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        targetIndex = (index - 1 + buttons.length) % buttons.length;
      } else if (e.key === 'Home') {
        targetIndex = 0;
      } else if (e.key === 'End') {
        targetIndex = buttons.length - 1;
      }

      if (targetIndex >= 0) {
        e.preventDefault();
        const targetBtn = buttons[targetIndex];
        if (targetBtn) {
          targetBtn.focus();
          const targetMode = targetBtn.getAttribute('data-mode');
          activateMode(targetMode);
        }
      }
    });
  });

  const statusDot = container.querySelector('#ce-top-status-dot');
  const statusText = container.querySelector('#ce-top-status-text');

  function updateSystemStatus(sysStatus) {
    if (!statusText) return;
    const s = (sysStatus || 'operational').toLowerCase();
    if (s === 'healthy' || s === 'ready' || s === 'operational') {
      statusText.textContent = 'OPERATIONAL';
      statusDot?.classList.add('online');
    } else if (s === 'loading') {
      statusText.textContent = 'INITIALIZING';
      statusDot?.classList.remove('online');
    } else if (s === 'degraded') {
      statusText.textContent = 'DEGRADED';
      statusDot?.classList.remove('online');
    } else {
      statusText.textContent = s.toUpperCase();
      statusDot?.classList.remove('online');
    }
  }

  // Sync initial state
  if (store && typeof store.getState === 'function') {
    const state = store.getState();
    const initialMode = state?.ui?.mode || CLIMATE_MODES.LIVE;
    updateActiveMode(initialMode);
    updateSystemStatus(state?.system?.status);
  }

  // Subscribe to store changes
  let unsubscribe = null;
  if (store && typeof store.subscribe === 'function') {
    unsubscribe = store.subscribe((state) => {
      const activeMode = state?.ui?.mode || CLIMATE_MODES.LIVE;
      updateActiveMode(activeMode);
      updateSystemStatus(state?.system?.status);
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
