from __future__ import annotations

from collision_analytics.core.config import DEFAULT_FIELD_MAP, FILTER_CONCEPTS
from collision_analytics.services.filter_value_service import build_filter_options, count_codes


def test_build_filter_options_uses_decode_values_and_preserves_checks(fake_layer):
    options, warning = build_filter_options(
        layer=fake_layer,
        field_map=DEFAULT_FIELD_MAP,
        concept_titles=FILTER_CONCEPTS,
        source="decodes",
        checked_codes={"impact_type": {"3"}},
        rows=[{"impact_type": "3"}],
        decode_mapping=lambda key: {"3": "Rear end"} if key == "impact_type" else {},
        decode_value=lambda key, value: {"impact_type": {"3": "Rear end"}}.get(key, {}).get(value, str(value)),
    )

    assert warning is None
    assert options["impact_type"].checked == {"3"}
    assert options["impact_type"].items == [("3", "Rear end (1)")]


def test_build_filter_options_warns_when_selection_source_has_no_selection(fake_layer):
    fake_layer._selected_fids = []
    options, warning = build_filter_options(
        layer=fake_layer,
        field_map=DEFAULT_FIELD_MAP,
        concept_titles=FILTER_CONCEPTS[:1],
        source="selection",
        checked_codes={},
        rows=[],
        decode_mapping=lambda _key: {},
        decode_value=lambda _key, value: str(value),
    )

    assert warning == "No selected features in map."
    assert "municipality" in options


def test_count_codes_ignores_blank_values():
    counts = count_codes(
        [
            {"impact_type": "3"},
            {"impact_type": ""},
            {"impact_type": None},
            {"impact_type": "3"},
        ],
        "impact_type",
    )

    assert counts == {"3": 2}
