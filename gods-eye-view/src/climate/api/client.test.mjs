/**
 * Climate Eye — Frontend REST API Client Unit Tests (Step F2)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  ClimateApiClient,
  createClimateApiClient,
  isValidNodeId,
  createErrorResult,
  createSuccessResult,
  API_ERROR_CODES,
} from './index.js';

/**
 * Creates a mock fetch function returning controlled responses.
 */
function createMockFetch(handler) {
  const calls = [];
  const mock = async (url, options = {}) => {
    calls.push({ url, options });
    return handler(url, options);
  };
  mock.calls = calls;
  return mock;
}

/**
 * Helper to build a mock Response object.
 */
function mockResponse({ status = 200, body = {}, headers = {} }) {
  const isOk = status >= 200 && status < 300;
  const jsonText = typeof body === 'string' ? body : JSON.stringify(body);
  return {
    ok: isOk,
    status,
    headers: new Headers({ 'Content-Type': 'application/json', ...headers }),
    text: async () => jsonText,
    json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
  };
}

describe('Frontend Step F2: Climate Eye REST API Client', () => {

  // -------------------------------------------------------------------------
  // 1. Client Initialization & Node ID Validation
  // -------------------------------------------------------------------------
  describe('Initialization & Validation', () => {
    test('instantiates with custom baseUrl and default timeout', () => {
      const client = new ClimateApiClient({ baseUrl: 'https://api.climate.example.com/', timeout: 5000 });
      assert.equal(client.baseUrl, 'https://api.climate.example.com');
      assert.equal(client.defaultTimeout, 5000);
    });

    test('validates node_id grammar strictly before network calls', () => {
      assert.equal(isValidNodeId('NODE-001'), true);
      assert.equal(isValidNodeId('node_alpha_123'), true);
      assert.equal(isValidNodeId('abc'), true);
      assert.equal(isValidNodeId('12345678901234567890123456789012'), true); // 32 chars

      assert.equal(isValidNodeId('no'), false); // < 3 chars
      assert.equal(isValidNodeId('123456789012345678901234567890123'), false); // > 32 chars
      assert.equal(isValidNodeId('node with spaces'), false);
      assert.equal(isValidNodeId('node/slash'), false);
      assert.equal(isValidNodeId('node?param=1'), false);
      assert.equal(isValidNodeId(null), false);
      assert.equal(isValidNodeId(undefined), false);
    });

    test('getNode and getNodeTelemetry reject invalid node_id without firing fetch', async () => {
      const mockFetch = createMockFetch(() => assert.fail('Fetch should not have been called'));
      const client = new ClimateApiClient({ fetch: mockFetch });

      const res1 = await client.getNode('bad/id');
      assert.equal(res1.ok, false);
      assert.equal(res1.code, API_ERROR_CODES.INVALID_NODE_ID);
      assert.equal(res1.status, 400);

      const res2 = await client.getNodeTelemetry('ab'); // too short
      assert.equal(res2.ok, false);
      assert.equal(res2.code, API_ERROR_CODES.INVALID_NODE_ID);

      assert.equal(mockFetch.calls.length, 0);
    });
  });

  // -------------------------------------------------------------------------
  // 2. Health Endpoint
  // -------------------------------------------------------------------------
  describe('GET /api/climate/health', () => {
    test('fetches health status and returns structured result', async () => {
      const mockPayload = {
        ok: true,
        service: 'climate-eye-s1',
        version: '1.0.0',
        subsystems: { api: 'ready', db: 'ready', realtime: 'listening' },
      };

      const mockFetch = createMockFetch((url) => {
        assert.equal(url, '/api/climate/health');
        return mockResponse({ status: 200, body: mockPayload });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getHealth();

      assert.equal(result.ok, true);
      assert.equal(result.status, 200);
      assert.equal(result.data.service, 'climate-eye-s1');
      assert.equal(result.data.subsystems.realtime, 'listening');
    });
  });

  // -------------------------------------------------------------------------
  // 3. Nodes Endpoints (List & Single)
  // -------------------------------------------------------------------------
  describe('Nodes Endpoints', () => {
    test('getNodes constructs query parameters correctly', async () => {
      const mockFetch = createMockFetch((url) => {
        assert.equal(url, '/api/nodes?status=active&profile=weather');
        return mockResponse({ status: 200, body: { ok: true, count: 1, nodes: [{ node_id: 'NODE-001' }] } });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getNodes({ status: 'active', profile: 'weather' });

      assert.equal(result.ok, true);
      assert.equal(result.data.count, 1);
      assert.equal(result.data.nodes[0].node_id, 'NODE-001');
    });

    test('getNode retrieves a single node', async () => {
      const mockFetch = createMockFetch((url) => {
        assert.equal(url, '/api/nodes/NODE-002');
        return mockResponse({ status: 200, body: { ok: true, node: { node_id: 'NODE-002', latitude: 12.5 } } });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getNode('NODE-002');

      assert.equal(result.ok, true);
      assert.equal(result.data.node.node_id, 'NODE-002');
      assert.equal(result.data.node.latitude, 12.5);
    });

    test('getNode handles 404 Not Found cleanly without throwing', async () => {
      const mockFetch = createMockFetch((url) => {
        return mockResponse({
          status: 404,
          body: { ok: false, error: 'Node "NODE-999" not found', code: 'NODE_NOT_FOUND', details: { node_id: 'NODE-999' } },
        });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getNode('NODE-999');

      assert.equal(result.ok, false);
      assert.equal(result.status, 404);
      assert.equal(result.code, 'NODE_NOT_FOUND');
      assert.equal(result.error, 'Node "NODE-999" not found');
      assert.deepEqual(result.details, { node_id: 'NODE-999' });
    });
  });

  // -------------------------------------------------------------------------
  // 4. Telemetry Endpoint & Value Preservation
  // -------------------------------------------------------------------------
  describe('Telemetry Endpoint & Value Preservation', () => {
    test('getNodeTelemetry passes pagination/filter query params', async () => {
      const mockFetch = createMockFetch((url) => {
        assert.equal(url, '/api/nodes/NODE-001/telemetry?limit=25&since=2026-09-08T00%3A00%3A00Z&order=asc');
        return mockResponse({
          status: 200,
          body: {
            ok: true,
            node_id: 'NODE-001',
            count: 2,
            readings: [
              { temperature: 0, rainfall: 0, soil_moisture: null },
              { temperature: 28.5, rainfall: 12.0, soil_moisture: 45.2 },
            ],
          },
        });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getNodeTelemetry('NODE-001', {
        limit: 25,
        since: '2026-09-08T00:00:00Z',
        order: 'asc',
      });

      assert.equal(result.ok, true);
      assert.equal(result.data.readings.length, 2);

      // Exact preservation of 0 and null
      const reading0 = result.data.readings[0];
      assert.equal(reading0.temperature, 0);
      assert.equal(reading0.rainfall, 0);
      assert.equal(reading0.soil_moisture, null);
    });
  });

  // -------------------------------------------------------------------------
  // 5. Future 501 Not Implemented Endpoints
  // -------------------------------------------------------------------------
  describe('Future Endpoints (501 Stubs)', () => {
    test('future endpoints surface 501 Not Implemented honestly', async () => {
      const stubEndpoints = [
        ['getCurrentHazards', '/api/hazards/current'],
        ['getPredictions', '/api/hazards/predictions'],
        ['getCompoundEvents', '/api/compound'],
        ['getVulnerability', '/api/vulnerability'],
        ['getEvacuation', '/api/evacuation'],
        ['getResponse', '/api/response'],
        ['getSimulationScenarios', '/api/simulation/scenarios'],
      ];

      for (const [methodName, expectedPath] of stubEndpoints) {
        const mockFetch = createMockFetch((url) => {
          assert.equal(url, expectedPath);
          return mockResponse({
            status: 501,
            body: { ok: false, error: `Endpoint GET ${expectedPath} is not implemented`, code: 'NOT_IMPLEMENTED' },
          });
        });

        const client = new ClimateApiClient({ fetch: mockFetch });
        const result = await client[methodName]();

        assert.equal(result.ok, false);
        assert.equal(result.status, 501);
        assert.equal(result.code, 'NOT_IMPLEMENTED');
      }
    });

    test('runSimulation surfaces 501 for POST /api/simulation/run', async () => {
      const mockFetch = createMockFetch((url, opts) => {
        assert.equal(url, '/api/simulation/run');
        assert.equal(opts.method, 'POST');
        return mockResponse({
          status: 501,
          body: { ok: false, error: 'Endpoint POST /api/simulation/run is not implemented', code: 'NOT_IMPLEMENTED' },
        });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.runSimulation({ scenario: 'cyclone' });

      assert.equal(result.ok, false);
      assert.equal(result.status, 501);
      assert.equal(result.code, 'NOT_IMPLEMENTED');
    });
  });

  // -------------------------------------------------------------------------
  // 6. Network Errors, Timeouts, & Parse Errors
  // -------------------------------------------------------------------------
  describe('Error Handling & Normalization', () => {
    test('handles network failure without crashing', async () => {
      const mockFetch = createMockFetch(() => {
        throw new TypeError('Failed to fetch');
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getHealth();

      assert.equal(result.ok, false);
      assert.equal(result.code, API_ERROR_CODES.NETWORK_ERROR);
      assert.match(result.error, /Network error/);
    });

    test('handles caller abort signal', async () => {
      const controller = new AbortController();
      const mockFetch = createMockFetch((url, { signal }) => {
        return new Promise((_, reject) => {
          signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
        });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const promise = client.getHealth({ signal: controller.signal });
      controller.abort();

      const result = await promise;
      assert.equal(result.ok, false);
      assert.equal(result.code, API_ERROR_CODES.REQUEST_ABORTED);
    });

    test('handles request timeout via AbortController', async () => {
      const mockFetch = createMockFetch(() => {
        const err = new DOMException('Request timeout', 'TimeoutError');
        throw err;
      });

      const client = new ClimateApiClient({ fetch: mockFetch, timeout: 50 });
      const result = await client.getHealth();

      assert.equal(result.ok, false);
      assert.equal(result.code, API_ERROR_CODES.REQUEST_TIMEOUT);
      assert.match(result.error, /Request timed out/);
    });

    test('handles malformed non-JSON response from server', async () => {
      const mockFetch = createMockFetch(() => {
        return mockResponse({ status: 502, body: '<html>Bad Gateway</html>' });
      });

      const client = new ClimateApiClient({ fetch: mockFetch });
      const result = await client.getHealth();

      assert.equal(result.ok, false);
      assert.equal(result.code, API_ERROR_CODES.PARSE_ERROR);
      assert.equal(result.status, 502);
    });

    test('redacts potential database credentials from error messages', () => {
      const errorWithSecret = 'Connection failed postgres://user:super_secret_password@db.internal:5432/climate';
      const result = createErrorResult({ error: errorWithSecret, code: 'DB_ERROR', status: 500 });

      assert.ok(!result.error.includes('super_secret_password'));
      assert.ok(result.error.includes('[redacted]'));
    });
  });
});
