/**
 * Climate Eye S1 — In-Memory Database Repository Implementation
 *
 * Implements the ClimateRepository contract using deterministic in-memory data structures.
 * Conforms strictly to the database contract without requiring an external PostgreSQL instance,
 * enabling fast, isolated, deterministic unit and integration testing.
 *
 * Conforms to DECISION-001, DECISION-003, and DECISION-005.
 */

'use strict';

import {
  ClimateRepository,
  mapTelemetryToReadingRecord,
} from './repository.js';

function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  return JSON.parse(JSON.stringify(obj));
}

/**
 * In-Memory persistence implementation of ClimateRepository.
 */
export class InMemoryClimateRepository extends ClimateRepository {
  /**
   * @param {object} [options]
   * @param {boolean} [options.enforceForeignKeys=true] - Whether sensor readings require an existing node in nodes table.
   */
  constructor(options = {}) {
    super();
    this.enforceForeignKeys = options.enforceForeignKeys !== false;
    this._nodes = new Map();
    this._readings = [];
    this._nextReadingId = 1;
    this._isOpen = true;
  }

  async init() {
    this._isOpen = true;
  }

  async close() {
    this._isOpen = false;
  }

  /**
   * Clears all stored data (useful for test isolation).
   */
  clear() {
    this._nodes.clear();
    this._readings = [];
    this._nextReadingId = 1;
  }

  // ---------------------------------------------------------------------------
  // Operational Table 1: nodes
  // ---------------------------------------------------------------------------

  /**
   * Inserts or updates a node definition.
   * Data-driven node identity (NODE-001 through NODE-006+).
   *
   * @param {object} nodeData
   * @returns {Promise<object>}
   */
  async upsertNode(nodeData) {
    if (!this._isOpen) throw new Error('Repository is closed');
    if (!nodeData || typeof nodeData !== 'object') {
      throw new TypeError('Node data must be an object');
    }

    const nodeId = typeof nodeData.node_id === 'string' ? nodeData.node_id.trim() : '';
    if (!nodeId || !/^[A-Za-z0-9_-]{3,32}$/.test(nodeId)) {
      throw new TypeError(`Invalid node_id: "${nodeData.node_id}". Must match ^[A-Za-z0-9_-]{3,32}$`);
    }

    const now = new Date().toISOString();
    const existing = this._nodes.get(nodeId);

    const lat = nodeData.latitude !== undefined && nodeData.latitude !== null
      ? Number(nodeData.latitude)
      : (existing ? existing.latitude : null);
    const lon = nodeData.longitude !== undefined && nodeData.longitude !== null
      ? Number(nodeData.longitude)
      : (existing ? existing.longitude : null);

    let location = null;
    if (lat !== null && lon !== null && Number.isFinite(lat) && Number.isFinite(lon)) {
      // WGS84 Point geography representation
      location = {
        type: 'Point',
        coordinates: [lon, lat],
        srid: 4326,
      };
    } else if (existing) {
      location = existing.location;
    }

    const record = {
      node_id: nodeId,
      name: nodeData.name !== undefined ? (nodeData.name || null) : (existing ? existing.name : null),
      profile: nodeData.profile !== undefined ? (nodeData.profile || null) : (existing ? existing.profile : null),
      latitude: lat,
      longitude: lon,
      altitude_m: nodeData.altitude_m !== undefined && nodeData.altitude_m !== null
        ? Number(nodeData.altitude_m)
        : (existing ? existing.altitude_m : null),
      status: nodeData.status !== undefined ? (nodeData.status || 'unknown') : (existing ? existing.status : 'unknown'),
      metadata: {
        ...(existing ? existing.metadata : {}),
        ...(nodeData.metadata || {}),
      },
      location,
      created_at: existing ? existing.created_at : now,
      updated_at: now,
    };

    this._nodes.set(nodeId, record);
    return deepClone(record);
  }

  /**
   * Retrieves a node by node_id.
   *
   * @param {string} nodeId
   * @returns {Promise<object|null>}
   */
  async getNode(nodeId) {
    if (!this._isOpen) throw new Error('Repository is closed');
    const node = this._nodes.get(nodeId);
    return node ? deepClone(node) : null;
  }

  /**
   * Lists nodes, optionally matching filter criteria.
   *
   * @param {object} [filter]
   * @returns {Promise<Array<object>>}
   */
  async listNodes(filter = {}) {
    if (!this._isOpen) throw new Error('Repository is closed');
    let results = Array.from(this._nodes.values());

    if (filter.status) {
      results = results.filter((n) => n.status === filter.status);
    }
    if (filter.profile) {
      results = results.filter((n) => n.profile === filter.profile);
    }

    return deepClone(results);
  }

  // ---------------------------------------------------------------------------
  // Operational Table 2: sensor_readings
  // ---------------------------------------------------------------------------

  /**
   * Inserts a canonical sensor reading.
   *
   * Enforces:
   *  - Node existence (foreign key constraint) when enforceForeignKeys is true
   *  - Canonical column mapping (camera/optical fields stripped)
   *  - Preserves null for missing measurements
   *  - Preserves numeric 0 for zero values
   *  - Assigns unique integer id and created_at timestamp
   *
   * @param {object} readingData
   * @returns {Promise<object>}
   */
  async insertSensorReading(readingData) {
    if (!this._isOpen) throw new Error('Repository is closed');

    // 1. Map to canonical reading record (enforces rules & discards optical fields)
    const canonical = mapTelemetryToReadingRecord(readingData);

    // 2. Enforce foreign key relationship
    if (this.enforceForeignKeys && !this._nodes.has(canonical.node_id)) {
      const err = new Error(`Foreign key violation: node "${canonical.node_id}" does not exist in nodes table`);
      err.code = '23503'; // Standard PostgreSQL foreign_key_violation code
      throw err;
    }

    // 3. PostGIS WGS84 Point representation
    const location = {
      type: 'Point',
      coordinates: [canonical.longitude, canonical.latitude],
      srid: 4326,
    };

    const record = {
      id: this._nextReadingId++,
      ...canonical,
      location,
      created_at: new Date().toISOString(),
    };

    this._readings.push(record);
    return deepClone(record);
  }

  /**
   * Queries sensor readings for a node with optional time range and limit filters.
   *
   * @param {object} [query]
   * @returns {Promise<Array<object>>}
   */
  async getSensorReadings(query = {}) {
    if (!this._isOpen) throw new Error('Repository is closed');

    let results = this._readings.slice();

    if (query.nodeId) {
      results = results.filter((r) => r.node_id === query.nodeId);
    }

    if (query.since) {
      const sinceTime = new Date(query.since).getTime();
      if (!isNaN(sinceTime)) {
        results = results.filter((r) => new Date(r.timestamp).getTime() >= sinceTime);
      }
    }

    if (query.until) {
      const untilTime = new Date(query.until).getTime();
      if (!isNaN(untilTime)) {
        results = results.filter((r) => new Date(r.timestamp).getTime() <= untilTime);
      }
    }

    // Sort order: default is newest first (descending timestamp)
    const ascending = query.order === 'asc' || query.order === 'ASC';
    results.sort((a, b) => {
      const diff = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      return ascending ? diff : -diff;
    });

    if (typeof query.limit === 'number' && query.limit > 0) {
      results = results.slice(0, query.limit);
    }

    return deepClone(results);
  }

  /**
   * Retrieves the most recent reading for a node.
   *
   * @param {string} nodeId
   * @returns {Promise<object|null>}
   */
  async getLatestReading(nodeId) {
    const readings = await this.getSensorReadings({ nodeId, limit: 1, order: 'desc' });
    return readings.length > 0 ? readings[0] : null;
  }
}
