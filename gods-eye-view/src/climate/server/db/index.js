/**
 * Climate Eye S1 — Database Persistence Subsystem Entry Point
 *
 * Exposes repository abstractions, schema definitions, data mapping utilities,
 * and repository factory functions for Climate Eye data access.
 */

'use strict';

import { getDbConfig, isDbConfigured } from './config.js';
import {
  TABLES,
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
  getFullSchemaSql,
  getOperationalSchemaSql,
  getDropSchemaSql,
} from './schema.js';
import {
  CANONICAL_SENSOR_FIELDS,
  CANONICAL_READING_COLUMNS,
  mapTelemetryToReadingRecord,
  buildInsertReadingQuery,
  buildUpsertNodeQuery,
  ClimateRepository,
} from './repository.js';
import { InMemoryClimateRepository } from './inMemoryRepository.js';
import { PostgresClimateRepository } from './postgresRepository.js';

/**
 * Factory to create a repository instance based on type or configuration.
 *
 * @param {'memory'|'postgres'|'auto'} [type='auto']
 * @param {object} [options]
 * @returns {ClimateRepository}
 */
export function createRepository(type = 'auto', options = {}) {
  if (type === 'memory') {
    return new InMemoryClimateRepository(options);
  }

  if (type === 'postgres') {
    return new PostgresClimateRepository(options);
  }

  // 'auto' mode: if environment has DB credentials configured, use postgres, else fallback to in-memory
  if (isDbConfigured()) {
    return new PostgresClimateRepository(options);
  }

  return new InMemoryClimateRepository(options);
}

export {
  getDbConfig,
  isDbConfigured,
  TABLES,
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
  getFullSchemaSql,
  getOperationalSchemaSql,
  getDropSchemaSql,
  CANONICAL_SENSOR_FIELDS,
  CANONICAL_READING_COLUMNS,
  mapTelemetryToReadingRecord,
  buildInsertReadingQuery,
  buildUpsertNodeQuery,
  ClimateRepository,
  InMemoryClimateRepository,
  PostgresClimateRepository,
};
