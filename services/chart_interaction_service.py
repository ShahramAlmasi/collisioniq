from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from ..core.utils import safe_str


def normalize_label_for_match(label: str) -> str:
    text = safe_str(label).replace("\n", " ")
    text = re.sub(r"\s*\(\s*[\d,]+\s*\)\s*$", "", text)
    return " ".join(text.split()).strip()


def resolve_codes_from_label(
    label: str,
    mapping: Dict[str, str],
    available_items: Sequence[Tuple[str, str]] | None = None,
) -> List[str]:
    if not mapping and not available_items:
        return []

    target = normalize_label_for_match(label)
    if not target:
        return []

    target_lower = target.lower()

    for code, decoded_label in mapping.items():
        if normalize_label_for_match(decoded_label).lower() == target_lower:
            return [code]

    for code, decoded_label in mapping.items():
        normalized = normalize_label_for_match(decoded_label).lower()
        if normalized.startswith(target_lower) or target_lower.startswith(normalized):
            return [code]

    for code, item_label in available_items or []:
        if normalize_label_for_match(item_label).lower() == target_lower:
            return [code]

    if target_lower in {"unknown", "unknown / blank", "unknown/blank", "blank"}:
        return [""]

    return []


def compute_updated_selection(
    current_selection: Iterable[str],
    available_codes: Iterable[str],
    target_codes: Iterable[str],
    additive: bool,
) -> Tuple[Set[str], bool]:
    available = {safe_str(code).strip() for code in available_codes}
    current = {safe_str(code).strip() for code in current_selection}
    targets = {safe_str(code).strip() for code in target_codes}
    matches = targets & available

    if not matches:
        return current, False

    updated = current | matches if additive else matches
    return updated, updated != current
