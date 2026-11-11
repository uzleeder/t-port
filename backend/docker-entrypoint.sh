#!/bin/sh
set -eu
# Apply migrations and idempotent reference data before serving.
# With several replicas, run this once as a release step instead (TPORT_SKIP_MIGRATIONS=1).
if [ "${TPORT_SKIP_MIGRATIONS:-0}" != "1" ]; then
  alembic upgrade head
  python -m app.cli seed
fi
# --proxy-headers: trust X-Forwarded-For only from FORWARDED_ALLOW_IPS (the web/proxy network).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
  --no-server-header --no-access-log
