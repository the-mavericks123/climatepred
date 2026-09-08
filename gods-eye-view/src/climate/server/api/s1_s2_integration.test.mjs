import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { InMemoryClimateRepository } from '../db/inMemoryRepository.js';
import { createClimateApiRouter } from './router.js';

describe('S1 + S2 Integration API Gateway & Forwarding Suite', () => {
  let mockS2Server;
  let s2Port;
  let s2BaseUrl;
  let recordedS2Requests = [];

  before(async () => {
    // Spin up an in-process mock S2 HTTP server to test S1 gateway forwarding
    await new Promise((resolve) => {
      mockS2Server = http.createServer((req, res) => {
        recordedS2Requests.push({
          method: req.method,
          url: req.url,
          headers: req.headers,
        });

        // Collect body if any
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          res.setHeader('Content-Type', 'application/json');

          if (req.url.startsWith('/api/v1/hazards/current')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              hazards: [
                {
                  hazard_id: 'HAZ-HEAT-01',
                  hazard_type: 'HEAT',
                  severity: 0.72,
                  confidence: 0.94,
                  status: 'DETECTED',
                  model_version: 'heat-v1',
                },
              ],
            }));
          } else if (req.url.startsWith('/api/v1/hazards/predictions')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              predictions: [
                {
                  prediction_id: 'PRED-HEAT-30M',
                  target_hazard: 'HEAT',
                  horizon_minutes: 30,
                  predicted_severity: 0.78,
                  confidence: 0.88,
                  status: 'PREDICTED',
                },
              ],
            }));
          } else if (req.url.startsWith('/api/v1/compound')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              events: [
                {
                  event_id: 'COMP-01',
                  severity: 0.85,
                  chain: ['HEAVY_RAIN', 'SOIL_SATURATION', 'FLOOD'],
                },
              ],
            }));
          } else if (req.url.startsWith('/api/v1/vulnerability')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              assessments: [
                {
                  zone_id: 'ZONE-CENTRAL-01',
                  vulnerability: 0.65,
                  human_impact: 0.70,
                  population_exposed: 1200,
                },
              ],
            }));
          } else if (req.url.startsWith('/api/v1/evacuation')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              recommendations: [
                {
                  origin_zone_id: 'ZONE-01',
                  status: 'ACTIVE',
                  primary_route: { distance_km: 4.2 },
                },
              ],
            }));
          } else if (req.url.startsWith('/api/v1/response')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              plan: {
                alert_level: 'ORANGE',
                actions: [
                  {
                    action_id: 'ACT-001',
                    action: 'DISPATCH_SUPPLIES',
                    priority: 1,
                    urgency: 'HIGH',
                  },
                ],
              },
            }));
          } else if (req.url.startsWith('/api/v1/simulation/scenarios')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              scenarios: [{ scenario_id: 'SCN-RAIN-40', name: 'Rainfall Surge (+40%)' }],
            }));
          } else if (req.url.startsWith('/api/v1/simulation/run')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              simulation: {
                simulation_id: 'SIM-001',
                scenario_id: 'SCN-RAIN-40',
                simulated: true,
              },
            }));
          } else if (req.url.startsWith('/api/v1/explainability/hazard/HAZ-001')) {
            res.writeHead(200);
            res.end(JSON.stringify({
              success: true,
              explanation: {
                target_id: 'HAZ-001',
                target_type: 'hazard',
                factors: [{ name: 'temperature', weight: 0.6 }],
              },
            }));
          } else {
            res.writeHead(404);
            res.end(JSON.stringify({ error: 'Not found' }));
          }
        });
      });

      mockS2Server.listen(0, '127.0.0.1', () => {
        s2Port = mockS2Server.address().port;
        s2BaseUrl = `http://127.0.0.1:${s2Port}`;
        resolve();
      });
    });
  });

  after(async () => {
    if (mockS2Server) {
      await new Promise((resolve) => mockS2Server.close(resolve));
    }
  });

  // Helper simulating request through router
  async function simulateRequest(router, { method = 'GET', url, body = null }) {
    return new Promise((resolve) => {
      const headers = { accept: 'application/json' };
      if (body) headers['content-type'] = 'application/json';

      const req = {
        method,
        url,
        headers,
        on(event, cb) {
          if (event === 'data' && body) {
            cb(Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)));
          }
          if (event === 'end') {
            cb();
          }
        },
      };

      let responseHeaders = {};
      let responseBody = '';

      const res = {
        statusCode: 200,
        writeHead(status, hdrs) {
          this.statusCode = status;
          if (hdrs) responseHeaders = hdrs;
        },
        setHeader(name, val) {
          responseHeaders[name] = val;
        },
        getHeader(name) {
          return responseHeaders[name];
        },
        end(data) {
          if (data) responseBody += data;
          let parsed = null;
          try {
            parsed = JSON.parse(responseBody);
          } catch {
            parsed = responseBody;
          }
          resolve({ status: this.statusCode, headers: responseHeaders, body: parsed });
        },
      };

      router(req, res);
    });
  }

  it('forwards GET /api/hazards/current to S2 /api/v1/hazards/current', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/hazards/current' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.hazards.length, 1);
    assert.equal(res.body.hazards[0].hazard_type, 'HEAT');
  });

  it('forwards GET /api/hazards/predictions to S2 /api/v1/hazards/predictions', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/hazards/predictions' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.predictions.length, 1);
    assert.equal(res.body.predictions[0].horizon_minutes, 30);
  });

  it('forwards GET /api/compound to S2 /api/v1/compound', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/compound' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.events.length, 1);
    assert.deepEqual(res.body.events[0].chain, ['HEAVY_RAIN', 'SOIL_SATURATION', 'FLOOD']);
  });

  it('forwards GET /api/vulnerability to S2 /api/v1/vulnerability', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/vulnerability' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.assessments[0].zone_id, 'ZONE-CENTRAL-01');
  });

  it('forwards GET /api/evacuation to S2 /api/v1/evacuation', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/evacuation' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.recommendations[0].status, 'ACTIVE');
  });

  it('forwards GET /api/response to S2 /api/v1/response', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/response' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.plan.alert_level, 'ORANGE');
  });

  it('forwards GET /api/simulation/scenarios to S2 /api/v1/simulation/scenarios', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/simulation/scenarios' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.scenarios[0].scenario_id, 'SCN-RAIN-40');
  });

  it('forwards POST /api/simulation/run to S2 /api/v1/simulation/run', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, {
      method: 'POST',
      url: '/api/simulation/run',
      body: { scenario_id: 'SCN-RAIN-40' },
    });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.simulation.simulated, true);
  });

  it('forwards GET /api/explainability/:target_type/:target_id to S2', async () => {
    const router = createClimateApiRouter({ repository: new InMemoryClimateRepository(), enableS2: true, s2BaseUrl });
    const res = await simulateRequest(router, { url: '/api/explainability/hazard/HAZ-001' });

    assert.equal(res.status, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.explanation.target_id, 'HAZ-001');
  });

  it('handles S2 backend unavailable with 503 MODEL_UNAVAILABLE', async () => {
    const offlineRouter = createClimateApiRouter({
      repository: new InMemoryClimateRepository(),
      enableS2: true,
      s2BaseUrl: 'http://127.0.0.1:59999', // Non-existent offline port
    });

    const res = await simulateRequest(offlineRouter, { url: '/api/hazards/current' });
    assert.equal(res.status, 503);
    assert.equal(res.body.ok, false);
    assert.equal(res.body.code, 'MODEL_UNAVAILABLE');
  });
});
