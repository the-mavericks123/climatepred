/**
 * Climate Eye S1 — MQTT Message Handler
 *
 * Processes raw MQTT messages for the ClimateMesh topic hierarchy (DECISION-004).
 *
 * Responsibilities:
 *   1. Parse the raw topic to extract node_id and topic type.
 *   2. For telemetry topics: parse JSON payload, cross-check topic node_id vs
 *      payload node_id, validate + normalize via the canonical validator.
 *   3. Emit valid normalized telemetry via a caller-supplied callback.
 *   4. Reject invalid payloads (bad JSON, validation failures, node_id mismatch)
 *      without throwing or crashing.
 *   5. Forward status and heartbeat messages without validation (passthrough).
 *
 * Contract compliance:
 *   - node_id comes from the MQTT topic (authoritative source).
 *   - A mismatch between topic node_id and payload node_id is a hard rejection;
 *     the payload node_id is NEVER silently rewritten.
 *   - No PostgreSQL I/O in this module.
 *   - No API route logic in this module.
 *   - S2 does not interact with this layer directly.
 */

'use strict';

import { parseTopic, TOPIC_TYPES } from './topics.js';
import { validateTelemetry } from '../telemetry/validator.js';

// ---------------------------------------------------------------------------
// Result type constants
// ---------------------------------------------------------------------------

/** @readonly */
const HANDLER_RESULTS = Object.freeze({
  NORMALIZED_TELEMETRY: 'normalized_telemetry',
  STATUS_RECEIVED:      'status_received',
  HEARTBEAT_RECEIVED:   'heartbeat_received',
  UNKNOWN_TOPIC:        'unknown_topic',
  INVALID_JSON:         'invalid_json',
  NODE_ID_MISMATCH:     'node_id_mismatch',
  VALIDATION_FAILED:    'validation_failed',
});

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} HandleResult
 * @property {string}      result      - One of HANDLER_RESULTS values.
 * @property {string}      topic       - Original MQTT topic string.
 * @property {string|null} nodeId      - node_id extracted from the topic (null for UNKNOWN_TOPIC).
 * @property {string}      topicType   - Parsed topic type.
 * @property {Object|null} payload     - Normalized payload (only for NORMALIZED_TELEMETRY).
 * @property {string[]|null} errors    - Validation/parse error messages (null on success).
 */

/**
 * Handles a single raw MQTT message.
 *
 * This function is pure with respect to I/O — it does not connect to brokers,
 * write to databases, or emit events itself. The caller is responsible for
 * wiring the returned result to downstream consumers.
 *
 * @param {string}          topic    - The MQTT topic string.
 * @param {Buffer|string}   message  - The raw message payload (Buffer or string).
 * @returns {HandleResult}
 */
function handleMessage(topic, message) {
  // ── 1. Parse topic ────────────────────────────────────────────────────────
  const parsed = parseTopic(topic);

  if (!parsed.matched) {
    return {
      result:    HANDLER_RESULTS.UNKNOWN_TOPIC,
      topic,
      nodeId:    null,
      topicType: parsed.topicType,
      payload:   null,
      errors:    [`unrecognized topic: "${topic}"`],
    };
  }

  const { nodeId, topicType } = parsed;

  // ── 2. Non-telemetry topics: passthrough (no validation required) ─────────
  if (topicType === TOPIC_TYPES.STATUS) {
    return {
      result:    HANDLER_RESULTS.STATUS_RECEIVED,
      topic,
      nodeId,
      topicType,
      payload:   null,
      errors:    null,
    };
  }

  if (topicType === TOPIC_TYPES.HEARTBEAT) {
    return {
      result:    HANDLER_RESULTS.HEARTBEAT_RECEIVED,
      topic,
      nodeId,
      topicType,
      payload:   null,
      errors:    null,
    };
  }

  // ── 3. Telemetry topic: parse JSON ────────────────────────────────────────
  let raw;
  try {
    const str = Buffer.isBuffer(message) ? message.toString('utf8') : String(message);
    raw = JSON.parse(str);
  } catch (err) {
    return {
      result:    HANDLER_RESULTS.INVALID_JSON,
      topic,
      nodeId,
      topicType,
      payload:   null,
      errors:    [`invalid JSON in telemetry payload: ${err.message}`],
    };
  }

  // ── 4. Enforce topic node_id vs payload node_id consistency ───────────────
  //       The topic is the authoritative source of node identity.
  //       A mismatch is a hard rejection — never silently rewrite the payload.
  if (raw !== null && typeof raw === 'object' && !Array.isArray(raw)) {
    if (raw.node_id !== undefined && raw.node_id !== nodeId) {
      return {
        result:    HANDLER_RESULTS.NODE_ID_MISMATCH,
        topic,
        nodeId,
        topicType,
        payload:   null,
        errors:    [
          `node_id mismatch: topic says "${nodeId}", payload says "${raw.node_id}" — payload rejected without rewrite`,
        ],
      };
    }
  }

  // ── 5. Validate and normalize via canonical validator ─────────────────────
  const validation = validateTelemetry(raw);

  if (!validation.valid) {
    return {
      result:    HANDLER_RESULTS.VALIDATION_FAILED,
      topic,
      nodeId,
      topicType,
      payload:   null,
      errors:    validation.errors,
    };
  }

  // ── 6. Emit normalized telemetry ──────────────────────────────────────────
  return {
    result:    HANDLER_RESULTS.NORMALIZED_TELEMETRY,
    topic,
    nodeId,
    topicType,
    payload:   validation.payload,
    errors:    null,
  };
}

// ---------------------------------------------------------------------------
// Exports (ESM)
// ---------------------------------------------------------------------------

export {
  handleMessage,
  HANDLER_RESULTS,
};
