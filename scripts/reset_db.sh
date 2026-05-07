#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if command -v docker >/dev/null 2>&1 && docker compose ps >/dev/null 2>&1; then
  echo "Resetting database via docker compose..."
  docker compose exec -T api python -m app.scripts.reset_db
  exit 0
fi

if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  echo "Resetting database via local virtualenv..."
  "$PROJECT_ROOT/.venv/bin/python" -m app.scripts.reset_db
  exit 0
fi

echo "Unable to reset database: neither docker compose nor local .venv is available." >&2
exit 1
