"""Config Panel - Field mapping and decode configuration."""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_FIELD_MAP
from ...core.decodes import DecodeRegistry

if TYPE_CHECKING:
    from ...core.config_manager import ConfigManager


class ConfigPanel(QWidget):
    """Panel for field mapping and decode configuration."""
    
    config_changed = None  # Callback: () -> None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layer = None
        self.config_mgr: Optional[ConfigManager] = None
        self.decodes: Optional[DecodeRegistry] = None
        self.field_map: Dict[str, str] = {}
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Create tabs using buttons
        nav_layout = QHBoxLayout()
        self.btn_fields = QPushButton("Field Mapping")
        self.btn_decodes = QPushButton("Decodes")
        self.btn_fields.setCheckable(True)
        self.btn_decodes.setCheckable(True)
        self.btn_fields.setChecked(True)
        
        self.btn_fields.clicked.connect(lambda: self._show_tab("fields"))
        self.btn_decodes.clicked.connect(lambda: self._show_tab("decodes"))
        
        nav_layout.addWidget(self.btn_fields)
        nav_layout.addWidget(self.btn_decodes)
        nav_layout.addStretch(1)
        
        layout.addLayout(nav_layout)
        
        # Stacked content
        self.stack = QWidget()
        self.stack_layout = QVBoxLayout()
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.setLayout(self.stack_layout)
        
        # Fields panel
        self.fields_panel = self._build_fields_panel()
        self.decodes_panel = self._build_decodes_panel()
        
        self.stack_layout.addWidget(self.fields_panel)
        self.stack_layout.addWidget(self.decodes_panel)
        
        layout.addWidget(self.stack, 1)
        self.setLayout(layout)
        
        self._show_tab("fields")
    
    def _show_tab(self, tab: str) -> None:
        """Switch between field mapping and decodes tabs."""
        self.btn_fields.setChecked(tab == "fields")
        self.btn_decodes.setChecked(tab == "decodes")
        self.fields_panel.setVisible(tab == "fields")
        self.decodes_panel.setVisible(tab == "decodes")
    
    def _build_fields_panel(self) -> QWidget:
        """Build the field mapping panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        hint = QLabel(
            "Map your layer fields to the plugin concepts.\n"
            "This keeps the plugin usable across different schemas.\n"
            "Config is saved to JSON in the project folder for portability."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # Form layout for field selectors
        form_container = QWidget()
        form_layout = QFormLayout()
        form_layout.setSpacing(6)
        
        from qgis.PyQt.QtWidgets import QComboBox
        self.field_selectors: Dict[str, QComboBox] = {}
        
        for key in DEFAULT_FIELD_MAP.keys():
            cb = QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(self._on_field_mapping_changed)
            self.field_selectors[key] = cb
            form_layout.addRow(f"{key}:", cb)
        
        form_container.setLayout(form_layout)
        
        # Make scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(form_container)
        layout.addWidget(scroll, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save_fields = QPushButton("Save field mapping")
        self.btn_save_fields.clicked.connect(self._save_field_map)
        
        self.btn_reset_fields = QPushButton("Reset to defaults")
        self.btn_reset_fields.clicked.connect(self._reset_field_map_defaults)
        
        self.btn_export_config = QPushButton("Export full config")
        self.btn_export_config.clicked.connect(self._export_full_config_json)
        
        self.btn_import_config = QPushButton("Import full config")
        self.btn_import_config.clicked.connect(self._import_full_config_json)
        
        btn_layout.addWidget(self.btn_save_fields)
        btn_layout.addWidget(self.btn_reset_fields)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(self.btn_export_config)
        btn_layout.addWidget(self.btn_import_config)
        btn_layout.addStretch(1)
        
        layout.addLayout(btn_layout)
        panel.setLayout(layout)
        return panel
    
    def _build_decodes_panel(self) -> QWidget:
        """Build the decodes configuration panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        hint = QLabel(
            "Decode tables map raw codes (e.g., 1, 2, 99) to labels.\n"
            "Edits are saved to JSON config. Use Export/Import to share configs."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # Splitter for group list and editor
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: group list
        left = QWidget()
        left_l = QVBoxLayout()
        left_l.setContentsMargins(0, 0, 0, 0)
        
        self.decode_search = QLineEdit()
        self.decode_search.setPlaceholderText("Filter decode groups...")
        self.decode_search.textChanged.connect(self._filter_decode_groups)
        
        self.decode_group_list = QListWidget()
        self.decode_group_list.currentItemChanged.connect(self._on_decode_group_selected)
        
        left_l.addWidget(self.decode_search)
        left_l.addWidget(self.decode_group_list, 1)
        left.setLayout(left_l)
        
        # Right: table editor
        right = QWidget()
        right_l = QVBoxLayout()
        right_l.setContentsMargins(0, 0, 0, 0)
        
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
        splitter.setSizes([150, 450])
        
        layout.addWidget(splitter, 1)
        panel.setLayout(layout)
        return panel
    
    def set_config_manager(self, config_mgr: ConfigManager, decodes: DecodeRegistry) -> None:
        """Set the configuration manager and decodes registry."""
        self.config_mgr = config_mgr
        self.decodes = decodes
        self.field_map = dict(config_mgr.field_map)
        
        self._populate_field_selectors()
        self._populate_decode_group_list()
    
    def set_layer(self, layer) -> None:
        """Set the current layer."""
        self.layer = layer
        self._populate_field_selectors()
    
    def _populate_field_selectors(self) -> None:
        """Populate field selector combos with layer fields."""
        if self.layer is None:
            return
        
        from qgis.PyQt.QtWidgets import QComboBox
        names = [f.name() for f in self.layer.fields()]
        
        for key, cb in self.field_selectors.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")  # Allow empty
            cb.addItems(names)
            mapped = self.field_map.get(key, "")
            if mapped in names:
                cb.setCurrentText(mapped)
            cb.blockSignals(False)
    
    def _on_field_mapping_changed(self, *_) -> None:
        """Handle field mapping changes."""
        for key, cb in self.field_selectors.items():
            name = cb.currentText().strip()
            if name:
                self.field_map[key] = name
            elif key in self.field_map:
                del self.field_map[key]
    
    def _save_field_map(self) -> None:
        """Save field mapping to config."""
        if not self.config_mgr:
            return
        
        self.config_mgr.field_map = self.field_map
        self.config_mgr.save()
        QMessageBox.information(self, "Collision Analytics", "Field mapping saved.")
        
        if self.config_changed:
            self.config_changed()
    
    def _reset_field_map_defaults(self) -> None:
        """Reset field mapping to defaults."""
        if not self.config_mgr:
            return
        
        self.config_mgr.reset_field_map()
        self.field_map = dict(self.config_mgr.field_map)
        self.config_mgr.save()
        self._populate_field_selectors()
        
        if self.config_changed:
            self.config_changed()
    
    def _export_full_config_json(self) -> None:
        """Export full configuration to JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export full config JSON",
            "collision_analytics_config.json", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.export_full_config(path)
            QMessageBox.information(self, "Collision Analytics", f"Exported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Export failed:\n{e}")
    
    def _import_full_config_json(self) -> None:
        """Import full configuration from JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getOpenFileName(
            self, "Import full config JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.import_full_config(path)
            self.field_map = dict(self.config_mgr.field_map)
            
            # Sync decodes
            if self.decodes:
                for concept, mapping in self.config_mgr.decodes.items():
                    self.decodes.set_mapping(concept, mapping)
                self.decodes.save()
            
            self._populate_field_selectors()
            self._populate_decode_group_list()
            
            QMessageBox.information(self, "Collision Analytics", f"Imported:\n{path}")
            
            if self.config_changed:
                self.config_changed()
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Import failed:\n{e}")
    
    # Decodes methods
    def _populate_decode_group_list(self) -> None:
        """Populate the decode group list."""
        if not self.decodes:
            return
        
        self.decode_group_list.blockSignals(True)
        self.decode_group_list.clear()
        for key in self.decodes.keys():
            self.decode_group_list.addItem(key)
        self.decode_group_list.blockSignals(False)
        
        if self.decode_group_list.count() > 0 and self.decode_group_list.currentRow() < 0:
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
        """Handle decode group selection."""
        key = self._current_decode_group_key()
        if not key or not self.decodes:
            self.decode_table.setRowCount(0)
            return
        
        mapping = self.decodes.mapping(key)
        
        # Sort codes: numeric first, then alphabetical
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
            reverse=True
        )
        for r in rows:
            self.decode_table.removeRow(r)
    
    def _read_decode_table(self) -> Dict[str, str]:
        """Read the decode table into a mapping dictionary."""
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
        if not key or not self.decodes or not self.config_mgr:
            return
        
        mapping = self._read_decode_table()
        
        # Save to both ConfigManager and DecodeRegistry
        self.config_mgr.set_decode_mapping(key, mapping)
        self.decodes.set_mapping(key, mapping)
        
        self.config_mgr.save()
        self.decodes.save()
        
        QMessageBox.information(self, "Collision Analytics", f"Saved decode group: {key}")
        
        if self.config_changed:
            self.config_changed()
    
    def _reset_all_decodes(self) -> None:
        """Reset all decodes to defaults."""
        if not self.decodes or not self.config_mgr:
            return
        
        reply = QMessageBox.question(
            self, "Collision Analytics",
            "Reset ALL decode groups to defaults? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.config_mgr.reset_decodes()
        self.decodes.reset_to_defaults()
        
        self.config_mgr.save()
        
        self._populate_decode_group_list()
        self.decode_table.setRowCount(0)
        
        QMessageBox.information(self, "Collision Analytics", "All decode groups reset to defaults.")
        
        if self.config_changed:
            self.config_changed()
    
    def _export_decodes_json(self) -> None:
        """Export decodes to JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export decodes JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.export_decodes(path)
            QMessageBox.information(self, "Collision Analytics", f"Exported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Export failed:\n{e}")
    
    def _import_decodes_json(self) -> None:
        """Import decodes from JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getOpenFileName(
            self, "Import decodes JSON", "", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.import_decodes(path, merge=True)
            self.config_mgr.save()
            
            # Update DecodeRegistry
            if self.decodes:
                for concept, mapping in self.config_mgr.decodes.items():
                    self.decodes.set_mapping(concept, mapping)
                self.decodes.save()
            
            self._populate_decode_group_list()
            
            QMessageBox.information(self, "Collision Analytics", f"Imported:\n{path}")
            
            if self.config_changed:
                self.config_changed()
        except Exception as e:
            QMessageBox.warning(self, "Collision Analytics", f"Import failed:\n{e}")
    
    def get_field_map(self) -> Dict[str, str]:
        """Get the current field map."""
        return dict(self.field_map)
