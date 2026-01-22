from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from qgis.core import QgsFeatureRequest, QgsVectorLayer

from .utils import clamp_date_range, is_blank, numeric_str, to_datetime, try_float

@dataclass(frozen=True)
class FilterSpec:
    # scope
    selection_only: bool
    selected_fids: Set[int]

    # date
    date_enabled: bool
    date_field: Optional[str]
    date_start: date
    date_end: date

    # categories
    # concept_key -> selected raw codes (as strings)
    category_codes: Dict[str, Set[str]]
    # concept_key -> layer field name
    field_map: Dict[str, str]

    def has_any_intent(self, default_date_start: date, default_date_end: date) -> bool:
        cats = any(bool(v) for v in self.category_codes.values())
        date_intent = self.date_enabled and (self.date_start != default_date_start or self.date_end != default_date_end)
        return cats or date_intent

class FilterEngine:
    """Pure-Python filtering to avoid QgsFeatureRequest filter-type collisions."""

    def __init__(self, layer: QgsVectorLayer):
        self.layer = layer

    def _is_numeric_field(self, field_name: str) -> bool:
        try:
            fld = self.layer.fields().field(field_name)
            return bool(fld and fld.isNumeric())
        except Exception:
            return False

    def iter_candidates(self, spec: FilterSpec, needed_fields: List[str]) -> Iterable[Tuple[int, Dict[str, Any]]]:
        req = QgsFeatureRequest()
        req.setSubsetOfAttributes(needed_fields, self.layer.fields())

        # Candidate scope: selection fids if present
        if spec.selection_only and spec.selected_fids:
            req.setFilterFids(list(spec.selected_fids))

        for f in self.layer.getFeatures(req):
            attrs = {name: f[name] for name in needed_fields}
            yield f.id(), attrs

    def _match_category(self, field_name: str, value: Any, selected: Set[str]) -> bool:
        # No filter -> pass
        if not selected:
            return True

        if value is None:
            return False

        # numeric fields: allow numeric equality
        if self._is_numeric_field(field_name):
            fv = try_float(value)
            if fv is None:
                return False
            # normalize selected numeric set once per call
            sel_num = set()
            sel_str = set()
            for s in selected:
                sel_str.add(s.strip())
                f = try_float(s)
                if f is not None:
                    sel_num.add(f)
            if fv in sel_num:
                return True
            # last chance: compare stable strings (e.g., 1.0 <-> '1')
            fvs = numeric_str(fv)
            return (fvs in sel_str) or (str(fv) in sel_str)

        # string-ish fields: match trimmed string
        sv = str(value).strip()
        return sv in {s.strip() for s in selected}

    def _match_date(self, spec: FilterSpec, attrs: Dict[str, Any]) -> bool:
        if not spec.date_enabled:
            return True
        if not spec.date_field:
            return True
        raw = attrs.get(spec.date_field)
        dt = to_datetime(raw)
        if dt is None:
            return False
        start_dt, end_dt = clamp_date_range(spec.date_start, spec.date_end)
        return start_dt <= dt <= end_dt

    def passes(self, spec: FilterSpec, attrs: Dict[str, Any]) -> bool:
        if not self._match_date(spec, attrs):
            return False
        for concept_key, selected_codes in spec.category_codes.items():
            if not selected_codes:
                continue
            field_name = spec.field_map.get(concept_key)
            if not field_name:
                continue
            if not self._match_category(field_name, attrs.get(field_name), selected_codes):
                return False
        return True

    def apply(self, spec: FilterSpec, needed_fields: List[str]) -> Tuple[List[int], List[Dict[str, Any]]]:
        fids: List[int] = []
        rows: List[Dict[str, Any]] = []
        for fid, attrs in self.iter_candidates(spec, needed_fields):
            if self.passes(spec, attrs):
                fids.append(fid)
                rows.append(attrs)
        return fids, rows
