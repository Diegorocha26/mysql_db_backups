# Database Backup to Google Drive - Setup Guide

This guide will help you set up automated MySQL database backups to Google Drive using a service account.

## Prerequisites

- Python 3.7 or higher
- MySQL installed with `mysqldump` command available
- A Google account with access to Google Drive
- Preferably uv if not pip can be used

---

## Step 1: Sync UV and activate the Virtual Environment

```bash
uv sync
source .venv/bin/activate.ps1
```

---

## Step 2: Set Up Google Drive API with Service Account

### 2.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "Database Backups")
4. Click "Create"

### 2.2 Enable Google Drive API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on it and press "Enable"

### 2.3 Create a Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Enter service account details:
   - **Name**: `db-backup-service`
   - **Description**: `Service account for automated database backups`
4. Click "Create and Continue"
5. Skip the optional "Grant this service account access to project" step
6. Click "Done"

### 2.4 Create and Download Service Account Key

1. In the "Credentials" page, find your service account under "Service Accounts"
2. Click on the service account email
3. Go to the "Keys" tab
4. Click "Add Key" → "Create new key"
5. Select "JSON" format
6. Click "Create"
7. **Save this JSON file securely** - you'll need it for the backup script

**Important Security Note**: This JSON file contains credentials that give access to your Google Drive. Keep it secure and never commit it to version control!

### 2.5 Share Google Drive Folder with Service Account

Since the service account is not a regular Google user, you need to share your backup folder with it:

1. **Create a backup folder in Google Drive** (or use an existing one)
2. **Right-click the folder** → "Share"
3. **Copy the service account email** from the JSON file (it looks like: `db-backup-service@your-project.iam.gserviceaccount.com`)
4. **Paste it in the share dialog** and give it "Editor" access
5. Click "Send"

6. **Get the Folder ID**:
   - Open the folder in Google Drive
   - Look at the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Copy the `FOLDER_ID_HERE` part

---

## Step 3: Configure the Backup Script

### 3.1 Create .env File

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

### 3.2 Edit .env File

Update the `.env` file with your settings:

```env
# Database Configuration
DB_USER= # DB user
DB_PASS= # DB password
DB_HOST= # DB host
DB_PORT= # DB port
DB_NAME= # DB name

# Google Drive Configuration
GOOGLE_SERVICE_ACCOUNT_FILE="/full/path/to/your-service-account-key.json"
GOOGLE_DRIVE_FOLDER_ID="your_folder_id_from_step_2.5"

# Backup Configuration
BACKUP_LOCAL_DIR="./backups"
MAX_BACKUPS_TO_KEEP="7"  # Keep last 7 backups
BACKUP_RETENTION_DAYS="30"
```

**Important**: Use the **full absolute path** to your service account JSON file.

---

## Step 4: Test the Backup Script

Run a test backup manually:

```bash
python db_backup_to_drive.py
```

You should see output like:
```
2024-01-15 10:30:00 - __main__ - INFO - ============================================================
2024-01-15 10:30:00 - __main__ - INFO - Starting database backup process...
2024-01-15 10:30:00 - __main__ - INFO - ============================================================
2024-01-15 10:30:00 - __main__ - INFO - Starting database backup for whatsapp_chatbot_prod...
2024-01-15 10:30:01 - __main__ - INFO - Database dump created successfully
2024-01-15 10:30:02 - __main__ - INFO - Backup compressed successfully. Size: 2.45 MB
2024-01-15 10:30:02 - __main__ - INFO - Uploading to Google Drive...
2024-01-15 10:30:05 - __main__ - INFO - File uploaded successfully to Google Drive
2024-01-15 10:30:05 - __main__ - INFO - Backup process completed successfully
```

Check your Google Drive folder to confirm the backup was uploaded!

---

## Step 5: Set Up with APScheduler (Your Existing Cron System)

Since you mentioned you already have APScheduler set up, here's how to integrate this backup:

### Example Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler
from db_backup_to_drive import DatabaseBackupManager
import logging

logger = logging.getLogger(__name__)

def run_database_backup():
    """Function to be called by scheduler"""
    try:
        backup_manager = DatabaseBackupManager()
        success = backup_manager.run_backup()
        
        if not success:
            logger.error("Database backup failed!")
        else:
            logger.info("Database backup completed successfully")
    except Exception as e:
        logger.error(f"Error running database backup: {e}")

# Add to your existing scheduler
scheduler = BackgroundScheduler()

# Run backup daily at 2 AM
scheduler.add_job(
    run_database_backup,
    'cron',
    hour=2,
    minute=0,
    id='database_backup'
)

# Or run every 6 hours
scheduler.add_job(
    run_database_backup,
    'interval',
    hours=6,
    id='database_backup'
)
```

### Alternative: System Cron (if preferred)

If you want to use system cron instead:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/your/script && /usr/bin/python3 db_backup_to_drive.py >> /var/log/db_backup.log 2>&1
```

---

## Step 6: Monitor and Maintain

### Check Logs

The script creates a log file `db_backup.log` in the same directory. Monitor it regularly:

```bash
tail -f db_backup.log
```

### Adjust Retention Policy

To change how many backups are kept, edit the `.env` file:

```env
MAX_BACKUPS_TO_KEEP="14"  # Keep last 14 backups (2 weeks if daily)
```

### Backup File Naming

Backups are automatically named with timestamps:
```
whatsapp_chatbot_prod_backup_20240115_143022.sql.gz
                               YYYYMMDD_HHMMSS
```

---

## Troubleshooting

### Common Issues

**1. "mysqldump: command not found"**
- Install MySQL client tools: `sudo apt-get install mysql-client` (Ubuntu/Debian)

**2. "Access denied for user"**
- Double-check your database credentials in `.env`
- Ensure the MySQL user has SELECT privileges on the database

**3. "Unable to find service account file"**
- Use the full absolute path to the JSON file in `.env`
- Check file permissions: `chmod 600 /path/to/service-account-key.json`

**4. "Insufficient permissions" from Google Drive**
- Make sure you shared the Drive folder with the service account email
- Verify the folder ID in your `.env` file

**5. "HttpError 404: File not found"**
- The folder ID might be incorrect
- Try leaving `GOOGLE_DRIVE_FOLDER_ID` empty to upload to the root of the Drive

---

## Security Best Practices

1. **Never commit `.env` or service account JSON to git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo "*.json" >> .gitignore
   echo "backups/" >> .gitignore
   ```

2. **Set proper file permissions**
   ```bash
   chmod 600 .env
   chmod 600 /path/to/service-account-key.json
   ```

3. **Regularly rotate service account keys** (every 90 days recommended)

4. **Use environment-specific service accounts** (different for dev/prod)

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_USER` | Yes | - | MySQL username |
| `DB_PASS` | Yes | - | MySQL password |
| `DB_HOST` | No | `localhost` | MySQL host |
| `DB_PORT` | No | `3306` | MySQL port |
| `DB_NAME` | Yes | - | Database name to backup |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes | - | Path to service account JSON |
| `GOOGLE_DRIVE_FOLDER_ID` | No | - | Drive folder ID (empty = root) |
| `BACKUP_LOCAL_DIR` | No | `./backups` | Local backup directory |
| `MAX_BACKUPS_TO_KEEP` | No | `7` | Number of backups to retain |
| `BACKUP_RETENTION_DAYS` | No | `30` | Days to keep backups |

---

## Advanced Usage

### Manual Backup Script

You can also import and use the class directly:

```python
from db_backup_to_drive import DatabaseBackupManager

# Create instance
manager = DatabaseBackupManager()

# Just create local backup (no upload)
backup_path = manager.create_backup()

# Upload existing file
manager.upload_to_drive(backup_path)

# Clean up old backups
manager.cleanup_old_backups()
```

### Restore from Backup

To restore from a backup:

```bash
# Download from Google Drive first
# Then restore:
gunzip whatsapp_chatbot_prod_backup_20240115_143022.sql.gz
mysql -u root -p whatsapp_chatbot_prod < whatsapp_chatbot_prod_backup_20240115_143022.sql
```

---

## Support

If you encounter any issues:
1. Check the `db_backup.log` file
2. Verify all environment variables in `.env`
3. Test Google Drive API access separately
4. Check MySQL permissions and connectivity

Good luck with your backups! 🚀
