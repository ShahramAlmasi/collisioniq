"""Main dock widget - thin coordinator for UI panels."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from ..core.config import FILTER_CONCEPTS
from ..core import get_config_manager
from ..core.decodes import DecodeRegistry
from .ui.filter_panel import FilterPanel
from .ui.results_panel import ResultsPanel
from .ui.config_panel import ConfigPanel
from .ui.quality_panel import QualityPanel
from .ui.summary_panel import SummaryPanel
from .ui.about_panel import AboutPanel


class CollisionAnalyticsDockWidget(QDockWidget):
    """Main dock widget coordinating all panels."""
    
    def __init__(self, iface):
        super().__init__("Collision Analytics", iface.mainWindow())
        self.iface = iface
        
        # Initialize config and decodes
        self.config_mgr = get_config_manager()
        self.decodes = DecodeRegistry()
        
        self.setObjectName("CollisionAnalyticsDockWidget")
        self.root = QWidget()
        self.setWidget(self.root)
        
        self.layer = None
        self.field_map: Dict[str, str] = dict(self.config_mgr.field_map)
        
        # Keep reference to filtered data
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        
        self._build_ui()
        self._connect_signals()
        
        # Deferred init
        QTimer.singleShot(0, self._deferred_init)
    
    def _build_ui(self) -> None:
        """Build the main UI structure."""
        root_layout = QVBoxLayout()
        root_layout.setSpacing(8)
        
        # Top bar: Layer selection
        top_bar = QHBoxLayout()
        
        top_bar.addWidget(QLabel("Layer:"))
        
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        top_bar.addWidget(self.layer_combo, 1)
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_from_layer)
        top_bar.addWidget(self.btn_refresh)
        
        root_layout.addLayout(top_bar)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Create panels
        self.filter_panel = FilterPanel()
        self.summary_panel = SummaryPanel()
        self.results_panel = ResultsPanel()
        self.config_panel = ConfigPanel()
        self.quality_panel = QualityPanel()
        self.about_panel = AboutPanel()
        
        # Add tabs
        self.tabs.addTab(self.filter_panel, "Filters")
        self.tabs.addTab(self.summary_panel, "Summary")
        self.tabs.addTab(self.results_panel, "Charts")
        self.tabs.addTab(self.config_panel, "Config")
        self.tabs.addTab(self.quality_panel, "Quality")
        self.tabs.addTab(self.about_panel, "About")
        
        root_layout.addWidget(self.tabs, 1)
        
        # Initialize panels with config
        self.config_panel.set_config_manager(self.config_mgr, self.decodes)
        self.summary_panel.set_data(self.field_map, self.decodes)
        self.results_panel.set_data(self.field_map, self.decodes)
        
        self.root.setLayout(root_layout)
    
    def _connect_signals(self) -> None:
        """Connect signals between panels."""
        # Layer changes
        self.layer_combo.layerChanged.connect(self._on_layer_changed)
        
        # Filter panel signals
        self.filter_panel.filters_applied = self._on_filters_applied
        
        # Results panel chart clicks
        self.results_panel.chart_clicked = self._on_chart_clicked
        
        # Config panel changes
        self.config_panel.config_changed = self._on_config_changed
    
    def _deferred_init(self) -> None:
        """Initialize after UI is shown."""
        self.layer = self.layer_combo.currentLayer()
        self._on_layer_changed(self.layer)
    
    def _on_layer_changed(self, layer) -> None:
        """Handle layer change."""
        self.layer = layer
        
        # Update all panels
        self.filter_panel.set_layer(layer, self.field_map, self.decodes)
        self.config_panel.set_layer(layer)
        self.quality_panel.set_layer(layer, self.field_map, self.decodes)
        
        # Reset state
        if layer is None:
            self._set_idle_state()
            return
        
        # Auto-populate if selection exists
        if layer.selectedFeatureCount() > 0:
            self.filter_panel.apply_filters()
        else:
            self._set_idle_state()
    
    def _refresh_from_layer(self) -> None:
        """Refresh from current layer."""
        self._on_layer_changed(self.layer)
    
    def _on_filters_applied(self, fids: List[int], rows: List[Dict[str, Any]], total_count: int) -> None:
        """Handle filter application."""
        self.filtered_fids = fids
        self.filtered_rows = rows
        
        # Update dependent panels
        if rows:
            self.summary_panel.update_summary(rows)
            self.results_panel.update_results(rows)
        else:
            self._set_idle_state()
    
    def _on_chart_clicked(self, concept_key: str, label: str, additive: bool) -> None:
        """Handle chart click - apply filter."""
        # Handle env_combo specially
        if concept_key == "env_combo":
            # Parse combined label
            base = label.replace("\n", " ")
            import re
            base = re.sub(r"\s*\(\s*[\d,]+\s*\)\s*$", "", base)
            parts = [p.strip() for p in base.split("+")]
            if len(parts) >= 2:
                self.filter_panel.apply_category_filter("env1", parts[0], additive)
                self.filter_panel.apply_category_filter("env2", parts[1], additive)
            return
        
        # Switch to filters tab and apply
        changed = self.filter_panel.apply_category_filter(concept_key, label, additive)
        if changed:
            self.tabs.setCurrentWidget(self.filter_panel)
    
    def _on_config_changed(self) -> None:
        """Handle configuration changes."""
        # Reload field map
        self.field_map = self.config_panel.get_field_map()
        
        # Update panels
        self.filter_panel.set_layer(self.layer, self.field_map, self.decodes)
        self.summary_panel.set_data(self.field_map, self.decodes)
        self.results_panel.set_data(self.field_map, self.decodes)
        self.quality_panel.set_layer(self.layer, self.field_map, self.decodes)
        
        # Re-apply filters with new config
        self.filter_panel.apply_filters()
    
    def _set_idle_state(self) -> None:
        """Set all panels to idle state."""
        self.filtered_fids = []
        self.filtered_rows = []
        self.filter_panel.reset_all_filters()
        self.summary_panel._set_idle_state()
        self.results_panel.set_idle_state()
    
    # Public API for external use
    def get_filtered_features(self) -> Tuple[List[int], List[Dict[str, Any]]]:
        """Get currently filtered feature IDs and data."""
        return self.filtered_fids, self.filtered_rows
    
    def apply_filters(self) -> None:
        """Trigger filter application."""
        self.filter_panel.apply_filters()
    
    def reset_filters(self) -> None:
        """Reset all filters."""
        self.filter_panel.reset_all_filters()
