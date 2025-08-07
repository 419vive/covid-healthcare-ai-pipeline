"""
Multi-level cache manager with Redis and in-memory caching
"""

import asyncio
import hashlib
import json
import pickle
import time
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd

from .redis_cache import RedisCache
from .memory_cache import MemoryCache
from .cache_strategies import CacheStrategy, LRUStrategy, TTLStrategy
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class CacheLevel(Enum):
    """Cache level enumeration"""
    MEMORY = "memory"
    REDIS = "redis"
    BOTH = "both"


@dataclass
class CacheConfig:
    """Cache configuration"""
    redis_enabled: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ttl: int = 3600  # 1 hour
    memory_size: int = 1000  # Max items in memory cache
    memory_ttl: int = 300  # 5 minutes
    compression_enabled: bool = True
    serialization_format: str = "pickle"  # 'pickle', 'json'


@dataclass
class CacheKey:
    """Structured cache key"""
    namespace: str
    key: str
    version: int = 1
    
    def to_string(self) -> str:
        """Convert to string representation"""
        return f"{self.namespace}:{self.key}:v{self.version}"


class CacheManager:
    """
    Multi-level cache manager providing:
    - L1: In-memory cache (fastest)
    - L2: Redis cache (persistent, shared)
    - Smart cache warming and invalidation
    """
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._memory_cache = MemoryCache(
            max_size=config.memory_size,
            ttl=config.memory_ttl
        )
        self._redis_cache = None
        self._initialized = False
        self._cache_stats = {
            "hits": {"memory": 0, "redis": 0},
            "misses": {"memory": 0, "redis": 0},
            "sets": {"memory": 0, "redis": 0},
            "evictions": {"memory": 0, "redis": 0}
        }
    
    async def initialize(self) -> None:
        """Initialize cache connections"""
        try:
            if self.config.redis_enabled:
                self._redis_cache = RedisCache(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    default_ttl=self.config.redis_ttl
                )
                await self._redis_cache.connect()
            
            self._initialized = True
            logger.info("Cache manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}")
            raise
    
    async def close(self) -> None:
        """Close cache connections"""
        if self._redis_cache:
            await self._redis_cache.disconnect()
        
        self._memory_cache.clear()
        logger.info("Cache manager closed")
    
    def _generate_cache_key(self, namespace: str, key: str, version: int = 1) -> str:
        """Generate standardized cache key"""
        cache_key = CacheKey(namespace=namespace, key=key, version=version)
        return cache_key.to_string()
    
    def _hash_key(self, key: str) -> str:
        """Hash key for consistent length"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage"""
        if self.config.serialization_format == "json":
            if isinstance(value, pd.DataFrame):
                serialized = value.to_json(orient='records', date_format='iso')
                return json.dumps({"type": "dataframe", "data": serialized}).encode()
            else:
                return json.dumps(value, default=str).encode()
        else:
            return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        if self.config.serialization_format == "json":
            try:
                json_data = json.loads(data.decode())
                if isinstance(json_data, dict) and json_data.get("type") == "dataframe":
                    return pd.read_json(json_data["data"], orient='records')
                return json_data
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fallback to pickle
                return pickle.loads(data)
        else:
            return pickle.loads(data)
    
    async def get(self, 
                  namespace: str, 
                  key: str, 
                  level: CacheLevel = CacheLevel.BOTH) -> Optional[Any]:
        """
        Get value from cache with multi-level lookup
        
        Args:
            namespace: Cache namespace
            key: Cache key
            level: Cache level to check
            
        Returns:
            Cached value or None if not found
        """
        cache_key = self._generate_cache_key(namespace, key)
        
        try:
            # L1: Memory cache first
            if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                memory_value = self._memory_cache.get(cache_key)
                if memory_value is not None:
                    self._cache_stats["hits"]["memory"] += 1
                    return memory_value
                else:
                    self._cache_stats["misses"]["memory"] += 1
            
            # L2: Redis cache
            if level in [CacheLevel.REDIS, CacheLevel.BOTH] and self._redis_cache:
                redis_value = await self._redis_cache.get(cache_key)
                if redis_value is not None:
                    self._cache_stats["hits"]["redis"] += 1
                    
                    # Promote to memory cache
                    if level == CacheLevel.BOTH:
                        deserialized = self._deserialize_value(redis_value)
                        self._memory_cache.set(cache_key, deserialized)
                        return deserialized
                    
                    return self._deserialize_value(redis_value)
                else:
                    self._cache_stats["misses"]["redis"] += 1
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for {cache_key}: {e}")
            return None
    
    async def set(self, 
                  namespace: str, 
                  key: str, 
                  value: Any, 
                  ttl: Optional[int] = None,
                  level: CacheLevel = CacheLevel.BOTH) -> bool:
        """
        Set value in cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            level: Cache level to set
            
        Returns:
            Success status
        """
        cache_key = self._generate_cache_key(namespace, key)
        
        try:
            success = True
            
            # Set in memory cache
            if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                memory_ttl = ttl or self.config.memory_ttl
                self._memory_cache.set(cache_key, value, ttl=memory_ttl)
                self._cache_stats["sets"]["memory"] += 1
            
            # Set in Redis cache
            if level in [CacheLevel.REDIS, CacheLevel.BOTH] and self._redis_cache:
                redis_ttl = ttl or self.config.redis_ttl
                serialized = self._serialize_value(value)
                redis_success = await self._redis_cache.set(cache_key, serialized, ttl=redis_ttl)
                success = success and redis_success
                if redis_success:
                    self._cache_stats["sets"]["redis"] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Cache set error for {cache_key}: {e}")
            return False
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete key from all cache levels"""
        cache_key = self._generate_cache_key(namespace, key)
        
        try:
            success = True
            
            # Delete from memory cache
            self._memory_cache.delete(cache_key)
            
            # Delete from Redis cache
            if self._redis_cache:
                redis_success = await self._redis_cache.delete(cache_key)
                success = success and redis_success
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for {cache_key}: {e}")
            return False
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all keys in namespace
        
        Args:
            namespace: Namespace to invalidate
            
        Returns:
            Number of keys invalidated
        """
        try:
            invalidated_count = 0
            
            # Invalidate memory cache
            memory_keys = list(self._memory_cache._cache.keys())
            for key in memory_keys:
                if key.startswith(f"{namespace}:"):
                    self._memory_cache.delete(key)
                    invalidated_count += 1
            
            # Invalidate Redis cache
            if self._redis_cache:
                redis_keys = await self._redis_cache.get_keys_by_pattern(f"{namespace}:*")
                for key in redis_keys:
                    await self._redis_cache.delete(key)
                    invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} keys in namespace {namespace}")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Namespace invalidation error: {e}")
            return 0
    
    async def warm_cache(self, 
                        warming_functions: Dict[str, Callable],
                        parallel: bool = True) -> Dict[str, bool]:
        """
        Warm cache with pre-computed values
        
        Args:
            warming_functions: Dict of namespace -> async function pairs
            parallel: Whether to run warming functions in parallel
            
        Returns:
            Success status for each namespace
        """
        results = {}
        
        if parallel:
            tasks = []
            for namespace, warming_func in warming_functions.items():
                task = asyncio.create_task(self._warm_namespace(namespace, warming_func))
                tasks.append((namespace, task))
            
            for namespace, task in tasks:
                try:
                    results[namespace] = await task
                except Exception as e:
                    logger.error(f"Cache warming failed for {namespace}: {e}")
                    results[namespace] = False
        else:
            for namespace, warming_func in warming_functions.items():
                try:
                    results[namespace] = await self._warm_namespace(namespace, warming_func)
                except Exception as e:
                    logger.error(f"Cache warming failed for {namespace}: {e}")
                    results[namespace] = False
        
        return results
    
    async def _warm_namespace(self, namespace: str, warming_func: Callable) -> bool:
        """Warm specific namespace"""
        try:
            warming_data = await warming_func()
            
            if isinstance(warming_data, dict):
                for key, value in warming_data.items():
                    await self.set(namespace, key, value)
                return True
            else:
                logger.warning(f"Warming function for {namespace} returned non-dict data")
                return False
                
        except Exception as e:
            logger.error(f"Error warming namespace {namespace}: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_hits = sum(self._cache_stats["hits"].values())
        total_requests = total_hits + sum(self._cache_stats["misses"].values())
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "total_hits": total_hits,
            "detailed_stats": self._cache_stats,
            "memory_cache_size": self._memory_cache.size(),
            "redis_connected": self._redis_cache is not None and self._redis_cache.is_connected()
        }
        
        return stats
    
    async def cleanup(self) -> Dict[str, int]:
        """Clean up expired cache entries"""
        cleanup_stats = {
            "memory_cleaned": 0,
            "redis_cleaned": 0
        }
        
        try:
            # Clean memory cache
            cleanup_stats["memory_cleaned"] = self._memory_cache.cleanup()
            
            # Clean Redis cache (Redis handles TTL automatically)
            if self._redis_cache:
                # Get some cleanup statistics if available
                info = await self._redis_cache.get_info()
                cleanup_stats["redis_info"] = info
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return cleanup_stats