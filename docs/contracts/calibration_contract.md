# Calibration Contract (Phase 10)
## Climate Eye View Intelligence Microservice

### 1. Objective & Scientific Grounding
Calibration transforms raw confidence or probability-like numerical model outputs into well-calibrated statistical probabilities. An output is well-calibrated if, among instances assigned predicted probability $p$, the empirical event frequency is approximately $p$.

**Critical Boundary:**
- Deterministic severity indices must NOT be blindly calibrated. Calibration is restricted to probabilistic forecasts where empirical ground truth reference outcomes exist.
- Calibration is an adjustment layer, NOT empirical validation.
- Raw model outputs must NEVER be overwritten. Both `raw_value` and `calibrated_value` are permanently retained.

---

### 2. Statistical Gating & Leakage Prevention
1. **Sample-Size Gating**:
   - Probability calibration requires $\ge 50$ binary ground-truth reference samples.
   - If sample count is insufficient, the system aborts calibration and returns:
     $$\text{status} = \text{"CALIBRATION\_UNAVAILABLE"}$$
     with reason `"Insufficient sample count (< 50) for statistically valid probability calibration."`
2. **Train / Calibration / Test Separation**:
   - `DatasetRegistry.split_dataset` provides deterministic, non-leaking partitions (e.g. 60% train, 20% calibration, 20% test).
   - The calibration model is fitted strictly on the calibration split and evaluated on the holdout evaluation split.

---

### 3. Calibration Methods
Both methods are implemented in pure standard Python:
1. **Platt Scaling (Logistic Calibration)**:
   - Fits a logistic sigmoid over raw scores:
     $$P(y=1 | s) = \frac{1}{1 + \exp(A \cdot s + B)}$$
   - Optimized via Newton-Raphson maximum likelihood with regularized target smoothing.
2. **Isotonic Regression (PAVA)**:
   - Non-parametric monotonic step function fitted via the Pool Adjacent Violators Algorithm (PAVA).
   - Guaranteed non-decreasing mapping $s \mapsto \hat{p}$.

---

### 4. Reliability Analysis & Calibration Metrics
1. **10-Bin Reliability Diagrams**:
   - Partitions predicted probabilities into deciles: $[0.0, 0.1), [0.1, 0.2), \dots, [0.9, 1.0]$.
   - Records bin sample count, mean predicted probability, empirical observed frequency, and absolute calibration gap.
2. **Brier Score**:
   $$\text{BS} = \frac{1}{N}\sum (p_i - y_i)^2 \quad (\in [0, 1])$$
3. **Expected Calibration Error (ECE)**:
   $$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \cdot |\bar{p}(B_m) - \bar{y}(B_m)|$$
4. **Maximum Calibration Error (MCE)**:
   $$\text{MCE} = \max_{m} |\bar{p}(B_m) - \bar{y}(B_m)|$$

---

### 5. Calibrated Output Contract (`CalibratedOutput`)
```json
{
  "calibration_id": "CAL-RUN-A1B2C3D4",
  "model_version": "flood-v1.0",
  "method": "isotonic",
  "raw_value": 0.82,
  "calibrated_value": 0.76,
  "calibration_dataset": "EVAL-FLOOD-SYNTHETIC-001",
  "calibration_version": "1.0",
  "provenance_hash": "c3d4e5f6a1b2..."
}
```
**Inviolable Property:** The original authoritative model calculation `raw_value` is preserved unaltered.
