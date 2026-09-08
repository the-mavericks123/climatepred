/**
 * Climate Eye S1 — MQTT Ingestion Unit Tests
 *
 * Test coverage for the MQTT ingestion boundary (Step 8F):
 *
 *   A. Topic parsing (parseTopic)
 *   B. Topic type recognition helpers
 *   C. node_id extraction from topics
 *   D. handleMessage — valid telemetry forwarding
 *   E. handleMessage — invalid telemetry rejection
 *   F. handleMessage — node_id mismatch
 *   G. handleMessage — JSON parse errors
 *   H. handleMessage — status & heartbeat passthrough
 *   I. Adapter lifecycle — start/stop safety, repeated calls
 *   J. Adapter dispatch — callback routing
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  parseTopic,
  isTelemetryTopic,
  isStatusTopic,
  isHeartbeatTopic,
  TOPIC_TYPES,
  SUBSCRIPTIONS,
} from './topics.js';

import {
  handleMessage,
  HANDLER_RESULTS,
} from './handler.js';

import {
  createMqttAdapter,
  ADAPTER_STATES,
} from './adapter.js';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** A fully-valid canonical telemetry payload for NODE-001. */
const VALID_PAYLOAD = {
  schema_version: '1.0.0',
  node_id:        'NODE-001',
  timestamp:      '2026-09-07T22:45:00Z',
  latitude:       30.2672,
  longitude:     -97.7431,
  temperature:    26.4,
  humidity:       58.2,
  pressure:       1013.25,
  rainfall:       0.0,
  soil_moisture:  null,
  water_level:    null,
  air_quality:    null,
  battery:        3.92,
};

function validJson(overrides = {}) {
  return JSON.stringify(Object.assign({}, VALID_PAYLOAD, overrides));
}

// ---------------------------------------------------------------------------
// A. Topic parsing
// ---------------------------------------------------------------------------

describe('A. Topic parsing (parseTopic)', () => {
  it('A1 — parses telemetry topic correctly', () => {
    const r = parseTopic('climate/nodes/NODE-001/telemetry');
    assert.equal(r.matched, true);
    assert.equal(r.topicType, TOPIC_TYPES.TELEMETRY);
    assert.equal(r.nodeId, 'NODE-001');
  });

  it('A2 — parses status topic correctly', () => {
    const r = parseTopic('climate/nodes/NODE-002/status');
    assert.equal(r.matched, true);
    assert.equal(r.topicType, TOPIC_TYPES.STATUS);
    assert.equal(r.nodeId, 'NODE-002');
  });

  it('A3 — parses heartbeat topic correctly', () => {
    const r = parseTopic('climate/nodes/NODE-003/heartbeat');
    assert.equal(r.matched, true);
    assert.equal(r.topicType, TOPIC_TYPES.HEARTBEAT);
    assert.equal(r.nodeId, 'NODE-003');
  });

  it('A4 — returns unmatched for an unknown topic', () => {
    const r = parseTopic('sensors/data/temperature');
    assert.equal(r.matched, false);
    assert.equal(r.topicType, TOPIC_TYPES.UNKNOWN);
    assert.equal(r.nodeId, null);
  });

  it('A5 — returns unmatched for a non-string input', () => {
    const r = parseTopic(null);
    assert.equal(r.matched, false);
    assert.equal(r.nodeId, null);
  });

  it('A6 — returns unmatched for a topic with an invalid topic suffix', () => {
    const r = parseTopic('climate/nodes/NODE-001/data');
    assert.equal(r.matched, false);
  });

  it('A7 — returns unmatched for a topic with a node_id too short (< 3 chars)', () => {
    const r = parseTopic('climate/nodes/AB/telemetry');
    assert.equal(r.matched, false);
  });

  it('A8 — returns unmatched for a topic with a node_id too long (> 32 chars)', () => {
    const longId = 'A'.repeat(33);
    const r = parseTopic(`climate/nodes/${longId}/telemetry`);
    assert.equal(r.matched, false);
  });

  it('A9 — returns unmatched for a topic with spaces in node_id', () => {
    const r = parseTopic('climate/nodes/NODE 001/telemetry');
    assert.equal(r.matched, false);
  });

  it('A10 — accepts node_id with hyphens and underscores', () => {
    const r = parseTopic('climate/nodes/node_alpha-1/telemetry');
    assert.equal(r.matched, true);
    assert.equal(r.nodeId, 'node_alpha-1');
  });

  it('A11 — SUBSCRIPTIONS array contains all three wildcard patterns', () => {
    assert.ok(SUBSCRIPTIONS.includes('climate/nodes/+/telemetry'));
    assert.ok(SUBSCRIPTIONS.includes('climate/nodes/+/status'));
    assert.ok(SUBSCRIPTIONS.includes('climate/nodes/+/heartbeat'));
    assert.equal(SUBSCRIPTIONS.length, 3);
  });
});

// ---------------------------------------------------------------------------
// B. Topic type recognition helpers
// ---------------------------------------------------------------------------

describe('B. Topic type recognition', () => {
  it('B1 — isTelemetryTopic identifies telemetry topics', () => {
    assert.equal(isTelemetryTopic('climate/nodes/NODE-001/telemetry'), true);
    assert.equal(isTelemetryTopic('climate/nodes/NODE-001/status'),    false);
    assert.equal(isTelemetryTopic('climate/nodes/NODE-001/heartbeat'), false);
    assert.equal(isTelemetryTopic('unknown/topic'),                    false);
  });

  it('B2 — isStatusTopic identifies status topics', () => {
    assert.equal(isStatusTopic('climate/nodes/NODE-002/status'),     true);
    assert.equal(isStatusTopic('climate/nodes/NODE-002/telemetry'),  false);
    assert.equal(isStatusTopic('climate/nodes/NODE-002/heartbeat'),  false);
  });

  it('B3 — isHeartbeatTopic identifies heartbeat topics', () => {
    assert.equal(isHeartbeatTopic('climate/nodes/NODE-003/heartbeat'), true);
    assert.equal(isHeartbeatTopic('climate/nodes/NODE-003/telemetry'), false);
    assert.equal(isHeartbeatTopic('climate/nodes/NODE-003/status'),    false);
  });
});

// ---------------------------------------------------------------------------
// C. node_id extraction
// ---------------------------------------------------------------------------

describe('C. node_id extraction', () => {
  it('C1 — extracts node_id from telemetry topic', () => {
    assert.equal(parseTopic('climate/nodes/NODE-004/telemetry').nodeId, 'NODE-004');
  });

  it('C2 — extracts node_id from status topic', () => {
    assert.equal(parseTopic('climate/nodes/NODE-005/status').nodeId, 'NODE-005');
  });

  it('C3 — extracts node_id from heartbeat topic', () => {
    assert.equal(parseTopic('climate/nodes/ALPHA_NODE/heartbeat').nodeId, 'ALPHA_NODE');
  });

  it('C4 — nodeId is null for unrecognized topics', () => {
    assert.equal(parseTopic('junk/topic').nodeId, null);
  });
});

// ---------------------------------------------------------------------------
// D. handleMessage — valid telemetry forwarding
// ---------------------------------------------------------------------------

describe('D. handleMessage — valid telemetry forwarding', () => {
  it('D1 — valid telemetry payload returns NORMALIZED_TELEMETRY result', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson());
    assert.equal(r.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
    assert.equal(r.nodeId, 'NODE-001');
    assert.equal(r.topicType, TOPIC_TYPES.TELEMETRY);
    assert.ok(r.payload !== null);
    assert.equal(r.errors, null);
  });

  it('D2 — normalized payload contains all 13 canonical fields', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson());
    const fields = [
      'schema_version','node_id','timestamp','latitude','longitude',
      'temperature','humidity','pressure','rainfall',
      'soil_moisture','water_level','air_quality','battery',
    ];
    for (const f of fields) {
      assert.ok(Object.prototype.hasOwnProperty.call(r.payload, f), `missing: ${f}`);
    }
  });

  it('D3 — accepts a Buffer message (simulating real MQTT client)', () => {
    const buf = Buffer.from(validJson(), 'utf8');
    const r = handleMessage('climate/nodes/NODE-001/telemetry', buf);
    assert.equal(r.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
  });

  it('D4 — valid payload with absent optional fields normalizes them to null', () => {
    const minimal = {
      schema_version: '1.0.0',
      node_id:        'NODE-001',
      timestamp:      '2026-09-07T22:45:00Z',
      latitude:       30.2672,
      longitude:     -97.7431,
    };
    const r = handleMessage('climate/nodes/NODE-001/telemetry', JSON.stringify(minimal));
    assert.equal(r.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
    assert.equal(r.payload.temperature, null);
    assert.equal(r.payload.humidity,    null);
  });

  it('D5 — preserves numeric zero through the full pipeline', () => {
    const r = handleMessage(
      'climate/nodes/NODE-001/telemetry',
      validJson({ rainfall: 0, water_level: 0 }),
    );
    assert.equal(r.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
    assert.strictEqual(r.payload.rainfall,    0);
    assert.strictEqual(r.payload.water_level, 0);
  });
});

// ---------------------------------------------------------------------------
// E. handleMessage — invalid telemetry rejection
// ---------------------------------------------------------------------------

describe('E. handleMessage — invalid telemetry rejection', () => {
  it('E1 — rejects payload with invalid schema_version', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson({ schema_version: '2.0.0' }));
    assert.equal(r.result, HANDLER_RESULTS.VALIDATION_FAILED);
    assert.equal(r.payload, null);
    assert.ok(Array.isArray(r.errors) && r.errors.length > 0);
  });

  it('E2 — rejects payload with latitude out of WGS84 range', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson({ latitude: 999 }));
    assert.equal(r.result, HANDLER_RESULTS.VALIDATION_FAILED);
    assert.equal(r.payload, null);
  });

  it('E3 — rejects payload with temperature out of physical bounds', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson({ temperature: 999 }));
    assert.equal(r.result, HANDLER_RESULTS.VALIDATION_FAILED);
  });

  it('E4 — rejects payload with invalid timestamp (missing Z)', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson({ timestamp: '2026-09-07T22:45:00' }));
    assert.equal(r.result, HANDLER_RESULTS.VALIDATION_FAILED);
  });

  it('E5 — does not crash on rejection — result is returned, not thrown', () => {
    assert.doesNotThrow(() => {
      handleMessage('climate/nodes/NODE-001/telemetry', validJson({ humidity: -999 }));
    });
  });
});

// ---------------------------------------------------------------------------
// F. handleMessage — node_id mismatch
// ---------------------------------------------------------------------------

describe('F. handleMessage — node_id mismatch', () => {
  it('F1 — rejects when payload node_id differs from topic node_id', () => {
    const r = handleMessage(
      'climate/nodes/NODE-001/telemetry',
      validJson({ node_id: 'NODE-002' }),  // payload says NODE-002, topic says NODE-001
    );
    assert.equal(r.result, HANDLER_RESULTS.NODE_ID_MISMATCH);
    assert.equal(r.payload, null);
    assert.ok(r.errors[0].includes('NODE-001'));
    assert.ok(r.errors[0].includes('NODE-002'));
  });

  it('F2 — node_id in rejected result comes from the topic, not the payload', () => {
    const r = handleMessage(
      'climate/nodes/NODE-001/telemetry',
      validJson({ node_id: 'ATTACKER' }),
    );
    assert.equal(r.result, HANDLER_RESULTS.NODE_ID_MISMATCH);
    assert.equal(r.nodeId, 'NODE-001');  // topic is authoritative
  });

  it('F3 — accepts when payload node_id matches topic node_id exactly', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', validJson({ node_id: 'NODE-001' }));
    assert.equal(r.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
  });

  it('F4 — accepts when payload node_id is absent (topic provides it via validator)', () => {
    // node_id absent in payload → validator will reject (required field), not mismatch
    const { node_id, ...noId } = VALID_PAYLOAD;
    const r = handleMessage('climate/nodes/NODE-001/telemetry', JSON.stringify(noId));
    // The validator requires node_id — this should be VALIDATION_FAILED, not NODE_ID_MISMATCH
    assert.equal(r.result, HANDLER_RESULTS.VALIDATION_FAILED);
    assert.notEqual(r.result, HANDLER_RESULTS.NODE_ID_MISMATCH);
  });
});

// ---------------------------------------------------------------------------
// G. handleMessage — JSON parse errors
// ---------------------------------------------------------------------------

describe('G. handleMessage — JSON parse errors', () => {
  it('G1 — returns INVALID_JSON for malformed JSON', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', '{broken json}');
    assert.equal(r.result, HANDLER_RESULTS.INVALID_JSON);
    assert.equal(r.payload, null);
    assert.ok(r.errors[0].includes('invalid JSON'));
  });

  it('G2 — returns INVALID_JSON for empty string', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', '');
    assert.equal(r.result, HANDLER_RESULTS.INVALID_JSON);
  });

  it('G3 — returns INVALID_JSON for truncated JSON', () => {
    const r = handleMessage('climate/nodes/NODE-001/telemetry', '{"schema_version": "1.0.0"');
    assert.equal(r.result, HANDLER_RESULTS.INVALID_JSON);
  });

  it('G4 — does not crash on garbage Buffer input', () => {
    assert.doesNotThrow(() => {
      handleMessage('climate/nodes/NODE-001/telemetry', Buffer.from([0xff, 0xfe, 0x00]));
    });
  });
});

// ---------------------------------------------------------------------------
// H. handleMessage — status & heartbeat passthrough
// ---------------------------------------------------------------------------

describe('H. handleMessage — status & heartbeat passthrough', () => {
  it('H1 — status topic returns STATUS_RECEIVED regardless of payload', () => {
    const r = handleMessage('climate/nodes/NODE-001/status', '{"status":"online"}');
    assert.equal(r.result, HANDLER_RESULTS.STATUS_RECEIVED);
    assert.equal(r.nodeId, 'NODE-001');
    assert.equal(r.topicType, TOPIC_TYPES.STATUS);
    assert.equal(r.payload, null);
    assert.equal(r.errors, null);
  });

  it('H2 — heartbeat topic returns HEARTBEAT_RECEIVED regardless of payload', () => {
    const r = handleMessage('climate/nodes/NODE-002/heartbeat', '{"uptime_s":1234}');
    assert.equal(r.result, HANDLER_RESULTS.HEARTBEAT_RECEIVED);
    assert.equal(r.nodeId, 'NODE-002');
    assert.equal(r.topicType, TOPIC_TYPES.HEARTBEAT);
    assert.equal(r.payload, null);
    assert.equal(r.errors, null);
  });

  it('H3 — unknown topic returns UNKNOWN_TOPIC', () => {
    const r = handleMessage('some/random/topic', '{}');
    assert.equal(r.result, HANDLER_RESULTS.UNKNOWN_TOPIC);
    assert.equal(r.nodeId, null);
    assert.ok(r.errors.length > 0);
  });
});

// ---------------------------------------------------------------------------
// I. Adapter lifecycle — start/stop safety, repeated calls
// ---------------------------------------------------------------------------

describe('I. Adapter lifecycle safety', () => {
  it('I1 — adapter starts in IDLE state', () => {
    const adapter = createMqttAdapter();
    assert.equal(adapter.status().state, ADAPTER_STATES.IDLE);
  });

  it('I2 — stop() on an IDLE adapter is a safe no-op', () => {
    const adapter = createMqttAdapter();
    assert.doesNotThrow(() => adapter.stop());
    assert.equal(adapter.status().state, ADAPTER_STATES.IDLE);
  });

  it('I3 — stop() can be called multiple times safely', () => {
    const adapter = createMqttAdapter();
    assert.doesNotThrow(() => {
      adapter.stop();
      adapter.stop();
      adapter.stop();
    });
  });

  it('I4 — start() without a valid client throws TypeError', () => {
    const adapter = createMqttAdapter();
    assert.throws(
      () => adapter.start(null),
      TypeError,
    );
    assert.throws(
      () => adapter.start({}),
      TypeError,
    );
  });

  it('I5 — start() with a mock client that has subscribe/on/end is accepted', () => {
    const adapter = createMqttAdapter();
    const mockClient = {
      subscribe: (_topics, _opts, cb) => cb(null),  // simulate success
      on:        () => {},
      end:       () => {},
    };
    assert.doesNotThrow(() => adapter.start(mockClient));
  });

  it('I6 — repeated start() calls with a valid client are safe (no duplicate subscriptions)', () => {
    const adapter = createMqttAdapter();
    let subscribeCount = 0;
    const mockClient = {
      subscribe: (_topics, _opts, cb) => { subscribeCount++; cb(null); },
      on:        () => {},
      end:       () => {},
    };
    adapter.start(mockClient);
    adapter.start(mockClient);  // second call should be a no-op
    adapter.start(mockClient);  // third call should be a no-op
    assert.equal(subscribeCount, 1, 'subscribe() must be called exactly once');
  });

  it('I7 — start → stop → start cycle completes without errors', () => {
    const adapter = createMqttAdapter();
    const mockClient = {
      subscribe: (_topics, _opts, cb) => cb(null),
      on:        () => {},
      end:       () => {},
    };
    assert.doesNotThrow(() => {
      adapter.start(mockClient);
      adapter.stop();
      adapter.start(mockClient);
      adapter.stop();
    });
  });

  it('I8 — after stop(), status returns IDLE with empty subscriptions', () => {
    const adapter = createMqttAdapter();
    const mockClient = {
      subscribe: (_topics, _opts, cb) => cb(null),
      on:        () => {},
      end:       () => {},
    };
    adapter.start(mockClient);
    adapter.stop();
    const s = adapter.status();
    assert.equal(s.state, ADAPTER_STATES.IDLE);
    assert.deepEqual(s.subscriptions, []);
  });
});

// ---------------------------------------------------------------------------
// J. Adapter dispatch — callback routing
// ---------------------------------------------------------------------------

describe('J. Adapter dispatch — callback routing', () => {
  it('J1 — valid telemetry dispatches to onTelemetry callback', () => {
    const adapter = createMqttAdapter();
    let received = null;
    adapter.onTelemetry((r) => { received = r; });

    adapter._dispatch('climate/nodes/NODE-001/telemetry', validJson());
    assert.ok(received !== null, 'onTelemetry callback should have fired');
    assert.equal(received.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
    assert.equal(received.nodeId, 'NODE-001');
  });

  it('J2 — invalid telemetry dispatches to onRejected callback', () => {
    const adapter = createMqttAdapter();
    let rejected = null;
    adapter.onRejected((r) => { rejected = r; });

    adapter._dispatch('climate/nodes/NODE-001/telemetry', validJson({ latitude: 999 }));
    assert.ok(rejected !== null, 'onRejected callback should have fired');
    assert.notEqual(rejected.result, HANDLER_RESULTS.NORMALIZED_TELEMETRY);
  });

  it('J3 — node_id mismatch dispatches to onRejected callback', () => {
    const adapter = createMqttAdapter();
    let rejected = null;
    adapter.onRejected((r) => { rejected = r; });

    adapter._dispatch('climate/nodes/NODE-001/telemetry', validJson({ node_id: 'NODE-002' }));
    assert.ok(rejected !== null);
    assert.equal(rejected.result, HANDLER_RESULTS.NODE_ID_MISMATCH);
  });

  it('J4 — status message does NOT fire onTelemetry or onRejected', () => {
    const adapter = createMqttAdapter();
    let telFired = false;
    let rejFired = false;
    adapter.onTelemetry(() => { telFired = true; });
    adapter.onRejected(() => { rejFired = true; });

    adapter._dispatch('climate/nodes/NODE-001/status', '{"status":"online"}');
    assert.equal(telFired, false, 'onTelemetry must not fire for status');
    assert.equal(rejFired, false, 'onRejected must not fire for status');
  });

  it('J5 — heartbeat message does NOT fire onTelemetry or onRejected', () => {
    const adapter = createMqttAdapter();
    let telFired = false;
    let rejFired = false;
    adapter.onTelemetry(() => { telFired = true; });
    adapter.onRejected(() => { rejFired = true; });

    adapter._dispatch('climate/nodes/NODE-001/heartbeat', '{"uptime_s":123}');
    assert.equal(telFired, false);
    assert.equal(rejFired, false);
  });

  it('J6 — _dispatch does not throw even when no callbacks are registered', () => {
    const adapter = createMqttAdapter();
    assert.doesNotThrow(() => {
      adapter._dispatch('climate/nodes/NODE-001/telemetry', validJson());
      adapter._dispatch('climate/nodes/NODE-001/telemetry', '{bad json}');
    });
  });

  it('J7 — bad JSON dispatches to onRejected callback', () => {
    const adapter = createMqttAdapter();
    let rejected = null;
    adapter.onRejected((r) => { rejected = r; });

    adapter._dispatch('climate/nodes/NODE-001/telemetry', '{not json}');
    assert.ok(rejected !== null);
    assert.equal(rejected.result, HANDLER_RESULTS.INVALID_JSON);
  });
});
