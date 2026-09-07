# Database Backup, Recovery & Retention Specification

**Subsystem:** Climate Eye View PostGIS & Time-Series Persistence  
**Milestone:** Phase 11 — Production Hardening  

---

## 1. Scope & Objective

This document defines the database backup, disaster recovery, schema migration rollback, and automated data retention protocols for the Climate Eye View system. The database persists geospatial infrastructure (sensors, roads, shelters, zones) and time-series telemetry/intelligence records.

---

## 2. Backup Strategy

### Automated Snapshot Schedule
- **Daily Full Logical Backup**: Created via `pg_dump` in custom compressed directory format at `02:00 UTC`.
- **Continuous Write-Ahead Log (WAL) Archiving**: (In enterprise production) streaming WAL segments to secure object storage allowing Point-In-Time Recovery (PITR) within a 7-day window.
- **Pre-Migration Snapshot**: Mandatory logical dump executed prior to applying any database schema migration.

### Standard Backup Command
```bash
# Export compressed PostGIS snapshot with geospatial metadata
pg_dump \
  --host="${POSTGRES_HOST:-localhost}" \
  --port="${POSTGRES_PORT:-5432}" \
  --username="${POSTGRES_USER:-postgres}" \
  --dbname="${POSTGRES_DB:-climate_eye_view}" \
  --format=custom \
  --compress=9 \
  --file="/var/backups/climate_eye_view_$(date -u +%Y%m%dT%H%M%SZ).dump"
```

---

## 3. Disaster Recovery & Restore Procedure

### Step-by-Step Restoration Protocol
1. **Quarantine / Isolate**: Halt application ingestion to prevent writes to the damaged database.
   ```bash
   docker compose stop intelligence
   ```
2. **Provision Target Database**: Ensure PostGIS extension is installed and schema is clean.
   ```sql
   DROP DATABASE IF EXISTS climate_eye_view;
   CREATE DATABASE climate_eye_view;
   \c climate_eye_view
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS postgis_topology;
   ```
3. **Restore from Dump**:
   ```bash
   pg_restore \
     --host="${POSTGRES_HOST:-localhost}" \
     --port="${POSTGRES_PORT:-5432}" \
     --username="${POSTGRES_USER:-postgres}" \
     --dbname="climate_eye_view" \
     --clean \
     --if-exists \
     --verbose \
     "/var/backups/climate_eye_view_TARGET_DATE.dump"
   ```
4. **Integrity Verification**: Execute representative verification queries to confirm table counts and coordinate references:
   ```sql
   SELECT count(*) FROM nodes;
   SELECT count(*) FROM sensor_readings;
   SELECT ST_AsText(location) FROM nodes LIMIT 5;
   ```
5. **Resume Application**:
   ```bash
   docker compose start intelligence
   ```

---

---

## 4. Schema Migration & Automated Restore Verification

### Canonical Migration Path
Database schema migrations are source-controlled in `database/migrations/`:
- `001_initial_schema.sql`: Enables `postgis` extension, creates all 9 canonical domain tables, defines primary keys, foreign keys, timestamps, uniqueness constraints (`node_id, timestamp`), and GiST spatial indexes.

### Automated Initialization (Docker Compose)
In containerized environments, `database/migrations/` is mounted to `/docker-entrypoint-initdb.d:ro` on the `postgis` service. PostgreSQL automatically executes all `.sql` scripts in alphabetical order upon initial volume creation.

### Automated Restore Drill Script
The repository provides an automated restore drill script:
```bash
python intelligence/scripts/test_db_restore.py
```
This script:
1. Loads and parses `database/migrations/001_initial_schema.sql`.
2. Validates table DDL, foreign keys, and GiST spatial indexes.
3. Checks live database connectivity via `pg_isready`.
4. If live PostGIS is running, applies schema, seeds records, dumps, resets, restores, and queries data.
5. If live database is offline, validates all DDL statements locally and explicitly reports runtime as `UNVERIFIED` without falsely claiming live execution.

---

## 5. Data Retention Policies

| Data Category | Target Retention Period | Storage Strategy | Purge Mechanism |
| :--- | :--- | :--- | :--- |
| **Raw Telemetry (`sensor_readings`)** | 90 days active | Timescale hypertable chunks / Monthly partitions | Automated drop chunk / partition purge |
| **Hazard & Prediction Evaluations** | 180 days active | Partitioned by evaluation month | Archived to cold storage |
| **Emergency Response Plans** | 3 years (Compliance) | Immutable relational table | Soft-delete / Long-term retention |
| **Digital Twin Simulation States** | 30 days ephemeral | LRU in-memory buffer + temporary table | Automated cleanup cron |
| **Audit & Provenance Logs** | 1 year | Encrypted append-only log storage | Annual rollover |

> [!IMPORTANT]
> Scientific ground truth datasets and benchmark evaluation fixtures are NEVER subject to automatic deletion. They reside in read-only versioned storage.
