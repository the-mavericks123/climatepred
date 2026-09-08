/**
 * Climate Eye S1 — Database Connection Configuration
 *
 * All configuration is environment-driven. No credentials are hard-coded here.
 * Copy .env.example to .env and populate the CLIMATE_DB_* variables to enable
 * the PostgreSQL/PostGIS persistence layer.
 *
 * Environment variables:
 *
 *   CLIMATE_DB_HOST      — PostgreSQL host (default: localhost)
 *   CLIMATE_DB_PORT      — PostgreSQL port (default: 5432)
 *   CLIMATE_DB_NAME      — Database name  (default: climate_eye)
 *   CLIMATE_DB_USER      — Database user  (required for live connection)
 *   CLIMATE_DB_PASSWORD  — Database password (required for live connection)
 *   CLIMATE_DB_SSL       — "true" to enable SSL, any other value disables (default: false)
 *   CLIMATE_DB_POOL_MIN  — Minimum connection pool size (default: 1)
 *   CLIMATE_DB_POOL_MAX  — Maximum connection pool size (default: 10)
 *   DATABASE_URL         — Optional full connection string (overrides individual vars)
 *
 * Security rules:
 *   - NEVER commit real credentials.
 *   - NEVER hard-code defaults for user or password.
 *   - Credentials must come only from environment variables.
 */

'use strict';

/**
 * Returns the resolved PostgreSQL connection configuration object.
 * Pure function — reads from process.env at call time to allow test overrides.
 *
 * @returns {DbConfig}
 *
 * @typedef {Object} DbConfig
 * @property {string|null} connectionString - Full DSN if DATABASE_URL is set, else null.
 * @property {string}      host
 * @property {number}      port
 * @property {string}      database
 * @property {string|null} user      - null when not configured (connection will fail gracefully)
 * @property {string|null} password  - null when not configured
 * @property {boolean}     ssl
 * @property {number}      poolMin
 * @property {number}      poolMax
 */
function getDbConfig() {
  const env = process.env;

  return {
    connectionString: env.DATABASE_URL || null,
    host:     env.CLIMATE_DB_HOST     || 'localhost',
    port:     parseInt(env.CLIMATE_DB_PORT || '5432', 10),
    database: env.CLIMATE_DB_NAME     || 'climate_eye',
    user:     env.CLIMATE_DB_USER     || null,
    password: env.CLIMATE_DB_PASSWORD || null,
    ssl:      env.CLIMATE_DB_SSL === 'true',
    poolMin:  parseInt(env.CLIMATE_DB_POOL_MIN || '1', 10),
    poolMax:  parseInt(env.CLIMATE_DB_POOL_MAX || '10', 10),
  };
}

/**
 * Returns true when the minimum required environment variables for a live
 * PostgreSQL connection are present.
 *
 * @returns {boolean}
 */
function isDbConfigured() {
  const cfg = getDbConfig();
  return !!(cfg.connectionString || (cfg.user && cfg.password));
}

export { getDbConfig, isDbConfigured };
