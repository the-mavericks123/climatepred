/**
 * Climate Eye S1 — PostgreSQL / PostGIS Repository Adapter
 *
 * Implements the ClimateRepository contract for PostgreSQL with PostGIS extensions.
 * Generates and executes parameterized queries conforming to DECISION-001 through DECISION-005.
 *
 * Designed to work either with:
 *  1. An injected database executor/pool (useful for deterministic contract testing)
 *  2. The standard 'pg' Pool when configured and installed
 *
 * Conforms to DECISION-005: encapsulated service boundary isolating PostGIS operations.
 */

'use strict';

import {
  ClimateRepository,
  mapTelemetryToReadingRecord,
  buildInsertReadingQuery,
  buildUpsertNodeQuery,
} from './repository.js';
import { getDbConfig } from './config.js';

export class PostgresClimateRepository extends ClimateRepository {
  /**
   * @param {object} [options]
   * @param {object} [options.pool] - Injected pg.Pool or mock executor with `.query(sql, params)`
   * @param {object} [options.config] - Database configuration overrides
   */
  constructor(options = {}) {
    super();
    this.config = options.config || getDbConfig();
    this._pool = options.pool || null;
    this._ownsPool = !options.pool;
    this._isOpen = false;
  }

  /**
   * Initializes the pool connection.
   */
  async init() {
    if (this._isOpen) return;

    if (!this._pool) {
      // If no pool was injected, dynamically attempt to import 'pg' if installed
      try {
        const pgModule = await import('pg');
        const PoolClass = pgModule.default?.Pool || pgModule.Pool;
        if (!PoolClass) throw new Error('Could not find Pool in pg module');

        const poolConfig = this.config.connectionString
          ? { connectionString: this.config.connectionString }
          : {
              host: this.config.host,
              port: this.config.port,
              database: this.config.database,
              user: this.config.user,
              password: this.config.password,
              ssl: this.config.ssl ? { rejectUnauthorized: false } : false,
              min: this.config.poolMin,
              max: this.config.poolMax,
            };

        this._pool = new PoolClass(poolConfig);
      } catch (err) {
        throw new Error(
          `PostgreSQL driver 'pg' is not installed or failed to load: ${err.message}. ` +
          `Install 'pg' or inject a pool/executor to use PostgresClimateRepository.`
        );
      }
    }

    this._isOpen = true;
  }

  /**
   * Shuts down the connection pool.
   */
  async close() {
    if (!this._isOpen && !this._pool) return;
    this._isOpen = false;

    if (this._ownsPool && this._pool?.end) {
      await this._pool.end();
      this._pool = null;
    }
  }

  /**
   * Executes a parameterized query using the active pool/client.
   *
   * @param {string} text - SQL query text.
   * @param {Array<any>} [params] - Parameter values.
   * @returns {Promise<object>} Query result with rows.
   */
  async query(text, params = []) {
    if (!this._pool) {
      throw new Error('Database pool is not initialized. Call init() or provide a pool.');
    }
    return this._pool.query(text, params);
  }

  // ---------------------------------------------------------------------------
  // Operational Table 1: nodes
  // ---------------------------------------------------------------------------

  async upsertNode(nodeData) {
    if (!nodeData || !nodeData.node_id) {
      throw new TypeError('Node data must include a valid node_id');
    }

    const { sql, values } = buildUpsertNodeQuery(nodeData);
    const result = await this.query(sql, values);
    return result.rows?.[0] || null;
  }

  async getNode(nodeId) {
    if (!nodeId) return null;
    const sql = `
SELECT
  node_id,
  name,
  profile,
  latitude,
  longitude,
  altitude_m,
  status,
  metadata,
  created_at,
  updated_at
FROM nodes
WHERE node_id = $1;
`.trim();

    const result = await this.query(sql, [nodeId]);
    return result.rows?.[0] || null;
  }

  async listNodes(filter = {}) {
    let sql = `
SELECT
  node_id,
  name,
  profile,
  latitude,
  longitude,
  altitude_m,
  status,
  metadata,
  created_at,
  updated_at
FROM nodes
`.trim();

    const clauses = [];
    const values = [];

    if (filter.status) {
      values.push(filter.status);
      clauses.push(`status = $${values.length}`);
    }
    if (filter.profile) {
      values.push(filter.profile);
      clauses.push(`profile = $${values.length}`);
    }

    if (clauses.length > 0) {
      sql += ` WHERE ${clauses.join(' AND ')}`;
    }
    sql += ` ORDER BY node_id ASC;`;

    const result = await this.query(sql, values);
    return result.rows || [];
  }

  // ---------------------------------------------------------------------------
  // Operational Table 2: sensor_readings
  // ---------------------------------------------------------------------------

  async insertSensorReading(readingData) {
    const canonical = mapTelemetryToReadingRecord(readingData);
    const { sql, values } = buildInsertReadingQuery(canonical);
    const result = await this.query(sql, values);
    return result.rows?.[0] || null;
  }

  async getSensorReadings(query = {}) {
    let sql = `
SELECT
  id,
  node_id,
  schema_version,
  timestamp,
  latitude,
  longitude,
  temperature,
  humidity,
  pressure,
  rainfall,
  soil_moisture,
  water_level,
  air_quality,
  battery,
  created_at
FROM sensor_readings
`.trim();

    const clauses = [];
    const values = [];

    if (query.nodeId) {
      values.push(query.nodeId);
      clauses.push(`node_id = $${values.length}`);
    }
    if (query.since) {
      values.push(new Date(query.since).toISOString());
      clauses.push(`timestamp >= $${values.length}`);
    }
    if (query.until) {
      values.push(new Date(query.until).toISOString());
      clauses.push(`timestamp <= $${values.length}`);
    }

    if (clauses.length > 0) {
      sql += ` WHERE ${clauses.join(' AND ')}`;
    }

    const direction = query.order === 'asc' || query.order === 'ASC' ? 'ASC' : 'DESC';
    sql += ` ORDER BY timestamp ${direction}`;

    if (typeof query.limit === 'number' && query.limit > 0) {
      values.push(query.limit);
      sql += ` LIMIT $${values.length}`;
    }
    sql += `;`;

    const result = await this.query(sql, values);
    return result.rows || [];
  }

  async getLatestReading(nodeId) {
    const rows = await this.getSensorReadings({ nodeId, limit: 1, order: 'desc' });
    return rows.length > 0 ? rows[0] : null;
  }
}
