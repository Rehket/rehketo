from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from rehketo.config import get_settings

_MAX_AGE_SECONDS = 60 * 60 * 24  # 24 hours


def _serializer() -> URLSafeTimedSerializer:
    key = get_settings().csrf_signing_key.get_secret_value()
    return URLSafeTimedSerializer(key, salt="rehketo-csrf")


def issue_csrf_token(session_id: str) -> str:
    return _serializer().dumps(session_id)


def verify_csrf_token(session_id: str, token: str) -> bool:
    try:
        payload: str = _serializer().loads(token, max_age=_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False
    return payload == session_id
