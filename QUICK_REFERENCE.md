# Quick Reference - Database Backup Script

## Quick Setup Checklist

- [ ] Sync with UV: `uv sync`
- [ ] Create Google Cloud Project
- [ ] Enable Google Drive API
- [ ] Create Service Account and download JSON key
- [ ] Share Google Drive folder with service account email
- [ ] Copy `.env.example` to `.env` and fill in values
- [ ] Run test: `uv run python db_backup_to_drive.py`
- [ ] Add to APScheduler or cron

## Service Account Email Format
```
your-service-name@your-project-id.iam.gserviceaccount.com
```
(Found in the downloaded JSON file)

## Get Google Drive Folder ID
1. Open folder in browser
2. URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
3. Copy the `FOLDER_ID_HERE` part

## Essential .env Settings
```env
DB_USER="root"
DB_PASS="your_password"
DB_NAME="your_database"
GOOGLE_SERVICE_ACCOUNT_FILE="/full/path/to/key.json"
GOOGLE_DRIVE_FOLDER_ID="your_folder_id"
MAX_BACKUPS_TO_KEEP="7"
```

## APScheduler Integration
```python
from db_backup_to_drive import DatabaseBackupManager

def backup_job():
    manager = DatabaseBackupManager()
    manager.run_backup()

# Daily at 2 AM
scheduler.add_job(backup_job, 'cron', hour=2, minute=0)
```

## Manual Test
```bash
python db_backup_to_drive.py
```

## Check Logs
```bash
tail -f db_backup.log
```

## Common Issues

**"Service account file not found"**
→ Use absolute path: `/home/user/key.json`

**"Permission denied" on Google Drive**
→ Share folder with service account email

**"mysqldump not found"**
→ Install: `sudo apt-get install mysql-client`

## Backup File Format
```
database_name_backup_YYYYMMDD_HHMMSS.sql.gz
```

## What Gets Cleaned Up Automatically
- Local backups: keeps last X (MAX_BACKUPS_TO_KEEP)
- Google Drive backups: keeps last X (MAX_BACKUPS_TO_KEEP)
- Runs after each successful backup
