# Climate Eye View — S2 Intelligence Subsystem

**Subsystem:** Software 2 (AI, Modeling & Intelligence)  
**Current Phase:** Phase 10 — Explainability + Evaluation + Calibration  
**Status:** Completed & Ready for Final Forensic Audit  

---

## 1. System Overview & Architecture

The Climate Eye View S2 Intelligence Service provides:
1. **Current-State Hazard Evaluation (Phase 2):** Deterministic evaluation of present hazard severity (horizon = 0).
2. **Deterministic Prediction Engine (Phase 3):** Deterministic, physically bounded forecasting of hazard trajectories across strictly 30-minute, 1-hour, and 6-hour horizons.
3. **Compound & Cascading Disaster Engine (Phase 4):** Deterministic rule- and graph-based engine detecting concurrent compound hazards, multi-stage cascading disaster chains, and inferred infrastructure consequences.
4. **Human Vulnerability & Exposure Intelligence (Phase 5):** Deterministic synthesis of hazard severity, spatial exposure, demographic vulnerability factors, and accessibility degradation into bounded human impact assessments while strictly preserving raw population counts.
5. **Dynamic Evacuation & Adaptive Route Intelligence (Phase 6):** Deterministic, auditable evacuation decision support matching demand from vulnerable zones to safe shelters under capacity constraints and computing hazard-aware routes over road networks.
6. **Digital Twin & Scenario Simulation Engine (Phase 7):** Deterministic, isolated counterfactual simulation engine allowing operators to ask "What happens if conditions change?" by applying controlled perturbations to baseline digital twin states and propagating effects through Phase 2-6 models.
7. **AI Response Planner (Phase 9):** Prioritized, deterministic emergency response plan generator converting multi-phase outputs into structured, evidence-grounded, operator-reviewed action recommendations.
8. **Explainability, Evaluation & Calibration (Phase 10):** Deterministic factor attribution, structured reasoning, counterfactual tipping points, multi-horizon benchmark evaluation, statistical model version comparison, distribution drift detection, and non-destructive probability calibration.


```
       Phase 2 Hazard / Phase 3 Prediction / Phase 4 Compound
                                 |
                                 v
                 Phase 5 Vulnerability Assessment
                                 |
                                 v
                     Evacuation Demand Engine
         (Thresholding, priority ranking, population to evacuate)
                                 |
                                 v
                   Shelter Screening & Capacity Gate
           (Safety verification, available capacity tracking)
                                 |
                                 v
                     Hazard-Aware Dijkstra Routing
             (Travel time x hazard penalty x access penalty)
                                 |
                                 v
                    Deterministic Allocation Manager
           (Greedy priority matching, partial capacity handling)
                                 |
                                 v
                       Confidence & Provenance
         (Multi-factor confidence, SHA-256 canonical hashing)
                                 |
                                 v
                            REST API
   (POST /api/v1/evacuation/evaluate, GET /api/v1/evacuation/routes)
```

### Scientific & Operational Definitions
- **EVACUATION DEMAND:** Requirement to evacuate triggered when zone `human_impact >= 0.50` or `hazard_risk >= 0.70`.
- **EVACUATION PRIORITY:** Weighted composite score in [0.0, 1.0] ranking urgency across human impact, vulnerability, hazard severity, accessibility impediments, and forecast horizon.
- **HAZARD-AWARE ROUTE COST:** Composite traversal impedance where hazardous or damaged road segments incur exponential penalties relative to clear roads.
- **SHELTER SAFETY:** Strict gate requiring certified shelters to be structurally operational and maintain local hazard risk $< 0.60$.
- **NO ROUTE CONDITION:** Explicit deterministic status when all candidate paths are closed, unsafe, or shelter capacity is exhausted.

### Scope Discipline & Hard Boundaries
- **Phase 6 Scope:** Evacuation demand calculation, priority ranking, safe shelter matching, capacity constraint enforcement, Dijkstra hazard-aware pathfinding, closed road avoidance, route safety scoring, dynamic recomputation, confidence discounting, and SHA-256 provenance tracking.
- **Strictly Prohibited & Absent in Phase 6:** Digital twin simulation, scenario simulation, emergency response action planning, autonomous emergency vehicle control, autonomous dispatch, physical barrier/signal actuators, and LLM-based numerical calculations.

---

## 2. Directory Structure

```
intelligence/
├── .env.example              # Reference environment configuration
├── README.md                 # Comprehensive subsystem documentation
├── requirements.txt          # Pinned lightweight dependencies
├── app/
│   ├── config.py             # Pydantic-settings configuration
│   ├── dependencies.py       # DI providers (HazardEngine, PredictionEngine, CompoundEngine, VulnerabilityEngine, EvacuationEngine)
│   └── main.py               # FastAPI application, routes, error handlers
├── core/
│   ├── contracts/telemetry.py # Canonical NormalizedTelemetry contract
│   ├── errors/exceptions.py  # Structured error contract and exception hierarchy
│   ├── logging.py            # Structured JSON logger
│   ├── provenance/tracker.py # SHA-256 fingerprinting
│   └── validation/validator.py # Telemetry validator
├── hazards/                  # Phase 2 Authoritative Models
│   ├── types.py              # Hazard contracts (HazardResult, enums)
│   ├── thresholds.py         # Configurable physical weights and classification tiers
│   ├── features.py           # FeatureExtractor & HazardFeatures
│   ├── quality_gate.py       # HazardQualityGate & QualityGateVerdict
│   ├── heat.py               # HeatModel (heat-v1: Steadman Apparent Temperature)
│   ├── flood.py              # FloodModel (flood-v1: Multi-factor hydrological score)
│   ├── drought.py            # DroughtModel (drought-v1: Moisture deficit & heat)
│   └── engine.py             # HazardEngine orchestrator
├── prediction/               # Phase 3 Deterministic Prediction Engine
│   ├── types.py              # PredictionResult, ForecastHorizon, Request/Response
│   ├── thresholds.py         # Physical bounds, horizons {30, 60, 360}, lookback limits
│   ├── features.py           # Temporal series extraction, OLS trend & anti-leakage filter
│   ├── models.py             # DeterministicTrendForecaster with physical clamping
│   ├── confidence.py         # PredictionConfidenceCalculator
│   └── engine.py             # PredictionEngine orchestrator
├── compound/                 # Phase 4 Compound & Cascading Disaster Engine
│   ├── __init__.py           # Package exports
│   ├── types.py              # CompoundEvent, ContributingState, RelationshipEdge, enums
│   ├── rules.py              # Canonical rule definitions and CompoundRuleConfig
│   ├── graph.py              # CascadeGraph (DAG, cycle protection, chain DFS)
│   ├── features.py           # StateFeatureExtractor (OBSERVED vs PREDICTED vs INFERRED)
│   ├── confidence.py         # CompoundConfidenceCalculator
│   └── engine.py             # CompoundDisasterEngine orchestrator
├── vulnerability/            # Phase 5 Human Vulnerability & Exposure Intelligence
│   ├── __init__.py           # Package exports
│   ├── types.py              # PopulationZone, VulnerabilityZoneAssessment, Request/Response
│   ├── exposure.py           # ExposureCalculator (preserves count, computes bounded ratio)
│   ├── vulnerability.py      # VulnerabilityCalculator (factor weighting, healthcare inversion)
│   ├── accessibility.py      # AccessibilityCalculator (road/facility access, cascade degradation)
│   ├── impact.py             # HumanImpactCalculator (deduplication, non-linear risk compounding)
│   ├── confidence.py         # VulnerabilityConfidenceCalculator (data quality, synthetic discounting)
│   ├── provenance.py         # VulnerabilityProvenanceTracker (deterministic SHA-256 hashing)
│   └── engine.py             # VulnerabilityEngine orchestrator
├── evacuation/               # Phase 6 Dynamic Evacuation & Adaptive Routing Intelligence
│   ├── __init__.py           # Package exports
│   ├── types.py              # Shelter, RoadEdge, RoadNetwork, EvacuationRecommendation, Request/Response
│   ├── network.py            # RoadNetworkGraph (adjacency, closed edge filtering, cascade disruptions)
│   ├── routing.py            # HazardAwareRouter (Dijkstra algorithm, hazard cost, route safety)
│   ├── demand.py             # EvacuationDemandCalculator (priority scoring, population to evacuate)
│   ├── shelters.py           # ShelterManager (safety screening, deterministic capacity allocation)
│   ├── confidence.py         # EvacuationConfidenceCalculator (multi-factor uncertainty blending)
│   ├── provenance.py         # EvacuationProvenanceTracker (canonical SHA-256 hashing)
│   └── engine.py             # EvacuationEngine orchestrator
├── ingestion/
│   ├── normalized_adapter.py # Ingestion normalization adapter
│   └── source_registry.py    # Multi-source registry
├── scripts/
│   ├── live_smoke_test.py    # Phase 2 live API smoke audit (12 scenarios)
│   ├── live_prediction_smoke_test.py # Phase 3 live prediction smoke audit (14 scenarios)
│   ├── live_compound_smoke_test.py   # Phase 4 live compound smoke audit (6 scenarios)
│   ├── live_vulnerability_smoke_test.py # Phase 5 live vulnerability smoke audit (7 scenarios)
│   ├── live_evacuation_smoke_test.py    # Phase 6 live evacuation smoke audit (7 scenarios)
│   ├── generate_evacuation_fixtures.py  # Evacuation benchmark fixture generator
│   └── generate_vulnerability_fixtures.py # Vulnerability benchmark fixture generator
└── tests/
    ├── contract/             # Pydantic schema validation tests
    ├── unit/                 # Model and component algorithmic unit tests
    ├── integration/          # HTTP API endpoint integration tests
    └── evaluation/           # Deterministic benchmark scenario evaluations
```

---

## 3. Mathematical Formulation (Phase 6)

### A. Evacuation Demand & Priority Ranking
Evacuation is triggered when `human_impact >= 0.50` or `hazard_risk >= 0.70`.
Priority is deterministically calculated across normalized dimensions:
```
priority = clamp(
    0.35 * human_impact
    + 0.25 * vulnerability
    + 0.20 * hazard_risk
    + 0.10 * accessibility_risk
    + 0.10 * urgency,
    0.0,
    1.0
)
```
Where `urgency = 1.00` for observed hazards, `0.85` for 30m forecasts, `0.70` for 60m forecasts, and `0.50` for 360m forecasts.

The population to evacuate is derived from the exposed population:
```
population_to_evacuate = round(population_exposed * min(1.0, 0.60 + 0.40 * priority))
```
Strict invariant: `0 <= population_to_evacuate <= population_exposed`.

### B. Hazard-Aware Dijkstra Routing
Traversable road edge traversal cost incorporates physical travel time and non-linear penalties for hazard presence and reduced roadway accessibility:
```
hazard_multiplier = 1.0 + (2.5 * hazard_risk)
accessibility_multiplier = 1.0 + (2.0 * (1.0 - accessibility))
edge_cost = travel_time_minutes * hazard_multiplier * accessibility_multiplier
```
If `closed == True`, `edge_cost = infinity` (impassable).

Route safety score:
```
safety_score = clamp(1.0 - (0.60 * mean_hazard) - (0.40 * (1.0 - mean_accessibility)), 0.0, 1.0)
```

### C. Shelter Capacity & Safety Gate
Candidate shelters must satisfy `safe == True` and `hazard_risk < 0.60`.
Available capacity is tracked statefully during allocation:
```
available_capacity = max(0, capacity - current_occupancy)
```
Candidate shelters are scored by composite traversal and facility safety:
```
shelter_score = route_cost * (1.0 + 1.5 * shelter.hazard_risk) * (1.0 + 0.5 * (1.0 - shelter.accessibility))
```
Demands are assigned greedily in order of priority. If available capacity is less than demand, `PARTIAL_CAPACITY` is assigned without exceeding shelter limits.

---

## 4. REST API Reference (Phase 6)

#### `POST /api/v1/evacuation/evaluate`
Evaluates demographic zones, candidate shelters, and road networks to produce actionable evacuation recommendations and hazard-aware routes.

**Example Response:**
```json
{
  "success": true,
  "recommendations": [
    {
      "evacuation_id": "EVAC-ZONE-A-4E38F1B0",
      "zone_id": "ZONE-A",
      "timestamp": "2026-09-07T14:30:00Z",
      "forecast_horizon_minutes": 0,
      "evidence_type": "OBSERVED",
      "population_exposed": 10000,
      "population_to_evacuate": 8179,
      "priority": 0.8448,
      "destination": {
        "shelter_id": "SHELTER-NORTH",
        "shelter_name": "North Civic Center",
        "assigned_population": 8179,
        "available_capacity_before": 11000,
        "available_capacity_after": 2821,
        "shelter_safety_score": 0.95
      },
      "route": {
        "route_id": "ROUTE-ZONE-A-SHELTER-NORTH-2E",
        "origin_node": "ZONE-A",
        "destination_node": "SHELTER-NORTH",
        "nodes": ["ZONE-A", "INT-1", "SHELTER-NORTH"],
        "edge_ids": ["ROAD-A-1", "ROAD-1-NORTH"],
        "distance_km": 7.0,
        "estimated_travel_minutes": 14.0,
        "hazard_exposure": 0.05,
        "accessibility": 0.925,
        "safety_score": 0.94,
        "total_cost": 21.65
      },
      "avoid_edges": ["ROAD-COLLAPSED-BRIDGE"],
      "status": "RECOMMENDED",
      "reason": "Safe evacuation route identified to North Civic Center (sufficient capacity: 11,000 available for 8,179 evacuees)",
      "confidence": 0.8872,
      "simulated": true,
      "provenance_hash": "a1b2c3d4e5f6...",
      "algorithm_version": "dijkstra-hazard-v1",
      "cost_formula_version": "cost-v1"
    }
  ],
  "recommendation_count": 1,
  "total_evacuated_population": 8179,
  "unassigned_demand_population": 0,
  "request_id": "REQ-1fb3aea9"
}
```

#### `GET /api/v1/evacuation/routes` & `GET /api/v1/evacuation/current`
Retrieves current cached evacuation directives and routing assessments.

---

## 5. Phase 6 Forensic Remediation: Architecture & Guarantees

### 5.1 Dynamic Edge Accessibility Invalidation (Blocker 1 Fix)
- **Configuration Field:** `edge_accessibility_threshold` in `Settings` (`intelligence/app/config.py`).
  - **Default Value:** `0.40`
  - **Valid Range:** `[0.0, 1.0]`
  - **Meaning:**
    - `accessibility >= edge_accessibility_threshold` $\to$ `EDGE_USABLE`
    - `accessibility < edge_accessibility_threshold` $\to$ `EDGE_UNAVAILABLE` (traversal cost = $\infty$)
  - **Consumption Points:** Evaluated in `HazardAwareRouter.calculate_edge_cost`, `HazardAwareRouter.find_route`, `RoadNetworkGraph.get_outbound_edges`, and `HazardAwareRouter.identify_avoid_edges`.
- **Strict Distinction Between Physical Closure & Accessibility Degradation:**
  - An edge with `accessibility = 0.30` and `edge_accessibility_threshold = 0.40` is rendered impassable / unavailable by the routing engine, but its `closed` attribute remains strictly `False`.
  - Inferred Phase 4 cascade events (e.g. `inferred_road_failure_risk`, `inferred_access_loss`) update `edge.inferred_failure_risk` and degrade `edge.accessibility`, but never automatically convert inferred risk into physical closure (`closed = True`).
- **Request-Time Dynamic Recomputation Architecture:**
  - Evacuation routing operates strictly on **request-time evaluation**. Every call to `EvacuationEngine.evaluate(...)` ingests current telemetry, active compound cascades, road edge conditions, and shelter occupancies.
  - If a road segment's accessibility degrades below threshold, any path traversing it is immediately invalidated, and Dijkstra search selects an alternate traversable corridor or returns `status = NO_ROUTE` (`no_route_reason = NO_FEASIBLE_PATH` or `ALL_ROADS_CLOSED`).

### 5.2 Complete Canonical Evacuation Provenance (Blocker 2 Fix)
- **Provenance Fingerprint:** Deterministic SHA-256 digest generated from a canonical JSON serialization (`json.dumps(..., sort_keys=True, separators=(',', ':'))`).
- **10 Material Decision Input Categories Captured:**
  1. **Zone / Population:** `zone_id`, `total_population`, `population_exposed`, `exposure_ratio`, `population_to_evacuate`, `priority`, `simulated`, `forecast_horizon_minutes`.
  2. **Vulnerability Assessment (Phase 5):** `vulnerability`, `human_impact`, `accessibility_risk`, `evidence_ids`, `source_confidence`, `confidence`.
  3. **Hazard Evidence (Phase 2):** Canonical list of hazards with `hazard_id`, `hazard_type`, `severity`, `confidence`, `timestamp`, `forecast_horizon_minutes`, `model_version`, `simulated`.
  4. **Prediction Evidence (Phase 3):** Canonical list of predictions with `prediction_id`, `hazard`, `severity`, `confidence`, `prediction_time`, `forecast_time`, `forecast_horizon_minutes`, `model_version`, `simulated`.
  5. **Compound Event Evidence (Phase 4):** Canonical list of compound events with `event_id`, `severity`, `confidence`, `causal_chain`, `contributing_hazards`, `rule_version`, `simulated`.
  6. **Road Network Inputs:** Canonical list of candidate edges with `edge_id`, `from_node`, `to_node`, `distance_km`, `travel_time_minutes`, `hazard_risk`, `accessibility`, `closed`, `inferred_failure_risk`.
  7. **Routing Configuration:** `algorithm`, `algorithm_version`, `cost_formula_version`, `hazard_multiplier_version`, `accessibility_multiplier_version`, `route_safety_formula_version`, `accessibility_threshold`, `hazard_threshold`.
  8. **Shelter Inputs:** Canonical list of candidate shelters with `shelter_id`, `capacity`, `current_occupancy`, `available_capacity`, `hazard_risk`, `accessibility`, `safe`, `latitude`, `longitude`, `simulated`.
  9. **Final Route Result:** `selected_shelter_id`, `route_nodes`, `route_edges`, `distance_km`, `travel_time_minutes`, `hazard_exposure`, `accessibility`, `route_safety_score`, `avoid_edges`, `assigned_population`, `status`, `reason`, `no_route_reason`.
  10. **Confidence Evaluation:** `confidence`, `confidence_formula_version`, `horizon_discount`, `synthetic_data_discount`, `cascade_penalty`.
- **Collection Ordering Semantics:**
  - **Order-Sensitive Collections:** `route_nodes`, `route_edges`, `causal_chain` (order preserved exactly; reordering modifies hash).
  - **Order-Insensitive Collections:** `avoid_edges`, `candidate_shelters`, `candidate_edges`, `hazards`, `predictions`, `compound_events`, `evidence_ids`, `contributing_hazards` (sorted deterministically by unique identifiers before serialization).

---

## 6. Verification & Testing

```bash
# Run all 287 tests across Phases 1-6
pytest -v intelligence/tests/

# Run Phase 2 live smoke test (12 scenarios)
python intelligence/scripts/live_smoke_test.py

# Run Phase 3 live prediction smoke test (14 scenarios)
python intelligence/scripts/live_prediction_smoke_test.py

# Run Phase 4 live compound smoke test (6 scenarios)
python intelligence/scripts/live_compound_smoke_test.py

# Run Phase 5 live vulnerability smoke test (7 scenarios)
python intelligence/scripts/live_vulnerability_smoke_test.py

# Run Phase 6 live evacuation smoke test (8 scenarios including dynamic accessibility invalidation)
python intelligence/scripts/live_evacuation_smoke_test.py

# Run Phase 7 live simulation smoke test (8 scenarios verifying isolation, propagation, catalog, caching)
python intelligence/scripts/live_simulation_smoke_test.py

# Run Phase 9 live response planner smoke test (12 scenarios verifying live, predictive, compound, NO_ROUTE, simulation, and provenance)
python intelligence/scripts/live_response_smoke_test.py

# Verify GEV production build
npm --prefix gods-eye-view run build
```

### Complete Test Matrix (446 Tests Total):
- **Phase 1 Foundations:** Ingestion, validation, registry, errors, provenance (43 tests).
- **Phase 2 Hazard Models:** Heat, flood, drought, quality gate, contracts, evaluation (53 tests).
- **Phase 3 Prediction Engine:** Temporal extraction, OLS forecasting, leakage invariance, horizons, contracts, evaluation (48 tests).
- **Phase 4 Compound Engine:** Graph creation, DAG cycle protection, cascade detection, contracts, benchmarks (28 tests).
- **Phase 5 Vulnerability Engine:** Exposure calculation, vulnerability weighting, healthcare deficit, human impact (40 tests).
- **Phase 6 Evacuation Engine:** Demand, routing, shelters, capacity allocation, dynamic invalidation, 22-mutation matrix (75 tests).
- **Phase 7 Scenario Simulation Engine:** Simulation contracts, multi-phase propagation, 30-item mutation matrix, API endpoints (93 tests).
- **Phase 9 AI Response Planner (66 tests total):**
  - `test_response_contract.py`: Pydantic schema contracts, ActionItem, SituationContext, ResponsePlan, and requests (7 tests).
  - `test_response_rules.py`: Deterministic response rule triggers across flood, predictive horizons, heat/drought facilities, road closures, shelter capacity, and NO_ROUTE directives (10 tests).
  - `test_response_priorities.py`: Urgency formulas, temporal discount factors, deterministic priority scoring, and tiebreaking order (8 tests).
  - `test_response_conflicts.py`: Conflict detection and resolution (BLOCKED unsafe routes, SUPERSEDED generic warnings, CONDITIONAL capacity deficit, and REDIRECT_EVACUATION) (6 tests).
  - `test_response_confidence.py`: Multi-source confidence aggregation, stale data penalties, low-confidence review gating, and missing evidence clamps (6 tests).
  - `test_response_provenance.py`: Deterministic SHA-256 canonical hashing, volatile metadata decoupling, order-sensitive action ranking sensitivity, and 10 material mutation tests (15 tests).
  - `test_response_safety.py`: Safety invariant enforcement (never invent routes, never allocate unsafe shelters, never claim executed actions, never confuse simulation with live reality) (8 tests).
  - `test_response_api.py`: FastAPI endpoints integration for `GET /api/v1/response/current`, `POST /api/v1/response/evaluate`, and `POST /api/v1/response/simulate` (6 tests).

---

## 9. Phase 9 AI Response Planner Architecture & Decision Support

### 9.1 Response Planner Pipeline
```
Phase 2 Hazard + Phase 3 Prediction + Phase 4 Compound + Phase 5 Vulnerability + Phase 6 Evacuation
                                       │
                                       ▼
                             Situation Assessment
                     (Active, predicted, compound, zones)
                                       │
                                       ▼
                            Alert Level Derivation
                         (GREEN, YELLOW, ORANGE, RED)
                                       │
                                       ▼
                               Action Generation
                     (Deterministic Phase 2-8 rules engine)
                                       │
                                       ▼
                             Priority & Urgency
                     (Multi-factor scoring & temporal weighting)
                                       │
                                       ▼
                            Conflict Resolution
                  (BLOCKED, SUPERSEDED, CONDITIONAL, REDIRECT)
                                       │
                                       ▼
                           Confidence & Freshness
                     (Upstream aggregation & stale discounting)
                                       │
                                       ▼
                           Cryptographic Provenance
                     (Deterministic SHA-256 canonical digest)
                                       │
                                       ▼
                          Structured Response Plan
                 (Decision support with mandatory human review gates)
```

### 9.2 Controlled Action Vocabulary
- `MONITOR`, `MAINTAIN_MONITORING`
- `ISSUE_WARNING`, `PREPARE_EVACUATION`
- `EVACUATE_ZONE`, `PRIORITIZE_VULNERABLE_POPULATION`
- `OPEN_SHELTER`, `REDIRECT_EVACUATION`
- `CLOSE_ROAD`, `CLOSE_BRIDGE`
- `PROTECT_CRITICAL_FACILITY`, `PREPOSITION_RESPONSE_RESOURCES`
- `REQUEST_FIELD_VERIFICATION`, `REASSESS`

### 9.3 Safety Commitments
1. **Decision Support Only:** The system NEVER autonomously executes emergency operations, dispatches vehicles, or actuates infrastructure.
2. **Zero Numerical Fabrication:** Numerical risk, population, capacity, and travel metrics are strictly derived from authoritative upstream models.
3. **No Route Invention:** On `NO_ROUTE`, the system issues `REQUEST_FIELD_VERIFICATION` and escalates to human operators; it never invents non-existent roads.
4. **Epistemic Integrity:** Distinguishes strictly between `OBSERVED`, `PREDICTED`, `INFERRED`, and `SIMULATED` information. Simulated what-if plans are explicitly tagged `simulated = true`.

---

## 10. Phase 10 — Explainability, Evaluation & Calibration

```
    Authoritative Model Outputs (Phases 2-9)
                      │
                      ▼
               Evidence Resolver
                      │
                      ▼
             Explanation Engine
     (Factor Attribution + Reasoning + Counterfactuals)
                      │
                      ▼
              Evaluation Engine
     (Benchmark Metrics + Horizon Errors + Comparisons + Drift)
                      │
                      ▼
             Calibration Engine
     (Platt Scaling + Isotonic Regression + Reliability Diagrams)
                      │
                      ▼
               REST API Service
     (GET/POST /api/v1/explainability/..., /evaluation/..., /calibration/...)
```

### 10.1 Key Capabilities
- **Exact Mathematical Attribution:** Re-uses authoritative formulas (flood index, Steadman AT, drought index, vulnerability weights, response priorities) to compute exact numerical factor contributions without artificial weights or percentage fabrication.
- **Epistemic Classification:** Rigorous separation of `OBSERVED`, `PREDICTED`, `INFERRED`, and `SIMULATED` outputs.
- **Empirical Evaluation Framework:** Standard-library metrics (Accuracy, Precision, Recall, F1, MAE, RMSE, Bias, Brier score, ECE, MCE) across versioned datasets (`REAL`, `SYNTHETIC`, `HISTORICAL`).
- **Model Version Comparison & Regression Detection:** Compares baseline vs. candidate models on identical datasets, automatically flagging `REGRESSION_DETECTED` when performance degrades.
- **Distribution Drift Detection:** Computes Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) statistics against baseline telemetry.
- **Non-Destructive Calibration:** Platt scaling and Isotonic regression fitted with strict $\ge 50$ sample gating and non-leaking data splits; never overwrites raw model outputs.
- **Cryptographic Provenance:** Deterministic SHA-256 digests over material features, formulas, datasets, and parameters while completely decoupling volatile execution metadata.

### 10.2 REST API Endpoints
- `GET /api/v1/explainability/{target_type}/{target_id}`: Retrieves cached or live explanation.
- `POST /api/v1/explainability/generate`: Generates on-demand explanation for any target object.
- `POST /api/v1/evaluation/run`: Executes benchmark evaluation against a dataset.
- `GET /api/v1/evaluation/{evaluation_id}`: Retrieves historical evaluation report.
- `POST /api/v1/calibration/run`: Fits and evaluates a probability calibrator.
- `GET /api/v1/calibration/{calibration_id}`: Retrieves calibration report with reliability bins.
- `GET /api/v1/models/{model_version}/evaluation`: Shortcut to evaluate a model on default synthetic benchmark.
- `POST /api/v1/models/compare`: Compares candidate vs baseline model versions.
- `POST /api/v1/drift/evaluate`: Evaluates telemetry distribution drift.

---

## 11. Scientific & Operational Limitations Disclaimer

> [!IMPORTANT]
> The Climate Eye View Intelligence Subsystem is a deterministic decision-support tool designed for situational awareness, prioritized recommendation synthesis, and explainable emergency planning within God's Eye View.
>
> - **Operational Boundary:** This engine is **NOT** an autonomous dispatch system, certified emergency command platform, or legally binding evacuation authority.
> - **Human-in-the-Loop:** All high-consequence recommendations enforce `requires_human_review: true` with structured review rationales.
> - **Scientific Honesty:** Synthetic datasets are engineered strictly for unit testing, benchmarking, and software verification; they do **NOT** constitute real-world empirical validation. When ground truth is unavailable, the system explicitly returns `INSUFFICIENT_GROUND_TRUTH` without fabricating labels.
> - **Non-Destructive Calibration:** Calibration adjusts probabilistic interpretations only where statistical ground truth exists ($\ge 50$ samples); raw model outputs are permanently retained and never overwritten.
> - **Simulation Labeling:** Every simulation response plan carries explicit `simulated = true` markings, dedicated simulation IDs, and SHA-256 cryptographic provenance digests.




