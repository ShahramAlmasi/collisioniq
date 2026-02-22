"""Config Panel - Modern field mapping and decode configuration."""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFileDialog,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_FIELD_MAP
from ...core.decodes import DecodeRegistry
from ..modern_widgets import (
    Badge,
    Card,
    Colors,
    EmptyState,
    IconButton,
    SegmentedControl,
    Typography,
    apply_modern_stylesheet,
)

if TYPE_CHECKING:
    from ...core.config_manager import ConfigManager


class ConfigPanel(QWidget):
    """Modern panel for field mapping and decode configuration."""
    
    config_changed = None  # Callback: () -> None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layer = None
        self.config_mgr: Optional[ConfigManager] = None
        self.decodes: Optional[DecodeRegistry] = None
        self.field_map: Dict[str, str] = {}
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build modern config UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # ===== Tab Navigation =====
        self.tab_control = SegmentedControl([
            ("fields", "📝 Field Mapping"),
            ("decodes", "🔤 Decode Tables"),
            ("import_export", "💾 Import/Export"),
        ])
        self.tab_control.selection_changed = self._on_tab_changed
        layout.addWidget(self.tab_control)
        
        # ===== Content Stack =====
        self.content_stack = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # Build panels
        self.fields_panel = self._build_fields_panel()
        self.decodes_panel = self._build_decodes_panel()
        self.io_panel = self._build_io_panel()
        
        self.content_layout.addWidget(self.fields_panel)
        self.content_layout.addWidget(self.decodes_panel)
        self.content_layout.addWidget(self.io_panel)
        
        self.content_stack.setLayout(self.content_layout)
        layout.addWidget(self.content_stack, 1)
        
        self.setLayout(layout)
        self._show_tab("fields")
    
    def _on_tab_changed(self, index: int, key: str) -> None:
        """Handle tab change."""
        self._show_tab(key)
    
    def _show_tab(self, tab: str) -> None:
        """Show selected tab."""
        self.fields_panel.setVisible(tab == "fields")
        self.decodes_panel.setVisible(tab == "decodes")
        self.io_panel.setVisible(tab == "import_export")
    
    def _build_fields_panel(self) -> QWidget:
        """Build the field mapping panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Info card
        info = Card()
        info.setStyleSheet(f"""
            Card {{
                background-color: {Colors.ACCENT_INFO}10;
                border: 1px solid {Colors.ACCENT_INFO}40;
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        
        icon = QLabel("💡")
        icon.setStyleSheet("font-size: 20px;")
        
        text = QLabel(
            "Map your layer fields to plugin concepts. "
            "This keeps the plugin usable across different data schemas. "
            "Config is saved to JSON in your project folder."
        )
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        
        info_layout.addWidget(icon)
        info_layout.addWidget(text, 1)
        info.setLayout(info_layout)
        layout.addWidget(info)
        
        # Field mapping grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameStyle(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        form_container = QWidget()
        form_container.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)
        
        from qgis.PyQt.QtWidgets import QComboBox, QFormLayout
        
        self.field_selectors: Dict[str, QComboBox] = {}
        
        for key in DEFAULT_FIELD_MAP.keys():
            row = QWidget()
            row.setStyleSheet(f"""
                background-color: {Colors.BG_SECONDARY};
                border-radius: 6px;
                padding: 8px;
            """)
            row_layout = QHBoxLayout()
            row_layout.setSpacing(12)
            
            label = QLabel(key)
            label.setFixedWidth(150)
            label.setStyleSheet(f"""
                font-weight: 500;
                color: {Colors.TEXT_PRIMARY};
            """)
            
            cb = QComboBox()
            cb.setMinimumWidth(180)
            cb.currentIndexChanged.connect(self._on_field_mapping_changed)
            
            status = QLabel("●")
            status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            status.setObjectName(f"status_{key}")
            
            row_layout.addWidget(label)
            row_layout.addWidget(cb, 1)
            row_layout.addWidget(status)
            
            row.setLayout(row_layout)
            form_layout.addWidget(row)
            self.field_selectors[key] = cb
        
        form_layout.addStretch(1)
        form_container.setLayout(form_layout)
        scroll.setWidget(form_container)
        layout.addWidget(scroll, 1)
        
        # Action buttons
        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"""
            background-color: {Colors.BG_SECONDARY};
            border-radius: 8px;
        """)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(12, 10, 12, 10)
        
        self.btn_save_fields = QPushButton("💾 Save Mapping")
        self.btn_save_fields.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_SUCCESS};
                border: 1px solid {Colors.ACCENT_SUCCESS};
                color: white;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        self.btn_save_fields.clicked.connect(self._save_field_map)
        
        self.btn_reset_fields = QPushButton("↺ Reset to Defaults")
        self.btn_reset_fields.clicked.connect(self._reset_field_map_defaults)
        
        self.mapped_count = Badge("0/22 mapped", "default")
        
        btn_layout.addWidget(self.btn_save_fields)
        btn_layout.addWidget(self.btn_reset_fields)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.mapped_count)
        
        btn_bar.setLayout(btn_layout)
        layout.addWidget(btn_bar)
        
        panel.setLayout(layout)
        return panel
    
    def _build_decodes_panel(self) -> QWidget:
        """Build the decodes configuration panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Info card
        info = Card()
        info.setStyleSheet(f"""
            Card {{
                background-color: {Colors.ACCENT_INFO}10;
                border: 1px solid {Colors.ACCENT_INFO}40;
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        
        icon = QLabel("💡")
        icon.setStyleSheet("font-size: 20px;")
        
        text = QLabel(
            "Decode tables map raw codes (e.g., 1, 2, 99) to human-readable labels. "
            "Edits are saved to JSON config. Use Import/Export to share configs with colleagues."
        )
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        
        info_layout.addWidget(icon)
        info_layout.addWidget(text, 1)
        info.setLayout(info_layout)
        layout.addWidget(info)
        
        # Splitter for group list and editor
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER_DEFAULT};
            }}
        """)
        
        # Left: group list
        left = Card()
        left.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        left_l = QVBoxLayout()
        left_l.setSpacing(8)
        
        search_label = QLabel("🔍 Search decode groups")
        search_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.XS}px;")
        
        self.decode_search = QLineEdit()
        self.decode_search.setPlaceholderText("Type to filter...")
        self.decode_search.textChanged.connect(self._filter_decode_groups)
        
        self.decode_group_list = QListWidget()
        self.decode_group_list.setAlternatingRowColors(True)
        self.decode_group_list.currentItemChanged.connect(self._on_decode_group_selected)
        
        left_l.addWidget(search_label)
        left_l.addWidget(self.decode_search)
        left_l.addWidget(self.decode_group_list, 1)
        left.setLayout(left_l)
        
        # Right: table editor
        right = Card()
        right.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        right_l = QVBoxLayout()
        right_l.setSpacing(12)
        
        # Editor header
        editor_header = QHBoxLayout()
        self.decode_title = QLabel("Select a decode group")
        self.decode_title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        editor_header.addWidget(self.decode_title)
        editor_header.addStretch(1)
        right_l.addLayout(editor_header)
        
        # Table
        self.decode_table = QTableWidget(0, 2)
        self.decode_table.setHorizontalHeaderLabels(["Code", "Label"])
        self.decode_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.decode_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.decode_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.decode_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed | QTableWidget.AnyKeyPressed
        )
        
        right_l.addWidget(self.decode_table, 1)
        
        # Action buttons
        btn_row = QHBoxLayout()
        
        self.btn_decode_add = QPushButton("➕ Add Row")
        self.btn_decode_add.clicked.connect(self._decode_add_row)
        
        self.btn_decode_delete = QPushButton("🗑️ Delete")
        self.btn_decode_delete.clicked.connect(self._decode_delete_selected)
        
        self.btn_decode_save = QPushButton("💾 Save Changes")
        self.btn_decode_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_SUCCESS};
                border: 1px solid {Colors.ACCENT_SUCCESS};
                color: white;
                padding: 6px 16px;
            }}
        """)
        self.btn_decode_save.clicked.connect(self._save_current_decode_group)
        
        self.btn_decode_reset = QPushButton("↺ Reset All")
        self.btn_decode_reset.clicked.connect(self._reset_all_decodes)
        
        btn_row.addWidget(self.btn_decode_add)
        btn_row.addWidget(self.btn_decode_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_decode_save)
        btn_row.addWidget(self.btn_decode_reset)
        
        right_l.addLayout(btn_row)
        right.setLayout(right_l)
        
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 400])
        
        layout.addWidget(splitter, 1)
        panel.setLayout(layout)
        return panel
    
    def _build_io_panel(self) -> QWidget:
        """Build import/export panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Export section
        export_card = Card()
        export_card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        export_layout = QVBoxLayout()
        export_layout.setSpacing(12)
        
        export_title = QLabel("📤 Export Configuration")
        export_title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        export_layout.addWidget(export_title)
        
        export_desc = QLabel("Export your configuration to share with colleagues or backup.")
        export_desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        export_desc.setWordWrap(True)
        export_layout.addWidget(export_desc)
        
        export_grid = QHBoxLayout()
        export_grid.setSpacing(12)
        
        self.btn_export_full = QPushButton("💾 Full Config (JSON)")
        self.btn_export_full.setToolTip("Export complete configuration")
        self.btn_export_full.clicked.connect(self._export_full_config_json)
        
        self.btn_export_fields = QPushButton("📝 Field Map Only")
        self.btn_export_fields.setToolTip("Export just field mappings")
        self.btn_export_fields.clicked.connect(self._export_field_map_json)
        
        self.btn_export_decodes = QPushButton("🔤 Decodes Only")
        self.btn_export_decodes.setToolTip("Export just decode tables")
        self.btn_export_decodes.clicked.connect(self._export_decodes_json)
        
        export_grid.addWidget(self.btn_export_full)
        export_grid.addWidget(self.btn_export_fields)
        export_grid.addWidget(self.btn_export_decodes)
        export_grid.addStretch(1)
        
        export_layout.addLayout(export_grid)
        export_card.setLayout(export_layout)
        layout.addWidget(export_card)
        
        # Import section
        import_card = Card()
        import_card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        import_layout = QVBoxLayout()
        import_layout.setSpacing(12)
        
        import_title = QLabel("📥 Import Configuration")
        import_title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        import_layout.addWidget(import_title)
        
        import_desc = QLabel("Import configuration from JSON files. You can merge with existing or replace entirely.")
        import_desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        import_desc.setWordWrap(True)
        import_layout.addWidget(import_desc)
        
        import_grid = QHBoxLayout()
        import_grid.setSpacing(12)
        
        self.btn_import_full = QPushButton("📂 Import Full Config")
        self.btn_import_full.setToolTip("Import complete configuration")
        self.btn_import_full.clicked.connect(self._import_full_config_json)
        
        self.btn_import_decodes = QPushButton("🔤 Import Decodes")
        self.btn_import_decodes.setToolTip("Import decode tables")
        self.btn_import_decodes.clicked.connect(self._import_decodes_json)
        
        import_grid.addWidget(self.btn_import_full)
        import_grid.addWidget(self.btn_import_decodes)
        import_grid.addStretch(1)
        
        import_layout.addLayout(import_grid)
        import_card.setLayout(import_layout)
        layout.addWidget(import_card)
        
        # Reset section
        reset_card = Card()
        reset_card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.ACCENT_DANGER}10;
                border: 1px solid {Colors.ACCENT_DANGER}40;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        reset_layout = QVBoxLayout()
        reset_layout.setSpacing(12)
        
        reset_title = QLabel("⚠️ Reset Configuration")
        reset_title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.ACCENT_DANGER};
        """)
        reset_layout.addWidget(reset_title)
        
        reset_desc = QLabel("Reset configuration to factory defaults. This cannot be undone.")
        reset_desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        reset_desc.setWordWrap(True)
        reset_layout.addWidget(reset_desc)
        
        self.btn_reset_all = QPushButton("🔄 Reset ALL to Defaults")
        self.btn_reset_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_DANGER};
                border: 1px solid {Colors.ACCENT_DANGER};
                color: white;
                padding: 8px 16px;
            }}
        """)
        self.btn_reset_all.clicked.connect(self._reset_all_config)
        
        reset_layout.addWidget(self.btn_reset_all)
        reset_card.setLayout(reset_layout)
        layout.addWidget(reset_card)
        
        layout.addStretch(1)
        panel.setLayout(layout)
        return panel
    
    def set_config_manager(self, config_mgr: ConfigManager, decodes: DecodeRegistry) -> None:
        """Set the configuration manager and decodes registry."""
        self.config_mgr = config_mgr
        self.decodes = decodes
        self.field_map = dict(config_mgr.field_map)
        
        self._populate_field_selectors()
        self._populate_decode_group_list()
        self._update_mapped_count()
    
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
        mapped_count = 0
        
        for key, cb in self.field_selectors.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")  # Allow empty
            cb.addItems(names)
            mapped = self.field_map.get(key, "")
            if mapped in names:
                cb.setCurrentText(mapped)
                mapped_count += 1
            
            # Update status indicator
            status = cb.parent().findChild(QLabel, f"status_{key}")
            if status:
                if mapped and mapped in names:
                    status.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS};")
                elif mapped:
                    status.setStyleSheet(f"color: {Colors.ACCENT_WARNING};")  # Mapped but not found
                else:
                    status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            
            cb.blockSignals(False)
        
        self._update_mapped_count()
    
    def _update_mapped_count(self):
        """Update the mapped fields counter."""
        total = len(self.field_selectors)
        mapped = sum(1 for key, cb in self.field_selectors.items() if cb.currentText())
        self.mapped_count.set_text(f"{mapped}/{total} mapped")
        if mapped == total:
            self.mapped_count.set_variant("success")
        elif mapped > 0:
            self.mapped_count.set_variant("primary")
        else:
            self.mapped_count.set_variant("default")
    
    def _on_field_mapping_changed(self, *_) -> None:
        """Handle field mapping changes."""
        for key, cb in self.field_selectors.items():
            name = cb.currentText().strip()
            if name:
                self.field_map[key] = name
            elif key in self.field_map:
                del self.field_map[key]
        
        self._update_mapped_count()
    
    def _save_field_map(self) -> None:
        """Save field mapping to config."""
        if not self.config_mgr:
            return
        
        self.config_mgr.field_map = self.field_map
        self.config_mgr.save()
        
        # Update status indicators
        for key, cb in self.field_selectors.items():
            status = cb.parent().findChild(QLabel, f"status_{key}")
            if status:
                if cb.currentText():
                    status.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS};")
                else:
                    status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        
        QMessageBox.information(self, "Configuration", "✅ Field mapping saved.")
        
        if self.config_changed:
            self.config_changed()
    
    def _reset_field_map_defaults(self) -> None:
        """Reset field mapping to defaults."""
        if not self.config_mgr:
            return
        
        reply = QMessageBox.question(
            self, "Reset Field Map",
            "Reset field mapping to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
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
            QMessageBox.information(self, "Export", f"✅ Exported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export", f"❌ Export failed:\n{e}")
    
    def _export_field_map_json(self) -> None:
        """Export field map to JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export field map JSON",
            "field_map.json", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.export_field_maps(path)
            QMessageBox.information(self, "Export", f"✅ Exported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export", f"❌ Export failed:\n{e}")
    
    def _export_decodes_json(self) -> None:
        """Export decodes to JSON."""
        if not self.config_mgr:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export decodes JSON",
            "decodes.json", "JSON (*.json)"
        )
        if not path:
            return
        
        try:
            self.config_mgr.export_decodes(path)
            QMessageBox.information(self, "Export", f"✅ Exported:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export", f"❌ Export failed:\n{e}")
    
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
            
            if self.decodes:
                for concept, mapping in self.config_mgr.decodes.items():
                    self.decodes.set_mapping(concept, mapping)
                self.decodes.save()
            
            self._populate_field_selectors()
            self._populate_decode_group_list()
            
            QMessageBox.information(self, "Import", f"✅ Imported:\n{path}")
            
            if self.config_changed:
                self.config_changed()
        except Exception as e:
            QMessageBox.warning(self, "Import", f"❌ Import failed:\n{e}")
    
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
            
            if self.decodes:
                for concept, mapping in self.config_mgr.decodes.items():
                    self.decodes.set_mapping(concept, mapping)
                self.decodes.save()
            
            self._populate_decode_group_list()
            
            QMessageBox.information(self, "Import", f"✅ Imported:\n{path}")
            
            if self.config_changed:
                self.config_changed()
        except Exception as e:
            QMessageBox.warning(self, "Import", f"❌ Import failed:\n{e}")
    
    def _reset_all_config(self) -> None:
        """Reset all configuration to defaults."""
        if not self.config_mgr or not self.decodes:
            return
        
        reply = QMessageBox.warning(
            self, "Reset All Configuration",
            "This will reset ALL settings to factory defaults.\n\n"
            "This action cannot be undone. Are you sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.config_mgr.reset_to_defaults()
        self.decodes.reset_to_defaults()
        
        self.config_mgr.save()
        
        self.field_map = dict(self.config_mgr.field_map)
        self._populate_field_selectors()
        self._populate_decode_group_list()
        self.decode_table.setRowCount(0)
        
        QMessageBox.information(self, "Configuration", "✅ All settings reset to defaults.")
        
        if self.config_changed:
            self.config_changed()
    
    # Decodes methods
    def _populate_decode_group_list(self) -> None:
        """Populate the decode group list."""
        if not self.decodes:
            return
        
        self.decode_group_list.blockSignals(True)
        self.decode_group_list.clear()
        for key in sorted(self.decodes.keys()):
            item = QListWidgetItem(key)
            item.setData(Qt.UserRole, key)
            self.decode_group_list.addItem(item)
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
        return it.data(Qt.UserRole) if it else None
    
    def _on_decode_group_selected(self, current, previous) -> None:
        """Handle decode group selection."""
        key = self._current_decode_group_key()
        if not key or not self.decodes:
            self.decode_table.setRowCount(0)
            self.decode_title.setText("Select a decode group")
            return
        
        self.decode_title.setText(f"🔤 {key}")
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
        
        self.config_mgr.set_decode_mapping(key, mapping)
        self.decodes.set_mapping(key, mapping)
        
        self.config_mgr.save()
        self.decodes.save()
        
        QMessageBox.information(self, "Configuration", f"✅ Saved decode group: {key}")
        
        if self.config_changed:
            self.config_changed()
    
    def _reset_all_decodes(self) -> None:
        """Reset all decodes to defaults."""
        if not self.decodes or not self.config_mgr:
            return
        
        reply = QMessageBox.question(
            self, "Reset Decodes",
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
        
        QMessageBox.information(self, "Configuration", "✅ All decode groups reset to defaults.")
        
        if self.config_changed:
            self.config_changed()
    
    def get_field_map(self) -> Dict[str, str]:
        """Get the current field map."""
        return dict(self.field_map)
