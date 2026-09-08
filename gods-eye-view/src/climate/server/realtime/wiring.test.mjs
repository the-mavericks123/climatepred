/**
 * Step 8J.2: Telemetry Ingestion to Realtime WebSocket Event Wiring Tests
 *
 * Verifies the complete pipeline:
 *   MQTT → Validation → Ingestion → DB Persistence → Realtime Event Broadcast → WS Clients
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { WebSocket } from 'ws';

import { createClimateServer } from '../index.js';
import { InMemoryClimateRepository } from '../db/inMemoryRepository.js';
import { createMqttAdapter } from '../mqtt/adapter.js';
import { createIngestionOrchestrator } from '../ingestion/orchestrator.js';
import { createClimateRealtimeServer } from './server.js';

describe('Step 8J.2: Ingestion → Realtime WebSocket Event Wiring', () => {
  let server;
  let port;
  let repository;
  let mqttAdapter;
  let realtimeServer;
  let orchestrator;
  let mockMqttClient;

  function createMockMqttClient() {
    const handlers = {};
    return {
      handlers,
      on(event, fn) {
        handlers[event] = fn;
        return this;
      },
      subscribe(topic, opts, cb) {
        if (typeof opts === 'function') opts(null);
        else if (typeof cb === 'function') cb(null);
        return this;
      },
      end(force, cb) {
        if (typeof force === 'function') force();
        else if (typeof cb === 'function') cb();
        return this;
      },
      simulateMessage(topic, payload) {
        if (handlers.message) {
          const buffer = Buffer.isBuffer(payload) ? payload : Buffer.from(typeof payload === 'string' ? payload : JSON.stringify(payload));
          handlers.message(topic, buffer);
        }
      },
    };
  }

  beforeEach(async () => {
    server = http.createServer((req, res) => {
      res.statusCode = 404;
      res.end('Not Found');
    });

    await new Promise((resolve) => {
      server.listen(0, '127.0.0.1', () => {
        port = server.address().port;
        resolve();
      });
    });

    repository = new InMemoryClimateRepository();
    await repository.init();

    mockMqttClient = createMockMqttClient();
    mqttAdapter = createMqttAdapter();
    mqttAdapter.start(mockMqttClient);

    realtimeServer = createClimateRealtimeServer({ httpServer: server });
    realtimeServer.start();

    orchestrator = createIngestionOrchestrator({
      repository,
      mqttAdapter,
      realtimeServer,
    });
    orchestrator.start();
  });

  afterEach(async () => {
    if (orchestrator) orchestrator.stop();
    if (mqttAdapter) mqttAdapter.stop();
    if (realtimeServer) realtimeServer.stop();
    if (repository) await repository.close();
    if (server) await new Promise((resolve) => server.close(resolve));
  });

  test('valid telemetry commits to repository and emits node.updated and telemetry.updated', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
    });

    const receivedMessages = [];
    ws.on('message', (data) => {
      receivedMessages.push(JSON.parse(data.toString()));
    });

    const telemetryPayload = {
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00.000Z',
      latitude: 12.9716,
      longitude: 77.5946,
      temperature: 26.4,
      humidity: 65.2,
      pressure: 1012.4,
      rainfall: 0.0,
      soil_moisture: null,
      water_level: null,
      air_quality: 42.0,
      battery: 3.98,
    };

    mockMqttClient.simulateMessage('climate/nodes/NODE-001/telemetry', telemetryPayload);

    // Wait a brief moment for async DB persistence and WS broadcast
    await new Promise((r) => setTimeout(r, 60));

    // 1. Verify DB persistence
    const node = await repository.getNode('NODE-001');
    assert.ok(node, 'Node must be registered in repository');
    assert.equal(node.node_id, 'NODE-001');

    const readings = await repository.getSensorReadings({ nodeId: 'NODE-001' });
    assert.equal(readings.length, 1);

    // 2. Verify WebSocket received exactly 2 events: node.updated and telemetry.updated
    assert.equal(receivedMessages.length, 2);

    const nodeEvent = receivedMessages.find((m) => m.event === 'node.updated');
    const telemetryEvent = receivedMessages.find((m) => m.event === 'telemetry.updated');

    assert.ok(nodeEvent, 'Must emit node.updated');
    assert.ok(telemetryEvent, 'Must emit telemetry.updated');

    // Verify node.updated payload has real available data only
    assert.equal(nodeEvent.payload.node_id, 'NODE-001');
    assert.equal(nodeEvent.payload.latitude, 12.9716);
    assert.equal(nodeEvent.payload.longitude, 77.5946);
    assert.equal(nodeEvent.payload.status, 'online');
    assert.equal(nodeEvent.payload.timestamp, '2026-09-08T00:00:00.000Z');
    assert.equal(nodeEvent.payload.hazard, undefined, 'Must not fabricate hazard data');
    assert.equal(nodeEvent.payload.prediction, undefined, 'Must not fabricate prediction data');

    // Verify telemetry.updated payload has canonical 13 fields with strict preservation
    assert.equal(telemetryEvent.payload.node_id, 'NODE-001');
    assert.equal(telemetryEvent.payload.rainfall, 0.0);
    assert.equal(telemetryEvent.payload.soil_moisture, null);
    assert.equal(telemetryEvent.payload.water_level, null);
    assert.equal(telemetryEvent.payload.battery, 3.98);

    ws.close();
  });

  test('preserves numeric zero and null values exactly in realtime payload', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    let telemetryMsg = null;
    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.event === 'telemetry.updated') telemetryMsg = msg;
    });

    const payloadWithZerosAndNulls = {
      schema_version: '1.0.0',
      node_id: 'NODE-002',
      timestamp: '2026-09-08T00:05:00.000Z',
      latitude: 0.0,
      longitude: 0.0,
      temperature: 0.0,
      humidity: 0.0,
      pressure: 1000.0,
      rainfall: 0.0,
      soil_moisture: null,
      water_level: null,
      air_quality: null,
      battery: 4.1,
    };

    mockMqttClient.simulateMessage('climate/nodes/NODE-002/telemetry', payloadWithZerosAndNulls);

    await new Promise((r) => setTimeout(r, 60));

    assert.ok(telemetryMsg, 'Must receive telemetry.updated event');
    assert.strictEqual(telemetryMsg.payload.latitude, 0.0);
    assert.strictEqual(telemetryMsg.payload.longitude, 0.0);
    assert.strictEqual(telemetryMsg.payload.temperature, 0.0);
    assert.strictEqual(telemetryMsg.payload.humidity, 0.0);
    assert.strictEqual(telemetryMsg.payload.rainfall, 0.0);
    assert.strictEqual(telemetryMsg.payload.soil_moisture, null);
    assert.strictEqual(telemetryMsg.payload.water_level, null);
    assert.strictEqual(telemetryMsg.payload.air_quality, null);

    ws.close();
  });

  test('invalid telemetry does not emit realtime events', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    const received = [];
    ws.on('message', (d) => received.push(d));

    // Invalid: temperature out of physical bounds (999 °C)
    mockMqttClient.simulateMessage('climate/nodes/NODE-001/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00.000Z',
      latitude: 12.9716,
      longitude: 77.5946,
      temperature: 999.0,
    });

    await new Promise((r) => setTimeout(r, 50));
    assert.equal(received.length, 0, 'No realtime events should be emitted for invalid telemetry');

    ws.close();
  });

  test('node_id mismatch does not emit realtime events', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    const received = [];
    ws.on('message', (d) => received.push(d));

    // Topic is NODE-001, payload has NODE-999
    mockMqttClient.simulateMessage('climate/nodes/NODE-001/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-999',
      timestamp: '2026-09-08T00:00:00.000Z',
      latitude: 12.9716,
      longitude: 77.5946,
      temperature: 25.0,
    });

    await new Promise((r) => setTimeout(r, 50));
    assert.equal(received.length, 0, 'No realtime events should be emitted on node_id mismatch');

    ws.close();
  });

  test('persistence failure does not emit realtime events', async () => {
    // Inject a failing repository
    const failingRepo = {
      async upsertNode() {
        throw new Error('Database connection lost');
      },
      async insertSensorReading() {
        throw new Error('Database connection lost');
      },
    };

    let persistenceErrorCaught = false;
    const failingMqttAdapter = createMqttAdapter();
    const failingMqttClient = createMockMqttClient();
    failingMqttAdapter.start(failingMqttClient);

    const failingOrchestrator = createIngestionOrchestrator({
      repository: failingRepo,
      mqttAdapter: failingMqttAdapter,
      realtimeServer,
      options: {
        onPersistenceError: () => {
          persistenceErrorCaught = true;
        },
      },
    });
    failingOrchestrator.start();

    const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    const received = [];
    ws.on('message', (d) => received.push(d));

    failingMqttClient.simulateMessage('climate/nodes/NODE-001/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00.000Z',
      latitude: 12.9716,
      longitude: 77.5946,
      temperature: 25.0,
    });

    await new Promise((r) => setTimeout(r, 60));

    assert.equal(persistenceErrorCaught, true, 'Persistence error must be surfaced');
    assert.equal(received.length, 0, 'Realtime event must NOT be emitted when persistence fails');

    failingOrchestrator.stop();
    failingMqttAdapter.stop();
    ws.close();
  });

  test('multiple connected clients receive the event concurrently', async () => {
    const c1 = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    const c2 = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);

    await Promise.all([
      new Promise((res) => c1.on('open', res)),
      new Promise((res) => c2.on('open', res)),
    ]);

    const msgs1 = [];
    const msgs2 = [];
    c1.on('message', (d) => msgs1.push(JSON.parse(d.toString())));
    c2.on('message', (d) => msgs2.push(JSON.parse(d.toString())));

    mockMqttClient.simulateMessage('climate/nodes/NODE-003/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-003',
      timestamp: '2026-09-08T00:10:00.000Z',
      latitude: 13.0827,
      longitude: 80.2707,
      temperature: 31.2,
      humidity: 80.0,
    });

    await new Promise((r) => setTimeout(r, 60));

    assert.equal(msgs1.length, 2);
    assert.equal(msgs2.length, 2);
    assert.equal(msgs1[0].event, 'node.updated');
    assert.equal(msgs2[0].event, 'node.updated');
    assert.equal(msgs1[1].event, 'telemetry.updated');
    assert.equal(msgs2[1].event, 'telemetry.updated');

    c1.close();
    c2.close();
  });

  test('one broken client does not block other clients or fail ingestion', async () => {
    const goodClient = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
    await new Promise((resolve) => goodClient.on('open', resolve));

    // Inject a client whose send() throws
    const throwingClient = {
      readyState: WebSocket.OPEN,
      send() {
        throw new Error('Socket pipe error');
      },
      close() {},
      on() {},
    };
    realtimeServer.clients.add(throwingClient);

    const received = [];
    goodClient.on('message', (d) => received.push(JSON.parse(d.toString())));

    mockMqttClient.simulateMessage('climate/nodes/NODE-004/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-004',
      timestamp: '2026-09-08T00:15:00.000Z',
      latitude: 19.0760,
      longitude: 72.8777,
      temperature: 28.0,
    });

    await new Promise((r) => setTimeout(r, 60));

    // Good client must receive events despite broken client
    assert.equal(received.length, 2);
    assert.equal(received[0].event, 'node.updated');
    assert.equal(received[1].event, 'telemetry.updated');

    goodClient.close();
  });

  test('integrated createClimateServer wires ingestion to realtime automatically', async () => {
    // Dedicated isolated server for integration test
    const intServer = http.createServer();
    await new Promise((res) => intServer.listen(0, '127.0.0.1', res));
    const intPort = intServer.address().port;

    const mockMqtt = createMockMqttClient();
    const intMqttAdapter = createMqttAdapter();
    intMqttAdapter.start(mockMqtt);

    const intRepo = new InMemoryClimateRepository();
    await intRepo.init();

    const climate = createClimateServer({
      httpServer: intServer,
      repository: intRepo,
      mqttAdapter: intMqttAdapter,
    });
    await climate.start();

    const ws = new WebSocket(`ws://127.0.0.1:${intPort}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    const events = [];
    ws.on('message', (d) => events.push(JSON.parse(d.toString())));

    mockMqtt.simulateMessage('climate/nodes/NODE-005/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-005',
      timestamp: '2026-09-08T00:20:00.000Z',
      latitude: 28.6139,
      longitude: 77.2090,
      temperature: 30.5,
      rainfall: 1.2,
    });

    await new Promise((r) => setTimeout(r, 60));

    assert.equal(events.length, 2);
    assert.equal(events[0].event, 'node.updated');
    assert.equal(events[0].payload.node_id, 'NODE-005');
    assert.equal(events[1].event, 'telemetry.updated');
    assert.equal(events[1].payload.rainfall, 1.2);

    ws.close();
    await climate.stop();
    await new Promise((res) => intServer.close(res));
  });

  test('repeated server start does not create duplicate listeners or duplicate events', async () => {
    const intServer = http.createServer();
    await new Promise((res) => intServer.listen(0, '127.0.0.1', res));
    const intPort = intServer.address().port;

    const mockMqtt = createMockMqttClient();
    const intMqttAdapter = createMqttAdapter();
    intMqttAdapter.start(mockMqtt);

    const intRepo = new InMemoryClimateRepository();
    await intRepo.init();

    const climate = createClimateServer({
      httpServer: intServer,
      repository: intRepo,
      mqttAdapter: intMqttAdapter,
    });
    await climate.start();
    await climate.start(); // idempotent second start

    const ws = new WebSocket(`ws://127.0.0.1:${intPort}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    const events = [];
    ws.on('message', (d) => events.push(JSON.parse(d.toString())));

    mockMqtt.simulateMessage('climate/nodes/NODE-006/telemetry', {
      schema_version: '1.0.0',
      node_id: 'NODE-006',
      timestamp: '2026-09-08T00:25:00.000Z',
      latitude: 22.5726,
      longitude: 88.3639,
      temperature: 27.8,
    });

    await new Promise((r) => setTimeout(r, 60));

    // Must be exactly 2 events (not 4)
    assert.equal(events.length, 2);

    ws.close();
    await climate.stop();
    await new Promise((res) => intServer.close(res));
  });

  test('clean shutdown stops ingestion and cleans up realtime event delivery', async () => {
    const intServer = http.createServer();
    await new Promise((res) => intServer.listen(0, '127.0.0.1', res));
    const intPort = intServer.address().port;

    const intRepo = new InMemoryClimateRepository();
    await intRepo.init();

    const climate = createClimateServer({
      httpServer: intServer,
      repository: intRepo,
    });
    await climate.start();

    const ws = new WebSocket(`ws://127.0.0.1:${intPort}/api/climate/stream`);
    await new Promise((resolve) => ws.on('open', resolve));

    let closedCode = null;
    ws.on('close', (code) => {
      closedCode = code;
    });

    await climate.stop();

    await new Promise((r) => setTimeout(r, 50));

    assert.equal(closedCode, 1001, 'Connected clients closed with 1001 on shutdown');
    assert.equal(climate.realtimeServer.getClientCount(), 0);
    assert.equal(climate.orchestrator.status().state, 'idle');

    await new Promise((res) => intServer.close(res));
  });
});
