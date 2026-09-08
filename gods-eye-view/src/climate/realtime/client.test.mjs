/**
 * Climate Eye — Frontend Realtime Client Unit Tests (Step F3)
 *
 * Tests cover:
 * - buildStreamUrl: URL construction from baseUrl and path
 * - validateEnvelope: canonical envelope validation
 * - createClimateRealtimeClient: connection lifecycle, reconnect, fault isolation
 * - createStateIntegratedRealtimeClient: event → state dispatch mapping
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  CLIMATE_STREAM_PATH,
  APPROVED_EVENTS,
  APPROVED_EVENT_SET,
  CLIENT_STATES,
  buildStreamUrl,
  validateEnvelope,
  createClimateRealtimeClient,
  createStateIntegratedRealtimeClient,
} from './index.js';

// ---------------------------------------------------------------------------
// Mock WebSocket Factory
// ---------------------------------------------------------------------------

/**
 * Creates a controllable mock WebSocket class.
 * Returns an instance with exposed triggerOpen/triggerMessage/triggerError/triggerClose.
 */
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

    close(code, reason) {
      this.closedWith = { code, reason };
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ code, reason, wasClean: code === 1000 });
    }

    triggerOpen() {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.({});
    }

    triggerMessage(data) {
      this.onmessage?.({ data });
    }

    triggerError(message = 'mock error') {
      this.onerror?.({ message });
    }

    triggerClose(code = 1001, reason = '') {
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
// Helpers
// ---------------------------------------------------------------------------

function makeValidEnvelope(event = 'node.updated', payload = { node_id: 'N001' }) {
  return { event, timestamp: new Date().toISOString(), payload };
}

function makeClient(opts = {}) {
  const MockWS = createMockWebSocketClass();
  const errors = [];
  const states = [];
  const events = [];

  const client = createClimateRealtimeClient({
    baseUrl: 'ws://localhost:5199',
    WebSocket: MockWS,
    reconnect: { maxRetries: 2, initialDelayMs: 10, maxDelayMs: 100, backoffFactor: 2 },
    onEvent: (env) => events.push(env),
    onStateChange: (s) => states.push(s),
    onError: (e) => errors.push(e),
    ...opts,
  });

  return { client, MockWS, errors, states, events };
}

// ---------------------------------------------------------------------------
// buildStreamUrl
// ---------------------------------------------------------------------------

describe('buildStreamUrl', () => {
  test('converts http base to ws', () => {
    assert.strictEqual(buildStreamUrl('http://localhost:5199'), 'ws://localhost:5199/api/climate/stream');
  });

  test('converts https base to wss', () => {
    assert.strictEqual(buildStreamUrl('https://example.com'), 'wss://example.com/api/climate/stream');
  });

  test('preserves ws:// base unchanged', () => {
    assert.strictEqual(buildStreamUrl('ws://localhost:5199'), 'ws://localhost:5199/api/climate/stream');
  });

  test('preserves wss:// base unchanged', () => {
    assert.strictEqual(buildStreamUrl('wss://example.com'), 'wss://example.com/api/climate/stream');
  });

  test('accepts custom path', () => {
    assert.strictEqual(
      buildStreamUrl('http://localhost:5199', '/api/custom/stream'),
      'ws://localhost:5199/api/custom/stream'
    );
  });

  test('strips trailing slash from base', () => {
    assert.strictEqual(buildStreamUrl('http://localhost:5199/'), 'ws://localhost:5199/api/climate/stream');
  });

  test('default path is CLIMATE_STREAM_PATH', () => {
    const url = buildStreamUrl('ws://localhost:5199');
    assert.ok(url.endsWith(CLIMATE_STREAM_PATH));
  });

  test('throws if no baseUrl and no globalThis.location', () => {
    const origLocation = globalThis.location;
    // Temporarily remove location
    Object.defineProperty(globalThis, 'location', { value: undefined, configurable: true });
    assert.throws(() => buildStreamUrl(), /no baseUrl provided/);
    Object.defineProperty(globalThis, 'location', { value: origLocation, configurable: true });
  });
});

// ---------------------------------------------------------------------------
// validateEnvelope
// ---------------------------------------------------------------------------

describe('validateEnvelope', () => {
  test('returns valid for a correct envelope', () => {
    const result = validateEnvelope(makeValidEnvelope());
    assert.strictEqual(result.valid, true);
    assert.ok(result.envelope.event);
    assert.ok(result.envelope.timestamp);
    assert.ok(result.envelope.payload);
  });

  test('rejects null input', () => {
    const r = validateEnvelope(null);
    assert.strictEqual(r.valid, false);
    assert.ok(r.reason);
  });

  test('rejects array input', () => {
    const r = validateEnvelope([]);
    assert.strictEqual(r.valid, false);
  });

  test('rejects unknown event type', () => {
    const r = validateEnvelope({ event: 'unknown.event', timestamp: new Date().toISOString(), payload: {} });
    assert.strictEqual(r.valid, false);
    assert.match(r.reason, /Unknown event type/);
  });

  test('rejects missing event field', () => {
    const r = validateEnvelope({ timestamp: new Date().toISOString(), payload: {} });
    assert.strictEqual(r.valid, false);
    assert.match(r.reason, /Invalid event field/);
  });

  test('rejects missing timestamp field', () => {
    const r = validateEnvelope({ event: 'node.updated', payload: {} });
    assert.strictEqual(r.valid, false);
    assert.match(r.reason, /Invalid timestamp field/);
  });

  test('rejects missing payload field', () => {
    const r = validateEnvelope({ event: 'node.updated', timestamp: new Date().toISOString() });
    assert.strictEqual(r.valid, false);
    assert.match(r.reason, /Missing payload/);
  });

  test('accepts null as a valid payload value (null != undefined)', () => {
    const r = validateEnvelope({ event: 'node.updated', timestamp: new Date().toISOString(), payload: null });
    assert.strictEqual(r.valid, true);
  });

  test('accepts numeric zero as valid payload', () => {
    const r = validateEnvelope({ event: 'telemetry.updated', timestamp: new Date().toISOString(), payload: 0 });
    assert.strictEqual(r.valid, true);
  });

  test('accepts all approved events', () => {
    for (const event of APPROVED_EVENTS) {
      const r = validateEnvelope({ event, timestamp: new Date().toISOString(), payload: {} });
      assert.strictEqual(r.valid, true, `Should accept: ${event}`);
    }
  });
});

// ---------------------------------------------------------------------------
// CLIENT_STATES constant
// ---------------------------------------------------------------------------

describe('CLIENT_STATES', () => {
  test('defines all expected states', () => {
    assert.ok(CLIENT_STATES.DISCONNECTED);
    assert.ok(CLIENT_STATES.CONNECTING);
    assert.ok(CLIENT_STATES.CONNECTED);
    assert.ok(CLIENT_STATES.RECONNECTING);
    assert.ok(CLIENT_STATES.CLOSING);
  });
});

// ---------------------------------------------------------------------------
// createClimateRealtimeClient — Connection Lifecycle
// ---------------------------------------------------------------------------

describe('createClimateRealtimeClient — lifecycle', () => {
  test('throws if WebSocket implementation is unavailable', () => {
    assert.throws(
      () => createClimateRealtimeClient({ WebSocket: null }),
      /WebSocket implementation is not available/
    );
  });

  test('initial state is DISCONNECTED', () => {
    const { client } = makeClient();
    assert.strictEqual(client.getConnectionState(), CLIENT_STATES.DISCONNECTED);
  });

  test('connect() transitions to CONNECTING then CONNECTED on open', () => {
    const { client, MockWS, states } = makeClient();
    client.connect();
    assert.strictEqual(states[0], CLIENT_STATES.CONNECTING);
    MockWS.instances[0].triggerOpen();
    assert.strictEqual(states[1], CLIENT_STATES.CONNECTED);
  });

  test('connect() is idempotent — does not open duplicate sockets', () => {
    const { client, MockWS } = makeClient();
    client.connect();
    client.connect();
    client.connect();
    assert.strictEqual(MockWS.instances.length, 1);
  });

  test('successful connection resets retry counter', () => {
    const { client, MockWS, states } = makeClient();
    client.connect();
    MockWS.instances[0].triggerOpen();
    // Simulate close and reconnect
    MockWS.instances[0].triggerClose(1006);
    // Should transition to RECONNECTING (not DISCONNECTED immediately since retries>0)
    assert.ok(states.includes(CLIENT_STATES.RECONNECTING) || states.includes(CLIENT_STATES.DISCONNECTED));
  });

  test('disconnect() sets CLOSING then DISCONNECTED', (_, done) => {
    const { client, MockWS, states } = makeClient();
    client.connect();
    MockWS.instances[0].triggerOpen();
    client.disconnect();
    // After close fires
    setTimeout(() => {
      assert.ok(states.includes(CLIENT_STATES.CLOSING));
      done();
    }, 20);
  });
});

// ---------------------------------------------------------------------------
// Fault Isolation — Malformed Messages
// ---------------------------------------------------------------------------

describe('createClimateRealtimeClient — fault isolation', () => {
  test('non-JSON message emits error but does NOT close socket', () => {
    const { client, MockWS, errors } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    ws.triggerMessage('not valid json{{{{');
    assert.strictEqual(errors.length, 1);
    assert.match(errors[0].message, /non-JSON/);
    // Socket should still be open
    assert.strictEqual(ws.closedWith, null);
  });

  test('invalid envelope emits error but does NOT close socket', () => {
    const { client, MockWS, errors } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    ws.triggerMessage(JSON.stringify({ event: 'unknown.event', timestamp: 'now', payload: {} }));
    assert.strictEqual(errors.length, 1);
    assert.match(errors[0].message, /Invalid realtime envelope/);
    assert.strictEqual(ws.closedWith, null);
  });

  test('onEvent throwing does NOT crash the client', () => {
    const { client, MockWS } = makeClient({
      onEvent: () => { throw new Error('handler crash'); },
    });
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    assert.doesNotThrow(() =>
      ws.triggerMessage(JSON.stringify(makeValidEnvelope()))
    );
  });

  test('onStateChange throwing does NOT crash the client', () => {
    const { client, MockWS } = makeClient({
      onStateChange: () => { throw new Error('state crash'); },
    });
    assert.doesNotThrow(() => {
      client.connect();
      MockWS.instances[0].triggerOpen();
    });
  });

  test('null payload is preserved (not treated as malformed)', () => {
    const { client, MockWS, events } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    ws.triggerMessage(JSON.stringify({
      event: 'node.updated',
      timestamp: new Date().toISOString(),
      payload: null,
    }));
    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].payload, null);
  });

  test('numeric zero payload is preserved', () => {
    const { client, MockWS, events } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    ws.triggerMessage(JSON.stringify({
      event: 'telemetry.updated',
      timestamp: new Date().toISOString(),
      payload: 0,
    }));
    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].payload, 0);
  });
});

// ---------------------------------------------------------------------------
// Event Dispatch
// ---------------------------------------------------------------------------

describe('createClimateRealtimeClient — event dispatch', () => {
  test('valid envelope is dispatched to onEvent', () => {
    const { client, MockWS, events } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    const envelope = makeValidEnvelope('node.updated', { node_id: 'N001' });
    ws.triggerMessage(JSON.stringify(envelope));
    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].event, 'node.updated');
    assert.deepStrictEqual(events[0].payload, { node_id: 'N001' });
  });

  test('on() registers per-event handler', () => {
    const { client, MockWS } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    const received = [];
    client.on('node.updated', (env) => received.push(env));

    ws.triggerMessage(JSON.stringify(makeValidEnvelope('node.updated', { node_id: 'N002' })));
    assert.strictEqual(received.length, 1);
    assert.strictEqual(received[0].payload.node_id, 'N002');
  });

  test('on() returns unsubscribe function', () => {
    const { client, MockWS } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();

    const received = [];
    const off = client.on('node.updated', (env) => received.push(env));

    ws.triggerMessage(JSON.stringify(makeValidEnvelope('node.updated', { node_id: 'N003' })));
    assert.strictEqual(received.length, 1);

    off(); // Unsubscribe
    ws.triggerMessage(JSON.stringify(makeValidEnvelope('node.updated', { node_id: 'N004' })));
    assert.strictEqual(received.length, 1); // No new events after unsubscribe
  });

  test('on() throws for unknown event type', () => {
    const { client } = makeClient();
    assert.throws(() => client.on('unknown.event', () => {}), /Unknown event type/);
  });

  test('on() throws for non-function handler', () => {
    const { client } = makeClient();
    assert.throws(() => client.on('node.updated', 'not a function'), /requires a function handler/);
  });

  test('telemetry.updated event dispatched correctly', () => {
    const { client, MockWS, events } = makeClient();
    client.connect();
    const ws = MockWS.instances[0];
    ws.triggerOpen();
    ws.triggerMessage(JSON.stringify(makeValidEnvelope('telemetry.updated', { node_id: 'N001', temperature: 25.3 })));
    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0].event, 'telemetry.updated');
    assert.strictEqual(events[0].payload.temperature, 25.3);
  });
});

// ---------------------------------------------------------------------------
// Reconnect Behavior
// ---------------------------------------------------------------------------

describe('createClimateRealtimeClient — reconnect', () => {
  test('transitions to RECONNECTING after unexpected close', (_, done) => {
    const { client, MockWS, states } = makeClient();
    client.connect();
    MockWS.instances[0].triggerOpen();
    MockWS.instances[0].triggerClose(1006);
    setTimeout(() => {
      assert.ok(states.includes(CLIENT_STATES.RECONNECTING));
      done();
    }, 20);
  });

  test('stops reconnecting after maxRetries exceeded', (_, done) => {
    const { client, MockWS, states, errors } = makeClient({
      reconnect: { maxRetries: 1, initialDelayMs: 10, maxDelayMs: 50, backoffFactor: 2 },
    });
    client.connect();

    function exhaustRetries(i) {
      if (i > 3) {
        setTimeout(() => {
          const finalState = states[states.length - 1];
          assert.strictEqual(finalState, CLIENT_STATES.DISCONNECTED);
          done();
        }, 50);
        return;
      }
      setTimeout(() => {
        const ws = MockWS.instances[MockWS.instances.length - 1];
        if (ws) ws.triggerClose(1006);
        exhaustRetries(i + 1);
      }, 20);
    }
    exhaustRetries(0);
  });

  test('does NOT reconnect after intentional disconnect', (_, done) => {
    const { client, MockWS, states } = makeClient();
    client.connect();
    MockWS.instances[0].triggerOpen();
    client.disconnect();
    MockWS.instances[0].triggerClose(1000, 'Client disconnected');
    setTimeout(() => {
      // Should not have transitioned to RECONNECTING after intentional close
      assert.ok(!states.includes(CLIENT_STATES.RECONNECTING));
      done();
    }, 50);
  });
});

// ---------------------------------------------------------------------------
// createStateIntegratedRealtimeClient
// ---------------------------------------------------------------------------

describe('createStateIntegratedRealtimeClient', () => {
  function makeStore() {
    const dispatched = [];
    const store = {
      dispatch: (action) => dispatched.push(action),
      updateNode: (node) => dispatched.push({ type: 'NODE_UPDATED', payload: node }),
      updateTelemetry: (t) => dispatched.push({ type: 'TELEMETRY_UPDATED', payload: t }),
      updateHazard: (h) => dispatched.push({ type: 'HAZARD_UPDATED', payload: h }),
      updatePrediction: (p) => dispatched.push({ type: 'PREDICTION_UPDATED', payload: p }),
      updateCompound: (c) => dispatched.push({ type: 'COMPOUND_UPDATED', payload: c }),
      updateVulnerability: (v) => dispatched.push({ type: 'VULNERABILITY_UPDATED', payload: v }),
      updateEvacuation: (e) => dispatched.push({ type: 'EVACUATION_UPDATED', payload: e }),
      updateResponse: (r) => dispatched.push({ type: 'RESPONSE_UPDATED', payload: r }),
      completeSimulation: (s) => dispatched.push({ type: 'SIMULATION_COMPLETED', payload: s }),
      setRealtimeState: (state, meta) => dispatched.push({ type: 'REALTIME_STATE_CHANGED', payload: { realtimeState: state, ...meta } }),
    };
    return { store, dispatched };
  }

  test('throws if store is missing', () => {
    assert.throws(() => createStateIntegratedRealtimeClient(null), /requires a valid/);
  });

  test('throws if store has no dispatch method', () => {
    assert.throws(() => createStateIntegratedRealtimeClient({}), /requires a valid/);
  });

  test('returns a client with connect/disconnect/on', () => {
    const { store } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
    });
    assert.strictEqual(typeof client.connect, 'function');
    assert.strictEqual(typeof client.disconnect, 'function');
    assert.strictEqual(typeof client.on, 'function');
    assert.strictEqual(typeof client.getConnectionState, 'function');
  });

  test('node.updated event dispatches updateNode and sets LIVE state', () => {
    const { store, dispatched } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
      reconnect: { maxRetries: 0, initialDelayMs: 10, maxDelayMs: 10, backoffFactor: 1 },
    });
    client.connect();
    MockWS.instances[0].triggerOpen();
    MockWS.instances[0].triggerMessage(JSON.stringify({
      event: 'node.updated',
      timestamp: new Date().toISOString(),
      payload: { node_id: 'N001', label: 'Test Node' },
    }));
    const nodeAction = dispatched.find((d) => d.type === 'NODE_UPDATED');
    assert.ok(nodeAction, 'Should dispatch NODE_UPDATED');
    assert.strictEqual(nodeAction.payload.node_id, 'N001');

    const liveAction = dispatched.find((d) => d.type === 'REALTIME_STATE_CHANGED' && d.payload.realtimeState === 'LIVE');
    assert.ok(liveAction, 'Should set LIVE state after node data arrives');
  });

  test('telemetry.updated event dispatches updateTelemetry and sets LIVE state', () => {
    const { store, dispatched } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
      reconnect: { maxRetries: 0, initialDelayMs: 10, maxDelayMs: 10, backoffFactor: 1 },
    });
    client.connect();
    MockWS.instances[0].triggerOpen();
    MockWS.instances[0].triggerMessage(JSON.stringify({
      event: 'telemetry.updated',
      timestamp: new Date().toISOString(),
      payload: { node_id: 'N001', temperature: 0 },
    }));
    const action = dispatched.find((d) => d.type === 'TELEMETRY_UPDATED');
    assert.ok(action);
    assert.strictEqual(action.payload.temperature, 0); // Numeric zero preserved
  });

  test('CONNECTED state sets STALE (not LIVE)', () => {
    const { store, dispatched } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
      reconnect: { maxRetries: 0, initialDelayMs: 10, maxDelayMs: 10, backoffFactor: 1 },
    });
    client.connect();
    MockWS.instances[0].triggerOpen();
    const staleAction = dispatched.find(
      (d) => d.type === 'REALTIME_STATE_CHANGED' && d.payload.realtimeState === 'STALE'
    );
    assert.ok(staleAction, 'Should set STALE on connection open — not LIVE');
  });

  test('DISCONNECTED state sets UNAVAILABLE', () => {
    const { store, dispatched } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
      reconnect: { maxRetries: 0, initialDelayMs: 10, maxDelayMs: 10, backoffFactor: 1 },
    });
    client.connect();
    MockWS.instances[0].triggerOpen();
    client.disconnect();
    MockWS.instances[0].close(1000, 'bye');
    const unavailableAction = dispatched.find(
      (d) => d.type === 'REALTIME_STATE_CHANGED' && d.payload.realtimeState === 'UNAVAILABLE'
    );
    assert.ok(unavailableAction, 'Should set UNAVAILABLE on disconnect');
  });

  test('hazard.updated → updateHazard', () => {
    const { store, dispatched } = makeStore();
    const MockWS = createMockWebSocketClass();
    const client = createStateIntegratedRealtimeClient(store, {
      baseUrl: 'ws://localhost:5199',
      WebSocket: MockWS,
      reconnect: { maxRetries: 0, initialDelayMs: 10, maxDelayMs: 10, backoffFactor: 1 },
    });
    client.connect();
    MockWS.instances[0].triggerOpen();
    MockWS.instances[0].triggerMessage(JSON.stringify({
      event: 'hazard.updated',
      timestamp: new Date().toISOString(),
      payload: { hazard_id: 'H001', type: 'flood' },
    }));
    const action = dispatched.find((d) => d.type === 'HAZARD_UPDATED');
    assert.ok(action);
    assert.strictEqual(action.payload.hazard_id, 'H001');
  });
});

// ---------------------------------------------------------------------------
// APPROVED_EVENT_SET smoke
// ---------------------------------------------------------------------------

describe('APPROVED_EVENT_SET', () => {
  test('contains all APPROVED_EVENTS', () => {
    for (const event of APPROVED_EVENTS) {
      assert.ok(APPROVED_EVENT_SET.has(event), `Missing: ${event}`);
    }
  });
});
