# Climate Eye Frontend REST API Client

Provides a browser-safe, native fetch client for communicating with the Climate Eye S1 REST API.

## Exports

- `ClimateApiClient`: Main client class supporting configurable `baseUrl`, `timeout`, and custom `fetch`.
- `createClimateApiClient(options)`: Convenience factory.
- `isValidNodeId(nodeId)`: Client-side node_id grammar validator.
- `API_ERROR_CODES`: Standardized error codes for client and server responses.
- `createErrorResult(params)` / `createSuccessResult(data, status)`: Structured result factories.

## Methods

- `getHealth(options)`
- `getNodes({ status, profile, ...options })`
- `getNode(nodeId, options)`
- `getNodeTelemetry(nodeId, { limit, since, until, order, ...options })`
- Future intelligence stubs (returning HTTP 501 Not Implemented):
  - `getCurrentHazards(options)`
  - `getPredictions(options)`
  - `getCompoundEvents(options)`
  - `getVulnerability(options)`
  - `getEvacuation(options)`
  - `getResponse(options)`
  - `getSimulationScenarios(options)`
  - `runSimulation(payload, options)`
