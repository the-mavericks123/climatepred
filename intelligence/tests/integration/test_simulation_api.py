"""Integration tests for Phase 7: Digital Twin & Scenario Simulation Engine endpoints.
Validates:
  - GET /api/v1/simulation/scenarios
  - POST /api/v1/simulation/run
  - GET /api/v1/simulation/{simulation_id}
  - Error responses (validation errors, stale data, unsupported scenario, not found).
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.simulation.types import ScenarioParameters

client = TestClient(app)


class TestSimulationAPI:
    """Verifies HTTP status codes, schema stability, and engine routing."""

    def test_get_scenarios_catalog(self):
        res = client.get("/api/v1/simulation/scenarios")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["count"] >= 7
        scenario_ids = [s["scenario_id"] for s in data["scenarios"]]
        assert "SCN-RAIN-20" in scenario_ids
        assert "SCN-RAIN-40" in scenario_ids
        assert "SCN-RAIN-60" in scenario_ids
        assert "SCN-EXTREME-HEAT" in scenario_ids
        assert "SCN-DRAINAGE-FAIL" in scenario_ids
        assert "SCN-ROAD-DEGRADE" in scenario_ids
        assert "SCN-FLOOD-HEAT" in scenario_ids

    def test_run_simulation_default_base_state(self):
        payload = {
            "scenario_id": "SCN-RAIN-20",
            "base_state": "current",
        }
        res = client.post("/api/v1/simulation/run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        sim = data["simulation"]
        assert sim["simulated"] is True
        assert sim["scenario_id"] == "SCN-RAIN-20"
        assert len(sim["simulation_id"]) > 0
        assert len(sim["provenance_hash"]) == 64
        assert "hazard_change" in sim["summary"]

        # Verify cached retrieval
        sim_id = sim["simulation_id"]
        get_res = client.get(f"/api/v1/simulation/{sim_id}")
        assert get_res.status_code == 200
        cached_data = get_res.json()
        assert cached_data["success"] is True
        assert cached_data["simulation"]["simulation_id"] == sim_id

    def test_run_simulation_with_parameter_overrides(self):
        payload = {
            "scenario_id": "SCN-EXTREME-HEAT",
            "base_state": "current",
            "changes": {
                "temperature_delta": 4.5
            }
        }
        res = client.post("/api/v1/simulation/run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["simulation"]["parameters"]["temperature_delta"] == 4.5

    def test_run_simulation_invalid_scenario_id(self):
        payload = {
            "scenario_id": "SCN-INVALID-SCENARIO-XYZ",
            "base_state": "current",
        }
        res = client.post("/api/v1/simulation/run", json=payload)
        assert res.status_code == 422
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_run_simulation_invalid_parameter_range(self):
        payload = {
            "scenario_id": "SCN-RAIN-20",
            "changes": {
                "rainfall_multiplier": -1.5
            }
        }
        res = client.post("/api/v1/simulation/run", json=payload)
        assert res.status_code == 422
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_run_simulation_missing_scenario_id(self):
        payload = {
            "changes": {"rainfall_multiplier": 1.2}
        }
        res = client.post("/api/v1/simulation/run", json=payload)
        assert res.status_code == 422
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_get_simulation_not_found(self):
        res = client.get("/api/v1/simulation/SIM-NONEXISTENT-ID")
        assert res.status_code == 404
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
