# Collision Analytics v2 - Architecture Plan

## Design Principles

1. **Practitioner-first**: Built by an engineer, for engineers
2. **Corporate GIS compatible**: Works with any schema, any data source
3. **250K+ record performance**: Sub-2-second filtering
4. **Shareable configurations**: Colleagues can use your field maps and decodes
5. **Progressive disclosure**: Simple by default, powerful when needed

## Module Structure

```
collision_analytics/
├── __init__.py              # Plugin entry point
├── plugin.py                # QGIS plugin lifecycle (thin)
├── metadata.txt             # QGIS plugin metadata
│
├── core/                    # Business logic (no UI)
│   ├── __init__.py
│   ├── config.py            # Constants, defaults, FILTER_CONCEPTS
│   ├── config_manager.py    # NEW: JSON-based config persistence
│   ├── filters.py           # REFACTORED: Optimized FilterEngine
│   ├── data_cache.py        # NEW: SQLite cache for large datasets
│   ├── analytics.py         # REFACTORED: Wired, rate calculations
│   ├── decodes.py           # UPDATED: Use ConfigManager
│   ├── charts.py            # REFACTORED: Render-on-demand
│   └── utils.py             # Date parsing, helpers
│
├── ui/                      # User interface
│   ├── __init__.py
│   ├── dock.py              # REFACTORED: Thin coordinator
│   ├── filter_panel.py      # NEW: Filter controls tab
│   ├── results_panel.py     # NEW: Charts + summary tab
│   ├── analytics_panel.py   # NEW: Engineering calculations tab
│   ├── config_panel.py      # NEW: Field mapping + decodes tab
│   ├── quality_panel.py     # NEW: Data quality checker
│   ├── widgets.py           # Reusable UI components
│   └── dialogs.py           # Export, import, profile management
│
├── resources/               # Static assets
│   ├── default_fields.json  # Default field mappings
│   └── default_decodes.json # Default decode tables
│
├── examples/                # Sample configs
│   ├── durham_schema.json   # Durham Region field map
│   └── mto_decodes.json     # MTO standard decodes
│
└── tests/                   # Unit tests (future)
```

## Performance Strategy

### Current Bottlenecks (250K records)
1. Pure Python iteration over all features
2. No indexing on categorical fields
3. All 18 charts render on every filter
4. No early-exit optimization

### Optimizations

| Technique | Implementation | Expected Gain |
|-----------|---------------|---------------|
| Early-exit filtering | Check most restrictive filter first | 20-40% |
| Categorical indexing | Build dict indexes on first load | 50-70% |
| Lazy chart rendering | Only render visible charts | 60-80% |
| SQLite cache | Cache decoded/filtered results | 70-90% |
| Background task | Already implemented, keep | Baseline |

### Target Performance
- 250K records, 12 filters: <2 seconds
- Chart render (visible only): <500ms
- Memory usage: <500MB for 250K records

## Config Portability Strategy

### Current Problem
- Field maps stored in QSettings (per-user, per-machine)
- Can't share configurations with colleagues
- Lost when QGIS profile resets

### Solution
```json
// collision_analytics_config.json (saved in same folder as .qgz)
{
  "version": "2.0.0",
  "field_map": {
    "date": "ACCIDENT_DATE",
    "municipality": "MUNICIPALITY",
    ...
  },
  "decodes": {
    "municipality": {"CL": "Clarington", ...},
    ...
  },
  "profiles": [
    {
      "name": "Fatal + Injury Only",
      "filters": {
        "accident_class": ["1", "2"],
        "date_range": ["2020-01-01", "2024-12-31"]
      }
    }
  ]
}
```

### Auto-Discovery
1. Check for `collision_analytics_config.json` in same folder as current project
2. If found, auto-load field map and decodes
3. User can still override per-session

## Analytics Engine

### Core Calculations

| Metric | Formula | Use Case |
|--------|---------|----------|
| Collision Rate | (Collisions × 1,000,000) / Entering Vehicles | Intersection comparison |
| KSI Rate | (Fatal + Injury × 1,000,000) / Entering Vehicles | Severity-adjusted comparison |
| PDO Rate | (PDO × 1,000,000) / Entering Vehicles | Property damage focus |
| Trend | Linear regression on annual counts | Directional assessment |
| Before/After | (After - Before) / Before × 100% | Treatment effectiveness |
| Statistical Significance | Chi-square or Poisson test | Confidence in change |

### Required Fields
- `entering_volume` (optional): For rate calculations
- `traffic_control`: For control type comparison
- `location_id`: For site-specific analysis

## Data Quality Panel

Auto-detect and flag:
- Missing required fields (date, location)
- Unknown codes (not in decode tables)
- Date gaps (missing years in time series)
- Duplicate locations (same coordinates)
- Null severity classifications
- Impossible dates (future, before 1900)

## UI Flow

```
User opens plugin
    ↓
Auto-detect current project config
    ↓
If no config: Show field mapping wizard
    ↓
Load layer → Build indexes → Show filter panel
    ↓
User applies filters → Background task → Results panel
    ↓
User explores charts (click to drill down)
    ↓
User exports or saves profile
```

## Migration Path

### From v1 to v2
1. v2 reads v1 QSettings if no JSON config exists (backward compatible)
2. On first save, export to JSON format
3. Future loads prefer JSON

### File Locations
| Type | v1 | v2 |
|------|----|----|
| Field maps | QSettings | JSON in project folder |
| Decodes | QSettings | JSON in project folder |
| Profiles | N/A | JSON in project folder |

## Development Phases

### Phase 1: Performance (Week 1)
- [ ] Profile current implementation
- [ ] Implement data cache layer
- [ ] Optimize FilterEngine
- [ ] Lazy chart rendering

### Phase 2: Config Portability (Week 1-2)
- [ ] ConfigManager implementation
- [ ] JSON schema design
- [ ] Auto-discovery logic
- [ ] Import/export UI

### Phase 3: Analytics (Week 2)
- [ ] Rate calculation engine
- [ ] Before/after comparison
- [ ] Trend analysis
- [ ] Analytics panel UI

### Phase 4: Quality & Polish (Week 2-3)
- [ ] Data quality panel
- [ ] Progress indicators
- [ ] UI refactoring
- [ ] Testing with 250K dataset

## Success Metrics

- [ ] Filter 250K records in <2 seconds
- [ ] Share configs with colleagues (copy JSON file)
- [ ] Save/load analysis profiles
- [ ] Data quality flags catch schema issues
- [ ] All analytics wired and displaying

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SQLite cache complexity | Make optional, fallback to in-memory |
| Config format changes | Version field in JSON, migration logic |
| Corporate schema variations | Extensive field mapping UI |
| QGIS version compatibility | Test with 3.16 LTR and 3.28+ |

---

*Architecture plan for practitioner-focused QGIS collision analysis plugin.*
