from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Avoid circular imports at module level
if TYPE_CHECKING:
    from .config_manager import ConfigManager

# ----------------------------
# Concept -> layer field mapping (defaults)
# ----------------------------
DEFAULT_FIELD_MAP = {
    "date": "report_date",
    "municipality": "municipality",
    "accident_class": "accident_class",
    "accident_location": "accident_location",
    "impact_location": "impact_location",
    "impact_type": "impact_type",
    "light": "light",
    "traffic_control": "traffic_control",
    "traffic_control_condition": "traffic_control_condition",
    "road_jurisdiction": "road_jurisdiction",
    "env1": "environment_condition_1",
    "env2": "environment_condition_2",
    "location_id": "location_id",
    "location_type": "location_type",
    "map_x": "map_x",
    "map_y": "map_y",
    "veh_cnt": "involved_vehicles_cnt",
    "ped_cnt": "involved_pedestrians_cnt",
    "occ_cnt": "involved_occupants_cnt",
    "drv_cnt": "involved_drivers_cnt",
    "per_cnt": "involved_persons_cnt",
}

# ----------------------------
# Default decode tables (concept -> {raw_code -> label})
# ----------------------------
DEFAULT_DECODES = {
    "location_type": {"mri": "Intersection", "mrs": "Road segment"},
    "municipality": {
        "CL": "Clarington", "WH": "Whitby", "OA": "Oshawa", "UX": "Uxbridge",
        "SC": "Scugog", "AJ": "Ajax", "PI": "Pickering", "BR": "Brock",
    },
    "env1": {
        "1": "Clear", "2": "Rain", "3": "Snow", "4": "Freezing rain / hail",
        "5": "Drifting snow", "6": "Strong wind", "7": "Fog / mist / smoke / dust",
        "8": "Glare", "99": "Other",
    },
    "env2": {
        "1": "Clear", "2": "Rain", "3": "Snow", "4": "Freezing rain / hail",
        "5": "Drifting snow", "6": "Strong wind", "7": "Fog / mist / smoke / dust",
        "8": "Glare", "99": "Other",
    },
    "accident_location": {
        "1": "Non Intersection",
        "2": "Intersection related",
        "30": "Four-way",
        "31": "Offset",
        "32": "L intersection",
        "33": "Y intersection",
        "34": "T intersection",
        "35": "Roundabout",
        "97": "Other intersection",
        "4": "At/near private drive",
        "5": "At railway crossing",
        "6": "Underpass or tunnel",
        "7": "Overpass or bridge",
        "8": "Trail",
        "9": "Frozen lake or river",
        "10": "Parking lot",
        "11": "Turnaround",
        "12": "Service centre",
        "13": "Truck inspection station",
        "14": "Rest area",
        "98": "Other on highway",
        "99": "Other off highway"
        },
    "impact_location": {
        "1": "Within intersection",
        "2": "Through",
        "3": "Left turn",
        "4": "Right turn",
        "5": "Right turn channel",
        "6": "Two-way left turn",
        "7": "Passing",
        "8": "Shoulder-Left",
        "9": "Shoulder-Right",
        "10": "Not on roadway left side",
        "11": "Not on roadway right side",
        "12": "Off highway",
        "13": "Gore/bullnose",
        "14": "Crossover",
        "15": "Crosswalk",
        "16": "School crossing",
        "17": "Sidewalk",
        "18": "High occupancy toll (HOT)",
        "19": "High occupancy vehicle (HOV)",
        "20": "Bicycle (unprotected)",
        "21": "Bicycle (protected)",
        "22": "Transit",
        "23": "Parking",
        "24": "Speed change",
        "25": "Bus bypass",
        "99": "Other"
        },
    "impact_type": {
        "1": "Approaching head-on",
        "2": "Angle",
        "3": "Rear end",
        "4": "Sideswipe",
        "5": "Turning movement",
        "6": "Single motor vehicle unattended",
        "7": "Single motor vehicle other",
        "8": "Reversing",
        "40": "Sideswipe - Same direction",
        "41": "Sideswipe - Opposite direction",
        "99": "Other"
        },
    "light": {
        "1": "Daylight",
        "2": "Daylight-artificial",
        "3": "Dawn",
        "4": "Dawn-artificial",
        "5": "Dusk",
        "6": "Dusk-artificial",
        "7": "Dark",
        "8": "Dark-artificial",
        "99": "Other",
    },
    "traffic_control": {
        "1": "Traffic signal",
        "2": "Stop sign",
        "3": "Yield sign",
        "4": "Pedestrian crossover",
        "5": "Police control",
        "6": "School guard",
        "7": "School bus flashing light and stop arm",
        "8": "Traffic gate",
        "9": "Traffic control person",
        "10": "No control",
        "11": "Flashing beacon",
        "12": "Railway crossing",
        "13": "Pedestrian signal",
        "14": "Half signal",
        "99": "Other",
    },
    "traffic_control_condition": {
        "1": "Functioning",
        "2": "Non-functioning",
        "3": "Obscured",
        "4": "Missing/Damaged",
    },
    "road_jurisdiction": {
        "1": "Municipal (excl. Twp. Rd.)",
        "2": "Provincial highway",
        "3": "Township",
        "4": "County or district",
        "5": "Regional municipality",
        "6": "Private property",
        "7": "Federal",
        "99": "Other",
    },
    "accident_class": {
        "1": "Fatal",
        "2": "Injury",
        "3": "PDO",
        "4": "Unknown",
    },
}

FILTER_CONCEPTS = [
    ("municipality", "Municipality"),
    ("road_jurisdiction", "Road jurisdiction"),
    ("accident_class", "Accident class"),
    ("accident_location", "Accident location"),
    ("location_type", "Location type"),
    ("impact_type", "Impact type"),
    ("impact_location", "Impact location"),
    ("light", "Lighting"),
    ("traffic_control", "Traffic control"),
    ("traffic_control_condition", "Traffic control condition"),
    ("env1", "Environment condition 1"),
    ("env2", "Environment condition 2"),
]

# Legacy settings keys for backward compatibility
SETTINGS_FIELD_MAP_KEY = "collision_analytics/field_map_json"
SETTINGS_DECODES_KEY = "collision_analytics/decodes_json"
SETTINGS_PROFILES_KEY = "collision_analytics/profiles_json"


# ----------------------------
# v2 ConfigManager Integration
# ----------------------------

_lazy_config_manager: Optional["ConfigManager"] = None


def _get_config_manager() -> "ConfigManager":
    """Lazy initialization of ConfigManager singleton."""
    global _lazy_config_manager
    if _lazy_config_manager is None:
        from .config_manager import get_config_manager
        _lazy_config_manager = get_config_manager()
    return _lazy_config_manager


def get_field_map() -> Dict[str, str]:
    """
    Get current field mapping (concept -> layer field).
    
    Returns field map from ConfigManager (JSON config if available,
    otherwise falls back to QSettings).
    """
    return _get_config_manager().field_map


def set_field_map(field_map: Dict[str, str]) -> None:
    """
    Set field mapping.
    
    Updates the ConfigManager and saves to JSON (if available)
    or QSettings for backward compatibility.
    """
    _get_config_manager().field_map = field_map
    _get_config_manager().save()


def get_decodes() -> Dict[str, Dict[str, str]]:
    """
    Get current decode tables (concept -> {code -> label}).
    
    Returns decodes from ConfigManager.
    """
    return _get_config_manager().decodes


def get_decode_mapping(concept: str) -> Dict[str, str]:
    """
    Get decode mapping for a specific concept.
    
    Args:
        concept: Concept key (e.g., "municipality", "accident_class")
        
    Returns:
        Dictionary mapping raw codes to labels
    """
    return _get_config_manager().get_decode_mapping(concept)


def set_decode_mapping(concept: str, mapping: Dict[str, str]) -> None:
    """
    Set decode mapping for a specific concept.
    
    Args:
        concept: Concept key
        mapping: Dictionary mapping raw codes to labels
    """
    _get_config_manager().set_decode_mapping(concept, mapping)
    _get_config_manager().save()


def save_config() -> None:
    """Save current configuration to JSON or QSettings."""
    _get_config_manager().save()


def reset_config_to_defaults() -> None:
    """Reset all configuration to default values."""
    _get_config_manager().reset_to_defaults()
    _get_config_manager().save()


def reset_field_map_to_defaults() -> None:
    """Reset field mapping to default values."""
    _get_config_manager().reset_field_map()
    _get_config_manager().save()


def reset_decodes_to_defaults() -> None:
    """Reset decode tables to default values."""
    _get_config_manager().reset_decodes()
    _get_config_manager().save()


# ----------------------------
# Import/Export for Sharing
# ----------------------------

def export_field_maps(path: Path | str, field_map: Optional[Dict[str, str]] = None) -> None:
    """
    Export field maps to JSON for sharing with colleagues.
    
    Args:
        path: Path to export JSON file
        field_map: Optional field map to export (defaults to current config)
    """
    if field_map is not None:
        # Create temporary export with provided field map
        from .config_manager import ConfigManager
        temp_mgr = ConfigManager()
        temp_mgr.field_map = field_map
        temp_mgr.export_field_maps(path)
    else:
        _get_config_manager().export_field_maps(path)


def export_decodes(path: Path | str, concepts: Optional[List[str]] = None) -> None:
    """
    Export decode tables to JSON for sharing.
    
    Args:
        path: Path to export JSON file
        concepts: Optional list of concept keys to export (default: all)
    """
    _get_config_manager().export_decodes(path, concepts)


def export_profiles(path: Path | str, profile_names: Optional[List[str]] = None) -> None:
    """
    Export saved filter profiles to JSON for sharing.
    
    Args:
        path: Path to export JSON file
        profile_names: Optional list of profile names to export (default: all)
    """
    _get_config_manager().export_profiles(path, profile_names)


def export_full_config(path: Path | str) -> None:
    """
    Export complete configuration to JSON.
    
    Args:
        path: Path to export JSON file
    """
    _get_config_manager().export_full_config(path)


def import_field_maps(path: Path | str, merge: bool = True) -> Dict[str, str]:
    """
    Import field maps from JSON.
    
    Args:
        path: Path to import JSON file
        merge: If True, merge with existing; if False, replace
        
    Returns:
        The imported field map
    """
    result = _get_config_manager().import_field_maps(path, merge)
    _get_config_manager().save()
    return result


def import_decodes(path: Path | str, merge: bool = True) -> Dict[str, Dict[str, str]]:
    """
    Import decode tables from JSON.
    
    Args:
        path: Path to import JSON file
        merge: If True, merge with existing; if False, replace
        
    Returns:
        The imported decodes
    """
    result = _get_config_manager().import_decodes(path, merge)
    _get_config_manager().save()
    return result


def import_profiles(path: Path | str) -> List[Any]:
    """
    Import profiles from JSON.
    
    Args:
        path: Path to import JSON file
        
    Returns:
        List of imported profiles
    """
    from .config_manager import Profile
    result = _get_config_manager().import_profiles(path)
    _get_config_manager().save()
    return result


def import_full_config(path: Path | str) -> None:
    """
    Import complete configuration from JSON.
    
    Args:
        path: Path to import JSON file
    """
    _get_config_manager().import_full_config(path)


# ----------------------------
# Backward Compatibility Helpers
# ----------------------------

def load_field_map_from_settings(settings) -> Dict[str, str]:
    """
    Legacy helper: Load field map from QSettings.
    
    New code should use get_field_map() instead.
    """
    raw = settings.value(SETTINGS_FIELD_MAP_KEY, "")
    if not raw:
        return dict(DEFAULT_FIELD_MAP)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return {str(k): str(v) for k, v in obj.items()}
    except Exception:
        pass
    return dict(DEFAULT_FIELD_MAP)


def save_field_map_to_settings(settings, field_map: Dict[str, str]) -> None:
    """
    Legacy helper: Save field map to QSettings.
    
    New code should use set_field_map() or save_config() instead.
    """
    try:
        settings.setValue(SETTINGS_FIELD_MAP_KEY, json.dumps(field_map, ensure_ascii=False))
    except Exception:
        pass


def load_decodes_from_settings(settings) -> Dict[str, Dict[str, str]]:
    """
    Legacy helper: Load decodes from QSettings.
    
    New code should use get_decodes() instead.
    """
    raw = settings.value(SETTINGS_DECODES_KEY, "")
    if not raw:
        return copy.deepcopy(DEFAULT_DECODES)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            result = copy.deepcopy(DEFAULT_DECODES)
            for k, v in obj.items():
                if isinstance(v, dict):
                    result[str(k)] = {str(code): str(label) for code, label in v.items()}
            return result
    except Exception:
        pass
    return copy.deepcopy(DEFAULT_DECODES)


def save_decodes_to_settings(settings, decodes: Dict[str, Dict[str, str]]) -> None:
    """
    Legacy helper: Save decodes to QSettings.
    
    New code should use set_decode_mapping() or save_config() instead.
    """
    try:
        settings.setValue(SETTINGS_DECODES_KEY, json.dumps(decodes, ensure_ascii=False))
    except Exception:
        pass


# ----------------------------
# Config Status
# ----------------------------

def get_config_info() -> Dict[str, Any]:
    """
    Get information about current configuration.
    
    Returns:
        Dictionary with config status info including:
        - is_using_json_config: Whether loaded from JSON file
        - config_path: Path to JSON config file (if applicable)
        - version: Config format version
        - metadata: Config metadata
    """
    mgr = _get_config_manager()
    return {
        "is_using_json_config": mgr.is_using_json_config,
        "config_path": str(mgr.config_path) if mgr.config_path else None,
        "version": mgr._config.version,
        "metadata": mgr.metadata,
    }
