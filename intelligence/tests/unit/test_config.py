"""
Unit tests for service configuration.
"""

from intelligence.app.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.api_prefix == "/api/v1"
    assert settings.data_freshness_threshold_sec == 300
    assert settings.enable_ingestion_validation is True


def test_custom_settings_override():
    custom = Settings(
        port=9000,
        environment="staging",
        log_level="DEBUG",
        data_freshness_threshold_sec=600,
    )
    assert custom.port == 9000
    assert custom.environment == "staging"
    assert custom.log_level == "DEBUG"
    assert custom.data_freshness_threshold_sec == 600
