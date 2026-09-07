"""
Pytest configuration and shared fixtures for Climate Eye View S2 tests.
"""

import json
from pathlib import Path
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient

from intelligence.app.main import app
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.ingestion.source_registry import SourceRegistry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> Dict[str, Any]:
    file_path = FIXTURES_DIR / filename
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def normal_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("normal_telemetry.json")


@pytest.fixture
def hot_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("hot_telemetry.json")


@pytest.fixture
def heavy_rain_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("heavy_rain_telemetry.json")


@pytest.fixture
def critical_flood_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("critical_flood_telemetry.json")


@pytest.fixture
def invalid_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("invalid_telemetry.json")


@pytest.fixture
def missing_sensor_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("missing_sensor_telemetry.json")


@pytest.fixture
def stale_telemetry_dict() -> Dict[str, Any]:
    return load_fixture("stale_telemetry.json")


@pytest.fixture
def normal_telemetry(normal_telemetry_dict) -> NormalizedTelemetry:
    return NormalizedTelemetry.model_validate(normal_telemetry_dict)


@pytest.fixture
def fresh_registry() -> SourceRegistry:
    return SourceRegistry()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def reset_rate_limiter_buckets():
    """Ensures rate limiter bucket isolation between tests."""
    from intelligence.core.security.rate_limiter import default_limiter
    default_limiter.reset()
    yield
    default_limiter.reset()
