/**
 * Climate Eye — Frontend WebSocket Realtime Client
 *
 * Browser-safe client that connects to /api/climate/stream, parses the canonical
 * { event, timestamp, payload } envelope, validates events, and dispatches them
 * to registered handlers — supporting integration with the Climate Eye state layer.
 *
 * Design principles:
 * - Same-origin relative URL construction (no hard-coded localhost).
 * - Conservative realtime state transitions (connected socket ≠ LIVE data).
 * - Bounded exponential-backoff reconnect (max retries, no infinite loop).
 * - Fault-isolated: malformed messages, invalid events, and transient errors
 *   never crash the client or propagate uncaught exceptions.
 * - Fully browser-safe: zero Node.js core imports.
 */

export const CLIMATE_STREAM_PATH = '/api/climate/stream';

/** Approved backend event names. Kept in sync with server/realtime/events.js. */
export const APPROVED_EVENTS = Object.freeze([
  'node.updated',
  'telemetry.updated',
  'hazard.updated',
  'prediction.updated',
  'compound.updated',
  'vulnerability.updated',
  'evacuation.updated',
  'response.updated',
  'simulation.completed',
]);

export const APPROVED_EVENT_SET = new Set(APPROVED_EVENTS);

/**
 * Events currently produced by the S1 backend.
 * Others are received if the backend starts producing them; they are never fabricated here.
 */
export const ACTIVE_EVENTS = Object.freeze(['node.updated', 'telemetry.updated']);

/** WebSocket client connection states. */
export const CLIENT_STATES = Object.freeze({
  DISCONNECTED: 'DISCONNECTED',
  CONNECTING:   'CONNECTING',
  CONNECTED:    'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  CLOSING:      'CLOSING',
});

/** Default reconnect configuration. */
const DEFAULT_RECONNECT_OPTIONS = Object.freeze({
  maxRetries:       8,
  initialDelayMs:   1000,
  maxDelayMs:       30000,
  backoffFactor:    2,
});

// ---------------------------------------------------------------------------
// URL Helpers
// ---------------------------------------------------------------------------

/**
 * Derives the WebSocket URL for the Climate Eye realtime stream from the
 * current browser location (or a provided base URL for testing).
 *
 * - Converts http(s) → ws(s) automatically.
 * - Uses same-origin relative construction (no hard-coded host/port).
 * - Accepts an explicit baseUrl for dependency-injected testing.
 *
 * @param {string} [baseUrl] - Optional base URL override (e.g. 'http://localhost:5199').
 * @param {string} [path]    - Stream path (default: CLIMATE_STREAM_PATH).
 * @returns {string} Fully qualified WebSocket URL.
 */
export function buildStreamUrl(baseUrl, path = CLIMATE_STREAM_PATH) {
  let base = baseUrl;

  if (!base) {
    // In a real browser context, derive from current location.
    if (typeof globalThis.location !== 'undefined') {
      const loc = globalThis.location;
      const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      base = `${protocol}//${loc.host}`;
    } else {
      // Fallback for non-browser test environments that inject baseUrl
      throw new Error('buildStreamUrl: no baseUrl provided and globalThis.location is unavailable');
    }
  }

  // Convert http(s) → ws(s)
  const normalized = base.replace(/^https:/i, 'wss:').replace(/^http:/i, 'ws:');

  // Clean trailing slash
  const cleanBase = normalized.replace(/\/+$/, '');
  // Ensure path starts with /
  const cleanPath = path.startsWith('/') ? path : `/${path}`;

  return `${cleanBase}${cleanPath}`;
}

// ---------------------------------------------------------------------------
// Envelope Validation
// ---------------------------------------------------------------------------

/**
 * Validates a parsed WebSocket message envelope from the Climate Eye backend.
 *
 * Expected shape: { event: string, timestamp: string, payload: any }
 *
 * @param {any} raw
 * @returns {{ valid: true, envelope: object } | { valid: false, reason: string }}
 */
export function validateEnvelope(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { valid: false, reason: 'Envelope must be a plain object' };
  }

  const { event, timestamp, payload } = raw;

  if (typeof event !== 'string' || !event.trim()) {
    return { valid: false, reason: `Invalid event field: ${JSON.stringify(event)}` };
  }

  if (!APPROVED_EVENT_SET.has(event)) {
    return { valid: false, reason: `Unknown event type: "${event}"` };
  }

  if (typeof timestamp !== 'string' || !timestamp.trim()) {
    return { valid: false, reason: `Invalid timestamp field: ${JSON.stringify(timestamp)}` };
  }

  if (payload === undefined) {
    return { valid: false, reason: 'Missing payload field' };
  }

  return { valid: true, envelope: { event, timestamp, payload } };
}

// ---------------------------------------------------------------------------
// Climate Realtime Client
// ---------------------------------------------------------------------------

/**
 * Creates a browser-safe Climate Eye WebSocket realtime client.
 *
 * @param {object} [options]
 * @param {string}  [options.baseUrl]       - Base URL for stream endpoint (default: same-origin).
 * @param {string}  [options.path]          - Stream path (default: /api/climate/stream).
 * @param {object}  [options.reconnect]     - Reconnect behavior overrides.
 * @param {typeof WebSocket} [options.WebSocket] - Injectable WebSocket constructor for tests.
 * @param {function} [options.onEvent]      - Called with a validated envelope on each message.
 * @param {function} [options.onStateChange] - Called with (clientState) when connection state changes.
 * @param {function} [options.onError]      - Called with a normalized error object.
 */
export function createClimateRealtimeClient({
  baseUrl,
  path = CLIMATE_STREAM_PATH,
  reconnect: reconnectConfig = {},
  WebSocket: WebSocketImpl = globalThis.WebSocket,
  onEvent,
  onStateChange,
  onError,
} = {}) {
  if (typeof WebSocketImpl !== 'function') {
    throw new TypeError('createClimateRealtimeClient: WebSocket implementation is not available');
  }

  const reconnectOpts = { ...DEFAULT_RECONNECT_OPTIONS, ...reconnectConfig };

  let socket = null;
  let clientState = CLIENT_STATES.DISCONNECTED;
  let retryCount = 0;
  let retryTimeoutId = null;
  let intentionalClose = false;

  // Cached event handlers registered externally
  const eventHandlers = new Map(); // event name → Set<handler>

  // ── Internal helpers ─────────────────────────────────────────────────────

  function setState(next) {
    if (next === clientState) return;
    clientState = next;
    try {
      onStateChange?.(clientState);
    } catch (_) {}
  }

  function emitError(message, detail = null) {
    try {
      onError?.({ message, detail, timestamp: new Date().toISOString() });
    } catch (_) {}
  }

  function dispatchEnvelope(envelope) {
    // Call generic onEvent handler
    try {
      onEvent?.(envelope);
    } catch (_) {}

    // Call per-event registered handlers
    const handlers = eventHandlers.get(envelope.event);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(envelope);
        } catch (_) {}
      }
    }
  }

  function clearRetryTimer() {
    if (retryTimeoutId !== null) {
      clearTimeout(retryTimeoutId);
      retryTimeoutId = null;
    }
  }

  function scheduleReconnect() {
    if (intentionalClose) return;
    if (retryCount >= reconnectOpts.maxRetries) {
      setState(CLIENT_STATES.DISCONNECTED);
      emitError(`Max reconnect attempts (${reconnectOpts.maxRetries}) reached. Stopped reconnecting.`);
      return;
    }

    const delay = Math.min(
      reconnectOpts.initialDelayMs * Math.pow(reconnectOpts.backoffFactor, retryCount),
      reconnectOpts.maxDelayMs
    );

    setState(CLIENT_STATES.RECONNECTING);
    retryCount++;

    retryTimeoutId = setTimeout(() => {
      retryTimeoutId = null;
      if (!intentionalClose) {
        _openSocket();
      }
    }, delay);
  }

  function _openSocket() {
    // Guard: never open a second socket while one exists
    if (socket !== null) return;

    let url;
    try {
      url = buildStreamUrl(baseUrl, path);
    } catch (err) {
      setState(CLIENT_STATES.DISCONNECTED);
      emitError(`Failed to build WebSocket URL: ${err.message}`);
      return;
    }

    setState(CLIENT_STATES.CONNECTING);

    let ws;
    try {
      ws = new WebSocketImpl(url);
    } catch (err) {
      socket = null;
      emitError(`WebSocket constructor failed: ${err.message}`);
      setState(CLIENT_STATES.DISCONNECTED);
      scheduleReconnect();
      return;
    }

    socket = ws;

    ws.onopen = () => {
      retryCount = 0; // Reset retry counter on successful connection
      // Connected, but NOT automatically LIVE — actual telemetry arriving determines LIVE status.
      setState(CLIENT_STATES.CONNECTED);
    };

    ws.onmessage = (event) => {
      const raw = event.data;

      // 1. Parse JSON safely
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch {
        emitError('Received non-JSON message from realtime stream', { raw: String(raw).slice(0, 200) });
        return; // Do NOT close on malformed — fault-isolated
      }

      // 2. Validate envelope
      const result = validateEnvelope(parsed);
      if (!result.valid) {
        emitError(`Invalid realtime envelope: ${result.reason}`, { raw: parsed });
        return; // Do NOT close — fault-isolated
      }

      // 3. Dispatch validated envelope
      dispatchEnvelope(result.envelope);
    };

    ws.onerror = (errorEvent) => {
      emitError('WebSocket connection error', {
        message: errorEvent?.message || 'Unknown WebSocket error',
      });
      // Do NOT call scheduleReconnect here — onclose always fires after onerror
    };

    ws.onclose = (closeEvent) => {
      const wasConnected = socket === ws;
      socket = null;

      if (intentionalClose) {
        setState(CLIENT_STATES.DISCONNECTED);
        return;
      }

      if (wasConnected) {
        scheduleReconnect();
      }
    };
  }

  // ── Public API ────────────────────────────────────────────────────────────

  function connect() {
    if (
      clientState === CLIENT_STATES.CONNECTED ||
      clientState === CLIENT_STATES.CONNECTING
    ) {
      return; // Already connecting or connected — idempotent
    }

    intentionalClose = false;
    clearRetryTimer();
    _openSocket();
  }

  function disconnect() {
    intentionalClose = true;
    clearRetryTimer();
    setState(CLIENT_STATES.CLOSING);

    if (socket !== null) {
      try {
        socket.close(1000, 'Client disconnected');
      } catch (_) {}
    } else {
      setState(CLIENT_STATES.DISCONNECTED);
    }
  }

  function reconnect() {
    disconnect();
    // Re-enable intentional reconnect after clean close
    retryTimeoutId = setTimeout(() => {
      intentionalClose = false;
      retryCount = 0;
      connect();
    }, 0);
  }

  function getConnectionState() {
    return clientState;
  }

  /**
   * Register a per-event handler for a specific approved event type.
   *
   * @param {string} eventName
   * @param {function} handler
   * @returns {function} Unregister function
   */
  function on(eventName, handler) {
    if (typeof handler !== 'function') {
      throw new TypeError('on() requires a function handler');
    }
    if (!APPROVED_EVENT_SET.has(eventName)) {
      throw new Error(`Unknown event type: "${eventName}". Must be one of: ${APPROVED_EVENTS.join(', ')}`);
    }
    if (!eventHandlers.has(eventName)) {
      eventHandlers.set(eventName, new Set());
    }
    eventHandlers.get(eventName).add(handler);

    return function off() {
      eventHandlers.get(eventName)?.delete(handler);
    };
  }

  return {
    connect,
    disconnect,
    reconnect,
    getConnectionState,
    on,
  };
}

// ---------------------------------------------------------------------------
// State-Integrated Client Factory
// ---------------------------------------------------------------------------

/**
 * Creates a ClimateRealtimeClient pre-wired to dispatch approved realtime events
 * into a Climate Eye state store instance.
 *
 * - `node.updated` → `store.updateNode(payload)`
 * - `telemetry.updated` → `store.updateTelemetry(payload)`
 * - `hazard.updated` → `store.updateHazard(payload)`
 * - `prediction.updated` → `store.updatePrediction(payload)`
 * - `compound.updated` → `store.updateCompound(payload)`
 * - `vulnerability.updated` → `store.updateVulnerability(payload)`
 * - `evacuation.updated` → `store.updateEvacuation(payload)`
 * - `response.updated` → `store.updateResponse(payload)`
 * - `simulation.completed` → `store.completeSimulation(payload)`
 *
 * Connection state transitions:
 * - `CONNECTED` → sets `STALE` (not automatically LIVE; actual data determines LIVE)
 * - `DISCONNECTED` → sets `UNAVAILABLE`
 * - `RECONNECTING` → sets `STALE`
 *
 * @param {object} store - A Climate Eye state store (`createClimateStore()` instance).
 * @param {object} [clientOptions] - Options forwarded to `createClimateRealtimeClient`.
 * @returns {object} The realtime client instance.
 */
export function createStateIntegratedRealtimeClient(store, clientOptions = {}) {
  if (!store || typeof store.dispatch !== 'function') {
    throw new TypeError('createStateIntegratedRealtimeClient: requires a valid Climate Eye state store');
  }

  function onEvent(envelope) {
    const { event, payload } = envelope;

    // Dispatch only for events that actually arrive; never fabricate
    switch (event) {
      case 'node.updated':
        store.updateNode(payload);
        // Transition to LIVE once we receive real node data
        store.setRealtimeState('LIVE', { connected: true, timestamp: envelope.timestamp });
        break;

      case 'telemetry.updated':
        store.updateTelemetry(payload);
        store.setRealtimeState('LIVE', { connected: true, timestamp: envelope.timestamp });
        break;

      case 'hazard.updated':
        store.updateHazard(payload);
        break;

      case 'prediction.updated':
        store.updatePrediction(payload);
        break;

      case 'compound.updated':
        store.updateCompound(payload);
        break;

      case 'vulnerability.updated':
        store.updateVulnerability(payload);
        break;

      case 'evacuation.updated':
        store.updateEvacuation(payload);
        break;

      case 'response.updated':
        store.updateResponse(payload);
        break;

      case 'simulation.completed':
        store.completeSimulation(payload);
        break;

      default:
        // Unknown events are silently ignored — fault-isolated
        break;
    }
  }

  function onStateChange(clientState) {
    switch (clientState) {
      case CLIENT_STATES.CONNECTED:
        // Connected but no data yet — STALE (not LIVE)
        store.setRealtimeState('STALE', { connected: true });
        break;

      case CLIENT_STATES.DISCONNECTED:
        store.setRealtimeState('UNAVAILABLE', { connected: false });
        break;

      case CLIENT_STATES.RECONNECTING:
        store.setRealtimeState('STALE', { connected: false });
        break;

      default:
        break;
    }
  }

  const client = createClimateRealtimeClient({
    ...clientOptions,
    onEvent,
    onStateChange,
  });

  return client;
}
