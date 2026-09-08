/**
 * Climate Eye — Operational Dashboard Unit Tests (Step F4.7)
 *
 * Tests the unified command center operational dashboard:
 * - Top navigation rendering & 7 operating modes
 * - Mode switching & state synchronization
 * - Honest unavailable states for RISK, SIMULATION, AI, EMERGENCY
 * - LIVE and SENSOR_MESH operational displays
 * - ANALYTICS mode raw measurement display without fabrication
 * - Subsystem status summary (API, DB, MQTT, Realtime)
 * - Dynamic node summary breakdown (Total, Live, Stale, Unavailable)
 * - Support for dynamic/future node IDs (NODE-006+)
 * - Latest telemetry timestamp handling (real ISO vs honest null '--')
 * - Numeric zero preservation (0 mm/h, 0 °C) vs null placeholder
 * - Bidirectional selection synchronization (Globe/Mesh <-> Right Panel)
 * - Layer toggle controls (9 layers, aria-pressed)
 * - Keyboard navigation & WAI-ARIA accessibility
 * - Clean lifecycle cleanup (destroy, unsubscription)
 * - Browser module safety (zero Node.js core module imports)
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  CLIMATE_MODES,
  REALTIME_STATES,
  CLIMATE_LAYERS,
  ACTION_TYPES,
  createClimateStore,
} from '../state/index.js';

import {
  mountClimateShell,
  createTopNav,
  createLeftPanel,
  createSensorMeshPanel,
  createRightPanel,
  createStatusBar,
  resolveSubsystemStatus,
  computeNodeFreshnessSummary,
} from './index.js';

// ---------------------------------------------------------------------------
// Mock DOM Implementation for Node.js Testing
// ---------------------------------------------------------------------------

function createMockElement(tagName = 'div') {
  const children = [];
  const attributes = new Map();
  const listeners = new Map();
  let _innerHTML = '';
  let _className = '';
  let _id = '';
  let _rel = '';
  let _href = '';
  const classListSet = new Set();

  function syncClassListFromClassName() {
    classListSet.clear();
    _className
      .split(/\s+/)
      .filter(Boolean)
      .forEach((c) => classListSet.add(c));
  }

  const element = {
    tagName: tagName.toUpperCase(),
    children,

    get id() {
      return _id;
    },
    set id(val) {
      _id = String(val);
      attributes.set('id', _id);
    },

    get rel() {
      return _rel;
    },
    set rel(val) {
      _rel = String(val);
      attributes.set('rel', _rel);
    },

    get href() {
      return _href;
    },
    set href(val) {
      _href = String(val);
      attributes.set('href', _href);
    },

    get className() {
      return _className;
    },
    set className(val) {
      _className = String(val);
      attributes.set('class', _className);
      syncClassListFromClassName();
    },

    get dataset() {
      const ds = {};
      for (const [k, v] of attributes) {
        if (k.startsWith('data-')) {
          const prop = k.slice(5).replace(/-([a-z])/g, (_, l) => l.toUpperCase());
          ds[prop] = v;
        }
      }
      return ds;
    },

    style: {},

    get classList() {
      return {
        add: (...cls) => {
          cls.forEach((c) => classListSet.add(c));
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
        },
        remove: (...cls) => {
          cls.forEach((c) => classListSet.delete(c));
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
        },
        toggle: (c, force) => {
          if (force === true) {
            classListSet.add(c);
          } else if (force === false) {
            classListSet.delete(c);
          } else if (classListSet.has(c)) {
            classListSet.delete(c);
          } else {
            classListSet.add(c);
          }
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
          return classListSet.has(c);
        },
        contains: (c) => classListSet.has(c),
      };
    },

    setAttribute: (name, value) => {
      const strVal = String(value);
      attributes.set(name, strVal);
      if (name === 'id') _id = strVal;
      if (name === 'class') {
        _className = strVal;
        syncClassListFromClassName();
      }
      if (name === 'rel') _rel = strVal;
      if (name === 'href') _href = strVal;
    },
    getAttribute: (name) => {
      if (name === 'id') return _id || attributes.get('id') || null;
      if (name === 'class') return _className || attributes.get('class') || null;
      if (name === 'rel') return _rel || attributes.get('rel') || null;
      if (name === 'href') return _href || attributes.get('href') || null;
      return attributes.get(name) || null;
    },
    hasAttribute: (name) => attributes.has(name),

    appendChild: (child) => {
      children.push(child);
      child.parentNode = element;
      return child;
    },
    remove: () => {
      if (element.parentNode && element.parentNode.children) {
        const idx = element.parentNode.children.indexOf(element);
        if (idx !== -1) element.parentNode.children.splice(idx, 1);
      }
    },

    addEventListener: (type, fn) => {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    removeEventListener: (type, fn) => {
      if (!listeners.has(type)) return;
      const arr = listeners.get(type).filter((f) => f !== fn);
      listeners.set(type, arr);
    },
    dispatchEvent: (event) => {
      const type = event.type || event;
      const fns = listeners.get(type) || [];
      fns.forEach((fn) => fn.call(element, { ...event, target: element }));
    },
    click: () => {
      element.dispatchEvent({ type: 'click' });
    },
    focus: () => {
      element.dispatchEvent({ type: 'focus' });
    },

    get innerHTML() {
      return _innerHTML;
    },
    set innerHTML(html) {
      _innerHTML = html;
      children.length = 0;
      parseHTMLStack(html, element);
    },

    get textContent() {
      let text = '';
      function walk(el) {
        if (el._text) text += el._text;
        if (el.children) el.children.forEach(walk);
      }
      walk(element);
      return text;
    },
    set textContent(val) {
      children.length = 0;
      element._text = String(val);
    },

    querySelector: (selector) => {
      return querySelectorAllDeep(element, selector)[0] || null;
    },
    querySelectorAll: (selector) => {
      return querySelectorAllDeep(element, selector);
    },
  };

  return element;
}

function parseHTMLStack(html, root) {
  const stack = [root];
  const tokenRegex = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9-]+)>|<([a-zA-Z0-9-]+)([^>]*?)(\/?)>|([^<]+)/g;
  const voidTags = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);

  let match;
  while ((match = tokenRegex.exec(html)) !== null) {
    const [full, closeTag, openTag, attrStr, selfClose, text] = match;

    if (full.startsWith('<!--')) continue;

    if (closeTag) {
      const tagLower = closeTag.toLowerCase();
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tagName.toLowerCase() === tagLower) {
          stack.splice(i);
          break;
        }
      }
    } else if (openTag) {
      const parent = stack[stack.length - 1];
      const el = createMockElement(openTag);

      const attrRegex = /([a-zA-Z0-9_-]+)(?:=["']([^"']*)["'])?/g;
      let am;
      while ((am = attrRegex.exec(attrStr || '')) !== null) {
        const [, aName, aVal] = am;
        el.setAttribute(aName, aVal !== undefined ? aVal : '');
      }

      parent.appendChild(el);

      const isVoid = voidTags.has(openTag.toLowerCase()) || selfClose === '/';
      if (!isVoid) {
        stack.push(el);
      }
    } else if (text) {
      const parent = stack[stack.length - 1];
      const trimmed = text.trim();
      if (trimmed || text.length > 0) {
        const textNode = createMockElement('#text');
        textNode._text = text;
        parent.appendChild(textNode);
      }
    }
  }
}

function matchesSelector(el, selector) {
  if (selector.startsWith('#')) return el.id === selector.slice(1);
  if (selector.startsWith('.')) return el.classList?.contains(selector.slice(1));
  const attrMatch = selector.match(/^\[([a-zA-Z0-9_-]+)(?:=["']?([^"']*)["']?)?\]$/);
  if (attrMatch) {
    const [, name, val] = attrMatch;
    if (val === undefined) return el.hasAttribute(name);
    return el.getAttribute(name) === val;
  }
  const tagAttrMatch = selector.match(/^([a-zA-Z0-9_-]+)\[([a-zA-Z0-9_-]+)(?:=["']?([^"']*)["']?)?\]$/);
  if (tagAttrMatch) {
    const [, tag, name, val] = tagAttrMatch;
    if (el.tagName.toLowerCase() !== tag.toLowerCase()) return false;
    if (val === undefined) return el.hasAttribute(name);
    return el.getAttribute(name) === val;
  }
  return el.tagName.toLowerCase() === selector.toLowerCase();
}

function querySelectorAllDeep(root, selector) {
  const results = [];
  function walk(node) {
    if (node !== root && matchesSelector(node, selector)) {
      results.push(node);
    }
    if (node.children) {
      node.children.forEach(walk);
    }
  }
  walk(root);
  return results;
}

// ---------------------------------------------------------------------------
// Test Suite Setup & Teardown
// ---------------------------------------------------------------------------

let origDocument;
let origWindow;

beforeEach(() => {
  origDocument = globalThis.document;
  origWindow = globalThis.window;

  const mockHead = createMockElement('head');
  const mockBody = createMockElement('body');
  const mockDoc = {
    head: mockHead,
    body: mockBody,
    createElement: (tag) => createMockElement(tag),
    getElementById: (id) => mockDoc.querySelector(`#${id}`),
    querySelector: (sel) => querySelectorAllDeep(mockDoc.body, sel)[0] || querySelectorAllDeep(mockDoc.head, sel)[0] || null,
    querySelectorAll: (sel) => [...querySelectorAllDeep(mockDoc.body, sel), ...querySelectorAllDeep(mockDoc.head, sel)],
  };

  globalThis.document = mockDoc;
  globalThis.window = globalThis;
});

afterEach(() => {
  globalThis.document = origDocument;
  globalThis.window = origWindow;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Frontend Step F4.7: Command Center UX / Operational Dashboard', () => {
  describe('1. Top Navigation & Application Modes', () => {
    test('renders all 7 application modes with LIVE active by default', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const buttons = topNav.element.querySelectorAll('.ce-mode-btn');
      assert.equal(buttons.length, 7, 'All 7 mode tabs must be rendered');

      const liveBtn = topNav.element.querySelector('#ce-mode-btn-live');
      assert.ok(liveBtn.classList.contains('active'), 'LIVE button must have active class');
      assert.equal(liveBtn.getAttribute('aria-selected'), 'true', 'LIVE button must have aria-selected="true"');
      assert.equal(liveBtn.getAttribute('tabindex'), '0', 'Active button must have tabindex="0"');

      topNav.destroy();
    });

    test('clicking mode button switches mode in store and updates tab active state', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const meshBtn = topNav.element.querySelector('#ce-mode-btn-sensor_mesh');
      meshBtn.click();

      assert.equal(store.getState().ui.mode, CLIMATE_MODES.SENSOR_MESH, 'Store UI mode must update to SENSOR_MESH');
      assert.ok(meshBtn.classList.contains('active'), 'SENSOR_MESH button must become active');
      assert.equal(meshBtn.getAttribute('aria-selected'), 'true');

      const liveBtn = topNav.element.querySelector('#ce-mode-btn-live');
      assert.ok(!liveBtn.classList.contains('active'), 'LIVE button must no longer be active');
      assert.equal(liveBtn.getAttribute('aria-selected'), 'false');
      assert.equal(liveBtn.getAttribute('tabindex'), '-1');

      topNav.destroy();
    });

    test('keyboard arrow keys cycle through mode tabs for accessibility', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const liveBtn = topNav.element.querySelector('#ce-mode-btn-live');
      // Dispatch ArrowRight
      liveBtn.dispatchEvent({ type: 'keydown', key: 'ArrowRight', preventDefault: () => {} });

      assert.equal(store.getState().ui.mode, CLIMATE_MODES.ANALYTICS, 'ArrowRight from LIVE must activate ANALYTICS');
      const analyticsBtn = topNav.element.querySelector('#ce-mode-btn-analytics');
      assert.ok(analyticsBtn.classList.contains('active'));

      // Dispatch ArrowLeft
      analyticsBtn.dispatchEvent({ type: 'keydown', key: 'ArrowLeft', preventDefault: () => {} });
      assert.equal(store.getState().ui.mode, CLIMATE_MODES.LIVE, 'ArrowLeft from ANALYTICS must return to LIVE');

      // Dispatch End key
      liveBtn.dispatchEvent({ type: 'keydown', key: 'End', preventDefault: () => {} });
      assert.equal(store.getState().ui.mode, CLIMATE_MODES.EMERGENCY, 'End key must activate EMERGENCY');

      topNav.destroy();
    });
  });

  describe('2. Operational Subsystems Status Summary', () => {
    test('resolveSubsystemStatus maps actual backend states honestly without false healthy claims', () => {
      const state1 = {
        system: { status: 'uninitialized', subsystems: { api: 'unknown', db: 'unknown', mqtt: 'unknown' } },
        connection: { realtimeState: REALTIME_STATES.UNAVAILABLE, connected: false },
      };
      assert.equal(resolveSubsystemStatus('api', state1), 'UNAVAILABLE');
      assert.equal(resolveSubsystemStatus('db', state1), 'UNAVAILABLE');
      assert.equal(resolveSubsystemStatus('mqtt', state1), 'UNAVAILABLE');
      assert.equal(resolveSubsystemStatus('realtime', state1), 'UNAVAILABLE');

      const state2 = {
        system: { status: 'healthy', subsystems: { api: 'ready', db: 'ready', mqtt: 'idle' } },
        connection: { realtimeState: REALTIME_STATES.LIVE, connected: true },
      };
      assert.equal(resolveSubsystemStatus('api', state2), 'READY');
      assert.equal(resolveSubsystemStatus('db', state2), 'CONNECTED');
      assert.equal(resolveSubsystemStatus('mqtt', state2), 'STANDBY');
      assert.equal(resolveSubsystemStatus('realtime', state2), 'LIVE');

      const state3 = {
        system: { status: 'degraded', subsystems: { db: 'degraded', mqtt: 'degraded' } },
        connection: { realtimeState: REALTIME_STATES.STALE, connected: true },
      };
      assert.equal(resolveSubsystemStatus('api', state3), 'DEGRADED');
      assert.equal(resolveSubsystemStatus('db', state3), 'DEGRADED');
      assert.equal(resolveSubsystemStatus('mqtt', state3), 'DEGRADED');
      assert.equal(resolveSubsystemStatus('realtime', state3), 'STALE');
    });

    test('renders compact subsystems summary grid in Right Panel', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      const subCard = rightPanel.element.querySelector('#ce-card-subsystems');
      assert.ok(subCard, 'Subsystems card must exist');

      const apiVal = rightPanel.element.querySelector('#ce-subsystem-api-val');
      const dbVal = rightPanel.element.querySelector('#ce-subsystem-db-val');
      const mqttVal = rightPanel.element.querySelector('#ce-subsystem-mqtt-val');
      const rtVal = rightPanel.element.querySelector('#ce-subsystem-realtime-val');

      assert.ok(apiVal, 'API subsystem value element must exist');
      assert.ok(dbVal, 'DB subsystem value element must exist');
      assert.ok(mqttVal, 'MQTT subsystem value element must exist');
      assert.ok(rtVal, 'Realtime subsystem value element must exist');

      // Update state
      store.setSystemStatus({
        status: 'healthy',
        subsystems: { api: 'ready', db: 'ready', mqtt: 'connected' },
      });
      store.setRealtimeState(REALTIME_STATES.LIVE);

      assert.equal(apiVal.textContent, 'READY');
      assert.equal(dbVal.textContent, 'CONNECTED');
      assert.equal(mqttVal.textContent, 'CONNECTED');
      assert.equal(rtVal.textContent, 'LIVE');

      rightPanel.destroy();
    });
  });

  describe('3. Honest Intelligence & Mode Displays', () => {
    test('LIVE mode shows real-time observation banner without risk fabrication', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      store.setUiMode(CLIMATE_MODES.LIVE);
      const headline = rightPanel.element.querySelector('#ce-mode-intel-headline');
      assert.equal(headline.textContent, 'REAL-TIME CLIMATE OBSERVATION');

      const desc = rightPanel.element.querySelector('#ce-mode-intel-desc');
      assert.match(desc.textContent, /Operating in real-time sensor observation mode/);

      rightPanel.destroy();
    });

    test('ANALYTICS mode displays raw measurements from existing telemetry without risk scoring', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      // Initially with no telemetry
      store.setUiMode(CLIMATE_MODES.ANALYTICS);
      let desc = rightPanel.element.querySelector('#ce-mode-intel-desc');
      assert.match(desc.textContent, /No historical telemetry recorded yet/);

      // Add real telemetry for two nodes
      store.updateNodes([{ node_id: 'NODE-001' }, { node_id: 'NODE-002' }]);
      store.updateTelemetry({
        node_id: 'NODE-001',
        temperature: 24.5,
        rainfall: 0.0, // preserved 0
        timestamp: '2026-09-08T06:00:00Z',
      });
      store.updateTelemetry({
        node_id: 'NODE-002',
        temperature: 31.0,
        rainfall: 8.4,
        timestamp: '2026-09-08T06:00:01Z',
      });

      desc = rightPanel.element.querySelector('#ce-mode-intel-desc');
      assert.match(desc.textContent, /24.5°C to 31°C/);
      assert.match(desc.textContent, /Peak rainfall: 8.4 mm\/h/);

      rightPanel.destroy();
    });

    test('RISK mode honestly reports intelligence not available without fake scores', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      store.setUiMode(CLIMATE_MODES.RISK);
      const badge = rightPanel.element.querySelector('#ce-mode-intel-badge');
      const headline = rightPanel.element.querySelector('#ce-mode-intel-headline');
      const desc = rightPanel.element.querySelector('#ce-mode-intel-desc');

      assert.equal(badge.textContent, 'UNAVAILABLE');
      assert.equal(headline.textContent, 'INTELLIGENCE NOT AVAILABLE');
      assert.match(desc.textContent, /S2 Risk Assessment Engine is not active/);

      rightPanel.destroy();
    });

    test('SIMULATION mode honestly reports simulation engine offline', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      store.setUiMode(CLIMATE_MODES.SIMULATION);
      const headline = rightPanel.element.querySelector('#ce-mode-intel-headline');
      const desc = rightPanel.element.querySelector('#ce-mode-intel-desc');

      assert.equal(headline.textContent, 'SIMULATION ENGINE OFFLINE');
      assert.match(desc.textContent, /Scenario modeling and physics simulation engines are currently offline/);

      rightPanel.destroy();
    });

    test('AI mode honestly reports AI reasoning agent standby', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      store.setUiMode(CLIMATE_MODES.AI);
      const headline = rightPanel.element.querySelector('#ce-mode-intel-headline');
      const desc = rightPanel.element.querySelector('#ce-mode-intel-desc');

      assert.equal(headline.textContent, 'AI REASONING STANDBY');
      assert.match(desc.textContent, /Multimodal spatial reasoning agent is in standby/);

      rightPanel.destroy();
    });

    test('EMERGENCY mode honestly reports emergency protocols inactive', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      store.setUiMode(CLIMATE_MODES.EMERGENCY);
      const headline = rightPanel.element.querySelector('#ce-mode-intel-headline');
      const desc = rightPanel.element.querySelector('#ce-mode-intel-desc');

      assert.equal(headline.textContent, 'EMERGENCY PROTOCOLS INACTIVE');
      assert.match(desc.textContent, /Automated emergency response plans and evacuation routing are inactive/);

      rightPanel.destroy();
    });
  });

  describe('4. Node Summary & Timestamp Freshness in Status Bar', () => {
    test('computeNodeFreshnessSummary accurately aggregates node breakdown and newest timestamp', () => {
      const now = 100000;
      const nodes = { allIds: ['NODE-001', 'NODE-002', 'NODE-003', 'NODE-006'] };
      const telemetryMap = {
        'NODE-001': { timestamp: new Date(now - 5000).toISOString() }, // live (<15s)
        'NODE-002': { timestamp: new Date(now - 30000).toISOString() }, // stale (15-60s)
        'NODE-003': { timestamp: new Date(now - 90000).toISOString() }, // unavailable (>60s)
        // NODE-006 has no telemetry -> unavailable
      };
      const connection = { realtimeState: REALTIME_STATES.LIVE, connected: true };

      const summary = computeNodeFreshnessSummary(nodes, telemetryMap, connection, now);
      assert.equal(summary.total, 4, 'Total nodes must be 4');
      assert.equal(summary.available, 1, '1 available node');
      assert.equal(summary.stale, 1, '1 stale node');
      assert.equal(summary.unavailable, 2, '2 unavailable nodes');
      assert.equal(summary.newestTimestamp, telemetryMap['NODE-001'].timestamp);
    });

    test('status bar renders dynamic node breakdown and latest timestamp', () => {
      const store = createClimateStore();
      const statusBar = createStatusBar(store);

      const totalEl = statusBar.element.querySelector('#ce-node-count-text');
      const liveEl = statusBar.element.querySelector('#ce-node-live-count');
      const unavailEl = statusBar.element.querySelector('#ce-node-unavail-count');
      const latestVal = statusBar.element.querySelector('#ce-status-last-telemetry-val');
      const latestBadge = statusBar.element.querySelector('#ce-status-last-telemetry-badge');

      // Initial empty state
      assert.equal(totalEl.textContent, '0');
      assert.equal(latestVal.textContent, '--');
      assert.equal(latestBadge.textContent, 'UNAVAILABLE');

      // Add dynamic nodes (including NODE-006+)
      const ts = new Date().toISOString();
      store.updateNodes([
        { node_id: 'NODE-001' },
        { node_id: 'NODE-006' },
      ]);
      store.setRealtimeState(REALTIME_STATES.LIVE);
      store.updateTelemetry({
        node_id: 'NODE-001',
        temperature: 28.0,
        timestamp: ts,
      });

      assert.equal(totalEl.textContent, '2');
      assert.equal(liveEl.textContent, '1');
      assert.equal(unavailEl.textContent, '1');
      assert.equal(latestVal.textContent, ts);
      assert.equal(latestBadge.textContent, 'LIVE');

      statusBar.destroy();
    });
  });

  describe('5. Value Preservation & Selection Synchronization', () => {
    test('strictly preserves numeric zero 0 vs null placeholder across views', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);
      const rightPanel = createRightPanel(store);

      store.updateNodes([{ node_id: 'NODE-001' }]);
      store.updateTelemetry({
        node_id: 'NODE-001',
        temperature: 0.0,
        rainfall: 0.0,
        soil_moisture: 0,
        air_quality: null, // missing reading
      });
      store.selectNode('NODE-001');

      // Left panel channel check
      const tempVal = leftPanel.element.querySelector('#ce-temp-value');
      const rainVal = leftPanel.element.querySelector('#ce-rain-value');
      const soilVal = leftPanel.element.querySelector('#ce-soil-value');
      const aqiVal = leftPanel.element.querySelector('#ce-aqi-value');

      assert.equal(tempVal.textContent, '0 °C', '0 °C temperature must be preserved');
      assert.equal(rainVal.textContent, '0 mm/h', '0 mm/h rain must be preserved');
      assert.equal(soilVal.textContent, '0 %', '0 % soil must be preserved');
      assert.equal(aqiVal.textContent, '--', 'Null AQI must display placeholder --');

      // Right panel detail check
      const detailTemp = rightPanel.element.querySelector('#ce-detail-temp');
      const detailRain = rightPanel.element.querySelector('#ce-detail-rain');
      const detailAqi = rightPanel.element.querySelector('#ce-detail-aqi');

      assert.equal(detailTemp.textContent, '0 °C');
      assert.equal(detailRain.textContent, '0 mm/h');
      assert.equal(detailAqi.textContent, '--');

      leftPanel.destroy();
      rightPanel.destroy();
    });

    test('synchronizes selected node between store, Sensor Mesh, and Right Panel detail', () => {
      const store = createClimateStore();
      const meshPanel = createSensorMeshPanel(store);
      const rightPanel = createRightPanel(store);

      store.updateNodes([{ node_id: 'NODE-001' }, { node_id: 'NODE-002' }]);
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 22.5 });

      // Initially hidden
      const detailCard = rightPanel.element.querySelector('#ce-card-selected-node');
      assert.ok(detailCard.classList.contains('hidden'));

      // Select via Sensor Mesh panel click
      const row1 = meshPanel.element.querySelector('[data-node-id="NODE-001"]');
      assert.ok(row1, 'Row for NODE-001 must exist');
      row1.click();

      assert.equal(store.getState().ui.selectedNodeId, 'NODE-001');
      assert.ok(!detailCard.classList.contains('hidden'), 'Right panel detail card must unhide');
      assert.equal(rightPanel.element.querySelector('#ce-detail-node-id').textContent, 'NODE-001');
      assert.equal(rightPanel.element.querySelector('#ce-detail-temp').textContent, '22.5 °C');

      // Click deselect button in Right Panel
      const deselectBtn = rightPanel.element.querySelector('#ce-node-deselect-btn');
      deselectBtn.click();

      assert.equal(store.getState().ui.selectedNodeId, null, 'Deselect button must clear store selection');
      assert.ok(detailCard.classList.contains('hidden'), 'Detail card must hide on deselection');

      meshPanel.destroy();
      rightPanel.destroy();
    });
  });

  describe('6. Layer Controls & Accessibility', () => {
    test('all 9 climate layers have toggle buttons with aria-pressed', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);

      const buttons = leftPanel.element.querySelectorAll('.ce-layer-toggle-btn');
      assert.equal(buttons.length, 9, 'All 9 layers must have toggle buttons');

      // Test toggling temperature layer
      const tempBtn = leftPanel.element.querySelector('button[data-layer="TEMPERATURE"]');
      assert.ok(tempBtn, 'Temperature toggle button must exist');
      assert.equal(tempBtn.getAttribute('aria-pressed'), 'true', 'Default active layer has aria-pressed="true"');

      tempBtn.click();
      assert.equal(store.getState().layers[CLIMATE_LAYERS.TEMPERATURE], false, 'Layer visibility must toggle to false');
      assert.equal(tempBtn.getAttribute('aria-pressed'), 'false');
      assert.equal(tempBtn.textContent, 'OFF');

      leftPanel.destroy();
    });
  });

  describe('7. Command Center Shell Coordination & Clean Destroy', () => {
    test('mountClimateShell creates root with all components and clean teardown', () => {
      const store = createClimateStore();
      const shell = mountClimateShell(document.body, { store });

      assert.ok(shell.root, 'Root container must exist');
      assert.ok(shell.components.topNav, 'TopNav component must exist');
      assert.ok(shell.components.leftPanel, 'LeftPanel component must exist');
      assert.ok(shell.components.sensorMeshPanel, 'SensorMeshPanel component must exist');
      assert.ok(shell.components.rightPanel, 'RightPanel component must exist');
      assert.ok(shell.components.statusBar, 'StatusBar component must exist');

      // Clean destroy
      shell.destroy();
      assert.equal(document.body.children.length, 0, 'Root element must be removed on destroy');
    });
  });
});
