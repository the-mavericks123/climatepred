"""
Climate Eye View — Realtime Event Broadcaster.
Enables streaming delivery of intelligence and telemetry events to God's Eye View (GEV)
via WebSockets and Server-Sent Events (SSE).
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
import uuid

from fastapi import WebSocket
from intelligence.core.logging import get_logger

logger = get_logger("realtime_broadcaster")

# Canonical event types defined in Phase 12 architecture
CANONICAL_REALTIME_EVENTS = {
    "telemetry.updated",
    "hazard.updated",
    "prediction.updated",
    "compound.updated",
    "vulnerability.updated",
    "evacuation.updated",
    "response.updated",
    "simulation.completed",
}


class RealtimeBroadcaster:
    """
    Central hub for broadcasting realtime climate intelligence events to connected clients.
    Supports both WebSocket connections and SSE streams.
    Thread-safe and async-safe.
    """

    def __init__(self, history_maxlen: int = 100) -> None:
        self._active_websockets: Set[WebSocket] = set()
        self._sse_subscribers: Set[asyncio.Queue] = set()
        self._history: deque = deque(maxlen=history_maxlen)
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def register_websocket(self, websocket: WebSocket) -> None:
        """Registers a newly connected WebSocket client."""
        await websocket.accept()
        async with self._async_lock:
            self._active_websockets.add(websocket)
        logger.info(
            f"WebSocket client connected. Active connections: {len(self._active_websockets)}"
        )

    async def unregister_websocket(self, websocket: WebSocket) -> None:
        """Unregisters a disconnecting WebSocket client."""
        async with self._async_lock:
            self._active_websockets.discard(websocket)
        logger.info(
            f"WebSocket client disconnected. Active connections: {len(self._active_websockets)}"
        )

    async def subscribe_sse(self) -> AsyncGenerator[str, None]:
        """Subscribes an SSE consumer and yields SSE-formatted events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._async_lock:
            self._sse_subscribers.add(queue)

        try:
            # Yield initial connection confirmation
            yield f"event: ping\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            while True:
                msg = await queue.get()
                yield f"event: {msg['event_type']}\ndata: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with self._async_lock:
                self._sse_subscribers.discard(queue)

    def create_event_packet(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Formats and wraps canonical event packet."""
        return {
            "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously broadcasts an event to all connected WebSockets and SSE queues.
        """
        packet = self.create_event_packet(event_type, data)

        with self._lock:
            self._history.append(packet)

        # Broadcast to WebSockets
        dead_ws: List[WebSocket] = []
        async with self._async_lock:
            current_ws = list(self._active_websockets)
            current_sse = list(self._sse_subscribers)

        for ws in current_ws:
            try:
                await ws.send_json(packet)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                dead_ws.append(ws)

        if dead_ws:
            async with self._async_lock:
                for ws in dead_ws:
                    self._active_websockets.discard(ws)

        # Broadcast to SSE queues
        for q in current_sse:
            try:
                q.put_nowait(packet)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full, dropping event")

        return packet

    def broadcast_sync(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thread-safe synchronous bridge for background worker threads (e.g. MQTT callbacks).
        """
        packet = self.create_event_packet(event_type, data)

        with self._lock:
            self._history.append(packet)

        # If an event loop is running on another thread or current thread, schedule it
        try:
            loop = self._loop or asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), loop)
        except Exception as exc:
            logger.debug(f"Broadcast sync dispatch note: {exc}")

        return packet

    def get_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent broadcast event history."""
        with self._lock:
            events = list(self._history)

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        return events[-limit:]

    def clear(self) -> None:
        """Clears connection sets and history (for test isolation)."""
        with self._lock:
            self._history.clear()


# Global singleton
realtime_broadcaster = RealtimeBroadcaster()
