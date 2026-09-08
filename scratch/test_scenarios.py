import urllib.request
import json
import time

S1_BASE = "http://localhost:4173"

scenarios = [
    ("Rain +20%", "SCN-RAIN-20"),
    ("Rain +40%", "SCN-RAIN-40"),
    ("Rain +60%", "SCN-RAIN-60"),
    ("Extreme Heat", "SCN-EXTREME-HEAT"),
    ("Drainage Failure", "SCN-DRAINAGE-FAIL"),
    ("Road Accessibility -50%", "SCN-ROAD-DEGRADE"),
    ("Flood + Heat", "SCN-FLOOD-HEAT"),
]

print("Executing all 7 Digital Twin What-If scenarios:")
for name, scn_id in scenarios:
    data = json.dumps({"scenario_id": scn_id}).encode("utf-8")
    req = urllib.request.Request(f"{S1_BASE}/api/simulation/run", data=data, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        dt = (time.perf_counter() - t0) * 1000
        sim = body.get("simulation") or body.get("result") or {}
        assert sim.get("simulated") is True, f"Scenario {scn_id} missing simulated=True flag!"
        print(f"  [{scn_id:18s}] HTTP {resp.status} ({dt:5.1f}ms) | simulated={sim.get('simulated')} | hazards={len(sim.get('hazards', []))} | cascades={len(sim.get('compound_events', []))} | evacuation={len(sim.get('evacuation_routes', []))}")
print("ALL 7 SCENARIOS VERIFIED SUCCESSFULLY!")
