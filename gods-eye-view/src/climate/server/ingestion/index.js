/**
 * Climate Eye S1 — Ingestion Layer Entry Point
 *
 * Exposes the TelemetryIngestionOrchestrator for binding MQTT message transport
 * to database repository persistence.
 */

'use strict';

import {
  createIngestionOrchestrator,
  ORCHESTRATOR_STATES,
} from './orchestrator.js';

export {
  createIngestionOrchestrator,
  ORCHESTRATOR_STATES,
};
