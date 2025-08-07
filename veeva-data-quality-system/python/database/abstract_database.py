"""
Abstract database interface for multi-database support
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass
import pandas as pd
from contextlib import asynccontextmanager


@dataclass
class DatabaseConfig:
    """Unified database configuration"""
    db_type: str  # 'sqlite', 'postgresql', 'mysql'
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    read_replicas: List[str] = None
    sharding_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.read_replicas is None:
            self.read_replicas = []


@dataclass
class QueryResult:
    """Standardized query result across all database types"""
    data: pd.DataFrame
    execution_time: float
    row_count: int
    columns: List[str]
    query: str
    success: bool = True
    error_message: Optional[str] = None
    shard_info: Optional[Dict[str, Any]] = None


class AbstractDatabaseManager(ABC):
    """
    Abstract database manager providing unified interface
    for SQLite, PostgreSQL, and MySQL databases
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection_pool = None
        self._read_replica_manager = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and pool"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections"""
        pass
    
    @abstractmethod
    async def execute_query(self, 
                           query: str, 
                           params: Optional[Dict[str, Any]] = None,
                           read_only: bool = False) -> QueryResult:
        """Execute SQL query"""
        pass
    
    @abstractmethod
    async def execute_batch(self, 
                           queries: List[str],
                           read_only: bool = False) -> List[QueryResult]:
        """Execute multiple queries in batch"""
        pass
    
    @abstractmethod
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table metadata"""
        pass
    
    @abstractmethod
    async def optimize_database(self) -> Dict[str, Any]:
        """Run database optimization"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        pass
    
    @abstractmethod
    async def create_indexes(self, 
                            table_name: str, 
                            indexes: List[Dict[str, Any]]) -> bool:
        """Create database indexes"""
        pass
    
    @abstractmethod
    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager"""
        pass
    
    @abstractmethod
    async def get_shard_for_query(self, query: str) -> str:
        """Determine which shard to use for query"""
        pass
    
    # Common helper methods
    def get_connection_string(self) -> str:
        """Get database connection string"""
        if self.config.db_type == 'sqlite':
            return f"sqlite:///{self.config.database}"
        elif self.config.db_type == 'postgresql':
            return f"postgresql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        elif self.config.db_type == 'mysql':
            return f"mysql+pymysql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.config.db_type}")
    
    def supports_sharding(self) -> bool:
        """Check if database supports sharding"""
        return self.config.sharding_config is not None
    
    def supports_read_replicas(self) -> bool:
        """Check if read replicas are configured"""
        return len(self.config.read_replicas) > 0