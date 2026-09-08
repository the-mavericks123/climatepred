/**
 * Climate Eye S1 — API Route Handlers
 *
 * Implements HTTP request handlers for the approved Climate Eye API routes.
 * Decoupled from transport framework (Vite/Connect/Express compatible).
 *
 * Conforms to DECISION-001, DECISION-002, DECISION-003, and DECISION-005.
 */

'use strict';

const NODE_ID_RE = /^[A-Za-z0-9_-]{3,32}$/;

/**
 * Send JSON response
 * @param {object} res
 * @param {number} statusCode
 * @param {object} body
 */
export function sendJson(res, statusCode, body) {
  const json = JSON.stringify(body);
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.end(json);
}

/**
 * Send standard JSON error response
 * @param {object} res
 * @param {number} statusCode
 * @param {string} message
 * @param {string} code
 * @param {any} [details]
 */
export function sendError(res, statusCode, message, code, details = null) {
  sendJson(res, statusCode, {
    ok: false,
    error: message,
    code,
    details,
  });
}

/**
 * Validates node_id parameter grammar.
 *
 * @param {string} nodeId
 * @returns {boolean}
 */
export function isValidNodeId(nodeId) {
  return typeof nodeId === 'string' && NODE_ID_RE.test(nodeId.trim());
}

/**
 * GET /api/climate/health
 *
 * Reports honest, verified operational status of Climate Eye S1 backend.
 * Never falsely claims unverified or unimplemented subsystems are healthy.
 */
export async function handleHealth(req, res, { climateServer, repository }) {
  if (req.method !== 'GET') {
    return sendError(res, 405, `Method ${req.method} not allowed`, 'METHOD_NOT_ALLOWED');
  }

  const serverStatus = climateServer?.status?.() || {};
  const subsystems = serverStatus.subsystems || {};

  sendJson(res, 200, {
    ok: true,
    service: 'climate-eye-s1',
    version: '1.0.0',
    uptime_s: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    subsystems: {
      api: 'ready',
      db: subsystems.db || 'uninitialized',
      mqtt: subsystems.mqtt || 'idle',
      ingestion: subsystems.ingestion || 'idle',
      realtime: subsystems.realtime || 'unimplemented',
      intelligence: subsystems.intelligence || 'unimplemented',
    },
    metrics: serverStatus.metrics || null,
  });
}

/**
 * GET /api/nodes
 *
 * Returns list of registered ClimateMesh nodes from the repository.
 * Data-driven: supports NODE-001 through NODE-006+ dynamically.
 */
export async function handleListNodes(req, res, { repository, url, options = {} }) {
  if (req.method !== 'GET') {
    return sendError(res, 405, `Method ${req.method} not allowed`, 'METHOD_NOT_ALLOWED');
  }

  try {
    const filter = {};
    const statusParam = url.searchParams.get('status');
    const profileParam = url.searchParams.get('profile');

    if (statusParam) filter.status = statusParam;
    if (profileParam) filter.profile = profileParam;

    let nodes = await repository.listNodes(filter);

    if (nodes.length === 0 && options?.enableS2 === true) {
      try {
        const s2Base = options?.s2BaseUrl || DEFAULT_S2_URL;
        const fetchImpl = options?.fetchImpl || globalThis.fetch;
        const resp = await fetchImpl(`${s2Base}/api/v1/nodes`);
        if (resp && resp.ok) {
          const s2Data = await resp.json();
          if (Array.isArray(s2Data.nodes) && s2Data.nodes.length > 0) {
            nodes = s2Data.nodes;
          }
        }
      } catch {}
    }

    sendJson(res, 200, {
      ok: true,
      count: nodes.length,
      nodes,
    });
  } catch (err) {
    sendError(res, 500, 'Failed to retrieve nodes', 'INTERNAL_SERVER_ERROR');
  }
}

/**
 * GET /api/nodes/:node_id
 *
 * Returns details for a single node.
 */
export async function handleGetNode(req, res, { repository, nodeId, options = {} }) {
  if (req.method !== 'GET') {
    return sendError(res, 405, `Method ${req.method} not allowed`, 'METHOD_NOT_ALLOWED');
  }

  if (!isValidNodeId(nodeId)) {
    return sendError(
      res,
      400,
      `Invalid node_id "${nodeId}". Must be 3-32 alphanumeric characters, hyphens, or underscores.`,
      'INVALID_NODE_ID'
    );
  }

  try {
    let node = await repository.getNode(nodeId);
    if (!node && options?.enableS2 === true) {
      try {
        const s2Base = options?.s2BaseUrl || DEFAULT_S2_URL;
        const fetchImpl = options?.fetchImpl || globalThis.fetch;
        const resp = await fetchImpl(`${s2Base}/api/v1/nodes/${encodeURIComponent(nodeId)}`);
        if (resp && resp.ok) {
          const s2Data = await resp.json();
          if (s2Data.node) node = s2Data.node;
        }
      } catch {}
    }

    if (!node) {
      return sendError(res, 404, `Node "${nodeId}" not found`, 'NODE_NOT_FOUND', { node_id: nodeId });
    }

    sendJson(res, 200, {
      ok: true,
      node,
    });
  } catch (err) {
    sendError(res, 500, 'Failed to retrieve node details', 'INTERNAL_SERVER_ERROR');
  }
}

/**
 * GET /api/nodes/:node_id/telemetry
 *
 * Returns historical sensor readings for a specific node.
 * Strictly preserves NULLs and real zeros without fabrication.
 */
export async function handleGetNodeTelemetry(req, res, { repository, nodeId, url, options = {} }) {
  if (req.method !== 'GET') {
    return sendError(res, 405, `Method ${req.method} not allowed`, 'METHOD_NOT_ALLOWED');
  }

  if (!isValidNodeId(nodeId)) {
    return sendError(
      res,
      400,
      `Invalid node_id "${nodeId}". Must be 3-32 alphanumeric characters, hyphens, or underscores.`,
      'INVALID_NODE_ID'
    );
  }

  try {
    // 1. Verify node exists
    let node = await repository.getNode(nodeId);
    let readings = [];

    if (!node && options?.enableS2 === true) {
      try {
        const s2Base = options?.s2BaseUrl || DEFAULT_S2_URL;
        const fetchImpl = options?.fetchImpl || globalThis.fetch;
        const resp = await fetchImpl(`${s2Base}/api/v1/telemetry?node_id=${encodeURIComponent(nodeId)}`);
        if (resp && resp.ok) {
          const s2Data = await resp.json();
          if (Array.isArray(s2Data.telemetry) && s2Data.telemetry.length > 0) {
            readings = s2Data.telemetry;
            node = { node_id: nodeId };
          }
        }
      } catch {}
    }

    if (!node) {
      return sendError(res, 404, `Node "${nodeId}" not found`, 'NODE_NOT_FOUND', { node_id: nodeId });
    }

    if (readings.length === 0) {
      // 2. Parse query parameters
      const limitRaw = url.searchParams.get('limit');
      let limit = 50;
      if (limitRaw) {
        const parsedLimit = parseInt(limitRaw, 10);
        if (Number.isFinite(parsedLimit) && parsedLimit > 0) {
          limit = Math.min(parsedLimit, 1000);
        }
      }

      const since = url.searchParams.get('since') || undefined;
      const until = url.searchParams.get('until') || undefined;
      const order = url.searchParams.get('order') === 'asc' ? 'asc' : 'desc';

      readings = await repository.getSensorReadings({
        nodeId,
        limit,
        since,
        until,
        order,
      });

      if (readings.length === 0 && options?.enableS2 === true) {
        try {
          const s2Base = options?.s2BaseUrl || DEFAULT_S2_URL;
          const fetchImpl = options?.fetchImpl || globalThis.fetch;
          const resp = await fetchImpl(`${s2Base}/api/v1/telemetry?node_id=${encodeURIComponent(nodeId)}`);
          if (resp && resp.ok) {
            const s2Data = await resp.json();
            if (Array.isArray(s2Data.telemetry)) {
              readings = s2Data.telemetry;
            }
          }
        } catch {}
      }
    }

    sendJson(res, 200, {
      ok: true,
      node_id: nodeId,
      count: readings.length,
      readings,
    });
  } catch (err) {
    sendError(res, 500, 'Failed to retrieve sensor readings', 'INTERNAL_SERVER_ERROR');
  }
}

/**
 * GET /api/telemetry
 *
 * Returns latest telemetry readings across nodes, forwarding to S2 or repository.
 */
export async function handleGetTelemetry(req, res, { repository, url, options = {} }) {
  if (req.method === 'POST') {
    return forwardToS2(req, res, '/api/v1/telemetry', options);
  }
  if (req.method !== 'GET') {
    return sendError(res, 405, `Method ${req.method} not allowed`, 'METHOD_NOT_ALLOWED');
  }
  const query = url.search || '';
  if (options.enableS2 !== false) {
    return forwardToS2(req, res, `/api/v1/telemetry${query}`, options);
  }
  try {
    const readings = repository.getLatestReadings ? await repository.getLatestReadings(50) : [];
    sendJson(res, 200, { ok: true, success: true, telemetry: readings, count: readings.length });
  } catch (err) {
    sendError(res, 500, 'Failed to retrieve telemetry', 'INTERNAL_SERVER_ERROR');
  }
}

export const DEFAULT_S2_URL = process.env.S2_INTELLIGENCE_URL || 'http://127.0.0.1:8000';

/**
 * Reads the request body stream as text.
 * @param {object} req
 * @returns {Promise<string|undefined>}
 */
export function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => resolve(body.length > 0 ? body : undefined));
    req.on('error', reject);
  });
}

/**
 * Forwards an HTTP request to the authoritative S2 Intelligence backend.
 *
 * @param {object} req - Incoming request.
 * @param {object} res - Outgoing response.
 * @param {string} targetPath - Target path on S2 (e.g. /api/v1/hazards/current).
 * @param {object} [options]
 * @param {string} [options.s2BaseUrl]
 * @param {number} [options.timeoutMs=8000]
 * @param {any} [options.bodyOverride]
 * @param {object} [options.fetchImpl] - Injectable fetch for unit tests.
 */
export async function forwardToS2(req, res, targetPath, options = {}) {
  const method = req.method || 'GET';
  const baseUrl = (options.s2BaseUrl || DEFAULT_S2_URL).replace(/\/+$/, '');
  const url = `${baseUrl}${targetPath.startsWith('/') ? targetPath : `/${targetPath}`}`;
  const fetchFn = options.fetchImpl || globalThis.fetch;

  const headers = {
    Accept: 'application/json',
  };

  if (req.headers) {
    if (req.headers['authorization']) headers['Authorization'] = req.headers['authorization'];
    if (req.headers['x-api-key']) headers['X-API-Key'] = req.headers['x-api-key'];
    if (req.headers['x-request-id']) headers['X-Request-ID'] = req.headers['x-request-id'];
  }
  if (options.operatorKey && !headers['X-API-Key'] && !headers['Authorization']) {
    headers['X-API-Key'] = options.operatorKey;
  }

  let body = undefined;
  if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
    headers['Content-Type'] = 'application/json';
    if (options.bodyOverride !== undefined) {
      body = typeof options.bodyOverride === 'string' ? options.bodyOverride : JSON.stringify(options.bodyOverride);
    } else {
      body = await readRequestBody(req);
    }
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort(new Error('Gateway timeout'));
    }, options.timeoutMs || 8000);

    const s2Res = await fetchFn(url, {
      method,
      headers,
      body,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    const text = await s2Res.text();
    let json = null;
    if (text && text.trim().length > 0) {
      try {
        json = JSON.parse(text);
      } catch {
        json = { raw: text };
      }
    } else {
      json = { ok: s2Res.ok, status: s2Res.status };
    }

    sendJson(res, s2Res.status, json);
  } catch (err) {
    if (err.name === 'AbortError' || err.message?.includes('timeout')) {
      return sendError(res, 504, 'S2 Intelligence gateway timed out', 'GATEWAY_TIMEOUT');
    }
    return sendError(
      res,
      503,
      `S2 Intelligence service unavailable at ${baseUrl}: ${err.message || 'Connection refused'}`,
      'MODEL_UNAVAILABLE',
      { targetUrl: url }
    );
  }
}

/**
 * GET /api/hazards/current
 */
export async function handleGetHazardsCurrent(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/hazards/current${query}`, options);
}

/**
 * GET /api/hazards/predictions
 */
export async function handleGetPredictions(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/hazards/predictions${query}`, options);
}

/**
 * GET /api/compound
 */
export async function handleGetCompound(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/compound-events/current${query}`, options);
}

/**
 * GET /api/vulnerability
 */
export async function handleGetVulnerability(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/vulnerability/zones${query}`, options);
}

/**
 * GET /api/evacuation
 */
export async function handleGetEvacuation(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/evacuation/current${query}`, options);
}

/**
 * GET /api/response
 */
export async function handleGetResponse(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/response/current${query}`, options);
}

/**
 * GET /api/simulation/scenarios
 */
export async function handleGetSimulationScenarios(req, res, { url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(req, res, `/api/v1/simulation/scenarios${query}`, options);
}

/**
 * POST /api/simulation/run
 */
export async function handleRunSimulation(req, res, { url, options = {} }) {
  return forwardToS2(req, res, '/api/v1/simulation/run', options);
}

/**
 * GET /api/explainability/:target_type/:target_id
 */
export async function handleGetExplainability(req, res, { targetType, targetId, url, options = {} }) {
  const query = url.search || '';
  return forwardToS2(
    req,
    res,
    `/api/v1/explainability/${encodeURIComponent(targetType)}/${encodeURIComponent(targetId)}${query}`,
    options
  );
}

/**
 * Explicit 501 Not Implemented handler for future intelligence and simulation endpoints.
 * Never invents hazard/prediction data or implies fake success.
 */
export function handleNotImplemented(req, res, { endpoint }) {
  sendError(
    res,
    501,
    `Endpoint ${req.method} ${endpoint} is not implemented in Step 8I`,
    'NOT_IMPLEMENTED',
    { endpoint, method: req.method }
  );
}

