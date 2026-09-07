"""Tests for Secret Redaction and Log Credential Sanitization."""
import json
import logging

from intelligence.core.logging import sanitize_data, JSONFormatter, REDACT_KEYS


class TestSecretSanitization:
    """Verifies that sensitive tokens and credentials cannot leak via data dumps."""

    def test_redacts_exact_keys(self):
        data = {
            "node_id": "NODE-001",
            "password": "super_secret_password",
            "api_key": "api-key-9999",
            "token": "jwt-token-xyz"
        }
        sanitized = sanitize_data(data)
        assert sanitized["node_id"] == "NODE-001"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["token"] == "[REDACTED]"

    def test_case_insensitive_matching(self):
        data = {
            "Admin_PASSWORD": "123",
            "SECRET_KEY": "456",
            "Authorization_Header": "Bearer abc"
        }
        sanitized = sanitize_data(data)
        assert sanitized["Admin_PASSWORD"] == "[REDACTED]"
        assert sanitized["SECRET_KEY"] == "[REDACTED]"
        assert sanitized["Authorization_Header"] == "[REDACTED]"

    def test_recursive_nested_sanitization(self):
        data = {
            "context": {
                "user": "operator_1",
                "auth": {
                    "keyring": {
                        "private_key": "-----BEGIN RSA PRIVATE KEY-----",
                        "safe_field": "visible"
                    }
                }
            }
        }
        sanitized = sanitize_data(data)
        assert sanitized["context"]["user"] == "operator_1"
        assert sanitized["context"]["auth"]["keyring"]["private_key"] == "[REDACTED]"
        assert sanitized["context"]["auth"]["keyring"]["safe_field"] == "visible"

    def test_parent_key_redaction(self):
        data = {"credentials": {"sub_key": "some_value"}}
        sanitized = sanitize_data(data)
        assert sanitized["credentials"] == "[REDACTED]"

    def test_list_sanitization(self):
        records = [
            {"name": "sensor_1", "api_key": "k1"},
            {"name": "sensor_2", "api_key": "k2"}
        ]
        sanitized = sanitize_data(records)
        assert sanitized[0]["api_key"] == "[REDACTED]"
        assert sanitized[1]["api_key"] == "[REDACTED]"
        assert sanitized[0]["name"] == "sensor_1"


class TestJSONFormatter:
    """Verifies that JSON log formatting sanitizes payloads before writing."""

    def test_json_formatter_masks_secrets(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User login attempted",
            args=(),
            exc_info=None
        )
        record.extra_data = {
            "username": "admin",
            "password": "attempted_pass",
            "api_key": "key_attempt"
        }

        formatted = formatter.format(record)
        log_json = json.loads(formatted)
        assert log_json["message"] == "User login attempted"
        assert log_json["username"] == "admin"
        assert log_json["password"] == "[REDACTED]"
        assert log_json["api_key"] == "[REDACTED]"
