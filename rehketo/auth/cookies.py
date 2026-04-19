from __future__ import annotations

from typing import TYPE_CHECKING

from rehketo.config import get_settings

if TYPE_CHECKING:
    from fastapi import Response

SESSION_COOKIE = "rehketo_session"
CSRF_COOKIE = "rehketo_csrf"
CSRF_HEADER = "X-CSRF-Token"


def set_session_cookie(
    response: Response, session_id: str, *, max_age_seconds: int
) -> None:
    s = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=max_age_seconds,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )


def set_csrf_cookie(
    response: Response, token: str, *, max_age_seconds: int
) -> None:
    s = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=max_age_seconds,
        httponly=False,  # readable by JS so it can echo in X-CSRF-Token header
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    for k in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            key=k,
            domain=s.cookie_domain,
            path="/",
            secure=s.cookie_secure,
        )
