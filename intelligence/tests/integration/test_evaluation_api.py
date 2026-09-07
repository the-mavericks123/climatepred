"""
Integration tests for Phase 10 Evaluation endpoints in FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from intelligence.app.main import app

client = TestClient(app)


def test_post_evaluation_run_default_flood():
    payload = {
        "model_version": "flood-v1",
        "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
    }
    res = client.post("/api/v1/evaluation/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    rep = data["report"]
    assert rep["status"] == "COMPLETED"
    assert rep["sample_count"] == 100
    assert rep["metrics"]["accuracy"] is not None
    assert rep["metrics"]["f1_score"] is not None
    assert len(rep["provenance_hash"]) == 64


def test_get_evaluation_report_by_id():
    # Run evaluation
    run_res = client.post("/api/v1/evaluation/run", json={"model_version": "heat-v1", "dataset_id": "EVAL-HEAT-SYNTHETIC-001"})
    assert run_res.status_code == 200
    eval_id = run_res.json()["report"]["evaluation_id"]

    # GET report
    get_res = client.get(f"/api/v1/evaluation/{eval_id}")
    assert get_res.status_code == 200
    assert get_res.json()["report"]["evaluation_id"] == eval_id


def test_get_model_evaluation_shortcut():
    res = client.get("/api/v1/models/flood-v1/evaluation")
    assert res.status_code == 200
    assert res.json()["report"]["model_version"] == "flood-v1"


def test_post_models_compare():
    payload = {
        "baseline_model_version": "flood-v1",
        "candidate_model_version": "flood-v1",
        "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
    }
    res = client.post("/api/v1/models/compare", json=payload)
    assert res.status_code == 200
    comp = res.json()["comparison"]
    assert comp["regression_detected"] is False
    assert comp["metric_deltas"]["f1_score"] == 0.0


def test_post_drift_evaluate():
    payload = {
        "feature_name": "water_level_m",
        "baseline_samples": [2.0, 3.0, 4.0, 5.0, 6.0] * 10,
        "current_samples": [8.0, 9.0, 10.0, 11.0, 12.0] * 10,
        "method": "PSI",
    }
    res = client.post("/api/v1/drift/evaluate", json=payload)
    assert res.status_code == 200
    report = res.json()["report"]
    assert report["drift_detected"] is True
    assert report["severity"] == "SIGNIFICANT"
