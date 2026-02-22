"""Summary Panel - KPIs and summary statistics."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.decodes import DecodeRegistry
from ..core.utils import safe_str


class SummaryPanel(QWidget):
    """Panel displaying KPIs and summary statistics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.field_map: Dict[str, str] = {}
        self.decodes: Optional[DecodeRegistry] = None
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # KPI row
        kpi_row = QWidget()
        kpi_layout = QHBoxLayout()
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(12)
        kpi_row.setLayout(kpi_layout)
        
        # Create KPI cards
        self.kpi_total, self.kpi_total_value = self._make_kpi_card("Total Collisions")
        self.kpi_fatal, self.kpi_fatal_value = self._make_kpi_card("Fatal Collisions")
        self.kpi_severe, self.kpi_severe_value = self._make_kpi_card("Severe Share")
        self.kpi_pdo, self.kpi_pdo_value = self._make_kpi_card("PDO Collisions")
        
        kpi_layout.addWidget(self.kpi_total)
        kpi_layout.addWidget(self.kpi_fatal)
        kpi_layout.addWidget(self.kpi_severe)
        kpi_layout.addWidget(self.kpi_pdo)
        kpi_layout.addStretch(1)
        
        layout.addWidget(kpi_row)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)
        
        # Severity breakdown
        sev_group = self._make_section("Severity Breakdown")
        sev_grid = QGridLayout()
        sev_grid.setHorizontalSpacing(20)
        sev_grid.setVerticalSpacing(8)
        
        self.sev_fatal_value = QLabel("n/a")
        self.sev_injury_value = QLabel("n/a")
        self.sev_pdo_value = QLabel("n/a")
        self.sev_unknown_value = QLabel("n/a")
        
        self._add_grid_row(sev_grid, 0, "Fatal:", self.sev_fatal_value, "#dc2626")
        self._add_grid_row(sev_grid, 1, "Injury:", self.sev_injury_value, "#ea580c")
        self._add_grid_row(sev_grid, 2, "PDO:", self.sev_pdo_value, "#2563eb")
        self._add_grid_row(sev_grid, 3, "Unknown/Blank:", self.sev_unknown_value, "#6b7280")
        
        sev_group.layout().addLayout(sev_grid)
        content_layout.addWidget(sev_group)
        
        # Exposure totals
        exp_group = self._make_section("Exposure Totals")
        exp_grid = QGridLayout()
        exp_grid.setHorizontalSpacing(20)
        exp_grid.setVerticalSpacing(8)
        
        self.exp_vehicles_value = QLabel("n/a")
        self.exp_persons_value = QLabel("n/a")
        self.exp_drivers_value = QLabel("n/a")
        self.exp_pedestrians_value = QLabel("n/a")
        
        self._add_grid_row(exp_grid, 0, "Vehicles:", self.exp_vehicles_value)
        self._add_grid_row(exp_grid, 1, "Persons:", self.exp_persons_value)
        self._add_grid_row(exp_grid, 2, "Drivers:", self.exp_drivers_value)
        self._add_grid_row(exp_grid, 3, "Pedestrians:", self.exp_pedestrians_value)
        
        exp_group.layout().addLayout(exp_grid)
        content_layout.addWidget(exp_group)
        
        # Risk flags
        risk_group = self._make_section("Risk Flags", warning_style=True)
        self.risk_layout = QVBoxLayout()
        self.risk_layout.setSpacing(6)
        
        self.risk_labels = []
        for _ in range(4):
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #dc2626;")
            lbl.setVisible(False)
            self.risk_layout.addWidget(lbl)
            self.risk_labels.append(lbl)
        
        self.risk_empty = QLabel("No major flags triggered")
        self.risk_empty.setStyleSheet("color: #16a34a;")
        self.risk_layout.addWidget(self.risk_empty)
        
        risk_group.layout().addLayout(self.risk_layout)
        content_layout.addWidget(risk_group)
        
        # Top contributors
        top_group = self._make_section("Top Contributors")
        top_layout = QVBoxLayout()
        top_layout.setSpacing(12)
        
        self.top_impact, self.top_impact_rows = self._make_top_panel("Impact Type")
        self.top_location, self.top_location_rows = self._make_top_panel("Accident Location")
        self.top_muni, self.top_muni_rows = self._make_top_panel("Municipality")
        
        top_layout.addWidget(self.top_impact)
        top_layout.addWidget(self.top_location)
        top_layout.addWidget(self.top_muni)
        
        top_group.layout().addLayout(top_layout)
        content_layout.addWidget(top_group)
        
        content_layout.addStretch(1)
        content.setLayout(content_layout)
        scroll.setWidget(content)
        
        layout.addWidget(scroll, 1)
        self.setLayout(layout)
    
    def _make_kpi_card(self, title: str) -> Tuple[QFrame, QLabel]:
        """Create a KPI card."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        value = QLabel("n/a")
        value.setStyleSheet("font-size: 28px; font-weight: bold; color: #1e293b;")
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #64748b; font-size: 11px;")
        
        layout.addWidget(value)
        layout.addWidget(title_label)
        frame.setLayout(layout)
        
        return frame, value
    
    def _make_section(self, title: str, warning_style: bool = False) -> QGroupBox:
        """Create a section group box."""
        from qgis.PyQt.QtWidgets import QGroupBox
        
        group = QGroupBox(title)
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        if warning_style:
            group.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #fecaca;
                    background-color: #fef2f2;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    color: #dc2626;
                }
            """)
        
        group.setLayout(layout)
        return group
    
    def _add_grid_row(self, grid: QGridLayout, row: int, title: str, 
                      value_label: QLabel, color: Optional[str] = None) -> None:
        """Add a row to a grid layout."""
        label = QLabel(title)
        label.setStyleSheet("color: #64748b;")
        
        if color:
            value_label.setStyleSheet(f"font-weight: 600; color: {color};")
        else:
            value_label.setStyleSheet("font-weight: 600; color: #1e293b;")
        
        grid.addWidget(label, row, 0)
        grid.addWidget(value_label, row, 1)
    
    def _make_top_panel(self, title: str, rows: int = 5) -> Tuple[QFrame, List[Tuple[QLabel, QLabel]]]:
        """Create a top contributors panel."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        header = QLabel(title)
        header.setStyleSheet("font-weight: 600; color: #334155;")
        layout.addWidget(header)
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        
        row_labels: List[Tuple[QLabel, QLabel]] = []
        for row in range(rows):
            name = QLabel()
            count = QLabel()
            name.setStyleSheet("color: #475569;")
            count.setStyleSheet("font-weight: 500; color: #1e293b;")
            grid.addWidget(name, row, 0)
            grid.addWidget(count, row, 1)
            row_labels.append((name, count))
        
        layout.addLayout(grid)
        frame.setLayout(layout)
        
        return frame, row_labels
    
    def set_data(self, field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        """Set field map and decodes."""
        self.field_map = field_map
        self.decodes = decodes
    
    def update_summary(self, rows: List[Dict[str, Any]]) -> None:
        """Update summary with filtered rows."""
        if not rows:
            self._set_idle_state()
            return
        
        total = len(rows)
        fm = self.field_map
        
        # Helper to sum fields
        def sum_field(concept: str) -> float:
            field = fm.get(concept)
            if not field:
                return 0.0
            return sum(float(r.get(field) or 0) for r in rows if r.get(field) is not None)
        
        # Severity counts
        sev_field = fm.get("accident_class")
        sev_counts = Counter()
        
        if sev_field and self.decodes:
            for r in rows:
                raw = safe_str(r.get(sev_field)).strip()
                lab = self.decodes.decode("accident_class", raw) if raw else "Unknown / blank"
                sev_counts[lab] += 1
        
        fatal = sev_counts.get("Fatal", 0)
        injury = sev_counts.get("Injury", 0)
        pdo = sev_counts.get("PDO", 0)
        unknown = sev_counts.get("Unknown", 0) + sev_counts.get("Unknown / blank", 0)
        severe = fatal + injury
        severe_rate = (severe / total * 100.0) if total else 0.0
        
        # Update KPIs
        self.kpi_total_value.setText(f"{total:,}")
        
        if fatal > 0:
            self.kpi_fatal_value.setText(f"{fatal}")
            self.kpi_fatal_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #dc2626;")
        else:
            self.kpi_fatal_value.setText("0")
            self.kpi_fatal_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #16a34a;")
        
        self.kpi_severe_value.setText(f"{severe_rate:.1f}%")
        if severe_rate >= 20:
            self.kpi_severe_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #dc2626;")
        else:
            self.kpi_severe_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #1e293b;")
        
        self.kpi_pdo_value.setText(f"{pdo:,}")
        
        # Update severity breakdown
        self.sev_fatal_value.setText(f"{fatal} ({100*fatal/total:.1f}%)" if total else "0")
        self.sev_injury_value.setText(f"{injury} ({100*injury/total:.1f}%)" if total else "0")
        self.sev_pdo_value.setText(f"{pdo} ({100*pdo/total:.1f}%)" if total else "0")
        self.sev_unknown_value.setText(f"{unknown} ({100*unknown/total:.1f}%)" if total else "0")
        
        # Update exposure
        self.exp_vehicles_value.setText(f"{sum_field('veh_cnt'):.0f}")
        self.exp_persons_value.setText(f"{sum_field('per_cnt'):.0f}")
        self.exp_drivers_value.setText(f"{sum_field('drv_cnt'):.0f}")
        self.exp_pedestrians_value.setText(f"{sum_field('ped_cnt'):.0f}")
        
        # Risk flags
        flags = []
        if fatal > 0:
            flags.append(f"⚠ Fatal collisions present: {fatal} in subset")
        if severe_rate >= 20.0:
            flags.append(f"⚠ High severe share: {severe_rate:.1f}% Fatal+Injury (≥20%)")
        if (unknown / total) >= 0.05:
            flags.append(f"⚠ Data quality: {unknown} unknown/blank severity (≥5%)")
        
        self._set_risk_flags(flags)
        
        # Top contributors
        def top_list(concept_key: str, n: int) -> List[Tuple[str, int]]:
            field = fm.get(concept_key)
            if not field or not self.decodes:
                return []
            c = Counter()
            for r in rows:
                raw = safe_str(r.get(field)).strip()
                lab = self.decodes.decode(concept_key, raw) if raw else "Unknown / blank"
                c[lab] += 1
            return c.most_common(n)
        
        self._fill_top_panel(self.top_impact_rows, top_list("impact_type", 5))
        self._fill_top_panel(self.top_location_rows, top_list("accident_location", 5))
        self._fill_top_panel(self.top_muni_rows, top_list("municipality", 5))
    
    def _set_risk_flags(self, flags: List[str]) -> None:
        """Set risk flag labels."""
        for lbl in self.risk_labels:
            lbl.setVisible(False)
        
        if not flags:
            self.risk_empty.setVisible(True)
            return
        
        self.risk_empty.setVisible(False)
        for idx, text in enumerate(flags[:len(self.risk_labels)]):
            self.risk_labels[idx].setText(text)
            self.risk_labels[idx].setVisible(True)
    
    def _fill_top_panel(self, rows: List[Tuple[QLabel, QLabel]], 
                        pairs: List[Tuple[str, int]]) -> None:
        """Fill a top contributors panel."""
        for idx, (name, count) in enumerate(rows):
            if idx < len(pairs):
                label, value = pairs[idx]
                name.setText(str(label))
                count.setText(f"{value:,}")
                name.setVisible(True)
                count.setVisible(True)
            else:
                name.setVisible(False)
                count.setVisible(False)
    
    def _set_idle_state(self) -> None:
        """Reset to idle state."""
        self.kpi_total_value.setText("n/a")
        self.kpi_fatal_value.setText("n/a")
        self.kpi_severe_value.setText("n/a")
        self.kpi_pdo_value.setText("n/a")
        
        self.sev_fatal_value.setText("n/a")
        self.sev_injury_value.setText("n/a")
        self.sev_pdo_value.setText("n/a")
        self.sev_unknown_value.setText("n/a")
        
        self.exp_vehicles_value.setText("n/a")
        self.exp_persons_value.setText("n/a")
        self.exp_drivers_value.setText("n/a")
        self.exp_pedestrians_value.setText("n/a")
        
        self._set_risk_flags([])
        
        for rows in [self.top_impact_rows, self.top_location_rows, self.top_muni_rows]:
            for name, count in rows:
                name.setVisible(False)
                count.setVisible(False)
