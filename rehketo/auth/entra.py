from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from rehketo.config import get_settings


@dataclass(frozen=True, slots=True)
class LoginStart:
    authorize_url: str
    state: str
    code_verifier: str


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()  # nosec B324  # PKCE requires sha256 per RFC 7636
        )
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def authority() -> str:
    s = get_settings()
    return f"https://login.microsoftonline.com/{s.entra_tenant_id}"


def build_login(scope: str = "openid profile email offline_access") -> LoginStart:
    s = get_settings()
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": s.entra_client_id,
        "response_type": "code",
        "redirect_uri": s.entra_redirect_uri,
        "response_mode": "query",
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{authority()}/oauth2/v2.0/authorize?{urlencode(params)}"
    return LoginStart(authorize_url=url, state=state, code_verifier=verifier)


async def exchange_code_for_tokens(code: str, code_verifier: str) -> dict[str, object]:
    s = get_settings()
    data = {
        "client_id": s.entra_client_id,
        "client_secret": s.entra_client_secret.get_secret_value(),
        "code": code,
        "redirect_uri": s.entra_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{authority()}/oauth2/v2.0/token", data=data)
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]


def parse_id_token_claims(id_token: str) -> dict[str, object]:
    """Decode WITHOUT signature validation — only safe immediately after TLS
    response from the Entra token endpoint we just called."""
    _, payload_b64, _ = id_token.split(".")
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))  # type: ignore[no-any-return]
