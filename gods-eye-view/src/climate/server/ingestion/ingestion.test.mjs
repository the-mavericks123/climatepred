/**
 * Climate Eye S1 — Step 8H: MQTT → Repository Persistence Ingestion Tests
 *
 * Validates the end-to-end telemetry ingestion pipeline:
 *   MQTT message
 *     → topic parsing
 *     → JSON parsing
 *     → telemetry validation / normalization
 *     → data-driven node registration
 *     → sensor reading persistence
 *
 * Guarantees:
 *   - Data-driven node identity (NODE-001..005, NODE-006+)
 *   - Null and zero preservation
 *   - Optical/camera fields excluded
 *   - Safe error handling on DB errors (no uncaught exceptions, no server crashes)
 *   - Idempotent lifecycle and clean teardown
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { createMqttAdapter } from '../mqtt/adapter.js';
import { InMemoryClimateRepository } from '../db/inMemoryRepository.js';
import { createIngestionOrchestrator, ORCHESTRATOR_STATES } from './index.js';

describe('Step 8H: Telemetry Ingestion Orchestrator (MQTT → DB)', () => {
  let repo;
  let adapter;
  let orchestrator;
  let persistenceErrors;
  let rejectedMessages;

  beforeEach(() => {
    repo = new InMemoryClimateRepository();
    adapter = createMqttAdapter();
    persistenceErrors = [];
    rejectedMessages = [];

    orchestrator = createIngestionOrchestrator({
      repository: repo,
      mqttAdapter: adapter,
      options: {
        onPersistenceError: (err, payload) => {
          persistenceErrors.push({ err, payload });
        },
        onRejected: (result) => {
          rejectedMessages.push(result);
        },
      },
    });

    orchestrator.start();
  });

  it('orchestrator starts in RUNNING state and tracks metrics', () => {
    const s = orchestrator.status();
    assert.equal(s.state, ORCHESTRATOR_STATES.RUNNING);
    assert.equal(s.metrics.receivedCount, 0);
    assert.equal(s.metrics.persistedCount, 0);
    assert.equal(s.metrics.rejectedCount, 0);
    assert.equal(s.metrics.errorCount, 0);
  });

  it('persists valid MQTT telemetry and automatically registers the node', async () => {
    const topic = 'climate/nodes/NODE-001/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 30.2672,
      longitude: -97.7431,
      temperature: 26.4,
      humidity: 58.2,
      pressure: 1013.25,
      rainfall: 0.0,
      soil_moisture: 32.5,
      water_level: 12.0,
      air_quality: 15.4,
      battery: 3.92,
    });

    // Dispatch MQTT message
    adapter._dispatch(topic, payload);

    // Wait a tick for async persistence
    await new Promise((resolve) => setTimeout(resolve, 10));

    // 1. Verify node registration
    const node = await repo.getNode('NODE-001');
    assert.ok(node, 'Node must be registered in repository');
    assert.equal(node.node_id, 'NODE-001');
    assert.equal(node.latitude, 30.2672);
    assert.equal(node.longitude, -97.7431);
    assert.equal(node.status, 'online');

    // 2. Verify reading persistence
    const readings = await repo.getSensorReadings({ nodeId: 'NODE-001' });
    assert.equal(readings.length, 1);
    const r = readings[0];
    assert.equal(r.node_id, 'NODE-001');
    assert.equal(r.temperature, 26.4);
    assert.equal(r.humidity, 58.2);
    assert.equal(r.pressure, 1013.25);
    assert.strictEqual(r.rainfall, 0.0, 'real zero must be preserved');
    assert.equal(r.soil_moisture, 32.5);
    assert.equal(r.water_level, 12.0);
    assert.equal(r.air_quality, 15.4);
    assert.equal(r.battery, 3.92);

    // 3. Verify metrics
    const s = orchestrator.status();
    assert.equal(s.metrics.receivedCount, 1);
    assert.equal(s.metrics.persistedCount, 1);
    assert.equal(s.metrics.errorCount, 0);
  });

  it('supports future data-driven node IDs (e.g. NODE-006+) without hardcoding', async () => {
    const futureTopic = 'climate/nodes/NODE-006/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-006',
      timestamp: '2026-09-08T00:05:00Z',
      latitude: 30.3100,
      longitude: -97.7200,
      temperature: 24.5,
      rainfall: 5.2,
    });

    adapter._dispatch(futureTopic, payload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const node = await repo.getNode('NODE-006');
    assert.ok(node, 'Future node NODE-006 must be automatically registered');
    assert.equal(node.node_id, 'NODE-006');

    const readings = await repo.getSensorReadings({ nodeId: 'NODE-006' });
    assert.equal(readings.length, 1);
    assert.equal(readings[0].node_id, 'NODE-006');
    assert.equal(readings[0].temperature, 24.5);
    assert.equal(readings[0].rainfall, 5.2);
  });

  it('preserves NULL for missing optional measurements and real numeric zero (0 / 0.0)', async () => {
    const topic = 'climate/nodes/NODE-002/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-002',
      timestamp: '2026-09-08T00:10:00Z',
      latitude: 30.2621,
      longitude: -97.7510,
      temperature: 0.0,       // numeric zero
      rainfall: 0.0,          // numeric zero
      water_level: 0.0,       // numeric zero
      soil_moisture: null,    // explicit null
      // air_quality and battery omitted
    });

    adapter._dispatch(topic, payload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const readings = await repo.getSensorReadings({ nodeId: 'NODE-002' });
    assert.equal(readings.length, 1);
    const r = readings[0];

    assert.strictEqual(r.temperature, 0, '0.0 temperature must remain 0');
    assert.strictEqual(r.rainfall, 0, '0.0 rainfall must remain 0');
    assert.strictEqual(r.water_level, 0, '0.0 water_level must remain 0');
    assert.strictEqual(r.soil_moisture, null, 'explicit null must remain null');
    assert.strictEqual(r.air_quality, null, 'omitted measurement must remain null');
    assert.strictEqual(r.battery, null, 'omitted measurement must remain null');
  });

  it('rejects invalid telemetry and NEVER reaches repository persistence', async () => {
    const topic = 'climate/nodes/NODE-001/telemetry';
    // Latitude out of range
    const invalidPayload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 95.0, // Invalid latitude
      longitude: -97.7431,
      temperature: 25.0,
    });

    adapter._dispatch(topic, invalidPayload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const readings = await repo.getSensorReadings({ nodeId: 'NODE-001' });
    assert.equal(readings.length, 0, 'Invalid telemetry must never be persisted');
    assert.equal(rejectedMessages.length, 1);
    assert.equal(rejectedMessages[0].result, 'validation_failed');

    const s = orchestrator.status();
    assert.equal(s.metrics.persistedCount, 0);
    assert.equal(s.metrics.rejectedCount, 1);
  });

  it('rejects topic/payload node_id mismatch and NEVER reaches persistence', async () => {
    const topic = 'climate/nodes/NODE-001/telemetry';
    const mismatchPayload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-999', // Mismatched ID!
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 30.2,
      longitude: -97.7,
      temperature: 25.0,
    });

    adapter._dispatch(topic, mismatchPayload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const readings1 = await repo.getSensorReadings({ nodeId: 'NODE-001' });
    const readings999 = await repo.getSensorReadings({ nodeId: 'NODE-999' });
    assert.equal(readings1.length, 0);
    assert.equal(readings999.length, 0);

    assert.equal(rejectedMessages.length, 1);
    assert.equal(rejectedMessages[0].result, 'node_id_mismatch');
  });

  it('handles database persistence failure safely without throwing or crashing', async () => {
    // Force repo to throw an error on insert
    repo.insertSensorReading = async () => {
      throw new Error('Simulated PostgreSQL connection timeout');
    };

    const topic = 'climate/nodes/NODE-001/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 30.2672,
      longitude: -97.7431,
      temperature: 25.0,
    });

    // Should not throw or crash
    adapter._dispatch(topic, payload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    assert.equal(persistenceErrors.length, 1);
    assert.match(persistenceErrors[0].err.message, /Simulated PostgreSQL connection timeout/);
    assert.equal(persistenceErrors[0].payload.node_id, 'NODE-001');

    const s = orchestrator.status();
    assert.equal(s.metrics.errorCount, 1);
    assert.equal(s.metrics.persistedCount, 0);
  });

  it('repeated start() calls do not register duplicate listeners or duplicate DB writes', async () => {
    // Call start() repeatedly
    orchestrator.start();
    orchestrator.start();

    const topic = 'climate/nodes/NODE-001/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 30.2672,
      longitude: -97.7431,
      temperature: 25.0,
    });

    adapter._dispatch(topic, payload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const readings = await repo.getSensorReadings({ nodeId: 'NODE-001' });
    // Must be exactly 1, not 2 or 3
    assert.equal(readings.length, 1);
    assert.equal(orchestrator.status().metrics.persistedCount, 1);
  });

  it('stop() cleanly unhooks listeners and halts processing', async () => {
    orchestrator.stop();
    assert.equal(orchestrator.status().state, ORCHESTRATOR_STATES.IDLE);

    const topic = 'climate/nodes/NODE-001/telemetry';
    const payload = JSON.stringify({
      schema_version: '1.0.0',
      node_id: 'NODE-001',
      timestamp: '2026-09-08T00:00:00Z',
      latitude: 30.2672,
      longitude: -97.7431,
      temperature: 25.0,
    });

    adapter._dispatch(topic, payload);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const readings = await repo.getSensorReadings({ nodeId: 'NODE-001' });
    assert.equal(readings.length, 0, 'No readings should be persisted when stopped');
  });
});

describe('createClimateServer Server Integration Lifecycle', () => {
  it('starts and stops all subsystems cleanly via server entry point', async () => {
    const { createClimateServer } = await import('../index.js');
    const server = createClimateServer({
      config: { dbType: 'memory' },
    });

    const initialStatus = server.status();
    assert.equal(initialStatus.initialized, false);
    assert.equal(initialStatus.subsystems.db, 'uninitialized');

    await server.start();

    const runningStatus = server.status();
    assert.equal(runningStatus.initialized, true);
    assert.equal(runningStatus.subsystems.db, 'ready');
    assert.equal(runningStatus.subsystems.ingestion, 'running');

    // Repeated start() is safe no-op
    await server.start();
    assert.equal(server.status().initialized, true);

    await server.stop();

    const stoppedStatus = server.status();
    assert.equal(stoppedStatus.initialized, false);
    assert.equal(stoppedStatus.subsystems.ingestion, 'idle');
  });
});

