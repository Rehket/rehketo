"""Unit test — X-CSRF-Token declared as a security scheme in the generated OpenAPI.

The CSRFMiddleware is the real enforcer; this test pins the schema declaration
so /docs and external codegen see the dependency, and so the scheme is applied
to unsafe-method operations outside the CSRF-exempt prefixes.
"""

from __future__ import annotations

from rehketo.auth.csrf_middleware import CSRF_EXEMPT_PREFIXES
from rehketo.main import create_app


def test_openapi_declares_csrf_token_security_scheme(
    settings_env: object, db_url: str
) -> None:
    app = create_app()
    schema = app.openapi()

    schemes = schema["components"]["securitySchemes"]
    assert "CSRFToken" in schemes
    assert schemes["CSRFToken"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-CSRF-Token",
        "description": (
            "Double-submit CSRF token. Required on all unsafe methods "
            "except /auth/* and /healthz."
        ),
    }


def test_openapi_applies_csrf_scheme_to_unsafe_non_exempt_ops(
    settings_env: object, db_url: str
) -> None:
    app = create_app()
    schema = app.openapi()

    # Conversations POST is a non-exempt unsafe operation — must require CSRF.
    conv_post = schema["paths"]["/conversations"]["post"]
    assert {"CSRFToken": []} in conv_post["security"]

    # Runs cancel is non-exempt, must require CSRF.
    cancel_post = schema["paths"]["/runs/{run_id}/cancel"]["post"]
    assert {"CSRFToken": []} in cancel_post["security"]


def test_openapi_omits_csrf_scheme_for_exempt_prefixes(
    settings_env: object, db_url: str
) -> None:
    app = create_app()
    schema = app.openapi()

    for path, path_item in schema["paths"].items():
        if not any(path.startswith(p) for p in CSRF_EXEMPT_PREFIXES):
            continue
        for method, op in path_item.items():
            if method not in {"post", "put", "patch", "delete"}:
                continue
            security = op.get("security", [])
            assert {"CSRFToken": []} not in security, (
                f"exempt path {path} {method} should not require CSRFToken"
            )


def test_openapi_omits_csrf_scheme_for_safe_methods(
    settings_env: object, db_url: str
) -> None:
    app = create_app()
    schema = app.openapi()

    me_get = schema["paths"]["/me"]["get"]
    assert {"CSRFToken": []} not in me_get.get("security", [])
