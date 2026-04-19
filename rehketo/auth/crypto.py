from __future__ import annotations

import base64
import binascii

from cryptography.fernet import Fernet, InvalidToken

from rehketo.config import get_settings

_FERNET_RAW_KEY_BYTES = 32


def _fernet() -> Fernet:
    raw = get_settings().session_encryption_key.get_secret_value()
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except (ValueError, binascii.Error) as exc:
        key_bytes = base64.urlsafe_b64decode(raw)
        if len(key_bytes) != _FERNET_RAW_KEY_BYTES:
            raise ValueError("SESSION_ENCRYPTION_KEY must decode to 32 bytes") from exc
        return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_token(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_token(ct: bytes) -> str:
    try:
        return _fernet().decrypt(ct).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("invalid ciphertext") from e
