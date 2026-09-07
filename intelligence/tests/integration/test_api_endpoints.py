"""
Integration tests for the S2 Intelligence FastAPI endpoints.
Executes real HTTP requests against the application.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "climate-intelligence"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_readiness_endpoint(async_client):
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["ready"] is True
    assert data["registered_sources_count"] > 0


@pytest.mark.asyncio
async def test_list_sources_endpoint(async_client):
    response = await async_client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["sources"], list)
    source_ids = [s["source_id"] for s in data["sources"]]
    assert "ESP32_DEFAULT" in source_ids


@pytest.mark.asyncio
async def test_validate_telemetry_valid(async_client, normal_telemetry_dict):
    response = await async_client.post(
        "/api/v1/telemetry/validate",
        json=normal_telemetry_dict,
        headers={"X-Request-ID": "REQ-INTEGRATION-001"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["valid"] is True
    assert data["request_id"] == "REQ-INTEGRATION-001"
    assert "provenance" in data
    assert len(data["provenance"]["record_hash"]) == 64


@pytest.mark.asyncio
async def test_validate_telemetry_invalid(async_client, invalid_telemetry_dict):
    response = await async_client.post(
        "/api/v1/telemetry/validate",
        json=invalid_telemetry_dict,
        headers={"X-Request-ID": "REQ-INVALID-002"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["request_id"] == "REQ-INVALID-002"
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "errors" in data["error"]["details"]
    assert len(data["error"]["details"]["errors"]) > 0
