"""Main dock widget - modern coordinator for UI panels."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from ..core.config import FILTER_CONCEPTS
from ..core import get_config_manager
from ..core.decodes import DecodeRegistry
from .modern_widgets import (
    apply_modern_stylesheet,
    Badge,
    Colors,
    SegmentedControl,
    StatusIndicator,
    Typography,
)
from .ui.filter_panel import FilterPanel
from .ui.results_panel import ResultsPanel
from .ui.config_panel import ConfigPanel
from .ui.quality_panel import QualityPanel
from .ui.summary_panel import SummaryPanel
from .ui.about_panel import AboutPanel


class CollisionAnalyticsDockWidget(QDockWidget):
    """Main dock widget coordinating all panels with modern UI."""
    
    def __init__(self, iface):
        super().__init__("Collision Analytics", iface.mainWindow())
        self.iface = iface
        
        # Initialize config and decodes
        self.config_mgr = get_config_manager()
        self.decodes = DecodeRegistry()
        
        self.setObjectName("CollisionAnalyticsDockWidget")
        self.setMinimumWidth(420)
        self.setMinimumHeight(600)
        
        # State
        self.layer = None
        self.field_map: Dict[str, str] = dict(self.config_mgr.field_map)
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self._setting_idle = False  # Guard against recursion
        
        self._build_ui()
        self._connect_signals()
        
        # Apply modern stylesheet
        apply_modern_stylesheet(self)
        
        # Deferred init
        QTimer.singleShot(0, self._deferred_init)
    
    def _build_ui(self) -> None:
        """Build the modern main UI structure."""
        self.root = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        
        # ===== Header Section =====
        header = self._build_header()
        root_layout.addWidget(header)
        
        # ===== Status Bar =====
        self.status_bar = self._build_status_bar()
        root_layout.addWidget(self.status_bar)
        
        # ===== Main Navigation =====
        self.nav_control = SegmentedControl([
            ("analyze", "📊 Analyze"),
            ("configure", "⚙️ Configure"),
        ])
        self.nav_control.selection_changed = self._on_nav_changed
        root_layout.addWidget(self.nav_control)
        
        # ===== Content Stack =====
        self.content_stack = QStackedWidget()
        
        # Analyze page
        self.analyze_page = self._build_analyze_page()
        self.content_stack.addWidget(self.analyze_page)
        
        # Configure page
        self.configure_page = self._build_configure_page()
        self.content_stack.addWidget(self.configure_page)
        
        root_layout.addWidget(self.content_stack, 1)
        
        self.root.setLayout(root_layout)
        self.setWidget(self.root)
    
    def _build_header(self) -> QWidget:
        """Build the header with layer selection."""
        header = QWidget()
        header.setStyleSheet(f"""
            background-color: {Colors.BG_SECONDARY};
            border-radius: 8px;
            padding: 8px;
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Title row
        title_row = QHBoxLayout()
        
        title = QLabel("🚦 Collision Analytics")
        title.setStyleSheet(f"""
            font-size: {Typography.XXL}px;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        version = Badge("v2.0", "info")
        
        title_row.addWidget(title)
        title_row.addWidget(version)
        title_row.addStretch(1)
        
        # Help button
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(28, 28)
        self.btn_help.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_RAISED};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 14px;
                color: {Colors.TEXT_SECONDARY};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: white;
            }}
        """)
        self.btn_help.setToolTip("About / Help")
        self.btn_help.clicked.connect(self._show_about)
        title_row.addWidget(self.btn_help)
        
        layout.addLayout(title_row)
        
        # Layer selector row
        layer_row = QHBoxLayout()
        layer_row.setSpacing(8)
        
        layer_label = QLabel("Data Layer:")
        layer_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layer_combo.setMinimumWidth(200)
        
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(32, 32)
        self.btn_refresh.setToolTip("Refresh from layer")
        
        layer_row.addWidget(layer_label)
        layer_row.addWidget(self.layer_combo, 1)
        layer_row.addWidget(self.btn_refresh)
        
        layout.addLayout(layer_row)
        
        header.setLayout(layout)
        return header
    
    def _build_status_bar(self) -> QWidget:
        """Build the status indicator bar."""
        bar = QWidget()
        bar.setStyleSheet(f"background: transparent;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(16)
        
        self.status_indicator = StatusIndicator("idle", "Ready")
        
        self.feature_badge = Badge("0 features", "default")
        self.filter_badge = Badge("No filters", "default")
        
        layout.addWidget(self.status_indicator)
        layout.addStretch(1)
        layout.addWidget(self.feature_badge)
        layout.addWidget(self.filter_badge)
        
        bar.setLayout(layout)
        return bar
    
    def _build_analyze_page(self) -> QWidget:
        """Build the Analyze page with tabs."""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Create panels
        self.filter_panel = FilterPanel()
        self.summary_panel = SummaryPanel()
        self.results_panel = ResultsPanel()
        self.quality_panel = QualityPanel()
        
        # Tab widget for analyze sections
        self.analyze_tabs = QTabWidget()
        self.analyze_tabs.setDocumentMode(True)
        
        self.analyze_tabs.addTab(self.filter_panel, "🔍 Filters")
        self.analyze_tabs.addTab(self.summary_panel, "📈 Summary")
        self.analyze_tabs.addTab(self.results_panel, "📊 Charts")
        self.analyze_tabs.addTab(self.quality_panel, "✓ Quality")
        
        layout.addWidget(self.analyze_tabs)
        page.setLayout(layout)
        
        # Initialize panels with config
        self.summary_panel.set_data(self.field_map, self.decodes)
        self.results_panel.set_data(self.field_map, self.decodes)
        
        return page
    
    def _build_configure_page(self) -> QWidget:
        """Build the Configure page."""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Config panel
        self.config_panel = ConfigPanel()
        self.config_panel.set_config_manager(self.config_mgr, self.decodes)
        
        # About panel in config (compact)
        self.about_panel = AboutPanel()
        
        # Tabs for config sections
        self.config_tabs = QTabWidget()
        self.config_tabs.setDocumentMode(True)
        
        self.config_tabs.addTab(self.config_panel, "⚙️ Field Mapping & Decodes")
        self.config_tabs.addTab(self.about_panel, "ℹ️ About")
        
        layout.addWidget(self.config_tabs)
        page.setLayout(layout)
        
        return page
    
    def _connect_signals(self) -> None:
        """Connect signals between panels."""
        # Layer changes
        self.layer_combo.layerChanged.connect(self._on_layer_changed)
        self.btn_refresh.clicked.connect(self._refresh_from_layer)
        
        # Filter panel signals
        self.filter_panel.filters_applied = self._on_filters_applied
        self.filter_panel.status_changed = self._on_filter_status_changed
        
        # Results panel chart clicks
        self.results_panel.chart_clicked = self._on_chart_clicked
        
        # Config panel changes
        self.config_panel.config_changed = self._on_config_changed
    
    def _deferred_init(self) -> None:
        """Initialize after UI is shown."""
        self.layer = self.layer_combo.currentLayer()
        self._on_layer_changed(self.layer)
    
    def _on_nav_changed(self, index: int, key: str) -> None:
        """Handle navigation change."""
        if key == "analyze":
            self.content_stack.setCurrentIndex(0)
        elif key == "configure":
            self.content_stack.setCurrentIndex(1)
    
    def _on_layer_changed(self, layer) -> None:
        """Handle layer change with modern status updates."""
        self.layer = layer
        
        # Update status
        if layer is None:
            self.status_indicator.set_status("idle", "No layer selected")
            self.feature_badge.setText("0 features")
            self._set_idle_state()
            return
        
        feature_count = layer.featureCount()
        self.status_indicator.set_status("active", f"Layer: {layer.name()}")
        self.feature_badge.setText(f"{feature_count:,} features")
        self.feature_badge.set_variant("info")
        
        # Update all panels
        self.filter_panel.set_layer(layer, self.field_map, self.decodes)
        self.config_panel.set_layer(layer)
        self.quality_panel.set_layer(layer, self.field_map, self.decodes)
        
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
        
        # Update status
        if rows:
            self.status_indicator.set_status("active", f"Showing {len(fids):,} of {total_count:,}")
            self.filter_badge.set_text(f"{len(fids):,} filtered")
            self.filter_badge.set_variant("success")
            
            # Update dependent panels
            self.summary_panel.update_summary(rows)
            self.results_panel.update_results(rows)
            
            # Switch to summary tab
            self.analyze_tabs.setCurrentWidget(self.summary_panel)
        else:
            self._set_idle_state()
    
    def _on_filter_status_changed(self, status: str, message: str) -> None:
        """Handle filter status updates."""
        self.status_indicator.set_status(status, message)
    
    def _on_chart_clicked(self, concept_key: str, label: str, additive: bool) -> None:
        """Handle chart click - apply filter."""
        # Handle env_combo specially
        if concept_key == "env_combo":
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
            self.analyze_tabs.setCurrentWidget(self.filter_panel)
    
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
        # Guard against recursion from callbacks
        if getattr(self, '_setting_idle', False):
            return
        self._setting_idle = True
        
        try:
            self.filtered_fids = []
            self.filtered_rows = []
            self.filter_badge.set_text("No filters")
            self.filter_badge.set_variant("default")
            self.filter_panel.reset_all_filters()
            self.summary_panel._set_idle_state()
            self.results_panel.set_idle_state()
        finally:
            self._setting_idle = False
    
    def _show_about(self) -> None:
        """Show about panel."""
        self.nav_control.set_selected(1)  # Switch to configure
        self.config_tabs.setCurrentWidget(self.about_panel)
    
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
