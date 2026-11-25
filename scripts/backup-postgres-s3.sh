#!/usr/bin/env bash
set -euo pipefail

# Upload a logical PostgreSQL backup to private Amazon S3.
# Required env: BACKUP_S3_BUCKET
# RDS: RDS_ENDPOINT, RDS_CA_BUNDLE, PGUSER, PGPASSFILE. Optional: RDS_DB_NAME.
# Self-hosted: COMPOSE_FILE with a postgres service. Optional: COMPOSE_ENV_FILE, POSTGRES_DB, POSTGRES_USER.

BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?Set BACKUP_S3_BUCKET}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-backups/postgres}"
if [[ -n "${RDS_ENDPOINT:-}" ]]; then
  DB_NAME="${RDS_DB_NAME:-interview_practice_db}"
  : "${RDS_CA_BUNDLE:?Set RDS_CA_BUNDLE to the RDS CA bundle path}"
  : "${PGUSER:?Set PGUSER to the database backup role}"
  : "${PGPASSFILE:?Set PGPASSFILE to the PostgreSQL password file}"
  if [[ ! -r "$RDS_CA_BUNDLE" || ! -r "$PGPASSFILE" ]]; then
    echo '[backup] ERROR: The RDS CA bundle and password file must be readable.' >&2
    exit 1
  fi
else
  : "${COMPOSE_FILE:?Set RDS_ENDPOINT or COMPOSE_FILE for a self-hosted PostgreSQL service}"
  DB_NAME="${POSTGRES_DB:-interview_practice_db}"
fi

TS="$(date -u +%Y%m%d_%H%M%SZ)"
TMP_FILE="$(mktemp "/tmp/${DB_NAME}_${TS}_XXXXXX.dump")"
cleanup() { rm -f "$TMP_FILE"; }
trap cleanup EXIT

echo "[backup] Dumping PostgreSQL database '${DB_NAME}'..."
if [[ -n "${RDS_ENDPOINT:-}" ]]; then
  PGSSLMODE=verify-full PGSSLROOTCERT="$RDS_CA_BUNDLE" PGPASSFILE="$PGPASSFILE" \
    pg_dump -h "$RDS_ENDPOINT" -p 5432 -U "$PGUSER" -d "$DB_NAME" --no-password \
      -Fc --no-owner --no-acl > "$TMP_FILE"
else
  docker compose --env-file "${COMPOSE_ENV_FILE:-.env}" -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-postgres}" -d "$DB_NAME" -Fc --no-owner --no-acl > "$TMP_FILE"
fi

if [ ! -s "$TMP_FILE" ]; then
  echo "[backup] ERROR: Backup file is empty." >&2
  exit 1
fi

S3_URI="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${DB_NAME}_${TS}.dump"
echo "[backup] Uploading $(wc -c < "$TMP_FILE") bytes to ${S3_URI}..."
aws s3 cp "$TMP_FILE" "$S3_URI" --sse AES256 --only-show-errors
echo "[backup] Completed successfully: ${S3_URI}"
