from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .gui.dock import CollisionAnalyticsDockWidget

class CollisionAnalyticsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None

    def initGui(self):
        self.action = QAction(QIcon(), "Collision Analytics", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle_dock)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Collision Analytics", self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("&Collision Analytics", self.action)
            self.action.deleteLater()
            self.action = None
        self._close_dock()

    def _toggle_dock(self, checked: bool):
        if checked:
            self._open_dock()
        else:
            # Hide, but keep the dock instance around; it's faster to reopen.
            if self.dock is not None:
                self.dock.hide()

    def _open_dock(self):
        if self.dock is None:
            self.dock = CollisionAnalyticsDockWidget(self.iface)
            self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.dock.visibilityChanged.connect(self._on_dock_visibility_changed)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.dock.raise_()

    def _close_dock(self):
        if self.dock is None:
            return
        try:
            self.dock.visibilityChanged.disconnect(self._on_dock_visibility_changed)
        except Exception:
            pass
        self.dock.close()
        self.dock.setParent(None)
        self.dock.deleteLater()
        self.dock = None

    def _on_dock_visibility_changed(self, visible: bool):
        if self.action:
            self.action.blockSignals(True)
            self.action.setChecked(visible)
            self.action.blockSignals(False)
