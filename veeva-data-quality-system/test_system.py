#!/usr/bin/env python3
"""
Comprehensive End-to-End System Testing for Veeva Data Quality System
Tests all components: CLI, Database, Validation, Monitoring, Logging
"""

import os
import sys
import subprocess
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import time
import pandas as pd

# Add project to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager
from python.utils.logging_config import setup_logging, get_logger
from python.utils.monitoring import SystemMonitor
from python.pipeline.query_executor import QueryExecutor
from python.utils.data_quality import DataQualityCalculator


class SystemTester:
    """Comprehensive system testing suite"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_results = {}
        self.start_time = time.time()
        
        # Setup test logging
        self.logger = setup_logging(
            log_level="INFO",
            log_file="logs/system_test.log",
            console_output=True
        )
        self.logger = get_logger('system_test')
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all system tests"""
        print("🚀 Starting Veeva Data Quality System End-to-End Testing")
        print("=" * 60)
        
        tests = [
            ("Database Connectivity", self.test_database_connectivity),
            ("Configuration Management", self.test_configuration),
            ("CLI Interface", self.test_cli_interface),
            ("Validation Framework", self.test_validation_framework),
            ("Monitoring System", self.test_monitoring_system),
            ("Data Quality Calculator", self.test_data_quality_calculator),
            ("File Export Functions", self.test_file_exports),
            ("Error Handling", self.test_error_handling),
            ("Performance Tests", self.test_performance)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running: {test_name}")
            try:
                result = test_func()
                self.test_results[test_name] = {
                    'status': 'PASSED' if result else 'FAILED',
                    'result': result,
                    'error': None
                }
                status_icon = "✅" if result else "❌"
                print(f"{status_icon} {test_name}: {'PASSED' if result else 'FAILED'}")
                
            except Exception as e:
                self.test_results[test_name] = {
                    'status': 'ERROR',
                    'result': False,
                    'error': str(e)
                }
                print(f"💥 {test_name}: ERROR - {e}")
                self.logger.error(f"Test failed: {test_name} - {e}")
        
        return self.generate_test_report()
    
    def test_database_connectivity(self) -> bool:
        """Test database connection and basic queries"""
        try:
            db_config = DatabaseConfig()
            db_manager = DatabaseManager(db_config)
            
            # Test basic connectivity
            health = db_manager.health_check()
            if not health.get('database_accessible', False):
                return False
            
            # Test query execution
            result = db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
            if not result.success or result.row_count == 0:
                return False
            
            # Test table existence
            expected_tables = ['healthcare_providers', 'healthcare_facilities', 'provider_facility_affiliations']
            overview = db_manager.get_database_overview()
            
            for table in expected_tables:
                if table not in overview.get('tables', {}):
                    print(f"Missing table: {table}")
                    return False
            
            self.logger.info("Database connectivity test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Database connectivity test failed: {e}")
            return False
    
    def test_configuration(self) -> bool:
        """Test configuration loading and management"""
        try:
            # Test pipeline configuration
            pipeline_config = PipelineConfig()
            
            # Test configuration sections
            quality_thresholds = pipeline_config.quality_thresholds
            if quality_thresholds.completeness_minimum < 0 or quality_thresholds.completeness_minimum > 100:
                return False
            
            # Test validation rules configuration
            validation_rules = pipeline_config.validation_rules
            if not validation_rules:
                return False
            
            # Test database configuration
            db_config = DatabaseConfig()
            if not db_config.db_path or not Path(db_config.db_path).exists():
                return False
            
            self.logger.info("Configuration test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration test failed: {e}")
            return False
    
    def test_cli_interface(self) -> bool:
        """Test CLI commands and functionality"""
        try:
            cli_script = self.project_root / "python" / "main.py"
            
            # Test help command
            result = subprocess.run(
                [sys.executable, str(cli_script), "--help"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"CLI help failed: {result.stderr}")
                return False
            
            # Test status command
            result = subprocess.run(
                [sys.executable, str(cli_script), "status"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"CLI status failed: {result.stderr}")
                return False
            
            # Test catalog command
            result = subprocess.run(
                [sys.executable, str(cli_script), "catalog"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"CLI catalog failed: {result.stderr}")
                return False
            
            # Test monitor command
            result = subprocess.run(
                [sys.executable, str(cli_script), "monitor", "--summary"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=45
            )
            if result.returncode != 0:
                print(f"CLI monitor failed: {result.stderr}")
                return False
            
            self.logger.info("CLI interface test passed")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("CLI test timed out")
            return False
        except Exception as e:
            self.logger.error(f"CLI interface test failed: {e}")
            return False
    
    def test_validation_framework(self) -> bool:
        """Test validation query execution"""
        try:
            db_config = DatabaseConfig()
            pipeline_config = PipelineConfig()
            db_manager = DatabaseManager(db_config)
            query_executor = QueryExecutor(db_manager, pipeline_config)
            
            # Test query loading
            if len(query_executor.validation_queries) == 0:
                print("No validation queries loaded")
                return False
            
            # Test catalog generation
            catalog = query_executor.get_query_catalog()
            if not catalog:
                return False
            
            # Test single query execution
            first_rule = catalog[0]['rule_name']
            result = query_executor.execute_single_query(first_rule)
            
            if not result:
                print(f"Failed to execute query: {first_rule}")
                return False
            
            # Test parallel execution (all queries)
            results = query_executor.execute_all_queries(parallel=True)
            
            if len(results) == 0:
                print("Parallel execution failed: no results returned")
                return False
            
            self.logger.info("Validation framework test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Validation framework test failed: {e}")
            return False
    
    def test_monitoring_system(self) -> bool:
        """Test monitoring and metrics collection"""
        try:
            db_config = DatabaseConfig()
            monitor = SystemMonitor(db_config.db_path)
            
            # Test system metrics collection
            system_metrics = monitor.collect_system_metrics()
            if not system_metrics or system_metrics.cpu_percent < 0:
                return False
            
            # Test database metrics collection
            db_metrics = monitor.collect_database_metrics()
            if not db_metrics or db_metrics.database_size_mb <= 0:
                return False
            
            # Test metrics storage
            monitor.store_metrics(system_metrics, db_metrics)
            
            # Test health status
            health_status = monitor.get_system_health_status()
            if 'overall_status' not in health_status:
                return False
            
            # Test metrics summary
            summary = monitor.get_metrics_summary(1)  # 1 hour
            if 'time_period_hours' not in summary:
                return False
            
            self.logger.info("Monitoring system test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Monitoring system test failed: {e}")
            return False
    
    def test_data_quality_calculator(self) -> bool:
        """Test data quality calculation engine"""
        try:
            db_config = DatabaseConfig()
            db_manager = DatabaseManager(db_config)
            
            # Get sample data
            result = db_manager.execute_query("SELECT * FROM healthcare_providers LIMIT 1000")
            if not result.success:
                return False
            
            df = result.data
            calculator = DataQualityCalculator()
            
            # Test individual quality calculations
            completeness = calculator.calculate_completeness(df)
            if completeness < 0 or completeness > 100:
                return False
            
            consistency = calculator.calculate_consistency(df)
            if consistency < 0 or consistency > 100:
                return False
            
            accuracy = calculator.calculate_accuracy(df)
            if accuracy < 0 or accuracy > 100:
                return False
            
            # Test overall quality calculation
            metrics = calculator.calculate_overall_quality(df)
            if not metrics or metrics.overall_score < 0 or metrics.overall_score > 100:
                return False
            
            # Test quality report generation
            report = calculator.generate_quality_report(metrics)
            if 'summary' not in report or 'dimensions' not in report:
                return False
            
            self.logger.info("Data quality calculator test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Data quality calculator test failed: {e}")
            return False
    
    def test_file_exports(self) -> bool:
        """Test file export functionality"""
        try:
            # Create temporary directory for test exports
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Test validation results export
                cli_script = self.project_root / "python" / "main.py"
                
                result = subprocess.run([
                    sys.executable, str(cli_script), "validate",
                    "--rule", "validation_summary",
                    "--format", "json",
                    "--output-dir", str(temp_path)
                ], cwd=self.project_root, capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    print(f"Export test failed: {result.stderr}")
                    return False
                
                # Check if files were created
                json_files = list(temp_path.glob("*.json"))
                if not json_files:
                    print("No JSON export files created")
                    return False
                
                # Verify JSON file content
                with open(json_files[0]) as f:
                    data = json.load(f)
                    if 'results' not in data:
                        print(f"JSON structure missing 'results' key. Found keys: {list(data.keys())}")
                        return False
            
            self.logger.info("File export test passed")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("File export test timed out")
            return False
        except Exception as e:
            self.logger.error(f"File export test failed: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling and recovery"""
        try:
            # Test invalid database path
            invalid_config = DatabaseConfig(db_path="invalid/path/database.db")
            db_manager = DatabaseManager(invalid_config)
            
            # This should fail gracefully
            result = db_manager.execute_query("SELECT 1")
            if result.success:  # Should fail
                return False
            
            # Test invalid SQL query
            valid_config = DatabaseConfig()
            valid_db_manager = DatabaseManager(valid_config)
            
            result = valid_db_manager.execute_query("INVALID SQL QUERY")
            if result.success:  # Should fail
                return False
            
            # Test CLI with invalid arguments
            cli_script = self.project_root / "python" / "main.py"
            
            result = subprocess.run([
                sys.executable, str(cli_script), "invalid-command"
            ], cwd=self.project_root, capture_output=True, text=True, timeout=30)
            
            # Should exit with error code but not crash
            if result.returncode == 0:
                return False
            
            self.logger.info("Error handling test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling test failed: {e}")
            return False
    
    def test_performance(self) -> bool:
        """Test system performance benchmarks"""
        try:
            db_config = DatabaseConfig()
            db_manager = DatabaseManager(db_config)
            
            # Test query performance
            start_time = time.time()
            result = db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
            query_time = time.time() - start_time
            
            if not result.success or query_time > 5.0:  # 5 second threshold
                print(f"Query performance test failed: {query_time:.2f}s")
                return False
            
            # Test large result set handling
            start_time = time.time()
            result = db_manager.execute_query("SELECT * FROM healthcare_providers LIMIT 10000")
            large_query_time = time.time() - start_time
            
            if not result.success or large_query_time > 15.0:  # 15 second threshold
                print(f"Large query performance test failed: {large_query_time:.2f}s")
                return False
            
            # Test validation performance (quick subset)
            pipeline_config = PipelineConfig()
            query_executor = QueryExecutor(db_manager, pipeline_config)
            
            start_time = time.time()
            result = query_executor.execute_single_query("validation_summary")
            validation_time = time.time() - start_time
            
            if not result or validation_time > 10.0:  # 10 second threshold
                print(f"Validation performance test failed: {validation_time:.2f}s")
                return False
            
            self.logger.info("Performance test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Performance test failed: {e}")
            return False
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_time = time.time() - self.start_time
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASSED')
        failed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'FAILED')
        error_tests = sum(1 for result in self.test_results.values() if result['status'] == 'ERROR')
        total_tests = len(self.test_results)
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'errors': error_tests,
                'success_rate': round(success_rate, 2),
                'total_time_seconds': round(total_time, 2),
                'overall_status': 'PASSED' if success_rate >= 80 else 'FAILED'
            },
            'test_results': self.test_results,
            'system_info': {
                'python_version': sys.version,
                'project_root': str(self.project_root),
                'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("🎯 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"💥 Errors: {error_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Overall Status: {'✅ PASSED' if report['summary']['overall_status'] == 'PASSED' else '❌ FAILED'}")
        
        # Save detailed report
        report_file = self.project_root / "reports" / "system_test_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved: {report_file}")
        
        return report


def main():
    """Main test execution"""
    try:
        tester = SystemTester()
        report = tester.run_all_tests()
        
        # Exit with appropriate code
        if report['summary']['overall_status'] == 'PASSED':
            print("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 Some tests failed. Check the detailed report.")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Test suite crashed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()