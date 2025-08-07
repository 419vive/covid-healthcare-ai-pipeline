#!/usr/bin/env python3
"""
Veeva Data Quality System - Production Readiness Validator

This script validates that the system is ready for production deployment
by checking all critical components, configurations, and dependencies.

Usage:
    python production_readiness_validator.py [--environment=production]

Author: Veeva Data Quality Team
Version: 3.0.0
"""

import os
import sys
import json
import time
import subprocess
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Represents the result of a validation check"""
    check_name: str
    status: str  # PASS, FAIL, WARNING
    message: str
    details: Dict[str, Any] = None
    execution_time: float = 0.0

@dataclass
class ProductionReadinessReport:
    """Complete production readiness report"""
    timestamp: str
    environment: str
    overall_status: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    results: List[ValidationResult]
    recommendations: List[str]

class ProductionReadinessValidator:
    """Validates system readiness for production deployment"""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.project_root = Path(__file__).parent
        self.deploy_dir = self.project_root / "deploy"
        self.results: List[ValidationResult] = []
        
    def validate_all(self) -> ProductionReadinessReport:
        """Run all validation checks"""
        logger.info(f"🔍 Starting production readiness validation for {self.environment}")
        
        # Core infrastructure checks
        self._validate_system_requirements()
        self._validate_docker_environment()
        self._validate_file_structure()
        self._validate_configuration_files()
        
        # Application checks
        self._validate_database_setup()
        self._validate_python_environment()
        self._validate_performance_optimization()
        self._validate_monitoring_setup()
        
        # Security checks
        self._validate_security_configuration()
        self._validate_container_security()
        
        # Operational checks
        self._validate_backup_configuration()
        self._validate_deployment_scripts()
        self._validate_health_checks()
        
        # Generate final report
        return self._generate_report()
    
    def _execute_check(self, check_name: str, check_function) -> ValidationResult:
        """Execute a single validation check with timing"""
        start_time = time.time()
        try:
            result = check_function()
            result.execution_time = time.time() - start_time
            self.results.append(result)
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            result = ValidationResult(
                check_name=check_name,
                status="FAIL",
                message=f"Check failed with exception: {str(e)}",
                execution_time=execution_time
            )
            self.results.append(result)
            return result
    
    def _validate_system_requirements(self) -> ValidationResult:
        """Validate system meets minimum requirements"""
        def check():
            details = {}
            issues = []
            
            # Check available memory
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    mem_total = int([line for line in meminfo.split('\\n') 
                                   if 'MemTotal' in line][0].split()[1]) // 1024
                details['memory_mb'] = mem_total
                if mem_total < 3072:
                    issues.append(f"Insufficient memory: {mem_total}MB < 4GB recommended")
            except:
                # Fallback for non-Linux systems
                details['memory_mb'] = "unknown"
            
            # Check disk space
            disk_usage = os.statvfs(str(self.project_root))
            available_gb = (disk_usage.f_bavail * disk_usage.f_frsize) // (1024**3)
            details['disk_available_gb'] = available_gb
            if available_gb < 20:
                issues.append(f"Insufficient disk space: {available_gb}GB < 20GB recommended")
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "System requirements met"
            
            return ValidationResult(
                check_name="System Requirements",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("System Requirements", check)
    
    def _validate_docker_environment(self) -> ValidationResult:
        """Validate Docker environment"""
        def check():
            details = {}
            issues = []
            
            # Check Docker installation
            try:
                result = subprocess.run(['docker', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    details['docker_version'] = result.stdout.strip()
                else:
                    issues.append("Docker not available")
            except:
                issues.append("Docker not installed or not accessible")
            
            # Check Docker Compose
            try:
                result = subprocess.run(['docker-compose', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    details['compose_version'] = result.stdout.strip()
                else:
                    # Try docker compose plugin
                    result = subprocess.run(['docker', 'compose', 'version'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        details['compose_version'] = result.stdout.strip()
                    else:
                        issues.append("Docker Compose not available")
            except:
                issues.append("Docker Compose not installed")
            
            # Check Docker daemon
            try:
                result = subprocess.run(['docker', 'info'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    issues.append("Docker daemon not running")
            except:
                issues.append("Cannot connect to Docker daemon")
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "Docker environment ready"
            
            return ValidationResult(
                check_name="Docker Environment",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Docker Environment", check)
    
    def _validate_file_structure(self) -> ValidationResult:
        """Validate required file structure exists"""
        def check():
            required_files = [
                "requirements.txt",
                "python/main.py",
                "deploy/Dockerfile",
                "deploy/docker-compose.yml",
                "deploy/scripts/deploy.sh",
                "deploy/scripts/backup.sh",
                "deploy/scripts/install.sh",
                "DEPLOYMENT_GUIDE.md"
            ]
            
            required_dirs = [
                "python",
                "sql",
                "deploy",
                "deploy/scripts",
                "deploy/environments"
            ]
            
            missing_files = []
            missing_dirs = []
            
            for file_path in required_files:
                if not (self.project_root / file_path).exists():
                    missing_files.append(file_path)
            
            for dir_path in required_dirs:
                if not (self.project_root / dir_path).is_dir():
                    missing_dirs.append(dir_path)
            
            issues = []
            if missing_files:
                issues.append(f"Missing files: {', '.join(missing_files)}")
            if missing_dirs:
                issues.append(f"Missing directories: {', '.join(missing_dirs)}")
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "All required files and directories present"
            
            details = {
                "missing_files": missing_files,
                "missing_directories": missing_dirs,
                "total_required_files": len(required_files),
                "total_required_dirs": len(required_dirs)
            }
            
            return ValidationResult(
                check_name="File Structure",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("File Structure", check)
    
    def _validate_configuration_files(self) -> ValidationResult:
        """Validate configuration files"""
        def check():
            env_file = self.deploy_dir / "environments" / f".env.{self.environment}"
            config_issues = []
            details = {}
            
            # Check environment file exists
            if not env_file.exists():
                config_issues.append(f"Environment file missing: {env_file}")
            else:
                details['environment_file'] = str(env_file)
                
                # Parse environment file
                env_vars = {}
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                env_vars[key] = value
                    
                    details['env_vars_count'] = len(env_vars)
                    
                    # Check critical environment variables
                    critical_vars = [
                        'VEEVA_ENV', 'VEEVA_DB_PATH', 'VEEVA_LOG_LEVEL',
                        'BACKUP_ENABLED', 'VEEVA_METRICS_ENABLED'
                    ]
                    
                    missing_vars = [var for var in critical_vars if var not in env_vars]
                    if missing_vars:
                        config_issues.append(f"Missing critical environment variables: {', '.join(missing_vars)}")
                    
                except Exception as e:
                    config_issues.append(f"Error parsing environment file: {e}")
            
            # Check Docker Compose configuration
            compose_file = self.deploy_dir / "docker-compose.yml"
            if not compose_file.exists():
                config_issues.append("Docker Compose file missing")
            
            status = "FAIL" if config_issues else "PASS"
            message = "; ".join(config_issues) if config_issues else "Configuration files valid"
            
            return ValidationResult(
                check_name="Configuration Files",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Configuration Files", check)
    
    def _validate_database_setup(self) -> ValidationResult:
        """Validate database setup and schemas"""
        def check():
            issues = []
            details = {}
            
            # Check SQL files
            sql_files = list((self.project_root / "sql").rglob("*.sql"))
            details['sql_files_count'] = len(sql_files)
            
            if len(sql_files) == 0:
                issues.append("No SQL files found")
            
            # Check for critical SQL files
            critical_sql = [
                "sql/01_schema/create_tables.sql",
                "sql/01_schema/create_indexes.sql"
            ]
            
            missing_sql = []
            for sql_file in critical_sql:
                if not (self.project_root / sql_file).exists():
                    missing_sql.append(sql_file)
            
            if missing_sql:
                issues.append(f"Missing SQL files: {', '.join(missing_sql)}")
            
            # Test database connectivity (if database exists)
            db_path = self.project_root / "data" / "database" / "veeva_opendata.db"
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    details['database_tables'] = [table[0] for table in tables]
                    conn.close()
                    
                    if len(tables) == 0:
                        issues.append("Database exists but has no tables")
                    
                except Exception as e:
                    issues.append(f"Database connection error: {e}")
            else:
                details['database_status'] = "No database file found (will be created on first run)"
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "Database setup valid"
            
            return ValidationResult(
                check_name="Database Setup",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Database Setup", check)
    
    def _validate_python_environment(self) -> ValidationResult:
        """Validate Python environment and dependencies"""
        def check():
            issues = []
            details = {}
            
            # Check Python version
            details['python_version'] = sys.version
            if sys.version_info < (3, 8):
                issues.append(f"Python version too old: {sys.version_info} < 3.8")
            
            # Check requirements.txt
            req_file = self.project_root / "requirements.txt"
            if not req_file.exists():
                issues.append("requirements.txt missing")
            else:
                with open(req_file, 'r') as f:
                    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                details['requirements_count'] = len(requirements)
                
                # Check critical packages
                critical_packages = ['pandas', 'SQLAlchemy', 'pyyaml', 'click']
                missing_packages = []
                for package in critical_packages:
                    if not any(package.lower() in req.lower() for req in requirements):
                        missing_packages.append(package)
                
                if missing_packages:
                    issues.append(f"Missing critical packages in requirements.txt: {', '.join(missing_packages)}")
            
            # Check main application entry point
            main_file = self.project_root / "python" / "main.py"
            if not main_file.exists():
                issues.append("Main application file missing: python/main.py")
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "Python environment ready"
            
            return ValidationResult(
                check_name="Python Environment",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Python Environment", check)
    
    def _validate_performance_optimization(self) -> ValidationResult:
        """Validate performance optimization features"""
        def check():
            issues = []
            details = {}
            
            # Check for performance-related files
            perf_files = [
                "python/cache/cache_manager.py",
                "python/utils/query_cache.py",
                "sql/01_schema/performance_indexes.sql"
            ]
            
            existing_perf_files = []
            for perf_file in perf_files:
                if (self.project_root / perf_file).exists():
                    existing_perf_files.append(perf_file)
            
            details['performance_files'] = existing_perf_files
            
            if len(existing_perf_files) < len(perf_files):
                missing = set(perf_files) - set(existing_perf_files)
                issues.append(f"Missing performance optimization files: {', '.join(missing)}")
            
            # Check for async processing capabilities
            async_files = [f for f in (self.project_root / "python").rglob("*async*.py")]
            details['async_files_count'] = len(async_files)
            
            status = "WARNING" if issues else "PASS"
            message = "; ".join(issues) if issues else "Performance optimization features present"
            
            return ValidationResult(
                check_name="Performance Optimization",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Performance Optimization", check)
    
    def _validate_monitoring_setup(self) -> ValidationResult:
        """Validate monitoring and observability setup"""
        def check():
            issues = []
            details = {}
            
            # Check monitoring configuration files
            monitoring_files = [
                "deploy/monitoring/prometheus.yml",
                "deploy/monitoring/alert_rules.yml"
            ]
            
            existing_monitoring = []
            for mon_file in monitoring_files:
                if (self.project_root / mon_file).exists():
                    existing_monitoring.append(mon_file)
            
            details['monitoring_files'] = existing_monitoring
            
            if len(existing_monitoring) < len(monitoring_files):
                missing = set(monitoring_files) - set(existing_monitoring)
                issues.append(f"Missing monitoring files: {', '.join(missing)}")
            
            # Check for monitoring code
            monitoring_code = [
                "python/utils/monitoring.py"
            ]
            
            for mon_code in monitoring_code:
                if not (self.project_root / mon_code).exists():
                    issues.append(f"Missing monitoring code: {mon_code}")
            
            status = "WARNING" if issues else "PASS"
            message = "; ".join(issues) if issues else "Monitoring setup complete"
            
            return ValidationResult(
                check_name="Monitoring Setup",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Monitoring Setup", check)
    
    def _validate_security_configuration(self) -> ValidationResult:
        """Validate security configuration"""
        def check():
            issues = []
            details = {}
            
            # Check Dockerfile security practices
            dockerfile = self.project_root / "deploy" / "Dockerfile"
            if dockerfile.exists():
                with open(dockerfile, 'r') as f:
                    dockerfile_content = f.read()
                
                security_checks = {
                    'non_root_user': 'USER ' in dockerfile_content,
                    'health_check': 'HEALTHCHECK' in dockerfile_content,
                    'minimal_base': 'slim' in dockerfile_content or 'alpine' in dockerfile_content
                }
                
                details['security_features'] = security_checks
                
                if not security_checks['non_root_user']:
                    issues.append("Dockerfile should specify non-root user")
                if not security_checks['health_check']:
                    issues.append("Dockerfile missing health check")
            else:
                issues.append("Dockerfile not found")
            
            # Check environment configuration for security settings
            env_file = self.deploy_dir / "environments" / f".env.{self.environment}"
            if env_file.exists():
                with open(env_file, 'r') as f:
                    env_content = f.read()
                
                security_vars = {
                    'secure_logs': 'VEEVA_SECURE_LOGS=true' in env_content,
                    'mask_sensitive': 'VEEVA_MASK_SENSITIVE_DATA=true' in env_content
                }
                
                details['security_env_vars'] = security_vars
                
                if self.environment == 'production':
                    if not security_vars['secure_logs']:
                        issues.append("Production should enable secure logging")
                    if not security_vars['mask_sensitive']:
                        issues.append("Production should mask sensitive data")
            
            status = "WARNING" if issues else "PASS"
            message = "; ".join(issues) if issues else "Security configuration appropriate"
            
            return ValidationResult(
                check_name="Security Configuration",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Security Configuration", check)
    
    def _validate_container_security(self) -> ValidationResult:
        """Validate container security settings"""
        def check():
            issues = []
            details = {}
            
            # Check docker-compose security settings
            compose_file = self.deploy_dir / "docker-compose.yml"
            if compose_file.exists():
                with open(compose_file, 'r') as f:
                    compose_content = f.read()
                
                security_features = {
                    'resource_limits': 'limits:' in compose_content,
                    'restart_policy': 'restart:' in compose_content,
                    'health_check': 'healthcheck:' in compose_content
                }
                
                details['container_security'] = security_features
                
                if not security_features['resource_limits']:
                    issues.append("Docker Compose missing resource limits")
                if not security_features['health_check']:
                    issues.append("Docker Compose missing health checks")
            
            status = "WARNING" if issues else "PASS"
            message = "; ".join(issues) if issues else "Container security configured"
            
            return ValidationResult(
                check_name="Container Security",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Container Security", check)
    
    def _validate_backup_configuration(self) -> ValidationResult:
        """Validate backup and recovery configuration"""
        def check():
            issues = []
            details = {}
            
            # Check backup script
            backup_script = self.project_root / "deploy" / "scripts" / "backup.sh"
            if not backup_script.exists():
                issues.append("Backup script missing")
            else:
                details['backup_script'] = str(backup_script)
                
                # Check if script is executable
                if not os.access(backup_script, os.X_OK):
                    issues.append("Backup script not executable")
            
            # Check restore script
            restore_script = self.project_root / "deploy" / "scripts" / "restore.sh"
            if not restore_script.exists():
                issues.append("Restore script missing")
            else:
                details['restore_script'] = str(restore_script)
            
            # Check backup directory
            backup_dir = self.project_root / "deploy" / "backups"
            backup_dir.mkdir(exist_ok=True)
            details['backup_directory'] = str(backup_dir)
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "Backup configuration ready"
            
            return ValidationResult(
                check_name="Backup Configuration",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Backup Configuration", check)
    
    def _validate_deployment_scripts(self) -> ValidationResult:
        """Validate deployment scripts"""
        def check():
            issues = []
            details = {}
            
            required_scripts = [
                "deploy/scripts/deploy.sh",
                "deploy/scripts/backup.sh",
                "deploy/scripts/restore.sh",
                "deploy/scripts/monitor.sh",
                "deploy/scripts/install.sh"
            ]
            
            existing_scripts = []
            executable_scripts = []
            
            for script in required_scripts:
                script_path = self.project_root / script
                if script_path.exists():
                    existing_scripts.append(script)
                    if os.access(script_path, os.X_OK):
                        executable_scripts.append(script)
                else:
                    issues.append(f"Missing deployment script: {script}")
            
            details['existing_scripts'] = existing_scripts
            details['executable_scripts'] = executable_scripts
            
            non_executable = set(existing_scripts) - set(executable_scripts)
            if non_executable:
                issues.append(f"Scripts not executable: {', '.join(non_executable)}")
            
            status = "FAIL" if issues else "PASS"
            message = "; ".join(issues) if issues else "All deployment scripts ready"
            
            return ValidationResult(
                check_name="Deployment Scripts",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Deployment Scripts", check)
    
    def _validate_health_checks(self) -> ValidationResult:
        """Validate health check implementation"""
        def check():
            issues = []
            details = {}
            
            # Check if main application supports status command
            main_file = self.project_root / "python" / "main.py"
            if main_file.exists():
                with open(main_file, 'r') as f:
                    main_content = f.read()
                
                health_features = {
                    'status_command': 'status' in main_content,
                    'health_endpoint': 'health' in main_content
                }
                
                details['health_features'] = health_features
                
                if not health_features['status_command']:
                    issues.append("Main application missing status command")
            
            # Check Docker health check
            dockerfile = self.project_root / "deploy" / "Dockerfile"
            if dockerfile.exists():
                with open(dockerfile, 'r') as f:
                    dockerfile_content = f.read()
                
                if 'HEALTHCHECK' not in dockerfile_content:
                    issues.append("Dockerfile missing health check")
                else:
                    details['docker_healthcheck'] = True
            
            status = "WARNING" if issues else "PASS"
            message = "; ".join(issues) if issues else "Health checks implemented"
            
            return ValidationResult(
                check_name="Health Checks",
                status=status,
                message=message,
                details=details
            )
        
        return self._execute_check("Health Checks", check)
    
    def _generate_report(self) -> ProductionReadinessReport:
        """Generate comprehensive production readiness report"""
        total_checks = len(self.results)
        passed_checks = len([r for r in self.results if r.status == "PASS"])
        failed_checks = len([r for r in self.results if r.status == "FAIL"])
        warning_checks = len([r for r in self.results if r.status == "WARNING"])
        
        # Determine overall status
        if failed_checks > 0:
            overall_status = "FAIL"
        elif warning_checks > 0:
            overall_status = "WARNING"
        else:
            overall_status = "PASS"
        
        # Generate recommendations
        recommendations = []
        
        for result in self.results:
            if result.status == "FAIL":
                recommendations.append(f"CRITICAL: {result.message}")
            elif result.status == "WARNING":
                recommendations.append(f"IMPROVE: {result.message}")
        
        # Add general recommendations
        if self.environment == "production":
            recommendations.extend([
                "Review security settings before production deployment",
                "Test backup and restore procedures",
                "Configure monitoring alerts",
                "Plan capacity scaling strategy",
                "Document operational procedures"
            ])
        
        return ProductionReadinessReport(
            timestamp=datetime.now().isoformat(),
            environment=self.environment,
            overall_status=overall_status,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warning_checks=warning_checks,
            results=self.results,
            recommendations=recommendations
        )
    
    def save_report(self, report: ProductionReadinessReport, output_path: str = None):
        """Save report to file"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"production_readiness_report_{timestamp}.json"
        
        # Convert dataclass to dict for JSON serialization
        report_dict = asdict(report)
        
        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        logger.info(f"📊 Report saved to: {output_path}")
        return output_path

def print_report_summary(report: ProductionReadinessReport):
    """Print a formatted summary of the report"""
    status_colors = {
        "PASS": "🟢",
        "WARNING": "🟡", 
        "FAIL": "🔴"
    }
    
    print(f"\\n{'='*80}")
    print(f"🔍 VEEVA DATA QUALITY SYSTEM - PRODUCTION READINESS REPORT")
    print(f"{'='*80}")
    print(f"Environment: {report.environment}")
    print(f"Validation Time: {report.timestamp}")
    print(f"Overall Status: {status_colors.get(report.overall_status, '⚪')} {report.overall_status}")
    print(f"\\nSummary:")
    print(f"  Total Checks: {report.total_checks}")
    print(f"  ✅ Passed: {report.passed_checks}")
    print(f"  ⚠️  Warnings: {report.warning_checks}")
    print(f"  ❌ Failed: {report.failed_checks}")
    
    print(f"\\n{'Detailed Results':<30} {'Status':<10} {'Time':<8} Message")
    print("-" * 80)
    
    for result in report.results:
        status_icon = status_colors.get(result.status, '⚪')
        print(f"{result.check_name:<30} {status_icon} {result.status:<7} {result.execution_time:>6.2f}s {result.message}")
    
    if report.recommendations:
        print(f"\\n📋 RECOMMENDATIONS:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")
    
    print(f"\\n{'='*80}")
    
    if report.overall_status == "PASS":
        print("🎉 System is READY for production deployment!")
    elif report.overall_status == "WARNING":
        print("⚠️  System has warnings - review recommendations before deployment")
    else:
        print("❌ System is NOT ready for production - fix critical issues first")
    
    print(f"{'='*80}\\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Veeva Data Quality System production readiness")
    parser.add_argument("--environment", default="production", 
                       choices=["production", "staging", "development"],
                       help="Target environment to validate")
    parser.add_argument("--output", help="Output file for JSON report")
    parser.add_argument("--quiet", action="store_true", help="Only show summary")
    
    args = parser.parse_args()
    
    # Run validation
    validator = ProductionReadinessValidator(args.environment)
    report = validator.validate_all()
    
    # Print results
    if not args.quiet:
        print_report_summary(report)
    
    # Save report
    output_path = validator.save_report(report, args.output)
    
    # Exit with appropriate code
    if report.overall_status == "FAIL":
        sys.exit(1)
    elif report.overall_status == "WARNING":
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()