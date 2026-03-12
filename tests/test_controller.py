from __future__ import annotations

from datetime import date

from collision_analytics.controllers import dock_controller
from collision_analytics.core.config import DEFAULT_FIELD_MAP
from collision_analytics.services import FilterPanelState, default_last_full_10y_range


class FakeDecodes:
    def __init__(self) -> None:
        self._mapping = {
            "accident_class": {"1": "Fatal", "2": "Injury"},
            "impact_type": {"3": "Rear end", "5": "Turning movement"},
            "municipality": {"OA": "Oshawa", "AJ": "Ajax"},
        }

    def decode(self, concept_key, raw):
        code = "" if raw is None else str(raw).strip()
        if code == "":
            return "Unknown / blank"
        return self._mapping.get(concept_key, {}).get(code, code)

    def mapping(self, concept_key):
        return dict(self._mapping.get(concept_key, {}))

    def keys(self):
        return sorted(self._mapping.keys())


class FakeView:
    def __init__(self, layer, state: FilterPanelState) -> None:
        self._layer = layer
        self.state = state
        self.status = None
        self.snapshot = None
        self.chart_refreshes = []
        self.no_data_calls = 0
        self.info_messages = []
        self.warning_messages = []
        self.filter_options = {}
        self.filter_labels = {}
        self.settings_opened = 0
        self.selected_codes = {key: set(values) for key, values in state.selected_codes.items()}
        self.available_pairs = {
            "impact_type": [("3", "Rear end (0)"), ("5", "Turning movement (0)")],
            "municipality": [("OA", "Oshawa (0)"), ("AJ", "Ajax (0)")],
            "accident_class": [("1", "Fatal (0)"), ("2", "Injury (0)")],
        }

    def current_layer(self):
        return self._layer

    def read_filter_panel_state(self):
        return FilterPanelState(
            use_date=self.state.use_date,
            date_start=self.state.date_start,
            date_end=self.state.date_end,
            selection_only=self.state.selection_only,
            select_filtered=self.state.select_filtered,
            selected_codes={key: set(values) for key, values in self.selected_codes.items()},
        )

    def default_filter_dates(self):
        return default_last_full_10y_range()

    def checked_codes(self):
        return {key: set(values) for key, values in self.selected_codes.items()}

    def selected_codes_for(self, concept_key):
        return set(self.selected_codes.get(concept_key, set()))

    def apply_filter_options(self, options):
        self.filter_options = options
        for concept_key, option in options.items():
            self.available_pairs[concept_key] = list(option.items)
            self.selected_codes.setdefault(concept_key, set(option.checked))

    def filter_item_pairs(self, concept_key):
        return list(self.available_pairs.get(concept_key, []))

    def filter_item_codes(self, concept_key):
        return [code for code, _label in self.available_pairs.get(concept_key, [])]

    def set_selected_codes(self, concept_key, selected_codes):
        self.selected_codes[concept_key] = set(selected_codes)

    def set_filter_item_labels(self, concept_key, labels):
        self.filter_labels[concept_key] = labels

    def reset_filter_controls(self, start_date, end_date):
        self.selected_codes = {}
        self.state = FilterPanelState(
            use_date=True,
            date_start=start_date,
            date_end=end_date,
            selection_only=True,
            select_filtered=False,
            selected_codes={},
        )

    def set_status(self, text):
        self.status = text

    def apply_dashboard_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.status = snapshot.status_text

    def show_no_data(self):
        self.no_data_calls += 1

    def refresh_charts(self, rows, field_map, decodes):
        self.chart_refreshes.append((rows, dict(field_map), decodes))

    def show_info(self, title, message):
        self.info_messages.append((title, message))

    def show_warning(self, title, message):
        self.warning_messages.append((title, message))

    def prompt_save_file(self, _title, _file_filter):
        return ""

    def chart_cards(self):
        return []

    def chart_figure_factory(self):
        return None

    def show_settings_dialog(self):
        self.settings_opened += 1


def build_state(**overrides):
    default_start, default_end = default_last_full_10y_range()
    values = {
        "use_date": True,
        "date_start": default_start,
        "date_end": default_end,
        "selection_only": False,
        "select_filtered": False,
        "selected_codes": {},
    }
    values.update(overrides)
    return FilterPanelState(**values)


def test_controller_sync_filtering_updates_snapshot(fake_layer):
    view = FakeView(fake_layer, build_state())
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    controller.field_map = dict(DEFAULT_FIELD_MAP)
    controller.on_layer_changed(fake_layer)
    controller.apply_filters()

    assert controller.filtered_fids == [1, 2]
    assert view.snapshot.total_value == "2"
    assert view.chart_refreshes


def test_controller_selection_only_without_selection_stays_idle(fake_layer):
    fake_layer._selected_fids = []
    view = FakeView(fake_layer, build_state(selection_only=True))
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    controller.field_map = dict(DEFAULT_FIELD_MAP)
    controller.on_layer_changed(fake_layer)
    controller.apply_filters()

    assert controller.filtered_fids == []
    assert view.snapshot.total_value == "-"
    assert view.no_data_calls >= 1


def test_controller_select_filtered_updates_layer_selection(fake_layer):
    view = FakeView(fake_layer, build_state(select_filtered=True))
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    controller.field_map = dict(DEFAULT_FIELD_MAP)
    controller.on_layer_changed(fake_layer)
    controller.apply_filters()

    assert fake_layer.selected_by_ids == [1, 2]


def test_controller_background_tasks_cancel_and_ignore_stale_results(fake_layer, monkeypatch):
    view = FakeView(fake_layer, build_state())
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    controller.field_map = dict(DEFAULT_FIELD_MAP)
    monkeypatch.setattr(dock_controller, "BACKGROUND_FILTER_THRESHOLD", 1)

    controller.on_layer_changed(fake_layer)
    controller.apply_filters()
    first_task = controller._active_filter_task
    assert first_task is not None

    view.selected_codes["impact_type"] = {"3"}
    controller.apply_filters()
    second_task = controller._active_filter_task

    assert first_task.isCanceled() is True
    assert second_task is not first_task

    first_task.filtered_fids = [1]
    first_task.filtered_rows = [{"impact_type": "3"}]
    controller._on_filter_complete(first_task)
    assert controller.filtered_fids == []

    second_task.filtered_fids = [1]
    second_task.filtered_rows = [{"impact_type": "3", "accident_class": "1"}]
    controller._on_filter_complete(second_task)
    assert controller.filtered_fids == [1]


def test_controller_rewires_layer_selection_signal(fake_layer):
    view = FakeView(fake_layer, build_state(selection_only=True))
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    controller.on_layer_changed(fake_layer)
    assert controller._signal_layer is fake_layer

    fake_layer._selected_fids = []
    controller.on_layer_selection_changed()
    assert view.snapshot.total_value == "-"


def test_controller_filter_by_category_updates_selection_and_reapplies(fake_layer):
    view = FakeView(fake_layer, build_state())
    controller = dock_controller.DockController(view, iface=None, settings=None, decodes=FakeDecodes())
    calls = []
    controller.apply_filters = lambda: calls.append("apply")
    controller.filter_by_category("impact_type", "Rear end (12)", additive=False)

    assert view.selected_codes["impact_type"] == {"3"}
    assert calls == ["apply"]
