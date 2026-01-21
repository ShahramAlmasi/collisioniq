from __future__ import annotations

import json
from typing import Any, Dict

from qgis.PyQt.QtCore import QSettings

def load_json(settings: QSettings, key: str, default: Any) -> Any:
    raw = settings.value(key, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

def save_json(settings: QSettings, key: str, value: Any) -> None:
    try:
        settings.setValue(key, json.dumps(value, ensure_ascii=False))
    except Exception:
        # Don't crash the plugin for a settings write failure.
        pass
