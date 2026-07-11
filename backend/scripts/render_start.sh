#!/usr/bin/env bash
# Comando de inicio recomendado en Render (Root Directory = backend).
# Bootstrap core (empresa, sucursal, …) + migrate + gunicorn.
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/setup_render_db.py
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
