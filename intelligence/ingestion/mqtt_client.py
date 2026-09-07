"""
Climate Eye View S2 — MQTT Telemetry Ingestion Client.
Provides production-grade MQTT subscription, schema validation, deduplication,
canonical normalization, bounded reconnection, and operational observability.
"""

from datetime import datetime, timezone
import json
import logging
import re
import ssl
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import paho.mqtt.client as mqtt

from intelligence.app.config import settings
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.logging import get_logger
from intelligence.core.metrics.collector import metrics
from intelligence.core.validation.validator import TelemetryValidator
from intelligence.ingestion.deduplication import TelemetryDeduplicator
from intelligence.ingestion.normalized_adapter import NormalizedAdapter
from intelligence.ingestion.source_registry import SourceRegistry

logger = get_logger("mqtt_ingestion")

TELEMETRY_TOPIC_REGEX = re.compile(r"^climate/nodes/([^/]+)/telemetry$")


class ClimateMqttClient:
    """
    Production-grade MQTT subscriber for hardware telemetry ingestion.
    Enforces canonical schema validation, cryptographic deduplication,
    bounded reconnection backoff, and thread-safe operational metrics.
    """

    def __init__(
        self,
        broker_host: Optional[str] = None,
        broker_port: Optional[int] = None,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topic: Optional[str] = None,
        keepalive: Optional[int] = None,
        tls_enabled: Optional[bool] = None,
        deduplicator: Optional[TelemetryDeduplicator] = None,
        adapter: Optional[NormalizedAdapter] = None,
        registry: Optional[SourceRegistry] = None,
        on_telemetry_callback: Optional[Callable[[NormalizedTelemetry], None]] = None,
        reconnect_min_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
    ) -> None:
        self.broker_host = broker_host or settings.mqtt_broker_host
        self.broker_port = broker_port or settings.mqtt_broker_port
        self.client_id = client_id or f"{settings.mqtt_client_id}-{int(time.time())}"
        self.username = username or settings.mqtt_username
        self.password = password or settings.mqtt_password
        self.topic = topic or settings.mqtt_topic_telemetry
        self.keepalive = keepalive or settings.mqtt_keepalive
        self.tls_enabled = tls_enabled if tls_enabled is not None else settings.mqtt_tls_enabled

        self.reconnect_min_delay = reconnect_min_delay
        self.reconnect_max_delay = reconnect_max_delay

        self.deduplicator = deduplicator or TelemetryDeduplicator()
        self.registry = registry or SourceRegistry()
        self.adapter = adapter or NormalizedAdapter(registry=self.registry)
        self.on_telemetry_callback = on_telemetry_callback

        self._client: Optional[mqtt.Client] = None
        self._is_connected = False
        self._is_running = False
        self._lock = threading.Lock()
        self._reconnect_attempts = 0

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._is_connected

    def _init_paho_client(self) -> mqtt.Client:
        """Configures underlying Paho MQTT client with protocol callbacks."""
        # Use MQTTv311 or MQTTv5 (Paho 2.x callback API)
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
                clean_session=True,
            )
        except AttributeError:
            # Fallback for older Paho versions if present
            client = mqtt.Client(client_id=self.client_id, clean_session=True)

        if self.username:
            client.username_pw_set(self.username, self.password)

        if self.tls_enabled:
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

        client.reconnect_delay_set(
            min_delay=int(self.reconnect_min_delay),
            max_delay=int(self.reconnect_max_delay),
        )

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe
        return client

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Connection lifecycle callback; auto-subscribes to configured topic."""
        with self._lock:
            if rc == 0:
                self._is_connected = True
                self._reconnect_attempts = 0
                metrics.set_mqtt_connected(True)
                logger.info(
                    f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}",
                    extra={"extra_data": {"client_id": self.client_id, "topic": self.topic}},
                )
                # Resubscribe after connect / reconnect
                result, mid = client.subscribe(self.topic, qos=1)
                if result != mqtt.MQTT_ERR_SUCCESS:
                    logger.error(f"Failed to subscribe to topic '{self.topic}', code: {result}")
                    metrics.record_mqtt_subscription_failure()
            else:
                self._is_connected = False
                metrics.set_mqtt_connected(False)
                logger.warning(
                    f"MQTT connection refused by broker with return code {rc}",
                    extra={"extra_data": {"broker": self.broker_host, "rc": rc}},
                )

    def _on_disconnect(self, client, userdata, rc, properties=None, reason_code=None):
        """Disconnect lifecycle callback; tracks reconnect attempts."""
        with self._lock:
            self._is_connected = False
            metrics.set_mqtt_connected(False)
            self._reconnect_attempts += 1
            metrics.record_mqtt_reconnect()

        if rc != 0:
            logger.warning(
                f"Unexpected MQTT disconnect from {self.broker_host}:{self.broker_port} (rc={rc}). Reconnecting...",
                extra={"extra_data": {"reconnect_attempt": self._reconnect_attempts}},
            )
        else:
            logger.info("Gracefully disconnected from MQTT broker.")

    def _on_subscribe(self, client, userdata, mid, reason_codes=None, properties=None):
        """Subscription confirmation callback."""
        logger.info(f"Successfully subscribed to MQTT topic: '{self.topic}' (mid={mid})")

    def _on_message(self, client, userdata, msg):
        """
        Processes an incoming MQTT packet:
        1. Validates topic format
        2. Decodes JSON payload
        3. Deduplicates via TelemetryDeduplicator
        4. Validates schema and physical ranges via TelemetryValidator
        5. Normalizes into Canonical NormalizedTelemetry
        6. Updates source heartbeat and dispatches to downstream pipeline
        """
        self.process_raw_message(topic=msg.topic, payload_bytes=msg.payload)

    def process_raw_message(self, topic: str, payload_bytes: bytes) -> Tuple[bool, Optional[NormalizedTelemetry], str]:
        """
        Core message processing logic decoupled for direct unit testability.
        Returns: (success, normalized_telemetry, status_message)
        """
        metrics.record_mqtt_received()

        # 1. Validate topic format
        match = TELEMETRY_TOPIC_REGEX.match(topic)
        if not match:
            metrics.record_mqtt_rejected()
            logger.warning(f"Rejected message from unauthorized/invalid topic format: '{topic}'")
            return False, None, f"Invalid topic format '{topic}'"

        topic_node_id = match.group(1)

        # 2. Decode JSON
        try:
            payload_str = payload_bytes.decode("utf-8")
            payload = json.loads(payload_str)
        except Exception as exc:
            metrics.record_mqtt_rejected()
            logger.warning(f"Malformed JSON payload on topic '{topic}': {exc}")
            return False, None, "Malformed JSON payload"

        if not isinstance(payload, dict):
            metrics.record_mqtt_rejected()
            logger.warning(f"Payload on topic '{topic}' is not a JSON object")
            return False, None, "Payload must be a JSON object"

        # Ensure node_id aligns with topic
        if "node_id" not in payload or not payload["node_id"]:
            payload["node_id"] = topic_node_id
        elif payload["node_id"] != topic_node_id:
            metrics.record_mqtt_rejected()
            logger.warning(
                f"Node ID mismatch: topic specifies '{topic_node_id}', payload specifies '{payload['node_id']}'"
            )
            return False, None, f"Topic node_id '{topic_node_id}' does not match payload '{payload['node_id']}'"

        # Canonicalize field names to match NormalizedTelemetry contract
        if "schema_version" in payload and str(payload["schema_version"]).startswith("1."):
            payload["schema_version"] = "1.0"
        elif "schema_version" not in payload:
            payload["schema_version"] = "1.0"

        # Align measurements vs readings
        if "measurements" not in payload and "readings" in payload and isinstance(payload["readings"], dict):
            payload["measurements"] = dict(payload["readings"])
        elif "readings" not in payload and "measurements" in payload and isinstance(payload["measurements"], dict):
            payload["readings"] = dict(payload["measurements"])

        # Align location coordinates (lat/lon vs latitude/longitude)
        if "location" in payload and isinstance(payload["location"], dict):
            loc = dict(payload["location"])
            if "latitude" in loc and "lat" not in loc:
                loc["lat"] = loc["latitude"]
            if "longitude" in loc and "lon" not in loc:
                loc["lon"] = loc["longitude"]
            if "elevation_m" in loc and "elevation" not in loc:
                loc["elevation"] = loc["elevation_m"]
            payload["location"] = loc

        # Ensure quality metadata is populated
        if "quality" not in payload:
            payload["quality"] = {
                "valid": True,
                "source": payload.get("source", "ESP32"),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        elif isinstance(payload["quality"], dict):
            if "received_at" not in payload["quality"] or not payload["quality"]["received_at"]:
                payload["quality"]["received_at"] = datetime.now(timezone.utc).isoformat()

        # 3. Deduplication Check
        if not self.deduplicator.check_and_record(payload):
            metrics.record_mqtt_duplicate()
            logger.info(
                f"Discarded duplicate telemetry packet for node '{topic_node_id}'",
                extra={"extra_data": {"node_id": topic_node_id}},
            )
            return False, None, "Duplicate telemetry packet"

        # 4. Canonical Schema & Physical Range Validation
        is_valid, telemetry, error_detail = TelemetryValidator.validate_dict(payload)
        if not is_valid or telemetry is None:
            metrics.record_mqtt_rejected()
            err_msg = error_detail.message if error_detail else "Unknown validation error"
            logger.warning(
                f"Rejected invalid telemetry from node '{topic_node_id}': {err_msg}",
                extra={"extra_data": {"node_id": topic_node_id, "error": err_msg}},
            )
            return False, None, f"Validation failed: {err_msg}"

        # 5. Normalization & Heartbeat
        try:
            normalized = self.adapter.adapt(payload)
        except Exception as exc:
            metrics.record_mqtt_rejected()
            logger.error(f"Normalization failed for node '{topic_node_id}': {exc}")
            return False, None, f"Normalization error: {exc}"

        # 6. Downstream Dispatch
        if self.on_telemetry_callback:
            try:
                self.on_telemetry_callback(normalized)
            except Exception as cb_exc:
                logger.error(f"Downstream callback error for node '{topic_node_id}': {cb_exc}", exc_info=True)

        return True, normalized, "Accepted"

    def start(self, non_blocking: bool = True) -> bool:
        """
        Connects to the MQTT broker and starts the background network loop.
        Returns True if connection initiated, False on immediate socket/config failure.
        """
        try:
            self._client = self._init_paho_client()
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self._client.connect_async(self.broker_host, port=self.broker_port, keepalive=self.keepalive)
            self._is_running = True

            if non_blocking:
                self._client.loop_start()
            else:
                self._client.loop_forever()
            return True
        except Exception as exc:
            logger.error(
                f"Failed to connect to MQTT broker {self.broker_host}:{self.broker_port}: {exc}",
                extra={"extra_data": {"broker": self.broker_host, "port": self.broker_port}},
            )
            return False

    def stop(self) -> None:
        """Gracefully stops the network loop and disconnects from the broker."""
        self._is_running = False
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as exc:
                logger.warning(f"Error during MQTT client disconnect: {exc}")
            finally:
                self._client = None
        with self._lock:
            self._is_connected = False
            metrics.set_mqtt_connected(False)
        logger.info("MQTT client stopped cleanly.")
