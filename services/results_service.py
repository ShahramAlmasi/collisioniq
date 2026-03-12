from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from ..core.analytics import summarize_rows


@dataclass(frozen=True)
class DashboardSnapshot:
    matched_count: int
    total_count: int
    total_value: str
    fatal_value: str
    severe_value: str
    status_text: str


def build_idle_snapshot(status_text: str = "Idle: select features or set filters, then Apply.") -> DashboardSnapshot:
    return DashboardSnapshot(
        matched_count=0,
        total_count=0,
        total_value="-",
        fatal_value="-",
        severe_value="-",
        status_text=status_text,
    )


def build_dashboard_snapshot(
    rows: List[Dict[str, Any]],
    total_count: int,
    field_map: Dict[str, str],
    decode_severity: Callable[[Any], str],
) -> DashboardSnapshot:
    summary = summarize_rows(rows, field_map, decode_severity)
    if summary.total == 0:
        return DashboardSnapshot(
            matched_count=0,
            total_count=total_count,
            total_value="0",
            fatal_value="0",
            severe_value="0%",
            status_text=f"Matched 0 of {total_count:,} features.",
        )

    return DashboardSnapshot(
        matched_count=summary.total,
        total_count=total_count,
        total_value=f"{summary.total:,}",
        fatal_value=f"{summary.fatal:,}",
        severe_value=f"{summary.severe_rate:.1f}%",
        status_text=f"Matched {summary.total:,} of {total_count:,} features.",
    )
