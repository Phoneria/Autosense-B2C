#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
npm ci
npm --prefix frontend ci
npx playwright install chromium
printf '\nKurulum tamamlandı. Referans verilerini hazırladıktan sonra ./dev.sh çalıştırın.\n'
