/**
 * Climate Eye — Realtime WebSocket Bridge & Controller (Step F4.3)
 *
 * Coordinates connecting the browser WebSocket client to:
 *   ws://<host>/api/climate/stream
 * and dispatching incoming realtime events into the authoritative
 * Climate Eye state store without page refreshes or polling.
 *
 * Rules:
 * - Does not duplicate the WebSocket client implementation.
 * - Does not duplicate REST logic.
 * - Connection alone does NOT claim LIVE (sets STALE or UNAVAILABLE).
 * - Only real telemetry events (`telemetry.updated`) cause a transition to LIVE.
 * - Preserves nulls, numeric zero (0), and backend timestamps.
 * - Dynamic: accepts any node ID (NODE-001 through NODE-006+).
 * - Fault-isolated: malformed or unknown events do not crash the app or terminate the socket.
 * - Disconnect transitions away from LIVE but retains last valid data.
 *
 * Browser-safe: No Node.js core modules.
 */

import {
  createClimateRealtimeClient,
  CLIENT_STATES,
} from './client.js';

import {
  ACTION_TYPES,
  REALTIME_STATES,
} from '../state/constants.js';

let activeBridge = null;

/**
 * Creates and manages a realtime WebSocket bridge for a Climate Eye state store.
 *
 * @param {object} options
 * @param {object} options.store - Authoritative Climate Eye store instance.
 * @param {object} [options.client] - Injected realtime client instance (for testing).
 * @param {object} [options.clientOptions] - Options forwarded to createClimateRealtimeClient.
 * @param {typeof WebSocket} [options.WebSocketClass] - Injected WebSocket class (for testing).
 * @returns {object} Realtime bridge controller.
 */
export function createRealtimeBridge({
  store,
  client = null,
  clientOptions = {},
  WebSocketClass,
} = {}) {
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createRealtimeBridge requires an authoritative Climate Eye state store');
  }

  let realtimeClient = client;

  function onEvent(envelope) {
    if (!envelope || typeof envelope !== 'object') return;
    const { event, payload, timestamp } = envelope;

    try {
      switch (event) {
        case 'telemetry.updated': {
          if (payload && typeof payload === 'object') {
            const telemetryData = payload.telemetry && typeof payload.telemetry === 'object' ? payload.telemetry : payload;
            if (typeof store.updateTelemetry === 'function') {
              store.updateTelemetry(telemetryData);
            } else {
              store.dispatch({ type: ACTION_TYPES.TELEMETRY_UPDATED, payload: telemetryData });
            }
            // Transition to LIVE only on verified telemetry
            const meta = { connected: true, timestamp: timestamp || telemetryData.timestamp || payload.timestamp || new Date().toISOString() };
            if (typeof store.setRealtimeState === 'function') {
              store.setRealtimeState(REALTIME_STATES.LIVE, meta);
            } else {
              store.dispatch({
                type: ACTION_TYPES.REALTIME_STATE_CHANGED,
                payload: { realtimeState: REALTIME_STATES.LIVE, ...meta },
              });
            }
          }
          break;
        }

        case 'node.updated': {
          if (payload && typeof payload === 'object') {
            if (typeof store.updateNode === 'function') {
              store.updateNode(payload);
            } else {
              store.dispatch({ type: ACTION_TYPES.NODE_UPDATED, payload });
            }
          }
          break;
        }

        // Approved future event types (routed safely without fabricating missing fields)
        case 'hazard.updated': {
          const hazardsList = Array.isArray(payload) ? payload : (payload?.hazards || (payload?.hazard_id ? [payload] : []));
          if (hazardsList.length > 0) {
            if (typeof store.updateHazards === 'function') {
              store.updateHazards(hazardsList);
            } else {
              store.dispatch({ type: ACTION_TYPES.HAZARDS_UPDATED, payload: hazardsList });
            }
          } else if (payload?.hazard_id) {
            if (typeof store.updateHazard === 'function') {
              store.updateHazard(payload);
            } else {
              store.dispatch({ type: ACTION_TYPES.HAZARD_UPDATED, payload });
            }
          }
          break;
        }

        case 'prediction.updated': {
          const predList = Array.isArray(payload) ? payload : (payload?.predictions || (payload?.prediction_id ? [payload] : []));
          if (predList.length > 0) {
            if (typeof store.updatePredictions === 'function') {
              store.updatePredictions(predList);
            } else {
              store.dispatch({ type: ACTION_TYPES.PREDICTIONS_UPDATED, payload: predList });
            }
          } else if (payload?.prediction_id) {
            if (typeof store.updatePrediction === 'function') {
              store.updatePrediction(payload);
            } else {
              store.dispatch({ type: ACTION_TYPES.PREDICTION_UPDATED, payload });
            }
          }
          break;
        }

        case 'compound.updated': {
          if (typeof store.updateCompound === 'function') {
            store.updateCompound(payload);
          } else {
            store.dispatch({ type: ACTION_TYPES.COMPOUND_UPDATED, payload });
          }
          break;
        }

        case 'vulnerability.updated': {
          if (typeof store.updateVulnerability === 'function') {
            store.updateVulnerability(payload);
          } else {
            store.dispatch({ type: ACTION_TYPES.VULNERABILITY_UPDATED, payload });
          }
          break;
        }

        case 'evacuation.updated': {
          if (typeof store.updateEvacuation === 'function') {
            store.updateEvacuation(payload);
          } else {
            store.dispatch({ type: ACTION_TYPES.EVACUATION_UPDATED, payload });
          }
          break;
        }

        case 'response.updated': {
          if (typeof store.updateResponse === 'function') {
            store.updateResponse(payload);
          } else {
            store.dispatch({ type: ACTION_TYPES.RESPONSE_UPDATED, payload });
          }
          break;
        }

        case 'simulation.completed': {
          if (typeof store.completeSimulation === 'function') {
            store.completeSimulation(payload);
          } else {
            store.dispatch({ type: ACTION_TYPES.SIMULATION_COMPLETED, payload });
          }
          break;
        }

        default:
          // Unrecognized event ignored safely; never crashes the connection
          break;
      }
    } catch (err) {
      console.warn('[ClimateRealtimeBridge] Error dispatching event:', event, err);
    }
  }

  function onStateChange(clientState) {
    switch (clientState) {
      case CLIENT_STATES.CONNECTED: {
        // Socket opened: mark connected, but DO NOT claim LIVE until real telemetry arrives!
        // Transition to STALE if currently UNAVAILABLE
        const currentState = store.getState();
        const currentRt = currentState?.connection?.realtimeState;
        const nextRt = currentRt === REALTIME_STATES.LIVE ? REALTIME_STATES.LIVE : REALTIME_STATES.STALE;
        if (typeof store.setRealtimeState === 'function') {
          store.setRealtimeState(nextRt, { connected: true });
        } else {
          store.dispatch({
            type: ACTION_TYPES.REALTIME_STATE_CHANGED,
            payload: { realtimeState: nextRt, connected: true },
          });
        }
        break;
      }

      case CLIENT_STATES.DISCONNECTED: {
        // Socket closed: transition to UNAVAILABLE, preserve all existing data
        if (typeof store.setRealtimeState === 'function') {
          store.setRealtimeState(REALTIME_STATES.UNAVAILABLE, { connected: false });
        } else {
          store.dispatch({
            type: ACTION_TYPES.REALTIME_STATE_CHANGED,
            payload: { realtimeState: REALTIME_STATES.UNAVAILABLE, connected: false },
          });
        }
        break;
      }

      case CLIENT_STATES.RECONNECTING: {
        // Reconnecting: transition away from LIVE to STALE, retain data
        if (typeof store.setRealtimeState === 'function') {
          store.setRealtimeState(REALTIME_STATES.STALE, { connected: false });
        } else {
          store.dispatch({
            type: ACTION_TYPES.REALTIME_STATE_CHANGED,
            payload: { realtimeState: REALTIME_STATES.STALE, connected: false },
          });
        }
        break;
      }

      default:
        break;
    }
  }

  if (!realtimeClient) {
    const opts = {
      ...clientOptions,
      onEvent,
      onStateChange,
    };
    if (WebSocketClass) {
      opts.WebSocket = WebSocketClass;
    }
    realtimeClient = createClimateRealtimeClient(opts);
  }

  return {
    client: realtimeClient,
    connect: () => realtimeClient.connect(),
    disconnect: () => realtimeClient.disconnect(),
    getConnectionState: () => realtimeClient.getConnectionState(),
  };
}

/**
 * Starts or returns the active singleton realtime bridge for the given store.
 *
 * @param {object} options
 * @param {object} options.store - Authoritative Climate Eye store.
 * @returns {object} Realtime bridge instance.
 */
export function startRealtimeBridge(options = {}) {
  if (activeBridge) {
    return activeBridge;
  }

  activeBridge = createRealtimeBridge(options);
  activeBridge.connect();
  return activeBridge;
}

/**
 * Returns the active realtime bridge instance, if any.
 *
 * @returns {object|null}
 */
export function getRealtimeBridge() {
  return activeBridge;
}

/**
 * Stops and disconnects the active realtime bridge.
 */
export function stopRealtimeBridge() {
  if (activeBridge) {
    try {
      activeBridge.disconnect();
    } catch (_) {}
    activeBridge = null;
  }
}
