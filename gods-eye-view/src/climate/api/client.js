/**
 * Climate Eye — Frontend REST API Client
 *
 * Provides a robust, browser-safe client for the Climate Eye S1 REST API.
 * Uses the native Fetch API with timeout, abort support, and normalized error reporting.
 *
 * Requirements (Frontend F2):
 * - Pure browser-safe ESM (zero Node.js core modules, zero external npm packages).
 * - Transparent and honest error normalization without leaking sensitive internal details.
 * - Exact preservation of nulls, numeric zeroes, and authoritative backend timestamps.
 * - Strict client-side validation of node IDs before URL construction.
 * - Prepared methods for future intelligence and simulation endpoints (surfacing HTTP 501
 *   or explicit not-implemented errors; never fabricating synthetic data).
 */

export const NODE_ID_REGEX = /^[A-Za-z0-9_-]{3,32}$/;

export const DEFAULT_REQUEST_TIMEOUT_MS = 10000;

export const API_ERROR_CODES = Object.freeze({
  INVALID_NODE_ID: 'INVALID_NODE_ID',
  REQUEST_ABORTED: 'REQUEST_ABORTED',
  REQUEST_TIMEOUT: 'REQUEST_TIMEOUT',
  NETWORK_ERROR: 'NETWORK_ERROR',
  PARSE_ERROR: 'PARSE_ERROR',
  HTTP_ERROR: 'HTTP_ERROR',
  NOT_IMPLEMENTED: 'NOT_IMPLEMENTED',
});

/**
 * Validates whether a node_id conforms to the canonical grammar.
 *
 * @param {*} nodeId
 * @returns {boolean}
 */
export function isValidNodeId(nodeId) {
  return typeof nodeId === 'string' && NODE_ID_REGEX.test(nodeId.trim());
}

/**
 * Normalizes client and server errors into a consistent structured result shape.
 *
 * @param {object} params
 * @param {string} params.error
 * @param {string} params.code
 * @param {number} [params.status=0]
 * @param {any} [params.details=null]
 * @returns {{ ok: false, error: string, code: string, status: number, details: any }}
 */
export function createErrorResult({ error, code, status = 0, details = null }) {
  // Strip any stack traces or potential db credentials/secrets
  const safeMessage = typeof error === 'string'
    ? error.split('\n')[0].replace(/postgres:\/\/[^\s]+/gi, '[redacted]')
    : 'An unexpected API error occurred';

  return {
    ok: false,
    error: safeMessage,
    code: code || API_ERROR_CODES.HTTP_ERROR,
    status: Number(status) || 0,
    details: details || null,
  };
}

/**
 * Creates a structured success result.
 *
 * @param {*} data
 * @param {number} [status=200]
 * @returns {{ ok: true, data: any, status: number }}
 */
export function createSuccessResult(data, status = 200) {
  return {
    ok: true,
    data,
    status,
  };
}

/**
 * Climate Eye REST API Client.
 */
export class ClimateApiClient {
  /**
   * @param {object} [options]
   * @param {string} [options.baseUrl=''] - Base URL prefix (e.g. '' for relative browser requests)
   * @param {number} [options.timeout=10000] - Default request timeout in ms
   * @param {typeof fetch} [options.fetch=globalThis.fetch] - Injectable fetch implementation for tests
   */
  constructor({
    baseUrl = '',
    timeout = DEFAULT_REQUEST_TIMEOUT_MS,
    fetch = globalThis.fetch,
  } = {}) {
    this.baseUrl = typeof baseUrl === 'string' ? baseUrl.replace(/\/+$/, '') : '';
    this.defaultTimeout = Number.isFinite(timeout) && timeout > 0 ? timeout : DEFAULT_REQUEST_TIMEOUT_MS;
    const rawFetch = fetch || globalThis.fetch;
    this.fetch = typeof rawFetch?.bind === 'function' ? rawFetch.bind(globalThis) : rawFetch;

    if (typeof this.fetch !== 'function') {
      throw new TypeError('ClimateApiClient requires a functional fetch implementation');
    }
  }

  /**
   * Internal request dispatcher with timeout, abort signal, and error normalization.
   *
   * @private
   * @param {string} path - Path starting with / (e.g. /api/nodes)
   * @param {object} [options]
   * @param {string} [options.method='GET']
   * @param {object} [options.headers]
   * @param {any} [options.body]
   * @param {AbortSignal} [options.signal]
   * @param {number} [options.timeout]
   * @returns {Promise<{ ok: boolean, data?: any, error?: string, code?: string, status: number, details?: any }>}
   */
  async _request(path, {
    method = 'GET',
    headers = {},
    body = undefined,
    signal = undefined,
    timeout = this.defaultTimeout,
  } = {}) {
    const safePath = path.startsWith('/') ? path : `/${path}`;
    const url = `${this.baseUrl}${safePath}`;

    const controller = new AbortController();
    let timeoutId = null;

    if (timeout > 0) {
      timeoutId = setTimeout(() => {
        controller.abort(new DOMException('Request timeout', 'TimeoutError'));
      }, timeout);
    }

    // Link caller-supplied signal to internal abort controller
    let onCallerAbort = null;
    if (signal) {
      if (signal.aborted) {
        if (timeoutId) clearTimeout(timeoutId);
        return createErrorResult({
          error: 'Request was aborted by caller',
          code: API_ERROR_CODES.REQUEST_ABORTED,
          status: 0,
        });
      }
      onCallerAbort = () => controller.abort(signal.reason);
      signal.addEventListener('abort', onCallerAbort, { once: true });
    }

    try {
      const response = await this.fetch(url, {
        method,
        headers: {
          Accept: 'application/json',
          ...(body ? { 'Content-Type': 'application/json' } : {}),
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (timeoutId) clearTimeout(timeoutId);

      // Attempt parsing JSON
      let json = null;
      const text = await response.text();
      if (text && text.trim().length > 0) {
        try {
          json = JSON.parse(text);
        } catch {
          return createErrorResult({
            error: `Malformed JSON response from server (HTTP ${response.status})`,
            code: API_ERROR_CODES.PARSE_ERROR,
            status: response.status,
            details: { raw: text.slice(0, 200) },
          });
        }
      }

      // Check HTTP status
      if (!response.ok) {
        const errorMessage = json?.error || `HTTP request failed with status ${response.status}`;
        const errorCode = json?.code || (response.status === 501 ? API_ERROR_CODES.NOT_IMPLEMENTED : API_ERROR_CODES.HTTP_ERROR);
        return createErrorResult({
          error: errorMessage,
          code: errorCode,
          status: response.status,
          details: json?.details || null,
        });
      }

      return createSuccessResult(json, response.status);
    } catch (err) {
      if (timeoutId) clearTimeout(timeoutId);

      if (err.name === 'TimeoutError' || controller.signal.reason?.name === 'TimeoutError') {
        return createErrorResult({
          error: `Request timed out after ${timeout}ms`,
          code: API_ERROR_CODES.REQUEST_TIMEOUT,
          status: 0,
        });
      }

      if (err.name === 'AbortError' || (signal && signal.aborted)) {
        return createErrorResult({
          error: 'Request was aborted',
          code: API_ERROR_CODES.REQUEST_ABORTED,
          status: 0,
        });
      }

      return createErrorResult({
        error: `Network error: ${err.message || 'Failed to connect'}`,
        code: API_ERROR_CODES.NETWORK_ERROR,
        status: 0,
      });
    } finally {
      if (signal && onCallerAbort) {
        signal.removeEventListener('abort', onCallerAbort);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Approved Implemented S1 Routes
  // -------------------------------------------------------------------------

  /**
   * GET /api/climate/health
   *
   * @param {object} [options]
   * @returns {Promise<object>}
   */
  async getHealth(options = {}) {
    return this._request('/api/climate/health', { method: 'GET', ...options });
  }

  /**
   * GET /api/nodes
   *
   * @param {object} [params]
   * @param {string} [params.status]
   * @param {string} [params.profile]
   * @param {object} [options]
   * @returns {Promise<object>}
   */
  async getNodes({ status, profile, ...options } = {}) {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (profile) params.set('profile', profile);

    const query = params.toString();
    const path = `/api/nodes${query ? `?${query}` : ''}`;
    return this._request(path, { method: 'GET', ...options });
  }

  /**
   * GET /api/nodes/:node_id
   *
   * @param {string} nodeId
   * @param {object} [options]
   * @returns {Promise<object>}
   */
  async getNode(nodeId, options = {}) {
    if (!isValidNodeId(nodeId)) {
      return createErrorResult({
        error: `Invalid node_id "${nodeId}". Must be 3-32 alphanumeric characters, hyphens, or underscores.`,
        code: API_ERROR_CODES.INVALID_NODE_ID,
        status: 400,
        details: { node_id: nodeId },
      });
    }

    const safeId = encodeURIComponent(String(nodeId).trim());
    return this._request(`/api/nodes/${safeId}`, { method: 'GET', ...options });
  }

  /**
   * GET /api/nodes/:node_id/telemetry
   *
   * @param {string} nodeId
   * @param {object} [query]
   * @param {number} [query.limit]
   * @param {string} [query.since]
   * @param {string} [query.until]
   * @param {'asc'|'desc'} [query.order]
   * @param {object} [options]
   * @returns {Promise<object>}
   */
  async getNodeTelemetry(nodeId, { limit, since, until, order, ...options } = {}) {
    if (!isValidNodeId(nodeId)) {
      return createErrorResult({
        error: `Invalid node_id "${nodeId}". Must be 3-32 alphanumeric characters, hyphens, or underscores.`,
        code: API_ERROR_CODES.INVALID_NODE_ID,
        status: 400,
        details: { node_id: nodeId },
      });
    }

    const params = new URLSearchParams();
    if (limit !== undefined && limit !== null) params.set('limit', String(limit));
    if (since) params.set('since', since);
    if (until) params.set('until', until);
    if (order) params.set('order', order);

    const qs = params.toString();
    const safeId = encodeURIComponent(String(nodeId).trim());
    const path = `/api/nodes/${safeId}/telemetry${qs ? `?${qs}` : ''}`;
    return this._request(path, { method: 'GET', ...options });
  }

  // -------------------------------------------------------------------------
  // Future Intelligence & Simulation Stubs
  // (Explicitly surfaces HTTP 501; never fabricates fake success data)
  // -------------------------------------------------------------------------

  /**
   * GET /api/hazards/current
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getCurrentHazards(options = {}) {
    return this._request('/api/hazards/current', { method: 'GET', ...options });
  }

  /**
   * GET /api/hazards/predictions
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getPredictions(options = {}) {
    return this._request('/api/hazards/predictions', { method: 'GET', ...options });
  }

  /**
   * GET /api/compound
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getCompoundEvents(options = {}) {
    return this._request('/api/compound', { method: 'GET', ...options });
  }

  /**
   * GET /api/vulnerability
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getVulnerability(options = {}) {
    return this._request('/api/vulnerability', { method: 'GET', ...options });
  }

  /**
   * GET /api/evacuation
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getEvacuation(options = {}) {
    return this._request('/api/evacuation', { method: 'GET', ...options });
  }

  /**
   * GET /api/response
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getResponse(options = {}) {
    return this._request('/api/response', { method: 'GET', ...options });
  }

  /**
   * GET /api/simulation/scenarios
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async getSimulationScenarios(options = {}) {
    return this._request('/api/simulation/scenarios', { method: 'GET', ...options });
  }

  /**
   * POST /api/simulation/run
   * (Reserved for future producer — returns 501 Not Implemented)
   */
  async runSimulation(payload = {}, options = {}) {
    return this._request('/api/simulation/run', { method: 'POST', body: payload, ...options });
  }

  // -------------------------------------------------------------------------
  // Global Live Data Endpoints
  // -------------------------------------------------------------------------

  async getGlobalSources(options = {}) {
    return this._request('/api/v1/global/sources', { method: 'GET', ...options });
  }

  async getGlobalHazards(hazardType = null, options = {}) {
    const qs = hazardType ? `?hazard_type=${encodeURIComponent(hazardType)}` : '';
    return this._request(`/api/v1/global/hazards${qs}`, { method: 'GET', ...options });
  }

  async getGlobalEvents(options = {}) {
    return this._request('/api/v1/global/events', { method: 'GET', ...options });
  }

  async getGlobalAiSummary(options = {}) {
    return this._request('/api/v1/global/ai-summary', { method: 'GET', ...options });
  }

  async syncGlobal(options = {}) {
    return this._request('/api/v1/global/sync', { method: 'POST', ...options });
  }
}

/**
 * Convenience factory to create a ClimateApiClient instance.
 *
 * @param {object} [options]
 * @returns {ClimateApiClient}
 */
export function createClimateApiClient(options = {}) {
  return new ClimateApiClient(options);
}
