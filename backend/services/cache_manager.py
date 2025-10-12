"""
Cache manager for storing and retrieving generated reports.
Implements in-memory caching with TTL and LRU eviction.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ReportCacheManager:
    """Manages caching of generated collision reports."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            max_size: Maximum number of reports to cache
            ttl_seconds: Time-to-live for cached reports in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'stores': 0
        }
        logger.info(f"Cache manager initialized: max_size={max_size}, ttl={ttl_seconds}s")
    
    def get_report(self, norad_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached report if valid.
        
        Args:
            norad_id: NORAD ID of the satellite
            
        Returns:
            Cached report dict if found and valid, None otherwise
        """
        cache_key = self._make_key(norad_id)
        
        if cache_key not in self._cache:
            self._stats['misses'] += 1
            logger.debug(f"Cache miss for {norad_id}")
            return None
        
        cached_entry = self._cache[cache_key]
        
        # Check if expired
        if self._is_expired(cached_entry['timestamp']):
            logger.debug(f"Cache entry expired for {norad_id}")
            del self._cache[cache_key]
            self._stats['misses'] += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        
        self._stats['hits'] += 1
        logger.debug(f"Cache hit for {norad_id}")
        
        return cached_entry['report'].copy()
    
    def store_report(self, norad_id: str, report: Dict[str, Any], 
                    collision_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Store report in cache with timestamp.
        
        Args:
            norad_id: NORAD ID of the satellite
            report: Generated report dict
            collision_data: Optional collision data for reference
        """
        cache_key = self._make_key(norad_id)
        
        # Evict oldest if cache is full
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            self._evict_oldest()
        
        # Store with timestamp
        self._cache[cache_key] = {
            'report': report.copy(),
            'timestamp': datetime.utcnow(),
            'collision_data': collision_data.copy() if collision_data else None,
            'norad_id': norad_id
        }
        
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        
        self._stats['stores'] += 1
        logger.debug(f"Report cached for {norad_id}")
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """
        Check if cached report has expired.
        
        Args:
            timestamp: Timestamp when report was cached
            
        Returns:
            True if expired, False otherwise
        """
        age = datetime.utcnow() - timestamp
        return age.total_seconds() > self.ttl_seconds
    
    def _evict_oldest(self) -> None:
        """Remove oldest report when cache is full."""
        if not self._cache:
            return
        
        # Remove first item (oldest)
        oldest_key = next(iter(self._cache))
        oldest_entry = self._cache[oldest_key]
        del self._cache[oldest_key]
        
        self._stats['evictions'] += 1
        logger.debug(f"Evicted oldest cache entry for {oldest_entry['norad_id']}")
    
    def _make_key(self, norad_id: str) -> str:
        """Create cache key from NORAD ID."""
        return f"report_{norad_id}"
    
    def clear(self) -> None:
        """Clear all cached reports."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dict with hits, misses, evictions, stores counts
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self._stats,
            'size': len(self._cache),
            'max_size': self.max_size,
            'hit_rate': round(hit_rate, 2)
        }
    
    def remove(self, norad_id: str) -> bool:
        """
        Remove a specific report from cache.
        
        Args:
            norad_id: NORAD ID of the satellite
            
        Returns:
            True if removed, False if not found
        """
        cache_key = self._make_key(norad_id)
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(f"Removed cache entry for {norad_id}")
            return True
        return False
    
    def get_all_keys(self) -> list:
        """Get list of all cached NORAD IDs."""
        return [entry['norad_id'] for entry in self._cache.values()]
