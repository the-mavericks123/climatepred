/**
 * Climate Eye Realtime Event Definitions & Envelope
 *
 * Defines canonical realtime event types, realtime stream states, and
 * standard envelope formatting conforming to DECISION-005.
 */

'use strict';

/**
 * Approved Climate Eye realtime event types.
 */
export const REALTIME_EVENTS = Object.freeze([
  'node.updated',
  'telemetry.updated',
  'hazard.updated',
  'prediction.updated',
  'compound.updated',
  'vulnerability.updated',
  'evacuation.updated',
  'response.updated',
  'simulation.completed',
]);

/**
 * Fast lookup set for approved event names.
 */
export const REALTIME_EVENT_SET = new Set(REALTIME_EVENTS);

/**
 * Canonical stream states for future data-driven integration.
 * A WebSocket connection is NOT automatically LIVE simply because the socket is open.
 */
export const REALTIME_STATES = Object.freeze({
  LIVE: 'LIVE',
  STALE: 'STALE',
  SIMULATED: 'SIMULATED',
  UNAVAILABLE: 'UNAVAILABLE',
});

/**
 * Check if an event name is an approved Climate Eye realtime event.
 *
 * @param {string} event
 * @returns {boolean}
 */
export function isValidRealtimeEvent(event) {
  return typeof event === 'string' && REALTIME_EVENT_SET.has(event);
}

/**
 * Formats a canonical Climate Eye realtime event envelope.
 *
 * @param {string} event - Approved event name.
 * @param {any} payload - Event payload (must be JSON-serializable).
 * @param {string} [timestamp] - Optional ISO-8601 UTC timestamp (defaults to now).
 * @returns {string} Serialized JSON envelope.
 */
export function formatRealtimeEnvelope(event, payload, timestamp = new Date().toISOString()) {
  if (!isValidRealtimeEvent(event)) {
    throw new TypeError(
      `Invalid Climate Eye realtime event: "${event}". Must be one of: ${REALTIME_EVENTS.join(', ')}`
    );
  }

  return JSON.stringify({
    event,
    timestamp,
    payload,
  });
}
