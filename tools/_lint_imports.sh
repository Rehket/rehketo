#!/usr/bin/env bash
# Run import-linter with a deterministic dummy environment so it can import the
# rehketo package (whose db/__init__.py reads settings at import time). The
# values are placeholders — lint-imports walks the import graph; it does not
# run code paths that consume these values.
set -euo pipefail

cd "$(dirname "$0")/../rehketo-api"

export APP_ENV=test
export DATABASE_URL='postgresql+psycopg://u:p@localhost:5432/rehketo'
export SESSION_ENCRYPTION_KEY="$(uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export CSRF_SIGNING_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
export ENTRA_TENANT_ID=t
export ENTRA_CLIENT_ID=c
export ENTRA_CLIENT_SECRET=s
export ENTRA_REDIRECT_URI='http://localhost:8000/auth/callback'
export UI_POST_LOGIN_URL='http://localhost:5173/'

exec uv run lint-imports
