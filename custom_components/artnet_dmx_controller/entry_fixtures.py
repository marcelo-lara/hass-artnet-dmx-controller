"""Helpers for fixture data stored inside config entries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .channel_math import absolute_channel
from .const import (
    CONF_CHANNEL_COUNT,
    CONF_FIXTURE_ID,
    CONF_FIXTURE_TYPE,
    CONF_FIXTURES,
    CONF_NAME,
    CONF_START_CHANNEL,
)
from .fixture_mapping import HomeAssistantError


def build_fixture_config(
    fixture_type: str,
    start_channel: int,
    channel_count: int,
    name: str | None = None,
    fixture_id: str | None = None,
) -> dict[str, Any]:
    """Return normalized fixture config data."""
    fixture: dict[str, Any] = {
        CONF_FIXTURE_ID: fixture_id or uuid4().hex,
        CONF_FIXTURE_TYPE: fixture_type,
        CONF_START_CHANNEL: int(start_channel),
        CONF_CHANNEL_COUNT: int(channel_count),
    }
    if name:
        fixture[CONF_NAME] = name.strip()
    return fixture


def normalize_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config-entry data into the fixtures-list format."""
    normalized = dict(data)
    fixtures = normalized.get(CONF_FIXTURES)
    if isinstance(fixtures, list):
        normalized[CONF_FIXTURES] = [normalize_fixture(fixture) for fixture in fixtures]
        return normalized

    legacy_fixture_type = normalized.get(CONF_FIXTURE_TYPE)
    legacy_start_channel = normalized.get(CONF_START_CHANNEL)
    legacy_channel_count = normalized.get(CONF_CHANNEL_COUNT)
    legacy_name = normalized.get(CONF_NAME)
    normalized[CONF_FIXTURES] = []
    if legacy_fixture_type and legacy_start_channel and legacy_channel_count:
        normalized[CONF_FIXTURES] = [
            build_fixture_config(
                fixture_type=str(legacy_fixture_type),
                start_channel=int(legacy_start_channel),
                channel_count=int(legacy_channel_count),
                name=legacy_name if isinstance(legacy_name, str) else None,
                fixture_id="legacy",
            )
        ]
    normalized.pop(CONF_FIXTURE_TYPE, None)
    normalized.pop(CONF_START_CHANNEL, None)
    normalized.pop(CONF_CHANNEL_COUNT, None)
    return normalized


def normalize_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Normalize one fixture definition."""
    normalized = dict(fixture)
    normalized[CONF_FIXTURE_ID] = str(normalized.get(CONF_FIXTURE_ID) or uuid4().hex)
    normalized[CONF_FIXTURE_TYPE] = str(normalized[CONF_FIXTURE_TYPE])
    normalized[CONF_START_CHANNEL] = int(normalized[CONF_START_CHANNEL])
    normalized[CONF_CHANNEL_COUNT] = int(normalized[CONF_CHANNEL_COUNT])
    name = normalized.get(CONF_NAME)
    if isinstance(name, str):
        name = name.strip()
        if name:
            normalized[CONF_NAME] = name
        else:
            normalized.pop(CONF_NAME, None)
    else:
        normalized.pop(CONF_NAME, None)
    return normalized


def get_entry_fixtures(entry_or_data: Any) -> list[dict[str, Any]]:
    """Return normalized fixture list for a config entry or raw data."""
    data = entry_or_data.data if hasattr(entry_or_data, "data") else entry_or_data
    normalized = normalize_entry_data(data)
    return deepcopy(normalized.get(CONF_FIXTURES, []))


def fixture_label(fixture: dict[str, Any], fallback: str | None = None) -> str | None:
    """Return display label for a fixture."""
    return fixture.get(CONF_NAME) or fallback or fixture.get(CONF_FIXTURE_TYPE)


def validate_fixture_channels(fixture: dict[str, Any]) -> None:
    """Validate the channel range for one fixture."""
    absolute_channel(int(fixture[CONF_START_CHANNEL]), int(fixture[CONF_CHANNEL_COUNT]))


def validate_fixture_overlap(
    fixtures: list[dict[str, Any]],
    candidate: dict[str, Any],
    exclude_fixture_id: str | None = None,
) -> None:
    """Raise if candidate overlaps any sibling fixture."""
    candidate_start = int(candidate[CONF_START_CHANNEL])
    candidate_end = candidate_start + int(candidate[CONF_CHANNEL_COUNT]) - 1
    for fixture in fixtures:
        if fixture.get(CONF_FIXTURE_ID) == exclude_fixture_id:
            continue
        start = int(fixture[CONF_START_CHANNEL])
        end = start + int(fixture[CONF_CHANNEL_COUNT]) - 1
        if not (end < candidate_start or candidate_end < start):
            raise HomeAssistantError("channel_overlap")
