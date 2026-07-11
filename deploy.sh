#!/bin/bash
# Run this script on the server after pulling new code changes.
set -e

echo "==> Pulling latest code..."
git fetch origin main
git clean -fd
git reset --hard origin/main

echo "==> Rebuilding and restarting app containers..."
docker compose up -d --build web worker

echo "==> Restarting nginx (re-resolves upstream after web rebuild)..."
docker compose restart nginx

echo "==> Running migrations..."
docker compose exec web python manage.py migrate

echo ""
echo "Done."
