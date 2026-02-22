"""Modern styled widgets and components for Collision Analytics."""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPainter, QPaintEvent
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)


# ============================================================================
# Design System Constants
# ============================================================================

class Colors:
    """Modern dark-mode color palette - higher contrast for QGIS."""
    # Backgrounds - lighter for better contrast
    BG_PRIMARY = "#1a1f2e"      # Main background (was #0d1117)
    BG_SECONDARY = "#242b3d"    # Cards/panels (was #161b22)
    BG_RAISED = "#2d364a"       # Elevated surfaces, inputs, hover (was #1c2433)
    
    # Text - brighter for readability
    TEXT_PRIMARY = "#ffffff"    # Primary text (was #f0f6fc)
    TEXT_SECONDARY = "#a8b5c8"  # Secondary/muted text (was #8b949e)
    TEXT_MUTED = "#6b7a8f"      # Very muted text
    
    # Borders - more visible
    BORDER_DEFAULT = "rgba(255,255,255,0.15)"  # Subtle borders (was 0.08)
    BORDER_HOVER = "rgba(255,255,255,0.25)"
    
    # Accents - brighter
    ACCENT_PRIMARY = "#4fc3f7"  # Cyan - primary actions (was #38bdf8)
    ACCENT_SUCCESS = "#66bb6a"  # Green - success/positive (was #22c55e)
    ACCENT_WARNING = "#ffb74d"  # Amber - warnings (was #f59e0b)
    ACCENT_DANGER = "#ef5350"   # Red - errors/danger (was #ef4444)
    ACCENT_INFO = "#7986cb"     # Indigo - info (was #818cf8)
    
    # Legacy mappings for backward compatibility
    BG_TERTIARY = BG_RAISED
    TEXT_MUTED = TEXT_SECONDARY
    TEXT_DISABLED = "#484f58"
    BORDER_HOVER = "rgba(255,255,255,0.12)"
    BORDER_FOCUS = ACCENT_PRIMARY
    ACCENT_PURPLE = ACCENT_INFO


class Spacing:
    """Consistent spacing scale."""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Typography:
    """Typography scale."""
    XS = 10
    SM = 11
    BASE = 13
    LG = 15
    XL = 18
    XXL = 24
    
    # Legacy mappings
    XXXL = XXL
    DISPLAY = XXL


# ============================================================================
# Base Stylesheet
# ============================================================================

BASE_STYLESHEET = f"""
/* Main Application Background */
QWidget {{
    background-color: {Colors.BG_PRIMARY};
    color: {Colors.TEXT_PRIMARY};
    font-size: {Typography.BASE}px;
}}

/* Group Boxes - Card Style */
QGroupBox {{
    background-color: {Colors.BG_SECONDARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    padding: {Spacing.MD}px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {Colors.TEXT_SECONDARY};
    font-size: {Typography.SM}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Push Buttons */
QPushButton {{
    background-color: {Colors.BG_RAISED};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 8px 16px;
    color: {Colors.TEXT_PRIMARY};
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {Colors.BORDER_HOVER};
    border-color: {Colors.BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: {Colors.ACCENT_PRIMARY};
}}

QPushButton:disabled {{
    background-color: {Colors.BG_SECONDARY};
    color: {Colors.TEXT_DISABLED};
    border-color: {Colors.BORDER_DEFAULT};
}}

QPushButton#primary {{
    background-color: {Colors.ACCENT_PRIMARY};
    border-color: {Colors.ACCENT_PRIMARY};
    color: {Colors.BG_PRIMARY};
}}

QPushButton#primary:hover {{
    background-color: #7dd3fc;
}}

QPushButton#danger {{
    background-color: {Colors.ACCENT_DANGER};
    border-color: {Colors.ACCENT_DANGER};
    color: white;
}}

QPushButton#success {{
    background-color: {Colors.ACCENT_SUCCESS};
    border-color: {Colors.ACCENT_SUCCESS};
    color: {Colors.BG_PRIMARY};
}}

/* Line Edits */
QLineEdit {{
    background-color: {Colors.BG_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    color: {Colors.TEXT_PRIMARY};
}}

QLineEdit:focus {{
    border-color: {Colors.ACCENT_PRIMARY};
}}

QLineEdit::placeholder {{
    color: {Colors.TEXT_SECONDARY};
}}

/* Check Boxes */
QCheckBox {{
    spacing: 8px;
    color: {Colors.TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {Colors.BORDER_DEFAULT};
    background-color: {Colors.BG_PRIMARY};
}}

QCheckBox::indicator:checked {{
    background-color: {Colors.ACCENT_PRIMARY};
    border-color: {Colors.ACCENT_PRIMARY};
}}

QCheckBox::indicator:hover {{
    border-color: {Colors.BORDER_HOVER};
}}

/* Combo Boxes */
QComboBox {{
    background-color: {Colors.BG_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    color: {Colors.TEXT_PRIMARY};
}}

QComboBox:hover {{
    border-color: {Colors.BORDER_HOVER};
}}

QComboBox:focus {{
    border-color: {Colors.ACCENT_PRIMARY};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {Colors.BG_SECONDARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    selection-background-color: {Colors.ACCENT_PRIMARY};
}}

/* Date Edits */
QDateEdit {{
    background-color: {Colors.BG_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    color: {Colors.TEXT_PRIMARY};
}}

QDateEdit::drop-down {{
    border: none;
    width: 24px;
}}

/* List Widgets */
QListWidget {{
    background-color: {Colors.BG_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
    margin: 2px 0;
}}

QListWidget::item:hover {{
    background-color: {Colors.BG_RAISED};
}}

QListWidget::item:selected {{
    background-color: rgba(56, 189, 248, 0.25);
}}

/* Scroll Bars */
QScrollBar:vertical {{
    background-color: {Colors.BG_SECONDARY};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {Colors.BORDER_HOVER};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {Colors.BG_SECONDARY};
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {Colors.BORDER_HOVER};
}}

/* Progress Bar */
QProgressBar {{
    background-color: {Colors.BG_RAISED};
    border-radius: 4px;
    text-align: center;
    color: {Colors.TEXT_PRIMARY};
}}

QProgressBar::chunk {{
    background-color: {Colors.ACCENT_PRIMARY};
    border-radius: 4px;
}}

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 8px;
    background-color: {Colors.BG_SECONDARY};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    border: none;
    padding: 10px 16px;
    margin-right: 4px;
    color: {Colors.TEXT_SECONDARY};
    font-weight: 500;
}}

QTabBar::tab:hover {{
    color: {Colors.TEXT_PRIMARY};
}}

QTabBar::tab:selected {{
    color: {Colors.ACCENT_PRIMARY};
    border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
}}

/* Table Widget */
QTableWidget {{
    background-color: {Colors.BG_PRIMARY};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 6px;
    gridline-color: {Colors.BORDER_DEFAULT};
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

QTableWidget::item:selected {{
    background-color: rgba(56, 189, 248, 0.25);
}}

QHeaderView::section {{
    background-color: {Colors.BG_SECONDARY};
    color: {Colors.TEXT_SECONDARY};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {Colors.BORDER_DEFAULT};
    font-weight: 600;
}}

/* Splitter */
QSplitter::handle {{
    background-color: {Colors.BORDER_DEFAULT};
}}

QSplitter::handle:hover {{
    background-color: {Colors.ACCENT_PRIMARY};
}}
"""


# ============================================================================
# Modern Widget Components
# ============================================================================

class Card(QFrame):
    """Modern card component with elevated appearance."""
    
    def __init__(self, parent=None, elevated: bool = False):
        super().__init__(parent)
        self.elevated = elevated
        self._setup_style()
    
    def _setup_style(self):
        self.setFrameStyle(QFrame.NoFrame)
        bg = Colors.BG_SECONDARY
        self.setStyleSheet(f"""
            Card {{
                background-color: {bg};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("Card")


class Badge(QLabel):
    """Status badge/pill component with variants."""
    
    VARIANTS = {
        "default": (Colors.BG_RAISED, Colors.TEXT_SECONDARY),
        "primary": (Colors.ACCENT_PRIMARY, Colors.BG_PRIMARY),
        "success": (Colors.ACCENT_SUCCESS, Colors.BG_PRIMARY),
        "warning": (Colors.ACCENT_WARNING, Colors.BG_PRIMARY),
        "danger": (Colors.ACCENT_DANGER, "white"),
        "info": (Colors.ACCENT_INFO, "white"),
    }
    
    def __init__(self, text: str = "", variant: str = "default", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._apply_style()
    
    def _apply_style(self):
        bg, fg = self.VARIANTS.get(self.variant, self.VARIANTS["default"])
        self.setStyleSheet(f"""
            Badge {{
                background-color: {bg};
                color: {fg};
                border-radius: 12px;
                padding: 4px 10px;
                font-size: {Typography.XS}px;
                font-weight: 600;
            }}
        """)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignCenter)
    
    def set_variant(self, variant: str):
        self.variant = variant
        self._apply_style()
    
    def set_text(self, text: str):
        """Set badge text."""
        self.setText(text)


class KPICard(QFrame):
    """Key Performance Indicator card with left accent border."""
    
    def __init__(self, title: str, value: str = "—", subtitle: str = "", 
                 accent_color: str = Colors.ACCENT_PRIMARY, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self._build_ui(title, value, subtitle)
    
    def _build_ui(self, title: str, value: str, subtitle: str):
        self.setFrameStyle(QFrame.NoFrame)
        self.setStyleSheet(f"""
            KPICard {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-left: 3px solid {self.accent_color};
                border-radius: 8px;
            }}
        """)
        self.setObjectName("KPICard")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: {Typography.XXL}px;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-size: {Typography.SM}px;
            color: {Colors.TEXT_SECONDARY};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet(f"""
                font-size: {Typography.XS}px;
                color: {Colors.TEXT_SECONDARY};
            """)
            layout.addWidget(self.subtitle_label)
        
        self.setLayout(layout)
        self.setMinimumWidth(140)
    
    def set_value(self, value: str, color: Optional[str] = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"""
                font-size: {Typography.XXL}px;
                font-weight: 700;
                color: {color};
            """)
    
    def set_subtitle(self, subtitle: str):
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(subtitle)


class StatusIndicator(QWidget):
    """Dot status indicator with optional label."""
    
    COLORS = {
        "idle": Colors.TEXT_SECONDARY,
        "active": Colors.ACCENT_SUCCESS,
        "processing": Colors.ACCENT_PRIMARY,
        "warning": Colors.ACCENT_WARNING,
        "error": Colors.ACCENT_DANGER,
    }
    
    def __init__(self, status: str = "idle", text: str = "", parent=None):
        super().__init__(parent)
        self.status = status
        self.text = text
        self._build_ui()
    
    def _build_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {self.COLORS.get(self.status, Colors.TEXT_SECONDARY)};")
        layout.addWidget(self.dot)
        
        if self.text:
            self.text_label = QLabel(self.text)
            self.text_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            layout.addWidget(self.text_label)
        
        layout.addStretch(1)
        self.setLayout(layout)
        self.setFixedHeight(20)
    
    def set_status(self, status: str, text: Optional[str] = None):
        self.status = status
        self.dot.setStyleSheet(f"color: {self.COLORS.get(status, Colors.TEXT_SECONDARY)};")
        if text and hasattr(self, 'text_label'):
            self.text_label.setText(text)


class CollapsibleSection(QGroupBox):
    """Collapsible section with header toggle."""
    
    def __init__(self, title: str, parent=None, expanded: bool = True):
        super().__init__(parent)
        self._expanded = expanded
        self._content: Optional[QWidget] = None
        self._animation: Optional[QPropertyAnimation] = None
        
        self._build_header(title)
        self._apply_style()
    
    def _build_header(self, title: str):
        self.header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toggle_btn = QPushButton("▼" if self._expanded else "▶")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_SECONDARY};
                font-size: 10px;
                padding: 0;
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        
        self.header.setLayout(header_layout)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 8, 12, 12)
        main_layout.setSpacing(8)
        main_layout.addWidget(self.header)
        
        self._content_container = QWidget()
        self._content_container.setVisible(self._expanded)
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_container.setLayout(self._content_layout)
        
        main_layout.addWidget(self._content_container)
        self.setLayout(main_layout)
    
    def _apply_style(self):
        self.setStyleSheet(f"""
            CollapsibleSection {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                margin-top: 0px;
            }}
        """)
        self.setObjectName("CollapsibleSection")
    
    def _toggle(self):
        self._expanded = not self._expanded
        self.toggle_btn.setText("▼" if self._expanded else "▶")
        self._content_container.setVisible(self._expanded)
    
    def set_content(self, widget: QWidget):
        """Set the content widget for this section."""
        # Clear existing
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        self._content_layout.addWidget(widget)
        self._content = widget
    
    def add_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)
    
    def is_expanded(self) -> bool:
        return self._expanded
    
    def set_expanded(self, expanded: bool):
        if self._expanded != expanded:
            self._toggle()


class CheckListFilterBox(QGroupBox):
    """Enhanced filter box with search, All/None, and checklist items."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        
        self._selected_count = 0
        self._total_count = 0
        
        self._build_ui()
    
    def _build_ui(self):
        # Header with search and actions
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search values...")
        self.search.setClearButtonEnabled(True)
        
        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        self.btn_all.setFixedWidth(50)
        self.btn_none.setFixedWidth(50)
        self.btn_all.setStyleSheet(f"padding: 4px 8px; font-size: {Typography.XS}px;")
        self.btn_none.setStyleSheet(f"padding: 4px 8px; font-size: {Typography.XS}px;")
        
        header_layout.addWidget(self.search, 1)
        header_layout.addWidget(self.btn_all)
        header_layout.addWidget(self.btn_none)
        header.setLayout(header_layout)
        
        # Status badge
        self.status_badge = Badge("0 selected", "default")
        
        # List widget
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setMaximumHeight(200)
        
        # Layout
        root = QVBoxLayout()
        root.setSpacing(8)
        root.addWidget(header)
        root.addWidget(self.list, 1)
        
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_badge)
        status_row.addStretch(1)
        root.addLayout(status_row)
        
        self.setLayout(root)
        
        # Connections
        self.search.textChanged.connect(self._apply_search)
        self.btn_all.clicked.connect(lambda: self._set_visible(Qt.Checked))
        self.btn_none.clicked.connect(lambda: self._set_visible(Qt.Unchecked))
        self.list.itemChanged.connect(self._on_item_changed)
    
    def _apply_search(self, txt: str):
        t = (txt or "").strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(False if not t else (t not in it.text().lower()))
    
    def _set_visible(self, state: Qt.CheckState):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden():
                it.setCheckState(state)
        self.list.blockSignals(False)
        self.list.itemChanged.emit(self.list.item(0) if self.list.count() else None)
        self._update_badge()
    
    def _on_item_changed(self, item):
        self._update_badge()
    
    def _update_badge(self):
        selected = len(self.selected_codes())
        total = self.list.count()
        
        self.status_badge.setText(f"{selected} of {total}")
        if selected == 0:
            self.status_badge.set_variant("default")
        elif selected == total:
            self.status_badge.set_variant("success")
        else:
            self.status_badge.set_variant("primary")
    
    def selected_codes(self) -> Set[str]:
        out: Set[str] = set()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                code = it.data(Qt.UserRole)
                if code is not None:
                    out.add(str(code).strip())
        return out
    
    def set_items(self, items: List[Tuple[str, str]], checked: Optional[Set[str]] = None):
        """Set items: [(code, label_for_ui)]"""
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
        self._update_badge()
    
    def clear_checks(self):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Unchecked)
        self.list.blockSignals(False)
        self._update_badge()


class SegmentedControl(QWidget):
    """iOS-style segmented control for tab-like selection."""
    
    selection_changed = None  # Callback: (index, key) -> None
    
    def __init__(self, segments: List[Tuple[str, str]], parent=None):
        """segments: [(key, label), ...]"""
        super().__init__(parent)
        self.segments = segments
        self.buttons: List[QPushButton] = []
        self._selected_index = 0
        self._build_ui()
    
    def _build_ui(self):
        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: {Colors.BG_RAISED};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        self.setObjectName("SegmentedControl")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        for idx, (key, label) in enumerate(self.segments):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 16px;
                    color: {Colors.TEXT_SECONDARY};
                    font-weight: 500;
                    font-size: {Typography.SM}px;
                }}
                QPushButton:checked {{
                    background-color: {Colors.ACCENT_PRIMARY};
                    color: {Colors.BG_PRIMARY};
                }}
                QPushButton:hover:!checked {{
                    color: {Colors.TEXT_PRIMARY};
                }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self._on_select(i))
            self.buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch(1)
        self.setLayout(layout)
        self.setFixedHeight(40)
    
    def _on_select(self, index: int):
        if self._selected_index == index:
            return
        
        self.buttons[self._selected_index].setChecked(False)
        self._selected_index = index
        self.buttons[index].setChecked(True)
        
        if self.selection_changed:
            self.selection_changed(index, self.segments[index][0])
    
    def set_selected(self, index: int):
        if 0 <= index < len(self.buttons):
            self._on_select(index)
    
    def current_key(self) -> str:
        return self.segments[self._selected_index][0]


class IconButton(QPushButton):
    """Icon-only button (32x32)."""
    
    def __init__(self, icon_text: str, tooltip: str = "", parent=None):
        super().__init__(icon_text, parent)
        self.setToolTip(tooltip)
        self.setFixedSize(32, 32)
        self.setStyleSheet(f"""
            IconButton {{
                background-color: transparent;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 14px;
            }}
            IconButton:hover {{
                background-color: {Colors.BG_RAISED};
                border-color: {Colors.BORDER_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.setObjectName("IconButton")


class EmptyState(QWidget):
    """Empty state widget with icon, title, and description."""
    
    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self._build_ui(icon, title, description)
    
    def _build_ui(self, icon: str, title: str, description: str):
        self.setStyleSheet(f"background: transparent;")
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 48px; color: {Colors.TEXT_SECONDARY};")
        icon_label.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {Typography.XL}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        title_label.setAlignment(Qt.AlignCenter)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)
        
        self.setLayout(layout)


class Toolbar(QWidget):
    """Horizontal toolbar with action buttons."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self):
        self.setStyleSheet(f"""
            Toolbar {{
                background-color: {Colors.BG_SECONDARY};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        self.setObjectName("Toolbar")
        self.setFixedHeight(48)
        
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(12, 6, 12, 6)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)
    
    def add_button(self, text: str, callback: Callable, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if primary:
            btn.setObjectName("primary")
        btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn
    
    def add_stretch(self):
        self.layout.addStretch(1)
    
    def add_widget(self, widget: QWidget):
        self.layout.addWidget(widget)


def apply_modern_stylesheet(app_or_widget):
    """Apply the modern dark-mode stylesheet to a widget or application."""
    app_or_widget.setStyleSheet(BASE_STYLESHEET)
