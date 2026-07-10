#!/bin/sh
set -e

if [ "${1:-}" = "pytest" ] || [ "${1:-}" = "py.test" ]; then
  echo "ERROR: pytest is blocked on owner runtime (AAROHAN_RUNTIME_PROFILE=owner)."
  exit 1
fi

if [ -n "${1:-}" ] && [ "$1" != "./entrypoint.sh" ]; then
  exec "$@"
fi

echo "Running Alembic migrations (owner migrate role)..."
if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
  echo "ERROR: MIGRATION_DATABASE_URL is required for owner migrations."
  exit 1
fi
alembic upgrade head
echo "Starting owner API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
