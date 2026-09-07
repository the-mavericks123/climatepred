"""
Integration tests for Phase 10 Calibration endpoints in FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from intelligence.app.main import app

client = TestClient(app)


def test_post_calibration_run_and_get():
    payload = {
        "model_version": "flood-v1",
        "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        "method": "isotonic",
    }
    res = client.post("/api/v1/calibration/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    rep = data["report"]
    assert rep["status"] == "CALIBRATED"
    assert rep["sample_count"] == 100
    assert len(rep["reliability_bins"]) == 10
    cal_id = rep["calibration_id"]

    # GET report
    get_res = client.get(f"/api/v1/calibration/{cal_id}")
    assert get_res.status_code == 200
    assert get_res.json()["report"]["calibration_id"] == cal_id


def test_calibration_unknown_dataset():
    payload = {
        "model_version": "flood-v1",
        "dataset_id": "NONEXISTENT-DATASET",
    }
    res = client.post("/api/v1/calibration/run", json=payload)
    assert res.status_code == 404
