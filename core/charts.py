from __future__ import annotations

import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from .utils import safe_str, to_datetime, is_blank

try:
    from qgis.core import QgsMessageLog, Qgis
except Exception:  # pragma: no cover
    QgsMessageLog = None
    Qgis = None


def _debug_log(msg: str) -> None:
    """Best-effort debug logging to QGIS message log."""
    if QgsMessageLog is None or Qgis is None:
        return
    try:
        QgsMessageLog.logMessage(msg, "Collision Analytics", Qgis.Info)
    except Exception:
        pass

# Optional matplotlib (QGIS runs Qt; FigureCanvasQTAgg is the right target)
try:
    import matplotlib
    matplotlib.use("QtAgg")  # QGIS/Qt-friendly backend
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    FigureCanvas = None
    Figure = None
    plt = None
    FuncFormatter = None
    MaxNLocator = None


# -----------------------------
# Palettes / "TAC-ish" conventions
# -----------------------------
# Severity is typically ordered most-to-least severe in safety analytics.
TAC_SEVERITY_ORDER = ["Fatal", "Injury", "PDO", "Unknown / blank"]
TAC_SEVERITY_COLORS = {
    "Fatal": "#B71C1C",   # deep red
    "Injury": "#F9A825",  # amber
    "PDO": "#1565C0",     # strong blue
    "Unknown / blank": "#9E9E9E",
}

# Neutral + accents for non-severity categorical charts
MODERN_COLORS = [
    "#2563EB", "#7C3AED", "#0EA5E9", "#10B981", "#F59E0B",
    "#EF4444", "#8B5CF6", "#14B8A6", "#F97316", "#64748B",
]

# Back-compat alias (older code referenced COLORBLIND_SAFE)
COLORBLIND_SAFE = [
    "#0173B2", "#DE8F05", "#029E73", "#CC78BC", "#CA9161",
    "#949494", "#ECE133", "#56B4E9", "#D55E00", "#F0E442",
]


# -----------------------------
# Config / theme helpers
# -----------------------------
@dataclass
class ChartConfig:
    """Chart rendering configuration (drop-in compatible, with extra knobs)."""
    colors: Optional[List[str]] = None
    show_labels: bool = True
    top_n: int = 10
    font_family: str = "sans-serif"
    use_colorblind_safe: bool = False

    # Severity mapping + style controls
    use_tac_severity: bool = True
    severity_order: List[str] = None
    severity_colors: Dict[str, str] = None

    # Smart-labeling thresholds (prevents label soup on dense charts)
    label_min_fraction_of_max: float = 0.06  # label only if >= 6% of max total
    label_min_value: int = 20               # absolute minimum to label segments
    total_label_max_buckets: int = 16       # label totals only when buckets are few

    # Trend / average overlays
    show_average_line: bool = True
    show_total_line: bool = True
    show_trend_line: bool = True
    show_ksi_line: bool = True  # KSI = Fatal + Injury (common safety KPI)

    def __post_init__(self) -> None:
        if self.colors is None:
            self.colors = COLORBLIND_SAFE if self.use_colorblind_safe else MODERN_COLORS
        if self.severity_order is None:
            self.severity_order = list(TAC_SEVERITY_ORDER)
        if self.severity_colors is None:
            self.severity_colors = dict(TAC_SEVERITY_COLORS)


@dataclass
class ChartCard:
    title: str
    figure: Any
    canvas: Any
    render_fn: Callable


def _fmt_int(x: Any) -> str:
    try:
        v = int(x)
    except Exception:
        return safe_str(x)
    return f"{v:,}"


def _human_int(x: Any) -> str:
    """Readable labels without losing integrity (no '1.2M' unless huge)."""
    try:
        v = float(x)
    except Exception:
        return safe_str(x)
    av = abs(v)
    if av >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if av >= 10_000:
        return f"{v/1_000:.1f}k"
    if av >= 1_000:
        return f"{v/1_000:.2f}k"
    return f"{int(round(v)):,}"


def _axis_thousands_formatter():
    if FuncFormatter is None:
        return None
    return FuncFormatter(lambda x, pos: _human_int(x))


def apply_modern_style(ax, *, format_x: bool = True, format_y: bool = True) -> None:
    """Modern, low-clutter styling for matplotlib axes.

    format_x / format_y control whether numeric formatters are applied. Disable
    for categorical axes to avoid clobbering custom tick labels.
    """
    ax.set_facecolor("#FBFBFC")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D7DCE3")
    ax.spines["bottom"].set_color("#D7DCE3")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)

    ax.grid(True, axis="y", alpha=0.22, linestyle="--", linewidth=0.6, color="#A8B3C3")
    ax.set_axisbelow(True)

    ax.tick_params(colors="#4B5563", which="both", labelsize=9)

    try:
        fmt = _axis_thousands_formatter()
        if fmt is not None:
            if format_y:
                ax.yaxis.set_major_formatter(fmt)
            if format_x:
                ax.xaxis.set_major_formatter(fmt)
        if MaxNLocator is not None and format_y:
            ax.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True, prune=None))
    except Exception:
        pass


def legend_below(ax, title: Optional[str] = None, ncol: Optional[int] = None) -> None:
    """Place legend below the chart, stretched across full width."""
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return

    count = len(labels)
    cols = ncol if ncol is not None else max(2, min(count, 6))
    ax.legend(
        handles,
        labels,
        title=title,
        fontsize=8,
        title_fontsize=9 if title else None,
        framealpha=0.95,
        edgecolor="#D7DCE3",
        loc="upper left",
        bbox_to_anchor=(0, -0.22, 1, 0.01),
        mode="expand",
        ncol=cols,
        columnspacing=1.1,
        handletextpad=0.6,
        borderpad=0.6,
        fancybox=True,
    )


def wrap_label(s: str, width: int = 26) -> str:
    """Wrap long labels with smart truncation."""
    s = s or ""
    if len(s) <= width:
        return s

    wrapped = textwrap.wrap(s, width=width)
    if len(wrapped) > 2:
        wrapped = wrapped[:2]
        wrapped[1] = (wrapped[1][: max(0, width - 3)] + "...") if len(wrapped[1]) >= width else wrapped[1]
    return "\n".join(wrapped)


def _format_hour_label(hour: int) -> str:
    """Convert an hour number into a friendly 12-hour label."""
    h = int(hour) % 24
    suffix = "AM" if h < 12 else "PM"
    display = h % 12
    if display == 0:
        display = 12
    return f"{display} {suffix}"


def _format_hour_label_compact(hour: int) -> str:
    """Compact hour label to reduce tick clutter (e.g., 12a, 1p)."""
    h = int(hour) % 24
    suffix = "a" if h < 12 else "p"
    display = h % 12
    if display == 0:
        display = 12
    return f"{display}{suffix}"


def get_color_gradient(n: int, base_colors: List[str]) -> List[str]:
    """Back-compat: cycle through colors if needed."""
    if n <= len(base_colors):
        return base_colors[:n]
    return [base_colors[i % len(base_colors)] for i in range(n)]


def _moving_average(values: List[float], window: int) -> np.ndarray:
    if window <= 1:
        return np.asarray(values, dtype=float)
    arr = np.asarray(values, dtype=float)
    if len(arr) < window:
        return arr
    pad = window // 2
    padded = np.pad(arr, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def _trend_line(x: List[float], y: List[float]) -> Tuple[float, float, np.ndarray]:
    """Return slope, intercept, fitted y values."""
    if len(x) < 2:
        return 0.0, float(y[0]) if y else 0.0, np.asarray(y, dtype=float)
    z = np.polyfit(x, y, 1)
    slope, intercept = float(z[0]), float(z[1])
    p = np.poly1d(z)
    yhat = p(np.asarray(x, dtype=float))
    return slope, intercept, yhat


def _severity_color(label: str, config: ChartConfig) -> Optional[str]:
    if not config.use_tac_severity:
        return None
    return config.severity_colors.get(label)


def _ordered_class_labels(
    encountered: Set[str],
    mapping: Optional[Dict[str, str]],
    preferred_order: Optional[List[str]] = None,
    config: Optional[ChartConfig] = None,
) -> List[str]:
    """Stable ordering for accident class labels, with severity-first behavior."""
    ordered: List[str] = []

    if config and config.use_tac_severity:
        for lab in config.severity_order:
            if lab in encountered and lab not in ordered:
                ordered.append(lab)

    if preferred_order:
        for lab in preferred_order:
            if lab in encountered and lab not in ordered:
                ordered.append(lab)

    if mapping:
        def sort_key(item):
            code, _ = item
            try:
                return (0, float(code))
            except Exception:
                return (1, safe_str(code))

        for _, label in sorted(mapping.items(), key=sort_key):
            if label in encountered and label not in ordered:
                ordered.append(label)

    for label in sorted(encountered):
        if label not in ordered:
            ordered.append(label)

    return ordered


@lru_cache(maxsize=256)
def _cached_decode(value: str, decoder_id: int) -> str:
    return value


def _is_blank(raw: Any) -> bool:
    """Treat None / empty / whitespace / NULL as blank. Numeric 0 is NOT blank."""
    return is_blank(raw)


def counter_decoded(
    rows: List[Dict[str, Any]],
    field: Optional[str],
    decode: Callable[[Any], str],
    include_blank: bool,
) -> Counter:
    """Count decoded values.

    Important: pass the *raw* value into decode(). Many QGIS fields are numeric and
    decoders often key off ints. We only stringify for blank detection.
    """
    c: Counter = Counter()
    if not field:
        return c

    for r in rows:
        raw = r.get(field)
        if _is_blank(raw):
            if include_blank:
                c["Unknown / blank"] += 1
            continue

        try:
            c[decode(raw)] += 1
        except Exception:
            # Fall back to a safe string if a decoder chokes on a QVariant/numpy type
            c[decode(safe_str(raw))] += 1

    return c

    for r in rows:
        raw = r.get(field)
        s = safe_str(raw).strip()
        if not s:
            if include_blank:
                c["Unknown / blank"] += 1
            continue
        c[decode(s)] += 1

    return c


def validate_temporal_field(rows: List[Dict[str, Any]], date_field: Optional[str]) -> Tuple[bool, str]:
    if not date_field:
        return False, "Date field not mapped"

    valid_count = sum(1 for r in rows if to_datetime(r.get(date_field)) is not None)
    if valid_count == 0:
        return False, "No valid date data available"
    return True, ""


def _sequential_palette(n: int, base_colors: List[str]) -> List[str]:
    if n <= 0:
        return []
    if n <= len(base_colors):
        return base_colors[:n]
    return [base_colors[i % len(base_colors)] for i in range(n)]


def barh_modern(ax, labels: List[str], values: List[int], config: ChartConfig, *, show_share: bool = True) -> None:
    if not values:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    labels = [wrap_label(l, 28) for l in labels]
    y = np.arange(len(labels))

    total = float(sum(values)) if sum(values) else 1.0
    colors = _sequential_palette(len(values), config.colors)

    bars = ax.barh(
        y,
        values,
        color=colors,
        edgecolor="white",
        linewidth=1.4,
        alpha=0.9,
        height=0.72,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()

    ax.grid(True, axis="x", alpha=0.22, linestyle="--", linewidth=0.6, color="#A8B3C3")
    ax.set_axisbelow(True)

    apply_modern_style(ax, format_y=False)
    ax.set_xlabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    if config.show_labels:
        max_val = max(values) if values else 0
        pad = max(1.0, max_val * 0.02)
        for i, (v, bar) in enumerate(zip(values, bars)):
            share = (v / total) * 100.0
            tail = f"  ({share:.1f}%)" if show_share else ""
            ax.text(
                v + pad,
                i,
                f"{_fmt_int(v)}{tail}",
                va="center",
                fontsize=9,
                fontweight="600",
                color="#374151",
            )


def _add_band(ax, x0: float, x1: float, *, label: Optional[str] = None, y: float = 0.98) -> None:
    try:
        ax.axvspan(x0, x1, color="#111827", alpha=0.06, zorder=0)
        if label:
            ax.text((x0 + x1) / 2.0, y, label, ha="center", va="top",
                    transform=ax.get_xaxis_transform(), fontsize=8, color="#6B7280")
    except Exception:
        pass


def _maybe_add_avg_and_trend(
    ax,
    x: List[float],
    totals: List[int],
    config: ChartConfig,
    *,
    label_prefix: str = "Total",
    allow_trend: bool = True,
) -> None:
    if not totals:
        return

    xarr = np.asarray(x, dtype=float)
    yarr = np.asarray(totals, dtype=float)

    if config.show_total_line and len(totals) >= 2:
        ax.plot(
            xarr,
            yarr,
            linewidth=2.2,
            marker="o",
            markersize=4.5,
            color="#111827",
            alpha=0.85,
            label=f"{label_prefix} (per bucket)",
            zorder=3,
        )

    if config.show_average_line and len(totals) >= 2:
        avg = float(np.mean(yarr))
        ax.axhline(avg, color="#111827", alpha=0.25, linewidth=1.6, linestyle="--", label="Average")
        ax.text(
            xarr[-1],
            avg,
            f"  avg {_human_int(avg)}",
            va="center",
            ha="left",
            fontsize=8,
            color="#6B7280",
        )

    if allow_trend and config.show_trend_line and len(totals) >= 3:
        slope, intercept, yhat = _trend_line(list(xarr), list(yarr))
        ax.plot(
            xarr,
            yhat,
            linewidth=2.0,
            linestyle=":",
            color="#EF4444",
            alpha=0.7,
            label="Trend",
            zorder=3,
        )

        mean = float(np.mean(yarr)) if float(np.mean(yarr)) else 1.0
        pct = (slope / mean) * 100.0
        ax.text(
            0.01,
            0.01,
            f"Trend: {slope:+.0f}/bucket ({pct:+.1f}%)",
            transform=ax.transAxes,
            fontsize=8,
            color="#6B7280",
            va="bottom",
            ha="left",
        )


def render_trend_year(ax, rows: List[Dict[str, Any]], date_field: Optional[str],
                      config: Optional[ChartConfig] = None) -> None:
    if config is None:
        config = ChartConfig()

    valid, msg = validate_temporal_field(rows, date_field)
    if not valid:
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    c: Counter = Counter()
    for r in rows:
        dt = to_datetime(r.get(date_field))
        if dt is not None:
            c[dt.year] += 1

    if not c:
        ax.text(0.5, 0.5, "No valid date data", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    years = sorted(c.keys())
    ys = [c[y] for y in years]
    x = list(range(len(years)))

    bars = ax.bar(
        x,
        ys,
        color="#2563EB",
        edgecolor="white",
        linewidth=1.4,
        alpha=0.85,
        width=0.72,
        zorder=2,
    )

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    ax.set_xlabel("Year", fontsize=10, fontweight="600", color="#111827")
    ax.set_ylabel("Collisions", fontsize=10, fontweight="600", color="#111827")
    apply_modern_style(ax, format_x=False)

    if config.show_labels and len(ys) <= 14:
        max_val = max(ys) if ys else 0
        for i, (bar, val) in enumerate(zip(bars, ys)):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                val + max(1.0, max_val * 0.01),
                _fmt_int(val),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="600",
                color="#374151",
            )

    _maybe_add_avg_and_trend(ax, x, ys, config, label_prefix="Total", allow_trend=True)
    legend_below(ax, ncol=3)


def render_day_of_week(ax, rows: List[Dict[str, Any]], date_field: Optional[str],
                       config: Optional[ChartConfig] = None) -> None:
    if config is None:
        config = ChartConfig()

    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    valid, msg = validate_temporal_field(rows, date_field)
    if not valid:
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    c: Counter = Counter()
    for r in rows:
        dt = to_datetime(r.get(date_field))
        if dt is not None:
            c[names[dt.weekday()]] += 1

    ys = [c.get(x, 0) for x in names]
    x = list(range(len(names)))

    colors = ["#2563EB"] * 5 + ["#7C3AED"] * 2
    bars = ax.bar(x, ys, color=colors, edgecolor="white", linewidth=1.4, alpha=0.88, width=0.72)

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_xlabel("Day of Week", fontsize=10, fontweight="600", color="#111827")
    ax.set_ylabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    apply_modern_style(ax, format_x=False)
    _add_band(ax, 4.5, 6.5, label="Weekend")

    if config.show_labels:
        max_val = max(ys) if ys else 0
        for bar, val in zip(bars, ys):
            if val <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                val + max(1.0, max_val * 0.01),
                _fmt_int(val),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="600",
                color="#374151",
            )

    _maybe_add_avg_and_trend(ax, x, ys, config, label_prefix="Total", allow_trend=False)
    legend_below(ax, ncol=2)


def render_hour_of_day(ax, rows: List[Dict[str, Any]], date_field: Optional[str],
                       config: Optional[ChartConfig] = None) -> None:
    if config is None:
        config = ChartConfig()

    valid, msg = validate_temporal_field(rows, date_field)
    if not valid:
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    c: Counter = Counter()
    has_time = False
    for r in rows:
        dt = to_datetime(r.get(date_field))
        if dt is not None:
            if dt.hour or dt.minute or dt.second:
                has_time = True
            c[dt.hour] += 1

    xs = list(range(24))
    ys = [c.get(h, 0) for h in xs]

    colors = []
    for h in xs:
        if 6 <= h < 9 or 15 <= h < 19:
            colors.append("#7C3AED")
        else:
            colors.append("#2563EB")

    ax.bar(xs, ys, color=colors, edgecolor="white", linewidth=1.0, alpha=0.88, width=0.85)

    ax.set_xticks(list(range(0, 24, 2)))
    ax.set_xticklabels([str(h) for h in range(0, 24, 2)])
    ax.set_xlabel("Hour (0–23)", fontsize=10, fontweight="600", color="#111827")
    ax.set_ylabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    apply_modern_style(ax, format_x=False)

    _add_band(ax, 6 - 0.5, 9 - 0.5, label="AM peak")
    _add_band(ax, 15 - 0.5, 19 - 0.5, label="PM peak")

    if len(ys) >= 5:
        sm = _moving_average([float(v) for v in ys], window=3)
        ax.plot(xs, sm, linewidth=2.2, color="#111827", alpha=0.75, label="3-hr avg", zorder=3)

    _maybe_add_avg_and_trend(ax, xs, ys, config, label_prefix="Total", allow_trend=False)

    if not has_time:
        ax.text(
            0.5,
            0.98,
            "Note: timestamps may be defaulted to midnight (check your input datetime field)",
            ha="center",
            va="top",
            transform=ax.transAxes,
            fontsize=8,
            color="#6B7280",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#FEF3C7", edgecolor="#F59E0B", alpha=0.65),
        )

    legend_below(ax, ncol=3)


def render_temporal_by_class(
    ax,
    rows: List[Dict[str, Any]],
    date_field: Optional[str],
    class_field: Optional[str],
    decode_class: Callable[[Any], str],
    class_mapping: Optional[Dict[str, str]],
    bucket: str,
    show_labels: bool = True,
    config: Optional[ChartConfig] = None,
) -> None:
    if config is None:
        config = ChartConfig(show_labels=show_labels)
    else:
        config.show_labels = show_labels

    if not date_field or not class_field:
        ax.text(0.5, 0.5, "Date / accident class not mapped", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    bucket_counts: Dict[Any, Counter] = defaultdict(Counter)
    encountered_classes: Set[str] = set()
    has_time = False if bucket == "hour" else None
    total_rows = len(rows)
    parsed_dates = 0
    time_component_rows = 0
    sample_invalid_dates: List[str] = []

    for r in rows:
        raw_dt = r.get(date_field)
        dt = to_datetime(raw_dt)
        if dt is None:
            if len(sample_invalid_dates) < 5:
                sample_invalid_dates.append(safe_str(raw_dt))
            continue
        parsed_dates += 1
        if bucket == "hour" and (dt.hour or dt.minute or dt.second):
            has_time = True
            time_component_rows += 1

        if bucket == "year":
            bkey = dt.year
        elif bucket == "month":
            bkey = dt.month
        elif bucket == "dow":
            bkey = dt.weekday()
        elif bucket == "hour":
            bkey = dt.hour
        else:
            ax.text(0.5, 0.5, f"Unsupported bucket: {bucket}", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="#9CA3AF")
            ax.set_axis_off()
            return

        cls_label = decode_class(r.get(class_field))
        if not safe_str(cls_label).strip():
            cls_label = "Unknown / blank"

        encountered_classes.add(cls_label)
        bucket_counts[bkey][cls_label] += 1

    if bucket == "hour":
        _debug_log(
            "[render_temporal_by_class/hour] "
            f"rows={total_rows}, parsed_dates={parsed_dates}, "
            f"time_component_rows={time_component_rows}, "
            f"date_field={safe_str(date_field)}, class_field={safe_str(class_field)}, "
            f"invalid_date_samples={sample_invalid_dates}"
        )

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    if bucket == "year":
        if not bucket_counts:
            ax.text(0.5, 0.5, "No date data available", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="#9CA3AF")
            ax.set_axis_off()
            return
        min_year = min(bucket_counts.keys())
        max_year = max(bucket_counts.keys())
        bucket_order = list(range(min_year, max_year + 1))
        bucket_labels = [str(b) for b in bucket_order]
        xlabel = "Year"
    elif bucket == "month":
        bucket_order = list(range(1, 13))
        bucket_labels = month_names
        xlabel = "Month"
        if not bucket_counts:
            ax.text(0.5, 0.5, "No date data available", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="#9CA3AF")
            ax.set_axis_off()
            return
    elif bucket == "dow":
        bucket_order = list(range(7))
        bucket_labels = dow_names
        xlabel = "Day of Week"
        if not bucket_counts:
            ax.text(0.5, 0.5, "No date data available", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="#9CA3AF")
            ax.set_axis_off()
            return
    else:
        bucket_order = list(range(24))
        bucket_labels = [_format_hour_label_compact(h) for h in bucket_order]
        xlabel = "Hour of day"
        if not bucket_counts:
            _debug_log(
                "[render_temporal_by_class/hour] no bucket counts produced; "
                f"rows={total_rows}, parsed_dates={parsed_dates}, "
                f"invalid_date_samples={sample_invalid_dates}"
            )
            ax.text(0.5, 0.5, "No date data available", ha="center", va="center",
                    transform=ax.transAxes, fontsize=11, color="#9CA3AF")
            ax.set_axis_off()
            return

    class_labels = _ordered_class_labels(
        encountered_classes,
        class_mapping,
        preferred_order=["Fatal", "Injury", "PDO"],
        config=config,
    )

    xpos = list(range(len(bucket_order)))
    bottoms = [0] * len(bucket_order)

    totals = [sum(bucket_counts.get(b, {}).values()) for b in bucket_order]
    max_total = max(totals) if totals else 0

    fallback = _sequential_palette(len(class_labels), config.colors)
    class_colors: List[str] = []
    for i, cls in enumerate(class_labels):
        class_colors.append(_severity_color(cls, config) or fallback[i % len(fallback)])

    for idx, cls in enumerate(class_labels):
        vals = [bucket_counts.get(b, Counter()).get(cls, 0) for b in bucket_order]
        base_levels = list(bottoms)
        ax.bar(
            xpos,
            vals,
            bottom=bottoms,
            label=cls,
            color=class_colors[idx],
            edgecolor="white",
            linewidth=1.0,
            alpha=0.88,
            width=0.75,
            zorder=2,
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]

        if config.show_labels:
            for i, v in enumerate(vals):
                if v <= 0:
                    continue
                if max_total > 0:
                    if v < config.label_min_value:
                        continue
                    if (v / max_total) < config.label_min_fraction_of_max:
                        continue
                ax.text(
                    xpos[i],
                    base_levels[i] + v / 2.0,
                    _human_int(v),
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="600",
                    color="#111827",
                )

    if config.show_labels and len(bucket_order) <= config.total_label_max_buckets:
        for i, t in enumerate(totals):
            ax.text(
                xpos[i],
                t + max(1.0, max_total * 0.01),
                _human_int(t),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="600",
                color="#374151",
            )

    ax.set_xticks(xpos)
    rotation = 45 if bucket in ("month",) else 0
    if bucket == "hour":
        # Show only every 4th hour to avoid label collisions; keep all bars visible.
        tick_labels = [_format_hour_label_compact(b) if (b % 4 == 0) else "" for b in bucket_order]
        ax.set_xticklabels(tick_labels, rotation=0, ha="center")
        ax.tick_params(axis="x", pad=6)
    else:
        ax.set_xticklabels(bucket_labels, rotation=rotation, ha="right" if rotation else "center")
    ax.set_xlabel(xlabel, fontsize=10, fontweight="600", color="#111827")
    ax.set_ylabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    apply_modern_style(ax, format_x=False)

    _maybe_add_avg_and_trend(
        ax,
        xpos,
        totals,
        config,
        label_prefix="Total",
        allow_trend=(bucket == "year"),
    )

    if bucket == "hour" and has_time is False:
        ax.text(
            0.5,
            0.98,
            "Note: timestamps may be defaulted to midnight (check your input datetime field)",
            ha="center",
            va="top",
            transform=ax.transAxes,
            fontsize=8,
            color="#6B7280",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#FEF3C7", edgecolor="#F59E0B", alpha=0.65),
        )

    if config.show_ksi_line and {"Fatal", "Injury"}.issubset(set(class_labels)):
        ksi = []
        for b in bucket_order:
            cc = bucket_counts.get(b, Counter())
            ksi.append(int(cc.get("Fatal", 0) + cc.get("Injury", 0)))
        ax.plot(
            xpos,
            ksi,
            linewidth=2.0,
            marker="o",
            markersize=4.0,
            linestyle="-",
            color="#10B981",
            alpha=0.85,
            label="KSI (Fatal+Injury)",
            zorder=3,
        )

    if bucket == "dow":
        _add_band(ax, 4.5, 6.5, label="Weekend")
    if bucket == "hour":
        _add_band(ax, 6 - 0.5, 9 - 0.5, label="AM peak")
        _add_band(ax, 15 - 0.5, 19 - 0.5, label="PM peak")

    legend_below(ax, title="Accident Class", ncol=max(3, min(len(class_labels) + 2, 6)))


def render_category(
    ax,
    rows: List[Dict[str, Any]],
    field: Optional[str],
    decode: Callable[[Any], str],
    top_n: int,
    show_labels: bool = True,
    config: Optional[ChartConfig] = None,
    include_blank: bool = True,
) -> None:
    if config is None:
        config = ChartConfig(show_labels=show_labels, top_n=top_n)
    else:
        config.show_labels = show_labels
        config.top_n = top_n

    c = counter_decoded(rows, field, decode, include_blank=include_blank)
    if not c:
        ax.text(0.5, 0.5, "Field not mapped or no data available",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    items = c.most_common()
    if len(items) > top_n:
        head = items[:top_n]
        other_sum = sum(v for _, v in items[top_n:])
        items = head + [("Other (combined)", other_sum)]

    labels = [k for k, _ in items]
    values = [v for _, v in items]

    if config.use_tac_severity and set(labels).issubset(set(config.severity_colors.keys())):
        ordered = [lab for lab in config.severity_order if lab in set(labels)]
        if ordered:
            idx = {lab: i for i, lab in enumerate(labels)}
            labels = ordered
            values = [values[idx[lab]] for lab in labels]

        config_local = ChartConfig(**{**config.__dict__})
        config_local.colors = [config.severity_colors.get(lab, "#64748B") for lab in labels]
        barh_modern(ax, labels, values, config_local, show_share=True)
        return

    barh_modern(ax, labels, values, config, show_share=True)


def render_category_by_class(
    ax,
    rows: List[Dict[str, Any]],
    category_field: Optional[str],
    decode_category: Callable[[Any], str],
    class_field: Optional[str],
    decode_class: Callable[[Any], str],
    class_mapping: Optional[Dict[str, str]],
    top_n: int,
    show_labels: bool = True,
    config: Optional[ChartConfig] = None,
    include_blank: bool = True,
) -> None:
    if config is None:
        config = ChartConfig(show_labels=show_labels, top_n=top_n)
    else:
        config.show_labels = show_labels
        config.top_n = top_n

    if not category_field or not class_field:
        ax.text(0.5, 0.5, "Category / accident class not mapped",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    cat_counts: Dict[str, Counter] = defaultdict(Counter)
    encountered_classes: Set[str] = set()

    for r in rows:
        raw_val = r.get(category_field)

        # Keep the original value type for decoding; use string only for blank detection.
        raw_s = safe_str(raw_val).strip()
        if not raw_s and not include_blank:
            continue

        if not raw_s:
            cat_label = "Unknown / blank"
        else:
            try:
                cat_label = decode_category(raw_val)
            except Exception:
                cat_label = decode_category(raw_s)

        cls_label = decode_class(r.get(class_field))
        if not safe_str(cls_label).strip():
            cls_label = "Unknown / blank"

        encountered_classes.add(cls_label)
        cat_counts[cat_label][cls_label] += 1

    if not cat_counts:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    totals = {cat: sum(c.values()) for cat, c in cat_counts.items()}
    sorted_cats = sorted(totals.items(), key=lambda t: t[1], reverse=True)

    if len(sorted_cats) > top_n:
        head = sorted_cats[:top_n]
        tail = sorted_cats[top_n:]
        other_counter: Counter = Counter()
        for cat, _ in tail:
            other_counter.update(cat_counts[cat])
        cat_counts["Other (combined)"] = other_counter
        sorted_cats = head + [("Other (combined)", sum(other_counter.values()))]

    categories = [wrap_label(cat, 28) for cat, _ in sorted_cats]
    class_labels = _ordered_class_labels(encountered_classes, class_mapping, config=config)

    y = list(range(len(categories)))
    left = [0] * len(categories)

    fallback = _sequential_palette(len(class_labels), config.colors)
    class_colors: List[str] = []
    for i, cls in enumerate(class_labels):
        class_colors.append(_severity_color(cls, config) or fallback[i % len(fallback)])

    for idx, cls in enumerate(class_labels):
        vals = [cat_counts[cat].get(cls, 0) for cat, _ in sorted_cats]
        ax.barh(
            y,
            vals,
            left=left,
            label=cls,
            color=class_colors[idx],
            edgecolor="white",
            linewidth=1.0,
            alpha=0.88,
            height=0.72,
        )
        left = [l + v for l, v in zip(left, vals)]

    if config.show_labels:
        max_total = max(left) if left else 0
        pad = max(1.0, max_total * 0.02)
        for i, total in enumerate(left):
            if total > 0:
                ax.text(
                    total + pad,
                    i,
                    _fmt_int(total),
                    va="center",
                    fontsize=8,
                    fontweight="600",
                    color="#374151",
                )

    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    ax.grid(True, axis="x", alpha=0.22, linestyle="--", linewidth=0.6, color="#A8B3C3")
    ax.set_axisbelow(True)
    apply_modern_style(ax, format_y=False)

    legend_below(ax, title="Accident Class", ncol=max(3, min(len(class_labels), 6)))


def render_pareto(
    ax,
    rows: List[Dict[str, Any]],
    field: Optional[str],
    decode: Callable[[Any], str],
    top_n: int,
    show_labels: bool = True,
    config: Optional[ChartConfig] = None,
) -> None:
    if config is None:
        config = ChartConfig(show_labels=show_labels, top_n=top_n)
    else:
        config.show_labels = show_labels
        config.top_n = top_n

    c = counter_decoded(rows, field, decode, include_blank=False)
    items = c.most_common(top_n)

    if not items:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    labels = [k for k, _ in items]
    counts = [v for _, v in items]
    total = sum(c.values()) or 1

    y = list(range(len(labels)))

    bar_colors = ["#2563EB"] + ["#93C5FD"] * (len(labels) - 1)
    ax.barh(y, counts, color=bar_colors, edgecolor="white", linewidth=1.2, alpha=0.9, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels([wrap_label(l, 28) for l in labels], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Collisions", fontsize=10, fontweight="600", color="#111827")

    ax.grid(True, axis="x", alpha=0.22, linestyle="--", linewidth=0.6, color="#A8B3C3")
    ax.set_axisbelow(True)
    apply_modern_style(ax, format_y=False)

    cum = []
    run = 0
    for v in counts:
        run += v
        cum.append(run / total * 100.0)

    ax2 = ax.twiny()
    ax2.plot(cum, y, marker="o", linewidth=2.4, markersize=5.0,
             color="#EF4444", alpha=0.85, label="Cumulative %")
    ax2.set_xlim(0, 100)
    ax2.set_xlabel("Cumulative %", fontsize=10, fontweight="600", color="#EF4444")
    ax2.tick_params(axis="x", colors="#EF4444", labelsize=9)
    ax2.spines["top"].set_color("#EF4444")
    ax2.spines["top"].set_linewidth(1.2)

    ax2.axvline(x=80, color="#6B7280", linestyle="--", linewidth=1.4, alpha=0.6)
    cross_idx = next((i for i, v in enumerate(cum) if v >= 80), None)
    if cross_idx is not None:
        ax2.scatter([cum[cross_idx]], [cross_idx], s=40, color="#10B981", zorder=4)
        ax2.text(80, cross_idx, " 80%", fontsize=8, color="#6B7280", va="center")
        ax2.text(
            0.98,
            0.02,
            f"80% reached by: {wrap_label(labels[cross_idx], 22)}",
            transform=ax2.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            color="#6B7280",
        )

    if config.show_labels:
        max_val = max(counts) if counts else 0
        pad = max(1.0, max_val * 0.02)
        for i, v in enumerate(counts):
            ax.text(
                v + pad,
                i,
                f"{_fmt_int(v)}  ({(v/total)*100:.1f}%)",
                va="center",
                fontsize=8,
                fontweight="600",
                color="#374151",
            )


def render_env_combo(
    ax,
    rows: List[Dict[str, Any]],
    field1: Optional[str],
    field2: Optional[str],
    decode1: Callable[[Any], str],
    decode2: Callable[[Any], str],
    top_n: int,
    show_labels: bool = True,
    config: Optional[ChartConfig] = None,
) -> None:
    if config is None:
        config = ChartConfig(show_labels=show_labels, top_n=top_n)
    else:
        config.show_labels = show_labels
        config.top_n = top_n

    if not field1 or not field2:
        ax.text(0.5, 0.5, "Environmental fields not mapped",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    c: Counter = Counter()
    for r in rows:
        raw1 = r.get(field1)
        raw2 = r.get(field2)

        s1 = safe_str(raw1).strip()
        s2 = safe_str(raw2).strip()

        # Treat null/blank/0 as not usable for the env-combo chart
        if not s1 or not s2 or s1 == "0" or s2 == "0":
            continue

        try:
            l1 = decode1(raw1)
        except Exception:
            l1 = decode1(s1)

        try:
            l2 = decode2(raw2)
        except Exception:
            l2 = decode2(s2)

        c[f"{l1} + {l2}"] += 1

    if not c:
        ax.text(0.5, 0.5, "No environmental combination data\n(non-null/non-zero)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#9CA3AF")
        ax.set_axis_off()
        return

    items = c.most_common()
    if len(items) > top_n:
        head = items[:top_n]
        other_sum = sum(v for _, v in items[top_n:])
        items = head + [("Other (combined)", other_sum)]

    labels = [k for k, _ in items]
    values = [v for _, v in items]
    barh_modern(ax, labels, values, config, show_share=True)


# -----------------------------
# Backward compatibility wrappers
# -----------------------------
def barh(ax, labels: List[str], values: List[int], show_labels: bool) -> None:
    config = ChartConfig(show_labels=show_labels)
    barh_modern(ax, labels, values, config, show_share=True)


def create_chart_config(
    use_colorblind_safe: bool = False,
    show_labels: bool = True,
    top_n: int = 10,
    custom_colors: Optional[List[str]] = None,
) -> ChartConfig:
    config = ChartConfig(
        use_colorblind_safe=use_colorblind_safe,
        show_labels=show_labels,
        top_n=top_n,
    )
    if custom_colors:
        config.colors = custom_colors
    return config
