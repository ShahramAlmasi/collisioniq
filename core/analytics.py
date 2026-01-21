from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
