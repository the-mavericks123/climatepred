/**
 * Climate Eye S1 — Telemetry Ingestion Orchestrator
 *
 * Bridges the MQTT transport layer and the PostgreSQL/PostGIS database repository:
 *
 *   MQTT message
 *     → topic parsing
 *     → JSON parsing
 *     → telemetry validation / normalization
 *     → node upsert (data-driven identity)
 *     → sensor reading persistence
 *
 * Responsibilities:
 *   1. Subscribes to the MQTT adapter's normalized telemetry stream.
 *   2. Dynamically registers/upserts nodes based on incoming telemetry coordinates
 *      and status (supporting NODE-001..NODE-005, NODE-006+, and future IDs).
 *   3. Persists canonical sensor readings while preserving NULLs and real zeros.
 *   4. Catches and surfaces database failures without crashing the server.
 *   5. Guarantees clean, idempotent lifecycle management (start/stop).
 *
 * Conforms to DECISION-001, DECISION-003, DECISION-004, and DECISION-005.
 */

'use strict';

import { HANDLER_RESULTS } from '../mqtt/handler.js';

/**
 * Orchestrator operational lifecycle states.
 * @readonly
 */
export const ORCHESTRATOR_STATES = Object.freeze({
  IDLE: 'idle',
  RUNNING: 'running',
  STOPPING: 'stopping',
});

/**
 * Creates a telemetry ingestion orchestrator.
 *
 * @param {object} params
 * @param {import('../db/repository.js').ClimateRepository} params.repository - The database repository instance.
 * @param {import('../mqtt/adapter.js').MqttIngestionAdapter} params.mqttAdapter - The MQTT adapter instance.
 * @param {object} [params.realtimeServer] - Optional ClimateRealtimeServer instance for live event broadcast.
 * @param {object} [params.options]
 * @param {function(Error, object): void} [params.options.onPersistenceError] - Optional callback when DB write fails.
 * @param {function(object): void} [params.options.onRejected] - Optional callback for rejected messages.
 * @param {function(object): void} [params.options.onPersisted] - Optional callback on successful persistence.
 * @returns {TelemetryIngestionOrchestrator}
 */
export function createIngestionOrchestrator({ repository, mqttAdapter, realtimeServer = null, options = {} }) {
  if (!repository) {
    throw new TypeError('createIngestionOrchestrator requires a valid repository instance');
  }
  if (!mqttAdapter) {
    throw new TypeError('createIngestionOrchestrator requires a valid mqttAdapter instance');
  }

  let state = ORCHESTRATOR_STATES.IDLE;

  const metrics = {
    receivedCount: 0,
    persistedCount: 0,
    rejectedCount: 0,
    errorCount: 0,
  };

  /**
   * Processes a validated telemetry result and commits it to the repository.
   *
   * Enforces data-driven node registration before reading persistence so
   * foreign key constraints are always satisfied.
   *
   * @param {import('../mqtt/handler.js').HandleResult} handleResult
   * @returns {Promise<{ success: boolean, reading?: object, error?: string }>}
   */
  async function processTelemetry(handleResult) {
    if (state !== ORCHESTRATOR_STATES.RUNNING) {
      return { success: false, error: 'Orchestrator is not running' };
    }

    if (!handleResult || handleResult.result !== HANDLER_RESULTS.NORMALIZED_TELEMETRY || !handleResult.payload) {
      metrics.rejectedCount++;
      return { success: false, error: 'Not a valid normalized telemetry payload' };
    }

    const payload = handleResult.payload;
    metrics.receivedCount++;

    try {
      // 1. Data-driven node registration / upsert
      // Guarantees foreign key constraint in sensor_readings table
      await repository.upsertNode({
        node_id: payload.node_id,
        latitude: payload.latitude,
        longitude: payload.longitude,
        status: 'online',
        updated_at: payload.timestamp,
      });

      // 2. Persist the sensor reading
      // Repository mapping ensures canonical 13 fields, PostGIS location,
      // NULL preservation, and zero preservation.
      const reading = await repository.insertSensorReading(payload);

      metrics.persistedCount++;

      // 3. Realtime event broadcast (ONLY after successful persistence)
      if (realtimeServer && typeof realtimeServer.broadcast === 'function') {
        try {
          // Emit node.updated with real node information available from telemetry
          realtimeServer.broadcast('node.updated', {
            node_id: payload.node_id,
            latitude: payload.latitude,
            longitude: payload.longitude,
            status: 'online',
            timestamp: payload.timestamp,
          });

          // Emit telemetry.updated with canonical normalized payload
          realtimeServer.broadcast('telemetry.updated', payload);
        } catch {
          // Broadcast failures must not crash ingestion or the server
        }
      }

      options.onPersisted?.({ reading, telemetry: payload });

      return { success: true, reading };
    } catch (err) {
      metrics.errorCount++;

      // Database failures must be handled explicitly:
      // - Do not silently discard persistence errors
      // - Return/emit a clear failure result
      // - Do not crash the entire server
      options.onPersistenceError?.(err, payload);

      return {
        success: false,
        error: `Persistence error for node "${payload.node_id}": ${err.message}`,
      };
    }
  }

  /**
   * Internal handler wired to mqttAdapter.onTelemetry.
   * Ensures asynchronous execution without unhandled rejections.
   */
  function _onTelemetryReceived(handleResult) {
    processTelemetry(handleResult).catch((err) => {
      metrics.errorCount++;
      options.onPersistenceError?.(err, handleResult?.payload);
    });
  }

  /**
   * Internal handler wired to mqttAdapter.onRejected.
   */
  function _onMessageRejected(rejectResult) {
    metrics.rejectedCount++;
    options.onRejected?.(rejectResult);
  }

  /**
   * Starts the orchestrator and registers callbacks on the MQTT adapter.
   * Idempotent: repeated start() calls are safe no-ops.
   */
  function start() {
    if (state === ORCHESTRATOR_STATES.RUNNING) {
      return;
    }

    state = ORCHESTRATOR_STATES.RUNNING;

    // Register adapter callbacks
    mqttAdapter.onTelemetry(_onTelemetryReceived);
    mqttAdapter.onRejected(_onMessageRejected);
  }

  /**
   * Stops the orchestrator and unhooks listeners.
   * Idempotent: repeated stop() calls are safe no-ops.
   */
  function stop() {
    if (state === ORCHESTRATOR_STATES.IDLE) {
      return;
    }

    state = ORCHESTRATOR_STATES.STOPPING;

    // Detach callbacks
    mqttAdapter.onTelemetry(() => {});
    mqttAdapter.onRejected(() => {});

    state = ORCHESTRATOR_STATES.IDLE;
  }

  /**
   * Returns current operational status and telemetry metrics.
   *
   * @returns {{ state: string, metrics: { receivedCount: number, persistedCount: number, rejectedCount: number, errorCount: number } }}
   */
  function status() {
    return {
      state,
      metrics: { ...metrics },
    };
  }

  return {
    start,
    stop,
    status,
    processTelemetry,
  };
}
