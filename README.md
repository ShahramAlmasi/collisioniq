# Collision Analytics (QGIS Plugin)

## What it does
- Pick a collision layer (typically point features).
- Filter by **map selection** (default) or **whole layer**.
- Filter by date range and categorical fields (municipality, impact type, etc.).
- View summary + charts (if matplotlib is available in your QGIS Python env).
- Customize **field mapping** and **decode tables** (saved in QSettings per user).

## Notes
- Filtering is implemented in **Python** to avoid subtle interactions between QgsFeatureRequest filter types.
- Compatible with QGIS 3.16+ (tested with recent 3.x releases).
- First pass prioritizes correctness + UX; performance tuning can follow.

## Install (dev)
1. Zip the `collision_analytics` folder.
2. In QGIS: Plugins > Manage and Install Plugins... > Install from ZIP.
