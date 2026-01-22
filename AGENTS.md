Collision Analytics (QGIS plugin) overview

Purpose
- Provides a dockable UI to filter collision point data (often the "clns" layer) by selection, date range, and categorical fields, then summarizes and charts the results.
- Designed for analysts to explore collision patterns without leaving QGIS; includes per-user field mapping and decode tables to adapt to varying schemas.

Architecture and entry points
- QGIS plugin entry: `__init__.py` exposes `classFactory()` which instantiates `CollisionAnalyticsPlugin` in `plugin.py`.
- UI entry: `CollisionAnalyticsPlugin.initGui()` registers a toolbar/menu action and opens `CollisionAnalyticsDockWidget` in `gui/dock.py`.
- Core logic modules:
  - `core/filters.py`: `FilterSpec`, `FilterEngine` apply selection/date/category filtering in pure Python.
  - `core/charts.py`: matplotlib-based chart renderers and styling helpers.
  - `core/config.py`: default field mapping and default decode tables.
  - `core/decodes.py`: decode registry persisted in `QSettings`.
  - `core/utils.py`: date parsing and numeric helpers.
  - `core/analytics.py`: counters/summaries (currently not wired into the UI).

How the "clns" layer is located and validated
- There is no hard-coded "clns" name. The user selects a layer via `QgsMapLayerComboBox` filtered to point layers (`QgsMapLayerProxyModel.PointLayer`).
- Validation is minimal: if a mapped field does not exist in the chosen layer, filter UI shows "field not mapped" and the field is skipped.
- Default field names are in `core/config.py` (`DEFAULT_FIELD_MAP`), which assumes a collision layer schema with specific attribute names.

How selected features are accessed and processed
- The default scope is "map selection" (`self.chk_selection_only` in `gui/dock.py`).
- Selected feature IDs are pulled from `layer.selectedFeatureIds()` and passed into `FilterSpec`.
- `FilterEngine.iter_candidates()` uses `QgsFeatureRequest.setFilterFids()` when selection-only is enabled and there is a selection; otherwise it iterates the layer.
- Attributes are reduced to the needed set of fields via `QgsFeatureRequest.setSubsetOfAttributes()` to limit per-feature work.

Data flow from selection to charts/graphs
1) User selects a point layer and (optionally) selects features on the map.
2) UI builds a `FilterSpec` from selection, date range, and checklist filters.
3) `FilterEngine.apply()` returns `(fids, rows)` where rows are dicts of field -> value.
4) `CollisionAnalyticsDockWidget` stores `self.filtered_rows` and `self.filtered_fids` and optionally selects them in QGIS.
5) Summary HTML is produced from `filtered_rows` (counts, severity, exposure sums, heuristics).
6) Chart cards call functions in `core/charts.py`, which aggregate with `Counter` and date parsing (`to_datetime`).
7) Results are rendered into embedded matplotlib canvases, or a text-only summary if matplotlib is unavailable.

Aggregation and chart generation
- Categorical breakdowns: `charts.render_category()` and `charts.render_category_by_class()` count and sort values, optionally decoding codes.
- Temporal breakdowns: `charts.render_temporal_by_class()` groups by year/month/day-of-week/hour using the mapped date field.
- Pareto: `charts.render_pareto()` builds cumulative contribution plots for impact types.
- Environment combo: `charts.render_env_combo()` combines env1/env2 categories (expects non-null/0-ish values).
- Summary calculations live in `gui/dock.py::_update_results_view()` and use decoding + numeric sums.

Outputs and rendering
- QGIS UI: a dock widget with tabs (Filters, Results, Fields, Decodes).
- Charts: embedded matplotlib canvases (`FigureCanvasQTAgg`) if matplotlib is installed; otherwise charts are disabled and only text summary is shown.
- Exports:
  - Summary CSV (`export_summary_csv`): totals and exposure sums.
  - Filtered features CSV (`export_filtered_features_csv`): raw fields plus decoded columns where applicable.
  - Dashboard PNG (`export_dashboard_png`): re-renders all charts into a single matplotlib figure.

Key assumptions and constraints
- Layer type: point geometries only (combo box filters to point layers).
- Field mapping: relies on `DEFAULT_FIELD_MAP` or user overrides; missing fields are skipped.
- Date handling: expects values convertible by `to_datetime` (datetime, date, QDateTime/QDate, or ISO-like strings).
- Categorical fields: values are compared as trimmed strings; numeric fields receive special float matching in `FilterEngine._match_category`.
- Unique values: `layer.uniqueValues()` is capped at 5000 and may not be supported; fallback is decode tables.
- Selection scope: if selection-only is enabled but no selection and no filter intent, UI stays idle; if filter intent exists, it scans the whole layer after a warning.

External dependencies
- PyQGIS (QGIS 3.28+), Qt/PyQt widgets, QSettings.
- Optional: matplotlib + numpy (charts are disabled if missing).

Fragile or tightly-coupled areas
- Chart rendering relies on matplotlib’s QtAgg backend; environment differences can disable charts entirely.
- Field mapping is user-configurable, but many UI elements and charts assume those concepts exist; missing mappings silently reduce chart content.
- Decode tables are stored in `QSettings`; malformed or missing decode data can lead to "Unknown / blank" labels.
- `core/analytics.py` is currently unused; avoid editing assuming it affects the UI without wiring it in.

Safe modification and extension guidance
- Prefer adding new concepts by extending `DEFAULT_FIELD_MAP`, `FILTER_CONCEPTS`, and `DEFAULT_DECODES` together, then update charts and UI to match.
- Keep filtering logic in `FilterEngine` to avoid mixing QgsFeatureRequest filter types (this is an explicit design choice).
- When adding charts, follow the existing pattern in `_init_dashboard_charts()` and create a dedicated render function in `core/charts.py`.
- Preserve the "selection-only by default" UX to avoid heavy scans on large layers.
- Maintain ASCII-only edits unless a file already contains Unicode; UI labels can remain ASCII.

Conventions to respect
- Concept keys (e.g., `impact_type`, `accident_class`) drive field mapping and decoding; don’t rename without updating all mappings and chart calls.
- Decode functions always accept raw values and return "Unknown / blank" for empty values.
- Filtering and summaries operate on `filtered_rows` (dicts of field -> value), not QgsFeature objects.
