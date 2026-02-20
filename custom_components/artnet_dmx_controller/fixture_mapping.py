"""
Fixture mapping loader and validator.

Loads `fixture_mapping.json`, validates schema strictly, and caches the parsed
structure for runtime use by the integration.

Provides `load_fixture_mapping(file_path=None)` which raises `HomeAssistantError`
with clear messages on error conditions.
"""
from __future__ import annotations

import json
import os
from typing import Any

try:
    from homeassistant.exceptions import HomeAssistantError
except Exception:  # pragma: no cover - allow running tests outside HA
    class HomeAssistantError(Exception):
        """Fallback exception when Home Assistant isn't available."""

_CACHE: dict[str, Any] | None = None


def _default_path() -> str:
    return os.path.join(os.path.dirname(__file__), "fixture_mapping.json")


def load_fixture_mapping(file_path: str | None = None) -> dict[str, Any]:
    """
    Load and validate fixture mapping JSON.

    If `file_path` is omitted, the bundled `fixture_mapping.json` is used.
    Returns the parsed mapping dictionary.
    Raises `HomeAssistantError` with clear messages on failure.
    """
    global _CACHE
    if file_path is None:
        file_path = _default_path()

    abs_path = os.path.abspath(file_path)
    if _CACHE is not None and _CACHE.get("path") == abs_path:
        return _CACHE["mapping"]

    if not os.path.exists(abs_path):
        raise HomeAssistantError(f"Fixture mapping file not found: {abs_path}")

    try:
        with open(abs_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as err:
        raise HomeAssistantError(f"Malformed JSON in fixture mapping file {abs_path}: {err}") from err
    except Exception as err:  # pragma: no cover - unexpected I/O errors
        raise HomeAssistantError(f"Error reading fixture mapping file {abs_path}: {err}") from err

    _validate_fixture_mapping(data)
    _CACHE = {"path": abs_path, "mapping": data}
    return data


def _validate_fixture_mapping(data: Any) -> None:
    """Validate the fixture mapping structure and raise `HomeAssistantError` on problems."""
    if not isinstance(data, dict):
        raise HomeAssistantError("Fixture mapping must be a JSON object at top level")

    fixtures = data.get("fixtures")
    if not isinstance(fixtures, dict):
        raise HomeAssistantError("Missing or invalid 'fixtures' object in fixture mapping")

    for fixture_key, fixture_def in fixtures.items():
        if not isinstance(fixture_def, dict):
            raise HomeAssistantError(f"Fixture '{fixture_key}' definition must be an object")

        if "fixture_specie" not in fixture_def:
            raise HomeAssistantError(f"Fixture '{fixture_key}' missing required 'fixture_specie'")

        if "channel_count" not in fixture_def:
            raise HomeAssistantError(f"Fixture '{fixture_key}' missing required 'channel_count'")
        channel_count = fixture_def["channel_count"]
        if not isinstance(channel_count, int) or channel_count <= 0:
            raise HomeAssistantError(f"Fixture '{fixture_key}' has invalid 'channel_count' (must be positive integer)")

        if "channels" not in fixture_def:
            raise HomeAssistantError(f"Fixture '{fixture_key}' missing required 'channels' array")
        channels = fixture_def["channels"]
        if not isinstance(channels, list):
            raise HomeAssistantError(f"Fixture '{fixture_key}' 'channels' must be an array")

        seen_offsets: set[int] = set()
        for idx, ch in enumerate(channels):
            if not isinstance(ch, dict):
                raise HomeAssistantError(f"Fixture '{fixture_key}' channel at index {idx} must be an object")
            for required in ("name", "offset", "description"):
                if required not in ch:
                    raise HomeAssistantError(
                        f"Fixture '{fixture_key}' channel at index {idx} missing required '{required}'"
                    )

            offset = ch["offset"]
            if not isinstance(offset, int) or offset < 1 or offset > channel_count:
                raise HomeAssistantError(
                    f"Fixture '{fixture_key}' channel '{ch.get('name', '?')}' has invalid offset {offset} (must be 1..{channel_count})"
                )
            if offset in seen_offsets:
                raise HomeAssistantError(f"Fixture '{fixture_key}' duplicate channel offset {offset}")
            seen_offsets.add(offset)

            if "value_map" in ch and not isinstance(ch["value_map"], dict):
                raise HomeAssistantError(
                    f"Fixture '{fixture_key}' channel '{ch.get('name')}' 'value_map' must be an object"
                )
            if "hidden_by_default" in ch and not isinstance(ch["hidden_by_default"], bool):
                raise HomeAssistantError(
                    f"Fixture '{fixture_key}' channel '{ch.get('name')}' 'hidden_by_default' must be boolean"
                )


__all__ = ["HomeAssistantError", "load_fixture_mapping"]


def clear_fixture_mapping_cache() -> None:
    """
    Clear the internal fixture mapping cache.

    Useful for tests that need to force a reload of the mapping file.
    """
    global _CACHE
    _CACHE = None

__all__.append("clear_fixture_mapping_cache")
