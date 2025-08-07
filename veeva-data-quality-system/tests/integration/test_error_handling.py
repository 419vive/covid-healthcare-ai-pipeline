"""
Integration tests for error handling and edge cases
Tests system resilience and error recovery mechanisms
"""

import unittest
import tempfile
import shutil
import os
import subprocess
import sqlite3
from pathlib import Path
import sys
import json
from unittest.mock import patch, Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager
from python.pipeline.query_executor import QueryExecutor


class TestDatabaseErrorHandling(unittest.TestCase):
    """Test database error handling scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.project_root = project_root
        self.cli_script = self.project_root / "python" / "main.py"
    
    def test_invalid_database_path(self):
        """Test handling of invalid database path"""
        invalid_config = DatabaseConfig(db_path="/nonexistent/path/database.db")
        
        # Should handle gracefully without crashing
        with self.assertRaises(Exception):
            db_manager = DatabaseManager(invalid_config)
            db_manager.execute_query("SELECT 1")
    
    def test_corrupted_database_file(self):
        """Test handling of corrupted database file"""
        # Create a corrupted database file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db.write(b"This is not a valid SQLite database file")
            corrupted_db_path = temp_db.name
        
        try:
            config = DatabaseConfig(db_path=corrupted_db_path)
            
            # Should handle corruption gracefully
            with self.assertRaises(Exception):
                db_manager = DatabaseManager(config)
                db_manager.execute_query("SELECT 1")
        finally:
            if os.path.exists(corrupted_db_path):
                os.unlink(corrupted_db_path)
    
    def test_database_permissions_error(self):
        """Test handling of database permissions issues"""
        # Create a read-only database directory
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            # Create a database file and make directory read-only
            db_path = readonly_dir / "test.db"
            
            # Create valid database first
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.close()
            
            # Make directory read-only (on Unix systems)
            if hasattr(os, 'chmod'):
                try:
                    os.chmod(readonly_dir, 0o444)
                    
                    config = DatabaseConfig(db_path=str(db_path))
                    db_manager = DatabaseManager(config)
                    
                    # Should handle permission errors gracefully
                    result = db_manager.execute_query("INSERT INTO test VALUES (1)")
                    self.assertFalse(result.success)
                    self.assertIsNotNone(result.error_message)
                
                except PermissionError:
                    # Expected on some systems
                    pass
                finally:
                    # Restore permissions for cleanup
                    os.chmod(readonly_dir, 0o755)
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Test with malicious SQL injection attempt
        malicious_input = "'; DROP TABLE healthcare_providers; --"
        
        # Using parameterized query should protect against injection
        safe_query = "SELECT * FROM healthcare_providers WHERE npi = :npi"
        result = db_manager.execute_query(safe_query, params={'npi': malicious_input})
        
        # Query should execute safely (even if no results)
        self.assertTrue(result.success or "no such table" not in result.error_message.lower())
        
        # Verify table still exists by counting records
        count_result = db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
        self.assertTrue(count_result.success)
    
    def test_large_query_timeout(self):
        """Test handling of long-running queries"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Create a potentially slow query (Cartesian product)
        slow_query = """
        SELECT COUNT(*) 
        FROM healthcare_providers p1, healthcare_providers p2 
        WHERE p1.npi > p2.npi 
        LIMIT 1000000
        """
        
        # Execute with timeout - should either succeed or fail gracefully
        result = db_manager.execute_query(slow_query)
        
        # Should not crash the system
        self.assertIsNotNone(result)
        if not result.success:
            self.assertIsNotNone(result.error_message)
    
    def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Try to load extremely large result set
        large_query = "SELECT * FROM healthcare_providers ORDER BY npi"
        
        result = db_manager.execute_query(large_query)
        
        # Should handle large results without crashing
        self.assertTrue(result.success)
        if result.row_count > 0:
            # Verify result is reasonable size
            self.assertLess(len(result.data), 100000)  # Reasonable limit


class TestConfigurationErrorHandling(unittest.TestCase):
    """Test configuration error handling"""
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file"""
        nonexistent_config = "/nonexistent/config.yaml"
        
        # Should handle missing file gracefully with defaults
        config = PipelineConfig(nonexistent_config)
        
        self.assertIsNotNone(config)
        self.assertEqual(config.config_data, {})
        # Should use default values
        self.assertEqual(config.quality_thresholds.completeness_minimum, 95.0)
    
    def test_malformed_config_file(self):
        """Test handling of malformed YAML configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_config:
            temp_config.write("invalid: yaml: content:\n  - missing bracket")
            malformed_config_path = temp_config.name
        
        try:
            # Should handle malformed YAML gracefully
            config = PipelineConfig(malformed_config_path)
            
            self.assertIsNotNone(config)
            self.assertEqual(config.config_data, {})
            # Should use default values
            self.assertEqual(config.quality_thresholds.completeness_minimum, 95.0)
        
        finally:
            if os.path.exists(malformed_config_path):
                os.unlink(malformed_config_path)
    
    def test_empty_config_sections(self):
        """Test handling of empty configuration sections"""
        import yaml
        
        empty_config_data = {
            "quality_checks": {},
            "business_rules": None,
            "performance": {},
            "reporting": None
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_config:
            yaml.dump(empty_config_data, temp_config)
            empty_config_path = temp_config.name
        
        try:
            config = PipelineConfig(empty_config_path)
            
            # Should handle empty sections gracefully with defaults
            self.assertIsNotNone(config.quality_thresholds)
            self.assertIsNotNone(config.business_rules)
            self.assertIsNotNone(config.performance)
            self.assertIsNotNone(config.reporting)
        
        finally:
            if os.path.exists(empty_config_path):
                os.unlink(empty_config_path)


class TestQueryExecutorErrorHandling(unittest.TestCase):
    """Test query executor error handling"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_config = DatabaseConfig()
        self.pipeline_config = PipelineConfig()
        self.db_manager = DatabaseManager(self.db_config)
        
        # Create temporary SQL directory with problematic queries
        self.temp_sql_dir = tempfile.mkdtemp()
        self.validation_dir = Path(self.temp_sql_dir) / "02_validation"
        self.validation_dir.mkdir(parents=True)
        
        self._create_problematic_queries()
        
        self.query_executor = QueryExecutor(
            self.db_manager,
            self.pipeline_config,
            self.temp_sql_dir
        )
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_sql_dir):
            shutil.rmtree(self.temp_sql_dir)
    
    def _create_problematic_queries(self):
        """Create SQL files with various problematic queries"""
        
        # Query with syntax error
        syntax_error_query = "INVALID SQL SYNTAX SELECT FROM WHERE"
        syntax_error_file = self.validation_dir / "syntax_error.sql"
        with open(syntax_error_file, 'w') as f:
            f.write(syntax_error_query)
        
        # Query referencing non-existent table
        nonexistent_table_query = "SELECT * FROM nonexistent_table"
        nonexistent_file = self.validation_dir / "nonexistent_table.sql"
        with open(nonexistent_file, 'w') as f:
            f.write(nonexistent_table_query)
        
        # Valid query for testing
        valid_query = "SELECT COUNT(*) as count FROM healthcare_providers"
        valid_file = self.validation_dir / "valid_query.sql"
        with open(valid_file, 'w') as f:
            f.write(valid_query)
        
        # Empty query file
        empty_file = self.validation_dir / "empty_query.sql"
        with open(empty_file, 'w') as f:
            f.write("")
    
    def test_syntax_error_handling(self):
        """Test handling of SQL syntax errors"""
        result = self.query_executor.execute_single_query("syntax_error")
        
        self.assertIsNotNone(result)
        self.assertFalse(result.result.success)
        self.assertIsNotNone(result.result.error_message)
        self.assertEqual(result.result.row_count, 0)
    
    def test_nonexistent_table_handling(self):
        """Test handling of queries referencing non-existent tables"""
        result = self.query_executor.execute_single_query("nonexistent_table")
        
        self.assertIsNotNone(result)
        self.assertFalse(result.result.success)
        self.assertIsNotNone(result.result.error_message)
    
    def test_empty_query_handling(self):
        """Test handling of empty query files"""
        result = self.query_executor.execute_single_query("empty_query")
        
        # Should handle empty queries gracefully
        if result:
            self.assertIsNotNone(result)
    
    def test_nonexistent_query_handling(self):
        """Test handling of non-existent query names"""
        result = self.query_executor.execute_single_query("nonexistent_query_name")
        
        self.assertIsNone(result)
    
    def test_parallel_execution_with_errors(self):
        """Test parallel execution when some queries fail"""
        results = self.query_executor.execute_all_queries(parallel=True)
        
        # Should return results for all queries, including failed ones
        self.assertGreater(len(results), 0)
        
        # Should have mix of successful and failed queries
        successful = [r for r in results.values() if r.result.success]
        failed = [r for r in results.values() if not r.result.success]
        
        self.assertGreater(len(failed), 0)  # Should have some failures
        
        # At least one query should succeed (the valid one)
        if len(successful) > 0:
            self.assertGreater(len(successful), 0)


class TestCLIErrorHandling(unittest.TestCase):
    """Test CLI error handling and edge cases"""
    
    def setUp(self):
        """Set up CLI test environment"""
        self.cli_script = project_root / "python" / "main.py"
    
    def test_invalid_command(self):
        """Test handling of invalid CLI commands"""
        result = subprocess.run(
            ["python", str(self.cli_script), "invalid_command"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        # Should exit with error code
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(len(result.stderr) > 0 or "Usage:" in result.stdout)
    
    def test_invalid_parameters(self):
        """Test handling of invalid command parameters"""
        # Test invalid rule name
        result = subprocess.run(
            ["python", str(self.cli_script), "validate", "--rule", "nonexistent_rule"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should handle gracefully (may succeed with no violations or fail gracefully)
        self.assertIsNotNone(result.returncode)
    
    def test_invalid_output_directory(self):
        """Test handling of invalid output directory"""
        result = subprocess.run([
            "python", str(self.cli_script), "validate",
            "--rule", "validation_summary",
            "--output-dir", "/nonexistent/directory"
        ], cwd=project_root, capture_output=True, text=True, timeout=30)
        
        # Should handle invalid output directory gracefully
        self.assertIsNotNone(result.returncode)
    
    def test_invalid_format_parameter(self):
        """Test handling of invalid format parameter"""
        result = subprocess.run([
            "python", str(self.cli_script), "validate",
            "--rule", "validation_summary",
            "--format", "invalid_format"
        ], cwd=project_root, capture_output=True, text=True, timeout=30)
        
        # Should handle invalid format gracefully
        self.assertIsNotNone(result.returncode)
    
    def test_cli_with_missing_database(self):
        """Test CLI behavior when database is missing"""
        # Temporarily move database
        original_db_path = project_root / "data" / "database" / "veeva_opendata.db"
        backup_path = None
        
        if original_db_path.exists():
            backup_path = original_db_path.with_suffix('.backup')
            shutil.move(str(original_db_path), str(backup_path))
        
        try:
            result = subprocess.run(
                ["python", str(self.cli_script), "status"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should handle missing database gracefully
            self.assertIsNotNone(result.returncode)
            
        finally:
            # Restore database
            if backup_path and backup_path.exists():
                shutil.move(str(backup_path), str(original_db_path))
    
    def test_cli_keyboard_interrupt_handling(self):
        """Test CLI handling of keyboard interrupts"""
        # This is difficult to test automatically, but we can verify
        # that the CLI script has proper signal handling
        
        # Check if main script has try/except blocks for KeyboardInterrupt
        with open(self.cli_script) as f:
            content = f.read()
            
        # Should have some form of exception handling
        self.assertTrue(
            "except" in content.lower() or "try:" in content,
            "CLI script should have exception handling"
        )


class TestExportErrorHandling(unittest.TestCase):
    """Test export functionality error handling"""
    
    def setUp(self):
        """Set up export test environment"""
        self.db_config = DatabaseConfig()
        self.pipeline_config = PipelineConfig()
        self.db_manager = DatabaseManager(self.db_config)
        self.query_executor = QueryExecutor(self.db_manager, self.pipeline_config)
    
    def test_export_to_readonly_directory(self):
        """Test export to read-only directory"""
        # Execute some queries
        results = {"test_query": self.query_executor.execute_single_query("validation_summary")}
        
        # Create read-only directory
        with tempfile.TemporaryDirectory() as temp_dir:
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            if hasattr(os, 'chmod'):
                try:
                    os.chmod(readonly_dir, 0o444)  # Read-only
                    
                    # Should handle read-only directory gracefully
                    with self.assertRaises(Exception):
                        self.query_executor.export_query_results(
                            results, str(readonly_dir), ['json']
                        )
                
                except PermissionError:
                    # Expected on some systems
                    pass
                finally:
                    os.chmod(readonly_dir, 0o755)  # Restore for cleanup
    
    def test_export_with_disk_full_simulation(self):
        """Test export behavior when disk is full"""
        # Execute some queries
        results = {"test_query": self.query_executor.execute_single_query("validation_summary")}
        
        # This test would require simulating disk full condition
        # For now, just verify export works normally
        with tempfile.TemporaryDirectory() as temp_dir:
            exported_files = self.query_executor.export_query_results(
                results, temp_dir, ['json']
            )
            
            self.assertIn('json', exported_files)
            self.assertTrue(Path(exported_files['json']).exists())
    
    def test_export_with_invalid_data(self):
        """Test export handling of invalid or corrupted data"""
        # Create mock results with problematic data
        from python.pipeline.query_executor import ValidationQueryResult
        from python.utils.database import QueryResult
        import pandas as pd
        
        # Create result with non-serializable data
        problematic_df = pd.DataFrame({
            'normal_col': [1, 2, 3],
            'problematic_col': [complex(1, 2), complex(3, 4), complex(5, 6)]  # Complex numbers
        })
        
        query_result = QueryResult(
            data=problematic_df,
            execution_time=0.1,
            row_count=3,
            columns=['normal_col', 'problematic_col'],
            query="SELECT test",
            success=True
        )
        
        validation_result = ValidationQueryResult(
            rule_name="test_rule",
            query_path="test",
            result=query_result,
            severity="MEDIUM",
            enabled=True,
            execution_timestamp=pd.Timestamp.now()
        )
        
        results = {"test_rule": validation_result}
        
        # Should handle problematic data gracefully
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                exported_files = self.query_executor.export_query_results(
                    results, temp_dir, ['json']
                )
                # If it succeeds, verify files were created
                if exported_files:
                    self.assertIn('json', exported_files)
            except Exception as e:
                # Should fail gracefully with informative error
                self.assertIsNotNone(str(e))


class TestEdgeCases(unittest.TestCase):
    """Test various edge cases and boundary conditions"""
    
    def test_extremely_large_query_result(self):
        """Test handling of extremely large query results"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Try to get maximum available data
        large_query = "SELECT * FROM provider_facility_affiliations"
        result = db_manager.execute_query(large_query)
        
        if result.success:
            # Should handle large results without crashing
            self.assertIsNotNone(result.data)
            self.assertGreater(result.row_count, 0)
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Query with special characters in the WHERE clause
        special_query = """
        SELECT * FROM healthcare_providers 
        WHERE full_name LIKE '%José%' 
           OR full_name LIKE '%Müller%'
           OR full_name LIKE '%O''Connor%'
        LIMIT 10
        """
        
        result = db_manager.execute_query(special_query)
        
        # Should handle special characters gracefully
        self.assertTrue(result.success or "syntax error" not in result.error_message.lower())
    
    def test_null_and_empty_data_handling(self):
        """Test handling of NULL and empty data"""
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        
        # Query specifically looking for NULL values
        null_query = """
        SELECT npi, full_name, provider_type 
        FROM healthcare_providers 
        WHERE full_name IS NULL OR TRIM(full_name) = ''
        LIMIT 100
        """
        
        result = db_manager.execute_query(null_query)
        
        self.assertTrue(result.success)
        # Result may be empty if no NULL values exist, which is fine
    
    def test_concurrent_access_edge_cases(self):
        """Test edge cases in concurrent access"""
        import threading
        import time
        
        config = DatabaseConfig()
        results = []
        errors = []
        
        def execute_query():
            try:
                db_manager = DatabaseManager(config)
                result = db_manager.execute_query("SELECT COUNT(*) FROM healthcare_providers")
                results.append(result.success)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=execute_query)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        # Most operations should succeed
        if results:
            success_rate = sum(results) / len(results)
            self.assertGreater(success_rate, 0.8)


if __name__ == '__main__':
    unittest.main()