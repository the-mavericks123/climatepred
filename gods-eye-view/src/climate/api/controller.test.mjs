/**
 * Climate Eye — Frontend REST Data Controller Unit Tests (Step F4.2)
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  createClimateStore,
  REALTIME_STATES,
} from '../state/index.js';

import {
  ClimateApiClient,
  syncClimateStateFromRest,
  bootstrapClimateData,
} from './index.js';

import {
  createLeftPanel,
  createStatusBar,
  createTopNav,
} from '../panels/index.js';

/** Helper to build mock responses */
function mockResponse({ status = 200, body = {} }) {
  const isOk = status >= 200 && status < 300;
  const jsonText = typeof body === 'string' ? body : JSON.stringify(body);
  return {
    ok: isOk,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    text: async () => jsonText,
    json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
  };
}

describe('Frontend Step F4.2: Climate Eye REST Data Synchronization', () => {

  // -------------------------------------------------------------------------
  // 1. Health & Service Availability
  // -------------------------------------------------------------------------
  describe('Health Synchronization', () => {
    test('successful health loading updates store system status to healthy with subsystems', async () => {
      const store = createClimateStore();
      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({
            status: 200,
            body: {
              ok: true,
              service: 'climate-eye-s1',
              version: '1.2.0',
              timestamp: '2026-09-08T00:00:00Z',
              subsystems: { api: 'ready', db: 'ready', mqtt: 'connected', realtime: 'listening' },
            },
          });
        }
        if (url.includes('/api/nodes')) {
          return mockResponse({ status: 200, body: { ok: true, count: 0, nodes: [] } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(result.ok, true);
      const state = store.getState();
      assert.equal(state.system.status, 'healthy');
      assert.equal(state.system.version, '1.2.0');
      assert.equal(state.system.subsystems.api, 'ready');
      assert.equal(state.system.subsystems.db, 'ready');
      assert.equal(state.system.subsystems.mqtt, 'connected');
    });

    test('API failure on health sets system status to degraded', async () => {
      const store = createClimateStore();
      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({ status: 503, body: { ok: false, error: 'Database unavailable' } });
        }
        return mockResponse({ status: 200, body: { ok: true, count: 0, nodes: [] } });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(result.ok, false);
      const state = store.getState();
      assert.equal(state.system.status, 'degraded');
      assert.ok(state.system.lastError);
    });

    test('network exception on health handles gracefully and sets degraded', async () => {
      const store = createClimateStore();
      const mockFetch = async () => {
        throw new Error('Failed to fetch (DNS failure)');
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(result.ok, false);
      assert.equal(store.getState().system.status, 'degraded');
    });
  });

  // -------------------------------------------------------------------------
  // 2. Node List & Extensibility
  // -------------------------------------------------------------------------
  describe('Nodes Synchronization & Extensibility', () => {
    test('loads dynamic nodes including future NODE-006+ without hardcoded bounds', async () => {
      const store = createClimateStore();
      const sampleNodes = [
        { node_id: 'NODE-001', name: 'Alpha Station', latitude: 37.77, longitude: -122.41, status: 'active' },
        { node_id: 'NODE-002', name: 'Beta Station', latitude: 37.78, longitude: -122.42, status: 'active' },
        { node_id: 'NODE-006', name: 'Zeta Station (Future)', latitude: 38.0, longitude: -122.5, status: 'active' },
        { node_id: 'NODE-999', name: 'Omega Station (Dynamic)', latitude: 38.1, longitude: -122.6, status: 'maintenance' },
      ];

      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({ status: 200, body: { ok: true, version: '1.0.0' } });
        }
        if (url.endsWith('/api/nodes')) {
          return mockResponse({ status: 200, body: { ok: true, count: sampleNodes.length, nodes: sampleNodes } });
        }
        if (url.includes('/telemetry')) {
          return mockResponse({ status: 200, body: { ok: true, readings: [] } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(result.ok, true);
      const state = store.getState();
      assert.equal(state.nodes.allIds.length, 4);
      assert.ok(state.nodes.byId['NODE-006']);
      assert.ok(state.nodes.byId['NODE-999']);
      assert.equal(state.nodes.byId['NODE-006'].name, 'Zeta Station (Future)');
    });

    test('handles empty node list correctly without fabricated data', async () => {
      const store = createClimateStore();
      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({ status: 200, body: { ok: true } });
        }
        if (url.endsWith('/api/nodes')) {
          return mockResponse({ status: 200, body: { ok: true, count: 0, nodes: [] } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(result.ok, true);
      const state = store.getState();
      assert.equal(state.nodes.allIds.length, 0);
      assert.deepEqual(state.nodes.byId, {});
    });

    test('malformed node response does not crash controller', async () => {
      const store = createClimateStore();
      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({ status: 200, body: { ok: true } });
        }
        if (url.endsWith('/api/nodes')) {
          // malformed: missing nodes array
          return mockResponse({ status: 200, body: { ok: true, count: 1 } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client });

      assert.equal(store.getState().nodes.allIds.length, 0);
    });
  });

  // -------------------------------------------------------------------------
  // 3. Telemetry Ingestion, Null & Zero Preservation
  // -------------------------------------------------------------------------
  describe('Telemetry & Value Preservation', () => {
    test('preserves numeric zero (0) and null correctly in node telemetry', async () => {
      const store = createClimateStore();
      const nodes = [{ node_id: 'NODE-001', name: 'Coastal Sensor' }];
      const telemetryReading = {
        node_id: 'NODE-001',
        timestamp: '2026-09-08T01:00:00Z',
        temperature: 0, // numeric zero (e.g. freezing point)
        rainfall: 0,    // numeric zero (no rain)
        soil_moisture: null, // absent/null measurement
        water_level: null,
        air_quality: 18,
      };

      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) {
          return mockResponse({ status: 200, body: { ok: true } });
        }
        if (url.endsWith('/api/nodes')) {
          return mockResponse({ status: 200, body: { ok: true, count: 1, nodes } });
        }
        if (url.includes('/api/nodes/NODE-001/telemetry')) {
          return mockResponse({ status: 200, body: { ok: true, readings: [telemetryReading] } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client, fetchTelemetry: true });

      assert.equal(result.nodeTelemetryCount, 1);
      const state = store.getState();
      const stored = state.telemetry.byNodeId['NODE-001'];
      assert.ok(stored);

      // Verify numeric 0 preserved
      assert.strictEqual(stored.temperature, 0);
      assert.strictEqual(stored.rainfall, 0);

      // Verify null preserved
      assert.strictEqual(stored.soil_moisture, null);
      assert.strictEqual(stored.water_level, null);

      // Verify non-zero value
      assert.strictEqual(stored.air_quality, 18);
    });

    test('partial node failure: one node telemetry failure does not prevent other valid nodes', async () => {
      const store = createClimateStore();
      const nodes = [
        { node_id: 'NODE-001', name: 'Sensor 1' },
        { node_id: 'NODE-002', name: 'Sensor 2 (Offline)' },
        { node_id: 'NODE-003', name: 'Sensor 3' },
      ];

      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) return mockResponse({ status: 200, body: { ok: true } });
        if (url.endsWith('/api/nodes')) return mockResponse({ status: 200, body: { ok: true, count: 3, nodes } });

        if (url.includes('/NODE-001/telemetry')) {
          return mockResponse({ status: 200, body: { ok: true, readings: [{ node_id: 'NODE-001', temperature: 21.5 }] } });
        }
        if (url.includes('/NODE-002/telemetry')) {
          // Node 2 telemetry 500 error
          return mockResponse({ status: 500, body: { ok: false, error: 'Database read error' } });
        }
        if (url.includes('/NODE-003/telemetry')) {
          return mockResponse({ status: 200, body: { ok: true, readings: [{ node_id: 'NODE-003', temperature: 19.8 }] } });
        }
        return mockResponse({ status: 404 });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await syncClimateStateFromRest({ store, client, fetchTelemetry: true });

      assert.equal(result.nodeTelemetryCount, 2); // 2 of 3 succeeded
      const state = store.getState();
      assert.equal(state.nodes.allIds.length, 3); // all 3 nodes registered
      assert.ok(state.telemetry.byNodeId['NODE-001']);
      assert.equal(state.telemetry.byNodeId['NODE-002'], undefined); // 2 has no telemetry
      assert.ok(state.telemetry.byNodeId['NODE-003']);
    });

    test('realtime state never falsely claims LIVE after REST sync', async () => {
      const store = createClimateStore();
      const mockFetch = async (url) => {
        if (url.includes('/api/climate/health')) return mockResponse({ status: 200, body: { ok: true } });
        if (url.endsWith('/api/nodes')) return mockResponse({ status: 200, body: { ok: true, count: 1, nodes: [{ node_id: 'NODE-001' }] } });
        return mockResponse({ status: 200, body: { ok: true, readings: [] } });
      };

      const client = new ClimateApiClient({ fetch: mockFetch });
      await syncClimateStateFromRest({ store, client });

      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
    });
  });

  // -------------------------------------------------------------------------
  // 4. UI Shell Integration & Reflection
  // -------------------------------------------------------------------------
  describe('UI Shell Reflection of Synchronized State', () => {
    let originalDoc;

    function createMockElement(tagName = 'div') {
      const children = [];
      const attributes = new Map();
      const listeners = new Map();
      let _innerHTML = '';
      let _className = '';
      let _id = '';
      const classListSet = new Set();

      const element = {
        tagName: tagName.toUpperCase(),
        children,
        style: {},

        get id() { return _id; },
        set id(val) { _id = String(val); attributes.set('id', _id); },

        get className() { return _className; },
        set className(val) {
          _className = String(val);
          attributes.set('class', _className);
          classListSet.clear();
          _className.split(/\s+/).filter(Boolean).forEach((c) => classListSet.add(c));
        },

        get classList() {
          return {
            add: (...cls) => { cls.forEach((c) => classListSet.add(c)); _className = Array.from(classListSet).join(' '); },
            remove: (...cls) => { cls.forEach((c) => classListSet.delete(c)); _className = Array.from(classListSet).join(' '); },
            toggle: (c, force) => {
              if (force === true) classListSet.add(c);
              else if (force === false) classListSet.delete(c);
              else if (classListSet.has(c)) classListSet.delete(c);
              else classListSet.add(c);
              _className = Array.from(classListSet).join(' ');
              return classListSet.has(c);
            },
            contains: (c) => classListSet.has(c),
          };
        },

        setAttribute: (k, v) => {
          attributes.set(k, String(v));
          if (k === 'id') _id = String(v);
          if (k === 'class') element.className = String(v);
        },
        getAttribute: (k) => attributes.get(k) || null,

        appendChild: (ch) => { children.push(ch); ch.parentNode = element; return ch; },

        get innerHTML() { return _innerHTML; },
        set innerHTML(html) {
          _innerHTML = html;
          children.length = 0;
          parseHTML(html, element);
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
        set textContent(v) { children.length = 0; element._text = String(v); },

        querySelector: (sel) => {
          if (sel.startsWith('#')) {
            const targetId = sel.slice(1);
            function find(n) {
              if (n.id === targetId) return n;
              for (const c of n.children || []) {
                const found = find(c);
                if (found) return found;
              }
              return null;
            }
            return find(element);
          }
          return null;
        },
        querySelectorAll: () => [],
        addEventListener: (t, fn) => {
          if (!listeners.has(t)) listeners.set(t, []);
          listeners.get(t).push(fn);
        },
      };

      return element;
    }

    function parseHTML(html, root) {
      const stack = [root];
      const tokenRegex = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9-]+)>|<([a-zA-Z0-9-]+)([^>]*?)(\/?)>|([^<]+)/g;
      let match;
      while ((match = tokenRegex.exec(html)) !== null) {
        const [full, closeTag, openTag, attrStr, selfClose, text] = match;
        if (full.startsWith('<!--')) continue;
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
          if (parent) parent.appendChild(el);
          if (selfClose !== '/') stack.push(el);
        } else if (text && text.trim()) {
          const parent = stack[stack.length - 1];
          if (parent) {
            const tNode = createMockElement('#text');
            tNode._text = text;
            parent.appendChild(tNode);
          }
        }
      }
    }

    beforeEach(() => {
      originalDoc = globalThis.document;
      globalThis.document = {
        createElement: (tag) => createMockElement(tag),
      };
    });

    afterEach(() => {
      globalThis.document = originalDoc;
    });

    test('left panel and status bar reflect synchronized nodes and telemetry', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);
      const statusBar = createStatusBar(store);

      // Initially 0 nodes, UNAVAILABLE
      const nodeBadge = leftPanel.element.querySelector('#ce-sensor-count-badge');
      const tempVal = leftPanel.element.querySelector('#ce-temp-value');
      const tempBadge = leftPanel.element.querySelector('#ce-temp-badge');
      const apiText = statusBar.element.querySelector('#ce-api-text');

      assert.equal(nodeBadge.textContent, '0 NODES');
      assert.equal(tempVal.textContent, '--');
      assert.equal(tempBadge.textContent, 'UNAVAILABLE');

      // Dispatch real synchronized data
      store.setSystemStatus({ status: 'healthy' });
      store.updateNodes([
        { node_id: 'NODE-001', name: 'Station Alpha' },
        { node_id: 'NODE-002', name: 'Station Beta' },
      ]);
      store.updateTelemetry({
        node_id: 'NODE-001',
        temperature: 23.4,
        rainfall: 0,
      });

      // Status bar reflects HEALTHY
      assert.equal(apiText.textContent, 'HEALTHY');

      // Left panel reflects 2 NODES and real temperature
      assert.equal(nodeBadge.textContent, '2 NODES');
      assert.equal(tempVal.textContent, '23.4 °C');
      assert.equal(tempBadge.textContent, 'TELEMETRY');

      leftPanel.destroy();
      statusBar.destroy();
    });
  });
});
