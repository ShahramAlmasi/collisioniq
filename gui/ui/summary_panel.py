"""Summary Panel - Modern KPI dashboard with visual hierarchy."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.decodes import DecodeRegistry
from ...core.utils import safe_str
from ..modern_widgets import (
    Badge,
    Card,
    Colors,
    EmptyState,
    KPICard,
    Typography,
)


class SummaryPanel(QWidget):
    """Modern summary panel with KPI cards and visual hierarchy."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.field_map: Dict[str, str] = {}
        self.decodes: Optional[DecodeRegistry] = None
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build modern summary UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # ===== KPI Cards Row =====
        kpi_section = self._build_kpi_section()
        layout.addWidget(kpi_section)
        
        # ===== Scrollable Content =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameStyle(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        
        # Severity breakdown
        severity_section = self._build_severity_section()
        content_layout.addWidget(severity_section)
        
        # Exposure metrics
        exposure_section = self._build_exposure_section()
        content_layout.addWidget(exposure_section)
        
        # Risk flags
        risk_section = self._build_risk_section()
        content_layout.addWidget(risk_section)
        
        # Top contributors
        contributors_section = self._build_contributors_section()
        content_layout.addWidget(contributors_section)
        
        content_layout.addStretch(1)
        content.setLayout(content_layout)
        scroll.setWidget(content)
        
        layout.addWidget(scroll, 1)
        self.content_scroll = scroll  # Store reference for visibility toggling
        
        # ===== Empty State =====
        self.empty_state = EmptyState(
            "📊",
            "No Data to Summarize",
            "Apply filters in the Filters tab to see summary statistics and KPIs."
        )
        self.empty_state.setVisible(False)
        layout.addWidget(self.empty_state)
        
        self.setLayout(layout)
        self._set_idle_state()
    
    def _build_kpi_section(self) -> QWidget:
        """Build KPI cards section."""
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Main KPIs
        self.kpi_total = KPICard(
            "Total Collisions",
            "—",
            accent_color=Colors.ACCENT_PRIMARY
        )
        
        self.kpi_severe = KPICard(
            "Severe Rate",
            "—",
            accent_color=Colors.ACCENT_WARNING
        )
        
        self.kpi_fatal = KPICard(
            "Fatal",
            "—",
            accent_color=Colors.ACCENT_DANGER
        )
        
        self.kpi_pdo = KPICard(
            "PDO",
            "—",
            accent_color=Colors.ACCENT_INFO
        )
        
        layout.addWidget(self.kpi_total)
        layout.addWidget(self.kpi_severe)
        layout.addWidget(self.kpi_fatal)
        layout.addWidget(self.kpi_pdo)
        
        section.setLayout(layout)
        return section
    
    def _build_severity_section(self) -> QWidget:
        """Build severity breakdown section."""
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
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Severity Breakdown")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        
        self.severity_badge = Badge("", "default")
        
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.severity_badge)
        
        layout.addLayout(header)
        
        # Progress bars for each severity
        self.severity_bars: List[Tuple[str, QProgressBar, QLabel]] = []
        
        severities = [
            ("Fatal", Colors.ACCENT_DANGER),
            ("Injury", Colors.ACCENT_WARNING),
            ("PDO", Colors.ACCENT_INFO),
            ("Unknown/Blank", Colors.TEXT_MUTED),
        ]
        
        for name, color in severities:
            row = QHBoxLayout()
            row.setSpacing(12)
            
            label = QLabel(name)
            label.setFixedWidth(100)
            label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            
            bar = QProgressBar()
            bar.setTextVisible(True)
            bar.setMaximumHeight(20)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {Colors.BG_PRIMARY};
                    border-radius: 4px;
                    text-align: center;
                    color: {Colors.TEXT_PRIMARY};
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 4px;
                }}
            """)
            
            count_label = QLabel("—")
            count_label.setFixedWidth(60)
            count_label.setAlignment(Qt.AlignRight)
            count_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 500;")
            
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(count_label)
            
            layout.addLayout(row)
            self.severity_bars.append((name.lower().replace("/blank", "").replace("unknown", "unknown"), bar, count_label))
        
        card.setLayout(layout)
        return card
    
    def _build_exposure_section(self) -> QWidget:
        """Build exposure metrics section."""
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
        
        # Header
        title = QLabel("Exposure Totals")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(title)
        
        # Grid of metrics
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(16)
        
        self.exposure_labels: Dict[str, Tuple[QLabel, QLabel]] = {}
        
        exposures = [
            ("veh_cnt", "🚗", "Vehicles"),
            ("per_cnt", "👥", "Persons"),
            ("drv_cnt", "🧑‍✈️", "Drivers"),
            ("occ_cnt", "🪑", "Occupants"),
            ("ped_cnt", "🚶", "Pedestrians"),
        ]
        
        for idx, (key, icon, label) in enumerate(exposures):
            row = idx // 3
            col = (idx % 3) * 2
            
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 20px;")
            
            value_label = QLabel("—")
            value_label.setStyleSheet(f"""
                font-size: {Typography.XL}px;
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
            """)
            
            name_label = QLabel(label)
            name_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.XS}px;")
            
            vbox = QVBoxLayout()
            vbox.setSpacing(2)
            vbox.addWidget(value_label)
            vbox.addWidget(name_label)
            
            grid.addWidget(icon_label, row, col)
            grid.addLayout(vbox, row, col + 1)
            
            self.exposure_labels[key] = (value_label, name_label)
        
        layout.addLayout(grid)
        card.setLayout(layout)
        return card
    
    def _build_risk_section(self) -> QWidget:
        """Build risk flags section."""
        card = Card()
        card.setStyleSheet(f"""
            Card {{
                background-color: {Colors.ACCENT_DANGER}10;
                border: 1px solid {Colors.ACCENT_DANGER}40;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("⚠️ Risk Flags")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.ACCENT_DANGER};
        """)
        
        header.addWidget(title)
        header.addStretch(1)
        
        self.risk_count = Badge("0", "danger")
        header.addWidget(self.risk_count)
        
        layout.addLayout(header)
        
        # Risk items container
        self.risk_container = QWidget()
        self.risk_layout = QVBoxLayout()
        self.risk_layout.setContentsMargins(0, 0, 0, 0)
        self.risk_layout.setSpacing(8)
        
        self.risk_labels: List[QLabel] = []
        for _ in range(5):
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {Colors.ACCENT_DANGER};")
            lbl.setVisible(False)
            self.risk_layout.addWidget(lbl)
            self.risk_labels.append(lbl)
        
        self.risk_empty = QLabel("✓ No major risk flags")
        self.risk_empty.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS};")
        self.risk_layout.addWidget(self.risk_empty)
        
        self.risk_layout.addStretch(1)
        self.risk_container.setLayout(self.risk_layout)
        layout.addWidget(self.risk_container)
        
        card.setLayout(layout)
        return card
    
    def _build_contributors_section(self) -> QWidget:
        """Build top contributors section."""
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
        layout.setSpacing(16)
        
        # Header
        title = QLabel("Top Contributors")
        title.setStyleSheet(f"""
            font-size: {Typography.LG}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(title)
        
        # Three columns
        columns = QHBoxLayout()
        columns.setSpacing(16)
        
        # Impact Type
        self.impact_panel = self._create_top_list_panel("Impact Type")
        columns.addWidget(self.impact_panel, 1)
        
        # Accident Location
        self.location_panel = self._create_top_list_panel("Accident Location")
        columns.addWidget(self.location_panel, 1)
        
        # Municipality
        self.muni_panel = self._create_top_list_panel("Municipality")
        columns.addWidget(self.muni_panel, 1)
        
        layout.addLayout(columns)
        card.setLayout(layout)
        return card
    
    def _create_top_list_panel(self, title: str) -> QWidget:
        """Create a top N list panel."""
        panel = QWidget()
        panel.setStyleSheet(f"""
            background-color: {Colors.BG_PRIMARY};
            border-radius: 8px;
            padding: 12px;
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        header = QLabel(title)
        header.setStyleSheet(f"""
            font-weight: 600;
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SM}px;
            text-transform: uppercase;
        """)
        layout.addWidget(header)
        
        # List rows
        rows: List[Tuple[QLabel, QLabel, QLabel]] = []
        for i in range(5):
            row = QHBoxLayout()
            row.setSpacing(8)
            
            rank = QLabel(f"#{i+1}")
            rank.setFixedWidth(24)
            rank.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.XS}px;")
            
            name = QLabel("—")
            name.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
            
            count = QLabel("—")
            count.setFixedWidth(50)
            count.setAlignment(Qt.AlignRight)
            count.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-weight: 500;")
            
            row.addWidget(rank)
            row.addWidget(name, 1)
            row.addWidget(count)
            
            layout.addLayout(row)
            rows.append((rank, name, count))
        
        panel.setLayout(layout)
        panel._rows = rows  # Store for updates
        return panel
    
    def set_data(self, field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        """Set field map and decodes."""
        self.field_map = field_map
        self.decodes = decodes
    
    def update_summary(self, rows: List[Dict[str, Any]]) -> None:
        """Update summary with filtered rows."""
        if not rows:
            self._set_idle_state()
            return
        
        self.empty_state.setVisible(False)
        self.content_scroll.setVisible(True)
        
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
        self.kpi_total.set_value(f"{total:,}")
        
        if fatal > 0:
            self.kpi_fatal.set_value(f"{fatal}", Colors.ACCENT_DANGER)
        else:
            self.kpi_fatal.set_value("0", Colors.ACCENT_SUCCESS)
        
        self.kpi_severe.set_value(f"{severe_rate:.1f}%")
        if severe_rate >= 20:
            self.kpi_severe.set_value(f"{severe_rate:.1f}%", Colors.ACCENT_DANGER)
        else:
            self.kpi_severe.set_value(f"{severe_rate:.1f}%", Colors.ACCENT_SUCCESS)
        
        self.kpi_pdo.set_value(f"{pdo:,}")
        
        # Update severity badge
        severe_pct = (severe / total * 100) if total else 0
        self.severity_badge.set_text(f"{severe_pct:.1f}% severe")
        if severe_pct >= 20:
            self.severity_badge.set_variant("danger")
        elif severe_pct >= 10:
            self.severity_badge.set_variant("warning")
        else:
            self.severity_badge.set_variant("success")
        
        # Update severity bars
        for key, bar, count_label in self.severity_bars:
            if key == "fatal":
                count = fatal
            elif key == "injury":
                count = injury
            elif key == "pdo":
                count = pdo
            else:
                count = unknown
            
            pct = (count / total * 100) if total else 0
            bar.setValue(int(pct))
            bar.setFormat(f"{pct:.1f}%")
            count_label.setText(f"{count:,}")
        
        # Update exposure
        for key, (value_label, _) in self.exposure_labels.items():
            value = sum_field(key)
            value_label.setText(f"{value:,.0f}")
        
        # Risk flags
        flags = []
        if fatal > 0:
            flags.append(f"Fatal collisions present: {fatal} in subset")
        if severe_rate >= 20.0:
            flags.append(f"High severe rate: {severe_rate:.1f}% Fatal+Injury (≥20% threshold)")
        if (unknown / total) >= 0.05:
            flags.append(f"Data quality concern: {unknown} unknown/blank severity (≥5%)")
        
        self._set_risk_flags(flags)
        self.risk_count.set_text(str(len(flags)))
        
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
        
        self._fill_top_panel(self.impact_panel, top_list("impact_type", 5))
        self._fill_top_panel(self.location_panel, top_list("accident_location", 5))
        self._fill_top_panel(self.muni_panel, top_list("municipality", 5))
    
    def _set_risk_flags(self, flags: List[str]) -> None:
        """Set risk flag labels."""
        for lbl in self.risk_labels:
            lbl.setVisible(False)
        
        if not flags:
            self.risk_empty.setVisible(True)
            return
        
        self.risk_empty.setVisible(False)
        for idx, text in enumerate(flags[:len(self.risk_labels)]):
            self.risk_labels[idx].setText(f"• {text}")
            self.risk_labels[idx].setVisible(True)
    
    def _fill_top_panel(self, panel: QWidget, pairs: List[Tuple[str, int]]) -> None:
        """Fill a top contributors panel."""
        rows = panel._rows
        for idx, (rank, name, count) in enumerate(rows):
            if idx < len(pairs):
                label, value = pairs[idx]
                name.setText(str(label))
                count.setText(f"{value:,}")
                rank.setVisible(True)
                name.setVisible(True)
                count.setVisible(True)
            else:
                rank.setVisible(False)
                name.setVisible(False)
                count.setVisible(False)
    
    def _set_idle_state(self) -> None:
        """Reset to idle state."""
        self.empty_state.setVisible(True)
        self.content_scroll.setVisible(False)
        
        self.kpi_total.set_value("—")
        self.kpi_fatal.set_value("—")
        self.kpi_severe.set_value("—")
        self.kpi_pdo.set_value("—")
        
        self.severity_badge.set_text("")
        
        for key, bar, count_label in self.severity_bars:
            bar.setValue(0)
            bar.setFormat("—")
            count_label.setText("—")
        
        for key, (value_label, _) in self.exposure_labels.items():
            value_label.setText("—")
        
        self._set_risk_flags([])
        self.risk_count.set_text("0")
        
        for panel in [self.impact_panel, self.location_panel, self.muni_panel]:
            self._fill_top_panel(panel, [])
