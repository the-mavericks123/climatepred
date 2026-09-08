/**
 * Step 8J.1: Climate Eye Realtime WebSocket Transport & Lifecycle Tests
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';

import {
  REALTIME_EVENTS,
  REALTIME_STATES,
  isValidRealtimeEvent,
  formatRealtimeEnvelope,
  CLIMATE_STREAM_PATH,
  ClimateRealtimeServer,
  createClimateRealtimeServer,
} from './index.js';

import { createClimateServer } from '../index.js';

describe('Step 8J.1: Climate Eye Realtime WebSocket Transport', () => {
  let server;
  let port;
  let realtimeServer;

  beforeEach(async () => {
    server = http.createServer((req, res) => {
      res.statusCode = 404;
      res.end('Not Found');
    });

    await new Promise((resolve) => {
      server.listen(0, '127.0.0.1', () => {
        port = server.address().port;
        resolve();
      });
    });

    realtimeServer = createClimateRealtimeServer({ httpServer: server });
    realtimeServer.start();
  });

  afterEach(async () => {
    if (realtimeServer) {
      realtimeServer.stop();
    }
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  describe('Event Envelope & Stream States', () => {
    test('defines all approved event types', () => {
      const expected = [
        'node.updated',
        'telemetry.updated',
        'hazard.updated',
        'prediction.updated',
        'compound.updated',
        'vulnerability.updated',
        'evacuation.updated',
        'response.updated',
        'simulation.completed',
      ];
      assert.deepEqual([...REALTIME_EVENTS].sort(), expected.sort());
      for (const ev of expected) {
        assert.equal(isValidRealtimeEvent(ev), true);
      }
      assert.equal(isValidRealtimeEvent('unknown.event'), false);
      assert.equal(isValidRealtimeEvent(''), false);
      assert.equal(isValidRealtimeEvent(null), false);
    });

    test('preserves canonical stream states without falsely claiming LIVE on open', () => {
      assert.equal(REALTIME_STATES.LIVE, 'LIVE');
      assert.equal(REALTIME_STATES.STALE, 'STALE');
      assert.equal(REALTIME_STATES.SIMULATED, 'SIMULATED');
      assert.equal(REALTIME_STATES.UNAVAILABLE, 'UNAVAILABLE');

      // Newly initialized server defaults to UNAVAILABLE (not LIVE)
      assert.equal(realtimeServer.streamState, REALTIME_STATES.UNAVAILABLE);
    });

    test('formats a standard envelope with UTC ISO-8601 timestamp and payload', () => {
      const payload = { node_id: 'NODE-001', temperature: 22.5 };
      const raw = formatRealtimeEnvelope('telemetry.updated', payload);
      const parsed = JSON.parse(raw);

      assert.equal(parsed.event, 'telemetry.updated');
      assert.deepEqual(parsed.payload, payload);
      assert.match(parsed.timestamp, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    });

    test('rejects unapproved event names in envelope formatter', () => {
      assert.throws(
        () => formatRealtimeEnvelope('fake.hazard', { foo: 'bar' }),
        /Invalid Climate Eye realtime event/
      );
    });
  });

  describe('WebSocket Client Connection & Lifecycle', () => {
    test('connects client to /api/climate/stream and tracks client count', async () => {
      assert.equal(realtimeServer.getClientCount(), 0);

      const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);

      await new Promise((resolve, reject) => {
        ws.on('open', resolve);
        ws.on('error', reject);
      });

      assert.equal(realtimeServer.getClientCount(), 1);

      // Close client and verify count decreases
      ws.close();
      await new Promise((resolve) => ws.on('close', resolve));

      // Small tick for server close event
      await new Promise((r) => setTimeout(r, 20));
      assert.equal(realtimeServer.getClientCount(), 0);
    });

    test('supports multiple concurrent clients', async () => {
      const clients = [
        new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`),
        new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`),
        new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`),
      ];

      await Promise.all(
        clients.map(
          (ws) =>
            new Promise((resolve, reject) => {
              ws.on('open', resolve);
              ws.on('error', reject);
            })
        )
      );

      assert.equal(realtimeServer.getClientCount(), 3);

      // Close all and await close events
      await Promise.all(
        clients.map(
          (ws) =>
            new Promise((resolve) => {
              ws.on('close', resolve);
              ws.close();
            })
        )
      );
      // Small tick for server close event
      await new Promise((r) => setTimeout(r, 50));
      assert.equal(realtimeServer.getClientCount(), 0);
    });

    test('broadcasts event envelope to all connected clients', async () => {
      const c1 = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
      const c2 = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);

      await Promise.all([
        new Promise((resolve) => c1.on('open', resolve)),
        new Promise((resolve) => c2.on('open', resolve)),
      ]);

      const messages1 = [];
      const messages2 = [];
      c1.on('message', (data) => messages1.push(JSON.parse(data.toString())));
      c2.on('message', (data) => messages2.push(JSON.parse(data.toString())));

      const payload = { node_id: 'NODE-002', status: 'maintenance' };
      const sentCount = realtimeServer.broadcast('node.updated', payload);
      assert.equal(sentCount, 2);

      await new Promise((r) => setTimeout(r, 40));

      assert.equal(messages1.length, 1);
      assert.equal(messages1[0].event, 'node.updated');
      assert.deepEqual(messages1[0].payload, payload);

      assert.equal(messages2.length, 1);
      assert.equal(messages2[0].event, 'node.updated');
      assert.deepEqual(messages2[0].payload, payload);

      c1.close();
      c2.close();
    });

    test('broken or disconnected client does not crash server or block other clients', async () => {
      const goodClient = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
      await new Promise((resolve) => goodClient.on('open', resolve));

      // Artificially inject a broken mock client that throws on send
      const mockBrokenClient = {
        readyState: WebSocket.OPEN,
        send() {
          throw new Error('Broken socket connection');
        },
        close() {},
        on() {},
      };
      realtimeServer.clients.add(mockBrokenClient);

      const received = [];
      goodClient.on('message', (d) => received.push(JSON.parse(d.toString())));

      // Broadcasting must not throw
      assert.doesNotThrow(() => {
        realtimeServer.broadcast('simulation.completed', { run_id: 'sim-123' });
      });

      await new Promise((r) => setTimeout(r, 30));
      assert.equal(received.length, 1);
      assert.equal(received[0].event, 'simulation.completed');

      goodClient.close();
    });

    test('repeated start() does not register duplicate listeners', () => {
      const initialListeners = server.listeners('upgrade').length;
      realtimeServer.start();
      realtimeServer.start();
      realtimeServer.start();
      assert.equal(server.listeners('upgrade').length, initialListeners);
    });

    test('repeated stop() is safe and idempotent', () => {
      assert.doesNotThrow(() => {
        realtimeServer.stop();
        realtimeServer.stop();
        realtimeServer.stop();
      });
      assert.equal(realtimeServer.getClientCount(), 0);
      assert.equal(realtimeServer.status().state, 'stopped');
    });

    test('server stop cleanly closes all connected clients with code 1001', async () => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
      await new Promise((resolve) => ws.on('open', resolve));

      const closePromise = new Promise((resolve) => {
        ws.on('close', (code, reason) => {
          resolve({ code, reason: reason.toString() });
        });
      });

      realtimeServer.stop();

      const result = await closePromise;
      assert.equal(result.code, 1001);
      assert.equal(result.reason, 'Climate Eye server shutdown');
      assert.equal(realtimeServer.getClientCount(), 0);
    });
  });

  describe('Pathname Isolation & Vite HMR Non-Interference', () => {
    test('handleUpgrade strictly filters by pathname', () => {
      const socket = { destroyed: false, destroy() { this.destroyed = true; } };
      const head = Buffer.from([]);

      // Non-matching path -> returns false, socket untouched
      const res1 = realtimeServer.handleUpgrade({ url: '/other/path' }, socket, head);
      assert.equal(res1, false);
      assert.equal(socket.destroyed, false);

      // Vite HMR path -> returns false, socket untouched
      const res2 = realtimeServer.handleUpgrade({ url: '/@vite/client' }, socket, head);
      assert.equal(res2, false);
      assert.equal(socket.destroyed, false);

      // Root path -> returns false, socket untouched
      const res3 = realtimeServer.handleUpgrade({ url: '/' }, socket, head);
      assert.equal(res3, false);
      assert.equal(socket.destroyed, false);
    });

    test('coexists with second WebSocket server (simulating Vite HMR) without interference', async () => {
      // Create a second WebSocketServer on the same HTTP server, simulating Vite HMR
      const hmrWss = new WebSocketServer({ noServer: true });
      let hmrConnected = false;

      hmrWss.on('connection', (ws) => {
        hmrConnected = true;
        ws.send(JSON.stringify({ type: 'connected' }));
      });

      // Attach HMR upgrade listener (just like Vite does)
      const hmrUpgradeHandler = (req, socket, head) => {
        const url = new URL(req.url, 'http://localhost');
        if (url.pathname === '/vite-hmr') {
          hmrWss.handleUpgrade(req, socket, head, (ws) => {
            hmrWss.emit('connection', ws, req);
          });
        } else if (url.pathname !== '/api/climate/stream') {
          // Fallback for unhandled paths in test
          socket.destroy();
        }
      };
      server.on('upgrade', hmrUpgradeHandler);

      // 1. Connect to Climate Eye stream
      const climateWs = new WebSocket(`ws://127.0.0.1:${port}/api/climate/stream`);
      await new Promise((resolve, reject) => {
        climateWs.on('open', resolve);
        climateWs.on('error', reject);
      });
      assert.equal(realtimeServer.getClientCount(), 1);

      // 2. Connect to Vite HMR stream
      const hmrWs = new WebSocket(`ws://127.0.0.1:${port}/vite-hmr`);
      const hmrMsgPromise = new Promise((resolve) => {
        hmrWs.on('message', (d) => resolve(JSON.parse(d.toString())));
      });
      await new Promise((resolve, reject) => {
        hmrWs.on('open', resolve);
        hmrWs.on('error', reject);
      });

      const hmrMsg = await hmrMsgPromise;
      assert.equal(hmrConnected, true);
      assert.equal(hmrMsg.type, 'connected');

      // Climate Eye client count is still 1 (did not capture HMR connection)
      assert.equal(realtimeServer.getClientCount(), 1);

      // 3. Connect to non-climate path -> rejected by fallback
      const otherWs = new WebSocket(`ws://127.0.0.1:${port}/other/unhandled`);
      const rejected = await new Promise((resolve) => {
        otherWs.on('open', () => resolve(false));
        otherWs.on('error', () => resolve(true));
      });
      assert.equal(rejected, true);

      climateWs.close();
      hmrWs.close();
      otherWs.close();
      hmrWss.close();
      server.off('upgrade', hmrUpgradeHandler);
    });
  });

  describe('Climate Eye Server Integration', () => {
    test('createClimateServer integrates realtimeServer with start/stop lifecycle', async () => {
      const climate = createClimateServer({ httpServer: server });
      assert.ok(climate.realtimeServer, 'climateServer exposes realtimeServer');

      const initialStatus = climate.status();
      assert.equal(initialStatus.subsystems.realtime, 'stopped');

      await climate.start();
      const runningStatus = climate.status();
      assert.equal(runningStatus.subsystems.realtime, 'running');

      await climate.stop();
      const stoppedStatus = climate.status();
      assert.equal(stoppedStatus.subsystems.realtime, 'stopped');
    });
  });
});
