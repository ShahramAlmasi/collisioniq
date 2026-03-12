from __future__ import annotations

from datetime import date, datetime

from collision_analytics.core.config import DEFAULT_FIELD_MAP
from collision_analytics.services.export_service import (
    build_feature_export_table,
    build_summary_export_rows,
    format_export_value,
    render_dashboard_png,
)


def test_format_export_value_handles_dates():
    assert format_export_value(date(2024, 1, 1)) == "2024-01-01"
    assert format_export_value(datetime(2024, 1, 1, 2, 3, 4)) == "2024-01-01 02:03:04"


def test_build_summary_export_rows_returns_expected_metrics():
    rows = build_summary_export_rows(
        [
            {"accident_class": "1", "involved_vehicles_cnt": 2},
            {"accident_class": "2", "involved_vehicles_cnt": 1},
        ],
        DEFAULT_FIELD_MAP,
        lambda raw: {"1": "Fatal", "2": "Injury"}.get(raw, "Unknown"),
        selection_only=True,
    )
    metrics = dict(rows)
    assert metrics["filtered_collisions"] == 2
    assert metrics["fatal_collisions"] == 1
    assert metrics["scope"] == "selection"


def test_build_feature_export_table_adds_decoded_columns():
    table = build_feature_export_table(
        [{"report_date": "2024-01-01", "accident_class": "1"}],
        DEFAULT_FIELD_MAP,
        {"accident_class"},
        lambda key, raw: "Fatal" if key == "accident_class" and raw == "1" else str(raw),
    )
    assert table.headers == ["accident_class", "accident_class_decoded", "report_date"]
    assert table.rows == [["1", "Fatal", "2024-01-01"]]


def test_render_dashboard_png_falls_back_when_chart_render_fails(tmp_path):
    events = []

    class FakeAxis:
        def __init__(self) -> None:
            self.transAxes = object()

        def set_title(self, title, fontsize=None):
            events.append(("title", title, fontsize))

        def text(self, *_args, **_kwargs):
            events.append("text")

        def set_axis_off(self):
            events.append("axis_off")

    class FakeFigure:
        def add_subplot(self, *_args):
            return FakeAxis()

        def tight_layout(self):
            events.append("tight_layout")

        def savefig(self, path, dpi=None):
            events.append(("savefig", path, dpi))

    class FakeCard:
        title = "Broken"

        @staticmethod
        def render_fn(_ax, _card):
            raise RuntimeError("boom")

    render_dashboard_png(str(tmp_path / "dashboard.png"), [FakeCard()], lambda **_kwargs: FakeFigure())
    assert "text" in events
    assert "axis_off" in events
