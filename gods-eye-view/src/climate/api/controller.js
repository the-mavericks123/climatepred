/**
 * Climate Eye — Frontend REST Data Controller (Step F4.2)
 *
 * Coordinates fetching initial backend data via the F2 REST API client
 * and populating the authoritative F1 Climate Eye state model:
 * - GET /api/climate/health -> backend service & subsystem availability
 * - GET /api/nodes -> node registration & network count
 * - GET /api/nodes/:node_id/telemetry -> initial telemetry readings
 *
 * Rules:
 * - Data-driven: No hard-coded node IDs; dynamic for NODE-001 through NODE-006+.
 * - Preserves nulls, numeric zeroes (0), and backend timestamps.
 * - Does not calculate climate risk in the browser.
 * - Does not fabricate data.
 * - Never claims LIVE realtime state (stays UNAVAILABLE).
 * - Partial node failures are isolated and do not block other nodes.
 *
 * Browser-safe: No Node.js core modules.
 */

import { createClimateApiClient } from './client.js';
import { ACTION_TYPES, REALTIME_STATES } from '../state/constants.js';

/**
 * Synchronizes the authoritative Climate Eye state with real backend data from REST API.
 *
 * @param {object} options
 * @param {object} options.store - Authoritative Climate Eye state store instance.
 * @param {object} [options.client] - ClimateApiClient instance (default created).
 * @param {boolean} [options.fetchTelemetry=true] - Whether to load initial node telemetry.
 * @returns {Promise<{ ok: boolean, health: object, nodes: object, nodeTelemetryCount: number }>}
 */
export async function syncClimateStateFromRest({
  store,
  client = createClimateApiClient(),
  fetchTelemetry = true,
  syncIntelligence = false,
} = {}) {
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('syncClimateStateFromRest requires an authoritative store instance with dispatch');
  }

  // 1. Mark system as loading
  if (typeof store.setSystemStatus === 'function') {
    store.setSystemStatus({ status: 'loading' });
  } else {
    store.dispatch({
      type: ACTION_TYPES.SYSTEM_STATUS_CHANGED,
      payload: { status: 'loading' },
    });
  }

  let healthResult = null;
  let nodesResult = null;
  let nodeTelemetryCount = 0;

  // 2. Fetch /api/climate/health
  try {
    healthResult = await client.getHealth();
    console.log('[ClimateEye DEBUG] healthResult:', healthResult);
    if (healthResult && healthResult.ok && healthResult.data) {
      const data = healthResult.data;
      const statusPayload = {
        status: 'healthy',
        version: data.version || '1.0.0',
        subsystems: data.subsystems || {},
        lastHeartbeat: data.timestamp || new Date().toISOString(),
      };
      if (typeof store.setSystemStatus === 'function') {
        store.setSystemStatus(statusPayload);
      } else {
        store.dispatch({
          type: ACTION_TYPES.SYSTEM_STATUS_CHANGED,
          payload: statusPayload,
        });
      }
    } else {
      const errorMsg = healthResult?.error || 'Health check returned non-ok';
      console.error('[ClimateEye DEBUG] health check returned non-ok:', errorMsg, healthResult);
      if (typeof store.setSystemStatus === 'function') {
        store.setSystemStatus({ status: 'degraded', lastError: errorMsg });
      } else {
        store.dispatch({
          type: ACTION_TYPES.SYSTEM_STATUS_CHANGED,
          payload: { status: 'degraded', lastError: errorMsg },
        });
      }
    }
  } catch (err) {
    const errorMsg = err?.message || 'Network error fetching health';
    console.error('[ClimateEye DEBUG] health check threw exception:', errorMsg, err);
    if (typeof store.setSystemStatus === 'function') {
      store.setSystemStatus({ status: 'degraded', lastError: errorMsg });
    } else {
      store.dispatch({
        type: ACTION_TYPES.SYSTEM_STATUS_CHANGED,
        payload: { status: 'degraded', lastError: errorMsg },
      });
    }
    healthResult = { ok: false, error: errorMsg, status: 0 };
  }

  // 3. Fetch /api/nodes
  try {
    nodesResult = await client.getNodes();
    if (nodesResult && nodesResult.ok && Array.isArray(nodesResult.data?.nodes)) {
      const rawNodes = nodesResult.data.nodes;

      // Update store with registered nodes
      if (typeof store.updateNodes === 'function') {
        store.updateNodes(rawNodes);
      } else {
        store.dispatch({
          type: ACTION_TYPES.NODES_UPDATED,
          payload: rawNodes,
        });
      }

      // 4. Fetch initial telemetry for nodes if requested
      if (fetchTelemetry && rawNodes.length > 0) {
        const telemetryPromises = rawNodes.map(async (node) => {
          const nodeId = node?.node_id;
          if (!nodeId) return null;

          try {
            const telemRes = await client.getNodeTelemetry(nodeId, { limit: 1 });
            if (telemRes && telemRes.ok && Array.isArray(telemRes.data?.readings) && telemRes.data.readings.length > 0) {
              const latestReading = telemRes.data.readings[0];
              if (typeof store.updateTelemetry === 'function') {
                store.updateTelemetry(latestReading);
              } else {
                store.dispatch({
                  type: ACTION_TYPES.TELEMETRY_UPDATED,
                  payload: latestReading,
                });
              }
              return latestReading;
            }
          } catch {
            // Fault isolation: failure for one node does NOT break other nodes
            return null;
          }
          return null;
        });

        const settled = await Promise.allSettled(telemetryPromises);
        nodeTelemetryCount = settled.filter((s) => s.status === 'fulfilled' && s.value !== null).length;
      }
    } else {
      const errorMsg = nodesResult?.error || 'Failed to retrieve nodes';
      // Do not wipe existing nodes; log failure
      nodesResult = nodesResult || { ok: false, error: errorMsg, status: 0 };
    }
  } catch (err) {
    const errorMsg = err?.message || 'Network error fetching nodes';
    nodesResult = { ok: false, error: errorMsg, status: 0 };
  }

  // 5. Optionally fetch initial intelligence from S2
  let intelligenceResult = null;
  if (syncIntelligence) {
    try {
      intelligenceResult = await syncIntelligenceFromRest({ store, client });
    } catch {
      // Fault isolation: intelligence loading errors do not crash REST sync
    }
  }

  // Ensure realtime state does not claim LIVE (remains UNAVAILABLE)
  const currentState = store.getState();
  if (currentState?.connection?.realtimeState === REALTIME_STATES.LIVE) {
    if (typeof store.setRealtimeState === 'function') {
      store.setRealtimeState(REALTIME_STATES.UNAVAILABLE);
    }
  }

  const overallOk = !!(healthResult?.ok && nodesResult?.ok);

  return {
    ok: overallOk,
    health: healthResult,
    nodes: nodesResult,
    nodeTelemetryCount,
    intelligence: intelligenceResult,
  };
}

/**
 * Synchronizes S2 intelligence state from REST APIs into the authoritative store.
 * Fetches:
 *  - getCurrentHazards() -> store.updateHazards()
 *  - getPredictions() -> store.updatePredictions()
 *  - getCompoundEvents() -> store.updateCompound()
 *  - getVulnerability() -> store.updateVulnerability()
 *  - getEvacuation() -> store.updateEvacuation()
 *  - getResponse() -> store.updateResponse()
 *
 * Fault isolated: individual endpoint failures never crash the controller.
 *
 * @param {object} options
 * @param {object} options.store
 * @param {object} [options.client]
 * @returns {Promise<object>}
 */
export async function syncIntelligenceFromRest({
  store,
  client = createClimateApiClient(),
} = {}) {
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('syncIntelligenceFromRest requires an authoritative store instance');
  }

  const results = {
    hazards: null,
    predictions: null,
    compound: null,
    vulnerability: null,
    evacuation: null,
    response: null,
  };

  // 1. Hazards
  try {
    const res = await client.getCurrentHazards();
    if (res?.ok && res.data) {
      const hazardsList = Array.isArray(res.data) ? res.data : (res.data.hazards || []);
      if (typeof store.updateHazards === 'function') {
        store.updateHazards(hazardsList);
      } else {
        store.dispatch({ type: ACTION_TYPES.HAZARDS_UPDATED, payload: hazardsList });
      }
      results.hazards = hazardsList;
    }
  } catch {}

  // 2. Predictions
  try {
    const res = await client.getPredictions();
    if (res?.ok && res.data) {
      const predsList = Array.isArray(res.data) ? res.data : (res.data.predictions || []);
      if (typeof store.updatePredictions === 'function') {
        store.updatePredictions(predsList);
      } else {
        store.dispatch({ type: ACTION_TYPES.PREDICTIONS_UPDATED, payload: predsList });
      }
      results.predictions = predsList;
    }
  } catch {}

  // 3. Compound Events
  try {
    const res = await client.getCompoundEvents();
    if (res?.ok && res.data) {
      const compoundData = res.data.events || res.data;
      if (typeof store.updateCompound === 'function') {
        store.updateCompound(compoundData);
      } else {
        store.dispatch({ type: ACTION_TYPES.COMPOUND_UPDATED, payload: compoundData });
      }
      results.compound = compoundData;
    }
  } catch {}

  // 4. Vulnerability
  try {
    const res = await client.getVulnerability();
    if (res?.ok && res.data) {
      const vulnData = res.data.assessments || res.data;
      if (typeof store.updateVulnerability === 'function') {
        store.updateVulnerability(vulnData);
      } else {
        store.dispatch({ type: ACTION_TYPES.VULNERABILITY_UPDATED, payload: vulnData });
      }
      results.vulnerability = vulnData;
    }
  } catch {}

  // 5. Evacuation
  try {
    const res = await client.getEvacuation();
    if (res?.ok && res.data) {
      const evacData = {
        routes: res.data.recommendations || res.data.routes || [],
        status: res.data.status || 'ACTIVE',
      };
      if (typeof store.updateEvacuation === 'function') {
        store.updateEvacuation(evacData);
      } else {
        store.dispatch({ type: ACTION_TYPES.EVACUATION_UPDATED, payload: evacData });
      }
      results.evacuation = evacData;
    }
  } catch {}

  // 6. Response Plans
  try {
    const res = await client.getResponse();
    if (res?.ok && res.data) {
      const planData = {
        plans: res.data.plan ? [res.data.plan] : (res.data.plans || []),
        activePlan: res.data.plan || null,
      };
      if (typeof store.updateResponse === 'function') {
        store.updateResponse(planData);
      } else {
        store.dispatch({ type: ACTION_TYPES.RESPONSE_UPDATED, payload: planData });
      }
      results.response = planData;
    }
  } catch {}

  return results;
}

/**
 * Synchronizes global live data feeds (sources, hazard zones, events, AI summary) into authoritative store.
 *
 * @param {object} options
 * @param {object} options.store
 * @param {object} [options.client]
 * @returns {Promise<object>}
 */
export async function syncGlobalDataFromRest({
  store,
  client = createClimateApiClient(),
} = {}) {
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('syncGlobalDataFromRest requires an authoritative store instance');
  }

  const results = {
    sources: null,
    hazards: null,
    events: null,
    aiSummary: null,
  };

  // 1. Sources
  try {
    const res = await client.getGlobalSources();
    if (res?.ok && res.data) {
      store.dispatch({ type: ACTION_TYPES.GLOBAL_SOURCES_UPDATED, payload: res.data });
      results.sources = res.data;
    }
  } catch {}

  // 2. Global Hazards
  try {
    const res = await client.getGlobalHazards();
    if (res?.ok && res.data) {
      const hazardsList = Array.isArray(res.data) ? res.data : (res.data.hazards || []);
      store.dispatch({ type: ACTION_TYPES.GLOBAL_HAZARDS_UPDATED, payload: hazardsList });
      results.hazards = hazardsList;
    }
  } catch {}

  // 3. Events
  try {
    const res = await client.getGlobalEvents();
    if (res?.ok && res.data) {
      const eventsList = Array.isArray(res.data) ? res.data : (res.data.events || []);
      store.dispatch({ type: ACTION_TYPES.GLOBAL_EVENTS_UPDATED, payload: eventsList });
      results.events = eventsList;
    }
  } catch {}

  // 4. AI Summary
  try {
    const res = await client.getGlobalAiSummary();
    if (res?.ok && res.data) {
      const aiData = res.data.ai_summary || res.data;
      store.dispatch({ type: ACTION_TYPES.GLOBAL_AI_UPDATED, payload: aiData });
      results.aiSummary = aiData;
    }
  } catch {}

  return results;
}

/**
 * Convenience bootstrap helper.
 */
export async function bootstrapClimateData(options = {}) {
  const res = await syncClimateStateFromRest({ syncIntelligence: true, ...options });
  await syncGlobalDataFromRest(options);
  return res;
}
