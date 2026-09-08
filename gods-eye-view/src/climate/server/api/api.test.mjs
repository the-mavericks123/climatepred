/**
 * Climate Eye S1 — Step 8I: API Layer Contract & Behavior Tests
 *
 * Validates the REST API routes, standard JSON error formatting,
 * NULL/zero preservation, data-driven node lookups, and 501 stubs.
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';

import { InMemoryClimateRepository } from '../db/inMemoryRepository.js';
import { createClimateApiRouter } from './router.js';

/**
 * Creates mock HTTP request and response objects for unit testing Connect middlewares.
 */
function createMockHttp({ method = 'GET', url = '/', headers = {} } = {}) {
  const req = {
    method,
    url,
    headers,
  };

  const res = new EventEmitter();
  res.statusCode = 200;
  res._headers = {};
  res._body = '';

  res.setHeader = (key, value) => {
    res._headers[key.toLowerCase()] = value;
  };

  res.getHeader = (key) => {
    return res._headers[key.toLowerCase()];
  };

  res.end = (chunk) => {
    if (chunk) {
      res._body += chunk;
    }
    res.emit('finish');
  };

  return { req, res };
}

/**
 * Helper to dispatch a request through the router middleware and parse JSON response.
 */
async function dispatchRequest(router, options) {
  const { req, res } = createMockHttp(options);
  let nextCalled = false;

  await new Promise((resolve) => {
    res.on('finish', resolve);
    router(req, res, () => {
      nextCalled = true;
      resolve();
    });
  });

  let json = null;
  if (res._body) {
    try {
      json = JSON.parse(res._body);
    } catch {
      json = res._body;
    }
  }

  return {
    statusCode: res.statusCode,
    headers: res._headers,
    body: json,
    nextCalled,
  };
}

describe('Step 8I: Climate Eye REST API Layer', () => {
  let repo;
  let router;
  let mockClimateServer;

  beforeEach(() => {
    repo = new InMemoryClimateRepository();
    mockClimateServer = {
      status() {
        return {
          initialized: true,
          subsystems: {
            mqtt: 'idle',
            db: 'ready',
            telemetry: 'ready',
            ingestion: 'idle',
            api: 'ready',
          },
          metrics: {
            receivedCount: 0,
            persistedCount: 0,
            rejectedCount: 0,
            errorCount: 0,
          },
        };
      },
    };

    router = createClimateApiRouter({
      repository: repo,
      climateServer: mockClimateServer,
    });
  });

  // ===========================================================================
  // 1. Health Endpoint: GET /api/climate/health
  // ===========================================================================
  describe('GET /api/climate/health', () => {
    it('reports Climate Eye service status without false health claims', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/climate/health',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.headers['content-type'], 'application/json; charset=utf-8');
      assert.equal(response.body.ok, true);
      assert.equal(response.body.service, 'climate-eye-s1');
      assert.equal(response.body.version, '1.0.0');
      assert.ok(typeof response.body.uptime_s === 'number');
      assert.ok(typeof response.body.timestamp === 'string');

      // Subsystems: never claim unverified components are active
      assert.equal(response.body.subsystems.api, 'ready');
      assert.equal(response.body.subsystems.db, 'ready');
      assert.equal(response.body.subsystems.mqtt, 'idle');
      assert.equal(response.body.subsystems.realtime, 'unimplemented');
      assert.equal(response.body.subsystems.intelligence, 'unimplemented');
    });

    it('rejects non-GET methods with 405 Method Not Allowed', async () => {
      const response = await dispatchRequest(router, {
        method: 'POST',
        url: '/api/climate/health',
      });

      assert.equal(response.statusCode, 405);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'METHOD_NOT_ALLOWED');
    });
  });

  // ===========================================================================
  // 2. Nodes List: GET /api/nodes
  // ===========================================================================
  describe('GET /api/nodes', () => {
    it('returns empty list when no nodes registered', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.body.ok, true);
      assert.equal(response.body.count, 0);
      assert.deepEqual(response.body.nodes, []);
    });

    it('returns registered nodes and supports future NODE-006+ data-driven identities', async () => {
      await repo.upsertNode({
        node_id: 'NODE-001',
        name: 'Downtown Austin Station',
        profile: 'weather',
        latitude: 30.2672,
        longitude: -97.7431,
        status: 'online',
      });

      await repo.upsertNode({
        node_id: 'NODE-006',
        name: 'Hill Country Outpost',
        profile: 'flood',
        latitude: 30.3500,
        longitude: -97.7800,
        status: 'online',
      });

      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.body.ok, true);
      assert.equal(response.body.count, 2);
      assert.equal(response.body.nodes[0].node_id, 'NODE-001');
      assert.equal(response.body.nodes[1].node_id, 'NODE-006');
    });

    it('supports query filtering by status and profile', async () => {
      await repo.upsertNode({ node_id: 'NODE-001', profile: 'weather', status: 'online' });
      await repo.upsertNode({ node_id: 'NODE-002', profile: 'flood', status: 'offline' });

      const resOnline = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes?status=online',
      });

      assert.equal(resOnline.statusCode, 200);
      assert.equal(resOnline.body.count, 1);
      assert.equal(resOnline.body.nodes[0].node_id, 'NODE-001');
    });
  });

  // ===========================================================================
  // 3. Node Details: GET /api/nodes/:node_id
  // ===========================================================================
  describe('GET /api/nodes/:node_id', () => {
    it('returns node details for a registered node', async () => {
      await repo.upsertNode({
        node_id: 'NODE-003',
        name: 'Agricultural Station',
        profile: 'agriculture',
        latitude: 30.1500,
        longitude: -97.6000,
        status: 'online',
      });

      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/NODE-003',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.body.ok, true);
      assert.equal(response.body.node.node_id, 'NODE-003');
      assert.equal(response.body.node.profile, 'agriculture');
    });

    it('returns 404 when node does not exist', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/NODE-NONEXISTENT',
      });

      assert.equal(response.statusCode, 404);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'NODE_NOT_FOUND');
      assert.match(response.body.error, /Node "NODE-NONEXISTENT" not found/);
    });

    it('returns 400 when node_id parameter has invalid grammar', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/ab', // Too short (minimum 3 characters)
      });

      assert.equal(response.statusCode, 400);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'INVALID_NODE_ID');
    });
  });

  // ===========================================================================
  // 4. Node Telemetry: GET /api/nodes/:node_id/telemetry
  // ===========================================================================
  describe('GET /api/nodes/:node_id/telemetry', () => {
    beforeEach(async () => {
      await repo.upsertNode({
        node_id: 'NODE-001',
        profile: 'weather',
        latitude: 30.2672,
        longitude: -97.7431,
      });

      // Insert readings with NULL and zero values
      await repo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-08T00:00:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 26.4,
        rainfall: 0.0, // numeric zero
        water_level: 0.0, // numeric zero
        soil_moisture: null, // explicit null
        // air_quality and battery omitted
      });

      await repo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-08T00:05:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 25.8,
        rainfall: 2.5,
        water_level: 1.0,
      });
    });

    it('returns readings and strictly preserves NULL and zero values', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/NODE-001/telemetry',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.body.ok, true);
      assert.equal(response.body.count, 2);

      // Verify descending order (newest first)
      const newest = response.body.readings[0];
      const oldest = response.body.readings[1];

      assert.equal(newest.timestamp, '2026-09-08T00:05:00.000Z');
      assert.equal(newest.temperature, 25.8);

      assert.equal(oldest.timestamp, '2026-09-08T00:00:00.000Z');
      assert.strictEqual(oldest.rainfall, 0, '0.0 rainfall must be preserved as 0');
      assert.strictEqual(oldest.water_level, 0, '0.0 water_level must be preserved as 0');
      assert.strictEqual(oldest.soil_moisture, null, 'explicit null must remain null');
      assert.strictEqual(oldest.air_quality, null, 'omitted measurement must remain null');
    });

    it('returns 404 when querying telemetry for a non-existent node', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/NODE-MISSING/telemetry',
      });

      assert.equal(response.statusCode, 404);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'NODE_NOT_FOUND');
    });

    it('supports query parameters (limit, order)', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/NODE-001/telemetry?limit=1&order=asc',
      });

      assert.equal(response.statusCode, 200);
      assert.equal(response.body.count, 1);
      assert.equal(response.body.readings[0].timestamp, '2026-09-08T00:00:00.000Z');
    });

    it('rejects invalid node_id parameter on telemetry route with 400', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes/x/telemetry', // Too short
      });

      assert.equal(response.statusCode, 400);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'INVALID_NODE_ID');
    });
  });

  // ===========================================================================
  // 5. Future Intelligence & Simulation Stubs (501 Not Implemented)
  // ===========================================================================
  describe('Future Intelligence & Simulation Stubs', () => {
    const futureEndpoints = [
      { method: 'GET', url: '/api/hazards/current' },
      { method: 'GET', url: '/api/hazards/predictions' },
      { method: 'GET', url: '/api/compound' },
      { method: 'GET', url: '/api/vulnerability' },
      { method: 'GET', url: '/api/evacuation' },
      { method: 'GET', url: '/api/response' },
      { method: 'GET', url: '/api/simulation/scenarios' },
      { method: 'POST', url: '/api/simulation/run' },
    ];

    for (const ep of futureEndpoints) {
      it(`returns explicit 501 Not Implemented for ${ep.method} ${ep.url}`, async () => {
        const response = await dispatchRequest(router, {
          method: ep.method,
          url: ep.url,
        });

        assert.equal(response.statusCode, 501);
        assert.equal(response.body.ok, false);
        assert.equal(response.body.code, 'NOT_IMPLEMENTED');
        assert.match(response.body.error, new RegExp(`Endpoint ${ep.method} ${ep.url} is not implemented in Step 8I`));
      });
    }
  });

  // ===========================================================================
  // 6. Non-Climate Eye Routes & Safe Error Handling
  // ===========================================================================
  describe('Non-Climate Eye Route Fallthrough & Error Safety', () => {
    it('passes unmatched /api routes to next middleware without interference', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/tomtom/traffic',
      });

      assert.equal(response.nextCalled, true, 'Unmatched route must call next()');
    });

    it('passes non-/api routes to next middleware immediately', async () => {
      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/index.html',
      });

      assert.equal(response.nextCalled, true);
    });

    it('safely handles internal repository errors with 500 without leaking details', async () => {
      repo.listNodes = async () => {
        throw new Error('Secret database credentials leaked error');
      };

      const response = await dispatchRequest(router, {
        method: 'GET',
        url: '/api/nodes',
      });

      assert.equal(response.statusCode, 500);
      assert.equal(response.body.ok, false);
      assert.equal(response.body.code, 'INTERNAL_SERVER_ERROR');
      assert.ok(!JSON.stringify(response.body).includes('Secret database credentials'));
    });
  });
});
