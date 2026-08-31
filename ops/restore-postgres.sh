#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 path/to/postgres.dump" >&2
  exit 2
fi

backup_file="$1"
test -f "$backup_file"

docker compose exec -T postgres pg_restore \
  --username zhiweave \
  --dbname zhiweave \
  --clean \
  --if-exists < "$backup_file"
