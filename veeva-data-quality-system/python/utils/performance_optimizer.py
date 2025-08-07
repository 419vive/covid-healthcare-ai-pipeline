"""
Performance Optimization Manager for Veeva Data Quality System
Implements comprehensive performance enhancements for Phase 3 optimization
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from contextlib import contextmanager

from .database import DatabaseManager
from .query_cache import QueryResultCache

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Results from a performance optimization operation"""
    operation: str
    success: bool
    execution_time: float
    details: str
    metrics_before: Optional[Dict[str, Any]] = None
    metrics_after: Optional[Dict[str, Any]] = None


class PerformanceOptimizer:
    """
    Comprehensive performance optimization manager
    
    Features:
    - Database optimization (indexes, PRAGMA settings)
    - Query performance analysis
    - Connection pooling optimization
    - Memory usage optimization
    - Automated performance monitoring
    """
    
    def __init__(self, db_manager: DatabaseManager, sql_dir: str):
        self.db_manager = db_manager
        self.sql_dir = Path(sql_dir)
        self.optimization_history: List[OptimizationResult] = []
        
        logger.info("PerformanceOptimizer initialized")
    
    @contextmanager
    def get_connection(self):
        """Get optimized database connection"""
        with self.db_manager.get_connection() as conn:
            # Apply performance optimizations per connection
            self._apply_connection_optimizations(conn)
            yield conn
    
    def _apply_connection_optimizations(self, conn):
        """Apply per-connection performance optimizations"""
        performance_pragmas = [
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL", 
            "PRAGMA cache_size = -65536",  # 64MB cache
            "PRAGMA temp_store = MEMORY",
            "PRAGMA mmap_size = 536870912",  # 512MB
            "PRAGMA threads = 4"
        ]
        
        for pragma in performance_pragmas:
            try:
                conn.execute(pragma)
            except Exception as e:
                logger.warning(f"Failed to apply pragma {pragma}: {e}")
    
    def apply_performance_indexes(self) -> OptimizationResult:
        """Apply performance optimization indexes"""
        start_time = time.time()
        
        try:
            # Load and execute performance indexes
            indexes_file = self.sql_dir / "01_schema" / "performance_indexes.sql"
            
            if not indexes_file.exists():
                return OptimizationResult(
                    operation="apply_performance_indexes",
                    success=False,
                    execution_time=time.time() - start_time,
                    details=f"Performance indexes file not found: {indexes_file}"
                )
            
            with open(indexes_file, 'r') as f:
                indexes_sql = f.read()
            
            # Get metrics before optimization
            metrics_before = self._get_database_metrics()
            
            # Execute index creation
            with self.get_connection() as conn:
                # Split SQL into individual statements
                statements = self._split_sql_statements(indexes_sql)
                
                executed_statements = 0
                for statement in statements:
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            conn.execute(statement)
                            executed_statements += 1
                        except Exception as e:
                            logger.warning(f"Failed to execute statement: {e}")
                
                conn.commit()
            
            # Get metrics after optimization
            metrics_after = self._get_database_metrics()
            
            execution_time = time.time() - start_time
            
            result = OptimizationResult(
                operation="apply_performance_indexes",
                success=True,
                execution_time=execution_time,
                details=f"Applied {executed_statements} index optimization statements",
                metrics_before=metrics_before,
                metrics_after=metrics_after
            )
            
            self.optimization_history.append(result)
            
            logger.info(f"Performance indexes applied in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = OptimizationResult(
                operation="apply_performance_indexes",
                success=False,
                execution_time=execution_time,
                details=f"Error applying performance indexes: {e}"
            )
            
            self.optimization_history.append(result)
            logger.error(f"Failed to apply performance indexes: {e}")
            return result
    
    def optimize_database_configuration(self) -> OptimizationResult:
        """Optimize SQLite configuration for performance"""
        start_time = time.time()
        
        try:
            optimization_commands = [
                "ANALYZE",
                "PRAGMA optimize",
                "VACUUM"  # Be careful with this on large databases
            ]
            
            metrics_before = self._get_database_metrics()
            
            with self.get_connection() as conn:
                for command in optimization_commands:
                    try:
                        logger.info(f"Executing: {command}")
                        conn.execute(command)
                    except Exception as e:
                        logger.warning(f"Optimization command failed {command}: {e}")
                
                conn.commit()
            
            metrics_after = self._get_database_metrics()
            execution_time = time.time() - start_time
            
            result = OptimizationResult(
                operation="optimize_database_configuration",
                success=True,
                execution_time=execution_time,
                details=f"Applied database optimization commands",
                metrics_before=metrics_before,
                metrics_after=metrics_after
            )
            
            self.optimization_history.append(result)
            
            logger.info(f"Database configuration optimized in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = OptimizationResult(
                operation="optimize_database_configuration",
                success=False,
                execution_time=execution_time,
                details=f"Database optimization failed: {e}"
            )
            
            self.optimization_history.append(result)
            logger.error(f"Database optimization failed: {e}")
            return result
    
    def benchmark_query_performance(self, queries: Dict[str, str], 
                                  iterations: int = 3) -> Dict[str, Dict[str, float]]:
        """Benchmark query performance"""
        logger.info(f"Benchmarking {len(queries)} queries with {iterations} iterations each")
        
        benchmarks = {}
        
        for query_name, query_sql in queries.items():
            times = []
            
            # Warm-up run
            try:
                with self.get_connection() as conn:
                    pd.read_sql_query(query_sql, conn)
            except Exception as e:
                logger.error(f"Warm-up failed for {query_name}: {e}")
                continue
            
            # Benchmark runs
            for i in range(iterations):
                start_time = time.time()
                try:
                    with self.get_connection() as conn:
                        result = pd.read_sql_query(query_sql, conn)
                        row_count = len(result)
                    
                    execution_time = time.time() - start_time
                    times.append(execution_time)
                    
                except Exception as e:
                    logger.error(f"Benchmark iteration {i+1} failed for {query_name}: {e}")
                    times.append(float('inf'))
            
            if times:
                benchmarks[query_name] = {
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'row_count': row_count if 'row_count' in locals() else 0,
                    'performance_grade': self._grade_performance(sum(times) / len(times))
                }
                
                logger.info(f"{query_name}: {benchmarks[query_name]['avg_time']:.3f}s avg")
        
        return benchmarks
    
    def run_comprehensive_optimization(self) -> Dict[str, OptimizationResult]:
        """Run all performance optimizations"""
        logger.info("Starting comprehensive performance optimization")
        
        optimizations = {}
        
        # Step 1: Apply performance indexes
        optimizations['indexes'] = self.apply_performance_indexes()
        
        # Step 2: Optimize database configuration
        optimizations['configuration'] = self.optimize_database_configuration()
        
        # Step 3: Additional optimizations based on database size
        db_size_mb = self._get_database_size_mb()
        if db_size_mb > 100:
            optimizations['large_db'] = self._optimize_for_large_database()
        
        # Log summary
        successful_ops = sum(1 for result in optimizations.values() if result.success)
        total_time = sum(result.execution_time for result in optimizations.values())
        
        logger.info(f"Comprehensive optimization completed: {successful_ops}/{len(optimizations)} successful, {total_time:.2f}s total")
        
        return optimizations
    
    def _optimize_for_large_database(self) -> OptimizationResult:
        """Additional optimizations for large databases"""
        start_time = time.time()
        
        try:
            # Increase cache and optimize for larger datasets
            large_db_pragmas = [
                "PRAGMA cache_size = -131072",  # 128MB cache
                "PRAGMA mmap_size = 1073741824",  # 1GB mmap
                "PRAGMA temp_store = MEMORY"
            ]
            
            with self.get_connection() as conn:
                for pragma in large_db_pragmas:
                    conn.execute(pragma)
                conn.commit()
            
            execution_time = time.time() - start_time
            
            result = OptimizationResult(
                operation="optimize_for_large_database",
                success=True,
                execution_time=execution_time,
                details="Applied large database optimizations"
            )
            
            logger.info("Large database optimizations applied")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = OptimizationResult(
                operation="optimize_for_large_database",
                success=False,
                execution_time=execution_time,
                details=f"Large database optimization failed: {e}"
            )
            
            logger.error(f"Large database optimization failed: {e}")
            return result
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Get current database performance metrics"""
        try:
            with self.get_connection() as conn:
                # Get basic database info
                tables_result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """).fetchall()
                
                # Get index count
                indexes_result = conn.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """).fetchone()
                
                # Get page info
                page_info = conn.execute("PRAGMA page_count").fetchone()
                page_size = conn.execute("PRAGMA page_size").fetchone()
                
                # Test query performance
                test_start = time.time()
                conn.execute("SELECT COUNT(*) FROM healthcare_providers").fetchone()
                test_time = time.time() - test_start
                
                return {
                    'table_count': len(tables_result),
                    'index_count': indexes_result[0] if indexes_result else 0,
                    'page_count': page_info[0] if page_info else 0,
                    'page_size': page_size[0] if page_size else 0,
                    'test_query_time': test_time,
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")
            return {'error': str(e)}
    
    def _get_database_size_mb(self) -> float:
        """Get database file size in MB"""
        try:
            db_path = Path(self.db_manager.config.db_path)
            if db_path.exists():
                return db_path.stat().st_size / (1024 * 1024)
        except Exception as e:
            logger.error(f"Failed to get database size: {e}")
        return 0.0
    
    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """Split SQL content into individual statements"""
        # Simple SQL statement splitter
        statements = []
        current_statement = []
        
        for line in sql_content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('--'):
                continue
            
            current_statement.append(line)
            
            # Check if statement is complete
            if line.endswith(';'):
                statements.append('\n'.join(current_statement))
                current_statement = []
        
        # Add any remaining statement
        if current_statement:
            statements.append('\n'.join(current_statement))
        
        return statements
    
    def _grade_performance(self, execution_time: float) -> str:
        """Grade query performance"""
        if execution_time < 0.1:
            return 'EXCELLENT'
        elif execution_time < 0.5:
            return 'GOOD'
        elif execution_time < 2.0:
            return 'ACCEPTABLE'
        elif execution_time < 5.0:
            return 'NEEDS_IMPROVEMENT'
        else:
            return 'POOR'
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        return {
            'optimization_history': [
                {
                    'operation': result.operation,
                    'success': result.success,
                    'execution_time': result.execution_time,
                    'details': result.details
                }
                for result in self.optimization_history
            ],
            'current_metrics': self._get_database_metrics(),
            'database_size_mb': self._get_database_size_mb(),
            'total_optimizations': len(self.optimization_history),
            'successful_optimizations': sum(1 for r in self.optimization_history if r.success)
        }


class PerformanceMonitor:
    """Continuous performance monitoring"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.performance_log: List[Dict[str, Any]] = []
    
    def monitor_query(self, query_name: str, execution_time: float, 
                     row_count: int, success: bool):
        """Log query performance metrics"""
        self.performance_log.append({
            'timestamp': time.time(),
            'query_name': query_name,
            'execution_time': execution_time,
            'row_count': row_count,
            'success': success,
            'performance_grade': self._grade_performance(execution_time)
        })
        
        # Alert on poor performance
        if execution_time > 5.0:
            logger.warning(f"SLOW QUERY ALERT: {query_name} took {execution_time:.2f}s")
    
    def _grade_performance(self, execution_time: float) -> str:
        """Grade query performance"""
        if execution_time < 0.1:
            return 'EXCELLENT'
        elif execution_time < 0.5:
            return 'GOOD'
        elif execution_time < 2.0:
            return 'ACCEPTABLE'
        elif execution_time < 5.0:
            return 'NEEDS_IMPROVEMENT'
        else:
            return 'POOR'
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for last N hours"""
        cutoff_time = time.time() - (hours * 3600)
        recent_logs = [log for log in self.performance_log if log['timestamp'] > cutoff_time]
        
        if not recent_logs:
            return {'message': 'No recent performance data'}
        
        # Calculate statistics
        avg_time = sum(log['execution_time'] for log in recent_logs) / len(recent_logs)
        slow_queries = [log for log in recent_logs if log['execution_time'] > 5.0]
        
        grade_counts = {}
        for log in recent_logs:
            grade = log['performance_grade']
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        
        return {
            'total_queries': len(recent_logs),
            'avg_execution_time': avg_time,
            'slow_queries_count': len(slow_queries),
            'performance_grades': grade_counts,
            'slowest_queries': sorted(recent_logs, key=lambda x: x['execution_time'], reverse=True)[:5]
        }