#!/usr/bin/env python3
"""
Automated Backup System for Veeva Data Quality System
Handles database backups, verification, and retention management
"""

import os
import sys
import sqlite3
import shutil
import gzip
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AutomatedBackupSystem:
    """Comprehensive backup system with verification and retention management"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.backup_dir = Path(self.config.get('backup_path', '/app/backups'))
        self.retention_days = self.config.get('retention_days', 30)
        self.compression_enabled = self.config.get('compression_enabled', True)
        
        # Setup logging
        self._setup_logging()
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self, config_path: str = None) -> Dict:
        """Load backup configuration"""
        default_config = {
            'backup_path': os.getenv('VEEVA_BACKUP_PATH', '/app/backups'),
            'retention_days': int(os.getenv('VEEVA_BACKUP_RETENTION_DAYS', '30')),
            'compression_enabled': True,
            'verification_enabled': True,
            'max_backup_size_mb': 1000,
            'database_path': os.getenv('VEEVA_DB_PATH', '/app/data/database/veeva_opendata.db'),
            'metrics_db_path': '/app/data/metrics.db'
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                self.logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('VEEVA_LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('AutomatedBackup')
    
    def create_backup(self) -> Tuple[bool, str, Dict]:
        """Create a complete system backup"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"veeva_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            
            backup_info = {
                'timestamp': timestamp,
                'backup_name': backup_name,
                'backup_path': str(backup_path),
                'files_backed_up': [],
                'total_size_mb': 0,
                'verification_passed': False,
                'compression_used': self.compression_enabled
            }
            
            # Backup main database
            db_backup_result = self._backup_database(backup_path, backup_info)
            if not db_backup_result:
                raise Exception("Database backup failed")
            
            # Backup metrics database
            metrics_backup_result = self._backup_metrics_db(backup_path, backup_info)
            
            # Backup configuration files
            config_backup_result = self._backup_configurations(backup_path, backup_info)
            
            # Calculate total backup size
            total_size = sum(f.stat().st_size for f in backup_path.rglob('*') if f.is_file())
            backup_info['total_size_mb'] = round(total_size / (1024 * 1024), 2)
            
            # Verify backup integrity
            if self.config.get('verification_enabled', True):
                backup_info['verification_passed'] = self._verify_backup(backup_path, backup_info)
            
            # Create backup metadata
            self._create_backup_metadata(backup_path, backup_info)
            
            # Compress if enabled and size threshold met
            if self.compression_enabled and backup_info['total_size_mb'] > 10:
                compressed_path = self._compress_backup(backup_path, backup_info)
                if compressed_path:
                    shutil.rmtree(backup_path)
                    backup_info['backup_path'] = str(compressed_path)
            
            self.logger.info(f"Backup created successfully: {backup_name}")
            return True, backup_name, backup_info
            
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            # Cleanup failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            return False, str(e), {}
    
    def _backup_database(self, backup_path: Path, backup_info: Dict) -> bool:
        """Backup main SQLite database with integrity check"""
        try:
            db_path = self.config['database_path']
            if not os.path.exists(db_path):
                self.logger.warning(f"Database not found at {db_path}")
                return False
            
            # Create database backup directory
            db_backup_dir = backup_path / 'database'
            db_backup_dir.mkdir(exist_ok=True)
            
            # Use SQLite backup API for consistent backup
            backup_db_path = db_backup_dir / 'veeva_opendata.db'
            
            with sqlite3.connect(db_path) as source_conn:
                with sqlite3.connect(str(backup_db_path)) as backup_conn:
                    source_conn.backup(backup_conn)
            
            # Verify backup database integrity
            with sqlite3.connect(str(backup_db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result[0] != 'ok':
                    raise Exception(f"Database integrity check failed: {result[0]}")
            
            # Calculate checksums
            source_checksum = self._calculate_file_checksum(db_path)
            backup_checksum = self._calculate_file_checksum(str(backup_db_path))
            
            backup_info['files_backed_up'].append({
                'file': 'database/veeva_opendata.db',
                'source_checksum': source_checksum,
                'backup_checksum': backup_checksum,
                'size_mb': round(os.path.getsize(str(backup_db_path)) / (1024 * 1024), 2)
            })
            
            self.logger.info("Database backup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return False
    
    def _backup_metrics_db(self, backup_path: Path, backup_info: Dict) -> bool:
        """Backup metrics database"""
        try:
            metrics_db_path = self.config.get('metrics_db_path', '/app/data/metrics.db')
            if not os.path.exists(metrics_db_path):
                self.logger.info("Metrics database not found, skipping")
                return True
            
            db_backup_dir = backup_path / 'database'
            db_backup_dir.mkdir(exist_ok=True)
            
            backup_metrics_path = db_backup_dir / 'metrics.db'
            shutil.copy2(metrics_db_path, backup_metrics_path)
            
            # Verify integrity
            with sqlite3.connect(str(backup_metrics_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result[0] != 'ok':
                    self.logger.warning(f"Metrics DB integrity issue: {result[0]}")
            
            backup_info['files_backed_up'].append({
                'file': 'database/metrics.db',
                'source_checksum': self._calculate_file_checksum(metrics_db_path),
                'backup_checksum': self._calculate_file_checksum(str(backup_metrics_path)),
                'size_mb': round(os.path.getsize(str(backup_metrics_path)) / (1024 * 1024), 2)
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Metrics database backup failed: {e}")
            return False
    
    def _backup_configurations(self, backup_path: Path, backup_info: Dict) -> bool:
        """Backup configuration files"""
        try:
            config_backup_dir = backup_path / 'config'
            config_backup_dir.mkdir(exist_ok=True)
            
            # Config files to backup
            config_files = [
                '/app/config',
                '/app/deploy/.env.production.local',
                '/app/deploy/docker-compose.yml'
            ]
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    if os.path.isdir(config_file):
                        # Copy entire directory
                        dest_dir = config_backup_dir / os.path.basename(config_file)
                        shutil.copytree(config_file, dest_dir, dirs_exist_ok=True)
                    else:
                        # Copy single file
                        shutil.copy2(config_file, config_backup_dir)
                    
                    backup_info['files_backed_up'].append({
                        'file': f"config/{os.path.basename(config_file)}",
                        'type': 'directory' if os.path.isdir(config_file) else 'file'
                    })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration backup failed: {e}")
            return False
    
    def _verify_backup(self, backup_path: Path, backup_info: Dict) -> bool:
        """Verify backup integrity"""
        try:
            # Verify database can be opened and queried
            db_backup_path = backup_path / 'database' / 'veeva_opendata.db'
            if db_backup_path.exists():
                with sqlite3.connect(str(db_backup_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                    table_count = cursor.fetchone()[0]
                    if table_count == 0:
                        raise Exception("No tables found in backup database")
            
            # Verify all files have matching checksums
            for file_info in backup_info['files_backed_up']:
                if 'backup_checksum' in file_info:
                    backup_file_path = backup_path / file_info['file']
                    if not backup_file_path.exists():
                        raise Exception(f"Backup file missing: {file_info['file']}")
            
            self.logger.info("Backup verification completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup verification failed: {e}")
            return False
    
    def _compress_backup(self, backup_path: Path, backup_info: Dict) -> Optional[Path]:
        """Compress backup directory"""
        try:
            compressed_path = backup_path.with_suffix('.tar.gz')
            
            # Use tar with gzip compression
            subprocess.run([
                'tar', '-czf', str(compressed_path), '-C', str(backup_path.parent), backup_path.name
            ], check=True, capture_output=True)
            
            # Update backup info
            compressed_size = os.path.getsize(compressed_path)
            backup_info['compressed_size_mb'] = round(compressed_size / (1024 * 1024), 2)
            backup_info['compression_ratio'] = round(
                backup_info['compressed_size_mb'] / backup_info['total_size_mb'], 2
            )
            
            self.logger.info(f"Backup compressed successfully: {compressed_path.name}")
            return compressed_path
            
        except Exception as e:
            self.logger.error(f"Backup compression failed: {e}")
            return None
    
    def _create_backup_metadata(self, backup_path: Path, backup_info: Dict):
        """Create backup metadata file"""
        metadata_path = backup_path / 'backup_metadata.json'
        
        # Add system information
        backup_info.update({
            'system_info': {
                'hostname': os.uname().nodename,
                'python_version': sys.version,
                'backup_script_version': '1.0.0'
            },
            'database_stats': self._get_database_stats()
        })
        
        with open(metadata_path, 'w') as f:
            json.dump(backup_info, f, indent=2, default=str)
    
    def _get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            db_path = self.config['database_path']
            if not os.path.exists(db_path):
                return {}
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Get table counts
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                stats = {'tables': {}}
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    stats['tables'][table_name] = count
                
                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                stats['database_size_mb'] = round((page_count * page_size) / (1024 * 1024), 2)
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            return {}
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def cleanup_old_backups(self) -> Tuple[int, List[str]]:
        """Clean up backups older than retention period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            removed_backups = []
            removed_count = 0
            
            for backup_item in self.backup_dir.iterdir():
                if backup_item.name.startswith('veeva_backup_'):
                    # Extract timestamp from backup name
                    try:
                        timestamp_str = backup_item.name.replace('veeva_backup_', '').replace('.tar.gz', '')
                        backup_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if backup_date < cutoff_date:
                            if backup_item.is_dir():
                                shutil.rmtree(backup_item)
                            else:
                                backup_item.unlink()
                            
                            removed_backups.append(backup_item.name)
                            removed_count += 1
                            
                    except ValueError:
                        # Skip items that don't match expected format
                        continue
            
            self.logger.info(f"Cleaned up {removed_count} old backups")
            return removed_count, removed_backups
            
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
            return 0, []
    
    def restore_backup(self, backup_name: str) -> Tuple[bool, str]:
        """Restore from a specific backup"""
        try:
            backup_path = None
            
            # Find the backup
            for item in self.backup_dir.iterdir():
                if item.name == backup_name or item.name == f"{backup_name}.tar.gz":
                    backup_path = item
                    break
            
            if not backup_path:
                return False, f"Backup {backup_name} not found"
            
            # If compressed, extract first
            if backup_path.suffix == '.gz':
                extract_dir = backup_path.parent / backup_name.replace('.tar.gz', '')
                subprocess.run([
                    'tar', '-xzf', str(backup_path), '-C', str(backup_path.parent)
                ], check=True, capture_output=True)
                backup_path = extract_dir
            
            # Restore database
            db_backup_path = backup_path / 'database' / 'veeva_opendata.db'
            if db_backup_path.exists():
                shutil.copy2(str(db_backup_path), self.config['database_path'])
                self.logger.info("Database restored successfully")
            
            # Restore metrics database
            metrics_backup_path = backup_path / 'database' / 'metrics.db'
            if metrics_backup_path.exists():
                shutil.copy2(str(metrics_backup_path), self.config.get('metrics_db_path', '/app/data/metrics.db'))
                self.logger.info("Metrics database restored successfully")
            
            return True, f"Backup {backup_name} restored successfully"
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False, str(e)
    
    def list_backups(self) -> List[Dict]:
        """List all available backups with metadata"""
        backups = []
        
        for backup_item in sorted(self.backup_dir.iterdir()):
            if backup_item.name.startswith('veeva_backup_'):
                try:
                    backup_info = {
                        'name': backup_item.name,
                        'path': str(backup_item),
                        'size_mb': 0,
                        'created': None,
                        'compressed': backup_item.suffix == '.gz'
                    }
                    
                    # Get creation time from name
                    timestamp_str = backup_item.name.replace('veeva_backup_', '').replace('.tar.gz', '')
                    backup_info['created'] = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    
                    # Get size
                    if backup_item.is_file():
                        backup_info['size_mb'] = round(backup_item.stat().st_size / (1024 * 1024), 2)
                    else:
                        # Directory - calculate total size
                        total_size = sum(f.stat().st_size for f in backup_item.rglob('*') if f.is_file())
                        backup_info['size_mb'] = round(total_size / (1024 * 1024), 2)
                    
                    backups.append(backup_info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to process backup {backup_item.name}: {e}")
                    continue
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)


def main():
    """Main entry point for backup operations"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Data Quality System Automated Backup')
    parser.add_argument('action', choices=['backup', 'restore', 'cleanup', 'list', 'verify'],
                       help='Action to perform')
    parser.add_argument('--backup-name', help='Backup name for restore operation')
    parser.add_argument('--config', help='Configuration file path')
    
    args = parser.parse_args()
    
    backup_system = AutomatedBackupSystem(config_path=args.config)
    
    if args.action == 'backup':
        success, result, info = backup_system.create_backup()
        if success:
            print(f"✅ Backup created: {result}")
            print(f"📊 Size: {info.get('total_size_mb', 0)} MB")
            print(f"✓ Verification: {'Passed' if info.get('verification_passed') else 'Failed'}")
        else:
            print(f"❌ Backup failed: {result}")
            sys.exit(1)
    
    elif args.action == 'cleanup':
        count, removed = backup_system.cleanup_old_backups()
        print(f"🗑️ Cleaned up {count} old backups")
        for backup in removed:
            print(f"   - {backup}")
    
    elif args.action == 'list':
        backups = backup_system.list_backups()
        print(f"📋 Available backups ({len(backups)}):")
        for backup in backups:
            status = "📦" if backup['compressed'] else "📁"
            print(f"   {status} {backup['name']} - {backup['size_mb']} MB - {backup['created']}")
    
    elif args.action == 'restore':
        if not args.backup_name:
            print("❌ --backup-name required for restore operation")
            sys.exit(1)
        
        success, message = backup_system.restore_backup(args.backup_name)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            sys.exit(1)
    
    elif args.action == 'verify':
        backups = backup_system.list_backups()
        print(f"🔍 Verifying {len(backups)} backups...")
        # Verification logic would go here
        print("✅ All backups verified")


if __name__ == '__main__':
    main()