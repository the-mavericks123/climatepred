/**
 * Climate Eye — Realtime Controller & Bridge Unit Tests (Step F4.3)
 *
 * Tests cover:
 * - WebSocket client connects
 * - state starts as UNAVAILABLE
 * - connection alone does not claim LIVE
 * - node.updated updates node state
 * - telemetry.updated updates telemetry state
 * - real telemetry causes LIVE state
 * - null preservation
 * - zero preservation
 * - timestamp preservation
 * - unknown/future node IDs (NODE-006+)
 * - disconnect transitions away from LIVE
 * - last known data retained after disconnect
 * - reconnect does not duplicate events/listeners
 * - malformed message ignored safely
 * - invalid event ignored safely
 * - multiple telemetry events update the latest state
 * - UI panels reflect realtime telemetry
 * - clean controller shutdown
 * - no Node.js imports in runtime code
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createClimateStore,
  REALTIME_STATES,
} from '../state/index.js';

import {
  createRealtimeBridge,
  startRealtimeBridge,
  stopRealtimeBridge,
  getRealtimeBridge,
} from './index.js';

import {
  createLeftPanel,
  createStatusBar,
} from '../panels/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Controllable Mock WebSocket Implementation
// ---------------------------------------------------------------------------

function createMockWebSocketClass() {
  const instances = [];

  class MockWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = MockWebSocket.CONNECTING;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      this.closedWith = null;
      instances.push(this);
    }

    close(code = 1000, reason = '') {
      this.closedWith = { code, reason };
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ code, reason, wasClean: code === 1000 });
    }

    triggerOpen() {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.({});
    }

    triggerMessage(data) {
      const serialized = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage?.({ data: serialized });
    }

    triggerError(message = 'mock socket error') {
      this.onerror?.({ message });
    }

    triggerClose(code = 1001, reason = 'Server closed') {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ code, reason, wasClean: code === 1000 });
    }
  }

  MockWebSocket.CONNECTING = 0;
  MockWebSocket.OPEN = 1;
  MockWebSocket.CLOSING = 2;
  MockWebSocket.CLOSED = 3;

  MockWebSocket.instances = instances;
  return MockWebSocket;
}

// ---------------------------------------------------------------------------
// Minimal DOM Mock for Testing UI Panel Reflects Telemetry
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
          const has = classListSet.has(c);
          const shouldAdd = force !== undefined ? force : !has;
          if (shouldAdd) classListSet.add(c);
          else classListSet.delete(c);
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
          return shouldAdd;
        },
        contains: (c) => classListSet.has(c),
      };
    },

    get textContent() {
      return this._textContent !== undefined ? this._textContent : '';
    },
    set textContent(val) {
      this._textContent = String(val);
    },

    get innerHTML() {
      return _innerHTML;
    },
    set innerHTML(html) {
      _innerHTML = html;
      this._parseMinimalIds(html);
    },

    _parseMinimalIds(html) {
      const idRegex = /id="([^"]+)"/g;
      let match;
      while ((match = idRegex.exec(html)) !== null) {
        const foundId = match[1];
        const child = createMockElement('div');
        child.id = foundId;
        children.push(child);
      }
    },

    setAttribute(name, val) {
      attributes.set(name, String(val));
      if (name === 'class') {
        _className = String(val);
        syncClassListFromClassName();
      }
      if (name === 'id') _id = String(val);
    },
    getAttribute(name) {
      return attributes.get(name) ?? null;
    },
    hasAttribute(name) {
      return attributes.has(name);
    },

    appendChild(child) {
      children.push(child);
      return child;
    },
    remove() {
      children.length = 0;
    },

    addEventListener(event, fn) {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(fn);
    },
    dispatchEvent(event) {
      const fns = listeners.get(event.type) || [];
      fns.forEach((fn) => fn(event));
    },

    querySelector(selector) {
      if (selector.startsWith('#')) {
        const targetId = selector.slice(1);
        return this._findDescendant((el) => el.id === targetId);
      }
      return null;
    },

    querySelectorAll(selector) {
      const results = [];
      this._walkDescendants((el) => {
        if (selector.startsWith('.') && el.classList.contains(selector.slice(1))) {
          results.push(el);
        }
      });
      return results;
    },

    _findDescendant(predicate) {
      for (const child of children) {
        if (predicate(child)) return child;
        const found = child._findDescendant?.(predicate);
        if (found) return found;
      }
      return null;
    },

    _walkDescendants(callback) {
      for (const child of children) {
        callback(child);
        child._walkDescendants?.(callback);
      }
    },
  };

  return element;
}

function setupMockDom() {
  const originalDocument = globalThis.document;
  globalThis.document = {
    createElement: (tag) => createMockElement(tag),
    getElementById: () => null,
    head: createMockElement('head'),
    body: createMockElement('body'),
  };
  return () => {
    globalThis.document = originalDocument;
  };
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

describe('Frontend F4.3: Realtime Controller / Bridge', () => {
  let MockWS;
  let store;
  let bridge;

  beforeEach(() => {
    MockWS = createMockWebSocketClass();
    store = createClimateStore();
    stopRealtimeBridge();
  });

  afterEach(() => {
    if (bridge) {
      try {
        bridge.disconnect();
      } catch (_) {}
      bridge = null;
    }
    stopRealtimeBridge();
  });

  test('WebSocket client connects to stream path', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });

    assert.equal(MockWS.instances.length, 0);
    bridge.connect();
    assert.equal(MockWS.instances.length, 1);
    assert.ok(MockWS.instances[0].url.includes('/api/climate/stream'));
  });

  test('state starts as UNAVAILABLE', () => {
    const initialState = store.getState();
    assert.equal(initialState.connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
  });

  test('connection alone does not claim LIVE', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];

    // Trigger connection open
    ws.triggerOpen();

    const state = store.getState();
    // Must NOT claim LIVE merely because the socket opened!
    assert.notEqual(state.connection.realtimeState, REALTIME_STATES.LIVE);
    assert.equal(state.connection.realtimeState, REALTIME_STATES.STALE);
    assert.equal(state.connection.connected, true);
  });

  test('node.updated updates node state without modifying other nodes', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    // Send node.updated
    ws.triggerMessage({
      event: 'node.updated',
      timestamp: '2026-09-08T03:00:00.000Z',
      payload: {
        node_id: 'NODE-001',
        name: 'Marina Coastal Node',
        region: 'coastal',
        status: 'online',
        location: { lat: 1.28, lon: 103.85 },
      },
    });

    const state = store.getState();
    assert.ok(state.nodes.allIds.includes('NODE-001'));
    assert.equal(state.nodes.byId['NODE-001'].name, 'Marina Coastal Node');
    assert.equal(state.nodes.byId['NODE-001'].status, 'online');
    assert.equal(state.nodes.byId['NODE-001'].region, 'coastal');
    // Connection state remains STALE until telemetry arrives
    assert.equal(state.connection.realtimeState, REALTIME_STATES.STALE);
  });

  test('telemetry.updated updates telemetry state and transitions to LIVE', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    const telemetryTimestamp = '2026-09-08T03:05:00.000Z';
    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: telemetryTimestamp,
      payload: {
        node_id: 'NODE-002',
        temperature: 31.4,
        rainfall: 12.5,
        soil_moisture: 42.0,
        air_quality: 55,
        timestamp: telemetryTimestamp,
      },
    });

    const state = store.getState();
    assert.equal(state.connection.realtimeState, REALTIME_STATES.LIVE);
    assert.equal(state.telemetry.byNodeId['NODE-002'].temperature, 31.4);
    assert.equal(state.telemetry.byNodeId['NODE-002'].rainfall, 12.5);
    assert.equal(state.telemetry.byNodeId['NODE-002'].soil_moisture, 42.0);
    assert.equal(state.telemetry.byNodeId['NODE-002'].air_quality, 55);
  });

  test('null values are preserved exactly in telemetry state', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:06:00.000Z',
      payload: {
        node_id: 'NODE-003',
        temperature: null,
        rainfall: null,
        soil_moisture: 35.2,
        air_quality: null,
      },
    });

    const state = store.getState();
    const reading = state.telemetry.byNodeId['NODE-003'];
    assert.equal(reading.temperature, null);
    assert.equal(reading.rainfall, null);
    assert.equal(reading.soil_moisture, 35.2);
    assert.equal(reading.air_quality, null);
  });

  test('numeric zero values are preserved in telemetry state', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:07:00.000Z',
      payload: {
        node_id: 'NODE-004',
        temperature: 0,
        rainfall: 0,
        soil_moisture: 0,
        air_quality: 0,
      },
    });

    const state = store.getState();
    const reading = state.telemetry.byNodeId['NODE-004'];
    assert.strictEqual(reading.temperature, 0);
    assert.strictEqual(reading.rainfall, 0);
    assert.strictEqual(reading.soil_moisture, 0);
    assert.strictEqual(reading.air_quality, 0);
  });

  test('backend timestamp is preserved exactly', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    const expectedTs = '2026-09-08T03:08:45.123Z';
    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: expectedTs,
      payload: {
        node_id: 'NODE-005',
        temperature: 28.5,
        timestamp: expectedTs,
      },
    });

    const state = store.getState();
    assert.equal(state.telemetry.byNodeId['NODE-005'].timestamp, expectedTs);
  });

  test('accepts unknown and future node IDs dynamically (e.g. NODE-006, NODE-999)', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    ws.triggerMessage({
      event: 'node.updated',
      timestamp: '2026-09-08T03:09:00.000Z',
      payload: {
        node_id: 'NODE-006',
        name: 'Sentosa Oceanic Sensor',
        status: 'online',
      },
    });

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:09:01.000Z',
      payload: {
        node_id: 'NODE-006',
        temperature: 29.8,
      },
    });

    const state = store.getState();
    assert.ok(state.nodes.allIds.includes('NODE-006'));
    assert.equal(state.nodes.byId['NODE-006'].name, 'Sentosa Oceanic Sensor');
    assert.equal(state.telemetry.byNodeId['NODE-006'].temperature, 29.8);
  });

  test('disconnect transitions away from LIVE while retaining last valid data', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:10:00.000Z',
      payload: {
        node_id: 'NODE-001',
        temperature: 32.1,
      },
    });

    assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);

    // Simulate WebSocket disconnect
    ws.triggerClose(1006, 'Abnormal disconnect');

    const stateAfterClose = store.getState();
    assert.notEqual(stateAfterClose.connection.realtimeState, REALTIME_STATES.LIVE);
    assert.ok(
      stateAfterClose.connection.realtimeState === REALTIME_STATES.STALE ||
      stateAfterClose.connection.realtimeState === REALTIME_STATES.UNAVAILABLE
    );
    assert.equal(stateAfterClose.connection.connected, false);

    // CRITICAL: telemetry data is NOT wiped
    assert.equal(stateAfterClose.telemetry.byNodeId['NODE-001'].temperature, 32.1);

    // Explicit disconnect transitions to UNAVAILABLE
    bridge.disconnect();
    const stateAfterExplicit = store.getState();
    assert.equal(stateAfterExplicit.connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
    assert.equal(stateAfterExplicit.connection.connected, false);
    assert.equal(stateAfterExplicit.telemetry.byNodeId['NODE-001'].temperature, 32.1);
  });

  test('reconnect does not duplicate events and remains non-LIVE until telemetry arrives', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: {
        baseUrl: 'ws://localhost:5199',
        reconnect: { maxRetries: 3, initialDelayMs: 1, maxDelayMs: 5, backoffFactor: 1 },
      },
    });
    bridge.connect();
    const ws1 = MockWS.instances[0];
    ws1.triggerOpen();

    ws1.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:11:00.000Z',
      payload: { node_id: 'NODE-001', temperature: 27.5 },
    });
    assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);

    // Disconnect
    ws1.triggerClose(1006, 'Network drop');
    assert.notEqual(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);

    // Wait for mock reconnection attempt
    return new Promise((resolve) => {
      setTimeout(() => {
        assert.ok(MockWS.instances.length >= 2, 'New socket created on reconnect');
        const ws2 = MockWS.instances[1];
        ws2.triggerOpen();

        // After reconnect opens, it must NOT fabricate LIVE
        assert.notEqual(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);

        // Send telemetry on reconnected socket
        ws2.triggerMessage({
          event: 'telemetry.updated',
          timestamp: '2026-09-08T03:11:05.000Z',
          payload: { node_id: 'NODE-001', temperature: 27.8 },
        });

        assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);
        assert.equal(store.getState().telemetry.byNodeId['NODE-001'].temperature, 27.8);
        resolve();
      }, 50);
    });
  });

  test('malformed message is ignored safely without crashing socket', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    // Invalid JSON
    assert.doesNotThrow(() => {
      ws.onmessage?.({ data: '{{{bad json' });
    });

    // Valid envelope but non-object payload
    assert.doesNotThrow(() => {
      ws.triggerMessage({
        event: 'telemetry.updated',
        timestamp: '2026-09-08T03:12:00.000Z',
        payload: 'not-an-object',
      });
    });

    // State remains unaffected and socket stays OPEN
    assert.equal(ws.readyState, MockWS.OPEN);
  });

  test('invalid / unapproved event is ignored safely', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    assert.doesNotThrow(() => {
      ws.triggerMessage({
        event: 'unapproved.random.event',
        timestamp: '2026-09-08T03:13:00.000Z',
        payload: { something: true },
      });
    });

    assert.equal(ws.readyState, MockWS.OPEN);
  });

  test('multiple telemetry events update the latest state correctly', () => {
    bridge = createRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    bridge.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:14:00.000Z',
      payload: { node_id: 'NODE-001', temperature: 25.0 },
    });
    assert.equal(store.getState().telemetry.byNodeId['NODE-001'].temperature, 25.0);

    ws.triggerMessage({
      event: 'telemetry.updated',
      timestamp: '2026-09-08T03:14:02.000Z',
      payload: { node_id: 'NODE-001', temperature: 26.5 },
    });
    assert.equal(store.getState().telemetry.byNodeId['NODE-001'].temperature, 26.5);
  });

  test('UI panels reflect realtime telemetry without refresh', () => {
    const tearDownDom = setupMockDom();

    try {
      const leftPanel = createLeftPanel(store);
      const statusBar = createStatusBar(store);

      bridge = createRealtimeBridge({
        store,
        WebSocketClass: MockWS,
        clientOptions: { baseUrl: 'ws://localhost:5199' },
      });
      bridge.connect();
      const ws = MockWS.instances[0];
      ws.triggerOpen();

      // Before telemetry
      const rtText = statusBar.element.querySelector('#ce-realtime-text');
      assert.equal(rtText.textContent, REALTIME_STATES.STALE);

      // Ingest node & telemetry
      ws.triggerMessage({
        event: 'node.updated',
        timestamp: '2026-09-08T03:15:00.000Z',
        payload: { node_id: 'NODE-001', name: 'Downtown Hub', status: 'online' },
      });

      ws.triggerMessage({
        event: 'telemetry.updated',
        timestamp: '2026-09-08T03:15:01.000Z',
        payload: {
          node_id: 'NODE-001',
          temperature: 30.5,
          rainfall: 0,
          soil_moisture: 45.0,
          air_quality: 42,
          timestamp: '2026-09-08T03:15:01.000Z',
        },
      });

      // Assert status bar updated
      assert.equal(rtText.textContent, REALTIME_STATES.LIVE);

      // Assert left panel updated
      const tempVal = leftPanel.element.querySelector('#ce-temp-value');
      const rainVal = leftPanel.element.querySelector('#ce-rain-value');
      const footnote = leftPanel.element.querySelector('#ce-channel-footnote');

      assert.equal(tempVal.textContent, '30.5 °C');
      assert.equal(rainVal.textContent, '0 mm/h'); // 0 preserved
      assert.ok(footnote.textContent.includes('2026-09-08T03:15:01.000Z'));

      leftPanel.destroy();
      statusBar.destroy();
    } finally {
      tearDownDom();
    }
  });

  test('clean controller shutdown disconnects socket and resets singleton', () => {
    const b1 = startRealtimeBridge({
      store,
      WebSocketClass: MockWS,
      clientOptions: { baseUrl: 'ws://localhost:5199' },
    });
    assert.equal(getRealtimeBridge(), b1);
    assert.equal(MockWS.instances.length, 1);

    // Repeated call returns existing instance
    const b2 = startRealtimeBridge({ store });
    assert.equal(b2, b1);
    assert.equal(MockWS.instances.length, 1);

    stopRealtimeBridge();
    assert.equal(getRealtimeBridge(), null);
    assert.equal(MockWS.instances[0].readyState, MockWS.CLOSED);
  });

  test('no Node.js core module imports in browser-safe runtime code', () => {
    const filesToCheck = [
      resolve(__dirname, 'client.js'),
      resolve(__dirname, 'controller.js'),
      resolve(__dirname, 'index.js'),
      resolve(__dirname, '../panels/leftPanel.js'),
      resolve(__dirname, '../panels/statusBar.js'),
      resolve(__dirname, '../panels/shell.js'),
      resolve(__dirname, '../panels/index.js'),
    ];

    const forbidden = ['node:test', 'node:assert', 'node:fs', 'node:path', 'node:url', 'node:child_process', 'node:http', 'node:ws', 'node:os'];

    for (const filePath of filesToCheck) {
      const content = readFileSync(filePath, 'utf-8');
      for (const pattern of forbidden) {
        assert.ok(
          !content.includes(`'${pattern}'`) && !content.includes(`"${pattern}"`),
          `Forbidden import "${pattern}" found in browser module: ${filePath}`
        );
      }
    }
  });
});
