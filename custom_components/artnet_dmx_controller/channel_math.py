"""DMX channel math and value helpers.

Central helpers for computing absolute DMX channel addresses and validating
DMX channel/value ranges. Designed to be used by entity write paths and scene
apply logic.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    from homeassistant.exceptions import HomeAssistantError
except Exception:  # pragma: no cover - allow running tests outside HA
    class HomeAssistantError(Exception):
        """Fallback exception when Home Assistant isn't available."""


DMX_MIN = 1
DMX_MAX = 512
DMX_VALUE_MIN = 0
DMX_VALUE_MAX = 255


def absolute_channel(start_channel: int, offset: int) -> int:
    """Return absolute DMX channel for a fixture starting at `start_channel`.

    Calculation: absolute = start_channel + offset - 1
    Raises HomeAssistantError if result is outside 1..512.
    """
    if not isinstance(start_channel, int) or not isinstance(offset, int):
        raise HomeAssistantError("start_channel and offset must be integers")
    abs_ch = start_channel + offset - 1
    if abs_ch < DMX_MIN or abs_ch > DMX_MAX:
        raise HomeAssistantError(f"Computed DMX channel {abs_ch} out of range ({DMX_MIN}..{DMX_MAX})")
    return abs_ch


def validate_dmx_value(value: int) -> int:
    """Validate a DMX channel value is in 0..255 and return it.

    Raises HomeAssistantError on invalid input.
    """
    if not isinstance(value, int):
        raise HomeAssistantError("DMX value must be an integer")
    if value < DMX_VALUE_MIN or value > DMX_VALUE_MAX:
        raise HomeAssistantError(f"DMX value {value} out of range ({DMX_VALUE_MIN}..{DMX_VALUE_MAX})")
    return value


def clamp_dmx_value(value: int) -> int:
    """Clamp a given value to 0..255 and return the clamped value."""
    try:
        iv = int(value)
    except Exception:
        raise HomeAssistantError("DMX value must be an integer-like")
    if iv < DMX_VALUE_MIN:
        return DMX_VALUE_MIN
    if iv > DMX_VALUE_MAX:
        return DMX_VALUE_MAX
    return iv


def value_from_label(value_map: Dict[Any, Any], label: str) -> int:
    """Given a mapping of numeric/string keys to labels, return the numeric value for `label`.

    Example mapping in JSON: {"0": "Off", "255": "On"}
    Returns int key corresponding to the given label, raises HomeAssistantError if not found.
    """
    for k, v in value_map.items():
        if v == label:
            try:
                return int(k)
            except Exception:
                raise HomeAssistantError(f"Invalid numeric key in value_map: {k}")
    raise HomeAssistantError(f"Label '{label}' not found in value_map")


def label_from_value(value_map: Dict[Any, Any], value: int) -> Optional[str]:
    """Return label for numeric `value` if present in `value_map`, else None."""
    sval = str(value)
    if sval in value_map:
        return value_map[sval]
    # fallback: try integer keys
    for k, v in value_map.items():
        try:
            if int(k) == value:
                return v
        except Exception:
            continue
    return None


__all__ = [
    "absolute_channel",
    "validate_dmx_value",
    "clamp_dmx_value",
    "value_from_label",
    "label_from_value",
]
