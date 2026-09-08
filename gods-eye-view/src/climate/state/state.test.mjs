/**
 * Climate Eye — Frontend State Architecture Unit Tests (Step F1)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  REALTIME_STATES,
  CLIMATE_MODES,
  ACTION_TYPES,
  createInitialState,
  climateReducer,
  createClimateStore,
  sanitizeMeasurement,
  normalizeTelemetryPayload,
} from './index.js';

describe('Frontend Step F1: Authoritative Climate Eye State Architecture', () => {

  // -------------------------------------------------------------------------
  // 1. Initial State & Defaults
  // -------------------------------------------------------------------------
  describe('Initial State & Defaults', () => {
    test('initial state contains all 13 required functional sections', () => {
      const state = createInitialState();

      assert.ok(state.connection, 'missing connection section');
      assert.ok(state.system, 'missing system section');
      assert.ok(state.ui, 'missing ui section');
      assert.ok(state.nodes, 'missing nodes section');
      assert.ok(state.telemetry, 'missing telemetry section');
      assert.ok(state.hazards, 'missing hazards section');
      assert.ok(state.predictions, 'missing predictions section');
      assert.ok(state.compound, 'missing compound section');
      assert.ok(state.vulnerability, 'missing vulnerability section');
      assert.ok(state.evacuation, 'missing evacuation section');
      assert.ok(state.response, 'missing response section');
      assert.ok(state.simulation, 'missing simulation section');
      assert.ok(state.ai, 'missing ai section');
    });

    test('realtime state defaults strictly to UNAVAILABLE (never falsely claims LIVE)', () => {
      const state = createInitialState();
      assert.equal(state.connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
      assert.equal(state.connection.connected, false);
      assert.equal(state.connection.lastConnectedAt, null);
    });

    test('UI mode defaults to approved LIVE mode', () => {
      const state = createInitialState();
      assert.equal(state.ui.mode, CLIMATE_MODES.LIVE);
      assert.equal(state.ui.selectedNodeId, null);
    });

    test('initial collections are empty and data-driven (no hardcoded node IDs)', () => {
      const state = createInitialState();
      assert.deepEqual(state.nodes.byId, {});
      assert.deepEqual(state.nodes.allIds, []);
      assert.deepEqual(state.telemetry.byNodeId, {});
      assert.deepEqual(state.telemetry.historyByNodeId, {});
      assert.deepEqual(state.hazards.byId, {});
      assert.deepEqual(state.predictions.byId, {});
      assert.deepEqual(state.compound.events, []);
      assert.equal(state.vulnerability.data, null);
      assert.equal(state.simulation.running, false);
    });
  });

  // -------------------------------------------------------------------------
  // 2. Value Preservation (Null vs Numeric Zero)
  // -------------------------------------------------------------------------
  describe('Value Preservation (Null vs Zero)', () => {
    test('sanitizeMeasurement preserves numeric 0 as a valid measurement', () => {
      assert.equal(sanitizeMeasurement(0), 0);
      assert.equal(sanitizeMeasurement(0.0), 0);
      assert.equal(sanitizeMeasurement('0'), 0);
    });

    test('sanitizeMeasurement converts null, undefined, and non-numeric to null', () => {
      assert.equal(sanitizeMeasurement(null), null);
      assert.equal(sanitizeMeasurement(undefined), null);
      assert.equal(sanitizeMeasurement('invalid'), null);
      assert.equal(sanitizeMeasurement(NaN), null);
      assert.equal(sanitizeMeasurement(Infinity), null);
    });

    test('normalizeTelemetryPayload preserves 0 and null across all canonical sensor fields', () => {
      const raw = {
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-08T00:00:00Z',
        latitude: 0,
        longitude: 0,
        temperature: 0,
        humidity: 0,
        pressure: 1013.25,
        rainfall: 0,
        soil_moisture: null,
        water_level: null,
        air_quality: 0,
        battery: 4.2,
      };

      const normalized = normalizeTelemetryPayload(raw);

      assert.equal(normalized.latitude, 0);
      assert.equal(normalized.longitude, 0);
      assert.equal(normalized.temperature, 0);
      assert.equal(normalized.humidity, 0);
      assert.equal(normalized.rainfall, 0);
      assert.equal(normalized.air_quality, 0);
      assert.equal(normalized.soil_moisture, null);
      assert.equal(normalized.water_level, null);
      assert.equal(normalized.battery, 4.2);
    });
  });

  // -------------------------------------------------------------------------
  // 3. Node Management & Data-Driven Extensibility
  // -------------------------------------------------------------------------
  describe('Node Operations & Extensibility', () => {
    test('inserts and updates nodes data-driven without hardcoded IDs', () => {
      const store = createClimateStore();

      store.updateNode({
        node_id: 'NODE-001',
        latitude: 12.9716,
        longitude: 77.5946,
        status: 'active',
      });

      let state = store.getState();
      assert.deepEqual(state.nodes.allIds, ['NODE-001']);
      assert.equal(state.nodes.byId['NODE-001'].latitude, 12.9716);

      // Future node IDs (NODE-006+) work seamlessly
      store.updateNode({
        node_id: 'NODE-006',
        latitude: 13.0827,
        longitude: 80.2707,
        status: 'active',
      });

      store.updateNode({
        node_id: 'NODE-999-SPECIAL',
        latitude: 28.6139,
        longitude: 77.2090,
        status: 'calibrating',
      });

      state = store.getState();
      assert.deepEqual(state.nodes.allIds, ['NODE-001', 'NODE-006', 'NODE-999-SPECIAL']);
      assert.equal(state.nodes.byId['NODE-006'].latitude, 13.0827);
      assert.equal(state.nodes.byId['NODE-999-SPECIAL'].status, 'calibrating');
    });

    test('batch updateNodes supports multiple nodes simultaneously', () => {
      const store = createClimateStore();
      store.updateNodes([
        { node_id: 'NODE-A', latitude: 10, longitude: 20 },
        { node_id: 'NODE-B', latitude: 30, longitude: 40 },
      ]);

      const state = store.getState();
      assert.deepEqual(state.nodes.allIds, ['NODE-A', 'NODE-B']);
      assert.equal(state.nodes.byId['NODE-A'].latitude, 10);
      assert.equal(state.nodes.byId['NODE-B'].longitude, 40);
    });

    test('removeNode removes node from byId and allIds, and clears selectedNodeId if active', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-X' });
      store.selectNode('NODE-X');

      assert.equal(store.getState().ui.selectedNodeId, 'NODE-X');

      store.removeNode('NODE-X');
      const state = store.getState();
      assert.equal(state.nodes.byId['NODE-X'], undefined);
      assert.ok(!state.nodes.allIds.includes('NODE-X'));
      assert.equal(state.ui.selectedNodeId, null);
    });
  });

  // -------------------------------------------------------------------------
  // 4. Telemetry Operations & Unknown Node Handling
  // -------------------------------------------------------------------------
  describe('Telemetry Operations & Unknown Node Handling', () => {
    test('updates telemetry keyed by node_id and maintains history', () => {
      const store = createClimateStore();

      store.updateTelemetry({
        node_id: 'NODE-001',
        timestamp: '2026-09-08T01:00:00Z',
        temperature: 24.5,
        humidity: 60,
        rainfall: 0,
      });

      store.updateTelemetry({
        node_id: 'NODE-001',
        timestamp: '2026-09-08T01:01:00Z',
        temperature: 25.0,
        humidity: 58,
        rainfall: 2.5,
      });

      const state = store.getState();
      const current = state.telemetry.byNodeId['NODE-001'];
      assert.equal(current.temperature, 25.0);
      assert.equal(current.rainfall, 2.5);

      const history = state.telemetry.historyByNodeId['NODE-001'];
      assert.equal(history.length, 2);
      assert.equal(history[0].temperature, 25.0); // Most recent first
      assert.equal(history[1].temperature, 24.5);
    });

    test('unknown node in telemetry is automatically registered into nodes (data-driven)', () => {
      const store = createClimateStore();

      store.updateTelemetry({
        node_id: 'NODE-007-NEW',
        timestamp: '2026-09-08T01:05:00Z',
        latitude: 19.0760,
        longitude: 72.8777,
        temperature: 31.0,
      });

      const state = store.getState();
      assert.ok(state.nodes.allIds.includes('NODE-007-NEW'));
      assert.equal(state.nodes.byId['NODE-007-NEW'].latitude, 19.0760);
      assert.equal(state.nodes.byId['NODE-007-NEW'].longitude, 72.8777);
      assert.equal(state.telemetry.byNodeId['NODE-007-NEW'].temperature, 31.0);
    });
  });

  // -------------------------------------------------------------------------
  // 5. Connection, Realtime States, & Modes
  // -------------------------------------------------------------------------
  describe('Connection, Realtime States, & Modes', () => {
    test('setRealtimeState transitions between approved realtime states', () => {
      const store = createClimateStore();

      store.setRealtimeState(REALTIME_STATES.LIVE, { connected: true });
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.LIVE);
      assert.equal(store.getState().connection.connected, true);
      assert.ok(store.getState().connection.lastConnectedAt);

      store.setRealtimeState(REALTIME_STATES.STALE);
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.STALE);

      store.setRealtimeState(REALTIME_STATES.SIMULATED);
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.SIMULATED);

      store.setRealtimeState(REALTIME_STATES.UNAVAILABLE, { connected: false });
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
      assert.equal(store.getState().connection.connected, false);
      assert.ok(store.getState().connection.lastDisconnectedAt);
    });

    test('ignores invalid realtime states and retains prior valid state', () => {
      const store = createClimateStore();
      store.setRealtimeState('FAKE_STATE');
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
    });

    test('setUiMode transitions across all approved Climate Eye modes', () => {
      const store = createClimateStore();
      const approvedModes = [
        CLIMATE_MODES.LIVE,
        CLIMATE_MODES.ANALYTICS,
        CLIMATE_MODES.RISK,
        CLIMATE_MODES.SIMULATION,
        CLIMATE_MODES.SENSOR_MESH,
        CLIMATE_MODES.AI,
        CLIMATE_MODES.EMERGENCY,
      ];

      for (const mode of approvedModes) {
        store.setUiMode(mode);
        assert.equal(store.getState().ui.mode, mode);
      }

      // Invalid mode rejected
      store.setUiMode('INVALID_MODE');
      assert.equal(store.getState().ui.mode, CLIMATE_MODES.EMERGENCY);
    });

    test('setSystemStatus updates system status and subsystem readiness honestly', () => {
      const store = createClimateStore();
      store.setSystemStatus({
        status: 'ready',
        subsystems: { mqtt: 'connected', db: 'ready', realtime: 'listening' },
      });

      const state = store.getState();
      assert.equal(state.system.status, 'ready');
      assert.equal(state.system.subsystems.mqtt, 'connected');
      assert.equal(state.system.subsystems.db, 'ready');
      assert.equal(state.system.subsystems.realtime, 'listening');
      assert.ok(state.system.lastHeartbeat);
    });
  });

  // -------------------------------------------------------------------------
  // 6. Intelligence Domains (Hazards, Predictions, Compound, Vulnerability, etc.)
  // -------------------------------------------------------------------------
  describe('Authoritative Intelligence Domains', () => {
    test('updateHazard and updateHazards track active and inactive hazards', () => {
      const store = createClimateStore();

      store.updateHazard({
        hazard_id: 'HAZ-001',
        type: 'flood',
        severity: 'high',
        status: 'active',
      });

      store.updateHazard({
        hazard_id: 'HAZ-002',
        type: 'heatwave',
        severity: 'extreme',
        status: 'resolved',
      });

      const state = store.getState();
      assert.deepEqual(state.hazards.allIds, ['HAZ-001', 'HAZ-002']);
      assert.deepEqual(state.hazards.activeIds, ['HAZ-001']);
      assert.equal(state.hazards.byId['HAZ-001'].severity, 'high');
      assert.equal(state.hazards.byId['HAZ-002'].status, 'resolved');
    });

    test('updatePrediction tracks predictions keyed by prediction_id', () => {
      const store = createClimateStore();

      store.updatePrediction({
        prediction_id: 'PRED-101',
        hazard_type: 'flood',
        confidence: 0.88,
        horizon_hours: 6,
      });

      const state = store.getState();
      assert.deepEqual(state.predictions.allIds, ['PRED-101']);
      assert.equal(state.predictions.byId['PRED-101'].confidence, 0.88);
    });

    test('updateCompound updates compound events list and active event', () => {
      const store = createClimateStore();
      const compoundEvent = {
        event_id: 'CMP-01',
        hazards: ['flood', 'landslide'],
        risk_score: 85,
      };

      store.updateCompound(compoundEvent);

      const state = store.getState();
      assert.equal(state.compound.events.length, 1);
      assert.deepEqual(state.compound.active, compoundEvent);
      assert.ok(state.compound.lastUpdated);
    });

    test('updateVulnerability records vulnerability assessment data', () => {
      const store = createClimateStore();
      const vulnData = { population_at_risk: 15400, hospital_capacity_pct: 78 };

      store.updateVulnerability(vulnData);

      const state = store.getState();
      assert.deepEqual(state.vulnerability.data, vulnData);
      assert.ok(state.vulnerability.lastUpdated);
    });

    test('updateEvacuation records evacuation zones and routes', () => {
      const store = createClimateStore();
      const evac = {
        routes: [{ route_id: 'R1', name: 'Main Arterial North', status: 'clear' }],
        zones: [{ zone_id: 'Z-North', priority: 1 }],
        status: 'advisory',
      };

      store.updateEvacuation(evac);

      const state = store.getState();
      assert.equal(state.evacuation.routes.length, 1);
      assert.equal(state.evacuation.status, 'advisory');
    });

    test('updateResponse records emergency response plans', () => {
      const store = createClimateStore();
      const plan = { plan_id: 'PLAN-ALPHA', units_dispatched: 4 };

      store.updateResponse({ plans: [plan], activePlan: plan });

      const state = store.getState();
      assert.equal(state.response.plans.length, 1);
      assert.deepEqual(state.response.activePlan, plan);
    });

    test('simulation lifecycle: setSimulationState and completeSimulation', () => {
      const store = createClimateStore();

      store.setSimulationState({ running: true, currentRun: 'SIM-2026-001' });
      assert.equal(store.getState().simulation.running, true);
      assert.equal(store.getState().simulation.currentRun, 'SIM-2026-001');

      const simResults = { scenario: 'sea_level_rise_1m', flooded_area_sqkm: 42.5 };
      store.completeSimulation(simResults);

      const state = store.getState();
      assert.equal(state.simulation.running, false);
      assert.equal(state.simulation.currentRun, null);
      assert.deepEqual(state.simulation.results, simResults);
      assert.ok(state.simulation.lastCompletedAt);
    });

    test('updateAiState updates AI inference status and insights', () => {
      const store = createClimateStore();

      store.updateAiState({
        status: 'analyzing',
        insight: { id: 'AI-1', summary: 'Flash flood anomaly detected in Zone 4' },
      });

      const state = store.getState();
      assert.equal(state.ai.status, 'analyzing');
      assert.equal(state.ai.insights.length, 1);
      assert.equal(state.ai.insights[0].summary, 'Flash flood anomaly detected in Zone 4');
      assert.ok(state.ai.lastInference);
    });
  });

  // -------------------------------------------------------------------------
  // 7. Immutability, Determinism, & Store Subscriptions
  // -------------------------------------------------------------------------
  describe('Immutability & Subscriptions', () => {
    test('reducers are pure and produce new object references without mutating previous state', () => {
      const state1 = createInitialState();
      const state2 = climateReducer(state1, {
        type: ACTION_TYPES.NODE_UPDATED,
        payload: { node_id: 'NODE-001', latitude: 10, longitude: 20 },
      });

      assert.notEqual(state1, state2);
      assert.notEqual(state1.nodes, state2.nodes);
      assert.notEqual(state1.nodes.byId, state2.nodes.byId);
      assert.equal(state1.nodes.allIds.length, 0);
      assert.equal(state2.nodes.allIds.length, 1);
    });

    test('subscribe receives state notifications on dispatch and unsubscribe stops delivery', () => {
      const store = createClimateStore();
      const notifications = [];

      const unsubscribe = store.subscribe((state, action) => {
        notifications.push({ state, action });
      });

      store.selectNode('NODE-123');
      store.setUiMode(CLIMATE_MODES.RISK);

      assert.equal(notifications.length, 2);
      assert.equal(notifications[0].action.type, ACTION_TYPES.NODE_SELECTED);
      assert.equal(notifications[1].action.type, ACTION_TYPES.UI_MODE_CHANGED);

      unsubscribe();

      store.selectNode('NODE-456');
      assert.equal(notifications.length, 2); // No further notifications after unsubscribe
    });

    test('resetState resets the store back to initial or provided overrides', () => {
      const store = createClimateStore();
      store.updateNode({ node_id: 'NODE-001' });
      assert.equal(store.getState().nodes.allIds.length, 1);

      store.resetState();
      assert.equal(store.getState().nodes.allIds.length, 0);
      assert.equal(store.getState().connection.realtimeState, REALTIME_STATES.UNAVAILABLE);
    });
  });
});
