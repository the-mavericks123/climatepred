/**
 * Climate Eye S1 — Database Persistence Boundary Contract Tests
 *
 * Tests the PostgreSQL/PostGIS schema definitions, repository contracts,
 * telemetry mapping, NULL handling, zero preservation, and spatial queries.
 *
 * Runs deterministically without requiring a live PostgreSQL instance.
 */

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  TABLES,
  POSTGIS_EXTENSION_DDL,
  NODES_TABLE_DDL,
  SENSOR_READINGS_TABLE_DDL,
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
  createRepository,
  getDbConfig,
  isDbConfigured,
} from './index.js';

describe('Step 8G: Climate Eye PostgreSQL/PostGIS Persistence Boundary', () => {

  // ===========================================================================
  // 1. Schema & Table Definitions Contract
  // ===========================================================================
  describe('Schema & Table Definitions', () => {
    it('defines all 9 initial Climate Eye tables in the TABLES contract', () => {
      const expectedTables = [
        'nodes',
        'sensor_readings',
        'hazard_events',
        'predictions',
        'compound_events',
        'vulnerability_zones',
        'evacuation_routes',
        'shelters',
        'response_plans',
      ];

      for (const table of expectedTables) {
        assert.ok(
          Object.values(TABLES).includes(table),
          `TABLES must declare table "${table}"`
        );
      }
    });

    it('requires PostGIS extension in spatial DDL', () => {
      assert.match(POSTGIS_EXTENSION_DDL, /CREATE EXTENSION IF NOT EXISTS postgis;/i);
    });

    it('defines nodes table with WGS84 PostGIS geography and data-driven identity', () => {
      assert.match(NODES_TABLE_DDL, /CREATE TABLE IF NOT EXISTS nodes/i);
      assert.match(NODES_TABLE_DDL, /node_id VARCHAR\(32\) PRIMARY KEY/i);
      assert.match(NODES_TABLE_DDL, /location GEOGRAPHY\(Point, 4326\)/i);
      assert.match(NODES_TABLE_DDL, /latitude DOUBLE PRECISION/i);
      assert.match(NODES_TABLE_DDL, /longitude DOUBLE PRECISION/i);
      assert.match(NODES_TABLE_DDL, /idx_nodes_location ON nodes USING GIST \(location\)/i);
    });

    it('defines sensor_readings table preserving all 8 canonical sensor metrics', () => {
      assert.match(SENSOR_READINGS_TABLE_DDL, /CREATE TABLE IF NOT EXISTS sensor_readings/i);
      assert.match(SENSOR_READINGS_TABLE_DDL, /node_id VARCHAR\(32\) NOT NULL REFERENCES nodes\(node_id\)/i);
      assert.match(SENSOR_READINGS_TABLE_DDL, /timestamp TIMESTAMPTZ NOT NULL/i);
      assert.match(SENSOR_READINGS_TABLE_DDL, /location GEOGRAPHY\(Point, 4326\)/i);

      for (const field of CANONICAL_SENSOR_FIELDS) {
        const regex = new RegExp(`${field}\\s+DOUBLE PRECISION`, 'i');
        assert.match(SENSOR_READINGS_TABLE_DDL, regex, `sensor_readings must contain column ${field}`);
      }
    });

    it('strictly excludes optical, camera, or video columns from schema DDL', () => {
      const forbiddenTerms = ['camera', 'optical', 'video', 'snapshot', 'frame'];
      for (const term of forbiddenTerms) {
        assert.ok(
          !SENSOR_READINGS_TABLE_DDL.toLowerCase().includes(term),
          `sensor_readings DDL must NOT contain "${term}"`
        );
        assert.ok(
          !NODES_TABLE_DDL.toLowerCase().includes(term),
          `nodes DDL must NOT contain "${term}"`
        );
      }
    });

    it('getFullSchemaSql() generates DDL for all 9 tables', () => {
      const sql = getFullSchemaSql();
      for (const tableName of Object.values(TABLES)) {
        assert.ok(sql.includes(`CREATE TABLE IF NOT EXISTS ${tableName}`), `Full schema missing ${tableName}`);
      }
    });

    it('getOperationalSchemaSql() generates DDL for nodes and sensor_readings only', () => {
      const sql = getOperationalSchemaSql();
      assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS nodes'));
      assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS sensor_readings'));
      assert.ok(!sql.includes('hazard_events'));
    });

    it('getDropSchemaSql() generates teardown in reverse dependency order', () => {
      const sql = getDropSchemaSql();
      const lines = sql.trim().split('\n');
      assert.ok(lines[lines.length - 1].includes('DROP TABLE IF EXISTS nodes CASCADE;'));
      assert.ok(lines[lines.length - 2].includes('DROP TABLE IF EXISTS sensor_readings CASCADE;'));
    });
  });

  // ===========================================================================
  // 2. Telemetry Persistence Mapping Contract
  // ===========================================================================
  describe('Telemetry Persistence Mapping (mapTelemetryToReadingRecord)', () => {
    it('successfully maps a fully populated canonical telemetry envelope', () => {
      const payload = {
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 26.4,
        humidity: 58.2,
        pressure: 1013.25,
        rainfall: 0.0,
        soil_moisture: 32.5,
        water_level: 12.0,
        air_quality: 15.4,
        battery: 3.92,
      };

      const mapped = mapTelemetryToReadingRecord(payload);

      assert.equal(mapped.node_id, 'NODE-001');
      assert.equal(mapped.schema_version, '1.0.0');
      assert.equal(mapped.timestamp, '2026-09-07T22:45:00.000Z');
      assert.equal(mapped.latitude, 30.2672);
      assert.equal(mapped.longitude, -97.7431);
      assert.equal(mapped.temperature, 26.4);
      assert.equal(mapped.humidity, 58.2);
      assert.equal(mapped.pressure, 1013.25);
      assert.equal(mapped.rainfall, 0.0);
      assert.equal(mapped.soil_moisture, 32.5);
      assert.equal(mapped.water_level, 12.0);
      assert.equal(mapped.air_quality, 15.4);
      assert.equal(mapped.battery, 3.92);
    });

    it('preserves NULL for missing or unmeasured optional sensors', () => {
      const specializedNode = {
        schema_version: '1.0.0',
        node_id: 'NODE-004',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2747,
        longitude: -97.7404,
        temperature: 27.1,
        humidity: 55.0,
        pressure: 1012.8,
        rainfall: null,
        // soil_moisture and water_level completely omitted
        air_quality: 14.8,
        battery: 4.05,
      };

      const mapped = mapTelemetryToReadingRecord(specializedNode);

      assert.equal(mapped.rainfall, null, 'explicit null must remain null');
      assert.equal(mapped.soil_moisture, null, 'omitted measurement must evaluate to null');
      assert.equal(mapped.water_level, null, 'omitted measurement must evaluate to null');
      assert.equal(mapped.air_quality, 14.8);
    });

    it('strictly preserves real numeric ZERO values (0 and 0.0) without converting to null', () => {
      const dryWeatherPayload = {
        schema_version: '1.0.0',
        node_id: 'NODE-002',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2621,
        longitude: -97.7510,
        temperature: 0.0,
        humidity: 0.0,
        pressure: 1000.0,
        rainfall: 0.0,
        soil_moisture: 0,
        water_level: 0.0,
        air_quality: 0.0,
        battery: 3.84,
      };

      const mapped = mapTelemetryToReadingRecord(dryWeatherPayload);

      assert.strictEqual(mapped.temperature, 0);
      assert.strictEqual(mapped.humidity, 0);
      assert.strictEqual(mapped.rainfall, 0);
      assert.strictEqual(mapped.soil_moisture, 0);
      assert.strictEqual(mapped.water_level, 0);
      assert.strictEqual(mapped.air_quality, 0);
    });

    it('strictly strips extra, unapproved, and optical/camera fields from mapped record', () => {
      const payloadWithExtras = {
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 25.0,
        // Prohibited camera / optical keys:
        camera: 'cam_sensor_01',
        optical_frame: 'base64_frame_data_xyz',
        video_stream: 'rtsp://stream.local',
        snapshot_url: 'https://example.com/snap.jpg',
        fps: 30,
        // Arbitrary keys:
        rssi: -65,
        firmware: 'v2.1.0',
      };

      const mapped = mapTelemetryToReadingRecord(payloadWithExtras);

      // Verify no extra keys exist in mapped object
      const keys = Object.keys(mapped);
      for (const col of CANONICAL_READING_COLUMNS) {
        assert.ok(keys.includes(col), `Mapped record must include ${col}`);
      }
      assert.equal(keys.length, CANONICAL_READING_COLUMNS.length, 'Mapped record must only have canonical columns');
      assert.equal(mapped.camera, undefined);
      assert.equal(mapped.optical_frame, undefined);
      assert.equal(mapped.video_stream, undefined);
      assert.equal(mapped.snapshot_url, undefined);
      assert.equal(mapped.rssi, undefined);
      assert.equal(mapped.firmware, undefined);
    });

    it('handles Date objects and normalizes to UTC ISO strings', () => {
      const date = new Date('2026-09-07T18:30:00.000Z');
      const payload = {
        schema_version: '1.0.0',
        node_id: 'NODE-003',
        timestamp: date,
        latitude: 30.0,
        longitude: -97.0,
      };

      const mapped = mapTelemetryToReadingRecord(payload);
      assert.equal(mapped.timestamp, '2026-09-07T18:30:00.000Z');
    });

    it('rejects invalid node_id, schema_version, timestamp, or coordinates', () => {
      // Invalid node_id
      assert.throws(() => {
        mapTelemetryToReadingRecord({ node_id: '', schema_version: '1.0.0', timestamp: '2026-09-07T00:00:00Z', latitude: 0, longitude: 0 });
      }, /Invalid node_id/i);

      // Invalid latitude
      assert.throws(() => {
        mapTelemetryToReadingRecord({ node_id: 'NODE-001', schema_version: '1.0.0', timestamp: '2026-09-07T00:00:00Z', latitude: 95.0, longitude: 0 });
      }, /Invalid latitude/i);

      // Invalid longitude
      assert.throws(() => {
        mapTelemetryToReadingRecord({ node_id: 'NODE-001', schema_version: '1.0.0', timestamp: '2026-09-07T00:00:00Z', latitude: 0, longitude: -190.0 });
      }, /Invalid longitude/i);

      // Invalid timestamp
      assert.throws(() => {
        mapTelemetryToReadingRecord({ node_id: 'NODE-001', schema_version: '1.0.0', timestamp: 'not-a-date', latitude: 0, longitude: 0 });
      }, /Invalid timestamp/i);
    });
  });

  // ===========================================================================
  // 3. PostgreSQL / PostGIS Parameterized SQL Builders
  // ===========================================================================
  describe('PostgreSQL / PostGIS Query Builders', () => {
    it('buildInsertReadingQuery creates valid PostGIS geography parameterized SQL', () => {
      const mapped = mapTelemetryToReadingRecord({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 26.4,
        humidity: null,
        rainfall: 0.0,
      });

      const { sql, values } = buildInsertReadingQuery(mapped);

      assert.match(sql, /INSERT INTO sensor_readings/i);
      assert.match(sql, /ST_SetSRID\(ST_MakePoint\(\$5, \$4\), 4326\)::geography/i);
      assert.equal(values.length, 13);
      assert.equal(values[0], 'NODE-001'); // node_id
      assert.equal(values[1], '1.0.0');    // schema_version
      assert.equal(values[3], 30.2672);    // latitude ($4)
      assert.equal(values[4], -97.7431);   // longitude ($5)
      assert.equal(values[5], 26.4);       // temperature ($6)
      assert.equal(values[6], null);       // humidity ($7)
      assert.equal(values[8], 0.0);        // rainfall ($9) - zero preserved
    });

    it('buildUpsertNodeQuery creates parameterized UPSERT with PostGIS location', () => {
      const node = {
        node_id: 'NODE-006',
        name: 'Hill Country Station',
        profile: 'weather',
        latitude: 30.3,
        longitude: -97.8,
        altitude_m: 220,
        status: 'online',
      };

      const { sql, values } = buildUpsertNodeQuery(node);

      assert.match(sql, /INSERT INTO nodes/i);
      assert.match(sql, /ON CONFLICT \(node_id\) DO UPDATE/i);
      assert.match(sql, /ST_SetSRID\(ST_MakePoint\(\$5, \$4\), 4326\)::geography/i);
      assert.equal(values[0], 'NODE-006');
      assert.equal(values[1], 'Hill Country Station');
      assert.equal(values[2], 'weather');
      assert.equal(values[3], 30.3);
      assert.equal(values[4], -97.8);
    });
  });

  // ===========================================================================
  // 4. InMemoryClimateRepository: Operational Tables & Behavior
  // ===========================================================================
  describe('InMemoryClimateRepository Operational Behavior', () => {
    let repo;

    beforeEach(() => {
      repo = new InMemoryClimateRepository();
    });

    it('supports data-driven node identity for current (NODE-001..005) and future nodes (NODE-006+)', async () => {
      // Current node
      const n1 = await repo.upsertNode({
        node_id: 'NODE-001',
        name: 'Downtown Weather',
        profile: 'weather',
        latitude: 30.2672,
        longitude: -97.7431,
        status: 'online',
      });
      assert.equal(n1.node_id, 'NODE-001');

      // Future node NODE-006
      const n6 = await repo.upsertNode({
        node_id: 'NODE-006',
        name: 'Reservoir Flood Gauge',
        profile: 'flood',
        latitude: 30.3800,
        longitude: -97.7100,
        status: 'online',
      });
      assert.equal(n6.node_id, 'NODE-006');

      // Another future arbitrary node ID
      const nCustom = await repo.upsertNode({
        node_id: 'COMMUNITY-STATION-99',
        name: 'Community Sensor',
        profile: 'urban_heat',
        latitude: 30.40,
        longitude: -97.60,
      });
      assert.equal(nCustom.node_id, 'COMMUNITY-STATION-99');

      const all = await repo.listNodes();
      assert.equal(all.length, 3);
    });

    it('upsertNode updates existing node fields while preserving created_at', async () => {
      const initial = await repo.upsertNode({
        node_id: 'NODE-002',
        name: 'Barton Springs Flood Station',
        profile: 'rain_flood',
        latitude: 30.2621,
        longitude: -97.7510,
        status: 'offline',
      });

      assert.equal(initial.status, 'offline');
      const createdAt = initial.created_at;

      // Update status and coordinates
      const updated = await repo.upsertNode({
        node_id: 'NODE-002',
        status: 'online',
        latitude: 30.2625,
      });

      assert.equal(updated.node_id, 'NODE-002');
      assert.equal(updated.status, 'online');
      assert.equal(updated.latitude, 30.2625);
      assert.equal(updated.longitude, -97.7510, 'unspecified coordinate must be preserved');
      assert.equal(updated.created_at, createdAt, 'created_at must be preserved');
      assert.ok(updated.updated_at >= createdAt, 'updated_at must be updated');
    });

    it('getNode returns deep clone and null for missing node', async () => {
      await repo.upsertNode({ node_id: 'NODE-003', profile: 'agriculture' });

      const node = await repo.getNode('NODE-003');
      assert.ok(node);
      assert.equal(node.node_id, 'NODE-003');

      // Mutation test
      node.profile = 'MUTATED';
      const fresh = await repo.getNode('NODE-003');
      assert.equal(fresh.profile, 'agriculture', 'internal repository state must not be mutable externally');

      // Non-existent
      const missing = await repo.getNode('NODE-NONEXISTENT');
      assert.equal(missing, null);
    });

    it('listNodes supports profile and status filtering', async () => {
      await repo.upsertNode({ node_id: 'NODE-001', profile: 'weather', status: 'online' });
      await repo.upsertNode({ node_id: 'NODE-002', profile: 'flood', status: 'offline' });
      await repo.upsertNode({ node_id: 'NODE-003', profile: 'agriculture', status: 'online' });

      const online = await repo.listNodes({ status: 'online' });
      assert.equal(online.length, 2);

      const flood = await repo.listNodes({ profile: 'flood' });
      assert.equal(flood.length, 1);
      assert.equal(flood[0].node_id, 'NODE-002');
    });

    it('enforces foreign key relationship: reading requires registered node', async () => {
      const telemetry = {
        schema_version: '1.0.0',
        node_id: 'NODE-UNKNOWN',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2,
        longitude: -97.7,
        temperature: 25.0,
      };

      await assert.rejects(async () => {
        await repo.insertSensorReading(telemetry);
      }, (err) => {
        assert.equal(err.code, '23503');
        assert.match(err.message, /foreign key violation/i);
        return true;
      });
    });

    it('successfully persists sensor readings with NULLs, zeros, and WGS84 location', async () => {
      // Register node first
      await repo.upsertNode({ node_id: 'NODE-001', profile: 'weather' });

      const readingData = {
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 26.4,
        rainfall: 0.0, // numeric zero
        soil_moisture: null, // explicit null
        camera: 'cam_ignored', // should be excluded
      };

      const reading = await repo.insertSensorReading(readingData);

      assert.ok(reading.id >= 1);
      assert.equal(reading.node_id, 'NODE-001');
      assert.equal(reading.temperature, 26.4);
      assert.strictEqual(reading.rainfall, 0.0);
      assert.strictEqual(reading.soil_moisture, null);
      assert.strictEqual(reading.water_level, null);
      assert.equal(reading.camera, undefined, 'optical field must not be stored');

      // Spatial representation
      assert.deepEqual(reading.location, {
        type: 'Point',
        coordinates: [-97.7431, 30.2672],
        srid: 4326,
      });
    });

    it('queries sensor readings by time range, limit, and order', async () => {
      await repo.upsertNode({ node_id: 'NODE-001' });

      // Insert three readings
      await repo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:40:00Z',
        latitude: 30.0,
        longitude: -97.0,
        temperature: 24.0,
      });

      await repo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.0,
        longitude: -97.0,
        temperature: 25.0,
      });

      await repo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:50:00Z',
        latitude: 30.0,
        longitude: -97.0,
        temperature: 26.0,
      });

      // Default query: newest first (descending)
      const all = await repo.getSensorReadings({ nodeId: 'NODE-001' });
      assert.equal(all.length, 3);
      assert.equal(all[0].temperature, 26.0);
      assert.equal(all[2].temperature, 24.0);

      // Limit query
      const limited = await repo.getSensorReadings({ nodeId: 'NODE-001', limit: 2 });
      assert.equal(limited.length, 2);
      assert.equal(limited[0].temperature, 26.0);
      assert.equal(limited[1].temperature, 25.0);

      // Time range query
      const windowed = await repo.getSensorReadings({
        nodeId: 'NODE-001',
        since: '2026-09-07T22:42:00Z',
        until: '2026-09-07T22:46:00Z',
      });
      assert.equal(windowed.length, 1);
      assert.equal(windowed[0].temperature, 25.0);

      // Latest reading
      const latest = await repo.getLatestReading('NODE-001');
      assert.ok(latest);
      assert.equal(latest.temperature, 26.0);
    });

    it('future operational tables throw descriptive NotImplemented error in Step 8G', async () => {
      await assert.rejects(async () => {
        await repo.insertHazardEvent({});
      }, /Not implemented in Step 8G: insertHazardEvent/);

      await assert.rejects(async () => {
        await repo.insertPrediction({});
      }, /Not implemented in Step 8G: insertPrediction/);

      await assert.rejects(async () => {
        await repo.upsertVulnerabilityZone({});
      }, /Not implemented in Step 8G: upsertVulnerabilityZone/);

      await assert.rejects(async () => {
        await repo.upsertShelter({});
      }, /Not implemented in Step 8G: upsertShelter/);
    });
  });

  // ===========================================================================
  // 5. PostgresClimateRepository Parameterized Contract & Mock Executor
  // ===========================================================================
  describe('PostgresClimateRepository Parameterized Contract', () => {
    it('executes parameterized SQL via injected mock executor without live DB', async () => {
      const executedQueries = [];

      const mockPool = {
        async query(sql, params) {
          executedQueries.push({ sql, params });
          if (sql.includes('INSERT INTO nodes')) {
            return { rows: [{ node_id: params[0], status: params[6] }] };
          }
          if (sql.includes('INSERT INTO sensor_readings')) {
            return { rows: [{ id: '1', node_id: params[0], temperature: params[5] }] };
          }
          return { rows: [] };
        },
      };

      const pgRepo = new PostgresClimateRepository({ pool: mockPool });
      await pgRepo.init();

      // 1. Upsert node
      const node = await pgRepo.upsertNode({
        node_id: 'NODE-001',
        latitude: 30.2672,
        longitude: -97.7431,
        status: 'online',
      });

      assert.equal(node.node_id, 'NODE-001');
      assert.equal(executedQueries.length, 1);
      assert.match(executedQueries[0].sql, /INSERT INTO nodes/);
      assert.equal(executedQueries[0].params[0], 'NODE-001');

      // 2. Insert reading
      const reading = await pgRepo.insertSensorReading({
        schema_version: '1.0.0',
        node_id: 'NODE-001',
        timestamp: '2026-09-07T22:45:00Z',
        latitude: 30.2672,
        longitude: -97.7431,
        temperature: 28.5,
      });

      assert.equal(reading.id, '1');
      assert.equal(reading.node_id, 'NODE-001');
      assert.equal(executedQueries.length, 2);
      assert.match(executedQueries[1].sql, /INSERT INTO sensor_readings/);
      assert.match(executedQueries[1].sql, /ST_SetSRID\(ST_MakePoint/);

      await pgRepo.close();
    });

    it('fails gracefully when init() is called without pg module or injected pool', async () => {
      const pgRepo = new PostgresClimateRepository({ pool: null });
      await assert.rejects(async () => {
        await pgRepo.init();
      }, /PostgreSQL driver 'pg' is not installed/);
    });
  });

  // ===========================================================================
  // 6. Environment Configuration & Repository Factory
  // ===========================================================================
  describe('Database Configuration & Factory', () => {
    it('getDbConfig() returns safe environment-driven defaults', () => {
      const cfg = getDbConfig();
      assert.equal(cfg.host, process.env.CLIMATE_DB_HOST || 'localhost');
      assert.equal(cfg.port, 5432);
      assert.equal(cfg.database, 'climate_eye');
      assert.strictEqual(cfg.ssl, false);
      assert.equal(cfg.poolMin, 1);
      assert.equal(cfg.poolMax, 10);
    });

    it('isDbConfigured() detects absence of credentials correctly', () => {
      // In default environment without CLIMATE_DB_USER / PASSWORD
      const savedUser = process.env.CLIMATE_DB_USER;
      const savedPass = process.env.CLIMATE_DB_PASSWORD;
      const savedUrl = process.env.DATABASE_URL;

      try {
        delete process.env.CLIMATE_DB_USER;
        delete process.env.CLIMATE_DB_PASSWORD;
        delete process.env.DATABASE_URL;

        assert.strictEqual(isDbConfigured(), false);

        process.env.DATABASE_URL = 'postgres://user:pass@localhost:5432/test';
        assert.strictEqual(isDbConfigured(), true);
      } finally {
        if (savedUser) process.env.CLIMATE_DB_USER = savedUser;
        else delete process.env.CLIMATE_DB_USER;
        if (savedPass) process.env.CLIMATE_DB_PASSWORD = savedPass;
        else delete process.env.CLIMATE_DB_PASSWORD;
        if (savedUrl) process.env.DATABASE_URL = savedUrl;
        else delete process.env.DATABASE_URL;
      }
    });

    it('createRepository returns appropriate repository instance', () => {
      const memRepo = createRepository('memory');
      assert.ok(memRepo instanceof InMemoryClimateRepository);
      assert.ok(memRepo instanceof ClimateRepository);

      const pgRepo = createRepository('postgres');
      assert.ok(pgRepo instanceof PostgresClimateRepository);
      assert.ok(pgRepo instanceof ClimateRepository);

      // Auto mode without configured DB returns InMemory
      const autoRepo = createRepository('auto');
      assert.ok(autoRepo instanceof InMemoryClimateRepository);
    });
  });
});
