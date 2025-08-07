#!/usr/bin/env python3
"""
Veeva Data Quality System - Production Deployment Monitor
Infrastructure monitoring and alerting during deployment
"""

import os
import sys
import time
import json
import logging
import subprocess
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
import psutil

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from python.utils.monitoring import SystemMonitor, SystemMetrics, DatabaseMetrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/veeva_deployment_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionMonitor:
    """Production deployment monitoring and health checking"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.compose_file = self.project_path / "deploy" / "docker-compose.yml"
        self.monitoring_enabled = True
        self.alert_thresholds = {
            'cpu_critical': 85.0,
            'cpu_warning': 70.0,
            'memory_critical': 90.0,
            'memory_warning': 80.0,
            'disk_critical': 95.0,
            'disk_warning': 85.0,
            'query_time_critical': 1000.0,  # ms
            'query_time_warning': 500.0,    # ms
            'error_rate_critical': 5.0,     # %
            'error_rate_warning': 1.0       # %
        }
        self.deployment_start_time = datetime.now()
        self.metrics_history = []
        
        # Initialize system monitor
        db_path = self.project_path / "data" / "veeva_healthcare_data.db"
        self.system_monitor = SystemMonitor(str(db_path))
        
    def check_docker_status(self) -> Dict[str, Any]:
        """Check Docker daemon and container status"""
        status = {
            'docker_daemon': False,
            'containers': {},
            'images': {},
            'networks': {},
            'volumes': {}
        }
        
        try:
            # Check Docker daemon
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=10)
            status['docker_daemon'] = result.returncode == 0
            
            if not status['docker_daemon']:
                logger.error("Docker daemon is not running")
                return status
            
            # Check containers
            result = subprocess.run(['docker', 'ps', '-a', '--format', 'json'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        container = json.loads(line)
                        status['containers'][container['Names']] = {
                            'status': container['State'],
                            'health': container.get('Status', 'unknown'),
                            'image': container['Image'],
                            'created': container['CreatedAt']
                        }
            
            # Check Docker Compose services
            if self.compose_file.exists():
                result = subprocess.run(['docker-compose', '-f', str(self.compose_file), 'ps', '--format', 'json'],
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            service = json.loads(line)
                            service_name = service['Service']
                            status['containers'][service_name] = {
                                'status': service['State'],
                                'health': service.get('Health', 'unknown'),
                                'ports': service.get('Publishers', [])
                            }
            
        except subprocess.TimeoutExpired:
            logger.error("Docker command timed out")
        except Exception as e:
            logger.error(f"Failed to check Docker status: {e}")
        
        return status
    
    def check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        db_status = {
            'connected': False,
            'query_performance_ms': 0,
            'record_count': 0,
            'database_size_mb': 0,
            'integrity_check': False
        }
        
        try:
            db_path = self.project_path / "data" / "veeva_healthcare_data.db"
            
            if not db_path.exists():
                logger.warning(f"Database file not found: {db_path}")
                return db_status
            
            # Test connection and performance
            start_time = time.time()
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Test query
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                query_time = (time.time() - start_time) * 1000
                db_status['query_performance_ms'] = round(query_time, 2)
                db_status['connected'] = True
                
                # Get record count (assuming healthcare_data table exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM healthcare_data")
                    db_status['record_count'] = cursor.fetchone()[0]
                except sqlite3.Error:
                    logger.warning("healthcare_data table not found")
                
                # Database size
                db_status['database_size_mb'] = round(db_path.stat().st_size / (1024*1024), 2)
                
                # Quick integrity check
                cursor.execute("PRAGMA integrity_check(1)")
                integrity_result = cursor.fetchone()[0]
                db_status['integrity_check'] = integrity_result.lower() == 'ok'
                
                logger.info(f"Database connectivity OK - Query time: {query_time:.2f}ms, Records: {db_status['record_count']:,}")
                
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            db_status['error'] = str(e)
        
        return db_status
    
    def check_application_endpoints(self) -> Dict[str, Any]:
        """Check application health endpoints and API responsiveness"""
        endpoints = {
            'health_check': {'url': 'http://localhost:8001/health', 'timeout': 10},
            'metrics': {'url': 'http://localhost:8002/metrics', 'timeout': 15},
            'api_status': {'url': 'http://localhost:8000/status', 'timeout': 20}
        }
        
        endpoint_status = {}
        
        for name, config in endpoints.items():
            status = {
                'available': False,
                'response_time_ms': 0,
                'status_code': 0,
                'error': None
            }
            
            try:
                start_time = time.time()
                response = requests.get(config['url'], timeout=config['timeout'])
                response_time = (time.time() - start_time) * 1000
                
                status['available'] = response.status_code == 200
                status['response_time_ms'] = round(response_time, 2)
                status['status_code'] = response.status_code
                
                if response.status_code == 200:
                    logger.info(f"Endpoint {name} OK - Response time: {response_time:.2f}ms")
                else:
                    logger.warning(f"Endpoint {name} returned {response.status_code}")
                    
            except requests.RequestException as e:
                status['error'] = str(e)
                logger.warning(f"Endpoint {name} unavailable: {e}")
            except Exception as e:
                status['error'] = str(e)
                logger.error(f"Failed to check endpoint {name}: {e}")
            
            endpoint_status[name] = status
        
        return endpoint_status
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Monitor system resource utilization"""
        try:
            # Collect system metrics
            system_metrics = self.system_monitor.collect_system_metrics()
            database_metrics = self.system_monitor.collect_database_metrics()
            
            # Get additional process information
            process_info = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    if 'python' in proc.info['name'].lower() or 'docker' in proc.info['name'].lower():
                        process_info.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_percent': proc.info['memory_percent']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            resource_status = {
                'system_metrics': system_metrics.__dict__ if system_metrics else {},
                'database_metrics': database_metrics.__dict__ if database_metrics else {},
                'relevant_processes': process_info,
                'alerts': []
            }
            
            # Check thresholds and generate alerts
            if system_metrics:
                if system_metrics.cpu_percent >= self.alert_thresholds['cpu_critical']:
                    resource_status['alerts'].append({
                        'level': 'CRITICAL',
                        'message': f"CPU usage critical: {system_metrics.cpu_percent:.1f}%"
                    })
                elif system_metrics.cpu_percent >= self.alert_thresholds['cpu_warning']:
                    resource_status['alerts'].append({
                        'level': 'WARNING',
                        'message': f"CPU usage high: {system_metrics.cpu_percent:.1f}%"
                    })
                
                if system_metrics.memory_percent >= self.alert_thresholds['memory_critical']:
                    resource_status['alerts'].append({
                        'level': 'CRITICAL',
                        'message': f"Memory usage critical: {system_metrics.memory_percent:.1f}%"
                    })
                elif system_metrics.memory_percent >= self.alert_thresholds['memory_warning']:
                    resource_status['alerts'].append({
                        'level': 'WARNING',
                        'message': f"Memory usage high: {system_metrics.memory_percent:.1f}%"
                    })
                
                if system_metrics.disk_usage_percent >= self.alert_thresholds['disk_critical']:
                    resource_status['alerts'].append({
                        'level': 'CRITICAL',
                        'message': f"Disk usage critical: {system_metrics.disk_usage_percent:.1f}% (Free: {system_metrics.disk_free_gb:.1f}GB)"
                    })
                elif system_metrics.disk_usage_percent >= self.alert_thresholds['disk_warning']:
                    resource_status['alerts'].append({
                        'level': 'WARNING',
                        'message': f"Disk usage high: {system_metrics.disk_usage_percent:.1f}% (Free: {system_metrics.disk_free_gb:.1f}GB)"
                    })
            
            if database_metrics:
                if database_metrics.query_performance_ms >= self.alert_thresholds['query_time_critical']:
                    resource_status['alerts'].append({
                        'level': 'CRITICAL',
                        'message': f"Database query performance critical: {database_metrics.query_performance_ms:.1f}ms"
                    })
                elif database_metrics.query_performance_ms >= self.alert_thresholds['query_time_warning']:
                    resource_status['alerts'].append({
                        'level': 'WARNING',
                        'message': f"Database query performance slow: {database_metrics.query_performance_ms:.1f}ms"
                    })
            
            return resource_status
            
        except Exception as e:
            logger.error(f"Failed to check system resources: {e}")
            return {'error': str(e), 'alerts': []}
    
    def check_security_compliance(self) -> Dict[str, Any]:
        """Check security and compliance measures"""
        security_status = {
            'container_security': False,
            'file_permissions': False,
            'ssl_certificates': False,
            'backup_integrity': False,
            'access_controls': False,
            'issues': []
        }
        
        try:
            # Check file permissions on sensitive files
            sensitive_files = [
                self.project_path / "data",
                self.project_path / "deploy" / ".env.production.local",
                self.project_path / "python" / "config"
            ]
            
            permission_issues = []
            for file_path in sensitive_files:
                if file_path.exists():
                    stat_info = file_path.stat()
                    mode = oct(stat_info.st_mode)[-3:]
                    if mode > '755':  # Too permissive
                        permission_issues.append(f"{file_path}: {mode}")
            
            if not permission_issues:
                security_status['file_permissions'] = True
            else:
                security_status['issues'].extend(permission_issues)
            
            # Check for backup files
            backup_dir = self.project_path / "deploy" / "backups"
            if backup_dir.exists():
                backup_files = list(backup_dir.glob("*.sql"))
                security_status['backup_integrity'] = len(backup_files) > 0
                if len(backup_files) == 0:
                    security_status['issues'].append("No database backups found")
            
            # Basic container security check (if Docker is running)
            try:
                result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    containers = result.stdout.strip().split('\n')
                    security_status['container_security'] = len(containers) > 0
            except:
                pass
            
            logger.info(f"Security compliance check completed - Issues: {len(security_status['issues'])}")
            
        except Exception as e:
            logger.error(f"Security compliance check failed: {e}")
            security_status['issues'].append(f"Security check error: {e}")
        
        return security_status
    
    def generate_deployment_report(self, monitoring_results: Dict[str, Any]) -> str:
        """Generate comprehensive deployment monitoring report"""
        
        deployment_duration = datetime.now() - self.deployment_start_time
        
        report = f"""
# Veeva Data Quality System - Production Deployment Monitor Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Deployment Duration: {str(deployment_duration).split('.')[0]}

## Overall System Status
"""
        
        # Determine overall status
        critical_issues = 0
        warning_issues = 0
        
        for category, results in monitoring_results.items():
            if isinstance(results, dict):
                alerts = results.get('alerts', [])
                for alert in alerts:
                    if alert.get('level') == 'CRITICAL':
                        critical_issues += 1
                    elif alert.get('level') == 'WARNING':
                        warning_issues += 1
        
        if critical_issues > 0:
            overall_status = "🔴 CRITICAL"
        elif warning_issues > 0:
            overall_status = "🟡 WARNING"
        else:
            overall_status = "🟢 HEALTHY"
        
        report += f"**Status: {overall_status}**\n"
        report += f"Critical Issues: {critical_issues}\n"
        report += f"Warnings: {warning_issues}\n\n"
        
        # Docker Status
        docker_status = monitoring_results.get('docker', {})
        report += "## Container Infrastructure\n"
        report += f"Docker Daemon: {'🟢 Running' if docker_status.get('docker_daemon') else '🔴 Not Running'}\n"
        
        containers = docker_status.get('containers', {})
        if containers:
            report += "### Container Status:\n"
            for name, status in containers.items():
                state_icon = "🟢" if status['status'] == 'running' else "🔴"
                report += f"- {name}: {state_icon} {status['status']} ({status.get('health', 'unknown')})\n"
        
        # Database Status
        db_status = monitoring_results.get('database', {})
        report += "\n## Database Infrastructure\n"
        if db_status.get('connected'):
            report += f"🟢 Connected - Query Performance: {db_status.get('query_performance_ms', 0):.2f}ms\n"
            report += f"Records: {db_status.get('record_count', 0):,}\n"
            report += f"Database Size: {db_status.get('database_size_mb', 0):.1f}MB\n"
            report += f"Integrity Check: {'🟢 OK' if db_status.get('integrity_check') else '🔴 Failed'}\n"
        else:
            report += "🔴 Database Connection Failed\n"
            if 'error' in db_status:
                report += f"Error: {db_status['error']}\n"
        
        # Application Endpoints
        endpoints = monitoring_results.get('endpoints', {})
        report += "\n## Application Endpoints\n"
        for name, status in endpoints.items():
            if status.get('available'):
                report += f"🟢 {name}: {status['response_time_ms']:.2f}ms\n"
            else:
                report += f"🔴 {name}: Unavailable\n"
                if status.get('error'):
                    report += f"   Error: {status['error']}\n"
        
        # System Resources
        resources = monitoring_results.get('resources', {})
        report += "\n## System Resources\n"
        
        system_metrics = resources.get('system_metrics', {})
        if system_metrics:
            report += f"CPU Usage: {system_metrics.get('cpu_percent', 0):.1f}%\n"
            report += f"Memory Usage: {system_metrics.get('memory_percent', 0):.1f}% ({system_metrics.get('memory_used_gb', 0):.1f}GB used)\n"
            report += f"Disk Usage: {system_metrics.get('disk_usage_percent', 0):.1f}% ({system_metrics.get('disk_free_gb', 0):.1f}GB free)\n"
        
        # Resource Alerts
        alerts = resources.get('alerts', [])
        if alerts:
            report += "\n### Resource Alerts:\n"
            for alert in alerts:
                icon = "🔴" if alert['level'] == 'CRITICAL' else "🟡"
                report += f"{icon} {alert['level']}: {alert['message']}\n"
        
        # Security Status
        security = monitoring_results.get('security', {})
        report += "\n## Security & Compliance\n"
        report += f"File Permissions: {'🟢 Secure' if security.get('file_permissions') else '🟡 Issues Found'}\n"
        report += f"Container Security: {'🟢 OK' if security.get('container_security') else '🔴 Issues'}\n"
        report += f"Backup Integrity: {'🟢 OK' if security.get('backup_integrity') else '🟡 No Backups'}\n"
        
        if security.get('issues'):
            report += "\n### Security Issues:\n"
            for issue in security['issues']:
                report += f"⚠️ {issue}\n"
        
        # Performance Targets
        report += "\n## Performance Target Status\n"
        target_query_time = 0.149  # Target: 0.149s average from requirements
        current_query_time = db_status.get('query_performance_ms', 0) / 1000  # Convert to seconds
        
        if current_query_time <= target_query_time:
            report += f"🟢 Query Performance: {current_query_time:.3f}s (Target: {target_query_time:.3f}s)\n"
        else:
            report += f"🔴 Query Performance: {current_query_time:.3f}s (Target: {target_query_time:.3f}s)\n"
        
        report += f"Healthcare Records: {db_status.get('record_count', 0):,} (Target: 125,531)\n"
        
        # Recommendations
        report += "\n## Recommendations\n"
        recommendations = []
        
        if critical_issues > 0:
            recommendations.append("🔴 Address critical issues immediately before proceeding with deployment")
        
        if warning_issues > 0:
            recommendations.append("🟡 Review and resolve warning conditions")
        
        if current_query_time > target_query_time:
            recommendations.append("⚡ Optimize database query performance")
        
        if not security.get('backup_integrity'):
            recommendations.append("💾 Set up automated database backups")
        
        if system_metrics.get('memory_percent', 0) > 80:
            recommendations.append("📈 Consider increasing memory allocation")
        
        if not recommendations:
            recommendations.append("✅ System is ready for production deployment")
        
        for rec in recommendations:
            report += f"{rec}\n"
        
        return report
    
    def run_continuous_monitoring(self, duration_minutes: int = 60, interval_seconds: int = 30):
        """Run continuous monitoring during deployment"""
        logger.info(f"Starting continuous monitoring for {duration_minutes} minutes")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        iteration = 0
        
        while datetime.now() < end_time:
            iteration += 1
            logger.info(f"Monitoring iteration {iteration}")
            
            try:
                # Collect all monitoring data
                monitoring_results = {}
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        'docker': executor.submit(self.check_docker_status),
                        'database': executor.submit(self.check_database_connectivity),
                        'endpoints': executor.submit(self.check_application_endpoints),
                        'resources': executor.submit(self.check_system_resources),
                        'security': executor.submit(self.check_security_compliance)
                    }
                    
                    for key, future in futures.items():
                        try:
                            monitoring_results[key] = future.result(timeout=60)
                        except Exception as e:
                            logger.error(f"Failed to collect {key} metrics: {e}")
                            monitoring_results[key] = {'error': str(e)}
                
                # Store metrics
                system_metrics = monitoring_results.get('resources', {}).get('system_metrics')
                database_metrics = monitoring_results.get('resources', {}).get('database_metrics')
                
                if system_metrics or database_metrics:
                    self.system_monitor.store_metrics(
                        system_metrics=SystemMetrics(**system_metrics) if system_metrics else None,
                        database_metrics=DatabaseMetrics(**database_metrics) if database_metrics else None
                    )
                
                # Generate and save report
                report = self.generate_deployment_report(monitoring_results)
                report_file = f"/tmp/veeva_deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                
                with open(report_file, 'w') as f:
                    f.write(report)
                
                logger.info(f"Monitoring report saved: {report_file}")
                
                # Check for critical issues
                critical_alerts = []
                for category, results in monitoring_results.items():
                    if isinstance(results, dict):
                        alerts = results.get('alerts', [])
                        critical_alerts.extend([alert for alert in alerts if alert.get('level') == 'CRITICAL'])
                
                if critical_alerts:
                    logger.critical("CRITICAL ISSUES DETECTED:")
                    for alert in critical_alerts:
                        logger.critical(f"  {alert['message']}")
                
                # Print summary to console
                print(f"\n{'='*60}")
                print(f"MONITORING SUMMARY - Iteration {iteration}")
                print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*60}")
                
                # Print key metrics
                resources = monitoring_results.get('resources', {})
                system_metrics = resources.get('system_metrics', {})
                if system_metrics:
                    print(f"CPU: {system_metrics.get('cpu_percent', 0):.1f}% | "
                          f"Memory: {system_metrics.get('memory_percent', 0):.1f}% | "
                          f"Disk Free: {system_metrics.get('disk_free_gb', 0):.1f}GB")
                
                db_status = monitoring_results.get('database', {})
                if db_status.get('connected'):
                    print(f"DB: Connected | Query: {db_status.get('query_performance_ms', 0):.2f}ms | "
                          f"Records: {db_status.get('record_count', 0):,}")
                else:
                    print("DB: ❌ Disconnected")
                
                # Print alerts
                all_alerts = []
                for category, results in monitoring_results.items():
                    if isinstance(results, dict):
                        all_alerts.extend(results.get('alerts', []))
                
                if all_alerts:
                    print(f"\n⚠️ ALERTS ({len(all_alerts)}):")
                    for alert in all_alerts:
                        icon = "🔴" if alert['level'] == 'CRITICAL' else "🟡"
                        print(f"  {icon} {alert['message']}")
                else:
                    print("✅ No alerts")
                
                print(f"{'='*60}\n")
                
            except Exception as e:
                logger.error(f"Monitoring iteration {iteration} failed: {e}")
            
            # Wait for next iteration
            if datetime.now() < end_time:
                time.sleep(interval_seconds)
        
        logger.info("Continuous monitoring completed")
        
        # Generate final comprehensive report
        final_report_file = f"/tmp/veeva_deployment_final_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        try:
            monitoring_results = {
                'docker': self.check_docker_status(),
                'database': self.check_database_connectivity(),
                'endpoints': self.check_application_endpoints(),
                'resources': self.check_system_resources(),
                'security': self.check_security_compliance()
            }
            
            final_report = self.generate_deployment_report(monitoring_results)
            with open(final_report_file, 'w') as f:
                f.write(final_report)
            
            logger.info(f"Final deployment report saved: {final_report_file}")
            print(f"\n📊 Final report saved: {final_report_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate final report: {e}")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Veeva Data Quality System - Production Deployment Monitor")
    parser.add_argument("--duration", type=int, default=60, help="Monitoring duration in minutes (default: 60)")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds (default: 30)")
    parser.add_argument("--project-path", type=str, 
                       default="/Users/jerrylaivivemachi/DS PROJECT/project5/veeva-data-quality-system",
                       help="Path to the project directory")
    parser.add_argument("--one-shot", action="store_true", help="Run single monitoring check instead of continuous")
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               Veeva Data Quality System                       ║
║               Production Deployment Monitor                   ║
╚══════════════════════════════════════════════════════════════╝

Project Path: {args.project_path}
Monitoring Duration: {args.duration} minutes
Check Interval: {args.interval} seconds
Mode: {'One-shot' if args.one_shot else 'Continuous'}

Starting infrastructure monitoring...
""")
    
    try:
        monitor = ProductionMonitor(args.project_path)
        
        if args.one_shot:
            # Single monitoring check
            logger.info("Running single monitoring check")
            
            monitoring_results = {
                'docker': monitor.check_docker_status(),
                'database': monitor.check_database_connectivity(),
                'endpoints': monitor.check_application_endpoints(),
                'resources': monitor.check_system_resources(),
                'security': monitor.check_security_compliance()
            }
            
            report = monitor.generate_deployment_report(monitoring_results)
            report_file = f"/tmp/veeva_monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            
            with open(report_file, 'w') as f:
                f.write(report)
            
            print(f"\n📊 Monitoring report generated: {report_file}")
            print("\n" + report)
            
        else:
            # Continuous monitoring
            monitor.run_continuous_monitoring(
                duration_minutes=args.duration,
                interval_seconds=args.interval
            )
        
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        print("\n⏹️ Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        print(f"\n❌ Monitoring failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()