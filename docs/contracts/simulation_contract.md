# Climate Eye View — Phase 7 Scenario Simulation Contract

## Overview

The Scenario Simulation Engine provides a deterministic, auditable, and isolated mechanism for asking "What happens if conditions change?" against a digital twin state representation.

---

## 1. Digital Twin State Contract

The digital twin base state snapshot encapsulates the operational and environmental state at evaluation time.

```json
{
  "base_state_id": "STATE-BASELINE-DEFAULT",
  "timestamp": "2026-09-07T12:00:00Z",
  "telemetry": { ... },
  "history": [ ... ],
  "hazards": [ ... ],
  "predictions": [ ... ],
  "compound_events": [ ... ],
  "vulnerability_zones": [ ... ],
  "population_zones": [ ... ],
  "road_network": { ... },
  "shelters": [ ... ],
  "evacuation_routes": [ ... ],
  "simulated": true,
  "provenance_hash": "8d14dc5677c6de419f6bfa20671ec10987f702edfc00fef24ef84861f7bb7c13"
}
```

---

## 2. Supported Scenarios

| Scenario ID | Name | Perturbation Formula |
| :--- | :--- | :--- |
| `SCN-RAIN-20` | Rainfall Increase (+20%) | $R' = \min(300, R \times 1.20)$ |
| `SCN-RAIN-40` | Rainfall Surge (+40%) | $R' = \min(300, R \times 1.40)$ |
| `SCN-RAIN-60` | Extreme Rainfall Deluge (+60%) | $R' = \min(300, R \times 1.60)$ |
| `SCN-EXTREME-HEAT` | Extreme Heat Wave (+5.0 °C) | $T' = \text{clamp}(-40, 65, T + 5.0)$ |
| `SCN-DRAINAGE-FAIL` | Urban Drainage Failure (50%) | $W' = W \times 1.375$, $S' = \min(100, S + 12.5)$ |
| `SCN-ROAD-DEGRADE` | Road Accessibility Degradation (50%) | $A'_e = A_e \times (1.0 - 0.50)$ |
| `SCN-FLOOD-HEAT` | Compound Flood + Heat Escalation | $R' = R \times 1.40$, $T' = T + 4.0$ |

---

## 3. REST API Endpoints

### 3.1 List Supported Scenarios
- **Method:** `GET`
- **Path:** `/api/v1/simulation/scenarios`
- **Response:**
```json
{
  "success": true,
  "count": 7,
  "scenarios": [
    {
      "scenario_id": "SCN-RAIN-20",
      "name": "Rainfall Increase (+20%)",
      "description": "Simulates a moderate 20% surge in precipitation intensity across the catchment basin.",
      "scenario_type": "RAINFALL_MULTIPLIER",
      "default_parameters": { "rainfall_multiplier": 1.2 },
      "version": "1.0",
      "simulated": true
    }
  ],
  "request_id": "REQ-12345"
}
```

### 3.2 Run Scenario Simulation
- **Method:** `POST`
- **Path:** `/api/v1/simulation/run`
- **Request Body:**
```json
{
  "scenario_id": "SCN-RAIN-20",
  "base_state": "current",
  "changes": {
    "rainfall_multiplier": 1.20
  }
}
```
- **Response:**
```json
{
  "success": true,
  "simulation": {
    "simulation_id": "SIM-SCN-RAIN-20-587B6211",
    "scenario_id": "SCN-RAIN-20",
    "scenario_version": "1.0",
    "timestamp": "2026-09-07T12:00:00Z",
    "simulated": true,
    "base_state_id": "STATE-BASELINE-DEFAULT",
    "base_state_hash": "8d14dc5677c6de419f6bfa20671ec10987f702edfc00fef24ef84861f7bb7c13",
    "parameters": { "rainfall_multiplier": 1.2 },
    "summary": {
      "hazard_change": { "primary_hazard": "flood", "max_severity_delta": 0.4056, "status": "ESCALATED" },
      "population_change": { "newly_exposed_population": 11682, "total_simulated_exposed": 11682, "evacuation_demand_shift": 9769 },
      "route_change": { "routes_severed": 0, "routes_modified": 1, "status_transitions_count": 1 },
      "infrastructure_change": { "newly_avoided_edges_count": 0, "shelters_with_demand_shift": 1 }
    },
    "comparison": {
      "metrics": [
        { "name": "flood_severity", "baseline": 0.0, "simulated": 0.4056, "delta": 0.4056, "units": "severity_index" }
      ]
    },
    "hazards": [ ... ],
    "predictions": [ ... ],
    "compound_events": [ ... ],
    "vulnerability_zones": [ ... ],
    "evacuation_routes": [ ... ],
    "confidence": 0.95,
    "provenance_hash": "587b6211..."
  },
  "request_id": "REQ-12345"
}
```

### 3.3 Get Cached Simulation Result
- **Method:** `GET`
- **Path:** `/api/v1/simulation/{simulation_id}`
- **Response:**
```json
{
  "success": true,
  "simulation": { ... },
  "request_id": "REQ-12345"
}
```

---

## 4. Error Codes & Handling

| Error Code | HTTP Status | Trigger Condition |
| :--- | :--- | :--- |
| `VALIDATION_ERROR` | 422 | Parameter value out of physical bounds, missing `scenario_id` |
| `NOT_FOUND` | 404 | Simulation ID not found or expired from cache |
| `STALE_DATA` | 409 | Base state telemetry exceeds `data_freshness_threshold_sec` (300s) |
| `SERVICE_UNAVAILABLE` | 503 | `enable_scenario_simulation` is false |
| `SIMULATION_ERROR` | 500 | Unhandled mathematical calculation error during propagation |

---

## 5. Deterministic Provenance Architecture (Forensic Remediation V2)

### 5.1 Metadata vs. Provenance Separation
To guarantee absolute determinism across processes, machines, and execution timestamps, volatile execution metadata is strictly separated from the deterministic simulation provenance payload:

- **Volatile Execution Metadata (Excluded from Hash):**
  - `simulation_id`: Ephemeral execution and cache retrieval identifier (e.g. `SIM-SCN-RAIN-20-4C55F84C`).
  - `execution_timestamp` / `timestamp`: Wall-clock evaluation time of the simulation request.
  - `request_id`: Tracing identifier for HTTP requests.
  - `execution_duration`: Elapsed compute time in milliseconds.

- **Deterministic Simulation Provenance (Hashed Payload):**
  The provenance hash `SHA256(canonical_material_input_payload)` is strictly computed over:
  - `base_state_id` and `base_state_hash`: Cryptographic fingerprint of the ingested base state.
  - `scenario_id` and `scenario_version`: Identifier and contract version of the scenario.
  - `scenario_type` and `transformation_version`: Transformation mathematical spec version.
  - `parameters`: Canonical key-value mapping of effective perturbation parameters (e.g. `rainfall_multiplier`, `temperature_delta`).
  - `decision_evidence`: Material decision evidence across Phases 2–6:
    - **Phase 2 (Hazards):** `hazard_id`, `hazard`, `severity`, `confidence`, `timestamp`, `forecast_horizon_minutes`, `model_version`, `source`, `simulated`. Only decision-relevant hazards are included; irrelevant telemetry or test artifacts are filtered out.
    - **Phase 3 (Predictions):** `prediction_id`, `hazard`, `prediction_time`, `forecast_time`, `severity`, `confidence`, `model_version`, `simulated`.
    - **Phase 4 (Compound Events):** `event_id`, `severity`, `confidence`, `causal_chain` (ordered), `contributing_hazards` (sorted), `rule_version`, `timestamp`, `simulated`.
    - **Phase 5 (Vulnerability Zones):** `zone_id`, `population_exposed`, `exposure_ratio`, `vulnerability`, `accessibility`, `accessibility_risk`, `human_impact`, `evidence_ids` (sorted), `confidence`, `formula_version`, `simulated`.
    - **Phase 6 (Evacuation Intelligence):**
      - `road_edges`: Canonical list of relevant road segments with `edge_id`, `from_node`, `to_node`, `distance_km`, `travel_time_minutes`, `hazard_risk`, `accessibility`, `closed`, `inferred_failure_risk`.
      - `shelters`: Canonical list of relevant shelters with `shelter_id`, `capacity`, `current_occupancy`, `available_capacity`, `hazard_risk`, `accessibility`, `safe`, `latitude`, `longitude`, `simulated`.
      - `evacuation_routes`: Resulting routes with `selected_shelter_id`, `route_nodes` (ordered), `route_edges` (ordered), `distance`, `travel_time`, `hazard_exposure`, `accessibility`, `route_safety`, `assigned_population`, `status`, `reason`.
      - `routing_config`: `algorithm`, `algorithm_version`, `cost_formula_version`, `hazard_multiplier_version`, `accessibility_multiplier_version`, `accessibility_threshold`, `hazard_threshold`.
  - `model_versions`: Authoritative model versions for all upstream engines.
  - `simulation_formula_versions`: Contract formula versioning.

### 5.2 Canonicalization Rules
1. **Order-Sensitive Sequences:**
   - `route_nodes` (origin to destination sequence)
   - `route_edges` (ordered path segments)
   - `causal_chain` (disaster progression, e.g. `[heavy_rain, soil_saturation, flood, road_access_loss]`)
   These sequences preserve exact order. Any permuting of elements strictly alters the provenance hash.
2. **Order-Insensitive Collections:**
   - `hazards`, `predictions`, `compound_events`, `vulnerability_zones`, `candidate_shelters`, `candidate_edges`, `evacuation_routes`, `evidence_ids`, `contributing_hazards`.
   These collections are sorted canonically by primary identifier (e.g. `hazard_id`, `zone_id`, `shelter_id`, `edge_id`, or alphabetical string).

### 5.3 Provenance Guarantees
- **Temporal Invariance:** Simulations executed seconds, hours, or days apart with identical base states and scenario parameters produce identical provenance hashes.
- **Execution Identity Invariance:** Mutating `simulation_id` or `request_id` does not alter the provenance hash.
- **Order Invariance on Sets:** Permuting order-insensitive collections produces identical provenance hashes.
- **Relevance Filtering Invariance:** Adding unreferenced or irrelevant hazards (e.g. `is_relevant=False`) does not alter the provenance hash.
- **Mutation Sensitivity:** The 30-item mutation matrix proves that mutating any single material decision input strictly modifies the provenance hash.

---

## 6. Scientific & Operational Limitations

1. **Hypothetical Decision-Support Tool:** The digital twin scenario simulation engine is intended strictly for exploratory "what-if" counterfactual analysis.
2. **Not a Physics/Hydrodynamic Twin:** Does not perform partial differential equation solving for 2D/3D shallow water equations or Navier-Stokes CFD.
3. **Not a Microscopic Traffic Simulator:** Evacuation routing uses static/hazard-weighted Dijkstra pathfinding rather than continuous-time dynamic traffic assignment.
4. **No Real-World Future Probability Claim:** Scenarios simulate deterministic propagation under assumed parameter escalations; they do not calculate posterior likelihoods of occurrence.

