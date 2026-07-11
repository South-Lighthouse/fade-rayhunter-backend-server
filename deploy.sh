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
docker compose exec web python manage.py migrate

echo ""
echo "Done."
