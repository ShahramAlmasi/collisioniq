from __future__ import annotations

import csv
from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QTimer
from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask

from ..core.config import DEFAULT_FIELD_MAP, FILTER_CONCEPTS, SETTINGS_FIELD_MAP_KEY
from ..core.decodes import DecodeRegistry
from ..core.filters import FilterEngine
from ..core.settings import load_json, save_json
from ..services import (
    build_dashboard_snapshot,
    build_execution_plan,
    build_feature_export_table,
    build_filter_options,
    build_idle_snapshot,
    build_summary_export_rows,
    compute_updated_selection,
    count_codes,
    render_dashboard_png,
    resolve_codes_from_label,
)

BACKGROUND_FILTER_THRESHOLD = 50000


class FilterTask(QgsTask):
    """Background task for filtering large datasets."""

    def __init__(self, layer, spec, needed_fields: List[str], request_id: int, filter_engine_factory=FilterEngine):
        super().__init__("Collision Analytics filtering", QgsTask.CanCancel)
        self.layer = layer
        self.spec = spec
        self.needed_fields = needed_fields
        self.request_id = request_id
        self.filter_engine_factory = filter_engine_factory
        self.feature_count = 0
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self.exception: Optional[Exception] = None

    def run(self) -> bool:
        try:
            engine = self.filter_engine_factory(self.layer)
            self.filtered_fids, self.filtered_rows = engine.apply(self.spec, self.needed_fields)
            return True
        except Exception as exc:
            self.exception = exc
            return False


class DockController:
    def __init__(
        self,
        view,
        iface,
        settings,
        decodes: DecodeRegistry,
        filter_engine_factory=FilterEngine,
    ) -> None:
        self.view = view
        self.iface = iface
        self.settings = settings
        self.decodes = decodes
        self.filter_engine_factory = filter_engine_factory

        self.field_map: Dict[str, str] = dict(DEFAULT_FIELD_MAP)
        self.filtered_fids: List[int] = []
        self.filtered_rows: List[Dict[str, Any]] = []
        self.layer = None

        self._active_filter_task: Optional[FilterTask] = None
        self._filter_request_id = 0
        self._signal_layer = None

    def initialize(self) -> None:
        self.load_field_map()
        self.on_layer_changed(self.view.current_layer())

    def close(self) -> None:
        self.cancel_active_filter_task()
        self._disconnect_layer_signals()

    def load_field_map(self) -> None:
        obj = load_json(self.settings, SETTINGS_FIELD_MAP_KEY, None)
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.field_map[str(key)] = str(value)

    def save_field_map(self) -> None:
        save_json(self.settings, SETTINGS_FIELD_MAP_KEY, self.field_map)

    def on_layer_changed(self, layer) -> None:
        self._disconnect_layer_signals()
        self.layer = layer
        self._connect_layer_signals(layer)
        self.refresh_from_layer()

    def refresh_from_layer(self) -> None:
        if self.layer is None:
            self.filtered_fids = []
            self.filtered_rows = []
            self.view.apply_dashboard_snapshot(build_idle_snapshot())
            self.view.show_no_data()
            return

        source = "selection" if self.view.read_filter_panel_state().selection_only and self.layer.selectedFeatureCount() > 0 else "decodes"
        self.populate_filter_values(source)

        if self.view.read_filter_panel_state().selection_only and self.layer.selectedFeatureCount() > 0:
            self.apply_filters()
            return

        self.filtered_fids = []
        self.filtered_rows = []
        snapshot = build_idle_snapshot()
        self.view.apply_dashboard_snapshot(snapshot)
        self.view.show_no_data()

    def apply_filters(self) -> None:
        if self.layer is None:
            return

        self._filter_request_id += 1
        request_id = self._filter_request_id
        self.cancel_active_filter_task()

        state = self.view.read_filter_panel_state()
        plan = build_execution_plan(
            self.layer,
            self.field_map,
            state,
            background_threshold=BACKGROUND_FILTER_THRESHOLD,
        )

        if plan.mode == "idle":
            self.filtered_fids = []
            self.filtered_rows = []
            self.refresh_filter_counts()
            self.view.apply_dashboard_snapshot(build_idle_snapshot(plan.status_text))
            self.view.show_no_data()
            return

        if (
            plan.spec.selection_only
            and not plan.spec.selected_fids
            and plan.spec.has_any_intent(*self.view.default_filter_dates())
        ):
            self.view.show_info(
                "Collision Analytics",
                "No map selection, but filters are set.\n\nRunning analysis on the whole layer for the active filters.",
            )

        feature_count = self.layer.featureCount()
        if plan.mode == "background":
            task = FilterTask(
                self.layer,
                plan.spec,
                plan.needed_fields,
                request_id=request_id,
                filter_engine_factory=self.filter_engine_factory,
            )
            task.feature_count = feature_count
            task.taskCompleted.connect(lambda _result=None, current=task: self._on_filter_complete(current))
            task.taskTerminated.connect(lambda *_, current=task: self._on_filter_failed(current))
            self._active_filter_task = task
            self.view.set_status(plan.status_text)
            QgsApplication.taskManager().addTask(task)
            return

        engine = self.filter_engine_factory(self.layer)
        filtered_fids, filtered_rows = engine.apply(plan.spec, plan.needed_fields)
        self._apply_filter_results(filtered_fids, filtered_rows, feature_count, request_id=request_id)

    def reset_all_filters(self) -> None:
        self.view.reset_filter_controls(*self.view.default_filter_dates())
        self.filtered_fids = []
        self.filtered_rows = []
        self.view.apply_dashboard_snapshot(build_idle_snapshot())
        self.view.show_no_data()
        self.apply_filters()

    def on_filter_changed(self) -> None:
        if self.layer is None:
            return
        state = self.view.read_filter_panel_state()
        if state.selection_only and self.layer.selectedFeatureCount() > 0:
            QTimer.singleShot(150, self.apply_filters)

    def on_layer_selection_changed(self, *_) -> None:
        if self.layer is None or not self.view.read_filter_panel_state().selection_only:
            return

        if self.layer.selectedFeatureCount() > 0:
            self.populate_filter_values("selection")
            QTimer.singleShot(50, self.apply_filters)
            return

        self.populate_filter_values("decodes")
        self.filtered_fids = []
        self.filtered_rows = []
        self.refresh_filter_counts()
        self.view.apply_dashboard_snapshot(build_idle_snapshot())
        self.view.show_no_data()

    def populate_filter_values(self, source: str) -> None:
        options, warning = build_filter_options(
            layer=self.layer,
            field_map=self.field_map,
            concept_titles=FILTER_CONCEPTS,
            source=source,
            checked_codes=self.view.checked_codes(),
            rows=self.filtered_rows,
            decode_mapping=self.decodes.mapping,
            decode_value=self.decodes.decode,
        )
        self.view.apply_filter_options(options)
        self.refresh_filter_counts()
        if warning:
            self.view.show_info("Collision Analytics", warning)

    def refresh_filter_counts(self) -> None:
        for concept_key, _title in FILTER_CONCEPTS:
            field_name = self.field_map.get(concept_key)
            counts = count_codes(self.filtered_rows, field_name)
            labels = {
                code: f"{self.decodes.decode(concept_key, code)} ({counts.get(code, 0)})"
                for code in self.view.filter_item_codes(concept_key)
            }
            self.view.set_filter_item_labels(concept_key, labels)

    def filter_by_category(self, concept_key: str, label: str, additive: bool) -> None:
        resolved_codes = resolve_codes_from_label(
            label,
            self.decodes.mapping(concept_key),
            self.view.filter_item_pairs(concept_key),
        )
        updated, changed = compute_updated_selection(
            self.view.selected_codes_for(concept_key),
            self.view.filter_item_codes(concept_key),
            resolved_codes,
            additive,
        )
        if not changed:
            return
        self.view.set_selected_codes(concept_key, updated)
        QTimer.singleShot(50, self.apply_filters)

    def export_summary_csv(self) -> None:
        if not self.filtered_rows:
            self.view.show_info("Collision Analytics", "No filtered results to export.")
            return

        path = self.view.prompt_save_file("Export summary CSV", "CSV (*.csv)")
        if not path:
            return

        rows = build_summary_export_rows(
            self.filtered_rows,
            self.field_map,
            lambda raw: self.decodes.decode("accident_class", raw),
            selection_only=self.view.read_filter_panel_state().selection_only,
        )
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            writer.writerows(rows)
        self.view.show_info("Collision Analytics", f"Saved:\n{path}")

    def export_filtered_features_csv(self) -> None:
        if not self.filtered_rows:
            self.view.show_info("Collision Analytics", "No filtered results to export.")
            return

        path = self.view.prompt_save_file("Export filtered features CSV", "CSV (*.csv)")
        if not path:
            return

        table = build_feature_export_table(
            self.filtered_rows,
            self.field_map,
            self.decodes.keys(),
            self.decodes.decode,
        )
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(table.headers)
                writer.writerows(table.rows)
            self.view.show_info(
                "Collision Analytics",
                f"Exported {len(table.rows)} features to:\n{path}",
            )
        except Exception as exc:
            self.view.show_warning("Collision Analytics", f"Export failed:\n{exc}")

    def export_dashboard_png(self) -> None:
        figure_factory = self.view.chart_figure_factory()
        if figure_factory is None:
            self.view.show_warning(
                "Collision Analytics",
                "Charts are not available (matplotlib missing).",
            )
            return

        cards = self.view.chart_cards()
        if not cards:
            self.view.show_info("Collision Analytics", "No charts to export.")
            return

        path = self.view.prompt_save_file("Export dashboard PNG", "PNG (*.png)")
        if not path:
            return

        render_dashboard_png(path, cards, figure_factory)
        self.view.show_info("Collision Analytics", f"Saved:\n{path}")

    def show_settings_dialog(self) -> None:
        self.view.show_settings_dialog()

    def _apply_filter_results(
        self,
        filtered_fids: List[int],
        filtered_rows: List[Dict[str, Any]],
        total_count: int,
        *,
        request_id: Optional[int] = None,
    ) -> None:
        if request_id is not None and request_id != self._filter_request_id:
            return

        self.filtered_fids = filtered_fids
        self.filtered_rows = filtered_rows

        if self.view.read_filter_panel_state().select_filtered and self.layer is not None:
            self.layer.selectByIds(filtered_fids)

        self.refresh_filter_counts()
        snapshot = build_dashboard_snapshot(
            filtered_rows,
            total_count,
            self.field_map,
            lambda raw: self.decodes.decode("accident_class", raw),
        )
        self.view.apply_dashboard_snapshot(snapshot)
        self.view.refresh_charts(filtered_rows, self.field_map, self.decodes)

    def _on_filter_complete(self, task: FilterTask) -> None:
        if self._active_filter_task is task:
            self._active_filter_task = None

        if self.layer is None or task.layer != self.layer:
            self.view.set_status("Layer changed during filtering; results ignored.")
            return

        if task.request_id != self._filter_request_id:
            return

        if task.exception:
            self._on_filter_failed(task)
            return

        self._apply_filter_results(
            task.filtered_fids,
            task.filtered_rows,
            getattr(task, "feature_count", self.layer.featureCount()),
            request_id=task.request_id,
        )

    def _on_filter_failed(self, task: FilterTask) -> None:
        if self._active_filter_task is task:
            self._active_filter_task = None
        if task.request_id != self._filter_request_id:
            return
        if task.isCanceled() and task.exception is None:
            self.view.set_status("Filtering canceled.")
            return
        exc = task.exception or Exception("Filtering task failed.")
        QgsMessageLog.logMessage(str(exc), "Collision Analytics", Qgis.Critical)
        self.view.set_status(f"Filtering failed: {exc}")

    def cancel_active_filter_task(self) -> None:
        if self._active_filter_task is None:
            return
        try:
            self._active_filter_task.cancel()
        except Exception:
            pass

    def _connect_layer_signals(self, layer) -> None:
        if layer is None:
            self._signal_layer = None
            return
        try:
            layer.selectionChanged.connect(self.on_layer_selection_changed)
            self._signal_layer = layer
        except Exception:
            self._signal_layer = None

    def _disconnect_layer_signals(self) -> None:
        if self._signal_layer is None:
            return
        try:
            self._signal_layer.selectionChanged.disconnect(self.on_layer_selection_changed)
        except Exception:
            pass
        self._signal_layer = None
