# Backup and Recovery

## Automatic Backups

The backup service runs automatically as a Docker container. It creates zip archives of all configuration files daily.

### Schedule

By default, backups run **daily at 2:00 AM** (configurable via `BACKUP_SCHEDULE` environment variable in `docker-compose.yml`).

### Backup Location

Backups are stored in `./data/backups/` as zip files with timestamps:
```
data/
  backups/
    backup_20250212_020000.zip
    backup_20250213_020000.zip
    ...
```

### Retention

The backup service automatically keeps **7 days** of backups. Older backups are deleted automatically.

## Manual Backup

To create a manual backup immediately:

```bash
docker-compose exec backup /backup.sh
```

Or from the host:

```bash
cd data && zip -r "backups/backup_$(date +%Y%m%d_%H%M%S).zip" . -x "*.zip" -x "backups/*"
```

## Disaster Recovery

### Full Recovery

1. **Stop the application**:
   ```bash
   docker-compose down
   ```

2. **Clear or backup current data** (optional):
   ```bash
   mv data data_corrupted_$(date +%Y%m%d)
   mkdir data
   ```

3. **Extract backup**:
   ```bash
   unzip data/backups/backup_YYYYMMDD_HHMMSS.zip -d data/
   ```

4. **Restart the application**:
   ```bash
   docker-compose up -d
   ```

### Restore from Backup Archive

```bash
# List available backups
ls -la data/backups/

# Extract specific backup
unzip data/backups/backup_20250212_020000.zip -d data/

# Restart to apply
docker-compose restart
```

## Offsite Backup (Recommended)

For production use, copy backups to external storage:

```bash
# Example: Copy to S3
aws s3 sync data/backups/ s3://my-backup-bucket/trg-backups/

# Example: Copy to remote server
rsync -avz data/backups/ user@backup-server:/backups/trg/
```

## Backup Contents

The backup includes all YAML configuration files:
- `users.yaml` - User accounts and passwords
- `tenants.yaml` - Therefore tenant configurations
- `reports.yaml` - Report definitions and schedules
- `templates.yaml` - Email templates
- `smtp.yaml` - SMTP server settings
- `run_logs.yaml` - Report execution history
- `app_config.yaml` - Application settings
- `audit_log.yaml` - Security audit trail

## Customizing Backup Schedule

Edit `docker-compose.yml` and modify the `BACKUP_SCHEDULE` environment variable:

```yaml
environment:
  - BACKUP_SCHEDULE=0 */6 * * *  # Every 6 hours
  - BACKUP_SCHEDULE=0 0 * * 0    # Weekly on Sunday
  - BACKUP_SCHEDULE=*/30 * * * * # Every 30 minutes (testing)
```

Cron format: `minute hour day month weekday`

## Troubleshooting

### Check backup logs

```bash
docker-compose logs backup
```

### Verify backup integrity

```bash
# List contents without extracting
unzip -l data/backups/backup_YYYYMMDD_HHMMSS.zip

# Test extraction
docker-compose exec backup unzip -t /backups/backup_YYYYMMDD_HHMMSS.zip
```

### Backup service not running

```bash
# Check status
docker-compose ps

# Restart backup service
docker-compose restart backup
```
