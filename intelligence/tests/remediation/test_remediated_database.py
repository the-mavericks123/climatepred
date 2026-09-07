"""
Tests for Phase 11 Remediation: BLK-DB-01 (Source-Controlled PostGIS Schema & Restore Drill).
Verifies:
- Migration file 001_initial_schema.sql existence and syntax
- Complete source-controlled DDL for all 9 required domain entities
- PostGIS spatial geometry column types (Point, Polygon, LineString with SRID 4326)
- GiST spatial indexes and B-Tree deduplication indexes
- Automated restore drill script execution and reporting
"""

from pathlib import Path
import re
import pytest

from intelligence.scripts.test_db_restore import (
    REQUIRED_SPATIAL_INDEXES,
    REQUIRED_TABLES,
    load_migration_ddl,
    parse_and_validate_ddl,
    run_restore_drill,
)


class TestDatabaseRemediation:
    """Verifies BLK-DB-01 remediation: source-controlled schema and restore verification."""

    def test_migration_file_exists_and_non_empty(self):
        """DDL migration file 001_initial_schema.sql must exist and have content."""
        migration_file = Path("database/migrations/001_initial_schema.sql")
        assert migration_file.exists(), "database/migrations/001_initial_schema.sql does not exist!"
        content = migration_file.read_text(encoding="utf-8")
        assert len(content) > 500

    def test_postgis_extension_enabled(self):
        """Migration explicitly enables PostGIS extension."""
        ddl = load_migration_ddl()
        assert "CREATE EXTENSION IF NOT EXISTS postgis;" in ddl

    def test_all_nine_required_tables_defined(self):
        """All 9 tables required by forensic audit exist in DDL with primary keys."""
        ddl = load_migration_ddl()
        tables, _, _ = parse_and_validate_ddl(ddl)

        for table in REQUIRED_TABLES:
            assert table in tables, f"Required table '{table}' missing from migration DDL!"

    def test_spatial_geometries_use_srid_4326(self):
        """Spatial geometry fields use WGS84 SRID 4326 for points, polygons, and linestrings."""
        ddl = load_migration_ddl()

        # Check Point geometry
        assert "GEOMETRY(Point, 4326)" in ddl
        # Check Polygon geometry
        assert "GEOMETRY(Polygon, 4326)" in ddl
        # Check LineString geometry
        assert "GEOMETRY(LineString, 4326)" in ddl

    def test_all_gist_spatial_indexes_defined(self):
        """GiST spatial indexes are defined for all spatial entities."""
        ddl = load_migration_ddl()
        _, indexes, gist_cols = parse_and_validate_ddl(ddl)

        for spatial_idx in REQUIRED_SPATIAL_INDEXES:
            assert spatial_idx in indexes, f"Required spatial index '{spatial_idx}' missing!"

        assert len(gist_cols) >= 6

    def test_sensor_readings_uniqueness_constraint_for_deduplication(self):
        """Sensor readings table has unique constraint on (node_id, timestamp) for deduplication."""
        ddl = load_migration_ddl()
        assert "UNIQUE (node_id, timestamp)" in ddl

    def test_foreign_key_relationships_defined(self):
        """Foreign keys link sensor readings, predictions, evacuation, and compound events."""
        ddl = load_migration_ddl()
        assert "REFERENCES nodes(node_id)" in ddl
        assert "REFERENCES vulnerability_zones(zone_id)" in ddl
        assert "REFERENCES shelters(shelter_id)" in ddl
        assert "REFERENCES hazard_events(event_id)" in ddl

    def test_restore_drill_script_executes_cleanly(self):
        """Automated restore drill script runs and verifies schema validity."""
        result = run_restore_drill()
        assert result.schema_file_exists is True
        assert len(result.tables_verified) == 9
        assert len(result.spatial_indexes_verified) >= 6
        assert result.representative_entities_valid is True
        assert result.status in ["VERIFIED", "SCHEMA_VERIFIED_RUNTIME_UNVERIFIED"]
