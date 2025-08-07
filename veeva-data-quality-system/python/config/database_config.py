"""
Database configuration management
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session


@dataclass
class DatabaseConfig:
    """Database configuration and connection management"""
    
    db_path: str = "data/database/veeva_opendata.db"
    echo_sql: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    
    def __post_init__(self):
        """Ensure database path is absolute"""
        if not os.path.isabs(self.db_path):
            # Get project root directory
            project_root = Path(__file__).parent.parent.parent
            self.db_path = str(project_root / self.db_path)
    
    @property
    def connection_string(self) -> str:
        """Get SQLAlchemy connection string"""
        return f"sqlite:///{self.db_path}"
    
    def create_engine(self) -> Engine:
        """Create SQLAlchemy engine with optimized settings"""
        return create_engine(
            self.connection_string,
            echo=self.echo_sql,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            # SQLite specific optimizations
            connect_args={
                "check_same_thread": False,
                "timeout": 20,
                # Enable WAL mode for better concurrency
                "isolation_level": None,
            },
            # Enable connection pooling
            poolclass=None,  # Use default StaticPool for SQLite
        )
    
    def create_session_factory(self, engine: Optional[Engine] = None) -> sessionmaker:
        """Create session factory"""
        if engine is None:
            engine = self.create_engine()
        
        return sessionmaker(
            bind=engine,
            autoflush=True,
            autocommit=False,
            expire_on_commit=False
        )
    
    def get_session(self) -> Session:
        """Get database session"""
        engine = self.create_engine()
        session_factory = self.create_session_factory(engine)
        return session_factory()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            engine = self.create_engine()
            with engine.connect() as conn:
                # Test basic query
                result = conn.execute("SELECT 1 as test")
                return result.fetchone()[0] == 1
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False
    
    def get_table_info(self) -> dict:
        """Get information about database tables"""
        try:
            engine = self.create_engine()
            with engine.connect() as conn:
                # Get all table names
                tables_result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """)
                tables = [row[0] for row in tables_result.fetchall()]
                
                table_info = {}
                for table in tables:
                    # Get row count for each table
                    count_result = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = count_result.fetchone()[0]
                    table_info[table] = {"row_count": count}
                
                return table_info
        except Exception as e:
            print(f"Failed to get table info: {e}")
            return {}
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create config from environment variables"""
        return cls(
            db_path=os.getenv("VEEVA_DB_PATH", "data/database/veeva_opendata.db"),
            echo_sql=os.getenv("VEEVA_DB_ECHO", "false").lower() == "true",
            pool_size=int(os.getenv("VEEVA_DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("VEEVA_DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("VEEVA_DB_POOL_TIMEOUT", "30")),
        )