#!/usr/bin/env sh
# Jalankan native (tanpa Docker)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
