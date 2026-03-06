"""Summary tab for Collision Analytics plugin."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core.utils import safe_str
from .base_tab import BaseTab


class SummaryTab(BaseTab):
    """Tab for displaying summary statistics and insights."""

    # Styles
    KPI_VALUE_STYLE = "font-size: 22px; font-weight: 600;"
    KPI_LABEL_STYLE = "color: #555;"
    SUMMARY_HEADER_STYLE = "font-weight: 600; font-size: 12px;"

    def __init__(self, dock) -> None:
        super().__init__(dock)
        self.kpi_total_value: QLabel | None = None
        self.kpi_fatal_value: QLabel | None = None
        self.kpi_severe_value: QLabel | None = None
        self.sev_fatal_value: QLabel | None = None
        self.sev_injury_value: QLabel | None = None
        self.sev_pdo_value: QLabel | None = None
        self.sev_unknown_value: QLabel | None = None
        self.exp_vehicles_value: QLabel | None = None
        self.exp_persons_value: QLabel | None = None
        self.exp_drivers_value: QLabel | None = None
        self.exp_occupants_value: QLabel | None = None
        self.exp_pedestrians_value: QLabel | None = None
        self.summary_status: QLabel | None = None
        self.risk_flag_labels: List[QLabel] = []
        self.risk_flag_empty: QLabel | None = None
        self.top_panels: Dict[str, List[Tuple[QLabel, QLabel]]] = {}

    def build(self) -> QWidget:
        """Build the summary tab UI."""
        root = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # KPI row
        kpi_row = self._build_kpi_row()
        layout.addWidget(kpi_row)

        # Summary content
        summary_container = self._build_summary_content()
        layout.addWidget(self._make_scrollable(summary_container), 1)

        root.setLayout(layout)
        self.tab_widget = root
        return root

    def _build_kpi_row(self) -> QWidget:
        """Build the KPI cards row."""
        kpi_row = QWidget()
        kpi_layout = QHBoxLayout()
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(8)

        kpi_total, self.kpi_total_value = self._make_kpi_card("Filtered collisions")
        kpi_fatal, self.kpi_fatal_value = self._make_kpi_card("Fatal collisions")
        kpi_severe, self.kpi_severe_value = self._make_kpi_card(
            "Severe share (Fatal + Injury)"
        )

        kpi_layout.addWidget(kpi_total)
        kpi_layout.addWidget(kpi_fatal)
        kpi_layout.addWidget(kpi_severe)
        kpi_layout.addStretch(1)

        kpi_row.setLayout(kpi_layout)
        return kpi_row

    def _build_summary_content(self) -> QWidget:
        """Build the main summary content."""
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # Status label
        self.summary_status = QLabel()
        self.summary_status.setWordWrap(True)
        self.summary_status.setStyleSheet("color: #555;")
        layout.addWidget(self.summary_status)

        # Severity breakdown
        layout.addWidget(self._make_section_header("Severity breakdown"))
        sev_grid = self._build_severity_grid()
        layout.addLayout(sev_grid)

        # Exposure totals
        layout.addWidget(self._make_section_header("Exposure totals"))
        exp_grid = self._build_exposure_grid()
        layout.addLayout(exp_grid)

        # Risk flags
        risk_frame = self._build_risk_flags_frame()
        layout.addWidget(risk_frame)

        # Top contributors
        layout.addWidget(self._make_section_header("Top contributors"))
        top_container = self._build_top_contributors()
        layout.addWidget(top_container)

        container.setLayout(layout)
        return container

    def _build_severity_grid(self) -> QGridLayout:
        """Build the severity breakdown grid."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        self.sev_fatal_value = QLabel("n/a")
        self.sev_fatal_value.setStyleSheet("font-weight: 600;")
        self.sev_injury_value = QLabel("n/a")
        self.sev_pdo_value = QLabel("n/a")
        self.sev_unknown_value = QLabel("n/a")

        self._add_grid_row(grid, 0, "Fatal", self.sev_fatal_value)
        self._add_grid_row(grid, 1, "Injury", self.sev_injury_value)
        self._add_grid_row(grid, 2, "PDO", self.sev_pdo_value)
        self._add_grid_row(grid, 3, "Unknown / Blank", self.sev_unknown_value)

        return grid

    def _build_exposure_grid(self) -> QGridLayout:
        """Build the exposure totals grid."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        self.exp_vehicles_value = QLabel("n/a")
        self.exp_persons_value = QLabel("n/a")
        self.exp_drivers_value = QLabel("n/a")
        self.exp_occupants_value = QLabel("n/a")
        self.exp_pedestrians_value = QLabel("n/a")

        self._add_grid_row(grid, 0, "Vehicles", self.exp_vehicles_value)
        self._add_grid_row(grid, 1, "Persons", self.exp_persons_value)
        self._add_grid_row(grid, 2, "Drivers", self.exp_drivers_value)
        self._add_grid_row(grid, 3, "Occupants", self.exp_occupants_value)
        self._add_grid_row(grid, 4, "Pedestrians", self.exp_pedestrians_value)

        return grid

    def _build_risk_flags_frame(self) -> QFrame:
        """Build the risk flags frame."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { border: 1px solid #f0d0d0; border-radius: 4px; background: #fff7f7; }"
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(self._make_section_header("Risk flags"))

        risk_flags_layout = QVBoxLayout()
        risk_flags_layout.setSpacing(4)

        self.risk_flag_labels = []
        for _ in range(3):
            label = QLabel()
            label.setWordWrap(True)
            label.setStyleSheet("color: #b00020;")
            risk_flags_layout.addWidget(label)
            self.risk_flag_labels.append(label)

        self.risk_flag_empty = QLabel()
        self.risk_flag_empty.setWordWrap(True)
        self.risk_flag_empty.setStyleSheet("color: #2e7d32;")
        risk_flags_layout.addWidget(self.risk_flag_empty)

        layout.addLayout(risk_flags_layout)
        frame.setLayout(layout)
        return frame

    def _build_top_contributors(self) -> QWidget:
        """Build the top contributors section."""
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        impact_panel, impact_rows = self._make_top_panel("Impact type")
        location_panel, location_rows = self._make_top_panel("Accident location")
        muni_panel, muni_rows = self._make_top_panel("Municipality")

        self.top_panels["impact_type"] = impact_rows
        self.top_panels["accident_location"] = location_rows
        self.top_panels["municipality"] = muni_rows

        layout.addWidget(impact_panel)
        layout.addWidget(location_panel)
        layout.addWidget(muni_panel)
        container.setLayout(layout)

        return container

    def _make_kpi_card(self, title: str) -> Tuple[QFrame, QLabel]:
        """Create a KPI card with value and title."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #d6d6d6; border-radius: 4px; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        value = QLabel("n/a")
        value.setStyleSheet(self.KPI_VALUE_STYLE)
        title_label = QLabel(title)
        title_label.setStyleSheet(self.KPI_LABEL_STYLE)

        layout.addWidget(value)
        layout.addWidget(title_label)
        frame.setLayout(layout)

        return frame, value

    def _make_section_header(self, title: str) -> QLabel:
        """Create a section header label."""
        label = QLabel(title)
        label.setStyleSheet(self.SUMMARY_HEADER_STYLE)
        return label

    def _add_grid_row(
        self, grid: QGridLayout, row: int, title: str, value_label: QLabel
    ) -> None:
        """Add a row to a grid layout."""
        label = QLabel(title)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(label, row, 0)
        grid.addWidget(value_label, row, 1)

    def _make_top_panel(
        self, title: str, rows: int = 5
    ) -> Tuple[QFrame, List[Tuple[QLabel, QLabel]]]:
        """Create a top contributors panel."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #e0e0e0; border-radius: 4px; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header = QLabel(title)
        header.setStyleSheet(self.SUMMARY_HEADER_STYLE)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)

        row_labels: List[Tuple[QLabel, QLabel]] = []
        for row in range(rows):
            name = QLabel()
            count = QLabel()
            name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            count.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(name, row, 0)
            grid.addWidget(count, row, 1)
            row_labels.append((name, count))

        layout.addLayout(grid)
        frame.setLayout(layout)

        return frame, row_labels

    def _set_kpi_value(
        self, label: QLabel | None, value: str, accent: str | None = None
    ) -> None:
        """Set a KPI value with optional color accent."""
        if label is None:
            return
        style = self.KPI_VALUE_STYLE
        if accent:
            style = f"{style} color: {accent};"
        label.setStyleSheet(style)
        label.setText(value)

    def _set_risk_flags(self, flags: List[str], empty_text: str) -> None:
        """Set the risk flags display."""
        for label in self.risk_flag_labels:
            label.setVisible(False)
        if self.risk_flag_empty:
            self.risk_flag_empty.setVisible(False)

        if not flags:
            if self.risk_flag_empty:
                self.risk_flag_empty.setText(empty_text)
                self.risk_flag_empty.setVisible(True)
            return

        for idx, text in enumerate(flags[: len(self.risk_flag_labels)]):
            label = self.risk_flag_labels[idx]
            label.setText(text)
            label.setVisible(True)

    def _fill_top_panel(
        self,
        rows: List[Tuple[QLabel, QLabel]],
        pairs: List[Tuple[str, int]],
        empty_text: str = "None",
    ) -> None:
        """Fill a top panel with data."""
        if not pairs:
            for idx, (name, count) in enumerate(rows):
                if idx == 0:
                    name.setText(empty_text)
                    count.setText("")
                    name.setVisible(True)
                    count.setVisible(False)
                else:
                    name.setVisible(False)
                    count.setVisible(False)
            return

        for idx, (name, count) in enumerate(rows):
            if idx < len(pairs):
                label, value = pairs[idx]
                name.setText(str(label))
                count.setText(str(value))
                name.setVisible(True)
                count.setVisible(True)
            else:
                name.setVisible(False)
                count.setVisible(False)

    def _sum_field(self, concept: str) -> float:
        """Sum a numeric field across all filtered rows."""
        field = self.field_map.get(concept)
        if not field:
            return 0.0
        s = 0.0
        for r in self.filtered_rows:
            try:
                v = float(r.get(field) or 0)
            except Exception:
                v = 0.0
            s += v
        return s

    def _top_list(self, concept_key: str, n: int) -> List[Tuple[str, int]]:
        """Get top N values for a concept."""
        field = self.field_map.get(concept_key)
        if not field:
            return []
        c = Counter()
        for r in self.filtered_rows:
            raw = safe_str(r.get(field)).strip()
            lab = self._decode(concept_key, raw) if raw else "Unknown / blank"
            c[lab] += 1
        return c.most_common(n)

    def refresh(self) -> None:
        """Refresh the summary with current data."""
        rows = self.filtered_rows or []
        total = len(rows)

        if total == 0:
            self.set_idle_state()
            return

        # Calculate severity counts
        sev_field = self.field_map.get("accident_class")
        sev_counts: Dict[str, int] = {}
        if sev_field:
            c = Counter()
            for r in rows:
                raw = safe_str(r.get(sev_field)).strip()
                lab = self._decode("accident_class", raw) if raw else "Unknown / blank"
                c[lab] += 1
            sev_counts = dict(c)

        fatal = sev_counts.get("Fatal", 0)
        injury = sev_counts.get("Injury", 0)
        pdo = sev_counts.get("PDO", 0)
        unknown = sev_counts.get("Unknown", 0) + sev_counts.get("Unknown / blank", 0)
        severe = fatal + injury
        severe_rate = (severe / total * 100.0) if total else 0.0

        # Calculate risk flags
        flags: List[str] = []
        if fatal > 0:
            flags.append(f"[!] Fatal collisions present: {fatal} in subset")
        if severe_rate >= 20.0:
            flags.append(
                f"[!] High severe share: {severe_rate:.1f}% Fatal+Injury (>=20%)"
            )
        if (unknown / total) >= 0.05:
            flags.append(
                f"[!] Data quality risk: {unknown} unknown/blank severity (>=5%)"
            )

        # Update display
        if self.summary_status:
            self.summary_status.setText("")
            self.summary_status.setVisible(False)

        self._set_kpi_value(self.kpi_total_value, str(total))
        fatal_accent = "#b00020" if fatal > 0 else None
        self._set_kpi_value(self.kpi_fatal_value, str(fatal), fatal_accent)
        severe_accent = "#b00020" if severe_rate >= 20.0 else None
        self._set_kpi_value(self.kpi_severe_value, f"{severe_rate:.1f}%", severe_accent)

        if self.sev_fatal_value:
            if fatal > 0:
                self.sev_fatal_value.setStyleSheet("font-weight: 600; color: #b00020;")
            else:
                self.sev_fatal_value.setStyleSheet("font-weight: 600;")
            self.sev_fatal_value.setText(str(fatal))

        if self.sev_injury_value:
            self.sev_injury_value.setText(str(injury))
        if self.sev_pdo_value:
            self.sev_pdo_value.setText(str(pdo))
        if self.sev_unknown_value:
            self.sev_unknown_value.setText(str(unknown))

        if self.exp_vehicles_value:
            self.exp_vehicles_value.setText(f"{self._sum_field('veh_cnt'):.0f}")
        if self.exp_persons_value:
            self.exp_persons_value.setText(f"{self._sum_field('per_cnt'):.0f}")
        if self.exp_drivers_value:
            self.exp_drivers_value.setText(f"{self._sum_field('drv_cnt'):.0f}")
        if self.exp_occupants_value:
            self.exp_occupants_value.setText(f"{self._sum_field('occ_cnt'):.0f}")
        if self.exp_pedestrians_value:
            self.exp_pedestrians_value.setText(f"{self._sum_field('ped_cnt'):.0f}")

        self._set_risk_flags(flags, "No major flags triggered")
        self._fill_top_panel(
            self.top_panels.get("impact_type", []),
            self._top_list("impact_type", 5),
            "None",
        )
        self._fill_top_panel(
            self.top_panels.get("accident_location", []),
            self._top_list("accident_location", 5),
            "None",
        )
        self._fill_top_panel(
            self.top_panels.get("municipality", []),
            self._top_list("municipality", 5),
            "None",
        )

    def set_idle_state(self) -> None:
        """Set summary to idle state."""
        if self.summary_status:
            self.summary_status.setText(
                "Ready. Default scope is map selection. Select points and click Apply, or disable selection scope."
            )
            self.summary_status.setVisible(True)

        self._set_kpi_value(self.kpi_total_value, "n/a")
        self._set_kpi_value(self.kpi_fatal_value, "n/a")
        self._set_kpi_value(self.kpi_severe_value, "n/a")

        if self.sev_fatal_value:
            self.sev_fatal_value.setText("n/a")
            self.sev_fatal_value.setStyleSheet("font-weight: 600;")
        if self.sev_injury_value:
            self.sev_injury_value.setText("n/a")
        if self.sev_pdo_value:
            self.sev_pdo_value.setText("n/a")
        if self.sev_unknown_value:
            self.sev_unknown_value.setText("n/a")

        if self.exp_vehicles_value:
            self.exp_vehicles_value.setText("n/a")
        if self.exp_persons_value:
            self.exp_persons_value.setText("n/a")
        if self.exp_drivers_value:
            self.exp_drivers_value.setText("n/a")
        if self.exp_occupants_value:
            self.exp_occupants_value.setText("n/a")
        if self.exp_pedestrians_value:
            self.exp_pedestrians_value.setText("n/a")

        self._set_risk_flags([], "No results yet")
        self._fill_top_panel(self.top_panels.get("impact_type", []), [], "No data")
        self._fill_top_panel(
            self.top_panels.get("accident_location", []), [], "No data"
        )
        self._fill_top_panel(self.top_panels.get("municipality", []), [], "No data")

    def reset(self) -> None:
        """Reset summary to idle state."""
        self.set_idle_state()
