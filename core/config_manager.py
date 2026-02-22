"""
ConfigManager - Portable JSON-based configuration for Collision Analytics.

Replaces QSettings storage with JSON files that travel with QGIS projects.
Provides backward compatibility with v1 QSettings.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from qgis.core import QgsProject
    from qgis.PyQt.QtCore import QSettings
    HAS_QGIS = True
except ImportError:
    QgsProject = None
    QSettings = None
    HAS_QGIS = False

# Import defaults from config module
from .config import DEFAULT_FIELD_MAP, DEFAULT_DECODES, FILTER_CONCEPTS


# Config file names
CONFIG_FILENAME = "collision_analytics_config.json"
FIELD_MAP_FILENAME = "field_maps.json"
DECODES_FILENAME = "decodes.json"
PROFILES_FILENAME = "profiles.json"

# Config format version
CONFIG_VERSION = "2.0.0"


@dataclass
class Profile:
    """Saved filter preset for common analyses."""
    name: str
    description: str = ""
    filters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "filters": self.filters
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        return cls(
            name=data.get("name", "Unnamed"),
            description=data.get("description", ""),
            filters=data.get("filters", {})
        )


@dataclass  
class Config:
    """Complete plugin configuration container."""
    version: str = CONFIG_VERSION
    metadata: Dict[str, Any] = field(default_factory=dict)
    field_map: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_FIELD_MAP))
    decodes: Dict[str, Dict[str, str]] = field(default_factory=lambda: copy.deepcopy(DEFAULT_DECODES))
    profiles: List[Profile] = field(default_factory=list)
    ui_preferences: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "metadata": self.metadata,
            "field_map": self.field_map,
            "decodes": self.decodes,
            "profiles": [p.to_dict() for p in self.profiles],
            "ui_preferences": self.ui_preferences,
            "performance": self.performance
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary (e.g., loaded JSON)."""
        config = cls()
        config.version = data.get("version", CONFIG_VERSION)
        config.metadata = data.get("metadata", {})
        
        # Merge with defaults for missing keys
        if "field_map" in data:
            config.field_map = {**dict(DEFAULT_FIELD_MAP), **data["field_map"]}
        
        if "decodes" in data:
            # Deep merge with defaults
            config.decodes = copy.deepcopy(DEFAULT_DECODES)
            for concept, mapping in data["decodes"].items():
                if isinstance(mapping, dict):
                    config.decodes[concept] = {str(k): str(v) for k, v in mapping.items()}
        
        if "profiles" in data:
            config.profiles = [
                Profile.from_dict(p) for p in data["profiles"] if isinstance(p, dict)
            ]
        
        config.ui_preferences = data.get("ui_preferences", {})
        config.performance = data.get("performance", {})
        
        return config


class ConfigManager:
    """
    Manages portable JSON-based configuration for Collision Analytics.
    
    Features:
    - Auto-discovers configs in QGIS project folders
    - Backward compatible with v1 QSettings
    - Supports separate file exports for team sharing
    - Human-readable JSON format
    """
    
    # QSettings keys for v1 backward compatibility
    SETTINGS_FIELD_MAP_KEY = "collision_analytics/field_map_json"
    SETTINGS_DECODES_KEY = "collision_analytics/decodes_json"
    SETTINGS_PROFILES_KEY = "collision_analytics/profiles_json"
    
    def __init__(self):
        self._config = Config()
        self._config_path: Optional[Path] = None
        self._project_path: Optional[Path] = None
        self._settings: Optional[Any] = None
        
        if HAS_QGIS:
            self._settings = QSettings()
            self._project_path = self._get_current_project_path()
            self._auto_load()
    
    # ------------------ Properties ------------------
    
    @property
    def field_map(self) -> Dict[str, str]:
        """Get current field mapping (concept -> layer field)."""
        return self._config.field_map
    
    @field_map.setter
    def field_map(self, value: Dict[str, str]) -> None:
        """Set field mapping."""
        self._config.field_map = dict(value)
    
    @property
    def decodes(self) -> Dict[str, Dict[str, str]]:
        """Get current decode tables (concept -> {code -> label})."""
        return self._config.decodes
    
    @property
    def profiles(self) -> List[Profile]:
        """Get saved filter profiles."""
        return self._config.profiles
    
    @property
    def ui_preferences(self) -> Dict[str, Any]:
        """Get UI preference settings."""
        return self._config.ui_preferences
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get config metadata."""
        return self._config.metadata
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Set config metadata."""
        self._config.metadata = dict(value)
    
    @property
    def config_path(self) -> Optional[Path]:
        """Get path to current config file (if loaded from JSON)."""
        return self._config_path
    
    @property
    def is_using_json_config(self) -> bool:
        """True if config was loaded from JSON file (not QSettings fallback)."""
        return self._config_path is not None and self._config_path.exists()
    
    # ------------------ Auto-discovery ------------------
    
    def _get_current_project_path(self) -> Optional[Path]:
        """Get the directory of the current QGIS project."""
        if not HAS_QGIS or QgsProject is None:
            return None
        try:
            project = QgsProject.instance()
            project_file = project.fileName()
            if project_file:
                return Path(project_file).parent
        except Exception:
            pass
        return None
    
    def _find_config_file(self, start_path: Optional[Path] = None, max_levels: int = 3) -> Optional[Path]:
        """
        Search for config file starting from start_path, then parent directories.
        
        Args:
            start_path: Directory to start search from (defaults to project path)
            max_levels: Maximum parent directories to search
            
        Returns:
            Path to config file if found, None otherwise
        """
        search_path = start_path or self._project_path
        if not search_path:
            return None
        
        current = Path(search_path)
        for _ in range(max_levels + 1):
            config_path = current / CONFIG_FILENAME
            if config_path.exists():
                return config_path
            parent = current.parent
            if parent == current:  # Reached root
                break
            current = parent
        
        return None
    
    def _auto_load(self) -> None:
        """Automatically load config from JSON or fall back to QSettings."""
        # Try to find and load JSON config
        json_path = self._find_config_file()
        if json_path:
            try:
                self.load_from_json(json_path)
                return
            except Exception:
                # Fall through to QSettings
                pass
        
        # Fall back to QSettings (v1 compatibility)
        self._load_from_qsettings()
    
    # ------------------ Load/Save ------------------
    
    def load_from_json(self, path: Path | str) -> None:
        """
        Load configuration from JSON file.
        
        Args:
            path: Path to JSON config file
        """
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._config = Config.from_dict(data)
        self._config_path = path
    
    def save_to_json(self, path: Optional[Path | str] = None) -> Path:
        """
        Save configuration to JSON file.
        
        Args:
            path: Path to save to (defaults to project folder + CONFIG_FILENAME)
            
        Returns:
            Path to saved file
        """
        if path is None:
            if self._config_path:
                path = self._config_path
            elif self._project_path:
                path = self._project_path / CONFIG_FILENAME
            else:
                raise ValueError("No path specified and no project path available")
        
        path = Path(path)
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Update metadata on save
        self._config.metadata.setdefault("last_modified", date.today().isoformat())
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._config_path = path
        return path
    
    def _load_from_qsettings(self) -> None:
        """Load configuration from QSettings (v1 backward compatibility)."""
        if not self._settings:
            self._config = Config()
            return
        
        # Load field map
        field_map_data = self._load_json_from_settings(self.SETTINGS_FIELD_MAP_KEY)
        if isinstance(field_map_data, dict):
            self._config.field_map = {**dict(DEFAULT_FIELD_MAP), **field_map_data}
        
        # Load decodes
        decodes_data = self._load_json_from_settings(self.SETTINGS_DECODES_KEY)
        if isinstance(decodes_data, dict):
            self._config.decodes = copy.deepcopy(DEFAULT_DECODES)
            for concept, mapping in decodes_data.items():
                if isinstance(mapping, dict):
                    self._config.decodes[concept] = {str(k): str(v) for k, v in mapping.items()}
        
        # Load profiles
        profiles_data = self._load_json_from_settings(self.SETTINGS_PROFILES_KEY)
        if isinstance(profiles_data, list):
            self._config.profiles = [
                Profile.from_dict(p) for p in profiles_data if isinstance(p, dict)
            ]
    
    def save(self) -> None:
        """
        Save configuration.
        
        If a JSON config path is set, saves to JSON.
        Otherwise saves to QSettings for backward compatibility.
        """
        if self._config_path or self._project_path:
            try:
                self.save_to_json()
                return
            except Exception:
                pass
        
        # Fall back to QSettings
        self._save_to_qsettings()
    
    def _save_to_qsettings(self) -> None:
        """Save configuration to QSettings (v1 backward compatibility)."""
        if not self._settings:
            return
        
        self._save_json_to_settings(self.SETTINGS_FIELD_MAP_KEY, self._config.field_map)
        self._save_json_to_settings(self.SETTINGS_DECODES_KEY, self._config.decodes)
        self._save_json_to_settings(
            self.SETTINGS_PROFILES_KEY, 
            [p.to_dict() for p in self._config.profiles]
        )
    
    def _load_json_from_settings(self, key: str) -> Any:
        """Helper to load JSON from QSettings."""
        if not self._settings:
            return None
        raw = self._settings.value(key, "")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    
    def _save_json_to_settings(self, key: str, value: Any) -> None:
        """Helper to save JSON to QSettings."""
        if not self._settings:
            return
        try:
            self._settings.setValue(key, json.dumps(value, ensure_ascii=False))
        except Exception:
            pass
    
    # ------------------ Reset ------------------
    
    def reset_to_defaults(self) -> None:
        """Reset all configuration to default values."""
        self._config = Config()
        self._config_path = None
    
    def reset_field_map(self) -> None:
        """Reset field mapping to defaults."""
        self._config.field_map = dict(DEFAULT_FIELD_MAP)
    
    def reset_decodes(self) -> None:
        """Reset decode tables to defaults."""
        self._config.decodes = copy.deepcopy(DEFAULT_DECODES)
    
    # ------------------ Profile Management ------------------
    
    def add_profile(self, profile: Profile) -> None:
        """Add a new filter profile."""
        self._config.profiles.append(profile)
    
    def remove_profile(self, name: str) -> bool:
        """Remove a profile by name. Returns True if found and removed."""
        for i, p in enumerate(self._config.profiles):
            if p.name == name:
                self._config.profiles.pop(i)
                return True
        return False
    
    def get_profile(self, name: str) -> Optional[Profile]:
        """Get a profile by name."""
        for p in self._config.profiles:
            if p.name == name:
                return p
        return None
    
    # ------------------ Decode Management ------------------
    
    def get_decode_mapping(self, concept: str) -> Dict[str, str]:
        """Get decode mapping for a concept."""
        return self._config.decodes.get(concept, {})
    
    def set_decode_mapping(self, concept: str, mapping: Dict[str, str]) -> None:
        """Set decode mapping for a concept."""
        self._config.decodes[concept] = {str(k): str(v) for k, v in mapping.items()}
    
    # ------------------ Import/Export for Sharing ------------------
    
    def export_field_maps(self, path: Path | str) -> None:
        """
        Export field maps to JSON for sharing with colleagues.
        
        Args:
            path: Path to export JSON file
        """
        path = Path(path)
        data = {
            "version": CONFIG_VERSION,
            "metadata": {
                "exported_by": self._config.metadata.get("created_by", ""),
                "export_date": date.today().isoformat(),
                "type": "field_maps"
            },
            "field_map": self._config.field_map
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def export_decodes(self, path: Path | str, concepts: Optional[List[str]] = None) -> None:
        """
        Export decode tables to JSON for sharing.
        
        Args:
            path: Path to export JSON file
            concepts: Optional list of concept keys to export (default: all)
        """
        path = Path(path)
        
        if concepts:
            decodes = {k: v for k, v in self._config.decodes.items() if k in concepts}
        else:
            decodes = self._config.decodes
        
        data = {
            "version": CONFIG_VERSION,
            "metadata": {
                "exported_by": self._config.metadata.get("created_by", ""),
                "export_date": date.today().isoformat(),
                "type": "decodes"
            },
            "decodes": decodes
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def export_profiles(self, path: Path | str, profile_names: Optional[List[str]] = None) -> None:
        """
        Export profiles to JSON for sharing.
        
        Args:
            path: Path to export JSON file
            profile_names: Optional list of profile names to export (default: all)
        """
        path = Path(path)
        
        if profile_names:
            profiles = [p for p in self._config.profiles if p.name in profile_names]
        else:
            profiles = self._config.profiles
        
        data = {
            "version": CONFIG_VERSION,
            "metadata": {
                "exported_by": self._config.metadata.get("created_by", ""),
                "export_date": date.today().isoformat(),
                "type": "profiles"
            },
            "profiles": [p.to_dict() for p in profiles]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def export_full_config(self, path: Path | str) -> None:
        """
        Export complete configuration to JSON.
        
        Args:
            path: Path to export JSON file
        """
        self.save_to_json(path)
    
    def import_field_maps(self, path: Path | str, merge: bool = True) -> Dict[str, str]:
        """
        Import field maps from JSON.
        
        Args:
            path: Path to import JSON file
            merge: If True, merge with existing; if False, replace
            
        Returns:
            The imported field map
        """
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported = data.get("field_map", {})
        
        if merge:
            self._config.field_map = {**self._config.field_map, **imported}
        else:
            self._config.field_map = imported
        
        return self._config.field_map
    
    def import_decodes(self, path: Path | str, merge: bool = True) -> Dict[str, Dict[str, str]]:
        """
        Import decode tables from JSON.
        
        Args:
            path: Path to import JSON file
            merge: If True, merge with existing; if False, replace
            
        Returns:
            The imported decodes
        """
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported = data.get("decodes", {})
        
        if merge:
            for concept, mapping in imported.items():
                if concept in self._config.decodes and isinstance(mapping, dict):
                    self._config.decodes[concept].update(mapping)
                else:
                    self._config.decodes[concept] = mapping
        else:
            self._config.decodes = imported
        
        return self._config.decodes
    
    def import_profiles(self, path: Path | str) -> List[Profile]:
        """
        Import profiles from JSON.
        
        Args:
            path: Path to import JSON file
            
        Returns:
            List of imported profiles
        """
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported = [Profile.from_dict(p) for p in data.get("profiles", [])]
        
        # Merge with existing, replacing duplicates by name
        existing_names = {p.name for p in self._config.profiles}
        self._config.profiles = [
            p for p in self._config.profiles 
            if p.name not in {ip.name for ip in imported}
        ]
        self._config.profiles.extend(imported)
        
        return imported
    
    def import_full_config(self, path: Path | str) -> None:
        """
        Import complete configuration from JSON.
        
        Args:
            path: Path to import JSON file
        """
        self.load_from_json(path)


# Singleton instance for plugin-wide access
_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the singleton ConfigManager instance."""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance


def reset_config_manager() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _config_manager_instance
    _config_manager_instance = None
