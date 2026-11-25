#!/usr/bin/env bash
set -euo pipefail

# Non-destructive restore drill: restores an S3 or local pg_dump (.dump) into a
# disposable postgres:17 container and verifies schema + critical tables.
# Usage:
#   ./scripts/restore-postgres-drill.sh s3://smile-interview/backups/postgres/db_20261125.dump
#   ./scripts/restore-postgres-drill.sh /tmp/local.dump

SOURCE="${1:?Usage: $0 <s3://bucket/key.dump | /path/to/local.dump>}"
CONTAINER="smile-restore-drill-$(date +%s)"
TEST_PW="drill-$(date +%s)"
TMP_DUMP=""

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  if [ -n "$TMP_DUMP" ]; then
    rm -f "$TMP_DUMP"
  fi
}
trap cleanup EXIT

if [[ "$SOURCE" == s3://* ]]; then
  TMP_DUMP="$(mktemp /tmp/smile_restore_XXXXXX.dump)"
  echo "[drill] Downloading ${SOURCE}..."
  aws s3 cp "$SOURCE" "$TMP_DUMP" --only-show-errors
  DUMP_PATH="$TMP_DUMP"
else
  DUMP_PATH="$SOURCE"
fi

echo "[drill] Starting disposable PostgreSQL 17 container (${CONTAINER})..."
docker run -d --rm --name "$CONTAINER" -e "POSTGRES_PASSWORD=${TEST_PW}" -e "POSTGRES_DB=restore_drill" postgres:17 >/dev/null

for _ in $(seq 1 20); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d restore_drill >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[drill] Restoring dump into disposable database..."
docker exec -i "$CONTAINER" pg_restore -U postgres -d restore_drill --no-owner --no-acl --exit-on-error < "$DUMP_PATH"

echo "[drill] Verifying restored tables and key references..."
docker exec -i "$CONTAINER" psql -U postgres -d restore_drill -v ON_ERROR_STOP=1 <<'SQL'
SELECT table_name,
       (xpath('/row/cnt/text()', query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text::int AS row_count
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT count(*) AS users_with_default_resume
FROM users u
JOIN resumes r ON r.id = u.default_resume_id;

SELECT count(*) AS orphan_default_resumes
FROM users u
LEFT JOIN resumes r ON r.id = u.default_resume_id
WHERE u.default_resume_id IS NOT NULL AND r.id IS NULL;
SQL

echo "[drill] Restore drill PASSED."
