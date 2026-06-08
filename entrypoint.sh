#!/bin/sh
set -e

echo "Running database migrations..."
MAX_RETRIES=10
RETRY_DELAY=5
n=0
until alembic upgrade head; do
  n=$((n + 1))
  if [ "$n" -ge "$MAX_RETRIES" ]; then
    echo "alembic upgrade head failed after $MAX_RETRIES attempts. Exiting."
    exit 1
  fi
  echo "Migration failed (attempt $n/$MAX_RETRIES). Retrying in ${RETRY_DELAY}s..."
  sleep "$RETRY_DELAY"
done

echo "Starting application..."
exec gunicorn mono:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 2
