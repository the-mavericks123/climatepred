# S1 Database & Persistence Subsystem

## Responsibilities

* **Repository Interface:** Abstracts database operations behind a clean service contract (NodeRepository, TelemetryRepository).
* **Storage Options:** Designed to support mock in-memory storage, SQLite/Spatialite, or full PostgreSQL/PostGIS.
* **Geospatial & Time-Series Data:**
  * Node locations (WGS84 Point geometry).
  * Time-series sensor logs indexed by `node_id` and `timestamp`.
* **Connection Lifecycle:** Manages connection pool acquisition and clean shutdown on process exit.
