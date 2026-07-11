#!/usr/bin/env bash
# Restores a PostgreSQL backup produced by scripts/docker_backup_postgres.sh
# into a running Docker Compose deployment.
#
# Usage:
#   bash scripts/docker_restore_postgres.sh data/backups/postgres_20260711T120000Z.dump [files_20260711T120000Z.tar.gz]
#   bash scripts/docker_restore_postgres.sh <dump-file> [files-archive] --yes
#
# This is destructive to the *current* database, so:
#   1. It always takes a fresh safety backup first (via
#      scripts/docker_backup_postgres.sh), so a bad restore can itself be
#      undone.
#   2. It prompts for confirmation unless --yes is passed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DB_DUMP="${1:-}"
FILES_ARCHIVE="${2:-}"
ASSUME_YES=false
for arg in "$@"; do
    [[ "$arg" == "--yes" ]] && ASSUME_YES=true
done
if [[ "$FILES_ARCHIVE" == "--yes" ]]; then
    FILES_ARCHIVE=""
fi

if [[ -z "$DB_DUMP" ]]; then
    echo "Usage: $0 <postgres-dump-file> [files-tar-gz] [--yes]" >&2
    exit 1
fi
if [[ ! -f "$DB_DUMP" ]]; then
    echo "Error: $DB_DUMP not found." >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Error: .env not found in $REPO_ROOT." >&2
    exit 1
fi
# shellcheck disable=SC1091
set -a; source .env; set +a
POSTGRES_USER="${POSTGRES_USER:-oap}"
POSTGRES_DB="${POSTGRES_DB:-office_automation}"

if [[ "$ASSUME_YES" != true ]]; then
    read -r -p "This will OVERWRITE the '$POSTGRES_DB' database (and data/ files, if a files archive was given) with the contents of $DB_DUMP. A safety backup of the current state will be taken first. Continue? [y/N] " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Taking a safety backup of the current state first..."
bash "$REPO_ROOT/scripts/docker_backup_postgres.sh"

echo "Restoring database from $DB_DUMP..."
# --clean drops existing objects first so the restore reflects the dump
# exactly; --if-exists avoids errors on a fresh/empty database.
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < "$DB_DUMP"
echo "Database restored."

if [[ -n "$FILES_ARCHIVE" ]]; then
    if [[ ! -f "$FILES_ARCHIVE" ]]; then
        echo "Error: files archive $FILES_ARCHIVE not found." >&2
        exit 1
    fi
    echo "Restoring data/archive, data/export, data/import from $FILES_ARCHIVE..."
    tar -xzf "$FILES_ARCHIVE" -C "$REPO_ROOT/data"
    echo "Files restored."
fi

echo "Done. Restart the api service to pick up any changes: docker compose restart api"
