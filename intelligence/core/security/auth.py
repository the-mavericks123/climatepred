"""
Authentication and Role-Based Access Control (RBAC) for S2 Intelligence Service.
Defines security roles (PUBLIC, OPERATOR, ADMIN), signed access tokens, and route-level authorization guards.
"""

import base64
from enum import Enum
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from intelligence.app.config import settings


class Role(str, Enum):
    """Access control tiers."""
    PUBLIC = "public"
    OPERATOR = "operator"
    ADMIN = "admin"

    @property
    def level(self) -> int:
        levels = {
            Role.PUBLIC: 1,
            Role.OPERATOR: 2,
            Role.ADMIN: 3,
        }
        return levels[self]

    def can_access(self, required_role: "Role") -> bool:
        """Evaluates whether this role meets or exceeds the required privilege level."""
        return self.level >= required_role.level


class UserSession(BaseModel):
    """Authenticated client security context."""
    client_id: str
    role: Role
    authenticated: bool


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(
    client_id: str,
    role: Role,
    expires_in_sec: int = 3600,
    secret_key: Optional[str] = None,
) -> str:
    """
    Creates a cryptographically signed HMAC-SHA256 bearer token.
    Token structure: <header_b64>.<payload_b64>.<signature_b64>
    """
    key = (secret_key or settings.secret_key).encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "client_id": client_id,
        "role": role.value,
        "iat": now,
        "exp": now + expires_in_sec,
    }

    h_b64 = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64encode(sig)

    return f"{h_b64}.{p_b64}.{sig_b64}"


def verify_access_token(
    token: str,
    secret_key: Optional[str] = None,
) -> UserSession:
    """
    Verifies signature, expiration, and claims of a signed access token.
    Raises HTTPException(401) on any cryptographic or claim invalidity.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Malformed token structure. Expected 3 segments.",
                "details": {},
            },
        )

    h_b64, p_b64, sig_b64 = parts
    key = (secret_key or settings.secret_key).encode("utf-8")
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _b64decode(sig_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Malformed token signature encoding.",
                "details": {},
            },
        )

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid token signature.",
                "details": {},
            },
        )

    try:
        payload_bytes = _b64decode(p_b64)
        payload: Dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Malformed token payload encoding.",
                "details": {},
            },
        )

    # Check expiration
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Token has expired.",
                "details": {"expired_at": exp},
            },
        )

    # Check role
    raw_role = payload.get("role")
    try:
        role = Role(raw_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": f"Invalid role claim '{raw_role}' in token.",
                "details": {},
            },
        )

    client_id = str(payload.get("client_id", "authenticated-client"))
    return UserSession(client_id=client_id, role=role, authenticated=True)


def authenticate_client(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> UserSession:
    """
    Authenticates incoming request based on pre-shared API keys or signed bearer tokens.
    In development mode or when api_auth_enabled=False, passes clients through as ADMIN.
    """
    if not settings.api_auth_enabled:
        return UserSession(client_id="dev-client", role=Role.ADMIN, authenticated=False)

    token = None
    if x_api_key is not None:
        token = x_api_key.strip()

    if not token and authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Missing authentication credentials. Provide X-API-Key or Bearer token.",
                "details": {},
            },
        )

    # 1. Check pre-shared Admin Key
    if settings.admin_api_key and token == settings.admin_api_key:
        return UserSession(client_id="admin-user", role=Role.ADMIN, authenticated=True)

    # 2. Check pre-shared Operator Key
    if settings.operator_api_key and token == settings.operator_api_key:
        return UserSession(client_id="operator-user", role=Role.OPERATOR, authenticated=True)

    # 3. Check Signed Bearer Token (JWT format)
    if "." in token:
        return verify_access_token(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "INVALID_CREDENTIALS",
            "message": "Invalid API key or authorization token.",
            "details": {},
        },
    )


def require_role(min_role: Role):
    """
    FastAPI dependency enforcing a minimum required role level.
    """
    def role_checker(session: UserSession = Depends(authenticate_client)) -> UserSession:
        if not session.role.can_access(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PRIVILEGES",
                    "message": f"Operation requires role '{min_role.value}', but client has role '{session.role.value}'.",
                    "details": {"required_role": min_role.value, "assigned_role": session.role.value},
                },
            )
        return session

    return role_checker
