from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from rehketo.auth import entra
from rehketo.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "rehketo_oauth_state"
OAUTH_VERIFIER_COOKIE = "rehketo_oauth_verifier"


def _set_oauth_cookie(
    resp: RedirectResponse, name: str, value: str, *, secure: bool
) -> None:
    resp.set_cookie(
        name,
        value,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=600,
        path="/auth/",
    )


@router.get("/login")
async def login() -> RedirectResponse:
    s = get_settings()
    start = entra.build_login()
    resp = RedirectResponse(start.authorize_url, status_code=302)
    _set_oauth_cookie(resp, OAUTH_STATE_COOKIE, start.state, secure=s.cookie_secure)
    _set_oauth_cookie(
        resp, OAUTH_VERIFIER_COOKIE, start.code_verifier, secure=s.cookie_secure
    )
    return resp
