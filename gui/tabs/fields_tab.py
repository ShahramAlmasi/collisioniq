"""Fields tab for Collision Analytics plugin."""

from __future__ import annotations

from typing import Dict

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_FIELD_MAP, SETTINGS_FIELD_MAP_KEY
from ...core.settings import load_json, save_json
from .base_tab import BaseTab


class FieldsTab(BaseTab):
    """Tab for configuring field mappings."""

    def __init__(self, dock) -> None:
        super().__init__(dock)
        self.field_selectors: Dict[str, QComboBox] = {}

    def build(self) -> QWidget:
        """Build the fields tab UI."""
        root = QWidget()
        layout = QVBoxLayout()

        # Hint text
        hint = QLabel(
            "Map your layer fields to the plugin concepts.\n"
            "This keeps the plugin usable across different schemas."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Form with field selectors
        form = QFormLayout()
        self.field_selectors = {}

        for key in DEFAULT_FIELD_MAP.keys():
            cb = QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(self._on_field_mapping_changed)
            self.field_selectors[key] = cb
            form.addRow(f"{key}:", cb)

        layout.addLayout(form)

        # Button row
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save field mapping")
        btn_save.clicked.connect(self._save_field_map)
        btn_reset = QPushButton("Reset to defaults")
        btn_reset.clicked.connect(self._reset_field_map_defaults)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch(1)

        layout.addLayout(btn_row)
        layout.addStretch(1)

        root.setLayout(layout)
        self.tab_widget = root

        # Load field map
        self._load_field_map()

        return root

    def _on_field_mapping_changed(self, *_) -> None:
        """Handle field mapping changes."""
        for key, cb in self.field_selectors.items():
            name = cb.currentText().strip()
            if name:
                self.dock.field_map[key] = name

    def _load_field_map(self) -> None:
        """Load field map from settings."""
        obj = load_json(self.dock.settings, SETTINGS_FIELD_MAP_KEY, None)
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.dock.field_map[str(k)] = str(v)

    def _save_field_map(self) -> None:
        """Save field map to settings."""
        save_json(self.dock.settings, SETTINGS_FIELD_MAP_KEY, self.dock.field_map)
        QMessageBox.information(
            self.tab_widget, "Collision Analytics", "Field mapping saved."
        )
        self.dock.refresh_from_layer()

    def _reset_field_map_defaults(self) -> None:
        """Reset field map to defaults."""
        self.dock.field_map = dict(DEFAULT_FIELD_MAP)
        self._save_field_map()

    def populate_selectors(self) -> None:
        """Populate field selectors with available layer fields."""
        if self.dock.layer is None:
            return
        names = [f.name() for f in self.dock.layer.fields()]
        for key, cb in self.field_selectors.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")  # allow empty
            cb.addItems(names)
            mapped = self.dock.field_map.get(key, "")
            if mapped in names:
                cb.setCurrentText(mapped)
            cb.blockSignals(False)

    def refresh(self) -> None:
        """Refresh the tab."""
        self.populate_selectors()
