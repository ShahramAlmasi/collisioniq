from __future__ import annotations

import copy
from typing import Dict

from qgis.PyQt.QtCore import QSettings

from .config import DEFAULT_DECODES, SETTINGS_DECODES_KEY
from .settings import load_json, save_json
from .utils import safe_str, is_blank

class DecodeRegistry:
    """Per-user decode tables (raw code -> friendly label), persisted via QSettings."""

    def __init__(self, settings: QSettings):
        self._settings = settings
        self._decodes: Dict[str, Dict[str, str]] = copy.deepcopy(DEFAULT_DECODES)
        self.load()

    def load(self) -> None:
        obj = load_json(self._settings, SETTINGS_DECODES_KEY, None)
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if isinstance(v, dict):
                self._decodes[str(k)] = {str(code): str(label) for code, label in v.items()}

    def save(self) -> None:
        save_json(self._settings, SETTINGS_DECODES_KEY, self._decodes)

    def reset_to_defaults(self) -> None:
        self._decodes = copy.deepcopy(DEFAULT_DECODES)
        self.save()

    def keys(self):
        return sorted(self._decodes.keys())

    def mapping(self, concept_key: str) -> Dict[str, str]:
        return self._decodes.get(concept_key, {})

    def set_mapping(self, concept_key: str, mapping: Dict[str, str]) -> None:
        self._decodes[concept_key] = {str(k): str(v) for k, v in mapping.items()}

    def _normalize_code(self, raw_value) -> str:
        """Coerce numeric-like values to an int-like string; otherwise return trimmed text."""
        if is_blank(raw_value):
            return ""
        if isinstance(raw_value, int):
            return str(raw_value)
        if isinstance(raw_value, float):
            return str(int(raw_value)) if raw_value.is_integer() else ""
        text = safe_str(raw_value).strip()
        if text == "":
            return ""
        try:
            as_float = float(text)
            if as_float.is_integer():
                return str(int(as_float))
            return ""
        except Exception:
            return text
        return text

    def decode(self, concept_key: str, raw_value) -> str:
        code = self._normalize_code(raw_value)
        if code == "":
            return "Unknown / blank"
        return self.mapping(concept_key).get(code, code)
