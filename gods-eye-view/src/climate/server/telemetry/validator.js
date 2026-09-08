/**
 * Climate Eye S1 — Telemetry Validator & Normalizer
 *
 * Implements the canonical MQTT telemetry envelope validation rules defined in
 * docs/contracts/DECISIONS.md § DECISION-003 (v1.0.0).
 *
 * Contract guarantees:
 *   - Pure function: no side effects, no I/O, no global state mutation.
 *   - Deterministic: same input always produces same output.
 *   - Numeric zero (0 / 0.0) is a valid real measurement — never coerced to null.
 *   - null is preserved as-is for missing / not-equipped sensor fields.
 *   - Missing optional fields default to null in the normalized output.
 *   - No optical / camera fields exist in this schema.
 */

'use strict';

// ---------------------------------------------------------------------------
// Constants (derived from DECISION-003 § 3. Validation Rules)
// ---------------------------------------------------------------------------

/** Valid schema_version pattern: "1.x.y" — major version must be 1. */
const SCHEMA_VERSION_RE = /^1\.[0-9]+\.[0-9]+$/;

/**
 * node_id grammar: 3–32 characters, alphanumeric + underscore + hyphen.
 * Must be data-driven — never hard-coded in application logic.
 */
const NODE_ID_RE = /^[A-Za-z0-9_-]{3,32}$/;

/**
 * UTC ISO-8601 timestamp pattern (RFC 3339 subset).
 * Must terminate with 'Z' (Zulu / UTC offset).
 * Example: "2026-09-07T22:45:00Z"
 */
const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

/**
 * Maximum allowable clock drift into the future (milliseconds).
 * Payloads with timestamps more than 24 hours ahead of now are rejected.
 */
const MAX_FUTURE_DRIFT_MS = 24 * 60 * 60 * 1000;

/** WGS84 coordinate bounds (DECISION-003 § 3.2) */
const LAT_MIN = -90.0;
const LAT_MAX = 90.0;
const LON_MIN = -180.0;
const LON_MAX = 180.0;

/**
 * Physical sensor value bounds (DECISION-003 § 3.3).
 * Each entry: [min, max] inclusive. null means unbounded on that side.
 */
const SENSOR_BOUNDS = {
  temperature:   [-40.0,  85.0],
  humidity:      [  0.0, 100.0],
  pressure:      [300.0, 1100.0],
  rainfall:      [  0.0,   null],  // non-negative, no defined upper bound
  soil_moisture: [  0.0, 100.0],
  water_level:   [  0.0,   null],  // non-negative, no defined upper bound
  air_quality:   [  0.0, 1000.0],
  battery:       [  0.0,   6.0],
};

/** Ordered list of optional sensor field names from the canonical envelope. */
const OPTIONAL_SENSOR_FIELDS = Object.keys(SENSOR_BOUNDS);

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Returns true when `v` is a finite JavaScript number (not NaN, not ±Infinity).
 * Note: typeof 0 === 'number' and isFinite(0) === true — zero is valid.
 *
 * @param {unknown} v
 * @returns {boolean}
 */
function isFiniteNumber(v) {
  return typeof v === 'number' && isFinite(v);
}

/**
 * Validates that a numeric value is within [min, max] (both ends inclusive).
 * A null bound means that side is unbounded.
 *
 * @param {number} value
 * @param {number|null} min
 * @param {number|null} max
 * @returns {boolean}
 */
function inBounds(value, min, max) {
  if (min !== null && value < min) return false;
  if (max !== null && value > max) return false;
  return true;
}

/**
 * Builds a structured validation error object.
 *
 * @param {string} field  - The field that failed.
 * @param {string} reason - Human-readable description of the failure.
 * @returns {{ field: string, reason: string }}
 */
function makeError(field, reason) {
  return { field, reason };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} ValidationResult
 * @property {boolean}      valid    - True only when all required fields pass and all
 *                                     present optional fields are within physical bounds.
 * @property {string[]}     errors   - Array of human-readable error strings (empty when valid).
 * @property {Object|null}  payload  - The normalized canonical payload (null when invalid).
 */

/**
 * Validates and normalizes a raw MQTT telemetry payload against the
 * Climate Eye Canonical Telemetry Envelope v1.0.0 (DECISION-003).
 *
 * Normalization rules applied to a valid payload:
 *   1. Only canonical fields are present in the output (unknown extra fields are
 *      stripped — forward-compat per DECISION-003 § 5.3 "Permissive Ingest").
 *   2. All optional sensor fields absent from the input are set to null.
 *   3. schema_version is preserved verbatim.
 *   4. timestamp is preserved verbatim (already validated as ISO-8601 UTC).
 *   5. Numeric zero is preserved as 0 (never coerced to null).
 *
 * @param {unknown} raw          - The raw parsed JSON object from the MQTT broker.
 * @param {{ now?: Date }} [opts] - Optional overrides (primarily for deterministic testing).
 * @returns {ValidationResult}
 */
function validateTelemetry(raw, opts = {}) {
  const errors = [];

  // ── Guard: input must be a plain object ──────────────────────────────────
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return {
      valid: false,
      errors: ['payload must be a non-null JSON object'],
      payload: null,
    };
  }

  // ── 1. schema_version ────────────────────────────────────────────────────
  if (typeof raw.schema_version !== 'string') {
    errors.push(makeError('schema_version', 'must be a string'));
  } else if (!SCHEMA_VERSION_RE.test(raw.schema_version)) {
    errors.push(makeError('schema_version', `must match pattern "1.x.y", got "${raw.schema_version}"`));
  }

  // ── 2. node_id ───────────────────────────────────────────────────────────
  if (typeof raw.node_id !== 'string') {
    errors.push(makeError('node_id', 'must be a string'));
  } else if (!NODE_ID_RE.test(raw.node_id)) {
    errors.push(makeError('node_id', `must match pattern [A-Za-z0-9_-]{3,32}, got "${raw.node_id}"`));
  }

  // ── 3. timestamp ─────────────────────────────────────────────────────────
  if (typeof raw.timestamp !== 'string') {
    errors.push(makeError('timestamp', 'must be a string'));
  } else if (!TIMESTAMP_RE.test(raw.timestamp)) {
    errors.push(makeError('timestamp', 'must be a UTC ISO-8601 string ending in Z (e.g. "2026-09-07T22:45:00Z")'));
  } else {
    const ts = Date.parse(raw.timestamp);
    if (isNaN(ts)) {
      errors.push(makeError('timestamp', 'could not be parsed as a valid date'));
    } else {
      const nowMs = (opts.now instanceof Date ? opts.now : new Date()).getTime();
      if (ts - nowMs > MAX_FUTURE_DRIFT_MS) {
        errors.push(makeError('timestamp', 'is more than 24 hours in the future'));
      }
    }
  }

  // ── 4. latitude ──────────────────────────────────────────────────────────
  if (!isFiniteNumber(raw.latitude)) {
    errors.push(makeError('latitude', 'must be a finite number'));
  } else if (!inBounds(raw.latitude, LAT_MIN, LAT_MAX)) {
    errors.push(makeError('latitude', `must be between ${LAT_MIN} and ${LAT_MAX}, got ${raw.latitude}`));
  }

  // ── 5. longitude ─────────────────────────────────────────────────────────
  if (!isFiniteNumber(raw.longitude)) {
    errors.push(makeError('longitude', 'must be a finite number'));
  } else if (!inBounds(raw.longitude, LON_MIN, LON_MAX)) {
    errors.push(makeError('longitude', `must be between ${LON_MIN} and ${LON_MAX}, got ${raw.longitude}`));
  }

  // ── 6. Optional sensor fields ────────────────────────────────────────────
  for (const field of OPTIONAL_SENSOR_FIELDS) {
    const value = raw[field];

    // Absent or explicitly null → valid (will be normalized to null in output)
    if (value === undefined || value === null) continue;

    // Present but wrong type
    if (!isFiniteNumber(value)) {
      errors.push(makeError(field, `must be a finite number or null, got ${JSON.stringify(value)}`));
      continue;
    }

    // Present and numeric: check physical bounds
    const [min, max] = SENSOR_BOUNDS[field];
    if (!inBounds(value, min, max)) {
      const boundsDesc = `[${min !== null ? min : '-inf'}, ${max !== null ? max : '+inf'}]`;
      errors.push(makeError(field, `value ${value} is outside physical bounds ${boundsDesc}`));
    }
  }

  // ── Build result ─────────────────────────────────────────────────────────
  if (errors.length > 0) {
    return {
      valid: false,
      errors: errors.map((e) => `${e.field}: ${e.reason}`),
      payload: null,
    };
  }

  // ── Normalize ─────────────────────────────────────────────────────────────
  // Produce a clean output containing only the canonical fields.
  // Optional fields absent in input default to null (never to 0).
  const normalized = {
    schema_version: raw.schema_version,
    node_id:        raw.node_id,
    timestamp:      raw.timestamp,
    latitude:       raw.latitude,
    longitude:      raw.longitude,
  };

  for (const field of OPTIONAL_SENSOR_FIELDS) {
    const value = raw[field];
    // undefined (absent) → null; null → null; finite number → preserved as-is (incl. 0)
    normalized[field] = (value === undefined || value === null) ? null : value;
  }

  return { valid: true, errors: [], payload: normalized };
}

// ---------------------------------------------------------------------------
// Exports (ESM)
// ---------------------------------------------------------------------------

export {
  validateTelemetry,
  // Expose internals for white-box unit testing only
  SCHEMA_VERSION_RE,
  NODE_ID_RE,
  TIMESTAMP_RE,
  SENSOR_BOUNDS,
  OPTIONAL_SENSOR_FIELDS,
};
