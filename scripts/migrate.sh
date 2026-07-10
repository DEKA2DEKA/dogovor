#!/bin/sh
# Usage: scripts/migrate.sh "description of changes"
# 1. Run inside the running container to generate a new migration
# 2. Copy the migration file back to the host
# 3. Commit it

MSG="${1:-auto_migration}"
CONTAINER="dogovor"

echo "=== Generating migration: $MSG ==="
docker exec "$CONTAINER" alembic -c /app/alembic.ini revision --autogenerate -m "$MSG" 2>&1

echo ""
echo "=== Migration file ==="
docker exec "$CONTAINER" sh -c 'ls -t /app/migrations/versions/*.py | head -1'
