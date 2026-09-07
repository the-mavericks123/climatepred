# Evaluation Contract (Phase 10)
## Climate Eye View Intelligence Microservice

### 1. Objective & Scope
The Evaluation layer establishes an empirical benchmarking framework to measure, track, and guard the performance of all Climate Eye View intelligence models. It benchmarks hazard classification, temporal predictions across horizons (+30m, +60m, +360m), compound disaster detection, human vulnerability, evacuation routing feasibility, and response plan quality.

---

### 2. Dataset Classification & Scientific Honesty
Evaluation datasets are explicitly versioned and typed:
- `REAL`: Empirical field sensor records with verified post-disaster survey outcomes.
- `SYNTHETIC`: Deterministic test fixtures designed for software regression and stress testing.
- `HISTORICAL`: Archived telemetry runs from past weather events.
- `REPLAY`: Re-streamed time-series data for temporal validation.
- `BENCHMARK`: Canonical test sets for model version comparisons.

**Critical Scientific Rule:**
- Synthetic datasets must NEVER be represented as proof of real-world accuracy.
- When ground truth is unavailable, the system MUST return `status = "INSUFFICIENT_GROUND_TRUTH"`. Fabricating reference labels is strictly prohibited.

---

### 3. Evaluation Schema (`EvaluationReport`)
```json
{
  "evaluation_id": "EVAL-A1B2C3D4",
  "model_version": "flood-v1.0",
  "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
  "dataset_version": "1.0",
  "dataset_type": "SYNTHETIC",
  "status": "COMPLETED",
  "sample_count": 100,
  "ground_truth_status": "AVAILABLE",
  "metrics": {
    "accuracy": 0.86,
    "precision": 0.8889,
    "recall": 0.8163,
    "f1_score": 0.8511,
    "confusion_matrix": {
      "true_positives": 40,
      "false_positives": 5,
      "true_negatives": 46,
      "false_negatives": 9
    },
    "mae": 0.082,
    "rmse": 0.114,
    "mean_bias": -0.012
  },
  "warnings": [],
  "limitations": [
    "Evaluated on SYNTHETIC benchmark dataset.",
    "Performance metrics reflect algorithmic fidelity, NOT real-world empirical validation."
  ],
  "provenance_hash": "b2c3d4e5f6a1..."
}
```

---

### 4. Mathematical Metrics
All metrics are computed in pure standard Python without external statistical packages:
1. **Classification Metrics**:
   - Accuracy: $\frac{\text{TP} + \text{TN}}{\text{Total}}$
   - Precision: $\frac{\text{TP}}{\text{TP} + \text{FP}}$
   - Recall: $\frac{\text{TP}}{\text{TP} + \text{FN}}$
   - $F_1\text{ Score}$: $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$
2. **Continuous Prediction Metrics**:
   - Mean Absolute Error (MAE): $\frac{1}{N}\sum |y_i - \hat{y}_i|$
   - Root Mean Squared Error (RMSE): $\sqrt{\frac{1}{N}\sum (y_i - \hat{y}_i)^2}$
   - Mean Bias: $\frac{1}{N}\sum (\hat{y}_i - y_i)$
3. **Horizon-Specific Error**:
   - Evaluated independently for each forecast horizon (+30m, +60m, +360m) to prevent aggregation masking.
4. **System-Quality Metrics (Response Planning)**:
   - `unsupported_action_rate`: Actions lacking required upstream evidence references.
   - `contradiction_rate`: Mutually exclusive conflicting directives recommended concurrently.
   - `unsafe_shelter_rate`: Allocations to compromised facilities.
   - `human_review_compliance`: Rate at which critical actions adhere to mandatory supervisor gates.

---

### 5. Model Comparison & Regression Detection
Two models evaluated against identical benchmark datasets produce a `ModelComparisonReport`:
- Evaluates deltas: $\Delta \text{metric} = \text{candidate} - \text{baseline}$.
- **Regression Detection**: If $\Delta F_1 < -0.05$ or $\Delta \text{MAE} > +0.05$, flags:
  $$\text{regression\_detected} = \text{True}$$
  with explicit explanatory reasons.

---

### 6. Distribution Drift Detection
Tracks operational feature distribution divergence from baseline training references:
- **Population Stability Index (PSI)**:
  $$\text{PSI} = \sum (P_i - Q_i) \cdot \ln\left(\frac{P_i}{Q_i}\right)$$
  - $\text{PSI} < 0.10$: Minimal drift (`NONE`).
  - $0.10 \le \text{PSI} < 0.20$: Moderate drift (`MODERATE`).
  - $\text{PSI} \ge 0.20$: Significant distribution shift (`SIGNIFICANT`).
- **Kolmogorov-Smirnov (KS) Two-Sample Test**:
  - Computes maximum difference between empirical cumulative distribution functions:
    $$D = \sup_x |F_{\text{baseline}}(x) - F_{\text{operational}}(x)|$$
  - Compared against critical threshold: $c(\alpha)\sqrt{\frac{n_1 + n_2}{n_1 n_2}}$.
