"""
Performance dashboard and management system
Provides comprehensive performance monitoring interface and automation
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
from dataclasses import asdict

from .performance_monitor import PerformanceMonitor, PerformanceMetrics
from .performance_optimizer import PerformanceOptimizer, OptimizationRecommendation
from ..testing.performance_regression_tests import PerformanceRegressionTester

logger = logging.getLogger(__name__)


class PerformanceDashboard:
    """
    Comprehensive performance management dashboard that:
    - Provides real-time performance monitoring
    - Executes automated performance optimization
    - Runs scheduled performance regression tests
    - Generates performance reports and alerts
    - Manages performance baselines and targets
    """
    
    def __init__(self,
                 database_manager=None,
                 cache_manager=None,
                 query_executor=None,
                 monitoring_config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance dashboard
        
        Args:
            database_manager: Database manager instance
            cache_manager: Cache manager instance
            query_executor: Query executor instance
            monitoring_config: Monitoring configuration
        """
        self.database_manager = database_manager
        self.cache_manager = cache_manager
        self.query_executor = query_executor
        
        # Configuration
        self.config = monitoring_config or self._get_default_config()
        
        # Initialize monitoring components
        db_path = self.config.get('database_path', '/Users/jerrylaivivemachi/DS PROJECT/project5/veeva-data-quality-system/data/database/veeva_opendata.db')
        
        self.performance_monitor = PerformanceMonitor(
            database_path=db_path,
            cache_manager=cache_manager,
            monitoring_interval=self.config.get('monitoring_interval', 60),
            retention_days=self.config.get('retention_days', 30)
        )
        
        self.performance_optimizer = PerformanceOptimizer(
            performance_monitor=self.performance_monitor,
            database_manager=database_manager,
            cache_manager=cache_manager,
            query_executor=query_executor
        )
        
        self.regression_tester = PerformanceRegressionTester(
            database_manager=database_manager,
            cache_manager=cache_manager,
            query_executor=query_executor,
            results_dir=self.config.get('results_dir')
        )
        
        # Dashboard state
        self._dashboard_active = False
        self._automation_tasks = []
        
        # Integrate performance monitoring with query executor
        if self.query_executor:
            self.query_executor.performance_monitor = self.performance_monitor
        
        logger.info("Performance dashboard initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default monitoring configuration"""
        return {
            'monitoring_interval': 60,  # seconds
            'optimization_interval': 3600,  # 1 hour
            'regression_test_interval': 86400,  # 24 hours
            'retention_days': 30,
            'auto_optimization_enabled': True,
            'regression_testing_enabled': True,
            'alert_thresholds': {
                'query_time_ms': 5000,
                'cache_hit_rate_percent': 80,
                'cpu_usage_percent': 70,
                'memory_usage_mb': 512,
                'health_score': 85
            }
        }
    
    async def start_dashboard(self):
        """Start the performance dashboard with all monitoring components"""
        if self._dashboard_active:
            logger.warning("Performance dashboard already active")
            return
        
        logger.info("Starting performance dashboard...")
        
        try:
            # Start performance monitoring
            await self.performance_monitor.start_monitoring()
            
            # Start automation tasks
            await self._start_automation_tasks()
            
            self._dashboard_active = True
            logger.info("Performance dashboard started successfully")
            
        except Exception as e:
            logger.error(f"Error starting performance dashboard: {e}")
            raise
    
    async def stop_dashboard(self):
        """Stop the performance dashboard"""
        if not self._dashboard_active:
            return
        
        logger.info("Stopping performance dashboard...")
        
        # Stop automation tasks
        for task in self._automation_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._automation_tasks:
            await asyncio.gather(*self._automation_tasks, return_exceptions=True)
        
        # Stop monitoring
        self.performance_monitor.stop_monitoring()
        
        self._dashboard_active = False
        self._automation_tasks = []
        
        logger.info("Performance dashboard stopped")
    
    async def _start_automation_tasks(self):
        """Start automated performance management tasks"""
        # Automatic optimization task
        if self.config.get('auto_optimization_enabled', True):
            task = asyncio.create_task(self._auto_optimization_loop())
            self._automation_tasks.append(task)
            logger.info("Started automatic optimization task")
        
        # Regression testing task
        if self.config.get('regression_testing_enabled', True):
            task = asyncio.create_task(self._regression_testing_loop())
            self._automation_tasks.append(task)
            logger.info("Started regression testing task")
        
        # Cleanup task
        task = asyncio.create_task(self._cleanup_loop())
        self._automation_tasks.append(task)
        logger.info("Started cleanup task")
    
    async def _auto_optimization_loop(self):
        """Automated optimization loop"""
        interval = self.config.get('optimization_interval', 3600)
        
        while self._dashboard_active:
            try:
                logger.info("Running automated performance optimization")
                
                # Run optimization analysis
                recommendations = await self.performance_optimizer.analyze_and_optimize(auto_implement=True)
                
                logger.info(f"Generated {len(recommendations)} optimization recommendations")
                
                # Sleep until next optimization cycle
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-optimization loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def _regression_testing_loop(self):
        """Automated regression testing loop"""
        interval = self.config.get('regression_test_interval', 86400)
        
        while self._dashboard_active:
            try:
                logger.info("Running automated performance regression tests")
                
                # Run core performance benchmarks
                results = await self.regression_tester.run_benchmarks(
                    tags=['database', 'cache', 'validation']
                )
                
                # Check for regressions
                failed_tests = [name for name, result in results.items() if not result.passed]
                if failed_tests:
                    logger.warning(f"Performance regression detected in: {', '.join(failed_tests)}")
                    # Could trigger alerts here
                else:
                    logger.info("All performance regression tests passed")
                
                # Sleep until next test cycle
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in regression testing loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def _cleanup_loop(self):
        """Automated cleanup loop"""
        # Run cleanup once per day
        interval = 86400
        
        while self._dashboard_active:
            try:
                logger.info("Running performance data cleanup")
                
                # Cleanup old performance data
                self.performance_monitor.cleanup_old_data()
                
                # Sleep until next cleanup
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    def get_dashboard_status(self) -> Dict[str, Any]:
        """Get current dashboard status and metrics"""
        try:
            # Get current performance metrics
            performance_summary = self.performance_monitor.get_performance_summary(hours=1)
            
            # Get cache statistics if available
            cache_stats = None
            if self.cache_manager:
                cache_stats = self.cache_manager.get_cache_stats()
            
            # Get optimization history
            optimization_history = self.performance_optimizer.get_optimization_history(days=7)
            optimization_effectiveness = self.performance_optimizer.get_optimization_effectiveness()
            
            status = {
                'dashboard_active': self._dashboard_active,
                'timestamp': datetime.now().isoformat(),
                'monitoring': {
                    'active': self.performance_monitor._monitoring_active,
                    'interval_seconds': self.performance_monitor.monitoring_interval
                },
                'current_performance': performance_summary,
                'cache_performance': cache_stats,
                'optimization': {
                    'recent_optimizations': len(optimization_history),
                    'effectiveness': optimization_effectiveness
                },
                'automation_tasks': {
                    'total_tasks': len(self._automation_tasks),
                    'auto_optimization_enabled': self.config.get('auto_optimization_enabled', True),
                    'regression_testing_enabled': self.config.get('regression_testing_enabled', True)
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting dashboard status: {e}")
            return {
                'dashboard_active': self._dashboard_active,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def run_performance_analysis(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis"""
        logger.info("Running comprehensive performance analysis")
        
        try:
            # Get performance summary
            summary_24h = self.performance_monitor.get_performance_summary(hours=24)
            summary_7d = self.performance_monitor.get_performance_summary(hours=168)
            
            # Run optimization analysis
            optimization_recommendations = await self.performance_optimizer.analyze_and_optimize(auto_implement=False)
            
            # Run regression tests
            regression_results = await self.regression_tester.run_benchmarks(tags=['core'])
            
            analysis = {
                'timestamp': datetime.now().isoformat(),
                'performance_summary': {
                    'last_24_hours': summary_24h,
                    'last_7_days': summary_7d
                },
                'optimization_recommendations': [
                    rec.to_dict() for rec in optimization_recommendations
                ],
                'regression_test_results': {
                    'total_tests': len(regression_results),
                    'passed_tests': sum(1 for r in regression_results.values() if r.passed),
                    'failed_tests': [name for name, r in regression_results.items() if not r.passed]
                },
                'health_assessment': self._assess_system_health(summary_24h, optimization_recommendations, regression_results)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error running performance analysis: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def _assess_system_health(self, performance_summary: Dict, recommendations: List, regression_results: Dict) -> Dict[str, Any]:
        """Assess overall system health based on metrics"""
        health_score = performance_summary.get('performance', {}).get('avg_health_score', 0)
        
        # Determine health status
        if health_score >= 90:
            status = "EXCELLENT"
        elif health_score >= 80:
            status = "GOOD"
        elif health_score >= 70:
            status = "ACCEPTABLE"
        elif health_score >= 60:
            status = "DEGRADED"
        else:
            status = "CRITICAL"
        
        # Count critical issues
        critical_recommendations = sum(1 for r in recommendations if r.priority == 'HIGH')
        failed_regression_tests = sum(1 for r in regression_results.values() if not r.passed)
        
        assessment = {
            'overall_status': status,
            'health_score': health_score,
            'critical_issues': critical_recommendations + failed_regression_tests,
            'recommendations_count': len(recommendations),
            'regression_failures': failed_regression_tests,
            'action_required': critical_recommendations > 0 or failed_regression_tests > 0
        }
        
        return assessment
    
    async def implement_optimization(self, optimization_type: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Manually implement a specific optimization"""
        try:
            logger.info(f"Implementing manual optimization: {optimization_type}")
            
            # Get available optimization strategies
            from .performance_optimizer import OptimizationType
            
            if optimization_type not in [ot.value for ot in OptimizationType]:
                return {
                    'success': False,
                    'error': f"Unknown optimization type: {optimization_type}"
                }
            
            # Create optimization recommendation
            opt_type = OptimizationType(optimization_type)
            
            # Execute optimization based on type
            if opt_type in self.performance_optimizer.optimization_strategies:
                start_time = time.time()
                
                strategy_func = self.performance_optimizer.optimization_strategies[opt_type]
                success = await strategy_func(parameters or {})
                
                implementation_time = time.time() - start_time
                
                result = {
                    'success': success,
                    'optimization_type': optimization_type,
                    'implementation_time_seconds': implementation_time,
                    'timestamp': datetime.now().isoformat()
                }
                
                if success:
                    logger.info(f"Successfully implemented optimization {optimization_type} in {implementation_time:.2f}s")
                else:
                    logger.warning(f"Failed to implement optimization {optimization_type}")
                
                return result
            else:
                return {
                    'success': False,
                    'error': f"No implementation strategy for {optimization_type}"
                }
                
        except Exception as e:
            logger.error(f"Error implementing optimization: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def run_benchmark_suite(self, suite_type: str = 'core') -> Dict[str, Any]:
        """Run performance benchmark suite"""
        try:
            logger.info(f"Running {suite_type} benchmark suite")
            
            if suite_type == 'core':
                tags = ['database', 'cache']
            elif suite_type == 'full':
                tags = None  # Run all benchmarks
            elif suite_type == 'validation':
                tags = ['validation']
            else:
                return {
                    'success': False,
                    'error': f"Unknown benchmark suite: {suite_type}"
                }
            
            # Run benchmarks
            results = await self.regression_tester.run_benchmarks(tags=tags)
            
            # Generate report
            report = self.regression_tester.generate_performance_report(results)
            
            return {
                'success': True,
                'suite_type': suite_type,
                'results_count': len(results),
                'passed_count': sum(1 for r in results.values() if r.passed),
                'failed_count': sum(1 for r in results.values() if not r.passed),
                'report': json.loads(report),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error running benchmark suite: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_performance_report(self, report_type: str = 'comprehensive') -> str:
        """Generate performance report"""
        try:
            if report_type == 'comprehensive':
                # Generate full performance report
                output_path = self.performance_monitor.results_dir / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                return self.performance_monitor.generate_performance_report(str(output_path))
            
            elif report_type == 'summary':
                # Generate summary report
                summary = self.performance_monitor.get_performance_summary(hours=24)
                return json.dumps(summary, indent=2)
            
            elif report_type == 'optimization':
                # Generate optimization report
                effectiveness = self.performance_optimizer.get_optimization_effectiveness()
                return json.dumps(effectiveness, indent=2)
            
            else:
                return json.dumps({
                    'error': f"Unknown report type: {report_type}",
                    'available_types': ['comprehensive', 'summary', 'optimization']
                }, indent=2)
                
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return json.dumps({'error': str(e)}, indent=2)
    
    async def set_performance_baseline(self) -> Dict[str, Any]:
        """Set current performance as baseline for future comparisons"""
        try:
            logger.info("Setting new performance baseline")
            
            # Run comprehensive benchmarks to establish baseline
            benchmark_results = await self.regression_tester.run_benchmarks()
            
            # Set as baseline
            self.regression_tester.set_as_baseline(benchmark_results)
            
            # Store current performance metrics as baseline
            current_metrics = self.performance_monitor._collect_performance_metrics()
            self.performance_monitor.baseline_metrics = current_metrics
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'benchmarks_count': len(benchmark_results),
                'baseline_health_score': current_metrics.system_health_score
            }
            
        except Exception as e:
            logger.error(f"Error setting performance baseline: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_performance_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get performance trends over specified period"""
        try:
            # This would analyze trends in the performance database
            # For now, return a basic structure
            summary = self.performance_monitor.get_performance_summary(hours=days * 24)
            
            trends = {
                'period_days': days,
                'current_summary': summary,
                'trend_analysis': 'Trend analysis would be implemented here',
                'timestamp': datetime.now().isoformat()
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
