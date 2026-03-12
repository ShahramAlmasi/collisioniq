from __future__ import annotations

from datetime import date

from collision_analytics.core.filters import FilterEngine, FilterSpec


def test_filter_engine_matches_numeric_categories(fake_layer):
    spec = FilterSpec(
        selection_only=False,
        selected_fids=set(),
        date_enabled=False,
        date_field="report_date",
        date_start=date(2024, 1, 1),
        date_end=date(2024, 12, 31),
        category_codes={"veh_cnt": {"2"}},
        field_map={"veh_cnt": "involved_vehicles_cnt"},
    )
    engine = FilterEngine(fake_layer)
    fids, rows = engine.apply(spec, ["involved_vehicles_cnt"])
    assert fids == [1]
    assert rows == [{"involved_vehicles_cnt": 2}]


def test_filter_engine_date_range_is_inclusive(fake_layer):
    spec = FilterSpec(
        selection_only=False,
        selected_fids=set(),
        date_enabled=True,
        date_field="report_date",
        date_start=date(2024, 1, 10),
        date_end=date(2024, 1, 10),
        category_codes={},
        field_map={},
    )
    engine = FilterEngine(fake_layer)
    fids, _rows = engine.apply(spec, ["report_date"])
    assert fids == [1]
