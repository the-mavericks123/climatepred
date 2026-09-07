"""Generator for Phase 3 deterministic prediction fixtures.
Creates time-series scenarios under shared/fixtures/ and intelligence/tests/fixtures/.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHARED_DIR = Path("shared/fixtures")
INTEL_DIR = Path("intelligence/tests/fixtures")
SHARED_DIR.mkdir(parents=True, exist_ok=True)
INTEL_DIR.mkdir(parents=True, exist_ok=True)


def make_packet(
    node_id: str,
    ts: datetime,
    temp: float = 25.0,
    humidity: float = 50.0,
    rainfall: float = 0.0,
    water_level: float = 1.0,
    soil_moisture: float = 40.0,
    pressure: float = 1013.0,
    air_quality: float = 45.0,
    lat: float = 17.385,
    lon: float = 78.4867,
    elevation: float = 500.0,
    confidence: float = 0.98,
    anomaly: float = 0.0,
    flags: list = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "node_id": node_id,
        "timestamp": ts.isoformat().replace("+00:00", "Z"),
        "location": {"lat": lat, "lon": lon, "elevation": elevation},
        "measurements": {
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "pressure": round(pressure, 2),
            "rainfall": round(rainfall, 2),
            "soil_moisture": round(soil_moisture, 2),
            "water_level": round(water_level, 2),
            "air_quality": round(air_quality, 2),
        },
        "quality": {
            "valid": True,
            "source": "ESP32",
            "received_at": (ts + timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
            "confidence": confidence,
            "anomaly_score": anomaly,
            "flags": flags or [],
        },
    }


def generate_all_fixtures():
    base_t = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    # 1. Stable Conditions (temperature ~30C, rainfall 0, water 1.2m, soil 45%)
    stable_history = [
        make_packet("STATION-STABLE", base_t - timedelta(minutes=10 * i), temp=30.0, humidity=50.0, water_level=1.2, soil_moisture=45.0)
        for i in range(5, 0, -1)
    ]
    stable_curr = make_packet("STATION-STABLE", base_t, temp=30.1, humidity=49.9, water_level=1.21, soil_moisture=45.0)
    save("prediction_stable.json", {"telemetry": stable_curr, "history": stable_history, "horizons_minutes": [30, 60, 360]})

    # 2. Heat Scenarios:
    # Rapidly increasing temperature (+1.5C per 10m)
    heat_history = [
        make_packet("STATION-HEAT", base_t - timedelta(minutes=10 * i), temp=32.0 + (5 - i) * 1.5, humidity=60.0)
        for i in range(5, 0, -1)
    ]
    heat_curr = make_packet("STATION-HEAT", base_t, temp=40.0, humidity=58.0)
    save("prediction_heat_30m.json", {"telemetry": heat_curr, "history": heat_history, "hazards": ["heat"], "horizons_minutes": [30]})
    save("prediction_heat_1h.json", {"telemetry": heat_curr, "history": heat_history, "hazards": ["heat"], "horizons_minutes": [60]})
    save("prediction_heat_6h.json", {"telemetry": heat_curr, "history": heat_history, "hazards": ["heat"], "horizons_minutes": [360]})

    # 3. Flood Scenarios:
    # Rising rainfall (10 -> 60 mm/hr), water level (2.0 -> 8.0 m), soil moisture (60% -> 90%)
    flood_history = [
        make_packet(
            "STATION-FLOOD",
            base_t - timedelta(minutes=10 * i),
            temp=24.0,
            rainfall=10.0 + (5 - i) * 10.0,
            water_level=2.0 + (5 - i) * 1.2,
            soil_moisture=60.0 + (5 - i) * 6.0,
        )
        for i in range(5, 0, -1)
    ]
    flood_curr = make_packet("STATION-FLOOD", base_t, temp=23.5, rainfall=65.0, water_level=8.5, soil_moisture=92.0)
    save("prediction_flood_30m.json", {"telemetry": flood_curr, "history": flood_history, "hazards": ["flood"], "horizons_minutes": [30]})
    save("prediction_flood_1h.json", {"telemetry": flood_curr, "history": flood_history, "hazards": ["flood"], "horizons_minutes": [60]})
    save("prediction_flood_6h.json", {"telemetry": flood_curr, "history": flood_history, "hazards": ["flood"], "horizons_minutes": [360]})

    # 4. Drought Scenarios:
    # Drying soil (35% -> 15%), rising temp (32C -> 42C), dropping humidity (40% -> 18%)
    drought_history = [
        make_packet(
            "STATION-DROUGHT",
            base_t - timedelta(minutes=10 * i),
            temp=32.0 + (5 - i) * 2.0,
            humidity=40.0 - (5 - i) * 4.0,
            soil_moisture=35.0 - (5 - i) * 4.0,
        )
        for i in range(5, 0, -1)
    ]
    drought_curr = make_packet("STATION-DROUGHT", base_t, temp=43.0, humidity=16.0, soil_moisture=13.0)
    save("prediction_drought_30m.json", {"telemetry": drought_curr, "history": drought_history, "hazards": ["drought"], "horizons_minutes": [30]})
    save("prediction_drought_1h.json", {"telemetry": drought_curr, "history": drought_history, "hazards": ["drought"], "horizons_minutes": [60]})
    save("prediction_drought_6h.json", {"telemetry": drought_curr, "history": drought_history, "hazards": ["drought"], "horizons_minutes": [360]})

    # 5. Increasing Trend Scenario
    save("prediction_increasing_trend.json", {"telemetry": flood_curr, "history": flood_history, "hazards": ["flood"], "horizons_minutes": [30, 60, 360]})

    # 6. Insufficient History Scenario (only 1 historical observation)
    insuf_history = [make_packet("STATION-INSUF", base_t - timedelta(minutes=15), temp=31.0, humidity=45.0)]
    insuf_curr = make_packet("STATION-INSUF", base_t, temp=31.2, humidity=44.8)
    save("prediction_insufficient_history.json", {"telemetry": insuf_curr, "history": insuf_history, "horizons_minutes": [30, 60, 360]})

    # 7. Future Leakage Test Scenario (includes observations with timestamp > base_t)
    leakage_history = list(heat_history) + [
        # Injected future data (10 and 20 mins into future)
        make_packet("STATION-HEAT", base_t + timedelta(minutes=10), temp=60.0, humidity=90.0),
        make_packet("STATION-HEAT", base_t + timedelta(minutes=20), temp=65.0, humidity=95.0),
    ]
    save("prediction_future_leakage.json", {"telemetry": heat_curr, "history": leakage_history, "hazards": ["heat"], "horizons_minutes": [30]})

    print("All fixtures generated successfully.")


def save(filename: str, data: dict):
    for dir_path in [SHARED_DIR, INTEL_DIR]:
        with open(dir_path / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    generate_all_fixtures()
