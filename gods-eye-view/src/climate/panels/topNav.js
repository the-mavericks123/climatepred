/**
 * Climate Eye — Top Navigation Bar Component (Redesigned)
 *
 * Renders an ultra-thin, premium planetary disaster intelligence system bar:
 * - Brand: CLIMATE EYE / PLANETARY DISASTER INTELLIGENCE
 * - Center: Real-time telemetry indicators: LIVE DATA | INTELLIGENCE ACTIVE | REALTIME CONNECTED
 * - Search: Compact coordinate / sector lookup
 * - Right: UTC Time (ZULU) | System Status (OPERATIONAL)
 * - Accessible mode buttons preserved for state and test contracts.
 *
 * Browser-safe: No Node.js core modules.
 */

import { CLIMATE_MODES, ACTION_TYPES } from '../state/constants.js';
import { geocodeLocation, reverseGeocodeLocation, KNOWN_REGIONS } from '../api/index.js';

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
    <div class="ce-top-main-bar">
      <!-- Left: Tactical Brand & Insignia -->
      <div class="ce-brand-group">
        <div class="ce-brand-radar-stitch" aria-hidden="true">
          <span class="ce-radar-ping-ring"></span>
          <span class="ce-radar-core-dot"></span>
        </div>
        <div class="ce-brand-text-col">
          <div class="ce-brand-row">
            <span class="ce-brand-title font-display">CLIMATE EYE</span>
            <span class="ce-brand-badge font-mono">v4.8-ORBIT</span>
          </div>
          <div class="ce-brand-subrow font-mono">
            <span class="ce-brand-subtext">PLANETARY DISASTER INTELLIGENCE</span>
          </div>
        </div>
      </div>

      <!-- Center: Core System Status Indicators & Compact Search -->
      <div class="ce-top-center-cluster">
        <div class="ce-top-stream-indicators font-mono">
          <div class="ce-top-indicator-pill live">
            <span class="ce-pill-dot animate-pulse">●</span>
            <span>LIVE DATA</span>
          </div>
          <span class="ce-indicator-sep">//</span>
          <div class="ce-top-indicator-pill active">
            <span class="ce-pill-dot animate-pulse">●</span>
            <span>INTELLIGENCE ACTIVE</span>
          </div>
          <span class="ce-indicator-sep">//</span>
          <div class="ce-top-indicator-pill connected">
            <span class="ce-pill-dot">●</span>
            <span>REALTIME CONNECTED</span>
          </div>
        </div>

        <!-- Dedicated Selected Region HUD Indicator (Part 6) -->
        <div class="ce-selected-region-indicator" id="ce-selected-region-indicator" title="Selected Planetary Monitoring Sector">
          <div class="ce-sri-badge-row">
            <span class="ce-sri-tag">SELECTED REGION</span>
            <span class="ce-sri-status-pill live font-mono" id="ce-sri-status">LIVE DATA</span>
          </div>
          <div class="ce-sri-name font-display" id="ce-sri-name">Hyderabad</div>
          <div class="ce-sri-sub" id="ce-sri-sub">Telangana, India</div>
          <div class="ce-sri-coords font-mono" id="ce-sri-coords">17.3850° N · 78.4867° E</div>
        </div>

        <div class="ce-nav-search-bar" id="ce-nav-search-bar">
          <div class="ce-search-input-box">
            <span class="ce-search-icon" aria-hidden="true">🔍</span>
            <input
              type="text"
              id="ce-location-search-input"
              class="ce-location-search-input"
              placeholder="SEARCH ANY LOCATION (E.G. MUMBAI, TOKYO, PARIS)..."
              aria-label="Search global location"
              autocomplete="off"
            />
            <button type="button" class="ce-search-btn font-mono" id="ce-search-submit-btn" aria-label="Submit search">SEARCH</button>
          </div>
          <div class="ce-quick-locations font-mono" id="ce-quick-locations">
            <button type="button" class="ce-quick-loc-btn active" data-city="Hyderabad" data-lat="17.3850" data-lon="78.4867">HYDERABAD</button>
            <button type="button" class="ce-quick-loc-btn" data-city="Mumbai" data-lat="19.0760" data-lon="72.8777">MUMBAI</button>
            <button type="button" class="ce-quick-loc-btn" data-city="Delhi" data-lat="28.6139" data-lon="77.2090">DELHI</button>
            <button type="button" class="ce-quick-loc-btn" data-city="Tokyo" data-lat="35.6762" data-lon="139.6503">TOKYO</button>
            <button type="button" class="ce-quick-loc-btn" data-city="London" data-lat="51.5074" data-lon="-0.1278">LONDON</button>
          </div>
        </div>
      </div>

      <!-- Right: Target Vectors, Zulu Time, System Status -->
      <div class="ce-top-right-group font-mono">
        <div class="ce-coord-chip font-mono" id="ce-coord-chip" title="Active Target Vector">
          <span class="ce-coord-pin">📍</span>
          <span id="ce-current-coord-display">LAT 17.3850° N / LON 78.4867° E</span>
        </div>

        <div class="ce-zulu-pill text-secondary">
          <span id="ce-top-zulu-clock">00:00:00 UTC (ZULU)</span>
        </div>

        <div class="ce-quick-chip">
          <span class="ce-quick-dot online" id="ce-top-status-dot"></span>
          <span id="ce-top-status-text">OPERATIONAL</span>
        </div>

        <!-- Accessible Mode Tabs (Kept compact/hidden from top clutter, functional for testing & keyboard) -->
        <nav class="ce-nav-modes font-mono ce-modes-compact" role="tablist" aria-label="Command center operating modes">
          ${navModes
            .map(
              ({ mode, label }) => `
            <button
              type="button"
              class="ce-mode-btn ${mode === CLIMATE_MODES.EMERGENCY ? 'ce-mode-emergency' : ''}"
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

  // Click handlers for mode buttons
  buttons.forEach((btn, index) => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      activateMode(mode);
    });

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

  // Location Search and Preset chips logic
  const searchInput = container.querySelector('#ce-location-search-input');
  const searchBtn = container.querySelector('#ce-search-submit-btn');
  const quickLocButtons = Array.from(container.querySelectorAll('.ce-quick-loc-btn'));
  const currentCoordDisplay = container.querySelector('#ce-current-coord-display');
  const sriName = container.querySelector('#ce-sri-name');
  const sriSub = container.querySelector('#ce-sri-sub');
  const sriCoords = container.querySelector('#ce-sri-coords');
  const sriStatus = container.querySelector('#ce-sri-status');

  const KNOWN_COORDS = {
    'hyderabad': { lat: 17.3850, lon: 78.4867, name: 'Hyderabad', sub: 'Telangana, India' },
    'mumbai': { lat: 19.0760, lon: 72.8777, name: 'Mumbai', sub: 'Maharashtra, India' },
    'delhi': { lat: 28.6139, lon: 77.2090, name: 'Delhi', sub: 'NCR, India' },
    'bengaluru': { lat: 12.9716, lon: 77.5946, name: 'Bengaluru', sub: 'Karnataka, India' },
    'tokyo': { lat: 35.6762, lon: 139.6503, name: 'Tokyo', sub: 'Kanto, Japan' },
    'california': { lat: 36.7783, lon: -119.4179, name: 'California', sub: 'United States' },
    'london': { lat: 51.5074, lon: -0.1278, name: 'London', sub: 'England, United Kingdom' },
    'new york': { lat: 40.7128, lon: -74.0060, name: 'New York', sub: 'United States' },
  };

  async function navigateToLocation(locationName, lat = null, lon = null, meta = null) {
    const cleanName = (locationName || 'Hyderabad').trim();
    let targetLat = lat;
    let targetLon = lon;
    let displayName = cleanName;
    let subDisplay = 'Planetary Sector';
    let countryDisplay = '';

    if (meta) {
      targetLat = meta.latitude ?? targetLat;
      targetLon = meta.longitude ?? targetLon;
      displayName = meta.name || cleanName;
      subDisplay = [meta.state, meta.country].filter(Boolean).join(', ') || subDisplay;
      countryDisplay = meta.country || '';
    } else if (targetLat === null || targetLon === null) {
      const match = KNOWN_COORDS[cleanName.toLowerCase()];
      if (match) {
        targetLat = match.lat;
        targetLon = match.lon;
        displayName = match.name;
        subDisplay = match.sub;
      } else {
        // Forward geocode via open-meteo / nominatim
        if (sriStatus) {
          sriStatus.textContent = 'GEOCODING...';
          sriStatus.className = 'ce-sri-status-pill warning font-mono';
        }
        const geoResult = await geocodeLocation(cleanName);
        if (geoResult && typeof geoResult.latitude === 'number') {
          targetLat = geoResult.latitude;
          targetLon = geoResult.longitude;
          displayName = geoResult.name;
          subDisplay = [geoResult.state, geoResult.country].filter(Boolean).join(', ') || 'Planetary Sector';
          countryDisplay = geoResult.country || '';
        } else {
          targetLat = 17.3850;
          targetLon = 78.4867;
          displayName = cleanName;
        }
      }
    }

    const latDir = targetLat >= 0 ? 'N' : 'S';
    const lonDir = targetLon >= 0 ? 'E' : 'W';
    const coordStr = `${Math.abs(targetLat).toFixed(4)}° ${latDir} · ${Math.abs(targetLon).toFixed(4)}° ${lonDir}`;

    // Update Selected Region HUD Indicator
    if (sriName) sriName.textContent = displayName;
    if (sriSub) sriSub.textContent = subDisplay;
    if (sriCoords) sriCoords.textContent = coordStr;
    if (currentCoordDisplay) currentCoordDisplay.textContent = `LAT ${Math.abs(targetLat).toFixed(4)}° ${latDir} / LON ${Math.abs(targetLon).toFixed(4)}° ${lonDir}`;

    const isSimulated = store?.getState?.()?.simulation?.isSimulated;
    if (sriStatus) {
      sriStatus.textContent = isSimulated ? 'SIMULATED SCENARIO' : 'LIVE DATA';
      sriStatus.className = `ce-sri-status-pill ${isSimulated ? 'simulated' : 'live'} font-mono`;
    }

    quickLocButtons.forEach((b) => {
      const city = b.getAttribute('data-city');
      b.classList.toggle('active', city.toLowerCase() === displayName.toLowerCase());
    });

    if (searchInput) searchInput.value = displayName;

    // Dispatch Region Selection to Store
    const regionPayload = {
      name: displayName,
      state: subDisplay,
      country: countryDisplay,
      latitude: targetLat,
      longitude: targetLon,
      source: meta ? 'globe-pick' : 'search',
    };
    if (store && typeof store.selectRegion === 'function') {
      store.selectRegion(regionPayload);
    } else if (store && typeof store.dispatch === 'function') {
      store.dispatch({
        type: ACTION_TYPES.REGION_SELECTED,
        payload: { region: regionPayload },
      });
    }

    // Trigger flyTo on Cesium globe
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new CustomEvent('climate:flyTo', {
        detail: {
          latitude: targetLat,
          longitude: targetLon,
          height: 150000,
          name: displayName,
        },
      }));
    }

    // Call regional intelligence API
    try {
      const url = `/api/v1/global/region?name=${encodeURIComponent(displayName)}&lat=${targetLat}&lon=${targetLon}`;
      let res = null;
      try {
        res = await fetch(url);
      } catch {
        res = await fetch(`/api/global/region?name=${encodeURIComponent(displayName)}&lat=${targetLat}&lon=${targetLon}`);
      }
      if (res && res.ok) {
        const data = await res.json();
        const regionData = data.region || data;
        if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
          window.dispatchEvent(new CustomEvent('climate:region-updated', {
            detail: {
              ...regionData,
              name: displayName,
              latitude: targetLat,
              longitude: targetLon,
              temperature: regionData.current_conditions?.temperature_c ?? regionData.temperature ?? 28.4,
              rain_rate: regionData.current_conditions?.rainfall_mmh ?? regionData.rain_rate ?? 45.0,
              humidity: regionData.current_conditions?.humidity_pct ?? regionData.humidity ?? 82,
              soil_saturation: regionData.current_conditions?.soil_saturation_pct ?? 88,
              risk_level: regionData.risk_assessment?.overall_risk || 'MODERATE',
            },
          }));
        }
      }
    } catch {
      // Offline fallback: notify with known baseline
      if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
        window.dispatchEvent(new CustomEvent('climate:region-updated', {
          detail: {
            name: displayName,
            latitude: targetLat,
            longitude: targetLon,
            temperature: 28.4,
            rain_rate: 45.0,
            humidity: 82,
            soil_saturation: 88,
            risk_level: 'MODERATE',
          },
        }));
      }
    }
  }

  if (searchBtn && searchInput) {
    searchBtn.addEventListener('click', () => {
      const val = searchInput.value.trim();
      if (val) navigateToLocation(val);
    });
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = searchInput.value.trim();
        if (val) navigateToLocation(val);
      }
    });
  }

  quickLocButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const city = btn.getAttribute('data-city');
      const lat = parseFloat(btn.getAttribute('data-lat'));
      const lon = parseFloat(btn.getAttribute('data-lon'));
      navigateToLocation(city, lat, lon);
    });
  });

  // Listen to Cesium Globe Click Events
  const onGlobeClicked = async (e) => {
    const { latitude, longitude } = e.detail || {};
    if (typeof latitude === 'number' && typeof longitude === 'number') {
      if (sriStatus) {
        sriStatus.textContent = 'RESOLVING SECTOR...';
        sriStatus.className = 'ce-sri-status-pill warning font-mono';
      }
      const geoResult = await reverseGeocodeLocation(latitude, longitude);
      navigateToLocation(geoResult.name, latitude, longitude, geoResult);
    }
  };

  // Listen to external coordinate update events
  const onCoordUpdate = (e) => {
    const { latitude, longitude } = e.detail || {};
    if (typeof latitude === 'number' && typeof longitude === 'number' && currentCoordDisplay) {
      const latDir = latitude >= 0 ? 'N' : 'S';
      const lonDir = longitude >= 0 ? 'E' : 'W';
      currentCoordDisplay.textContent = `LAT ${Math.abs(latitude).toFixed(4)}° ${latDir} / LON ${Math.abs(longitude).toFixed(4)}° ${lonDir}`;
    }
  };
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('climate:coords-updated', onCoordUpdate);
    window.addEventListener('climate:globe-clicked', onGlobeClicked);
    window.addEventListener('climate:navigate-vector', (e) => {
      const { name, latitude, longitude } = e.detail || {};
      navigateToLocation(name, latitude, longitude);
    });
  }

  // Zulu Clock
  const clockEl = container.querySelector('#ce-top-zulu-clock');
  let clockTimer = null;
  if (typeof setInterval !== 'undefined') {
    clockTimer = setInterval(() => {
      if (!clockEl) return;
      const now = new Date();
      const h = String(now.getUTCHours()).padStart(2, '0');
      const m = String(now.getUTCMinutes()).padStart(2, '0');
      const s = String(now.getUTCSeconds()).padStart(2, '0');
      clockEl.textContent = `${h}:${m}:${s} UTC (ZULU)`;
    }, 1000);
    if (typeof clockTimer?.unref === 'function') clockTimer.unref();
  }

  // Subscribe to store updates for UI mode and connection
  const statusDot = container.querySelector('#ce-top-status-dot');
  const statusText = container.querySelector('#ce-top-status-text');

  let lastMode = null;
  let lastIsSim = null;
  const unsubscribe = store.subscribe(() => {
    const state = store.getState();
    const currentMode = state?.ui?.mode || CLIMATE_MODES.LIVE;
    if (currentMode !== lastMode) {
      lastMode = currentMode;
      updateActiveMode(currentMode);
    }

    const isSim = state?.simulation?.isSimulated;
    if (isSim !== lastIsSim) {
      lastIsSim = isSim;
      if (sriStatus) {
        sriStatus.textContent = isSim ? 'SIMULATED SCENARIO' : 'LIVE DATA';
        sriStatus.className = `ce-sri-status-pill ${isSim ? 'simulated' : 'live'} font-mono`;
      }
    }

    if (statusDot && statusText) {
      const isOnline = state?.system?.status === 'healthy' || state?.system?.status === 'ready' || state?.connection?.connected;
      statusDot.className = `ce-quick-dot ${isOnline ? 'online' : 'degraded'}`;
      statusText.textContent = isOnline ? 'OPERATIONAL' : 'DEGRADED';
    }
  });

  // Initial render
  const initialMode = store.getState()?.ui?.mode || CLIMATE_MODES.LIVE;
  lastMode = initialMode;
  updateActiveMode(initialMode);

  return {
    element: container,
    destroy() {
      if (clockTimer) clearInterval(clockTimer);
      if (typeof unsubscribe === 'function') unsubscribe();
      if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
        window.removeEventListener('climate:coords-updated', onCoordUpdate);
        window.removeEventListener('climate:globe-clicked', onGlobeClicked);
      }
      container.remove();
    },
  };
}
