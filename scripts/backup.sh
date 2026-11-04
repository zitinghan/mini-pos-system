#!/usr/bin/env sh
set -eu
backup_name="pos-$(date +%Y%m%d-%H%M%S).db"
mkdir -p backups
docker compose exec -T backend python - backup /data/pos.db "/data/$backup_name" < scripts/backup.py
docker compose cp "backend:/data/$backup_name" "backups/$backup_name"
echo "Backup saved to backups/$backup_name"
