/**
 * Climate Eye Software 1 (S1) Backend Integration Entry Point
 *
 * Modular backend integration skeleton designed to mount into Vite Connect
 * middleware during local development or cleanly decouple into an external
 * service (Express, Fastify, etc.) for production deployment.
 *
 * Conforms to DECISION-005 (S1 Backend Architecture Boundary).
 */

'use strict';

import { createRepository } from './db/index.js';
import { createMqttAdapter } from './mqtt/adapter.js';
import { createIngestionOrchestrator } from './ingestion/index.js';
import { createClimateApiRouter } from './api/index.js';
import { createClimateRealtimeServer } from './realtime/index.js';

/**
 * Creates and initializes the Climate Eye S1 backend subsystem.
 *
 * @param {object} options - Initialization options.
 * @param {object} [options.httpServer] - Optional Node.js HTTP server instance for lifecycle cleanup.
 * @param {object} [options.config] - Optional configuration overrides.
 * @param {object} [options.repository] - Optional repository override (e.g. for testing).
 * @param {object} [options.mqttAdapter] - Optional MQTT adapter override.
 * @param {object} [options.orchestrator] - Optional orchestrator override.
 * @param {object} [options.realtimeServer] - Optional realtime server override.
 * @returns {object} Climate S1 server instance.
 */
export function createClimateServer(options = {}) {
  const { httpServer = null, config = {} } = options;

  let isInitialized = false;

  // Initialize DB repository (defaults to in-memory or env-configured PostgreSQL)
  const repository = options.repository || createRepository(config.dbType || 'auto', config.dbOptions || {});

  // Initialize MQTT adapter
  const mqttAdapter = options.mqttAdapter || createMqttAdapter();

  // Initialize Realtime WebSocket Server
  const realtimeServer = options.realtimeServer || createClimateRealtimeServer({ httpServer });

  // Initialize Ingestion Orchestrator
  const orchestrator = options.orchestrator || createIngestionOrchestrator({
    repository,
    mqttAdapter,
    realtimeServer,
    options: {
      onPersistenceError: config.onPersistenceError,
      onRejected: config.onRejected,
    },
  });

  // Initialize API Router middleware
  const apiRouter = createClimateApiRouter({
    repository,
    options: {
      enableS2: config.enableS2 !== false,
      s2BaseUrl: config.s2BaseUrl || process.env.S2_INTELLIGENCE_URL || 'http://127.0.0.1:8000',
      operatorKey: config.operatorKey || process.env.S2_OPERATOR_KEY,
      ...(config.apiOptions || {}),
    },
    climateServer: {
      status() {
        return {
          initialized: isInitialized,
          subsystems: {
            mqtt: mqttAdapter.status().state,
            db: isInitialized ? 'ready' : 'uninitialized',
            telemetry: 'ready',
            ingestion: orchestrator.status().state,
            api: 'ready',
            realtime: realtimeServer.status().state,
            intelligence: 'connected',
          },
          metrics: orchestrator.status().metrics,
        };
      },
    },
  });

  /**
   * Mounts Climate Eye connect middlewares into an existing middleware stack
   * (e.g. Vite dev server middlewares or Connect/Express app).
   *
   * @param {object} middlewares - Connect-compatible middleware stack.
   */
  function installMiddlewares(middlewares) {
    if (!middlewares?.use) return;

    middlewares.use(apiRouter);
  }

  /**
   * Initializes background telemetry consumers, realtime transport, and storage adapters.
   */
  async function start() {
    if (isInitialized) return;
    isInitialized = true;

    await repository.init();
    orchestrator.start();
    realtimeServer.start(httpServer);

    // Clean teardown hook when bound to an HTTP server
    if (httpServer?.on) {
      httpServer.on('close', stop);
    }
  }

  /**
   * Performs graceful teardown of MQTT subscriptions, WebSocket channels,
   * and database connection pools.
   */
  async function stop() {
    if (!isInitialized) return;
    isInitialized = false;

    realtimeServer.stop();
    orchestrator.stop();
    mqttAdapter.stop();
    await repository.close();
  }

  return {
    name: 'climate-eye-s1-backend',
    version: '1.0.0',
    installMiddlewares,
    start,
    stop,
    status() {
      return {
        initialized: isInitialized,
        subsystems: {
          mqtt: mqttAdapter.status().state,
          db: isInitialized ? 'ready' : 'uninitialized',
          telemetry: 'ready',
          ingestion: orchestrator.status().state,
          api: 'ready',
          realtime: realtimeServer.status().state,
        },
        metrics: orchestrator.status().metrics,
      };
    },
    // Expose subsystems for programmatic access and testing
    repository,
    mqttAdapter,
    orchestrator,
    realtimeServer,
  };
}

let activeClimateServer = globalThis.__CLIMATE_SERVER_INSTANCE__ || null;

/**
 * Vite plugin factory for mounting Climate Eye S1 backend into Vite's dev server.
 *
 * Safe against in-process Vite reloads: closes any prior active instance before
 * starting a fresh instance, and registers a teardown hook with httpServer.
 *
 * @param {object} [options]
 * @returns {object} Vite plugin definition.
 */
export function climateServerPlugin(options = {}) {
  return {
    name: 'vite-plugin-climate-server',
    async configureServer(server) {
      if (activeClimateServer) {
        await activeClimateServer.stop();
        activeClimateServer = null;
        globalThis.__CLIMATE_SERVER_INSTANCE__ = null;
      }

      const climateServer = createClimateServer({
        httpServer: server.httpServer,
        config: options,
      });

      climateServer.installMiddlewares(server.middlewares);
      await climateServer.start();

      activeClimateServer = climateServer;
      globalThis.__CLIMATE_SERVER_INSTANCE__ = climateServer;

      server.httpServer?.on('close', async () => {
        if (activeClimateServer === climateServer) {
          await climateServer.stop();
          activeClimateServer = null;
          globalThis.__CLIMATE_SERVER_INSTANCE__ = null;
        }
      });
    },
  };
}
