"""Base tab class for Collision Analytics plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout

if TYPE_CHECKING:
    from ..dock import CollisionAnalyticsDockWidget


class BaseTab:
    """Base class for all tabs in the Collision Analytics dock."""

    def __init__(self, dock: CollisionAnalyticsDockWidget) -> None:
        self.dock = dock
        self.tab_widget: Optional[QWidget] = None
        self._layout: Optional[QVBoxLayout] = None

    def build(self) -> QWidget:
        """Build and return the tab widget. Must be implemented by subclasses."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Refresh the tab when data changes. Override in subclasses if needed."""
        pass

    def reset(self) -> None:
        """Reset the tab to default state. Override in subclasses if needed."""
        pass

    @property
    def iface(self):
        """Access the QGIS interface from the dock widget."""
        return self.dock.iface

    @property
    def layer(self):
        """Access the current layer from the dock widget."""
        return self.dock.controller.layer

    @property
    def field_map(self):
        """Access the field map from the dock widget."""
        return self.dock.controller.field_map

    @property
    def filtered_rows(self):
        """Access filtered rows from the dock widget."""
        return self.dock.controller.filtered_rows

    @property
    def filtered_fids(self):
        """Access filtered feature IDs from the dock widget."""
        return self.dock.controller.filtered_fids

    @property
    def decodes(self):
        """Access the decode registry from the dock widget."""
        return self.dock.controller.decodes

    def _make_scrollable(self, content: QWidget) -> QWidget:
        """Create a scrollable container for content."""
        from qgis.PyQt.QtWidgets import QScrollArea
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtWidgets import QSizePolicy

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(content)
        return scroll

    def _decode(self, concept_key: str, raw) -> str:
        """Decode a raw value using the decode registry."""
        return self.decodes.decode(concept_key, raw)
