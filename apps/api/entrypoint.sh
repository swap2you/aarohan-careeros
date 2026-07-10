#!/bin/sh
set -e
echo "Running Alembic migrations..."
DATABASE_URL_SAVE=""
if [ -n "${MIGRATION_DATABASE_URL:-}" ]; then
  DATABASE_URL_SAVE="${DATABASE_URL}"
  export DATABASE_URL="${MIGRATION_DATABASE_URL}"
fi
alembic upgrade head
if [ -n "${DATABASE_URL_SAVE}" ]; then
  export DATABASE_URL="${DATABASE_URL_SAVE}"
fi
echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
