# Climate Eye View — Response Contract Specification
## Phase 9: AI Response Planner Contract & Schema

**Subsystem:** Software 2 (AI, Modeling & Intelligence)  
**Contract Version:** `response-v1`  
**Rules Version:** `response-rules-v1`  
**Status:** Canonical Reference

---

## 1. Primary Mission & System Boundary

The Phase 9 **AI Response Planner** is a deterministic emergency decision-support engine. It aggregates and interprets authoritative multi-phase outputs from:
- **Phase 2:** Hazard models (heat, flood, drought) and data quality telemetry.
- **Phase 3:** Deterministic predictions (+30m, +60m, +360m horizons).
- **Phase 4:** Compound hazard interactions, cascading disaster chains, and infrastructure risks.
- **Phase 5:** Human vulnerability, demographic exposure, and human impact scores.
- **Phase 6:** Evacuation demand, road accessibility/closures, safe shelter capacities, and `NO_ROUTE` conditions.
- **Phase 7/8:** Digital twin state perturbations and what-if scenario simulations.

### Critical Operational Boundary
- **Decision-Support Only:** The system generates structured recommendations for incident commanders and human emergency operators. It **NEVER** autonomously executes emergency actions, closes physical roads, or dispatches vehicles.
- **No Numerical Invention:** The planner strictly consumes upstream numerical values (hazard severity, confidence, population, travel times, capacities). It **NEVER** invents or fabricates hazard metrics.
- **Epistemic Separation:** Strictly distinguishes between `OBSERVED`, `PREDICTED`, `INFERRED`, and `SIMULATED` information. Simulated scenario outputs carry `simulated: true` and are **NEVER** presented as live emergency alerts.

---

## 2. Action Vocabulary

The response planner generates recommendations from a strict, controlled vocabulary:

| Action Identifier | Description | Default Target | Operator Review Gate |
| :--- | :--- | :--- | :--- |
| `MONITOR` | Baseline continuous telemetry observation | Region/Sector | Automatic |
| `MAINTAIN_MONITORING` | Maintain standard telemetry polling under nominal safety | Regional Observation | Automatic |
| `ISSUE_WARNING` | Public advisory for emerging or projected hazard conditions | Region/Hazard | Advisory |
| `PREPARE_EVACUATION` | Staged evacuation preparation based on predictive escalation | Regional Sector | Advisory |
| `EVACUATE_ZONE` | Immediate population extraction directive | Impacted Zone | **Mandatory** |
| `PRIORITIZE_VULNERABLE_POPULATION` | Special assistance mobilization for elderly, disabled, or children | Impacted Zone | Standard |
| `OPEN_SHELTER` | Activate auxiliary shelter due to capacity exhaustion | Shelter Facility | Standard |
| `REDIRECT_EVACUATION` | Diversion order away from unsafe or saturated destinations | Compromised Facility | **Mandatory** |
| `CLOSE_ROAD` | Roadway closure recommendation due to damage or flood risk | Road Segment | Standard |
| `CLOSE_BRIDGE` | Bridge corridor closure recommendation | Bridge Structure | Standard |
| `PROTECT_CRITICAL_FACILITY` | Deploy cooling centers, water tankers, or asset protection | Facility / Reserves | Standard |
| `PREPOSITION_RESPONSE_RESOURCES` | Forward deployment of rapid pumps, barriers, or rescue teams | Multizone Corridor | Standard |
| `REQUEST_FIELD_VERIFICATION` | Urgent on-the-ground reconnaissance when `NO_ROUTE` occurs | Isolated Zone | **Mandatory** |
| `REASSESS` | Routing and operational re-evaluation directive | Isolated Zone | **Mandatory** |

---

## 3. Alert Level Classification

Deterministic alert levels are calculated across regional maximum hazard, compound severity, human impact, and isolation conditions:

| Alert Level | Definition & Criteria | Operational Implication |
| :--- | :--- | :--- |
| `GREEN` | Nominal conditions: max hazard $< 0.40$ and human impact $< 0.30$. | Standard automated monitoring. |
| `YELLOW` | Emerging concern: hazard $\ge 0.40$ or human impact $\ge 0.30$ or compound $\ge 0.40$. | Enhanced monitoring & public advisories. |
| `ORANGE` | High hazard/impact: hazard $\ge 0.65$ or human impact $\ge 0.50$ or compound $\ge 0.65$. | Resource prepositioning & preparation. |
| `RED` | Critical emergency: hazard $\ge 0.85$ and human impact $\ge 0.70$, or `NO_ROUTE` with human impact $> 0.30$, or compound $\ge 0.85$. | Immediate evacuation & incident commander intervention. |

---

## 4. Priority, Urgency & Temporal Horizon Models

### 4.1 Temporal Horizon Weighting
Lead time directly impacts action urgency:
- $\omega_{\text{temporal}}(\text{OBSERVED}) = 1.00$
- $\omega_{\text{temporal}}(\text{PREDICTED}_{+30\text{m}}) = 0.85$
- $\omega_{\text{temporal}}(\text{PREDICTED}_{+60\text{m}}) = 0.70$
- $\omega_{\text{temporal}}(\text{PREDICTED}_{+360\text{m}}) = 0.50$
- $\omega_{\text{temporal}}(\text{SIMULATED}) = 0.60$

### 4.2 Urgency Formula
Urgency combines physical threat, demographic impact, physical access degradation, and temporal horizon:
$$\text{Urgency Score} = \min\left(1.0, \left(0.35 \cdot H + 0.35 \cdot I + 0.15 \cdot A_{\text{risk}}\right) \cdot \omega_{\text{temporal}} + 0.15 \cdot \omega_{\text{temporal}}\right)$$
where $H$ is hazard severity, $I$ is human impact, and $A_{\text{risk}}$ is access impediment risk.

Mapping to Urgency Tiers:
- **`CRITICAL`:** $\ge 0.80$
- **`HIGH`:** $\ge 0.60$ and $< 0.80$
- **`MEDIUM`:** $\ge 0.35$ and $< 0.60$
- **`LOW`:** $< 0.35$

### 4.3 Deterministic Priority Score & Ranking
Priority combines urgency, demographic vulnerability, cascading amplification, and data confidence:
$$\text{Priority Score} = 0.40 \cdot U_{\text{score}} + 0.30 \cdot V + 0.15 \cdot C_{\text{sev}} + 0.15 \cdot C_{\text{conf}}$$
Deterministic sorting rules:
1. Primary key: `priority_score` descending.
2. Secondary key: `urgency_score` descending.
3. Tertiary tiebreaker: `action_id` alphabetical ascending.

Rank integer $1, 2, 3, \dots$ is assigned strictly based on the ordered sequence.

---

## 5. Confidence Aggregation & Stale Data Degradation

Confidence in every response action derives from upstream evidence items:
$$C_{\text{base}} = \frac{1}{|E|} \sum_{e \in E} C_e$$
- **Stale Data Penalty:** If telemetry or model inputs exceed freshness limits ($> 300\text{s}$), a $-0.25$ penalty is applied, and warning `STALE_DATA` is emitted.
- **Low Confidence Review:** If confidence falls below $0.50$, warning `LOW_CONFIDENCE` is emitted, and critical actions transition to `status: REQUIRES_HUMAN_REVIEW`.
- **Missing Evidence Penalty:** If an action lacks required upstream evidence, confidence is clamped to $0.40$, warning `MISSING_EVIDENCE` is emitted, and `requires_human_review` is enforced.

---

## 6. Conflict Resolution Engine

The planner inspects all generated candidate actions to eliminate operational contradictions:

1. **Unsafe Route vs. Evacuation Route:**
   - If an evacuation corridor utilizes a road marked `CLOSE_ROAD`, `CLOSE_BRIDGE`, or inaccessible, the evacuation action status transitions to `BLOCKED`.
   - A companion `REDIRECT_EVACUATION` action is generated with mandatory operator review.
2. **Unsafe Shelter vs. Destination Assignment:**
   - If a shelter is compromised ($H_{\text{shelter}} \ge 0.60$ or `safe: false`), any action directing population to it transitions to `BLOCKED`.
   - An explicit `REDIRECT_EVACUATION` order is issued.
3. **Capacity Deficit vs. Evacuation:**
   - If candidate shelters operate at exhaustion ($A_{\text{capacity}} < 100$), evacuation actions to that facility transition to `CONDITIONAL`.
   - An `OPEN_SHELTER` action is generated.
4. **General Warning vs. Zone Evacuation:**
   - If both `ISSUE_WARNING` and `EVACUATE_ZONE` target the same zone/hazard, the weaker warning is marked `SUPERSEDED`.
5. **No Route (`NO_ROUTE`):**
   - Evacuation action is marked `BLOCKED`.
   - System issues `REQUEST_FIELD_VERIFICATION` and `REASSESS`.
   - The engine **NEVER** invents synthetic alternate routes.

---

## 7. Deterministic Provenance Specification

Every response plan generates a SHA-256 cryptographic digest proving mathematical reproducibility:
$$\text{Provenance Hash} = \text{SHA256}(\text{Canonical Material Payload})$$

### Invariance Rules
- **Volatile Metadata Decoupled:** `plan_id` (UUID), `generated_at` (timestamp), and `request_id` are strictly excluded from the provenance payload.
- **Unordered Collections:** Hazards, predictions, compound events, vulnerability zones, road edges, and shelters are sorted canonically by ID.
- **Order-Sensitive Sequences:** The ranked sequence of actions and cascading causal chains preserve exact position. Altering priority rank or chain steps mutates the hash.
- **Material Input Sensitivity:** Changing any hazard severity, prediction horizon, vulnerability factor, road closure status, shelter capacity, or threshold config produces a distinct hash.

---

## 8. REST API Interface

### 8.1 `GET /api/v1/response/current`
Returns the cached current response plan.
- **Status 200:** Returns `ResponsePlanResponse`.

### 8.2 `POST /api/v1/response/evaluate`
Evaluates authoritative current-state inputs and returns a response plan.
- **Request Body (`ResponseEvaluateRequest`):**
  - `telemetry`: Optional normalized telemetry dictionary.
  - `history`: Optional historical telemetry records.
  - `population_zones`: Optional demographic zone overrides.
  - `road_network`: Optional road network graph.
  - `shelters`: Optional shelter specifications.
  - `include_predictions`: bool (default: true).
- **Status 200:** Returns `ResponsePlanResponse`.

### 8.3 `POST /api/v1/response/simulate`
Executes response planning against a Phase 7/8 counterfactual digital twin simulation scenario.
- **Request Body (`ResponseSimulateRequest`):**
  - `scenario_id`: str (e.g. `"SCN-RAIN-40"`, `"SCN-FLOOD-HEAT"`).
  - `changes`: Optional parameter overrides.
  - `base_state`: Optional base state snapshot identifier.
- **Status 200:** Returns `ResponsePlanResponse` with `simulated: true`, `SIMULATED` epistemic tags, and advisory warnings.

---

## 9. Scientific Limitations & Safety Commitments

> [!CAUTION]
> 1. **Decision-Support Non-Execution:** Climate Eye View produces recommendations only. Incident commanders bear full legal, statutory, and operational responsibility for evacuation execution.
> 2. **No Route Fabrication:** If the physical transport network is severed, the system reports `NO_ROUTE` and requests human verification. It does not fabricate hypothetical extraction paths.
> 3. **Simulation Disclaimer:** Counterfactual scenario outputs represent synthetic stress-tests and must never be disseminated as real-world disaster warnings.
