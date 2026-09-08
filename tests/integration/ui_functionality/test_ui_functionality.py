"""
Climate Eye — UI Functionality Integration Tests
Validates all backend intelligence APIs backing the UI buttons, controls, and features:
- Sidebar navigation & hazard toggle
- Hazard selection & retrieval
- Prediction timeline (+30m, +60m, +6h)
- Simulation presets (RAIN-20, RAIN-40, RAIN-60, EXTREME-HEAT, DRAINAGE-FAIL, ROAD-DEGRADE, FLOOD-HEAT)
- Simulation sliders & execution (POST /api/v1/simulation/run)
- Simulation propagation into downstream models (hazards, cascade, vulnerability, evacuation, response)
- Compound cascade graph retrieval
- Human impact & vulnerability zones
- Evacuation routes & shelter allocations
- AI queries & action buttons (POST /api/v1/global/ai-query)
- Live data sources status (GET /api/v1/global/sources)
- Regional search & coordinate intelligence (GET /api/v1/global/region)
- ESP32 disconnected state graceful handling
"""

import pytest
from fastapi.testclient import TestClient
from intelligence.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# 1. System Health & Core Modes
# ---------------------------------------------------------------------------
def test_system_health_and_subsystems(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "climate-intelligence"


# ---------------------------------------------------------------------------
# 2. Hazards Engine & Filtering
# ---------------------------------------------------------------------------
def test_hazards_retrieval_and_filtering(client):
    res = client.get("/api/v1/hazards/current")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "hazards" in data
    assert isinstance(data["hazards"], list)

    # Filtered hazard query
    res_flood = client.get("/api/v1/global/hazards?hazard_type=FLOOD")
    assert res_flood.status_code == 200
    assert "hazards" in res_flood.json()


# ---------------------------------------------------------------------------
# 3. Predictions Timeline
# ---------------------------------------------------------------------------
def test_prediction_timeline_horizons(client):
    res = client.get("/api/v1/hazards/predictions")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "predictions" in data

    # Test regional prediction horizons
    res_reg = client.get("/api/v1/global/region?name=Hyderabad&lat=17.385&lon=78.4867")
    assert res_reg.status_code == 200
    reg = res_reg.json()["region"]
    assert "predictions" in reg
    assert "current" in reg["predictions"]
    assert "horizon_30m" in reg["predictions"]
    assert "horizon_60m" in reg["predictions"]
    assert "horizon_6h" in reg["predictions"]


# ---------------------------------------------------------------------------
# 4. Compound Cascade Engine
# ---------------------------------------------------------------------------
def test_compound_cascade_graph(client):
    res = client.get("/api/v1/compound")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "events" in data
    assert isinstance(data["events"], list)
    if data["events"]:
        event = data["events"][0]
        assert "chain" in event or "contributing_states" in event


# ---------------------------------------------------------------------------
# 5. Human Impact & Vulnerability Zones
# ---------------------------------------------------------------------------
def test_vulnerability_human_impact(client):
    res = client.get("/api/v1/vulnerability")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "assessments" in data
    assert isinstance(data["assessments"], list)
    if data["assessments"]:
        assessment = data["assessments"][0]
        assert "population_exposed" in assessment or "human_impact" in assessment


# ---------------------------------------------------------------------------
# 6. Evacuation Routing & Shelters
# ---------------------------------------------------------------------------
def test_evacuation_routes_and_shelters(client):
    res = client.get("/api/v1/evacuation")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    if data["recommendations"]:
        rec = data["recommendations"][0]
        assert "destination" in rec or "route" in rec


# ---------------------------------------------------------------------------
# 7. Simulation Scenarios Catalog & Execution
# ---------------------------------------------------------------------------
def test_simulation_scenarios_catalog(client):
    res = client.get("/api/v1/simulation/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] >= 6
    ids = [s["scenario_id"] for s in data["scenarios"]]
    assert "SCN-RAIN-20" in ids
    assert "SCN-RAIN-40" in ids
    assert "SCN-RAIN-60" in ids
    assert "SCN-EXTREME-HEAT" in ids
    assert "SCN-DRAINAGE-FAIL" in ids
    assert "SCN-ROAD-DEGRADE" in ids


def test_simulation_execution_and_propagation(client):
    payload = {
        "scenario_id": "SCN-RAIN-40",
        "base_state": "current",
        "changes": {
            "rainfall_multiplier": 1.4,
            "temperature_delta": 2.0,
            "drainage_failure_severity": 0.5,
            "road_accessibility_reduction": 0.5,
        },
    }
    res = client.post("/api/v1/simulation/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    sim = data["simulation"]
    assert sim["scenario_id"] == "SCN-RAIN-40"
    assert sim["simulated"] is True

    # Verify propagation into downstream models
    assert "hazards" in sim
    assert "predictions" in sim
    assert "compound_events" in sim
    assert "vulnerability_zones" in sim
    assert "evacuation_routes" in sim
    assert "response_plan" in sim

    # Verify simulation-derived tags
    for h in sim["hazards"]:
        assert h["simulated"] is True
    for p in sim["predictions"]:
        assert p["simulated"] is True


# ---------------------------------------------------------------------------
# 8. AI Query & Grounded Directives
# ---------------------------------------------------------------------------
def test_ai_query_with_string_and_dict_region(client):
    # Test with string region
    res_str = client.post(
        "/api/v1/global/ai-query",
        json={"question": "What is happening in this region?", "region": "Hyderabad"},
    )
    assert res_str.status_code == 200
    data_str = res_str.json()
    assert data_str["success"] is True
    assert "answer" in data_str
    assert "headline" in data_str["answer"]
    assert "actions" in data_str["answer"]
    assert "evidence_ids" in data_str["answer"]

    # Test with dict region
    res_dict = client.post(
        "/api/v1/global/ai-query",
        json={
            "question": "What should emergency responders do first?",
            "region": {"name": "Hyderabad"},
        },
    )
    assert res_dict.status_code == 200
    data_dict = res_dict.json()
    assert data_dict["success"] is True
    assert len(data_dict["answer"]["actions"]) > 0
    assert len(data_dict["answer"]["evidence_ids"]) > 0


def test_ai_simulation_query(client):
    res = client.post(
        "/api/v1/global/ai-query",
        json={"question": "What happens if rainfall increases by 40%?", "region": "Hyderabad"},
    )
    assert res.status_code == 200
    answer = res.json()["answer"]
    assert "40%" in answer["headline"] or "SIMULATION" in answer["headline"]
    assert len(answer["actions"]) > 0


# ---------------------------------------------------------------------------
# 9. Live Data Sources Health
# ---------------------------------------------------------------------------
def test_live_data_sources_status(client):
    res = client.get("/api/v1/global/sources")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    summary = data["summary"]
    assert summary["global_data"] == "ONLINE"
    assert summary["intelligence"] == "ACTIVE"
    assert summary["esp32_status"] in ["NOT_CONNECTED", "ONLINE"]

    # Check provider records
    sources = {s["source_id"]: s for s in summary["sources"]}
    assert "open_meteo" in sources
    assert "nasa_firms" in sources
    assert "usgs" in sources
    assert "gdacs" in sources
    assert "glofas" in sources
    assert "esp32_mesh" in sources

    # Ensure honest statuses
    assert sources["glofas"]["status"] == "UNAVAILABLE"
    assert sources["esp32_mesh"]["status"] == "NOT_CONNECTED"


# ---------------------------------------------------------------------------
# 10. Regional Target Navigation
# ---------------------------------------------------------------------------
def test_regional_target_navigation(client):
    res = client.get("/api/v1/global/region?name=Hyderabad&lat=17.385&lon=78.4867")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    reg = data["region"]
    assert reg["name"] == "Hyderabad"
    assert reg["current_conditions"]["temperature_c"] is not None
    assert reg["evacuation"]["has_safe_route"] is True
