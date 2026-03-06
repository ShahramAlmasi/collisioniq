"""Filters tab for Collision Analytics plugin."""

from __future__ import annotations

import re
from collections import Counter
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
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsFeatureRequest

from ..widgets import CheckListFilterBox
from ...core.config import FILTER_CONCEPTS
from ...core.utils import safe_str, is_blank
from .base_tab import BaseTab


class FiltersTab(BaseTab):
    """Tab for configuring and applying filters."""

    def __init__(self, dock) -> None:
        super().__init__(dock)
        self.chk_use_date: QCheckBox | None = None
        self.date_start: QDateEdit | None = None
        self.date_end: QDateEdit | None = None
        self.chk_selection_only: QCheckBox | None = None
        self.chk_select_filtered: QCheckBox | None = None
        self.filter_boxes: Dict[str, CheckListFilterBox] = {}
        self.btn_apply: QPushButton | None = None
        self.btn_reset: QPushButton | None = None
        self.btn_values_decodes: QPushButton | None = None
        self.btn_values_selection: QPushButton | None = None
        self.btn_values_layer: QPushButton | None = None
        self.lbl_status: QLabel | None = None
        self._checked_cache: Dict[str, Set[str]] = {}
        self._concept_titles: Dict[str, str] = {k: v for k, v in FILTER_CONCEPTS}

    def build(self) -> QWidget:
        """Build the filters tab UI."""
        root = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Controls section
        controls = self._build_controls()
        layout.addLayout(controls)

        # Filter boxes in split layout
        splitter = self._build_filter_splitter()

        # Button row
        btn_row = self._build_button_row()
        layout.addLayout(btn_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        layout.addWidget(divider)

        # Filters content (scrollable)
        filters_content = QWidget()
        filters_layout = QVBoxLayout()
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)
        filters_layout.addWidget(splitter)
        filters_layout.addStretch(1)
        filters_content.setLayout(filters_layout)

        layout.addWidget(self._make_scrollable(filters_content), 1)

        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#555;")
        layout.addWidget(self.lbl_status)

        root.setLayout(layout)
        self.tab_widget = root
        return root

    def _build_controls(self) -> QVBoxLayout:
        """Build date and selection controls."""
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

        return controls

    def _build_filter_splitter(self) -> QSplitter:
        """Build the splitter with filter boxes."""
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        right = QWidget()
        left_l = QVBoxLayout()
        right_l = QVBoxLayout()
        left_l.setSpacing(8)
        right_l.setSpacing(8)

        self.filter_boxes = {}
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

        return splitter

    def _build_button_row(self) -> QHBoxLayout:
        """Build the button row."""
        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.apply_filters)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset)

        self.btn_values_decodes = QPushButton("Use decode values")
        self.btn_values_decodes.clicked.connect(
            lambda: self._populate_filter_values(source="decodes")
        )

        self.btn_values_selection = QPushButton("Load values from selection")
        self.btn_values_selection.clicked.connect(
            lambda: self._populate_filter_values(source="selection")
        )

        self.btn_values_layer = QPushButton("Load values from layer (may be slow)")
        self.btn_values_layer.clicked.connect(
            lambda: self._populate_filter_values(source="layer")
        )

        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_reset)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.btn_values_decodes)
        btn_row.addWidget(self.btn_values_selection)
        btn_row.addWidget(self.btn_values_layer)
        btn_row.addStretch(1)

        return btn_row

    def _default_last_full_10y_range(self) -> Tuple[QDate, QDate]:
        """Get default 10-year date range."""
        today = QDate.currentDate()
        end_year = today.year() - 1
        end = QDate(end_year, 12, 31)
        start = QDate(end_year - 9, 1, 1)
        return start, end

    def _on_filter_changed(self, *_) -> None:
        """Handle filter selection changes with debounced auto-apply."""
        self._update_active_filters_summary()
        if self.layer is None:
            return
        if (
            self.chk_selection_only.isChecked()
            and self.layer.selectedFeatureCount() > 0
        ):
            QTimer.singleShot(150, self.apply_filters)

    def _date_intent(self) -> bool:
        """Check if date filter has been modified from defaults."""
        if not self.chk_use_date.isChecked():
            return False
        dstart, dend = self._default_last_full_10y_range()
        return self.date_start.date() != dstart or self.date_end.date() != dend

    def _category_intent(self) -> bool:
        """Check if any category filters are selected."""
        return any(bool(box.selected_codes()) for box in self.filter_boxes.values())

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

    def refresh_filter_counts(self) -> None:
        """Update checklist labels to show decode label plus count from matched rows."""
        for concept_key, box in self.filter_boxes.items():
            counts = self._code_counts_for_concept(concept_key)
            box.list.blockSignals(True)
            for i in range(box.list.count()):
                it = box.list.item(i)
                code = safe_str(it.data(Qt.UserRole)).strip()
                lab = self._decode(concept_key, code)
                it.setText(f"{lab} ({counts.get(code, 0)})")
            box.list.blockSignals(False)

    def _normalize_label_for_match(self, label: str) -> str:
        """Normalize a chart label so it can be matched back to decode labels."""
        text = safe_str(label).replace("\n", " ")
        text = re.sub(
            r"\s*\(\s*[\d,]+\s*\)\s*$", "", text
        )  # strip trailing count suffix
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

        normalized = {
            code: self._normalize_label_for_match(lab) for code, lab in mapping.items()
        }

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

        fuzzy = match_codes(
            lambda norm: (
                norm.lower().startswith(target_lower)
                or target_lower.startswith(norm.lower())
            )
        )
        if fuzzy:
            return fuzzy

        # Fallback: match codes directly if labels are missing.
        direct = [
            code
            for code in mapping.keys()
            if self._normalize_label_for_match(code).lower() == target_lower
        ]
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

    def _apply_category_label(
        self, concept_key: str, label: str, additive: bool
    ) -> bool:
        """Apply/toggle checklist selections for a concept from a chart click."""
        box = self.filter_boxes.get(concept_key)
        if box is None:
            return False

        codes = {
            safe_str(c).strip()
            for c in self._resolve_codes_from_label(concept_key, label)
            if c is not None
        }
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
        """Update the active filters summary display."""
        lines: List[str] = []

        if self.chk_use_date.isChecked() and self._date_intent():
            ds = self.date_start.date()
            de = self.date_end.date()
            lines.append(
                f"Date: {ds.toString('yyyy-MM-dd')} -> {de.toString('yyyy-MM-dd')}"
            )

        for concept_key, box in self.filter_boxes.items():
            codes = box.selected_codes()
            if not codes:
                continue
            labels = {self._decode(concept_key, c) for c in codes}
            title = self._concept_titles.get(concept_key, concept_key)
            lines.append(
                f"{title}: {', '.join(sorted(labels, key=lambda s: s.lower()))}"
            )

        self.dock.update_active_filters_summary(lines)

    def filter_by_category(self, concept_key: str, label: str, additive: bool) -> None:
        """Apply chart-driven category filtering without changing the active tab."""
        # Special-case env combo to drive both env1/env2 filters.
        if concept_key == "env_combo":
            base = self._normalize_label_for_match(label)
            parts = [p.strip() for p in base.split("+")]
            if len(parts) >= 2:
                updated = False
                updated = (
                    self._apply_category_label("env1", parts[0], additive) or updated
                )
                updated = (
                    self._apply_category_label("env2", parts[1], additive) or updated
                )
                if updated:
                    self._update_active_filters_summary()
                    QTimer.singleShot(50, self.apply_filters)
            return

        if self._apply_category_label(concept_key, label, additive):
            self._update_active_filters_summary()
            QTimer.singleShot(50, self.apply_filters)

    def _populate_filter_values(self, source: str) -> None:
        """Populate filter value lists from various sources."""
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
                    QMessageBox.information(
                        self.tab_widget,
                        "Collision Analytics",
                        "No selected features in map.",
                    )
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
                lab = self._decode(concept_key, code)
                return f"{lab} ({counts.get(code, 0)})"

            items = sorted(
                [(c, label_for(c)) for c in codes], key=lambda t: t[1].lower()
            )
            box.setTitle(box.title().split(" (")[0])
            box.set_items(items, checked=self._checked_cache.get(concept_key, set()))
        self.refresh_filter_counts()

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

    def reset(self) -> None:
        """Reset all filters to defaults."""
        self.chk_use_date.setChecked(True)
        self.chk_selection_only.setChecked(True)
        self.chk_select_filtered.setChecked(False)

        dstart, dend = self._default_last_full_10y_range()
        self.date_start.setDate(dstart)
        self.date_end.setDate(dend)

        for box in self.filter_boxes.values():
            box.clear_checks()

        self.lbl_status.setText("")
        self._update_active_filters_summary()

    def apply_filters(self) -> None:
        """Delegate filter application to the dock widget."""
        self.dock.apply_filters()

    def set_status(self, text: str) -> None:
        """Set the status label text."""
        if self.lbl_status:
            self.lbl_status.setText(text)

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

    def on_layer_changed(self) -> None:
        """Handle layer change."""
        if (
            self.chk_selection_only.isChecked()
            and self.layer
            and self.layer.selectedFeatureCount() > 0
        ):
            self._populate_filter_values(source="selection")
        else:
            self._populate_filter_values(source="decodes")
