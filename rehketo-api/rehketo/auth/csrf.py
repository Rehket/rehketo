from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from rehketo.config import get_settings


def _serializer() -> URLSafeTimedSerializer:
    key = get_settings().csrf_signing_key.get_secret_value()
    return URLSafeTimedSerializer(key, salt="rehketo-csrf")


def _max_age_seconds() -> int:
    """Keep CSRF TTL aligned with session TTL so a valid session always has
    a valid CSRF token. A shorter CSRF TTL strands the user with mysterious
    403s while the session cookie still says they're logged in."""
    return get_settings().session_ttl_minutes * 60


def issue_csrf_token(session_id: str) -> str:
    return _serializer().dumps(session_id)


def verify_csrf_token(session_id: str, token: str) -> bool:
    try:
        payload: str = _serializer().loads(token, max_age=_max_age_seconds())
    except BadSignature, SignatureExpired:
        return False
    return payload == session_id
