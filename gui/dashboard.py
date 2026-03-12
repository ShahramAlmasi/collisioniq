"""Split Dashboard layout for Collision Analytics plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import charts as charts_mod

if TYPE_CHECKING:
    from .dock import CollisionAnalyticsDockWidget


class KPICard(QFrame):
    """KPI metric card with value and label."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setStyleSheet("""
            QFrame#kpiCard {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
        """)

        self._value_label = QLabel("n/a")
        self._value_label.setStyleSheet("""
            font-size: 24px;
            font-weight: 600;
            color: #212529;
        """)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("""
            font-size: 11px;
            color: #6c757d;
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(self._value_label)
        layout.addWidget(self._title_label)
        self.setLayout(layout)

    def set_value(self, value: str, color: Optional[str] = None) -> None:
        """Set the KPI value with optional color."""
        self._value_label.setText(value)
        if color:
            self._value_label.setStyleSheet(f"""
                font-size: 24px;
                font-weight: 600;
                color: {color};
            """)


class ChartCard(QWidget):
    """Card container for a single chart."""

    def __init__(
        self,
        title: str,
        figure: Any,
        canvas: Any,
        render_fn: Callable,
        concept_key: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.title = title
        self.figure = figure
        self.canvas = canvas
        self.render_fn = render_fn
        self.concept_key = concept_key

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the chart card UI."""
        self.setStyleSheet("""
            background-color: white;
            border: 1px solid #dee2e6;
            border-radius: 6px;
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 600;
            color: #495057;
        """)
        layout.addWidget(title_label)

        # Chart canvas
        if self.canvas:
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(self.canvas, 1)

        self.setLayout(layout)


class FilterPanel(QWidget):
    """Collapsible filter panel for the left sidebar."""

    def __init__(
        self, dock: CollisionAnalyticsDockWidget, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.dock = dock
        self._is_expanded = True
        self._content_widget: Optional[QWidget] = None
        self._content_layout: Optional[QVBoxLayout] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the filter panel UI."""
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with collapse button
        header = QWidget()
        header.setStyleSheet("""
            background-color: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        """)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("FILTERS")
        title.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #495057;
            letter-spacing: 0.5px;
        """)

        self._collapse_btn = QPushButton("<")
        self._collapse_btn.setFixedSize(24, 24)
        self._collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #6c757d;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #212529;
            }
        """)
        self._collapse_btn.setToolTip("Collapse filter panel")
        self._collapse_btn.clicked.connect(self._toggle_collapse)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._collapse_btn)
        header.setLayout(header_layout)

        # Content container
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(12)
        self._content_widget.setLayout(self._content_layout)

        # Scroll area for filter content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self._content_widget)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")

        layout.addWidget(header)
        layout.addWidget(scroll, 1)
        self.setLayout(layout)

        # Add subtle shadow effect via stylesheet
        self.setStyleSheet("""
            FilterPanel {
                background-color: white;
                border-right: 1px solid #dee2e6;
            }
        """)

    def content_layout(self) -> QVBoxLayout:
        """Get the content layout to add filter controls."""
        return self._content_layout

    def _toggle_collapse(self) -> None:
        """Toggle panel collapse state."""
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self.setMaximumWidth(400)
            self._content_widget.setVisible(True)
            self._collapse_btn.setText("<")
            self._collapse_btn.setToolTip("Collapse filter panel")
        else:
            self.setMaximumWidth(40)
            self._content_widget.setVisible(False)
            self._collapse_btn.setText(">")
            self._collapse_btn.setToolTip("Expand filter panel")

    def is_expanded(self) -> bool:
        """Check if panel is expanded."""
        return self._is_expanded


class DashboardWidget(QWidget):
    """Main dashboard widget with split layout."""

    def __init__(
        self, dock: CollisionAnalyticsDockWidget, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.dock = dock
        self.kpi_cards: Dict[str, KPICard] = {}
        self.chart_cards: List[ChartCard] = []
        self.chart_grid: Optional[QGridLayout] = None
        self.filter_panel: Optional[FilterPanel] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the main dashboard UI."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left: Filter panel
        self.filter_panel = FilterPanel(self.dock)

        # Right: Dashboard content
        dashboard = self._build_dashboard_content()

        splitter.addWidget(self.filter_panel)
        splitter.addWidget(dashboard)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #dee2e6;
            }
        """)

        layout.addWidget(splitter)
        self.setLayout(layout)

    def _build_dashboard_content(self) -> QWidget:
        """Build the right-side dashboard content."""
        container = QWidget()
        container.setStyleSheet("background-color: #f8f9fa;")

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # KPI row
        kpi_row = self._build_kpi_row()
        layout.addLayout(kpi_row)

        # Chart grid
        chart_container = self._build_chart_grid()
        layout.addWidget(chart_container, 1)

        # Bottom actions bar
        actions_bar = self._build_actions_bar()
        layout.addWidget(actions_bar)

        container.setLayout(layout)
        return container

    def _build_kpi_row(self) -> QHBoxLayout:
        """Build the KPI cards row."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Create KPI cards
        kpi_specs = [
            ("total", "Filtered collisions", "#0d6efd"),
            ("fatal", "Fatal collisions", "#dc3545"),
            ("severe", "Severe share (Fatal + Injury)", "#fd7e14"),
        ]

        for key, title, color in kpi_specs:
            card = KPICard(title)
            self.kpi_cards[key] = card
            layout.addWidget(card)

        layout.addStretch(1)
        return layout

    def _build_chart_grid(self) -> QWidget:
        """Build the responsive chart grid."""
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        # Scroll area for charts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        # Grid container
        grid_widget = QWidget()
        self.chart_grid = QGridLayout()
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(12)

        grid_widget.setLayout(self.chart_grid)
        scroll.setWidget(grid_widget)

        # Main container layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        container.setLayout(layout)

        return container

    def _build_actions_bar(self) -> QWidget:
        """Build the bottom actions bar."""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        # Export buttons
        btn_csv = QPushButton("Export CSV")
        btn_csv.setStyleSheet(self._button_style())
        btn_csv.clicked.connect(self.dock.export_summary_csv)

        btn_features = QPushButton("Export Features")
        btn_features.setStyleSheet(self._button_style())
        btn_features.clicked.connect(self.dock.export_filtered_features_csv)

        btn_png = QPushButton("Export PNG")
        btn_png.setStyleSheet(self._button_style())
        btn_png.clicked.connect(self.dock.export_dashboard_png)

        layout.addWidget(btn_csv)
        layout.addWidget(btn_features)
        layout.addWidget(btn_png)

        bar.setLayout(layout)
        return bar

    def _button_style(self) -> str:
        """Get consistent button styling."""
        return """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """

    def add_chart_card(self, card: ChartCard) -> None:
        """Add a chart card to the grid."""
        self.chart_cards.append(card)
        self._refresh_chart_grid()

    def clear_chart_cards(self) -> None:
        """Remove all chart cards."""
        for card in self.chart_cards:
            card.setParent(None)
            card.deleteLater()
        self.chart_cards.clear()

    def _refresh_chart_grid(self) -> None:
        """Refresh the chart grid layout."""
        if self.chart_grid is None:
            return

        # Clear existing
        while self.chart_grid.count():
            item = self.chart_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Arrange in 1-column grid (one chart per row)
        cols = 1
        for idx, card in enumerate(self.chart_cards):
            row = idx // cols
            col = idx % cols
            card.setMinimumHeight(400)
            self.chart_grid.addWidget(card, row, col)

        # Add stretch to bottom
        self.chart_grid.setRowStretch(self.chart_grid.rowCount(), 1)

    def update_kpi(self, key: str, value: str, color: Optional[str] = None) -> None:
        """Update a KPI card value."""
        if key in self.kpi_cards:
            self.kpi_cards[key].set_value(value, color)

    def set_status(self, text: str) -> None:
        """Update the status label."""
        if hasattr(self, "status_label"):
            self.status_label.setText(text)

    def get_filter_panel(self) -> FilterPanel:
        """Get the filter panel for adding controls."""
        return self.filter_panel
