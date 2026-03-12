"""Decodes tab for Collision Analytics plugin."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_DECODES
from .base_tab import BaseTab


class DecodesTab(BaseTab):
    """Tab for managing decode tables."""

    def __init__(self, dock) -> None:
        super().__init__(dock)
        self.decode_search: Optional[QLineEdit] = None
        self.decode_group_list: Optional[QListWidget] = None
        self.decode_table: Optional[QTableWidget] = None

    def build(self) -> QWidget:
        """Build the decodes tab UI."""
        root = QWidget()
        layout = QVBoxLayout()

        # Hint text
        hint = QLabel(
            "Decode tables map raw codes (e.g., 1, 2, 99) to labels.\n"
            "Edits are saved per-user. You can export/import JSON for sharing."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Splitter with group list and table editor
        splitter = self._build_splitter()
        layout.addWidget(splitter, 1)

        root.setLayout(layout)
        self.tab_widget = root

        # Populate group list
        self._populate_decode_group_list()

        return root

    def _build_splitter(self) -> QSplitter:
        """Build the splitter with group list and table editor."""
        splitter = QSplitter(Qt.Horizontal)

        # Left: group list
        left = self._build_group_list_panel()
        splitter.addWidget(left)

        # Right: table editor
        right = self._build_table_editor_panel()
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        return splitter

    def _build_group_list_panel(self) -> QWidget:
        """Build the left panel with decode group list."""
        panel = QWidget()
        layout = QVBoxLayout()

        self.decode_search = QLineEdit()
        self.decode_search.setPlaceholderText("Filter decode groups")
        self.decode_search.textChanged.connect(self._filter_decode_groups)

        self.decode_group_list = QListWidget()
        self.decode_group_list.currentItemChanged.connect(
            self._on_decode_group_selected
        )

        layout.addWidget(self.decode_search)
        layout.addWidget(self.decode_group_list, 1)
        panel.setLayout(layout)

        return panel

    def _build_table_editor_panel(self) -> QWidget:
        """Build the right panel with table editor."""
        panel = QWidget()
        layout = QVBoxLayout()

        self.decode_table = QTableWidget(0, 2)
        self.decode_table.setHorizontalHeaderLabels(["Code", "Label"])
        self.decode_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.decode_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.decode_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.decode_table.setEditTriggers(
            QTableWidget.DoubleClicked
            | QTableWidget.EditKeyPressed
            | QTableWidget.AnyKeyPressed
        )

        # Button row
        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add row")
        btn_add.clicked.connect(self._decode_add_row)
        btn_delete = QPushButton("Delete selected")
        btn_delete.clicked.connect(self._decode_delete_selected)
        btn_save = QPushButton("Save changes")
        btn_save.clicked.connect(self._save_current_decode_group)
        btn_reset = QPushButton("Reset ALL to defaults")
        btn_reset.clicked.connect(self._reset_all_decodes)
        btn_export = QPushButton("Export JSON")
        btn_export.clicked.connect(self._export_decodes_json)
        btn_import = QPushButton("Import JSON")
        btn_import.clicked.connect(self._import_decodes_json)

        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_delete)
        btn_row.addSpacing(12)
        btn_row.addWidget(btn_save)
        btn_row.addSpacing(12)
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_export)
        btn_row.addSpacing(12)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch(1)

        layout.addWidget(self.decode_table, 1)
        layout.addLayout(btn_row)
        panel.setLayout(layout)

        return panel

    def _populate_decode_group_list(self) -> None:
        """Populate the decode group list widget."""
        self.decode_group_list.blockSignals(True)
        self.decode_group_list.clear()
        for key in self.decodes.keys():
            self.decode_group_list.addItem(key)
        self.decode_group_list.blockSignals(False)
        if (
            self.decode_group_list.count() > 0
            and self.decode_group_list.currentRow() < 0
        ):
            self.decode_group_list.setCurrentRow(0)

    def _filter_decode_groups(self, text: str) -> None:
        """Filter the decode group list."""
        t = (text or "").strip().lower()
        for i in range(self.decode_group_list.count()):
            it = self.decode_group_list.item(i)
            it.setHidden(False if not t else (t not in it.text().lower()))

    def _current_decode_group_key(self) -> Optional[str]:
        """Get the currently selected decode group key."""
        it = self.decode_group_list.currentItem()
        return it.text() if it else None

    def _on_decode_group_selected(self, current, previous) -> None:
        """Handle decode group selection change."""
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
        """Add a new row to the decode table."""
        row = self.decode_table.rowCount()
        self.decode_table.insertRow(row)
        self.decode_table.setItem(row, 0, QTableWidgetItem(""))
        self.decode_table.setItem(row, 1, QTableWidgetItem(""))
        self.decode_table.setCurrentCell(row, 0)
        self.decode_table.editItem(self.decode_table.item(row, 0))

    def _decode_delete_selected(self) -> None:
        """Delete selected rows from the decode table."""
        rows = sorted(
            {idx.row() for idx in self.decode_table.selectionModel().selectedRows()},
            reverse=True,
        )
        for r in rows:
            self.decode_table.removeRow(r)

    def _read_decode_table(self) -> Dict[str, str]:
        """Read the decode table into a dictionary."""
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
        """Save the current decode group."""
        key = self._current_decode_group_key()
        if not key:
            return
        self.decodes.set_mapping(key, self._read_decode_table())
        self.decodes.save()
        QMessageBox.information(
            self.tab_widget, "Collision Analytics", f"Saved decode group: {key}"
        )
        self.dock.controller.populate_filter_values("decodes")

    def _reset_all_decodes(self) -> None:
        """Reset all decode groups to defaults."""
        self.decodes.reset_to_defaults()
        self._populate_decode_group_list()
        self.dock.controller.populate_filter_values("decodes")
        QMessageBox.information(
            self.tab_widget,
            "Collision Analytics",
            "All decode groups reset to defaults.",
        )

    def _export_decodes_json(self) -> None:
        """Export decodes to JSON file."""
        path, _ = QFileDialog.getSaveFileName(
            self.tab_widget, "Export decodes JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        obj = {k: self.decodes.mapping(k) for k in self.decodes.keys()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        QMessageBox.information(
            self.tab_widget, "Collision Analytics", f"Exported:\n{path}"
        )

    def _import_decodes_json(self) -> None:
        """Import decodes from JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self.tab_widget, "Import decodes JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if not isinstance(obj, dict):
                raise ValueError("Expected {group: {code: label}}")
            for k, v in obj.items():
                if isinstance(v, dict):
                    self.decodes.set_mapping(
                        str(k), {str(code): str(label) for code, label in v.items()}
                    )
            self.decodes.save()
            self._populate_decode_group_list()
            self.dock.controller.populate_filter_values("decodes")
            QMessageBox.information(
                self.tab_widget, "Collision Analytics", f"Imported:\n{path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self.tab_widget, "Collision Analytics", f"Import failed:\n{e}"
            )

    def reset(self) -> None:
        """Reset decodes tab."""
        self._populate_decode_group_list()
