"""Tests for Role-Based Access Control and Authentication boundaries."""
import pytest
from fastapi import HTTPException

from intelligence.core.security.auth import (
    Role,
    UserSession,
    authenticate_client,
    require_role,
)
from intelligence.app.config import settings


class TestRoleHierarchy:
    """Validates the RBAC role levels and permission monotonicity."""

    def test_role_levels(self):
        assert Role.PUBLIC.level < Role.OPERATOR.level < Role.ADMIN.level
        assert Role.PUBLIC.level == 1
        assert Role.OPERATOR.level == 2
        assert Role.ADMIN.level == 3

    def test_public_access_boundary(self):
        assert Role.PUBLIC.can_access(Role.PUBLIC) is True
        assert Role.PUBLIC.can_access(Role.OPERATOR) is False
        assert Role.PUBLIC.can_access(Role.ADMIN) is False

    def test_operator_access_boundary(self):
        assert Role.OPERATOR.can_access(Role.PUBLIC) is True
        assert Role.OPERATOR.can_access(Role.OPERATOR) is True
        assert Role.OPERATOR.can_access(Role.ADMIN) is False

    def test_admin_access_boundary(self):
        assert Role.ADMIN.can_access(Role.PUBLIC) is True
        assert Role.ADMIN.can_access(Role.OPERATOR) is True
        assert Role.ADMIN.can_access(Role.ADMIN) is True


class TestAuthenticationMechanisms:
    """Validates API token extraction and authentication verification."""

    def test_passthrough_when_auth_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", False)
        session = authenticate_client(x_api_key=None, authorization=None)
        assert session.client_id == "dev-client"
        assert session.role == Role.ADMIN
        assert session.authenticated is False

    def test_missing_credentials_fails(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        with pytest.raises(HTTPException) as exc_info:
            authenticate_client(x_api_key=None, authorization=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTHENTICATION_REQUIRED"

    def test_invalid_api_key_fails(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "valid-admin-key")
        with pytest.raises(HTTPException) as exc_info:
            authenticate_client(x_api_key="wrong-key", authorization=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_CREDENTIALS"

    def test_valid_admin_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "secret-admin-123")
        session = authenticate_client(x_api_key="secret-admin-123", authorization=None)
        assert session.client_id == "admin-user"
        assert session.role == Role.ADMIN
        assert session.authenticated is True

    def test_valid_operator_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "operator_api_key", "secret-operator-456")
        session = authenticate_client(x_api_key="secret-operator-456", authorization=None)
        assert session.client_id == "operator-user"
        assert session.role == Role.OPERATOR
        assert session.authenticated is True

    def test_bearer_authorization_header(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "bearer-token-789")
        session = authenticate_client(x_api_key=None, authorization="Bearer bearer-token-789")
        assert session.role == Role.ADMIN
        assert session.authenticated is True

    def test_malformed_bearer_header_fails(self, monkeypatch):
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "bearer-token-789")
        with pytest.raises(HTTPException) as exc_info:
            authenticate_client(x_api_key=None, authorization="Token bearer-token-789")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTHENTICATION_REQUIRED"


class TestAuthorizationGuards:
    """Validates role-level access gating."""

    def test_require_role_granted(self):
        checker = require_role(Role.OPERATOR)
        session = UserSession(client_id="test", role=Role.ADMIN, authenticated=True)
        res = checker(session=session)
        assert res == session

    def test_require_role_denied(self):
        checker = require_role(Role.ADMIN)
        session = UserSession(client_id="test", role=Role.OPERATOR, authenticated=True)
        with pytest.raises(HTTPException) as exc_info:
            checker(session=session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "INSUFFICIENT_PRIVILEGES"
        assert exc_info.value.detail["details"]["required_role"] == "admin"
