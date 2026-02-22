from __future__ import annotations

import functools
from datetime import date, datetime, time, timezone
from typing import Any, Callable, Optional, Tuple, TypeVar, Union

T = TypeVar('T')

# =============================================================================
# Caching Decorators
# =============================================================================

def lru_cache_typed(maxsize: int = 128, typed: bool = False):
    """Thread-safe LRU cache decorator with optional type sensitivity.
    
    This is a thin wrapper around functools.lru_cache that provides
    better handling for methods and QGIS variant types.
    
    Args:
        maxsize: Maximum cache size (None for unlimited)
        typed: If True, arguments of different types are cached separately
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cached_func = functools.lru_cache(maxsize=maxsize, typed=typed)(func)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return cached_func(*args, **kwargs)
        
        # Expose cache management methods
        wrapper.cache_info = cached_func.cache_info
        wrapper.cache_clear = cached_func.cache_clear
        
        return wrapper
    return decorator


def memoize(maxsize: int = 256):
    """Simple memoization decorator for expensive functions.
    
    Similar to lru_cache but with simpler semantics.
    
    Example:
        @memoize(maxsize=1024)
        def expensive_lookup(key):
            return database.query(key)
    """
    return lru_cache_typed(maxsize=maxsize)


# =============================================================================
# Safe Value Handling
# =============================================================================

def _is_qt_null(v: Any) -> bool:
    """Check if a value is a Qt null/invalid value."""
    try:
        if hasattr(v, "isNull") and v.isNull():
            return True
        if hasattr(v, "isValid") and not v.isValid():
            return True
    except Exception:
        return False
    return False


def safe_str(v: Any) -> str:
    """Convert any value to string, handling None and Qt types."""
    if v is None:
        return ""
    return str(v)


def is_blank(v: Any) -> bool:
    """Check if a value is blank/empty/NULL.
    
    Treats None, empty strings, whitespace, and 'NULL' as blank.
    Numeric 0 is NOT blank.
    """
    if v is None:
        return True
    if _is_qt_null(v):
        return True
    if isinstance(v, str):
        s = v.strip()
        return s == "" or s.upper() == "NULL"
    s = safe_str(v).strip()
    return s == "" or s.upper() == "NULL"


# =============================================================================
# Numeric Conversion
# =============================================================================

def try_float(v: Any) -> Optional[float]:
    """Try to convert a value to float.
    
    Args:
        v: Value to convert
    
    Returns:
        Float value or None if conversion fails
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = safe_str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def numeric_str(v: Any) -> Optional[str]:
    """Convert numeric value to stable string representation.
    
    Examples:
        1.0 -> '1'
        1.5 -> '1.5'
        '001' -> '1'
    """
    f = try_float(v)
    if f is None:
        return None
    if abs(f - int(f)) < 1e-9:
        return str(int(f))
    return str(f)


# =============================================================================
# Date/Time Parsing with Caching
# =============================================================================

# Pre-compiled format strings for common date patterns
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]


def _normalize_date_string(s: str) -> str:
    """Normalize a date string for caching purposes."""
    return s.strip()[:50]  # Limit length for cache key


@lru_cache_typed(maxsize=65536)
def to_datetime_cached(value: Union[str, int, float]) -> Optional[datetime]:
    """Cached version of to_datetime for hashable primitive types.
    
    This function caches parsed datetime values to avoid repeated
    parsing of the same date strings. Use this when you know the
    input is a primitive type (str, int, float).
    
    Args:
        value: Date value as string, int (timestamp), or float
    
    Returns:
        Parsed datetime or None
    """
    return _to_datetime_impl(value)


def to_datetime(value: Any) -> Optional[datetime]:
    """Convert various date formats to Python datetime.
    
    Handles:
    - Python datetime/date objects
    - QDateTime/QDate objects (QGIS)
    - ISO format strings
    - Common date formats
    - Unix timestamps
    
    Args:
        value: Date value in various formats
    
    Returns:
        Python datetime object or None if parsing fails
    """
    # Fast path for already-parsed dates
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    
    # QGIS types
    if hasattr(value, "toPyDateTime"):
        try:
            return value.toPyDateTime()
        except Exception:
            pass
    if hasattr(value, "toPyDate"):
        try:
            d = value.toPyDate()
            return datetime(d.year, d.month, d.day)
        except Exception:
            pass
    
    # String/int/float - use cached version
    if isinstance(value, (str, int, float)):
        return to_datetime_cached(value)
    
    # Try string conversion as last resort
    s = safe_str(value).strip()
    if s:
        return _to_datetime_impl(s)
    
    return None


def _to_datetime_impl(value: Union[str, int, float]) -> Optional[datetime]:
    """Internal implementation of datetime parsing."""
    # Handle numeric timestamps
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    
    # String parsing
    s = value.strip()
    if not s:
        return None
    
    # ISO format (fast path)
    if 'T' in s or (len(s) >= 10 and s[4] == '-' and s[7] == '-'):
        try:
            iso_str = s.replace("Z", "+00:00") if s.endswith("Z") else s
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            pass
    
    # Try other formats
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    
    return None


def clamp_date_range(start_date: date, end_date: date) -> Tuple[datetime, datetime]:
    """Convert date range to datetime range (inclusive).
    
    Args:
        start_date: Start date
        end_date: End date (inclusive)
    
    Returns:
        Tuple of (start_datetime, end_datetime)
        where end_datetime is end-of-day
    """
    start_dt = datetime.combine(start_date, time(0, 0, 0))
    # inclusive end-of-day
    end_dt = datetime.combine(end_date, time(23, 59, 59, 999000))
    return start_dt, end_dt


# =============================================================================
# Batch Processing Utilities
# =============================================================================

def batch_iterator(items: list, batch_size: int):
    """Iterate over items in batches.
    
    Args:
        items: List of items
        batch_size: Size of each batch
    
    Yields:
        Batches of items
    
    Example:
        for batch in batch_iterator(features, 1000):
            process_batch(batch)
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def chunked(iterable, chunk_size: int):
    """Chunk an iterable into fixed-size groups.
    
    More memory-efficient than batch_iterator for generators.
    """
    iterator = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(chunk_size):
                chunk.append(next(iterator))
        except StopIteration:
            if chunk:
                yield chunk
            break
        yield chunk


# =============================================================================
# Performance Timing
# =============================================================================

class Timer:
    """Simple context manager for timing code blocks.
    
    Example:
        with Timer("filter operation") as t:
            results = engine.apply(spec, fields)
        print(f"Took {t.elapsed:.3f}s")
    """
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.elapsed: float = 0.0
        self._start: Optional[float] = None
    
    def __enter__(self):
        import time
        self._start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        import time
        if self._start is not None:
            self.elapsed = time.perf_counter() - self._start


# =============================================================================
# Type Coercion for QGIS
# =============================================================================

def coerce_qgis_value(value: Any, target_type: type) -> Any:
    """Coerce a QGIS variant value to a Python type.
    
    Args:
        value: QGIS attribute value (may be QVariant)
        target_type: Target Python type
    
    Returns:
        Coerced value or None
    """
    if value is None or _is_qt_null(value):
        return None
    
    if target_type == str:
        return safe_str(value)
    elif target_type in (int, float):
        f = try_float(value)
        if f is not None:
            return target_type(f)
        return None
    elif target_type == datetime:
        return to_datetime(value)
    elif target_type == date:
        dt = to_datetime(value)
        return dt.date() if dt else None
    
    return value
