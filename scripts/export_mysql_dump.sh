#!/usr/bin/env bash

set -euo pipefail

DATABASE_NAME="${1:-chicago_neighborhood}"
OUTPUT_FILE="${2:-${DATABASE_NAME}_dump.sql}"

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"

if [[ -z "${MYSQL_PASSWORD:-}" ]]; then
  read -r -s -p "MySQL password: " MYSQL_PASSWORD
  echo
fi

MYSQL_PWD="$MYSQL_PASSWORD" mysqldump \
  --host="$MYSQL_HOST" \
  --port="$MYSQL_PORT" \
  --user="$MYSQL_USER" \
  --databases "$DATABASE_NAME" \
  --single-transaction \
  --skip-lock-tables \
  --routines \
  --triggers \
  --events \
  --default-character-set=utf8mb4 \
  --set-gtid-purged=OFF \
  > "$OUTPUT_FILE"

echo "Wrote $OUTPUT_FILE"
