"""
Custom Swagger UI page wired for Pattern B auth.

The stock FastAPI /docs expects a Bearer token in the Authorization header,
which we don't use. This page instead:
- Sends cookies on every request (`credentials: 'include'`) so the session
  cookie set by /auth/login or /auth/devonly/login flows through unchanged.
- Reads the `rehketo_csrf` cookie via JS and injects it as `X-CSRF-Token`
  on every unsafe (POST/PUT/PATCH/DELETE) request, so CSRF middleware passes.

Workflow for a developer:
1. Log in first — either hit /auth/login in a normal tab (Entra round-trip
   sets the session cookie), or POST /auth/devonly/login (CSRF-exempt, so
   it works without any header).
2. Open /docs. All Try-it-out requests now include both cookies and the
   CSRF header automatically.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)


_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Rehketo API — docs</title>
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
  />
  <style>
    body { margin: 0; }
    .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.addEventListener("load", () => {
      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        withCredentials: true,
        requestInterceptor: (req) => {
          const method = (req.method || "GET").toUpperCase();
          const unsafe = new Set(["POST", "PUT", "PATCH", "DELETE"]);
          if (unsafe.has(method)) {
            const match = document.cookie.match(/rehketo_csrf=([^;]+)/);
            if (match) {
              req.headers["X-CSRF-Token"] = decodeURIComponent(match[1]);
            }
          }
          return req;
        },
      });
    });
  </script>
</body>
</html>
"""


@router.get("/docs")
async def custom_swagger_ui() -> HTMLResponse:
    return HTMLResponse(_SWAGGER_UI_HTML)
