/**
 * Climate Eye Realtime WebSocket Server
 *
 * Provides a dedicated, pathname-isolated WebSocket transport on `/api/climate/stream`
 * that guarantees zero interference with Vite's internal Hot Module Replacement (HMR).
 * Conforms to DECISION-005.
 */

'use strict';

import { WebSocketServer, WebSocket } from 'ws';
import { formatRealtimeEnvelope, REALTIME_STATES, isValidRealtimeEvent } from './events.js';

export const CLIMATE_STREAM_PATH = '/api/climate/stream';

export class ClimateRealtimeServer {
  /**
   * @param {object} [options]
   * @param {string} [options.path] - WebSocket endpoint pathname (default: '/api/climate/stream').
   * @param {object} [options.httpServer] - Node HTTP server to attach upgrade listener.
   * @param {string} [options.s2WsUrl] - S2 WebSocket URL for event bridging.
   */
  constructor(options = {}) {
    this.path = options.path || CLIMATE_STREAM_PATH;
    this.httpServer = options.httpServer || null;
    this.s2WsUrl = options.s2WsUrl || process.env.S2_WS_URL || 'ws://127.0.0.1:8000/api/v1/events/ws';
    this.clients = new Set();
    this.isStarted = false;
    this.upgradeHandler = null;
    this.streamState = REALTIME_STATES.UNAVAILABLE;
    this._s2WsClient = null;
    this._s2ReconnectTimer = null;

    // WebSocketServer configured with noServer: true for manual pathname-gated upgrades
    this.wss = new WebSocketServer({ noServer: true });

    this.wss.on('connection', (ws, req) => {
      this._handleConnection(ws, req);
    });
  }

  /**
   * Starts the realtime server and binds to the HTTP upgrade lifecycle.
   * Repeated calls are idempotent and will not register duplicate listeners.
   *
   * @param {object} [httpServer] - Optional HTTP server instance.
   */
  start(httpServer = this.httpServer) {
    if (this.isStarted) return;

    if (httpServer) {
      this.httpServer = httpServer;
    }

    if (this.httpServer && typeof this.httpServer.on === 'function') {
      this.upgradeHandler = (req, socket, head) => {
        this.handleUpgrade(req, socket, head);
      };
      this.httpServer.on('upgrade', this.upgradeHandler);
    }

    this.isStarted = true;

    if (this.s2WsUrl) {
      this.connectS2Bridge(this.s2WsUrl);
    }
  }

  /**
   * Bridges realtime events from the S2 Intelligence WebSocket server.
   * Auto-reconnects with exponential backoff if S2 is restarting.
   *
   * @param {string} [s2WsUrl] - WebSocket URL to S2 (e.g. ws://127.0.0.1:8000/api/v1/events/ws).
   */
  connectS2Bridge(s2WsUrl = this.s2WsUrl) {
    if (this._s2WsClient) {
      try { this._s2WsClient.close(); } catch {}
      this._s2WsClient = null;
    }
    if (this._s2ReconnectTimer) {
      clearTimeout(this._s2ReconnectTimer);
      this._s2ReconnectTimer = null;
    }

    let delayMs = 2000;
    const maxDelayMs = 30000;

    const connect = () => {
      if (!this.isStarted) return;
      try {
        const ws = new WebSocket(s2WsUrl);
        this._s2WsClient = ws;

        ws.on('open', () => {
          delayMs = 2000;
          this.streamState = REALTIME_STATES.LIVE;
        });

        ws.on('message', (data) => {
          try {
            const raw = JSON.parse(data.toString());
            const eventName = raw.event_type || raw.event;
            const payload = raw.data !== undefined ? raw.data : raw.payload;
            if (eventName && isValidRealtimeEvent(eventName)) {
              this.broadcast(eventName, payload);
            }
          } catch {}
        });

        ws.on('error', () => {});

        ws.on('close', () => {
          this._s2WsClient = null;
          if (this.isStarted) {
            this._s2ReconnectTimer = setTimeout(() => {
              delayMs = Math.min(delayMs * 1.5, maxDelayMs);
              connect();
            }, delayMs);
          }
        });
      } catch {
        if (this.isStarted) {
          this._s2ReconnectTimer = setTimeout(connect, delayMs);
        }
      }
    };

    connect();
  }

  /**
   * Intercepts HTTP upgrade requests. Only upgrades requests whose pathname exactly
   * matches this.path (/api/climate/stream). All other upgrades (including Vite HMR)
   * are completely ignored without modifying or closing the socket.
   *
   * @param {object} req - HTTP request.
   * @param {object} socket - Network socket.
   * @param {Buffer} head - Upgrade buffer head.
   * @returns {boolean} True if handled by Climate Eye, false if passed through.
   */
  handleUpgrade(req, socket, head) {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname !== this.path) {
        // Pathname does not match Climate Eye stream endpoint.
        // DO NOT touch socket — allow Vite HMR or other upgrade handlers to process it.
        return false;
      }

      this.wss.handleUpgrade(req, socket, head, (ws) => {
        this.wss.emit('connection', ws, req);
      });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Internal connection lifecycle registration.
   *
   * @private
   * @param {WebSocket} ws
   * @param {object} req
   */
  _handleConnection(ws, req) {
    this.clients.add(ws);

    // Guard against unhandled socket error exceptions
    ws.on('error', () => {
      // Swallowed safely; client will be cleaned up on close event
    });

    ws.on('close', () => {
      this.clients.delete(ws);
    });
  }

  /**
   * Broadcasts an approved Climate Eye realtime event to all connected clients.
   * A broken or throwing client will not crash the server or affect other clients.
   *
   * @param {string} event - Approved event name (e.g. 'node.updated').
   * @param {any} payload - Event payload.
   * @returns {number} Count of clients the message was successfully dispatched to.
   */
  broadcast(event, payload) {
    if (!this.isStarted || this.clients.size === 0) return 0;

    const message = formatRealtimeEnvelope(event, payload);
    let sentCount = 0;

    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send(message);
          sentCount++;
        } catch {
          // Fault isolation: broken client is ignored and does not crash the server
        }
      }
    }

    return sentCount;
  }

  /**
   * Returns the count of currently connected WebSocket clients.
   *
   * @returns {number}
   */
  getClientCount() {
    return this.clients.size;
  }

  /**
   * Gracefully shuts down the realtime server, closes all connected client sockets,
   * detaches HTTP upgrade listeners, and resets state.
   * Repeated calls are idempotent and safe.
   */
  stop() {
    if (!this.isStarted) return;
    this.isStarted = false;

    // Detach upgrade handler from HTTP server
    if (this.httpServer && this.upgradeHandler) {
      if (typeof this.httpServer.off === 'function') {
        this.httpServer.off('upgrade', this.upgradeHandler);
      } else if (typeof this.httpServer.removeListener === 'function') {
        this.httpServer.removeListener('upgrade', this.upgradeHandler);
      }
      this.upgradeHandler = null;
    }

    if (this._s2ReconnectTimer) {
      clearTimeout(this._s2ReconnectTimer);
      this._s2ReconnectTimer = null;
    }
    if (this._s2WsClient) {
      try { this._s2WsClient.close(); } catch {}
      this._s2WsClient = null;
    }

    // Terminate all client connections cleanly
    for (const client of this.clients) {
      try {
        client.close(1001, 'Climate Eye server shutdown');
      } catch {
        // ignore
      }
    }
    this.clients.clear();

    try {
      this.wss.close();
    } catch {
      // ignore
    }
  }

  /**
   * Returns current transport status.
   *
   * @returns {object}
   */
  status() {
    return {
      state: this.isStarted ? 'running' : 'stopped',
      streamState: this.streamState,
      clientCount: this.getClientCount(),
      endpoint: this.path,
    };
  }
}

/**
 * Factory function for creating a ClimateRealtimeServer.
 *
 * @param {object} [options]
 * @returns {ClimateRealtimeServer}
 */
export function createClimateRealtimeServer(options = {}) {
  return new ClimateRealtimeServer(options);
}
