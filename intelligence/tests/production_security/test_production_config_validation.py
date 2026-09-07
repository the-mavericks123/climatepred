"""Tests for Fail-Fast Startup Configuration Validation."""
import pytest
from intelligence.app.config import Settings


class TestProductionConfigValidation:
    """Verifies that insecure configuration fails fast at startup in production."""

    def test_dev_environment_permits_defaults(self):
        dev_settings = Settings(
            environment="development",
            secret_key="dev-secret-key-change-in-production",
            allowed_origins=["*"]
        )
        # Should not raise
        dev_settings.validate_production_security()

    def test_production_rejects_default_secret_key(self):
        with pytest.raises((ValueError, Exception)) as exc_info:
            Settings(
                environment="production",
                secret_key="dev-secret-key-change-in-production",
                allowed_origins=["https://climate-eye.internal"]
            )
        assert "insecure" in str(exc_info.value).lower() or "secret_key" in str(exc_info.value).lower()

    def test_production_rejects_short_secret_key(self):
        with pytest.raises((ValueError, Exception)) as exc_info:
            Settings(
                environment="production",
                secret_key="short_key_123",
                allowed_origins=["https://climate-eye.internal"]
            )
        assert "32 characters" in str(exc_info.value)

    def test_production_rejects_wildcard_cors(self):
        with pytest.raises((ValueError, Exception)) as exc_info:
            Settings(
                environment="production",
                secret_key="a" * 32,
                allowed_origins=["*"]
            )
        assert "wildcard" in str(exc_info.value).lower()

    def test_production_accepts_secure_configuration(self):
        prod_settings = Settings(
            environment="production",
            secret_key="a" * 32,
            allowed_origins=["https://climate-eye.internal", "https://operator.climate-eye.internal"]
        )
        # Should pass without raising
        prod_settings.validate_production_security()
