#!/usr/bin/env python3
"""
Veeva Data Quality System - Automated Maintenance System
Performance optimization and proactive maintenance automation

This system handles automated performance optimization, capacity management,
and preventive maintenance for the production Veeva Data Quality System.
"""

import os
import sys
import json
import time
import logging
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import docker
import psutil


@dataclass
class MaintenanceTask:
    """Maintenance task definition"""
    name: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    frequency: str  # daily, weekly, monthly
    last_run: Optional[str]
    status: str
    execution_time_seconds: float
    details: Dict


class AutomatedMaintenance:
    """Automated maintenance and optimization system"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.maintenance_db = os.path.join(data_dir, "maintenance.db")
        self.log_file = os.path.join("logs", "automated_maintenance.log")
        
        # Performance thresholds
        self.QUERY_OPTIMIZATION_THRESHOLD_MS = 50.0
        self.CACHE_HIT_RATE_THRESHOLD = 80.0
        self.DB_FRAGMENTATION_THRESHOLD = 20.0
        self.LOG_SIZE_THRESHOLD_MB = 100.0
        
        # Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            self.docker_client = None
            
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
        """Setup maintenance tracking database"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        with sqlite3.connect(self.maintenance_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    priority TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    last_run TEXT,
                    status TEXT NOT NULL,
                    execution_time_seconds REAL DEFAULT 0,
                    details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_optimizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    optimization_type TEXT NOT NULL,
                    before_metrics TEXT,
                    after_metrics TEXT,
                    improvement_percent REAL,
                    status TEXT NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS capacity_planning (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    current_usage REAL,
                    predicted_usage REAL,
                    days_to_limit INTEGER,
                    recommended_action TEXT
                )
            ''')
            
    def database_optimization(self) -> Dict:
        """Comprehensive database optimization"""
        start_time = time.time()
        results = {
            "status": "SUCCESS",
            "optimizations": [],
            "errors": [],
            "performance_improvement": 0.0
        }
        
        try:
            db_path = os.path.join(self.data_dir, "metrics.db")
            if not os.path.exists(db_path):
                return {"status": "SKIPPED", "message": "Database not found"}
                
            # Measure initial performance
            initial_query_time = self._measure_query_performance(db_path)
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # 1. Update table statistics
                cursor.execute("ANALYZE")
                results["optimizations"].append("Updated table statistics (ANALYZE)")
                
                # 2. Rebuild fragmented indexes
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND sql IS NOT NULL
                """)
                indexes = cursor.fetchall()
                
                for (index_name,) in indexes:
                    cursor.execute(f"REINDEX {index_name}")
                    
                results["optimizations"].append(f"Rebuilt {len(indexes)} indexes")
                
                # 3. Vacuum database to reclaim space
                initial_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
                cursor.execute("VACUUM")
                final_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
                
                space_saved = initial_size - final_size
                results["optimizations"].append(f"VACUUM saved {space_saved:.2f} MB")
                
                # 4. Check and optimize query execution plans
                cursor.execute("""
                    SELECT sql FROM sqlite_master 
                    WHERE type='table' AND sql IS NOT NULL
                """)
                tables = cursor.fetchall()
                
                optimization_suggestions = []
                for (table_sql,) in tables:
                    # Basic optimization checks
                    if "CREATE INDEX" not in table_sql and "PRIMARY KEY" not in table_sql:
                        optimization_suggestions.append(f"Consider adding indexes to: {table_sql[:50]}...")
                        
                if optimization_suggestions:
                    results["optimizations"].append(f"Generated {len(optimization_suggestions)} optimization suggestions")
                    
            # Measure final performance
            final_query_time = self._measure_query_performance(db_path)
            
            if initial_query_time > 0 and final_query_time > 0:
                improvement = ((initial_query_time - final_query_time) / initial_query_time) * 100
                results["performance_improvement"] = improvement
                results["optimizations"].append(f"Query performance improved by {improvement:.1f}%")
                
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        # Log optimization results
        execution_time = time.time() - start_time
        self._log_maintenance_task("database_optimization", "HIGH", results, execution_time)
        
        return results
        
    def _measure_query_performance(self, db_path: str) -> float:
        """Measure average query performance"""
        try:
            start_time = time.time()
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Run several test queries
                test_queries = [
                    "SELECT COUNT(*) FROM sqlite_master",
                    "SELECT name FROM sqlite_master WHERE type='table' LIMIT 5",
                    "PRAGMA table_info(sqlite_master)"
                ]
                
                for query in test_queries:
                    cursor.execute(query)
                    cursor.fetchall()
                    
            return (time.time() - start_time) * 1000  # Convert to milliseconds
            
        except Exception:
            return 0.0
            
    def cache_optimization(self) -> Dict:
        """Optimize caching system"""
        start_time = time.time()
        results = {
            "status": "SUCCESS",
            "optimizations": [],
            "errors": [],
            "cache_hit_rate": 0.0
        }
        
        try:
            cache_dir = "cache"
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                results["optimizations"].append("Created cache directory")
                
            # Clean expired cache entries
            current_time = time.time()
            expired_count = 0
            
            for filename in os.listdir(cache_dir):
                filepath = os.path.join(cache_dir, filename)
                if os.path.isfile(filepath):
                    # Check if file is older than 1 hour (3600 seconds)
                    if current_time - os.path.getmtime(filepath) > 3600:
                        os.remove(filepath)
                        expired_count += 1
                        
            if expired_count > 0:
                results["optimizations"].append(f"Cleaned {expired_count} expired cache entries")
                
            # Calculate cache directory size
            total_size = sum(
                os.path.getsize(os.path.join(cache_dir, f)) 
                for f in os.listdir(cache_dir) 
                if os.path.isfile(os.path.join(cache_dir, f))
            ) / (1024 * 1024)  # MB
            
            results["optimizations"].append(f"Cache directory size: {total_size:.2f} MB")
            
            # If cache is too large, clean oldest files
            if total_size > 100:  # 100 MB threshold
                files_with_time = [
                    (f, os.path.getmtime(os.path.join(cache_dir, f)))
                    for f in os.listdir(cache_dir)
                    if os.path.isfile(os.path.join(cache_dir, f))
                ]
                
                # Sort by modification time (oldest first)
                files_with_time.sort(key=lambda x: x[1])
                
                # Remove oldest 25% of files
                files_to_remove = len(files_with_time) // 4
                for filename, _ in files_with_time[:files_to_remove]:
                    os.remove(os.path.join(cache_dir, filename))
                    
                results["optimizations"].append(f"Cleaned {files_to_remove} old cache files to manage size")
                
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        # Log cache optimization
        execution_time = time.time() - start_time
        self._log_maintenance_task("cache_optimization", "MEDIUM", results, execution_time)
        
        return results
        
    def log_rotation(self) -> Dict:
        """Rotate and compress log files"""
        start_time = time.time()
        results = {
            "status": "SUCCESS",
            "rotated_files": [],
            "errors": [],
            "space_saved_mb": 0.0
        }
        
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                return {"status": "SKIPPED", "message": "No logs directory"}
                
            current_time = time.time()
            total_space_saved = 0
            
            for filename in os.listdir(log_dir):
                if not filename.endswith('.log'):
                    continue
                    
                filepath = os.path.join(log_dir, filename)
                if not os.path.isfile(filepath):
                    continue
                    
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                
                # Rotate if file is larger than 50MB or older than 7 days
                file_age_days = (current_time - os.path.getmtime(filepath)) / 86400
                
                if file_size_mb > 50 or file_age_days > 7:
                    # Create rotated filename with timestamp
                    timestamp = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y%m%d_%H%M%S')
                    rotated_name = f"{filename}.{timestamp}"
                    rotated_path = os.path.join(log_dir, rotated_name)
                    
                    # Move and compress the file
                    os.rename(filepath, rotated_path)
                    
                    # Use gzip compression if available
                    try:
                        import gzip
                        import shutil
                        
                        with open(rotated_path, 'rb') as f_in:
                            with gzip.open(f"{rotated_path}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                                
                        # Remove uncompressed file
                        compressed_size = os.path.getsize(f"{rotated_path}.gz") / (1024 * 1024)
                        space_saved = file_size_mb - compressed_size
                        total_space_saved += space_saved
                        
                        os.remove(rotated_path)
                        results["rotated_files"].append(f"{filename} -> {rotated_name}.gz (saved {space_saved:.2f}MB)")
                        
                    except ImportError:
                        # Fallback without compression
                        results["rotated_files"].append(f"{filename} -> {rotated_name}")
                        
            results["space_saved_mb"] = total_space_saved
            
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        # Log rotation results
        execution_time = time.time() - start_time
        self._log_maintenance_task("log_rotation", "LOW", results, execution_time)
        
        return results
        
    def container_optimization(self) -> Dict:
        """Optimize container performance"""
        start_time = time.time()
        results = {
            "status": "SUCCESS",
            "optimizations": [],
            "errors": [],
            "containers_optimized": 0
        }
        
        if not self.docker_client:
            return {"status": "SKIPPED", "message": "Docker client not available"}
            
        try:
            containers = self.docker_client.containers.list()
            
            for container in containers:
                container_optimizations = []
                
                # Get container stats
                stats = container.stats(stream=False)
                
                # Check memory usage
                memory_usage = stats['memory_stats'].get('usage', 0)
                memory_limit = stats['memory_stats'].get('limit', 0)
                
                if memory_limit > 0:
                    memory_percent = (memory_usage / memory_limit) * 100
                    if memory_percent > 85:
                        container_optimizations.append(f"High memory usage: {memory_percent:.1f}%")
                        
                # Check if container needs restart due to uptime
                container_info = container.attrs
                started_at = container_info['State']['StartedAt']
                
                # Parse start time and check uptime
                from dateutil import parser
                start_time_dt = parser.parse(started_at.split('.')[0] + 'Z')
                uptime_hours = (datetime.utcnow() - start_time_dt).total_seconds() / 3600
                
                if uptime_hours > 168:  # 1 week
                    container_optimizations.append(f"Long uptime: {uptime_hours:.1f}h - consider restart")
                    
                if container_optimizations:
                    results["optimizations"].append(f"{container.name}: {', '.join(container_optimizations)}")
                    results["containers_optimized"] += 1
                    
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        # Log container optimization
        execution_time = time.time() - start_time
        self._log_maintenance_task("container_optimization", "MEDIUM", results, execution_time)
        
        return results
        
    def capacity_planning(self) -> Dict:
        """Analyze system capacity and predict resource needs"""
        start_time = time.time()
        results = {
            "status": "SUCCESS",
            "predictions": [],
            "recommendations": [],
            "errors": []
        }
        
        try:
            # Get current resource usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database growth analysis
            db_path = os.path.join(self.data_dir, "metrics.db")
            current_db_size = 0
            if os.path.exists(db_path):
                current_db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
                
            # Analyze historical data for trends
            with sqlite3.connect(self.maintenance_db) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, current_usage 
                    FROM capacity_planning 
                    WHERE resource_type = 'database_size'
                    ORDER BY timestamp DESC 
                    LIMIT 30
                """)
                historical_data = cursor.fetchall()
                
            # Simple trend analysis
            if len(historical_data) >= 7:
                recent_sizes = [float(row[1]) for row in historical_data[:7]]
                avg_growth = (max(recent_sizes) - min(recent_sizes)) / 7  # MB per day
                
                if avg_growth > 0:
                    days_to_1gb = (1000 - current_db_size) / avg_growth if current_db_size < 1000 else -1
                    results["predictions"].append(f"Database growing at {avg_growth:.2f}MB/day")
                    if days_to_1gb > 0:
                        results["predictions"].append(f"Will reach 1GB in {days_to_1gb:.0f} days")
                        
            # Disk space analysis
            disk_free_gb = disk.free / (1024**3)
            if disk_free_gb < 10:
                results["recommendations"].append(f"LOW DISK SPACE: {disk_free_gb:.1f}GB free - Clean up files")
            elif disk_free_gb < 20:
                results["recommendations"].append(f"Monitor disk space: {disk_free_gb:.1f}GB free")
                
            # Memory analysis
            if memory.percent > 80:
                results["recommendations"].append(f"HIGH MEMORY USAGE: {memory.percent:.1f}% - Consider adding RAM")
                
            # CPU analysis
            if cpu_percent > 70:
                results["recommendations"].append(f"HIGH CPU USAGE: {cpu_percent:.1f}% - Monitor workload")
                
            # Record current capacity metrics
            self._record_capacity_metrics(current_db_size, memory.percent, disk_free_gb)
            
        except Exception as e:
            results["status"] = "ERROR"
            results["errors"].append(str(e))
            
        # Log capacity planning
        execution_time = time.time() - start_time
        self._log_maintenance_task("capacity_planning", "HIGH", results, execution_time)
        
        return results
        
    def _record_capacity_metrics(self, db_size_mb: float, memory_percent: float, disk_free_gb: float):
        """Record current capacity metrics for trend analysis"""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.maintenance_db) as conn:
            metrics = [
                (timestamp, "database_size", db_size_mb, 0, 0, "Monitor growth"),
                (timestamp, "memory_usage", memory_percent, 0, 0, "Monitor usage"),
                (timestamp, "disk_free", disk_free_gb, 0, 0, "Monitor space")
            ]
            
            conn.executemany('''
                INSERT INTO capacity_planning 
                (timestamp, resource_type, current_usage, predicted_usage, days_to_limit, recommended_action)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', metrics)
            
    def _log_maintenance_task(self, task_name: str, priority: str, results: Dict, execution_time: float):
        """Log maintenance task execution"""
        with sqlite3.connect(self.maintenance_db) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO maintenance_tasks 
                (name, priority, frequency, last_run, status, execution_time_seconds, details, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_name,
                priority,
                "as_needed",
                datetime.now().isoformat(),
                results["status"],
                execution_time,
                json.dumps(results),
                datetime.now().isoformat()
            ))
            
    def run_full_maintenance(self) -> Dict:
        """Run comprehensive maintenance routine"""
        start_time = time.time()
        maintenance_results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "SUCCESS",
            "tasks_completed": 0,
            "tasks_failed": 0,
            "results": {}
        }
        
        tasks = [
            ("database_optimization", self.database_optimization),
            ("cache_optimization", self.cache_optimization),
            ("log_rotation", self.log_rotation),
            ("container_optimization", self.container_optimization),
            ("capacity_planning", self.capacity_planning)
        ]
        
        for task_name, task_function in tasks:
            try:
                self.logger.info(f"Running {task_name}...")
                result = task_function()
                maintenance_results["results"][task_name] = result
                
                if result["status"] == "SUCCESS":
                    maintenance_results["tasks_completed"] += 1
                    self.logger.info(f"{task_name} completed successfully")
                else:
                    maintenance_results["tasks_failed"] += 1
                    self.logger.warning(f"{task_name} failed: {result.get('errors', [])}")
                    
            except Exception as e:
                maintenance_results["tasks_failed"] += 1
                maintenance_results["results"][task_name] = {
                    "status": "ERROR",
                    "error": str(e)
                }
                self.logger.error(f"{task_name} failed with exception: {e}")
                
        # Determine overall status
        if maintenance_results["tasks_failed"] > 0:
            maintenance_results["overall_status"] = "PARTIAL_FAILURE"
            
        if maintenance_results["tasks_completed"] == 0:
            maintenance_results["overall_status"] = "FAILURE"
            
        total_time = time.time() - start_time
        maintenance_results["total_execution_time"] = total_time
        
        # Generate maintenance report
        self._generate_maintenance_report(maintenance_results)
        
        return maintenance_results
        
    def _generate_maintenance_report(self, results: Dict):
        """Generate comprehensive maintenance report"""
        report = f"""
=== VEEVA DATA QUALITY SYSTEM - AUTOMATED MAINTENANCE REPORT ===
Timestamp: {results['timestamp']}
Overall Status: {results['overall_status']}
Tasks Completed: {results['tasks_completed']}
Tasks Failed: {results['tasks_failed']}
Total Execution Time: {results['total_execution_time']:.2f} seconds

TASK RESULTS:
"""
        
        for task_name, task_result in results["results"].items():
            report += f"\n{task_name.upper()}:\n"
            report += f"  Status: {task_result['status']}\n"
            
            if "optimizations" in task_result:
                report += f"  Optimizations ({len(task_result['optimizations'])}):\n"
                for opt in task_result["optimizations"]:
                    report += f"    - {opt}\n"
                    
            if "errors" in task_result and task_result["errors"]:
                report += f"  Errors:\n"
                for error in task_result["errors"]:
                    report += f"    - {error}\n"
                    
        # Save report
        os.makedirs("reports", exist_ok=True)
        report_file = f"reports/maintenance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report)
            
        self.logger.info(f"Maintenance report saved to {report_file}")


def main():
    """Main function for automated maintenance"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Automated Maintenance System')
    parser.add_argument('--task', choices=['all', 'database', 'cache', 'logs', 'containers', 'capacity'],
                        default='all', help='Specific maintenance task to run')
    parser.add_argument('--data-dir', default='data', help='Data directory path')
    
    args = parser.parse_args()
    
    maintenance = AutomatedMaintenance(data_dir=args.data_dir)
    
    if args.task == 'all':
        results = maintenance.run_full_maintenance()
        print(f"Maintenance completed with status: {results['overall_status']}")
        print(f"Tasks completed: {results['tasks_completed']}")
        print(f"Tasks failed: {results['tasks_failed']}")
        
    elif args.task == 'database':
        results = maintenance.database_optimization()
        print(f"Database optimization: {results['status']}")
        
    elif args.task == 'cache':
        results = maintenance.cache_optimization()
        print(f"Cache optimization: {results['status']}")
        
    elif args.task == 'logs':
        results = maintenance.log_rotation()
        print(f"Log rotation: {results['status']}")
        
    elif args.task == 'containers':
        results = maintenance.container_optimization()
        print(f"Container optimization: {results['status']}")
        
    elif args.task == 'capacity':
        results = maintenance.capacity_planning()
        print(f"Capacity planning: {results['status']}")


if __name__ == "__main__":
    main()