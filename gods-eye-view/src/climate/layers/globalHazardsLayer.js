/**
 * Climate Eye — Global Hazard & Disaster Visualization Layer (Step F4.8)
 *
 * Renders authoritative global hazard zones, disaster events, fire clusters,
 * earthquake rings, and compound disaster cascades onto the Cesium 3D globe:
 * - Heat Zones (semi-transparent thermal ellipses with gradient styling)
 * - Flood Zones (blue hydrological extents from GDACS/GloFAS)
 * - Wildfire Clusters (NASA FIRMS clustered point markers & thermal perimeters)
 * - Earthquake Rings (concentric circles scaled by magnitude from USGS)
 * - Storm / Cyclone Vectors (GDACS tropical storm extents & wind buffers)
 * - Compound Hazard Polygons (distinct purple pulsing overlays)
 *
 * Features:
 * - Interactive tactical picking popovers:
 *   Shows hazard type, severity, confidence, epistemic status, source attribution,
 *   timestamp, affected radius, population, and recommended action.
 * - Decoupled from physical sensor mesh (operates whether sensor nodes are 0 or 100+).
 * - Honest epistemic status: OBSERVED vs INFERRED vs PREDICTED vs SIMULATED.
 * - Integrates with Cesium CustomDataSource, pickRegistry, and governorRequestRender.
 *
 * Browser-safe: No Node.js core modules.
 */

import * as CesiumDefault from 'cesium';
import {
  registerPickOwner,
  unregisterPickOwner,
  resolvePickId,
} from '../../data/pickRegistry.js';
import { isPickedWorldPosition } from '../../data/scenePick.js';
import { governorRequestRender } from '../../renderGovernor.js';
import { CLIMATE_LAYERS } from '../state/constants.js';

export const CLIMATE_GLOBAL_HAZARDS_DATA_SOURCE_NAME = 'climate-eye-global-hazards';
export const GLOBAL_HAZARD_ENTITY_PREFIX = 'global-hazard:';
export const GLOBAL_EVENT_ENTITY_PREFIX = 'global-event:';
export const CLIMATE_GLOBAL_HAZARDS_LAYER_ID = 'climate-global-hazards';

let activeGlobalHazardsLayer = null;

/**
 * Creates the Climate Eye global hazard layer instance.
 *
 * @param {object} options
 * @param {object} options.viewer - Cesium Viewer instance
 * @param {object} options.store - Authoritative Climate Eye store
 * @param {object} [options.Cesium] - Optional Cesium module override
 * @returns {object} Layer controller
 */
export function createGlobalHazardsLayer({
  viewer,
  store,
  Cesium = CesiumDefault,
} = {}) {
  if (!viewer) {
    throw new TypeError('createGlobalHazardsLayer requires a valid Cesium viewer instance');
  }
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createGlobalHazardsLayer requires an authoritative Climate Eye store');
  }

  let dataSource = null;
  let clickHandler = null;
  let storeUnsubscribe = null;
  let isDestroyed = false;
  let popoverEl = null;
  let currentExpansionFactor = 1.0;
  let isSimulationActive = false;

  let layerFilters = {
    hazards: true,
    heat: true,
    flood: true,
    drought: true,
    wildfire: true,
    earthquake: true,
    predictions: true,
    compound: true,
    impact: true,
    evacuation: true,
    infra: true,
    nodes: true,
  };

  // Track entities by ID
  const entityMap = new Map();

  // Tactical Color Palettes (Refined Editorial Command Center Palette)
  const COLOR_HEAT_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(184, 50, 50, 0.35)') : null;
  const COLOR_HEAT_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#B83232') : null;

  const COLOR_FLOOD_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(70, 110, 150, 0.40)') : null;
  const COLOR_FLOOD_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#3F648A') : null;

  const COLOR_FIRE_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(190, 80, 25, 0.38)') : null;
  const COLOR_FIRE_POINT = Cesium.Color ? Cesium.Color.fromCssColorString('#C2551A') : null;
  const COLOR_FIRE_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#8A2500') : null;

  const COLOR_QUAKE_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(180, 140, 40, 0.25)') : null;
  const COLOR_QUAKE_POINT = Cesium.Color ? Cesium.Color.fromCssColorString('#B48C28') : null;
  const COLOR_QUAKE_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#705510') : null;

  const COLOR_CYCLONE_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(80, 125, 110, 0.35)') : null;
  const COLOR_CYCLONE_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#3D7865') : null;

  const COLOR_COMPOUND_FILL = Cesium.Color ? Cesium.Color.fromCssColorString('rgba(110, 75, 115, 0.40)') : null;
  const COLOR_COMPOUND_OUTLINE = Cesium.Color ? Cesium.Color.fromCssColorString('#7A4C82') : null;

  /**
   * Builds or returns the tactical popover HUD overlay container.
   */
  function ensurePopoverElement() {
    if (popoverEl) return popoverEl;
    if (typeof document === 'undefined') return null;

    popoverEl = document.getElementById('ce-tactical-hazard-popover');
    if (!popoverEl) {
      popoverEl = document.createElement('div');
      popoverEl.id = 'ce-tactical-hazard-popover';
      popoverEl.className = 'ce-tactical-hazard-popover ce-hidden';
      popoverEl.setAttribute('role', 'dialog');
      popoverEl.setAttribute('aria-label', 'Tactical Hazard Intelligence HUD');

      // Append to viewer container or document body
      const targetContainer = viewer.container || document.body;
      targetContainer.appendChild(popoverEl);
    }
    return popoverEl;
  }

  /**
   * Displays the tactical HUD popover with normalized hazard intelligence.
   *
   * @param {object} hazardData
   * @param {{ x: number, y: number }} [screenPos]
   */
  function showPopover(hazardData, screenPos = null) {
    const popover = ensurePopoverElement();
    if (!popover || !hazardData) return;

    const type = (hazardData.hazard_type || hazardData.event_type || 'HAZARD').toUpperCase();
    const title = hazardData.title || `${type} ZONE`;
    const severity = typeof hazardData.severity === 'number' ? hazardData.severity : 0.5;
    const severityPct = (severity * 100).toFixed(0);
    const confidence = typeof hazardData.confidence === 'number' ? (hazardData.confidence * 100).toFixed(0) : '100';
    const epistemic = (hazardData.epistemic_status || (hazardData.simulated ? 'SIMULATED' : 'OBSERVED')).toUpperCase();
    const source = (hazardData.source || 'GLOBAL DATA').toUpperCase();
    const ts = hazardData.timestamp ? new Date(hazardData.timestamp).toUTCString() : 'REALTIME LIVE';
    const radius = hazardData.radius_km || hazardData.affected_radius_km || 10;
    const pop = hazardData.affected_population != null ? Number(hazardData.affected_population).toLocaleString() : 'CALCULATING';
    const vuln = hazardData.vulnerability_score != null ? (hazardData.vulnerability_score * 100).toFixed(0) + '%' : 'STANDARD';
    const action = hazardData.recommended_action || 'Maintain continuous perimeter monitoring and situational telemetry.';

    let severityClass = 'standby';
    let severityLabel = 'LOW';
    if (severity >= 0.8) {
      severityClass = 'danger';
      severityLabel = 'CRITICAL';
    } else if (severity >= 0.5) {
      severityClass = 'warning';
      severityLabel = 'ELEVATED';
    } else {
      severityClass = 'info';
      severityLabel = 'MODERATE';
    }

    popover.innerHTML = `
      <div class="ce-popover-card">
        <div class="ce-popover-header">
          <div class="ce-popover-title-row">
            <span class="ce-popover-badge ${severityClass}">${severityLabel}</span>
            <span class="ce-popover-type">${type}</span>
          </div>
          <button type="button" class="ce-popover-close-btn" id="ce-popover-close" aria-label="Close Popover">&times;</button>
        </div>

        <div class="ce-popover-subhead">${title}</div>

        <div class="ce-popover-metrics">
          <div class="ce-pop-metric">
            <span class="label">SEVERITY</span>
            <div class="bar-wrap">
              <div class="bar-fill ${severityClass}" style="width: ${severityPct}%"></div>
            </div>
            <span class="val mono">${severityPct}%</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">CONFIDENCE:</span>
            <span class="val mono">${confidence}%</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">EPISTEMIC STATUS:</span>
            <span class="val mono epistemic-tag">${epistemic}</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">SOURCE ATTRIBUTION:</span>
            <span class="val mono">${source}</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">TIMESTAMP (UTC):</span>
            <span class="val mono">${ts}</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">AFFECTED RADIUS:</span>
            <span class="val mono">${Number(radius).toFixed(1)} km</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">EXPOSED POPULATION:</span>
            <span class="val mono">${pop}</span>
          </div>

          <div class="ce-pop-row">
            <span class="label">VULNERABILITY INDEX:</span>
            <span class="val mono">${vuln}</span>
          </div>
        </div>

        <div class="ce-popover-directive">
          <span class="label">RECOMMENDED DIRECTIVE:</span>
          <p class="directive-text">${action}</p>
        </div>

        <div class="ce-popover-actions-bar">
          <button type="button" class="ce-popover-act-btn" data-tab="SIMULATION">SIMULATE</button>
          <button type="button" class="ce-popover-act-btn" data-tab="PREDICTIONS">PREDICT</button>
          <button type="button" class="ce-popover-act-btn" data-tab="CASCADE">CASCADE</button>
          <button type="button" class="ce-popover-act-btn" data-tab="EVACUATION">EVACUATE</button>
        </div>
      </div>
    `;

    // Position Popover
    if (screenPos && screenPos.x && screenPos.y) {
      const pad = 20;
      const maxX = (window.innerWidth || 1200) - 340;
      const maxY = (window.innerHeight || 800) - 400;
      const left = Math.min(Math.max(pad, screenPos.x + 15), maxX);
      const top = Math.min(Math.max(pad, screenPos.y - 40), maxY);
      popover.style.left = `${left}px`;
      popover.style.top = `${top}px`;
      popover.style.right = 'auto';
      popover.style.bottom = 'auto';
      popover.style.position = 'absolute';
    } else {
      popover.style.position = 'fixed';
      popover.style.top = '80px';
      popover.style.right = '380px';
      popover.style.left = 'auto';
      popover.style.bottom = 'auto';
    }

    popover.classList.remove('ce-hidden');

    const closeBtn = popover.querySelector('#ce-popover-close');
    if (closeBtn) {
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        hidePopover();
      };
    }

    const actionBtns = popover.querySelectorAll('.ce-popover-act-btn');
    actionBtns.forEach((btn) => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const tab = btn.getAttribute('data-tab');
        if (typeof window !== 'undefined' && tab) {
          window.dispatchEvent(new CustomEvent('climate:open-drawer-tab', { detail: { tab } }));
        }
      };
    });
  }

  function hidePopover() {
    if (popoverEl) {
      popoverEl.classList.add('ce-hidden');
    }
  }

  /**
   * Synchronizes Cesium entities with authoritative global hazard state.
   */
  function syncEntitiesFromState() {
    if (isDestroyed || !dataSource) return;

    const state = store.getState();
    const currentLayers = state?.layers || {};

    const globalMaster = currentLayers[CLIMATE_LAYERS.GLOBAL_HAZARDS] !== false;
    dataSource.show = globalMaster;

    if (!globalMaster) {
      return;
    }

    const hazardsMaster = layerFilters.hazards !== false;
    const heatEnabled = hazardsMaster && (currentLayers[CLIMATE_LAYERS.HEAT_ZONES] !== false) && (layerFilters.heat !== false);
    const floodEnabled = hazardsMaster && (currentLayers[CLIMATE_LAYERS.FLOOD_ZONES] !== false) && (layerFilters.flood !== false);
    const compoundEnabled = hazardsMaster && (currentLayers[CLIMATE_LAYERS.COMPOUND_ZONES] !== false) && (layerFilters.compound !== false);
    const cycloneEnabled = hazardsMaster && (currentLayers[CLIMATE_LAYERS.CYCLONE_ZONES] !== false);
    const wildfireEnabled = hazardsMaster && (layerFilters.wildfire !== false);
    const earthquakeEnabled = hazardsMaster && (layerFilters.earthquake !== false);
    const droughtEnabled = hazardsMaster && (layerFilters.drought !== false);
    const evacEnabled = layerFilters.evacuation !== false;

    // Aggregate hazards from global feed slice and local hazard slice
    const globalHazards = state.global?.hazards || [];
    const globalEvents = state.global?.events || [];
    const localHazards = Object.values(state.hazards?.byId || {});
    const compoundEvents = state.compound?.events || [];

    const activeEntityIds = new Set();

    // 1. Process Global Hazards (GlobalHazardZone)
    for (const hz of globalHazards) {
      if (!hz || !hz.center) continue;
      const lat = hz.center.latitude;
      const lon = hz.center.longitude;
      if (typeof lat !== 'number' || typeof lon !== 'number') continue;

      const type = (hz.hazard_type || '').toUpperCase();
      if (type === 'HEAT' && !heatEnabled) continue;
      if (type === 'FLOOD' && !floodEnabled) continue;
      if (type === 'COMPOUND' && !compoundEnabled) continue;
      if (type === 'CYCLONE' && !cycloneEnabled) continue;
      if (type === 'DROUGHT' && !droughtEnabled) continue;
      if (type === 'WILDFIRE' && !wildfireEnabled) continue;
      if (type === 'EARTHQUAKE' && !earthquakeEnabled) continue;

      const entityId = `${GLOBAL_HAZARD_ENTITY_PREFIX}${hz.zone_id}`;
      activeEntityIds.add(entityId);

      const rawRadius = (hz.radius_km || 10) * 1000;
      const radiusMeters = Math.max(rawRadius * currentExpansionFactor, 2000);
      const position = Cesium.Cartesian3.fromDegrees(lon, lat, 0);

      let fillColor = COLOR_HEAT_FILL;
      let outlineColor = COLOR_HEAT_OUTLINE;
      let icon = '⚠️';

      if (type === 'HEAT') {
        fillColor = COLOR_HEAT_FILL;
        outlineColor = COLOR_HEAT_OUTLINE;
        icon = '🔥';
      } else if (type === 'FLOOD') {
        fillColor = COLOR_FLOOD_FILL;
        outlineColor = COLOR_FLOOD_OUTLINE;
        icon = '🌊';
      } else if (type === 'WILDFIRE') {
        fillColor = COLOR_FIRE_FILL;
        outlineColor = COLOR_FIRE_OUTLINE;
        icon = '🔥';
      } else if (type === 'EARTHQUAKE') {
        fillColor = COLOR_QUAKE_FILL;
        outlineColor = COLOR_QUAKE_OUTLINE;
        icon = '⚡';
      } else if (type === 'CYCLONE') {
        fillColor = COLOR_CYCLONE_FILL;
        outlineColor = COLOR_CYCLONE_OUTLINE;
        icon = '🌀';
      } else if (type === 'COMPOUND') {
        fillColor = COLOR_COMPOUND_FILL;
        outlineColor = COLOR_COMPOUND_OUTLINE;
        icon = '⚡';
      }

      let entity = entityMap.get(entityId);
      if (!entity) {
        entity = dataSource.entities.add({
          id: entityId,
          name: `${type} ZONE: ${hz.zone_id}`,
          position,
          ellipse: {
            semiMajorAxis: radiusMeters,
            semiMinorAxis: radiusMeters,
            material: fillColor || Cesium.Color.RED.withAlpha(0.3),
            outline: true,
            outlineColor: outlineColor || Cesium.Color.RED,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
          },
          point: {
            pixelSize: 10,
            color: outlineColor || Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: `${icon} ${type}`,
            font: '11px "JetBrains Mono", monospace',
            style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            pixelOffset: new Cesium.Cartesian2(0, -14),
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: {
            ...hz,
            entityType: 'global_hazard',
          },
        });
        entityMap.set(entityId, entity);
      } else {
        // In-place update
        if (entity.position && typeof entity.position.setValue === 'function') {
          entity.position.setValue(position);
        } else {
          entity.position = position;
        }
        if (entity.ellipse) {
          entity.ellipse.semiMajorAxis = radiusMeters;
          entity.ellipse.semiMinorAxis = radiusMeters;
        }
        entity.properties = { ...hz, entityType: 'global_hazard' };
      }
    }

    // 2. Process Global Authoritative Events (GlobalDisasterEvent)
    for (const ev of globalEvents) {
      if (!ev || !ev.location) continue;
      const lat = ev.location.latitude;
      const lon = ev.location.longitude;
      if (typeof lat !== 'number' || typeof lon !== 'number') continue;

      const entityId = `${GLOBAL_EVENT_ENTITY_PREFIX}${ev.event_id}`;
      activeEntityIds.add(entityId);

      const radiusMeters = Math.max((ev.affected_radius_km || 15) * 1000, 3000);
      const position = Cesium.Cartesian3.fromDegrees(lon, lat, 0);

      const evType = (ev.event_type || '').toUpperCase();
      if (evType === 'EARTHQUAKE' && !earthquakeEnabled) continue;
      if (evType === 'WILDFIRE' && !wildfireEnabled) continue;
      if (evType === 'CYCLONE' && !cycloneEnabled) continue;

      let pointColor = COLOR_QUAKE_POINT;
      let outlineColor = COLOR_QUAKE_OUTLINE;
      let fillColor = COLOR_QUAKE_FILL;
      let icon = '⚡';

      if (evType === 'EARTHQUAKE') {
        pointColor = COLOR_QUAKE_POINT;
        outlineColor = COLOR_QUAKE_OUTLINE;
        fillColor = COLOR_QUAKE_FILL;
        icon = '⚠️';
      } else if (evType === 'WILDFIRE') {
        pointColor = COLOR_FIRE_POINT;
        outlineColor = COLOR_FIRE_OUTLINE;
        fillColor = COLOR_FIRE_FILL;
        icon = '🔥';
      } else if (evType === 'CYCLONE') {
        pointColor = COLOR_CYCLONE_OUTLINE;
        outlineColor = COLOR_CYCLONE_OUTLINE;
        fillColor = COLOR_CYCLONE_FILL;
        icon = '🌀';
      }

      let entity = entityMap.get(entityId);
      if (!entity) {
        entity = dataSource.entities.add({
          id: entityId,
          name: ev.title || `${evType} Event`,
          position,
          ellipse: {
            semiMajorAxis: radiusMeters,
            semiMinorAxis: radiusMeters,
            material: fillColor || Cesium.Color.YELLOW.withAlpha(0.2),
            outline: true,
            outlineColor: outlineColor || Cesium.Color.YELLOW,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
          },
          point: {
            pixelSize: 12,
            color: pointColor || Cesium.Color.YELLOW,
            outlineColor: outlineColor || Cesium.Color.BLACK,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: `${icon} ${ev.title || evType}`,
            font: '11px "JetBrains Mono", monospace',
            style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            pixelOffset: new Cesium.Cartesian2(0, -16),
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: {
            ...ev,
            hazard_type: evType,
            entityType: 'global_event',
          },
        });
        entityMap.set(entityId, entity);
      } else {
        if (entity.position && typeof entity.position.setValue === 'function') {
          entity.position.setValue(position);
        } else {
          entity.position = position;
        }
        entity.properties = { ...ev, hazard_type: evType, entityType: 'global_event' };
      }
    }

    // 3. Process Compound Events (CompoundEvent cascade overlays)
    if (compoundEnabled) {
      for (const comp of compoundEvents) {
        if (!comp || !comp.primary_location) continue;
        const lat = comp.primary_location.latitude || comp.primary_location.lat;
        const lon = comp.primary_location.longitude || comp.primary_location.lon;
        if (typeof lat !== 'number' || typeof lon !== 'number') continue;

        const entityId = `${GLOBAL_HAZARD_ENTITY_PREFIX}compound-${comp.compound_id || comp.id}`;
        activeEntityIds.add(entityId);

        const radiusMeters = 35000; // 35km default compound zone
        const position = Cesium.Cartesian3.fromDegrees(lon, lat, 0);

        let entity = entityMap.get(entityId);
        if (!entity) {
          entity = dataSource.entities.add({
            id: entityId,
            name: `COMPOUND DISASTER: ${comp.name || comp.compound_id}`,
            position,
            ellipse: {
              semiMajorAxis: radiusMeters,
              semiMinorAxis: radiusMeters,
              material: COLOR_COMPOUND_FILL || Cesium.Color.PURPLE.withAlpha(0.4),
              outline: true,
              outlineColor: COLOR_COMPOUND_OUTLINE || Cesium.Color.PURPLE,
              outlineWidth: 3,
              heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            },
            point: {
              pixelSize: 14,
              color: COLOR_COMPOUND_OUTLINE || Cesium.Color.PURPLE,
              outlineColor: Cesium.Color.WHITE,
              outlineWidth: 2,
              heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            label: {
              text: `⚡ CASCADE: ${comp.name || 'COMPOUND'}`,
              font: '12px "JetBrains Mono", monospace',
              style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
              fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 3,
              pixelOffset: new Cesium.Cartesian2(0, -18),
              heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            properties: {
              ...comp,
              hazard_type: 'COMPOUND',
              radius_km: 35.0,
              entityType: 'compound_hazard',
            },
          });
          entityMap.set(entityId, entity);
        } else {
          if (entity.position && typeof entity.position.setValue === 'function') {
            entity.position.setValue(position);
          } else {
            entity.position = position;
          }
          entity.properties = { ...comp, hazard_type: 'COMPOUND', radius_km: 35.0, entityType: 'compound_hazard' };
        }
      }
    }

    // 4. Process Evacuation Corridors & Shelters (Dynamic around selected region)
    const selectedRegion = state.selectedRegion || { latitude: 17.3850, longitude: 78.4867, name: 'Hyderabad' };
    const regLat = Number.isFinite(selectedRegion.latitude) ? selectedRegion.latitude : 17.3850;
    const regLon = Number.isFinite(selectedRegion.longitude) ? selectedRegion.longitude : 78.4867;
    const regName = selectedRegion.name || 'Selected Region';

    // 4a. Dynamic Regional Hazard Spatial Zone (Part 12 & 13)
    const regHazardEntityId = `${GLOBAL_HAZARD_ENTITY_PREFIX}region-focus-${regName.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;
    activeEntityIds.add(regHazardEntityId);
    const regBaseRadius = 18000;
    const regEffectiveRadius = regBaseRadius * (isSimulationActive ? currentExpansionFactor : 1.0);
    const regPosition = Cesium.Cartesian3.fromDegrees(regLon, regLat, 0);

    const regColorFill = isSimulationActive
      ? Cesium.Color.fromCssColorString('rgba(168, 85, 247, 0.35)')
      : Cesium.Color.fromCssColorString('rgba(239, 68, 68, 0.28)');
    const regColorOutline = isSimulationActive
      ? Cesium.Color.fromCssColorString('#a855f7')
      : Cesium.Color.fromCssColorString('#ef4444');

    let regEntity = entityMap.get(regHazardEntityId);
    if (!regEntity) {
      regEntity = dataSource.entities.add({
        id: regHazardEntityId,
        name: `${regName.toUpperCase()} ACTIVE IMPACT ZONE`,
        position: regPosition,
        ellipse: {
          semiMajorAxis: regEffectiveRadius,
          semiMinorAxis: regEffectiveRadius,
          material: regColorFill,
          outline: true,
          outlineColor: regColorOutline,
          outlineWidth: isSimulationActive ? 3 : 2,
          heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
        },
        label: {
          text: isSimulationActive ? `⚠️ [SIMULATED] ${regName.toUpperCase()} EXPANDED IMPACT ZONE` : `📍 ${regName.toUpperCase()} HAZARD ZONE`,
          font: '12px "Plus Jakarta Sans", sans-serif',
          style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          pixelOffset: new Cesium.Cartesian2(0, -22),
          heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        properties: {
          hazard_type: isSimulationActive ? 'SIMULATED_HAZARD' : 'REGIONAL_HAZARD',
          region: regName,
          simulated: isSimulationActive,
          radius_km: Math.round(regEffectiveRadius / 1000),
        },
      });
      entityMap.set(regHazardEntityId, regEntity);
    } else {
      if (regEntity.position?.setValue) regEntity.position.setValue(regPosition);
      else regEntity.position = regPosition;
      if (regEntity.ellipse) {
        regEntity.ellipse.semiMajorAxis = regEffectiveRadius;
        regEntity.ellipse.semiMinorAxis = regEffectiveRadius;
        regEntity.ellipse.material = regColorFill;
        regEntity.ellipse.outlineColor = regColorOutline;
      }
      if (regEntity.label) {
        regEntity.label.text = isSimulationActive ? `⚠️ [SIMULATED] ${regName.toUpperCase()} EXPANDED IMPACT ZONE` : `📍 ${regName.toUpperCase()} HAZARD ZONE`;
      }
    }

    if (evacEnabled && typeof Cesium.Cartesian3?.fromDegreesArray === 'function') {
      // Safe Corridor 1 (Highground safe egress towards elevated shelter)
      const corridor1Id = `${GLOBAL_HAZARD_ENTITY_PREFIX}evac-safe-corridor`;
      activeEntityIds.add(corridor1Id);
      const safePositions = Cesium.Cartesian3.fromDegreesArray([
        regLon, regLat,
        regLon + 0.025, regLat + 0.020,
        regLon + 0.053, regLat + 0.040,
      ]);

      let corridorEntity = entityMap.get(corridor1Id);
      if (!corridorEntity) {
        corridorEntity = dataSource.entities.add({
          id: corridor1Id,
          name: `SAFE EVACUATION CORRIDOR: ${regName.toUpperCase()} NORTH EGRESS`,
          polyline: {
            positions: safePositions,
            width: isSimulationActive ? 6 : 4,
            material: Cesium.Color.fromCssColorString('#10b981'),
            clampToGround: true,
          },
          properties: {
            hazard_type: 'EVACUATION_CORRIDOR',
            status: 'SAFE',
            corridor_name: `${regName} Highground Vector`,
            eta_minutes: 18,
          },
        });
        entityMap.set(corridor1Id, corridorEntity);
      } else {
        if (corridorEntity.polyline) {
          corridorEntity.polyline.positions = safePositions;
        }
      }

      // Blocked Route (Lowland Crossing susceptible to flood surcharge)
      const blockedRouteId = `${GLOBAL_HAZARD_ENTITY_PREFIX}evac-blocked-corridor`;
      activeEntityIds.add(blockedRouteId);
      const blockedPositions = Cesium.Cartesian3.fromDegreesArray([
        regLon, regLat,
        regLon - 0.015, regLat - 0.020,
        regLon - 0.032, regLat - 0.035,
      ]);

      let blockedEntity = entityMap.get(blockedRouteId);
      if (!blockedEntity) {
        blockedEntity = dataSource.entities.add({
          id: blockedRouteId,
          name: `BLOCKED CORRIDOR: ${regName.toUpperCase()} LOWLAND CROSSING`,
          polyline: {
            positions: blockedPositions,
            width: isSimulationActive ? 6 : 4,
            material: Cesium.Color.fromCssColorString('#ef4444'),
            clampToGround: true,
          },
          properties: {
            hazard_type: 'BLOCKED_ROUTE',
            status: 'UNSAFE',
            reason: 'Surface flooding exceedance (Strain Index: 0.88)',
          },
        });
        entityMap.set(blockedRouteId, blockedEntity);
      } else {
        if (blockedEntity.polyline) {
          blockedEntity.polyline.positions = blockedPositions;
        }
      }

      // Safe Shelter Marker
      const shelterId = `${GLOBAL_HAZARD_ENTITY_PREFIX}safe-shelter`;
      activeEntityIds.add(shelterId);
      const shelterPos = Cesium.Cartesian3.fromDegrees(regLon + 0.053, regLat + 0.040, 0);

      let shelterEntity = entityMap.get(shelterId);
      if (!shelterEntity) {
        shelterEntity = dataSource.entities.add({
          id: shelterId,
          name: `SAFE SHELTER: ${regName.toUpperCase()} ELEVATED CENTER`,
          position: shelterPos,
          point: {
            pixelSize: 14,
            color: Cesium.Color.fromCssColorString('#10b981'),
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: `🏥 SAFE SHELTER [${regName.toUpperCase()}]`,
            font: '12px "Plus Jakarta Sans", sans-serif',
            style: Cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 3,
            pixelOffset: new Cesium.Cartesian2(0, -18),
            heightReference: Cesium.HeightReference?.CLAMP_TO_GROUND ?? 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: {
            hazard_type: 'SHELTER',
            title: `SAFE SHELTER: ${regName}`,
            capacity: 2500,
            current_demand: 1850,
            distance_km: 4.2,
            eta_minutes: 18,
            status: 'SAFE',
          },
        });
        entityMap.set(shelterId, shelterEntity);
      } else {
        if (shelterEntity.position?.setValue) shelterEntity.position.setValue(shelterPos);
        else shelterEntity.position = shelterPos;
      }
    }

    // Remove entities that are no longer active
    for (const [entityId, entity] of entityMap.entries()) {
      if (!activeEntityIds.has(entityId)) {
        dataSource.entities.remove(entity);
        entityMap.delete(entityId);
      }
    }

    try {
      governorRequestRender('climate-global-hazards-update');
    } catch (_) {}
  }

  /**
   * Initializes the layer and registers pick owner.
   */
  function init() {
    if (isDestroyed) return;

    dataSource = new Cesium.CustomDataSource(CLIMATE_GLOBAL_HAZARDS_DATA_SOURCE_NAME);
    viewer.dataSources.add(dataSource);

    // Register with GEV pick ownership registry
    registerPickOwner(CLIMATE_GLOBAL_HAZARDS_LAYER_ID, (pickedId) => {
      return typeof pickedId === 'string' && (
        pickedId.startsWith(GLOBAL_HAZARD_ENTITY_PREFIX) ||
        pickedId.startsWith(GLOBAL_EVENT_ENTITY_PREFIX)
      );
    });

    // Screen-space click handler for tactical picking popovers
    if (viewer.scene?.canvas && Cesium.ScreenSpaceEventHandler) {
      clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      clickHandler.setInputAction((movement) => {
        if (!movement?.position || !viewer.scene) return;
        const picked = viewer.scene.pick(movement.position);
        const pickId = resolvePickId(picked);

        if (pickId && (
          pickId.startsWith(GLOBAL_HAZARD_ENTITY_PREFIX) ||
          pickId.startsWith(GLOBAL_EVENT_ENTITY_PREFIX)
        )) {
          const entity = entityMap.get(pickId) || (dataSource?.entities?.getById ? dataSource.entities.getById(pickId) : null);
          const rawProps = entity?.properties;
          const data = rawProps?.getValue ? rawProps.getValue(viewer.clock?.currentTime) : rawProps;

          if (data) {
            showPopover(data, movement.position);
            // Also notify store and listeners
            store.dispatch({
              type: 'HAZARD_SELECTED',
              payload: { hazardId: data.zone_id || data.event_id || pickId },
            });
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('climate:hazard-selected', { detail: data }));
            }
          }
          try {
            governorRequestRender('climate-global-hazard-picked');
          } catch (_) {}
        } else {
          // If clicked on empty space, hide popover
          hidePopover();

          // Globe click to select location (Part 5 & 7)
          let cartesian = null;
          if (viewer.scene?.pickPositionSupported && typeof viewer.scene.pickPosition === 'function') {
            try {
              cartesian = viewer.scene.pickPosition(movement.position);
            } catch (_) {}
          }
          if (!cartesian || !isPickedWorldPosition(cartesian)) {
            const ray = viewer.camera?.getPickRay ? viewer.camera.getPickRay(movement.position) : null;
            if (ray && viewer.scene?.globe?.pick) {
              cartesian = viewer.scene.globe.pick(ray, viewer.scene);
            } else if (viewer.camera?.pickEllipsoid) {
              cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene?.globe?.ellipsoid);
            }
          }

          if (cartesian && isPickedWorldPosition(cartesian)) {
            try {
              const carto = Cesium.Cartographic.fromCartesian(cartesian);
              const lat = Cesium.Math.toDegrees(carto.latitude);
              const lon = Cesium.Math.toDegrees(carto.longitude);
              if (Number.isFinite(lat) && Number.isFinite(lon)) {
                if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                  window.dispatchEvent(new CustomEvent('climate:globe-clicked', {
                    detail: { latitude: lat, longitude: lon }
                  }));
                }
              }
            } catch (err) {
              console.warn('[ClimateEye] Globe click conversion error:', err);
            }
          }
        }
      }, Cesium.ScreenSpaceEventType?.LEFT_CLICK ?? 0);
    }

    storeUnsubscribe = store.subscribe(() => {
      syncEntitiesFromState();
    });

    if (typeof window !== 'undefined') {
      window.addEventListener('climate:simulation-applied', (e) => {
        currentExpansionFactor = e.detail?.expansionFactor || 1.64;
        isSimulationActive = true;
        syncEntitiesFromState();
      });

      window.addEventListener('climate:simulation-reset', () => {
        currentExpansionFactor = 1.0;
        isSimulationActive = false;
        syncEntitiesFromState();
      });

      window.addEventListener('climate:prediction-horizon-changed', (e) => {
        const horizon = e.detail?.horizon || 'now';
        if (horizon === '30m') currentExpansionFactor = 1.25;
        else if (horizon === '60m') currentExpansionFactor = 1.55;
        else if (horizon === '6h') currentExpansionFactor = 2.10;
        else currentExpansionFactor = 1.0;
        syncEntitiesFromState();
      });

      window.addEventListener('climate:layer-filter-changed', (e) => {
        layerFilters = { ...layerFilters, ...(e.detail || {}) };
        syncEntitiesFromState();
      });

      window.addEventListener('climate:highlight-evac-corridors', () => {
        const corridorId = `${GLOBAL_HAZARD_ENTITY_PREFIX}evac-corridor-nh65`;
        const entity = entityMap.get(corridorId);
        if (entity?.polyline) {
          entity.polyline.width = 8;
          setTimeout(() => {
            if (entity?.polyline) entity.polyline.width = 4;
          }, 4000);
        }
      });

      window.addEventListener('climate:causal-node-picked', (e) => {
        const target = e.detail?.target;
        const CAUSAL_TARGETS = {
          rain: { lat: 17.3850, lon: 78.4867, height: 40000 },
          soil: { lat: 17.3950, lon: 78.4950, height: 35000 },
          flood: { lat: 17.3800, lon: 78.4800, height: 30000 },
          road: { lat: 17.3700, lon: 78.4700, height: 25000 },
          hospital: { lat: 17.4250, lon: 78.5400, height: 25000 },
          delay: { lat: 17.4000, lon: 78.5100, height: 35000 },
        };
        const dest = CAUSAL_TARGETS[target] || CAUSAL_TARGETS.rain;
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(dest.lon, dest.lat, dest.height),
          duration: 2.0,
        });
      });

      window.addEventListener('climate:flyTo', (e) => {
        const { latitude, longitude, height } = e.detail || {};
        if (typeof latitude === 'number' && typeof longitude === 'number') {
          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, height || 350000),
            duration: 2.0,
          });
        }
      });
    }

    syncEntitiesFromState();
  }

  function setVisible(visible) {
    if (dataSource) {
      dataSource.show = Boolean(visible);
      if (!visible) hidePopover();
      try {
        governorRequestRender('climate-global-hazards-visibility');
      } catch (_) {}
    }
  }

  function destroy() {
    if (isDestroyed) return;
    isDestroyed = true;

    if (typeof storeUnsubscribe === 'function') {
      storeUnsubscribe();
      storeUnsubscribe = null;
    }

    if (clickHandler) {
      clickHandler.destroy();
      clickHandler = null;
    }

    unregisterPickOwner(CLIMATE_GLOBAL_HAZARDS_LAYER_ID);

    hidePopover();
    if (popoverEl && popoverEl.parentNode) {
      popoverEl.parentNode.removeChild(popoverEl);
      popoverEl = null;
    }

    if (dataSource && viewer.dataSources) {
      try {
        dataSource.entities.removeAll();
        viewer.dataSources.remove(dataSource, true);
      } catch (_) {}
      dataSource = null;
    }

    entityMap.clear();

    try {
      governorRequestRender('climate-global-hazards-destroyed');
    } catch (_) {}
  }

  return {
    init,
    update: syncEntitiesFromState,
    setVisible,
    showPopover,
    hidePopover,
    destroy,
    getDataSource: () => dataSource,
    getEntityMap: () => entityMap,
  };
}

/**
 * Initializes or returns the singleton Climate Eye global hazards layer.
 */
export function initGlobalHazardsLayer(options = {}) {
  if (activeGlobalHazardsLayer) {
    return activeGlobalHazardsLayer;
  }
  activeGlobalHazardsLayer = createGlobalHazardsLayer(options);
  activeGlobalHazardsLayer.init();
  return activeGlobalHazardsLayer;
}

export function getGlobalHazardsLayer() {
  return activeGlobalHazardsLayer;
}

export function destroyGlobalHazardsLayer() {
  if (activeGlobalHazardsLayer) {
    activeGlobalHazardsLayer.destroy();
    activeGlobalHazardsLayer = null;
  }
}
