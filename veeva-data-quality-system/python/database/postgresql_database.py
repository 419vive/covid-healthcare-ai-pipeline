"""
PostgreSQL database manager implementation
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
import pandas as pd
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from .abstract_database import AbstractDatabaseManager, DatabaseConfig, QueryResult
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class PostgreSQLDatabaseManager(AbstractDatabaseManager):
    """
    PostgreSQL implementation with connection pooling,
    read replicas, and sharding support
    """
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._engine = None
        self._session_factory = None
        self._connection_pool = None
        self._read_replica_pools = {}
    
    async def initialize(self) -> None:
        """Initialize PostgreSQL connections and pools"""
        try:
            # Create async engine with connection pooling
            connection_string = self.get_connection_string().replace('postgresql://', 'postgresql+asyncpg://')
            
            self._engine = create_async_engine(
                connection_string,
                pool_size=self.config.connection_pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                echo=False,
                # PostgreSQL specific optimizations
                connect_args={
                    "server_settings": {
                        "jit": "off",  # Disable JIT for better performance on analytical queries
                        "shared_preload_libraries": "pg_stat_statements",
                        "work_mem": "256MB",
                        "maintenance_work_mem": "512MB",
                        "effective_cache_size": "4GB",
                        "random_page_cost": "1.1",
                        "checkpoint_completion_target": "0.9"
                    }
                }
            )
            
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Initialize read replica connections
            await self._initialize_read_replicas()
            
            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info("PostgreSQL database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL manager: {e}")
            raise
    
    async def _initialize_read_replicas(self) -> None:
        """Initialize read replica connections"""
        if not self.config.read_replicas:
            return
        
        for replica_url in self.config.read_replicas:
            try:
                replica_engine = create_async_engine(
                    replica_url,
                    pool_size=self.config.connection_pool_size // 2,
                    max_overflow=self.config.max_overflow // 2,
                    pool_timeout=self.config.pool_timeout
                )
                
                # Test replica connection
                async with replica_engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                
                self._read_replica_pools[replica_url] = replica_engine
                logger.info(f"Read replica initialized: {replica_url}")
                
            except Exception as e:
                logger.warning(f"Failed to initialize read replica {replica_url}: {e}")
    
    async def close(self) -> None:
        """Close all database connections"""
        try:
            if self._engine:
                await self._engine.dispose()
            
            for replica_engine in self._read_replica_pools.values():
                await replica_engine.dispose()
            
            self._read_replica_pools.clear()
            logger.info("PostgreSQL connections closed")
            
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connections: {e}")
    
    async def execute_query(self, 
                           query: str, 
                           params: Optional[Dict[str, Any]] = None,
                           read_only: bool = False) -> QueryResult:
        """Execute SQL query with automatic read replica routing"""
        start_time = time.time()
        
        try:
            # Route read-only queries to replicas if available
            engine = self._get_engine_for_query(read_only)
            
            async with engine.begin() as conn:
                if params:
                    df = await asyncio.to_thread(
                        pd.read_sql_query, 
                        text(query), 
                        conn.sync_connection, 
                        params=params
                    )
                else:
                    df = await asyncio.to_thread(
                        pd.read_sql_query, 
                        query, 
                        conn.sync_connection
                    )
                
                execution_time = time.time() - start_time
                
                return QueryResult(
                    data=df,
                    execution_time=execution_time,
                    row_count=len(df),
                    columns=df.columns.tolist(),
                    query=query,
                    success=True
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"PostgreSQL query execution failed: {e}")
            
            return QueryResult(
                data=pd.DataFrame(),
                execution_time=execution_time,
                row_count=0,
                columns=[],
                query=query,
                success=False,
                error_message=str(e)
            )
    
    def _get_engine_for_query(self, read_only: bool):
        """Get appropriate engine based on query type"""
        if read_only and self._read_replica_pools:
            # Simple round-robin selection of read replicas
            replicas = list(self._read_replica_pools.values())
            return replicas[hash(time.time()) % len(replicas)]
        return self._engine
    
    async def execute_batch(self, 
                           queries: List[str],
                           read_only: bool = False) -> List[QueryResult]:
        """Execute multiple queries efficiently"""
        if read_only:
            # Distribute read queries across replicas
            return await self._execute_batch_distributed(queries)
        else:
            # Execute write queries on primary
            return await self._execute_batch_sequential(queries)
    
    async def _execute_batch_distributed(self, queries: List[str]) -> List[QueryResult]:
        """Execute read queries distributed across replicas"""
        if not self._read_replica_pools:
            return await self._execute_batch_sequential(queries)
        
        # Distribute queries across available replicas
        replicas = list(self._read_replica_pools.values())
        tasks = []
        
        for i, query in enumerate(queries):
            replica = replicas[i % len(replicas)]
            task = asyncio.create_task(
                self._execute_single_query_on_engine(query, replica)
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def _execute_batch_sequential(self, queries: List[str]) -> List[QueryResult]:
        """Execute queries sequentially on primary"""
        results = []
        for query in queries:
            result = await self.execute_query(query, read_only=False)
            results.append(result)
        return results
    
    async def _execute_single_query_on_engine(self, query: str, engine) -> QueryResult:
        """Execute single query on specific engine"""
        start_time = time.time()
        
        try:
            async with engine.begin() as conn:
                df = await asyncio.to_thread(
                    pd.read_sql_query, 
                    query, 
                    conn.sync_connection
                )
                
                execution_time = time.time() - start_time
                
                return QueryResult(
                    data=df,
                    execution_time=execution_time,
                    row_count=len(df),
                    columns=df.columns.tolist(),
                    query=query,
                    success=True
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return QueryResult(
                data=pd.DataFrame(),
                execution_time=execution_time,
                row_count=0,
                columns=[],
                query=query,
                success=False,
                error_message=str(e)
            )
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get PostgreSQL table information"""
        info_query = """
        SELECT 
            schemaname,
            tablename,
            tableowner,
            tablespace,
            hasindexes,
            hasrules,
            hastriggers
        FROM pg_tables 
        WHERE tablename = :table_name
        """
        
        stats_query = """
        SELECT 
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze
        FROM pg_stat_user_tables 
        WHERE relname = :table_name
        """
        
        try:
            info_result = await self.execute_query(info_query, {"table_name": table_name}, read_only=True)
            stats_result = await self.execute_query(stats_query, {"table_name": table_name}, read_only=True)
            
            table_info = {}
            if info_result.success and not info_result.data.empty:
                table_info.update(info_result.data.iloc[0].to_dict())
            
            if stats_result.success and not stats_result.data.empty:
                table_info.update(stats_result.data.iloc[0].to_dict())
            
            return table_info
            
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return {"error": str(e)}
    
    async def optimize_database(self) -> Dict[str, Any]:
        """Run PostgreSQL optimization commands"""
        optimization_queries = {
            "analyze": "ANALYZE",
            "vacuum": "VACUUM ANALYZE",
            "reindex": "REINDEX DATABASE CONCURRENTLY",
            "update_stats": "SELECT pg_stat_reset()"
        }
        
        results = {}
        for operation, query in optimization_queries.items():
            try:
                start_time = time.time()
                result = await self.execute_query(query)
                execution_time = time.time() - start_time
                
                results[operation] = {
                    "status": "SUCCESS" if result.success else "ERROR",
                    "execution_time": execution_time,
                    "error": result.error_message if not result.success else None
                }
                
            except Exception as e:
                results[operation] = {
                    "status": "ERROR",
                    "error": str(e)
                }
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform PostgreSQL health check"""
        health_status = {
            "database_type": "postgresql",
            "timestamp": pd.Timestamp.now(),
            "primary_accessible": False,
            "replicas_accessible": {},
            "connection_pool_status": {},
            "performance_metrics": {},
            "overall_status": "UNKNOWN"
        }
        
        try:
            # Test primary connection
            test_result = await self.execute_query("SELECT version()", read_only=False)
            health_status["primary_accessible"] = test_result.success
            
            if test_result.success:
                health_status["database_version"] = test_result.data.iloc[0, 0]
            
            # Test read replicas
            for replica_url, replica_engine in self._read_replica_pools.items():
                try:
                    replica_result = await self._execute_single_query_on_engine("SELECT 1", replica_engine)
                    health_status["replicas_accessible"][replica_url] = replica_result.success
                except Exception as e:
                    health_status["replicas_accessible"][replica_url] = False
            
            # Connection pool metrics
            if self._engine:
                pool = self._engine.pool
                health_status["connection_pool_status"] = {
                    "pool_size": pool.size(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "checked_in": pool.checkedin()
                }
            
            # Performance test
            start_time = time.time()
            perf_result = await self.execute_query("SELECT COUNT(*) FROM healthcare_providers", read_only=True)
            perf_time = time.time() - start_time
            
            health_status["performance_metrics"] = {
                "query_time": perf_time,
                "acceptable": perf_time < 5.0
            }
            
            # Overall status assessment
            primary_ok = health_status["primary_accessible"]
            replicas_ok = all(health_status["replicas_accessible"].values()) if health_status["replicas_accessible"] else True
            perf_ok = health_status["performance_metrics"]["acceptable"]
            
            if primary_ok and replicas_ok and perf_ok:
                health_status["overall_status"] = "HEALTHY"
            elif primary_ok and replicas_ok:
                health_status["overall_status"] = "WARNING"
            else:
                health_status["overall_status"] = "ERROR"
        
        except Exception as e:
            health_status["overall_status"] = "ERROR"
            health_status["error"] = str(e)
        
        return health_status
    
    async def create_indexes(self, 
                            table_name: str, 
                            indexes: List[Dict[str, Any]]) -> bool:
        """Create PostgreSQL indexes"""
        try:
            for index_config in indexes:
                index_name = index_config.get("name", f"idx_{table_name}_{index_config['column']}")
                column = index_config["column"]
                index_type = index_config.get("type", "btree")
                unique = "UNIQUE " if index_config.get("unique", False) else ""
                
                create_index_query = f"""
                CREATE {unique}INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON {table_name} USING {index_type} ({column})
                """
                
                result = await self.execute_query(create_index_query)
                if not result.success:
                    logger.error(f"Failed to create index {index_name}: {result.error_message}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            return False
    
    @asynccontextmanager
    async def transaction(self):
        """PostgreSQL transaction context manager"""
        async with self._session_factory() as session:
            try:
                await session.begin()
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def get_shard_for_query(self, query: str) -> str:
        """Determine shard for query (placeholder for future implementation)"""
        # This would implement sharding logic based on query analysis
        # For now, return default shard
        return "default"