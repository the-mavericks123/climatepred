"""
Fixture generator script for Phase 4 Compound & Cascading Disaster Engine.
Generates deterministic scenario payloads under shared/fixtures/ and intelligence/tests/fixtures/.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_T = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _make_hazard(h_id: str, hazard: str, severity: float, conf: float = 0.90, dt_min: int = 0, feats: dict = None):
    return {
        "hazard_id": h_id,
        "hazard": hazard,
        "severity": severity,
        "confidence": conf,
        "classification": "HIGH" if severity >= 0.70 else "MODERATE",
        "status": "DETECTED",
        "timestamp": (BASE_T + timedelta(minutes=dt_min)).isoformat(),
        "forecast_horizon_minutes": 0,
        "location": {"lat": 25.5941, "lon": 85.1376, "elevation": 53.0},
        "features": feats or {},
        "drivers": [f"{hazard} severity {severity:.2f}"],
        "source": "model",
        "model_version": f"{hazard}-v1",
        "simulated": False,
        "provenance_hash": f"prov-{h_id.lower()}",
    }


def _make_pred(p_id: str, hazard: str, severity: float, horizon: int = 60, conf: float = 0.85, feats: dict = None):
    return {
        "prediction_id": p_id,
        "hazard": hazard,
        "prediction_time": BASE_T.isoformat(),
        "forecast_time": (BASE_T + timedelta(minutes=horizon)).isoformat(),
        "forecast_horizon_minutes": horizon,
        "severity": severity,
        "confidence": conf,
        "classification": "HIGH" if severity >= 0.70 else "MODERATE",
        "status": "DETECTED",
        "model_version": f"{hazard}-pred-v1",
        "source_hazard_id": f"HAZ-{p_id}",
        "provenance_hash": f"prov-{p_id.lower()}",
        "drivers": [f"predicted {hazard} severity {severity:.2f} at +{horizon}m"],
        "data_quality": {"sample_count": 5},
        "predicted_features": feats or {},
        "simulated": False,
    }


def generate_all_fixtures():
    fixtures = {}

    # 1. compound_heat_drought.json
    fixtures["compound_heat_drought.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-HEAT-01", "heat", 0.78, 0.92, feats={"temperature": 43.5, "humidity": 18.0}),
            _make_hazard("HAZ-DROUGHT-01", "drought", 0.82, 0.88, feats={"soil_moisture": 8.0, "temperature": 43.5}),
        ],
        "predictions": [],
    }

    # 2. compound_heat_flood.json
    fixtures["compound_heat_flood.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-HEAT-02", "heat", 0.75, 0.90, feats={"temperature": 41.0, "humidity": 70.0}),
            _make_hazard("HAZ-FLOOD-02", "flood", 0.72, 0.88, feats={"water_level": 7.5, "rainfall": 45.0}),
        ],
        "predictions": [],
    }

    # 3. cascade_rain_soil_flood.json
    fixtures["cascade_rain_soil_flood.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-FLOOD-03", "flood", 0.76, 0.92, feats={"rainfall": 85.0, "soil_moisture": 92.0, "water_level": 8.2}),
        ],
        "predictions": [],
    }

    # 4. cascade_flood_access.json
    fixtures["cascade_flood_access.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-FLOOD-04", "flood", 0.88, 0.94, feats={"water_level": 14.5, "rainfall": 90.0}),
        ],
        "predictions": [],
    }

    # 5. cascade_predicted_flood.json
    fixtures["cascade_predicted_flood.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [],
        "predictions": [
            _make_pred("PRED-FLOOD-60M", "flood", 0.84, 60, 0.88, feats={"water_level": 12.0, "rainfall": 60.0}),
        ],
    }

    # 6. compound_normal.json
    fixtures["compound_normal.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-HEAT-NORM", "heat", 0.15, 0.95, feats={"temperature": 24.0, "humidity": 50.0}),
            _make_hazard("HAZ-FLOOD-NORM", "flood", 0.10, 0.95, feats={"water_level": 1.0, "rainfall": 0.0}),
        ],
        "predictions": [],
    }

    # 7. compound_missing_data.json
    fixtures["compound_missing_data.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [],
        "predictions": [],
    }

    # 8. compound_multiple_hazards.json
    fixtures["compound_multiple_hazards.json"] = {
        "timestamp": BASE_T.isoformat(),
        "hazards": [
            _make_hazard("HAZ-HEAT-05", "heat", 0.74, 0.90, feats={"temperature": 42.0, "humidity": 15.0}),
            _make_hazard("HAZ-DROUGHT-05", "drought", 0.80, 0.88, feats={"soil_moisture": 10.0}),
        ],
        "predictions": [
            _make_pred("PRED-FLOOD-05", "flood", 0.75, 30, 0.86, feats={"water_level": 9.0, "rainfall": 75.0}),
        ],
    }

    target_dirs = [
        Path("shared/fixtures"),
        Path("intelligence/tests/fixtures"),
    ]

    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)
        for fname, content in fixtures.items():
            out_file = d / fname
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2)
            print(f"Written: {out_file}")


if __name__ == "__main__":
    generate_all_fixtures()
