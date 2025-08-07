"""
Query Result Caching System for Performance Optimization
Implements intelligent caching for validation queries to achieve <5s response times
"""

import hashlib
import json
import sqlite3
import pandas as pd
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached query result"""
    query_hash: str
    rule_name: str
    query_sql: str
    result_data: pd.DataFrame
    execution_time: float
    row_count: int
    created_at: datetime
    expires_at: datetime
    cache_hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'query_hash': self.query_hash,
            'rule_name': self.rule_name,
            'query_sql': self.query_sql,
            'result_data': self.result_data.to_json(),
            'execution_time': self.execution_time,
            'row_count': self.row_count,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'cache_hit_count': self.cache_hit_count
        }


class QueryResultCache:
    """
    High-performance query result caching system
    Features:
    - TTL-based expiration
    - Memory and disk caching
    - Query fingerprinting
    - Cache statistics
    - Automatic cleanup
    """
    
    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 default_ttl_minutes: int = 60,
                 max_memory_entries: int = 100,
                 max_disk_size_mb: int = 500):
        """
        Initialize query cache
        
        Args:
            cache_dir: Directory for disk cache storage
            default_ttl_minutes: Default time-to-live for cache entries
            max_memory_entries: Maximum entries to keep in memory
            max_disk_size_mb: Maximum disk cache size
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self.max_memory_entries = max_memory_entries
        self.max_disk_size_mb = max_disk_size_mb
        
        # In-memory cache for fastest access
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'disk_hits': 0,
            'evictions': 0,
            'errors': 0
        }
        
        # Initialize disk cache
        self._init_disk_cache()
        
        logger.info(f"QueryResultCache initialized: {self.cache_dir}, TTL: {default_ttl_minutes}min")
    
    def _init_disk_cache(self):
        """Initialize SQLite-based disk cache"""
        self.disk_cache_path = self.cache_dir / "query_cache.db"
        
        with self._get_disk_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    query_hash TEXT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    query_sql TEXT NOT NULL,
                    result_data BLOB NOT NULL,
                    execution_time REAL NOT NULL,
                    row_count INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    cache_hit_count INTEGER DEFAULT 0,
                    data_size INTEGER NOT NULL
                )
            """)
            
            # Index for cleanup operations
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires 
                ON query_cache(expires_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_rule 
                ON query_cache(rule_name, created_at)
            """)
    
    @contextmanager
    def _get_disk_connection(self):
        """Get connection to disk cache database"""
        conn = sqlite3.connect(self.disk_cache_path)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Disk cache error: {e}")
            raise
        finally:
            conn.close()
    
    def _generate_query_hash(self, query_sql: str, params: Optional[Dict] = None) -> str:
        """Generate unique hash for query + parameters"""
        query_text = query_sql.strip().lower()
        if params:
            query_text += json.dumps(params, sort_keys=True)
        
        return hashlib.sha256(query_text.encode()).hexdigest()[:16]
    
    def get(self, rule_name: str, query_sql: str, params: Optional[Dict] = None) -> Optional[CacheEntry]:
        """
        Retrieve cached query result
        
        Args:
            rule_name: Name of validation rule
            query_sql: SQL query string
            params: Query parameters
            
        Returns:
            CacheEntry if found and valid, None otherwise
        """
        query_hash = self._generate_query_hash(query_sql, params)
        
        # Check memory cache first
        if query_hash in self.memory_cache:
            entry = self.memory_cache[query_hash]
            
            if not entry.is_expired():
                entry.cache_hit_count += 1
                self.stats['hits'] += 1
                self.stats['memory_hits'] += 1
                logger.debug(f"Cache HIT (memory): {rule_name}")
                return entry
            else:
                # Remove expired entry
                del self.memory_cache[query_hash]
        
        # Check disk cache
        entry = self._get_from_disk(query_hash)
        if entry and not entry.is_expired():
            entry.cache_hit_count += 1
            self.stats['hits'] += 1
            self.stats['disk_hits'] += 1
            
            # Promote to memory cache
            self._add_to_memory(entry)
            
            logger.debug(f"Cache HIT (disk): {rule_name}")
            return entry
        
        self.stats['misses'] += 1
        logger.debug(f"Cache MISS: {rule_name}")
        return None
    
    def set(self, rule_name: str, query_sql: str, result_data: pd.DataFrame, 
            execution_time: float, params: Optional[Dict] = None,
            ttl_minutes: Optional[int] = None) -> str:
        """
        Store query result in cache
        
        Args:
            rule_name: Name of validation rule
            query_sql: SQL query string  
            result_data: Query result DataFrame
            execution_time: Query execution time
            params: Query parameters
            ttl_minutes: Custom TTL in minutes
            
        Returns:
            Query hash for the cached entry
        """
        query_hash = self._generate_query_hash(query_sql, params)
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self.default_ttl
        
        entry = CacheEntry(
            query_hash=query_hash,
            rule_name=rule_name,
            query_sql=query_sql,
            result_data=result_data.copy(),
            execution_time=execution_time,
            row_count=len(result_data),
            created_at=datetime.now(),
            expires_at=datetime.now() + ttl
        )
        
        # Store in both memory and disk
        self._add_to_memory(entry)
        self._add_to_disk(entry)
        
        logger.debug(f"Cache SET: {rule_name} (TTL: {ttl_minutes or 'default'}min)")
        return query_hash
    
    def _add_to_memory(self, entry: CacheEntry):
        """Add entry to memory cache with size management"""
        if len(self.memory_cache) >= self.max_memory_entries:
            self._evict_from_memory()
        
        self.memory_cache[entry.query_hash] = entry
    
    def _evict_from_memory(self):
        """Evict least recently used entries from memory"""
        if not self.memory_cache:
            return
        
        # Sort by last access (cache_hit_count as proxy) and creation time
        sorted_entries = sorted(
            self.memory_cache.items(),
            key=lambda x: (x[1].cache_hit_count, x[1].created_at)
        )
        
        # Remove oldest 25% of entries
        evict_count = max(1, len(sorted_entries) // 4)
        
        for i in range(evict_count):
            query_hash, _ = sorted_entries[i]
            del self.memory_cache[query_hash]
            self.stats['evictions'] += 1
    
    def _add_to_disk(self, entry: CacheEntry):
        """Add entry to disk cache"""
        try:
            # Serialize DataFrame
            result_blob = pickle.dumps(entry.result_data)
            data_size = len(result_blob)
            
            with self._get_disk_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO query_cache 
                    (query_hash, rule_name, query_sql, result_data, execution_time, 
                     row_count, created_at, expires_at, cache_hit_count, data_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.query_hash,
                    entry.rule_name,
                    entry.query_sql,
                    result_blob,
                    entry.execution_time,
                    entry.row_count,
                    entry.created_at,
                    entry.expires_at,
                    entry.cache_hit_count,
                    data_size
                ))
                
        except Exception as e:
            logger.error(f"Failed to store cache entry: {e}")
            self.stats['errors'] += 1
    
    def _get_from_disk(self, query_hash: str) -> Optional[CacheEntry]:
        """Retrieve entry from disk cache"""
        try:
            with self._get_disk_connection() as conn:
                cursor = conn.execute("""
                    SELECT rule_name, query_sql, result_data, execution_time, row_count,
                           created_at, expires_at, cache_hit_count
                    FROM query_cache 
                    WHERE query_hash = ?
                """, (query_hash,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Deserialize DataFrame
                result_data = pickle.loads(row[2])
                
                return CacheEntry(
                    query_hash=query_hash,
                    rule_name=row[0],
                    query_sql=row[1],
                    result_data=result_data,
                    execution_time=row[3],
                    row_count=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    expires_at=datetime.fromisoformat(row[6]),
                    cache_hit_count=row[7]
                )
                
        except Exception as e:
            logger.error(f"Failed to retrieve cache entry: {e}")
            self.stats['errors'] += 1
            return None
    
    def cleanup_expired(self) -> int:
        """Remove expired entries from cache"""
        removed_count = 0
        now = datetime.now()
        
        # Clean memory cache
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
            removed_count += 1
        
        # Clean disk cache
        try:
            with self._get_disk_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM query_cache WHERE expires_at < ?
                """, (now,))
                removed_count += cursor.rowcount
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired entries: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired cache entries")
        
        return removed_count
    
    def invalidate_rule(self, rule_name: str) -> int:
        """Invalidate all cache entries for a specific rule"""
        removed_count = 0
        
        # Remove from memory cache
        keys_to_remove = [
            key for key, entry in self.memory_cache.items()
            if entry.rule_name == rule_name
        ]
        
        for key in keys_to_remove:
            del self.memory_cache[key]
            removed_count += 1
        
        # Remove from disk cache
        try:
            with self._get_disk_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM query_cache WHERE rule_name = ?
                """, (rule_name,))
                removed_count += cursor.rowcount
                
        except Exception as e:
            logger.error(f"Failed to invalidate rule cache: {e}")
        
        logger.info(f"Invalidated {removed_count} cache entries for rule: {rule_name}")
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        stats = {
            **self.stats,
            'hit_rate': hit_rate,
            'memory_entries': len(self.memory_cache),
            'total_requests': total_requests
        }
        
        # Add disk cache stats
        try:
            with self._get_disk_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as disk_entries,
                        SUM(data_size) as total_size,
                        AVG(cache_hit_count) as avg_hits
                    FROM query_cache
                """)
                disk_stats = cursor.fetchone()
                
                if disk_stats:
                    stats.update({
                        'disk_entries': disk_stats[0],
                        'disk_size_mb': (disk_stats[1] or 0) / (1024 * 1024),
                        'avg_cache_hits': disk_stats[2] or 0
                    })
                    
        except Exception as e:
            logger.error(f"Failed to get disk cache stats: {e}")
        
        return stats
    
    def clear_all(self):
        """Clear all cache entries"""
        self.memory_cache.clear()
        
        try:
            with self._get_disk_connection() as conn:
                conn.execute("DELETE FROM query_cache")
                
        except Exception as e:
            logger.error(f"Failed to clear disk cache: {e}")
        
        logger.info("All cache entries cleared")
    
    def optimize_cache(self):
        """Optimize cache storage and performance"""
        # Clean up expired entries
        self.cleanup_expired()
        
        # Optimize disk cache
        try:
            with self._get_disk_connection() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                
        except Exception as e:
            logger.error(f"Failed to optimize disk cache: {e}")
        
        logger.info("Cache optimization completed")


# Cache configuration for different query types
CACHE_CONFIGS = {
    'affiliation_anomaly': {'ttl_minutes': 30},  # Slower changing data
    'provider_name_inconsistency': {'ttl_minutes': 60},
    'npi_validation': {'ttl_minutes': 120},  # Very stable data
    'contact_validation': {'ttl_minutes': 15},  # Frequently changing
    'temporal_consistency': {'ttl_minutes': 240},  # Very stable
    'cross_reference_integrity': {'ttl_minutes': 60},
    'validation_summary': {'ttl_minutes': 5}  # Always fresh
}