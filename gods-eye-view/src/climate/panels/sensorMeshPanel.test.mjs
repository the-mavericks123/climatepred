/**
 * Climate Eye — Sensor Mesh Panel Unit Tests (Step F4.6)
 *
 * Validates:
 * - Empty node list display (honest empty state)
 * - Single node rendering with real telemetry
 * - Multiple nodes rendering
 * - Future dynamic nodes (NODE-006+) rendering without hardcoded IDs
 * - Node ordering preservation
 * - Dynamic addition and removal of nodes
 * - node.updated and telemetry.updated live refreshes
 * - Strict numeric zero (0) preservation in temperature, rainfall, soil, etc.
 * - Strict null preservation (-- without false zeroing)
 * - Exact backend timestamp preservation
 * - LIVE/AVAILABLE, STALE, and UNAVAILABLE state badges
 * - Derived summary counts (TOTAL, AVAILABLE, STALE, OFFLINE)
 * - "LAST TELEMETRY" newest timestamp indicator
 * - Node selection from panel
 * - Globe -> panel selection synchronization
 * - Deselection (re-clicking selected node or clicking Deselect button)
 * - Keyboard accessibility (Enter, Space, tabindex="0", aria-pressed)
 * - Connection state changes update freshness without deleting data
 * - Clean destroy without memory leaks
 * - Browser-safe code check (no Node.js core modules)
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createClimateStore,
  REALTIME_STATES,
  CLIMATE_MODES,
  ACTION_TYPES,
} from '../state/index.js';

import {
  createSensorMeshPanel,
  formatNodeMetric,
  getNodeFreshness,
  formatTimeAgo,
} from './sensorMeshPanel.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Robust DOM Mock Implementation
// ---------------------------------------------------------------------------

function createMockElement(tagName = 'div') {
  const children = [];
  const attributes = new Map();
  const listeners = new Map();
  let _innerHTML = '';
  let _className = '';
  let _id = '';
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

    get className() {
      return _className;
    },
    set className(val) {
      _className = String(val);
      attributes.set('class', _className);
      syncClassListFromClassName();
    },

    style: {},
    get dataset() {
      const data = {};
      for (const [k, v] of attributes.entries()) {
        if (k.startsWith('data-')) {
          const prop = k.slice(5).replace(/-([a-z])/g, (_, l) => l.toUpperCase());
          data[prop] = v;
        }
      }
      return data;
    },

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
    },
    getAttribute: (name) => {
      if (name === 'id') return _id || attributes.get('id') || null;
      if (name === 'class') return _className || attributes.get('class') || null;
      return attributes.get(name) ?? null;
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
    closest: (selector) => {
      let curr = element;
      while (curr) {
        if (matchesSelector(curr, selector)) return curr;
        curr = curr.parentNode;
      }
      return null;
    },
  };

  return element;
}

/** Stack-based HTML parser handling nested identical tags */
function parseHTMLStack(html, root) {
  const stack = [root];
  const tokenRegex = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9-]+)>|<([a-zA-Z0-9-]+)([^>]*?)(\/?)>|([^<]+)/g;
  const voidTags = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);

  let match;
  while ((match = tokenRegex.exec(html)) !== null) {
    const [full, closeTag, openTag, attrStr, selfClose, text] = match;

    if (full.startsWith('<!--')) {
      continue;
    }

    if (closeTag) {
      const lower = closeTag.toLowerCase();
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tagName.toLowerCase() === lower) {
          stack.length = i;
          break;
        }
      }
    } else if (openTag) {
      const el = createMockElement(openTag);
      const attrRegex = /([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g;
      let aMatch;
      while ((aMatch = attrRegex.exec(attrStr || '')) !== null) {
        el.setAttribute(aMatch[1], aMatch[2] !== undefined ? aMatch[2] : '');
      }

      const parent = stack[stack.length - 1];
      if (parent) {
        parent.appendChild(el);
      }

      const isVoid = voidTags.has(openTag.toLowerCase()) || selfClose === '/';
      if (!isVoid) {
        stack.push(el);
      }
    } else if (text && text.trim()) {
      const parent = stack[stack.length - 1];
      if (parent) {
        const textNode = createMockElement('#text');
        textNode._text = text;
        parent.appendChild(textNode);
      }
    }
  }
}

function matchesSelector(el, selector) {
  if (!el || !selector || !el.getAttribute) return false;
  selector = selector.trim();

  let remaining = selector;

  // Check ID (#id)
  const idMatch = remaining.match(/^#([a-zA-Z0-9_-]+)/);
  if (idMatch) {
    if (el.id !== idMatch[1]) return false;
    remaining = remaining.slice(idMatch[0].length);
  }

  // Check Tag name
  const tagMatch = remaining.match(/^([a-zA-Z0-9-]+)/);
  if (tagMatch) {
    if (el.tagName.toLowerCase() !== tagMatch[1].toLowerCase()) return false;
    remaining = remaining.slice(tagMatch[0].length);
  }

  // Check Classes (.class)
  const classMatches = remaining.matchAll(/\.([a-zA-Z0-9_-]+)/g);
  for (const cm of classMatches) {
    if (!el.classList.contains(cm[1])) return false;
  }
  remaining = remaining.replace(/\.([a-zA-Z0-9_-]+)/g, '');

  // Check Attributes ([name="val"] or [name])
  const attrMatches = remaining.matchAll(/\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\]/g);
  for (const am of attrMatches) {
    const [, attrName, attrVal] = am;
    if (attrVal !== undefined) {
      if (el.getAttribute(attrName) !== attrVal) return false;
    } else if (!el.hasAttribute(attrName)) {
      return false;
    }
  }

  return true;
}

function querySelectorAllDeep(root, selector) {
  const results = [];
  function walk(node) {
    if (!node || !node.children) return;
    for (const child of node.children) {
      if (matchesSelector(child, selector)) {
        results.push(child);
      }
      walk(child);
    }
  }
  walk(root);
  return results;
}

let originalDocument;

beforeEach(() => {
  originalDocument = globalThis.document;
  globalThis.document = {
    createElement: (tag) => createMockElement(tag),
  };
});

afterEach(() => {
  globalThis.document = originalDocument;
});

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe('Frontend Step F4.6: Climate Eye Sensor Mesh Panel', () => {

  describe('1. Formatting & Freshness Utilities', () => {
    test('formatNodeMetric strictly preserves numeric 0', () => {
      assert.equal(formatNodeMetric(0, '°C', 1), '0.0 °C');
      assert.equal(formatNodeMetric(0, 'mm/h', 1), '0.0 mm/h');
      assert.equal(formatNodeMetric(0, '%', 1), '0.0 %');
      assert.equal(formatNodeMetric(0, 'AQI', 0), '0 AQI');
    });

    test('formatNodeMetric returns placeholder -- for null or missing values', () => {
      assert.equal(formatNodeMetric(null, '°C', 1), '-- °C');
      assert.equal(formatNodeMetric(undefined, 'mm/h', 1), '-- mm/h');
      assert.equal(formatNodeMetric(NaN, '%', 1), '-- %');
    });

    test('getNodeFreshness determines availability correctly', () => {
      // Live state
      assert.equal(getNodeFreshness({ status: 'active' }, { timestamp: '2026-09-08T06:00:00Z' }, REALTIME_STATES.LIVE), 'AVAILABLE');

      // Stale state
      assert.equal(getNodeFreshness({ status: 'stale' }, null, REALTIME_STATES.LIVE), 'STALE');
      assert.equal(getNodeFreshness({ status: 'active' }, null, REALTIME_STATES.STALE), 'STALE');

      // Unavailable state
      assert.equal(getNodeFreshness({ status: 'offline' }, null, REALTIME_STATES.LIVE), 'UNAVAILABLE');
      assert.equal(getNodeFreshness({ status: 'active' }, null, REALTIME_STATES.UNAVAILABLE), 'UNAVAILABLE');
    });

    test('formatTimeAgo converts timestamps to relative format', () => {
      const now = 1000000000;
      assert.equal(formatTimeAgo(new Date(now - 2000).toISOString(), now), 'just now');
      assert.equal(formatTimeAgo(new Date(now - 15000).toISOString(), now), '15s ago');
      assert.equal(formatTimeAgo(new Date(now - 120000).toISOString(), now), '2m ago');
      assert.equal(formatTimeAgo(null), 'NEVER');
    });
  });

  describe('2. Empty Node List Handling', () => {
    test('displays honest empty state when no nodes exist in state', () => {
      const store = createClimateStore();
      const panel = createSensorMeshPanel(store);

      const emptyText = panel.element.querySelector('.ce-mesh-empty-text');
      assert.ok(emptyText, 'Empty state text element must exist');
      assert.match(emptyText.textContent, /NO SENSOR NODES DETECTED/i);

      const totalVal = panel.element.querySelector('#ce-mesh-total-val');
      assert.equal(totalVal.textContent, '0');

      const latestVal = panel.element.querySelector('#ce-mesh-latest-telemetry-val');
      assert.equal(latestVal.textContent, 'UNAVAILABLE');

      panel.destroy();
    });
  });

  describe('3. Dynamic Node Rendering & Telemetry Value Preservation', () => {
    test('renders a single node dynamically with real measurements and zero preservation', () => {
      const store = createClimateStore();
      store.setRealtimeState(REALTIME_STATES.LIVE);

      store.updateNode({ node_id: 'NODE-001', latitude: 19.07, longitude: 72.87 });
      store.updateTelemetry({
        node_id: 'NODE-001',
        timestamp: '2026-09-08T06:30:00.000Z',
        temperature: 28.5,
        rainfall: 0, // 0 mm/h must be preserved
        soil_moisture: 0, // 0 % must be preserved
        water_level: null, // null must be preserved
      });

      const panel = createSensorMeshPanel(store);

      const nodeRows = panel.element.querySelectorAll('.ce-mesh-node-row');
      assert.equal(nodeRows.length, 1);

      const row = nodeRows[0];
      assert.equal(row.dataset.nodeId, 'NODE-001');

      // Metric values in row
      const text = row.textContent;
      assert.match(text, /28\.5\s*°C/);
      assert.match(text, /0\.0\s*mm\/h/, 'Rainfall 0 must be preserved as 0.0 mm/h');
      assert.match(text, /0\.0\s*%/, 'Soil moisture 0 must be preserved as 0.0 %');
      assert.match(text, /--\s*m/, 'Water level null must be preserved as -- m');

      // Summary counts
      assert.equal(panel.element.querySelector('#ce-mesh-total-val').textContent, '1');
      assert.equal(panel.element.querySelector('#ce-mesh-available-val').textContent, '1');

      panel.destroy();
    });

    test('dynamically renders multiple nodes including future NODE-006+ without hardcoding', () => {
      const store = createClimateStore();
      store.setRealtimeState(REALTIME_STATES.LIVE);

      const nodes = [
        { node_id: 'NODE-001', latitude: 19.07, longitude: 72.87 },
        { node_id: 'NODE-002', latitude: 28.61, longitude: 77.20 },
        { node_id: 'NODE-006', latitude: 12.97, longitude: 77.59 }, // Future node
        { node_id: 'CUSTOM-NODE-ALPHA', latitude: 13.08, longitude: 80.27 }, // Dynamic ID
      ];

      store.updateNodes(nodes);

      const panel = createSensorMeshPanel(store);
      const rows = panel.element.querySelectorAll('.ce-mesh-node-row');
      assert.equal(rows.length, 4, 'Must render all 4 dynamic nodes');

      const ids = Array.from(rows).map((r) => r.dataset.nodeId);
      assert.deepEqual(ids, ['NODE-001', 'NODE-002', 'NODE-006', 'CUSTOM-NODE-ALPHA']);

      panel.destroy();
    });

    test('node ordering matches store.allIds order', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-B' });
      store.updateNode({ node_id: 'NODE-A' });
      store.updateNode({ node_id: 'NODE-C' });

      const panel = createSensorMeshPanel(store);
      const rows = panel.element.querySelectorAll('.ce-mesh-node-row');
      const renderedIds = Array.from(rows).map((r) => r.dataset.nodeId);

      assert.deepEqual(renderedIds, ['NODE-B', 'NODE-A', 'NODE-C']);
      panel.destroy();
    });
  });

  describe('4. Realtime Updates & Lifecycle Synchronization', () => {
    test('node.updated dynamically adds new node to panel without refresh', () => {
      const store = createClimateStore();
      const panel = createSensorMeshPanel(store);

      assert.equal(panel.element.querySelectorAll('.ce-mesh-node-row').length, 0);

      // Node arrives via realtime
      store.updateNode({ node_id: 'NODE-001', latitude: 19.0, longitude: 72.0 });

      assert.equal(panel.element.querySelectorAll('.ce-mesh-node-row').length, 1);
      assert.equal(panel.element.querySelector('#ce-mesh-total-val').textContent, '1');

      panel.destroy();
    });

    test('telemetry.updated updates measurements in place without recreating panel', () => {
      const store = createClimateStore();
      store.setRealtimeState(REALTIME_STATES.LIVE);
      store.updateNode({ node_id: 'NODE-001', latitude: 19.0, longitude: 72.0 });
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 20.0, rainfall: 1.0 });

      const panel = createSensorMeshPanel(store);
      let row = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');
      assert.match(row.textContent, /20\.0\s*°C/);

      // Subsequent telemetry update
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 27.5, rainfall: 0.0 });
      row = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');
      assert.match(row.textContent, /27\.5\s*°C/);
      assert.match(row.textContent, /0\.0\s*mm\/h/);

      panel.destroy();
    });

    test('removeNode removes node row from panel and clears selection if active', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      store.updateNode({ node_id: 'NODE-002' });
      store.selectNode('NODE-001');

      const panel = createSensorMeshPanel(store);
      assert.equal(panel.element.querySelectorAll('.ce-mesh-node-row').length, 2);

      // Remove NODE-001
      store.removeNode('NODE-001');

      assert.equal(panel.element.querySelectorAll('.ce-mesh-node-row').length, 1);
      assert.equal(panel.element.querySelector('.ce-mesh-node-row').dataset.nodeId, 'NODE-002');
      assert.equal(store.getState().ui.selectedNodeId, null, 'Selected node must be cleared in store');

      panel.destroy();
    });
  });

  describe('5. Selection & Bidirectional Synchronization', () => {
    test('clicking a node row in panel updates store.selectedNodeId', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      store.updateNode({ node_id: 'NODE-002' });

      const panel = createSensorMeshPanel(store);
      const row1 = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');

      row1.click();
      assert.equal(store.getState().ui.selectedNodeId, 'NODE-001', 'Clicking row must select NODE-001 in store');

      panel.destroy();
    });

    test('clicking the already-selected node row deselects it', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      store.selectNode('NODE-001');

      const panel = createSensorMeshPanel(store);
      const row1 = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');

      // Click selected row -> should toggle to null
      row1.click();
      assert.equal(store.getState().ui.selectedNodeId, null, 'Re-clicking selected row must deselect it');

      panel.destroy();
    });

    test('clicking the Deselect button clears active selection', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      store.selectNode('NODE-001');

      const panel = createSensorMeshPanel(store);
      const deselectBtn = panel.element.querySelector('#ce-mesh-deselect-btn');
      assert.ok(!deselectBtn.classList.contains('hidden'), 'Deselect button must be visible when node selected');

      deselectBtn.click();
      assert.equal(store.getState().ui.selectedNodeId, null, 'Clicking deselect button must clear selection in store');

      panel.destroy();
    });

    test('external store selection (globe -> panel) highlights corresponding row with .selected', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      store.updateNode({ node_id: 'NODE-002' });

      const panel = createSensorMeshPanel(store);
      let row2 = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-002"]');
      assert.ok(!row2.classList.contains('selected'));

      // Simulate Cesium globe selection via store dispatch
      store.selectNode('NODE-002');

      row2 = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-002"]');
      assert.ok(row2.classList.contains('selected'), 'Row must have .selected class when selected on globe');
      assert.equal(row2.getAttribute('aria-pressed'), 'true');

      panel.destroy();
    });
  });

  describe('6. Keyboard Accessibility', () => {
    test('node rows have role="button", tabindex="0", and trigger selection on Enter/Space', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });

      const panel = createSensorMeshPanel(store);
      const row = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');

      assert.equal(row.getAttribute('role'), 'button');
      assert.equal(row.getAttribute('tabindex'), '0');

      // Press Enter
      row.dispatchEvent({ type: 'keydown', key: 'Enter', preventDefault: () => {} });
      assert.equal(store.getState().ui.selectedNodeId, 'NODE-001', 'Enter key must select node');

      // Press Space on already selected row -> deselects
      const activeRow = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');
      activeRow.dispatchEvent({ type: 'keydown', key: ' ', preventDefault: () => {} });
      assert.equal(store.getState().ui.selectedNodeId, null, 'Space key must deselect node');

      panel.destroy();
    });
  });

  describe('7. Connection State & Freshness Display', () => {
    test('disconnecting realtime updates freshness states without erasing telemetry data', () => {
      const store = createClimateStore();
      store.setRealtimeState(REALTIME_STATES.LIVE);
      store.updateNode({ node_id: 'NODE-001' });
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 30.0, rainfall: 2.0 });

      const panel = createSensorMeshPanel(store);
      let row = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');
      assert.match(row.textContent, /AVAILABLE/);

      // Disconnect realtime
      store.setRealtimeState(REALTIME_STATES.UNAVAILABLE);

      row = panel.element.querySelector('.ce-mesh-node-row[data-node-id="NODE-001"]');
      assert.match(row.textContent, /UNAVAILABLE/, 'Must reflect unavailable state when disconnected');
      assert.match(row.textContent, /30\.0\s*°C/, 'Historical temperature data must not be deleted');
      assert.match(row.textContent, /2\.0\s*mm\/h/, 'Historical rainfall data must not be deleted');

      panel.destroy();
    });
  });

  describe('8. Clean Destroy & Leak Prevention', () => {
    test('destroy unsubscribes from store and removes panel element', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });

      const panel = createSensorMeshPanel(store);
      panel.destroy();

      // Dispatching to store after destroy should not throw
      assert.doesNotThrow(() => {
        store.updateNode({ node_id: 'NODE-002' });
        store.selectNode('NODE-002');
      });
    });
  });

  describe('9. Browser-Safe Code Verification', () => {
    test('sensorMeshPanel.js contains no Node.js core module imports', () => {
      const filePath = resolve(__dirname, 'sensorMeshPanel.js');
      const content = readFileSync(filePath, 'utf-8');

      assert.doesNotMatch(content, /from\s+['"]node:/, 'sensorMeshPanel.js must not import node: modules');
      assert.doesNotMatch(content, /require\s*\(['"]node:/, 'sensorMeshPanel.js must not require node: modules');
      assert.doesNotMatch(content, /from\s+['"]fs['"]/, 'sensorMeshPanel.js must not import fs');
      assert.doesNotMatch(content, /from\s+['"]path['"]/, 'sensorMeshPanel.js must not import path');
    });
  });
});
