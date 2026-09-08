/**
 * Climate Eye S1 — Database Repository Interface & Data Mapping
 *
 * Implements the abstract repository pattern for Climate Eye persistence.
 * Decouples telemetry ingestion and API handlers from the concrete database driver.
 *
 * Conforms to DECISION-001, DECISION-003, and DECISION-005.
 */

'use strict';

/**
 * List of canonical sensor measurement keys allowed in sensor_readings.
 * Optical/camera parameters are strictly excluded per DECISION-001.
 */
export const CANONICAL_SENSOR_FIELDS = Object.freeze([
  'temperature',
  'humidity',
  'pressure',
  'rainfall',
  'soil_moisture',
  'water_level',
  'air_quality',
  'battery',
]);

/**
 * All allowed columns for a persisted sensor reading record.
 */
export const CANONICAL_READING_COLUMNS = Object.freeze([
  'node_id',
  'schema_version',
  'timestamp',
  'latitude',
  'longitude',
  ...CANONICAL_SENSOR_FIELDS,
]);

/**
 * Pure mapping function that transforms a raw or validated telemetry payload
 * into a canonical sensor_readings record suitable for persistence.
 *
 * Guarantees:
 *  1. Missing or undefined measurements become explicit `null`.
 *  2. Real zero values (e.g. rainfall = 0, water_level = 0.0) remain numeric `0`.
 *  3. Never fabricates values.
 *  4. Filters out any optical, camera, or extra non-canonical fields.
 *  5. Normalizes timestamp to ISO 8601 UTC string.
 *  6. Validates latitude and longitude ranges.
 *
 * @param {object} telemetry - Raw or validated telemetry envelope.
 * @returns {object} Canonical sensor reading record.
 * @throws {TypeError|RangeError} If required envelope fields are invalid.
 */
export function mapTelemetryToReadingRecord(telemetry) {
  if (!telemetry || typeof telemetry !== 'object' || Array.isArray(telemetry)) {
    throw new TypeError('Telemetry payload must be a non-null object');
  }

  // 1. Required: node_id (Data-driven, supports NODE-001 .. NODE-006+)
  const nodeId = typeof telemetry.node_id === 'string' ? telemetry.node_id.trim() : '';
  if (!nodeId || !/^[A-Za-z0-9_-]{3,32}$/.test(nodeId)) {
    throw new TypeError(`Invalid node_id: "${telemetry.node_id}". Must be 3-32 alphanumeric characters.`);
  }

  // 2. Required: schema_version
  const schemaVersion = typeof telemetry.schema_version === 'string' ? telemetry.schema_version.trim() : '';
  if (!schemaVersion) {
    throw new TypeError('Missing or invalid schema_version');
  }

  // 3. Required: timestamp (UTC ISO-8601)
  let timestampIso;
  if (telemetry.timestamp instanceof Date) {
    if (isNaN(telemetry.timestamp.getTime())) {
      throw new RangeError('Invalid Date timestamp');
    }
    timestampIso = telemetry.timestamp.toISOString();
  } else if (typeof telemetry.timestamp === 'string') {
    const parsed = new Date(telemetry.timestamp);
    if (isNaN(parsed.getTime())) {
      throw new RangeError(`Invalid timestamp string: "${telemetry.timestamp}"`);
    }
    timestampIso = parsed.toISOString();
  } else {
    throw new TypeError('timestamp must be an ISO string or Date instance');
  }

  // 4. Required: latitude (-90.0 .. +90.0)
  const lat = Number(telemetry.latitude);
  if (!Number.isFinite(lat) || lat < -90.0 || lat > 90.0) {
    throw new RangeError(`Invalid latitude: ${telemetry.latitude}. Must be between -90 and +90.`);
  }

  // 5. Required: longitude (-180.0 .. +180.0)
  const lon = Number(telemetry.longitude);
  if (!Number.isFinite(lon) || lon < -180.0 || lon > 180.0) {
    throw new RangeError(`Invalid longitude: ${telemetry.longitude}. Must be between -180 and +180.`);
  }

  // 6. Optional Canonical Sensor Measurements
  // Rule: Missing/null remains null; numeric zero remains 0; non-canonical fields dropped
  const reading = {
    node_id: nodeId,
    schema_version: schemaVersion,
    timestamp: timestampIso,
    latitude: lat,
    longitude: lon,
  };

  for (const field of CANONICAL_SENSOR_FIELDS) {
    const rawVal = telemetry[field];
    if (rawVal === null || rawVal === undefined) {
      reading[field] = null;
    } else {
      const num = Number(rawVal);
      if (Number.isFinite(num)) {
        reading[field] = num;
      } else {
        reading[field] = null;
      }
    }
  }

  // Object strictly contains only the 13 canonical columns (no optical/camera keys)
  return Object.freeze(reading);
}

/**
 * Helper to build PostgreSQL parameterized INSERT statement and parameter values
 * for a canonical sensor reading, utilizing PostGIS ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography.
 *
 * @param {object} readingRecord - Mapped canonical reading record.
 * @returns {{ sql: string, values: Array<any> }}
 */
export function buildInsertReadingQuery(readingRecord) {
  const sql = `
INSERT INTO sensor_readings (
  node_id,
  schema_version,
  timestamp,
  latitude,
  longitude,
  location,
  temperature,
  humidity,
  pressure,
  rainfall,
  soil_moisture,
  water_level,
  air_quality,
  battery
) VALUES (
  $1, $2, $3, $4, $5,
  ST_SetSRID(ST_MakePoint($5, $4), 4326)::geography,
  $6, $7, $8, $9, $10, $11, $12, $13
) RETURNING *;
`.trim();

  const values = [
    readingRecord.node_id,
    readingRecord.schema_version,
    readingRecord.timestamp,
    readingRecord.latitude,
    readingRecord.longitude,
    readingRecord.temperature,
    readingRecord.humidity,
    readingRecord.pressure,
    readingRecord.rainfall,
    readingRecord.soil_moisture,
    readingRecord.water_level,
    readingRecord.air_quality,
    readingRecord.battery,
  ];

  return { sql, values };
}

/**
 * Helper to build PostgreSQL parameterized UPSERT statement and values for a node.
 *
 * @param {object} nodeRecord - Node attributes.
 * @returns {{ sql: string, values: Array<any> }}
 */
export function buildUpsertNodeQuery(nodeRecord) {
  const sql = `
INSERT INTO nodes (
  node_id,
  name,
  profile,
  latitude,
  longitude,
  altitude_m,
  status,
  metadata,
  location,
  created_at,
  updated_at
) VALUES (
  $1, $2, $3, $4, $5, $6, $7, $8,
  CASE WHEN $4::double precision IS NOT NULL AND $5::double precision IS NOT NULL
    THEN ST_SetSRID(ST_MakePoint($5, $4), 4326)::geography
    ELSE NULL
  END,
  NOW(),
  NOW()
) ON CONFLICT (node_id) DO UPDATE SET
  name = COALESCE(EXCLUDED.name, nodes.name),
  profile = COALESCE(EXCLUDED.profile, nodes.profile),
  latitude = COALESCE(EXCLUDED.latitude, nodes.latitude),
  longitude = COALESCE(EXCLUDED.longitude, nodes.longitude),
  altitude_m = COALESCE(EXCLUDED.altitude_m, nodes.altitude_m),
  status = COALESCE(EXCLUDED.status, nodes.status),
  metadata = nodes.metadata || EXCLUDED.metadata,
  location = CASE WHEN EXCLUDED.latitude IS NOT NULL AND EXCLUDED.longitude IS NOT NULL
    THEN ST_SetSRID(ST_MakePoint(EXCLUDED.longitude, EXCLUDED.latitude), 4326)::geography
    ELSE nodes.location
  END,
  updated_at = NOW()
RETURNING *;
`.trim();

  const values = [
    nodeRecord.node_id,
    nodeRecord.name || null,
    nodeRecord.profile || null,
    nodeRecord.latitude ?? null,
    nodeRecord.longitude ?? null,
    nodeRecord.altitude_m ?? null,
    nodeRecord.status || 'unknown',
    JSON.stringify(nodeRecord.metadata || {}),
  ];

  return { sql, values };
}

/**
 * Abstract base class defining the Climate Eye Repository contract.
 * Concrete implementations (e.g. InMemoryClimateRepository, PostgresClimateRepository)
 * must implement these methods.
 */
export class ClimateRepository {
  /**
   * Initializes the repository (e.g. connects to DB, creates tables if configured).
   * @returns {Promise<void>}
   */
  async init() {
    throw new Error('Not implemented: init()');
  }

  /**
   * Closes database connections or releases resources.
   * @returns {Promise<void>}
   */
  async close() {
    throw new Error('Not implemented: close()');
  }

  // ---------------------------------------------------------------------------
  // Operational Table 1: nodes (Step 8G)
  // ---------------------------------------------------------------------------

  /**
   * Inserts or updates a node definition.
   * Data-driven node identity (NODE-001 through NODE-006+).
   *
   * @param {object} nodeData - Node attributes { node_id, name, profile, latitude, longitude, altitude_m, status, metadata }.
   * @returns {Promise<object>} The persisted node record.
   */
  async upsertNode(nodeData) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: upsertNode()');
  }

  /**
   * Retrieves a node by its node_id.
   *
   * @param {string} nodeId - Node identifier.
   * @returns {Promise<object|null>} The node record or null if not found.
   */
  async getNode(nodeId) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: getNode()');
  }

  /**
   * Lists registered nodes, optionally filtered by status or profile.
   *
   * @param {object} [filter] - Optional filter { status, profile }.
   * @returns {Promise<Array<object>>} List of node records.
   */
  async listNodes(filter = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: listNodes()');
  }

  // ---------------------------------------------------------------------------
  // Operational Table 2: sensor_readings (Step 8G)
  // ---------------------------------------------------------------------------

  /**
   * Inserts a canonical sensor reading.
   * Enforces canonical fields, null preservation, zero preservation, and foreign key semantics.
   *
   * @param {object} readingData - Raw or validated telemetry envelope.
   * @returns {Promise<object>} The persisted sensor reading record (with generated id).
   */
  async insertSensorReading(readingData) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: insertSensorReading()');
  }

  /**
   * Queries sensor readings for a node within a given time range or limit.
   *
   * @param {object} query - Query parameters { nodeId, since, until, limit, order }.
   * @returns {Promise<Array<object>>} List of sensor readings.
   */
  async getSensorReadings(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: getSensorReadings()');
  }

  /**
   * Retrieves the latest sensor reading for a specific node.
   *
   * @param {string} nodeId - Node identifier.
   * @returns {Promise<object|null>} The latest reading or null.
   */
  async getLatestReading(nodeId) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented: getLatestReading()');
  }

  // ---------------------------------------------------------------------------
  // Future Operational Tables (Stubs for Step 8G)
  // ---------------------------------------------------------------------------

  async insertHazardEvent(event) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: insertHazardEvent()');
  }

  async getHazardEvents(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getHazardEvents()');
  }

  async insertPrediction(prediction) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: insertPrediction()');
  }

  async getPredictions(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getPredictions()');
  }

  async insertCompoundEvent(event) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: insertCompoundEvent()');
  }

  async getCompoundEvents(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getCompoundEvents()');
  }

  async upsertVulnerabilityZone(zone) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: upsertVulnerabilityZone()');
  }

  async getVulnerabilityZones(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getVulnerabilityZones()');
  }

  async upsertEvacuationRoute(route) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: upsertEvacuationRoute()');
  }

  async getEvacuationRoutes(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getEvacuationRoutes()');
  }

  async upsertShelter(shelter) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: upsertShelter()');
  }

  async getShelters(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getShelters()');
  }

  async upsertResponsePlan(plan) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: upsertResponsePlan()');
  }

  async getResponsePlans(query = {}) { // eslint-disable-line no-unused-vars
    throw new Error('Not implemented in Step 8G: getResponsePlans()');
  }
}
