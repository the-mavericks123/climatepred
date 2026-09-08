"""
Runtime Acceptance Test Script
Validates all runtime services, endpoints, data flow, failure modes, and scenario execution.
"""

import urllib.request
import urllib.error
import json
import time

S2_BASE = "http://127.0.0.1:8000"
S1_BASE = "http://localhost:4173"

def http_get(url):
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")
            dt = (time.perf_counter() - t0) * 1000
            return resp.status, json.loads(data), dt
    except urllib.error.HTTPError as e:
        dt = (time.perf_counter() - t0) * 1000
        try:
            body = json.loads(e.read().decode("utf-8"))
        except:
            body = e.reason
        return e.code, body, dt
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return 0, str(e), dt

def http_post(url, payload):
    t0 = time.perf_counter()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            dt = (time.perf_counter() - t0) * 1000
            return resp.status, json.loads(body), dt
    except urllib.error.HTTPError as e:
        dt = (time.perf_counter() - t0) * 1000
        try:
            body = json.loads(e.read().decode("utf-8"))
        except:
            body = e.reason
        return e.code, body, dt
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return 0, str(e), dt

print("=" * 60)
print("1. HEALTH CHECKS")
print("=" * 60)

s2_h_code, s2_h_body, s2_h_lat = http_get(f"{S2_BASE}/api/v1/health")
print(f"S2 Health: HTTP {s2_h_code} in {s2_h_lat:.1f}ms -> {s2_h_body}")

s1_h_code, s1_h_body, s1_h_lat = http_get(f"{S1_BASE}/api/climate/health")
print(f"S1 Health: HTTP {s1_h_code} in {s1_h_lat:.1f}ms -> {s1_h_body}")

print("\n" + "=" * 60)
print("2. S1 API GATEWAY -> S2 INTELLIGENCE ENDPOINTS")
print("=" * 60)

endpoints = [
    ("/api/nodes", "GET", None),
    ("/api/telemetry", "GET", None),
    ("/api/hazards/current", "GET", None),
    ("/api/hazards/predictions", "GET", None),
    ("/api/compound", "GET", None),
    ("/api/vulnerability", "GET", None),
    ("/api/evacuation", "GET", None),
    ("/api/response", "GET", None),
    ("/api/simulation/scenarios", "GET", None),
]

for path, method, body in endpoints:
    url = f"{S1_BASE}{path}"
    code, resp_body, lat = http_get(url)
    if isinstance(resp_body, dict):
        success = resp_body.get("success", resp_body.get("ok"))
    else:
        success = f"Error/Raw: {resp_body}"
    print(f"S1 Gateway {path:30s} -> HTTP {code} ({lat:5.1f}ms) | success={success}")

print("\n" + "=" * 60)
print("3. DIGITAL TWIN SIMULATION: Rain +40%")
print("=" * 60)

sim_code, sim_body, sim_lat = http_post(f"{S1_BASE}/api/simulation/run", {"scenario_id": "SCN-RAIN-40"})
print(f"Simulation SCN-RAIN-40 -> HTTP {sim_code} ({sim_lat:5.1f}ms)")
if sim_code == 200:
    sim_data = sim_body.get("simulation") or sim_body.get("result") or {}
    print(f"  Simulation ID: {sim_data.get('simulation_id')}")
    print(f"  Scenario: {sim_data.get('scenario_id')}")
    print(f"  Simulated Flag: {sim_data.get('simulated')}")
    print(f"  Hazards: {len(sim_data.get('hazards', []))}")
    print(f"  Cascades: {len(sim_data.get('compound_events', []))}")
    print(f"  Evacuation Routes: {len(sim_data.get('evacuation_routes', []))}")
    print(f"  Response Actions: {len(sim_data.get('response_plan', {}).get('actions', []))}")
else:
    print(f"  Error: {sim_body}")
