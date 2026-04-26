#!/bin/sh
set -e

echo "Starting application..."
exec gunicorn mono:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 2
