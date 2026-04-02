#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%F-%H%M%S)"
mkdir -p "$BACKUP_DIR"

OUTPUT_PATH="$BACKUP_DIR/luminos_engine_${TIMESTAMP}.sql.gz"
pg_dump "$DATABASE_URL" | gzip -c > "$OUTPUT_PATH"

echo "created $OUTPUT_PATH"
