from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..core.utils import is_blank, safe_str


@dataclass(frozen=True)
class FilterOptions:
    title: str
    items: List[Tuple[str, str]]
    checked: Set[str]
    warning: Optional[str] = None


def count_codes(rows: Sequence[Dict[str, object]], field_name: Optional[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not field_name:
        return counts

    for row in rows or []:
        raw_value = row.get(field_name)
        if is_blank(raw_value):
            continue
        code = safe_str(raw_value).strip()
        counts[code] = counts.get(code, 0) + 1
    return counts


def _gather_codes_from_selection(layer, field_name: str, selection_fids: Set[int]) -> Set[str]:
    from qgis.core import QgsFeatureRequest

    codes: Set[str] = set()
    request = QgsFeatureRequest().setFilterFids(list(selection_fids))
    request.setSubsetOfAttributes([field_name], layer.fields())
    for feature in layer.getFeatures(request):
        raw_value = feature[field_name]
        if is_blank(raw_value):
            continue
        code = safe_str(raw_value).strip()
        if code:
            codes.add(code)
    return codes


def _gather_codes_from_layer(layer, field_name: str) -> Set[str]:
    codes: Set[str] = set()
    index = layer.fields().indexOf(field_name)
    for value in layer.uniqueValues(index, 5000):
        if is_blank(value):
            continue
        code = safe_str(value).strip()
        if code:
            codes.add(code)
    return codes


def build_filter_options(
    *,
    layer,
    field_map: Dict[str, str],
    concept_titles: Iterable[Tuple[str, str]],
    source: str,
    checked_codes: Dict[str, Set[str]],
    rows: Sequence[Dict[str, object]],
    decode_mapping: Callable[[str], Dict[str, str]],
    decode_value: Callable[[str, object], str],
) -> Tuple[Dict[str, FilterOptions], Optional[str]]:
    options: Dict[str, FilterOptions] = {}
    warning: Optional[str] = None

    if layer is None:
        return options, warning

    layer_fields = {field.name() for field in layer.fields()}
    selection_fids = set(layer.selectedFeatureIds())

    for concept_key, title in concept_titles:
        field_name = field_map.get(concept_key)
        checked = set(checked_codes.get(concept_key, set()))

        if not field_name or field_name not in layer_fields:
            options[concept_key] = FilterOptions(
                title=f"{title} (field not mapped)",
                items=[],
                checked=checked,
            )
            continue

        codes: Set[str] = set()
        if source == "decodes":
            codes.update(decode_mapping(concept_key).keys())
        elif source == "selection":
            if not selection_fids:
                warning = "No selected features in map."
            else:
                codes.update(_gather_codes_from_selection(layer, field_name, selection_fids))
        elif source == "layer":
            try:
                codes.update(_gather_codes_from_layer(layer, field_name))
            except Exception:
                codes.update(decode_mapping(concept_key).keys())

        counts = count_codes(rows, field_name)
        items = sorted(
            [
                (
                    code,
                    f"{decode_value(concept_key, code)} ({counts.get(code, 0)})",
                )
                for code in codes
            ],
            key=lambda item: item[1].lower(),
        )
        options[concept_key] = FilterOptions(title=title, items=items, checked=checked)

    return options, warning
