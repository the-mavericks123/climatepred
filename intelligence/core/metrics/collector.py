"""Operational Metrics Collector for Climate Eye View."""
import time
from typing import Dict, Any, List
from collections import defaultdict, deque
import threading

class MetricsCollector:
    """Thread-safe operational metrics collector."""
    
    def __init__(self, max_latency_samples: int = 1000):
        self._lock = threading.Lock()
        self.max_latency_samples = max_latency_samples
        
        # Counters
        self.request_count: Dict[str, int] = defaultdict(int)
        self.error_count: Dict[str, int] = defaultdict(int)
        self.mqtt_messages_received: int = 0
        self.mqtt_messages_rejected: int = 0
        self.mqtt_messages_duplicate: int = 0
        self.mqtt_connected: bool = False
        self.mqtt_reconnect_attempts: int = 0
        self.mqtt_subscription_failures: int = 0
        self.stale_nodes_count: int = 0
        
        # Duration/Latency samples (in seconds)
        self.endpoint_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.max_latency_samples))
        self.database_latencies: deque = deque(maxlen=self.max_latency_samples)
        self.intelligence_latencies: deque = deque(maxlen=self.max_latency_samples)
        self.simulation_durations: deque = deque(maxlen=self.max_latency_samples)
        self.evaluation_durations: deque = deque(maxlen=self.max_latency_samples)
        self.calibration_durations: deque = deque(maxlen=self.max_latency_samples)

    def record_request(self, endpoint: str, status_code: int, duration_sec: float) -> None:
        with self._lock:
            key = f"{endpoint}:{status_code}"
            self.request_count[key] += 1
            self.endpoint_latencies[endpoint].append(duration_sec)
            if status_code >= 400:
                self.error_count[str(status_code)] += 1

    def record_error(self, error_type: str) -> None:
        with self._lock:
            self.error_count[error_type] += 1

    def record_mqtt_received(self, count: int = 1) -> None:
        with self._lock:
            self.mqtt_messages_received += count

    def record_mqtt_rejected(self, count: int = 1) -> None:
        with self._lock:
            self.mqtt_messages_rejected += count

    def record_mqtt_duplicate(self, count: int = 1) -> None:
        with self._lock:
            self.mqtt_messages_duplicate += count

    def set_mqtt_connected(self, connected: bool) -> None:
        with self._lock:
            self.mqtt_connected = connected

    def record_mqtt_reconnect(self, count: int = 1) -> None:
        with self._lock:
            self.mqtt_reconnect_attempts += count

    def record_mqtt_subscription_failure(self, count: int = 1) -> None:
        with self._lock:
            self.mqtt_subscription_failures += count

    def set_stale_nodes(self, count: int) -> None:
        with self._lock:
            self.stale_nodes_count = count

    def record_database_latency(self, duration_sec: float) -> None:
        with self._lock:
            self.database_latencies.append(duration_sec)

    def record_intelligence_latency(self, duration_sec: float) -> None:
        with self._lock:
            self.intelligence_latencies.append(duration_sec)

    def record_simulation_duration(self, duration_sec: float) -> None:
        with self._lock:
            self.simulation_durations.append(duration_sec)

    def record_evaluation_duration(self, duration_sec: float) -> None:
        with self._lock:
            self.evaluation_durations.append(duration_sec)

    def record_calibration_duration(self, duration_sec: float) -> None:
        with self._lock:
            self.calibration_durations.append(duration_sec)

    def _calc_stats(self, samples: deque) -> Dict[str, float]:
        if not samples:
            return {"count": 0, "avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        vals = sorted(list(samples))
        n = len(vals)
        avg = sum(vals) / n
        p95_idx = int(0.95 * (n - 1))
        return {
            "count": n,
            "avg_ms": round(avg * 1000.0, 2),
            "p95_ms": round(vals[p95_idx] * 1000.0, 2),
            "max_ms": round(vals[-1] * 1000.0, 2)
        }

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total_requests = sum(self.request_count.values())
            total_errors = sum(self.error_count.values())
            return {
                "timestamp": time.time(),
                "requests": {
                    "total": total_requests,
                    "by_endpoint_and_status": dict(self.request_count),
                },
                "errors": {
                    "total": total_errors,
                    "by_type": dict(self.error_count)
                },
                "mqtt": {
                    "connected": self.mqtt_connected,
                    "received": self.mqtt_messages_received,
                    "rejected": self.mqtt_messages_rejected,
                    "duplicate": self.mqtt_messages_duplicate,
                    "reconnect_attempts": self.mqtt_reconnect_attempts,
                    "subscription_failures": self.mqtt_subscription_failures,
                    "stale_nodes": self.stale_nodes_count,
                },
                "latencies_ms": {
                    "database": self._calc_stats(self.database_latencies),
                    "intelligence": self._calc_stats(self.intelligence_latencies),
                    "simulation": self._calc_stats(self.simulation_durations),
                    "evaluation": self._calc_stats(self.evaluation_durations),
                    "calibration": self._calc_stats(self.calibration_durations)
                }
            }

    def reset(self) -> None:
        with self._lock:
            self.request_count.clear()
            self.error_count.clear()
            self.mqtt_messages_received = 0
            self.mqtt_messages_rejected = 0
            self.mqtt_messages_duplicate = 0
            self.mqtt_connected = False
            self.mqtt_reconnect_attempts = 0
            self.mqtt_subscription_failures = 0
            self.stale_nodes_count = 0
            self.endpoint_latencies.clear()
            self.database_latencies.clear()
            self.intelligence_latencies.clear()
            self.simulation_durations.clear()
            self.evaluation_durations.clear()
            self.calibration_durations.clear()

# Global Singleton
metrics = MetricsCollector()
