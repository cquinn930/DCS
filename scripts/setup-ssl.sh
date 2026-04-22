#!/usr/bin/env bash
set -euo pipefail

#
# Generate a self-signed certificate for dcs.flnet.local and deploy it to nginx
#
# Usage: sudo bash /opt/sites/DCS/scripts/setup-ssl.sh
#

DOMAIN="dcs.flnet.local"
CERT_DIR="/etc/ssl/dcs"
DAYS=3650  # 10-year validity

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)."
    exit 1
fi

echo "=== DCS Self-Signed SSL Setup — $(date) ==="

# 1. Create cert directory
echo "[1/3] Generating self-signed certificate for $DOMAIN..."
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days "$DAYS" \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/dcs.key" \
    -out "$CERT_DIR/dcs.crt" \
    -subj "/C=US/ST=Local/L=Local/O=FLNet/OU=IT/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:*.flnet.local"

chmod 600 "$CERT_DIR/dcs.key"
chmod 644 "$CERT_DIR/dcs.crt"

echo "  Certificate: $CERT_DIR/dcs.crt"
echo "  Private key: $CERT_DIR/dcs.key"

# 2. Deploy nginx config with SSL
echo "[2/3] Updating nginx configuration..."
cat > /etc/nginx/sites-available/dcs <<'NGINX'
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name dcs.flnet.local;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name dcs.flnet.local;

    ssl_certificate     /etc/ssl/dcs/dcs.crt;
    ssl_certificate_key /etc/ssl/dcs/dcs.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend — proxy to Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API — proxy to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # API health check
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # API docs (remove in production if not needed)
    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }
}
NGINX

# 3. Test and reload nginx
echo "[3/3] Reloading nginx..."
nginx -t
systemctl reload nginx

echo ""
echo "========================================"
echo "  SSL Setup Complete"
echo "========================================"
echo ""
echo "  URL:  https://$DOMAIN"
echo ""
echo "  Certificate valid for $DAYS days (until $(date -d "+${DAYS} days" +%Y-%m-%d 2>/dev/null || date -v+${DAYS}d +%Y-%m-%d 2>/dev/null || echo 'N/A'))."
echo ""
echo "  Since this is self-signed, browsers will show a warning."
echo "  To suppress it, import $CERT_DIR/dcs.crt into your"
echo "  browser or OS trusted certificate store."
echo ""
echo "  Don't forget to update your .env files:"
echo "    services/ui/.env.local  →  NEXT_PUBLIC_API_URL=https://$DOMAIN"
echo "    services/api/.env      →  CORS_ORIGINS=[\"https://$DOMAIN\"]"
echo ""
echo "  Then restart services:"
echo "    sudo systemctl restart dcs-api dcs-ui"
