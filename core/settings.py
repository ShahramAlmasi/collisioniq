from __future__ import annotations

import json
from typing import Any, Dict

try:
    from qgis.PyQt.QtCore import QSettings
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    QSettings = None

def load_json(settings, key: str, default: Any) -> Any:
    if settings is None:
        return default
    raw = settings.value(key, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

def save_json(settings, key: str, value: Any) -> None:
    if settings is None:
        return
    try:
        settings.setValue(key, json.dumps(value, ensure_ascii=False))
    except Exception:
        # Don't crash the plugin for a settings write failure.
        pass
