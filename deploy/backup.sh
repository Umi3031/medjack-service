#!/usr/bin/env bash
# ------------------------------------------------------------------
# PostgreSQL өгөгдлийн санг өдөр бүр нөөцлөх скрипт (Docker хувилбар).
# 14 хоногоос хуучин нөөцийг автоматаар устгана.
# cron-д нэмэх (өдөр бүр 02:00):
#   0 2 * * * /opt/medjack-service/deploy/backup.sh >> /var/log/medjack-backup.log 2>&1
# Сэргээх:
#   gunzip -c backups/medjack_YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U medjack -d medjack
# ------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
FILE="backups/medjack_$(date +%F).sql.gz"
docker compose exec -T db pg_dump -U medjack -d medjack | gzip > "$FILE"
find backups -name 'medjack_*.sql.gz' -mtime +14 -delete
echo "$(date '+%F %T') Нөөц үүслээ: $FILE"
