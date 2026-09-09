#!/bin/sh
# Local-only production settings exercise; disposable Postgres/mail/Redis volumes.
# Requires Docker Compose >=2.24.4. Access mail UI at http://localhost:8026.
set -eu
cd "$(dirname "$0")/.."
mkdir -p .local
chmod 700 .local
if [ ! -f .local/smoke.env ]; then
    (umask 077; python3 - <<'ENV'
import secrets
from pathlib import Path
Path(".local/smoke.env").write_text("B2C_DOMAIN=localhost\nB2C_SECRET_KEY="+secrets.token_urlsafe(48)+"\nB2C_DB_PASSWORD="+secrets.token_urlsafe(32)+"\nB2C_SMTP_HOST=mailpit\nB2C_FROM_EMAIL=noreply@smoke.example\n")
ENV
    )
fi
set -a
. ./.local/smoke.env
set +a
docker compose -p autosense-b2c-smoke -f compose.yaml -f deploy/compose.smoke.yaml up --build -d --wait
# Trust this test Caddy CA explicitly (no --insecure).
mkdir -p .local
chmod 700 .local
docker compose -p autosense-b2c-smoke -f compose.yaml -f deploy/compose.smoke.yaml cp web:/data/caddy/pki/authorities/local/root.crt .local/smoke-ca.crt
python3 deploy/https-smoke-check.py
printf '\nHTTPS smoke server ready. Mail: http://localhost:8026\n'
printf 'Clean up disposable services/volumes: docker compose --env-file .local/smoke.env -p autosense-b2c-smoke -f compose.yaml -f deploy/compose.smoke.yaml down -v\n'
