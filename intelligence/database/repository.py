"""
Climate Eye View — Database Repository Implementation.
Provides unified persistence conforming to database/migrations/001_initial_schema.sql
for telemetry, hazards, predictions, compound disasters, vulnerability, evacuation, and response plans.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.logging import get_logger

logger = get_logger("database_repository")


class IntelligenceRepository:
    """
    Thread-safe repository providing persistence for all 9 Climate Eye View core entities.
    Supports SQLite database files (for standalone/local/testing persistence across restarts)
    and maps exactly to the relational schema defined in 001_initial_schema.sql.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys = ON")
            return self._conn
        else:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn

    def _init_db(self) -> None:
        """Creates the relational tables matching 001_initial_schema.sql."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Nodes
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                elevation_m REAL,
                hardware_version TEXT DEFAULT 'ESP32-V1',
                firmware_version TEXT DEFAULT '1.0.0',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 2. Sensor Readings (Telemetry)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                rainfall REAL,
                soil_moisture REAL,
                water_level REAL,
                air_quality REAL,
                battery REAL,
                light_intensity REAL,
                sensor_status_json TEXT DEFAULT '{}',
                provenance_hash TEXT,
                quality_valid INTEGER NOT NULL DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                anomaly_score REAL DEFAULT 0.0,
                FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE,
                UNIQUE (node_id, timestamp)
            );
            """)

            for col, col_type in [("light_intensity", "REAL"), ("sensor_status_json", "TEXT DEFAULT '{}'")]:
                try:
                    cursor.execute(f"ALTER TABLE sensor_readings ADD COLUMN {col} {col_type};")
                except sqlite3.OperationalError:
                    pass

            # 3. Hazard Events
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hazard_events (
                event_id TEXT PRIMARY KEY,
                node_id TEXT,
                hazard_type TEXT NOT NULL,
                severity REAL NOT NULL,
                confidence REAL NOT NULL,
                affected_area_wkt TEXT,
                detected_at TEXT NOT NULL,
                expires_at TEXT,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE SET NULL
            );
            """)

            # 4. Predictions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                target_hazard TEXT NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                predicted_severity REAL NOT NULL,
                confidence REAL NOT NULL,
                trend TEXT NOT NULL,
                model_version TEXT NOT NULL,
                predicted_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
            );
            """)

            # 5. Compound Events
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS compound_events (
                compound_id TEXT PRIMARY KEY,
                primary_hazard_id TEXT,
                secondary_hazard_id TEXT,
                cascade_risk REAL NOT NULL,
                rule_id TEXT NOT NULL,
                compound_severity REAL NOT NULL,
                detected_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (primary_hazard_id) REFERENCES hazard_events(event_id) ON DELETE CASCADE,
                FOREIGN KEY (secondary_hazard_id) REFERENCES hazard_events(event_id) ON DELETE CASCADE
            );
            """)

            # 6. Vulnerability Zones
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vulnerability_zones (
                zone_id TEXT PRIMARY KEY,
                zone_name TEXT NOT NULL,
                vulnerability_score REAL NOT NULL,
                boundary_wkt TEXT NOT NULL,
                population_total INTEGER NOT NULL DEFAULT 0,
                elderly_count INTEGER NOT NULL DEFAULT 0,
                children_count INTEGER NOT NULL DEFAULT 0,
                hospital_count INTEGER NOT NULL DEFAULT 0,
                school_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 7. Shelters
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS shelters (
                shelter_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                current_occupancy INTEGER NOT NULL DEFAULT 0,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                accessibility_rating REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 8. Evacuation Routes
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evacuation_routes (
                route_id TEXT PRIMARY KEY,
                origin_zone_id TEXT NOT NULL,
                destination_shelter_id TEXT NOT NULL,
                route_geometry_wkt TEXT NOT NULL,
                accessibility_score REAL NOT NULL,
                hazard_exposure REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'PASSABLE',
                estimated_travel_minutes REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (origin_zone_id) REFERENCES vulnerability_zones(zone_id) ON DELETE CASCADE,
                FOREIGN KEY (destination_shelter_id) REFERENCES shelters(shelter_id) ON DELETE CASCADE
            );
            """)

            # 9. Response Plans
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS response_plans (
                plan_id TEXT PRIMARY KEY,
                alert_level TEXT NOT NULL,
                primary_hazard TEXT NOT NULL,
                actions_json TEXT NOT NULL DEFAULT '[]',
                resource_allocations TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                evaluated_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    # -------------------------------------------------------------------------
    # 1. Nodes Operations
    # -------------------------------------------------------------------------
    def upsert_node(
        self,
        node_id: str,
        name: str,
        latitude: float,
        longitude: float,
        status: str = "ACTIVE",
        elevation_m: Optional[float] = None,
        hardware_version: str = "ESP32-V1",
        firmware_version: str = "1.0.0",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO nodes (node_id, name, status, latitude, longitude, elevation_m, hardware_version, firmware_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                name=excluded.name,
                status=excluded.status,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                elevation_m=excluded.elevation_m,
                updated_at=excluded.updated_at;
            """, (node_id, name, status, latitude, longitude, elevation_m, hardware_version, firmware_version, now, now))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            res = dict(row) if row else None
            if self.db_path != ":memory:":
                conn.close()
            return res

    # -------------------------------------------------------------------------
    # 2. Telemetry Operations
    # -------------------------------------------------------------------------
    def save_telemetry(
        self,
        telemetry: NormalizedTelemetry,
        provenance_hash: Optional[str] = None,
        anomaly_score: float = 0.0,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        # Extract lat/lon safely
        lat = telemetry.location.lat if hasattr(telemetry, "location") and hasattr(telemetry.location, "lat") else getattr(telemetry, "latitude", 0.0)
        lon = telemetry.location.lon if hasattr(telemetry, "location") and hasattr(telemetry.location, "lon") else getattr(telemetry, "longitude", 0.0)
        meas = telemetry.measurements if hasattr(telemetry, "measurements") else None

        temp = getattr(meas, "temperature", None) if meas else getattr(telemetry, "temperature", None)
        hum = getattr(meas, "humidity", None) if meas else getattr(telemetry, "humidity", None)
        press = getattr(meas, "pressure", None) if meas else getattr(telemetry, "pressure", None)
        rain = getattr(meas, "rainfall", None) if meas else getattr(telemetry, "rainfall", None)
        soil = getattr(meas, "soil_moisture", None) if meas else getattr(telemetry, "soil_moisture", None)
        water = getattr(meas, "water_level", None) if meas else getattr(telemetry, "water_level", None)
        aqi = getattr(meas, "air_quality", None) if meas else getattr(telemetry, "air_quality", None)
        batt = getattr(meas, "battery", None) if meas else getattr(telemetry, "battery", None)
        lux = getattr(meas, "light_intensity", None) if meas else getattr(telemetry, "light_intensity", None)
        status_dict = getattr(meas, "sensor_status", None) if meas else getattr(telemetry, "sensor_status", None)

        # Ensure node exists before inserting reading
        if self.get_node(telemetry.node_id) is None:
            self.upsert_node(
                node_id=telemetry.node_id,
                name=f"Sensor {telemetry.node_id}",
                latitude=lat,
                longitude=lon,
            )

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO sensor_readings (
                node_id, timestamp, received_at, latitude, longitude,
                temperature, humidity, pressure, rainfall, soil_moisture,
                water_level, air_quality, battery, light_intensity, sensor_status_json,
                provenance_hash, quality_valid, confidence, anomaly_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id, timestamp) DO UPDATE SET
                temperature=excluded.temperature,
                humidity=excluded.humidity,
                pressure=excluded.pressure,
                rainfall=excluded.rainfall,
                soil_moisture=excluded.soil_moisture,
                water_level=excluded.water_level,
                air_quality=excluded.air_quality,
                battery=excluded.battery,
                light_intensity=excluded.light_intensity,
                sensor_status_json=excluded.sensor_status_json,
                provenance_hash=excluded.provenance_hash;
            """, (
                telemetry.node_id,
                telemetry.timestamp.isoformat(),
                now,
                lat,
                lon,
                temp,
                hum,
                press,
                rain,
                soil,
                water,
                aqi,
                batt,
                lux,
                json.dumps(status_dict or {}),
                provenance_hash or telemetry.node_id,
                1 if (temp is not None or rain is not None) else 0,
                1.0,
                anomaly_score,
            ))
            reading_id = cursor.lastrowid or 0
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()
            return reading_id

    def get_telemetry(self, node_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM sensor_readings WHERE node_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (node_id, limit))
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 3. Hazard Events Operations
    # -------------------------------------------------------------------------
    def save_hazard_event(
        self,
        event_id: str,
        hazard_type: str,
        severity: float,
        confidence: float,
        detected_at: datetime,
        node_id: Optional[str] = None,
        affected_area_wkt: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if node_id and self.get_node(node_id) is None:
            self.upsert_node(node_id, f"Node {node_id}", 0.0, 0.0)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO hazard_events (
                event_id, node_id, hazard_type, severity, confidence,
                affected_area_wkt, detected_at, expires_at, evidence_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                node_id,
                hazard_type,
                severity,
                confidence,
                affected_area_wkt,
                detected_at.isoformat(),
                expires_at.isoformat() if expires_at else None,
                json.dumps(evidence or {}),
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_hazard_events(
        self,
        node_id: Optional[str] = None,
        hazard_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM hazard_events WHERE 1=1"
            params: List[Any] = []
            if node_id:
                query += " AND node_id = ?"
                params.append(node_id)
            if hazard_type:
                query += " AND hazard_type = ?"
                params.append(hazard_type)
            query += " ORDER BY detected_at DESC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 4. Predictions Operations
    # -------------------------------------------------------------------------
    def save_prediction(
        self,
        prediction_id: str,
        node_id: str,
        target_hazard: str,
        horizon_minutes: int,
        predicted_severity: float,
        confidence: float,
        trend: str,
        model_version: str,
        predicted_at: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        pred_ts = (predicted_at or datetime.now(timezone.utc)).isoformat()
        if node_id and self.get_node(node_id) is None:
            self.upsert_node(node_id, f"Node {node_id}", 0.0, 0.0)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO predictions (
                prediction_id, node_id, target_hazard, horizon_minutes,
                predicted_severity, confidence, trend, model_version, predicted_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction_id,
                node_id,
                target_hazard,
                horizon_minutes,
                predicted_severity,
                confidence,
                trend,
                model_version,
                pred_ts,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_predictions(self, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM predictions WHERE 1=1"
            params: List[Any] = []
            if node_id:
                query += " AND node_id = ?"
                params.append(node_id)
            query += " ORDER BY predicted_at DESC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 5. Compound Events Operations
    # -------------------------------------------------------------------------
    def save_compound_event(
        self,
        compound_id: str,
        primary_hazard_id: Optional[str],
        secondary_hazard_id: Optional[str],
        cascade_risk: float,
        rule_id: str,
        compound_severity: float,
        detected_at: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        det_ts = (detected_at or datetime.now(timezone.utc)).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO compound_events (
                compound_id, primary_hazard_id, secondary_hazard_id,
                cascade_risk, rule_id, compound_severity, detected_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                compound_id,
                primary_hazard_id,
                secondary_hazard_id,
                cascade_risk,
                rule_id,
                compound_severity,
                det_ts,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_compound_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM compound_events ORDER BY cascade_risk DESC")
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 6. Vulnerability Zones Operations
    # -------------------------------------------------------------------------
    def save_vulnerability_zone(
        self,
        zone_id: str,
        zone_name: str,
        vulnerability_score: float,
        boundary_wkt: str,
        population_total: int = 0,
        elderly_count: int = 0,
        children_count: int = 0,
        hospital_count: int = 0,
        school_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO vulnerability_zones (
                zone_id, zone_name, vulnerability_score, boundary_wkt,
                population_total, elderly_count, children_count, hospital_count, school_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id) DO UPDATE SET
                zone_name=excluded.zone_name,
                vulnerability_score=excluded.vulnerability_score,
                boundary_wkt=excluded.boundary_wkt,
                population_total=excluded.population_total,
                updated_at=excluded.updated_at;
            """, (
                zone_id,
                zone_name,
                vulnerability_score,
                boundary_wkt,
                population_total,
                elderly_count,
                children_count,
                hospital_count,
                school_count,
                now,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_vulnerability_zones(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vulnerability_zones ORDER BY vulnerability_score DESC")
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 7. Shelters Operations
    # -------------------------------------------------------------------------
    def save_shelter(
        self,
        shelter_id: str,
        name: str,
        capacity: int,
        latitude: float,
        longitude: float,
        current_occupancy: int = 0,
        status: str = "OPEN",
        accessibility_rating: float = 1.0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO shelters (
                shelter_id, name, capacity, current_occupancy, latitude, longitude,
                status, accessibility_rating, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shelter_id) DO UPDATE SET
                name=excluded.name,
                capacity=excluded.capacity,
                current_occupancy=excluded.current_occupancy,
                status=excluded.status,
                accessibility_rating=excluded.accessibility_rating,
                updated_at=excluded.updated_at;
            """, (
                shelter_id,
                name,
                capacity,
                current_occupancy,
                latitude,
                longitude,
                status,
                accessibility_rating,
                now,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_shelters(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shelters ORDER BY name ASC")
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 8. Evacuation Routes Operations
    # -------------------------------------------------------------------------
    def save_evacuation_route(
        self,
        route_id: str,
        origin_zone_id: str,
        destination_shelter_id: str,
        route_geometry_wkt: str,
        accessibility_score: float,
        hazard_exposure: float = 0.0,
        status: str = "PASSABLE",
        estimated_travel_minutes: Optional[float] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO evacuation_routes (
                route_id, origin_zone_id, destination_shelter_id, route_geometry_wkt,
                accessibility_score, hazard_exposure, status, estimated_travel_minutes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(route_id) DO UPDATE SET
                accessibility_score=excluded.accessibility_score,
                hazard_exposure=excluded.hazard_exposure,
                status=excluded.status,
                estimated_travel_minutes=excluded.estimated_travel_minutes,
                updated_at=excluded.updated_at;
            """, (
                route_id,
                origin_zone_id,
                destination_shelter_id,
                route_geometry_wkt,
                accessibility_score,
                hazard_exposure,
                status,
                estimated_travel_minutes,
                now,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_evacuation_routes(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evacuation_routes ORDER BY accessibility_score DESC")
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results

    # -------------------------------------------------------------------------
    # 9. Response Plans Operations
    # -------------------------------------------------------------------------
    def save_response_plan(
        self,
        plan_id: str,
        alert_level: str,
        primary_hazard: str,
        actions: List[Dict[str, Any]],
        resource_allocations: Optional[Dict[str, Any]] = None,
        status: str = "ACTIVE",
        evaluated_at: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        eval_ts = (evaluated_at or datetime.now(timezone.utc)).isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO response_plans (
                plan_id, alert_level, primary_hazard, actions_json,
                resource_allocations, status, evaluated_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                alert_level=excluded.alert_level,
                primary_hazard=excluded.primary_hazard,
                actions_json=excluded.actions_json,
                resource_allocations=excluded.resource_allocations,
                status=excluded.status;
            """, (
                plan_id,
                alert_level,
                primary_hazard,
                json.dumps(actions),
                json.dumps(resource_allocations or {}),
                status,
                eval_ts,
                now,
            ))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def get_response_plans(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM response_plans ORDER BY evaluated_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]
            if self.db_path != ":memory:":
                conn.close()
            return results


# Global singleton instance (in-memory default, configurable to file or PostgreSQL)
_global_repository: Optional[IntelligenceRepository] = None


def get_repository() -> IntelligenceRepository:
    global _global_repository
    if _global_repository is None:
        _global_repository = IntelligenceRepository()
    return _global_repository
