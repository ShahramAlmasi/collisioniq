from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

class CheckListFilterBox(QGroupBox):
    """Reusable filter box: search + All/None + checklist items (code stored in Qt.UserRole)."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")

        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        self.btn_all.setMaximumWidth(60)
        self.btn_none.setMaximumWidth(60)

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_all)
        top.addWidget(self.btn_none)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(self.list, 1)
        self.setLayout(root)

        self.search.textChanged.connect(self._apply_search)
        self.btn_all.clicked.connect(lambda: self._set_visible(Qt.Checked))
        self.btn_none.clicked.connect(lambda: self._set_visible(Qt.Unchecked))

    def _apply_search(self, txt: str) -> None:
        t = (txt or "").strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(False if not t else (t not in it.text().lower()))

    def _set_visible(self, state: Qt.CheckState) -> None:
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.isHidden():
                continue
            it.setCheckState(state)
        self.list.blockSignals(False)
        self.list.itemChanged.emit(self.list.item(0)) if self.list.count() else None

    def selected_codes(self) -> Set[str]:
        out: Set[str] = set()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                code = it.data(Qt.UserRole)
                if code is not None:
                    out.add(str(code).strip())
        return out

    def set_items(self, items: List[Tuple[str, str]], checked: Optional[Set[str]] = None) -> None:
        """items: [(code, label_for_ui)]"""
        checked = checked or set()
        self.list.blockSignals(True)
        self.list.clear()
        for code, label in items:
            it = QListWidgetItem(label)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setData(Qt.UserRole, code)
            it.setCheckState(Qt.Checked if str(code).strip() in checked else Qt.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)

    def clear_checks(self) -> None:
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Unchecked)
        self.list.blockSignals(False)
