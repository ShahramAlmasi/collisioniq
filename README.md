# Collision Analytics v2

A QGIS plugin for practitioner-focused collision data analysis. Built by engineers, for engineers.

## What's New in v2

### Performance (v2.1 - Major Improvements)
- **4-8x faster filtering** on 250K records (<2 seconds target achieved!)
- **Pre-computed field metadata** - Eliminates 3M+ repeated QgsField lookups
- **Cached date parsing** - LRU cache eliminates redundant datetime operations
- **Pre-normalized filter sets** - Category codes normalized once, not 250K times
- **Early-exit optimization** - Most selective filters checked first
- **SQLite result caching** - Filter results persist across sessions
- **Pre-allocated arrays** - Reduced memory reallocations during filtering

### Portability
- **JSON-based configs** - Share field maps and decodes with colleagues
- **Project-portable settings** - Configs travel with `.qgz` projects
- **Analysis profiles** - Save and reuse common filter combinations
- **Import/export** - Easy team collaboration

### Analytics (New)
- **Rate calculations** - Collisions per entering vehicles, per km
- **Before/after comparison** - Treatment effectiveness analysis
- **Trend analysis** - Linear regression on time series
- **KSI metrics** - Kill-and-Serious-Injury calculations

### Data Quality
- **Auto-detection** of schema mismatches
- **Missing field warnings** - Clear guidance on field mapping
- **Unknown code flags** - Identify decode table gaps
- **Date gap detection** - Spot missing years in data

## Performance Benchmarks

| Dataset Size | Filters | v1 Time | v2.1 Time | Speedup |
|--------------|---------|---------|-----------|---------|
| 50K records | 12 filters | ~3s | 0.04s | **75x** |
| 250K records | 12 filters | ~12s | 0.20s | **60x** |
| 250K records | Date only | ~3s | 0.15s | **20x** |

*Benchmarks on standard hardware. Actual performance varies by data complexity.*

## Installation

### Requirements
- QGIS 3.16+ (LTR recommended)
- Python 3.9+

### Install from ZIP
1. Download `collision_analytics.zip` from releases
2. In QGIS: Plugins → Manage and Install Plugins → Install from ZIP
3. Select the downloaded file

### Development Install
```bash
cd ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
git clone https://gitea.deex.cc/deex/collision_analytics.git
```

## Quick Start

1. **Load collision data** as a point layer in QGIS
2. **Open Collision Analytics** from the toolbar
3. **Configure field mapping** (first time only) - map your layer fields to plugin concepts
4. **Select features** on map or set filters
5. **Click Apply** to analyze

## Configuration

### Creating a Config File

Save `collision_analytics_config.json` in your project folder:

```json
{
  "version": "2.0.0",
  "field_map": {
    "date": "ACCIDENT_DATE",
    "municipality": "MUNICIPALITY",
    "accident_class": "ACCIDENT_CLASS"
  },
  "decodes": {
    "municipality": {
      "CL": "Clarington",
      "WH": "Whitby"
    }
  }
}
```

The plugin auto-discovers this file when you open your QGIS project.

### Sharing Configs

1. Export your config: File → Export Config
2. Share the JSON file with colleagues
3. They import: File → Import Config

## Performance Tuning

For large datasets (100K+ records):

### Automatic Optimizations (v2.1+)
The plugin now automatically applies these optimizations:

1. **Field metadata caching** - QgsField lookups cached per filter operation
2. **Date parsing cache** - LRU cache for repeated date values
3. **Filter reordering** - Most selective filters checked first
4. **Result caching** - SQLite-backed cache persists across sessions
5. **Pre-allocated arrays** - Memory-efficient result collection

### Manual Tuning

1. **Enable caching** - Cache is on by default; disable with `enable_cache=False`
2. **Use selection scope** - Filter selected features only (faster initial filtering)
3. **Date range first** - Date filters are most selective for early exit
4. **Background tasks** - Auto-enabled for 50K+ features

### Cache Location

Cache files stored in:
```
~/.qgis/collision_analytics_cache/
```

Clear cache programmatically:
```python
from core.data_cache import clear_all_caches
clear_all_caches()
```

### Cache Statistics
```python
from core.data_cache import get_global_cache_stats
print(get_global_cache_stats())
# {'hits': 42, 'misses': 8, 'hit_rate': 0.84}
```

## Architecture

```
collision_analytics/
├── core/                 # Business logic
│   ├── filters.py        # Optimized filtering engine (v2.1)
│   ├── data_cache.py     # SQLite caching layer (v2.1)
│   ├── analytics.py      # Rate calculations
│   ├── decodes.py        # Decode registry
│   ├── utils.py          # Utilities with LRU caching
│   └── config.py         # Default configurations
├── gui/                  # User interface
│   ├── dock.py           # Main dock widget
│   ├── widgets.py        # Reusable UI components
│   └── dialogs.py        # Dialog windows
└── benchmark.py          # Performance testing
```

### Key Optimizations (v2.1)

**filters.py:**
- `_FieldMeta` - Pre-computed field metadata
- `_CategoryFilter` - Pre-normalized filter sets
- `to_datetime_cached()` - LRU-cached date parsing
- `DataCache` integration - Persistent result caching

**data_cache.py:**
- SQLite WAL mode for concurrency
- Thread-local connections
- LRU eviction for size limits
- Cache statistics tracking

**utils.py:**
- `lru_cache_typed()` decorator
- `to_datetime_cached()` with 64K entry cache
- `Timer` context manager for profiling

## Development

### Running Tests
```bash
cd projects/collision_analytics
python -m pytest tests/
```

### Building Release
```bash
make zip
# Creates collision_analytics.zip for distribution
```

## License

Proprietary - Regional Municipality of Durham

## Author

**Shahram Almasi**  
Traffic Operations and Road Safety Engineer  
Regional Municipality of Durham

---

*Built for practitioners. Optimized for 250K records. Shareable with colleagues.*
