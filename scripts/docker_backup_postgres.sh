#!/usr/bin/env bash
# Backs up the PostgreSQL database (via `docker compose exec ... pg_dump`)
# and the bind-mounted data directory (archive/export/import) for a Docker
# Compose deployment. This is the Postgres-backed equivalent of
# `scripts/backup_db.py`, which only knows how to back up SQLite directly
# and deliberately just reminds you to use pg_dump when the backend is
# PostgreSQL - this script is that pg_dump step, wired up for Compose.
#
# Usage (run from the repository root, where docker-compose.yml lives):
#   bash scripts/docker_backup_postgres.sh
#
# Requires: `.env` present (for POSTGRES_USER/POSTGRES_DB), the `db`
# service running (`docker compose up -d db`).
#
# Output: data/backups/postgres_<timestamp>.dump (pg_dump custom format -
# restore with `scripts/docker_restore_postgres.sh` or `pg_restore` directly)
# plus data/backups/files_<timestamp>.tar.gz (archive/export/import).
#
# Intended to be run on a schedule (cron) on the Docker host.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
    echo "Error: .env not found in $REPO_ROOT - copy .env.docker.example to .env first." >&2
    exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

POSTGRES_USER="${POSTGRES_USER:-oap}"
POSTGRES_DB="${POSTGRES_DB:-office_automation}"
RETENTION_DAYS="${OAP_BACKUP_RETENTION_DAYS:-90}"

BACKUP_DIR="$REPO_ROOT/data/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_BACKUP="$BACKUP_DIR/postgres_${TIMESTAMP}.dump"
FILES_BACKUP="$BACKUP_DIR/files_${TIMESTAMP}.tar.gz"

echo "Backing up PostgreSQL database '$POSTGRES_DB'..."
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$DB_BACKUP"
echo "  -> $DB_BACKUP"

echo "Backing up data/archive, data/export, data/import..."
dirs_to_backup=()
for dir in archive export import; do
    if [[ -d "$REPO_ROOT/data/$dir" ]]; then
        dirs_to_backup+=("$dir")
    fi
done
if [[ ${#dirs_to_backup[@]} -gt 0 ]]; then
    tar -czf "$FILES_BACKUP" -C "$REPO_ROOT/data" "${dirs_to_backup[@]}"
    echo "  -> $FILES_BACKUP"
else
    echo "  (nothing to back up yet - no archive/export/import directories found)"
fi

echo "Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "postgres_*.dump" -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name "files_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Done."
