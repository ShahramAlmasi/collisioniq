from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Optional, Tuple

def _is_qt_null(v: Any) -> bool:
    try:
        if hasattr(v, "isNull") and v.isNull():
            return True
        if hasattr(v, "isValid") and not v.isValid():
            return True
    except Exception:
        return False
    return False

def safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)

def is_blank(v: Any) -> bool:
    if v is None:
        return True
    if _is_qt_null(v):
        return True
    if isinstance(v, str):
        s = v.strip()
        return s == "" or s.upper() == "NULL"
    s = safe_str(v).strip()
    return s == "" or s.upper() == "NULL"

def to_datetime(value: Any) -> Optional[datetime]:
    # QDateTime/QDate in QGIS often provide these methods
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)

    if hasattr(value, "toPyDateTime"):
        try:
            return value.toPyDateTime()
        except Exception:
            pass
    if hasattr(value, "toPyDate"):
        try:
            d = value.toPyDate()
            return datetime(d.year, d.month, d.day)
        except Exception:
            pass

    s = safe_str(value).strip()
    if not s:
        return None

    # ISO-ish strings
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00") if s.endswith("Z") else s)
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m/%d/%y",
    ):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    return None

def clamp_date_range(start_date: date, end_date: date) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(start_date, time(0, 0, 0))
    # inclusive end-of-day
    end_dt = datetime.combine(end_date, time(23, 59, 59, 999000))
    return start_dt, end_dt

def try_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = safe_str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None

def numeric_str(v: Any) -> Optional[str]:
    """Human-stable numeric formatting for matching (e.g., 1.0 -> '1')."""
    f = try_float(v)
    if f is None:
        return None
    if abs(f - int(f)) < 1e-9:
        return str(int(f))
    return str(f)
