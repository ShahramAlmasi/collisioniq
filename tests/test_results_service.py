from __future__ import annotations

from collision_analytics.core.config import DEFAULT_FIELD_MAP
from collision_analytics.services.results_service import build_dashboard_snapshot, build_idle_snapshot


def test_build_idle_snapshot_uses_placeholder_values():
    snapshot = build_idle_snapshot()
    assert snapshot.total_value == "-"
    assert snapshot.fatal_value == "-"


def test_build_dashboard_snapshot_formats_kpis():
    snapshot = build_dashboard_snapshot(
        [
            {"accident_class": "1"},
            {"accident_class": "2"},
        ],
        5,
        DEFAULT_FIELD_MAP,
        lambda raw: {"1": "Fatal", "2": "Injury"}.get(raw, "Unknown"),
    )

    assert snapshot.total_value == "2"
    assert snapshot.fatal_value == "1"
    assert snapshot.severe_value == "100.0%"
    assert snapshot.status_text == "Matched 2 of 5 features."
