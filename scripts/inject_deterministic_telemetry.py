"""
Deterministic Telemetry Ingestion Script for Climate Eye View
Seeds canonical nodes NODE-001 through NODE-006 into the live pipeline.
Maintains invariant: water_level is null (no physical sensor).
"""

import urllib.request
import json
from datetime import datetime, timezone

NODES = [
    {
        "node_id": "NODE-001",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "temperature": 32.5,
        "humidity": 78.0,
        "pressure": 1008.0,
        "rainfall": 15.0,
        "soil_moisture": 65.0,
        "water_level": None,
        "air_quality": 42.0,
        "battery": 95.0,
    },
    {
        "node_id": "NODE-002",
        "latitude": 13.0600,
        "longitude": 80.2500,
        "temperature": 31.0,
        "humidity": 82.0,
        "pressure": 1006.5,
        "rainfall": 45.0,
        "soil_moisture": 85.0,
        "water_level": None,
        "air_quality": 55.0,
        "battery": 91.0,
    },
    {
        "node_id": "NODE-003",
        "latitude": 13.0400,
        "longitude": 80.2100,
        "temperature": 29.5,
        "humidity": 88.0,
        "pressure": 1004.0,
        "rainfall": 65.0,
        "soil_moisture": 90.0,
        "water_level": None,
        "air_quality": 35.0,
        "battery": 88.0,
    },
    {
        "node_id": "NODE-004",
        "latitude": 13.0200,
        "longitude": 80.1800,
        "temperature": 28.0,
        "humidity": 92.0,
        "pressure": 1002.0,
        "rainfall": 85.0,
        "soil_moisture": 95.0,
        "water_level": None,
        "air_quality": 30.0,
        "battery": 82.0,
    },
    {
        "node_id": "NODE-005",
        "latitude": 13.1000,
        "longitude": 80.2200,
        "temperature": 30.0,
        "humidity": 80.0,
        "pressure": 1007.0,
        "rainfall": 25.0,
        "soil_moisture": 70.0,
        "water_level": None,
        "air_quality": 48.0,
        "battery": 94.0,
    },
    {
        "node_id": "NODE-006",
        "latitude": 13.1200,
        "longitude": 80.2900,
        "temperature": 33.0,
        "humidity": 75.0,
        "pressure": 1009.0,
        "rainfall": 5.0,
        "soil_moisture": 50.0,
        "water_level": None,
        "air_quality": 60.0,
        "battery": 97.0,
    },
]

def inject_telemetry(base_url="http://localhost:4173"):
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    success_count = 0
    print(f"Injecting 6 canonical telemetry packets into {base_url}/api/telemetry...")

    for node in NODES:
        payload = {
            "schema_version": "1.0",
            "node_id": node["node_id"],
            "timestamp": now_iso,
            "latitude": node["latitude"],
            "longitude": node["longitude"],
            "temperature": node["temperature"],
            "humidity": node["humidity"],
            "pressure": node["pressure"],
            "rainfall": node["rainfall"],
            "soil_moisture": node["soil_moisture"],
            "water_level": node["water_level"],
            "air_quality": node["air_quality"],
            "battery": node["battery"],
        }

        req = urllib.request.Request(
            f"{base_url}/api/telemetry",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("valid") or data.get("success"):
                    print(f"  [OK] {node['node_id']}: accepted, provenance hash: {data.get('provenance', {}).get('record_hash', '')[:16]}...")
                    success_count += 1
                else:
                    print(f"  [FAIL] {node['node_id']}: {data}")
        except Exception as ex:
            print(f"  [ERR] {node['node_id']}: {ex}")

    print(f"Ingestion complete: {success_count}/{len(NODES)} nodes successfully ingested.")
    return success_count

if __name__ == "__main__":
    inject_telemetry()
