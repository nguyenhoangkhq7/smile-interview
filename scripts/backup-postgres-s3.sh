#!/usr/bin/env bash
set -euo pipefail

# Nightly PostgreSQL backup from Docker Compose container directly to private Amazon S3.
# Required env: BACKUP_S3_BUCKET (e.g. smile-interview)
# Optional env: COMPOSE_FILE, COMPOSE_ENV_FILE, POSTGRES_DB, POSTGRES_USER, BACKUP_S3_PREFIX

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.staging.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env}"
POSTGRES_DB="${POSTGRES_DB:-interview_practice_db}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?Set BACKUP_S3_BUCKET}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-backups/postgres}"

TS="$(date -u +%Y%m%d_%H%M%SZ)"
TMP_FILE="$(mktemp "/tmp/${POSTGRES_DB}_${TS}_XXXXXX.dump")"
cleanup() { rm -f "$TMP_FILE"; }
trap cleanup EXIT

echo "[backup] Dumping PostgreSQL database '${POSTGRES_DB}'..."
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl > "$TMP_FILE"

if [ ! -s "$TMP_FILE" ]; then
  echo "[backup] ERROR: Backup file is empty." >&2
  exit 1
fi

S3_URI="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${POSTGRES_DB}_${TS}.dump"
echo "[backup] Uploading $(wc -c < "$TMP_FILE") bytes to ${S3_URI}..."
aws s3 cp "$TMP_FILE" "$S3_URI" --sse AES256 --only-show-errors
echo "[backup] Completed successfully: ${S3_URI}"
