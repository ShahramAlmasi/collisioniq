"""Quality Panel - Data quality checks and validation."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from ...core.config import FILTER_CONCEPTS
from ...core.decodes import DecodeRegistry
from ...core.utils import safe_str, is_blank, to_datetime


@dataclass
class QualityIssue:
    """Represents a data quality issue."""
    severity: str  # 'error', 'warning', 'info'
    category: str  # e.g., 'missing_field', 'unknown_code', 'date_gap'
    field: str
    message: str
    count: int
    sample_values: List[str]
    recommendation: str


class QualityPanel(QWidget):
    """Panel for data quality analysis and reporting."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layer = None
        self.field_map: Dict[str, str] = {}
        self.decodes: Optional[DecodeRegistry] = None
        
        self.issues: List[QualityIssue] = []
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Header
        header = QLabel(
            "Data Quality Analysis\n"
            "Auto-detect missing fields, unknown codes, date gaps, and null severities."
        )
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)
        
        # Check options
        options_group = QGroupBox("Check Options")
        options_layout = QHBoxLayout()
        
        self.chk_missing_fields = QCheckBox("Missing fields")
        self.chk_missing_fields.setChecked(True)
        
        self.chk_unknown_codes = QCheckBox("Unknown codes")
        self.chk_unknown_codes.setChecked(True)
        
        self.chk_date_gaps = QCheckBox("Date gaps")
        self.chk_date_gaps.setChecked(True)
        
        self.chk_null_severity = QCheckBox("Null severities")
        self.chk_null_severity.setChecked(True)
        
        self.chk_completeness = QCheckBox("Field completeness")
        self.chk_completeness.setChecked(True)
        
        options_layout.addWidget(self.chk_missing_fields)
        options_layout.addWidget(self.chk_unknown_codes)
        options_layout.addWidget(self.chk_date_gaps)
        options_layout.addWidget(self.chk_null_severity)
        options_layout.addWidget(self.chk_completeness)
        options_layout.addStretch(1)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_run_check = QPushButton("Run Quality Check")
        self.btn_run_check.setStyleSheet("font-weight: bold;")
        self.btn_run_check.clicked.connect(self.run_quality_check)
        
        self.btn_export_report = QPushButton("Export Report")
        self.btn_export_report.clicked.connect(self.export_report)
        self.btn_export_report.setEnabled(False)
        
        btn_layout.addWidget(self.btn_run_check)
        btn_layout.addWidget(self.btn_export_report)
        btn_layout.addStretch(1)
        
        layout.addLayout(btn_layout)
        
        # Summary cards
        self.summary_widget = QWidget()
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        
        self.card_errors = self._create_summary_card("Errors", "#dc2626")
        self.card_warnings = self._create_summary_card("Warnings", "#ea580c")
        self.card_info = self._create_summary_card("Info", "#2563eb")
        
        summary_layout.addWidget(self.card_errors)
        summary_layout.addWidget(self.card_warnings)
        summary_layout.addWidget(self.card_info)
        summary_layout.addStretch(1)
        
        self.summary_widget.setLayout(summary_layout)
        self.summary_widget.setVisible(False)
        layout.addWidget(self.summary_widget)
        
        # Issues table
        self.issues_table = QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels([
            "Severity", "Category", "Field", "Count", "Description"
        ])
        self.issues_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.issues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.issues_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.issues_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.issues_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.issues_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.issues_table.setAlternatingRowColors(True)
        self.issues_table.setVisible(False)
        
        layout.addWidget(self.issues_table, 1)
        
        # Details panel for selected issue
        self.details_group = QGroupBox("Issue Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QLabel("Select an issue to see details and recommendations.")
        self.details_text.setWordWrap(True)
        self.details_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        details_layout.addWidget(self.details_text)
        self.details_group.setLayout(details_layout)
        self.details_group.setVisible(False)
        
        layout.addWidget(self.details_group)
        
        # Status label
        self.lbl_status = QLabel("Click 'Run Quality Check' to analyze the current layer.")
        layout.addWidget(self.lbl_status)
        
        self.setLayout(layout)
        
        # Connect selection change
        self.issues_table.itemSelectionChanged.connect(self._on_issue_selected)
    
    def _create_summary_card(self, title: str, color: str) -> QFrame:
        """Create a summary card widget."""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color}15;
                border: 1px solid {color}40;
                border-radius: 4px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        
        label = QLabel(title)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        value = QLabel("0")
        value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        
        layout.addWidget(label)
        layout.addWidget(value)
        
        card.setLayout(layout)
        card._value_label = value  # Store reference for updates
        
        return card
    
    def _update_summary_cards(self) -> None:
        """Update summary card values."""
        errors = sum(1 for i in self.issues if i.severity == 'error')
        warnings = sum(1 for i in self.issues if i.severity == 'warning')
        info = sum(1 for i in self.issues if i.severity == 'info')
        
        self.card_errors._value_label.setText(str(errors))
        self.card_warnings._value_label.setText(str(warnings))
        self.card_info._value_label.setText(str(info))
        
        self.summary_widget.setVisible(True)
    
    def set_layer(self, layer, field_map: Dict[str, str], decodes: DecodeRegistry) -> None:
        """Set the current layer and configuration."""
        self.layer = layer
        self.field_map = field_map
        self.decodes = decodes
        
        if layer is not None:
            self.lbl_status.setText(f"Layer: {layer.name()} | {layer.featureCount()} features")
    
    def run_quality_check(self) -> None:
        """Run the quality check analysis."""
        if self.layer is None:
            QMessageBox.warning(self, "Data Quality", "No layer selected.")
            return
        
        self.issues = []
        
        # Run selected checks
        if self.chk_missing_fields.isChecked():
            self._check_missing_fields()
        
        if self.chk_unknown_codes.isChecked():
            self._check_unknown_codes()
        
        if self.chk_date_gaps.isChecked():
            self._check_date_gaps()
        
        if self.chk_null_severity.isChecked():
            self._check_null_severities()
        
        if self.chk_completeness.isChecked():
            self._check_field_completeness()
        
        # Update UI
        self._update_issues_table()
        self._update_summary_cards()
        self.btn_export_report.setEnabled(bool(self.issues))
        
        total = len(self.issues)
        self.lbl_status.setText(f"Quality check complete. Found {total} issue(s).")
    
    def _check_missing_fields(self) -> None:
        """Check for missing/unmapped fields."""
        if not self.layer:
            return
        
        layer_fields = {f.name() for f in self.layer.fields()}
        
        for concept, _ in FILTER_CONCEPTS:
            field_name = self.field_map.get(concept)
            if not field_name:
                self.issues.append(QualityIssue(
                    severity='warning',
                    category='missing_field',
                    field=concept,
                    message=f"Field not mapped for concept: {concept}",
                    count=0,
                    sample_values=[],
                    recommendation=f"Map a layer field to the '{concept}' concept in the Config panel."
                ))
            elif field_name not in layer_fields:
                self.issues.append(QualityIssue(
                    severity='error',
                    category='missing_field',
                    field=field_name,
                    message=f"Mapped field '{field_name}' not found in layer",
                    count=0,
                    sample_values=[],
                    recommendation=f"Check field mapping or layer schema. '{field_name}' does not exist."
                ))
    
    def _check_unknown_codes(self) -> None:
        """Check for unknown/uncoded values in categorical fields."""
        if not self.layer or not self.decodes:
            return
        
        # Get fields that have decode tables
        for concept in self.decodes.keys():
            field_name = self.field_map.get(concept)
            if not field_name:
                continue
            
            try:
                idx = self.layer.fields().indexOf(field_name)
                if idx < 0:
                    continue
                
                known_codes = set(self.decodes.mapping(concept).keys())
                unknown_codes: Counter = Counter()
                
                for f in self.layer.getFeatures():
                    raw = f[field_name]
                    if is_blank(raw):
                        continue
                    
                    code = safe_str(raw).strip()
                    if code and code not in known_codes:
                        unknown_codes[code] += 1
                
                if unknown_codes:
                    top_unknown = unknown_codes.most_common(5)
                    total_unknown = sum(unknown_codes.values())
                    
                    self.issues.append(QualityIssue(
                        severity='warning',
                        category='unknown_code',
                        field=field_name,
                        message=f"Found {len(unknown_codes)} unknown code(s) in {concept}",
                        count=total_unknown,
                        sample_values=[code for code, _ in top_unknown],
                        recommendation=f"Add missing codes to decode table for '{concept}' or verify data source."
                    ))
            except Exception:
                pass
    
    def _check_date_gaps(self) -> None:
        """Check for gaps in date data."""
        if not self.layer:
            return
        
        date_field = self.field_map.get("date")
        if not date_field:
            return
        
        try:
            idx = self.layer.fields().indexOf(date_field)
            if idx < 0:
                return
            
            dates: List[datetime] = []
            null_count = 0
            
            for f in self.layer.getFeatures():
                raw = f[date_field]
                dt = to_datetime(raw)
                if dt:
                    dates.append(dt)
                else:
                    null_count += 1
            
            if not dates:
                self.issues.append(QualityIssue(
                    severity='error',
                    category='date_gap',
                    field=date_field,
                    message="No valid dates found in date field",
                    count=null_count,
                    sample_values=[],
                    recommendation="Verify date field mapping and format."
                ))
                return
            
            # Check for null dates
            if null_count > 0:
                pct = 100 * null_count / (null_count + len(dates))
                severity = 'error' if pct > 5 else 'warning'
                self.issues.append(QualityIssue(
                    severity=severity,
                    category='date_gap',
                    field=date_field,
                    message=f"{null_count} records ({pct:.1f}%) have missing/invalid dates",
                    count=null_count,
                    sample_values=[],
                    recommendation="Investigate missing dates. May indicate data import issues."
                ))
            
            # Check for date range
            dates.sort()
            date_range = dates[-1] - dates[0]
            
            if date_range.days > 365 * 20:
                self.issues.append(QualityIssue(
                    severity='info',
                    category='date_gap',
                    field=date_field,
                    message=f"Very large date range: {date_range.days} days",
                    count=0,
                    sample_values=[dates[0].strftime('%Y-%m-%d'), dates[-1].strftime('%Y-%m-%d')],
                    recommendation="Verify date range is correct for your analysis period."
                ))
            
            # Check for year gaps
            years = sorted(set(d.year for d in dates))
            year_gaps = []
            for i in range(1, len(years)):
                gap = years[i] - years[i-1]
                if gap > 1:
                    year_gaps.append((years[i-1], years[i]))
            
            if year_gaps:
                gap_strs = [f"{a}-{b}" for a, b in year_gaps[:3]]
                self.issues.append(QualityIssue(
                    severity='warning',
                    category='date_gap',
                    field=date_field,
                    message=f"Found {len(year_gaps)} year gap(s) in data",
                    count=len(year_gaps),
                    sample_values=gap_strs,
                    recommendation="Check for missing years of data. May affect trend analysis."
                ))
        
        except Exception as e:
            self.issues.append(QualityIssue(
                severity='error',
                category='date_gap',
                field=date_field,
                message=f"Error analyzing dates: {str(e)}",
                count=0,
                sample_values=[],
                recommendation="Check date field format and values."
            ))
    
    def _check_null_severities(self) -> None:
        """Check for null/unknown severity values."""
        if not self.layer:
            return
        
        severity_field = self.field_map.get("accident_class")
        if not severity_field:
            return
        
        try:
            idx = self.layer.fields().indexOf(severity_field)
            if idx < 0:
                return
            
            null_count = 0
            unknown_count = 0
            total = 0
            
            for f in self.layer.getFeatures():
                total += 1
                raw = f[severity_field]
                
                if is_blank(raw):
                    null_count += 1
                elif self.decodes:
                    decoded = self.decodes.decode("accident_class", raw)
                    if decoded in ("Unknown", "Unknown / blank", ""):
                        unknown_count += 1
            
            total_unknown = null_count + unknown_count
            if total_unknown > 0:
                pct = 100 * total_unknown / max(total, 1)
                severity = 'error' if pct > 10 else 'warning' if pct > 5 else 'info'
                
                self.issues.append(QualityIssue(
                    severity=severity,
                    category='null_severity',
                    field=severity_field,
                    message=f"{total_unknown} records ({pct:.1f}%) have null/unknown severity",
                    count=total_unknown,
                    sample_values=[],
                    recommendation="Verify severity field mapping and decode table."
                ))
        
        except Exception as e:
            pass
    
    def _check_field_completeness(self) -> None:
        """Check completeness of key fields."""
        if not self.layer:
            return
        
        key_fields = [
            ("date", "Date"),
            ("accident_class", "Accident class"),
            ("municipality", "Municipality"),
            ("impact_type", "Impact type"),
        ]
        
        for concept, label in key_fields:
            field_name = self.field_map.get(concept)
            if not field_name:
                continue
            
            try:
                idx = self.layer.fields().indexOf(field_name)
                if idx < 0:
                    continue
                
                null_count = 0
                total = 0
                
                for f in self.layer.getFeatures():
                    total += 1
                    raw = f[field_name]
                    if is_blank(raw):
                        null_count += 1
                
                if total > 0:
                    pct = 100 * null_count / total
                    if pct > 10:
                        severity = 'warning'
                    elif pct > 0:
                        severity = 'info'
                    else:
                        continue
                    
                    self.issues.append(QualityIssue(
                        severity=severity,
                        category='completeness',
                        field=field_name,
                        message=f"{label} is {100-pct:.1f}% complete ({null_count} nulls)",
                        count=null_count,
                        sample_values=[],
                        recommendation=f"Consider investigating {null_count} missing values."
                    ))
            
            except Exception:
                pass
    
    def _update_issues_table(self) -> None:
        """Update the issues table with current issues."""
        self.issues_table.setRowCount(0)
        
        # Severity sort order
        severity_order = {'error': 0, 'warning': 1, 'info': 2}
        sorted_issues = sorted(self.issues, key=lambda i: severity_order.get(i.severity, 3))
        
        for issue in sorted_issues:
            row = self.issues_table.rowCount()
            self.issues_table.insertRow(row)
            
            # Severity with color
            sev_item = QTableWidgetItem(issue.severity.upper())
            colors = {
                'error': '#dc2626',
                'warning': '#ea580c',
                'info': '#2563eb'
            }
            sev_item.setForeground(Qt.red if issue.severity == 'error' else 
                                  (Qt.darkYellow if issue.severity == 'warning' else Qt.blue))
            sev_item.setData(Qt.UserRole, issue)
            
            self.issues_table.setItem(row, 0, sev_item)
            self.issues_table.setItem(row, 1, QTableWidgetItem(issue.category))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.field))
            self.issues_table.setItem(row, 3, QTableWidgetItem(str(issue.count) if issue.count > 0 else "-"))
            self.issues_table.setItem(row, 4, QTableWidgetItem(issue.message))
        
        self.issues_table.setVisible(bool(self.issues))
    
    def _on_issue_selected(self) -> None:
        """Handle issue selection to show details."""
        selected = self.issues_table.selectedItems()
        if not selected:
            self.details_group.setVisible(False)
            return
        
        row = selected[0].row()
        issue = self.issues_table.item(row, 0).data(Qt.UserRole)
        
        if not issue:
            return
        
        details = f"""
        <b>Severity:</b> {issue.severity.upper()}<br>
        <b>Category:</b> {issue.category}<br>
        <b>Field:</b> {issue.field}<br>
        <b>Count:</b> {issue.count if issue.count > 0 else 'N/A'}<br>
        <b>Message:</b> {issue.message}<br>
        """
        
        if issue.sample_values:
            details += f"<b>Sample values:</b> {', '.join(issue.sample_values[:5])}<br>"
        
        details += f"<b>Recommendation:</b> {issue.recommendation}"
        
        self.details_text.setText(details)
        self.details_group.setVisible(True)
    
    def export_report(self) -> None:
        """Export quality report to text file."""
        if not self.issues:
            QMessageBox.information(self, "Data Quality", "No issues to export.")
            return
        
        from qgis.PyQt.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Quality Report", "quality_report.txt", "Text (*.txt)"
        )
        if not path:
            return
        
        try:
            with open(path, 'w') as f:
                f.write("=" * 60 + "\n")
                f.write("DATA QUALITY REPORT\n")
                f.write("=" * 60 + "\n\n")
                
                if self.layer:
                    f.write(f"Layer: {self.layer.name()}\n")
                    f.write(f"Features: {self.layer.featureCount()}\n\n")
                
                f.write(f"Total issues: {len(self.issues)}\n")
                f.write(f"  Errors: {sum(1 for i in self.issues if i.severity == 'error')}\n")
                f.write(f"  Warnings: {sum(1 for i in self.issues if i.severity == 'warning')}\n")
                f.write(f"  Info: {sum(1 for i in self.issues if i.severity == 'info')}\n\n")
                
                f.write("-" * 60 + "\n")
                f.write("ISSUE DETAILS\n")
                f.write("-" * 60 + "\n\n")
                
                for i, issue in enumerate(self.issues, 1):
                    f.write(f"{i}. [{issue.severity.upper()}] {issue.category}\n")
                    f.write(f"   Field: {issue.field}\n")
                    f.write(f"   Count: {issue.count if issue.count > 0 else 'N/A'}\n")
                    f.write(f"   Message: {issue.message}\n")
                    if issue.sample_values:
                        f.write(f"   Samples: {', '.join(issue.sample_values[:5])}\n")
                    f.write(f"   Recommendation: {issue.recommendation}\n\n")
            
            QMessageBox.information(self, "Data Quality", f"Report saved:\n{path}")
        
        except Exception as e:
            QMessageBox.warning(self, "Data Quality", f"Export failed:\n{e}")
