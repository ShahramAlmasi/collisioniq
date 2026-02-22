"""About Panel - Plugin information and credits."""
from __future__ import annotations

from typing import List

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class AboutPanel(QWidget):
    """Panel displaying plugin information and credits."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Collision Analytics")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "A QGIS plugin for exploratory analysis and practitioner-oriented "
            "interpretation of road collision data."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569;")
        layout.addWidget(desc)
        
        layout.addSpacing(20)
        
        # Sections
        self._add_section(layout, "Version", ["2.0.0 (Modernized UI)"])
        
        self._add_section(layout, "Author", [
            "Shahram Almasi",
            "Traffic Operations and Road Safety Engineer"
        ])
        
        self._add_section(layout, "Organisation", [
            "The Regional Municipality of Durham",
            "Developed in support of transportation safety analysis and Vision Zero-aligned practice."
        ])
        
        self._add_section(layout, "Features", [
            "• Interactive filtering with background processing",
            "• Virtual scrolling charts for performance",
            "• Data quality analysis and reporting",
            "• Configurable field mapping and decodes",
            "• Click-to-filter chart interactions",
            "• Export to CSV and PNG",
        ])
        
        # Disclaimer
        layout.addSpacing(20)
        
        disclaimer = QLabel(
            "Disclaimer: This plugin is intended as a decision-support and exploratory analysis tool only. "
            "Results are dependent on the quality, completeness, and interpretation of the underlying data. "
            "Outputs from this tool do not constitute engineering design, legal findings, or official collision statistics. "
            "Users are responsible for applying appropriate professional judgment, standards, and review when interpreting results."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("""
            color: #64748b;
            font-size: 10px;
            border: 1px solid #e2e8f0;
            background-color: #f8fafc;
            padding: 12px;
            border-radius: 4px;
        """)
        layout.addWidget(disclaimer)
        
        layout.addStretch(1)
        self.setLayout(layout)
    
    def _add_section(self, layout: QVBoxLayout, title: str, lines: List[str]) -> None:
        """Add a section to the about panel."""
        header = QLabel(f"{title}")
        header.setStyleSheet("font-weight: 600; color: #334155; margin-top: 8px;")
        layout.addWidget(header)
        
        for line in lines:
            body = QLabel(line)
            body.setWordWrap(True)
            body.setStyleSheet("color: #475569; margin-left: 8px;")
            layout.addWidget(body)
