#!/bin/sh
# Backup script for Therefore Report Generator data

BACKUP_DIR="/backups"
DATA_DIR="/data"
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.zip"

echo "[$(date)] Starting backup..."

# Create zip archive of data directory
cd "$DATA_DIR" || exit 1
zip -r "$BACKUP_FILE" . -x "*.zip" -x "backups/*"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup created: $BACKUP_FILE"
    
    # Clean up old backups (keep last $RETENTION_DAYS days)
    find "$BACKUP_DIR" -name "backup_*.zip" -type f -mtime +$RETENTION_DAYS -delete
    
    # List current backups
    echo "[$(date)] Current backups:"
    ls -lh "$BACKUP_DIR"/backup_*.zip 2>/dev/null || echo "No backups found"
else
    echo "[$(date)] Backup failed!"
    exit 1
fi

echo "[$(date)] Backup complete."
