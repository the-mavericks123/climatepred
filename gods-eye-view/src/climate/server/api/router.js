/**
 * Climate Eye S1 — API Router & Connect Middleware
 *
 * Provides a clean Connect-compatible middleware function for routing Climate Eye
 * REST API requests without disturbing existing God's Eye View routes.
 *
 * Conforms to DECISION-005: isolated S1 backend boundary.
 */

'use strict';

import {
  handleHealth,
  handleListNodes,
  handleGetNode,
  handleGetNodeTelemetry,
  handleGetTelemetry,
  handleGetHazardsCurrent,
  handleGetPredictions,
  handleGetCompound,
  handleGetVulnerability,
  handleGetEvacuation,
  handleGetResponse,
  handleGetSimulationScenarios,
  handleRunSimulation,
  handleGetExplainability,
  handleNotImplemented,
  forwardToS2,
  sendError,
} from './handlers.js';

/**
 * Route pattern regular expressions.
 */
const ROUTE_PATTERNS = Object.freeze({
  HEALTH: /^\/api\/climate\/health\/?$/,
  NODES_LIST: /^\/api\/nodes\/?$/,
  TELEMETRY: /^\/api\/telemetry\/?$/,
  NODE_TELEMETRY: /^\/api\/nodes\/([^/]+)\/telemetry\/?$/,
  NODE_DETAILS: /^\/api\/nodes\/([^/]+)\/?$/,

  // Intelligence Routes (S2 Connected)
  HAZARDS_CURRENT: /^\/api\/hazards\/current\/?$/,
  HAZARDS_PREDICTIONS: /^\/api\/hazards\/predictions\/?$/,
  COMPOUND: /^\/api\/(compound|compound-events\/current)\/?$/,
  VULNERABILITY: /^\/api\/(vulnerability|vulnerability\/zones)\/?$/,
  EVACUATION: /^\/api\/(evacuation|evacuation\/routes|evacuation\/current)\/?$/,
  RESPONSE: /^\/api\/(response|response\/current)\/?$/,

  // Simulation Routes (S2 Connected)
  SIM_SCENARIOS: /^\/api\/simulation\/scenarios\/?$/,
  SIM_RUN: /^\/api\/simulation\/run\/?$/,

  // Explainability Route (S2 Connected)
  EXPLAINABILITY: /^\/api\/explainability\/([^/]+)\/([^/]+)\/?$/,
});

/**
 * Creates the Climate Eye API router middleware.
 *
 * @param {object} options
 * @param {object} options.repository
 * @param {object} [options.climateServer]
 * @param {object} [options.options]
 * @returns {function(object, object, function): void}
 */
export function createClimateApiRouter(config = {}) {
  const repository = config.repository;
  const climateServer = config.climateServer || null;
  const options = config.options || config;
  if (!repository) {
    throw new TypeError('createClimateApiRouter requires a valid repository');
  }

  const enableS2 = config.enableS2 ?? options.enableS2 ?? (process.env.ENABLE_S2_INTELLIGENCE === 'true' || Boolean(options.s2BaseUrl || config.s2BaseUrl));

  return async function climateApiMiddleware(req, res, next) {
    let url;
    try {
      url = new URL(req.url, 'http://localhost');
    } catch {
      return next();
    }

    const pathname = url.pathname;

    // Fast-path exit: if request does not start with /api/, pass to next middleware immediately
    if (!pathname.startsWith('/api/')) {
      return next();
    }

    try {
      // 1. GET /api/climate/health
      if (ROUTE_PATTERNS.HEALTH.test(pathname)) {
        return await handleHealth(req, res, { climateServer, repository, url });
      }

      // 2. GET /api/nodes/:node_id/telemetry
      const telemetryMatch = pathname.match(ROUTE_PATTERNS.NODE_TELEMETRY);
      if (telemetryMatch) {
        const nodeId = decodeURIComponent(telemetryMatch[1]);
        return await handleGetNodeTelemetry(req, res, { repository, nodeId, url, options: { ...options, enableS2 } });
      }

      // 3. GET /api/nodes/:node_id
      const nodeMatch = pathname.match(ROUTE_PATTERNS.NODE_DETAILS);
      if (nodeMatch) {
        const nodeId = decodeURIComponent(nodeMatch[1]);
        return await handleGetNode(req, res, { repository, nodeId, url, options: { ...options, enableS2 } });
      }

      // 4. GET /api/nodes
      if (ROUTE_PATTERNS.NODES_LIST.test(pathname)) {
        return await handleListNodes(req, res, { repository, url, options: { ...options, enableS2 } });
      }

      // 4b. GET /api/telemetry
      if (ROUTE_PATTERNS.TELEMETRY.test(pathname)) {
        return await handleGetTelemetry(req, res, { repository, url, options });
      }

      // 5. Intelligence Routes (S2 Connected vs Step 8I Stubs)
      if (ROUTE_PATTERNS.HAZARDS_CURRENT.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetHazardsCurrent(req, res, { repository, url, options });
      }

      if (ROUTE_PATTERNS.HAZARDS_PREDICTIONS.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetPredictions(req, res, { repository, url, options });
      }

      if (ROUTE_PATTERNS.COMPOUND.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetCompound(req, res, { url, options });
      }

      if (ROUTE_PATTERNS.VULNERABILITY.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetVulnerability(req, res, { url, options });
      }

      if (ROUTE_PATTERNS.EVACUATION.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetEvacuation(req, res, { url, options });
      }

      if (ROUTE_PATTERNS.RESPONSE.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetResponse(req, res, { url, options });
      }

      // 6. Simulation Routes (S2 Connected vs Step 8I Stubs)
      if (ROUTE_PATTERNS.SIM_SCENARIOS.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleGetSimulationScenarios(req, res, { url, options });
      }

      if (ROUTE_PATTERNS.SIM_RUN.test(pathname)) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        return await handleRunSimulation(req, res, { url, options });
      }

      // 7. Explainability Route
      const explainMatch = pathname.match(ROUTE_PATTERNS.EXPLAINABILITY);
      if (explainMatch) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        const targetType = decodeURIComponent(explainMatch[1]);
        const targetId = decodeURIComponent(explainMatch[2]);
        return await handleGetExplainability(req, res, { targetType, targetId, url, options });
      }

      // 8. Global Live Data Feeds & S2 fallback routes
      if (pathname.startsWith('/api/global/') || pathname.startsWith('/api/v1/global/')) {
        const targetPath = pathname.startsWith('/api/v1/') ? pathname : `/api/v1${pathname.slice(4)}`;
        const query = url.search || '';
        return await forwardToS2(req, res, `${targetPath}${query}`, options);
      }

      // Generic S2 v1 routing fallback for /api/v1/*
      if (pathname.startsWith('/api/v1/')) {
        if (!enableS2) return handleNotImplemented(req, res, { endpoint: pathname });
        const query = url.search || '';
        return await forwardToS2(req, res, `${pathname}${query}`, options);
      }

      // Unmatched /api/... paths pass to existing GEV handlers
      return next();
    } catch (err) {
      // Never crash the server on unexpected handler errors; return safe 500
      sendError(res, 500, 'Internal server error', 'INTERNAL_SERVER_ERROR');
    }
  };
}
