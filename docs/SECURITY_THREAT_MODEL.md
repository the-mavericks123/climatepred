# Security Threat Model: Climate Eye View

**Application:** Climate Eye View S1 & S2 Disaster Intelligence  
**Milestone:** Phase 11 — Production Hardening  
**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  

---

## 1. System Assets & Security Boundaries

Critical assets protected by the system:
1. **Physical Sensor Telemetry**: Authentic environmental measurements from river basins and urban sectors.
2. **Authoritative Disaster Models**: Validated formulas computing hazard, vulnerability, and evacuation routes.
3. **Emergency Response Directives**: Prioritized operational action plans presented to emergency managers.
4. **Cryptographic Provenance**: Immutable SHA-256 audit trails establishing traceability.
5. **Database Records**: Historical disaster archives and geospatial population topologies.

---

## 2. Threat Matrix & Mitigation

| Threat Category | Specific Threat Description | Impact | Mitigation Strategy | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing (Edge)** | Attacker injects fraudulent sensor node with fabricated low water levels to mask a flood. | CRITICAL | MQTT client certificates / pre-shared node tokens; physical range validation gates; multi-node spatial correlation. | Compromised physical sensor hardware in the field. |
| **Tampering (Telemetry)** | Attacker intercepts and alters rainfall measurements in transit. | HIGH | MQTTS (TLS 1.3 encryption); payload SHA-256 validation; rejection of out-of-order timestamps. | Local gateway tampering if keys are extracted. |
| **Tampering (Replay)** | Attacker captures valid historical storm packets and replays them during fair weather. | HIGH | Timestamp clock-skew validation (rejecting packets > 10 min old or future); in-memory sliding-window packet deduplication. | Replay within the active 10-second sliding window. |
| **Denial of Service** | Flooding simulation or calibration endpoints with complex payloads to exhaust server CPU. | HIGH | Token-bucket rate limiting (HTTP 429); maximum payload body limit (10MB); simulation execution timeouts (15s). | Distributed denial of service at edge network layer. |
| **Information Disclosure** | Error responses leaking database credentials, local filesystem paths, or stack traces. | MEDIUM | Standardized error handling middleware masking internal exceptions; structured log redacting credentials. | Minimal (strict schema compliance enforced). |
| **Elevation of Privilege** | Unauthenticated user executing what-if scenario simulations or altering alert thresholds. | HIGH | Token-based Role-Based Access Control (`Public`, `Operator`, `Admin`); high-impact endpoints require `Operator` or `Admin` role. | Leakage of administrative API keys. |
| **AI / LLM Prompt Injection** | Malicious text injected into sensor notes attempting to override decision logic. | HIGH | Strict isolation: LLM/AI narration layers have zero access to numerical decision logic or emergency plan execution. | Unintended text formatting in generated summaries. |

---

## 3. Residual Risk Management

The system is engineered as an operational decision-support tool, not an autonomous emergency actuator:
- **Mandatory Human Supervisor Review**: High-consequence directives (`EVACUATE_ZONE`, `REDIRECT_EVACUATION`) strictly mandate human sign-off regardless of model confidence.
- **Fail-Safe Epistemic Separation**: Simulated what-if runs are cryptographically and structurally prevented from presenting as live observed telemetry.
