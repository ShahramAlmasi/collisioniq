"""Core analytics engine for Collision Analytics plugin."""

from .config_manager import ConfigManager, Profile, Config, get_config_manager, reset_config_manager
from .analytics import (
    # Main API functions
    analyze_collisions,
    quick_summary,
    # Data classes
    AnalyticsResult,
    SeverityDistribution,
    RateMetrics,
    TrendResult,
    BeforeAfterComparison,
    # Calculation functions
    calculate_severity_distribution,
    calculate_rate_metrics,
    calculate_annual_counts,
    calculate_trend,
    compare_before_after,
    identify_risk_flags,
    generate_insights,
    # Formatting utilities
    format_rate,
    format_percent,
    format_change,
    rate_summary_text,
    trend_summary_text,
)
from .config import (
    # Defaults
    DEFAULT_FIELD_MAP,
    DEFAULT_DECODES,
    FILTER_CONCEPTS,
    # Settings keys (backward compatibility)
    SETTINGS_FIELD_MAP_KEY,
    SETTINGS_DECODES_KEY,
    SETTINGS_PROFILES_KEY,
    # v2 ConfigManager API
    get_field_map,
    set_field_map,
    get_decodes,
    get_decode_mapping,
    set_decode_mapping,
    save_config,
    reset_config_to_defaults,
    reset_field_map_to_defaults,
    reset_decodes_to_defaults,
    # Import/Export
    export_field_maps,
    export_decodes,
    export_profiles,
    export_full_config,
    import_field_maps,
    import_decodes,
    import_profiles,
    import_full_config,
    # Legacy helpers
    load_field_map_from_settings,
    save_field_map_to_settings,
    load_decodes_from_settings,
    save_decodes_to_settings,
    get_config_info,
)
from .filters import FilterEngine, FilterSpec, DataCache
from .data_cache import DataCache as DataCacheStandalone, CacheStats
from .decodes import DecodeRegistry
from .utils import (
    to_datetime,
    to_datetime_cached,
    clamp_date_range,
    is_blank,
    safe_str,
    try_float,
    numeric_str,
    lru_cache_typed,
    memoize,
    Timer,
)

__all__ = [
    # ConfigManager (new v2)
    'ConfigManager',
    'Profile',
    'Config',
    'get_config_manager',
    'reset_config_manager',
    
    # Analytics
    'analyze_collisions',
    'quick_summary',
    'AnalyticsResult',
    'SeverityDistribution',
    'RateMetrics',
    'TrendResult',
    'BeforeAfterComparison',
    'calculate_severity_distribution',
    'calculate_rate_metrics',
    'calculate_annual_counts',
    'calculate_trend',
    'compare_before_after',
    'identify_risk_flags',
    'generate_insights',
    'format_rate',
    'format_percent',
    'format_change',
    'rate_summary_text',
    'trend_summary_text',
    
    # Defaults
    'DEFAULT_FIELD_MAP',
    'DEFAULT_DECODES',
    'FILTER_CONCEPTS',
    
    # Settings keys (backward compatibility)
    'SETTINGS_FIELD_MAP_KEY',
    'SETTINGS_DECODES_KEY',
    'SETTINGS_PROFILES_KEY',
    
    # v2 ConfigManager API
    'get_field_map',
    'set_field_map',
    'get_decodes',
    'get_decode_mapping',
    'set_decode_mapping',
    'save_config',
    'reset_config_to_defaults',
    'reset_field_map_to_defaults',
    'reset_decodes_to_defaults',
    
    # Import/Export
    'export_field_maps',
    'export_decodes',
    'export_profiles',
    'export_full_config',
    'import_field_maps',
    'import_decodes',
    'import_profiles',
    'import_full_config',
    
    # Legacy helpers
    'load_field_map_from_settings',
    'save_field_map_to_settings',
    'load_decodes_from_settings',
    'save_decodes_to_settings',
    'get_config_info',
    
    # Filter engine
    'FilterEngine',
    'FilterSpec',
    'DataCache',
    
    # Decode registry (legacy, still used by GUI)
    'DecodeRegistry',
    
    # Caching
    'DataCacheStandalone',
    'CacheStats',
    
    # Utilities
    'to_datetime',
    'to_datetime_cached',
    'clamp_date_range',
    'is_blank',
    'safe_str',
    'try_float',
    'numeric_str',
    'lru_cache_typed',
    'memoize',
    'Timer',
]
