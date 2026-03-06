"""Main dock widget for Collision Analytics plugin - Split Dashboard Design."""

from __future__ import annotations

import csv
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import QSettings, QTimer, Qt, QDate
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMapLayerProxyModel,
    QgsMessageLog,
    QgsTask,
)
from qgis.gui import QgsMapLayerComboBox

from ..core import charts as charts_mod
from ..core.config import DEFAULT_FIELD_MAP, FILTER_CONCEPTS
from ..core.decodes import DecodeRegistry
from ..core.filters import FilterEngine, FilterSpec
from ..core.settings import load_json, save_json
from ..core.utils import safe_str, to_datetime, is_blank
from ..gui.widgets import CheckListFilterBox
from ..gui.tabs import AboutTab, DecodesTab, FieldsTab
from .dashboard import DashboardWidget, ChartCard, FilterPanel

BACKGROUND_FILTER_THRESHOLD = 50000


class FilterTask(QgsTask):
    """Background task for filtering large datasets."""

    def __init__(self, layer, spec: FilterSpec, needed_fields: List[str]):
        super().__init__("Collision Analytics filtering", QgsTask.CanCancel)
        self.layer = layer
        self.spec = spec
        self.needed_fields = needed_fields
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        """Run filtering in background thread."""
        try:
            engine = FilterEngine(self.layer)
            fids, rows = engine.apply(self.spec, self.needed_fields)
            self.filtered_fids = fids
            self.filtered_rows = rows
            return True
        except Exception as e:
            self.exception = e
            return False


class CollisionAnalyticsDockWidget(QDockWidget):
    """Main dock widget with split dashboard layout."""

    def __init__(self, iface):
        super().__init__("Collision Analytics", iface.mainWindow())
        self.iface = iface
        self.settings = QSettings()
        self.decodes = DecodeRegistry(self.settings)

        self.setObjectName("CollisionAnalyticsDockWidget")
        self.root = QWidget()
        self.setWidget(self.root)

        # Core state
        self.layer = None
        self.field_map: Dict[str, str] = dict(DEFAULT_FIELD_MAP)
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self._active_filter_task: Optional[FilterTask] = None

        # UX defaults
        self.top_n_default = 12
        self.chart_height_default = 320

        # Filter controls (will be moved to filter panel)
        self.chk_use_date: QCheckBox | None = None
        self.date_start: QDateEdit | None = None
        self.date_end: QDateEdit | None = None
        self.chk_selection_only: QCheckBox | None = None
        self.chk_select_filtered: QCheckBox | None = None
        self.filter_boxes: Dict[str, CheckListFilterBox] = {}

        # Dashboard widget
        self.dashboard: DashboardWidget | None = None

        # Settings dialog tabs (kept for configuration)
        self.settings_dialog: QDialog | None = None
        self.tabs: Dict[str, Any] = {}

        self._build_ui()
        self._load_field_map()

        QTimer.singleShot(0, self._deferred_init)

    def _build_ui(self) -> None:
        """Build the main UI structure."""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar with layer selector and actions
        top_bar = self._build_top_bar()
        layout.addWidget(top_bar)

        # Dashboard with split layout
        self.dashboard = DashboardWidget(self)
        layout.addWidget(self.dashboard, 1)

        # Build filter controls in the filter panel
        self._build_filter_controls()

        # Initialize charts in dashboard
        self._init_dashboard_charts()

        self.root.setLayout(layout)

    def _build_top_bar(self) -> QWidget:
        """Build the top action bar."""
        bar = QWidget()
        bar.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Layer selector
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layer_combo.layerChanged.connect(self._on_layer_changed)

        layout.addWidget(QLabel("Layer:"))
        layout.addWidget(self.layer_combo, 1)

        # Quick actions
        btn_apply = QPushButton("Apply")
        btn_apply.setStyleSheet(self._action_button_style())
        btn_apply.clicked.connect(self.apply_filters)

        btn_reset = QPushButton("Reset")
        btn_reset.setStyleSheet(self._secondary_button_style())
        btn_reset.clicked.connect(self.reset_all_filters)

        btn_settings = QPushButton("Settings")
        btn_settings.setStyleSheet(self._secondary_button_style())
        btn_settings.clicked.connect(self._show_settings_dialog)

        layout.addWidget(btn_apply)
        layout.addWidget(btn_reset)
        layout.addSpacing(12)
        layout.addWidget(btn_settings)

        bar.setLayout(layout)
        return bar

    def _action_button_style(self) -> str:
        """Primary action button style."""
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
        """Secondary button style."""
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
        """Build filter controls in the filter panel."""
        panel = self.dashboard.get_filter_panel()
        layout = panel.content_layout()

        # Date range section
        date_section = self._create_section("Date Range")

        self.chk_use_date = QCheckBox("Filter by date range")
        self.chk_use_date.setChecked(True)
        self.chk_use_date.stateChanged.connect(self._on_filter_changed)

        self.date_start = QDateEdit()
        self.date_end = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_end.setCalendarPopup(True)

        dstart, dend = self._default_last_full_10y_range()
        self.date_start.setDate(dstart)
        self.date_end.setDate(dend)

        self.date_start.dateChanged.connect(self._on_filter_changed)
        self.date_end.dateChanged.connect(self._on_filter_changed)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self.date_start)
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self.date_end)

        date_section.layout().addWidget(self.chk_use_date)
        date_section.layout().addLayout(date_row)
        layout.addWidget(date_section)

        # Scope section
        scope_section = self._create_section("Scope")

        self.chk_selection_only = QCheckBox("Map selection only (recommended)")
        self.chk_selection_only.setChecked(True)
        self.chk_selection_only.stateChanged.connect(self._on_filter_changed)

        self.chk_select_filtered = QCheckBox("Select filtered features on map")
        self.chk_select_filtered.setChecked(False)

        scope_section.layout().addWidget(self.chk_selection_only)
        scope_section.layout().addWidget(self.chk_select_filtered)
        layout.addWidget(scope_section)

        # Filter values section
        values_section = self._create_section("Filter Values")

        btn_decodes = QPushButton("Load from decode tables")
        btn_decodes.clicked.connect(lambda: self._populate_filter_values("decodes"))
        btn_decodes.setStyleSheet(self._secondary_button_style())

        btn_selection = QPushButton("Load from map selection")
        btn_selection.clicked.connect(lambda: self._populate_filter_values("selection"))
        btn_selection.setStyleSheet(self._secondary_button_style())

        btn_layer = QPushButton("Load from entire layer")
        btn_layer.clicked.connect(lambda: self._populate_filter_values("layer"))
        btn_layer.setStyleSheet(self._secondary_button_style())
        btn_layer.setToolTip("May be slow for large layers")

        values_section.layout().addWidget(btn_decodes)
        values_section.layout().addWidget(btn_selection)
        values_section.layout().addWidget(btn_layer)
        layout.addWidget(values_section)

        # Category filters section
        filters_section = self._create_section("Category Filters")

        self.filter_boxes = {}
        for concept, title in FILTER_CONCEPTS:
            box = CheckListFilterBox(title)
            box.list.itemChanged.connect(self._on_filter_changed)
            self.filter_boxes[concept] = box
            filters_section.layout().addWidget(box)

        layout.addWidget(filters_section)
        layout.addStretch(1)

    def _create_section(self, title: str) -> QWidget:
        """Create a collapsible section container."""
        section = QWidget()
        section.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        # Section header
        header = QLabel(title)
        header.setStyleSheet("""
            font-size: 10px;
            font-weight: 700;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding-bottom: 4px;
            border-bottom: 1px solid #dee2e6;
        """)
        layout.addWidget(header)

        section.setLayout(layout)
        return section

    def _init_dashboard_charts(self) -> None:
        """Initialize chart cards in the dashboard."""
        if charts_mod.FigureCanvas is None:
            return

        self.dashboard.clear_chart_cards()
        self._click_cids: Dict[Any, int] = {}

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
            fig = charts_mod.Figure(figsize=(6.5, 3.0))
            canvas = charts_mod.FigureCanvas(fig)
            canvas.setMinimumHeight(self.chart_height_default)

            card = ChartCard(
                title=title,
                figure=fig,
                canvas=canvas,
                render_fn=render_fn,
                concept_key=concept_key,
            )
            self.dashboard.add_chart_card(card)

    def _deferred_init(self) -> None:
        """Initialize after UI is shown."""
        self.layer = self.layer_combo.currentLayer()
        self._on_layer_changed(self.layer)

    def _load_field_map(self) -> None:
        """Load field mapping from settings."""
        from ..core.config import SETTINGS_FIELD_MAP_KEY

        obj = load_json(self.settings, SETTINGS_FIELD_MAP_KEY, None)
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.field_map[str(k)] = str(v)

    def _save_field_map(self) -> None:
        """Save field mapping to settings."""
        from ..core.config import SETTINGS_FIELD_MAP_KEY

        save_json(self.settings, SETTINGS_FIELD_MAP_KEY, self.field_map)

    # ------------------ Layer lifecycle ------------------

    def _on_layer_changed(self, layer) -> None:
        """Handle layer selection changes."""
        self.layer = layer
        self.refresh_from_layer()

    def refresh_from_layer(self) -> None:
        """Refresh UI when layer changes."""
        if self.layer is None:
            self.filtered_fids = []
            self.filtered_rows = []
            self._set_idle_state()
            return

        # Populate filter values from layer/selection/decodes
        if self.selection_only and self.layer.selectedFeatureCount() > 0:
            self._populate_filter_values(source="selection")
        else:
            self._populate_filter_values(source="decodes")

        # Auto-run if selection scope + selection exists
        if self.selection_only and self.layer.selectedFeatureCount() > 0:
            self.apply_filters()
        else:
            self.filtered_fids = []
            self.filtered_rows = []
            self._set_idle_state()

    # ------------------ Filtering ------------------

    def _build_spec(self) -> FilterSpec:
        """Build filter specification from UI state."""
        selected_fids = set(self.layer.selectedFeatureIds()) if self.layer else set()

        date_start, date_end = self.get_date_range()

        return FilterSpec(
            selection_only=self.selection_only,
            selected_fids=selected_fids,
            date_enabled=self.use_date,
            date_field=self.field_map.get("date"),
            date_start=date_start,
            date_end=date_end,
            category_codes=self.get_selected_codes(),
            field_map=self.field_map,
        )

    def _needed_fields(self, spec: FilterSpec) -> List[str]:
        """Determine which fields are needed for filtering and display."""
        layer_fields = {f.name() for f in self.layer.fields()}
        needed: Set[str] = set()

        # Used by filters
        if spec.date_enabled and spec.date_field and spec.date_field in layer_fields:
            needed.add(spec.date_field)

        for concept_key, selected in spec.category_codes.items():
            if not selected:
                continue
            fname = spec.field_map.get(concept_key)
            if fname and fname in layer_fields:
                needed.add(fname)

        # Used by results
        for k, fname in self.field_map.items():
            if fname and fname in layer_fields:
                needed.add(fname)

        return sorted(needed)

    def _default_last_full_10y_range(self):
        """Get default 10-year date range."""
        today = QDate.currentDate()
        end_year = today.year() - 1
        end = QDate(end_year, 12, 31)
        start = QDate(end_year - 9, 1, 1)
        return start, end

    def _default_dates(self) -> tuple:
        """Get default dates as Python dates."""
        dstart, dend = self._default_last_full_10y_range()
        return (
            date(dstart.year(), dstart.month(), dstart.day()),
            date(dend.year(), dend.month(), dend.day()),
        )

    def apply_filters(self) -> None:
        """Apply filters to the current layer."""
        if self.layer is None:
            return

        spec = self._build_spec()
        default_start, default_end = self._default_dates()

        # UX: selection-only + no selection + no intent => idle
        if (
            spec.selection_only
            and not spec.selected_fids
            and not spec.has_any_intent(default_start, default_end)
        ):
            self.filtered_fids = []
            self.filtered_rows = []
            self._refresh_filter_counts()
            self._set_idle_state()
            self.dashboard.set_status(
                "Idle: select features or set filters, then Apply."
            )
            return

        # UX: selection-only + no selection but intent => inform user
        if (
            spec.selection_only
            and not spec.selected_fids
            and spec.has_any_intent(default_start, default_end)
        ):
            QMessageBox.information(
                self,
                "Collision Analytics",
                "No map selection, but filters are set.\n\n"
                "Running analysis on the whole layer for the active filters.",
            )

        feature_count = self.layer.featureCount()
        needed = self._needed_fields(spec)

        if feature_count >= BACKGROUND_FILTER_THRESHOLD:
            # Offload to background task
            task = FilterTask(self.layer, spec, needed)
            task.feature_count = feature_count
            task.taskCompleted.connect(
                lambda _result=None, t=task: self._on_filter_complete(t)
            )
            task.taskTerminated.connect(lambda *_, t=task: self._on_filter_failed(t))
            self._active_filter_task = task
            self.dashboard.set_status(f"Filtering {feature_count:,} features...")
            QgsApplication.taskManager().addTask(task)
            return

        # Run synchronously for small datasets
        engine = FilterEngine(self.layer)
        fids, rows = engine.apply(spec, needed)
        self._apply_filter_results(fids, rows, feature_count)

    def _apply_filter_results(
        self, fids: List[int], rows: List[Dict[str, Any]], total_count: int
    ) -> None:
        """Apply filtering results to the UI."""
        self.filtered_fids = fids
        self.filtered_rows = rows

        if self.select_filtered and self.layer is not None:
            self.layer.selectByIds(fids)

        self._refresh_filter_counts()
        self.dashboard.set_status(f"Matched {len(fids):,} of {total_count:,} features.")

        # Update dashboard
        self._update_kpis()
        self._refresh_charts()

    def _on_filter_complete(self, task: FilterTask) -> None:
        """Handle background filter task completion."""
        self._active_filter_task = None

        if self.layer is None or task.layer != self.layer:
            self.dashboard.set_status(
                "Layer changed during filtering; results ignored."
            )
            return

        if task.exception:
            self._on_filter_failed(task)
            return

        total_count = getattr(task, "feature_count", self.layer.featureCount())
        self._apply_filter_results(task.filtered_fids, task.filtered_rows, total_count)

    def _on_filter_failed(self, task: FilterTask) -> None:
        """Handle background filter task failure."""
        self._active_filter_task = None
        exc = task.exception or Exception("Filtering task failed.")
        QgsMessageLog.logMessage(str(exc), "Collision Analytics", Qgis.Critical)
        self.dashboard.set_status(f"Filtering failed: {exc}")

    # ------------------ State management ------------------

    def _set_idle_state(self) -> None:
        """Set UI to idle state."""
        self.dashboard.update_kpi("total", "-")
        self.dashboard.update_kpi("fatal", "-")
        self.dashboard.update_kpi("severe", "-")
        self._show_no_data_in_charts()

    def _show_no_data_in_charts(self) -> None:
        """Show 'No data' message in all charts."""
        if charts_mod.FigureCanvas is None:
            return

        for card in self.dashboard.chart_cards:
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

    def reset_all_filters(self) -> None:
        """Reset all filters to defaults."""
        self.chk_use_date.setChecked(True)
        self.chk_selection_only.setChecked(True)
        self.chk_select_filtered.setChecked(False)

        dstart, dend = self._default_last_full_10y_range()
        self.date_start.setDate(dstart)
        self.date_end.setDate(dend)

        for box in self.filter_boxes.values():
            box.clear_checks()

        self.filtered_fids = []
        self.filtered_rows = []
        self._set_idle_state()
        self.apply_filters()

    # ------------------ KPIs ------------------

    def _update_kpis(self) -> None:
        """Update KPI cards with current data."""
        rows = self.filtered_rows or []
        total = len(rows)

        if total == 0:
            self.dashboard.update_kpi("total", "0")
            self.dashboard.update_kpi("fatal", "0")
            self.dashboard.update_kpi("severe", "0%")
            return

        # Calculate severity
        sev_field = self.field_map.get("accident_class")
        fatal = 0
        injury = 0

        if sev_field:
            for r in rows:
                raw = safe_str(r.get(sev_field)).strip()
                label = self.decodes.decode("accident_class", raw)
                if label == "Fatal":
                    fatal += 1
                elif label == "Injury":
                    injury += 1

        severe_rate = ((fatal + injury) / total * 100.0) if total else 0.0

        self.dashboard.update_kpi("total", f"{total:,}", "#0d6efd")
        self.dashboard.update_kpi("fatal", f"{fatal:,}", "#dc3545")
        self.dashboard.update_kpi("severe", f"{severe_rate:.1f}%", "#fd7e14")

    # ------------------ Charts ------------------

    def _refresh_charts(self) -> None:
        """Refresh all charts."""
        if charts_mod.FigureCanvas is None:
            return

        for card in self.dashboard.chart_cards:
            card.figure.clear()
            ax = card.figure.add_subplot(111)

            try:
                card.render_fn(ax, card)
                # Install click handler if applicable
                if card.concept_key:
                    self._install_chart_click(ax, card.canvas, card.concept_key)
            except Exception as e:
                ax.text(
                    0.5,
                    0.5,
                    f"Chart error:\n{e}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_axis_off()

            card.figure.tight_layout()
            card.canvas.draw()

    def _chart_temporal(self, ax: Any, card: ChartCard) -> None:
        """Render temporal chart."""
        bucket = card.concept_key  # year, month, dow, hour
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self.decodes.decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket=bucket,
            show_labels=True,
        )

    def _chart_category(self, ax: Any, card: ChartCard) -> None:
        """Render category chart."""
        concept_key = card.concept_key
        field = self.field_map.get(concept_key)
        decode = lambda raw: self.decodes.decode(concept_key, raw)
        charts_mod.render_category(
            ax,
            self.filtered_rows,
            field,
            decode,
            top_n=self.top_n_default,
            show_labels=True,
            include_blank=True,
        )

    def _install_chart_click(self, ax: Any, canvas: Any, concept_key: str) -> None:
        """Wire up click-to-filter for charts."""
        if charts_mod.FigureCanvas is None or canvas is None or ax is None:
            return

        labels = [t.get_text() for t in ax.get_yticklabels()]
        if not labels:
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

            self.filter_by_category(concept_key, label, additive)

        # Disconnect previous handler if exists
        cid = getattr(self, "_click_cids", {}).get(canvas)
        if cid is not None:
            try:
                canvas.mpl_disconnect(cid)
            except Exception:
                pass

        if not hasattr(self, "_click_cids"):
            self._click_cids = {}

        try:
            self._click_cids[canvas] = canvas.mpl_connect("button_press_event", handler)
        except Exception:
            pass

    # ------------------ Filter helpers ------------------

    def _on_filter_changed(self, *_) -> None:
        """Handle filter selection changes."""
        if self.layer is None:
            return
        if self.selection_only and self.layer.selectedFeatureCount() > 0:
            QTimer.singleShot(150, self.apply_filters)

    def _refresh_filter_counts(self) -> None:
        """Update filter list counts."""
        for concept_key, box in self.filter_boxes.items():
            field_name = self.field_map.get(concept_key)
            if not field_name:
                continue

            counts: Dict[str, int] = {}
            for r in self.filtered_rows or []:
                raw_val = r.get(field_name)
                if is_blank(raw_val):
                    continue
                raw = safe_str(raw_val).strip()
                counts[raw] = counts.get(raw, 0) + 1

            box.list.blockSignals(True)
            for i in range(box.list.count()):
                it = box.list.item(i)
                code = safe_str(it.data(Qt.UserRole)).strip()
                lab = self.decodes.decode(concept_key, code)
                it.setText(f"{lab} ({counts.get(code, 0)})")
            box.list.blockSignals(False)

    def populate_filter_values(self, source: str) -> None:
        """Public wrapper for populating filter values.

        Kept for compatibility with tab modules that still call the
        legacy public method name.
        """
        self._populate_filter_values(source)

    def update_active_filters_summary(self, lines: List[str]) -> None:
        """Update active-filter summary in the dashboard status area.

        This preserves the old dock API used by legacy tab classes while
        mapping the summary text into the new split-dashboard UI.
        """
        if not lines:
            self.dashboard.set_status("No filters applied")
            return
        self.dashboard.set_status("Active filters: " + " | ".join(lines))

    def _populate_filter_values(self, source: str) -> None:
        """Populate filter value lists from various sources."""
        if self.layer is None:
            return

        # Cache checked state
        checked_cache = {
            ck: box.selected_codes() for ck, box in self.filter_boxes.items()
        }

        layer_fields = {f.name() for f in self.layer.fields()}
        selection_fids = set(self.layer.selectedFeatureIds())

        for concept_key, box in self.filter_boxes.items():
            field_name = self.field_map.get(concept_key)
            if not field_name or field_name not in layer_fields:
                box.setTitle(f"{box.title()} (field not mapped)")
                box.set_items([])
                continue

            codes: Set[str] = set()

            if source == "decodes":
                codes.update(self.decodes.mapping(concept_key).keys())

            elif source == "selection":
                if not selection_fids:
                    QMessageBox.information(
                        self, "Collision Analytics", "No selected features in map."
                    )
                    return
                from qgis.core import QgsFeatureRequest

                req = QgsFeatureRequest().setFilterFids(list(selection_fids))
                req.setSubsetOfAttributes([field_name], self.layer.fields())
                for f in self.layer.getFeatures(req):
                    raw_val = f[field_name]
                    if is_blank(raw_val):
                        continue
                    v = safe_str(raw_val).strip()
                    if v:
                        codes.add(v)

            elif source == "layer":
                try:
                    idx = self.layer.fields().indexOf(field_name)
                    vals = self.layer.uniqueValues(idx, 5000)
                    for v in vals:
                        if is_blank(v):
                            continue
                        s = safe_str(v).strip()
                        if s:
                            codes.add(s)
                except Exception:
                    codes.update(self.decodes.mapping(concept_key).keys())

            # Build items with counts
            def label_for(code: str) -> str:
                lab = self.decodes.decode(concept_key, code)
                return f"{lab} (0)"

            items = sorted(
                [(c, label_for(c)) for c in codes], key=lambda t: t[1].lower()
            )
            box.setTitle(box.title().split(" (")[0])
            box.set_items(items, checked=checked_cache.get(concept_key, set()))

        self._refresh_filter_counts()

    def get_selected_codes(self) -> Dict[str, Set[str]]:
        """Get all selected codes from filter boxes."""
        return {k: box.selected_codes() for k, box in self.filter_boxes.items()}

    def get_date_range(self) -> Tuple[date, date]:
        """Get the current date range as Python dates."""
        qds = self.date_start.date()
        qde = self.date_end.date()
        return (
            date(qds.year(), qds.month(), qds.day()),
            date(qde.year(), qde.month(), qde.day()),
        )

    @property
    def use_date(self) -> bool:
        """Whether date filtering is enabled."""
        return self.chk_use_date.isChecked()

    @property
    def selection_only(self) -> bool:
        """Whether to use map selection only."""
        return self.chk_selection_only.isChecked()

    @property
    def select_filtered(self) -> bool:
        """Whether to select filtered features on map."""
        return self.chk_select_filtered.isChecked()

    # ------------------ Chart interactions ------------------

    def filter_by_category(self, concept_key: str, label: str, additive: bool) -> None:
        """Apply filter from chart click."""
        # Resolve label to codes
        codes = self._resolve_codes_from_label(concept_key, label)
        if not codes:
            return

        box = self.filter_boxes.get(concept_key)
        if box is None:
            return

        box.list.blockSignals(True)

        # Get matching items
        matches = []
        for i in range(box.list.count()):
            it = box.list.item(i)
            code = safe_str(it.data(Qt.UserRole)).strip()
            if code in codes:
                matches.append(it)

        if not matches:
            box.list.blockSignals(False)
            return

        # Clear non-matches if not additive
        if not additive:
            for i in range(box.list.count()):
                it = box.list.item(i)
                if it in matches:
                    continue
                if it.checkState() != Qt.Unchecked:
                    it.setCheckState(Qt.Unchecked)

        # Check matches
        for it in matches:
            if it.checkState() != Qt.Checked:
                it.setCheckState(Qt.Checked)

        box.list.blockSignals(False)
        QTimer.singleShot(50, self.apply_filters)

    def _resolve_codes_from_label(self, concept_key: str, label: str) -> List[str]:
        """Resolve chart label back to codes."""
        mapping = self.decodes.mapping(concept_key)
        if not mapping:
            return []

        # Strip count suffix
        text = safe_str(label).replace("\n", " ")
        import re

        text = re.sub(r"\s*\(\s*[\d,]+\s*\)\s*$", "", text)
        text = " ".join(text.split()).strip()

        target = text.lower()

        # Try exact match
        for code, lab in mapping.items():
            if lab.lower() == target:
                return [code]

        # Try startswith
        for code, lab in mapping.items():
            if lab.lower().startswith(target) or target.startswith(lab.lower()):
                return [code]

        # Unknown/blank fallback
        if target in {"unknown", "unknown / blank", "blank"}:
            return [""]

        return []

    # ------------------ Settings Dialog ------------------

    def _show_settings_dialog(self) -> None:
        """Show settings dialog with Fields and Decodes tabs."""
        if self.settings_dialog is None:
            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("Collision Analytics Settings")
            self.settings_dialog.setMinimumSize(600, 500)

            layout = QVBoxLayout()

            # Tab widget for settings
            tab_widget = QTabWidget()

            # Create tabs
            self.tabs["fields"] = FieldsTab(self)
            self.tabs["decodes"] = DecodesTab(self)
            self.tabs["about"] = AboutTab(self)

            tab_widget.addTab(self.tabs["fields"].build(), "Field Mapping")
            tab_widget.addTab(self.tabs["decodes"].build(), "Decode Tables")
            tab_widget.addTab(self.tabs["about"].build(), "About")

            layout.addWidget(tab_widget)

            # Close button
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(self.settings_dialog.accept)
            layout.addWidget(btn_close)

            self.settings_dialog.setLayout(layout)

        # Populate current layer fields
        if self.layer:
            self.tabs["fields"].populate_selectors()

        self.settings_dialog.exec_()

    # ------------------ Export ------------------

    def export_summary_csv(self) -> None:
        """Export summary statistics to CSV."""
        if not self.filtered_rows:
            QMessageBox.information(
                self, "Collision Analytics", "No filtered results to export."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export summary CSV", "", "CSV (*.csv)"
        )
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

        rows = [
            ("filtered_collisions", total),
            ("sum_involved_vehicles_cnt", sum_field("veh_cnt")),
            ("sum_involved_persons_cnt", sum_field("per_cnt")),
            ("sum_involved_drivers_cnt", sum_field("drv_cnt")),
            ("sum_involved_occupants_cnt", sum_field("occ_cnt")),
            ("sum_involved_pedestrians_cnt", sum_field("ped_cnt")),
            ("scope", "selection" if self.selection_only else "layer"),
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            for k, v in rows:
                w.writerow([k, v])

        QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")

    def export_filtered_features_csv(self) -> None:
        """Export filtered features to CSV with decoded values."""
        if not self.filtered_rows:
            QMessageBox.information(
                self, "Collision Analytics", "No filtered results to export."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export filtered features CSV", "", "CSV (*.csv)"
        )
        if not path:
            return

        # Collect all fields present in the filtered rows
        all_fields = set()
        for row in self.filtered_rows:
            all_fields.update(row.keys())
        all_fields = sorted(all_fields)

        # Map concepts to fields
        field_to_concept: Dict[str, str] = {}
        for concept_key, field_name in self.field_map.items():
            if field_name in all_fields:
                field_to_concept[field_name] = concept_key

        # Build column headers
        headers: List[str] = []
        concepts_with_decodes = set(self.decodes.keys())

        for field in all_fields:
            headers.append(field)
            concept_key = field_to_concept.get(field)
            if concept_key and concept_key in concepts_with_decodes:
                headers.append(f"{field}_decoded")

        # Build rows
        csv_rows = []
        for row in self.filtered_rows:
            csv_row = []
            for field in all_fields:
                raw_value = row.get(field)
                # Format the raw value
                if raw_value is None:
                    formatted_raw = ""
                elif isinstance(raw_value, (date, datetime)):
                    formatted_raw = (
                        raw_value.strftime("%Y-%m-%d %H:%M:%S")
                        if isinstance(raw_value, datetime)
                        else raw_value.strftime("%Y-%m-%d")
                    )
                elif hasattr(raw_value, "toPyDateTime"):
                    try:
                        dt = raw_value.toPyDateTime()
                        formatted_raw = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        formatted_raw = safe_str(raw_value)
                elif hasattr(raw_value, "toPyDate"):
                    try:
                        d = raw_value.toPyDate()
                        dt = datetime(d.year, d.month, d.day)
                        formatted_raw = dt.strftime("%Y-%m-%d")
                    except Exception:
                        formatted_raw = safe_str(raw_value)
                else:
                    formatted_raw = safe_str(raw_value)
                csv_row.append(formatted_raw)

                # Add decoded value if applicable
                concept_key = field_to_concept.get(field)
                if concept_key and concept_key in concepts_with_decodes:
                    decoded_value = self.decodes.decode(concept_key, raw_value)
                    csv_row.append(decoded_value)
            csv_rows.append(csv_row)

        # Write CSV
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(headers)
                w.writerows(csv_rows)
            QMessageBox.information(
                self,
                "Collision Analytics",
                f"Exported {len(csv_rows)} features to:\n{path}",
            )
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Export failed:\n{e}")

    def export_dashboard_png(self) -> None:
        """Export dashboard charts as PNG."""
        if charts_mod.FigureCanvas is None:
            QMessageBox.warning(
                self,
                "Collision Analytics",
                "Charts are not available (matplotlib missing).",
            )
            return

        if not self.dashboard.chart_cards:
            QMessageBox.information(self, "Collision Analytics", "No charts to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export dashboard PNG", "", "PNG (*.png)"
        )
        if not path:
            return

        cols = 2
        cards = self.dashboard.chart_cards
        rows = (len(cards) + cols - 1) // cols
        fig = charts_mod.Figure(figsize=(cols * 7.5, rows * 3.2))

        for idx, card in enumerate(cards):
            ax = fig.add_subplot(rows, cols, idx + 1)
            ax.set_title(card.title, fontsize=10)
            try:
                card.render_fn(ax, card)
            except Exception as e:
                ax.text(
                    0.5,
                    0.5,
                    f"Chart error:\n{e}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_axis_off()

        fig.tight_layout()
        fig.savefig(path, dpi=200)
        QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")
