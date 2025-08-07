#!/usr/bin/env python3
"""
Health Check System for Veeva Data Quality System
Provides comprehensive health monitoring and status endpoints
"""

import os
import time
import psutil
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging

from python.config.database_config import DatabaseConfig
from python.utils.database import DatabaseManager
from python.utils.monitoring import SystemMonitor


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""
    name: str
    status: str  # HEALTHY, WARNING, CRITICAL, UNKNOWN
    message: str
    details: Dict[str, Any]
    execution_time: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat()
        }


class HealthChecker:
    """Comprehensive health checking system"""
    
    def __init__(self, db_config: DatabaseConfig):
        self.db_config = db_config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.system_monitor = SystemMonitor(db_config.db_path)
        
        # Health check thresholds
        self.thresholds = {
            'cpu_warning': 80.0,
            'cpu_critical': 95.0,
            'memory_warning': 85.0,
            'memory_critical': 95.0,
            'disk_warning': 90.0,
            'disk_critical': 98.0,
            'query_time_warning': 5.0,  # seconds
            'query_time_critical': 15.0,  # seconds
            'db_size_warning': 10.0,  # GB
            'db_size_critical': 20.0,  # GB
        }
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks and return results"""
        checks = {
            'database': self._check_database_health,
            'system_resources': self._check_system_resources,
            'disk_space': self._check_disk_space,
            'application': self._check_application_health,
            'performance': self._check_performance,
        }
        
        results = {}
        for check_name, check_func in checks.items():
            try:
                start_time = time.time()
                result = check_func()
                execution_time = time.time() - start_time
                
                results[check_name] = HealthCheckResult(
                    name=check_name,
                    status=result.get('status', 'UNKNOWN'),
                    message=result.get('message', ''),
                    details=result.get('details', {}),
                    execution_time=execution_time,
                    timestamp=datetime.now()
                )
            except Exception as e:
                self.logger.error(f"Health check {check_name} failed: {e}")
                results[check_name] = HealthCheckResult(
                    name=check_name,
                    status='CRITICAL',
                    message=f"Health check failed: {str(e)}",
                    details={'error': str(e)},
                    execution_time=0.0,
                    timestamp=datetime.now()
                )
        
        return results
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and integrity"""
        try:
            db_manager = DatabaseManager(self.db_config)
            
            # Basic connectivity check
            health_status = db_manager.health_check()
            
            if not health_status['database_accessible']:
                return {
                    'status': 'CRITICAL',
                    'message': 'Database is not accessible',
                    'details': health_status
                }
            
            # Database size check
            db_path = Path(self.db_config.db_path)
            if db_path.exists():
                db_size_gb = db_path.stat().st_size / (1024 ** 3)
                
                status = 'HEALTHY'
                message = 'Database is accessible and healthy'
                
                if db_size_gb > self.thresholds['db_size_critical']:
                    status = 'CRITICAL'
                    message = f'Database size critical: {db_size_gb:.2f} GB'
                elif db_size_gb > self.thresholds['db_size_warning']:
                    status = 'WARNING'
                    message = f'Database size warning: {db_size_gb:.2f} GB'
                
                health_status['database_size_gb'] = db_size_gb
            
            # Table integrity check
            try:
                overview = db_manager.get_database_overview()
                health_status['table_info'] = overview
                
                # Check for empty tables
                empty_tables = []
                for table_name, table_info in overview.get('tables', {}).items():
                    if table_info.get('row_count', 0) == 0:
                        empty_tables.append(table_name)
                
                if empty_tables:
                    status = 'WARNING'
                    message = f'Empty tables detected: {", ".join(empty_tables)}'
                    health_status['empty_tables'] = empty_tables
                
            except Exception as e:
                status = 'WARNING'
                message = f'Could not get table information: {str(e)}'
                health_status['table_info_error'] = str(e)
            
            return {
                'status': status,
                'message': message,
                'details': health_status
            }
            
        except Exception as e:
            return {
                'status': 'CRITICAL',
                'message': f'Database health check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system CPU and memory usage"""
        try:
            # Get current system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            details = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'memory_available_gb': memory.available / (1024 ** 3),
                'memory_total_gb': memory.total / (1024 ** 3)
            }
            
            # Determine overall status
            status = 'HEALTHY'
            messages = []
            
            if cpu_percent > self.thresholds['cpu_critical']:
                status = 'CRITICAL'
                messages.append(f'CPU usage critical: {cpu_percent:.1f}%')
            elif cpu_percent > self.thresholds['cpu_warning']:
                status = 'WARNING' if status == 'HEALTHY' else status
                messages.append(f'CPU usage high: {cpu_percent:.1f}%')
            
            if memory_percent > self.thresholds['memory_critical']:
                status = 'CRITICAL'
                messages.append(f'Memory usage critical: {memory_percent:.1f}%')
            elif memory_percent > self.thresholds['memory_warning']:
                status = 'WARNING' if status == 'HEALTHY' else status
                messages.append(f'Memory usage high: {memory_percent:.1f}%')
            
            message = '; '.join(messages) if messages else 'System resources normal'
            
            return {
                'status': status,
                'message': message,
                'details': details
            }
            
        except Exception as e:
            return {
                'status': 'UNKNOWN',
                'message': f'Could not check system resources: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space availability"""
        try:
            db_path = Path(self.db_config.db_path)
            disk_usage = psutil.disk_usage(str(db_path.parent))
            
            used_percent = (disk_usage.used / disk_usage.total) * 100
            free_gb = disk_usage.free / (1024 ** 3)
            
            details = {
                'disk_total_gb': disk_usage.total / (1024 ** 3),
                'disk_used_gb': disk_usage.used / (1024 ** 3),
                'disk_free_gb': free_gb,
                'disk_used_percent': used_percent
            }
            
            status = 'HEALTHY'
            message = f'Disk space normal: {used_percent:.1f}% used, {free_gb:.1f} GB free'
            
            if used_percent > self.thresholds['disk_critical']:
                status = 'CRITICAL'
                message = f'Disk space critical: {used_percent:.1f}% used'
            elif used_percent > self.thresholds['disk_warning']:
                status = 'WARNING'
                message = f'Disk space warning: {used_percent:.1f}% used'
            
            return {
                'status': status,
                'message': message,
                'details': details
            }
            
        except Exception as e:
            return {
                'status': 'UNKNOWN',
                'message': f'Could not check disk space: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _check_application_health(self) -> Dict[str, Any]:
        """Check application-specific health"""
        try:
            details = {}
            status = 'HEALTHY'
            messages = []
            
            # Check log directory
            log_dir = Path('logs')
            if log_dir.exists():
                log_files = list(log_dir.glob('*.log'))
                details['log_files_count'] = len(log_files)
                
                # Check for recent log errors
                recent_errors = self._check_recent_log_errors()
                if recent_errors:
                    status = 'WARNING'
                    messages.append(f'{recent_errors} recent log errors')
                    details['recent_errors'] = recent_errors
            
            # Check reports directory
            reports_dir = Path('reports')
            if reports_dir.exists():
                report_files = list(reports_dir.rglob('*'))
                details['report_files_count'] = len([f for f in report_files if f.is_file()])
            
            # Check configuration
            config_status = self._check_configuration()
            details['configuration'] = config_status
            
            if not config_status.get('valid', True):
                status = 'WARNING'
                messages.append('Configuration issues detected')
            
            message = '; '.join(messages) if messages else 'Application healthy'
            
            return {
                'status': status,
                'message': message,
                'details': details
            }
            
        except Exception as e:
            return {
                'status': 'UNKNOWN',
                'message': f'Could not check application health: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _check_performance(self) -> Dict[str, Any]:
        """Check system performance metrics"""
        try:
            db_manager = DatabaseManager(self.db_config)
            
            # Run a simple performance test
            start_time = time.time()
            result = db_manager.execute_query("SELECT COUNT(*) FROM sqlite_master")
            query_time = time.time() - start_time
            
            details = {
                'query_time': query_time,
                'query_successful': result.success
            }
            
            status = 'HEALTHY'
            message = f'Performance normal: {query_time:.3f}s query time'
            
            if query_time > self.thresholds['query_time_critical']:
                status = 'CRITICAL'
                message = f'Performance critical: {query_time:.3f}s query time'
            elif query_time > self.thresholds['query_time_warning']:
                status = 'WARNING'
                message = f'Performance slow: {query_time:.3f}s query time'
            
            # Add system load information
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            if load_avg:
                details['load_average'] = {
                    '1min': load_avg[0],
                    '5min': load_avg[1],
                    '15min': load_avg[2]
                }
            
            return {
                'status': status,
                'message': message,
                'details': details
            }
            
        except Exception as e:
            return {
                'status': 'UNKNOWN',
                'message': f'Could not check performance: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def _check_recent_log_errors(self, hours: int = 1) -> int:
        """Count recent errors in log files"""
        try:
            log_dir = Path('logs')
            if not log_dir.exists():
                return 0
            
            error_count = 0
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            for log_file in log_dir.glob('*.log'):
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if 'ERROR' in line or 'CRITICAL' in line:
                                error_count += 1
                except Exception:
                    continue
            
            return error_count
            
        except Exception:
            return 0
    
    def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity"""
        try:
            config_info = {
                'database_path_exists': Path(self.db_config.db_path).parent.exists(),
                'database_writable': os.access(Path(self.db_config.db_path).parent, os.W_OK),
                'pool_size': self.db_config.pool_size,
                'valid': True
            }
            
            if not config_info['database_path_exists']:
                config_info['valid'] = False
                config_info['error'] = 'Database directory does not exist'
            
            if not config_info['database_writable']:
                config_info['valid'] = False
                config_info['error'] = 'Database directory is not writable'
            
            return config_info
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        results = self.run_all_checks()
        
        # Determine overall status
        statuses = [result.status for result in results.values()]
        
        if 'CRITICAL' in statuses:
            overall_status = 'CRITICAL'
        elif 'WARNING' in statuses:
            overall_status = 'WARNING'
        elif 'UNKNOWN' in statuses:
            overall_status = 'UNKNOWN'
        else:
            overall_status = 'HEALTHY'
        
        # Count issues
        status_counts = {
            'HEALTHY': sum(1 for s in statuses if s == 'HEALTHY'),
            'WARNING': sum(1 for s in statuses if s == 'WARNING'),
            'CRITICAL': sum(1 for s in statuses if s == 'CRITICAL'),
            'UNKNOWN': sum(1 for s in statuses if s == 'UNKNOWN')
        }
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'status_counts': status_counts,
            'checks': {name: result.to_dict() for name, result in results.items()}
        }
    
    def export_health_report(self, output_path: str) -> bool:
        """Export comprehensive health report to file"""
        try:
            health_summary = self.get_health_summary()
            
            with open(output_path, 'w') as f:
                json.dump(health_summary, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export health report: {e}")
            return False


if __name__ == '__main__':
    # Example usage
    import os
    import sys
    
    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize health checker
    db_config = DatabaseConfig.from_env()
    health_checker = HealthChecker(db_config)
    
    # Run health check
    summary = health_checker.get_health_summary()
    print(json.dumps(summary, indent=2))
    
    # Export report
    report_path = 'health_report.json'
    if health_checker.export_health_report(report_path):
        print(f"\nHealth report exported to: {report_path}")
    
    # Exit with appropriate code
    exit_code = 0 if summary['overall_status'] == 'HEALTHY' else 1
    sys.exit(exit_code)