"""
Structured JSON/standard logging configuration for Climate Eye View S2 Intelligence Service.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any


REDACT_KEYS = {"password", "secret", "token", "api_key", "authorization", "credential", "private_key"}


def sanitize_data(data: Any) -> Any:
    """Recursively redacts sensitive keys from dictionaries and collections."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(rk in str(k).lower() for rk in REDACT_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with credential redaction."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = getattr(record, "request_id")
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry.update(sanitize_data(record.extra_data))
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """Configures root logger with clean stdout formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    while root_logger.handlers:
        root_logger.handlers.pop()

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        standard_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        handler.setFormatter(logging.Formatter(standard_format, datefmt="%Y-%m-%d %H:%M:%SZ"))

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Retrieve named logger."""
    return logging.getLogger(f"climate_intelligence.{name}")
