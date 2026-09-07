"""Telemetry Packet Deduplication using sliding window of message signatures."""
import hashlib
import json
import time
import threading
from typing import Dict, Any, Optional
from collections import OrderedDict

class TelemetryDeduplicator:
    """Thread-safe bounded sliding window deduplicator for MQTT/sensor telemetry."""
    
    def __init__(self, max_signatures: int = 10000, ttl_sec: float = 300.0):
        self.max_signatures = max_signatures
        self.ttl_sec = ttl_sec
        self._signatures: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def _generate_signature(self, packet: Dict[str, Any]) -> str:
        # Check if explicit message_id or packet_id exists
        if "message_id" in packet and packet["message_id"]:
            return f"id:{packet['message_id']}"
        if "packet_id" in packet and packet["packet_id"]:
            return f"id:{packet['packet_id']}"
            
        # Fallback to deterministic hash of node_id, timestamp, and core sensor readings
        node_id = str(packet.get("node_id", ""))
        timestamp = str(packet.get("timestamp", ""))
        readings = packet.get("readings", {})
        
        # Canonicalize readings to sorted key-value pairs
        canonical_readings = []
        if isinstance(readings, dict):
            for k in sorted(readings.keys()):
                val = readings[k]
                if isinstance(val, float):
                    canonical_readings.append(f"{k}:{round(val, 4)}")
                else:
                    canonical_readings.append(f"{k}:{val}")
        
        sig_str = f"{node_id}|{timestamp}|{','.join(canonical_readings)}"
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

    def _purge_expired(self, current_time: float) -> None:
        cutoff = current_time - self.ttl_sec
        # OrderedDict maintains insertion order
        while self._signatures:
            first_key = next(iter(self._signatures))
            if self._signatures[first_key] < cutoff:
                del self._signatures[first_key]
            else:
                break

    def is_duplicate(self, packet: Dict[str, Any]) -> bool:
        sig = self._generate_signature(packet)
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            if sig in self._signatures:
                return True
            return False

    def check_and_record(self, packet: Dict[str, Any]) -> bool:
        """Returns True if the packet is NEW and recorded. Returns False if DUPLICATE."""
        sig = self._generate_signature(packet)
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            if sig in self._signatures:
                return False  # Duplicate
                
            # If at capacity, pop the oldest
            if len(self._signatures) >= self.max_signatures:
                self._signatures.popitem(last=False)
                
            self._signatures[sig] = now
            return True

    def clear(self) -> None:
        with self._lock:
            self._signatures.clear()
