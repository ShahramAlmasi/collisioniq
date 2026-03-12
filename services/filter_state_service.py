from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from ..core.filters import FilterSpec


@dataclass(frozen=True)
class FilterPanelState:
    use_date: bool
    date_start: date
    date_end: date
    selection_only: bool
    select_filtered: bool
    selected_codes: Dict[str, Set[str]]


@dataclass(frozen=True)
class FilterExecutionPlan:
    spec: FilterSpec
    needed_fields: List[str]
    mode: str
    status_text: str


def default_last_full_10y_range(today: Optional[date] = None) -> Tuple[date, date]:
    today = today or date.today()
    end_year = today.year - 1
    return date(end_year - 9, 1, 1), date(end_year, 12, 31)


def build_filter_spec(layer, field_map: Dict[str, str], state: FilterPanelState) -> FilterSpec:
    selected_fids = set(layer.selectedFeatureIds()) if layer is not None else set()
    return FilterSpec(
        selection_only=state.selection_only,
        selected_fids=selected_fids,
        date_enabled=state.use_date,
        date_field=field_map.get("date"),
        date_start=state.date_start,
        date_end=state.date_end,
        category_codes=state.selected_codes,
        field_map=field_map,
    )


def collect_needed_fields(layer, spec: FilterSpec, field_map: Dict[str, str]) -> List[str]:
    if layer is None:
        return []

    layer_fields = {field.name() for field in layer.fields()}
    needed = set()

    if spec.date_enabled and spec.date_field and spec.date_field in layer_fields:
        needed.add(spec.date_field)

    for concept_key, selected_codes in spec.category_codes.items():
        if not selected_codes:
            continue
        field_name = spec.field_map.get(concept_key)
        if field_name and field_name in layer_fields:
            needed.add(field_name)

    for field_name in field_map.values():
        if field_name and field_name in layer_fields:
            needed.add(field_name)

    return sorted(needed)


def build_execution_plan(
    layer,
    field_map: Dict[str, str],
    state: FilterPanelState,
    *,
    background_threshold: int,
    today: Optional[date] = None,
) -> FilterExecutionPlan:
    spec = build_filter_spec(layer, field_map, state)
    needed_fields = collect_needed_fields(layer, spec, field_map)
    default_start, default_end = default_last_full_10y_range(today)

    if (
        spec.selection_only
        and not spec.selected_fids
        and not spec.has_any_intent(default_start, default_end)
    ):
        return FilterExecutionPlan(
            spec=spec,
            needed_fields=needed_fields,
            mode="idle",
            status_text="Idle: select features or set filters, then Apply.",
        )

    if layer is None:
        return FilterExecutionPlan(
            spec=spec,
            needed_fields=needed_fields,
            mode="idle",
            status_text="No layer selected.",
        )

    feature_count = layer.featureCount()
    mode = "background" if feature_count >= background_threshold else "sync"
    return FilterExecutionPlan(
        spec=spec,
        needed_fields=needed_fields,
        mode=mode,
        status_text=f"Filtering {feature_count:,} features...",
    )
