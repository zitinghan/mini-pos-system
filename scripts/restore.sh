#!/usr/bin/env sh
set -eu
if [ "$#" -ne 1 ]; then echo 'Usage: scripts/restore.sh backups/pos-YYYYMMDD-HHMMSS.db'; exit 1; fi
test -f "$1"
# Keep file ownership inside the volume consistent with the application user.
docker compose stop frontend worker backend
docker compose run --rm --no-deps -T --entrypoint sh backend -c 'cat > /data/restore-source.db' < "$1"
docker compose run --rm --no-deps -T backend python - restore /data/restore-source.db /data/pos.db --services-stopped < scripts/backup.py
docker compose run --rm --no-deps -T --entrypoint sh backend -c 'rm /data/restore-source.db'
docker compose up -d
