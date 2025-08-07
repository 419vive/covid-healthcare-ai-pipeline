"""
Performance and stress tests for Veeva Data Quality System
Tests system performance under various load conditions
"""

import unittest
import time
import concurrent.futures
import psutil
import gc
import pandas as pd
from pathlib import Path
import sys
import subprocess
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager
from python.pipeline.query_executor import QueryExecutor


class PerformanceTestBase(unittest.TestCase):
    """Base class for performance tests"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.db_config = DatabaseConfig()
        self.pipeline_config = PipelineConfig()
        self.db_manager = DatabaseManager(self.db_config)
        self.query_executor = QueryExecutor(self.db_manager, self.pipeline_config)
        
        # Performance thresholds
        self.performance_thresholds = {
            'simple_query_max_time': 1.0,  # seconds
            'complex_query_max_time': 10.0,  # seconds
            'large_result_max_time': 30.0,  # seconds
            'parallel_query_max_time': 20.0,  # seconds
            'memory_usage_max_mb': 1024,  # MB
            'cpu_usage_max_percent': 80.0  # percent
        }
    
    def measure_performance(self, func, *args, **kwargs):
        """Measure performance metrics for a function"""
        # Get initial system metrics
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = psutil.cpu_percent(interval=None)
        
        # Execute function and measure time
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Get final system metrics
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        final_cpu = psutil.cpu_percent(interval=0.1)
        
        return {
            'result': result,
            'execution_time': execution_time,
            'memory_used_mb': final_memory - initial_memory,
            'peak_memory_mb': final_memory,
            'cpu_usage_percent': max(initial_cpu, final_cpu)
        }


class TestDatabasePerformance(PerformanceTestBase):
    """Test database performance under various conditions"""
    
    def test_simple_query_performance(self):
        """Test performance of simple queries"""
        queries = [
            "SELECT COUNT(*) FROM healthcare_providers",
            "SELECT COUNT(*) FROM healthcare_facilities", 
            "SELECT COUNT(*) FROM provider_facility_affiliations"
        ]
        
        for query in queries:
            with self.subTest(query=query):
                metrics = self.measure_performance(
                    self.db_manager.execute_query, query
                )
                
                # Verify performance thresholds
                self.assertLess(
                    metrics['execution_time'], 
                    self.performance_thresholds['simple_query_max_time'],
                    f"Query took {metrics['execution_time']:.2f}s, expected < {self.performance_thresholds['simple_query_max_time']}s"
                )
                
                self.assertTrue(metrics['result'].success, "Query should succeed")
    
    def test_complex_query_performance(self):
        """Test performance of complex analytical queries"""
        complex_query = """
        SELECT 
            p.provider_type,
            COUNT(*) as provider_count,
            COUNT(DISTINCT pfa.ccn) as facility_count,
            AVG(LENGTH(p.full_name)) as avg_name_length
        FROM healthcare_providers p
        LEFT JOIN provider_facility_affiliations pfa ON p.npi = pfa.npi
        GROUP BY p.provider_type
        ORDER BY provider_count DESC
        """
        
        metrics = self.measure_performance(
            self.db_manager.execute_query, complex_query
        )
        
        # Verify performance thresholds
        self.assertLess(
            metrics['execution_time'],
            self.performance_thresholds['complex_query_max_time'],
            f"Complex query took {metrics['execution_time']:.2f}s"
        )
        
        self.assertTrue(metrics['result'].success)
        self.assertGreater(metrics['result'].row_count, 0)
    
    def test_large_result_set_performance(self):
        """Test performance when handling large result sets"""
        large_query = "SELECT * FROM healthcare_providers LIMIT 10000"
        
        metrics = self.measure_performance(
            self.db_manager.execute_query, large_query
        )
        
        # Verify performance and memory usage
        self.assertLess(
            metrics['execution_time'],
            self.performance_thresholds['large_result_max_time']
        )
        
        self.assertLess(
            metrics['memory_used_mb'],
            self.performance_thresholds['memory_usage_max_mb']
        )
        
        self.assertTrue(metrics['result'].success)
        self.assertEqual(metrics['result'].row_count, 10000)
    
    def test_concurrent_query_performance(self):
        """Test performance with concurrent query execution"""
        queries = [
            "SELECT COUNT(*) FROM healthcare_providers",
            "SELECT COUNT(*) FROM healthcare_facilities",
            "SELECT COUNT(*) FROM provider_facility_affiliations",
            "SELECT provider_type, COUNT(*) FROM healthcare_providers GROUP BY provider_type",
            "SELECT state, COUNT(*) FROM healthcare_facilities GROUP BY state"
        ]
        
        def execute_query(query):
            return self.db_manager.execute_query(query)
        
        start_time = time.time()
        
        # Execute queries concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_query, query) for query in queries]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Verify all queries succeeded
        for result in results:
            self.assertTrue(result.success)
        
        # Verify concurrent execution is reasonably efficient
        self.assertLess(
            total_time,
            self.performance_thresholds['parallel_query_max_time']
        )
    
    def test_memory_usage_under_load(self):
        """Test memory usage under sustained load"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Execute multiple queries to stress memory
        for i in range(20):
            query = f"SELECT * FROM healthcare_providers LIMIT {1000 + i * 100}"
            result = self.db_manager.execute_query(query)
            self.assertTrue(result.success)
            
            # Force garbage collection
            if i % 5 == 0:
                gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        self.assertLess(
            memory_increase,
            self.performance_thresholds['memory_usage_max_mb'] / 2,
            f"Memory increased by {memory_increase:.2f} MB"
        )


class TestValidationPerformance(PerformanceTestBase):
    """Test validation query performance"""
    
    def test_single_validation_performance(self):
        """Test performance of individual validation queries"""
        catalog = self.query_executor.get_query_catalog()
        
        for query_info in catalog[:3]:  # Test first 3 queries
            rule_name = query_info['rule_name']
            
            with self.subTest(rule=rule_name):
                metrics = self.measure_performance(
                    self.query_executor.execute_single_query, rule_name
                )
                
                self.assertIsNotNone(metrics['result'])
                self.assertLess(
                    metrics['execution_time'],
                    self.performance_thresholds['complex_query_max_time']
                )
    
    def test_parallel_validation_performance(self):
        """Test performance of parallel validation execution"""
        metrics = self.measure_performance(
            self.query_executor.execute_all_queries, True  # parallel=True
        )
        
        results = metrics['result']
        
        # Verify all queries executed
        self.assertGreater(len(results), 0)
        
        # Verify reasonable execution time for parallel processing
        self.assertLess(
            metrics['execution_time'],
            self.performance_thresholds['parallel_query_max_time']
        )
        
        # Verify results quality
        successful_queries = sum(1 for r in results.values() if r.result.success)
        success_rate = successful_queries / len(results) if results else 0
        self.assertGreater(success_rate, 0.8, "At least 80% of queries should succeed")
    
    def test_validation_export_performance(self):
        """Test performance of result export functionality"""
        # Execute validation queries
        results = self.query_executor.execute_all_queries(parallel=True)
        
        # Create temporary output directory
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test export performance
            metrics = self.measure_performance(
                self.query_executor.export_query_results,
                results, temp_dir, ['json', 'csv', 'xlsx']
            )
            
            # Verify export succeeded and was reasonably fast
            exported_files = metrics['result']
            self.assertEqual(len(exported_files), 3)  # json, csv, xlsx
            
            # Export should be reasonably fast
            self.assertLess(metrics['execution_time'], 30.0)


class TestCLIPerformance(PerformanceTestBase):
    """Test CLI command performance"""
    
    def test_cli_status_performance(self):
        """Test performance of status command"""
        cli_script = project_root / "python" / "main.py"
        
        start_time = time.time()
        result = subprocess.run(
            ["python", str(cli_script), "status"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        execution_time = time.time() - start_time
        
        self.assertEqual(result.returncode, 0)
        self.assertLess(execution_time, 5.0)  # Status should be fast
        self.assertIn("Database Accessible", result.stdout)
    
    def test_cli_catalog_performance(self):
        """Test performance of catalog command"""
        cli_script = project_root / "python" / "main.py"
        
        start_time = time.time()
        result = subprocess.run(
            ["python", str(cli_script), "catalog"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        execution_time = time.time() - start_time
        
        self.assertEqual(result.returncode, 0)
        self.assertLess(execution_time, 10.0)  # Catalog should be reasonably fast
        self.assertIn("Validation Rules Catalog", result.stdout)
    
    def test_cli_validation_performance(self):
        """Test performance of validation command"""
        cli_script = project_root / "python" / "main.py"
        
        start_time = time.time()
        result = subprocess.run(
            ["python", str(cli_script), "validate", "--rule", "validation_summary"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        execution_time = time.time() - start_time
        
        self.assertEqual(result.returncode, 0)
        self.assertLess(execution_time, 30.0)  # Single validation should be reasonably fast
        self.assertIn("Validation Results Summary", result.stdout)


class TestStressTests(PerformanceTestBase):
    """Stress tests for system limits"""
    
    def test_rapid_query_execution(self):
        """Test system under rapid query execution"""
        query_count = 100
        errors = 0
        total_time = 0
        
        start_time = time.time()
        
        for i in range(query_count):
            try:
                result = self.db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
                if not result.success:
                    errors += 1
                total_time += result.execution_time
            except Exception:
                errors += 1
        
        end_time = time.time()
        
        # Verify system handled rapid queries well
        error_rate = errors / query_count
        self.assertLess(error_rate, 0.05, f"Error rate {error_rate:.2%} too high")
        
        avg_query_time = total_time / query_count
        self.assertLess(avg_query_time, 0.1, f"Average query time {avg_query_time:.3f}s too slow")
        
        total_wall_time = end_time - start_time
        self.assertLess(total_wall_time, 60.0, "Stress test took too long")
    
    def test_memory_leak_detection(self):
        """Test for potential memory leaks"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Execute many operations to detect leaks
        for iteration in range(50):
            # Execute query
            result = self.db_manager.execute_query(
                "SELECT * FROM healthcare_providers LIMIT 100"
            )
            self.assertTrue(result.success)
            
            # Execute validation
            validation_result = self.query_executor.execute_single_query("validation_summary")
            self.assertIsNotNone(validation_result)
            
            # Force garbage collection every 10 iterations
            if iteration % 10 == 0:
                gc.collect()
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                # Memory should not grow unreasonably
                self.assertLess(
                    memory_increase, 
                    500,  # 500MB max increase
                    f"Potential memory leak detected: {memory_increase:.2f} MB increase"
                )
    
    def test_database_connection_stress(self):
        """Test database connection handling under stress"""
        def create_and_query():
            """Create DB manager and execute query"""
            try:
                db_manager = DatabaseManager(self.db_config)
                result = db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
                return result.success
            except Exception:
                return False
        
        # Test concurrent database connections
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_query) for _ in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Most connections should succeed
        success_rate = sum(results) / len(results)
        self.assertGreater(
            success_rate, 
            0.9, 
            f"Connection success rate {success_rate:.2%} too low"
        )


class TestPerformanceReporting(unittest.TestCase):
    """Test performance reporting and metrics"""
    
    def test_generate_performance_report(self):
        """Test generation of performance report"""
        report_data = {
            'test_suite': 'performance_tests',
            'timestamp': pd.Timestamp.now(),
            'database_size_mb': 50.0,
            'total_records': 125531,
            'query_performance': {
                'simple_queries_avg_time': 0.05,
                'complex_queries_avg_time': 2.1,
                'parallel_execution_time': 8.5
            },
            'memory_usage': {
                'peak_memory_mb': 256,
                'average_memory_mb': 128
            },
            'system_metrics': {
                'cpu_usage_percent': 45.2,
                'disk_io_rate': 'normal'
            }
        }
        
        # Verify report structure
        self.assertIn('test_suite', report_data)
        self.assertIn('query_performance', report_data)
        self.assertIn('memory_usage', report_data)
        self.assertIn('system_metrics', report_data)
        
        # Verify reasonable values
        self.assertLess(report_data['query_performance']['simple_queries_avg_time'], 1.0)
        self.assertLess(report_data['memory_usage']['peak_memory_mb'], 1024)
        self.assertLess(report_data['system_metrics']['cpu_usage_percent'], 100.0)


if __name__ == '__main__':
    unittest.main()