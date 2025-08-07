"""
System monitoring and metrics collection utilities
"""

import psutil
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    active_connections: int = 0
    query_count_per_minute: int = 0


@dataclass
class DatabaseMetrics:
    """Database-specific metrics"""
    timestamp: str
    database_size_mb: float
    table_count: int
    total_records: int
    largest_table: str
    largest_table_records: int
    query_performance_ms: float
    connection_pool_size: int = 0
    active_queries: int = 0


@dataclass
class QualityMetrics:
    """Data quality metrics summary"""
    timestamp: str
    overall_quality_score: float
    completeness_score: float
    consistency_score: float
    accuracy_score: float
    timeliness_score: float
    uniqueness_score: float
    validity_score: float
    failed_validations: int
    critical_issues: int


class SystemMonitor:
    """System monitoring and metrics collection"""
    
    def __init__(self, db_path: str, metrics_retention_days: int = 30):
        self.db_path = Path(db_path)
        self.metrics_retention_days = metrics_retention_days
        self.metrics_db_path = self.db_path.parent / "metrics.db"
        self._init_metrics_database()
    
    def _init_metrics_database(self):
        """Initialize metrics storage database"""
        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                cursor = conn.cursor()
                
                # System metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        memory_used_gb REAL,
                        memory_available_gb REAL,
                        disk_usage_percent REAL,
                        disk_free_gb REAL,
                        active_connections INTEGER,
                        query_count_per_minute INTEGER
                    )
                """)
                
                # Database metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS database_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        database_size_mb REAL,
                        table_count INTEGER,
                        total_records INTEGER,
                        largest_table TEXT,
                        largest_table_records INTEGER,
                        query_performance_ms REAL,
                        connection_pool_size INTEGER,
                        active_queries INTEGER
                    )
                """)
                
                # Quality metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quality_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        overall_quality_score REAL,
                        completeness_score REAL,
                        consistency_score REAL,
                        accuracy_score REAL,
                        timeliness_score REAL,
                        uniqueness_score REAL,
                        validity_score REAL,
                        failed_validations INTEGER,
                        critical_issues INTEGER
                    )
                """)
                
                # Create indexes for better query performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_metrics(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_database_timestamp ON database_metrics(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_timestamp ON quality_metrics(timestamp)")
                
                conn.commit()
                logger.info(f"Metrics database initialized: {self.metrics_db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize metrics database: {e}")
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system performance metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage(self.db_path.parent)
            
            metrics = SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=round(memory.used / (1024**3), 2),
                memory_available_gb=round(memory.available / (1024**3), 2),
                disk_usage_percent=round((disk.used / disk.total) * 100, 2),
                disk_free_gb=round(disk.free / (1024**3), 2)
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return None
    
    def collect_database_metrics(self) -> Optional[DatabaseMetrics]:
        """Collect database performance and size metrics"""
        try:
            if not self.db_path.exists():
                logger.warning(f"Database not found: {self.db_path}")
                return None
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Database size
                db_size_bytes = self.db_path.stat().st_size
                db_size_mb = round(db_size_bytes / (1024**2), 2)
                
                # Table count and record counts
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                table_count = len(tables)
                
                total_records = 0
                largest_table = ""
                largest_table_records = 0
                
                for (table_name,) in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        total_records += count
                        
                        if count > largest_table_records:
                            largest_table = table_name
                            largest_table_records = count
                            
                    except sqlite3.Error as e:
                        logger.warning(f"Error counting records in {table_name}: {e}")
                
                # Query performance test
                start_time = time.time()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                query_time_ms = round((time.time() - start_time) * 1000, 2)
                
                metrics = DatabaseMetrics(
                    timestamp=datetime.now().isoformat(),
                    database_size_mb=db_size_mb,
                    table_count=table_count,
                    total_records=total_records,
                    largest_table=largest_table,
                    largest_table_records=largest_table_records,
                    query_performance_ms=query_time_ms
                )
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            return None
    
    def store_metrics(self, system_metrics: Optional[SystemMetrics] = None,
                     database_metrics: Optional[DatabaseMetrics] = None,
                     quality_metrics: Optional[QualityMetrics] = None):
        """Store metrics in the metrics database"""
        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                cursor = conn.cursor()
                
                if system_metrics:
                    cursor.execute("""
                        INSERT INTO system_metrics 
                        (timestamp, cpu_percent, memory_percent, memory_used_gb, 
                         memory_available_gb, disk_usage_percent, disk_free_gb, 
                         active_connections, query_count_per_minute)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        system_metrics.timestamp,
                        system_metrics.cpu_percent,
                        system_metrics.memory_percent,
                        system_metrics.memory_used_gb,
                        system_metrics.memory_available_gb,
                        system_metrics.disk_usage_percent,
                        system_metrics.disk_free_gb,
                        system_metrics.active_connections,
                        system_metrics.query_count_per_minute
                    ))
                
                if database_metrics:
                    cursor.execute("""
                        INSERT INTO database_metrics 
                        (timestamp, database_size_mb, table_count, total_records,
                         largest_table, largest_table_records, query_performance_ms,
                         connection_pool_size, active_queries)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        database_metrics.timestamp,
                        database_metrics.database_size_mb,
                        database_metrics.table_count,
                        database_metrics.total_records,
                        database_metrics.largest_table,
                        database_metrics.largest_table_records,
                        database_metrics.query_performance_ms,
                        database_metrics.connection_pool_size,
                        database_metrics.active_queries
                    ))
                
                if quality_metrics:
                    cursor.execute("""
                        INSERT INTO quality_metrics 
                        (timestamp, overall_quality_score, completeness_score,
                         consistency_score, accuracy_score, timeliness_score,
                         uniqueness_score, validity_score, failed_validations,
                         critical_issues)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        quality_metrics.timestamp,
                        quality_metrics.overall_quality_score,
                        quality_metrics.completeness_score,
                        quality_metrics.consistency_score,
                        quality_metrics.accuracy_score,
                        quality_metrics.timeliness_score,
                        quality_metrics.uniqueness_score,
                        quality_metrics.validity_score,
                        quality_metrics.failed_validations,
                        quality_metrics.critical_issues
                    ))
                
                conn.commit()
                logger.debug("Metrics stored successfully")
                
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
    
    def get_system_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        system_metrics = self.collect_system_metrics()
        database_metrics = self.collect_database_metrics()
        
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'issues': [],
            'warnings': []
        }
        
        if system_metrics:
            # Check system thresholds
            if system_metrics.cpu_percent > 80:
                health_status['issues'].append(f"High CPU usage: {system_metrics.cpu_percent}%")
                health_status['overall_status'] = 'WARNING'
            
            if system_metrics.memory_percent > 85:
                health_status['issues'].append(f"High memory usage: {system_metrics.memory_percent}%")
                health_status['overall_status'] = 'WARNING'
            
            if system_metrics.disk_usage_percent > 90:
                health_status['issues'].append(f"Low disk space: {system_metrics.disk_free_gb}GB free")
                health_status['overall_status'] = 'CRITICAL'
            
            health_status['system_metrics'] = asdict(system_metrics)
        
        if database_metrics:
            # Check database health
            if database_metrics.query_performance_ms > 1000:
                health_status['warnings'].append(f"Slow query performance: {database_metrics.query_performance_ms}ms")
            
            if database_metrics.database_size_mb > 5000:  # 5GB threshold
                health_status['warnings'].append(f"Large database size: {database_metrics.database_size_mb}MB")
            
            health_status['database_metrics'] = asdict(database_metrics)
        
        # Set overall status based on issues
        if health_status['issues']:
            if any('CRITICAL' in issue or 'disk space' in issue.lower() for issue in health_status['issues']):
                health_status['overall_status'] = 'CRITICAL'
            else:
                health_status['overall_status'] = 'WARNING'
        
        return health_status
    
    def cleanup_old_metrics(self):
        """Remove old metrics data beyond retention period"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=self.metrics_retention_days)).isoformat()
            
            with sqlite3.connect(self.metrics_db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up old records
                tables = ['system_metrics', 'database_metrics', 'quality_metrics']
                total_deleted = 0
                
                for table in tables:
                    cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff_date,))
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    if deleted > 0:
                        logger.info(f"Deleted {deleted} old records from {table}")
                
                conn.commit()
                
                if total_deleted > 0:
                    logger.info(f"Metrics cleanup completed: {total_deleted} total records deleted")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary for the specified time period"""
        try:
            start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            with sqlite3.connect(self.metrics_db_path) as conn:
                cursor = conn.cursor()
                
                summary = {
                    'time_period_hours': hours,
                    'start_time': start_time,
                    'end_time': datetime.now().isoformat()
                }
                
                # System metrics summary
                cursor.execute("""
                    SELECT 
                        AVG(cpu_percent) as avg_cpu,
                        MAX(cpu_percent) as max_cpu,
                        AVG(memory_percent) as avg_memory,
                        MAX(memory_percent) as max_memory,
                        MIN(disk_free_gb) as min_disk_free,
                        COUNT(*) as data_points
                    FROM system_metrics 
                    WHERE timestamp >= ?
                """, (start_time,))
                
                system_summary = cursor.fetchone()
                if system_summary:
                    summary['system'] = {
                        'avg_cpu_percent': round(system_summary[0] or 0, 2),
                        'max_cpu_percent': round(system_summary[1] or 0, 2),
                        'avg_memory_percent': round(system_summary[2] or 0, 2),
                        'max_memory_percent': round(system_summary[3] or 0, 2),
                        'min_disk_free_gb': round(system_summary[4] or 0, 2),
                        'data_points': system_summary[5]
                    }
                
                # Database metrics summary
                cursor.execute("""
                    SELECT 
                        AVG(database_size_mb) as avg_db_size,
                        AVG(query_performance_ms) as avg_query_time,
                        MAX(query_performance_ms) as max_query_time,
                        AVG(total_records) as avg_total_records
                    FROM database_metrics 
                    WHERE timestamp >= ?
                """, (start_time,))
                
                db_summary = cursor.fetchone()
                if db_summary:
                    summary['database'] = {
                        'avg_size_mb': round(db_summary[0] or 0, 2),
                        'avg_query_time_ms': round(db_summary[1] or 0, 2),
                        'max_query_time_ms': round(db_summary[2] or 0, 2),
                        'avg_total_records': int(db_summary[3] or 0)
                    }
                
                return summary
                
        except Exception as e:
            logger.error(f"Failed to generate metrics summary: {e}")
            return {'error': str(e)}


def create_monitoring_dashboard(monitor: SystemMonitor, output_file: str = "monitoring_dashboard.html"):
    """Create a simple HTML monitoring dashboard"""
    try:
        health_status = monitor.get_system_health_status()
        metrics_summary = monitor.get_metrics_summary(24)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Veeva Data Quality System - Monitoring Dashboard</title>
            <meta http-equiv="refresh" content="60"> <!-- Auto refresh every minute -->
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .dashboard {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .status-healthy {{ color: #28a745; }}
                .status-warning {{ color: #ffc107; }}
                .status-critical {{ color: #dc3545; }}
                .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
                .metric-value {{ font-size: 24px; font-weight: bold; }}
                .metric-label {{ font-size: 14px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <h1>🏥 Veeva Data Quality System - Monitoring Dashboard</h1>
                <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="card">
                    <h2>System Health Status</h2>
                    <p class="status-{health_status['overall_status'].lower()}">
                        <strong>Status: {health_status['overall_status']}</strong>
                    </p>
                    
                    {'<h3>Issues:</h3><ul>' + ''.join([f'<li>{issue}</li>' for issue in health_status['issues']]) + '</ul>' if health_status['issues'] else ''}
                    {'<h3>Warnings:</h3><ul>' + ''.join([f'<li>{warning}</li>' for warning in health_status['warnings']]) + '</ul>' if health_status['warnings'] else ''}
                </div>
                
                <div class="card">
                    <h2>Current System Metrics</h2>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('system_metrics', {}).get('cpu_percent', 0):.1f}%</div>
                        <div class="metric-label">CPU Usage</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('system_metrics', {}).get('memory_percent', 0):.1f}%</div>
                        <div class="metric-label">Memory Usage</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('system_metrics', {}).get('disk_free_gb', 0):.1f}GB</div>
                        <div class="metric-label">Disk Free</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Database Metrics</h2>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('database_metrics', {}).get('database_size_mb', 0):.1f}MB</div>
                        <div class="metric-label">Database Size</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('database_metrics', {}).get('total_records', 0):,}</div>
                        <div class="metric-label">Total Records</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{health_status.get('database_metrics', {}).get('query_performance_ms', 0):.1f}ms</div>
                        <div class="metric-label">Query Performance</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>24-Hour Summary</h2>
                    <table>
                        <tr><th>Metric</th><th>Average</th><th>Peak</th></tr>
                        <tr>
                            <td>CPU Usage</td>
                            <td>{metrics_summary.get('system', {}).get('avg_cpu_percent', 0):.1f}%</td>
                            <td>{metrics_summary.get('system', {}).get('max_cpu_percent', 0):.1f}%</td>
                        </tr>
                        <tr>
                            <td>Memory Usage</td>
                            <td>{metrics_summary.get('system', {}).get('avg_memory_percent', 0):.1f}%</td>
                            <td>{metrics_summary.get('system', {}).get('max_memory_percent', 0):.1f}%</td>
                        </tr>
                        <tr>
                            <td>Query Performance</td>
                            <td>{metrics_summary.get('database', {}).get('avg_query_time_ms', 0):.1f}ms</td>
                            <td>{metrics_summary.get('database', {}).get('max_query_time_ms', 0):.1f}ms</td>
                        </tr>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Monitoring dashboard created: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Failed to create monitoring dashboard: {e}")
        return None