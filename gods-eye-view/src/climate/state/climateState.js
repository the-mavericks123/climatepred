/**
 * Climate Eye — Authoritative Frontend State Architecture
 *
 * Implements a pure, deterministic, browser-safe state container for Climate Eye.
 *
 * Requirements (Frontend F1):
 * - One authoritative state model with clear domain sections:
 *   connection, system, nodes, telemetry, hazards, predictions, compound,
 *   vulnerability, evacuation, response, simulation, AI, UI mode.
 * - Realtime state defaults to UNAVAILABLE (never falsely claims LIVE on startup).
 * - Fully data-driven: no hard-coded node IDs; supports dynamic/future IDs (NODE-006+).
 * - Preserves null as missing/unavailable and numeric zero (0) as real measurement.
 * - Does NOT calculate risk or duplicate backend intelligence.
 * - 100% browser-safe: no Node.js built-ins.
 * - Zero external state-management dependencies.
 */

import { REALTIME_STATES, CLIMATE_MODES, CLIMATE_LAYERS, ACTION_TYPES } from './constants.js';

// ---------------------------------------------------------------------------
// Initial State Factory
// ---------------------------------------------------------------------------

/**
 * Creates a fresh, authoritative initial state tree.
 *
 * @param {object} [overrides]
 * @returns {object} Initial state
 */
export function createInitialState(overrides = {}) {
  const base = {
    connection: {
      realtimeState: REALTIME_STATES.UNAVAILABLE,
      connected: false,
      lastConnectedAt: null,
      lastDisconnectedAt: null,
      lastError: null,
    },
    system: {
      status: 'uninitialized',
      version: '1.0.0',
      subsystems: {
        mqtt: 'unknown',
        db: 'unknown',
        telemetry: 'unknown',
        ingestion: 'unknown',
        api: 'unknown',
        realtime: 'unknown',
      },
      lastHeartbeat: null,
    },
    ui: {
      mode: CLIMATE_MODES.LIVE,
      selectedNodeId: null,
      selectedHazardId: null,
      selectedPredictionId: null,
      activeOverlays: [],
    },
    nodes: {
      byId: {},
      allIds: [],
    },
    telemetry: {
      byNodeId: {},
      historyByNodeId: {},
    },
    hazards: {
      byId: {},
      allIds: [],
      activeIds: [],
    },
    predictions: {
      byId: {},
      allIds: [],
    },
    compound: {
      events: [],
      active: null,
      lastUpdated: null,
    },
    vulnerability: {
      data: null,
      lastUpdated: null,
    },
    evacuation: {
      routes: [],
      zones: [],
      status: null,
      lastUpdated: null,
    },
    response: {
      plans: [],
      activePlan: null,
      lastUpdated: null,
    },
    simulation: {
      running: false,
      currentRun: null,
      results: null,
      lastCompletedAt: null,
    },
    ai: {
      status: 'idle',
      insights: [],
      lastInference: null,
    },
    global: {
      status: 'ONLINE',
      systemStatus: 'OPERATIONAL',
      sources: [],
      hazards: [],
      events: [],
      weather: [],
      activeCount: 0,
      highRiskCount: 0,
      compoundCount: 0,
      aiSummary: null,
      lastSync: null,
    },
    layers: {
      [CLIMATE_LAYERS.SENSOR_MESH]: true,
      [CLIMATE_LAYERS.TEMPERATURE]: true,
      [CLIMATE_LAYERS.RAINFALL]: false,
      [CLIMATE_LAYERS.SOIL_MOISTURE]: false,
      [CLIMATE_LAYERS.AIR_QUALITY]: false,
      [CLIMATE_LAYERS.WATER_LEVEL]: false,
      [CLIMATE_LAYERS.FIRES]: false,
      [CLIMATE_LAYERS.DAMS]: false,
      [CLIMATE_LAYERS.EARTHQUAKES]: false,
      [CLIMATE_LAYERS.GLOBAL_HAZARDS]: true,
      [CLIMATE_LAYERS.HEAT_ZONES]: true,
      [CLIMATE_LAYERS.FLOOD_ZONES]: true,
      [CLIMATE_LAYERS.COMPOUND_ZONES]: true,
      [CLIMATE_LAYERS.CYCLONE_ZONES]: true,

    },
  };

  return {
    ...base,
    ...overrides,
    connection: { ...base.connection, ...(overrides.connection || {}) },
    system: { ...base.system, ...(overrides.system || {}) },
    ui: { ...base.ui, ...(overrides.ui || {}) },
    layers: { ...base.layers, ...(overrides.layers || {}) },
    nodes: { ...base.nodes, ...(overrides.nodes || {}) },
    telemetry: { ...base.telemetry, ...(overrides.telemetry || {}) },
    hazards: { ...base.hazards, ...(overrides.hazards || {}) },
    predictions: { ...base.predictions, ...(overrides.predictions || {}) },
    compound: { ...base.compound, ...(overrides.compound || {}) },
    vulnerability: { ...base.vulnerability, ...(overrides.vulnerability || {}) },
    evacuation: { ...base.evacuation, ...(overrides.evacuation || {}) },
    response: { ...base.response, ...(overrides.response || {}) },
    simulation: { ...base.simulation, ...(overrides.simulation || {}) },
    ai: { ...base.ai, ...(overrides.ai || {}) },
    global: { ...base.global, ...(overrides.global || {}) },
  };
}

// ---------------------------------------------------------------------------
// Telemetry Normalization & Value Preservation
// ---------------------------------------------------------------------------

/**
 * Sanitizes and preserves a telemetry measurement value:
 * - numeric 0 is strictly preserved (NOT converted to null or false)
 * - null or undefined becomes null
 * - numbers are kept as numbers
 *
 * @param {*} value
 * @returns {number|null}
 */
export function sanitizeMeasurement(value) {
  if (value === null || value === undefined) return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

/**
 * Normalizes incoming telemetry payload into the frontend store shape,
 * strictly preserving null and 0 values.
 *
 * @param {object} raw
 * @returns {object|null}
 */
export function normalizeTelemetryPayload(raw) {
  const data = raw?.telemetry && typeof raw.telemetry === 'object' ? raw.telemetry : raw;
  if (!data || typeof data !== 'object' || !data.node_id) return null;

  return {
    schema_version: data.schema_version || '1.0.0',
    node_id: String(data.node_id),
    timestamp: data.timestamp || raw?.timestamp || new Date().toISOString(),
    latitude: sanitizeMeasurement(data.latitude),
    longitude: sanitizeMeasurement(data.longitude),
    temperature: sanitizeMeasurement(data.temperature),
    humidity: sanitizeMeasurement(data.humidity),
    pressure: sanitizeMeasurement(data.pressure),
    rainfall: sanitizeMeasurement(data.rainfall),
    soil_moisture: sanitizeMeasurement(data.soil_moisture),
    water_level: sanitizeMeasurement(data.water_level),
    air_quality: sanitizeMeasurement(data.air_quality),
    battery: sanitizeMeasurement(data.battery),
  };
}

// ---------------------------------------------------------------------------
// Pure Reducer
// ---------------------------------------------------------------------------

const MAX_TELEMETRY_HISTORY_PER_NODE = 50;

/**
 * Pure reducer function for Climate Eye state.
 *
 * @param {object} state
 * @param {{ type: string, payload?: any }} action
 * @returns {object} New state
 */
export function climateReducer(state = createInitialState(), action = {}) {
  if (!action || !action.type) return state;

  switch (action.type) {
    case ACTION_TYPES.REALTIME_STATE_CHANGED: {
      const { realtimeState, connected, error } = action.payload || {};
      const validState = Object.values(REALTIME_STATES).includes(realtimeState)
        ? realtimeState
        : state.connection.realtimeState;

      const isConnected = typeof connected === 'boolean'
        ? connected
        : validState === REALTIME_STATES.LIVE;

      return {
        ...state,
        connection: {
          ...state.connection,
          realtimeState: validState,
          connected: isConnected,
          lastConnectedAt: isConnected ? (action.payload?.timestamp || new Date().toISOString()) : state.connection.lastConnectedAt,
          lastDisconnectedAt: !isConnected && state.connection.connected ? (action.payload?.timestamp || new Date().toISOString()) : state.connection.lastDisconnectedAt,
          lastError: error !== undefined ? error : state.connection.lastError,
        },
      };
    }

    case ACTION_TYPES.SYSTEM_STATUS_CHANGED: {
      const payload = action.payload || {};
      return {
        ...state,
        system: {
          ...state.system,
          ...payload,
          subsystems: {
            ...state.system.subsystems,
            ...(payload.subsystems || {}),
          },
          lastHeartbeat: payload.lastHeartbeat || new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.LAYER_VISIBILITY_CHANGED: {
      const { layerId, visible } = action.payload || {};
      if (!layerId || typeof visible !== 'boolean') return state;
      if (state.layers && state.layers[layerId] === visible) return state;

      return {
        ...state,
        layers: {
          ...(state.layers || {}),
          [layerId]: visible,
        },
      };
    }

    case ACTION_TYPES.UI_MODE_CHANGED: {
      const { mode } = action.payload || {};
      if (!Object.values(CLIMATE_MODES).includes(mode)) {
        return state;
      }
      return {
        ...state,
        ui: {
          ...state.ui,
          mode,
        },
      };
    }

    case ACTION_TYPES.NODE_SELECTED: {
      const { nodeId } = action.payload || {};
      return {
        ...state,
        ui: {
          ...state.ui,
          selectedNodeId: nodeId ? String(nodeId) : null,
        },
      };
    }

    case ACTION_TYPES.NODE_UPDATED: {
      const node = action.payload;
      if (!node || !node.node_id) return state;

      const nodeId = String(node.node_id);
      const existing = state.nodes.byId[nodeId] || {};
      const updated = {
        ...existing,
        ...node,
        node_id: nodeId,
        latitude: node.latitude !== undefined ? sanitizeMeasurement(node.latitude) : existing.latitude ?? null,
        longitude: node.longitude !== undefined ? sanitizeMeasurement(node.longitude) : existing.longitude ?? null,
        status: node.status || existing.status || 'active',
        lastSeen: node.timestamp || node.lastSeen || existing.lastSeen || new Date().toISOString(),
      };

      const allIds = state.nodes.allIds.includes(nodeId)
        ? state.nodes.allIds
        : [...state.nodes.allIds, nodeId];

      return {
        ...state,
        nodes: {
          ...state.nodes,
          byId: {
            ...state.nodes.byId,
            [nodeId]: updated,
          },
          allIds,
        },
      };
    }

    case ACTION_TYPES.NODES_UPDATED: {
      const nodes = action.payload;
      if (!Array.isArray(nodes) || nodes.length === 0) return state;

      let nextState = state;
      for (const node of nodes) {
        nextState = climateReducer(nextState, { type: ACTION_TYPES.NODE_UPDATED, payload: node });
      }
      return nextState;
    }

    case ACTION_TYPES.NODE_REMOVED: {
      const { nodeId } = action.payload || {};
      if (!nodeId || !state.nodes.byId[nodeId]) return state;

      const nextById = { ...state.nodes.byId };
      delete nextById[nodeId];

      return {
        ...state,
        nodes: {
          ...state.nodes,
          byId: nextById,
          allIds: state.nodes.allIds.filter((id) => id !== nodeId),
        },
        ui: {
          ...state.ui,
          selectedNodeId: state.ui.selectedNodeId === nodeId ? null : state.ui.selectedNodeId,
        },
      };
    }

    case ACTION_TYPES.TELEMETRY_UPDATED: {
      const rawTelemetry = action.payload;
      const normalized = normalizeTelemetryPayload(rawTelemetry);
      if (!normalized) return state;

      const nodeId = normalized.node_id;

      // Update telemetry history
      const prevHistory = state.telemetry.historyByNodeId[nodeId] || [];
      const nextHistory = [normalized, ...prevHistory].slice(0, MAX_TELEMETRY_HISTORY_PER_NODE);

      // Keep node coordinates & lastSeen in sync if provided
      let nextNodes = state.nodes;
      const existingNode = state.nodes.byId[nodeId];
      if (existingNode) {
        nextNodes = {
          ...state.nodes,
          byId: {
            ...state.nodes.byId,
            [nodeId]: {
              ...existingNode,
              latitude: normalized.latitude !== null ? normalized.latitude : existingNode.latitude,
              longitude: normalized.longitude !== null ? normalized.longitude : existingNode.longitude,
              lastSeen: normalized.timestamp,
            },
          },
        };
      } else {
        // Unknown node: auto-insert minimal node entry (data-driven)
        nextNodes = {
          ...state.nodes,
          byId: {
            ...state.nodes.byId,
            [nodeId]: {
              node_id: nodeId,
              latitude: normalized.latitude,
              longitude: normalized.longitude,
              status: 'active',
              lastSeen: normalized.timestamp,
            },
          },
          allIds: [...state.nodes.allIds, nodeId],
        };
      }

      return {
        ...state,
        nodes: nextNodes,
        telemetry: {
          ...state.telemetry,
          byNodeId: {
            ...state.telemetry.byNodeId,
            [nodeId]: normalized,
          },
          historyByNodeId: {
            ...state.telemetry.historyByNodeId,
            [nodeId]: nextHistory,
          },
        },
      };
    }

    case ACTION_TYPES.HAZARD_UPDATED: {
      const hazard = action.payload;
      if (!hazard) return state;

      if (Array.isArray(hazard.hazards)) {
        return climateReducer(state, { type: ACTION_TYPES.HAZARDS_UPDATED, payload: hazard.hazards });
      }
      if (!hazard.hazard_id) return state;

      const hazardId = String(hazard.hazard_id);
      const existing = state.hazards.byId[hazardId] || {};
      const updated = { ...existing, ...hazard, hazard_id: hazardId };

      const allIds = state.hazards.allIds.includes(hazardId)
        ? state.hazards.allIds
        : [...state.hazards.allIds, hazardId];

      const isActive = updated.status === 'active' || updated.active === true;
      const activeIds = isActive
        ? (state.hazards.activeIds.includes(hazardId) ? state.hazards.activeIds : [...state.hazards.activeIds, hazardId])
        : state.hazards.activeIds.filter((id) => id !== hazardId);

      return {
        ...state,
        hazards: {
          ...state.hazards,
          byId: {
            ...state.hazards.byId,
            [hazardId]: updated,
          },
          allIds,
          activeIds,
        },
      };
    }

    case ACTION_TYPES.HAZARDS_UPDATED: {
      const hazards = action.payload;
      if (!Array.isArray(hazards)) return state;

      let nextState = state;
      for (const h of hazards) {
        nextState = climateReducer(nextState, { type: ACTION_TYPES.HAZARD_UPDATED, payload: h });
      }
      return nextState;
    }

    case ACTION_TYPES.PREDICTION_UPDATED: {
      const prediction = action.payload;
      if (!prediction) return state;

      if (Array.isArray(prediction.predictions)) {
        return climateReducer(state, { type: ACTION_TYPES.PREDICTIONS_UPDATED, payload: prediction.predictions });
      }
      if (!prediction.prediction_id) return state;

      const predId = String(prediction.prediction_id);
      const existing = state.predictions.byId[predId] || {};
      const updated = { ...existing, ...prediction, prediction_id: predId };

      const allIds = state.predictions.allIds.includes(predId)
        ? state.predictions.allIds
        : [...state.predictions.allIds, predId];

      return {
        ...state,
        predictions: {
          ...state.predictions,
          byId: {
            ...state.predictions.byId,
            [predId]: updated,
          },
          allIds,
        },
      };
    }

    case ACTION_TYPES.PREDICTIONS_UPDATED: {
      const predictions = action.payload;
      if (!Array.isArray(predictions)) return state;

      let nextState = state;
      for (const p of predictions) {
        nextState = climateReducer(nextState, { type: ACTION_TYPES.PREDICTION_UPDATED, payload: p });
      }
      return nextState;
    }

    case ACTION_TYPES.COMPOUND_UPDATED: {
      const event = action.payload;
      if (!event) return state;

      const list = Array.isArray(event) ? event : (Array.isArray(event?.events) ? event.events : [event]);

      return {
        ...state,
        compound: {
          ...state.compound,
          events: list,
          active: list[0] || null,
          lastUpdated: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.VULNERABILITY_UPDATED: {
      return {
        ...state,
        vulnerability: {
          data: action.payload || null,
          lastUpdated: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.EVACUATION_UPDATED: {
      const data = action.payload || {};
      return {
        ...state,
        evacuation: {
          ...state.evacuation,
          routes: data.routes || state.evacuation.routes,
          zones: data.zones || state.evacuation.zones,
          status: data.status !== undefined ? data.status : state.evacuation.status,
          lastUpdated: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.RESPONSE_UPDATED: {
      const data = action.payload || {};
      return {
        ...state,
        response: {
          ...state.response,
          plans: data.plans || state.response.plans,
          activePlan: data.activePlan !== undefined ? data.activePlan : state.response.activePlan,
          lastUpdated: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.SIMULATION_STATE_CHANGED: {
      const data = action.payload || {};
      return {
        ...state,
        simulation: {
          ...state.simulation,
          running: !!data.running,
          currentRun: data.currentRun !== undefined ? data.currentRun : state.simulation.currentRun,
        },
      };
    }

    case ACTION_TYPES.SIMULATION_COMPLETED: {
      const results = action.payload;
      return {
        ...state,
        simulation: {
          ...state.simulation,
          running: false,
          currentRun: null,
          results,
          lastCompletedAt: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.AI_STATE_UPDATED: {
      const ai = action.payload || {};
      return {
        ...state,
        ai: {
          ...state.ai,
          status: ai.status || state.ai.status,
          insights: ai.insights || (ai.insight ? [...state.ai.insights, ai.insight] : state.ai.insights),
          lastInference: ai.lastInference || new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.GLOBAL_SOURCES_UPDATED: {
      const payload = action.payload || {};
      const summary = payload.summary || payload;
      return {
        ...state,
        global: {
          ...state.global,
          systemStatus: summary.system || state.global.systemStatus,
          status: summary.global_data || state.global.status,
          sources: summary.sources || state.global.sources,
          lastSync: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.GLOBAL_HAZARDS_UPDATED: {
      const hazards = Array.isArray(action.payload) ? action.payload : (action.payload?.hazards || []);
      const activeCount = hazards.length;
      const highRiskCount = hazards.filter((h) => (h.severity || 0) >= 0.7).length;
      const compoundCount = hazards.filter((h) => h.hazard_type === 'COMPOUND').length;
      return {
        ...state,
        global: {
          ...state.global,
          hazards,
          activeCount,
          highRiskCount,
          compoundCount,
          lastSync: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.GLOBAL_EVENTS_UPDATED: {
      const events = Array.isArray(action.payload) ? action.payload : (action.payload?.events || []);
      return {
        ...state,
        global: {
          ...state.global,
          events,
          lastSync: new Date().toISOString(),
        },
      };
    }

    case ACTION_TYPES.GLOBAL_AI_UPDATED: {
      const aiSummary = action.payload || {};
      return {
        ...state,
        global: {
          ...state.global,
          aiSummary,
        },
      };
    }

    case ACTION_TYPES.RESET_STATE: {
      return createInitialState(action.payload);
    }

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Store Factory
// ---------------------------------------------------------------------------

/**
 * Creates an authoritative Climate Eye state store instance.
 *
 * @param {object} [initialOverrides]
 * @returns {ClimateStore}
 */
export function createClimateStore(initialOverrides = {}) {
  let currentState = createInitialState(initialOverrides);
  const listeners = new Set();

  function getState() {
    return currentState;
  }

  function dispatch(action) {
    if (!action || typeof action.type !== 'string') {
      throw new TypeError('Dispatch requires an action object with a string type property');
    }

    const nextState = climateReducer(currentState, action);
    if (nextState !== currentState) {
      currentState = nextState;
      for (const listener of listeners) {
        try {
          listener(currentState, action);
        } catch (err) {
          console.error('[ClimateState] Listener error:', err);
        }
      }
    }
    return action;
  }

  function subscribe(listener) {
    if (typeof listener !== 'function') {
      throw new TypeError('Subscribe requires a listener function');
    }
    listeners.add(listener);
    return function unsubscribe() {
      listeners.delete(listener);
    };
  }

  // Explicit action creators bound to dispatch
  return {
    getState,
    dispatch,
    subscribe,

    // Domain actions
    setRealtimeState: (realtimeState, meta = {}) =>
      dispatch({ type: ACTION_TYPES.REALTIME_STATE_CHANGED, payload: { realtimeState, ...meta } }),

    setSystemStatus: (status) =>
      dispatch({ type: ACTION_TYPES.SYSTEM_STATUS_CHANGED, payload: status }),

    setUiMode: (mode) =>
      dispatch({ type: ACTION_TYPES.UI_MODE_CHANGED, payload: { mode } }),

    selectNode: (nodeId) =>
      dispatch({ type: ACTION_TYPES.NODE_SELECTED, payload: { nodeId } }),

    updateNode: (node) =>
      dispatch({ type: ACTION_TYPES.NODE_UPDATED, payload: node }),

    updateNodes: (nodes) =>
      dispatch({ type: ACTION_TYPES.NODES_UPDATED, payload: nodes }),

    removeNode: (nodeId) =>
      dispatch({ type: ACTION_TYPES.NODE_REMOVED, payload: { nodeId } }),

    updateTelemetry: (telemetry) =>
      dispatch({ type: ACTION_TYPES.TELEMETRY_UPDATED, payload: telemetry }),

    updateHazard: (hazard) =>
      dispatch({ type: ACTION_TYPES.HAZARD_UPDATED, payload: hazard }),

    updateHazards: (hazards) =>
      dispatch({ type: ACTION_TYPES.HAZARDS_UPDATED, payload: hazards }),

    updatePrediction: (prediction) =>
      dispatch({ type: ACTION_TYPES.PREDICTION_UPDATED, payload: prediction }),

    updatePredictions: (predictions) =>
      dispatch({ type: ACTION_TYPES.PREDICTIONS_UPDATED, payload: predictions }),

    updateCompound: (compound) =>
      dispatch({ type: ACTION_TYPES.COMPOUND_UPDATED, payload: compound }),

    updateVulnerability: (vulnerability) =>
      dispatch({ type: ACTION_TYPES.VULNERABILITY_UPDATED, payload: vulnerability }),

    updateEvacuation: (evacuation) =>
      dispatch({ type: ACTION_TYPES.EVACUATION_UPDATED, payload: evacuation }),

    updateResponse: (response) =>
      dispatch({ type: ACTION_TYPES.RESPONSE_UPDATED, payload: response }),

    setSimulationState: (simState) =>
      dispatch({ type: ACTION_TYPES.SIMULATION_STATE_CHANGED, payload: simState }),

    completeSimulation: (results) =>
      dispatch({ type: ACTION_TYPES.SIMULATION_COMPLETED, payload: results }),

    updateAiState: (aiState) =>
      dispatch({ type: ACTION_TYPES.AI_STATE_UPDATED, payload: aiState }),

    setLayerVisibility: (layerId, visible) =>
      dispatch({ type: ACTION_TYPES.LAYER_VISIBILITY_CHANGED, payload: { layerId, visible: Boolean(visible) } }),

    toggleLayer: (layerId) => {
      const current = Boolean(currentState.layers?.[layerId]);
      return dispatch({ type: ACTION_TYPES.LAYER_VISIBILITY_CHANGED, payload: { layerId, visible: !current } });
    },

    isLayerVisible: (layerId) => Boolean(currentState.layers?.[layerId]),

    getLayerVisibility: () => ({ ...(currentState.layers || {}) }),

    resetState: (overrides) =>
      dispatch({ type: ACTION_TYPES.RESET_STATE, payload: overrides }),
  };
}
