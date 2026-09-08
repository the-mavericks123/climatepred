/**
 * Climate Eye — Frontend REST API Client Module
 *
 * Browser-safe ESM exports.
 */

export {
  ClimateApiClient,
  createClimateApiClient,
  isValidNodeId,
  createErrorResult,
  createSuccessResult,
  NODE_ID_REGEX,
  DEFAULT_REQUEST_TIMEOUT_MS,
  API_ERROR_CODES,
} from './client.js';

export {
  syncClimateStateFromRest,
  syncIntelligenceFromRest,
  syncGlobalDataFromRest,
  bootstrapClimateData,
  runSimulationScenario,
  resetSimulationBaseline,
  queryAiDirective,
  fetchRegionalIntelligence,
} from './controller.js';

export {
  geocodeLocation,
  reverseGeocodeLocation,
  KNOWN_REGIONS,
} from './geocoding.js';
