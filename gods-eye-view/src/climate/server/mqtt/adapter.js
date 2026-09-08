/**
 * Climate Eye S1 — MQTT Ingestion Adapter
 *
 * Provides an explicit lifecycle interface for the MQTT ingestion layer:
 *
 *   start()      — attaches a real MQTT client and subscribes to all
 *                  ClimateMesh topics.
 *   stop()       — gracefully disconnects and clears subscriptions.
 *   onTelemetry  — registers a callback for valid normalized telemetry.
 *   onRejected   — registers a callback for invalid/rejected messages.
 *
 * Design:
 *   No MQTT client library is installed in this project yet. Rather than
 *   invent a fake implementation, this adapter defines the clean interface
 *   that a real client (e.g. `mqtt` npm package) will fulfil when connected.
 *
 *   The adapter is deliberately decoupled from the handler and validator
 *   layers — connecting a real broker requires only supplying a conformant
 *   MQTT client object, without redesigning any other module.
 *
 *   Lifecycle rules (DECISION-005):
 *     - Repeated start() calls are safe; a second start without stop is a no-op.
 *     - Repeated stop() calls are safe.
 *     - No duplicate subscriptions can be registered.
 *     - All resources must be released on stop().
 */

'use strict';

import { SUBSCRIPTIONS } from './topics.js';
import { handleMessage, HANDLER_RESULTS } from './handler.js';

// ---------------------------------------------------------------------------
// Adapter states
// ---------------------------------------------------------------------------

/** @readonly */
const ADAPTER_STATES = Object.freeze({
  IDLE:       'idle',       // Never started or fully stopped
  STARTING:   'starting',  // start() in progress
  RUNNING:    'running',   // Connected and subscribed
  STOPPING:   'stopping',  // stop() in progress
});

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Creates an MQTT ingestion adapter instance.
 *
 * @returns {MqttIngestionAdapter}
 */
function createMqttAdapter() {
  let state       = ADAPTER_STATES.IDLE;
  let mqttClient  = null;   // Holds the real MQTT client once connected
  let _onTelemetry = null;  // Callback: (HandleResult) => void
  let _onRejected  = null;  // Callback: (HandleResult) => void

  // ── Internal message dispatcher ──────────────────────────────────────────

  /**
   * Called by the real MQTT client for every received message.
   * Routes to handleMessage, then dispatches the result to registered callbacks.
   *
   * This function must never throw — all errors are caught and dispatched
   * as rejection events.
   *
   * @param {string}        topic
   * @param {Buffer|string} message
   */
  function _dispatch(topic, message) {
    let result;
    try {
      result = handleMessage(topic, message);
    } catch (err) {
      result = {
        result:    HANDLER_RESULTS.VALIDATION_FAILED,
        topic,
        nodeId:    null,
        topicType: 'unknown',
        payload:   null,
        errors:    [`internal handler error: ${err.message}`],
      };
    }

    if (result.result === HANDLER_RESULTS.NORMALIZED_TELEMETRY) {
      _onTelemetry?.(result);
    } else if (result.result !== HANDLER_RESULTS.STATUS_RECEIVED &&
               result.result !== HANDLER_RESULTS.HEARTBEAT_RECEIVED) {
      _onRejected?.(result);
    }
    // Status and heartbeat are acknowledged but not forwarded to either callback
    // (they will be handled by a dedicated status/heartbeat processor in a later step)
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /**
   * @typedef {Object} MqttClientInterface
   * An external MQTT client must implement this interface to be accepted by the adapter.
   *
   * @property {function(string[], object, function): void} subscribe
   *   Subscribe to an array of topic strings.
   * @property {function(string, any): void}               on
   *   Register event listeners ('message', 'error', 'close').
   * @property {function(function=): void}                 end
   *   Gracefully disconnect the client.
   */

  /**
   * Starts the MQTT ingestion adapter by attaching the supplied client and
   * subscribing to all ClimateMesh topics.
   *
   * Repeated start() calls without an intervening stop() are safe no-ops.
   *
   * @param {MqttClientInterface} client - A connected MQTT client instance.
   * @returns {void}
   */
  function start(client) {
    if (state === ADAPTER_STATES.RUNNING || state === ADAPTER_STATES.STARTING) {
      // Already running — idempotent, do not re-subscribe.
      return;
    }

    if (!client || typeof client.subscribe !== 'function' || typeof client.on !== 'function') {
      throw new TypeError(
        'start() requires a valid MQTT client with subscribe() and on() methods. ' +
        'No MQTT client library is currently installed — install "mqtt" (npm) and ' +
        'call start() with an mqtt.connect() instance.'
      );
    }

    state      = ADAPTER_STATES.STARTING;
    mqttClient = client;

    // Subscribe to all ClimateMesh wildcard topics
    mqttClient.subscribe(SUBSCRIPTIONS, { qos: 1 }, (err) => {
      if (err) {
        // Subscription failure — revert to idle so start() can be retried
        mqttClient = null;
        state      = ADAPTER_STATES.IDLE;
        _onRejected?.({
          result:    'subscription_error',
          topic:     SUBSCRIPTIONS.join(', '),
          nodeId:    null,
          topicType: 'unknown',
          payload:   null,
          errors:    [`MQTT subscription failed: ${err.message}`],
        });
        return;
      }
      state = ADAPTER_STATES.RUNNING;
    });

    // Wire the message dispatcher
    mqttClient.on('message', _dispatch);

    // Handle broker-level errors without crashing
    mqttClient.on('error', (err) => {
      _onRejected?.({
        result:    'broker_error',
        topic:     null,
        nodeId:    null,
        topicType: 'unknown',
        payload:   null,
        errors:    [`MQTT broker error: ${err.message}`],
      });
    });
  }

  /**
   * Stops the adapter and releases all resources.
   * Repeated stop() calls are safe no-ops.
   *
   * @returns {void}
   */
  function stop() {
    if (state === ADAPTER_STATES.IDLE || state === ADAPTER_STATES.STOPPING) {
      return;
    }

    state = ADAPTER_STATES.STOPPING;

    if (mqttClient) {
      try {
        mqttClient.end(true); // force=true for immediate disconnect
      } catch (_) {
        // Ignore errors during teardown
      }
      mqttClient = null;
    }

    state = ADAPTER_STATES.IDLE;
  }

  /**
   * Registers a callback for valid, normalized telemetry results.
   * Replaces any previously registered callback.
   *
   * @param {function(HandleResult): void} cb
   */
  function onTelemetry(cb) {
    if (typeof cb !== 'function') throw new TypeError('onTelemetry requires a function');
    _onTelemetry = cb;
  }

  /**
   * Registers a callback for rejected / invalid messages.
   * Replaces any previously registered callback.
   *
   * @param {function(HandleResult): void} cb
   */
  function onRejected(cb) {
    if (typeof cb !== 'function') throw new TypeError('onRejected requires a function');
    _onRejected = cb;
  }

  /**
   * Returns a snapshot of the adapter's current operational state.
   *
   * @returns {{ state: string, subscriptions: string[] }}
   */
  function status() {
    return {
      state,
      subscriptions: state === ADAPTER_STATES.RUNNING ? [...SUBSCRIPTIONS] : [],
    };
  }

  /**
   * @typedef {Object} MqttIngestionAdapter
   * @property {function} start        - Attach a real MQTT client and subscribe.
   * @property {function} stop         - Gracefully disconnect and clean up.
   * @property {function} onTelemetry  - Register normalized-telemetry callback.
   * @property {function} onRejected   - Register rejection callback.
   * @property {function} status       - Return current adapter state snapshot.
   * @property {function} _dispatch    - Exposed for unit testing only.
   */
  return {
    start,
    stop,
    onTelemetry,
    onRejected,
    status,
    // Expose _dispatch for unit testing without needing a real MQTT client
    _dispatch,
  };
}

// ---------------------------------------------------------------------------
// Exports (ESM)
// ---------------------------------------------------------------------------

export {
  createMqttAdapter,
  ADAPTER_STATES,
};
