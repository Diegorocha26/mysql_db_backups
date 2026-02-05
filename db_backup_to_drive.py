#!/usr/bin/env python3
"""
Database Backup to Google Drive Script
Backs up MySQL database and uploads to Google Drive with retention policy
"""

import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import gzip
import shutil

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """Manages MySQL database backups and Google Drive uploads"""
    
    def __init__(self):
        """Initialize backup manager with configuration from environment"""
        # Database configuration
        self.db_user = os.getenv('DB_USER')
        self.db_pass = os.getenv('DB_PASS')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '3306')
        self.db_name = os.getenv('DB_NAME')
        
        # Google Drive configuration
        self.service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        self.drive_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        # Backup configuration
        self.backup_dir = Path(os.getenv('BACKUP_LOCAL_DIR', './backups'))
        self.max_backups_to_keep = int(os.getenv('MAX_BACKUPS_TO_KEEP', '7'))
        self.backup_retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        
        # Validate configuration
        self._validate_config()
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Google Drive service
        self.drive_service = None
        
    def _validate_config(self):
        """Validate that all required configuration is present"""
        required_vars = {
            'DB_USER': self.db_user,
            'DB_PASS': self.db_pass,
            'DB_NAME': self.db_name,
            'GOOGLE_SERVICE_ACCOUNT_FILE': self.service_account_file,
        }
        
        missing_vars = [key for key, value in required_vars.items() if not value]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
    def _initialize_drive_service(self):
        """Initialize Google Drive API service"""
        if self.drive_service:
            return
            
        try:
            logger.info("Initializing Google Drive service...")
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def create_backup(self) -> Optional[Path]:
        """
        Create a MySQL database backup using mysqldump
        
        Returns:
            Path to the compressed backup file, or None if failed
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{self.db_name}_backup_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        compressed_path = self.backup_dir / f"{backup_filename}.gz"
        
        try:
            logger.info(f"Starting database backup for {self.db_name}...")
            
            # Build mysqldump command
            dump_cmd = [
                'mysqldump',
                f'--user={self.db_user}',
                f'--password={self.db_pass}',
                f'--host={self.db_host}',
                f'--port={self.db_port}',
                '--single-transaction',
                '--quick',
                '--lock-tables=false',
                self.db_name
            ]
            
            # Execute mysqldump and save to file
            logger.info(f"Executing mysqldump to {backup_path}...")
            with open(backup_path, 'w') as f:
                result = subprocess.run(
                    dump_cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if result.returncode != 0:
                logger.error(f"mysqldump failed: {result.stderr}")
                return None
            
            logger.info(f"Database dump created successfully: {backup_path}")
            
            # Compress the backup
            logger.info(f"Compressing backup to {compressed_path}...")
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed file
            backup_path.unlink()
            
            file_size_mb = compressed_path.stat().st_size / (1024 * 1024)
            logger.info(f"Backup compressed successfully. Size: {file_size_mb:.2f} MB")
            
            return compressed_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running mysqldump: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            # Clean up partial files
            if backup_path.exists():
                backup_path.unlink()
            if compressed_path.exists():
                compressed_path.unlink()
            return None
    
    def upload_to_drive(self, file_path: Path) -> Optional[str]:
        """
        Upload backup file to Google Drive
        
        Args:
            file_path: Path to the backup file
            
        Returns:
            File ID of uploaded file, or None if failed
        """
        try:
            self._initialize_drive_service()
            
            logger.info(f"Uploading {file_path.name} to Google Drive...")
            
            file_metadata = {
                'name': file_path.name,
            }
            
            # Add to specific folder if folder ID is provided
            if self.drive_folder_id:
                file_metadata['parents'] = [self.drive_folder_id]
            
            media = MediaFileUpload(
                str(file_path),
                mimetype='application/gzip',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size'
            ).execute()
            
            file_size_mb = int(file.get('size', 0)) / (1024 * 1024)
            logger.info(f"File uploaded successfully to Google Drive")
            logger.info(f"File ID: {file.get('id')}, Name: {file.get('name')}, Size: {file_size_mb:.2f} MB")
            
            return file.get('id')
            
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error uploading to Google Drive: {e}")
            return None
    
    def cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        try:
            # Clean up local backups
            logger.info("Cleaning up old local backups...")
            local_backups = sorted(
                self.backup_dir.glob(f"{self.db_name}_backup_*.sql.gz"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if len(local_backups) > self.max_backups_to_keep:
                for old_backup in local_backups[self.max_backups_to_keep:]:
                    logger.info(f"Removing old local backup: {old_backup.name}")
                    old_backup.unlink()
            
            # Clean up Google Drive backups
            if self.drive_service:
                logger.info("Cleaning up old Google Drive backups...")
                self._cleanup_drive_backups()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def _cleanup_drive_backups(self):
        """Remove old backups from Google Drive based on retention policy"""
        try:
            # Build query to find backup files
            query = f"name contains '{self.db_name}_backup_' and name contains '.sql.gz'"
            if self.drive_folder_id:
                query += f" and '{self.drive_folder_id}' in parents"
            
            query += " and trashed=false"
            
            # Get all backup files
            results = self.drive_service.files().list(
                q=query,
                fields='files(id, name, createdTime)',
                orderBy='createdTime desc'
            ).execute()
            
            files = results.get('files', [])
            
            # Keep only the most recent backups
            if len(files) > self.max_backups_to_keep:
                for old_file in files[self.max_backups_to_keep:]:
                    logger.info(f"Removing old Google Drive backup: {old_file['name']}")
                    self.drive_service.files().delete(fileId=old_file['id']).execute()
                    
        except HttpError as e:
            logger.error(f"Error cleaning up Google Drive backups: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Drive cleanup: {e}")
    
    def run_backup(self) -> bool:
        """
        Execute complete backup workflow
        
        Returns:
            True if backup was successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("Starting database backup process...")
        logger.info("=" * 60)
        
        try:
            # Create backup
            backup_path = self.create_backup()
            if not backup_path:
                logger.error("Backup creation failed")
                return False
            
            # Upload to Google Drive
            file_id = self.upload_to_drive(backup_path)
            if not file_id:
                logger.warning("Upload to Google Drive failed, but local backup exists")
                # Don't return False here - we still have local backup
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            logger.info("=" * 60)
            logger.info("Backup process completed successfully")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"Backup process failed: {e}")
            logger.info("=" * 60)
            return False


def main():
    """Main entry point"""
    try:
        backup_manager = DatabaseBackupManager()
        success = backup_manager.run_backup()
        
        if not success:
            logger.error("Backup completed with errors")
            exit(1)
        else:
            logger.info("Backup completed successfully")
            exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)


if __name__ == '__main__':
    main()
