"""
SQLite-based Data Cache Layer for Collision Analytics

Provides persistent caching for:
- Filter results across sessions
- Feature data for static layers
- Query result memoization

Usage:
    from core.data_cache import DataCache
    
    cache = DataCache.for_layer(layer)
    results = cache.get_results(filter_spec)
    if results is None:
        results = compute_results()
        cache.store_results(filter_spec, results)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CACHE_TTL = 3600  # 1 hour
MAX_CACHE_ENTRY_SIZE = 100_000  # Max features to cache
DEFAULT_BATCH_SIZE = 5000


# =============================================================================
# Cache Statistics
# =============================================================================

@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def total_requests(self) -> int:
        return self.hits + self.misses


# =============================================================================
# Data Cache Implementation
# =============================================================================

class DataCache:
    """SQLite-based caching layer for filter results and feature data.
    
    Features:
    - Persistent storage across QGIS sessions
    - Automatic expiration (TTL)
    - Size limits with LRU eviction
    - Thread-safe concurrent access
    - WAL mode for better concurrency
    - Optional compression for large datasets
    
    Thread Safety:
    This class is thread-safe. Each thread gets its own SQLite connection
    via thread-local storage. The instance registry is protected by a lock.
    """
    
    _instances: Dict[str, 'DataCache'] = {}
    _lock = threading.RLock()
    _global_stats = CacheStats()
    
    def __init__(
        self, 
        layer_id: str, 
        layer_name: str = "",
        cache_dir: Optional[Path] = None,
        ttl_seconds: float = DEFAULT_CACHE_TTL,
        max_size_mb: float = 100.0
    ):
        """Initialize cache for a specific layer.
        
        Args:
            layer_id: Unique layer identifier (from QgsLayer.id())
            layer_name: Human-readable layer name
            cache_dir: Directory for cache files (default: ~/.qgis/collision_analytics_cache)
            ttl_seconds: Default time-to-live for cache entries
            max_size_mb: Maximum cache size before LRU eviction
        """
        self.layer_id = layer_id
        self.layer_name = layer_name
        self.ttl_seconds = ttl_seconds
        self.max_size_mb = max_size_mb
        self._local = threading.local()
        self._stats = CacheStats()
        
        # Setup cache directory
        if cache_dir is None:
            cache_dir = Path.home() / '.qgis' / 'collision_analytics_cache'
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Database path based on layer ID (sanitize for filesystem)
        safe_id = self._sanitize_filename(layer_id)
        self.db_path = self.cache_dir / f"{safe_id}.db"
        
        # Initialize schema
        self._init_db()
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Replace problematic characters
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)
        # Limit length
        if len(safe) > 64:
            safe = safe[:32] + '_' + hashlib.md5(safe.encode()).hexdigest()[:16]
        return safe or 'layer'
    
    @classmethod
    def for_layer(cls, layer, **kwargs) -> 'DataCache':
        """Get or create cache instance for a QGIS layer.
        
        Args:
            layer: QgsVectorLayer instance
            **kwargs: Additional arguments passed to constructor
        
        Returns:
            DataCache instance for the layer
        """
        layer_id = layer.id() if hasattr(layer, 'id') else str(id(layer))
        
        with cls._lock:
            if layer_id not in cls._instances:
                layer_name = layer.name() if hasattr(layer, 'name') else 'unknown'
                cls._instances[layer_id] = cls(layer_id, layer_name, **kwargs)
            return cls._instances[layer_id]
    
    @classmethod
    def clear_all(cls):
        """Clear all caches across all layers."""
        with cls._lock:
            for cache in cls._instances.values():
                cache.clear()
    
    @classmethod
    def get_global_stats(cls) -> CacheStats:
        """Get aggregated statistics across all cache instances."""
        with cls._lock:
            total = CacheStats()
            for cache in cls._instances.values():
                total.hits += cache._stats.hits
                total.misses += cache._stats.misses
                total.stores += cache._stats.stores
                total.evictions += cache._stats.evictions
            return total
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection.
        
        Each thread gets its own connection to avoid SQLite threading issues.
        Connections are created on-demand and cached per-thread.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            
            # Optimize for read-heavy workload
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
            
            self._local.conn = conn
        
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema with optimized indexes."""
        conn = self._get_connection()
        
        # Filter results cache - stores serialized results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS filter_results (
                cache_key TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                feature_count INTEGER NOT NULL,
                fids_json TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        
        # Feature data cache - stores individual feature attributes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feature_data (
                fid INTEGER PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        # Metadata for cache invalidation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        # Performance indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_filter_expires 
            ON filter_results(expires_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_filter_accessed 
            ON filter_results(accessed_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_updated 
            ON feature_data(updated_at)
        """)
        
        conn.commit()
        
        # Store metadata
        self._set_metadata('created', str(time.time()))
        self._set_metadata('layer_id', self.layer_id)
        self._set_metadata('layer_name', self.layer_name)
    
    def _set_metadata(self, key: str, value: str):
        """Store metadata value."""
        try:
            conn = self._get_connection()
            conn.execute(
                """INSERT OR REPLACE INTO cache_metadata (key, value, updated_at)
                   VALUES (?, ?, ?)""",
                (key, value, time.time())
            )
            conn.commit()
        except Exception:
            pass
    
    def _get_metadata(self, key: str) -> Optional[str]:
        """Retrieve metadata value."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            return None
    
    # ======================================================================
    # Filter Results Cache
    # ======================================================================
    
    def get_results(
        self, 
        spec: Any,
        cache_key: Optional[str] = None
    ) -> Optional[Tuple[List[int], List[Dict[str, Any]]]]:
        """Get cached filter results.
        
        Args:
            spec: FilterSpec object (must have cache_key() method) or any object
            cache_key: Optional explicit cache key (if spec doesn't have cache_key())
        
        Returns:
            Tuple of (fids, rows) or None if not cached
        """
        if cache_key is None:
            cache_key = spec.cache_key() if hasattr(spec, 'cache_key') else str(spec)
        
        try:
            conn = self._get_connection()
            now = time.time()
            
            # Try to get valid cached result
            cursor = conn.execute(
                """SELECT fids_json FROM filter_results 
                   WHERE cache_key = ? AND expires_at > ?""",
                (cache_key, now)
            )
            row = cursor.fetchone()
            
            if row:
                # Update access time for LRU
                conn.execute(
                    "UPDATE filter_results SET accessed_at = ? WHERE cache_key = ?",
                    (now, cache_key)
                )
                conn.commit()
                
                # Deserialize
                data = json.loads(row[0])
                self._stats.hits += 1
                DataCache._global_stats.hits += 1
                return (data['fids'], data['rows'])
            
            self._stats.misses += 1
            DataCache._global_stats.misses += 1
            return None
            
        except Exception:
            self._stats.misses += 1
            DataCache._global_stats.misses += 1
            return None
    
    def store_results(
        self, 
        spec: Any,
        results: Tuple[List[int], List[Dict[str, Any]]],
        cache_key: Optional[str] = None,
        ttl_seconds: Optional[float] = None
    ) -> bool:
        """Store filter results in cache.
        
        Args:
            spec: FilterSpec object or any hashable key
            results: Tuple of (fids, rows)
            cache_key: Optional explicit cache key
            ttl_seconds: Override default TTL
        
        Returns:
            True if stored successfully, False otherwise
        """
        if cache_key is None:
            cache_key = spec.cache_key() if hasattr(spec, 'cache_key') else str(spec)
        
        fids, rows = results
        
        # Don't cache enormous results
        if len(fids) > MAX_CACHE_ENTRY_SIZE:
            return False
        
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds
        
        try:
            conn = self._get_connection()
            now = time.time()
            
            # Serialize results
            data = {
                'fids': fids,
                'rows': rows
            }
            
            conn.execute(
                """INSERT OR REPLACE INTO filter_results 
                   (cache_key, created_at, accessed_at, feature_count, fids_json, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cache_key, now, now, len(fids), json.dumps(data), now + ttl_seconds)
            )
            conn.commit()
            
            self._stats.stores += 1
            DataCache._global_stats.stores += 1
            
            # Check if we need to evict old entries
            self._maybe_evict()
            
            return True
            
        except Exception:
            return False
    
    def invalidate_results(self, cache_key: str) -> bool:
        """Invalidate a specific cached result.
        
        Args:
            cache_key: The cache key to invalidate
        
        Returns:
            True if an entry was removed
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "DELETE FROM filter_results WHERE cache_key = ?",
                (cache_key,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    # ======================================================================
    # Feature Data Cache
    # ======================================================================
    
    def get_feature(self, fid: int) -> Optional[Dict[str, Any]]:
        """Get cached feature data by feature ID.
        
        Args:
            fid: Feature ID
        
        Returns:
            Feature attributes dict or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT data_json FROM feature_data WHERE fid = ?",
                (fid,)
            )
            row = cursor.fetchone()
            
            if row:
                self._stats.hits += 1
                return json.loads(row[0])
            
            self._stats.misses += 1
            return None
            
        except Exception:
            self._stats.misses += 1
            return None
    
    def store_feature(self, fid: int, data: Dict[str, Any]) -> bool:
        """Cache feature data.
        
        Args:
            fid: Feature ID
            data: Feature attributes
        
        Returns:
            True if stored successfully
        """
        try:
            conn = self._get_connection()
            conn.execute(
                """INSERT OR REPLACE INTO feature_data (fid, data_json, updated_at)
                   VALUES (?, ?, ?)""",
                (fid, json.dumps(data), time.time())
            )
            conn.commit()
            return True
        except Exception:
            return False
    
    def store_features_batch(
        self, 
        features: List[Tuple[int, Dict[str, Any]]]
    ) -> int:
        """Batch store feature data.
        
        Args:
            features: List of (fid, data) tuples
        
        Returns:
            Number of features stored
        """
        if not features:
            return 0
        
        try:
            conn = self._get_connection()
            now = time.time()
            
            conn.executemany(
                """INSERT OR REPLACE INTO feature_data (fid, data_json, updated_at)
                   VALUES (?, ?, ?)""",
                [(fid, json.dumps(data), now) for fid, data in features]
            )
            conn.commit()
            return len(features)
            
        except Exception:
            return 0
    
    # ======================================================================
    # Maintenance
    # ======================================================================
    
    def _maybe_evict(self):
        """Evict old entries if cache is too large."""
        try:
            conn = self._get_connection()
            
            # Check current size
            cursor = conn.execute(
                "SELECT COUNT(*) FROM filter_results"
            )
            count = cursor.fetchone()[0]
            
            # Simple LRU: if more than 100 entries, remove oldest accessed
            if count > 100:
                conn.execute(
                    """DELETE FROM filter_results WHERE cache_key IN (
                        SELECT cache_key FROM filter_results
                        ORDER BY accessed_at ASC
                        LIMIT ?
                    )""",
                    (count - 50,)  # Remove oldest 50%
                )
                conn.commit()
                self._stats.evictions += count - 50
                
        except Exception:
            pass
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "DELETE FROM filter_results WHERE expires_at <= ?",
                (time.time(),)
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            return 0
    
    def clear(self):
        """Clear all cached data for this layer."""
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM filter_results")
            conn.execute("DELETE FROM feature_data")
            conn.commit()
            self._stats = CacheStats()
        except Exception:
            pass
    
    def vacuum(self):
        """Compact the database file."""
        try:
            conn = self._get_connection()
            conn.execute("VACUUM")
            conn.commit()
        except Exception:
            pass
    
    # ======================================================================
    # Statistics
    # ======================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        stats = {
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'stores': self._stats.stores,
            'evictions': self._stats.evictions,
            'hit_rate': self._stats.hit_rate,
            'db_path': str(self.db_path),
            'layer_id': self.layer_id,
        }
        
        # Add database-level stats
        try:
            conn = self._get_connection()
            
            cursor = conn.execute("SELECT COUNT(*) FROM filter_results")
            stats['cached_filters'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM feature_data")
            stats['cached_features'] = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT SUM(feature_count) FROM filter_results"
            )
            stats['total_cached_features'] = cursor.fetchone()[0] or 0
            
            # Database file size
            if self.db_path.exists():
                stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
            else:
                stats['db_size_mb'] = 0
                
        except Exception as e:
            stats['error'] = str(e)
        
        return stats
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"DataCache({self.layer_name[:30]!r}, "
            f"hits={stats['hits']}, misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate']:.1%})"
        )


# =============================================================================
# Utility Functions
# =============================================================================

def get_cache_dir() -> Path:
    """Get the default cache directory."""
    return Path.home() / '.qgis' / 'collision_analytics_cache'


def clear_all_caches():
    """Clear all collision analytics caches."""
    DataCache.clear_all()


def get_global_cache_stats() -> Dict[str, Any]:
    """Get statistics across all caches."""
    stats = DataCache.get_global_stats()
    return {
        'hits': stats.hits,
        'misses': stats.misses,
        'stores': stats.stores,
        'hit_rate': stats.hit_rate,
    }
