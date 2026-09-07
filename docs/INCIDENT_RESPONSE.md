# Climate Eye View: Incident Response Protocol

**Classification:** Operational Incident Response Guide  
**Milestone:** Phase 11 — Production Hardening  

---

## 1. Incident Classification Levels

| Severity Level | Definition | Response SLA | Escalation |
| :--- | :--- | :--- | :--- |
| **SEV-1 (CRITICAL)** | Total intelligence microservice outage, active database corruption, or security compromise during a live disaster event. | Immediate (< 15 mins) | Technical Lead, Incident Commander |
| **SEV-2 (HIGH)** | Ingestion failure on multiple sensor nodes, MQTT broker offline, or stale state across an entire urban sector. | < 1 hour | Backend / Edge Lead |
| **SEV-3 (MEDIUM)** | Single sensor reporting anomaly, elevated API latency, rate limit triggering under drill load. | < 4 hours | On-call Engineer |
| **SEV-4 (LOW)** | Minor UI cosmetic glitch, documentation discrepancy, non-impacting telemetry drift. | Next business day | Development Team |

---

## 2. Incident Response Playbooks

### Playbook A: PostGIS Database Outage
1. **Declare Incident**: Open an incident channel (`#incident-database-outage`).
2. **Containment**: S2 intelligence service automatically enters read-only fallback mode, serving the latest cached state to GEV.
3. **Investigation**:
   - Check storage limits: `df -h /var/lib/postgresql/data`
   - Check connection saturation: `SELECT count(*) FROM pg_stat_activity;`
4. **Resolution**:
   - If process crashed: restart container.
   - If corrupted: restore latest clean snapshot using `docs/database_backup_recovery.md`.
5. **Post-Incident**: Review connection pool settings and WAL generation rates.

### Playbook B: MQTT Broker Ingestion Outage
1. **Containment**: S2 switches telemetry status for silent nodes from `LIVE` to `STALE` (at $t=300s$), avoiding false guarantees of safety.
2. **Investigation**:
   - Verify network port accessibility: `nc -zv localhost 1883`
   - Check Mosquitto resource usage.
3. **Resolution**:
   - Restart Mosquitto.
   - Trigger edge gateways to flush local spool buffers.
4. **Post-Incident**: Verify packet deduplication dropped any replayed queue bursts.

### Playbook C: Credential Compromise / Secret Leakage
1. **Immediate Revocation**:
   - Invalidate compromised `API_KEY` or JWT secret immediately in environment variables.
   - Restart S2 microservice to flush in-memory auth caches.
2. **Audit Access Logs**:
   - Search structured logs for the compromised token:
     ```bash
     grep "COMPROMISED_KEY_HASH" /var/log/intelligence/access.log
     ```
   - Determine whether unauthorized simulations or configuration edits occurred.
3. **Rotation**: Reissue edge sensor provisioning tokens and administrative passwords.

---

## 3. Post-Mortem & Reporting

A Root Cause Analysis (RCA) document must be drafted within 48 hours of any SEV-1 or SEV-2 resolution. The RCA must detail:
- Chronological timeline of events.
- Detection time vs resolution time.
- Direct root cause and contributing environmental factors.
- Corrective actions and new regression tests added to Phase 11 test suite.
