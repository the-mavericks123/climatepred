/**
 * Climate Eye S1 — Telemetry Validator Unit Tests
 *
 * Test coverage for docs/contracts/DECISIONS.md § DECISION-003 (v1.0.0).
 *
 * Test categories:
 *   A. Valid payloads (fully populated, optional fields null, zero values)
 *   B. Invalid payload shape (null, array, string, number)
 *   C. schema_version validation
 *   D. node_id validation
 *   E. timestamp validation (format, UTC-Z, future drift)
 *   F. Coordinate validation (lat/lon WGS84 bounds)
 *   G. Optional sensor field validation (type, physical bounds)
 *   H. Normalization (unknown fields stripped, absent→null, zero preserved)
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { validateTelemetry, SENSOR_BOUNDS } from './validator.js';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** A fully-valid canonical payload (all optional fields populated). */
const VALID_FULL = {
  schema_version: '1.0.0',
  node_id:        'NODE-001',
  timestamp:      '2026-09-07T22:45:00Z',
  latitude:       30.2672,
  longitude:     -97.7431,
  temperature:    26.4,
  humidity:       58.2,
  pressure:       1013.25,
  rainfall:       0.0,
  soil_moisture:  45.0,
  water_level:    0.0,
  air_quality:    14.8,
  battery:        3.92,
};

/** Returns a deep copy of VALID_FULL, optionally merging overrides. */
function valid(overrides = {}) {
  return Object.assign({}, VALID_FULL, overrides);
}

// ---------------------------------------------------------------------------
// A. Valid payloads
// ---------------------------------------------------------------------------

describe('A. Valid payloads', () => {
  it('A1 — accepts a fully populated canonical payload', () => {
    const result = validateTelemetry(valid());
    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
    assert.ok(result.payload !== null);
  });

  it('A2 — accepts a payload where all optional sensor fields are null', () => {
    const result = validateTelemetry(valid({
      temperature:   null,
      humidity:      null,
      pressure:      null,
      rainfall:      null,
      soil_moisture: null,
      water_level:   null,
      air_quality:   null,
      battery:       null,
    }));
    assert.equal(result.valid, true);
    const p = result.payload;
    assert.equal(p.temperature,   null);
    assert.equal(p.humidity,      null);
    assert.equal(p.pressure,      null);
    assert.equal(p.rainfall,      null);
    assert.equal(p.soil_moisture, null);
    assert.equal(p.water_level,   null);
    assert.equal(p.air_quality,   null);
    assert.equal(p.battery,       null);
  });

  it('A3 — accepts a payload where optional sensor fields are absent (missing → null)', () => {
    const { temperature, humidity, pressure, rainfall, soil_moisture,
            water_level, air_quality, battery, ...minimal } = valid();
    const result = validateTelemetry(minimal);
    assert.equal(result.valid, true);
    const p = result.payload;
    assert.equal(p.temperature,   null);
    assert.equal(p.humidity,      null);
    assert.equal(p.pressure,      null);
    assert.equal(p.rainfall,      null);
    assert.equal(p.soil_moisture, null);
    assert.equal(p.water_level,   null);
    assert.equal(p.air_quality,   null);
    assert.equal(p.battery,       null);
  });

  it('A4 — preserves numeric zero as a valid real measurement (not coerced to null)', () => {
    const result = validateTelemetry(valid({
      temperature:   0,
      humidity:      0,
      pressure:      300.0,   // lower bound
      rainfall:      0,
      soil_moisture: 0,
      water_level:   0,
      air_quality:   0,
      battery:       0,
    }));
    assert.equal(result.valid, true);
    const p = result.payload;
    assert.equal(p.temperature,   0);
    assert.equal(p.humidity,      0);
    assert.equal(p.pressure,      300.0);
    assert.equal(p.rainfall,      0);
    assert.equal(p.soil_moisture, 0);
    assert.equal(p.water_level,   0);
    assert.equal(p.air_quality,   0);
    assert.equal(p.battery,       0);
  });

  it('A5 — accepts NODE-004 air-quality specialist payload (non-relevant fields null)', () => {
    const result = validateTelemetry(valid({
      node_id:       'NODE-004',
      rainfall:      null,
      soil_moisture: null,
      water_level:   null,
      air_quality:   14.8,
    }));
    assert.equal(result.valid, true);
    assert.equal(result.payload.node_id, 'NODE-004');
  });

  it('A6 — schema_version minor/patch variants accepted (1.1.0, 1.2.99)', () => {
    assert.equal(validateTelemetry(valid({ schema_version: '1.1.0' })).valid, true);
    assert.equal(validateTelemetry(valid({ schema_version: '1.2.99' })).valid, true);
  });

  it('A7 — timestamp with sub-second precision accepted (2026-09-07T22:45:00.123Z)', () => {
    const result = validateTelemetry(valid({ timestamp: '2026-09-07T22:45:00.123Z' }));
    assert.equal(result.valid, true);
  });
});

// ---------------------------------------------------------------------------
// B. Invalid payload shape
// ---------------------------------------------------------------------------

describe('B. Invalid payload shape', () => {
  it('B1 — rejects null', () => {
    const r = validateTelemetry(null);
    assert.equal(r.valid, false);
    assert.equal(r.payload, null);
  });

  it('B2 — rejects an array', () => {
    assert.equal(validateTelemetry([]).valid, false);
  });

  it('B3 — rejects a string', () => {
    assert.equal(validateTelemetry('hello').valid, false);
  });

  it('B4 — rejects a number', () => {
    assert.equal(validateTelemetry(42).valid, false);
  });

  it('B5 — rejects undefined', () => {
    assert.equal(validateTelemetry(undefined).valid, false);
  });
});

// ---------------------------------------------------------------------------
// C. schema_version validation
// ---------------------------------------------------------------------------

describe('C. schema_version', () => {
  it('C1 — rejects when missing', () => {
    const r = validateTelemetry(valid({ schema_version: undefined }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('schema_version')));
  });

  it('C2 — rejects when not a string (number)', () => {
    assert.equal(validateTelemetry(valid({ schema_version: 1 })).valid, false);
  });

  it('C3 — rejects major version 2 (2.0.0)', () => {
    const r = validateTelemetry(valid({ schema_version: '2.0.0' }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('schema_version')));
  });

  it('C4 — rejects major version 0 (0.9.0)', () => {
    assert.equal(validateTelemetry(valid({ schema_version: '0.9.0' })).valid, false);
  });

  it('C5 — rejects non-semver string ("latest")', () => {
    assert.equal(validateTelemetry(valid({ schema_version: 'latest' })).valid, false);
  });

  it('C6 — rejects version without patch ("1.0")', () => {
    assert.equal(validateTelemetry(valid({ schema_version: '1.0' })).valid, false);
  });
});

// ---------------------------------------------------------------------------
// D. node_id validation
// ---------------------------------------------------------------------------

describe('D. node_id', () => {
  it('D1 — rejects when missing', () => {
    const r = validateTelemetry(valid({ node_id: undefined }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('node_id')));
  });

  it('D2 — rejects when not a string (number)', () => {
    assert.equal(validateTelemetry(valid({ node_id: 1 })).valid, false);
  });

  it('D3 — rejects too-short id (< 3 chars)', () => {
    assert.equal(validateTelemetry(valid({ node_id: 'AB' })).valid, false);
  });

  it('D4 — rejects too-long id (> 32 chars)', () => {
    assert.equal(validateTelemetry(valid({ node_id: 'A'.repeat(33) })).valid, false);
  });

  it('D5 — rejects id with invalid chars (space)', () => {
    assert.equal(validateTelemetry(valid({ node_id: 'NODE 001' })).valid, false);
  });

  it('D6 — accepts id with hyphen and underscore (NODE-001, node_alpha)', () => {
    assert.equal(validateTelemetry(valid({ node_id: 'NODE-001' })).valid, true);
    assert.equal(validateTelemetry(valid({ node_id: 'node_alpha' })).valid, true);
  });

  it('D7 — accepts exactly 3-char and 32-char ids', () => {
    assert.equal(validateTelemetry(valid({ node_id: 'ABC' })).valid, true);
    assert.equal(validateTelemetry(valid({ node_id: 'A'.repeat(32) })).valid, true);
  });
});

// ---------------------------------------------------------------------------
// E. timestamp validation
// ---------------------------------------------------------------------------

describe('E. timestamp', () => {
  it('E1 — rejects when missing', () => {
    const r = validateTelemetry(valid({ timestamp: undefined }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('timestamp')));
  });

  it('E2 — rejects when not a string (number)', () => {
    assert.equal(validateTelemetry(valid({ timestamp: 1725753900 })).valid, false);
  });

  it('E3 — rejects timestamp without Z suffix (offset +00:00)', () => {
    assert.equal(validateTelemetry(valid({ timestamp: '2026-09-07T22:45:00+00:00' })).valid, false);
  });

  it('E4 — rejects local-time timestamp (no offset)', () => {
    assert.equal(validateTelemetry(valid({ timestamp: '2026-09-07T22:45:00' })).valid, false);
  });

  it('E5 — rejects date-only string', () => {
    assert.equal(validateTelemetry(valid({ timestamp: '2026-09-07' })).valid, false);
  });

  it('E6 — rejects timestamp > 24 h in the future', () => {
    // Pin "now" to a known moment, then set ts to now + 25h
    const now = new Date('2026-09-07T22:45:00Z');
    const future = new Date(now.getTime() + 25 * 60 * 60 * 1000);
    const ts = future.toISOString().replace(/\.\d+Z$/, 'Z');
    const r = validateTelemetry(valid({ timestamp: ts }), { now });
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('timestamp')));
  });

  it('E7 — accepts timestamp exactly at the 24 h future boundary (should pass)', () => {
    const now = new Date('2026-09-07T22:45:00Z');
    const boundary = new Date(now.getTime() + 24 * 60 * 60 * 1000 - 1000);
    const ts = boundary.toISOString().replace(/\.\d+Z$/, 'Z');
    assert.equal(validateTelemetry(valid({ timestamp: ts }), { now }).valid, true);
  });

  it('E8 — accepts past timestamps freely', () => {
    assert.equal(validateTelemetry(valid({ timestamp: '2020-01-01T00:00:00Z' })).valid, true);
  });
});

// ---------------------------------------------------------------------------
// F. Coordinate validation (WGS84)
// ---------------------------------------------------------------------------

describe('F. Coordinate (lat/lon)', () => {
  it('F1 — rejects latitude > 90', () => {
    const r = validateTelemetry(valid({ latitude: 90.001 }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('latitude')));
  });

  it('F2 — rejects latitude < -90', () => {
    assert.equal(validateTelemetry(valid({ latitude: -90.001 })).valid, false);
  });

  it('F3 — rejects longitude > 180', () => {
    assert.equal(validateTelemetry(valid({ longitude: 180.001 })).valid, false);
  });

  it('F4 — rejects longitude < -180', () => {
    assert.equal(validateTelemetry(valid({ longitude: -180.001 })).valid, false);
  });

  it('F5 — accepts boundary values (90, -90, 180, -180)', () => {
    assert.equal(validateTelemetry(valid({ latitude:   90, longitude:  180 })).valid, true);
    assert.equal(validateTelemetry(valid({ latitude:  -90, longitude: -180 })).valid, true);
  });

  it('F6 — rejects non-number latitude (string)', () => {
    assert.equal(validateTelemetry(valid({ latitude: '30.2672' })).valid, false);
  });

  it('F7 — rejects NaN latitude', () => {
    assert.equal(validateTelemetry(valid({ latitude: NaN })).valid, false);
  });

  it('F8 — rejects Infinity longitude', () => {
    assert.equal(validateTelemetry(valid({ longitude: Infinity })).valid, false);
  });

  it('F9 — rejects missing latitude', () => {
    assert.equal(validateTelemetry(valid({ latitude: undefined })).valid, false);
  });
});

// ---------------------------------------------------------------------------
// G. Optional sensor field validation
// ---------------------------------------------------------------------------

describe('G. Sensor field validation', () => {
  // ── Type errors ──────────────────────────────────────────────────────────
  it('G1 — rejects temperature as a string', () => {
    assert.equal(validateTelemetry(valid({ temperature: '26.4' })).valid, false);
  });

  it('G2 — rejects humidity as NaN', () => {
    assert.equal(validateTelemetry(valid({ humidity: NaN })).valid, false);
  });

  it('G3 — rejects air_quality as Infinity', () => {
    assert.equal(validateTelemetry(valid({ air_quality: Infinity })).valid, false);
  });

  it('G4 — rejects battery as an array', () => {
    assert.equal(validateTelemetry(valid({ battery: [3.92] })).valid, false);
  });

  // ── Physical bounds ──────────────────────────────────────────────────────
  it('G5 — rejects temperature below -40', () => {
    const r = validateTelemetry(valid({ temperature: -40.1 }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.some(e => e.startsWith('temperature')));
  });

  it('G6 — rejects temperature above 85', () => {
    assert.equal(validateTelemetry(valid({ temperature: 85.1 })).valid, false);
  });

  it('G7 — accepts temperature at exact bounds (-40, 85)', () => {
    assert.equal(validateTelemetry(valid({ temperature: -40 })).valid, true);
    assert.equal(validateTelemetry(valid({ temperature:  85 })).valid, true);
  });

  it('G8 — rejects humidity above 100', () => {
    assert.equal(validateTelemetry(valid({ humidity: 100.1 })).valid, false);
  });

  it('G9 — rejects humidity below 0', () => {
    assert.equal(validateTelemetry(valid({ humidity: -0.1 })).valid, false);
  });

  it('G10 — rejects pressure below 300', () => {
    assert.equal(validateTelemetry(valid({ pressure: 299.9 })).valid, false);
  });

  it('G11 — rejects pressure above 1100', () => {
    assert.equal(validateTelemetry(valid({ pressure: 1100.1 })).valid, false);
  });

  it('G12 — rejects negative rainfall', () => {
    assert.equal(validateTelemetry(valid({ rainfall: -0.1 })).valid, false);
  });

  it('G13 — accepts very large rainfall (no upper bound)', () => {
    assert.equal(validateTelemetry(valid({ rainfall: 9999 })).valid, true);
  });

  it('G14 — rejects soil_moisture above 100', () => {
    assert.equal(validateTelemetry(valid({ soil_moisture: 100.1 })).valid, false);
  });

  it('G15 — rejects negative water_level', () => {
    assert.equal(validateTelemetry(valid({ water_level: -1 })).valid, false);
  });

  it('G16 — rejects air_quality above 1000', () => {
    assert.equal(validateTelemetry(valid({ air_quality: 1000.1 })).valid, false);
  });

  it('G17 — rejects battery above 6.0', () => {
    assert.equal(validateTelemetry(valid({ battery: 6.001 })).valid, false);
  });

  it('G18 — accepts battery at exact bounds (0, 6.0)', () => {
    assert.equal(validateTelemetry(valid({ battery: 0 })).valid, true);
    assert.equal(validateTelemetry(valid({ battery: 6.0 })).valid, true);
  });

  it('G19 — accumulates multiple field errors in a single result', () => {
    const r = validateTelemetry(valid({
      temperature: 999,
      humidity:    999,
      battery:     999,
    }));
    assert.equal(r.valid, false);
    assert.ok(r.errors.length >= 3);
  });
});

// ---------------------------------------------------------------------------
// H. Normalization behaviour
// ---------------------------------------------------------------------------

describe('H. Normalization', () => {
  it('H1 — strips unknown fields from the normalized payload', () => {
    const r = validateTelemetry(valid({
      firmware_version: '2.1.0',
      rssi_dbm:        -64,
      _internal_flag:  true,
    }));
    assert.equal(r.valid, true);
    assert.equal(r.payload.firmware_version, undefined);
    assert.equal(r.payload.rssi_dbm, undefined);
    assert.equal(r.payload._internal_flag, undefined);
  });

  it('H2 — normalizes absent optional fields to null (not 0 or undefined)', () => {
    const { temperature, ...noTemp } = valid();
    const r = validateTelemetry(noTemp);
    assert.equal(r.valid, true);
    assert.equal(r.payload.temperature, null);
    assert.notEqual(r.payload.temperature, undefined);
    assert.notEqual(r.payload.temperature, 0);
  });

  it('H3 — preserves numeric zero as 0 in the normalized output', () => {
    const r = validateTelemetry(valid({ rainfall: 0, water_level: 0 }));
    assert.equal(r.valid, true);
    assert.strictEqual(r.payload.rainfall,    0);
    assert.strictEqual(r.payload.water_level, 0);
  });

  it('H4 — normalized payload contains all 13 canonical fields', () => {
    const r = validateTelemetry(valid());
    assert.equal(r.valid, true);
    const canonicalFields = [
      'schema_version', 'node_id', 'timestamp', 'latitude', 'longitude',
      'temperature', 'humidity', 'pressure', 'rainfall',
      'soil_moisture', 'water_level', 'air_quality', 'battery',
    ];
    for (const f of canonicalFields) {
      assert.ok(Object.prototype.hasOwnProperty.call(r.payload, f), `missing field: ${f}`);
    }
  });

  it('H5 — errors array is empty for valid payloads', () => {
    const r = validateTelemetry(valid());
    assert.deepEqual(r.errors, []);
  });

  it('H6 — payload is null for invalid payloads', () => {
    const r = validateTelemetry(valid({ schema_version: 'bad' }));
    assert.equal(r.payload, null);
  });

  it('H7 — no optical/camera fields present in normalized output', () => {
    const r = validateTelemetry(valid({ camera_frame: 'base64...', optical_id: 42 }));
    assert.equal(r.valid, true);
    assert.equal(r.payload.camera_frame, undefined);
    assert.equal(r.payload.optical_id,   undefined);
  });

  it('H8 — node_id is preserved verbatim in normalized output', () => {
    const r = validateTelemetry(valid({ node_id: 'NODE-005' }));
    assert.equal(r.valid, true);
    assert.equal(r.payload.node_id, 'NODE-005');
  });

  it('H9 — schema_version is preserved verbatim in normalized output', () => {
    const r = validateTelemetry(valid({ schema_version: '1.2.0' }));
    assert.equal(r.valid, true);
    assert.equal(r.payload.schema_version, '1.2.0');
  });
});
