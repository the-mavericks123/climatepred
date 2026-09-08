/**
 * Climate Eye S1 — PostgreSQL/PostGIS Database Schema
 *
 * Defines the canonical DDL and table definitions for Climate Eye S1 persistence.
 *
 * Schema rules & constraints (conforming to DECISIONS 001-005):
 *  1. PostGIS is required for spatial storage/query semantics (GEOGRAPHY Point, 4326).
 *  2. Data-driven node identities: any valid node ID string (e.g. NODE-001, NODE-006+) is supported.
 *  3. Canonical telemetry semantics:
 *     - UTC timestamp (TIMESTAMPTZ)
 *     - WGS84 coordinates (latitude, longitude, GEOGRAPHY)
 *     - 8 canonical sensor metrics (temperature, humidity, pressure, rainfall,
 *       soil_moisture, water_level, air_quality, battery)
 *  4. Missing measurements evaluate to NULL.
 *  5. Real zero values remain numeric zero (0.0).
 *  6. Optical / camera columns are strictly EXCLUDED (DECISION-001).
 *  7. All 9 initial Climate Eye tables are declared in this schema:
 *     - Operational in Step 8G: nodes, sensor_readings
 *     - Future operational: hazard_events, predictions, compound_events,
 *       vulnerability_zones, evacuation_routes, shelters, response_plans
 */

'use strict';

/**
 * Approved Climate Eye database table names.
 */
export const TABLES = Object.freeze({
  NODES: 'nodes',
  SENSOR_READINGS: 'sensor_readings',
  HAZARD_EVENTS: 'hazard_events',
  PREDICTIONS: 'predictions',
  COMPOUND_EVENTS: 'compound_events',
  VULNERABILITY_ZONES: 'vulnerability_zones',
  EVACUATION_ROUTES: 'evacuation_routes',
  SHELTERS: 'shelters',
  RESPONSE_PLANS: 'response_plans',
});

/**
 * PostgreSQL / PostGIS DDL for creating the spatial extension.
 */
export const POSTGIS_EXTENSION_DDL = `
CREATE EXTENSION IF NOT EXISTS postgis;
`.trim();

/**
 * DDL for the 'nodes' table.
 * Supports data-driven node identities (NODE-001 through NODE-006+) without hardcoding.
 */
export const NODES_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS nodes (
  node_id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(128),
  profile VARCHAR(64),
  location GEOGRAPHY(Point, 4326),
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  altitude_m DOUBLE PRECISION,
  status VARCHAR(32) DEFAULT 'unknown',
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nodes_location ON nodes USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes (status);
`.trim();

/**
 * DDL for the 'sensor_readings' table.
 * Preserves canonical telemetry semantics with WGS84 PostGIS geometry and nullable sensor metrics.
 * Note: Camera/optical columns are strictly excluded.
 */
export const SENSOR_READINGS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS sensor_readings (
  id BIGSERIAL PRIMARY KEY,
  node_id VARCHAR(32) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
  schema_version VARCHAR(16) NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  location GEOGRAPHY(Point, 4326),
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,
  pressure DOUBLE PRECISION,
  rainfall DOUBLE PRECISION,
  soil_moisture DOUBLE PRECISION,
  water_level DOUBLE PRECISION,
  air_quality DOUBLE PRECISION,
  battery DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_node_ts ON sensor_readings (node_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_location ON sensor_readings USING GIST (location);
`.trim();

/**
 * DDL specifications for future operational tables (stubs for Step 8G).
 */
export const HAZARD_EVENTS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS hazard_events (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(64) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  location GEOGRAPHY(Point, 4326),
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  affected_radius_m DOUBLE PRECISION,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  details JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_hazard_events_location ON hazard_events USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_hazard_events_status ON hazard_events (status);
`.trim();

export const PREDICTIONS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS predictions (
  id BIGSERIAL PRIMARY KEY,
  model_name VARCHAR(64) NOT NULL,
  target_hazard VARCHAR(64) NOT NULL,
  prediction_timestamp TIMESTAMPTZ NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ NOT NULL,
  location GEOGRAPHY(Point, 4326),
  confidence DOUBLE PRECISION,
  payload JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_validity ON predictions (valid_from, valid_to);
`.trim();

export const COMPOUND_EVENTS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS compound_events (
  id BIGSERIAL PRIMARY KEY,
  title VARCHAR(128) NOT NULL,
  primary_event_id BIGINT REFERENCES hazard_events(id),
  contributing_events JSONB DEFAULT '[]'::jsonb,
  risk_multiplier DOUBLE PRECISION DEFAULT 1.0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
`.trim();

export const VULNERABILITY_ZONES_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS vulnerability_zones (
  id SERIAL PRIMARY KEY,
  zone_name VARCHAR(128) NOT NULL,
  boundary GEOGRAPHY(Polygon, 4326) NOT NULL,
  vulnerability_level VARCHAR(32) NOT NULL,
  population_estimate INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vulnerability_zones_boundary ON vulnerability_zones USING GIST (boundary);
`.trim();

export const EVACUATION_ROUTES_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS evacuation_routes (
  id SERIAL PRIMARY KEY,
  route_name VARCHAR(128) NOT NULL,
  path GEOGRAPHY(LineString, 4326) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  capacity INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evacuation_routes_path ON evacuation_routes USING GIST (path);
`.trim();

export const SHELTERS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS shelters (
  id SERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  location GEOGRAPHY(Point, 4326) NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  capacity INTEGER NOT NULL DEFAULT 0,
  current_occupancy INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'available',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shelters_location ON shelters USING GIST (location);
`.trim();

export const RESPONSE_PLANS_TABLE_DDL = `
CREATE TABLE IF NOT EXISTS response_plans (
  id SERIAL PRIMARY KEY,
  plan_name VARCHAR(128) NOT NULL,
  hazard_type VARCHAR(64) NOT NULL,
  trigger_conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
  actions JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
`.trim();

/**
 * Returns the complete PostgreSQL / PostGIS DDL script for initializing all 9 tables.
 *
 * @returns {string} SQL DDL statements separated by semicolons.
 */
export function getFullSchemaSql() {
  return [
    POSTGIS_EXTENSION_DDL,
    NODES_TABLE_DDL,
    SENSOR_READINGS_TABLE_DDL,
    HAZARD_EVENTS_TABLE_DDL,
    PREDICTIONS_TABLE_DDL,
    COMPOUND_EVENTS_TABLE_DDL,
    VULNERABILITY_ZONES_TABLE_DDL,
    EVACUATION_ROUTES_TABLE_DDL,
    SHELTERS_TABLE_DDL,
    RESPONSE_PLANS_TABLE_DDL,
  ].join('\n\n');
}

/**
 * Returns the operational DDL script for Step 8G (nodes and sensor_readings only).
 *
 * @returns {string} SQL DDL statements.
 */
export function getOperationalSchemaSql() {
  return [
    POSTGIS_EXTENSION_DDL,
    NODES_TABLE_DDL,
    SENSOR_READINGS_TABLE_DDL,
  ].join('\n\n');
}

/**
 * Returns DROP TABLE statements for teardown in reverse dependency order.
 *
 * @returns {string} SQL DROP statements.
 */
export function getDropSchemaSql() {
  return [
    `DROP TABLE IF EXISTS response_plans CASCADE;`,
    `DROP TABLE IF EXISTS shelters CASCADE;`,
    `DROP TABLE IF EXISTS evacuation_routes CASCADE;`,
    `DROP TABLE IF EXISTS vulnerability_zones CASCADE;`,
    `DROP TABLE IF EXISTS compound_events CASCADE;`,
    `DROP TABLE IF EXISTS predictions CASCADE;`,
    `DROP TABLE IF EXISTS hazard_events CASCADE;`,
    `DROP TABLE IF EXISTS sensor_readings CASCADE;`,
    `DROP TABLE IF EXISTS nodes CASCADE;`,
  ].join('\n');
}
