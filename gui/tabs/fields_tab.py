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

from ...core.config import DEFAULT_FIELD_MAP
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

        return root

    def _on_field_mapping_changed(self, *_) -> None:
        """Handle field mapping changes."""
        for key, cb in self.field_selectors.items():
            name = cb.currentText().strip()
            self.dock.controller.field_map[key] = name

    def _save_field_map(self) -> None:
        """Save field map to settings."""
        self.dock.controller.save_field_map()
        QMessageBox.information(
            self.tab_widget, "Collision Analytics", "Field mapping saved."
        )
        self.dock.controller.refresh_from_layer()

    def _reset_field_map_defaults(self) -> None:
        """Reset field map to defaults."""
        self.dock.controller.field_map = dict(DEFAULT_FIELD_MAP)
        self.populate_selectors()
        self._save_field_map()

    def populate_selectors(self) -> None:
        """Populate field selectors with available layer fields."""
        if self.layer is None:
            return
        names = [f.name() for f in self.layer.fields()]
        for key, cb in self.field_selectors.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")  # allow empty
            cb.addItems(names)
            mapped = self.dock.controller.field_map.get(key, "")
            if mapped in names:
                cb.setCurrentText(mapped)
            cb.blockSignals(False)

    def refresh(self) -> None:
        """Refresh the tab."""
        self.populate_selectors()
