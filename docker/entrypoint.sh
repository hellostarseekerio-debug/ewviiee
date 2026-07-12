#!/bin/sh
# Production container entrypoint:
#   1. Wait for the database to accept connections (PostgreSQL takes a
#      moment to become ready even after its own healthcheck passes on a
#      cold start, and `depends_on: condition: service_healthy` in
#      docker-compose.yml only guarantees the DB *container* is healthy,
#      not that this specific app's connection pool can reach it yet).
#   2. Run `alembic upgrade head` so the schema is always current before
#      the API starts serving traffic - never rely on an operator
#      remembering to migrate manually after a deploy.
#   3. exec the real process (uvicorn, by default - see the Dockerfile's
#      CMD) as PID 1, so it receives SIGTERM directly from `docker stop`
#      instead of a shell swallowing it.
set -eu

echo "office-automation-platform: waiting for the database..."
attempt=0
max_attempts=30
until python -c "
import sys
from app.core.config import get_settings
from app.core.database import build_engine
try:
    engine = build_engine(get_settings().database_url)
    with engine.connect():
        pass
except Exception as exc:
    print(f'  not ready yet: {exc}')
    sys.exit(1)
"; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "office-automation-platform: database did not become reachable after ${max_attempts} attempts - giving up." >&2
        exit 1
    fi
    sleep 2
done
echo "office-automation-platform: database is reachable."

echo "office-automation-platform: running migrations (alembic upgrade head)..."
alembic upgrade head

# No-op unless OAP_BOOTSTRAP_ADMIN_USERNAME/OAP_BOOTSTRAP_ADMIN_PASSWORD are
# both set - see scripts/bootstrap_admin_from_env.py's docstring. Exists so
# an admin account can be created/reset on platforms with no Shell access
# (e.g. Render's free tier) by setting environment variables and
# redeploying, instead of running scripts/create_admin.py interactively.
python scripts/bootstrap_admin_from_env.py

echo "office-automation-platform: starting application: $*"
exec "$@"
