#!/usr/bin/env bash
set -euo pipefail

backup_dir="${ZHIWEAVE_BACKUP_DIR:-./storage/backups}"
mkdir -p "$backup_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/postgres-$timestamp.dump"

docker compose exec -T postgres pg_dump \
  --username zhiweave \
  --dbname zhiweave \
  --format custom > "$target"

echo "$target"
