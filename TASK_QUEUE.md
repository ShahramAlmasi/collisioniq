# Collision Analytics v2 - Task Queue

## Active
- [ ] Performance & Data Layer (subagent running)

## Queued
1. [ ] Config Portability - ConfigManager + JSON schema
2. [ ] Analytics Engine - Rate calculations, before/after
3. [ ] UI/UX Modernization - Refactored panels, virtual scrolling

## Manual Tasks (main session)
- [x] Architecture plan
- [ ] Review subagent outputs
- [ ] Integration testing
- [ ] Documentation updates
- [ ] Version bump & changelog

## Subagent Spawn Commands (ready to run)

### Config Portability
```
sessions_spawn(mode="run", model="kimi-coding/k2p5", task="""
Collision Analytics v2 Rebuild - Config Portability

Read the current collision_analytics codebase.

Your mission:
1. Replace QSettings storage with JSON file-based configs that travel with QGIS projects
2. Design schema for:
   - field_maps.json (layer field → plugin concept mapping)
   - decodes.json (code → label mappings)
   - profiles.json (saved filter presets)
3. Implement ConfigManager class in core/config_manager.py
4. Update core/config.py to use new system while keeping backward compatibility
5. Add import/export UI functions for sharing configs with colleagues

Deliver:
- core/config_manager.py (new)
- Updated core/config.py
- JSON schema documentation: CONFIG_SCHEMA.md
- Example config files in examples/
""")
```

### Analytics Engine
```
sessions_spawn(mode="run", model="kimi-coding/k2p5", task="""
Collision Analytics v2 Rebuild - Analytics Engine

Read the current collision_analytics codebase.

Your mission:
1. Currently core/analytics.py is unused - wire it into the UI properly
2. Implement practitioner-focused analytics:
   - Rate calculations (collisions per entering vehicles, per km, per intersection)
   - Before/after comparison (two time periods, statistical significance)
   - Exposure-adjusted metrics (KSI per 100M entering vehicles)
   - Trend analysis (simple linear regression on annual counts)
3. Design API that accepts filtered_rows and returns analytics results
4. Add summary panel display for key metrics

Deliver:
- Rewritten core/analytics.py with full analytics suite
- Updated gui/dock.py integration (add Analytics tab or integrate into Summary)
- Document calculations in ANALYTICS.md
""")
```

### UI/UX Modernization
```
sessions_spawn(mode="run", model="kimi-coding/k2p5", task="""
Collision Analytics v2 Rebuild - UI/UX Modernization

Read the current collision_analytics codebase.

Your mission:
1. gui/dock.py is 1,900 lines - refactor into focused modules:
   - ui/filter_panel.py (filter controls)
   - ui/results_panel.py (charts + summary)
   - ui/config_panel.py (field mapping, decodes)
2. Implement virtual scrolling for charts (render on demand, not all 18 at once)
3. Add Data Quality panel: auto-detect missing fields, unknown codes, date gaps
4. Add Progress indicators for background filtering
5. Improve responsive layout (collapsible sections, better use of dock space)

Deliver:
- Refactored ui/ package with clean separation
- Virtual chart rendering implementation
- Data quality checker in ui/quality_panel.py
- Progress bar integration with FilterTask
""")
```
