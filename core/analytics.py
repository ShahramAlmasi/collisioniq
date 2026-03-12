from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .utils import safe_str, to_datetime, try_float

@dataclass(frozen=True)
class SummaryNumbers:
    total: int
    severe: int
    severe_rate: float
    fatal: int
    injury: int
    pdo: int
    unknown_severity: int
    sum_vehicles: float
    sum_persons: float
    sum_drivers: float
    sum_occupants: float
    sum_pedestrians: float


def severity_counter(
    rows: List[Dict[str, Any]],
    field: Optional[str],
    decode: Callable[[Any], str],
) -> Counter:
    c: Counter = Counter()
    if not field:
        return c
    for r in rows:
        raw = r.get(field)
        label = decode(raw)
        if not safe_str(label).strip():
            label = "Unknown / blank"
        c[label] += 1
    return c

def counter(rows: List[Dict[str, Any]], field: Optional[str]) -> Counter:
    c: Counter = Counter()
    if not field:
        return c
    for r in rows:
        v = safe_str(r.get(field)).strip()
        if not v:
            c["Unknown / blank"] += 1
        else:
            c[v] += 1
    return c

def sum_numeric(rows: List[Dict[str, Any]], field: Optional[str]) -> float:
    if not field:
        return 0.0
    s = 0.0
    for r in rows:
        f = try_float(r.get(field))
        if f is not None:
            s += f
    return s

def by_year(rows: List[Dict[str, Any]], date_field: Optional[str]) -> Counter:
    c: Counter = Counter()
    if not date_field:
        return c
    for r in rows:
        dt = to_datetime(r.get(date_field))
        if dt is not None:
            c[dt.year] += 1
    return c


def summarize_rows(
    rows: List[Dict[str, Any]],
    field_map: Dict[str, str],
    decode_severity: Callable[[Any], str],
) -> SummaryNumbers:
    total = len(rows)
    sev_counts = severity_counter(rows, field_map.get("accident_class"), decode_severity)

    fatal = sev_counts.get("Fatal", 0)
    injury = sev_counts.get("Injury", 0)
    pdo = sev_counts.get("PDO", 0)
    unknown = sev_counts.get("Unknown", 0) + sev_counts.get("Unknown / blank", 0)
    severe = fatal + injury
    severe_rate = ((severe / total) * 100.0) if total else 0.0

    return SummaryNumbers(
        total=total,
        severe=severe,
        severe_rate=severe_rate,
        fatal=fatal,
        injury=injury,
        pdo=pdo,
        unknown_severity=unknown,
        sum_vehicles=sum_numeric(rows, field_map.get("veh_cnt")),
        sum_persons=sum_numeric(rows, field_map.get("per_cnt")),
        sum_drivers=sum_numeric(rows, field_map.get("drv_cnt")),
        sum_occupants=sum_numeric(rows, field_map.get("occ_cnt")),
        sum_pedestrians=sum_numeric(rows, field_map.get("ped_cnt")),
    )
