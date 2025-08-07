#!/usr/bin/env python3
"""
Generate comprehensive infrastructure status report for Veeva Data Quality System
"""

import os
import json
import time
import sqlite3
import subprocess
from datetime import datetime
from infrastructure_orchestrator import InfrastructureOrchestrator


def get_container_status():
    """Get Docker container status"""
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'json'], 
                              capture_output=True, text=True, check=True)
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                containers.append(json.loads(line))
                
        return {
            "status": "SUCCESS",
            "containers": containers,
            "total_running": len(containers)
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def get_system_metrics():
    """Get detailed system metrics"""
    import psutil
    
    # CPU info
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Memory info
    memory = psutil.virtual_memory()
    
    # Disk info
    disk = psutil.disk_usage('/')
    
    # Network info (basic)
    network = psutil.net_io_counters()
    
    return {
        "cpu": {
            "count": cpu_count,
            "usage_percent": cpu_percent,
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        },
        "memory": {
            "total_gb": memory.total / (1024**3),
            "available_gb": memory.available / (1024**3),
            "used_percent": memory.percent
        },
        "disk": {
            "total_gb": disk.total / (1024**3),
            "free_gb": disk.free / (1024**3),
            "used_percent": (disk.used / disk.total) * 100
        },
        "network": {
            "bytes_sent": network.bytes_sent if network else 0,
            "bytes_recv": network.bytes_recv if network else 0
        }
    }


def check_database_health():
    """Check database health and metrics"""
    db_metrics = {
        "status": "UNKNOWN",
        "databases": [],
        "total_size_mb": 0,
        "table_counts": {},
        "performance_test_ms": 0
    }
    
    # Check main databases
    data_dir = "data"
    db_files = ["metrics.db", "quality_metrics.db", "infrastructure_monitoring.db"]
    
    for db_file in db_files:
        db_path = os.path.join(data_dir, db_file)
        if os.path.exists(db_path):
            try:
                # Get file size
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                db_metrics["total_size_mb"] += size_mb
                
                # Test connection and get table info
                start_time = time.time()
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    # Count records in each table
                    table_counts = {}
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            table_counts[table] = cursor.fetchone()[0]
                        except:
                            table_counts[table] = "ERROR"
                            
                query_time = (time.time() - start_time) * 1000
                
                db_metrics["databases"].append({
                    "name": db_file,
                    "size_mb": size_mb,
                    "tables": len(tables),
                    "table_counts": table_counts,
                    "query_time_ms": query_time
                })
                
                db_metrics["performance_test_ms"] += query_time
                
            except Exception as e:
                db_metrics["databases"].append({
                    "name": db_file,
                    "error": str(e)
                })
    
    db_metrics["status"] = "HEALTHY" if db_metrics["databases"] else "NO_DATABASES"
    return db_metrics


def check_monitoring_systems():
    """Check status of monitoring systems"""
    monitoring_status = {
        "prometheus": {"status": "UNKNOWN", "url": "http://localhost:9090"},
        "grafana": {"status": "UNKNOWN", "url": "http://localhost:3000"},
        "infrastructure_monitor": {"status": "UNKNOWN"}
    }
    
    # Check Prometheus
    try:
        import requests
        response = requests.get("http://localhost:9090/api/v1/status/config", timeout=5)
        if response.status_code == 200:
            monitoring_status["prometheus"]["status"] = "RUNNING"
        else:
            monitoring_status["prometheus"]["status"] = "ERROR"
    except:
        monitoring_status["prometheus"]["status"] = "NOT_ACCESSIBLE"
    
    # Check Grafana
    try:
        response = requests.get("http://localhost:3000/api/health", timeout=5)
        if response.status_code == 200:
            monitoring_status["grafana"]["status"] = "RUNNING"
        else:
            monitoring_status["grafana"]["status"] = "ERROR"
    except:
        monitoring_status["grafana"]["status"] = "NOT_ACCESSIBLE"
    
    # Check if monitoring PID file exists
    if os.path.exists("monitoring.pid"):
        try:
            with open("monitoring.pid", 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is running
            try:
                os.kill(pid, 0)  # Doesn't actually kill, just checks if PID exists
                monitoring_status["infrastructure_monitor"]["status"] = "RUNNING"
                monitoring_status["infrastructure_monitor"]["pid"] = pid
            except ProcessLookupError:
                monitoring_status["infrastructure_monitor"]["status"] = "STOPPED"
        except:
            monitoring_status["infrastructure_monitor"]["status"] = "ERROR"
    else:
        monitoring_status["infrastructure_monitor"]["status"] = "NOT_STARTED"
    
    return monitoring_status


def get_log_summary():
    """Get summary of log files"""
    log_summary = {
        "total_logs": 0,
        "total_size_mb": 0,
        "recent_errors": 0,
        "log_files": []
    }
    
    log_dir = "logs"
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                if os.path.isfile(filepath):
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    log_summary["total_logs"] += 1
                    log_summary["total_size_mb"] += size_mb
                    
                    # Count recent errors (last 100 lines)
                    error_count = 0
                    try:
                        with open(filepath, 'r') as f:
                            lines = f.readlines()[-100:]  # Last 100 lines
                            error_count = len([line for line in lines if 'ERROR' in line or 'CRITICAL' in line])
                    except:
                        pass
                    
                    log_summary["log_files"].append({
                        "name": filename,
                        "size_mb": size_mb,
                        "recent_errors": error_count,
                        "modified": os.path.getmtime(filepath)
                    })
                    
                    log_summary["recent_errors"] += error_count
    
    return log_summary


def generate_infrastructure_report():
    """Generate comprehensive infrastructure report"""
    print("Generating Veeva Infrastructure Status Report...")
    
    # Initialize orchestrator for comprehensive assessment
    orchestrator = InfrastructureOrchestrator()
    
    # Gather all metrics
    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "report_type": "Infrastructure Status Report",
            "system": "Veeva Data Quality System",
            "version": "3.0.0"
        },
        "system_assessment": {},
        "system_metrics": {},
        "container_status": {},
        "database_health": {},
        "monitoring_systems": {},
        "log_summary": {},
        "performance_analysis": {},
        "recommendations": [],
        "alerts": []
    }
    
    print("  ✓ Running system assessment...")
    try:
        assessment = orchestrator.comprehensive_health_assessment()
        report["system_assessment"] = assessment
        report["alerts"].extend(assessment.get("alerts", []))
        report["recommendations"].extend(assessment.get("recommendations", []))
    except Exception as e:
        report["system_assessment"] = {"error": str(e)}
    
    print("  ✓ Gathering system metrics...")
    report["system_metrics"] = get_system_metrics()
    
    print("  ✓ Checking container status...")
    report["container_status"] = get_container_status()
    
    print("  ✓ Checking database health...")
    report["database_health"] = check_database_health()
    
    print("  ✓ Checking monitoring systems...")
    report["monitoring_systems"] = check_monitoring_systems()
    
    print("  ✓ Analyzing logs...")
    report["log_summary"] = get_log_summary()
    
    # Performance analysis
    print("  ✓ Analyzing performance...")
    performance_analysis = {
        "status": "UNKNOWN",
        "bottlenecks": [],
        "efficiency_score": 0,
        "recommendations": []
    }
    
    # Calculate efficiency score based on resource usage
    cpu_usage = report["system_metrics"]["cpu"]["usage_percent"]
    memory_usage = report["system_metrics"]["memory"]["used_percent"]
    disk_usage = report["system_metrics"]["disk"]["used_percent"]
    
    # Simple efficiency calculation (100 = perfect, lower = issues)
    efficiency_score = 100
    
    if cpu_usage > 80:
        efficiency_score -= 20
        performance_analysis["bottlenecks"].append("High CPU usage")
    elif cpu_usage > 60:
        efficiency_score -= 10
        
    if memory_usage > 85:
        efficiency_score -= 20
        performance_analysis["bottlenecks"].append("High memory usage")
    elif memory_usage > 70:
        efficiency_score -= 10
        
    if disk_usage > 90:
        efficiency_score -= 30
        performance_analysis["bottlenecks"].append("Low disk space")
    elif disk_usage > 80:
        efficiency_score -= 15
        
    # Check database performance
    total_db_size = report["database_health"]["total_size_mb"]
    avg_query_time = report["database_health"].get("performance_test_ms", 0)
    
    if avg_query_time > 100:
        efficiency_score -= 15
        performance_analysis["bottlenecks"].append("Slow database queries")
        
    performance_analysis["efficiency_score"] = max(0, efficiency_score)
    
    if efficiency_score >= 80:
        performance_analysis["status"] = "EXCELLENT"
    elif efficiency_score >= 60:
        performance_analysis["status"] = "GOOD"
    elif efficiency_score >= 40:
        performance_analysis["status"] = "FAIR"
    else:
        performance_analysis["status"] = "POOR"
        
    # Generate performance recommendations
    if cpu_usage > 70:
        performance_analysis["recommendations"].append("Consider CPU optimization or scaling")
    if memory_usage > 80:
        performance_analysis["recommendations"].append("Monitor memory usage and consider adding RAM")
    if disk_usage > 85:
        performance_analysis["recommendations"].append("Clean up disk space or add storage")
    if total_db_size > 500:
        performance_analysis["recommendations"].append("Consider database archiving strategy")
        
    report["performance_analysis"] = performance_analysis
    
    # Add infrastructure-specific recommendations
    if report["container_status"]["status"] != "SUCCESS":
        report["recommendations"].append("Docker container issues detected - check container health")
        
    if report["monitoring_systems"]["infrastructure_monitor"]["status"] != "RUNNING":
        report["recommendations"].append("Start infrastructure monitoring system")
        
    if report["log_summary"]["recent_errors"] > 10:
        report["recommendations"].append("Investigate recent error logs")
        
    # Generate summary status
    overall_status = "HEALTHY"
    critical_issues = 0
    
    if report["system_assessment"].get("overall_status") in ["CRITICAL", "DEGRADED"]:
        overall_status = "DEGRADED"
        critical_issues += 1
        
    if performance_analysis["status"] in ["POOR", "FAIR"]:
        overall_status = "DEGRADED"
        
    if report["database_health"]["status"] != "HEALTHY":
        critical_issues += 1
        
    if critical_issues >= 2:
        overall_status = "CRITICAL"
        
    report["overall_status"] = overall_status
    
    # Save report
    os.makedirs("reports", exist_ok=True)
    report_filename = f"reports/infrastructure_status_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2)
        
    print(f"  ✓ Report saved to: {report_filename}")
    
    # Generate human-readable summary
    summary_filename = f"reports/infrastructure_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    generate_readable_summary(report, summary_filename)
    
    print(f"  ✓ Summary saved to: {summary_filename}")
    
    return report, report_filename, summary_filename


def generate_readable_summary(report, filename):
    """Generate human-readable summary report"""
    
    summary = f"""
=== VEEVA DATA QUALITY SYSTEM - INFRASTRUCTURE STATUS REPORT ===
Generated: {report['report_metadata']['generated_at']}
Overall Status: {report['overall_status']}
Performance Score: {report['performance_analysis']['efficiency_score']}/100 ({report['performance_analysis']['status']})

SYSTEM OVERVIEW:
- CPU Usage: {report['system_metrics']['cpu']['usage_percent']:.1f}%
- Memory Usage: {report['system_metrics']['memory']['used_percent']:.1f}%
- Disk Usage: {report['system_metrics']['disk']['used_percent']:.1f}% ({report['system_metrics']['disk']['free_gb']:.1f}GB free)
- Total Database Size: {report['database_health']['total_size_mb']:.1f}MB

CONTAINER STATUS:
- Docker Status: {report['container_status']['status']}
- Running Containers: {report['container_status'].get('total_running', 0)}

DATABASE HEALTH:
- Status: {report['database_health']['status']}
- Databases Found: {len(report['database_health']['databases'])}
- Performance Test: {report['database_health']['performance_test_ms']:.1f}ms

MONITORING SYSTEMS:
- Infrastructure Monitor: {report['monitoring_systems']['infrastructure_monitor']['status']}
- Prometheus: {report['monitoring_systems']['prometheus']['status']}
- Grafana: {report['monitoring_systems']['grafana']['status']}

LOG ANALYSIS:
- Total Log Files: {report['log_summary']['total_logs']}
- Total Log Size: {report['log_summary']['total_size_mb']:.1f}MB
- Recent Errors: {report['log_summary']['recent_errors']}

PERFORMANCE BOTTLENECKS ({len(report['performance_analysis']['bottlenecks'])}):
"""
    
    for bottleneck in report['performance_analysis']['bottlenecks']:
        summary += f"- {bottleneck}\n"
    
    if not report['performance_analysis']['bottlenecks']:
        summary += "- No significant bottlenecks detected\n"
    
    summary += f"\nACTIVE ALERTS ({len(report['alerts'])}):\n"
    for alert in report['alerts']:
        summary += f"- {alert}\n"
    
    if not report['alerts']:
        summary += "- No active alerts\n"
    
    summary += f"\nRECOMMENDATIONS ({len(report['recommendations'])}):\n"
    for rec in report['recommendations']:
        summary += f"- {rec}\n"
    
    if not report['recommendations']:
        summary += "- System is operating optimally\n"
    
    # Add database details
    summary += "\nDATABASE DETAILS:\n"
    for db in report['database_health']['databases']:
        summary += f"- {db['name']}: {db.get('size_mb', 0):.1f}MB, {db.get('tables', 0)} tables\n"
        if 'table_counts' in db:
            total_records = sum(count for count in db['table_counts'].values() if isinstance(count, int))
            summary += f"  Total records: {total_records:,}\n"
    
    # Add container details if available
    if report['container_status']['status'] == 'SUCCESS':
        summary += "\nCONTAINER DETAILS:\n"
        for container in report['container_status']['containers']:
            summary += f"- {container.get('Names', 'Unknown')}: {container.get('State', 'Unknown')} ({container.get('Status', 'Unknown')})\n"
    
    summary += f"\n=== END REPORT ===\n"
    
    with open(filename, 'w') as f:
        f.write(summary)


def main():
    """Main function"""
    print("Veeva Data Quality System - Infrastructure Reporter")
    print("=" * 60)
    
    report, json_file, summary_file = generate_infrastructure_report()
    
    print("\n" + "=" * 60)
    print("INFRASTRUCTURE REPORT SUMMARY")
    print("=" * 60)
    
    # Display key metrics
    print(f"Overall Status: {report['overall_status']}")
    print(f"Performance Score: {report['performance_analysis']['efficiency_score']}/100")
    print(f"Active Alerts: {len(report['alerts'])}")
    print(f"Recommendations: {len(report['recommendations'])}")
    
    print(f"\nSystem Resources:")
    print(f"  CPU: {report['system_metrics']['cpu']['usage_percent']:.1f}%")
    print(f"  Memory: {report['system_metrics']['memory']['used_percent']:.1f}%")
    print(f"  Disk Free: {report['system_metrics']['disk']['free_gb']:.1f}GB")
    
    print(f"\nMonitoring Status:")
    print(f"  Infrastructure Monitor: {report['monitoring_systems']['infrastructure_monitor']['status']}")
    print(f"  Prometheus: {report['monitoring_systems']['prometheus']['status']}")
    print(f"  Grafana: {report['monitoring_systems']['grafana']['status']}")
    
    if report['alerts']:
        print(f"\nActive Alerts:")
        for alert in report['alerts'][:5]:  # Show first 5 alerts
            print(f"  - {alert}")
        if len(report['alerts']) > 5:
            print(f"  ... and {len(report['alerts']) - 5} more")
    
    if report['recommendations']:
        print(f"\nTop Recommendations:")
        for rec in report['recommendations'][:3]:  # Show top 3 recommendations
            print(f"  - {rec}")
        if len(report['recommendations']) > 3:
            print(f"  ... and {len(report['recommendations']) - 3} more")
    
    print(f"\nDetailed reports saved:")
    print(f"  JSON: {json_file}")
    print(f"  Summary: {summary_file}")
    
    print("\n" + "=" * 60)
    print("Infrastructure assessment completed!")
    
    # Return status code based on overall status
    if report['overall_status'] == 'CRITICAL':
        return 2
    elif report['overall_status'] == 'DEGRADED':
        return 1
    else:
        return 0


if __name__ == "__main__":
    exit(main())