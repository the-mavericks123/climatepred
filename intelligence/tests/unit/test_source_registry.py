"""
Unit tests for Source Registry.
"""

from intelligence.ingestion.source_registry import (
    SourceMetadata,
    SourceRegistry,
    SourceStatus,
    SourceType,
)


def test_default_sources_present(fresh_registry):
    sources = fresh_registry.list_all()
    source_ids = [s.source_id for s in sources]
    assert "ESP32_DEFAULT" in source_ids
    assert "WEATHER_API_DEFAULT" in source_ids
    assert "SATELLITE_VIIRS_DEFAULT" in source_ids
    assert "SIMULATION_ENGINE" in source_ids


def test_register_custom_source(fresh_registry):
    custom = SourceMetadata(
        source_id="CUSTOM_HYDRO_01",
        source_type=SourceType.ESP32,
        display_name="Custom River Hydro Station",
        status=SourceStatus.REGISTERED,
    )
    fresh_registry.register(custom)
    retrieved = fresh_registry.get("CUSTOM_HYDRO_01")
    assert retrieved is not None
    assert retrieved.display_name == "Custom River Hydro Station"
    assert fresh_registry.is_source_available("CUSTOM_HYDRO_01") is True


def test_heartbeat_updates_status(fresh_registry):
    source = fresh_registry.get("ESP32_DEFAULT")
    assert source.last_heartbeat is None
    success = fresh_registry.update_heartbeat("ESP32_DEFAULT")
    assert success is True
    updated = fresh_registry.get("ESP32_DEFAULT")
    assert updated.last_heartbeat is not None
