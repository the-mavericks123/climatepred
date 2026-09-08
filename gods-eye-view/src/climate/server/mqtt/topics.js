/**
 * Climate Eye S1 — MQTT Topic Patterns & Parser
 *
 * Defines and parses the ClimateMesh MQTT topic hierarchy per DECISION-004:
 *
 *   climate/nodes/{node_id}/telemetry
 *   climate/nodes/{node_id}/status
 *   climate/nodes/{node_id}/heartbeat
 *
 * Rules:
 *   - Hardware publishes; S1 subscribes.
 *   - S2 must NOT consume raw MQTT directly.
 *   - Pure functions: no I/O, no side effects, deterministic.
 */

'use strict';

// ---------------------------------------------------------------------------
// Topic type constants
// ---------------------------------------------------------------------------

/** @readonly */
const TOPIC_TYPES = Object.freeze({
  TELEMETRY:  'telemetry',
  STATUS:     'status',
  HEARTBEAT:  'heartbeat',
  UNKNOWN:    'unknown',
});

// ---------------------------------------------------------------------------
// Topic patterns (DECISION-004)
//
// Pattern: climate/nodes/{node_id}/telemetry|status|heartbeat
// node_id grammar matches DECISION-003: [A-Za-z0-9_-]{3,32}
// ---------------------------------------------------------------------------

/**
 * Wildcard subscription string for the S1 subscriber.
 * Using MQTT single-level wildcard '+' to capture any node_id.
 */
const SUBSCRIPTIONS = Object.freeze([
  'climate/nodes/+/telemetry',
  'climate/nodes/+/status',
  'climate/nodes/+/heartbeat',
]);

/**
 * Regex that matches a valid ClimateMesh topic and captures node_id and type.
 *
 * Groups:
 *   [1] node_id   — the node identifier segment
 *   [2] topicType — "telemetry" | "status" | "heartbeat"
 */
const TOPIC_RE = /^climate\/nodes\/([A-Za-z0-9_-]{3,32})\/(telemetry|status|heartbeat)$/;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} ParsedTopic
 * @property {boolean} matched    - True when the topic matches a known ClimateMesh pattern.
 * @property {string}  topicType  - One of TOPIC_TYPES values.
 * @property {string|null} nodeId - The extracted node_id, or null when unmatched.
 */

/**
 * Parses a raw MQTT topic string against the ClimateMesh topic hierarchy.
 *
 * @param {string} topic - The raw MQTT topic string.
 * @returns {ParsedTopic}
 */
function parseTopic(topic) {
  if (typeof topic !== 'string') {
    return { matched: false, topicType: TOPIC_TYPES.UNKNOWN, nodeId: null };
  }

  const m = TOPIC_RE.exec(topic);
  if (!m) {
    return { matched: false, topicType: TOPIC_TYPES.UNKNOWN, nodeId: null };
  }

  return {
    matched:   true,
    topicType: m[2],   // "telemetry" | "status" | "heartbeat"
    nodeId:    m[1],
  };
}

/**
 * Returns true when the topic is a telemetry topic.
 * @param {string} topic
 * @returns {boolean}
 */
function isTelemetryTopic(topic) {
  const p = parseTopic(topic);
  return p.matched && p.topicType === TOPIC_TYPES.TELEMETRY;
}

/**
 * Returns true when the topic is a status topic.
 * @param {string} topic
 * @returns {boolean}
 */
function isStatusTopic(topic) {
  const p = parseTopic(topic);
  return p.matched && p.topicType === TOPIC_TYPES.STATUS;
}

/**
 * Returns true when the topic is a heartbeat topic.
 * @param {string} topic
 * @returns {boolean}
 */
function isHeartbeatTopic(topic) {
  const p = parseTopic(topic);
  return p.matched && p.topicType === TOPIC_TYPES.HEARTBEAT;
}

// ---------------------------------------------------------------------------
// Exports (ESM)
// ---------------------------------------------------------------------------

export {
  TOPIC_TYPES,
  SUBSCRIPTIONS,
  TOPIC_RE,
  parseTopic,
  isTelemetryTopic,
  isStatusTopic,
  isHeartbeatTopic,
};
