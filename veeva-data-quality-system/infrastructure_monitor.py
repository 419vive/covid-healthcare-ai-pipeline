#!/usr/bin/env python3
"""
Veeva Data Quality System - Infrastructure Monitoring & Maintenance
Primary Infrastructure Maintainer System

This system provides comprehensive monitoring, alerting, and automated maintenance
for the live production Veeva Data Quality System.
"""

import os
import sys
import json
import time
import logging
import sqlite3
import subprocess
import threading
import schedule
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import psutil
import docker


@dataclass
class SystemHealth:
    """System health metrics"""
    timestamp: str
    status: str
    cpu_percent: float
    memory_percent: float
    disk_free_gb: float
    container_count: int
    database_size_mb: float
    avg_query_time_ms: float
    total_records: int
    uptime_hours: float
    alerts: List[str]


class InfrastructureMonitor:
    """Primary Infrastructure Monitoring System"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.monitoring_db = os.path.join(data_dir, "infrastructure_monitoring.db")
        self.log_file = os.path.join("logs", "infrastructure_monitor.log")
        
        # Thresholds
        self.CPU_THRESHOLD = 80.0
        self.MEMORY_THRESHOLD = 85.0
        self.DISK_THRESHOLD_GB = 5.0
        self.QUERY_TIME_THRESHOLD_MS = 100.0
        self.ERROR_RATE_THRESHOLD = 5.0
        
        # Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            self.docker_client = None
            print(f"Warning: Docker client not available: {e}")
        
        self._setup_logging()
        self._setup_database()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        os.makedirs("logs", exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_database(self):
        """Setup monitoring database"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        with sqlite3.connect(self.monitoring_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_free_gb REAL,
                    container_count INTEGER,
                    database_size_mb REAL,
                    avg_query_time_ms REAL,
                    total_records INTEGER,
                    uptime_hours REAL,
                    alerts TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    execution_time_seconds REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    threshold REAL,
                    status TEXT
                )
            ''')
            
    def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health metrics"""
        alerts = []
        
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/')
        disk_free_gb = disk_usage.free / (1024**3)
        
        # Container health
        container_count = 0
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list()
                container_count = len([c for c in containers if c.status == 'running'])
            except Exception as e:
                alerts.append(f"Docker monitoring error: {e}")
                
        # Database metrics
        database_size_mb = 0
        avg_query_time_ms = 0.0
        total_records = 0
        
        try:
            # Check database size
            db_path = os.path.join(self.data_dir, "metrics.db")
            if os.path.exists(db_path):
                database_size_mb = os.path.getsize(db_path) / (1024 * 1024)
                
                # Test database performance
                start_time = time.time()
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                    table_count = cursor.fetchone()[0]
                    
                    # Count total records across all tables
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            total_records += cursor.fetchone()[0]
                        except:
                            continue
                            
                avg_query_time_ms = (time.time() - start_time) * 1000
                
        except Exception as e:
            alerts.append(f"Database monitoring error: {e}")
            
        # System uptime (approximate based on process)
        uptime_hours = 0
        try:
            boot_time = psutil.boot_time()
            uptime_hours = (time.time() - boot_time) / 3600
        except:
            pass
            
        # Check thresholds and generate alerts
        if cpu_percent > self.CPU_THRESHOLD:
            alerts.append(f"HIGH CPU: {cpu_percent:.1f}% > {self.CPU_THRESHOLD}%")
            
        if memory_percent > self.MEMORY_THRESHOLD:
            alerts.append(f"HIGH MEMORY: {memory_percent:.1f}% > {self.MEMORY_THRESHOLD}%")
            
        if disk_free_gb < self.DISK_THRESHOLD_GB:
            alerts.append(f"LOW DISK SPACE: {disk_free_gb:.1f}GB < {self.DISK_THRESHOLD_GB}GB")
            
        if avg_query_time_ms > self.QUERY_TIME_THRESHOLD_MS:
            alerts.append(f"SLOW QUERIES: {avg_query_time_ms:.1f}ms > {self.QUERY_TIME_THRESHOLD_MS}ms")
            
        # Determine overall status
        if any("HIGH" in alert or "LOW" in alert or "SLOW" in alert for alert in alerts):
            status = "WARNING"
        elif alerts:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
            
        return SystemHealth(
            timestamp=datetime.now().isoformat(),
            status=status,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_free_gb=disk_free_gb,
            container_count=container_count,
            database_size_mb=database_size_mb,
            avg_query_time_ms=avg_query_time_ms,
            total_records=total_records,
            uptime_hours=uptime_hours,
            alerts=alerts
        )
        
    def log_system_health(self, health: SystemHealth):
        """Log system health to database"""
        with sqlite3.connect(self.monitoring_db) as conn:
            conn.execute('''
                INSERT INTO system_health 
                (timestamp, status, cpu_percent, memory_percent, disk_free_gb, 
                 container_count, database_size_mb, avg_query_time_ms, 
                 total_records, uptime_hours, alerts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                health.timestamp, health.status, health.cpu_percent, 
                health.memory_percent, health.disk_free_gb, health.container_count,
                health.database_size_mb, health.avg_query_time_ms,
                health.total_records, health.uptime_hours, json.dumps(health.alerts)
            ))
            
    def run_database_maintenance(self) -> Dict:
        """Run automated database maintenance"""
        start_time = time.time()
        results = {"status": "SUCCESS", "actions": [], "errors": []}
        
        try:
            db_path = os.path.join(self.data_dir, "metrics.db")
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    # VACUUM to reclaim space
                    conn.execute("VACUUM")
                    results["actions"].append("Database VACUUM completed")
                    
                    # ANALYZE to update statistics
                    conn.execute("ANALYZE")
                    results["actions"].append("Database ANALYZE completed")
                    
                    # Clean up old monitoring data (keep 30 days)
                    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                    
            # Clean monitoring database
            with sqlite3.connect(self.monitoring_db) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM system_health WHERE timestamp < ?", (cutoff,))
                deleted = cursor.rowcount
                if deleted > 0:
                    results["actions"].append(f"Cleaned {deleted} old health records")
                    
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        execution_time = time.time() - start_time
        
        # Log maintenance action
        with sqlite3.connect(self.monitoring_db) as conn:
            conn.execute('''
                INSERT INTO maintenance_log 
                (timestamp, action, status, details, execution_time_seconds)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                "database_maintenance",
                results["status"],
                json.dumps(results),
                execution_time
            ))
            
        return results
        
    def cleanup_old_files(self) -> Dict:
        """Clean up old log files and temporary data"""
        start_time = time.time()
        results = {"status": "SUCCESS", "actions": [], "errors": []}
        
        try:
            # Clean old log files
            log_dir = "logs"
            if os.path.exists(log_dir):
                cutoff_time = time.time() - (30 * 24 * 3600)  # 30 days
                for filename in os.listdir(log_dir):
                    filepath = os.path.join(log_dir, filename)
                    if os.path.isfile(filepath) and filename.endswith('.log'):
                        if os.path.getmtime(filepath) < cutoff_time:
                            os.remove(filepath)
                            results["actions"].append(f"Removed old log file: {filename}")
                            
            # Clean cache directory
            cache_dir = "cache"
            if os.path.exists(cache_dir):
                for filename in os.listdir(cache_dir):
                    filepath = os.path.join(cache_dir, filename)
                    if os.path.isfile(filepath):
                        if os.path.getmtime(filepath) < cutoff_time:
                            os.remove(filepath)
                            results["actions"].append(f"Removed old cache file: {filename}")
                            
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        execution_time = time.time() - start_time
        
        # Log maintenance action
        with sqlite3.connect(self.monitoring_db) as conn:
            conn.execute('''
                INSERT INTO maintenance_log 
                (timestamp, action, status, details, execution_time_seconds)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                "file_cleanup",
                results["status"],
                json.dumps(results),
                execution_time
            ))
            
        return results
        
    def check_container_health(self) -> Dict:
        """Check health of all containers"""
        results = {"healthy": [], "unhealthy": [], "missing": []}
        
        expected_containers = [
            "veeva-data-quality-system",
            "veeva-prometheus", 
            "veeva-grafana"
        ]
        
        if not self.docker_client:
            return {"error": "Docker client not available"}
            
        try:
            containers = self.docker_client.containers.list(all=True)
            container_names = [c.name for c in containers]
            
            for expected in expected_containers:
                found = False
                for container in containers:
                    if container.name == expected:
                        found = True
                        if container.status == 'running':
                            # Check if container has health check
                            try:
                                health = container.attrs.get('State', {}).get('Health', {})
                                if health:
                                    status = health.get('Status', 'unknown')
                                    if status == 'healthy':
                                        results["healthy"].append(expected)
                                    else:
                                        results["unhealthy"].append(f"{expected}: {status}")
                                else:
                                    results["healthy"].append(f"{expected}: running (no healthcheck)")
                            except:
                                results["healthy"].append(f"{expected}: running")
                        else:
                            results["unhealthy"].append(f"{expected}: {container.status}")
                        break
                        
                if not found:
                    results["missing"].append(expected)
                    
        except Exception as e:
            results["error"] = str(e)
            
        return results
        
    def generate_health_report(self) -> str:
        """Generate comprehensive health report"""
        health = self.get_system_health()
        container_health = self.check_container_health()
        
        report = f"""
=== VEEVA DATA QUALITY SYSTEM - INFRASTRUCTURE HEALTH REPORT ===
Generated: {health.timestamp}
Status: {health.status}

SYSTEM METRICS:
- CPU Usage: {health.cpu_percent:.1f}%
- Memory Usage: {health.memory_percent:.1f}%
- Disk Free: {health.disk_free_gb:.1f} GB
- Database Size: {health.database_size_mb:.1f} MB
- Average Query Time: {health.avg_query_time_ms:.1f} ms
- Total Records: {health.total_records:,}
- System Uptime: {health.uptime_hours:.1f} hours

CONTAINER STATUS:
- Total Containers: {health.container_count}
- Healthy: {len(container_health.get('healthy', []))}
- Unhealthy: {len(container_health.get('unhealthy', []))}
- Missing: {len(container_health.get('missing', []))}

ALERTS ({len(health.alerts)}):
"""
        
        for alert in health.alerts:
            report += f"  - {alert}\n"
            
        if not health.alerts:
            report += "  - No active alerts\n"
            
        # Recent maintenance actions
        try:
            with sqlite3.connect(self.monitoring_db) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, action, status 
                    FROM maintenance_log 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                ''')
                maintenance_actions = cursor.fetchall()
                
            report += "\nRECENT MAINTENANCE:\n"
            for timestamp, action, status in maintenance_actions:
                report += f"  - {timestamp}: {action} ({status})\n"
                
        except:
            report += "\nRECENT MAINTENANCE: Unable to retrieve\n"
            
        return report
        
    def monitor_continuously(self):
        """Run continuous monitoring with scheduled tasks"""
        self.logger.info("Starting continuous infrastructure monitoring...")
        
        # Schedule health checks every 15 minutes
        schedule.every(15).minutes.do(self._health_check_job)
        
        # Schedule database maintenance weekly (Sunday at 2 AM)
        schedule.every().sunday.at("02:00").do(self._maintenance_job)
        
        # Schedule file cleanup daily at 3 AM
        schedule.every().day.at("03:00").do(self._cleanup_job)
        
        # Schedule health report generation daily at 8 AM
        schedule.every().day.at("08:00").do(self._health_report_job)
        
        # Run initial health check
        self._health_check_job()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Infrastructure monitoring stopped by user")
            
    def _health_check_job(self):
        """Scheduled health check job"""
        try:
            health = self.get_system_health()
            self.log_system_health(health)
            
            if health.status != "HEALTHY":
                self.logger.warning(f"System status: {health.status}")
                for alert in health.alerts:
                    self.logger.warning(f"Alert: {alert}")
            else:
                self.logger.info("System health check: HEALTHY")
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            
    def _maintenance_job(self):
        """Scheduled maintenance job"""
        try:
            self.logger.info("Starting automated maintenance...")
            db_result = self.run_database_maintenance()
            self.logger.info(f"Database maintenance: {db_result['status']}")
            
        except Exception as e:
            self.logger.error(f"Maintenance job failed: {e}")
            
    def _cleanup_job(self):
        """Scheduled cleanup job"""
        try:
            self.logger.info("Starting file cleanup...")
            cleanup_result = self.cleanup_old_files()
            self.logger.info(f"File cleanup: {cleanup_result['status']}")
            
        except Exception as e:
            self.logger.error(f"Cleanup job failed: {e}")
            
    def _health_report_job(self):
        """Scheduled health report job"""
        try:
            report = self.generate_health_report()
            
            # Save report to file
            report_file = f"reports/infrastructure_health_{datetime.now().strftime('%Y%m%d')}.txt"
            os.makedirs("reports", exist_ok=True)
            
            with open(report_file, 'w') as f:
                f.write(report)
                
            self.logger.info(f"Health report generated: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Health report generation failed: {e}")


def main():
    """Main function to start infrastructure monitoring"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Infrastructure Monitor')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once',
                        help='Run mode: once for single check, continuous for ongoing monitoring')
    parser.add_argument('--data-dir', default='data', help='Data directory path')
    
    args = parser.parse_args()
    
    monitor = InfrastructureMonitor(data_dir=args.data_dir)
    
    if args.mode == 'once':
        # Single health check and report
        health = monitor.get_system_health()
        monitor.log_system_health(health)
        
        print(monitor.generate_health_report())
        
        # Run maintenance if needed
        if health.status != "HEALTHY":
            print("\n=== RUNNING EMERGENCY MAINTENANCE ===")
            db_result = monitor.run_database_maintenance()
            cleanup_result = monitor.cleanup_old_files()
            
            print(f"Database maintenance: {db_result['status']}")
            print(f"File cleanup: {cleanup_result['status']}")
            
    else:
        # Continuous monitoring
        monitor.monitor_continuously()


if __name__ == "__main__":
    main()