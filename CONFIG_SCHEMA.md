# JSON Schema for Collision Analytics v2 Configs

## Overview

Configs are stored as JSON files alongside QGIS projects for portability. The `ConfigManager` class (in `core/config_manager.py`) handles loading, saving, and auto-discovery of configuration files.

## Main Config File

**Filename:** `collision_analytics_config.json`

**Location:** Auto-discovered in QGIS project folder (and parent folders up to 3 levels).

### Full JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Collision Analytics Configuration",
  "description": "Portable configuration for Collision Analytics QGIS plugin",
  "type": "object",
  "required": ["version", "field_map"],
  "properties": {
    "version": {
      "type": "string",
      "description": "Config format version",
      "enum": ["2.0.0"]
    },
    "metadata": {
      "type": "object",
      "properties": {
        "created_by": { "type": "string" },
        "created_date": { "type": "string", "format": "date" },
        "description": { "type": "string" },
        "organization": { "type": "string" },
        "schema_source": { "type": "string" },
        "last_modified": { "type": "string", "format": "date" }
      }
    },
    "field_map": {
      "type": "object",
      "description": "Maps plugin concepts to layer field names",
      "properties": {
        "date": { "type": "string", "description": "Accident date field" },
        "municipality": { "type": "string" },
        "accident_class": { "type": "string" },
        "accident_location": { "type": "string" },
        "impact_location": { "type": "string" },
        "impact_type": { "type": "string" },
        "light": { "type": "string" },
        "traffic_control": { "type": "string" },
        "traffic_control_condition": { "type": "string" },
        "road_jurisdiction": { "type": "string" },
        "env1": { "type": "string", "description": "Environment condition 1" },
        "env2": { "type": "string", "description": "Environment condition 2" },
        "location_id": { "type": "string" },
        "location_type": { "type": "string" },
        "map_x": { "type": "string", "description": "X coordinate field" },
        "map_y": { "type": "string", "description": "Y coordinate field" },
        "veh_cnt": { "type": "string", "description": "Vehicle count field" },
        "ped_cnt": { "type": "string", "description": "Pedestrian count field" },
        "occ_cnt": { "type": "string", "description": "Occupant count field" },
        "drv_cnt": { "type": "string", "description": "Driver count field" },
        "per_cnt": { "type": "string", "description": "Person count field" },
        "entering_volume": { "type": "string", "description": "Optional: for rate calculations" }
      },
      "additionalProperties": false
    },
    "decodes": {
      "type": "object",
      "description": "Code-to-label mappings for categorical fields",
      "patternProperties": {
        "^[a-z_]+$": {
          "type": "object",
          "description": "Concept key mapping raw codes to labels",
          "patternProperties": {
            "^.+$": { "type": "string" }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": false
    },
    "profiles": {
      "type": "array",
      "description": "Saved filter presets for common analyses",
      "items": {
        "type": "object",
        "required": ["name", "filters"],
        "properties": {
          "name": { "type": "string", "description": "Profile display name" },
          "description": { "type": "string" },
          "filters": {
            "type": "object",
            "properties": {
              "date_enabled": { "type": "boolean", "default": true },
              "date_start": { "type": "string", "format": "date" },
              "date_end": { "type": "string", "format": "date" },
              "selection_only": { "type": "boolean", "default": true },
              "categories": {
                "type": "object",
                "description": "Concept key → array of selected raw codes",
                "patternProperties": {
                  "^[a-z_]+$": { "type": "array", "items": { "type": "string" } }
                }
              }
            }
          }
        }
      }
    },
    "ui_preferences": {
      "type": "object",
      "properties": {
        "top_n_default": { "type": "integer", "default": 12 },
        "chart_height": { "type": "integer", "default": 420 },
        "show_value_labels": { "type": "boolean", "default": true },
        "default_date_range_years": { "type": "integer", "default": 10 }
      }
    },
    "performance": {
      "type": "object",
      "properties": {
        "enable_caching": { "type": "boolean", "default": true },
        "cache_threshold": { "type": "integer", "default": 50000, "description": "Feature count to trigger caching" },
        "background_task_threshold": { "type": "integer", "default": 50000 }
      }
    }
  }
}
```

## Example Full Config

```json
{
  "version": "2.0.0",
  "metadata": {
    "created_by": "Shahram Almasi",
    "created_date": "2024-02-22",
    "description": "Durham Region collision analysis configuration",
    "organization": "Regional Municipality of Durham",
    "schema_source": "Corporate GIS - Safety Section",
    "last_modified": "2024-02-22"
  },
  "field_map": {
    "date": "ACCIDENT_DATE",
    "municipality": "MUNICIPALITY",
    "accident_class": "ACCIDENT_CLASS",
    "accident_location": "LOCATION_TYPE",
    "impact_type": "IMPACT_TYPE",
    "light": "LIGHT_CONDITION",
    "traffic_control": "TRAFFIC_CONTROL",
    "env1": "ENV_CONDITION1",
    "env2": "ENV_CONDITION2",
    "veh_cnt": "VEHICLES_INVOLVED",
    "ped_cnt": "PEDESTRIANS_INVOLVED"
  },
  "decodes": {
    "municipality": {
      "CL": "Clarington",
      "WH": "Whitby",
      "OA": "Oshawa",
      "UX": "Uxbridge",
      "SC": "Scugog",
      "AJ": "Ajax",
      "PI": "Pickering",
      "BR": "Brock"
    },
    "accident_class": {
      "1": "Fatal",
      "2": "Injury",
      "3": "PDO",
      "4": "Unknown"
    }
  },
  "profiles": [
    {
      "name": "Fatal + Injury Last 5 Years",
      "description": "Severe collisions in recent period",
      "filters": {
        "date_enabled": true,
        "date_start": "2020-01-01",
        "date_end": "2024-12-31",
        "selection_only": true,
        "categories": {
          "accident_class": ["1", "2"]
        }
      }
    },
    {
      "name": "Signalized Intersections",
      "filters": {
        "traffic_control": ["1"]
      }
    }
  ],
  "ui_preferences": {
    "top_n_default": 15,
    "default_date_range_years": 10
  },
  "performance": {
    "enable_caching": true,
    "cache_threshold": 50000
  }
}
```

## Shareable Export Files

For team sharing, configs can be exported as separate files:

### 1. Field Maps Export (`field_maps.json`)

```json
{
  "version": "2.0.0",
  "metadata": {
    "exported_by": "Shahram Almasi",
    "export_date": "2024-02-22",
    "type": "field_maps"
  },
  "field_map": {
    "date": "ACCIDENT_DATE",
    "municipality": "MUNICIPALITY",
    "accident_class": "ACCIDENT_CLASS"
  }
}
```

### 2. Decodes Export (`decodes.json`)

```json
{
  "version": "2.0.0",
  "metadata": {
    "exported_by": "Shahram Almasi",
    "export_date": "2024-02-22",
    "type": "decodes"
  },
  "decodes": {
    "municipality": {
      "CL": "Clarington",
      "WH": "Whitby"
    },
    "accident_class": {
      "1": "Fatal",
      "2": "Injury"
    }
  }
}
```

### 3. Profiles Export (`profiles.json`)

```json
{
  "version": "2.0.0",
  "metadata": {
    "exported_by": "Shahram Almasi",
    "export_date": "2024-02-22",
    "type": "profiles"
  },
  "profiles": [
    {
      "name": "Fatal + Injury Last 5 Years",
      "description": "Severe collisions in recent period",
      "filters": {
        "date_enabled": true,
        "date_start": "2020-01-01",
        "date_end": "2024-12-31",
        "selection_only": true,
        "categories": {
          "accident_class": ["1", "2"]
        }
      }
    }
  ]
}
```

## Auto-Discovery Rules

The `ConfigManager` implements the following auto-discovery:

1. **Primary:** Check current QGIS project folder for `collision_analytics_config.json`
2. **Secondary:** Check parent folders (up to 3 levels up)
3. **Fallback:** Use defaults + v1 QSettings (backward compatibility)
4. **On Save:** Always write to current project folder

```python
from core import get_config_manager

# ConfigManager auto-loads on initialization
mgr = get_config_manager()

# Check where config was loaded from
if mgr.is_using_json_config:
    print(f"Loaded from: {mgr.config_path}")
else:
    print("Using QSettings fallback (v1 compatibility)")
```

## Python API

### ConfigManager Class

```python
from core import ConfigManager, get_config_manager

# Get singleton instance (auto-loads config)
mgr = get_config_manager()

# Access current configuration
field_map = mgr.field_map          # Dict[str, str]
decodes = mgr.decodes              # Dict[str, Dict[str, str]]
profiles = mgr.profiles            # List[Profile]
ui_prefs = mgr.ui_preferences      # Dict[str, Any]
metadata = mgr.metadata            # Dict[str, Any]
```

### Modify and Save

```python
# Update field mapping
mgr.field_map["date"] = "ACCIDENT_DATE"
mgr.save()

# Update decode table
mgr.set_decode_mapping("municipality", {"CL": "Clarington", "WH": "Whitby"})
mgr.save()

# Add profile
from core.config_manager import Profile
profile = Profile(
    name="Fatal + Injury Last 5 Years",
    description="Severe collisions",
    filters={"categories": {"accident_class": ["1", "2"]}}
)
mgr.add_profile(profile)
mgr.save()
```

### Reset to Defaults

```python
# Reset all to defaults
mgr.reset_to_defaults()
mgr.save()

# Or reset specific sections
mgr.reset_field_map()
mgr.reset_decodes()
mgr.save()
```

### Import/Export for Sharing

```python
# Export specific components
mgr.export_field_maps("/path/to/field_maps.json")
mgr.export_decodes("/path/to/decodes.json", concepts=["municipality", "accident_class"])
mgr.export_profiles("/path/to/profiles.json", profile_names=["Profile 1", "Profile 2"])

# Export full config
mgr.export_full_config("/path/to/full_config.json")

# Import (with merge option for field maps and decodes)
mgr.import_field_maps("/path/to/field_maps.json", merge=True)
mgr.import_decodes("/path/to/decodes.json", merge=True)
mgr.import_profiles("/path/to/profiles.json")
mgr.import_full_config("/path/to/full_config.json")
mgr.save()
```

### Convenience Functions (core.config)

```python
from core import (
    # Get/Set
    get_field_map, set_field_map,
    get_decodes, get_decode_mapping, set_decode_mapping,
    
    # Save
    save_config,
    
    # Reset
    reset_config_to_defaults,
    reset_field_map_to_defaults,
    reset_decodes_to_defaults,
    
    # Import/Export
    export_field_maps, export_decodes, export_profiles, export_full_config,
    import_field_maps, import_decodes, import_profiles, import_full_config,
    
    # Info
    get_config_info,
)

# Simple API (auto-saves)
set_field_map({"date": "ACCIDENT_DATE", ...})
decodes = get_decodes()
export_full_config("/path/to/config.json")
```

## Backward Compatibility

### v1 QSettings Integration

- **QSettings Keys:**
  - `collision_analytics/field_map_json`
  - `collision_analytics/decodes_json`
  - `collision_analytics/profiles_json`

### Migration Path

1. **Existing v1 users:** Plugin continues to work with QSettings
2. **First JSON save:** Config automatically exports to project folder
3. **Subsequent loads:** JSON preferred over QSettings
4. **Legacy API:** `DecodeRegistry` still works via QSettings for UI compatibility

```python
# Legacy QSettings helpers (still available)
from core import load_field_map_from_settings, save_field_map_to_settings
from core import load_decodes_from_settings, save_decodes_to_settings

# These work alongside the new ConfigManager
```

### Config Status Check

```python
from core import get_config_info

info = get_config_info()
print(info)
# {
#   "is_using_json_config": True,
#   "config_path": "/path/to/project/collision_analytics_config.json",
#   "version": "2.0.0",
#   "metadata": {...}
# }
```

## File Organization

Recommended project structure for team sharing:

```
project_folder/
├── project_name.qgz              # QGIS project file
├── collision_analytics_config.json  # Main plugin config
├── data/
│   └── collisions.gpkg
└── shared_configs/               # Optional: shared team configs
    ├── durham_field_maps.json
    ├── durham_decodes.json
    └── common_profiles.json
```
