/**
 * Climate Eye S1 — API Subsystem Entry Point
 *
 * Exposes the Climate Eye API router, handlers, and response utilities.
 */

'use strict';

import { createClimateApiRouter } from './router.js';
import {
  handleHealth,
  handleListNodes,
  handleGetNode,
  handleGetNodeTelemetry,
  handleNotImplemented,
  sendJson,
  sendError,
  isValidNodeId,
} from './handlers.js';

export {
  createClimateApiRouter,
  handleHealth,
  handleListNodes,
  handleGetNode,
  handleGetNodeTelemetry,
  handleNotImplemented,
  sendJson,
  sendError,
  isValidNodeId,
};
