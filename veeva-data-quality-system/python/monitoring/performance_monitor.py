"""
Performance monitoring and optimization system for Veeva Data Quality System
Tracks query performance, database metrics, cache efficiency, and system health
"""

import asyncio
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    timestamp: datetime
    query_execution_time: float
    query_count: int
    cache_hit_rate: float
    database_size_mb: float
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    active_connections: int
    slow_queries: int
    error_rate: float
    system_health_score: float = field(default=0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'query_execution_time_ms': round(self.query_execution_time * 1000, 3),
            'query_count': self.query_count,
            'cache_hit_rate_percent': round(self.cache_hit_rate * 100, 2),
            'database_size_mb': round(self.database_size_mb, 2),
            'memory_usage_mb': round(self.memory_usage_mb, 2),
            'cpu_usage_percent': round(self.cpu_usage_percent, 2),
            'disk_io_read_mb': round(self.disk_io_read_mb, 2),
            'disk_io_write_mb': round(self.disk_io_write_mb, 2),
            'active_connections': self.active_connections,
            'slow_queries': self.slow_queries,
            'error_rate_percent': round(self.error_rate * 100, 2),
            'system_health_score': round(self.system_health_score, 2)
        }


@dataclass
class PerformanceTarget:
    """Performance targets and thresholds"""
    max_query_time_seconds: float = 5.0
    target_cache_hit_rate: float = 0.80
    max_cpu_usage: float = 70.0
    max_memory_usage_mb: float = 512.0
    min_health_score: float = 85.0
    max_error_rate: float = 0.01
    

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system that:
    - Tracks query execution times and patterns
    - Monitors cache performance and hit rates
    - Analyzes database performance metrics
    - Monitors system resource usage
    - Generates performance reports and alerts
    """
    
    def __init__(self, 
                 database_path: str,
                 cache_manager=None,
                 monitoring_interval: int = 30,
                 retention_days: int = 30):
        """
        Initialize performance monitor
        
        Args:
            database_path: Path to main database file
            cache_manager: Cache manager instance for monitoring
            monitoring_interval: Monitoring frequency in seconds
            retention_days: Days to retain performance data
        """
        self.database_path = Path(database_path)
        self.cache_manager = cache_manager
        self.monitoring_interval = monitoring_interval
        self.retention_days = retention_days
        
        # Performance tracking
        self.targets = PerformanceTarget()
        self.query_tracker = QueryPerformanceTracker()
        self.system_tracker = SystemResourceTracker()
        
        # Metrics storage
        self.metrics_db_path = self.database_path.parent / "performance_metrics.db"
        self._init_metrics_database()
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread = None
        self._lock = threading.Lock()
        
        # Performance baselines
        self.baseline_metrics: Optional[PerformanceMetrics] = None
        self._load_baseline_metrics()
        
        logger.info(f"Performance monitor initialized with {monitoring_interval}s interval")
    
    def _init_metrics_database(self):
        """Initialize performance metrics database"""
        self.metrics_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.metrics_db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    query_execution_time_ms REAL,
                    query_count INTEGER,
                    cache_hit_rate_percent REAL,
                    database_size_mb REAL,
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    disk_io_read_mb REAL,
                    disk_io_write_mb REAL,
                    active_connections INTEGER,
                    slow_queries INTEGER,
                    error_rate_percent REAL,
                    system_health_score REAL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    query_name TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    row_count INTEGER,
                    cache_hit BOOLEAN,
                    error_message TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metric_value REAL,
                    threshold_value REAL,
                    resolved BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create indexes for better query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_timestamp ON query_performance(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON performance_alerts(timestamp)")
            
            conn.commit()
            logger.info("Performance metrics database initialized")
        finally:
            conn.close()
    
    def _load_baseline_metrics(self):
        """Load baseline performance metrics"""
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            cursor = conn.execute("""
                SELECT * FROM performance_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                # Convert row to PerformanceMetrics (simplified)
                self.baseline_metrics = PerformanceMetrics(
                    timestamp=datetime.fromisoformat(row[1]),
                    query_execution_time=row[2] / 1000,  # Convert ms to seconds
                    query_count=row[3] or 0,
                    cache_hit_rate=row[4] / 100 if row[4] else 0,  # Convert % to ratio
                    database_size_mb=row[5] or 0,
                    memory_usage_mb=row[6] or 0,
                    cpu_usage_percent=row[7] or 0,
                    disk_io_read_mb=row[8] or 0,
                    disk_io_write_mb=row[9] or 0,
                    active_connections=row[10] or 0,
                    slow_queries=row[11] or 0,
                    error_rate=row[12] / 100 if row[12] else 0,
                    system_health_score=row[13] or 0
                )
            conn.close()
        except Exception as e:
            logger.warning(f"Could not load baseline metrics: {e}")
    
    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        if self._monitoring_active:
            logger.warning("Performance monitoring already active")
            return
        
        self._monitoring_active = True
        
        # Start monitoring in background thread
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitoring_thread.start()
        
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._monitoring_active:
            try:
                # Collect metrics
                metrics = self._collect_performance_metrics()
                
                # Store metrics
                self._store_metrics(metrics)
                
                # Check for alerts
                self._check_performance_alerts(metrics)
                
                # Sleep until next monitoring cycle
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        current_time = datetime.now()
        
        # Get database metrics
        db_size = self._get_database_size()
        query_stats = self.query_tracker.get_recent_stats()
        
        # Get cache metrics
        cache_hit_rate = 0.0
        if self.cache_manager:
            cache_stats = self.cache_manager.get_cache_stats()
            cache_hit_rate = cache_stats.get('hit_rate_percent', 0) / 100
        
        # Get system metrics
        system_stats = self.system_tracker.get_current_stats()
        
        # Calculate health score
        health_score = self._calculate_health_score(
            query_stats, cache_hit_rate, system_stats
        )
        
        metrics = PerformanceMetrics(
            timestamp=current_time,
            query_execution_time=query_stats.get('avg_execution_time', 0),
            query_count=query_stats.get('total_queries', 0),
            cache_hit_rate=cache_hit_rate,
            database_size_mb=db_size,
            memory_usage_mb=system_stats.get('memory_mb', 0),
            cpu_usage_percent=system_stats.get('cpu_percent', 0),
            disk_io_read_mb=system_stats.get('disk_read_mb', 0),
            disk_io_write_mb=system_stats.get('disk_write_mb', 0),
            active_connections=1,  # SQLite single connection
            slow_queries=query_stats.get('slow_queries', 0),
            error_rate=query_stats.get('error_rate', 0),
            system_health_score=health_score
        )
        
        return metrics
    
    def _get_database_size(self) -> float:
        """Get database file size in MB"""
        try:
            if self.database_path.exists():
                size_bytes = self.database_path.stat().st_size
                return size_bytes / (1024 * 1024)
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
        return 0.0
    
    def _calculate_health_score(self, query_stats: Dict, cache_hit_rate: float, system_stats: Dict) -> float:
        """Calculate overall system health score (0-100)"""
        score = 100.0
        
        # Query performance penalty (0-30 points)
        avg_query_time = query_stats.get('avg_execution_time', 0)
        if avg_query_time > self.targets.max_query_time_seconds:
            penalty = min(30, (avg_query_time / self.targets.max_query_time_seconds - 1) * 20)
            score -= penalty
        
        # Cache performance penalty (0-20 points)
        if cache_hit_rate < self.targets.target_cache_hit_rate:
            penalty = (self.targets.target_cache_hit_rate - cache_hit_rate) * 50
            score -= min(20, penalty)
        
        # System resource penalty (0-25 points)
        cpu_usage = system_stats.get('cpu_percent', 0)
        if cpu_usage > self.targets.max_cpu_usage:
            penalty = (cpu_usage - self.targets.max_cpu_usage) / 30 * 15
            score -= min(15, penalty)
        
        memory_usage = system_stats.get('memory_mb', 0)
        if memory_usage > self.targets.max_memory_usage_mb:
            penalty = (memory_usage - self.targets.max_memory_usage_mb) / self.targets.max_memory_usage_mb * 10
            score -= min(10, penalty)
        
        # Error rate penalty (0-25 points)
        error_rate = query_stats.get('error_rate', 0)
        if error_rate > self.targets.max_error_rate:
            penalty = (error_rate - self.targets.max_error_rate) * 100
            score -= min(25, penalty)
        
        return max(0, score)
    
    def _store_metrics(self, metrics: PerformanceMetrics):
        """Store metrics in database"""
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            metrics_dict = metrics.to_dict()
            
            conn.execute("""
                INSERT INTO performance_metrics (
                    timestamp, query_execution_time_ms, query_count, cache_hit_rate_percent,
                    database_size_mb, memory_usage_mb, cpu_usage_percent, disk_io_read_mb,
                    disk_io_write_mb, active_connections, slow_queries, error_rate_percent,
                    system_health_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics_dict['timestamp'],
                metrics_dict['query_execution_time_ms'],
                metrics_dict['query_count'],
                metrics_dict['cache_hit_rate_percent'],
                metrics_dict['database_size_mb'],
                metrics_dict['memory_usage_mb'],
                metrics_dict['cpu_usage_percent'],
                metrics_dict['disk_io_read_mb'],
                metrics_dict['disk_io_write_mb'],
                metrics_dict['active_connections'],
                metrics_dict['slow_queries'],
                metrics_dict['error_rate_percent'],
                metrics_dict['system_health_score']
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    def _check_performance_alerts(self, metrics: PerformanceMetrics):
        """Check for performance threshold breaches and generate alerts"""
        alerts = []
        
        # Query time alert
        if metrics.query_execution_time > self.targets.max_query_time_seconds:
            alerts.append({
                'type': 'query_performance',
                'severity': 'HIGH' if metrics.query_execution_time > self.targets.max_query_time_seconds * 2 else 'MEDIUM',
                'message': f'Query execution time {metrics.query_execution_time:.3f}s exceeds target {self.targets.max_query_time_seconds}s',
                'value': metrics.query_execution_time,
                'threshold': self.targets.max_query_time_seconds
            })
        
        # Cache hit rate alert
        if metrics.cache_hit_rate < self.targets.target_cache_hit_rate:
            alerts.append({
                'type': 'cache_performance',
                'severity': 'MEDIUM',
                'message': f'Cache hit rate {metrics.cache_hit_rate:.1%} below target {self.targets.target_cache_hit_rate:.1%}',
                'value': metrics.cache_hit_rate,
                'threshold': self.targets.target_cache_hit_rate
            })
        
        # CPU usage alert
        if metrics.cpu_usage_percent > self.targets.max_cpu_usage:
            alerts.append({
                'type': 'cpu_usage',
                'severity': 'HIGH' if metrics.cpu_usage_percent > 90 else 'MEDIUM',
                'message': f'CPU usage {metrics.cpu_usage_percent:.1f}% exceeds target {self.targets.max_cpu_usage}%',
                'value': metrics.cpu_usage_percent,
                'threshold': self.targets.max_cpu_usage
            })
        
        # Memory usage alert
        if metrics.memory_usage_mb > self.targets.max_memory_usage_mb:
            alerts.append({
                'type': 'memory_usage',
                'severity': 'MEDIUM',
                'message': f'Memory usage {metrics.memory_usage_mb:.0f}MB exceeds target {self.targets.max_memory_usage_mb}MB',
                'value': metrics.memory_usage_mb,
                'threshold': self.targets.max_memory_usage_mb
            })
        
        # Health score alert
        if metrics.system_health_score < self.targets.min_health_score:
            alerts.append({
                'type': 'system_health',
                'severity': 'HIGH' if metrics.system_health_score < 70 else 'MEDIUM',
                'message': f'System health score {metrics.system_health_score:.1f} below target {self.targets.min_health_score}',
                'value': metrics.system_health_score,
                'threshold': self.targets.min_health_score
            })
        
        # Store alerts
        for alert in alerts:
            self._store_alert(alert)
    
    def _store_alert(self, alert: Dict[str, Any]):
        """Store performance alert"""
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            conn.execute("""
                INSERT INTO performance_alerts (
                    timestamp, alert_type, severity, message, metric_value, threshold_value
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                alert['type'],
                alert['severity'],
                alert['message'],
                alert['value'],
                alert['threshold']
            ))
            conn.commit()
            conn.close()
            
            logger.warning(f"PERFORMANCE ALERT: {alert['message']}")
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    def track_query_performance(self, query_name: str, execution_time: float, 
                              row_count: int = 0, cache_hit: bool = False, 
                              error_message: Optional[str] = None):
        """Track individual query performance"""
        self.query_tracker.record_query(
            query_name, execution_time, row_count, cache_hit, error_message
        )
        
        # Store in database for historical analysis
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            conn.execute("""
                INSERT INTO query_performance (
                    timestamp, query_name, execution_time_ms, row_count, cache_hit, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                query_name,
                execution_time * 1000,  # Convert to ms
                row_count,
                cache_hit,
                error_message
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing query performance: {e}")
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for specified time period"""
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            # Get recent metrics
            cursor = conn.execute("""
                SELECT 
                    AVG(query_execution_time_ms) as avg_query_time_ms,
                    AVG(cache_hit_rate_percent) as avg_cache_hit_rate,
                    AVG(cpu_usage_percent) as avg_cpu_usage,
                    AVG(memory_usage_mb) as avg_memory_usage,
                    AVG(system_health_score) as avg_health_score,
                    MAX(query_execution_time_ms) as max_query_time_ms,
                    MIN(system_health_score) as min_health_score,
                    COUNT(*) as measurement_count
                FROM performance_metrics 
                WHERE timestamp > ?
            """, (cutoff_time,))
            
            metrics_row = cursor.fetchone()
            
            # Get recent alerts
            cursor = conn.execute("""
                SELECT alert_type, severity, COUNT(*) as count
                FROM performance_alerts 
                WHERE timestamp > ? AND resolved = FALSE
                GROUP BY alert_type, severity
            """, (cutoff_time,))
            
            alerts = cursor.fetchall()
            conn.close()
            
            # Format results
            summary = {
                'time_period_hours': hours,
                'measurement_count': metrics_row[7] if metrics_row else 0,
                'performance': {
                    'avg_query_time_ms': round(metrics_row[0] or 0, 3),
                    'max_query_time_ms': round(metrics_row[5] or 0, 3),
                    'avg_cache_hit_rate_percent': round(metrics_row[1] or 0, 2),
                    'avg_cpu_usage_percent': round(metrics_row[2] or 0, 2),
                    'avg_memory_usage_mb': round(metrics_row[3] or 0, 2),
                    'avg_health_score': round(metrics_row[4] or 0, 2),
                    'min_health_score': round(metrics_row[6] or 0, 2)
                },
                'alerts': {
                    'total_active_alerts': sum(alert[2] for alert in alerts),
                    'by_type': {f"{alert[0]}_{alert[1]}": alert[2] for alert in alerts}
                },
                'targets': {
                    'max_query_time_ms': self.targets.max_query_time_seconds * 1000,
                    'target_cache_hit_rate_percent': self.targets.target_cache_hit_rate * 100,
                    'max_cpu_usage_percent': self.targets.max_cpu_usage,
                    'max_memory_usage_mb': self.targets.max_memory_usage_mb,
                    'min_health_score': self.targets.min_health_score
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return {'error': str(e)}
    
    def generate_performance_report(self, output_path: Optional[str] = None) -> str:
        """Generate detailed performance report"""
        try:
            # Get performance data
            summary_24h = self.get_performance_summary(24)
            summary_7d = self.get_performance_summary(168)  # 7 days
            
            # Generate report
            report = {
                'generated_at': datetime.now().isoformat(),
                'system_status': 'HEALTHY' if summary_24h['performance']['avg_health_score'] >= self.targets.min_health_score else 'DEGRADED',
                'performance_summary': {
                    'last_24_hours': summary_24h,
                    'last_7_days': summary_7d
                },
                'baseline_comparison': self._compare_with_baseline(summary_24h) if self.baseline_metrics else None,
                'recommendations': self._generate_recommendations(summary_24h, summary_7d)
            }
            
            # Save report if path specified
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"Performance report saved to {output_file}")
                return str(output_file)
            
            return json.dumps(report, indent=2)
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return f"Error generating report: {e}"
    
    def _compare_with_baseline(self, current_summary: Dict) -> Dict[str, Any]:
        """Compare current performance with baseline"""
        if not self.baseline_metrics:
            return {'error': 'No baseline metrics available'}
        
        current_perf = current_summary['performance']
        baseline_query_time_ms = self.baseline_metrics.query_execution_time * 1000
        baseline_cache_rate = self.baseline_metrics.cache_hit_rate * 100
        
        comparison = {
            'query_time': {
                'current_ms': current_perf['avg_query_time_ms'],
                'baseline_ms': baseline_query_time_ms,
                'change_percent': ((current_perf['avg_query_time_ms'] - baseline_query_time_ms) / baseline_query_time_ms * 100) if baseline_query_time_ms > 0 else 0
            },
            'cache_hit_rate': {
                'current_percent': current_perf['avg_cache_hit_rate_percent'],
                'baseline_percent': baseline_cache_rate,
                'change_percent': current_perf['avg_cache_hit_rate_percent'] - baseline_cache_rate
            },
            'health_score': {
                'current': current_perf['avg_health_score'],
                'baseline': self.baseline_metrics.system_health_score,
                'change': current_perf['avg_health_score'] - self.baseline_metrics.system_health_score
            }
        }
        
        return comparison
    
    def _generate_recommendations(self, summary_24h: Dict, summary_7d: Dict) -> List[str]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        perf_24h = summary_24h['performance']
        perf_7d = summary_7d['performance']
        
        # Query performance recommendations
        if perf_24h['avg_query_time_ms'] > self.targets.max_query_time_seconds * 1000:
            recommendations.append(f"Query execution time ({perf_24h['avg_query_time_ms']:.1f}ms) exceeds target. Consider optimizing slow queries or adding database indexes.")
        
        # Cache performance recommendations  
        if perf_24h['avg_cache_hit_rate_percent'] < self.targets.target_cache_hit_rate * 100:
            recommendations.append(f"Cache hit rate ({perf_24h['avg_cache_hit_rate_percent']:.1f}%) below target. Consider increasing cache size or adjusting TTL settings.")
        
        # System resource recommendations
        if perf_24h['avg_cpu_usage_percent'] > self.targets.max_cpu_usage:
            recommendations.append(f"CPU usage ({perf_24h['avg_cpu_usage_percent']:.1f}%) high. Consider query optimization or system scaling.")
        
        if perf_24h['avg_memory_usage_mb'] > self.targets.max_memory_usage_mb:
            recommendations.append(f"Memory usage ({perf_24h['avg_memory_usage_mb']:.0f}MB) exceeds target. Check for memory leaks or reduce cache size.")
        
        # Trend-based recommendations
        if perf_7d['measurement_count'] > 0:
            query_time_trend = ((perf_24h['avg_query_time_ms'] - perf_7d['avg_query_time_ms']) / perf_7d['avg_query_time_ms'] * 100) if perf_7d['avg_query_time_ms'] > 0 else 0
            if query_time_trend > 20:
                recommendations.append(f"Query performance degrading over 7 days (+{query_time_trend:.1f}%). Investigate recent changes.")
        
        # Active alerts recommendations
        if summary_24h['alerts']['total_active_alerts'] > 0:
            recommendations.append(f"{summary_24h['alerts']['total_active_alerts']} active performance alerts require attention.")
        
        # General recommendations if performance is excellent
        if not recommendations and perf_24h['avg_health_score'] > 95:
            recommendations.append("System performance is excellent. Consider documenting current configuration as baseline.")
        
        return recommendations
    
    def cleanup_old_data(self):
        """Clean up old performance data based on retention policy"""
        try:
            conn = sqlite3.connect(str(self.metrics_db_path))
            cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
            
            # Clean up old metrics
            cursor = conn.execute("DELETE FROM performance_metrics WHERE timestamp < ?", (cutoff_date,))
            metrics_deleted = cursor.rowcount
            
            # Clean up old query performance data
            cursor = conn.execute("DELETE FROM query_performance WHERE timestamp < ?", (cutoff_date,))
            queries_deleted = cursor.rowcount
            
            # Clean up resolved alerts older than 7 days
            alert_cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            cursor = conn.execute("DELETE FROM performance_alerts WHERE timestamp < ? AND resolved = TRUE", (alert_cutoff,))
            alerts_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up old data: {metrics_deleted} metrics, {queries_deleted} query records, {alerts_deleted} alerts")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")


class QueryPerformanceTracker:
    """Tracks individual query performance metrics"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.query_history = []
        self._lock = threading.Lock()
    
    def record_query(self, query_name: str, execution_time: float, 
                    row_count: int = 0, cache_hit: bool = False, 
                    error_message: Optional[str] = None):
        """Record query execution"""
        with self._lock:
            self.query_history.append({
                'timestamp': datetime.now(),
                'query_name': query_name,
                'execution_time': execution_time,
                'row_count': row_count,
                'cache_hit': cache_hit,
                'error': error_message is not None,
                'error_message': error_message
            })
            
            # Maintain window size
            if len(self.query_history) > self.window_size:
                self.query_history.pop(0)
    
    def get_recent_stats(self, minutes: int = 5) -> Dict[str, Any]:
        """Get recent query performance statistics"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            recent_queries = [
                q for q in self.query_history 
                if q['timestamp'] > cutoff_time
            ]
            
            if not recent_queries:
                return {
                    'total_queries': 0,
                    'avg_execution_time': 0.0,
                    'slow_queries': 0,
                    'error_rate': 0.0,
                    'cache_hit_rate': 0.0
                }
            
            total_queries = len(recent_queries)
            total_time = sum(q['execution_time'] for q in recent_queries)
            slow_queries = sum(1 for q in recent_queries if q['execution_time'] > 5.0)
            errors = sum(1 for q in recent_queries if q['error'])
            cache_hits = sum(1 for q in recent_queries if q['cache_hit'])
            
            return {
                'total_queries': total_queries,
                'avg_execution_time': total_time / total_queries,
                'slow_queries': slow_queries,
                'error_rate': errors / total_queries,
                'cache_hit_rate': cache_hits / total_queries if total_queries > 0 else 0
            }


class SystemResourceTracker:
    """Tracks system resource usage metrics"""
    
    def __init__(self):
        self.process = psutil.Process()
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current system resource statistics"""
        try:
            # Memory usage
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # CPU usage
            cpu_percent = self.process.cpu_percent()
            
            # Disk I/O
            io_stats = self.process.io_counters()
            disk_read_mb = io_stats.read_bytes / (1024 * 1024)
            disk_write_mb = io_stats.write_bytes / (1024 * 1024)
            
            return {
                'memory_mb': memory_mb,
                'cpu_percent': cpu_percent,
                'disk_read_mb': disk_read_mb,
                'disk_write_mb': disk_write_mb,
                'threads': self.process.num_threads()
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                'memory_mb': 0,
                'cpu_percent': 0,
                'disk_read_mb': 0,
                'disk_write_mb': 0,
                'threads': 0
            }
