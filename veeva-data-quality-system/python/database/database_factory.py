"""
Database factory for creating appropriate database managers
"""

from typing import Dict, Any, Optional
from .abstract_database import AbstractDatabaseManager, DatabaseConfig
from .sqlite_database import SQLiteDatabaseManager
from .postgresql_database import PostgreSQLDatabaseManager
from .mysql_database import MySQLDatabaseManager
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseFactory:
    """
    Factory for creating database managers based on configuration
    Supports SQLite, PostgreSQL, and MySQL with automatic failover
    """
    
    _instances: Dict[str, AbstractDatabaseManager] = {}
    
    @classmethod
    async def create_database_manager(cls, config: DatabaseConfig) -> AbstractDatabaseManager:
        """
        Create and initialize appropriate database manager
        
        Args:
            config: Database configuration
            
        Returns:
            Initialized database manager instance
        """
        # Create unique key for manager instances
        instance_key = f"{config.db_type}_{config.database}_{config.host or 'local'}"
        
        # Return existing instance if available
        if instance_key in cls._instances:
            return cls._instances[instance_key]
        
        # Create new manager based on database type
        manager = None
        
        if config.db_type.lower() == 'sqlite':
            manager = SQLiteDatabaseManager(config)
        elif config.db_type.lower() == 'postgresql':
            manager = PostgreSQLDatabaseManager(config)
        elif config.db_type.lower() == 'mysql':
            manager = MySQLDatabaseManager(config)
        else:
            raise ValueError(f"Unsupported database type: {config.db_type}")
        
        # Initialize the manager
        try:
            await manager.initialize()
            cls._instances[instance_key] = manager
            logger.info(f"Database manager created: {config.db_type} - {instance_key}")
            return manager
            
        except Exception as e:
            logger.error(f"Failed to initialize {config.db_type} manager: {e}")
            raise
    
    @classmethod
    def from_environment(cls) -> DatabaseConfig:
        """
        Create database configuration from environment variables
        
        Returns:
            DatabaseConfig instance
        """
        import os
        
        db_type = os.getenv('VEEVA_DB_TYPE', 'sqlite').lower()
        
        config = DatabaseConfig(
            db_type=db_type,
            host=os.getenv('VEEVA_DB_HOST'),
            port=int(os.getenv('VEEVA_DB_PORT', 5432)) if os.getenv('VEEVA_DB_PORT') else None,
            database=os.getenv('VEEVA_DB_NAME', 'data/database/veeva_opendata.db'),
            username=os.getenv('VEEVA_DB_USER'),
            password=os.getenv('VEEVA_DB_PASSWORD'),
            connection_pool_size=int(os.getenv('VEEVA_DB_POOL_SIZE', 10)),
            max_overflow=int(os.getenv('VEEVA_DB_MAX_OVERFLOW', 20)),
            pool_timeout=int(os.getenv('VEEVA_DB_POOL_TIMEOUT', 30))
        )
        
        # Parse read replicas if provided
        replicas_str = os.getenv('VEEVA_DB_READ_REPLICAS')
        if replicas_str:
            config.read_replicas = [url.strip() for url in replicas_str.split(',')]
        
        # Parse sharding config if provided
        sharding_str = os.getenv('VEEVA_DB_SHARDING_CONFIG')
        if sharding_str:
            import json
            try:
                config.sharding_config = json.loads(sharding_str)
            except json.JSONDecodeError:
                logger.warning("Invalid sharding configuration in environment")
        
        return config
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> DatabaseConfig:
        """
        Create database configuration from dictionary
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            DatabaseConfig instance
        """
        return DatabaseConfig(**config_dict)
    
    @classmethod
    async def create_migration_manager(cls, 
                                     source_config: DatabaseConfig, 
                                     target_config: DatabaseConfig) -> 'DatabaseMigrationManager':
        """
        Create migration manager for database migrations
        
        Args:
            source_config: Source database configuration
            target_config: Target database configuration
            
        Returns:
            DatabaseMigrationManager instance
        """
        from .migration_manager import DatabaseMigrationManager
        
        source_manager = await cls.create_database_manager(source_config)
        target_manager = await cls.create_database_manager(target_config)
        
        return DatabaseMigrationManager(source_manager, target_manager)
    
    @classmethod
    async def create_sharded_manager(cls, 
                                   primary_config: DatabaseConfig,
                                   shard_configs: List[DatabaseConfig]) -> 'ShardedDatabaseManager':
        """
        Create sharded database manager
        
        Args:
            primary_config: Primary database configuration
            shard_configs: List of shard configurations
            
        Returns:
            ShardedDatabaseManager instance
        """
        from .sharded_database import ShardedDatabaseManager
        
        primary_manager = await cls.create_database_manager(primary_config)
        shard_managers = []
        
        for shard_config in shard_configs:
            shard_manager = await cls.create_database_manager(shard_config)
            shard_managers.append(shard_manager)
        
        return ShardedDatabaseManager(primary_manager, shard_managers)
    
    @classmethod
    async def close_all_connections(cls) -> None:
        """Close all database connections"""
        for manager in cls._instances.values():
            try:
                await manager.close()
            except Exception as e:
                logger.error(f"Error closing database manager: {e}")
        
        cls._instances.clear()
        logger.info("All database connections closed")
    
    @classmethod
    def get_supported_databases(cls) -> List[str]:
        """Get list of supported database types"""
        return ['sqlite', 'postgresql', 'mysql']
    
    @classmethod
    async def test_configuration(cls, config: DatabaseConfig) -> Dict[str, Any]:
        """
        Test database configuration
        
        Args:
            config: Database configuration to test
            
        Returns:
            Test results dictionary
        """
        test_results = {
            "config_valid": False,
            "connection_successful": False,
            "performance_acceptable": False,
            "error_message": None,
            "connection_time": None,
            "query_time": None
        }
        
        try:
            # Validate configuration
            if not config.db_type in cls.get_supported_databases():
                raise ValueError(f"Unsupported database type: {config.db_type}")
            
            test_results["config_valid"] = True
            
            # Test connection
            import time
            start_time = time.time()
            manager = await cls.create_database_manager(config)
            connection_time = time.time() - start_time
            
            test_results["connection_successful"] = True
            test_results["connection_time"] = connection_time
            
            # Test query performance
            start_time = time.time()
            health_result = await manager.health_check()
            query_time = time.time() - start_time
            
            test_results["query_time"] = query_time
            test_results["performance_acceptable"] = query_time < 5.0
            test_results["health_check"] = health_result
            
            # Clean up test connection
            await manager.close()
            
        except Exception as e:
            test_results["error_message"] = str(e)
            logger.error(f"Database configuration test failed: {e}")
        
        return test_results