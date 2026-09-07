-- ============================================================================
-- Climate Eye View — Production PostGIS Database Migration 001
-- Canonical source-controlled schema for hardware telemetry, hazards,
-- predictions, compound disasters, vulnerability, evacuation, and response.
-- ============================================================================

-- 0. Extensions
CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------------------
-- 1. Hardware Nodes Registry
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    location GEOMETRY(Point, 4326) NOT NULL,
    elevation_m DOUBLE PRECISION,
    hardware_version VARCHAR(32) DEFAULT 'ESP32-V1',
    firmware_version VARCHAR(32) DEFAULT '1.0.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nodes_location ON nodes USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

-- ----------------------------------------------------------------------------
-- 2. Sensor Readings (Telemetry Persistence)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(64) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    location GEOMETRY(Point, 4326) NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION,
    rainfall DOUBLE PRECISION,
    soil_moisture DOUBLE PRECISION,
    water_level DOUBLE PRECISION,
    air_quality DOUBLE PRECISION,
    battery DOUBLE PRECISION,
    provenance_hash CHAR(64),
    quality_valid BOOLEAN NOT NULL DEFAULT TRUE,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    anomaly_score DOUBLE PRECISION DEFAULT 0.0,
    CONSTRAINT uq_sensor_readings_node_time UNIQUE (node_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_node_time ON sensor_readings(node_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_location ON sensor_readings USING GIST(location);

-- ----------------------------------------------------------------------------
-- 3. Hazard Events
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hazard_events (
    event_id VARCHAR(64) PRIMARY KEY,
    node_id VARCHAR(64) REFERENCES nodes(node_id) ON DELETE SET NULL,
    hazard_type VARCHAR(32) NOT NULL,
    severity DOUBLE PRECISION NOT NULL CHECK (severity >= 0.0 AND severity <= 1.0),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    affected_area GEOMETRY(Polygon, 4326),
    detected_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hazard_events_area ON hazard_events USING GIST(affected_area);
CREATE INDEX IF NOT EXISTS idx_hazard_events_type_severity ON hazard_events(hazard_type, severity DESC);
CREATE INDEX IF NOT EXISTS idx_hazard_events_detected_at ON hazard_events(detected_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Predictions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id VARCHAR(64) PRIMARY KEY,
    node_id VARCHAR(64) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    target_hazard VARCHAR(32) NOT NULL,
    horizon_minutes INT NOT NULL,
    predicted_severity DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    trend VARCHAR(32) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_node_hazard ON predictions(node_id, target_hazard, predicted_at DESC);

-- ----------------------------------------------------------------------------
-- 5. Compound & Cascading Disaster Events
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compound_events (
    compound_id VARCHAR(64) PRIMARY KEY,
    primary_hazard_id VARCHAR(64) REFERENCES hazard_events(event_id) ON DELETE CASCADE,
    secondary_hazard_id VARCHAR(64) REFERENCES hazard_events(event_id) ON DELETE CASCADE,
    cascade_risk DOUBLE PRECISION NOT NULL CHECK (cascade_risk >= 0.0 AND cascade_risk <= 1.0),
    rule_id VARCHAR(64) NOT NULL,
    compound_severity DOUBLE PRECISION NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compound_events_risk ON compound_events(cascade_risk DESC);

-- ----------------------------------------------------------------------------
-- 6. Human Vulnerability Zones
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vulnerability_zones (
    zone_id VARCHAR(64) PRIMARY KEY,
    zone_name VARCHAR(128) NOT NULL,
    vulnerability_score DOUBLE PRECISION NOT NULL CHECK (vulnerability_score >= 0.0 AND vulnerability_score <= 1.0),
    boundary GEOMETRY(Polygon, 4326) NOT NULL,
    population_total INT NOT NULL DEFAULT 0,
    elderly_count INT NOT NULL DEFAULT 0,
    children_count INT NOT NULL DEFAULT 0,
    hospital_count INT NOT NULL DEFAULT 0,
    school_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vulnerability_zones_boundary ON vulnerability_zones USING GIST(boundary);
CREATE INDEX IF NOT EXISTS idx_vulnerability_score ON vulnerability_zones(vulnerability_score DESC);

-- ----------------------------------------------------------------------------
-- 7. Emergency Shelters
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shelters (
    shelter_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    current_occupancy INT NOT NULL DEFAULT 0,
    location GEOMETRY(Point, 4326) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    accessibility_rating DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shelters_location ON shelters USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_shelters_status ON shelters(status);

-- ----------------------------------------------------------------------------
-- 8. Evacuation Routes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evacuation_routes (
    route_id VARCHAR(64) PRIMARY KEY,
    origin_zone_id VARCHAR(64) NOT NULL REFERENCES vulnerability_zones(zone_id) ON DELETE CASCADE,
    destination_shelter_id VARCHAR(64) NOT NULL REFERENCES shelters(shelter_id) ON DELETE CASCADE,
    route_geometry GEOMETRY(LineString, 4326) NOT NULL,
    accessibility_score DOUBLE PRECISION NOT NULL CHECK (accessibility_score >= 0.0 AND accessibility_score <= 1.0),
    hazard_exposure DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(32) NOT NULL DEFAULT 'PASSABLE',
    estimated_travel_minutes DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evacuation_routes_geom ON evacuation_routes USING GIST(route_geometry);
CREATE INDEX IF NOT EXISTS idx_evacuation_routes_status ON evacuation_routes(status);

-- ----------------------------------------------------------------------------
-- 9. Emergency Response Plans
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS response_plans (
    plan_id VARCHAR(64) PRIMARY KEY,
    alert_level VARCHAR(32) NOT NULL,
    primary_hazard VARCHAR(32) NOT NULL,
    actions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_allocations JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_response_plans_alert ON response_plans(alert_level, status);
CREATE INDEX IF NOT EXISTS idx_response_plans_evaluated_at ON response_plans(evaluated_at DESC);
