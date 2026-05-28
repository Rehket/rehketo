_default:
    @just --list

# Bring up postgres + bifrost (detached).
[working-directory("rehketo-api/deploy")]
db:
    @test -f .env || { echo "rehketo-api/deploy/.env missing — cp .env.example .env"; exit 1; }
    docker compose up -d postgres bifrost

# Stop postgres + bifrost.
[working-directory("rehketo-api/deploy")]
db-down:
    docker compose down

# Run the FastAPI backend on :8000 (foreground).
[working-directory("rehketo-api")]
api:
    @test -f .env || { echo "rehketo-api/.env missing — cp .env.example .env"; exit 1; }
    uv run python -m rehketo.cli.serve

# Run the SvelteKit UI on :5173 (foreground).
[working-directory("rehketo-ui")]
ui:
    pnpm dev
