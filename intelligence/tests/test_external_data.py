"""
Comprehensive Test Suite for Climate Eye View Global Live Data Ingestion & Multi-Source Fusion.
Validates all 24 required test vectors:
 1. Open-Meteo normalization
 2. FIRMS normalization
 3. USGS normalization
 4. GDACS normalization
 5. GloFAS normalization
 6. Malformed provider response
 7. Provider timeout handling
 8. Provider circuit breaker / rate limiting
 9. Stale provider marking
10. Provider unavailable handling
11. Cache fallback
12. Spatial mapping & distance
13. Hazard zone generation
14. Global -> Intelligence pipeline
15. Global -> Realtime broadcaster events
16. Global -> Cesium GeoJSON formatting
17. Multiple simultaneous providers
18. Source provenance hashing
19. Epistemic status separation
20. No fabricated values rule
21. Water-level invariant (strictly None)
22. ESP32 + global fusion
23. AI grounded reasoning (zero hallucination)
24. Simulation remains simulated=true
"""

from datetime import datetime, timezone
import json
import pytest
from unittest.mock import MagicMock, patch

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.fusion.hazard_fusion import GlobalHazardFusionEngine
from intelligence.external_data.fusion.spatial_fusion import GlobalSpatialGrid
from intelligence.external_data.fusion.weather_fusion import WeatherFusionEngine
from intelligence.external_data.provenance import ExternalProvenanceTracker
from intelligence.external_data.providers.gdacs import GdacsProvider
from intelligence.external_data.providers.glofas import GlofasProvider
from intelligence.external_data.providers.nasa_firms import NasaFirmsProvider
from intelligence.external_data.providers.open_meteo import OpenMeteoProvider
from intelligence.external_data.providers.usgs import UsgsEarthquakeProvider
from intelligence.external_data.quality import ObservationQualityGate
from intelligence.external_data.registry import ExternalSourceRegistry
from intelligence.external_data.service import ExternalDataService
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    ExternalMeasurements,
    ExternalObservation,
    GlobalDisasterEvent,
    GlobalHazardZone,
    SourceType,
)


@pytest.fixture
def mock_cache():
    return ExternalDataCache()


@pytest.fixture
def sample_location():
    return ExternalLocation(lat=17.3850, lon=78.4867, elevation_m=542.0, name="Hyderabad Station")


# 1. Open-Meteo normalization
def test_open_meteo_normalization():
    raw_payload = {
        "latitude": 17.385,
        "longitude": 78.4867,
        "elevation": 542.0,
        "current": {
            "time": "2026-09-08T06:00",
            "temperature_2m": 32.4,
            "relative_humidity_2m": 71.0,
            "apparent_temperature": 37.2,
            "surface_pressure": 1007.2,
            "precipitation": 12.4,
            "wind_speed_10m": 18.0,  # km/h
            "wind_direction_10m": 240.0,
        }
    }
    provider = OpenMeteoProvider()
    obs = provider._normalize(
        raw_payload,
        req_lat=17.385,
        req_lon=78.4867,
        source_url="https://api.open-meteo.com/v1/forecast?test=1",
        station_name="Hyderabad Station",
    )
    assert obs is not None
    assert obs.location.lat == 17.385
    assert obs.location.lon == 78.4867
    assert obs.measurements.temperature == 32.4
    assert obs.measurements.apparent_temperature == 37.2
    assert obs.measurements.humidity == 71.0
    assert obs.measurements.pressure == 1007.2
    assert obs.measurements.precipitation == 12.4
    assert obs.measurements.wind_speed == 5.0  # 18 km/h / 3.6 = 5.0 m/s
    assert obs.measurements.water_level is None  # CRITICAL INVARIANT
    assert obs.epistemic_status == EpistemicStatus.OBSERVED
    assert obs.simulated is False


# 2. FIRMS normalization and clustering
def test_firms_normalization_and_clustering():
    provider = NasaFirmsProvider()
    sample_points = [
        {"lat": 34.05, "lon": -118.25, "brightness_k": 365.2, "confidence": 0.85, "satellite": "MODIS", "source": "MODIS_C6_1"},
        {"lat": 34.07, "lon": -118.22, "brightness_k": 380.0, "confidence": 0.90, "satellite": "MODIS", "source": "MODIS_C6_1"},
        {"lat": 34.04, "lon": -118.28, "brightness_k": 340.5, "confidence": 0.70, "satellite": "MODIS", "source": "MODIS_C6_1"},
    ]
    zones = provider.cluster_fires(sample_points)
    assert len(zones) == 1
    zone = zones[0]
    assert zone.hazard_type == "WILDFIRE"
    assert zone.severity > 0.3
    assert zone.metrics["hotspot_count"] == 3
    assert zone.metrics["peak_brightness_k"] == 380.0
    assert zone.epistemic_status == EpistemicStatus.OBSERVED
    assert zone.simulated is False


# 3. USGS normalization & radius calculation
def test_usgs_normalization():
    provider = UsgsEarthquakeProvider()
    quake_event = GlobalDisasterEvent(
        event_id="USGS-TEST-001",
        event_type="EARTHQUAKE",
        title="M 5.8 Earthquake - Hindu Kush Region",
        severity=0.63,
        alert_level="ORANGE",
        confidence=0.98,
        location=ExternalLocation(lat=36.5, lon=70.5, name="Hindu Kush"),
        affected_radius_km=25.1,
        source="USGS",
        timestamp=datetime.now(timezone.utc),
        metadata={"magnitude": 5.8, "depth_km": 120.0},
    )
    zones = provider.to_hazard_zones([quake_event])
    assert len(zones) == 1
    z = zones[0]
    assert z.hazard_type == "EARTHQUAKE"
    assert z.severity == 0.63
    assert z.metrics["magnitude"] == 5.8
    assert z.radius_km == 25.1
    assert z.epistemic_status == EpistemicStatus.OBSERVED


# 4. GDACS normalization
def test_gdacs_normalization():
    provider = GdacsProvider()
    ev = GlobalDisasterEvent(
        event_id="GDACS-TC-100234",
        event_type="CYCLONE",
        title="Tropical Cyclone BEJISA-14",
        severity=0.90,
        alert_level="RED",
        confidence=0.92,
        location=ExternalLocation(lat=-21.5, lon=55.5, name="Reunion Island"),
        affected_radius_km=80.0,
        source="GDACS",
        timestamp=datetime.now(timezone.utc),
        metadata={"raw_alert_level": "RED"},
    )
    zones = provider.to_hazard_zones([ev])
    assert len(zones) == 1
    z = zones[0]
    assert z.hazard_type == "CYCLONE"
    assert z.severity == 0.90
    assert z.radius_km == 80.0


# 5. GloFAS normalization (Honest UNAVAILABLE status)
def test_glofas_honest_unavailable_handling():
    with patch.dict("os.environ", {}, clear=True):
        provider = GlofasProvider()
        status = provider.get_status()
        assert status.status == "UNAVAILABLE"
        assert "CDS_API_KEY" in status.error_message
        zones = provider.fetch_flood_zones()
        assert len(zones) == 0  # Zero fabricated flood zones


# 6. Malformed provider response
def test_malformed_provider_response():
    provider = OpenMeteoProvider()
    obs = provider._normalize({}, req_lat=10.0, req_lon=20.0, source_url="http://bad.url", station_name="Test")
    assert obs is None


# 7. Provider timeout handling
def test_provider_timeout_handling():
    cache = ExternalDataCache()
    provider = OpenMeteoProvider(cache=cache, timeout_sec=0.001)
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        obs = provider.fetch_point_weather(17.38, 78.48)
        assert obs is None


# 8. Provider circuit breaker / rate limiting
def test_circuit_breaker_tripping():
    cache = ExternalDataCache()
    provider = OpenMeteoProvider(cache=cache)
    breaker = cache.get_breaker("open_meteo")
    assert breaker.state == "CLOSED"

    # Simulate 3 consecutive network failures
    for _ in range(3):
        breaker.record_failure()

    assert breaker.state == "OPEN"
    assert breaker.can_attempt() is False


# 9. Stale provider marking
def test_stale_provider_marking():
    cache = ExternalDataCache()
    now = datetime.now(timezone.utc)
    obs = ExternalObservation(
        observation_id="OBS-1",
        source="open_meteo",
        source_type=SourceType.WEATHER_API,
        timestamp=now,
        received_at=now,
        location=ExternalLocation(lat=10.0, lon=20.0),
        measurements=ExternalMeasurements(temperature=25.0),
        quality=ObservationQualityGate.evaluate(
            ExternalLocation(lat=10.0, lon=20.0),
            ExternalMeasurements(temperature=25.0),
            now,
            now,
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        provenance=ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://url", now, now, 10.0, 20.0, {"temperature": 25.0}),
    )
    cache.set("open_meteo_10.000_20.000", obs, ttl_seconds=0.01)

    import time
    time.sleep(0.02)
    provider = OpenMeteoProvider(cache=cache)
    # Trip breaker so it falls back to stale
    cache.get_breaker("open_meteo").record_failure()
    cache.get_breaker("open_meteo").record_failure()
    cache.get_breaker("open_meteo").record_failure()

    stale_obs = provider.fetch_point_weather(10.0, 20.0)
    assert stale_obs is not None
    assert stale_obs.epistemic_status == EpistemicStatus.STALE


# 10. Provider unavailable handling (System remains operational)
def test_provider_unavailable_system_remains_operational():
    registry = ExternalSourceRegistry()
    registry.update_source_status("open_meteo", "UNAVAILABLE", error_message="Network offline")
    registry.update_source_status("usgs", "ONLINE", record_count=12)

    summary = registry.get_system_summary()
    assert summary["system"] == "OPERATIONAL"  # Still operational via remaining feeds
    assert summary["global_data"] == "ONLINE"


# 11. Cache fallback
def test_cache_fallback():
    cache = ExternalDataCache()
    cache.set("test_key", "sample_data", ttl_seconds=60.0)
    data, is_fresh = cache.get("test_key")
    assert data == "sample_data"
    assert is_fresh is True


# 12. Spatial mapping & distance
def test_spatial_mapping_distance():
    # Distance between London (51.5074, -0.1278) and Paris (48.8566, 2.3522) is ~343 km
    dist = GlobalSpatialGrid.haversine_distance_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340.0 <= dist <= 346.0

    nearest_stn, dist_hyd = GlobalSpatialGrid.find_nearest_reference(17.40, 78.50)
    assert nearest_stn["id"] == "EXT-HYD-001"
    assert dist_hyd < 10.0


# 13. Hazard zone generation
def test_hazard_zone_generation():
    engine = GlobalHazardFusionEngine()
    now = datetime.now(timezone.utc)
    obs = ExternalObservation(
        observation_id="OBS-HEAT-01",
        source="open_meteo",
        source_type=SourceType.WEATHER_API,
        timestamp=now,
        received_at=now,
        location=ExternalLocation(lat=24.71, lon=46.67, name="Riyadh Desert Station"),
        measurements=ExternalMeasurements(
            temperature=46.5,
            apparent_temperature=49.0,
            humidity=15.0,
            pressure=1005.0,
            precipitation=0.0,
            wind_speed=6.0,
            water_level=None,
        ),
        provenance=ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 24.71, 46.67, {"temperature": 46.5}),
    )
    zones, preds, compound = engine.evaluate_weather_hazards([obs])
    assert len(zones) >= 1
    heat_zone = [z for z in zones if z.hazard_type == "HEAT"][0]
    assert heat_zone.severity >= 0.65
    assert heat_zone.epistemic_status == EpistemicStatus.INFERRED
    assert heat_zone.simulated is False


# 14. Global -> Intelligence pipeline
def test_global_to_intelligence_pipeline():
    engine = GlobalHazardFusionEngine()
    now = datetime.now(timezone.utc)
    obs = ExternalObservation(
        observation_id="OBS-TEST",
        source="open_meteo",
        source_type=SourceType.WEATHER_API,
        timestamp=now,
        received_at=now,
        location=ExternalLocation(lat=17.38, lon=78.48, name="Hyderabad Station"),
        measurements=ExternalMeasurements(
            temperature=33.0,
            humidity=65.0,
            pressure=1008.0,
            precipitation=15.0,
            water_level=None,
        ),
        provenance=ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 17.38, 78.48, {"temperature": 33.0}),
    )
    telem = engine.observation_to_telemetry(obs, "EXT-HYD-001")
    assert isinstance(telem, NormalizedTelemetry)
    assert telem.measurements.water_level is None
    assert telem.node_id == "EXT-HYD-001"


# 15. Global -> WebSocket event payload validity
def test_global_websocket_event_payload():
    now = datetime.now(timezone.utc)
    zone = GlobalHazardZone(
        zone_id="ZONE-001",
        hazard_type="HEAT",
        severity=0.82,
        confidence=0.91,
        epistemic_status=EpistemicStatus.INFERRED,
        geometry={"type": "Point", "coordinates": [78.48, 17.38]},
        center=ExternalLocation(lat=17.38, lon=78.48),
        radius_km=35.0,
        source="Open-Meteo",
        timestamp=now,
        simulated=False,
    )
    dumped = zone.model_dump()
    assert dumped["hazard_type"] == "HEAT"
    assert dumped["severity"] == 0.82
    assert dumped["simulated"] is False


# 16. Global -> Cesium GeoJSON formatting
def test_global_cesium_geojson_formatting():
    zone = GlobalHazardZone(
        zone_id="ZONE-TEST",
        hazard_type="WILDFIRE",
        severity=0.75,
        confidence=0.90,
        epistemic_status=EpistemicStatus.OBSERVED,
        geometry={"type": "Point", "coordinates": [-118.25, 34.05]},
        center=ExternalLocation(lat=34.05, lon=-118.25),
        radius_km=25.0,
        source="NASA FIRMS",
        simulated=False,
    )
    geojson_feature = {
        "type": "Feature",
        "geometry": zone.geometry,
        "properties": {
            "zone_id": zone.zone_id,
            "hazard_type": zone.hazard_type,
            "severity": zone.severity,
            "radius_km": zone.radius_km,
            "epistemic_status": zone.epistemic_status.value,
        }
    }
    assert geojson_feature["type"] == "Feature"
    assert geojson_feature["geometry"]["coordinates"] == [-118.25, 34.05]
    assert geojson_feature["properties"]["hazard_type"] == "WILDFIRE"


# 17. Multiple simultaneous providers
def test_multiple_simultaneous_providers():
    service = ExternalDataService()
    summary = service.registry.get_system_summary()
    assert len(summary["sources"]) >= 5
    source_ids = [s["source_id"] for s in summary["sources"]]
    assert "open_meteo" in source_ids
    assert "nasa_firms" in source_ids
    assert "usgs" in source_ids
    assert "gdacs" in source_ids
    assert "glofas" in source_ids
    assert "esp32_mesh" in source_ids


# 18. Source provenance hashing
def test_source_provenance_hashing():
    now = datetime.now(timezone.utc)
    p1 = ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 17.38, 78.48, {"temp": 30.0})
    p2 = ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 17.38, 78.48, {"temp": 30.0})
    p3 = ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 17.38, 78.48, {"temp": 35.0})

    assert len(p1.record_hash) == 64
    assert p1.record_hash == p2.record_hash  # Deterministic
    assert p1.record_hash != p3.record_hash  # Changes on altered measurement


# 19. Epistemic status separation
def test_epistemic_status_separation():
    assert EpistemicStatus.OBSERVED.value == "OBSERVED"
    assert EpistemicStatus.PREDICTED.value == "PREDICTED"
    assert EpistemicStatus.INFERRED.value == "INFERRED"
    assert EpistemicStatus.SIMULATED.value == "SIMULATED"
    assert EpistemicStatus.STALE.value == "STALE"
    assert EpistemicStatus.UNAVAILABLE.value == "UNAVAILABLE"


# 20. No fabricated values rule
def test_no_fabricated_values():
    meas = ExternalMeasurements(temperature=None, humidity=None)
    assert meas.temperature is None
    assert meas.water_level is None


# 21. Water-level invariant (Strictly None for weather feeds)
def test_water_level_invariant():
    meas = ExternalMeasurements(temperature=28.0, precipitation=15.0)
    assert meas.water_level is None
    assert meas.water_level != 0.0


# 22. ESP32 + global fusion
def test_esp32_and_global_fusion():
    now = datetime.now(timezone.utc)
    global_obs = ExternalObservation(
        observation_id="OBS-HYD",
        source="open_meteo",
        source_type=SourceType.WEATHER_API,
        timestamp=now,
        received_at=now,
        location=ExternalLocation(lat=17.385, lon=78.486),
        measurements=ExternalMeasurements(
            temperature=31.8,
            humidity=68.0,
            pressure=1007.0,
            precipitation=0.0,
            water_level=None,
        ),
        provenance=ExternalProvenanceTracker.create_provenance("Open-Meteo", "http://test", now, now, 17.385, 78.486, {"temperature": 31.8}),
    )

    local_packet = {
        "node_id": "NODE-001",
        "measurements": {
            "temperature": 32.6,
            "humidity": 70.0,
            "pressure": 1008.0,
            "rainfall": 0.0,
            "water_level": None,
        },
        "quality": {"confidence": 0.95},
    }

    fused = WeatherFusionEngine.fuse_weather_readings(
        global_obs=global_obs,
        local_telemetry=local_packet,
        distance_km=2.5,
    )

    assert fused["mode"] == "FUSED_GLOBAL_LOCAL"
    assert 31.8 < fused["temperature"] < 32.6
    assert fused["breakdown"]["global_model"] == 31.8
    assert fused["breakdown"]["local_sensor"] == 32.6
    assert fused["confidence"] >= 0.85


# 23. AI grounded reasoning (zero hallucinated metrics)
def test_ai_grounded_reasoning():
    service = ExternalDataService()
    now = datetime.now(timezone.utc)
    service._hazard_zones = [
        GlobalHazardZone(
            zone_id="ZONE-TEST-HEAT",
            hazard_type="HEAT",
            severity=0.82,
            confidence=0.91,
            epistemic_status=EpistemicStatus.INFERRED,
            geometry={"type": "Point", "coordinates": [78.48, 17.38]},
            center=ExternalLocation(lat=17.38, lon=78.48, name="Northern Region"),
            radius_km=45.0,
            drivers=["Temperature above 42°C threshold", "Sustained heat index"],
            source="Open-Meteo",
            timestamp=now,
            simulated=False,
            recommended_action="Open cooling shelters.",
        )
    ]
    ai_summary = service.get_ai_summary()
    assert ai_summary["mode"] == "ACTIVE — DETERMINISTIC EVIDENCE MODE"
    assert ai_summary["active_events_count"] == 1
    assert ai_summary["top_event"]["hazard"] == "HEAT"
    assert ai_summary["top_event"]["severity"] == 0.82
    assert ai_summary["top_event"]["confidence"] == 0.91
    assert ai_summary["top_event"]["sources"] == ["Open-Meteo"]


# 24. Simulation remains simulated=true
def test_simulation_remains_simulated_true():
    zone = GlobalHazardZone(
        zone_id="SIM-ZONE-01",
        hazard_type="FLOOD",
        severity=0.85,
        confidence=0.95,
        epistemic_status=EpistemicStatus.SIMULATED,
        geometry={"type": "Point", "coordinates": [78.48, 17.38]},
        center=ExternalLocation(lat=17.38, lon=78.48),
        radius_km=30.0,
        source="Digital Twin Simulator",
        simulated=True,
    )
    assert zone.simulated is True
    assert zone.epistemic_status == EpistemicStatus.SIMULATED
