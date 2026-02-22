"""GUI components for Collision Analytics."""
from __future__ import annotations

# Export all UI panels
from .ui import (
    FilterPanel,
    ResultsPanel,
    ConfigPanel,
    QualityPanel,
    SummaryPanel,
    AboutPanel,
)

# Keep existing exports for backward compatibility
from .dock import CollisionAnalyticsDockWidget
from .widgets import CheckListFilterBox

__all__ = [
    # Main dock widget
    "CollisionAnalyticsDockWidget",
    # Reusable widgets
    "CheckListFilterBox",
    # Individual panels
    "FilterPanel",
    "ResultsPanel",
    "ConfigPanel",
    "QualityPanel",
    "SummaryPanel",
    "AboutPanel",
]
