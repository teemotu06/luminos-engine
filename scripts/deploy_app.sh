#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:?APP_DIR is required}"
SERVICE_NAME="${SERVICE_NAME:?SERVICE_NAME is required}"

cd "$APP_DIR"

git pull --ff-only
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python scripts/build_static.py
./.venv/bin/alembic upgrade head
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager
