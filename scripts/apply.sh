#!/bin/sh
# Apply pending migrations manually
CONTAINER="dogovor"
echo "=== Applying migrations ==="
docker exec "$CONTAINER" alembic -c /app/alembic.ini upgrade head 2>&1
