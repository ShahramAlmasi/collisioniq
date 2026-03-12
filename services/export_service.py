from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from ..core.analytics import summarize_rows
from ..core.utils import safe_str


@dataclass(frozen=True)
class FeatureExportTable:
    headers: List[str]
    rows: List[List[str]]


def build_summary_export_rows(
    filtered_rows: Sequence[Dict[str, Any]],
    field_map: Dict[str, str],
    decode_severity: Callable[[Any], str],
    *,
    selection_only: bool,
) -> List[Tuple[str, Any]]:
    summary = summarize_rows(list(filtered_rows), field_map, decode_severity)
    return [
        ("filtered_collisions", summary.total),
        ("fatal_collisions", summary.fatal),
        ("injury_collisions", summary.injury),
        ("pdo_collisions", summary.pdo),
        ("unknown_severity_collisions", summary.unknown_severity),
        ("severe_collisions", summary.severe),
        ("severe_share_pct", round(summary.severe_rate, 2)),
        ("sum_involved_vehicles_cnt", summary.sum_vehicles),
        ("sum_involved_persons_cnt", summary.sum_persons),
        ("sum_involved_drivers_cnt", summary.sum_drivers),
        ("sum_involved_occupants_cnt", summary.sum_occupants),
        ("sum_involved_pedestrians_cnt", summary.sum_pedestrians),
        ("scope", "selection" if selection_only else "layer"),
    ]


def format_export_value(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    if isinstance(raw_value, datetime):
        return raw_value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(raw_value, date):
        return raw_value.strftime("%Y-%m-%d")
    if hasattr(raw_value, "toPyDateTime"):
        try:
            return raw_value.toPyDateTime().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return safe_str(raw_value)
    if hasattr(raw_value, "toPyDate"):
        try:
            return raw_value.toPyDate().strftime("%Y-%m-%d")
        except Exception:
            return safe_str(raw_value)
    return safe_str(raw_value)


def build_feature_export_table(
    filtered_rows: Sequence[Dict[str, Any]],
    field_map: Dict[str, str],
    decode_keys: Iterable[str],
    decode_value: Callable[[str, Any], str],
) -> FeatureExportTable:
    all_fields = sorted({field for row in filtered_rows for field in row.keys()})
    field_to_concept = {
        field_name: concept_key
        for concept_key, field_name in field_map.items()
        if field_name in all_fields
    }

    decode_keys = set(decode_keys)
    headers: List[str] = []
    for field in all_fields:
        headers.append(field)
        concept_key = field_to_concept.get(field)
        if concept_key and concept_key in decode_keys:
            headers.append(f"{field}_decoded")

    rows: List[List[str]] = []
    for row in filtered_rows:
        out: List[str] = []
        for field in all_fields:
            raw_value = row.get(field)
            out.append(format_export_value(raw_value))
            concept_key = field_to_concept.get(field)
            if concept_key and concept_key in decode_keys:
                out.append(decode_value(concept_key, raw_value))
        rows.append(out)

    return FeatureExportTable(headers=headers, rows=rows)


def render_dashboard_png(path: str, cards: Sequence[Any], figure_factory: Callable[..., Any], *, cols: int = 2, dpi: int = 200) -> None:
    rows = (len(cards) + cols - 1) // cols
    figure = figure_factory(figsize=(cols * 7.5, rows * 3.2))

    for index, card in enumerate(cards):
        ax = figure.add_subplot(rows, cols, index + 1)
        ax.set_title(card.title, fontsize=10)
        try:
            card.render_fn(ax, card)
        except Exception as exc:
            ax.text(
                0.5,
                0.5,
                f"Chart error:\n{exc}",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()

    figure.tight_layout()
    figure.savefig(path, dpi=dpi)
