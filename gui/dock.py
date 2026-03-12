"""Main dock widget for Collision Analytics plugin."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from qgis.PyQt.QtCore import QDate, QSettings, QTimer, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QDockWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from ..controllers import DockController
from ..core import charts as charts_mod
from ..core.config import FILTER_CONCEPTS
from ..core.decodes import DecodeRegistry
from ..services import DashboardSnapshot, FilterOptions, FilterPanelState, default_last_full_10y_range
from .dashboard import ChartCard, DashboardWidget
from .tabs import AboutTab, DecodesTab, FieldsTab
from .widgets import CheckListFilterBox


class CollisionAnalyticsDockWidget(QDockWidget):
    """Main dock widget with split dashboard layout."""

    def __init__(self, iface):
        super().__init__("Collision Analytics", iface.mainWindow())
        self.iface = iface
        self.settings = QSettings()
        self.decodes = DecodeRegistry(self.settings)
        self.controller = DockController(self, iface, self.settings, self.decodes)

        self.setObjectName("CollisionAnalyticsDockWidget")
        self.root = QWidget()
        self.setWidget(self.root)

        self.top_n_default = 12
        self.chart_height_default = 320

        self.layer_combo: Optional[QgsMapLayerComboBox] = None
        self.chk_use_date: Optional[QCheckBox] = None
        self.date_start: Optional[QDateEdit] = None
        self.date_end: Optional[QDateEdit] = None
        self.chk_selection_only: Optional[QCheckBox] = None
        self.chk_select_filtered: Optional[QCheckBox] = None
        self.filter_boxes: Dict[str, CheckListFilterBox] = {}
        self.dashboard: Optional[DashboardWidget] = None
        self.settings_dialog: Optional[QDialog] = None
        self.tabs: Dict[str, Any] = {}

        self._click_cids: Dict[Any, int] = {}
        self._chart_rows: List[Dict[str, Any]] = []
        self._chart_field_map: Dict[str, str] = {}
        self._chart_decodes: Optional[DecodeRegistry] = None

        self._build_ui()
        QTimer.singleShot(0, self.controller.initialize)

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_top_bar())

        self.dashboard = DashboardWidget(self)
        layout.addWidget(self.dashboard, 1)

        self._build_filter_controls()
        self._init_dashboard_charts()

        self.root.setLayout(layout)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            """
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            """
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layer_combo.layerChanged.connect(self.controller.on_layer_changed)

        btn_apply = QPushButton("Apply")
        btn_apply.setStyleSheet(self._action_button_style())
        btn_apply.clicked.connect(self.controller.apply_filters)

        btn_reset = QPushButton("Reset")
        btn_reset.setStyleSheet(self._secondary_button_style())
        btn_reset.clicked.connect(self.controller.reset_all_filters)

        btn_settings = QPushButton("Settings")
        btn_settings.setStyleSheet(self._secondary_button_style())
        btn_settings.clicked.connect(self.controller.show_settings_dialog)

        layout.addWidget(QLabel("Layer:"))
        layout.addWidget(self.layer_combo, 1)
        layout.addWidget(btn_apply)
        layout.addWidget(btn_reset)
        layout.addSpacing(12)
        layout.addWidget(btn_settings)

        bar.setLayout(layout)
        return bar

    def _action_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
            }
        """

    def _secondary_button_style(self) -> str:
        return """
            QPushButton {
                background-color: transparent;
                border: 1px solid #6c757d;
                color: #6c757d;
                border-radius: 4px;
                padding: 4px 16px;
            }
            QPushButton:hover {
                background-color: #6c757d;
                color: white;
            }
        """

    def _build_filter_controls(self) -> None:
        panel = self.dashboard.get_filter_panel()
        layout = panel.content_layout()

        date_section = self._create_section("Date Range")
        self.chk_use_date = QCheckBox("Filter by date range")
        self.chk_use_date.setChecked(True)
        self.chk_use_date.stateChanged.connect(self.controller.on_filter_changed)

        self.date_start = QDateEdit()
        self.date_end = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_end.setCalendarPopup(True)

        default_start, default_end = self._default_qdate_range()
        self.date_start.setDate(default_start)
        self.date_end.setDate(default_end)
        self.date_start.dateChanged.connect(self.controller.on_filter_changed)
        self.date_end.dateChanged.connect(self.controller.on_filter_changed)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self.date_start)
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self.date_end)

        date_section.layout().addWidget(self.chk_use_date)
        date_section.layout().addLayout(date_row)
        layout.addWidget(date_section)

        scope_section = self._create_section("Scope")
        self.chk_selection_only = QCheckBox("Map selection only (recommended)")
        self.chk_selection_only.setChecked(True)
        self.chk_selection_only.stateChanged.connect(self.controller.on_filter_changed)

        self.chk_select_filtered = QCheckBox("Select filtered features on map")
        self.chk_select_filtered.setChecked(False)

        scope_section.layout().addWidget(self.chk_selection_only)
        scope_section.layout().addWidget(self.chk_select_filtered)
        layout.addWidget(scope_section)

        values_section = self._create_section("Filter Values")
        btn_decodes = QPushButton("Load from decode tables")
        btn_decodes.clicked.connect(lambda: self.controller.populate_filter_values("decodes"))
        btn_decodes.setStyleSheet(self._secondary_button_style())

        btn_selection = QPushButton("Load from map selection")
        btn_selection.clicked.connect(lambda: self.controller.populate_filter_values("selection"))
        btn_selection.setStyleSheet(self._secondary_button_style())

        btn_layer = QPushButton("Load from entire layer")
        btn_layer.clicked.connect(lambda: self.controller.populate_filter_values("layer"))
        btn_layer.setStyleSheet(self._secondary_button_style())
        btn_layer.setToolTip("May be slow for large layers")

        values_section.layout().addWidget(btn_decodes)
        values_section.layout().addWidget(btn_selection)
        values_section.layout().addWidget(btn_layer)
        layout.addWidget(values_section)

        filters_section = self._create_section("Category Filters")
        self.filter_boxes = {}
        for concept_key, title in FILTER_CONCEPTS:
            box = CheckListFilterBox(title)
            box.list.itemChanged.connect(self.controller.on_filter_changed)
            self.filter_boxes[concept_key] = box
            filters_section.layout().addWidget(box)

        layout.addWidget(filters_section)
        layout.addStretch(1)

    def _create_section(self, title: str) -> QWidget:
        section = QWidget()
        section.setStyleSheet("QWidget { background-color: transparent; }")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(
            """
            font-size: 10px;
            font-weight: 700;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding-bottom: 4px;
            border-bottom: 1px solid #dee2e6;
            """
        )
        layout.addWidget(header)
        section.setLayout(layout)
        return section

    def _init_dashboard_charts(self) -> None:
        if charts_mod.FigureCanvas is None:
            return

        self.dashboard.clear_chart_cards()

        chart_configs = [
            ("Collisions by Year", self._chart_temporal, "year"),
            ("Collisions by Month", self._chart_temporal, "month"),
            ("Collisions by Day of Week", self._chart_temporal, "dow"),
            ("Collisions by Hour", self._chart_temporal, "hour"),
            ("Accident Class (Severity)", self._chart_category, "accident_class"),
            ("Impact Type", self._chart_category, "impact_type"),
            ("Environment Condition 1", self._chart_category, "env1"),
            ("Environment Condition 2", self._chart_category, "env2"),
            ("Lighting", self._chart_category, "light"),
            ("Location Type", self._chart_category, "location_type"),
            ("Municipality", self._chart_category, "municipality"),
            ("Traffic Control", self._chart_category, "traffic_control"),
        ]

        for title, render_fn, concept_key in chart_configs:
            figure = charts_mod.Figure(figsize=(6.5, 3.0))
            canvas = charts_mod.FigureCanvas(figure)
            canvas.setMinimumHeight(self.chart_height_default)
            self.dashboard.add_chart_card(
                ChartCard(
                    title=title,
                    figure=figure,
                    canvas=canvas,
                    render_fn=render_fn,
                    concept_key=concept_key,
                )
            )

    def _default_qdate_range(self) -> Tuple[QDate, QDate]:
        start, end = self.default_filter_dates()
        return QDate(start.year, start.month, start.day), QDate(end.year, end.month, end.day)

    def default_filter_dates(self) -> Tuple[date, date]:
        return default_last_full_10y_range()

    def current_layer(self):
        return self.layer_combo.currentLayer() if self.layer_combo is not None else None

    def read_filter_panel_state(self) -> FilterPanelState:
        qds = self.date_start.date()
        qde = self.date_end.date()
        return FilterPanelState(
            use_date=self.chk_use_date.isChecked(),
            date_start=date(qds.year(), qds.month(), qds.day()),
            date_end=date(qde.year(), qde.month(), qde.day()),
            selection_only=self.chk_selection_only.isChecked(),
            select_filtered=self.chk_select_filtered.isChecked(),
            selected_codes=self.checked_codes(),
        )

    def checked_codes(self) -> Dict[str, Set[str]]:
        return {concept_key: box.selected_codes() for concept_key, box in self.filter_boxes.items()}

    def selected_codes_for(self, concept_key: str) -> Set[str]:
        box = self.filter_boxes.get(concept_key)
        return set() if box is None else box.selected_codes()

    def apply_filter_options(self, options: Dict[str, FilterOptions]) -> None:
        for concept_key, option in options.items():
            box = self.filter_boxes.get(concept_key)
            if box is None:
                continue
            box.setTitle(option.title)
            box.set_items(option.items, checked=option.checked)

    def filter_item_pairs(self, concept_key: str) -> List[Tuple[str, str]]:
        box = self.filter_boxes.get(concept_key)
        if box is None:
            return []
        pairs: List[Tuple[str, str]] = []
        for index in range(box.list.count()):
            item = box.list.item(index)
            pairs.append((str(item.data(Qt.UserRole)).strip(), item.text()))
        return pairs

    def filter_item_codes(self, concept_key: str) -> List[str]:
        return [code for code, _label in self.filter_item_pairs(concept_key)]

    def set_selected_codes(self, concept_key: str, selected_codes: Set[str]) -> None:
        box = self.filter_boxes.get(concept_key)
        if box is None:
            return
        normalized = {str(code).strip() for code in selected_codes}
        box.list.blockSignals(True)
        for index in range(box.list.count()):
            item = box.list.item(index)
            code = str(item.data(Qt.UserRole)).strip()
            item.setCheckState(Qt.Checked if code in normalized else Qt.Unchecked)
        box.list.blockSignals(False)

    def set_filter_item_labels(self, concept_key: str, labels: Dict[str, str]) -> None:
        box = self.filter_boxes.get(concept_key)
        if box is None:
            return
        box.list.blockSignals(True)
        for index in range(box.list.count()):
            item = box.list.item(index)
            code = str(item.data(Qt.UserRole)).strip()
            if code in labels:
                item.setText(labels[code])
        box.list.blockSignals(False)

    def reset_filter_controls(self, start_date: date, end_date: date) -> None:
        self.chk_use_date.setChecked(True)
        self.chk_selection_only.setChecked(True)
        self.chk_select_filtered.setChecked(False)
        self.date_start.setDate(QDate(start_date.year, start_date.month, start_date.day))
        self.date_end.setDate(QDate(end_date.year, end_date.month, end_date.day))
        for box in self.filter_boxes.values():
            box.clear_checks()

    def set_status(self, text: str) -> None:
        self.dashboard.set_status(text)

    def apply_dashboard_snapshot(self, snapshot: DashboardSnapshot) -> None:
        self.dashboard.update_kpi("total", snapshot.total_value, "#0d6efd" if snapshot.total_value not in {"-", "0"} else None)
        self.dashboard.update_kpi("fatal", snapshot.fatal_value, "#dc3545" if snapshot.fatal_value not in {"-", "0"} else None)
        self.dashboard.update_kpi("severe", snapshot.severe_value, "#fd7e14" if snapshot.severe_value not in {"-", "0%"} else None)
        self.dashboard.set_status(snapshot.status_text)

    def show_no_data(self) -> None:
        if charts_mod.FigureCanvas is None:
            return
        for card in self.dashboard.chart_cards:
            self._disconnect_chart_click(card.canvas)
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "No data\nSelect features or click Apply",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=11,
                color="#9CA3AF",
            )
            ax.set_axis_off()
            card.figure.tight_layout()
            card.canvas.draw()

    def refresh_charts(self, rows: List[Dict[str, Any]], field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        if charts_mod.FigureCanvas is None:
            return

        self._chart_rows = rows
        self._chart_field_map = dict(field_map)
        self._chart_decodes = decodes

        for card in self.dashboard.chart_cards:
            self._disconnect_chart_click(card.canvas)
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            try:
                card.render_fn(ax, card)
                if card.concept_key in self.filter_boxes:
                    self._install_chart_click(ax, card.canvas, card.concept_key)
            except Exception as exc:
                ax.text(
                    0.5,
                    0.5,
                    f"Chart error:\n{exc}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_axis_off()
            card.figure.tight_layout()
            card.canvas.draw()

    def _chart_temporal(self, ax: Any, card: ChartCard) -> None:
        charts_mod.render_temporal_by_class(
            ax,
            self._chart_rows,
            self._chart_field_map.get("date"),
            self._chart_field_map.get("accident_class"),
            lambda raw: self._chart_decodes.decode("accident_class", raw),
            self._chart_decodes.mapping("accident_class"),
            bucket=card.concept_key,
            show_labels=True,
        )

    def _chart_category(self, ax: Any, card: ChartCard) -> None:
        concept_key = card.concept_key
        charts_mod.render_category(
            ax,
            self._chart_rows,
            self._chart_field_map.get(concept_key),
            lambda raw: self._chart_decodes.decode(concept_key, raw),
            top_n=self.top_n_default,
            show_labels=True,
            include_blank=True,
        )

    def _install_chart_click(self, ax: Any, canvas: Any, concept_key: str) -> None:
        labels = [tick.get_text() for tick in ax.get_yticklabels()]
        if not labels:
            return

        ticks = list(ax.get_yticks())[: len(labels)] or list(range(len(labels)))
        targets = []
        for patch in ax.patches:
            try:
                center = patch.get_y() + patch.get_height() / 2.0
            except Exception:
                continue
            index = min(range(len(ticks)), key=lambda current: abs(ticks[current] - center))
            if index < len(labels):
                targets.append((patch, labels[index]))

        if not targets:
            return

        def handler(event, current_ax=ax, current_targets=targets, current_key=concept_key):
            if event.name != "button_press_event" or event.inaxes != current_ax:
                return
            if event.x is None or event.y is None or getattr(event, "button", None) != 1:
                return

            label = None
            for patch, patch_label in current_targets:
                try:
                    if patch.contains_point((event.x, event.y)):
                        label = patch_label
                        break
                except Exception:
                    continue

            if label is None:
                return

            additive = False
            gui_event = getattr(event, "guiEvent", None)
            try:
                if gui_event is not None:
                    additive = bool(gui_event.modifiers() & Qt.ControlModifier)
            except Exception:
                additive = False

            self.controller.filter_by_category(current_key, label, additive)

        self._disconnect_chart_click(canvas)
        self._click_cids[canvas] = canvas.mpl_connect("button_press_event", handler)

    def _disconnect_chart_click(self, canvas: Any) -> None:
        cid = self._click_cids.get(canvas)
        if cid is None:
            return
        try:
            canvas.mpl_disconnect(cid)
        except Exception:
            pass
        del self._click_cids[canvas]

    def chart_cards(self) -> Sequence[ChartCard]:
        return list(self.dashboard.chart_cards)

    def chart_figure_factory(self):
        return charts_mod.Figure

    def prompt_save_file(self, title: str, file_filter: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, title, "", file_filter)
        return path

    def prompt_open_file(self, title: str, file_filter: str) -> str:
        path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        return path

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_settings_dialog(self) -> None:
        if self.settings_dialog is None:
            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("Collision Analytics Settings")
            self.settings_dialog.setMinimumSize(600, 500)

            layout = QVBoxLayout()
            tab_widget = QTabWidget()

            self.tabs["fields"] = FieldsTab(self)
            self.tabs["decodes"] = DecodesTab(self)
            self.tabs["about"] = AboutTab(self)

            tab_widget.addTab(self.tabs["fields"].build(), "Field Mapping")
            tab_widget.addTab(self.tabs["decodes"].build(), "Decode Tables")
            tab_widget.addTab(self.tabs["about"].build(), "About")

            btn_close = QPushButton("Close")
            btn_close.clicked.connect(self.settings_dialog.accept)

            layout.addWidget(tab_widget)
            layout.addWidget(btn_close)
            self.settings_dialog.setLayout(layout)

        if self.current_layer() is not None:
            self.tabs["fields"].populate_selectors()
        self.settings_dialog.exec_()

    def apply_filters(self) -> None:
        self.controller.apply_filters()

    def reset_all_filters(self) -> None:
        self.controller.reset_all_filters()

    def export_summary_csv(self) -> None:
        self.controller.export_summary_csv()

    def export_filtered_features_csv(self) -> None:
        self.controller.export_filtered_features_csv()

    def export_dashboard_png(self) -> None:
        self.controller.export_dashboard_png()

    def closeEvent(self, event) -> None:
        self.controller.close()
        super().closeEvent(event)
