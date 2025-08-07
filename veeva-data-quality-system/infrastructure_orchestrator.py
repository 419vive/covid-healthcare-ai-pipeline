#!/usr/bin/env python3
"""
Veeva Data Quality System - Infrastructure Orchestrator
Master control system for comprehensive infrastructure management

This is the primary infrastructure control system that coordinates monitoring,
maintenance, alerting, and performance optimization for the production system.
"""

import os
import sys
import json
import time
import logging
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

# Import our infrastructure modules
from infrastructure_monitor import InfrastructureMonitor, SystemHealth
from automated_maintenance import AutomatedMaintenance
from alerting_system import AlertingSystem, Alert


class InfrastructureOrchestrator:
    """Master infrastructure management orchestrator"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.orchestrator_db = os.path.join(data_dir, "orchestrator.db")
        self.log_file = os.path.join("logs", "infrastructure_orchestrator.log")
        
        # Initialize subsystems
        self.monitor = InfrastructureMonitor(data_dir)
        self.maintenance = AutomatedMaintenance(data_dir)
        self.alerting = AlertingSystem()
        
        # Orchestrator state
        self.is_running = False
        self.last_health_check = None
        self.last_maintenance = None
        self.system_status = "UNKNOWN"
        
        # Performance baselines
        self.performance_baselines = {
            "query_time_ms": 10.0,
            "cpu_percent": 20.0,
            "memory_percent": 40.0,
            "response_time_ms": 100.0
        }
        
        self._setup_logging()
        self._setup_database()
        self._load_system_state()
        
    def _setup_logging(self):
        """Setup orchestrator logging"""
        os.makedirs("logs", exist_ok=True)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - [ORCHESTRATOR] - %(levelname)s - %(message)s'
        )
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Setup logger
        self.logger = logging.getLogger("orchestrator")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
    def _setup_database(self):
        """Setup orchestrator tracking database"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        with sqlite3.connect(self.orchestrator_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS orchestrator_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_baselines (
                    metric_name TEXT PRIMARY KEY,
                    baseline_value REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS orchestrator_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
    def _load_system_state(self):
        """Load previous system state"""
        try:
            with sqlite3.connect(self.orchestrator_db) as conn:
                cursor = conn.cursor()
                
                # Load last health check time
                cursor.execute("SELECT value FROM orchestrator_state WHERE key = 'last_health_check'")
                result = cursor.fetchone()
                if result:
                    self.last_health_check = result[0]
                    
                # Load last maintenance time
                cursor.execute("SELECT value FROM orchestrator_state WHERE key = 'last_maintenance'")
                result = cursor.fetchone()
                if result:
                    self.last_maintenance = result[0]
                    
                # Load system status
                cursor.execute("SELECT value FROM orchestrator_state WHERE key = 'system_status'")
                result = cursor.fetchone()
                if result:
                    self.system_status = result[0]
                    
        except Exception as e:
            self.logger.warning(f"Could not load system state: {e}")
            
    def _save_system_state(self):
        """Save current system state"""
        try:
            with sqlite3.connect(self.orchestrator_db) as conn:
                state_data = [
                    ("last_health_check", self.last_health_check or ""),
                    ("last_maintenance", self.last_maintenance or ""),
                    ("system_status", self.system_status),
                    ("orchestrator_version", "1.0.0"),
                    ("data_directory", self.data_dir)
                ]
                
                conn.executemany('''
                    INSERT OR REPLACE INTO orchestrator_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', [(k, v, datetime.now().isoformat()) for k, v in state_data])
                
        except Exception as e:
            self.logger.error(f"Could not save system state: {e}")
            
    def _log_event(self, event_type: str, component: str, message: str, 
                   severity: str = "INFO", details: Dict = None):
        """Log orchestrator event"""
        try:
            with sqlite3.connect(self.orchestrator_db) as conn:
                conn.execute('''
                    INSERT INTO orchestrator_events 
                    (event_type, component, message, severity, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    event_type, component, message, severity,
                    json.dumps(details) if details else None
                ))
                
        except Exception as e:
            self.logger.error(f"Could not log event: {e}")
            
    def comprehensive_health_assessment(self) -> Dict:
        """Run comprehensive health assessment of entire system"""
        self.logger.info("Starting comprehensive health assessment...")
        
        assessment_start = time.time()
        assessment = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "HEALTHY",
            "components": {},
            "alerts": [],
            "recommendations": [],
            "performance_metrics": {},
            "assessment_duration_seconds": 0
        }
        
        # 1. System Health Check
        try:
            health = self.monitor.get_system_health()
            assessment["components"]["system_health"] = {
                "status": health.status,
                "cpu_percent": health.cpu_percent,
                "memory_percent": health.memory_percent,
                "disk_free_gb": health.disk_free_gb,
                "alerts": health.alerts
            }
            
            # Add to performance metrics
            assessment["performance_metrics"].update({
                "cpu_percent": health.cpu_percent,
                "memory_percent": health.memory_percent,
                "avg_query_time_ms": health.avg_query_time_ms,
                "total_records": health.total_records
            })
            
            # Process alerts from health check
            if health.alerts:
                assessment["alerts"].extend(health.alerts)
                if health.status != "HEALTHY":
                    assessment["overall_status"] = "DEGRADED"
                    
        except Exception as e:
            assessment["components"]["system_health"] = {"status": "ERROR", "error": str(e)}
            assessment["overall_status"] = "CRITICAL"
            
        # 2. Container Health Check
        try:
            container_health = self.monitor.check_container_health()
            assessment["components"]["containers"] = container_health
            
            if container_health.get("unhealthy") or container_health.get("missing"):
                assessment["overall_status"] = "DEGRADED"
                assessment["alerts"].append("Container issues detected")
                
        except Exception as e:
            assessment["components"]["containers"] = {"status": "ERROR", "error": str(e)}
            
        # 3. Database Performance Assessment
        try:
            db_metrics = self._assess_database_performance()
            assessment["components"]["database"] = db_metrics
            
            if db_metrics.get("slow_queries", 0) > 0:
                assessment["recommendations"].append("Database optimization recommended")
                
        except Exception as e:
            assessment["components"]["database"] = {"status": "ERROR", "error": str(e)}
            
        # 4. Alert System Status
        try:
            alert_summary = self.alerting.get_alert_summary()
            assessment["components"]["alerts"] = alert_summary
            
            if alert_summary["total_active"] > 0:
                assessment["overall_status"] = "DEGRADED"
                assessment["alerts"].append(f"{alert_summary['total_active']} active alerts")
                
        except Exception as e:
            assessment["components"]["alerts"] = {"status": "ERROR", "error": str(e)}
            
        # 5. Performance vs Baselines
        performance_issues = self._check_performance_baselines(assessment["performance_metrics"])
        if performance_issues:
            assessment["alerts"].extend(performance_issues)
            assessment["recommendations"].append("Performance optimization needed")
            
        # 6. Capacity Planning Assessment
        try:
            capacity_analysis = self.maintenance.capacity_planning()
            assessment["components"]["capacity"] = capacity_analysis
            
            if capacity_analysis.get("recommendations"):
                assessment["recommendations"].extend(capacity_analysis["recommendations"])
                
        except Exception as e:
            assessment["components"]["capacity"] = {"status": "ERROR", "error": str(e)}
            
        # Determine final status
        if assessment["overall_status"] == "HEALTHY" and assessment["alerts"]:
            assessment["overall_status"] = "WARNING"
            
        assessment["assessment_duration_seconds"] = time.time() - assessment_start
        
        # Update system status
        self.system_status = assessment["overall_status"]
        self.last_health_check = assessment["timestamp"]
        self._save_system_state()
        
        # Log the assessment
        self._log_event(
            "HEALTH_ASSESSMENT", 
            "orchestrator", 
            f"Health assessment completed: {assessment['overall_status']}", 
            "INFO" if assessment["overall_status"] == "HEALTHY" else "WARNING",
            {"duration": assessment["assessment_duration_seconds"]}
        )
        
        self.logger.info(f"Health assessment completed in {assessment['assessment_duration_seconds']:.2f}s: {assessment['overall_status']}")
        
        return assessment
        
    def _assess_database_performance(self) -> Dict:
        """Assess database performance"""
        metrics = {
            "status": "HEALTHY",
            "size_mb": 0,
            "query_performance_ms": 0,
            "slow_queries": 0,
            "recommendations": []
        }
        
        try:
            db_path = os.path.join(self.data_dir, "metrics.db")
            if os.path.exists(db_path):
                # Get database size
                metrics["size_mb"] = os.path.getsize(db_path) / (1024 * 1024)
                
                # Test query performance
                start_time = time.time()
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                    cursor.fetchone()
                    
                query_time_ms = (time.time() - start_time) * 1000
                metrics["query_performance_ms"] = query_time_ms
                
                # Check against baseline
                if query_time_ms > self.performance_baselines["query_time_ms"] * 2:
                    metrics["slow_queries"] = 1
                    metrics["status"] = "DEGRADED"
                    metrics["recommendations"].append("Database optimization needed")
                    
        except Exception as e:
            metrics["status"] = "ERROR"
            metrics["error"] = str(e)
            
        return metrics
        
    def _check_performance_baselines(self, current_metrics: Dict) -> List[str]:
        """Check current performance against baselines"""
        issues = []
        
        for metric, baseline in self.performance_baselines.items():
            if metric in current_metrics:
                current = current_metrics[metric]
                
                # Check if performance has degraded significantly
                if metric.endswith("_ms"):  # Lower is better for time metrics
                    if current > baseline * 2:
                        issues.append(f"Performance degraded: {metric} = {current:.1f}ms (baseline: {baseline:.1f}ms)")
                else:  # Lower is better for resource usage
                    if current > baseline * 1.5:
                        issues.append(f"Resource usage high: {metric} = {current:.1f}% (baseline: {baseline:.1f}%)")
                        
        return issues
        
    def automated_optimization(self) -> Dict:
        """Run automated system optimization"""
        self.logger.info("Starting automated optimization...")
        
        optimization_start = time.time()
        optimization_results = {
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS",
            "optimizations": [],
            "errors": [],
            "performance_improvement": {}
        }
        
        try:
            # Run full maintenance suite
            maintenance_results = self.maintenance.run_full_maintenance()
            
            optimization_results["optimizations"].append({
                "component": "maintenance",
                "results": maintenance_results
            })
            
            # Check if maintenance improved performance
            post_maintenance_health = self.monitor.get_system_health()
            
            # Log optimization completion
            self.last_maintenance = optimization_results["timestamp"]
            self._save_system_state()
            
            self._log_event(
                "OPTIMIZATION",
                "orchestrator", 
                "Automated optimization completed",
                "INFO",
                {"tasks_completed": maintenance_results.get("tasks_completed", 0)}
            )
            
        except Exception as e:
            optimization_results["status"] = "ERROR"
            optimization_results["errors"].append(str(e))
            self.logger.error(f"Optimization failed: {e}")
            
        optimization_results["duration_seconds"] = time.time() - optimization_start
        
        return optimization_results
        
    def emergency_response(self, severity: str = "HIGH") -> Dict:
        """Execute emergency response procedures"""
        self.logger.critical(f"Executing emergency response - Severity: {severity}")
        
        response = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "actions_taken": [],
            "status": "SUCCESS"
        }
        
        try:
            # 1. Immediate health assessment
            health = self.monitor.get_system_health()
            response["actions_taken"].append(f"Health check: {health.status}")
            
            # 2. Emergency maintenance if needed
            if health.status in ["WARNING", "CRITICAL"]:
                maintenance_result = self.maintenance.run_full_maintenance()
                response["actions_taken"].append(f"Emergency maintenance: {maintenance_result['overall_status']}")
                
            # 3. Container health check and restart if needed
            container_health = self.monitor.check_container_health()
            if container_health.get("unhealthy"):
                response["actions_taken"].append("Container issues detected - manual intervention required")
                
            # 4. Generate emergency report
            emergency_report = self._generate_emergency_report(health, response)
            response["actions_taken"].append(f"Emergency report generated")
            
            self._log_event(
                "EMERGENCY_RESPONSE",
                "orchestrator",
                f"Emergency response executed - {severity}",
                "CRITICAL",
                {"actions_count": len(response["actions_taken"])}
            )
            
        except Exception as e:
            response["status"] = "ERROR"
            response["error"] = str(e)
            self.logger.error(f"Emergency response failed: {e}")
            
        return response
        
    def _generate_emergency_report(self, health: SystemHealth, response: Dict) -> str:
        """Generate emergency response report"""
        report = f"""
=== VEEVA SYSTEM EMERGENCY RESPONSE REPORT ===
Timestamp: {response['timestamp']}
Severity: {response['severity']}

SYSTEM STATUS:
- Overall Status: {health.status}
- CPU Usage: {health.cpu_percent:.1f}%
- Memory Usage: {health.memory_percent:.1f}%
- Disk Free: {health.disk_free_gb:.1f}GB
- Query Time: {health.avg_query_time_ms:.1f}ms

ACTIVE ALERTS ({len(health.alerts)}):
"""
        for alert in health.alerts:
            report += f"- {alert}\n"
            
        report += f"\nEMERGENCY ACTIONS TAKEN ({len(response['actions_taken'])}):\n"
        for action in response["actions_taken"]:
            report += f"- {action}\n"
            
        # Save emergency report
        os.makedirs("reports", exist_ok=True)
        report_file = f"reports/emergency_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report)
            
        self.logger.info(f"Emergency report saved: {report_file}")
        return report_file
        
    def start_continuous_monitoring(self):
        """Start continuous monitoring and maintenance"""
        self.logger.info("Starting continuous infrastructure monitoring...")
        self.is_running = True
        
        # Schedule regular tasks
        schedule.every(15).minutes.do(self._scheduled_health_check)
        schedule.every(1).hours.do(self._scheduled_performance_check)
        schedule.every().day.at("02:00").do(self._scheduled_maintenance)
        schedule.every().day.at("08:00").do(self._scheduled_daily_report)
        
        # Run initial assessment
        initial_assessment = self.comprehensive_health_assessment()
        self.logger.info(f"Initial system status: {initial_assessment['overall_status']}")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Stopping continuous monitoring...")
            self.is_running = False
            
    def _scheduled_health_check(self):
        """Scheduled health check task"""
        try:
            assessment = self.comprehensive_health_assessment()
            
            # Process alerts
            if assessment["alerts"]:
                for alert_msg in assessment["alerts"]:
                    # Create alert object and process
                    alert_id = f"HEALTH_{int(time.time())}"
                    alert = Alert(
                        id=alert_id,
                        severity="HIGH" if assessment["overall_status"] == "CRITICAL" else "MEDIUM",
                        component="system",
                        message=alert_msg,
                        details=assessment["performance_metrics"],
                        timestamp=datetime.now().isoformat(),
                        status="ACTIVE",
                        escalation_level=0,
                        last_notified=None
                    )
                    
                    self.alerting.process_alert(alert)
                    
        except Exception as e:
            self.logger.error(f"Scheduled health check failed: {e}")
            
    def _scheduled_performance_check(self):
        """Scheduled performance optimization check"""
        try:
            health = self.monitor.get_system_health()
            
            # Check if optimization is needed
            if health.avg_query_time_ms > self.performance_baselines["query_time_ms"] * 2:
                self.logger.info("Performance degradation detected - running optimization")
                optimization_result = self.automated_optimization()
                self.logger.info(f"Optimization completed: {optimization_result['status']}")
                
        except Exception as e:
            self.logger.error(f"Performance check failed: {e}")
            
    def _scheduled_maintenance(self):
        """Scheduled maintenance task"""
        try:
            self.logger.info("Running scheduled maintenance...")
            result = self.automated_optimization()
            self.logger.info(f"Scheduled maintenance completed: {result['status']}")
            
        except Exception as e:
            self.logger.error(f"Scheduled maintenance failed: {e}")
            
    def _scheduled_daily_report(self):
        """Generate daily system report"""
        try:
            assessment = self.comprehensive_health_assessment()
            alert_summary = self.alerting.get_alert_summary()
            
            report = self._generate_daily_report(assessment, alert_summary)
            self.logger.info("Daily report generated")
            
        except Exception as e:
            self.logger.error(f"Daily report generation failed: {e}")
            
    def _generate_daily_report(self, assessment: Dict, alert_summary: Dict) -> str:
        """Generate comprehensive daily report"""
        report = f"""
=== VEEVA DATA QUALITY SYSTEM - DAILY INFRASTRUCTURE REPORT ===
Date: {datetime.now().strftime('%Y-%m-%d')}
Report Generated: {datetime.now().isoformat()}

SYSTEM OVERVIEW:
- Overall Status: {assessment['overall_status']}
- System Uptime: {assessment['components']['system_health'].get('uptime_hours', 0):.1f} hours
- Last Health Check: {self.last_health_check}
- Last Maintenance: {self.last_maintenance}

PERFORMANCE METRICS:
- CPU Usage: {assessment['performance_metrics'].get('cpu_percent', 0):.1f}%
- Memory Usage: {assessment['performance_metrics'].get('memory_percent', 0):.1f}%
- Average Query Time: {assessment['performance_metrics'].get('avg_query_time_ms', 0):.1f}ms
- Total Records: {assessment['performance_metrics'].get('total_records', 0):,}

ALERT SUMMARY:
- Total Active Alerts: {alert_summary['total_active']}
- Critical: {alert_summary['by_severity']['CRITICAL']}
- High: {alert_summary['by_severity']['HIGH']}
- Medium: {alert_summary['by_severity']['MEDIUM']}
- Low: {alert_summary['by_severity']['LOW']}

RECOMMENDATIONS:
"""
        
        for rec in assessment.get("recommendations", []):
            report += f"- {rec}\n"
            
        if not assessment.get("recommendations"):
            report += "- No recommendations at this time\n"
            
        # Save report
        os.makedirs("reports", exist_ok=True)
        report_file = f"reports/daily_infrastructure_report_{datetime.now().strftime('%Y%m%d')}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report)
            
        return report_file
        
    def get_system_dashboard(self) -> Dict:
        """Get real-time system dashboard data"""
        try:
            health = self.monitor.get_system_health()
            alert_summary = self.alerting.get_alert_summary()
            
            dashboard = {
                "timestamp": datetime.now().isoformat(),
                "system_status": self.system_status,
                "health_metrics": {
                    "cpu_percent": health.cpu_percent,
                    "memory_percent": health.memory_percent,
                    "disk_free_gb": health.disk_free_gb,
                    "query_time_ms": health.avg_query_time_ms,
                    "total_records": health.total_records,
                    "uptime_hours": health.uptime_hours
                },
                "alerts": {
                    "total_active": alert_summary["total_active"],
                    "by_severity": alert_summary["by_severity"],
                    "recent_alerts": [alert.message for alert in self.alerting.get_active_alerts()[:5]]
                },
                "operational_metrics": {
                    "last_health_check": self.last_health_check,
                    "last_maintenance": self.last_maintenance,
                    "orchestrator_uptime": "running" if self.is_running else "stopped"
                }
            }
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Dashboard generation failed: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


def main():
    """Main function for infrastructure orchestrator"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Infrastructure Orchestrator')
    parser.add_argument('--mode', choices=['assessment', 'optimization', 'monitor', 'emergency', 'dashboard'],
                        default='assessment', help='Operation mode')
    parser.add_argument('--data-dir', default='data', help='Data directory path')
    
    args = parser.parse_args()
    
    orchestrator = InfrastructureOrchestrator(data_dir=args.data_dir)
    
    if args.mode == 'assessment':
        print("Running comprehensive health assessment...")
        assessment = orchestrator.comprehensive_health_assessment()
        print(f"\n=== SYSTEM HEALTH ASSESSMENT ===")
        print(f"Overall Status: {assessment['overall_status']}")
        print(f"Assessment Duration: {assessment['assessment_duration_seconds']:.2f}s")
        
        if assessment['alerts']:
            print(f"\nACTIVE ALERTS ({len(assessment['alerts'])}):")
            for alert in assessment['alerts']:
                print(f"  - {alert}")
                
        if assessment['recommendations']:
            print(f"\nRECOMMENDATIONS ({len(assessment['recommendations'])}):")
            for rec in assessment['recommendations']:
                print(f"  - {rec}")
                
    elif args.mode == 'optimization':
        print("Running automated optimization...")
        result = orchestrator.automated_optimization()
        print(f"Optimization Status: {result['status']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        
    elif args.mode == 'monitor':
        print("Starting continuous monitoring...")
        orchestrator.start_continuous_monitoring()
        
    elif args.mode == 'emergency':
        print("Executing emergency response...")
        response = orchestrator.emergency_response("HIGH")
        print(f"Emergency Response Status: {response['status']}")
        print(f"Actions Taken: {len(response['actions_taken'])}")
        
    elif args.mode == 'dashboard':
        dashboard = orchestrator.get_system_dashboard()
        print("=== SYSTEM DASHBOARD ===")
        print(json.dumps(dashboard, indent=2))


if __name__ == "__main__":
    main()