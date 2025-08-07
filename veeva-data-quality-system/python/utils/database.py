"""
Database utility functions and connection management
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from contextlib import contextmanager
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import Session, sessionmaker
from dataclasses import dataclass
import time
import logging

from ..config.database_config import DatabaseConfig


logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Container for query execution results"""
    data: pd.DataFrame
    execution_time: float
    row_count: int
    columns: List[str]
    query: str
    success: bool = True
    error_message: Optional[str] = None


class DatabaseManager:
    """
    Database connection and query management for Veeva Data Quality System
    Handles SQLite connections, query execution, and result processing
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """Initialize database manager with configuration"""
        self.config = config or DatabaseConfig()
        self.engine = self.config.create_engine()
        self.session_factory = self.config.create_session_factory(self.engine)
        
        logger.info(f"DatabaseManager initialized with database: {self.config.db_path}")
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager  
    def get_connection(self):
        """Context manager for direct database connections"""
        connection = self.engine.connect()
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            connection.close()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """
        Execute SQL query and return structured result
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            QueryResult object with data and metadata
        """
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                # Execute query with pandas for easy result handling
                if params:
                    df = pd.read_sql_query(text(query), conn, params=params)
                else:
                    df = pd.read_sql_query(query, conn)
                
                execution_time = time.time() - start_time
                
                result = QueryResult(
                    data=df,
                    execution_time=execution_time,
                    row_count=len(df),
                    columns=df.columns.tolist(),
                    query=query,
                    success=True
                )
                
                logger.info(f"Query executed successfully: {result.row_count} rows in {result.execution_time:.2f}s")
                return result
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Query execution failed: {error_msg}")
            
            return QueryResult(
                data=pd.DataFrame(),
                execution_time=execution_time,
                row_count=0,
                columns=[],
                query=query,
                success=False,
                error_message=error_msg
            )
    
    def execute_validation_query(self, query_name: str, query: str) -> Dict[str, Any]:
        """
        Execute a validation query and format result for reporting
        
        Args:
            query_name: Name of the validation rule
            query: SQL query string
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Executing validation query: {query_name}")
        
        result = self.execute_query(query)
        
        if not result.success:
            return {
                "rule_name": query_name,
                "status": "ERROR", 
                "error_message": result.error_message,
                "execution_time": result.execution_time,
                "timestamp": pd.Timestamp.now()
            }
        
        # Process validation results
        validation_result = {
            "rule_name": query_name,
            "status": "SUCCESS",
            "row_count": result.row_count,
            "execution_time": result.execution_time,
            "timestamp": pd.Timestamp.now(),
            "data": result.data.to_dict('records') if result.row_count > 0 else [],
            "columns": result.columns
        }
        
        # Add summary statistics if applicable
        if result.row_count > 0:
            validation_result["summary"] = self._generate_validation_summary(result.data)
        
        return validation_result
    
    def _generate_validation_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics for validation results"""
        summary = {
            "total_violations": len(df),
            "unique_entities": df.get('entity_id', pd.Series()).nunique() if 'entity_id' in df.columns else None,
        }
        
        # Add severity distribution if severity column exists
        if 'severity_level' in df.columns:
            severity_counts = df['severity_level'].value_counts().to_dict()
            summary["severity_distribution"] = severity_counts
        
        # Add confidence level distribution if available
        if 'confidence_level' in df.columns:
            confidence_counts = df['confidence_level'].value_counts().to_dict()
            summary["confidence_distribution"] = confidence_counts
        
        return summary
    
    def get_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """
        Get metadata information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with table metadata
        """
        metadata_query = f"""
        SELECT 
            COUNT(*) as row_count,
            COUNT(DISTINCT rowid) as unique_rows
        FROM {table_name}
        """
        
        result = self.execute_query(metadata_query)
        
        if result.success and result.row_count > 0:
            metadata = result.data.iloc[0].to_dict()
            
            # Get column information
            columns_query = f"PRAGMA table_info({table_name})"
            columns_result = self.execute_query(columns_query)
            
            if columns_result.success:
                metadata["columns"] = columns_result.data.to_dict('records')
            
            return metadata
        
        return {"error": "Failed to retrieve table metadata"}
    
    def get_database_overview(self) -> Dict[str, Any]:
        """Get overview of entire database"""
        overview = {
            "database_path": self.config.db_path,
            "tables": {},
            "total_records": 0,
            "timestamp": pd.Timestamp.now()
        }
        
        # Get all table names
        tables_query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
        
        result = self.execute_query(tables_query)
        
        if result.success:
            for table in result.data['name']:
                table_info = self.get_table_metadata(table)
                overview["tables"][table] = table_info
                
                if 'row_count' in table_info:
                    overview["total_records"] += table_info['row_count']
        
        return overview
    
    def execute_batch_queries(self, queries: Dict[str, str]) -> Dict[str, QueryResult]:
        """
        Execute multiple queries in batch
        
        Args:
            queries: Dictionary mapping query names to SQL strings
            
        Returns:
            Dictionary mapping query names to QueryResult objects
        """
        results = {}
        
        logger.info(f"Executing batch of {len(queries)} queries")
        
        for query_name, query in queries.items():
            logger.info(f"Executing query: {query_name}")
            results[query_name] = self.execute_query(query)
        
        # Log batch summary
        successful_queries = sum(1 for r in results.values() if r.success)
        failed_queries = len(queries) - successful_queries
        
        logger.info(f"Batch execution complete: {successful_queries} successful, {failed_queries} failed")
        
        return results
    
    def optimize_database(self) -> Dict[str, Any]:
        """Run database optimization commands"""
        optimization_queries = {
            "analyze": "ANALYZE",
            "vacuum": "VACUUM", 
            "pragma_optimize": "PRAGMA optimize"
        }
        
        logger.info("Starting database optimization")
        
        results = {}
        for operation, query in optimization_queries.items():
            try:
                start_time = time.time()
                with self.get_connection() as conn:
                    conn.execute(text(query))
                execution_time = time.time() - start_time
                
                results[operation] = {
                    "status": "SUCCESS",
                    "execution_time": execution_time
                }
                
                logger.info(f"Database {operation} completed in {execution_time:.2f}s")
                
            except Exception as e:
                results[operation] = {
                    "status": "ERROR", 
                    "error": str(e)
                }
                logger.error(f"Database {operation} failed: {e}")
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        health_status = {
            "timestamp": pd.Timestamp.now(),
            "database_accessible": False,
            "tables_accessible": {},
            "performance_test": {},
            "overall_status": "UNKNOWN"
        }
        
        try:
            # Test basic connectivity
            test_result = self.execute_query("SELECT 1 as test")
            health_status["database_accessible"] = test_result.success
            
            if test_result.success:
                # Test table accessibility
                overview = self.get_database_overview()
                for table_name in overview.get("tables", {}):
                    test_query = f"SELECT COUNT(*) FROM {table_name} LIMIT 1"
                    table_result = self.execute_query(test_query)
                    health_status["tables_accessible"][table_name] = table_result.success
                
                # Simple performance test
                start_time = time.time()
                perf_result = self.execute_query("SELECT COUNT(*) FROM healthcare_providers")
                perf_time = time.time() - start_time
                
                health_status["performance_test"] = {
                    "query_time": perf_time,
                    "acceptable": perf_time < 5.0  # 5 second threshold
                }
                
                # Determine overall status
                all_tables_ok = all(health_status["tables_accessible"].values())
                perf_ok = health_status["performance_test"]["acceptable"]
                
                if all_tables_ok and perf_ok:
                    health_status["overall_status"] = "HEALTHY"
                elif all_tables_ok:
                    health_status["overall_status"] = "WARNING"  # Performance issues
                else:
                    health_status["overall_status"] = "ERROR"    # Table access issues
                    
        except Exception as e:
            health_status["overall_status"] = "ERROR"
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return health_status