import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import ApiError


class TokenDecryptionError(ApiError):
    status_code = 500
    code = "token_decryption_failed"


def _build_key() -> bytes:
    settings = get_settings()
    if settings.fernet_key:
        return settings.fernet_key.encode()
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_build_key())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise TokenDecryptionError("Stored token could not be decrypted") from exc
