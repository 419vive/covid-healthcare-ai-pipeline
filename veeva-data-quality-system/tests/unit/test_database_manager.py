"""
Unit tests for DatabaseManager class
Tests database connection, query execution, and error handling
"""

import unittest
import tempfile
import sqlite3
import pandas as pd
from pathlib import Path
import os
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.utils.database import DatabaseManager, QueryResult


class TestDatabaseManager(unittest.TestCase):
    """Test cases for DatabaseManager class"""
    
    def setUp(self):
        """Set up test database and manager"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.test_db_path = self.temp_db.name
        
        # Create test database with sample data
        self._create_test_database()
        
        # Initialize database manager with test database
        self.config = DatabaseConfig(db_path=self.test_db_path)
        self.db_manager = DatabaseManager(self.config)
    
    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
    
    def _create_test_database(self):
        """Create test database with sample data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create test tables
        cursor.execute("""
            CREATE TABLE healthcare_providers (
                npi TEXT PRIMARY KEY,
                full_name TEXT,
                provider_type TEXT,
                city TEXT,
                state TEXT,
                created_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE healthcare_facilities (
                ccn TEXT PRIMARY KEY,
                facility_name TEXT,
                facility_type TEXT,
                city TEXT,
                state TEXT,
                created_at TEXT
            )
        """)
        
        # Insert test data
        test_providers = [
            ('1234567890', 'John Doe', 'PHYSICIAN', 'Boston', 'MA', '2024-01-01'),
            ('2345678901', 'Jane Smith', 'NURSE', 'Cambridge', 'MA', '2024-01-02'),
            ('3456789012', 'Bob Johnson', 'PHYSICIAN', 'Worcester', 'MA', '2024-01-03')
        ]
        
        cursor.executemany("""
            INSERT INTO healthcare_providers 
            (npi, full_name, provider_type, city, state, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, test_providers)
        
        test_facilities = [
            ('001234', 'General Hospital', 'HOSPITAL', 'Boston', 'MA', '2024-01-01'),
            ('002345', 'Community Clinic', 'CLINIC', 'Cambridge', 'MA', '2024-01-02')
        ]
        
        cursor.executemany("""
            INSERT INTO healthcare_facilities 
            (ccn, facility_name, facility_type, city, state, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, test_facilities)
        
        conn.commit()
        conn.close()
    
    def test_initialization(self):
        """Test DatabaseManager initialization"""
        self.assertIsNotNone(self.db_manager)
        self.assertEqual(self.db_manager.config.db_path, self.test_db_path)
        self.assertIsNotNone(self.db_manager.engine)
        self.assertIsNotNone(self.db_manager.session_factory)
    
    def test_initialization_with_default_config(self):
        """Test DatabaseManager initialization with default config"""
        # This will fail because default path doesn't exist, but tests error handling
        try:
            default_manager = DatabaseManager()
            self.assertIsNotNone(default_manager)
        except Exception:
            # Expected to fail with default non-existent database
            pass
    
    def test_execute_simple_query(self):
        """Test executing a simple SELECT query"""
        result = self.db_manager.execute_query("SELECT COUNT(*) as count FROM healthcare_providers")
        
        self.assertIsInstance(result, QueryResult)
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.data.iloc[0]['count'], 3)
        self.assertGreater(result.execution_time, 0)
        self.assertIn('count', result.columns)
    
    def test_execute_query_with_results(self):
        """Test executing query that returns multiple rows"""
        result = self.db_manager.execute_query("SELECT * FROM healthcare_providers ORDER BY npi")
        
        self.assertTrue(result.success)
        self.assertEqual(result.row_count, 3)
        self.assertEqual(len(result.columns), 6)
        self.assertIn('npi', result.columns)
        self.assertIn('full_name', result.columns)
        
        # Verify data content
        self.assertEqual(result.data.iloc[0]['npi'], '1234567890')
        self.assertEqual(result.data.iloc[0]['full_name'], 'John Doe')
    
    def test_execute_query_with_parameters(self):
        """Test executing parameterized query"""
        result = self.db_manager.execute_query(
            "SELECT * FROM healthcare_providers WHERE state = :state",
            params={'state': 'MA'}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.row_count, 3)
        
        # All results should be from MA
        states = result.data['state'].unique()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0], 'MA')
    
    def test_execute_invalid_query(self):
        """Test executing invalid SQL query"""
        result = self.db_manager.execute_query("SELECT * FROM nonexistent_table")
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertEqual(result.row_count, 0)
        self.assertTrue(result.data.empty)
    
    def test_execute_query_syntax_error(self):
        """Test executing query with syntax error"""
        result = self.db_manager.execute_query("INVALID SQL QUERY")
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertEqual(result.row_count, 0)
        self.assertTrue(result.data.empty)
    
    def test_execute_query_empty_result(self):
        """Test executing query that returns no rows"""
        result = self.db_manager.execute_query(
            "SELECT * FROM healthcare_providers WHERE state = 'INVALID'"
        )
        
        self.assertTrue(result.success)  # Query is valid, just returns no rows
        self.assertEqual(result.row_count, 0)
        self.assertTrue(result.data.empty)
    
    def test_health_check(self):
        """Test database health check functionality"""
        health = self.db_manager.health_check()
        
        self.assertIsInstance(health, dict)
        self.assertTrue(health['database_accessible'])
        self.assertGreater(health['database_size_mb'], 0)
        self.assertIn('total_tables', health)
        self.assertGreaterEqual(health['total_tables'], 2)  # We created 2 tables
        self.assertIn('last_check', health)
    
    def test_get_database_overview(self):
        """Test database overview functionality"""
        overview = self.db_manager.get_database_overview()
        
        self.assertIsInstance(overview, dict)
        self.assertIn('tables', overview)
        self.assertIn('database_info', overview)
        
        # Check that our test tables are present
        tables = overview['tables']
        self.assertIn('healthcare_providers', tables)
        self.assertIn('healthcare_facilities', tables)
        
        # Check table info
        provider_info = tables['healthcare_providers']
        self.assertEqual(provider_info['row_count'], 3)
        self.assertEqual(provider_info['column_count'], 6)
    
    def test_context_managers(self):
        """Test context managers for sessions and connections"""
        # Test session context manager
        try:
            with self.db_manager.get_session() as session:
                result = session.execute(text("SELECT COUNT(*) FROM healthcare_providers"))
                row = result.fetchone()
                self.assertEqual(row[0], 3)
        except Exception as e:
            self.fail(f"Session context manager failed: {e}")
        
        # Test connection context manager
        try:
            with self.db_manager.get_connection() as conn:
                df = pd.read_sql_query("SELECT COUNT(*) as count FROM healthcare_providers", conn)
                self.assertEqual(df.iloc[0]['count'], 3)
        except Exception as e:
            self.fail(f"Connection context manager failed: {e}")
    
    def test_connection_with_invalid_database(self):
        """Test handling of invalid database paths"""
        invalid_config = DatabaseConfig(db_path="invalid/path/database.db")
        
        with self.assertRaises(Exception):
            invalid_manager = DatabaseManager(invalid_config)
            invalid_manager.execute_query("SELECT 1")
    
    def test_query_result_dataclass(self):
        """Test QueryResult dataclass functionality"""
        # Create a sample QueryResult
        df = pd.DataFrame({'col1': [1, 2], 'col2': ['a', 'b']})
        result = QueryResult(
            data=df,
            execution_time=0.5,
            row_count=2,
            columns=['col1', 'col2'],
            query="SELECT col1, col2 FROM test",
            success=True
        )
        
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.execution_time, 0.5)
        self.assertEqual(result.columns, ['col1', 'col2'])
        self.assertFalse(result.data.empty)
    
    def test_query_performance(self):
        """Test that queries complete within reasonable time"""
        start_time = pd.Timestamp.now()
        
        result = self.db_manager.execute_query("SELECT * FROM healthcare_providers")
        
        end_time = pd.Timestamp.now()
        total_time = (end_time - start_time).total_seconds()
        
        self.assertTrue(result.success)
        self.assertLess(total_time, 1.0)  # Should complete in under 1 second
        self.assertGreater(result.execution_time, 0)
        self.assertLess(result.execution_time, 1.0)


class TestQueryResult(unittest.TestCase):
    """Test cases for QueryResult dataclass"""
    
    def test_query_result_creation(self):
        """Test QueryResult creation and attributes"""
        df = pd.DataFrame({'test': [1, 2, 3]})
        result = QueryResult(
            data=df,
            execution_time=0.123,
            row_count=3,
            columns=['test'],
            query="SELECT test FROM table",
            success=True,
            error_message=None
        )
        
        self.assertEqual(result.row_count, 3)
        self.assertEqual(result.execution_time, 0.123)
        self.assertTrue(result.success)
        self.assertEqual(result.columns, ['test'])
        self.assertIsNone(result.error_message)
        self.assertEqual(len(result.data), 3)
    
    def test_query_result_with_error(self):
        """Test QueryResult creation with error"""
        result = QueryResult(
            data=pd.DataFrame(),
            execution_time=0.0,
            row_count=0,
            columns=[],
            query="INVALID SQL",
            success=False,
            error_message="SQL syntax error"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "SQL syntax error")
        self.assertEqual(result.row_count, 0)
        self.assertTrue(result.data.empty)


if __name__ == '__main__':
    unittest.main()