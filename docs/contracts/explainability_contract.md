# Explainability Contract (Phase 10)
## Climate Eye View Intelligence Microservice

### 1. Architectural Mission
The Explainability layer translates authoritative numerical intelligence outputs produced across Phases 2 through 9 into structured, verifiable, and mathematically faithful representations. It ensures that decision makers, auditors, and frontline emergency personnel can inspect exactly:
1. **Why** a particular score or recommendation was generated.
2. **Which inputs and factors** contributed quantitatively, adhering strictly to the underlying model equations.
3. **What upstream evidence** (telemetry, hazards, vulnerability assessments, routing results) was utilized.
4. **Where epistemic uncertainty** resides (sensor density, forecast distance, network isolation).
5. **What counterfactual shifts** would modify the outcome or resolve bottlenecks.

---

### 2. Epistemic Status & Scientific Honesty
Outputs must never conflate observed empirical reality with hypothetical or extrapolated calculations. Every explanation carries an `EpistemicClassification`:
- `OBSERVED`: Grounded in physical sensor telemetry and verified field observations (Phase 2 & 3).
- `PREDICTED`: Projected forward across a temporal horizon (+30m, +60m, +360m) subject to physical bounds and confidence decay (Phase 4).
- `INFERRED`: Derived via deterministic causal graph traversal or spatial overlay rules (Phases 5, 6, 7, 9).
- `SIMULATED`: Generated via what-if parameter perturbations in the Digital Twin environment (Phase 8). Must never masquerade as active reality.

---

### 3. Explanation Schema (`ExplanationContract`)
```json
{
  "explanation_id": "EXP-HAZ-A1B2C3D4",
  "target_type": "hazard",
  "target_id": "HAZ-FLOOD-001",
  "model_version": "flood-v1.0",
  "classification": "OBSERVED",
  "summary": "OBSERVED hazard flood detected at severity 0.78 (confidence 0.92).",
  "explanation_level": "DETAILED",
  "formula_name": "Linear Weighted Hydrological Index",
  "formula_expression": "flood_score = 0.40 * norm(rainfall) + 0.35 * norm(water_level) + 0.25 * norm(soil_moisture)",
  "factors": [
    {
      "factor_name": "rainfall_rate",
      "display_name": "Rainfall Intensity Rate",
      "input_value": 35.0,
      "normalized_value": 0.35,
      "weight": 0.40,
      "contribution": 0.14,
      "unit": "mm/hr",
      "description": "Surface precipitation rate contributing 0.140 to flood score."
    }
  ],
  "reasoning_steps": [
    "Deterministic evaluation using Linear Weighted Hydrological Index.",
    "Evaluated raw inputs against baseline bounds."
  ],
  "evidence": [
    {
      "type": "telemetry",
      "id": "TEL-SENSOR-01",
      "severity": 0.78,
      "confidence": 0.92
    }
  ],
  "uncertainty": [],
  "counterfactuals": [
    {
      "condition": "Surface rainfall intensity reduced from 35.0 mm/hr to <= 15.0 mm/hr",
      "altered_parameter": "rainfall_mmhr",
      "original_value": 35.0,
      "counterfactual_value": 15.0,
      "counterfactual_outcome": "Flood hazard severity drops below emergency warning threshold (0.60)."
    }
  ],
  "provenance_hash": "a1b2c3d4e5f6...",
  "simulated": false
}
```

---

### 4. Deterministic Factor Attribution Formulas
Attributions reflect the exact mathematical equations implemented in the underlying models:
1. **Flood Hazard (`flood-v1`)**:
   $$\text{flood\_score} = 0.40 \cdot \text{norm}(\text{rain}) + 0.35 \cdot \text{norm}(\text{level}) + 0.25 \cdot \text{norm}(\text{soil})$$
2. **Heat Hazard (`heat-v1`)**:
   $$\text{AT} = -2.653 + 0.994 \cdot T + 0.0153 \cdot e(T, \text{RH})$$
   Normalized across thermal stress bounds with dry bulb (0.60) and moisture suppression (0.40).
3. **Drought Hazard (`drought-v1`)**:
   $$\text{drought\_score} = 0.50 \cdot \text{norm}(\text{soil\_deficit}) + 0.30 \cdot \text{norm}(\text{temp}) + 0.20 \cdot \text{norm}(\text{humidity\_deficit})$$
4. **Human Impact / Vulnerability (`vuln-v1`)**:
   $$\text{impact} = 0.50 \cdot \text{exposure\_ratio} + 0.35 \cdot \text{demographic\_vulnerability} + 0.15 \cdot \text{accessibility\_risk}$$
5. **Response Action Priority (`response-v1`)**:
   $$\text{priority} = 0.40 \cdot \text{urgency} + 0.30 \cdot \text{vulnerability} + 0.15 \cdot \text{cascade\_severity} + 0.15 \cdot \text{confidence}$$

---

### 5. Multi-Tier Formatting
- `SUMMARY`: Concise 1-2 sentence executive operational digest.
- `STANDARD`: Primary contributing factors, evidence items, and key drivers.
- `DETAILED`: Complete mathematical formulas, exact weights, normalized terms, uncertainty bounds, and counterfactuals.

---

### 6. Fallback-Safe LLM Layer
An optional LLM client can be attached to provide natural language narration.
**Inviolable Safety Boundaries:**
- The LLM must NEVER compute numerical scores, weights, or probabilities.
- The LLM must NEVER alter scores, evidence lists, or confidence values.
- If the LLM invocation fails, times out, or hallucinates, the deterministic structured `ExplanationContract` remains intact and immediately returned.
