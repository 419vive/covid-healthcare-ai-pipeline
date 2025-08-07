"""
Unit tests for QueryExecutor class
Tests SQL query loading, execution, and result processing
"""

import unittest
import tempfile
import sqlite3
import pandas as pd
from pathlib import Path
import os
import sys
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager, QueryResult
from python.pipeline.query_executor import QueryExecutor, ValidationQueryResult


class TestQueryExecutor(unittest.TestCase):
    """Test cases for QueryExecutor class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.test_db_path = self.temp_db.name
        
        # Create temporary SQL directory
        self.temp_sql_dir = tempfile.mkdtemp()
        self.validation_dir = Path(self.temp_sql_dir) / "02_validation"
        self.validation_dir.mkdir(parents=True)
        
        # Create test database and SQL files
        self._create_test_database()
        self._create_test_sql_files()
        
        # Initialize components
        self.db_config = DatabaseConfig(db_path=self.test_db_path)
        self.db_manager = DatabaseManager(self.db_config)
        self.pipeline_config = PipelineConfig()
        
        # Initialize QueryExecutor
        self.query_executor = QueryExecutor(
            self.db_manager,
            self.pipeline_config,
            self.temp_sql_dir
        )
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
        if os.path.exists(self.temp_sql_dir):
            shutil.rmtree(self.temp_sql_dir)
    
    def _create_test_database(self):
        """Create test database with sample data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create test table
        cursor.execute("""
            CREATE TABLE healthcare_providers (
                npi TEXT PRIMARY KEY,
                full_name TEXT,
                provider_type TEXT,
                city TEXT,
                state TEXT
            )
        """)
        
        # Insert test data
        test_data = [
            ('1234567890', 'John Doe', 'PHYSICIAN', 'Boston', 'MA'),
            ('2345678901', 'Jane Smith', 'NURSE', 'Cambridge', 'MA'),
            ('3456789012', '', 'PHYSICIAN', 'Worcester', 'MA'),  # Empty name for testing
            ('4567890123', 'Bob Johnson', 'INVALID_TYPE', 'Springfield', 'MA'),  # Invalid type
        ]
        
        cursor.executemany("""
            INSERT INTO healthcare_providers (npi, full_name, provider_type, city, state)
            VALUES (?, ?, ?, ?, ?)
        """, test_data)
        
        conn.commit()
        conn.close()
    
    def _create_test_sql_files(self):
        """Create test SQL validation query files"""
        
        # Create AI-enhanced validation queries file
        ai_queries_content = """
-- AI Enhanced Validation Queries for Data Quality Testing

-- Query 1: Empty Name Validation
-- Purpose: Find providers with empty or null names
SELECT 
    npi,
    full_name,
    'Empty provider name' as issue_description,
    'HIGH' as severity_level
FROM healthcare_providers 
WHERE full_name IS NULL OR TRIM(full_name) = ''

-- Query 2: Invalid Provider Type Validation  
-- Purpose: Find providers with invalid provider types
SELECT 
    npi,
    full_name,
    provider_type,
    'Invalid provider type: ' || provider_type as issue_description,
    'MEDIUM' as severity_level
FROM healthcare_providers 
WHERE provider_type NOT IN ('PHYSICIAN', 'NURSE', 'THERAPIST', 'TECHNICIAN')

-- Query 3: Basic Count Query
-- Purpose: Count total providers for testing
SELECT 
    COUNT(*) as total_providers,
    'Summary' as category,
    'INFO' as severity_level
FROM healthcare_providers
"""
        
        ai_queries_file = self.validation_dir / "ai_enhanced_validation_queries.sql"
        with open(ai_queries_file, 'w') as f:
            f.write(ai_queries_content)
        
        # Create another validation file
        other_queries_content = """
-- Simple provider validation
SELECT npi, full_name 
FROM healthcare_providers 
WHERE LENGTH(npi) != 10
"""
        
        other_file = self.validation_dir / "npi_length_check.sql"
        with open(other_file, 'w') as f:
            f.write(other_queries_content)
    
    def test_initialization(self):
        """Test QueryExecutor initialization"""
        self.assertIsNotNone(self.query_executor)
        self.assertEqual(self.query_executor.sql_queries_dir, self.temp_sql_dir)
        self.assertIsInstance(self.query_executor.validation_queries, dict)
        self.assertGreater(len(self.query_executor.validation_queries), 0)
    
    def test_load_validation_queries(self):
        """Test loading validation queries from SQL files"""
        queries = self.query_executor.validation_queries
        
        # Should have loaded queries from AI-enhanced file and other files
        self.assertGreater(len(queries), 0)
        
        # Check that AI-enhanced queries were parsed correctly
        expected_queries = ['empty_name_validation', 'invalid_provider_type_validation', 'basic_count_query']
        for query_name in expected_queries:
            self.assertIn(query_name, queries)
            self.assertIsInstance(queries[query_name], str)
            self.assertGreater(len(queries[query_name]), 0)
        
        # Check that other file was loaded
        self.assertIn('npi_length_check', queries)
    
    def test_execute_single_query(self):
        """Test executing a single validation query"""
        # Test executing a query that should find violations
        result = self.query_executor.execute_single_query('empty_name_validation')
        
        self.assertIsInstance(result, ValidationQueryResult)
        self.assertTrue(result.enabled)
        self.assertTrue(result.result.success)
        self.assertEqual(result.result.row_count, 1)  # Should find one empty name
        self.assertIsNotNone(result.execution_timestamp)
        self.assertEqual(result.rule_name, 'empty_name_validation')
    
    def test_execute_single_query_nonexistent(self):
        """Test executing a non-existent validation query"""
        result = self.query_executor.execute_single_query('nonexistent_query')
        
        self.assertIsNone(result)
    
    def test_execute_single_query_with_results(self):
        """Test executing query that returns results"""
        result = self.query_executor.execute_single_query('invalid_provider_type_validation')
        
        self.assertTrue(result.result.success)
        self.assertEqual(result.result.row_count, 1)  # Should find one invalid type
        self.assertGreater(len(result.result.data), 0)
        
        # Check data content
        data = result.result.data.iloc[0]
        self.assertEqual(data['npi'], '4567890123')
        self.assertEqual(data['provider_type'], 'INVALID_TYPE')
    
    def test_execute_single_query_no_violations(self):
        """Test executing query that returns no violations"""
        result = self.query_executor.execute_single_query('npi_length_check')
        
        self.assertTrue(result.result.success)
        self.assertEqual(result.result.row_count, 0)  # All NPIs are 10 digits
    
    def test_execute_all_queries_sequential(self):
        """Test executing all queries sequentially"""
        results = self.query_executor.execute_all_queries(parallel=False)
        
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        
        # All results should be ValidationQueryResult objects
        for rule_name, result in results.items():
            self.assertIsInstance(result, ValidationQueryResult)
            self.assertEqual(result.rule_name, rule_name)
    
    def test_execute_all_queries_parallel(self):
        """Test executing all queries in parallel"""
        results = self.query_executor.execute_all_queries(parallel=True)
        
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        
        # Check that we got results for all queries
        expected_queries = len(self.query_executor.validation_queries)
        self.assertEqual(len(results), expected_queries)
    
    def test_get_query_catalog(self):
        """Test getting catalog of available queries"""
        catalog = self.query_executor.get_query_catalog()
        
        self.assertIsInstance(catalog, list)
        self.assertGreater(len(catalog), 0)
        
        # Check catalog structure
        for item in catalog:
            self.assertIn('rule_name', item)
            self.assertIn('enabled', item)
            self.assertIn('severity', item)
            self.assertIn('query_length', item)
            self.assertIn('description', item)
            
            # Verify types
            self.assertIsInstance(item['rule_name'], str)
            self.assertIsInstance(item['enabled'], bool)
            self.assertIsInstance(item['severity'], str)
            self.assertIsInstance(item['query_length'], int)
    
    def test_generate_query_summary(self):
        """Test query summary generation"""
        # Create test DataFrame
        test_data = pd.DataFrame({
            'npi': ['1234567890', '2345678901'],
            'full_name': ['John Doe', 'Jane Smith'],
            'severity_level': ['HIGH', 'MEDIUM'],
            'confidence_level': ['HIGH', 'LOW'],
            'entity_id': ['ENT001', 'ENT002'],
            'provider_id': ['PROV001', 'PROV002']
        })
        
        summary = self.query_executor._generate_query_summary(test_data, 'test_rule')
        
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary['total_violations'], 2)
        self.assertEqual(summary['rule_name'], 'test_rule')
        self.assertIn('severity_distribution', summary)
        self.assertIn('confidence_distribution', summary)
        self.assertIn('unique_entities_affected', summary)
        self.assertIn('unique_providers_affected', summary)
        self.assertIn('sample_violations', summary)
        
        # Check specific values
        self.assertEqual(summary['severity_distribution']['HIGH'], 1)
        self.assertEqual(summary['severity_distribution']['MEDIUM'], 1)
        self.assertEqual(summary['unique_entities_affected'], 2)
        self.assertEqual(summary['unique_providers_affected'], 2)
    
    def test_export_query_results(self):
        """Test exporting query results to files"""
        # Execute some queries to get results
        results = self.query_executor.execute_all_queries(parallel=False)
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_output:
            exported_files = self.query_executor.export_query_results(
                results, 
                temp_output, 
                formats=['json', 'csv', 'xlsx']
            )
            
            self.assertIn('json', exported_files)
            self.assertIn('csv', exported_files)
            self.assertIn('xlsx', exported_files)
            
            # Verify files exist
            for format_type, file_path in exported_files.items():
                self.assertTrue(Path(file_path).exists())
                self.assertGreater(Path(file_path).stat().st_size, 0)
    
    def test_export_query_results_json_only(self):
        """Test exporting only JSON format"""
        results = self.query_executor.execute_all_queries(parallel=False)
        
        with tempfile.TemporaryDirectory() as temp_output:
            exported_files = self.query_executor.export_query_results(
                results, 
                temp_output, 
                formats=['json']
            )
            
            self.assertEqual(len(exported_files), 1)
            self.assertIn('json', exported_files)
            
            # Load and verify JSON content
            import json
            with open(exported_files['json']) as f:
                data = json.load(f)
            
            self.assertIn('execution_timestamp', data)
            self.assertIn('summary', data)
            self.assertIn('results', data)
    
    def test_extract_ai_enhanced_queries(self):
        """Test extraction of AI-enhanced queries from SQL file"""
        # Create test content
        test_content = """
-- Query 1: Test Query One
-- Purpose: Testing query parsing
SELECT * FROM test1

-- Query 2: Test Query Two  
-- Purpose: Another test query
SELECT * FROM test2
"""
        
        queries = self.query_executor._extract_ai_enhanced_queries(
            test_content, 
            Path("test.sql")
        )
        
        self.assertIsInstance(queries, dict)
        self.assertEqual(len(queries), 2)
        self.assertIn('test_query_one', queries)
        self.assertIn('test_query_two', queries)
        
        # Verify query content
        self.assertIn('SELECT * FROM test1', queries['test_query_one'])
        self.assertIn('SELECT * FROM test2', queries['test_query_two'])
    
    def test_query_with_disabled_rule(self):
        """Test executing a disabled validation rule"""
        # Mock the config to return disabled rule
        mock_rule_config = Mock()
        mock_rule_config.enabled = False
        mock_rule_config.severity = "LOW"
        
        with patch.object(self.query_executor.config, 'get_validation_rule_config', 
                         return_value=mock_rule_config):
            result = self.query_executor.execute_single_query('empty_name_validation')
            
            self.assertFalse(result.enabled)
            self.assertEqual(result.result.row_count, 0)
            self.assertIn("disabled", result.result.error_message.lower())
    
    def test_query_execution_error_handling(self):
        """Test handling of query execution errors"""
        # Add a query with syntax error to the executor
        self.query_executor.validation_queries['syntax_error_query'] = "INVALID SQL SYNTAX"
        
        result = self.query_executor.execute_single_query('syntax_error_query')
        
        self.assertFalse(result.result.success)
        self.assertIsNotNone(result.result.error_message)
        self.assertEqual(result.result.row_count, 0)
    
    def test_parallel_execution_with_errors(self):
        """Test parallel execution when some queries have errors"""
        # Add a problematic query
        self.query_executor.validation_queries['error_query'] = "SELECT * FROM nonexistent_table"
        
        results = self.query_executor.execute_all_queries(parallel=True)
        
        # Should still get results for valid queries
        self.assertGreater(len(results), 0)
        
        # Check that error query failed properly
        if 'error_query' in results:
            error_result = results['error_query']
            self.assertFalse(error_result.result.success)
    
    def test_create_summary_dataframe(self):
        """Test creation of summary DataFrame"""
        # Execute queries to get real results
        results = self.query_executor.execute_all_queries(parallel=False)
        
        summary_df = self.query_executor._create_summary_dataframe(results)
        
        self.assertIsInstance(summary_df, pd.DataFrame)
        self.assertEqual(len(summary_df), len(results))
        
        # Check required columns
        expected_columns = [
            'rule_name', 'enabled', 'severity', 'success',
            'violation_count', 'execution_time_seconds', 
            'execution_timestamp', 'error_message'
        ]
        
        for col in expected_columns:
            self.assertIn(col, summary_df.columns)
    
    def test_create_summary_dict(self):
        """Test creation of summary dictionary"""
        results = self.query_executor.execute_all_queries(parallel=False)
        
        summary = self.query_executor._create_summary_dict(results)
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_queries', summary)
        self.assertIn('successful_queries', summary)
        self.assertIn('failed_queries', summary)
        self.assertIn('total_violations', summary)
        self.assertIn('severity_distribution', summary)
        
        # Verify values make sense
        self.assertEqual(summary['total_queries'], len(results))
        self.assertGreaterEqual(summary['successful_queries'], 0)
        self.assertGreaterEqual(summary['failed_queries'], 0)
        self.assertEqual(
            summary['total_queries'], 
            summary['successful_queries'] + summary['failed_queries']
        )


class TestValidationQueryResult(unittest.TestCase):
    """Test cases for ValidationQueryResult dataclass"""
    
    def test_validation_query_result_creation(self):
        """Test ValidationQueryResult creation"""
        query_result = QueryResult(
            data=pd.DataFrame({'test': [1]}),
            execution_time=0.1,
            row_count=1,
            columns=['test'],
            query="SELECT 1",
            success=True
        )
        
        validation_result = ValidationQueryResult(
            rule_name="test_rule",
            query_path="/path/to/sql",
            result=query_result,
            severity="HIGH",
            enabled=True,
            execution_timestamp=pd.Timestamp.now()
        )
        
        self.assertEqual(validation_result.rule_name, "test_rule")
        self.assertEqual(validation_result.severity, "HIGH")
        self.assertTrue(validation_result.enabled)
        self.assertIsNotNone(validation_result.execution_timestamp)
        self.assertEqual(validation_result.result, query_result)


if __name__ == '__main__':
    unittest.main()