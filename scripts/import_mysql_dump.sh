#!/usr/bin/env bash

set -euo pipefail

DUMP_FILE="${1:-chicago_neighborhood_dump.sql}"

MYSQL_HOST="${MYSQL_HOST:?Set MYSQL_HOST to the Railway MySQL host or another MySQL server.}"
MYSQL_PORT="${MYSQL_PORT:?Set MYSQL_PORT to the Railway MySQL port or another MySQL server.}"
MYSQL_USER="${MYSQL_USER:?Set MYSQL_USER to the Railway MySQL user.}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:?Set MYSQL_PASSWORD to the Railway MySQL password.}"

MYSQL_PWD="$MYSQL_PASSWORD" mysql \
  --host="$MYSQL_HOST" \
  --port="$MYSQL_PORT" \
  --user="$MYSQL_USER" \
  < "$DUMP_FILE"

echo "Imported $DUMP_FILE"
