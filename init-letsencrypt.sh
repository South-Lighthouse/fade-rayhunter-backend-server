#!/bin/bash
# Run this script ONCE on the VPS before starting the full stack.
# It obtains a Let's Encrypt certificate and generates nginx/nginx.conf
# with HTTPS support.  After this, plain `docker compose up -d` is enough.
#
# Requirements: docker, docker compose, openssl

set -e

# ── Load .env ────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in the values."
  exit 1
fi
set -a; source .env; set +a

[ -z "$DOMAIN" ]          && { echo "ERROR: DOMAIN not set in .env";          exit 1; }
[ -z "$CERTBOT_EMAIL" ]   && { echo "ERROR: CERTBOT_EMAIL not set in .env";   exit 1; }

echo "==> Domain  : $DOMAIN"
echo "==> Email   : $CERTBOT_EMAIL"
echo ""

# ── Generate nginx.conf from template ────────────────────────────────────────
# envsubst only replaces ${DOMAIN}; nginx variables like $host are left alone.
envsubst '${DOMAIN}' < nginx/default.conf.template > nginx/nginx.conf
echo "✓ nginx/nginx.conf generated for $DOMAIN"

# ── Prepare certbot directories ───────────────────────────────────────────────
mkdir -p data/certbot/www data/certbot/conf

# ── Bootstrap: use a minimal HTTP-only nginx config so nginx can start
#    without requiring a certificate, then swap in the full config after.
echo "Starting nginx with HTTP-only config for ACME challenge..."
cp nginx/nginx.conf nginx/nginx.conf.bak 2>/dev/null || true
cat > nginx/nginx.conf << 'NGINXEOF'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 2G;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'ok';
        add_header Content-Type text/plain;
    }
}
NGINXEOF
docker compose up --force-recreate -d nginx
echo "Waiting for nginx to be ready..."
sleep 5

# ── Request real certificate from Let's Encrypt ───────────────────────────────
echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose run --rm --entrypoint certbot certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email "$CERTBOT_EMAIL" \
  -d "$DOMAIN" \
  --agree-tos --no-eff-email

# ── Restore full nginx config (with HTTPS) and reload ────────────────────────
envsubst '${DOMAIN}' < nginx/default.conf.template > nginx/nginx.conf
rm -f nginx/nginx.conf.bak

# ── Reload nginx with the real certificate ────────────────────────────────────
docker compose exec nginx nginx -s reload
echo ""
echo "✓ Certificate obtained and nginx reloaded."
echo ""
echo "Next steps:"
echo "  1. Make sure ALLOWED_HOSTS in .env includes $DOMAIN"
echo "  2. Run: docker compose up -d"
