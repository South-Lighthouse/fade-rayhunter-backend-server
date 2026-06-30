#!/bin/bash
# Run this script on the server after pulling new code changes.
set -e

echo "==> Pulling latest code..."
git pull origin main

echo "==> Rebuilding and restarting app containers..."
docker compose up -d --build web worker

echo "==> Reloading nginx (picks up config changes)..."
docker compose up -d nginx

echo "==> Running migrations..."
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

echo "==> Copying migration files back to host..."
docker compose cp web:/app/sensors/migrations/ ./sensors/migrations/
docker compose cp web:/app/ingestion/migrations/ ./ingestion/migrations/
docker compose cp web:/app/telemetry/migrations/ ./telemetry/migrations/

echo ""
echo "Done. If new migration files were generated, commit and push them:"
echo "  git add */migrations/"
echo "  git commit -m 'Add migrations'"
echo "  git push"
