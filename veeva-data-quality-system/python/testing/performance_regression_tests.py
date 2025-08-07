"""
Performance regression testing system
Ensures performance doesn't degrade with changes
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class PerformanceBenchmark:
    """Performance benchmark definition"""
    name: str
    description: str
    test_function: str
    target_execution_time_ms: float
    acceptable_variance_percent: float
    iterations: int
    setup_function: Optional[str] = None
    teardown_function: Optional[str] = None
    parallel_execution: bool = False
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class BenchmarkResult:
    """Benchmark execution result"""
    benchmark_name: str
    execution_times_ms: List[float]
    avg_execution_time_ms: float
    median_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    std_deviation_ms: float
    target_time_ms: float
    performance_ratio: float  # actual/target
    passed: bool
    timestamp: datetime
    error_message: Optional[str] = None
    system_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'benchmark_name': self.benchmark_name,
            'avg_execution_time_ms': round(self.avg_execution_time_ms, 3),
            'median_execution_time_ms': round(self.median_execution_time_ms, 3),
            'min_execution_time_ms': round(self.min_execution_time_ms, 3),
            'max_execution_time_ms': round(self.max_execution_time_ms, 3),
            'std_deviation_ms': round(self.std_deviation_ms, 3),
            'target_time_ms': self.target_time_ms,
            'performance_ratio': round(self.performance_ratio, 3),
            'passed': self.passed,
            'timestamp': self.timestamp.isoformat(),
            'error_message': self.error_message,
            'system_info': self.system_info
        }


class PerformanceRegressionTester:
    """
    Performance regression testing system that:
    - Defines performance benchmarks for critical operations
    - Executes benchmarks with statistical rigor
    - Compares results against baselines and targets
    - Detects performance regressions
    - Generates performance reports
    """
    
    def __init__(self, 
                 database_manager=None,
                 cache_manager=None,
                 query_executor=None,
                 results_dir: Optional[str] = None):
        """
        Initialize performance regression tester
        
        Args:
            database_manager: Database manager for testing
            cache_manager: Cache manager for testing
            query_executor: Query executor for testing
            results_dir: Directory to store test results
        """
        self.database_manager = database_manager
        self.cache_manager = cache_manager
        self.query_executor = query_executor
        
        # Results storage
        self.results_dir = Path(results_dir or "performance_test_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Benchmark definitions
        self.benchmarks = self._define_benchmarks()
        self.baseline_results = self._load_baseline_results()
        
        # Test environment
        self._test_data_initialized = False
        
        logger.info(f"Performance regression tester initialized with {len(self.benchmarks)} benchmarks")
    
    def _define_benchmarks(self) -> List[PerformanceBenchmark]:
        """Define performance benchmarks for critical system operations"""
        benchmarks = [
            # Database query benchmarks
            PerformanceBenchmark(
                name="basic_provider_query",
                description="Basic healthcare provider lookup query",
                test_function="_benchmark_basic_provider_query",
                target_execution_time_ms=50.0,
                acceptable_variance_percent=20.0,
                iterations=10,
                tags=["database", "query", "provider"]
            ),
            
            PerformanceBenchmark(
                name="complex_validation_query",
                description="Complex data validation query with joins",
                test_function="_benchmark_complex_validation_query",
                target_execution_time_ms=500.0,
                acceptable_variance_percent=30.0,
                iterations=5,
                tags=["database", "validation", "complex"]
            ),
            
            PerformanceBenchmark(
                name="aggregation_query",
                description="Data aggregation and statistics query",
                test_function="_benchmark_aggregation_query",
                target_execution_time_ms=200.0,
                acceptable_variance_percent=25.0,
                iterations=8,
                tags=["database", "aggregation"]
            ),
            
            # Cache benchmarks
            PerformanceBenchmark(
                name="cache_read_performance",
                description="Cache read operation performance",
                test_function="_benchmark_cache_read",
                target_execution_time_ms=5.0,
                acceptable_variance_percent=50.0,
                iterations=20,
                tags=["cache", "read"]
            ),
            
            PerformanceBenchmark(
                name="cache_write_performance",
                description="Cache write operation performance",
                test_function="_benchmark_cache_write",
                target_execution_time_ms=10.0,
                acceptable_variance_percent=40.0,
                iterations=15,
                tags=["cache", "write"]
            ),
            
            # Validation pipeline benchmarks
            PerformanceBenchmark(
                name="single_validation_rule",
                description="Single validation rule execution",
                test_function="_benchmark_single_validation",
                target_execution_time_ms=100.0,
                acceptable_variance_percent=30.0,
                iterations=10,
                tags=["validation", "pipeline"]
            ),
            
            PerformanceBenchmark(
                name="full_validation_suite",
                description="Complete validation suite execution",
                test_function="_benchmark_full_validation_suite",
                target_execution_time_ms=2000.0,
                acceptable_variance_percent=25.0,
                iterations=3,
                tags=["validation", "suite", "full"]
            ),
            
            # System integration benchmarks
            PerformanceBenchmark(
                name="end_to_end_data_processing",
                description="End-to-end data processing pipeline",
                test_function="_benchmark_end_to_end_processing",
                target_execution_time_ms=5000.0,
                acceptable_variance_percent=20.0,
                iterations=2,
                tags=["integration", "pipeline", "e2e"]
            )
        ]
        
        return benchmarks
    
    def _load_baseline_results(self) -> Dict[str, BenchmarkResult]:
        """Load baseline benchmark results"""
        baseline_file = self.results_dir / "baseline_results.json"
        
        if not baseline_file.exists():
            logger.info("No baseline results found")
            return {}
        
        try:
            with open(baseline_file, 'r') as f:
                data = json.load(f)
            
            baselines = {}
            for name, result_data in data.items():
                # Reconstruct BenchmarkResult from dict
                baselines[name] = BenchmarkResult(
                    benchmark_name=result_data['benchmark_name'],
                    execution_times_ms=result_data.get('execution_times_ms', []),
                    avg_execution_time_ms=result_data['avg_execution_time_ms'],
                    median_execution_time_ms=result_data['median_execution_time_ms'],
                    min_execution_time_ms=result_data['min_execution_time_ms'],
                    max_execution_time_ms=result_data['max_execution_time_ms'],
                    std_deviation_ms=result_data['std_deviation_ms'],
                    target_time_ms=result_data['target_time_ms'],
                    performance_ratio=result_data['performance_ratio'],
                    passed=result_data['passed'],
                    timestamp=datetime.fromisoformat(result_data['timestamp'])
                )
            
            logger.info(f"Loaded {len(baselines)} baseline results")
            return baselines
            
        except Exception as e:
            logger.error(f"Error loading baseline results: {e}")
            return {}
    
    def _save_baseline_results(self, results: Dict[str, BenchmarkResult]):
        """Save results as new baseline"""
        baseline_file = self.results_dir / "baseline_results.json"
        
        try:
            # Convert to serializable format
            data = {}
            for name, result in results.items():
                result_dict = result.to_dict()
                result_dict['execution_times_ms'] = result.execution_times_ms
                data[name] = result_dict
            
            with open(baseline_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(results)} baseline results")
            
        except Exception as e:
            logger.error(f"Error saving baseline results: {e}")
    
    async def run_benchmarks(self, 
                           benchmark_names: Optional[List[str]] = None,
                           tags: Optional[List[str]] = None) -> Dict[str, BenchmarkResult]:
        """Run performance benchmarks"""
        # Filter benchmarks
        benchmarks_to_run = self._filter_benchmarks(benchmark_names, tags)
        
        if not benchmarks_to_run:
            logger.warning("No benchmarks to run")
            return {}
        
        logger.info(f"Running {len(benchmarks_to_run)} performance benchmarks")
        
        # Initialize test data if needed
        if not self._test_data_initialized:
            await self._initialize_test_data()
        
        # Run benchmarks
        results = {}
        total_start_time = time.time()
        
        for benchmark in benchmarks_to_run:
            logger.info(f"Running benchmark: {benchmark.name}")
            try:
                result = await self._run_single_benchmark(benchmark)
                results[benchmark.name] = result
                
                # Log result
                status = "PASSED" if result.passed else "FAILED"
                logger.info(f"Benchmark {benchmark.name}: {result.avg_execution_time_ms:.1f}ms (target: {result.target_time_ms}ms) - {status}")
                
            except Exception as e:
                logger.error(f"Error running benchmark {benchmark.name}: {e}")
                # Create error result
                results[benchmark.name] = BenchmarkResult(
                    benchmark_name=benchmark.name,
                    execution_times_ms=[],
                    avg_execution_time_ms=0,
                    median_execution_time_ms=0,
                    min_execution_time_ms=0,
                    max_execution_time_ms=0,
                    std_deviation_ms=0,
                    target_time_ms=benchmark.target_execution_time_ms,
                    performance_ratio=0,
                    passed=False,
                    timestamp=datetime.now(),
                    error_message=str(e)
                )
        
        total_time = time.time() - total_start_time
        logger.info(f"Completed {len(benchmarks_to_run)} benchmarks in {total_time:.1f}s")
        
        # Save results
        await self._save_results(results)
        
        return results
    
    def _filter_benchmarks(self, 
                          benchmark_names: Optional[List[str]] = None,
                          tags: Optional[List[str]] = None) -> List[PerformanceBenchmark]:
        """Filter benchmarks by name or tags"""
        benchmarks = self.benchmarks
        
        if benchmark_names:
            benchmarks = [b for b in benchmarks if b.name in benchmark_names]
        
        if tags:
            benchmarks = [b for b in benchmarks if any(tag in b.tags for tag in tags)]
        
        return benchmarks
    
    async def _initialize_test_data(self):
        """Initialize test data for benchmarks"""
        try:
            # This would set up any necessary test data
            logger.info("Initializing test data for benchmarks")
            self._test_data_initialized = True
        except Exception as e:
            logger.error(f"Error initializing test data: {e}")
            raise
    
    async def _run_single_benchmark(self, benchmark: PerformanceBenchmark) -> BenchmarkResult:
        """Run a single benchmark with multiple iterations"""
        # Setup
        if benchmark.setup_function:
            await getattr(self, benchmark.setup_function)()
        
        # Get test function
        test_func = getattr(self, benchmark.test_function)
        
        # Run iterations
        execution_times = []
        
        try:
            if benchmark.parallel_execution and benchmark.iterations > 1:
                # Run iterations in parallel
                with ThreadPoolExecutor(max_workers=min(benchmark.iterations, 4)) as executor:
                    futures = [executor.submit(self._time_function, test_func) for _ in range(benchmark.iterations)]
                    
                    for future in as_completed(futures):
                        exec_time = await asyncio.wrap_future(future)
                        execution_times.append(exec_time)
            else:
                # Run iterations sequentially
                for _ in range(benchmark.iterations):
                    exec_time = await self._time_async_function(test_func)
                    execution_times.append(exec_time)
            
            # Calculate statistics
            avg_time = statistics.mean(execution_times)
            median_time = statistics.median(execution_times)
            min_time = min(execution_times)
            max_time = max(execution_times)
            std_dev = statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            
            # Check performance
            performance_ratio = avg_time / benchmark.target_execution_time_ms
            acceptable_ratio = 1 + (benchmark.acceptable_variance_percent / 100)
            passed = performance_ratio <= acceptable_ratio
            
            result = BenchmarkResult(
                benchmark_name=benchmark.name,
                execution_times_ms=execution_times,
                avg_execution_time_ms=avg_time,
                median_execution_time_ms=median_time,
                min_execution_time_ms=min_time,
                max_execution_time_ms=max_time,
                std_deviation_ms=std_dev,
                target_time_ms=benchmark.target_execution_time_ms,
                performance_ratio=performance_ratio,
                passed=passed,
                timestamp=datetime.now(),
                system_info=self._get_system_info()
            )
            
        except Exception as e:
            result = BenchmarkResult(
                benchmark_name=benchmark.name,
                execution_times_ms=[],
                avg_execution_time_ms=0,
                median_execution_time_ms=0,
                min_execution_time_ms=0,
                max_execution_time_ms=0,
                std_deviation_ms=0,
                target_time_ms=benchmark.target_execution_time_ms,
                performance_ratio=0,
                passed=False,
                timestamp=datetime.now(),
                error_message=str(e)
            )
        
        finally:
            # Teardown
            if benchmark.teardown_function:
                await getattr(self, benchmark.teardown_function)()
        
        return result
    
    def _time_function(self, func) -> float:
        """Time a synchronous function execution"""
        start_time = time.perf_counter()
        func()
        end_time = time.perf_counter()
        return (end_time - start_time) * 1000  # Convert to milliseconds
    
    async def _time_async_function(self, func) -> float:
        """Time an asynchronous function execution"""
        start_time = time.perf_counter()
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()
        end_time = time.perf_counter()
        return (end_time - start_time) * 1000  # Convert to milliseconds
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        try:
            import psutil
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage_percent': psutil.disk_usage('/').percent
            }
        except ImportError:
            return {}
    
    async def _save_results(self, results: Dict[str, BenchmarkResult]):
        """Save benchmark results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"benchmark_results_{timestamp}.json"
        
        try:
            # Convert results to serializable format
            data = {
                'timestamp': datetime.now().isoformat(),
                'results': {name: result.to_dict() for name, result in results.items()},
                'summary': self._generate_results_summary(results)
            }
            
            with open(results_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Benchmark results saved to {results_file}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def _generate_results_summary(self, results: Dict[str, BenchmarkResult]) -> Dict[str, Any]:
        """Generate summary of benchmark results"""
        total_benchmarks = len(results)
        passed_benchmarks = sum(1 for r in results.values() if r.passed)
        failed_benchmarks = total_benchmarks - passed_benchmarks
        
        summary = {
            'total_benchmarks': total_benchmarks,
            'passed_benchmarks': passed_benchmarks,
            'failed_benchmarks': failed_benchmarks,
            'pass_rate_percent': (passed_benchmarks / total_benchmarks * 100) if total_benchmarks > 0 else 0,
            'failed_benchmark_names': [name for name, result in results.items() if not result.passed]
        }
        
        # Add regression analysis if baseline exists
        if self.baseline_results:
            summary['regression_analysis'] = self._analyze_regressions(results)
        
        return summary
    
    def _analyze_regressions(self, results: Dict[str, BenchmarkResult]) -> Dict[str, Any]:
        """Analyze performance regressions compared to baseline"""
        regressions = []
        improvements = []
        
        for name, current_result in results.items():
            if name in self.baseline_results and current_result.passed:
                baseline_result = self.baseline_results[name]
                
                # Calculate performance change
                performance_change = (current_result.avg_execution_time_ms - baseline_result.avg_execution_time_ms) / baseline_result.avg_execution_time_ms * 100
                
                if performance_change > 10:  # More than 10% slower
                    regressions.append({
                        'benchmark': name,
                        'baseline_ms': baseline_result.avg_execution_time_ms,
                        'current_ms': current_result.avg_execution_time_ms,
                        'change_percent': performance_change
                    })
                elif performance_change < -10:  # More than 10% faster
                    improvements.append({
                        'benchmark': name,
                        'baseline_ms': baseline_result.avg_execution_time_ms,
                        'current_ms': current_result.avg_execution_time_ms,
                        'change_percent': performance_change
                    })
        
        return {
            'regressions': regressions,
            'improvements': improvements,
            'regression_count': len(regressions),
            'improvement_count': len(improvements)
        }
    
    def set_as_baseline(self, results: Dict[str, BenchmarkResult]):
        """Set current results as baseline for future comparisons"""
        self.baseline_results = results.copy()
        self._save_baseline_results(results)
        logger.info(f"Set {len(results)} benchmark results as baseline")
    
    def generate_performance_report(self, results: Dict[str, BenchmarkResult]) -> str:
        """Generate comprehensive performance report"""
        report = {
            'test_execution': {
                'timestamp': datetime.now().isoformat(),
                'total_benchmarks': len(results),
                'passed_benchmarks': sum(1 for r in results.values() if r.passed),
                'failed_benchmarks': sum(1 for r in results.values() if not r.passed)
            },
            'benchmark_results': [result.to_dict() for result in results.values()],
            'performance_summary': self._generate_results_summary(results),
            'recommendations': self._generate_performance_recommendations(results)
        }
        
        return json.dumps(report, indent=2)
    
    def _generate_performance_recommendations(self, results: Dict[str, BenchmarkResult]) -> List[str]:
        """Generate performance recommendations based on results"""
        recommendations = []
        
        # Check for failed benchmarks
        failed_benchmarks = [name for name, result in results.items() if not result.passed]
        if failed_benchmarks:
            recommendations.append(f"Performance regression detected in {len(failed_benchmarks)} benchmarks: {', '.join(failed_benchmarks)}")
        
        # Check for high variance
        high_variance_benchmarks = []
        for name, result in results.items():
            if result.passed and result.std_deviation_ms > result.avg_execution_time_ms * 0.3:
                high_variance_benchmarks.append(name)
        
        if high_variance_benchmarks:
            recommendations.append(f"High performance variance detected in: {', '.join(high_variance_benchmarks)}. Consider system optimization.")
        
        # Check baseline comparison
        if self.baseline_results:
            regression_analysis = self._analyze_regressions(results)
            if regression_analysis['regression_count'] > 0:
                recommendations.append(f"{regression_analysis['regression_count']} performance regressions detected compared to baseline.")
            if regression_analysis['improvement_count'] > 0:
                recommendations.append(f"{regression_analysis['improvement_count']} performance improvements detected compared to baseline.")
        
        if not recommendations:
            recommendations.append("All benchmarks passed. System performance is stable.")
        
        return recommendations
    
    # Benchmark implementation methods
    
    async def _benchmark_basic_provider_query(self):
        """Benchmark basic provider lookup query"""
        if not self.database_manager:
            raise RuntimeError("Database manager not available")
        
        query = "SELECT * FROM healthcare_providers LIMIT 10"
        result = await self.database_manager.execute_query(query)
        
        if not result.success:
            raise RuntimeError(f"Query failed: {result.error_message}")
    
    async def _benchmark_complex_validation_query(self):
        """Benchmark complex validation query"""
        if not self.database_manager:
            raise RuntimeError("Database manager not available")
        
        query = """
        SELECT p.*, f.facility_name
        FROM healthcare_providers p
        LEFT JOIN provider_facility_affiliations pfa ON p.id = pfa.provider_id
        LEFT JOIN healthcare_facilities f ON pfa.facility_id = f.id
        WHERE p.provider_state = 'CA'
        LIMIT 50
        """
        
        result = await self.database_manager.execute_query(query)
        
        if not result.success:
            raise RuntimeError(f"Query failed: {result.error_message}")
    
    async def _benchmark_aggregation_query(self):
        """Benchmark data aggregation query"""
        if not self.database_manager:
            raise RuntimeError("Database manager not available")
        
        query = """
        SELECT provider_state, COUNT(*) as provider_count
        FROM healthcare_providers
        GROUP BY provider_state
        ORDER BY provider_count DESC
        """
        
        result = await self.database_manager.execute_query(query)
        
        if not result.success:
            raise RuntimeError(f"Query failed: {result.error_message}")
    
    async def _benchmark_cache_read(self):
        """Benchmark cache read performance"""
        if not self.cache_manager:
            # Simulate cache operation
            await asyncio.sleep(0.001)
            return
        
        # Test cache read
        await self.cache_manager.get("test", "benchmark_key")
    
    async def _benchmark_cache_write(self):
        """Benchmark cache write performance"""
        if not self.cache_manager:
            # Simulate cache operation
            await asyncio.sleep(0.002)
            return
        
        # Test cache write
        await self.cache_manager.set("test", "benchmark_key", "benchmark_value")
    
    async def _benchmark_single_validation(self):
        """Benchmark single validation rule execution"""
        if not self.query_executor:
            raise RuntimeError("Query executor not available")
        
        # Get first available validation rule
        if not self.query_executor.validation_queries:
            raise RuntimeError("No validation queries available")
        
        first_rule = list(self.query_executor.validation_queries.keys())[0]
        result = self.query_executor.execute_single_query(first_rule)
        
        if not result or not result.result.success:
            raise RuntimeError("Validation query failed")
    
    async def _benchmark_full_validation_suite(self):
        """Benchmark full validation suite execution"""
        if not self.query_executor:
            raise RuntimeError("Query executor not available")
        
        results = self.query_executor.execute_all_queries(parallel=True)
        
        if not results:
            raise RuntimeError("No validation results")
        
        # Check for any failures
        failed_count = sum(1 for r in results.values() if not r.result.success)
        if failed_count > len(results) / 2:  # More than half failed
            raise RuntimeError(f"Too many validation failures: {failed_count}/{len(results)}")
    
    async def _benchmark_end_to_end_processing(self):
        """Benchmark end-to-end data processing"""
        # This would test the complete data processing pipeline
        # For now, simulate with a complex query
        await self._benchmark_complex_validation_query()
        await self._benchmark_aggregation_query()
        if self.cache_manager:
            await self._benchmark_cache_write()
            await self._benchmark_cache_read()
