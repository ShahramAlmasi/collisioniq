from __future__ import annotations

import csv
import copy
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt, QDate, QDateTime, QSettings, QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDockWidget,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from qgis.core import Qgis, QgsApplication, QgsFeatureRequest, QgsMapLayerProxyModel, QgsMessageLog, QgsTask
from qgis.gui import QgsMapLayerComboBox

from ..core.config import (
    DEFAULT_FIELD_MAP,
    FILTER_CONCEPTS,
    SETTINGS_FIELD_MAP_KEY,
)
from ..core.decodes import DecodeRegistry
from ..core.filters import FilterEngine, FilterSpec
from ..core.settings import load_json, save_json
from ..core.utils import safe_str, to_datetime, is_blank
from ..core import charts as charts_mod
from .widgets import CheckListFilterBox

BACKGROUND_FILTER_THRESHOLD = 50000


class FilterTask(QgsTask):
    def __init__(self, layer, spec: FilterSpec, needed_fields: List[str]):
        super().__init__("Collision Analytics filtering", QgsTask.CanCancel)
        self.layer = layer
        self.spec = spec
        self.needed_fields = needed_fields
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        # Runs in a background thread; do not touch UI or layer selection here.
        try:
            engine = FilterEngine(self.layer)
            fids, rows = engine.apply(self.spec, self.needed_fields)
            self.filtered_fids = fids
            self.filtered_rows = rows
            return True
        except Exception as e:
            # Store the exception so the main thread can surface it safely.
            self.exception = e
            return False


class CollisionAnalyticsDockWidget(QDockWidget):
    def __init__(self, iface):
        super().__init__("Collision Analytics", iface.mainWindow())
        self.iface = iface
        self.settings = QSettings()
        self.decodes = DecodeRegistry(self.settings)

        self.setObjectName("CollisionAnalyticsDockWidget")
        self.root = QWidget()
        self.setWidget(self.root)

        self.layer = None
        self.field_map: Dict[str, str] = dict(DEFAULT_FIELD_MAP)
        self.filter_boxes: Dict[str, CheckListFilterBox] = {}

        # filtered cache
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self._active_filter_task: Optional[FilterTask] = None

        # UX defaults
        self.top_n_default = 12
        self.chart_height_default = 420

        # remember checks while reloading value lists
        self._checked_cache: Dict[str, Set[str]] = {}
        self._concept_titles: Dict[str, str] = {k: v for k, v in FILTER_CONCEPTS}

        self._build_ui()
        self._load_field_map()

        QTimer.singleShot(0, self._deferred_init)

    # ------------------ UI ------------------
    def _build_ui(self) -> None:
        top = QHBoxLayout()

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.layer_combo.layerChanged.connect(self._on_layer_changed)

        top.addWidget(QLabel("Collision layer:"))
        top.addWidget(self.layer_combo, 1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_from_layer)
        top.addWidget(self.btn_refresh)

        self.btn_reset_all = QPushButton("Reset Filters")
        self.btn_reset_all.clicked.connect(self._reset_all_filters)

        self.lbl_active_filters = QLabel("No filters applied")
        self.lbl_active_filters.setWordWrap(True)
        self.lbl_active_filters.setStyleSheet("color:#111;")

        active_row = QHBoxLayout()
        active_row.addWidget(self.btn_reset_all)
        active_row.addSpacing(12)
        active_row.addWidget(QLabel("Active filters:"))
        active_row.addWidget(self.lbl_active_filters, 1)

        self.tabs = QTabWidget()
        self.tab_filters = QWidget()
        self.tab_charts = QWidget()
        self.tab_summary = QWidget()
        self.tab_fields = QWidget()
        self.tab_decodes = QWidget()
        self.tab_about = QWidget()

        self.tabs.addTab(self.tab_filters, "Filters")
        self.tabs.addTab(self.tab_charts, "Charts")
        self.tabs.addTab(self.tab_summary, "Summary & Insights")
        self.tabs.addTab(self.tab_fields, "Fields")
        self.tabs.addTab(self.tab_decodes, "Decodes")
        self.tabs.addTab(self.tab_about, "About")

        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(active_row)
        root.addWidget(self.tabs, 1)
        self.root.setLayout(root)

        self._build_filters_tab()
        self._build_charts_tab()
        self._build_summary_tab()
        self._build_fields_tab()
        self._build_decodes_tab()
        self._build_about_tab()
        self._set_idle_state()

    def _deferred_init(self) -> None:
        self.layer = self.layer_combo.currentLayer()
        self._on_layer_changed(self.layer)

    def _make_scrollable(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(content)
        return scroll

    # ------------------ Filters tab ------------------
    def _default_last_full_10y_range(self) -> Tuple[QDate, QDate]:
        today = QDate.currentDate()
        end_year = today.year() - 1
        end = QDate(end_year, 12, 31)
        start = QDate(end_year - 9, 1, 1)
        return start, end

    def _build_filters_tab(self) -> None:
        root = QVBoxLayout()
        root.setSpacing(8)

        self.chk_use_date = QCheckBox("Filter by date range")
        self.chk_use_date.setChecked(True)

        self.date_start = QDateEdit()
        self.date_end = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_end.setCalendarPopup(True)
        self.date_start.dateChanged.connect(self._update_active_filters_summary)
        self.date_end.dateChanged.connect(self._update_active_filters_summary)

        dstart, dend = self._default_last_full_10y_range()
        self.date_start.setDate(dstart)
        self.date_end.setDate(dend)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Start:"))
        date_row.addWidget(self.date_start)
        date_row.addSpacing(12)
        date_row.addWidget(QLabel("End:"))
        date_row.addWidget(self.date_end)
        date_row.addStretch(1)

        self.chk_selection_only = QCheckBox("Scope = map selection (recommended)")
        self.chk_selection_only.setChecked(True)

        self.chk_select_filtered = QCheckBox("Select filtered features on map")
        self.chk_select_filtered.setChecked(False)
        self.chk_use_date.stateChanged.connect(self._update_active_filters_summary)

        controls = QVBoxLayout()
        controls.setSpacing(4)
        controls.addWidget(self.chk_use_date)
        controls.addLayout(date_row)
        controls.addWidget(self.chk_selection_only)
        controls.addWidget(self.chk_select_filtered)

        # filter boxes arranged in 2 columns via splitter
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        right = QWidget()
        left_l = QVBoxLayout()
        right_l = QVBoxLayout()
        left_l.setSpacing(8)
        right_l.setSpacing(8)

        self.filter_boxes: Dict[str, CheckListFilterBox] = {}
        half = (len(FILTER_CONCEPTS) + 1) // 2
        for idx, (concept, title) in enumerate(FILTER_CONCEPTS):
            box = CheckListFilterBox(title)
            box.list.itemChanged.connect(self._on_filter_changed)
            self.filter_boxes[concept] = box
            (left_l if idx < half else right_l).addWidget(box)

        left_l.addStretch(1)
        right_l.addStretch(1)
        left.setLayout(left_l)
        right.setLayout(right_l)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.apply_filters)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self._reset_all_filters)

        self.btn_values_decodes = QPushButton("Use decode values")
        self.btn_values_decodes.clicked.connect(lambda: self._populate_filter_values(source="decodes"))

        self.btn_values_selection = QPushButton("Load values from selection")
        self.btn_values_selection.clicked.connect(lambda: self._populate_filter_values(source="selection"))

        self.btn_values_layer = QPushButton("Load values from layer (may be slow)")
        self.btn_values_layer.clicked.connect(lambda: self._populate_filter_values(source="layer"))

        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_reset)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.btn_values_decodes)
        btn_row.addWidget(self.btn_values_selection)
        btn_row.addWidget(self.btn_values_layer)
        btn_row.addStretch(1)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#555;")

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)

        filters_content = QWidget()
        filters_layout = QVBoxLayout()
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)
        filters_layout.addWidget(splitter)
        filters_layout.addStretch(1)
        filters_content.setLayout(filters_layout)

        root.addLayout(controls)
        root.addLayout(btn_row)
        root.addWidget(divider)
        root.addWidget(self._make_scrollable(filters_content), 1)
        root.addWidget(self.lbl_status)

        tab_layout = QVBoxLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addLayout(root)
        self.tab_filters.setLayout(tab_layout)

    def _on_filter_changed(self, *_):
        self._update_active_filters_summary()
        # Debounce auto-apply only when selection scope is active and there is a selection.
        if self.layer is None:
            return
        if self.chk_selection_only.isChecked() and self.layer.selectedFeatureCount() > 0:
            QTimer.singleShot(150, self.apply_filters)

    def _date_intent(self) -> bool:
        if not self.chk_use_date.isChecked():
            return False
        dstart, dend = self._default_last_full_10y_range()
        return self.date_start.date() != dstart or self.date_end.date() != dend

    def _category_intent(self) -> bool:
        return any(bool(box.selected_codes()) for box in self.filter_boxes.values())

    # ------------------ Values population ------------------
    def _code_counts_for_concept(self, concept_key: str) -> Dict[str, int]:
        """Count occurrences of raw codes for a concept within the current matched rows."""
        field_name = self.field_map.get(concept_key)
        if not field_name:
            return {}
        counts: Dict[str, int] = {}
        for r in self.filtered_rows or []:
            raw_val = r.get(field_name)
            if is_blank(raw_val):
                continue
            raw = safe_str(raw_val).strip()
            counts[raw] = counts.get(raw, 0) + 1
        return counts

    def _refresh_filter_counts(self) -> None:
        """Update checklist labels to show decode label plus count from matched rows."""
        for concept_key, box in self.filter_boxes.items():
            counts = self._code_counts_for_concept(concept_key)
            box.list.blockSignals(True)
            for i in range(box.list.count()):
                it = box.list.item(i)
                code = safe_str(it.data(Qt.UserRole)).strip()
                lab = self.decodes.decode(concept_key, code)
                it.setText(f"{lab} ({counts.get(code, 0)})")
            box.list.blockSignals(False)

    def _normalize_label_for_match(self, label: str) -> str:
        """Normalize a chart label so it can be matched back to decode labels."""
        text = safe_str(label).replace("\n", " ")
        text = re.sub(r"\s*\(\s*[\d,]+\s*\)\s*$", "", text)  # strip trailing count suffix
        text = " ".join(text.split())  # collapse whitespace
        return text.strip()

    def _resolve_codes_from_label(self, concept_key: str, label: str) -> List[str]:
        """Resolve chart label back to one or more decode codes for a concept."""
        mapping = self.decodes.mapping(concept_key)
        if not mapping:
            return []

        target = self._normalize_label_for_match(label)
        if not target:
            return []

        normalized = {code: self._normalize_label_for_match(lab) for code, lab in mapping.items()}

        def match_codes(predicate) -> List[str]:
            return [code for code, norm in normalized.items() if predicate(norm)]

        # Exact first, then case-insensitive, then prefix/startswith fallback.
        exact = match_codes(lambda norm: norm == target)
        if exact:
            return exact

        target_lower = target.lower()
        insensitive = match_codes(lambda norm: norm.lower() == target_lower)
        if insensitive:
            return insensitive

        fuzzy = match_codes(lambda norm: norm.lower().startswith(target_lower) or target_lower.startswith(norm.lower()))
        if fuzzy:
            return fuzzy

        # Fallback: match codes directly if labels are missing.
        direct = [code for code in mapping.keys() if self._normalize_label_for_match(code).lower() == target_lower]
        if direct:
            return direct

        box = self.filter_boxes.get(concept_key)
        if box is not None:
            from_items: List[str] = []
            for i in range(box.list.count()):
                it = box.list.item(i)
                item_label = self._normalize_label_for_match(it.text())
                if item_label.lower() == target_lower:
                    code = safe_str(it.data(Qt.UserRole)).strip()
                    if code or code == "":
                        from_items.append(code)
            if from_items:
                return from_items

        if target_lower in {"unknown", "unknown / blank", "unknown/blank", "blank"}:
            return [""]

        return []

    def _apply_category_label(self, concept_key: str, label: str, additive: bool) -> bool:
        """Apply/toggle checklist selections for a concept from a chart click."""
        box = self.filter_boxes.get(concept_key)
        if box is None:
            return False

        codes = {safe_str(c).strip() for c in self._resolve_codes_from_label(concept_key, label) if c is not None}
        if not codes:
            return False

        changed = False
        box.list.blockSignals(True)

        matches = []
        for i in range(box.list.count()):
            it = box.list.item(i)
            code = safe_str(it.data(Qt.UserRole)).strip()
            if code in codes:
                matches.append(it)

        if not matches:
            box.list.blockSignals(False)
            return False

        if not additive:
            for i in range(box.list.count()):
                it = box.list.item(i)
                if it in matches:
                    continue
                if it.checkState() != Qt.Unchecked:
                    it.setCheckState(Qt.Unchecked)
                    changed = True

        # Additive = add only; non-additive = replace selection. Never toggle off.
        for it in matches:
            if it.checkState() != Qt.Checked:
                it.setCheckState(Qt.Checked)
                changed = True

        box.list.blockSignals(False)
        return changed

    def _update_active_filters_summary(self) -> None:
        lines: List[str] = []

        if self.chk_use_date.isChecked() and self._date_intent():
            ds = self.date_start.date()
            de = self.date_end.date()
            lines.append(f"Date: {ds.toString('yyyy-MM-dd')} -> {de.toString('yyyy-MM-dd')}")

        for concept_key, box in self.filter_boxes.items():
            codes = box.selected_codes()
            if not codes:
                continue
            labels = {self.decodes.decode(concept_key, c) for c in codes}
            title = self._concept_titles.get(concept_key, concept_key)
            lines.append(f"{title}: {', '.join(sorted(labels, key=lambda s: s.lower()))}")

        if not lines:
            self.lbl_active_filters.setText("No filters applied")
        else:
            bullet_lines = "\n".join([f"- {t}" for t in lines])
            self.lbl_active_filters.setText(bullet_lines)

    def _filter_by_category(self, concept_key: str, label: str, additive: bool) -> None:
        """Apply chart-driven category filtering without changing the active tab."""
        # Special-case env combo to drive both env1/env2 filters.
        if concept_key == "env_combo":
            base = self._normalize_label_for_match(label)
            parts = [p.strip() for p in base.split("+")]
            if len(parts) >= 2:
                updated = False
                updated = self._apply_category_label("env1", parts[0], additive) or updated
                updated = self._apply_category_label("env2", parts[1], additive) or updated
                if updated:
                    self._update_active_filters_summary()
                    QTimer.singleShot(50, self.apply_filters)
            return

        if self._apply_category_label(concept_key, label, additive):
            self._update_active_filters_summary()
            QTimer.singleShot(50, self.apply_filters)

    def _populate_filter_values(self, source: str) -> None:
        if self.layer is None:
            return

        # cache checked state so we can keep it across reloads
        for ck, box in self.filter_boxes.items():
            self._checked_cache[ck] = box.selected_codes()

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
                    QMessageBox.information(self, "Collision Analytics", "No selected features in map.")
                    return
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
                    # fallback to decodes if provider doesn't support uniqueValues
                    codes.update(self.decodes.mapping(concept_key).keys())

            # Stable UI ordering by decoded label
            counts = self._code_counts_for_concept(concept_key)
            def label_for(code: str) -> str:
                lab = self.decodes.decode(concept_key, code)
                return f"{lab} ({counts.get(code, 0)})"

            items = sorted([(c, label_for(c)) for c in codes], key=lambda t: t[1].lower())
            box.setTitle(box.title().split(" (")[0])
            box.set_items(items, checked=self._checked_cache.get(concept_key, set()))
        self._refresh_filter_counts()

    # ------------------ Filtering ------------------
    def _build_spec(self) -> FilterSpec:
        selected_fids = set(self.layer.selectedFeatureIds()) if self.layer else set()

        category_codes: Dict[str, Set[str]] = {k: box.selected_codes() for k, box in self.filter_boxes.items()}

        date_field = self.field_map.get("date")
        qds = self.date_start.date()
        qde = self.date_end.date()
        return FilterSpec(
            selection_only=self.chk_selection_only.isChecked(),
            selected_fids=selected_fids,
            date_enabled=self.chk_use_date.isChecked(),
            date_field=date_field if date_field else None,
            date_start=date(qds.year(), qds.month(), qds.day()),
            date_end=date(qde.year(), qde.month(), qde.day()),
            category_codes=category_codes,
            field_map=self.field_map,
        )

    def _needed_fields(self, spec: FilterSpec) -> List[str]:
        layer_fields = {f.name() for f in self.layer.fields()}
        needed: Set[str] = set()

        # Used by filters
        if spec.date_enabled and spec.date_field and spec.date_field in layer_fields:
            needed.add(spec.date_field)

        for concept_key, selected in spec.category_codes.items():
            if not selected:
                continue
            fname = self.field_map.get(concept_key)
            if fname and fname in layer_fields:
                needed.add(fname)

        # Used by results
        for k, fname in self.field_map.items():
            if fname and fname in layer_fields:
                needed.add(fname)

        return sorted(needed)

    def _apply_filter_results(self, fids: List[int], rows: List[Dict[str, Any]], total_count: int) -> None:
        self.filtered_fids = fids
        self.filtered_rows = rows

        if self.chk_select_filtered.isChecked() and self.layer is not None:
            self.layer.selectByIds(fids)

        self._refresh_filter_counts()
        self.lbl_status.setText(f"Matched {len(fids)} of {total_count} features.")

        self._update_results_view()
        self._update_active_filters_summary()

    def apply_filters(self) -> None:
        if self.layer is None:
            return

        spec = self._build_spec()
        dstart, dend = self._default_last_full_10y_range()
        default_start = date(dstart.year(), dstart.month(), dstart.day())
        default_end = date(dend.year(), dend.month(), dend.day())

        # UX: selection-only + no selection + no intent => idle
        if spec.selection_only and not spec.selected_fids and not spec.has_any_intent(default_start, default_end):
            self.filtered_fids = []
            self.filtered_rows = []
            self._refresh_filter_counts()
            self._set_idle_state()
            self.lbl_status.setText("Idle: select features on map or set a filter, then Apply.")
            return

        # UX: selection-only + no selection but intent => inform user we're scanning layer
        if spec.selection_only and not spec.selected_fids and spec.has_any_intent(default_start, default_end):
            QMessageBox.information(
                self,
                "Collision Analytics",
                "No map selection, but filters are set.\n\n"
                "Running analysis on the whole layer for the active filters."
            )

        feature_count = self.layer.featureCount()
        needed = self._needed_fields(spec)

        if feature_count >= BACKGROUND_FILTER_THRESHOLD:
            # Offload heavy filtering to a background task; UI updates happen on completion.
            task = FilterTask(self.layer, spec, needed)
            task.feature_count = feature_count
            task.taskCompleted.connect(lambda _result=None, t=task: self._on_filter_complete(t))
            task.taskTerminated.connect(lambda *_, t=task: self._on_filter_failed(t))
            self._active_filter_task = task
            self.lbl_status.setText(f"Filtering {feature_count:,} collisions in background...")
            QgsApplication.taskManager().addTask(task)
            return

        engine = FilterEngine(self.layer)
        fids, rows = engine.apply(spec, needed)

        self._apply_filter_results(fids, rows, feature_count)
        self._update_active_filters_summary()

    def _on_filter_complete(self, task: FilterTask) -> None:
        self._active_filter_task = None

        if self.layer is None or task.layer != self.layer:
            self.lbl_status.setText("Layer changed during filtering; results ignored.")
            return

        if task.exception:
            self._on_filter_failed(task)
            return

        total_count = getattr(task, "feature_count", self.layer.featureCount())
        self._apply_filter_results(task.filtered_fids, task.filtered_rows, total_count)

    def _on_filter_failed(self, task: FilterTask) -> None:
        self._active_filter_task = None
        exc = task.exception or Exception("Filtering task failed.")
        QgsMessageLog.logMessage(str(exc), "Collision Analytics", Qgis.Critical)
        self.lbl_status.setText(f"Filtering failed: {exc}")

    def _reset_all_filters(self) -> None:
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
        self._refresh_filter_counts()
        self._set_idle_state()
        self.lbl_status.setText("")
        self._update_active_filters_summary()
        self.apply_filters()

    # ------------------ Charts / Summary tabs ------------------
    def _build_charts_tab(self) -> None:
        root = QVBoxLayout()

        top = QHBoxLayout()
        self.btn_apply_results = QPushButton("Apply filters / update selection")
        self.btn_apply_results.clicked.connect(self._reset_all_filters)
        self.btn_export_csv = QPushButton("Export summary CSV")
        self.btn_export_csv.clicked.connect(self.export_summary_csv)
        self.btn_export_features_csv = QPushButton("Export filtered features CSV")
        self.btn_export_features_csv.clicked.connect(self.export_filtered_features_csv)

        self.btn_export_dashboard_png = QPushButton("Export dashboard PNG")
        self.btn_export_dashboard_png.clicked.connect(self.export_dashboard_png)

        top.addWidget(self.btn_apply_results)
        top.addSpacing(12)
        top.addWidget(self.btn_export_csv)
        top.addWidget(self.btn_export_features_csv)
        top.addWidget(self.btn_export_dashboard_png)
        top.addStretch(1)
        root.addLayout(top)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Top N:"))
        self.cbo_top_n = QComboBox()
        self.cbo_top_n.addItems(["8", "12", "15", "20"])
        self.cbo_top_n.setCurrentText(str(self.top_n_default))
        self.cbo_top_n.currentIndexChanged.connect(self._update_results_view)

        self.chk_value_labels = QCheckBox("Show value labels")
        self.chk_value_labels.setChecked(True)
        self.chk_value_labels.stateChanged.connect(self._update_results_view)

        ctl.addWidget(self.cbo_top_n)
        ctl.addSpacing(10)
        ctl.addWidget(self.chk_value_labels)
        ctl.addStretch(1)
        root.addLayout(ctl)

        # ensure attribute exists even when charts are disabled
        self.chart_cards: List[charts_mod.ChartCard] = []

        if charts_mod.FigureCanvas is None:
            msg = QLabel("matplotlib is not available in this QGIS Python environment.\nCharts are disabled.")
            msg.setWordWrap(True)
            root.addWidget(msg)
            self.tab_charts.setLayout(root)
            return

        self.dashboard_scroll = QScrollArea()
        self.dashboard_scroll.setWidgetResizable(True)

        self.dashboard_root = QWidget()
        self.dashboard_vbox = QVBoxLayout()
        self.dashboard_vbox.setContentsMargins(8, 8, 8, 8)
        self.dashboard_vbox.setSpacing(10)
        self.dashboard_root.setLayout(self.dashboard_vbox)
        self.dashboard_scroll.setWidget(self.dashboard_root)

        root.addWidget(self.dashboard_scroll, 1)
        self.tab_charts.setLayout(root)

        self._init_dashboard_charts()

    def _make_kpi_card(self, title: str) -> Tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #d6d6d6; border-radius: 4px; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        frame.setLayout(layout)

        value = QLabel("n/a")
        value.setStyleSheet(self.kpi_value_style)
        title_label = QLabel(title)
        title_label.setStyleSheet(self.kpi_label_style)

        layout.addWidget(value)
        layout.addWidget(title_label)
        return frame, value

    def _make_section_header(self, title: str) -> QLabel:
        label = QLabel(title)
        label.setStyleSheet(self.summary_header_style)
        return label

    def _add_grid_row(self, grid: QGridLayout, row: int, title: str, value_label: QLabel) -> None:
        label = QLabel(title)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(label, row, 0)
        grid.addWidget(value_label, row, 1)

    def _set_kpi_value(self, label: QLabel, value: str, accent: Optional[str] = None) -> None:
        style = self.kpi_value_style
        if accent:
            style = f"{style} color: {accent};"
        label.setStyleSheet(style)
        label.setText(value)

    def _set_risk_flags(self, flags: List[str], empty_text: str) -> None:
        for label in self.risk_flag_labels:
            label.setVisible(False)
        self.risk_flag_empty.setVisible(False)

        if not flags:
            self.risk_flag_empty.setText(empty_text)
            self.risk_flag_empty.setVisible(True)
            return

        for idx, text in enumerate(flags[: len(self.risk_flag_labels)]):
            label = self.risk_flag_labels[idx]
            label.setText(text)
            label.setVisible(True)

    def _fill_top_panel(
        self,
        rows: List[Tuple[QLabel, QLabel]],
        pairs: List[Tuple[str, int]],
        empty_text: str = "None",
    ) -> None:
        if not pairs:
            for idx, (name, count) in enumerate(rows):
                if idx == 0:
                    name.setText(empty_text)
                    count.setText("")
                    name.setVisible(True)
                    count.setVisible(False)
                else:
                    name.setVisible(False)
                    count.setVisible(False)
            return

        for idx, (name, count) in enumerate(rows):
            if idx < len(pairs):
                label, value = pairs[idx]
                name.setText(str(label))
                count.setText(str(value))
                name.setVisible(True)
                count.setVisible(True)
            else:
                name.setVisible(False)
                count.setVisible(False)

    def _make_top_panel(self, title: str, rows: int = 5) -> Tuple[QFrame, List[Tuple[QLabel, QLabel]]]:
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #e0e0e0; border-radius: 4px; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        frame.setLayout(layout)

        header = QLabel(title)
        header.setStyleSheet(self.summary_header_style)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)
        layout.addLayout(grid)

        row_labels: List[Tuple[QLabel, QLabel]] = []
        for row in range(rows):
            name = QLabel()
            count = QLabel()
            name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            count.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(name, row, 0)
            grid.addWidget(count, row, 1)
            row_labels.append((name, count))

        return frame, row_labels

    def _build_summary_tab(self) -> None:
        root = QVBoxLayout()
        root.setSpacing(8)

        self.kpi_value_style = "font-size: 22px; font-weight: 600;"
        self.kpi_label_style = "color: #555;"
        self.summary_header_style = "font-weight: 600; font-size: 12px;"

        kpi_row = QWidget()
        kpi_layout = QHBoxLayout()
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(8)
        kpi_row.setLayout(kpi_layout)

        kpi_total, self.kpi_total_value = self._make_kpi_card("Filtered collisions")
        kpi_fatal, self.kpi_fatal_value = self._make_kpi_card("Fatal collisions")
        kpi_severe, self.kpi_severe_value = self._make_kpi_card("Severe share (Fatal + Injury)")

        kpi_layout.addWidget(kpi_total)
        kpi_layout.addWidget(kpi_fatal)
        kpi_layout.addWidget(kpi_severe)
        kpi_layout.addStretch(1)

        root.addWidget(kpi_row)

        summary_container = QWidget()
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(4, 4, 4, 4)
        summary_layout.setSpacing(12)
        summary_container.setLayout(summary_layout)

        self.summary_status = QLabel()
        self.summary_status.setWordWrap(True)
        self.summary_status.setStyleSheet("color: #555;")
        summary_layout.addWidget(self.summary_status)

        summary_layout.addWidget(self._make_section_header("Severity breakdown"))
        sev_grid = QGridLayout()
        sev_grid.setHorizontalSpacing(20)
        sev_grid.setVerticalSpacing(6)
        self.sev_fatal_value = QLabel("n/a")
        self.sev_fatal_value.setStyleSheet("font-weight: 600;")
        self.sev_injury_value = QLabel("n/a")
        self.sev_pdo_value = QLabel("n/a")
        self.sev_unknown_value = QLabel("n/a")
        self._add_grid_row(sev_grid, 0, "Fatal", self.sev_fatal_value)
        self._add_grid_row(sev_grid, 1, "Injury", self.sev_injury_value)
        self._add_grid_row(sev_grid, 2, "PDO", self.sev_pdo_value)
        self._add_grid_row(sev_grid, 3, "Unknown / Blank", self.sev_unknown_value)
        summary_layout.addLayout(sev_grid)

        summary_layout.addWidget(self._make_section_header("Exposure totals"))
        exp_grid = QGridLayout()
        exp_grid.setHorizontalSpacing(20)
        exp_grid.setVerticalSpacing(6)
        self.exp_vehicles_value = QLabel("n/a")
        self.exp_persons_value = QLabel("n/a")
        self.exp_drivers_value = QLabel("n/a")
        self.exp_occupants_value = QLabel("n/a")
        self.exp_pedestrians_value = QLabel("n/a")
        self._add_grid_row(exp_grid, 0, "Vehicles", self.exp_vehicles_value)
        self._add_grid_row(exp_grid, 1, "Persons", self.exp_persons_value)
        self._add_grid_row(exp_grid, 2, "Drivers", self.exp_drivers_value)
        self._add_grid_row(exp_grid, 3, "Occupants", self.exp_occupants_value)
        self._add_grid_row(exp_grid, 4, "Pedestrians", self.exp_pedestrians_value)
        summary_layout.addLayout(exp_grid)

        risk_frame = QFrame()
        risk_frame.setStyleSheet(
            "QFrame { border: 1px solid #f0d0d0; border-radius: 4px; background: #fff7f7; }"
        )
        risk_layout = QVBoxLayout()
        risk_layout.setContentsMargins(8, 8, 8, 8)
        risk_layout.setSpacing(6)
        risk_frame.setLayout(risk_layout)
        risk_layout.addWidget(self._make_section_header("Risk flags"))

        self.risk_flags_layout = QVBoxLayout()
        self.risk_flags_layout.setSpacing(4)
        risk_layout.addLayout(self.risk_flags_layout)

        self.risk_flag_labels = []
        for _ in range(3):
            label = QLabel()
            label.setWordWrap(True)
            label.setStyleSheet("color: #b00020;")
            self.risk_flags_layout.addWidget(label)
            self.risk_flag_labels.append(label)

        self.risk_flag_empty = QLabel()
        self.risk_flag_empty.setWordWrap(True)
        self.risk_flag_empty.setStyleSheet("color: #2e7d32;")
        self.risk_flags_layout.addWidget(self.risk_flag_empty)

        summary_layout.addWidget(risk_frame)

        summary_layout.addWidget(self._make_section_header("Top contributors"))
        top_container = QWidget()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        top_container.setLayout(top_layout)

        self.top_panels: Dict[str, List[Tuple[QLabel, QLabel]]] = {}
        impact_panel, impact_rows = self._make_top_panel("Impact type")
        location_panel, location_rows = self._make_top_panel("Accident location")
        muni_panel, muni_rows = self._make_top_panel("Municipality")
        self.top_panels["impact_type"] = impact_rows
        self.top_panels["accident_location"] = location_rows
        self.top_panels["municipality"] = muni_rows

        top_layout.addWidget(impact_panel)
        top_layout.addWidget(location_panel)
        top_layout.addWidget(muni_panel)
        summary_layout.addWidget(top_container)

        root.addWidget(self._make_scrollable(summary_container), 1)
        self.tab_summary.setLayout(root)

    def _init_dashboard_charts(self) -> None:
        # clear
        while self.dashboard_vbox.count():
            item = self.dashboard_vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        self.chart_cards: List[charts_mod.ChartCard] = []

        sections = [
            ("Temporal (by accident class)", [
                ("Collisions by year (by accident class)", self._chart_year_by_class),
                ("Collisions by month (by accident class)", self._chart_month_by_class),
                ("Collisions by day of week (by accident class)", self._chart_dow_by_class),
                ("Collisions by hour of day (by accident class)", self._chart_hour_by_class),
            ]),
            ("Core breakdowns", [
                ("Accident class (severity)", lambda ax, **k: self._chart_category(ax, "accident_class", **k)),
                ("Impact type by accident class", self._chart_impact_by_class),
                ("Environment condition 1", lambda ax, **k: self._chart_category(ax, "env1", **k)),
                ("Environment condition 2", lambda ax, **k: self._chart_category(ax, "env2", **k)),
                ("Environment combos (Env1 + Env2, non-null/0)", self._chart_env_combo),
                ("Lighting", lambda ax, **k: self._chart_category(ax, "light", **k)),
            ]),
            ("Prioritization", [
                ("Pareto: Impact type concentration", self._chart_pareto_impact),
            ]),
            ("Other charts", [
                ("Location type", lambda ax, **k: self._chart_category(ax, "location_type", **k)),
                ("Municipality", lambda ax, **k: self._chart_category(ax, "municipality", **k)),
                ("Accident location context", lambda ax, **k: self._chart_category(ax, "accident_location", **k)),
                ("Impact location", lambda ax, **k: self._chart_category(ax, "impact_location", **k)),
                ("Traffic control", lambda ax, **k: self._chart_category(ax, "traffic_control", **k)),
                ("Traffic control condition", lambda ax, **k: self._chart_category(ax, "traffic_control_condition", **k)),
                ("Road jurisdiction", lambda ax, **k: self._chart_category(ax, "road_jurisdiction", **k)),
            ]),
        ]

        for section_title, charts in sections:
            sec = QGroupBox(section_title)
            sec_l = QVBoxLayout()
            sec.setLayout(sec_l)

            for title, render in charts:
                box = QGroupBox(title)
                box_l = QVBoxLayout()
                box.setLayout(box_l)

                fig = charts_mod.Figure(figsize=(9.0, 3.2))
                canvas = charts_mod.FigureCanvas(fig)
                canvas.setMinimumHeight(self.chart_height_default)
                canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                box_l.addWidget(canvas)

                sec_l.addWidget(box)
                self.chart_cards.append(charts_mod.ChartCard(title=title, figure=fig, canvas=canvas, render_fn=render))

            self.dashboard_vbox.addWidget(sec)

        self.dashboard_vbox.addStretch(1)

    def _set_idle_state(self) -> None:
        if charts_mod.FigureCanvas is not None and hasattr(self, "chart_cards"):
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

        if hasattr(self, "summary_status"):
            self.summary_status.setText(
                "Ready. Default scope is map selection. Select points and click Apply, or disable selection scope."
            )
            self.summary_status.setVisible(True)

            self._set_kpi_value(self.kpi_total_value, "n/a")
            self._set_kpi_value(self.kpi_fatal_value, "n/a")
            self._set_kpi_value(self.kpi_severe_value, "n/a")

            self.sev_fatal_value.setText("n/a")
            self.sev_fatal_value.setStyleSheet("font-weight: 600;")
            self.sev_injury_value.setText("n/a")
            self.sev_pdo_value.setText("n/a")
            self.sev_unknown_value.setText("n/a")

            self.exp_vehicles_value.setText("n/a")
            self.exp_persons_value.setText("n/a")
            self.exp_drivers_value.setText("n/a")
            self.exp_occupants_value.setText("n/a")
            self.exp_pedestrians_value.setText("n/a")

            self._set_risk_flags([], "No results yet")
            self._fill_top_panel(self.top_panels.get("impact_type", []), [], "No data")
            self._fill_top_panel(self.top_panels.get("accident_location", []), [], "No data")
            self._fill_top_panel(self.top_panels.get("municipality", []), [], "No data")

        self._update_active_filters_summary()

    def _disconnect_chart_click(self, canvas) -> None:
        cid = getattr(canvas, "_collision_click_cid", None)
        if cid is None:
            return
        try:
            canvas.mpl_disconnect(cid)
        except Exception:
            pass
        canvas._collision_click_cid = None

    def _install_chart_click(self, ax, canvas, concept_key: str) -> None:
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

            self._filter_by_category(concept_key, label, additive)

        self._disconnect_chart_click(canvas)
        try:
            canvas._collision_click_cid = canvas.mpl_connect("button_press_event", handler)
        except Exception:
            pass

    def _decode(self, concept_key: str, raw: Any) -> str:
        return self.decodes.decode(concept_key, raw)

    def _update_results_view(self) -> None:
        if not hasattr(self, "summary_status"):
            return

        rows = self.filtered_rows or []
        total = len(rows)

        if total == 0:
            self._set_idle_state()
            return

        top_n = int(self.cbo_top_n.currentText())
        show_labels = self.chk_value_labels.isChecked()

        fm = self.field_map

        def sum_field(concept: str) -> float:
            field = fm.get(concept)
            if not field:
                return 0.0
            s = 0.0
            for r in rows:
                try:
                    v = float(r.get(field) or 0)
                except Exception:
                    v = 0.0
                s += v
            return s

        # severity
        sev_field = fm.get("accident_class")
        sev_counts: Dict[str, int] = {}
        if sev_field:
            from collections import Counter
            c = Counter()
            for r in rows:
                raw = safe_str(r.get(sev_field)).strip()
                lab = self._decode("accident_class", raw) if raw else "Unknown / blank"
                c[lab] += 1
            sev_counts = dict(c)

        fatal = sev_counts.get("Fatal", 0)
        injury = sev_counts.get("Injury", 0)
        pdo = sev_counts.get("PDO", 0)
        unknown = sev_counts.get("Unknown", 0) + sev_counts.get("Unknown / blank", 0)
        severe = fatal + injury
        severe_rate = (severe / total * 100.0) if total else 0.0

        # heuristics
        flags: List[str] = []
        if fatal > 0:
            flags.append(f"[!] Fatal collisions present: {fatal} in subset")
        if severe_rate >= 20.0:
            flags.append(f"[!] High severe share: {severe_rate:.1f}% Fatal+Injury (>=20%)")
        if (unknown / total) >= 0.05:
            flags.append(f"[!] Data quality risk: {unknown} unknown/blank severity (>=5%)")

        # top contributors
        def top_list(concept_key: str, n: int) -> List[Tuple[str, int]]:
            field = fm.get(concept_key)
            if not field:
                return []
            from collections import Counter
            c = Counter()
            for r in rows:
                raw = safe_str(r.get(field)).strip()
                lab = self._decode(concept_key, raw) if raw else "Unknown / blank"
                c[lab] += 1
            return c.most_common(n)

        self.summary_status.setText("")
        self.summary_status.setVisible(False)

        self._set_kpi_value(self.kpi_total_value, str(total))
        fatal_accent = "#b00020" if fatal > 0 else None
        self._set_kpi_value(self.kpi_fatal_value, str(fatal), fatal_accent)
        severe_accent = "#b00020" if severe_rate >= 20.0 else None
        self._set_kpi_value(self.kpi_severe_value, f"{severe_rate:.1f}%", severe_accent)

        if fatal > 0:
            self.sev_fatal_value.setStyleSheet("font-weight: 600; color: #b00020;")
        else:
            self.sev_fatal_value.setStyleSheet("font-weight: 600;")
        self.sev_fatal_value.setText(str(fatal))
        self.sev_injury_value.setText(str(injury))
        self.sev_pdo_value.setText(str(pdo))
        self.sev_unknown_value.setText(str(unknown))

        self.exp_vehicles_value.setText(f"{sum_field('veh_cnt'):.0f}")
        self.exp_persons_value.setText(f"{sum_field('per_cnt'):.0f}")
        self.exp_drivers_value.setText(f"{sum_field('drv_cnt'):.0f}")
        self.exp_occupants_value.setText(f"{sum_field('occ_cnt'):.0f}")
        self.exp_pedestrians_value.setText(f"{sum_field('ped_cnt'):.0f}")

        self._set_risk_flags(flags, "No major flags triggered")
        self._fill_top_panel(self.top_panels.get("impact_type", []), top_list("impact_type", 5), "None")
        self._fill_top_panel(self.top_panels.get("accident_location", []), top_list("accident_location", 5), "None")
        self._fill_top_panel(self.top_panels.get("municipality", []), top_list("municipality", 5), "None")

        # charts
        if charts_mod.FigureCanvas is None:
            return

        for card in self.chart_cards:
            card.figure.clear()
            ax = card.figure.add_subplot(111)
            self._disconnect_chart_click(card.canvas)
            try:
                # Allow renderers to receive the canvas for click wiring.
                card.render_fn(ax, top_n=top_n, show_labels=show_labels, canvas=card.canvas)
            except TypeError:
                try:
                    card.render_fn(ax, canvas=card.canvas)
                except TypeError:
                    card.render_fn(ax)
            except Exception as e:
                ax.text(0.5, 0.5, f"Chart error:\n{e}", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
            card.figure.tight_layout()
            card.canvas.draw()

    # ---- chart adapter methods ----
    def _chart_year(self, ax, **_):
        charts_mod.render_trend_year(ax, self.filtered_rows, self.field_map.get("date"))

    def _chart_year_by_class(self, ax, show_labels: bool = True, **_):
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket="year",
            show_labels=show_labels,
        )

    def _chart_month_by_class(self, ax, show_labels: bool = True, **_):
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket="month",
            show_labels=show_labels,
        )

    def _chart_dow(self, ax, **_):
        charts_mod.render_day_of_week(ax, self.filtered_rows, self.field_map.get("date"))

    def _chart_dow_by_class(self, ax, show_labels: bool = True, **_):
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket="dow",
            show_labels=show_labels,
        )

    def _chart_hour(self, ax, **_):
        charts_mod.render_hour_of_day(ax, self.filtered_rows, self.field_map.get("date"))

    def _chart_hour_by_class(self, ax, show_labels: bool = True, **_):
        charts_mod.render_temporal_by_class(
            ax,
            self.filtered_rows,
            self.field_map.get("date"),
            self.field_map.get("accident_class"),
            lambda raw: self._decode("accident_class", raw),
            self.decodes.mapping("accident_class"),
            bucket="hour",
            show_labels=show_labels,
        )

    def _chart_category(self, ax, concept_key: str, top_n: int = 12, show_labels: bool = True, canvas=None, **_):
        field = self.field_map.get(concept_key)
        decode = lambda raw: self._decode(concept_key, raw)
        charts_mod.render_category(ax, self.filtered_rows, field, decode, top_n=top_n, show_labels=show_labels, include_blank=True)
        self._install_chart_click(ax, canvas, concept_key)

    def _chart_impact_by_class(self, ax, top_n: int = 12, show_labels: bool = True, canvas=None, **_):
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
        self._install_chart_click(ax, canvas, "impact_type")

    def _chart_env_combo(self, ax, top_n: int = 12, show_labels: bool = True, canvas=None, **_):
        f1 = self.field_map.get("env1")
        f2 = self.field_map.get("env2")
        d1 = lambda raw: self._decode("env1", raw)
        d2 = lambda raw: self._decode("env2", raw)
        charts_mod.render_env_combo(ax, self.filtered_rows, f1, f2, d1, d2, top_n=top_n, show_labels=show_labels)
        self._install_chart_click(ax, canvas, "env_combo")

    def _chart_pareto_impact(self, ax, top_n: int = 10, show_labels: bool = True, **_):
        field = self.field_map.get("impact_type")
        decode = lambda raw: self._decode("impact_type", raw)
        charts_mod.render_pareto(ax, self.filtered_rows, field, decode, top_n=top_n, show_labels=show_labels)

    # ------------------ Fields tab ------------------
    def _build_fields_tab(self) -> None:
        root = QVBoxLayout()

        hint = QLabel(
            "Map your layer fields to the plugin concepts.\n"
            "This keeps the plugin usable across different schemas."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self.field_selectors: Dict[str, QComboBox] = {}

        for key in DEFAULT_FIELD_MAP.keys():
            cb = QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(self._on_field_mapping_changed)
            self.field_selectors[key] = cb
            form.addRow(f"{key}:", cb)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_save_fields = QPushButton("Save field mapping")
        self.btn_save_fields.clicked.connect(self._save_field_map)
        self.btn_reset_fields = QPushButton("Reset to defaults")
        self.btn_reset_fields.clicked.connect(self._reset_field_map_defaults)
        btn_row.addWidget(self.btn_save_fields)
        btn_row.addWidget(self.btn_reset_fields)
        btn_row.addStretch(1)

        root.addLayout(btn_row)
        root.addStretch(1)

        content = QWidget()
        content.setLayout(root)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(self._make_scrollable(content))
        self.tab_fields.setLayout(tab_layout)

    def _populate_field_selectors(self) -> None:
        if self.layer is None:
            return
        names = [f.name() for f in self.layer.fields()]
        for key, cb in self.field_selectors.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")  # allow empty
            cb.addItems(names)
            mapped = self.field_map.get(key, "")
            if mapped in names:
                cb.setCurrentText(mapped)
            cb.blockSignals(False)

    def _on_field_mapping_changed(self, *_):
        for key, cb in self.field_selectors.items():
            name = cb.currentText().strip()
            if name:
                self.field_map[key] = name

    def _load_field_map(self) -> None:
        obj = load_json(self.settings, SETTINGS_FIELD_MAP_KEY, None)
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.field_map[str(k)] = str(v)

    def _save_field_map(self) -> None:
        save_json(self.settings, SETTINGS_FIELD_MAP_KEY, self.field_map)
        QMessageBox.information(self, "Collision Analytics", "Field mapping saved.")
        self._refresh_from_layer()

    def _reset_field_map_defaults(self) -> None:
        self.field_map = dict(DEFAULT_FIELD_MAP)
        self._save_field_map()

    # ------------------ Decodes tab ------------------
    def _build_decodes_tab(self) -> None:
        root = QVBoxLayout()

        hint = QLabel(
            "Decode tables map raw codes (e.g., 1, 2, 99) to labels.\n"
            "Edits are saved per-user. You can export/import JSON for sharing."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Horizontal)

        # left: group list
        from qgis.PyQt.QtWidgets import QListWidget, QLineEdit
        left = QWidget()
        left_l = QVBoxLayout()
        self.decode_search = QLineEdit()
        self.decode_search.setPlaceholderText("Filter decode groups")
        self.decode_search.textChanged.connect(self._filter_decode_groups)

        self.decode_group_list = QListWidget()
        self.decode_group_list.currentItemChanged.connect(self._on_decode_group_selected)

        left_l.addWidget(self.decode_search)
        left_l.addWidget(self.decode_group_list, 1)
        left.setLayout(left_l)

        # right: table editor
        right = QWidget()
        right_l = QVBoxLayout()

        self.decode_table = QTableWidget(0, 2)
        self.decode_table.setHorizontalHeaderLabels(["Code", "Label"])
        self.decode_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.decode_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.decode_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.decode_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed | QTableWidget.AnyKeyPressed
        )

        btn_row = QHBoxLayout()
        self.btn_decode_add = QPushButton("Add row")
        self.btn_decode_add.clicked.connect(self._decode_add_row)
        self.btn_decode_delete = QPushButton("Delete selected")
        self.btn_decode_delete.clicked.connect(self._decode_delete_selected)
        self.btn_decode_save = QPushButton("Save changes")
        self.btn_decode_save.clicked.connect(self._save_current_decode_group)
        self.btn_decode_reset_all = QPushButton("Reset ALL to defaults")
        self.btn_decode_reset_all.clicked.connect(self._reset_all_decodes)
        self.btn_decode_export = QPushButton("Export JSON")
        self.btn_decode_export.clicked.connect(self._export_decodes_json)
        self.btn_decode_import = QPushButton("Import JSON")
        self.btn_decode_import.clicked.connect(self._import_decodes_json)

        btn_row.addWidget(self.btn_decode_add)
        btn_row.addWidget(self.btn_decode_delete)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.btn_decode_save)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.btn_decode_import)
        btn_row.addWidget(self.btn_decode_export)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.btn_decode_reset_all)
        btn_row.addStretch(1)

        right_l.addWidget(self.decode_table, 1)
        right_l.addLayout(btn_row)
        right.setLayout(right_l)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        content = QWidget()
        content.setLayout(root)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(self._make_scrollable(content))
        self.tab_decodes.setLayout(tab_layout)

        self._populate_decode_group_list()

    # ------------------ About tab ------------------
    def _build_about_tab(self) -> None:
        root = QVBoxLayout()
        root.setSpacing(10)

        def add_section(title: str, lines: List[str]) -> None:
            header = QLabel(f"<b>{title}</b>")
            header.setWordWrap(True)
            header.setStyleSheet("font-size: 12pt;")
            root.addWidget(header)
            for line in lines:
                body = QLabel(line)
                body.setWordWrap(True)
                root.addWidget(body)
            root.addSpacing(8)

        add_section(
            "Plugin Information",
            [
                "<b>Name:</b> Collision Analytics",
                "<b>Description:</b> A QGIS plugin for exploratory analysis and practitioner-oriented interpretation of road collision data.",
            ],
        )

        add_section(
            "Author",
            [
                "<b>Name:</b> Shahram Almasi",
                "<b>Role:</b> Traffic Operations and Road Safety Engineer",
            ],
        )

        add_section(
            "Organisation",
            [
                "<b>Employer:</b> The Regional Municipality of Durham",
                "<b>Context:</b> Developed in support of transportation safety analysis and Vision Zero-aligned practice.",
            ],
        )

        disclaimer_text = (
            "This plugin is intended as a decision-support and exploratory analysis tool only. "
            "Results are dependent on the quality, completeness, and interpretation of the underlying data. "
            "Outputs from this tool do not constitute engineering design, legal findings, or official collision statistics. "
            "Users are responsible for applying appropriate professional judgment, standards, and review when interpreting results."
        )
        add_section("Disclaimer", [disclaimer_text])

        root.addStretch(1)
        content = QWidget()
        content.setLayout(root)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(content)
        self.tab_about.setLayout(tab_layout)

    def _populate_decode_group_list(self) -> None:
        self.decode_group_list.blockSignals(True)
        self.decode_group_list.clear()
        for key in self.decodes.keys():
            self.decode_group_list.addItem(key)
        self.decode_group_list.blockSignals(False)
        if self.decode_group_list.count() > 0 and self.decode_group_list.currentRow() < 0:
            self.decode_group_list.setCurrentRow(0)

    def _filter_decode_groups(self, text: str) -> None:
        t = (text or "").strip().lower()
        for i in range(self.decode_group_list.count()):
            it = self.decode_group_list.item(i)
            it.setHidden(False if not t else (t not in it.text().lower()))

    def _current_decode_group_key(self) -> Optional[str]:
        it = self.decode_group_list.currentItem()
        return it.text() if it else None

    def _on_decode_group_selected(self, current, previous) -> None:
        key = self._current_decode_group_key()
        if not key:
            self.decode_table.setRowCount(0)
            return
        mapping = self.decodes.mapping(key)

        def sort_key(code: str):
            try:
                return (0, float(code))
            except Exception:
                return (1, code)

        codes = sorted(mapping.keys(), key=sort_key)
        self.decode_table.blockSignals(True)
        self.decode_table.setRowCount(0)
        for code in codes:
            label = mapping.get(code, "")
            row = self.decode_table.rowCount()
            self.decode_table.insertRow(row)
            self.decode_table.setItem(row, 0, QTableWidgetItem(str(code)))
            self.decode_table.setItem(row, 1, QTableWidgetItem(str(label)))
        self.decode_table.blockSignals(False)

    def _decode_add_row(self) -> None:
        row = self.decode_table.rowCount()
        self.decode_table.insertRow(row)
        self.decode_table.setItem(row, 0, QTableWidgetItem(""))
        self.decode_table.setItem(row, 1, QTableWidgetItem(""))
        self.decode_table.setCurrentCell(row, 0)
        self.decode_table.editItem(self.decode_table.item(row, 0))

    def _decode_delete_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.decode_table.selectionModel().selectedRows()}, reverse=True)
        for r in rows:
            self.decode_table.removeRow(r)

    def _read_decode_table(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for r in range(self.decode_table.rowCount()):
            code_item = self.decode_table.item(r, 0)
            label_item = self.decode_table.item(r, 1)
            code = (code_item.text() if code_item else "").strip()
            label = (label_item.text() if label_item else "").strip()
            if not code:
                continue
            mapping[code] = label if label else code
        return mapping

    def _save_current_decode_group(self) -> None:
        key = self._current_decode_group_key()
        if not key:
            return
        self.decodes.set_mapping(key, self._read_decode_table())
        self.decodes.save()
        QMessageBox.information(self, "Collision Analytics", f"Saved decode group: {key}")
        self._populate_filter_values(source="decodes")

    def _reset_all_decodes(self) -> None:
        self.decodes.reset_to_defaults()
        self._populate_decode_group_list()
        self._populate_filter_values(source="decodes")
        QMessageBox.information(self, "Collision Analytics", "All decode groups reset to defaults.")

    def _export_decodes_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export decodes JSON", "", "JSON (*.json)")
        if not path:
            return
        obj = {k: self.decodes.mapping(k) for k in self.decodes.keys()}
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Collision Analytics", f"Exported:\n{path}")

    def _import_decodes_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import decodes JSON", "", "JSON (*.json)")
        if not path:
            return
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if not isinstance(obj, dict):
                raise ValueError("Expected {group: {code: label}}")
            for k, v in obj.items():
                if isinstance(v, dict):
                    self.decodes.set_mapping(str(k), {str(code): str(label) for code, label in v.items()})
            self.decodes.save()
            self._populate_decode_group_list()
            self._populate_filter_values(source="decodes")
            QMessageBox.information(self, "Collision Analytics", f"Imported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Import failed:\n{e}")

    # ------------------ Layer lifecycle ------------------
    def _on_layer_changed(self, layer) -> None:
        self.layer = layer
        self._refresh_from_layer()

    def _refresh_from_layer(self) -> None:
        if self.layer is None:
            self.filtered_fids = []
            self.filtered_rows = []
            self._set_idle_state()
            return

        self._populate_field_selectors()
        if self.chk_selection_only.isChecked() and self.layer.selectedFeatureCount() > 0:
            self._populate_filter_values(source="selection")
        else:
            self._populate_filter_values(source="decodes")

        # auto-run if selection scope + selection exists
        if self.chk_selection_only.isChecked() and self.layer.selectedFeatureCount() > 0:
            self.apply_filters()
        else:
            self.filtered_fids = []
            self.filtered_rows = []
            self._set_idle_state()

    # ------------------ Export ------------------
    def export_summary_csv(self) -> None:
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

        rows = [
            ("filtered_collisions", total),
            ("sum_involved_vehicles_cnt", sum_field("veh_cnt")),
            ("sum_involved_persons_cnt", sum_field("per_cnt")),
            ("sum_involved_drivers_cnt", sum_field("drv_cnt")),
            ("sum_involved_occupants_cnt", sum_field("occ_cnt")),
            ("sum_involved_pedestrians_cnt", sum_field("ped_cnt")),
            ("scope", "selection" if self.chk_selection_only.isChecked() else "layer"),
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            for k, v in rows:
                w.writerow([k, v])

        QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")

    def export_filtered_features_csv(self) -> None:
        """Export filtered collision features to CSV with raw and decoded values."""
        if not self.filtered_rows:
            QMessageBox.information(self, "Collision Analytics", "No filtered results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export filtered features CSV", "", "CSV (*.csv)")
        if not path:
            return

        # Collect all fields present in the filtered rows
        all_fields = set()
        for row in self.filtered_rows:
            all_fields.update(row.keys())
        all_fields = sorted(all_fields)

        # Map concepts to fields (inverse of field_map)
        field_to_concept: Dict[str, str] = {}
        for concept_key, field_name in self.field_map.items():
            if field_name in all_fields:
                field_to_concept[field_name] = concept_key

        # Build column headers: raw field names, plus decoded columns where applicable
        headers: List[str] = []
        # Track which concepts have decode tables available
        concepts_with_decodes = set(self.decodes.keys())

        # Add raw field columns and decoded columns
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
                    formatted_raw = raw_value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(raw_value, datetime) else raw_value.strftime("%Y-%m-%d")
                elif hasattr(raw_value, "toPyDateTime"):
                    # Handle QDateTime objects - more robust than isinstance check
                    try:
                        dt = raw_value.toPyDateTime()
                        formatted_raw = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        formatted_raw = safe_str(raw_value)
                elif hasattr(raw_value, "toPyDate"):
                    # Handle QDate objects - more robust than isinstance check
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
            QMessageBox.information(self, "Collision Analytics", f"Exported {len(csv_rows)} features to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Export failed:\n{e}")

    def export_dashboard_png(self) -> None:
        if charts_mod.Figure is None:
            QMessageBox.warning(self, "Collision Analytics", "Charts are not available (matplotlib missing).")
            return
        if not hasattr(self, "chart_cards") or not self.chart_cards:
            QMessageBox.information(self, "Collision Analytics", "No charts to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export dashboard PNG", "", "PNG (*.png)")
        if not path:
            return

        cols = 2
        cards = self.chart_cards
        rows = (len(cards) + cols - 1) // cols
        fig = charts_mod.Figure(figsize=(cols * 7.5, rows * 3.2))

        top_n = int(self.cbo_top_n.currentText())
        show_labels = self.chk_value_labels.isChecked()

        for idx, card in enumerate(cards):
            ax = fig.add_subplot(rows, cols, idx + 1)
            ax.set_title(card.title, fontsize=10)
            try:
                card.render_fn(ax, top_n=top_n, show_labels=show_labels)
            except Exception as e:
                ax.text(0.5, 0.5, f"Chart error:\n{e}", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()

        fig.tight_layout()
        fig.savefig(path, dpi=200)
        QMessageBox.information(self, "Collision Analytics", f"Saved:\n{path}")
