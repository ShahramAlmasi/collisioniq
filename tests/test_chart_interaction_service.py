from __future__ import annotations

from collision_analytics.services.chart_interaction_service import (
    compute_updated_selection,
    normalize_label_for_match,
    resolve_codes_from_label,
)


def test_normalize_label_for_match_strips_counts():
    assert normalize_label_for_match("Rear end (12)") == "Rear end"


def test_resolve_codes_from_label_supports_unknown_blank():
    resolved = resolve_codes_from_label("Unknown / blank", {"1": "Fatal"})
    assert resolved == [""]


def test_compute_updated_selection_replaces_or_adds_matches():
    updated, changed = compute_updated_selection({"1"}, {"1", "2"}, {"2"}, additive=False)
    assert changed is True
    assert updated == {"2"}

    updated, changed = compute_updated_selection({"1"}, {"1", "2"}, {"2"}, additive=True)
    assert changed is True
    assert updated == {"1", "2"}
