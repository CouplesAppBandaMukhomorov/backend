import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.errors import Unauthorized

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
OAUTH_STATE_TYPE = "oauth_state"

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid or expired token", code="invalid_token") from exc


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "sub": str(user_id),
            "type": ACCESS_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        }
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "sub": str(user_id),
            "type": REFRESH_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(days=settings.refresh_token_ttl_days),
        }
    )


def create_oauth_state(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "sub": str(user_id),
            "type": OAUTH_STATE_TYPE,
            "nonce": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(minutes=settings.oauth_state_ttl_minutes),
        }
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = _decode(token)
    if payload.get("type") != expected_type:
        raise Unauthorized("Unexpected token type", code="invalid_token")
    return payload
