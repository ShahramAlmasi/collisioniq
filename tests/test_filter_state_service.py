from __future__ import annotations

from datetime import date

from collision_analytics.core.config import DEFAULT_FIELD_MAP
from collision_analytics.services.filter_state_service import (
    FilterPanelState,
    build_execution_plan,
    collect_needed_fields,
)


def test_build_execution_plan_is_idle_without_selection_or_filter_intent(fake_layer):
    fake_layer._selected_fids = []
    state = FilterPanelState(
        use_date=True,
        date_start=date(2016, 1, 1),
        date_end=date(2025, 12, 31),
        selection_only=True,
        select_filtered=False,
        selected_codes={},
    )

    plan = build_execution_plan(
        fake_layer,
        DEFAULT_FIELD_MAP,
        state,
        background_threshold=999,
        today=date(2026, 3, 11),
    )

    assert plan.mode == "idle"
    assert "Idle:" in plan.status_text


def test_build_execution_plan_uses_background_for_large_layers(fake_layer):
    state = FilterPanelState(
        use_date=True,
        date_start=date(2015, 1, 1),
        date_end=date(2024, 12, 31),
        selection_only=False,
        select_filtered=False,
        selected_codes={"impact_type": {"3"}},
    )

    plan = build_execution_plan(
        fake_layer,
        DEFAULT_FIELD_MAP,
        state,
        background_threshold=1,
        today=date(2026, 3, 11),
    )

    assert plan.mode == "background"
    assert "Filtering 2 features" in plan.status_text


def test_collect_needed_fields_includes_filter_and_display_fields(fake_layer):
    state = FilterPanelState(
        use_date=True,
        date_start=date(2015, 1, 1),
        date_end=date(2024, 12, 31),
        selection_only=False,
        select_filtered=False,
        selected_codes={"impact_type": {"3"}},
    )

    plan = build_execution_plan(
        fake_layer,
        DEFAULT_FIELD_MAP,
        state,
        background_threshold=999,
        today=date(2026, 3, 11),
    )

    needed = collect_needed_fields(fake_layer, plan.spec, DEFAULT_FIELD_MAP)
    assert "report_date" in needed
    assert "impact_type" in needed
    assert "accident_class" in needed
