/**
 * Climate Eye — Frontend State Module Exports
 *
 * Exposes the authoritative state model, store factory, constants, and action types.
 *
 * Browser-safe: No Node.js core modules.
 */

export {
  REALTIME_STATES,
  CLIMATE_MODES,
  CLIMATE_LAYERS,
  ACTION_TYPES,
} from './constants.js';

export {
  createInitialState,
  climateReducer,
  createClimateStore,
  sanitizeMeasurement,
  normalizeTelemetryPayload,
} from './climateState.js';
