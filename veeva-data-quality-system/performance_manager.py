#!/usr/bin/env python3
"""
Veeva Data Quality System - Performance Management
Comprehensive performance monitoring, optimization, and regression testing system

Usage:
    python performance_manager.py --action [monitor|analyze|optimize|test|report|dashboard]
    
Examples:
    python performance_manager.py --action monitor          # Start continuous monitoring
    python performance_manager.py --action analyze         # Run performance analysis
    python performance_manager.py --action optimize        # Run automated optimization
    python performance_manager.py --action test           # Run regression tests
    python performance_manager.py --action report         # Generate performance report
    python performance_manager.py --action dashboard      # Start full dashboard
    python performance_manager.py --action baseline       # Set performance baseline
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from python.monitoring.performance_dashboard import PerformanceDashboard
from python.monitoring.performance_monitor import PerformanceMonitor
from python.monitoring.performance_optimizer import PerformanceOptimizer
from python.testing.performance_regression_tests import PerformanceRegressionTester
from python.utils.database import DatabaseManager
from python.config.pipeline_config import PipelineConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('performance_manager.log')
    ]
)
logger = logging.getLogger(__name__)


class PerformanceManager:
    """
    Main performance management interface for the Veeva Data Quality System
    """
    
    def __init__(self):
        """Initialize performance manager"""
        self.config = self._load_config()
        self.dashboard = None
        self.database_manager = None
        
        logger.info("Performance Manager initialized")
    
    def _load_config(self) -> dict:
        """Load configuration"""
        # Basic configuration - could be loaded from file
        return {
            'database_path': '/Users/jerrylaivivemachi/DS PROJECT/project5/veeva-data-quality-system/data/database/veeva_opendata.db',
            'monitoring_interval': 60,
            'retention_days': 30,
            'auto_optimization_enabled': True,
            'regression_testing_enabled': True
        }
    
    async def initialize_components(self):
        """Initialize performance monitoring components"""
        try:
            # Initialize database manager (simplified for this example)
            # In production, this would use the full DatabaseFactory
            logger.info("Initializing performance monitoring components")
            
            # Create performance dashboard
            self.dashboard = PerformanceDashboard(
                database_manager=self.database_manager,
                cache_manager=None,  # Would be initialized if available
                query_executor=None,  # Would be initialized if available
                monitoring_config=self.config
            )
            
            logger.info("Performance components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise
    
    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        logger.info("Starting continuous performance monitoring...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            await self.dashboard.start_dashboard()
            
            logger.info("Performance monitoring started. Press Ctrl+C to stop.")
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(60)
                    
                    # Print status every 10 minutes
                    if int(time.time()) % 600 == 0:
                        status = self.dashboard.get_dashboard_status()
                        logger.info(f"Dashboard Status: Active={status['dashboard_active']}, Health Score={status.get('current_performance', {}).get('performance', {}).get('avg_health_score', 'N/A')}")
            
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
            
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
        
        finally:
            if self.dashboard:
                await self.dashboard.stop_dashboard()
    
    async def run_analysis(self):
        """Run comprehensive performance analysis"""
        logger.info("Running comprehensive performance analysis...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            analysis = await self.dashboard.run_performance_analysis()
            
            print("\n" + "="*80)
            print("PERFORMANCE ANALYSIS REPORT")
            print("="*80)
            
            # Current Performance
            perf_24h = analysis.get('performance_summary', {}).get('last_24_hours', {}).get('performance', {})
            print(f"\nCurrent Performance (24h average):")
            print(f"  Query Time: {perf_24h.get('avg_query_time_ms', 0):.1f}ms")
            print(f"  Cache Hit Rate: {perf_24h.get('avg_cache_hit_rate_percent', 0):.1f}%")
            print(f"  CPU Usage: {perf_24h.get('avg_cpu_usage_percent', 0):.1f}%")
            print(f"  Memory Usage: {perf_24h.get('avg_memory_usage_mb', 0):.1f}MB")
            print(f"  Health Score: {perf_24h.get('avg_health_score', 0):.1f}/100")
            
            # Health Assessment
            health = analysis.get('health_assessment', {})
            print(f"\nSystem Health: {health.get('overall_status', 'UNKNOWN')}")
            print(f"  Critical Issues: {health.get('critical_issues', 0)}")
            print(f"  Action Required: {'YES' if health.get('action_required', False) else 'NO'}")
            
            # Optimization Recommendations
            recommendations = analysis.get('optimization_recommendations', [])
            print(f"\nOptimization Recommendations: {len(recommendations)}")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"  {i}. [{rec['priority']}] {rec['description']} (Est. {rec['estimated_improvement_percent']:.1f}% improvement)")
            
            # Regression Tests
            regression = analysis.get('regression_test_results', {})
            print(f"\nRegression Tests: {regression.get('passed_tests', 0)}/{regression.get('total_tests', 0)} passed")
            if regression.get('failed_tests'):
                print(f"  Failed: {', '.join(regression['failed_tests'])}")
            
            print("\n" + "="*80)
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
            print(f"Error: {e}")
    
    async def run_optimization(self):
        """Run automated performance optimization"""
        logger.info("Running automated performance optimization...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            # Get optimization recommendations
            recommendations = await self.dashboard.performance_optimizer.analyze_and_optimize(auto_implement=False)
            
            print(f"\nFound {len(recommendations)} optimization opportunities:")
            
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec.description}")
                print(f"   Priority: {rec.priority}")
                print(f"   Expected Improvement: {rec.estimated_improvement:.1f}%")
                print(f"   Complexity: {rec.implementation_complexity}")
                print(f"   Auto-implementable: {'Yes' if rec.auto_implementable else 'No'}")
            
            # Ask user for confirmation
            auto_implementable = [rec for rec in recommendations if rec.auto_implementable]
            if auto_implementable:
                print(f"\n{len(auto_implementable)} optimizations can be implemented automatically.")
                response = input("Implement automatic optimizations? (y/n): ")
                
                if response.lower() == 'y':
                    implemented = await self.dashboard.performance_optimizer._implement_automatic_optimizations(auto_implementable)
                    print(f"Successfully implemented {implemented} optimizations.")
                else:
                    print("Automatic optimizations skipped.")
            
        except Exception as e:
            logger.error(f"Error during optimization: {e}")
            print(f"Error: {e}")
    
    async def run_regression_tests(self):
        """Run performance regression tests"""
        logger.info("Running performance regression tests...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            result = await self.dashboard.run_benchmark_suite('core')
            
            if result['success']:
                print(f"\nRegression Test Results:")
                print(f"  Total Tests: {result['results_count']}")
                print(f"  Passed: {result['passed_count']}")
                print(f"  Failed: {result['failed_count']}")
                
                if result['failed_count'] > 0:
                    print(f"\nWarning: {result['failed_count']} performance regressions detected!")
                else:
                    print(f"\nAll performance tests passed successfully.")
            else:
                print(f"Error: {result['error']}")
            
        except Exception as e:
            logger.error(f"Error during regression testing: {e}")
            print(f"Error: {e}")
    
    async def generate_report(self):
        """Generate performance report"""
        logger.info("Generating performance report...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            report = self.dashboard.generate_performance_report('comprehensive')
            
            # Save report to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"performance_report_{timestamp}.json"
            
            if report.startswith('{'):
                # Report is JSON string
                with open(report_file, 'w') as f:
                    f.write(report)
                print(f"\nPerformance report generated: {report_file}")
            else:
                # Report is file path
                print(f"\nPerformance report generated: {report}")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            print(f"Error: {e}")
    
    async def start_dashboard(self):
        """Start full performance dashboard"""
        logger.info("Starting full performance dashboard...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            await self.dashboard.start_dashboard()
            
            print("\n" + "="*60)
            print("VEEVA DATA QUALITY SYSTEM - PERFORMANCE DASHBOARD")
            print("="*60)
            print("Dashboard started successfully!")
            print("\nMonitoring Status:")
            
            # Show initial status
            status = self.dashboard.get_dashboard_status()
            print(f"  Active: {status['dashboard_active']}")
            print(f"  Monitoring Interval: {status['monitoring']['interval_seconds']}s")
            print(f"  Auto-optimization: {status['automation_tasks']['auto_optimization_enabled']}")
            print(f"  Regression Testing: {status['automation_tasks']['regression_testing_enabled']}")
            
            print("\nPress Ctrl+C to stop the dashboard.")
            print("="*60)
            
            # Keep dashboard running
            try:
                while True:
                    await asyncio.sleep(300)  # Update every 5 minutes
                    
                    status = self.dashboard.get_dashboard_status()
                    current_time = datetime.now().strftime("%H:%M:%S")
                    health_score = status.get('current_performance', {}).get('performance', {}).get('avg_health_score', 'N/A')
                    
                    print(f"[{current_time}] System Health: {health_score}/100")
            
            except KeyboardInterrupt:
                print("\nDashboard stopped by user.")
            
        except Exception as e:
            logger.error(f"Error in dashboard: {e}")
            print(f"Error: {e}")
        
        finally:
            if self.dashboard:
                await self.dashboard.stop_dashboard()
    
    async def set_baseline(self):
        """Set performance baseline"""
        logger.info("Setting performance baseline...")
        
        if not self.dashboard:
            await self.initialize_components()
        
        try:
            result = await self.dashboard.set_performance_baseline()
            
            if result['success']:
                print(f"\nPerformance baseline set successfully!")
                print(f"  Benchmarks: {result['benchmarks_count']}")
                print(f"  Health Score: {result['baseline_health_score']:.1f}/100")
                print(f"  Timestamp: {result['timestamp']}")
            else:
                print(f"Error: {result['error']}")
            
        except Exception as e:
            logger.error(f"Error setting baseline: {e}")
            print(f"Error: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Veeva Data Quality System - Performance Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--action',
        choices=['monitor', 'analyze', 'optimize', 'test', 'report', 'dashboard', 'baseline'],
        required=True,
        help='Action to perform'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create performance manager
    manager = PerformanceManager()
    
    # Execute requested action
    try:
        if args.action == 'monitor':
            asyncio.run(manager.start_monitoring())
        elif args.action == 'analyze':
            asyncio.run(manager.run_analysis())
        elif args.action == 'optimize':
            asyncio.run(manager.run_optimization())
        elif args.action == 'test':
            asyncio.run(manager.run_regression_tests())
        elif args.action == 'report':
            asyncio.run(manager.generate_report())
        elif args.action == 'dashboard':
            asyncio.run(manager.start_dashboard())
        elif args.action == 'baseline':
            asyncio.run(manager.set_baseline())
    
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
