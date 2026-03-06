"""Charts tab for Collision Analytics plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QCheckBox,
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

from ...core import charts as charts_mod
from .base_tab import BaseTab

if TYPE_CHECKING:
    from ..dock import CollisionAnalyticsDockWidget


class ChartCard:
    """Container for a single chart."""

    def __init__(
        self,
        title: str,
        figure: Any,
        canvas: Any,
        render_fn: Callable,
        concept_key: Optional[str] = None,
    ):
        self.title = title
        self.figure = figure
        self.canvas = canvas
        self.render_fn = render_fn
        self.concept_key = concept_key


class ChartsTab(BaseTab):
    """Tab for displaying collision analytics charts."""

    def __init__(self, dock: CollisionAnalyticsDockWidget) -> None:
        super().__init__(dock)
        self.chart_cards: List[ChartCard] = []
        self.cbo_top_n: QComboBox | None = None
        self.chk_value_labels: QCheckBox | None = None
        self.dashboard_vbox: QVBoxLayout | None = None
        self._click_cids: Dict[Any, int] = {}

    def build(self) -> QWidget:
        """Build the charts tab UI."""
        root = QWidget()
        layout = QVBoxLayout()

        # Top control bar
        top = self._build_top_bar()
        layout.addLayout(top)

        # Chart controls
        ctl = self._build_chart_controls()
        layout.addLayout(ctl)

        # Charts container
        if charts_mod.FigureCanvas is None:
            msg = QLabel(
                "matplotlib is not available in this QGIS Python environment.\nCharts are disabled."
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
        else:
            scroll = self._build_charts_scroll_area()
            layout.addWidget(scroll, 1)
            self._init_dashboard_charts()

        root.setLayout(layout)
        self.tab_widget = root
        return root

    def _build_top_bar(self) -> QHBoxLayout:
        """Build the top button bar."""
        top = QHBoxLayout()

        btn_apply = QPushButton("Apply filters / update selection")
        btn_apply.clicked.connect(self.dock.reset_all_filters)

        btn_export_csv = QPushButton("Export summary CSV")
        btn_export_csv.clicked.connect(self.dock.export_summary_csv)

        btn_export_features = QPushButton("Export filtered features CSV")
        btn_export_features.clicked.connect(self.dock.export_filtered_features_csv)

        btn_export_png = QPushButton("Export dashboard PNG")
        btn_export_png.clicked.connect(self.export_dashboard_png)

        top.addWidget(btn_apply)
        top.addSpacing(12)
        top.addWidget(btn_export_csv)
        top.addWidget(btn_export_features)
        top.addWidget(btn_export_png)
        top.addStretch(1)

        return top

    def _build_chart_controls(self) -> QHBoxLayout:
        """Build chart control options."""
        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Top N:"))

        self.cbo_top_n = QComboBox()
        self.cbo_top_n.addItems(["8", "12", "15", "20"])
        self.cbo_top_n.setCurrentText(str(self.dock.top_n_default))
        self.cbo_top_n.currentIndexChanged.connect(self.refresh)

        self.chk_value_labels = QCheckBox("Show value labels")
        self.chk_value_labels.setChecked(True)
        self.chk_value_labels.stateChanged.connect(self.refresh)

        ctl.addWidget(self.cbo_top_n)
        ctl.addSpacing(10)
        ctl.addWidget(self.chk_value_labels)
        ctl.addStretch(1)

        return ctl

    def _build_charts_scroll_area(self) -> QScrollArea:
        """Build the scrollable charts area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        dashboard_root = QWidget()
        self.dashboard_vbox = QVBoxLayout()
        self.dashboard_vbox.setContentsMargins(8, 8, 8, 8)
        self.dashboard_vbox.setSpacing(10)
        dashboard_root.setLayout(self.dashboard_vbox)
        scroll.setWidget(dashboard_root)

        return scroll

    def _init_dashboard_charts(self) -> None:
        """Initialize all chart cards."""
        # Clear existing
        while self.dashboard_vbox.count():
            item = self.dashboard_vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        self.chart_cards = []

        sections = [
            (
                "Temporal (by accident class)",
                [
                    (
                        "Collisions by year (by accident class)",
                        self._chart_temporal,
                        "year",
                    ),
                    (
                        "Collisions by month (by accident class)",
                        self._chart_temporal,
                        "month",
                    ),
                    (
                        "Collisions by day of week (by accident class)",
                        self._chart_temporal,
                        "dow",
                    ),
                    (
                        "Collisions by hour of day (by accident class)",
                        self._chart_temporal,
                        "hour",
                    ),
                ],
            ),
            (
                "Core breakdowns",
                [
                    (
                        "Accident class (severity)",
                        self._chart_category,
                        "accident_class",
                    ),
                    (
                        "Impact type by accident class",
                        self._chart_impact_by_class,
                        None,
                    ),
                    ("Environment condition 1", self._chart_category, "env1"),
                    ("Environment condition 2", self._chart_category, "env2"),
                    (
                        "Environment combos (Env1 + Env2, non-null/0)",
                        self._chart_env_combo,
                        None,
                    ),
                    ("Lighting", self._chart_category, "light"),
                ],
            ),
            (
                "Prioritization",
                [
                    ("Pareto: Impact type concentration", self._chart_pareto, None),
                ],
            ),
            (
                "Other charts",
                [
                    ("Location type", self._chart_category, "location_type"),
                    ("Municipality", self._chart_category, "municipality"),
                    (
                        "Accident location context",
                        self._chart_category,
                        "accident_location",
                    ),
                    ("Impact location", self._chart_category, "impact_location"),
                    ("Traffic control", self._chart_category, "traffic_control"),
                    (
                        "Traffic control condition",
                        self._chart_category,
                        "traffic_control_condition",
                    ),
                    ("Road jurisdiction", self._chart_category, "road_jurisdiction"),
                ],
            ),
        ]

        for section_title, charts in sections:
            sec = QGroupBox(section_title)
            sec_l = QVBoxLayout()
            sec.setLayout(sec_l)

            for title, render_fn, concept_key in charts:
                box = QGroupBox(title)
                box_l = QVBoxLayout()
                box.setLayout(box_l)

                fig = charts_mod.Figure(figsize=(10.0, 4.5))
                canvas = charts_mod.FigureCanvas(fig)
                canvas.setMinimumHeight(400)
                canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                box_l.addWidget(canvas)

                sec_l.addWidget(box)
                self.chart_cards.append(
                    ChartCard(
                        title=title,
                        figure=fig,
                        canvas=canvas,
                        render_fn=render_fn,
                        concept_key=concept_key,
                    )
                )

            self.dashboard_vbox.addWidget(sec)

        self.dashboard_vbox.addStretch(1)

    def _safe_render_chart(
        self, card: ChartCard, ax: Any, top_n: int, show_labels: bool
    ) -> None:
        """Render a chart with error handling."""
        try:
            card.render_fn(ax, card, top_n=top_n, show_labels=show_labels)
        except ValueError as e:
            self._show_chart_error(ax, f"Data error: {e}")
        except MemoryError:
            self._show_chart_error(ax, "Too many data points. Try a smaller selection.")
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis

            QgsMessageLog.logMessage(
                f"Chart render failed: {e}", "Collision Analytics", Qgis.Warning
            )
            self._show_chart_error(ax, "Unable to render chart")

    def _show_chart_error(self, ax: Any, message: str) -> None:
        """Display an error message in a chart axis."""
        ax.clear()
        ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()

    def refresh(self) -> None:
        """Refresh all charts with current data."""
        if charts_mod.FigureCanvas is None:
            return

        top_n = int(self.cbo_top_n.currentText())
        show_labels = self.chk_value_labels.isChecked()

        for card in self.chart_cards:
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            self._disconnect_chart_click(card.canvas)
            self._safe_render_chart(card, ax, top_n, show_labels)
            card.figure.tight_layout()
            card.canvas.draw()

    def _disconnect_chart_click(self, canvas: Any) -> None:
        """Disconnect any existing click handler."""
        cid = self._click_cids.get(canvas)
        if cid is None:
            return
        try:
            canvas.mpl_disconnect(cid)
        except Exception:
            pass
        del self._click_cids[canvas]

    def _install_chart_click(self, ax: Any, canvas: Any, concept_key: str) -> None:
        """Wire up click-to-filter for horizontal bar charts."""
        if charts_mod.FigureCanvas is None or canvas is None or ax is None:
            return

        labels = [t.get_text() for t in ax.get_yticklabels()]
        if not labels:
            self._disconnect_chart_click(canvas)
            return

        ticks = list(ax.get_yticks())[: len(labels)]
        if not ticks:
            ticks = list(range(len(labels)))

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
            self._disconnect_chart_click(canvas)
            return

        def handler(event, ax=ax, concept_key=concept_key, targets=targets):
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

            additive = False
            ge = getattr(event, "guiEvent", None)
            try:
                if ge is not None:
                    additive = bool(ge.modifiers() & Qt.ControlModifier)
            except Exception:
                additive = False

            self.dock.filter_by_category(concept_key, label, additive)

        self._disconnect_chart_click(canvas)
        try:
            self._click_cids[canvas] = canvas.mpl_connect("button_press_event", handler)
        except Exception:
            pass

    def _chart_temporal(
        self, ax: Any, card: ChartCard, top_n: int = 12, show_labels: bool = True
    ) -> None:
        """Render temporal chart (year/month/dow/hour)."""
        bucket = card.concept_key  # year, month, dow, hour
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket=bucket,
            show_labels=show_labels,
        )
        self._install_chart_click(ax, card.canvas, "accident_class")

    def _chart_category(
        self, ax: Any, card: ChartCard, top_n: int = 12, show_labels: bool = True
    ) -> None:
        """Render category chart."""
        concept_key = card.concept_key
        field = self.field_map.get(concept_key)
        decode = lambda raw: self._decode(concept_key, raw)
        charts_mod.render_category(
            ax,
            self.filtered_rows,
            field,
            decode,
            top_n=top_n,
            show_labels=show_labels,
            include_blank=True,
        )
        self._install_chart_click(ax, card.canvas, concept_key)

    def _chart_impact_by_class(
        self, ax: Any, card: ChartCard, top_n: int = 12, show_labels: bool = True
    ) -> None:
        """Render impact type by accident class chart."""
        charts_mod.render_category_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("impact_type"),
            lambda raw: self._decode("impact_type", raw),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            top_n=top_n,
            show_labels=show_labels,
            include_blank=True,
        )
        self._install_chart_click(ax, card.canvas, "impact_type")

    def _chart_env_combo(
        self, ax: Any, card: ChartCard, top_n: int = 12, show_labels: bool = True
    ) -> None:
        """Render environment combo chart."""
        f1 = self.field_map.get("env1")
        f2 = self.field_map.get("env2")
        d1 = lambda raw: self._decode("env1", raw)
        d2 = lambda raw: self._decode("env2", raw)
        charts_mod.render_env_combo(
            ax, self.filtered_rows, f1, f2, d1, d2, top_n=top_n, show_labels=show_labels
        )
        self._install_chart_click(ax, card.canvas, "env_combo")

    def _chart_pareto(
        self, ax: Any, card: ChartCard, top_n: int = 10, show_labels: bool = True
    ) -> None:
        """Render pareto chart for impact types."""
        field = self.field_map.get("impact_type")
        decode = lambda raw: self._decode("impact_type", raw)
        charts_mod.render_pareto(
            ax, self.filtered_rows, field, decode, top_n=top_n, show_labels=show_labels
        )

    def set_idle_state(self) -> None:
        """Set charts to idle state."""
        if charts_mod.FigureCanvas is None:
            return

        for card in self.chart_cards:
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "Select collisions on the map (or disable selection scope),\nthen click Apply.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            card.figure.tight_layout()
            card.canvas.draw()

    def export_dashboard_png(self) -> None:
        """Export all charts as a dashboard PNG."""
        self.dock.export_dashboard_png()

    def reset(self) -> None:
        """Reset chart settings to defaults."""
        if self.cbo_top_n:
            self.cbo_top_n.setCurrentText(str(self.dock.top_n_default))
        if self.chk_value_labels:
            self.chk_value_labels.setChecked(True)
