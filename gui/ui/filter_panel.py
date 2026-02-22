"""Filter Panel - Modern filter controls with collapsible sections."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt, QDate, QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsMessageLog, Qgis, QgsTask

from ...core.config import FILTER_CONCEPTS
from ...core.decodes import DecodeRegistry
from ...core.filters import FilterEngine, FilterSpec
from ...core.utils import safe_str, is_blank
from ..modern_widgets import (
    Badge,
    CheckListFilterBox,
    CollapsibleSection,
    Colors,
    EmptyState,
    KPICard,
    SegmentedControl,
    Typography,
)


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
        self.progress_pct = 0

    def run(self) -> bool:
        try:
            engine = FilterEngine(self.layer)
            total = self.layer.featureCount()
            processed = 0
            batch_size = 1000
            
            all_fids: List[int] = []
            all_rows: List[Dict[str, Any]] = []
            
            for batch_fids, batch_rows in engine.apply_batch(
                self.spec, 
                self.needed_fields,
                batch_size=batch_size,
                progress_callback=lambda p, t: self._update_progress(p, t)
            ):
                all_fids.extend(batch_fids)
                all_rows.extend(batch_rows)
                processed += batch_size
                self.progress_pct = min(99, int(100 * processed / max(total, 1)))
            
            self.filtered_fids = all_fids
            self.filtered_rows = all_rows
            return True
        except Exception as e:
            self.exception = e
            return False
    
    def _update_progress(self, processed: int, total: int):
        self.progress_pct = min(99, int(100 * processed / max(total, 1)))


class FilterPanel(QWidget):
    """Modern filter panel with collapsible sections and better organization."""
    
    filters_changed = None  # Callback: () -> None
    filters_applied = None  # Callback: (fids, rows, total_count) -> None
    status_changed = None   # Callback: (status, message) -> None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layer = None
        self.field_map: Dict[str, str] = {}
        self.decodes: Optional[DecodeRegistry] = None
        self.filter_boxes: Dict[str, CheckListFilterBox] = {}
        
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self._active_filter_task: Optional[FilterTask] = None
        
        self._checked_cache: Dict[str, Set[str]] = {}
        self._concept_titles: Dict[str, str] = {k: v for k, v in FILTER_CONCEPTS}
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build modern filter panel UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # ===== Quick Actions Toolbar =====
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)
        
        # ===== Active Filters Summary =====
        self.active_filters_card = self._build_active_filters_card()
        layout.addWidget(self.active_filters_card)
        
        # ===== Progress Bar (hidden by default) =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Processing: %p%")
        layout.addWidget(self.progress_bar)
        
        # ===== Filter Sections (Scrollable) =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameStyle(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        filter_container = QWidget()
        filter_container.setStyleSheet("background: transparent;")
        filter_layout = QVBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        
        # Date Range Section
        self.date_section = self._build_date_section()
        filter_layout.addWidget(self.date_section)
        
        # Scope Section
        self.scope_section = self._build_scope_section()
        filter_layout.addWidget(self.scope_section)
        
        # Category Filters Section (collapsible groups)
        self.category_section = self._build_category_section()
        filter_layout.addWidget(self.category_section, 1)
        
        filter_layout.addStretch(1)
        filter_container.setLayout(filter_layout)
        scroll.setWidget(filter_container)
        
        layout.addWidget(scroll, 1)
        self.setLayout(layout)
        
        self._ui_ready = True
    
    def _build_toolbar(self) -> QWidget:
        """Build quick actions toolbar."""
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            background-color: {Colors.BG_SECONDARY};
            border-radius: 8px;
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Primary action
        self.btn_apply = QPushButton("▶ Apply Filters")
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        self.btn_apply.clicked.connect(self.apply_filters)
        
        # Secondary actions
        self.btn_reset = QPushButton("↺ Reset")
        self.btn_reset.setToolTip("Clear all filters")
        self.btn_reset.clicked.connect(self.reset_all_filters)
        
        # Load values dropdown
        self.btn_load = QPushButton("Load Values ▼")
        self.btn_load.setToolTip("Load filter values from selection or layer")
        
        # Simple menu for load options
        from qgis.PyQt.QtWidgets import QMenu
        load_menu = QMenu(self)
        load_menu.addAction("From Selection", lambda: self._populate_filter_values("selection"))
        load_menu.addAction("From Layer", lambda: self._populate_filter_values("layer"))
        load_menu.addSeparator()
        load_menu.addAction("Use Decodes", lambda: self._populate_filter_values("decodes"))
        self.btn_load.setMenu(load_menu)
        
        layout.addWidget(self.btn_apply)
        layout.addWidget(self.btn_reset)
        layout.addStretch(1)
        layout.addWidget(self.btn_load)
        
        toolbar.setLayout(layout)
        return toolbar
    
    def _build_active_filters_card(self) -> QWidget:
        """Build active filters summary card."""
        card = QWidget()
        card.setStyleSheet(f"""
            background-color: {Colors.BG_SECONDARY};
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-radius: 8px;
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Header
        header = QHBoxLayout()
        header_label = QLabel("Active Filters")
        header_label.setStyleSheet(f"""
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SM}px;
            text-transform: uppercase;
        """)
        
        self.result_count = Badge("0 results", "default")
        
        header.addWidget(header_label)
        header.addStretch(1)
        header.addWidget(self.result_count)
        
        layout.addLayout(header)
        
        # Filter pills
        self.filters_container = QWidget()
        self.filters_layout = QHBoxLayout()
        self.filters_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_layout.setSpacing(6)
        self.filters_layout.addStretch(1)
        
        self.filters_container.setLayout(self.filters_layout)
        layout.addWidget(self.filters_container)
        
        # Empty state
        self.empty_filters_label = QLabel("No filters applied")
        self.empty_filters_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-style: italic;")
        self.empty_filters_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_filters_label)
        
        card.setLayout(layout)
        return card
    
    def _build_date_section(self) -> CollapsibleSection:
        """Build date range filter section."""
        section = CollapsibleSection("📅 Date Range", expanded=True)
        
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Enable checkbox
        self.chk_use_date = QCheckBox("Filter by date range")
        self.chk_use_date.setChecked(True)
        self.chk_use_date.stateChanged.connect(self._on_filter_changed)
        layout.addWidget(self.chk_use_date)
        
        # Date inputs
        date_row = QHBoxLayout()
        date_row.setSpacing(6)
        
        start_col = QVBoxLayout()
        start_label = QLabel("Start Date")
        start_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.XS}px;")
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.dateChanged.connect(self._on_filter_changed)
        start_col.addWidget(start_label)
        start_col.addWidget(self.date_start)
        
        end_col = QVBoxLayout()
        end_label = QLabel("End Date")
        end_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.XS}px;")
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.dateChanged.connect(self._on_filter_changed)
        end_col.addWidget(end_label)
        end_col.addWidget(self.date_end)
        
        date_row.addLayout(start_col, 1)
        date_row.addLayout(end_col, 1)
        
        layout.addLayout(date_row)
        
        # Preset buttons
        presets = QHBoxLayout()
        presets.setSpacing(6)
        
        presets_label = QLabel("Quick:")
        presets_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        
        self.btn_last_5y = QPushButton("5 years")
        self.btn_last_10y = QPushButton("10 years")
        self.btn_last_5y.setStyleSheet(f"padding: 4px 8px; font-size: {Typography.XS}px;")
        self.btn_last_10y.setStyleSheet(f"padding: 4px 8px; font-size: {Typography.XS}px;")
        
        self.btn_last_5y.clicked.connect(lambda: self._set_date_preset(5))
        self.btn_last_10y.clicked.connect(lambda: self._set_date_preset(10))
        
        presets.addWidget(presets_label)
        presets.addWidget(self.btn_last_5y)
        presets.addWidget(self.btn_last_10y)
        presets.addStretch(1)
        
        layout.addLayout(presets)
        
        # Set defaults
        dstart, dend = self._default_last_full_10y_range()
        self.date_start.setDate(dstart)
        self.date_end.setDate(dend)
        
        content.setLayout(layout)
        section.set_content(content)
        
        return section
    
    def _build_scope_section(self) -> CollapsibleSection:
        """Build scope and selection section."""
        section = CollapsibleSection("🎯 Scope & Selection", expanded=True)
        
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.chk_selection_only = QCheckBox("Limit to map selection")
        self.chk_selection_only.setChecked(True)
        self.chk_selection_only.setToolTip("Only analyze features selected on the map")
        self.chk_selection_only.stateChanged.connect(self._on_filter_changed)
        
        self.chk_select_filtered = QCheckBox("Select filtered features on map")
        self.chk_select_filtered.setChecked(False)
        self.chk_select_filtered.setToolTip("Update map selection to match filtered results")
        
        # Selection info
        self.selection_info = QLabel("No features selected on map")
        self.selection_info.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.XS}px;")
        
        layout.addWidget(self.chk_selection_only)
        layout.addWidget(self.selection_info)
        layout.addSpacing(8)
        layout.addWidget(self.chk_select_filtered)
        
        content.setLayout(layout)
        section.set_content(content)
        
        return section
    
    def _build_category_section(self) -> CollapsibleSection:
        """Build category filters section with two-column layout."""
        section = CollapsibleSection("🏷️ Category Filters", expanded=True)
        
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Search all filters
        search_row = QHBoxLayout()
        self.global_search = QLabel("🔍")
        self.global_search.setStyleSheet("font-size: 14px;")
        
        self.category_search = QLabel("Filter categories by typing in each box below")
        self.category_search.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.XS}px;")
        
        search_row.addWidget(self.global_search)
        search_row.addWidget(self.category_search)
        search_row.addStretch(1)
        
        layout.addLayout(search_row)
        
        # Two-column layout for filters
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER_DEFAULT};
            }}
        """)
        
        left_col = QWidget()
        right_col = QWidget()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        right_layout.setSpacing(6)
        
        # Distribute filters evenly
        half = (len(FILTER_CONCEPTS) + 1) // 2
        for idx, (concept, title) in enumerate(FILTER_CONCEPTS):
            box = CheckListFilterBox(title)
            box.list.itemChanged.connect(self._on_filter_changed)
            self.filter_boxes[concept] = box
            
            if idx < half:
                left_layout.addWidget(box)
            else:
                right_layout.addWidget(box)
        
        left_layout.addStretch(1)
        right_layout.addStretch(1)
        
        left_col.setLayout(left_layout)
        right_col.setLayout(right_layout)
        
        splitter.addWidget(left_col)
        splitter.addWidget(right_col)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 200])
        
        layout.addWidget(splitter, 1)
        
        content.setLayout(layout)
        section.set_content(content)
        
        return section
    
    def _default_last_full_10y_range(self) -> Tuple[QDate, QDate]:
        today = QDate.currentDate()
        end_year = today.year() - 1
        end = QDate(end_year, 12, 31)
        start = QDate(end_year - 9, 1, 1)
        return start, end
    
    def _set_date_preset(self, years: int):
        """Set date range to last N full years."""
        today = QDate.currentDate()
        end_year = today.year() - 1
        end = QDate(end_year, 12, 31)
        start = QDate(end_year - years + 1, 1, 1)
        
        self.date_start.setDate(start)
        self.date_end.setDate(end)
        self.chk_use_date.setChecked(True)
    
    def set_layer(self, layer, field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        """Set the current layer and refresh filter values."""
        self.layer = layer
        self.field_map = field_map
        self.decodes = decodes
        
        # Update selection info
        if layer:
            selected_count = layer.selectedFeatureCount()
            if selected_count > 0:
                self.selection_info.setText(f"{selected_count} features selected on map")
                self.selection_info.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS};")
            else:
                self.selection_info.setText("No features selected on map")
                self.selection_info.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        else:
            self.selection_info.setText("No layer selected")
            self.selection_info.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        
        if layer is None:
            self.reset_all_filters()
            return
        
        if self.chk_selection_only.isChecked() and layer.selectedFeatureCount() > 0:
            self._populate_filter_values(source="selection")
        else:
            self._populate_filter_values(source="decodes")
    
    def _on_filter_changed(self, *_) -> None:
        """Handle filter change - debounce auto-apply."""
        if not getattr(self, '_ui_ready', False):
            return
        
        self._update_active_filters_summary()
        
        if self.filters_changed:
            self.filters_changed()
        
        if self.layer is None:
            return
        
        # Auto-apply if selection-based
        if self.chk_selection_only.isChecked() and self.layer.selectedFeatureCount() > 0:
            QTimer.singleShot(150, self.apply_filters)
    
    def _date_intent(self) -> bool:
        if not self.chk_use_date.isChecked():
            return False
        dstart, dend = self._default_last_full_10y_range()
        return self.date_start.date() != dstart or self.date_end.date() != dend
    
    def _category_intent(self) -> bool:
        return any(bool(box.selected_codes()) for box in self.filter_boxes.values())
    
    def _code_counts_for_concept(self, concept_key: str) -> Dict[str, int]:
        """Count occurrences of raw codes for a concept within matched rows."""
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
    
    def refresh_filter_counts(self) -> None:
        """Update checklist labels to show decode label plus count from matched rows."""
        if not self.decodes:
            return
        for concept_key, box in self.filter_boxes.items():
            counts = self._code_counts_for_concept(concept_key)
            box.list.blockSignals(True)
            for i in range(box.list.count()):
                it = box.list.item(i)
                code = safe_str(it.data(Qt.UserRole)).strip()
                lab = self.decodes.decode(concept_key, code)
                it.setText(f"{lab} ({counts.get(code, 0)})")
            box.list.blockSignals(False)
    
    def _populate_filter_values(self, source: str) -> None:
        """Populate filter values from decodes, selection, or layer."""
        if self.layer is None or self.decodes is None:
            return
        
        # Cache checked state
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
            
            # Build items with decoded labels
            counts = self._code_counts_for_concept(concept_key)
            def label_for(code: str) -> str:
                lab = self.decodes.decode(concept_key, code)
                return f"{lab} ({counts.get(code, 0)})"
            
            items = sorted([(c, label_for(c)) for c in codes], key=lambda t: t[1].lower())
            box.setTitle(box.title().split(" (")[0])
            box.set_items(items, checked=self._checked_cache.get(concept_key, set()))
        
        self.refresh_filter_counts()
    
    def _build_spec(self) -> FilterSpec:
        """Build filter specification from current UI state."""
        selected_fids = set(self.layer.selectedFeatureIds()) if self.layer else set()
        
        category_codes: Dict[str, Set[str]] = {
            k: box.selected_codes() for k, box in self.filter_boxes.items()
        }
        
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
        """Determine which fields are needed for filtering and results."""
        if not self.layer:
            return []
        
        layer_fields = {f.name() for f in self.layer.fields()}
        needed: Set[str] = set()
        
        if spec.date_enabled and spec.date_field and spec.date_field in layer_fields:
            needed.add(spec.date_field)
        
        for concept_key, selected in spec.category_codes.items():
            if not selected:
                continue
            fname = self.field_map.get(concept_key)
            if fname and fname in layer_fields:
                needed.add(fname)
        
        for k, fname in self.field_map.items():
            if fname and fname in layer_fields:
                needed.add(fname)
        
        return sorted(needed)
    
    def apply_filters(self) -> None:
        """Apply filters and emit results."""
        if self.layer is None:
            return
        
        spec = self._build_spec()
        dstart, dend = self._default_last_full_10y_range()
        default_start = date(dstart.year(), dstart.month(), dstart.day())
        default_end = date(dend.year(), dend.month(), dend.day())
        
        # Check for idle state
        if spec.selection_only and not spec.selected_fids and not spec.has_any_intent(default_start, default_end):
            self.filtered_fids = []
            self.filtered_rows = []
            self.refresh_filter_counts()
            
            if self.status_changed:
                self.status_changed("idle", "Set filters or select features to analyze")
            if self.filters_applied:
                self.filters_applied([], [], 0)
            return
        
        if spec.selection_only and not spec.selected_fids and spec.has_any_intent(default_start, default_end):
            reply = QMessageBox.question(
                self, "Collision Analytics",
                "No map selection, but filters are set.\n\n"
                "Analyze the entire layer for the active filters?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        feature_count = self.layer.featureCount()
        needed = self._needed_fields(spec)
        
        if self.status_changed:
            self.status_changed("processing", f"Processing {feature_count:,} features...")
        
        if feature_count >= BACKGROUND_FILTER_THRESHOLD:
            self._run_background_filter(spec, needed, feature_count)
        else:
            self._run_sync_filter(spec, needed, feature_count)
    
    def _run_background_filter(self, spec: FilterSpec, needed: List[str], feature_count: int) -> None:
        """Run filtering in background with progress updates."""
        task = FilterTask(self.layer, spec, needed)
        task.feature_count = feature_count
        
        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_apply.setEnabled(False)
        
        # Timer to update progress
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(lambda: self._update_progress_from_task(task))
        self._progress_timer.start(100)
        
        task.taskCompleted.connect(lambda _result=None, t=task: self._on_filter_complete(t))
        task.taskTerminated.connect(lambda *_, t=task: self._on_filter_failed(t))
        
        self._active_filter_task = task
        QgsApplication.taskManager().addTask(task)
    
    def _update_progress_from_task(self, task: FilterTask) -> None:
        """Update progress bar from background task."""
        self.progress_bar.setValue(task.progress_pct)
    
    def _on_filter_complete(self, task: FilterTask) -> None:
        """Handle background filter completion."""
        self._active_filter_task = None
        
        # Hide progress
        if hasattr(self, '_progress_timer'):
            self._progress_timer.stop()
        self.progress_bar.setVisible(False)
        self.btn_apply.setEnabled(True)
        
        if self.layer is None or task.layer != self.layer:
            if self.status_changed:
                self.status_changed("warning", "Layer changed during filtering")
            return
        
        if task.exception:
            self._on_filter_failed(task)
            return
        
        total_count = getattr(task, "feature_count", self.layer.featureCount())
        self._apply_results(task.filtered_fids, task.filtered_rows, total_count)
    
    def _on_filter_failed(self, task: FilterTask) -> None:
        """Handle filter failure."""
        self._active_filter_task = None
        
        if hasattr(self, '_progress_timer'):
            self._progress_timer.stop()
        self.progress_bar.setVisible(False)
        self.btn_apply.setEnabled(True)
        
        exc = task.exception or Exception("Filtering task failed.")
        QgsMessageLog.logMessage(str(exc), "Collision Analytics", Qgis.Critical)
        
        if self.status_changed:
            self.status_changed("error", f"Filtering failed: {exc}")
    
    def _run_sync_filter(self, spec: FilterSpec, needed: List[str], feature_count: int) -> None:
        """Run filtering synchronously for smaller datasets."""
        engine = FilterEngine(self.layer)
        fids, rows = engine.apply(spec, needed)
        self._apply_results(fids, rows, feature_count)
    
    def _apply_results(self, fids: List[int], rows: List[Dict[str, Any]], total_count: int) -> None:
        """Apply filter results to UI and emit signal."""
        self.filtered_fids = fids
        self.filtered_rows = rows
        
        if self.chk_select_filtered.isChecked() and self.layer is not None:
            self.layer.selectByIds(fids)
        
        self.refresh_filter_counts()
        self._update_active_filters_summary()
        
        if self.status_changed:
            self.status_changed("active", f"Showing {len(fids):,} of {total_count:,} features")
        
        if self.filters_applied:
            self.filters_applied(fids, rows, total_count)
    
    def _update_active_filters_summary(self) -> None:
        """Update the active filters summary with pills."""
        pills = []
        
        if self.chk_use_date.isChecked() and self._date_intent():
            ds = self.date_start.date()
            de = self.date_end.date()
            pills.append((f"📅 {ds.toString('yyyy-MM-dd')} → {de.toString('yyyy-MM-dd')}", "info"))
        
        if self.chk_selection_only.isChecked():
            if self.layer:
                count = self.layer.selectedFeatureCount()
                if count > 0:
                    pills.append((f"🎯 {count} selected on map", "success"))
        
        if self.decodes:
            for concept_key, box in self.filter_boxes.items():
                codes = box.selected_codes()
                if not codes:
                    continue
                title = self._concept_titles.get(concept_key, concept_key)
                if len(codes) == 1:
                    label = self.decodes.decode(concept_key, list(codes)[0])
                    pills.append((f"{title}: {label}", "primary"))
                else:
                    pills.append((f"{title}: {len(codes)} selected", "primary"))
        
        # Clear existing pills
        while self.filters_layout.count() > 1:  # Keep stretch
            item = self.filters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if pills:
            self.empty_filters_label.setVisible(False)
            for text, variant in pills:
                badge = Badge(text, variant)
                self.filters_layout.insertWidget(self.filters_layout.count() - 1, badge)
        else:
            self.empty_filters_label.setVisible(True)
    
    def reset_all_filters(self) -> None:
        """Reset all filters to default state."""
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
        self.refresh_filter_counts()
        self._update_active_filters_summary()
        
        if self.filters_applied:
            self.filters_applied([], [], 0)
    
    def get_filtered_data(self) -> Tuple[List[int], List[Dict[str, Any]]]:
        """Get current filtered feature IDs and rows."""
        return self.filtered_fids, self.filtered_rows
    
    def set_selection_scope(self, enabled: bool) -> None:
        """Set the selection-only scope."""
        self.chk_selection_only.setChecked(enabled)
    
    def get_filter_codes(self, concept_key: str) -> Set[str]:
        """Get selected codes for a concept."""
        box = self.filter_boxes.get(concept_key)
        return box.selected_codes() if box else set()
    
    def apply_category_filter(self, concept_key: str, label: str, additive: bool = False) -> bool:
        """Apply a category filter from a chart click."""
        box = self.filter_boxes.get(concept_key)
        if box is None or self.decodes is None:
            return False
        
        codes = self._resolve_codes_from_label(concept_key, label)
        if not codes:
            return False
        
        box.list.blockSignals(True)
        
        if not additive:
            for i in range(box.list.count()):
                it = box.list.item(i)
                code = safe_str(it.data(Qt.UserRole)).strip()
                if code not in codes and it.checkState() != Qt.Unchecked:
                    it.setCheckState(Qt.Unchecked)
        
        changed = False
        for i in range(box.list.count()):
            it = box.list.item(i)
            code = safe_str(it.data(Qt.UserRole)).strip()
            if code in codes and it.checkState() != Qt.Checked:
                it.setCheckState(Qt.Checked)
                changed = True
        
        box.list.blockSignals(False)
        
        if changed:
            self._on_filter_changed()
            QTimer.singleShot(50, self.apply_filters)
        
        return changed
    
    def _resolve_codes_from_label(self, concept_key: str, label: str) -> List[str]:
        """Resolve a chart label back to decode codes."""
        if not self.decodes:
            return []
        
        mapping = self.decodes.mapping(concept_key)
        if not mapping:
            return []
        
        target = self._normalize_label_for_match(label)
        if not target:
            return []
        
        normalized = {code: self._normalize_label_for_match(lab) for code, lab in mapping.items()}
        
        for code, norm in normalized.items():
            if norm == target:
                return [code]
        
        target_lower = target.lower()
        matches = [code for code, norm in normalized.items() if norm.lower() == target_lower]
        if matches:
            return matches
        
        fuzzy = [code for code, norm in normalized.items() 
                 if norm.lower().startswith(target_lower) or target_lower.startswith(norm.lower())]
        if fuzzy:
            return fuzzy
        
        direct = [code for code in mapping.keys() if self._normalize_label_for_match(code).lower() == target_lower]
        if direct:
            return direct
        
        if target_lower in {"unknown", "unknown / blank", "unknown/blank", "blank"}:
            return [""]
        
        return []
    
    def _normalize_label_for_match(self, label: str) -> str:
        """Normalize a label for matching."""
        text = safe_str(label).replace("\n", " ")
        text = re.sub(r"\s*\(\s*[\d,]+\s*\)\s*$", "", text)
        text = " ".join(text.split())
        return text.strip()
