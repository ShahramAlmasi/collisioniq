"""About tab for Collision Analytics plugin."""

from __future__ import annotations

from typing import List

from qgis.PyQt.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .base_tab import BaseTab


class AboutTab(BaseTab):
    """Tab for displaying plugin information and disclaimer."""

    def build(self) -> QWidget:
        """Build the about tab UI."""
        root = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Plugin Information
        self._add_section(
            layout,
            "Plugin Information",
            [
                "<b>Name:</b> Collision Analytics",
                "<b>Description:</b> A QGIS plugin for exploratory analysis and practitioner-oriented interpretation of road collision data.",
            ],
        )

        # Author
        self._add_section(
            layout,
            "Author",
            [
                "<b>Name:</b> Shahram Almasi",
                "<b>Role:</b> Traffic Operations and Road Safety Engineer",
            ],
        )

        # Organisation
        self._add_section(
            layout,
            "Organisation",
            [
                "<b>Employer:</b> The Regional Municipality of Durham",
                "<b>Context:</b> Developed in support of transportation safety analysis and Vision Zero-aligned practice.",
            ],
        )

        # Disclaimer
        disclaimer_text = (
            "This plugin is intended as a decision-support and exploratory analysis tool only. "
            "Results are dependent on the quality, completeness, and interpretation of the underlying data. "
            "Outputs from this tool do not constitute engineering design, legal findings, or official collision statistics. "
            "Users are responsible for applying appropriate professional judgment, standards, and review when interpreting results."
        )
        self._add_section(layout, "Disclaimer", [disclaimer_text])

        layout.addStretch(1)
        root.setLayout(layout)
        self.tab_widget = root
        return root

    def _add_section(self, layout: QVBoxLayout, title: str, lines: List[str]) -> None:
        """Add a section to the about tab."""
        header = QLabel(f"<b>{title}</b>")
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 12pt;")
        layout.addWidget(header)

        for line in lines:
            body = QLabel(line)
            body.setWordWrap(True)
            layout.addWidget(body)

        layout.addSpacing(8)
