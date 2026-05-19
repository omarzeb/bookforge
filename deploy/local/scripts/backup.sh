#!/usr/bin/env bash
# deploy/local/scripts/backup.sh
#
# Daily backup script.
# Run via cron: 0 2 * * * /opt/bookforge/deploy/local/scripts/backup.sh
#
# Backs up:
#   - PostgreSQL database dump
#   - output/ directory (compiled books)
#
# Destination: configurable — local path, rsync to remote, or rclone to cloud.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/bookforge/backups}"
DATE=$(date +%Y-%m-%d_%H-%M)
KEEP_DAYS="${BACKUP_DAYS:-7}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

mkdir -p "$BACKUP_DIR"

# ── PostgreSQL dump ───────────────────────────────────────────────────────────
log "Backing up PostgreSQL..."
PGDUMP="$BACKUP_DIR/postgres_$DATE.sql.gz"

docker compose -f "$REPO_ROOT/deploy/local/docker-compose.yml" exec -T postgres \
    pg_dump -U bookforge bookforge | gzip > "$PGDUMP"

log "Database backup: $PGDUMP ($(du -sh "$PGDUMP" | cut -f1))"

# ── Output directory (compiled books) ────────────────────────────────────────
log "Backing up compiled books..."
OUTPUT_BACKUP="$BACKUP_DIR/output_$DATE.tar.gz"

# Get the Docker volume contents via the api container
docker compose -f "$REPO_ROOT/deploy/local/docker-compose.yml" exec -T api \
    tar -czf - /app/output 2>/dev/null > "$OUTPUT_BACKUP" || true

log "Output backup: $OUTPUT_BACKUP"

# ── Optional: sync to Google Drive via rclone ─────────────────────────────────
# Uncomment and configure rclone (rclone.org) to sync to cloud:
#
# if command -v rclone &>/dev/null; then
#     log "Syncing to Google Drive..."
#     rclone sync "$BACKUP_DIR" "gdrive:bookforge-backups" --max-age "${KEEP_DAYS}d"
#     log "Cloud sync complete"
# fi

# ── Clean up old local backups ────────────────────────────────────────────────
log "Cleaning backups older than $KEEP_DAYS days..."
find "$BACKUP_DIR" -name "*.gz" -mtime "+$KEEP_DAYS" -delete

log "Backup complete."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Backup Summary ==="
ls -lh "$BACKUP_DIR" | grep "$DATE" || true
echo "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
