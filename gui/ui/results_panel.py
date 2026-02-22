"""Results Panel - Charts and summary statistics with virtual scrolling."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core import charts as charts_mod
from ..core.decodes import DecodeRegistry
from ..core.utils import safe_str, to_datetime


@dataclass
class VirtualChartCard:
    """A chart card that can be rendered on-demand for virtual scrolling."""
    title: str
    render_fn: Callable
    concept_key: Optional[str] = None
    widget: Optional[QWidget] = None
    canvas: Optional[Any] = None
    figure: Optional[Any] = None
    is_rendered: bool = False


class VirtualChartScrollArea(QScrollArea):
    """Scroll area that renders charts on-demand as they become visible."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.chart_cards: List[VirtualChartCard] = []
        self.render_margin = 200  # Pixels below viewport to trigger render
        
        # Container widget
        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(10)
        self.container.setLayout(self.layout)
        self.setWidget(self.container)
        
        # Connect scroll event
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def clear_charts(self) -> None:
        """Clear all chart cards."""
        self.chart_cards = []
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
    
    def add_chart_section(self, title: str, charts: List[Tuple[str, Callable, Optional[str]]]) -> None:
        """Add a section of charts."""
        sec = QGroupBox(title)
        sec_l = QVBoxLayout()
        sec.setLayout(sec_l)
        
        for chart_title, render_fn, concept_key in charts:
            card = self._create_chart_card(chart_title, render_fn, concept_key)
            sec_l.addWidget(card.widget)
            self.chart_cards.append(card)
        
        self.layout.addWidget(sec)
    
    def _create_chart_card(self, title: str, render_fn: Callable, concept_key: Optional[str]) -> VirtualChartCard:
        """Create a chart card widget (initially empty)."""
        box = QGroupBox(title)
        box_l = QVBoxLayout()
        box.setLayout(box_l)
        
        # Placeholder label
        placeholder = QLabel("Scroll into view to render...")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #999; padding: 40px;")
        box_l.addWidget(placeholder)
        
        return VirtualChartCard(
            title=title,
            render_fn=render_fn,
            concept_key=concept_key,
            widget=box,
        )
    
    def _on_scroll(self) -> None:
        """Handle scroll events to trigger lazy rendering."""
        QTimer.singleShot(50, self._render_visible_charts)
    
    def _render_visible_charts(self) -> None:
        """Render charts that are visible or near viewport."""
        viewport_rect = self.viewport().rect()
        scroll_y = self.verticalScrollBar().value()
        
        for card in self.chart_cards:
            if card.is_rendered:
                continue
            
            widget_rect = card.widget.geometry()
            widget_top = widget_rect.y() - scroll_y
            widget_bottom = widget_top + widget_rect.height()
            
            # Check if widget is visible or within render margin
            if widget_bottom >= -self.render_margin and widget_top <= viewport_rect.height() + self.render_margin:
                self._render_chart(card)
    
    def _render_chart(self, card: VirtualChartCard) -> None:
        """Render a specific chart card."""
        if charts_mod.FigureCanvas is None:
            return
        
        # Clear placeholder
        box_l = card.widget.layout()
        while box_l.count():
            item = box_l.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        
        # Create figure and canvas
        fig = charts_mod.Figure(figsize=(9.0, 3.2))
        canvas = charts_mod.FigureCanvas(fig)
        canvas.setMinimumHeight(320)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        card.figure = fig
        card.canvas = canvas
        card.is_rendered = True
        
        box_l.addWidget(canvas)
    
    def render_all(self, rows: List[Dict[str, Any]], field_map: Dict[str, str],
                   decodes: DecodeRegistry, top_n: int, show_labels: bool) -> None:
        """Render all charts with data."""
        for card in self.chart_cards:
            if not card.is_rendered or card.figure is None:
                continue
            
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            
            try:
                # Allow renderers to receive the canvas for click wiring
                card.render_fn(ax, rows=rows, field_map=field_map, decodes=decodes,
                              top_n=top_n, show_labels=show_labels, canvas=card.canvas)
            except TypeError:
                try:
                    card.render_fn(ax, rows=rows, field_map=field_map, decodes=decodes,
                                  top_n=top_n, show_labels=show_labels)
                except TypeError:
                    card.render_fn(ax)
            except Exception as e:
                ax.text(0.5, 0.5, f"Chart error:\n{e}", ha="center", va="center",
                       transform=ax.transAxes)
                ax.set_axis_off()
            
            card.figure.tight_layout()
            if card.canvas:
                card.canvas.draw()
    
    def install_click_handlers(self, handler: Callable[[str, str, bool], None]) -> None:
        """Install click handlers for charts that support filtering."""
        for card in self.chart_cards:
            if card.canvas and card.concept_key:
                self._install_chart_click(card.canvas, card.concept_key, handler)
    
    def _install_chart_click(self, canvas, concept_key: str, 
                             handler: Callable[[str, str, bool], None]) -> None:
        """Wire up click-to-filter for horizontal bar charts."""
        if charts_mod.FigureCanvas is None or canvas is None:
            return
        
        fig = canvas.figure
        if not fig or not fig.axes:
            return
        
        ax = fig.axes[0]
        labels = [t.get_text() for t in ax.get_yticklabels()]
        if not labels:
            return
        
        ticks = list(ax.get_yticks())[:len(labels)]
        if not ticks:
            ticks = list(range(len(labels)))
        
        # Build targets from patches
        targets = []
        for patch in ax.patches:
            try:
                center = patch.get_y() + (patch.get_height() / 2.0)
            except Exception:
                continue
            if not ticks:
                continue
            idx = min(range(len(ticks)), key=lambda i: abs(ticks[i] - center))
            if idx >= len(labels):
                continue
            targets.append((patch, labels[idx]))
        
        if not targets:
            return
        
        def on_click(event, ax=ax, concept_key=concept_key, targets=targets):
            if event.name != "button_press_event" or event.inaxes != ax:
                return
            if event.x is None or event.y is None:
                return
            if getattr(event, "button", None) != 1:
                return
            
            label = None
            for patch, lab in targets:
                try:
                    if patch.contains_point((event.x, event.y)):
                        label = lab
                        break
                except Exception:
                    continue
            
            if label is None:
                return
            
            # Check for control modifier
            additive = False
            ge = getattr(event, "guiEvent", None)
            try:
                if ge is not None:
                    additive = bool(ge.modifiers() & Qt.ControlModifier)
            except Exception:
                additive = False
            
            handler(concept_key, label, additive)
        
        # Disconnect any existing handler
        cid = getattr(canvas, "_collision_click_cid", None)
        if cid is not None:
            try:
                canvas.mpl_disconnect(cid)
            except Exception:
                pass
        
        try:
            canvas._collision_click_cid = canvas.mpl_connect("button_press_event", on_click)
        except Exception:
            pass
    
    def export_to_png(self, path: str, top_n: int, show_labels: bool,
                      rows: List[Dict[str, Any]], field_map: Dict[str, str],
                      decodes: DecodeRegistry) -> None:
        """Export all charts to a PNG file."""
        if charts_mod.Figure is None:
            raise RuntimeError("matplotlib is not available")
        
        # Ensure all charts are rendered
        for card in self.chart_cards:
            if not card.is_rendered:
                self._render_chart(card)
        
        # Now render with data
        self.render_all(rows, field_map, decodes, top_n, show_labels)
        
        cols = 2
        cards = [c for c in self.chart_cards if c.is_rendered]
        rows_needed = (len(cards) + cols - 1) // cols
        
        fig = charts_mod.Figure(figsize=(cols * 7.5, rows_needed * 3.2))
        
        for idx, card in enumerate(cards):
            ax = fig.add_subplot(rows_needed, cols, idx + 1)
            ax.set_title(card.title, fontsize=10)
            try:
                card.render_fn(ax, rows=rows, field_map=field_map, decodes=decodes,
                              top_n=top_n, show_labels=show_labels)
            except Exception as e:
                ax.text(0.5, 0.5, f"Chart error:\n{e}", ha="center", va="center",
                       transform=ax.transAxes)
                ax.set_axis_off()
        
        fig.tight_layout()
        fig.savefig(path, dpi=200)


class ResultsPanel(QWidget):
    """Panel containing charts and summary statistics."""
    
    chart_clicked = None  # Callback: (concept_key, label, additive) -> None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.field_map: Dict[str, str] = {}
        self.decodes: Optional[DecodeRegistry] = None
        self.filtered_rows: List[Dict[str, Any]] = []
        
        self.top_n_default = 12
        self.chart_height_default = 320
        
        self._build_ui()
        self._init_charts()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        
        self.btn_export_csv = QPushButton("Export summary CSV")
        self.btn_export_csv.clicked.connect(self.export_summary_csv)
        
        self.btn_export_features_csv = QPushButton("Export features CSV")
        self.btn_export_features_csv.clicked.connect(self.export_filtered_features_csv)
        
        self.btn_export_dashboard_png = QPushButton("Export dashboard PNG")
        self.btn_export_dashboard_png.clicked.connect(self.export_dashboard_png)
        
        ctrl_layout.addWidget(self.btn_export_csv)
        ctrl_layout.addWidget(self.btn_export_features_csv)
        ctrl_layout.addWidget(self.btn_export_dashboard_png)
        
        ctrl_layout.addSpacing(20)
        
        ctrl_layout.addWidget(QLabel("Top N:"))
        self.cbo_top_n = QComboBox()
        self.cbo_top_n.addItems(["8", "12", "15", "20"])
        self.cbo_top_n.setCurrentText(str(self.top_n_default))
        self.cbo_top_n.currentIndexChanged.connect(self.update_view)
        
        self.chk_value_labels = QCheckBox("Show value labels")
        self.chk_value_labels.setChecked(True)
        self.chk_value_labels.stateChanged.connect(self.update_view)
        
        ctrl_layout.addWidget(self.cbo_top_n)
        ctrl_layout.addWidget(self.chk_value_labels)
        ctrl_layout.addStretch(1)
        
        layout.addLayout(ctrl_layout)
        
        # Chart scroll area
        if charts_mod.FigureCanvas is not None:
            self.chart_scroll = VirtualChartScrollArea()
            layout.addWidget(self.chart_scroll, 1)
        else:
            msg = QLabel("matplotlib is not available. Charts are disabled.")
            msg.setWordWrap(True)
            layout.addWidget(msg)
            self.chart_scroll = None
        
        self.setLayout(layout)
    
    def _init_charts(self) -> None:
        """Initialize chart definitions."""
        if self.chart_scroll is None:
            return
        
        self.chart_scroll.clear_charts()
        
        # Chart definitions with their render functions and concept keys
        sections = [
            ("Temporal (by accident class)", [
                ("Collisions by year", self._render_year_by_class, "year"),
                ("Collisions by month", self._render_month_by_class, "month"),
                ("Collisions by day of week", self._render_dow_by_class, "dow"),
                ("Collisions by hour of day", self._render_hour_by_class, "hour"),
            ]),
            ("Core breakdowns", [
                ("Accident class (severity)", self._render_accident_class, "accident_class"),
                ("Impact type by accident class", self._render_impact_by_class, "impact_type"),
                ("Environment condition 1", self._render_env1, "env1"),
                ("Environment condition 2", self._render_env2, "env2"),
                ("Environment combos", self._render_env_combo, "env_combo"),
                ("Lighting", self._render_light, "light"),
            ]),
            ("Prioritization", [
                ("Pareto: Impact type concentration", self._render_pareto_impact, None),
            ]),
            ("Other breakdowns", [
                ("Location type", self._render_location_type, "location_type"),
                ("Municipality", self._render_municipality, "municipality"),
                ("Accident location context", self._render_accident_location, "accident_location"),
                ("Impact location", self._render_impact_location, "impact_location"),
                ("Traffic control", self._render_traffic_control, "traffic_control"),
                ("Traffic control condition", self._render_traffic_control_condition, "traffic_control_condition"),
                ("Road jurisdiction", self._render_road_jurisdiction, "road_jurisdiction"),
            ]),
        ]
        
        for section_title, charts in sections:
            self.chart_scroll.add_chart_section(section_title, charts)
    
    def set_data(self, field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        """Set field map and decodes registry."""
        self.field_map = field_map
        self.decodes = decodes
    
    def update_results(self, rows: List[Dict[str, Any]]) -> None:
        """Update results with new filtered rows."""
        self.filtered_rows = rows
        self.update_view()
    
    def update_view(self) -> None:
        """Update the view with current data."""
        if self.chart_scroll is None or not self.decodes:
            return
        
        top_n = int(self.cbo_top_n.currentText())
        show_labels = self.chk_value_labels.isChecked()
        
        self.chart_scroll.render_all(self.filtered_rows, self.field_map, 
                                     self.decodes, top_n, show_labels)
        
        # Install click handlers
        if self.chart_clicked:
            self.chart_scroll.install_click_handlers(self.chart_clicked)
    
    # Chart render functions
    def _render_year_by_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_temporal_by_class(
            ax, rows, field_map.get("date"), field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            decodes.mapping("accident_class"),
            bucket="year", show_labels=show_labels,
        )
    
    def _render_month_by_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_temporal_by_class(
            ax, rows, field_map.get("date"), field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            decodes.mapping("accident_class"),
            bucket="month", show_labels=show_labels,
        )
    
    def _render_dow_by_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_temporal_by_class(
            ax, rows, field_map.get("date"), field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            decodes.mapping("accident_class"),
            bucket="dow", show_labels=show_labels,
        )
    
    def _render_hour_by_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_temporal_by_class(
            ax, rows, field_map.get("date"), field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            decodes.mapping("accident_class"),
            bucket="hour", show_labels=show_labels,
        )
    
    def _render_accident_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_impact_by_class(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category_by_class(
            ax, rows, field_map.get("impact_type"),
            lambda raw: decodes.decode("impact_type", raw),
            field_map.get("accident_class"),
            lambda raw: decodes.decode("accident_class", raw),
            decodes.mapping("accident_class"),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_env1(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("env1"),
            lambda raw: decodes.decode("env1", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_env2(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("env2"),
            lambda raw: decodes.decode("env2", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_env_combo(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_env_combo(
            ax, rows, field_map.get("env1"), field_map.get("env2"),
            lambda raw: decodes.decode("env1", raw),
            lambda raw: decodes.decode("env2", raw),
            top_n=top_n, show_labels=show_labels,
        )
    
    def _render_light(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("light"),
            lambda raw: decodes.decode("light", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_pareto_impact(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_pareto(
            ax, rows, field_map.get("impact_type"),
            lambda raw: decodes.decode("impact_type", raw),
            top_n=top_n, show_labels=show_labels,
        )
    
    def _render_location_type(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("location_type"),
            lambda raw: decodes.decode("location_type", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_municipality(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("municipality"),
            lambda raw: decodes.decode("municipality", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_accident_location(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("accident_location"),
            lambda raw: decodes.decode("accident_location", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_impact_location(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("impact_location"),
            lambda raw: decodes.decode("impact_location", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_traffic_control(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("traffic_control"),
            lambda raw: decodes.decode("traffic_control", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_traffic_control_condition(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("traffic_control_condition"),
            lambda raw: decodes.decode("traffic_control_condition", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def _render_road_jurisdiction(self, ax, rows, field_map, decodes, top_n, show_labels, **kwargs):
        charts_mod.render_category(
            ax, rows, field_map.get("road_jurisdiction"),
            lambda raw: decodes.decode("road_jurisdiction", raw),
            top_n=top_n, show_labels=show_labels, include_blank=True,
        )
    
    def export_summary_csv(self) -> None:
        """Export summary statistics to CSV."""
        if not self.filtered_rows:
            QMessageBox.information(self, "Collision Analytics", "No filtered results to export.")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Export summary CSV", "", "CSV (*.csv)")
        if not path:
            return
        
        total = len(self.filtered_rows)
        fm = self.field_map
        
        def sum_field(concept: str) -> float:
            field = fm.get(concept)
            if not field:
                return 0.0
            s = 0.0
            for r in self.filtered_rows:
                try:
                    s += float(r.get(field) or 0)
                except Exception:
                    pass
            return s
        
        import csv
        rows = [
            ("filtered_collisions", total),
            ("sum_involved_vehicles_cnt", sum_field("veh_cnt")),
            ("sum_involved_persons_cnt", sum_field("per_cnt")),
            ("sum_involved_drivers_cnt", sum_field("drv_cnt")),
            ("sum_involved_occupants_cnt", sum_field("occ_cnt")),
            ("sum_involved_pedestrians_cnt", sum_field("ped_cnt")),
        ]
        
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerows(rows)
        
        QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")
    
    def export_filtered_features_csv(self) -> None:
        """Export filtered features to CSV with decoded values."""
        if not self.filtered_rows:
            QMessageBox.information(self, "Collision Analytics", "No filtered results to export.")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Export features CSV", "", "CSV (*.csv)")
        if not path:
            return
        
        # Collect all fields
        all_fields = set()
        for row in self.filtered_rows:
            all_fields.update(row.keys())
        all_fields = sorted(all_fields)
        
        # Map fields to concepts
        field_to_concept: Dict[str, str] = {}
        for concept_key, field_name in self.field_map.items():
            if field_name in all_fields:
                field_to_concept[field_name] = concept_key
        
        # Build headers with decoded columns
        headers = []
        concepts_with_decodes = set(self.decodes.keys()) if self.decodes else set()
        
        for field in all_fields:
            headers.append(field)
            concept_key = field_to_concept.get(field)
            if concept_key and concept_key in concepts_with_decodes:
                headers.append(f"{field}_decoded")
        
        # Build rows
        import csv
        from datetime import date, datetime
        
        csv_rows = []
        for row in self.filtered_rows:
            csv_row = []
            for field in all_fields:
                raw_value = row.get(field)
                # Format value
                if raw_value is None:
                    formatted = ""
                elif isinstance(raw_value, (date, datetime)):
                    formatted = raw_value.isoformat()
                elif hasattr(raw_value, "toPyDateTime"):
                    try:
                        formatted = raw_value.toPyDateTime().isoformat()
                    except Exception:
                        formatted = safe_str(raw_value)
                else:
                    formatted = safe_str(raw_value)
                
                csv_row.append(formatted)
                
                # Add decoded value
                concept_key = field_to_concept.get(field)
                if concept_key and self.decodes and concept_key in concepts_with_decodes:
                    decoded = self.decodes.decode(concept_key, raw_value)
                    csv_row.append(decoded)
            
            csv_rows.append(csv_row)
        
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(csv_rows)
        
        QMessageBox.information(self, "Collision Analytics", 
                               f"Exported {len(csv_rows)} features to:\n{path}")
    
    def export_dashboard_png(self) -> None:
        """Export dashboard to PNG."""
        if self.chart_scroll is None:
            QMessageBox.warning(self, "Collision Analytics", "Charts are not available.")
            return
        
        if not self.filtered_rows:
            QMessageBox.information(self, "Collision Analytics", "No data to export.")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Export dashboard PNG", "", "PNG (*.png)")
        if not path:
            return
        
        try:
            top_n = int(self.cbo_top_n.currentText())
            show_labels = self.chk_value_labels.isChecked()
            
            self.chart_scroll.export_to_png(
                path, top_n, show_labels,
                self.filtered_rows, self.field_map, self.decodes
            )
            QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Export failed:\n{e}")
    
    def set_idle_state(self) -> None:
        """Set charts to idle state."""
        if self.chart_scroll is None:
            return
        
        for card in self.chart_scroll.chart_cards:
            if card.figure:
                card.figure.clear()
                ax = card.figure.add_subplot(111)
                ax.text(
                    0.5, 0.5,
                    "Select collisions on the map\n(or disable selection scope),\nthen click Apply.",
                    ha="center", va="center", transform=ax.transAxes,
                )
                ax.set_axis_off()
                card.figure.tight_layout()
                if card.canvas:
                    card.canvas.draw()
