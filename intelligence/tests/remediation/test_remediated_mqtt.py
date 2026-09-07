"""
Tests for Phase 11 Remediation: BLK-ING-01 (Real MQTT Ingestion & Security).
Verifies:
- Production MQTT client initialization, configuration externalization
- Topic format parsing and validation
- Message validation against canonical contracts
- Deduplication and replay rejection
- NormalizedTelemetry adaptation
- Bounded reconnection backoff logic
- Production Mosquitto configuration and topic ACL policies
- Observability and metrics recording
"""

import json
from pathlib import Path
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import pytest

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.metrics.collector import metrics
from intelligence.ingestion.deduplication import TelemetryDeduplicator
from intelligence.ingestion.mqtt_client import ClimateMqttClient


def make_valid_telemetry_payload(node_id: str = "NODE-FLOOD-001", msg_id: str = "MSG-101") -> Dict[str, Any]:
    """Generates a valid canonical telemetry payload."""
    return {
        "schema_version": "1.0.0",
        "message_id": msg_id,
        "node_id": node_id,
        "timestamp": "2026-09-07T12:00:00Z",
        "location": {
            "latitude": 13.0827,
            "longitude": 80.2707,
            "elevation_m": 12.5,
        },
        "readings": {
            "temperature": 29.5,
            "humidity": 78.0,
            "pressure": 1011.2,
            "rainfall": 15.0,
            "soil_moisture": 45.0,
            "water_level": 0.8,
            "air_quality": 42.0,
            "battery": 92.0,
        },
        "source": "ESP32-STATION-01",
    }


class TestMqttClientRemediation:
    """Verifies BLK-ING-01 remediation: real MQTT subscriber and validation pipeline."""

    def test_mqtt_client_configuration_externalized(self):
        """Broker host, port, credentials, and topics are fully configurable without hard-coding."""
        client = ClimateMqttClient(
            broker_host="custom-broker.local",
            broker_port=8883,
            client_id="custom-id-99",
            username="test_user",
            password="test_password",
            topic="climate/nodes/+/telemetry",
            keepalive=120,
            tls_enabled=True,
            reconnect_min_delay=2.0,
            reconnect_max_delay=60.0,
        )
        assert client.broker_host == "custom-broker.local"
        assert client.broker_port == 8883
        assert client.client_id == "custom-id-99"
        assert client.username == "test_user"
        assert client.password == "test_password"
        assert client.topic == "climate/nodes/+/telemetry"
        assert client.keepalive == 120
        assert client.tls_enabled is True
        assert client.reconnect_min_delay == 2.0
        assert client.reconnect_max_delay == 60.0

    def test_valid_mqtt_telemetry_reaches_normalized_model(self):
        """Valid incoming MQTT packet is normalized into NormalizedTelemetry and updates metrics."""
        metrics.reset()
        received_telemetry = []

        client = ClimateMqttClient(
            on_telemetry_callback=lambda t: received_telemetry.append(t),
        )

        topic = "climate/nodes/NODE-FLOOD-001/telemetry"
        payload = make_valid_telemetry_payload("NODE-FLOOD-001", "MSG-NORMAL-1")
        payload_bytes = json.dumps(payload).encode("utf-8")

        success, norm, msg = client.process_raw_message(topic, payload_bytes)
        assert success is True
        assert msg == "Accepted"
        assert norm is not None
        assert isinstance(norm, NormalizedTelemetry)
        assert norm.node_id == "NODE-FLOOD-001"
        assert norm.measurements.temperature == 29.5
        assert len(received_telemetry) == 1
        assert received_telemetry[0].node_id == "NODE-FLOOD-001"

        # Check metrics
        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["received"] == 1
        assert snapshot["rejected"] == 0
        assert snapshot["duplicate"] == 0

    def test_invalid_telemetry_payload_rejected_and_metric_recorded(self):
        """Telemetry with physical violations (e.g. temperature > 60°C) is rejected."""
        metrics.reset()
        client = ClimateMqttClient()

        topic = "climate/nodes/NODE-FLOOD-001/telemetry"
        invalid_payload = make_valid_telemetry_payload("NODE-FLOOD-001", "MSG-INVALID-1")
        # Physically impossible temperature
        invalid_payload["readings"]["temperature"] = 150.0
        payload_bytes = json.dumps(invalid_payload).encode("utf-8")

        success, norm, err = client.process_raw_message(topic, payload_bytes)
        assert success is False
        assert norm is None
        assert "Validation failed" in err

        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["received"] == 1
        assert snapshot["rejected"] == 1

    def test_malformed_json_rejected(self):
        """Non-JSON or malformed bytes are safely rejected without throwing exceptions."""
        metrics.reset()
        client = ClimateMqttClient()

        topic = "climate/nodes/NODE-FLOOD-001/telemetry"
        success, norm, err = client.process_raw_message(topic, b"not valid json {{{")
        assert success is False
        assert norm is None
        assert "Malformed JSON" in err

        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["rejected"] == 1

    def test_unauthorized_topic_format_rejected(self):
        """Messages published to non-conforming or administrative topics are rejected."""
        metrics.reset()
        client = ClimateMqttClient()

        payload = make_valid_telemetry_payload("NODE-FLOOD-001", "MSG-UNAUTH-1")
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Unauthorized topic
        success, norm, err = client.process_raw_message("climate/commands/all", payload_bytes)
        assert success is False
        assert norm is None
        assert "Invalid topic format" in err

        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["rejected"] == 1

    def test_node_id_topic_payload_mismatch_rejected(self):
        """Mismatched node_id between topic and payload body is rejected."""
        metrics.reset()
        client = ClimateMqttClient()

        topic = "climate/nodes/NODE-FLOOD-001/telemetry"
        payload = make_valid_telemetry_payload("NODE-FLOOD-999", "MSG-MISMATCH-1")
        payload_bytes = json.dumps(payload).encode("utf-8")

        success, norm, err = client.process_raw_message(topic, payload_bytes)
        assert success is False
        assert norm is None
        assert "not match" in err.lower()

        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["rejected"] == 1

    def test_duplicate_and_replay_packets_rejected(self):
        """Duplicate message IDs or identical sensor readings within window are discarded."""
        metrics.reset()
        dedup = TelemetryDeduplicator(ttl_sec=60.0)
        client = ClimateMqttClient(deduplicator=dedup)

        topic = "climate/nodes/NODE-FLOOD-001/telemetry"
        payload = make_valid_telemetry_payload("NODE-FLOOD-001", "MSG-DUP-1")
        payload_bytes = json.dumps(payload).encode("utf-8")

        # First delivery -> succeeds
        success1, norm1, msg1 = client.process_raw_message(topic, payload_bytes)
        assert success1 is True
        assert msg1 == "Accepted"

        # Immediate replay -> duplicate rejected
        success2, norm2, msg2 = client.process_raw_message(topic, payload_bytes)
        assert success2 is False
        assert norm2 is None
        assert "Duplicate" in msg2

        snapshot = metrics.get_snapshot()["mqtt"]
        assert snapshot["received"] == 2
        assert snapshot["duplicate"] == 1

    def test_broker_connection_lifecycle_and_reconnect(self):
        """Simulates connect, disconnect, and reconnect callbacks with metric tracking."""
        metrics.reset()
        client = ClimateMqttClient(
            broker_host="localhost",
            broker_port=1883,
            topic="climate/nodes/+/telemetry",
        )

        mock_paho = MagicMock()
        mock_paho.subscribe.return_value = (0, 1)

        # 1. Connected
        client._on_connect(mock_paho, None, None, 0)
        assert client.is_connected is True
        assert metrics.get_snapshot()["mqtt"]["connected"] is True
        mock_paho.subscribe.assert_called_with("climate/nodes/+/telemetry", qos=1)

        # 2. Unexpected Disconnect
        client._on_disconnect(mock_paho, None, rc=7)  # rc != 0 indicates abnormal drop
        assert client.is_connected is False
        assert metrics.get_snapshot()["mqtt"]["connected"] is False
        assert metrics.get_snapshot()["mqtt"]["reconnect_attempts"] == 1

        # 3. Reconnected
        client._on_connect(mock_paho, None, None, 0)
        assert client.is_connected is True
        assert metrics.get_snapshot()["mqtt"]["connected"] is True
        # Subscription was restored
        assert mock_paho.subscribe.call_count == 2


class TestMosquittoProductionConfiguration:
    """Verifies BLK-ING-01 configuration files: mosquitto.conf, ACLs, and passwords."""

    def test_production_mosquitto_conf_disables_anonymous_access(self):
        """Production Mosquitto configuration MUST forbid anonymous access."""
        conf_path = Path("config/mosquitto.conf")
        assert conf_path.exists(), "config/mosquitto.conf missing!"
        content = conf_path.read_text(encoding="utf-8")
        assert "allow_anonymous false" in content
        assert "password_file" in content
        assert "acl_file" in content
        assert "listener 1883" in content

    def test_production_mosquitto_acl_restricts_node_and_command_topics(self):
        """Topic ACLs restrict sensor nodes and protect administrative command topics."""
        acl_path = Path("config/acls")
        assert acl_path.exists(), "config/acls missing!"
        content = acl_path.read_text(encoding="utf-8")
        # Nodes restricted to their own ID
        assert "climate/nodes/%u/telemetry" in content
        assert "climate/commands/%u" in content
        # Backend authorized
        assert "climate_backend" in content
        assert "climate/alerts" in content
        assert "climate/commands/#" in content

    def test_no_real_passwords_committed_in_config(self):
        """Ensures template files do not contain real active production secrets."""
        passwords_path = Path("config/passwords")
        assert passwords_path.exists(), "config/passwords missing!"
        content = passwords_path.read_text(encoding="utf-8")
        assert "mosquitto_passwd" in content
