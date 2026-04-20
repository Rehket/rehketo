from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import verify_csrf_token

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

UNSAFE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

CSRF_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/auth/devonly/login",
    "/healthz",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)
        if any(request.url.path.startswith(p) for p in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        sid = request.cookies.get(SESSION_COOKIE)
        csrf_cookie = request.cookies.get(CSRF_COOKIE)
        csrf_header = request.headers.get(CSRF_HEADER)

        if not sid or not csrf_cookie or not csrf_header:
            return _forbid("missing csrf token")
        if csrf_cookie != csrf_header:
            return _forbid("csrf cookie/header mismatch")
        if not verify_csrf_token(sid, csrf_header):
            return _forbid("csrf token invalid")

        return await call_next(request)


def _forbid(msg: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": {"code": "forbidden", "message": msg}},
    )
