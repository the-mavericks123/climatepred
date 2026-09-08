/**
 * Climate Eye — Frontend Realtime Client Index
 *
 * Public API surface for the Climate Eye WebSocket realtime layer.
 * Browser-safe: no Node.js core imports.
 */

export {
  CLIMATE_STREAM_PATH,
  APPROVED_EVENTS,
  APPROVED_EVENT_SET,
  ACTIVE_EVENTS,
  CLIENT_STATES,
  buildStreamUrl,
  validateEnvelope,
  createClimateRealtimeClient,
  createStateIntegratedRealtimeClient,
} from './client.js';

export {
  createRealtimeBridge,
  startRealtimeBridge,
  getRealtimeBridge,
  stopRealtimeBridge,
} from './controller.js';
