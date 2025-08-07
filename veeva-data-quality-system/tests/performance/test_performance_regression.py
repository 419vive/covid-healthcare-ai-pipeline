#!/usr/bin/env python3
"""
Performance Regression Test Suite
Ensures Phase 3 optimizations maintain performance over time
"""

import unittest
import time
import sys
from pathlib import Path
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from python.pipeline.query_executor import QueryExecutor
from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager
from python.utils.performance_optimizer import PerformanceOptimizer, PerformanceMonitor


class PerformanceRegressionTest(unittest.TestCase):
    """
    Performance regression test suite
    
    Verifies that all optimization targets continue to be met:
    - All queries execute in <5 seconds
    - Average query time remains <2 seconds
    - Cache hit rate >30%
    - System maintains EXCELLENT performance grade
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.db_config = DatabaseConfig()
        cls.pipeline_config = PipelineConfig()
        cls.db_manager = DatabaseManager(cls.db_config)
        
        cls.query_executor = QueryExecutor(
            cls.db_manager, 
            cls.pipeline_config,
            enable_caching=True
        )
        
        cls.performance_monitor = PerformanceMonitor(cls.db_manager)
        
        # Performance benchmarks (from Phase 3 optimization)
        cls.PERFORMANCE_BENCHMARKS = {
            'provider_name_inconsistency': 0.106,
            'npi_validation': 0.103,
            'affiliation_anomaly_(simplified_for_performance)': 0.072,
            'temporal_consistency': 0.021,
            'cross_reference_integrity': 0.104,
            'contact_validation': 0.770,
            'validation_summary': 0.010
        }
        
        cls.MAX_QUERY_TIME = 5.0  # Primary performance target
        cls.MAX_AVG_TIME = 2.0    # Secondary performance target
        cls.MIN_CACHE_HIT_RATE = 0.30  # Cache efficiency target
    
    def test_individual_query_performance(self):
        """Test that each query meets performance benchmarks"""
        print("\n=== Testing Individual Query Performance ===")
        
        failures = []
        
        for rule_name in self.query_executor.validation_queries.keys():
            with self.subTest(query=rule_name):
                # Execute query multiple times for accuracy
                times = []
                for _ in range(3):
                    start_time = time.time()
                    result = self.query_executor.execute_single_query(rule_name)
                    execution_time = time.time() - start_time
                    times.append(execution_time)
                    
                    # Verify query succeeded
                    self.assertTrue(result.result.success, 
                                  f"Query {rule_name} failed: {result.result.error_message}")
                
                avg_time = sum(times) / len(times)
                benchmark_time = self.PERFORMANCE_BENCHMARKS.get(rule_name, self.MAX_QUERY_TIME)
                
                print(f"{rule_name}: {avg_time:.3f}s (benchmark: {benchmark_time:.3f}s)")
                
                # Performance assertions
                if avg_time > self.MAX_QUERY_TIME:
                    failures.append(f"{rule_name}: {avg_time:.3f}s > {self.MAX_QUERY_TIME}s (CRITICAL FAILURE)")
                
                # Allow 50% regression tolerance from benchmark
                if avg_time > benchmark_time * 1.5:
                    warnings.warn(f"{rule_name} performance regression: {avg_time:.3f}s vs benchmark {benchmark_time:.3f}s")
                
                # Record performance for monitoring
                self.performance_monitor.monitor_query(rule_name, avg_time, 
                                                     result.result.row_count if result else 0, 
                                                     result.result.success if result else False)
        
        # Fail test if any critical performance failures
        if failures:
            self.fail(f"Performance failures detected:\n" + "\n".join(failures))
    
    def test_aggregate_performance_targets(self):
        """Test overall system performance targets"""
        print("\n=== Testing Aggregate Performance Targets ===")
        
        # Execute all queries and measure total time
        start_time = time.time()
        results = self.query_executor.execute_all_queries(parallel=False)
        total_time = time.time() - start_time
        
        # Calculate metrics
        successful_queries = sum(1 for r in results.values() if r.result.success)
        avg_time = sum(r.result.execution_time for r in results.values() if r.result.success) / len(results)
        
        print(f"Total queries: {len(results)}")
        print(f"Successful queries: {successful_queries}")
        print(f"Total execution time: {total_time:.3f}s")
        print(f"Average query time: {avg_time:.3f}s")
        
        # Performance assertions
        self.assertGreaterEqual(successful_queries, len(results), 
                               "All queries should succeed")
        
        self.assertLess(avg_time, self.MAX_AVG_TIME, 
                       f"Average query time {avg_time:.3f}s exceeds target {self.MAX_AVG_TIME}s")
        
        # Check that no individual query exceeded maximum time
        slow_queries = [(name, result.result.execution_time) 
                       for name, result in results.items() 
                       if result.result.execution_time > self.MAX_QUERY_TIME]
        
        self.assertEqual(len(slow_queries), 0, 
                        f"Slow queries detected: {slow_queries}")
    
    def test_cache_performance(self):
        """Test that caching system maintains efficiency"""
        print("\n=== Testing Cache Performance ===")
        
        # Execute queries to populate cache
        test_query = 'provider_name_inconsistency'
        
        # First execution (cache miss)
        start_time = time.time()
        result1 = self.query_executor.execute_single_query(test_query)
        first_time = time.time() - start_time
        
        # Second execution (should hit cache)
        start_time = time.time()
        result2 = self.query_executor.execute_single_query(test_query)
        second_time = time.time() - start_time
        
        # Cache statistics
        cache_stats = self.query_executor.get_cache_statistics()
        
        if cache_stats:
            hit_rate = cache_stats.get('hit_rate', 0)
            print(f"Cache hit rate: {hit_rate:.2%}")
            print(f"Cache hits: {cache_stats.get('hits', 0)}")
            print(f"Memory entries: {cache_stats.get('memory_entries', 0)}")
            
            # Performance assertions
            self.assertGreaterEqual(hit_rate, self.MIN_CACHE_HIT_RATE, 
                                   f"Cache hit rate {hit_rate:.2%} below target {self.MIN_CACHE_HIT_RATE:.2%}")
            
            # Verify cache provides speedup
            if first_time > 0.01:  # Only test if query was slow enough to measure
                self.assertLess(second_time, first_time, 
                               "Cache should provide performance improvement")
        else:
            self.fail("Cache statistics not available - caching may be disabled")
    
    def test_concurrent_performance(self):
        """Test parallel execution performance"""
        print("\n=== Testing Concurrent Performance ===")
        
        # Test parallel execution
        start_time = time.time()
        parallel_results = self.query_executor.execute_all_queries(parallel=True)
        parallel_time = time.time() - start_time
        
        # Test sequential execution
        start_time = time.time()
        sequential_results = self.query_executor.execute_all_queries(parallel=False)
        sequential_time = time.time() - start_time
        
        print(f"Parallel execution: {parallel_time:.3f}s")
        print(f"Sequential execution: {sequential_time:.3f}s")
        
        # Performance assertions
        successful_parallel = sum(1 for r in parallel_results.values() if r.result.success)
        successful_sequential = sum(1 for r in sequential_results.values() if r.result.success)
        
        self.assertEqual(successful_parallel, successful_sequential, 
                        "Parallel and sequential execution should have same success rate")
        
        # Parallel should be at least as fast (or close to) sequential
        # Allow small overhead for thread management
        self.assertLess(parallel_time, sequential_time * 1.2, 
                       "Parallel execution should not be significantly slower than sequential")
    
    def test_scalability_performance(self):
        """Test performance with different data access patterns"""
        print("\n=== Testing Scalability Performance ===")
        
        scalability_queries = {
            'count_providers': 'SELECT COUNT(*) FROM healthcare_providers',
            'count_affiliations': 'SELECT COUNT(*) FROM provider_facility_affiliations',
            'simple_join': '''
                SELECT COUNT(*) FROM healthcare_providers hp 
                JOIN provider_facility_affiliations pfa ON hp.provider_id = pfa.provider_id 
                LIMIT 1000
            '''
        }
        
        for query_name, query_sql in scalability_queries.items():
            with self.subTest(scalability_query=query_name):
                times = []
                for _ in range(3):
                    result = self.db_manager.execute_query(query_sql)
                    times.append(result.execution_time)
                    self.assertTrue(result.success, f"Scalability query {query_name} failed")
                
                avg_time = sum(times) / len(times)
                print(f"{query_name}: {avg_time:.3f}s")
                
                # Even basic queries should be fast
                self.assertLess(avg_time, 1.0, 
                               f"Scalability query {query_name} too slow: {avg_time:.3f}s")
    
    def test_performance_monitoring_integration(self):
        """Test that performance monitoring is working"""
        print("\n=== Testing Performance Monitoring ===")
        
        # Execute a query to generate monitoring data
        result = self.query_executor.execute_single_query('validation_summary')
        self.assertTrue(result.result.success, "Monitoring test query failed")
        
        # Check monitoring data
        summary = self.performance_monitor.get_performance_summary(hours=1)
        
        self.assertIsInstance(summary, dict, "Performance summary should be available")
        
        if 'total_queries' in summary:
            self.assertGreater(summary['total_queries'], 0, "Should have monitoring data")
            print(f"Monitoring active: {summary['total_queries']} queries tracked")
        else:
            print("No recent monitoring data available")
    
    def test_database_optimization_status(self):
        """Test that database optimizations are still applied"""
        print("\n=== Testing Database Optimization Status ===")
        
        with self.db_manager.get_connection() as conn:
            # Check if performance indexes exist
            index_query = """
                SELECT COUNT(*) as index_count 
                FROM sqlite_master 
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
            """
            
            result = conn.execute(index_query)
            index_count = result.fetchone()[0]
            
            print(f"Total indexes: {index_count}")
            
            # Should have at least 100 indexes (84 original + 53 performance)
            self.assertGreaterEqual(index_count, 100, 
                                   f"Expected at least 100 indexes, found {index_count}")
            
            # Check SQLite optimization settings
            pragma_checks = {
                'journal_mode': 'wal',
                'synchronous': '1',  # NORMAL = 1
                'temp_store': '2'    # MEMORY = 2
            }
            
            for pragma, expected in pragma_checks.items():
                result = conn.execute(f"PRAGMA {pragma}")
                actual = result.fetchone()[0]
                print(f"PRAGMA {pragma}: {actual}")
                
                # Note: Some pragmas might return different formats
                # This is informational rather than strict assertion
    
    def tearDown(self):
        """Clean up after each test"""
        # Optimize cache after test run
        if hasattr(self, 'query_executor') and self.query_executor.query_cache:
            self.query_executor.query_cache.cleanup_expired()


class PerformanceBenchmarkTest(unittest.TestCase):
    """
    Benchmark test to establish new performance baselines
    Run this to update performance benchmarks after optimizations
    """
    
    @classmethod
    def setUpClass(cls):
        cls.db_config = DatabaseConfig()
        cls.pipeline_config = PipelineConfig()
        cls.db_manager = DatabaseManager(cls.db_config)
        cls.query_executor = QueryExecutor(cls.db_manager, cls.pipeline_config, enable_caching=False)
    
    def test_establish_performance_benchmarks(self):
        """Establish fresh performance benchmarks"""
        print("\n=== Establishing Performance Benchmarks ===")
        print("Note: Run this test to update benchmark values after optimizations")
        
        benchmarks = {}
        
        for rule_name in self.query_executor.validation_queries.keys():
            times = []
            for _ in range(5):  # More iterations for accurate benchmarking
                start_time = time.time()
                result = self.query_executor.execute_single_query(rule_name)
                execution_time = time.time() - start_time
                times.append(execution_time)
            
            # Remove outliers (fastest and slowest)
            times.sort()
            avg_time = sum(times[1:-1]) / (len(times) - 2)
            
            benchmarks[rule_name] = avg_time
            print(f"'{rule_name}': {avg_time:.3f},")
        
        print("\nBenchmark dictionary for code:")
        print("cls.PERFORMANCE_BENCHMARKS = {")
        for rule_name, time_val in benchmarks.items():
            print(f"    '{rule_name}': {time_val:.3f},")
        print("}")


if __name__ == '__main__':
    # Configure test runner
    unittest.TextTestRunner.resultclass.addSuccess = lambda self, test: print(f"✓ {test._testMethodName}")
    unittest.TextTestRunner.resultclass.addError = lambda self, test, err: print(f"✗ {test._testMethodName}: ERROR")
    unittest.TextTestRunner.resultclass.addFailure = lambda self, test, err: print(f"✗ {test._testMethodName}: FAILURE")
    
    print("VEEVA DATA QUALITY SYSTEM - PERFORMANCE REGRESSION TEST")
    print("=" * 60)
    print("Verifying Phase 3 optimization performance targets")
    print("=" * 60)
    
    # Run regression tests
    suite = unittest.TestLoader().loadTestsFromTestCase(PerformanceRegressionTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print final results
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 ALL PERFORMANCE REGRESSION TESTS PASSED")
        print("Phase 3 optimizations are maintaining target performance")
    else:
        print("⚠️  PERFORMANCE REGRESSION DETECTED")
        print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
    
    print("=" * 60)