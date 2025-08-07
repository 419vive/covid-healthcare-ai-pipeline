#!/usr/bin/env python3
"""
Disk Space Management System for Veeva Data Quality System
Automated cleanup, monitoring, and space optimization
"""

import os
import sys
import shutil
import glob
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import gzip

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class DiskSpaceManager:
    """Comprehensive disk space management and cleanup system"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.warning_threshold = self.config.get('warning_threshold_percent', 85)
        self.critical_threshold = self.config.get('critical_threshold_percent', 95)
        self.cleanup_paths = self.config.get('cleanup_paths', self._default_cleanup_paths())
        
        # Setup logging
        self._setup_logging()
        
    def _load_config(self, config_path: str = None) -> Dict:
        """Load disk space management configuration"""
        default_config = {
            'warning_threshold_percent': 85,
            'critical_threshold_percent': 95,
            'log_retention_days': 7,
            'report_retention_days': 30,
            'cache_retention_days': 3,
            'temp_file_retention_hours': 24,
            'compress_old_logs': True,
            'vacuum_databases': True,
            'enable_aggressive_cleanup': False
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('VEEVA_LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DiskSpaceManager')
    
    def _default_cleanup_paths(self) -> Dict:
        """Default paths for cleanup operations"""
        return {
            'logs': {
                'path': '/app/logs',
                'retention_days': self.config.get('log_retention_days', 7),
                'patterns': ['*.log', '*.log.*'],
                'compress_old': self.config.get('compress_old_logs', True)
            },
            'reports': {
                'path': '/app/reports',
                'retention_days': self.config.get('report_retention_days', 30),
                'patterns': ['*.json', '*.html', '*.csv'],
                'exclude_dirs': ['live-demo']  # Keep demo reports
            },
            'cache': {
                'path': '/app/cache',
                'retention_days': self.config.get('cache_retention_days', 3),
                'patterns': ['*'],
                'recursive': True
            },
            'temp': {
                'path': '/tmp',
                'retention_hours': self.config.get('temp_file_retention_hours', 24),
                'patterns': ['veeva_*', 'tmp_*', '*.tmp'],
                'recursive': False
            },
            'docker_logs': {
                'path': '/var/lib/docker/containers',
                'retention_days': 7,
                'patterns': ['*-json.log*'],
                'requires_root': True
            }
        }
    
    def get_disk_usage(self, path: str = '/') -> Dict:
        """Get disk usage statistics for a given path"""
        try:
            statvfs = os.statvfs(path)
            total_space = statvfs.f_frsize * statvfs.f_blocks
            free_space = statvfs.f_frsize * statvfs.f_available
            used_space = total_space - free_space
            
            return {
                'path': path,
                'total_gb': round(total_space / (1024**3), 2),
                'used_gb': round(used_space / (1024**3), 2),
                'free_gb': round(free_space / (1024**3), 2),
                'used_percent': round((used_space / total_space) * 100, 1),
                'free_percent': round((free_space / total_space) * 100, 1)
            }
        except Exception as e:
            self.logger.error(f"Failed to get disk usage for {path}: {e}")
            return {}
    
    def check_disk_status(self) -> Dict:
        """Check disk space status and determine action needed"""
        usage = self.get_disk_usage()
        if not usage:
            return {'status': 'error', 'message': 'Failed to get disk usage'}
        
        used_percent = usage['used_percent']
        
        if used_percent >= self.critical_threshold:
            status = 'critical'
            message = f"CRITICAL: Disk usage at {used_percent}% (threshold: {self.critical_threshold}%)"
            action_needed = 'immediate_cleanup'
        elif used_percent >= self.warning_threshold:
            status = 'warning'
            message = f"WARNING: Disk usage at {used_percent}% (threshold: {self.warning_threshold}%)"
            action_needed = 'scheduled_cleanup'
        else:
            status = 'ok'
            message = f"Disk usage healthy at {used_percent}%"
            action_needed = 'none'
        
        return {
            'status': status,
            'message': message,
            'action_needed': action_needed,
            'usage': usage,
            'thresholds': {
                'warning': self.warning_threshold,
                'critical': self.critical_threshold
            }
        }
    
    def perform_cleanup(self, aggressive: bool = False) -> Dict:
        """Perform disk cleanup operations"""
        cleanup_results = {
            'total_freed_mb': 0,
            'operations': [],
            'errors': []
        }
        
        try:
            # Log rotation and compression
            log_cleanup = self._cleanup_logs()
            cleanup_results['operations'].append(log_cleanup)
            cleanup_results['total_freed_mb'] += log_cleanup.get('freed_mb', 0)
            
            # Report cleanup
            report_cleanup = self._cleanup_reports()
            cleanup_results['operations'].append(report_cleanup)
            cleanup_results['total_freed_mb'] += report_cleanup.get('freed_mb', 0)
            
            # Cache cleanup
            cache_cleanup = self._cleanup_cache()
            cleanup_results['operations'].append(cache_cleanup)
            cleanup_results['total_freed_mb'] += cache_cleanup.get('freed_mb', 0)
            
            # Temporary files
            temp_cleanup = self._cleanup_temp_files()
            cleanup_results['operations'].append(temp_cleanup)
            cleanup_results['total_freed_mb'] += temp_cleanup.get('freed_mb', 0)
            
            # Database optimization
            if self.config.get('vacuum_databases', True):
                db_cleanup = self._vacuum_databases()
                cleanup_results['operations'].append(db_cleanup)
                cleanup_results['total_freed_mb'] += db_cleanup.get('freed_mb', 0)
            
            # Aggressive cleanup if enabled or requested
            if aggressive or self.config.get('enable_aggressive_cleanup', False):
                aggressive_cleanup = self._perform_aggressive_cleanup()
                cleanup_results['operations'].extend(aggressive_cleanup)
                cleanup_results['total_freed_mb'] += sum(
                    op.get('freed_mb', 0) for op in aggressive_cleanup
                )
            
            # Docker cleanup
            docker_cleanup = self._cleanup_docker()
            cleanup_results['operations'].append(docker_cleanup)
            cleanup_results['total_freed_mb'] += docker_cleanup.get('freed_mb', 0)
            
            self.logger.info(f"Cleanup completed: {cleanup_results['total_freed_mb']} MB freed")
            
        except Exception as e:
            self.logger.error(f"Cleanup operation failed: {e}")
            cleanup_results['errors'].append(str(e))
        
        return cleanup_results
    
    def _cleanup_logs(self) -> Dict:
        """Clean up and rotate log files"""
        result = {'operation': 'log_cleanup', 'freed_mb': 0, 'files_processed': 0}
        
        try:
            log_config = self.cleanup_paths['logs']
            log_path = Path(log_config['path'])
            
            if not log_path.exists():
                return result
            
            retention_date = datetime.now() - timedelta(days=log_config['retention_days'])
            
            # Process log files
            for pattern in log_config['patterns']:
                for log_file in log_path.glob(pattern):
                    try:
                        if log_file.is_file():
                            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                            file_size = log_file.stat().st_size
                            
                            if file_mtime < retention_date:
                                # Old file - remove or compress
                                if log_config.get('compress_old') and not str(log_file).endswith('.gz'):
                                    # Compress instead of delete
                                    compressed_path = f"{log_file}.gz"
                                    with open(log_file, 'rb') as f_in:
                                        with gzip.open(compressed_path, 'wb') as f_out:
                                            shutil.copyfileobj(f_in, f_out)
                                    
                                    log_file.unlink()
                                    compressed_size = os.path.getsize(compressed_path)
                                    result['freed_mb'] += (file_size - compressed_size) / (1024 * 1024)
                                    
                                else:
                                    # Delete old compressed files
                                    log_file.unlink()
                                    result['freed_mb'] += file_size / (1024 * 1024)
                                
                                result['files_processed'] += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to process log file {log_file}: {e}")
            
            # Rotate current log files if they're too large
            self._rotate_large_logs(log_path, result)
            
        except Exception as e:
            self.logger.error(f"Log cleanup failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _rotate_large_logs(self, log_path: Path, result: Dict):
        """Rotate log files that are too large"""
        max_size_mb = 50  # Rotate logs larger than 50MB
        
        for log_file in log_path.glob('*.log'):
            if log_file.is_file():
                size_mb = log_file.stat().st_size / (1024 * 1024)
                if size_mb > max_size_mb:
                    # Rotate the log
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    rotated_name = f"{log_file.stem}_{timestamp}.log"
                    rotated_path = log_path / rotated_name
                    
                    shutil.move(str(log_file), str(rotated_path))
                    
                    # Create new empty log file
                    log_file.touch()
                    
                    # Compress the rotated file
                    with open(rotated_path, 'rb') as f_in:
                        with gzip.open(f"{rotated_path}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    rotated_path.unlink()
                    result['files_processed'] += 1
    
    def _cleanup_reports(self) -> Dict:
        """Clean up old report files"""
        result = {'operation': 'report_cleanup', 'freed_mb': 0, 'files_processed': 0}
        
        try:
            report_config = self.cleanup_paths['reports']
            report_path = Path(report_config['path'])
            
            if not report_path.exists():
                return result
            
            retention_date = datetime.now() - timedelta(days=report_config['retention_days'])
            exclude_dirs = set(report_config.get('exclude_dirs', []))
            
            # Process report files
            for pattern in report_config['patterns']:
                for report_file in report_path.rglob(pattern):
                    try:
                        # Skip excluded directories
                        if any(excluded in report_file.parts for excluded in exclude_dirs):
                            continue
                        
                        if report_file.is_file():
                            file_mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                            
                            if file_mtime < retention_date:
                                file_size = report_file.stat().st_size
                                report_file.unlink()
                                result['freed_mb'] += file_size / (1024 * 1024)
                                result['files_processed'] += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to process report file {report_file}: {e}")
            
        except Exception as e:
            self.logger.error(f"Report cleanup failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _cleanup_cache(self) -> Dict:
        """Clean up cache files"""
        result = {'operation': 'cache_cleanup', 'freed_mb': 0, 'files_processed': 0}
        
        try:
            cache_config = self.cleanup_paths['cache']
            cache_path = Path(cache_config['path'])
            
            if not cache_path.exists():
                return result
            
            retention_date = datetime.now() - timedelta(days=cache_config['retention_days'])
            
            # Process cache files
            for pattern in cache_config['patterns']:
                if cache_config.get('recursive', True):
                    files = cache_path.rglob(pattern)
                else:
                    files = cache_path.glob(pattern)
                
                for cache_file in files:
                    try:
                        if cache_file.is_file():
                            file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                            
                            if file_mtime < retention_date:
                                file_size = cache_file.stat().st_size
                                cache_file.unlink()
                                result['freed_mb'] += file_size / (1024 * 1024)
                                result['files_processed'] += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to process cache file {cache_file}: {e}")
            
        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _cleanup_temp_files(self) -> Dict:
        """Clean up temporary files"""
        result = {'operation': 'temp_cleanup', 'freed_mb': 0, 'files_processed': 0}
        
        try:
            temp_config = self.cleanup_paths['temp']
            temp_path = Path(temp_config['path'])
            
            if not temp_path.exists():
                return result
            
            retention_hours = temp_config['retention_hours']
            retention_date = datetime.now() - timedelta(hours=retention_hours)
            
            # Process temp files
            for pattern in temp_config['patterns']:
                for temp_file in temp_path.glob(pattern):
                    try:
                        if temp_file.is_file():
                            file_mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                            
                            if file_mtime < retention_date:
                                file_size = temp_file.stat().st_size
                                temp_file.unlink()
                                result['freed_mb'] += file_size / (1024 * 1024)
                                result['files_processed'] += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to process temp file {temp_file}: {e}")
            
        except Exception as e:
            self.logger.error(f"Temp cleanup failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _vacuum_databases(self) -> Dict:
        """Vacuum SQLite databases to reclaim space"""
        result = {'operation': 'database_vacuum', 'freed_mb': 0, 'databases_processed': 0}
        
        try:
            import sqlite3
            
            # Database paths to vacuum
            db_paths = [
                '/app/data/database/veeva_opendata.db',
                '/app/data/metrics.db'
            ]
            
            for db_path in db_paths:
                if os.path.exists(db_path):
                    try:
                        # Get size before vacuum
                        size_before = os.path.getsize(db_path)
                        
                        # Perform vacuum
                        with sqlite3.connect(db_path) as conn:
                            conn.execute('VACUUM')
                            conn.execute('ANALYZE')
                        
                        # Get size after vacuum
                        size_after = os.path.getsize(db_path)
                        freed = (size_before - size_after) / (1024 * 1024)
                        
                        result['freed_mb'] += max(0, freed)  # Only positive values
                        result['databases_processed'] += 1
                        
                        self.logger.info(f"Vacuumed {db_path}: {freed:.2f} MB freed")
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to vacuum {db_path}: {e}")
            
        except Exception as e:
            self.logger.error(f"Database vacuum failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _cleanup_docker(self) -> Dict:
        """Clean up Docker resources"""
        result = {'operation': 'docker_cleanup', 'freed_mb': 0, 'items_cleaned': 0}
        
        try:
            # Clean up unused Docker resources
            commands = [
                ['docker', 'system', 'prune', '-f'],
                ['docker', 'container', 'prune', '-f'],
                ['docker', 'image', 'prune', '-f']
            ]
            
            for cmd in commands:
                try:
                    subprocess.run(cmd, capture_output=True, check=True, timeout=60)
                    result['items_cleaned'] += 1
                except subprocess.CalledProcessError:
                    # Docker command failed, but continue with other cleanup
                    pass
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Docker command timed out: {' '.join(cmd)}")
            
            # Estimate space freed (Docker doesn't provide exact numbers)
            result['freed_mb'] = result['items_cleaned'] * 10  # Rough estimate
            
        except Exception as e:
            self.logger.error(f"Docker cleanup failed: {e}")
            result['error'] = str(e)
        
        return result
    
    def _perform_aggressive_cleanup(self) -> List[Dict]:
        """Perform aggressive cleanup operations"""
        operations = []
        
        try:
            # More aggressive log cleanup
            aggressive_log = {
                'operation': 'aggressive_log_cleanup',
                'freed_mb': 0,
                'files_processed': 0
            }
            
            # Remove all logs older than 3 days
            log_path = Path('/app/logs')
            if log_path.exists():
                cutoff = datetime.now() - timedelta(days=3)
                for log_file in log_path.glob('**/*'):
                    if log_file.is_file():
                        file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if file_mtime < cutoff:
                            size = log_file.stat().st_size
                            log_file.unlink()
                            aggressive_log['freed_mb'] += size / (1024 * 1024)
                            aggressive_log['files_processed'] += 1
            
            operations.append(aggressive_log)
            
            # Aggressive report cleanup
            aggressive_report = {
                'operation': 'aggressive_report_cleanup',
                'freed_mb': 0,
                'files_processed': 0
            }
            
            # Remove validation reports older than 14 days
            reports_path = Path('/app/reports/validation')
            if reports_path.exists():
                cutoff = datetime.now() - timedelta(days=14)
                for report_file in reports_path.glob('**/*'):
                    if report_file.is_file():
                        file_mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                        if file_mtime < cutoff:
                            size = report_file.stat().st_size
                            report_file.unlink()
                            aggressive_report['freed_mb'] += size / (1024 * 1024)
                            aggressive_report['files_processed'] += 1
            
            operations.append(aggressive_report)
            
        except Exception as e:
            self.logger.error(f"Aggressive cleanup failed: {e}")
        
        return operations
    
    def generate_space_report(self) -> Dict:
        """Generate comprehensive disk space report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': self.check_disk_status(),
            'directory_usage': {},
            'cleanup_recommendations': []
        }
        
        # Analyze key directories
        key_dirs = [
            '/app/data',
            '/app/logs',
            '/app/reports',
            '/app/cache',
            '/tmp'
        ]
        
        for directory in key_dirs:
            if os.path.exists(directory):
                report['directory_usage'][directory] = self._analyze_directory_usage(directory)
        
        # Generate cleanup recommendations
        report['cleanup_recommendations'] = self._generate_cleanup_recommendations(report)
        
        return report
    
    def _analyze_directory_usage(self, directory: str) -> Dict:
        """Analyze disk usage for a specific directory"""
        try:
            total_size = 0
            file_count = 0
            largest_files = []
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        
                        # Track largest files
                        largest_files.append({
                            'path': file_path,
                            'size_mb': round(file_size / (1024 * 1024), 2)
                        })
                        
                    except (OSError, IOError):
                        # Skip files we can't access
                        continue
            
            # Keep only top 10 largest files
            largest_files = sorted(largest_files, key=lambda x: x['size_mb'], reverse=True)[:10]
            
            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'largest_files': largest_files
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze directory {directory}: {e}")
            return {}
    
    def _generate_cleanup_recommendations(self, report: Dict) -> List[Dict]:
        """Generate cleanup recommendations based on analysis"""
        recommendations = []
        
        status = report['overall_status']
        
        if status['usage']['used_percent'] > 90:
            recommendations.append({
                'priority': 'high',
                'action': 'immediate_cleanup',
                'description': 'Disk usage critical - immediate cleanup required'
            })
        
        # Check for large directories
        for directory, usage in report['directory_usage'].items():
            if usage.get('total_size_mb', 0) > 1000:  # > 1GB
                recommendations.append({
                    'priority': 'medium',
                    'action': 'review_directory',
                    'description': f'{directory} using {usage["total_size_mb"]} MB',
                    'details': usage
                })
        
        return recommendations


def main():
    """Main entry point for disk space management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Data Quality System Disk Space Manager')
    parser.add_argument('action', 
                       choices=['status', 'cleanup', 'report', 'aggressive-cleanup'],
                       help='Action to perform')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    manager = DiskSpaceManager(config_path=args.config)
    
    if args.action == 'status':
        status = manager.check_disk_status()
        
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            usage = status['usage']
            print(f"🖥️  Disk Status: {status['status'].upper()}")
            print(f"📊 Usage: {usage['used_gb']} GB / {usage['total_gb']} GB ({usage['used_percent']}%)")
            print(f"💿 Free: {usage['free_gb']} GB ({usage['free_percent']}%)")
            print(f"📋 Status: {status['message']}")
            print(f"⚡ Action: {status['action_needed']}")
    
    elif args.action == 'cleanup':
        print("🧹 Starting disk cleanup...")
        results = manager.perform_cleanup()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"✅ Cleanup completed: {results['total_freed_mb']:.2f} MB freed")
            for op in results['operations']:
                if op.get('freed_mb', 0) > 0:
                    print(f"   📁 {op['operation']}: {op.get('freed_mb', 0):.2f} MB")
            
            if results['errors']:
                print("⚠️  Errors encountered:")
                for error in results['errors']:
                    print(f"   - {error}")
    
    elif args.action == 'aggressive-cleanup':
        print("🧹🔥 Starting aggressive disk cleanup...")
        results = manager.perform_cleanup(aggressive=True)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"✅ Aggressive cleanup completed: {results['total_freed_mb']:.2f} MB freed")
            for op in results['operations']:
                if op.get('freed_mb', 0) > 0:
                    print(f"   📁 {op['operation']}: {op.get('freed_mb', 0):.2f} MB")
    
    elif args.action == 'report':
        report = manager.generate_space_report()
        
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print("📊 Disk Space Report")
            print("=" * 50)
            
            status = report['overall_status']
            usage = status['usage']
            print(f"Overall Status: {status['status'].upper()}")
            print(f"Total Space: {usage['total_gb']} GB")
            print(f"Used Space: {usage['used_gb']} GB ({usage['used_percent']}%)")
            print(f"Free Space: {usage['free_gb']} GB")
            
            print("\nDirectory Usage:")
            for directory, usage_info in report['directory_usage'].items():
                print(f"  {directory}: {usage_info.get('total_size_mb', 0)} MB")
            
            if report['cleanup_recommendations']:
                print("\nRecommendations:")
                for rec in report['cleanup_recommendations']:
                    print(f"  [{rec['priority'].upper()}] {rec['description']}")


if __name__ == '__main__':
    main()