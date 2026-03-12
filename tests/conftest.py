from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

ROOT_PARENT = Path(__file__).resolve().parents[2]
if str(ROOT_PARENT) not in sys.path:
    sys.path.insert(0, str(ROOT_PARENT))

HAS_REAL_QGIS = importlib.util.find_spec("qgis") is not None


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback) -> None:
        self._callbacks = [current for current in self._callbacks if current != callback]

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FakeTaskManager:
    def __init__(self) -> None:
        self.added_tasks = []

    def addTask(self, task) -> None:
        self.added_tasks.append(task)


TASK_MANAGER = FakeTaskManager()


def install_qgis_stubs() -> None:
    qgis_mod = types.ModuleType("qgis")
    qgis_mod.__path__ = []

    pyqt_mod = types.ModuleType("qgis.PyQt")
    qtcore_mod = types.ModuleType("qgis.PyQt.QtCore")
    qtwidgets_mod = types.ModuleType("qgis.PyQt.QtWidgets")
    qtgui_mod = types.ModuleType("qgis.PyQt.QtGui")
    core_mod = types.ModuleType("qgis.core")
    gui_mod = types.ModuleType("qgis.gui")

    class Qt:
        Checked = 2
        Unchecked = 0
        UserRole = 32
        ControlModifier = 0x04000000
        ScrollBarAlwaysOff = 1
        Horizontal = 1
        LeftDockWidgetArea = 1
        RightDockWidgetArea = 2

    class QTimer:
        @staticmethod
        def singleShot(_ms, callback):
            callback()

    class QDate:
        def __init__(self, year: int, month: int, day: int) -> None:
            self._date = date(year, month, day)

        @classmethod
        def currentDate(cls):
            today = date.today()
            return cls(today.year, today.month, today.day)

        def year(self) -> int:
            return self._date.year

        def month(self) -> int:
            return self._date.month

        def day(self) -> int:
            return self._date.day

    class QSettings:
        def __init__(self) -> None:
            self._values = {}

        def value(self, key, default=""):
            return self._values.get(key, default)

        def setValue(self, key, value) -> None:
            self._values[key] = value

    class QIcon:
        pass

    class DummyWidget:
        def __init__(self, *args, **kwargs) -> None:
            self._layout = None

        def setLayout(self, layout) -> None:
            self._layout = layout

        def layout(self):
            return self._layout

        def setWidget(self, _widget) -> None:
            pass

        def setObjectName(self, _name) -> None:
            pass

        def setStyleSheet(self, _style) -> None:
            pass

        def setMinimumSize(self, *_args) -> None:
            pass

        def setMinimumWidth(self, *_args) -> None:
            pass

        def setMaximumWidth(self, *_args) -> None:
            pass

        def show(self) -> None:
            pass

        def raise_(self) -> None:
            pass

        def close(self) -> None:
            pass

        def setParent(self, *_args) -> None:
            pass

        def deleteLater(self) -> None:
            pass

    class Layout:
        def addWidget(self, *_args) -> None:
            pass

        def addLayout(self, *_args) -> None:
            pass

        def addStretch(self, *_args) -> None:
            pass

        def addSpacing(self, *_args) -> None:
            pass

        def setContentsMargins(self, *_args) -> None:
            pass

        def setSpacing(self, *_args) -> None:
            pass

    for name in [
        "QWidget",
        "QDockWidget",
        "QDialog",
        "QCheckBox",
        "QDateEdit",
        "QPushButton",
        "QLabel",
        "QTabWidget",
        "QFrame",
        "QScrollArea",
        "QSplitter",
        "QGroupBox",
        "QListWidget",
        "QLineEdit",
        "QTableWidget",
        "QTableWidgetItem",
        "QComboBox",
        "QHeaderView",
        "QFileDialog",
    ]:
        setattr(qtwidgets_mod, name, type(name, (DummyWidget,), {}))

    for name in ["QVBoxLayout", "QHBoxLayout", "QGridLayout", "QFormLayout"]:
        setattr(qtwidgets_mod, name, type(name, (Layout,), {}))

    class QAction(DummyWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.triggered = FakeSignal()

        def setCheckable(self, *_args) -> None:
            pass

        def blockSignals(self, *_args) -> None:
            pass

        def setChecked(self, *_args) -> None:
            pass

    class QgsTask:
        CanCancel = 1

        def __init__(self, *_args, **_kwargs) -> None:
            self.taskCompleted = FakeSignal()
            self.taskTerminated = FakeSignal()
            self._canceled = False

        def cancel(self) -> None:
            self._canceled = True

        def isCanceled(self) -> bool:
            return self._canceled

    class Qgis:
        Critical = "critical"
        Warning = "warning"

    class QgsApplication:
        @staticmethod
        def taskManager():
            return TASK_MANAGER

    class QgsFeatureRequest:
        def __init__(self) -> None:
            self.filter_fids = None
            self.subset_attributes = None

        def setFilterFids(self, fids):
            self.filter_fids = list(fids)
            return self

        def setSubsetOfAttributes(self, attributes, _fields):
            self.subset_attributes = list(attributes)
            return self

    class QgsMessageLog:
        last = None

        @classmethod
        def logMessage(cls, message, *_args) -> None:
            cls.last = message

    class QgsMapLayerProxyModel:
        PointLayer = 1

    class QgsMapLayerComboBox(DummyWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.layerChanged = FakeSignal()
            self._layer = None

        def setFilters(self, *_args) -> None:
            pass

        def currentLayer(self):
            return self._layer

        def setCurrentLayer(self, layer) -> None:
            self._layer = layer
            self.layerChanged.emit(layer)

    qtcore_mod.Qt = Qt
    qtcore_mod.QTimer = QTimer
    qtcore_mod.QDate = QDate
    qtcore_mod.QSettings = QSettings
    qtgui_mod.QIcon = QIcon
    qtwidgets_mod.QAction = QAction

    core_mod.QgsTask = QgsTask
    core_mod.Qgis = Qgis
    core_mod.QgsApplication = QgsApplication
    core_mod.QgsFeatureRequest = QgsFeatureRequest
    core_mod.QgsMessageLog = QgsMessageLog
    core_mod.QgsMapLayerProxyModel = QgsMapLayerProxyModel
    core_mod.QgsVectorLayer = object

    gui_mod.QgsMapLayerComboBox = QgsMapLayerComboBox

    sys.modules["qgis"] = qgis_mod
    sys.modules["qgis.PyQt"] = pyqt_mod
    sys.modules["qgis.PyQt.QtCore"] = qtcore_mod
    sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets_mod
    sys.modules["qgis.PyQt.QtGui"] = qtgui_mod
    sys.modules["qgis.core"] = core_mod
    sys.modules["qgis.gui"] = gui_mod


if not HAS_REAL_QGIS:
    install_qgis_stubs()


def pytest_collection_modifyitems(config, items):
    if HAS_REAL_QGIS:
        return
    skip_marker = pytest.mark.skip(reason="requires a real QGIS runtime")
    for item in items:
        if "qgis_integration" in item.keywords:
            item.add_marker(skip_marker)


@dataclass
class FakeField:
    field_name: str
    numeric: bool = False

    def name(self) -> str:
        return self.field_name

    def isNumeric(self) -> bool:
        return self.numeric


class FakeFields:
    def __init__(self, fields) -> None:
        self._fields = list(fields)

    def __iter__(self):
        return iter(self._fields)

    def field(self, name: str):
        for field in self._fields:
            if field.name() == name:
                return field
        return None

    def indexOf(self, name: str) -> int:
        for index, field in enumerate(self._fields):
            if field.name() == name:
                return index
        return -1


class FakeFeature:
    def __init__(self, fid: int, attrs) -> None:
        self._fid = fid
        self._attrs = dict(attrs)

    def id(self) -> int:
        return self._fid

    def __getitem__(self, key):
        return self._attrs.get(key)


class FakeLayer:
    def __init__(self, fields, rows, *, selected_fids=None) -> None:
        self._fields = FakeFields(fields)
        self._rows = [FakeFeature(index + 1, row) for index, row in enumerate(rows)]
        self._selected_fids = list(selected_fids or [])
        self.selectionChanged = FakeSignal()
        self.selected_by_ids = None

    def fields(self):
        return self._fields

    def selectedFeatureIds(self):
        return list(self._selected_fids)

    def selectedFeatureCount(self) -> int:
        return len(self._selected_fids)

    def featureCount(self) -> int:
        return len(self._rows)

    def selectByIds(self, fids) -> None:
        self.selected_by_ids = list(fids)

    def uniqueValues(self, index: int, limit: int):
        name = list(self._fields)[index].name()
        values = []
        seen = set()
        for feature in self._rows:
            value = feature[name]
            if value in seen:
                continue
            seen.add(value)
            values.append(value)
            if len(values) >= limit:
                break
        return values

    def getFeatures(self, request=None):
        rows = self._rows
        if request is not None and getattr(request, "filter_fids", None):
            allowed = set(request.filter_fids)
            rows = [feature for feature in rows if feature.id() in allowed]
        if request is not None and getattr(request, "subset_attributes", None):
            subset = list(request.subset_attributes)
            rows = [
                FakeFeature(feature.id(), {key: feature[key] for key in subset})
                for feature in rows
            ]
        return rows


class FakeSettings:
    def __init__(self) -> None:
        self.values = {}

    def value(self, key, default=""):
        return self.values.get(key, default)

    def setValue(self, key, value) -> None:
        self.values[key] = value


@pytest.fixture(autouse=True)
def reset_task_manager():
    TASK_MANAGER.added_tasks.clear()
    yield
    TASK_MANAGER.added_tasks.clear()


@pytest.fixture
def fake_layer():
    return FakeLayer(
        [
            FakeField("report_date"),
            FakeField("accident_class"),
            FakeField("impact_type"),
            FakeField("municipality"),
            FakeField("involved_vehicles_cnt", numeric=True),
        ],
        [
            {
                "report_date": "2024-01-10",
                "accident_class": "1",
                "impact_type": "3",
                "municipality": "OA",
                "involved_vehicles_cnt": 2,
            },
            {
                "report_date": "2024-02-11",
                "accident_class": "2",
                "impact_type": "5",
                "municipality": "AJ",
                "involved_vehicles_cnt": 1,
            },
        ],
        selected_fids=[1],
    )
