"""About Panel - Modern plugin information and credits."""
from __future__ import annotations

from typing import List

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
)

from ..modern_widgets import (
    Card,
    Colors,
    Badge,
    Typography,
)


class AboutPanel(QWidget):
    """Modern panel displaying plugin information and credits."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build modern about panel UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # ===== Header Card =====
        header = self._build_header_card()
        layout.addWidget(header)
        
        # ===== Info Cards =====
        info_grid = self._build_info_grid()
        layout.addWidget(info_grid)
        
        # ===== Features Card =====
        features = self._build_features_card()
        layout.addWidget(features)
        
        # ===== Disclaimer Card =====
        disclaimer = self._build_disclaimer_card()
        layout.addWidget(disclaimer)
        
        layout.addStretch(1)
        self.setLayout(layout)
    
    def _build_header_card(self) -> QWidget:
        """Build header card with title and version."""
        card = Card()
        card.setStyleSheet(f"""
            Card {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {Colors.ACCENT_PRIMARY},
                    stop: 1 {Colors.ACCENT_PURPLE}
                );
                border-radius: 12px;
                padding: 24px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Icon and title row
        title_row = QHBoxLayout()
        
        icon = QLabel("🚦")
        icon.setStyleSheet("font-size: 48px;")
        
        title_col = QVBoxLayout()
        title = QLabel("Collision Analytics")
        title.setStyleSheet(f"""
            font-size: {Typography.XXXL}px;
            font-weight: 700;
            color: white;
        """)
        
        subtitle = QLabel("QGIS Plugin for Road Safety Analysis")
        subtitle.setStyleSheet(f"""
            font-size: {Typography.BASE}px;
            color: rgba(255, 255, 255, 0.8);
        """)
        
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        
        title_row.addWidget(icon)
        title_row.addLayout(title_col, 1)
        
        # Version badge
        version = Badge("v2.0 Modern UI", "default")
        version.setStyleSheet(f"""
            Badge {{
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: 600;
            }}
        """)
        title_row.addWidget(version)
        
        layout.addLayout(title_row)
        card.setLayout(layout)
        
        return card
    
    def _build_info_grid(self) -> QWidget:
        """Build info grid with author and organization."""
        grid = QWidget()
        grid.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Author card
        author_card = Card()
        author_card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        author_layout = QVBoxLayout()
        author_layout.setSpacing(8)
        
        author_title = QLabel("👤 Author")
        author_title.setStyleSheet(f"""
            font-size: {Typography.SM}px;
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            text-transform: uppercase;
        """)
        
        author_name = QLabel("Shahram Almasi")
        author_name.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        author_role = QLabel("Traffic Operations and Road Safety Engineer")
        author_role.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        author_role.setWordWrap(True)
        
        author_layout.addWidget(author_title)
        author_layout.addWidget(author_name)
        author_layout.addWidget(author_role)
        author_card.setLayout(author_layout)
        
        # Organization card
        org_card = Card()
        org_card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        org_layout = QVBoxLayout()
        org_layout.setSpacing(8)
        
        org_title = QLabel("🏢 Organization")
        org_title.setStyleSheet(f"""
            font-size: {Typography.SM}px;
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            text-transform: uppercase;
        """)
        
        org_name = QLabel("The Regional Municipality of Durham")
        org_name.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        org_desc = QLabel("Developed in support of transportation safety analysis and Vision Zero-aligned practice.")
        org_desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        org_desc.setWordWrap(True)
        
        org_layout.addWidget(org_title)
        org_layout.addWidget(org_name)
        org_layout.addWidget(org_desc)
        org_card.setLayout(org_layout)
        
        layout.addWidget(author_card, 1)
        layout.addWidget(org_card, 1)
        grid.setLayout(layout)
        
        return grid
    
    def _build_features_card(self) -> QWidget:
        """Build features card."""
        card = Card()
        card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        title = QLabel("✨ Features")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(title)
        
        features_grid = QHBoxLayout()
        features_grid.setSpacing(16)
        
        # Column 1
        col1 = QVBoxLayout()
        for feature in [
            "🎯 Interactive filtering with background processing",
            "📊 Virtual scrolling charts for performance",
            "📈 KPI dashboard with severity breakdowns",
        ]:
            lbl = QLabel(feature)
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            col1.addWidget(lbl)
        
        # Column 2
        col2 = QVBoxLayout()
        for feature in [
            "✓ Data quality analysis and reporting",
            "⚙️ Configurable field mapping and decodes",
            "🖱️ Click-to-filter chart interactions",
        ]:
            lbl = QLabel(feature)
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            col2.addWidget(lbl)
        
        features_grid.addLayout(col1, 1)
        features_grid.addLayout(col2, 1)
        
        layout.addLayout(features_grid)
        card.setLayout(layout)
        
        return card
    
    def _build_disclaimer_card(self) -> QWidget:
        """Build disclaimer card."""
        card = Card()
        card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.ACCENT_WARNING}10;
                border: 1px solid {Colors.ACCENT_WARNING}40;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        title = QLabel("⚠️ Disclaimer")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.ACCENT_WARNING};
        """)
        layout.addWidget(title)
        
        disclaimer = QLabel(
            "This plugin is intended as a decision-support and exploratory analysis tool only. "
            "Results are dependent on the quality, completeness, and interpretation of the underlying data. "
            "Outputs from this tool do not constitute engineering design, legal findings, or official collision statistics. "
            "Users are responsible for applying appropriate professional judgment, standards, and review when interpreting results."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        
        layout.addWidget(disclaimer)
        card.setLayout(layout)
        
        return card
