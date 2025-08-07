#!/usr/bin/env python3
"""
Health check script for the Veeva Data Quality System
Used by Docker healthcheck and monitoring systems
"""

import sys
import json
import time
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Configure minimal logging for health checks
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class HealthChecker:
    """Lightweight health check for the application"""
    
    def __init__(self, project_path: str = "/app"):
        self.project_path = Path(project_path)
        self.db_path = self.project_path / "data" / "veeva_healthcare_data.db"
        
    def check_database_health(self) -> Dict[str, Any]:
        """Quick database connectivity and performance check"""
        health = {
            'database_connected': False,
            'query_time_ms': 0,
            'record_count': 0,
            'error': None
        }
        
        try:
            if not self.db_path.exists():
                health['error'] = f"Database file not found: {self.db_path}"
                return health
            
            start_time = time.time()
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cursor = conn.cursor()
                
                # Quick connectivity test
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    health['database_connected'] = True
                    health['query_time_ms'] = round((time.time() - start_time) * 1000, 2)
                    
                    # Quick record count if table exists
                    try:
                        cursor.execute("SELECT COUNT(*) FROM healthcare_data LIMIT 1")
                        health['record_count'] = cursor.fetchone()[0]
                    except sqlite3.Error:
                        # Table might not exist yet, that's okay for health check
                        pass
                        
        except sqlite3.Error as e:
            health['error'] = f"Database error: {e}"
        except Exception as e:
            health['error'] = f"Unexpected error: {e}"
            
        return health
    
    def check_file_system_health(self) -> Dict[str, Any]:
        """Check file system accessibility and space"""
        health = {
            'data_directory_accessible': False,
            'logs_directory_accessible': False,
            'sufficient_disk_space': False,
            'error': None
        }
        
        try:
            # Check data directory
            data_dir = self.project_path / "data"
            if data_dir.exists():
                health['data_directory_accessible'] = True
            
            # Check logs directory
            logs_dir = self.project_path / "logs"
            if logs_dir.exists() or logs_dir.parent.exists():
                health['logs_directory_accessible'] = True
            
            # Check disk space (minimum 1GB free)
            import shutil
            free_space = shutil.disk_usage(self.project_path).free
            health['sufficient_disk_space'] = free_space > 1024 * 1024 * 1024  # 1GB
            
        except Exception as e:
            health['error'] = f"File system check error: {e}"
            
        return health
    
    def check_application_health(self) -> Dict[str, Any]:
        """Check application-specific health indicators"""
        health = {
            'python_path_accessible': False,
            'required_modules_available': False,
            'config_files_present': False,
            'error': None
        }
        
        try:
            # Check if Python modules are accessible
            try:
                import sqlite3
                import psutil
                health['required_modules_available'] = True
            except ImportError as e:
                health['error'] = f"Required modules not available: {e}"
            
            # Check Python path structure
            python_dir = self.project_path / "python"
            if python_dir.exists():
                health['python_path_accessible'] = True
            
            # Check config files
            config_dir = self.project_path / "python" / "config"
            if config_dir.exists():
                health['config_files_present'] = True
                
        except Exception as e:
            health['error'] = f"Application check error: {e}"
            
        return health
    
    def run_comprehensive_check(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status"""
        
        start_time = time.time()
        
        overall_health = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'checks': {},
            'errors': [],
            'warnings': [],
            'check_duration_ms': 0
        }
        
        # Run individual checks
        try:
            overall_health['checks']['database'] = self.check_database_health()
            overall_health['checks']['filesystem'] = self.check_file_system_health()
            overall_health['checks']['application'] = self.check_application_health()
            
            # Analyze results and determine overall status
            errors = []
            warnings = []
            
            # Database health analysis
            db_check = overall_health['checks']['database']
            if not db_check['database_connected']:
                if db_check.get('error'):
                    errors.append(f"Database: {db_check['error']}")
                else:
                    errors.append("Database connection failed")
            elif db_check['query_time_ms'] > 1000:  # Slow query threshold
                warnings.append(f"Database queries are slow: {db_check['query_time_ms']}ms")
            
            # File system health analysis
            fs_check = overall_health['checks']['filesystem']
            if not fs_check['data_directory_accessible']:
                errors.append("Data directory not accessible")
            if not fs_check['sufficient_disk_space']:
                errors.append("Insufficient disk space")
            if fs_check.get('error'):
                errors.append(f"Filesystem: {fs_check['error']}")
            
            # Application health analysis
            app_check = overall_health['checks']['application']
            if not app_check['required_modules_available']:
                errors.append("Required Python modules not available")
            if not app_check['python_path_accessible']:
                warnings.append("Python application path not accessible")
            if app_check.get('error'):
                errors.append(f"Application: {app_check['error']}")
            
            # Set overall status
            overall_health['errors'] = errors
            overall_health['warnings'] = warnings
            
            if errors:
                overall_health['overall_status'] = 'UNHEALTHY'
            elif warnings:
                overall_health['overall_status'] = 'WARNING'
            else:
                overall_health['overall_status'] = 'HEALTHY'
                
        except Exception as e:
            overall_health['overall_status'] = 'ERROR'
            overall_health['errors'].append(f"Health check failed: {e}")
            logger.error(f"Health check failed: {e}")
        
        overall_health['check_duration_ms'] = round((time.time() - start_time) * 1000, 2)
        return overall_health
    
    def run_quick_check(self) -> bool:
        """Quick health check returning boolean result for Docker healthcheck"""
        try:
            # Quick database connectivity test
            if self.db_path.exists():
                with sqlite3.connect(self.db_path, timeout=2) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result is not None and result[0] == 1
            else:
                # If database doesn't exist yet, check if the data directory is accessible
                return self.project_path.exists() and (self.project_path / "data").parent.exists()
                
        except Exception as e:
            logger.warning(f"Quick health check failed: {e}")
            return False


def main():
    """Main health check execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Veeva Data Quality System Health Check")
    parser.add_argument("--mode", choices=["quick", "comprehensive"], default="comprehensive",
                       help="Health check mode (default: comprehensive)")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                       help="Output format (default: text)")
    parser.add_argument("--project-path", type=str, default="/app",
                       help="Project root path (default: /app)")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress output, only return exit code")
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.project_path)
    
    try:
        if args.mode == "quick":
            # Quick check for Docker healthcheck
            is_healthy = checker.run_quick_check()
            
            if not args.quiet:
                if args.format == "json":
                    result = {
                        "status": "HEALTHY" if is_healthy else "UNHEALTHY",
                        "timestamp": datetime.now().isoformat()
                    }
                    print(json.dumps(result))
                else:
                    status = "HEALTHY" if is_healthy else "UNHEALTHY"
                    print(f"Health Status: {status}")
            
            sys.exit(0 if is_healthy else 1)
            
        else:
            # Comprehensive check
            health_result = checker.run_comprehensive_check()
            
            if not args.quiet:
                if args.format == "json":
                    print(json.dumps(health_result, indent=2))
                else:
                    # Text format output
                    print(f"Health Check Report - {health_result['timestamp']}")
                    print(f"Overall Status: {health_result['overall_status']}")
                    print(f"Check Duration: {health_result['check_duration_ms']}ms")
                    
                    if health_result['errors']:
                        print("\nErrors:")
                        for error in health_result['errors']:
                            print(f"  - {error}")
                    
                    if health_result['warnings']:
                        print("\nWarnings:")
                        for warning in health_result['warnings']:
                            print(f"  - {warning}")
                    
                    print("\nDetailed Checks:")
                    for check_name, check_result in health_result['checks'].items():
                        print(f"  {check_name.title()}:")
                        for key, value in check_result.items():
                            if key != 'error' or value:  # Only show errors if they exist
                                print(f"    {key}: {value}")
            
            # Exit with appropriate code
            if health_result['overall_status'] == 'HEALTHY':
                sys.exit(0)
            elif health_result['overall_status'] == 'WARNING':
                sys.exit(0)  # Warnings are still considered passing for deployment
            else:
                sys.exit(1)
                
    except Exception as e:
        if not args.quiet:
            print(f"Health check failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()